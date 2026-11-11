"""能力框架调用方迁移回归 — 新闻调用方（stock_news_cn）

覆盖 4 处调用方从 AKShareProvider.get_stock_news_sync 直调改为
query_capability_sync("stock_news_cn") 后的消费者行为：
1. realtime_news.RealtimeNewsAggregator._get_chinese_finance_news：
   标准列消费（title/content/media_source/url）、publish_time 补时区、
   时效过滤、美股代码跳过、None/空 df 防御
2. realtime_news.get_realtime_stock_news：A股主路径走能力 + 港股备用
   路径走能力（聚合器空结果后兜底）
3. agent_utils.Toolkit.get_stock_news_unified：东财新闻段落标准列格式化

patch 方式：调用方均为函数内 import（from tradingagents.dataflows.capability
import query_capability_sync），运行时按 capability 包命名空间查找，
monkeypatch 包属性即可生效。RSS/Google 等外围网络点一并 patch 短路。
"""

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import pandas as pd

import tradingagents.dataflows.capability as capability_pkg
import tradingagents.dataflows.interface as interface_mod
from tradingagents.dataflows.news.realtime_news import (
    RealtimeNewsAggregator,
    get_realtime_stock_news,
)

TZ = ZoneInfo("Asia/Shanghai")


def _news_row(title, hours_ago=1.0, media_source="东方财富", content="", url=""):
    return {
        "title": title,
        "content": content,
        "summary": "",
        "url": url,
        "media_source": media_source,
        "publish_time": datetime.now(TZ) - timedelta(hours=hours_ago),
    }


def _std_news_df():
    return pd.DataFrame(
        [
            _news_row("贵州茅台发布三季报", media_source="新浪财经",
                      content="营收增长", url="https://example.com/1"),
            _news_row("白酒板块盘中拉升", media_source=""),
        ]
    )


def _patch_capability(monkeypatch, df=None, error=None):
    calls = []

    def _stub(capability_id, **params):
        calls.append({"capability_id": capability_id, **params})
        if error is not None:
            raise error
        return df

    monkeypatch.setattr(capability_pkg, "query_capability_sync", _stub)
    return calls


def _patch_rss_empty(monkeypatch):
    monkeypatch.setattr(
        RealtimeNewsAggregator,
        "_parse_rss_feed",
        lambda self, rss_url, ticker, hours_back: [],
    )


# ---------------------------------------------------------------- _get_chinese_finance_news


def test_chinese_finance_news_maps_standard_fields(monkeypatch):
    """标准列消费：title/content/media_source/url 透传 + naive 补时区 + 空媒体源保底"""
    calls = _patch_capability(monkeypatch, df=_std_news_df())
    _patch_rss_empty(monkeypatch)

    items = RealtimeNewsAggregator()._get_chinese_finance_news("600519.SH", 24)

    assert len(items) == 2
    assert items[0].title == "贵州茅台发布三季报"
    assert items[0].content == "营收增长"
    assert items[0].source == "新浪财经"  # media_source 语义保留
    assert items[0].url == "https://example.com/1"
    assert items[0].publish_time.tzinfo is not None  # naive datetime 补时区
    assert items[1].source == "东方财富"  # 空媒体源保底
    assert calls[0]["capability_id"] == "stock_news_cn"
    assert calls[0]["symbol"] == "600519"
    assert calls[0]["hours_back"] == 24


def test_chinese_finance_news_filters_stale(monkeypatch):
    """时效过滤：hours_back 窗口外的新闻被跳过"""
    df = pd.DataFrame(
        [
            _news_row("新鲜新闻", hours_ago=1.0),
            _news_row("过期新闻", hours_ago=10.0),
        ]
    )
    _patch_capability(monkeypatch, df=df)
    _patch_rss_empty(monkeypatch)

    items = RealtimeNewsAggregator()._get_chinese_finance_news("600519.SH", 6)

    assert [i.title for i in items] == ["新鲜新闻"]


def test_chinese_finance_news_skips_us_ticker(monkeypatch):
    """美股代码跳过东财路径（能力不被调用）"""
    calls = _patch_capability(monkeypatch, df=_std_news_df())
    _patch_rss_empty(monkeypatch)

    items = RealtimeNewsAggregator()._get_chinese_finance_news("AAPL.US", 24)

    assert calls == []
    assert items == []


def test_chinese_finance_news_none_and_error_defense(monkeypatch):
    """能力返回 None / 抛异常 -> 东财 0 条不炸（RSS 被短路后整体为空）"""
    _patch_capability(monkeypatch, df=None)
    _patch_rss_empty(monkeypatch)
    items = RealtimeNewsAggregator()._get_chinese_finance_news("600519.SH", 24)
    assert items == []

    calls = _patch_capability(monkeypatch, error=RuntimeError("网络中断"))
    _patch_rss_empty(monkeypatch)
    items = RealtimeNewsAggregator()._get_chinese_finance_news("600519.SH", 24)
    assert items == []
    assert calls[0]["capability_id"] == "stock_news_cn"


# ---------------------------------------------------------------- get_realtime_stock_news


def test_realtime_stock_news_a_share_uses_capability(monkeypatch):
    """A股主路径：走能力 stock_news_cn 并生成东财新闻报告"""
    calls = _patch_capability(monkeypatch, df=_std_news_df())

    report = get_realtime_stock_news("600519.SH", "2024-10-25")

    assert "东方财富新闻报告" in report
    assert "贵州茅台发布三季报" in report
    assert calls and calls[0]["symbol"] == "600519"
    assert calls[0]["limit"] == 10


def test_realtime_stock_news_hk_fallback_uses_capability(monkeypatch):
    """港股备用路径：聚合器空结果后走能力 stock_news_cn"""
    calls = _patch_capability(monkeypatch, df=_std_news_df())
    monkeypatch.setattr(
        RealtimeNewsAggregator,
        "get_realtime_stock_news",
        lambda self, ticker, hours_back=6, max_news=10: [],
    )

    report = get_realtime_stock_news("00700.HK", "2024-10-25")

    assert "东方财富新闻报告" in report
    assert calls and calls[0]["symbol"] == "00700"


# ---------------------------------------------------------------- agent_utils


def test_agent_utils_unified_news_uses_capability(monkeypatch):
    """统一新闻工具：东财段落走能力标准列，Google 段落被 patch 短路"""
    from tradingagents.agents.utils.agent_utils import Toolkit

    calls = _patch_capability(monkeypatch, df=_std_news_df())
    monkeypatch.setattr(interface_mod, "get_google_news", lambda query, date: "google-stub")

    result = Toolkit.get_stock_news_unified.invoke(
        {"ticker": "600519", "curr_date": "2024-10-25"}
    )

    assert "## 东方财富新闻" in result
    assert "**贵州茅台发布三季报**" in result
    assert "google-stub" in result
    assert calls and calls[0]["capability_id"] == "stock_news_cn"
    assert calls[0]["limit"] == 10
