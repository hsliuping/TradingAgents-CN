"""数据能力注册机制 — A股个股新闻能力测试（stock_news_cn）

stock_news_cn（个股新闻条目事件流，GRAIN_STOCK_EVENT 粒度）双源：
tushare 委托高层 get_stock_news（多源轮询/权限检测，付费无权限返回
None 经门面降级），akshare 委托高层 get_stock_news（重试/Docker
curl_cffi 回退）。两源高层方法均输出结构化 Dict 列表，适配器仅包装
为 DataFrame。

媒体源命名约定：新闻条目自带媒体来源（source），与门面附加的数据
来源标记列 source 冲突——两源均注册 field_mapping
{"source": "media_source"} 前置改名（rename 发生在门面附加 source
之前），媒体源语义无损保留。本文件覆盖：
1. 注册健全性：源集合 + grain + 参数签名机器校验 + field_mapping
   目标合法性（source -> media_source 必须是标准字段）
2. schema 字段基准（12 字段，防漂移）
3. 双源适配器契约：不可用/异常/None -> None 降级；空列表 -> 空
   DataFrame 不降级；参数透传；akshare 忽略 hours_back
4. facade 真实能力全链路：媒体源改名（media_source 保留 + 门面
   source 覆盖为 provider 名）+ tushare->akshare 降级链 +
   query_capability_sync 同步路径

设计文档：docs/05-design/v4.0/data-architecture-problems-and-optimization.md 5.4
"""

import asyncio
import inspect
import logging

import pandas as pd

import tradingagents.dataflows.providers.china.akshare  # noqa: F401 —— import 即注册 akshare 源
import tradingagents.dataflows.providers.china.tushare  # noqa: F401 —— import 即注册 tushare 源
from tradingagents.dataflows.capability import query_capability_sync
from tradingagents.dataflows.capability.facade import get_data_facade
from tradingagents.dataflows.capability.registry import registry
from tradingagents.dataflows.capability.schema import GRAIN_STOCK_EVENT

EXPECTED_SOURCES = {"stock_news_cn": {"tushare", "akshare"}}
EXPECTED_GRAIN = {"stock_news_cn": GRAIN_STOCK_EVENT}

# 标准字段集合基准（对齐两源高层方法共同输出命名，防 schema 漂移）
STANDARD_FIELDS = {
    "title", "content", "summary", "url", "media_source", "author",
    "publish_time", "category", "sentiment", "sentiment_score",
    "keywords", "importance",
}

# 双源 field_mapping 基准（媒体源前置改名，防映射漂移）
NEWS_FIELD_MAPPING = {"source": "media_source"}


def _fixed_order(monkeypatch, order):
    from tradingagents.dataflows.capability import facade as facade_mod

    monkeypatch.setattr(
        facade_mod.CapabilityHandle,
        "_resolve_source_order",
        lambda self, registered: [s for s in order if s in registered],
    )


def _news_payload():
    """两源高层 get_stock_news 共同输出形态（结构化 Dict 列表，publish_time 降序）"""
    return [
        {
            "title": "贵州茅台发布三季报",
            "content": "营收净利润双增长……",
            "summary": "营收净利润双增长",
            "url": "https://example.com/news/1",
            "source": "新浪财经",
            "author": "",
            "publish_time": pd.Timestamp("2024-10-25 09:30:00"),
            "category": "财报",
            "sentiment": "positive",
            "sentiment_score": 0.8,
            "keywords": ["茅台", "三季报"],
            "importance": "high",
        },
        {
            "title": "白酒板块盘中拉升",
            "content": "",
            "summary": "",
            "url": "",
            "source": "东方财富",
            "author": "",
            "publish_time": pd.Timestamp("2024-10-25 10:15:00"),
            "category": "行情",
            "sentiment": "neutral",
            "sentiment_score": float("nan"),
            "keywords": [],
            "importance": "medium",
        },
    ]


def _make_tushare_stub(monkeypatch, news=None, error=None):
    """构造跳过 __init__ 的 TushareProvider 桩，get_stock_news 返回预设载荷"""
    from tradingagents.dataflows.providers.china.tushare import TushareProvider

    monkeypatch.setattr(TushareProvider, "is_available", lambda self: True)
    calls = []

    async def _stub(self, symbol, limit=10, hours_back=24):
        calls.append({"symbol": symbol, "limit": limit, "hours_back": hours_back})
        if error is not None:
            raise error
        return news

    monkeypatch.setattr(TushareProvider, "get_stock_news", _stub)
    provider = TushareProvider.__new__(TushareProvider)
    provider.api = None
    provider.logger = logging.getLogger("test-stub-tushare")
    return provider, calls


def _make_akshare_stub(monkeypatch, news=None, error=None):
    """构造跳过 __init__ 的 AKShareProvider 桩，get_stock_news 返回预设载荷"""
    from tradingagents.dataflows.providers.china.akshare import AKShareProvider

    monkeypatch.setattr(AKShareProvider, "is_available", lambda self: True)
    calls = []

    async def _stub(self, symbol, limit=10):
        calls.append({"symbol": symbol, "limit": limit})
        if error is not None:
            raise error
        return news

    monkeypatch.setattr(AKShareProvider, "get_stock_news", _stub)
    provider = AKShareProvider.__new__(AKShareProvider)
    provider.logger = logging.getLogger("test-stub-akshare")
    return provider, calls


def _patch_factories(monkeypatch, tushare_provider=None, akshare_provider=None):
    from tradingagents.dataflows.capability import facade as facade_mod

    if tushare_provider is not None:
        monkeypatch.setitem(
            facade_mod._PROVIDER_FACTORIES, "tushare", lambda: tushare_provider
        )
    if akshare_provider is not None:
        monkeypatch.setitem(
            facade_mod._PROVIDER_FACTORIES, "akshare", lambda: akshare_provider
        )


# ---------------------------------------------------------------- 注册健全性


def test_registration_sanity():
    """源集合 + grain + Schema 参数被 provider 方法签名接受 + 映射目标合法性"""
    for cap_id, expected in EXPECTED_SOURCES.items():
        assert set(registry.get_sources(cap_id)) == expected, cap_id
        for source in sorted(registry.get_sources(cap_id)):
            entry = registry.get_entry(cap_id, source)
            assert entry.schema.grain == EXPECTED_GRAIN[cap_id], cap_id
            func_params = set(inspect.signature(entry.func).parameters)
            for param in entry.schema.params:
                assert param.name in func_params, f"{cap_id}/{source} 缺参数 {param.name}"
            assert set(entry.field_mapping.values()) <= set(
                entry.schema.standard_field_names()
            ), cap_id


def test_schema_standard_fields_baseline():
    """标准字段集合与 field_mapping 对齐基准（防漂移）"""
    entry = registry.get_entry("stock_news_cn", "tushare")
    assert set(entry.schema.standard_field_names()) == STANDARD_FIELDS
    assert entry.field_mapping == NEWS_FIELD_MAPPING
    ak_entry = registry.get_entry("stock_news_cn", "akshare")
    assert ak_entry.field_mapping == NEWS_FIELD_MAPPING


# ---------------------------------------------------------------- 适配器契约


def test_tushare_adapter_wraps_list_and_passes_params(monkeypatch):
    """tushare 适配器：结构化 Dict 列表 -> DataFrame + 参数透传"""
    provider, calls = _make_tushare_stub(monkeypatch, news=_news_payload())
    entry = registry.get_entry("stock_news_cn", "tushare")

    df = asyncio.run(
        entry.func(provider, symbol="600519", limit=5, hours_back=48)
    )

    assert isinstance(df, pd.DataFrame)
    assert len(df) == 2
    assert calls[-1] == {"symbol": "600519", "limit": 5, "hours_back": 48}
    # 媒体源仍以 source 键承载（field_mapping 改名由门面完成）
    assert df["source"].tolist() == ["新浪财经", "东方财富"]
    assert df["title"].tolist() == ["贵州茅台发布三季报", "白酒板块盘中拉升"]


def test_tushare_adapter_none_and_error(monkeypatch):
    """tushare 付费无权限 -> None 降级；抛异常 -> None 降级"""
    entry = registry.get_entry("stock_news_cn", "tushare")

    provider, _ = _make_tushare_stub(monkeypatch, news=None)
    assert asyncio.run(
        entry.func(provider, symbol="600519", limit=10)
    ) is None

    provider2, _ = _make_tushare_stub(monkeypatch, error=RuntimeError("接口权限不足"))
    assert asyncio.run(
        entry.func(provider2, symbol="600519", limit=10)
    ) is None


def test_tushare_adapter_unavailable_returns_none(monkeypatch):
    """源不可用 -> None（触发门面降级语义）"""
    from tradingagents.dataflows.providers.china.tushare import TushareProvider

    monkeypatch.setattr(TushareProvider, "is_available", lambda self: False)
    provider = TushareProvider.__new__(TushareProvider)
    provider.api = None
    entry = registry.get_entry("stock_news_cn", "tushare")
    assert asyncio.run(
        entry.func(provider, symbol="600519", limit=10)
    ) is None


def test_akshare_adapter_wraps_list_and_ignores_hours_back(monkeypatch):
    """akshare 适配器：Dict 列表 -> DataFrame + hours_back 忽略（东财无窗口参数）"""
    provider, calls = _make_akshare_stub(monkeypatch, news=_news_payload())
    entry = registry.get_entry("stock_news_cn", "akshare")

    df = asyncio.run(
        entry.func(provider, symbol="600519", limit=5, hours_back=48)
    )

    assert isinstance(df, pd.DataFrame)
    assert len(df) == 2
    # akshare 签名无 hours_back，仅透传 symbol/limit
    assert calls[-1] == {"symbol": "600519", "limit": 5}
    assert df["source"].tolist() == ["新浪财经", "东方财富"]


def test_akshare_adapter_none_and_error(monkeypatch):
    """akshare 反爬拦截（None）-> None 降级；抛异常 -> None 降级"""
    entry = registry.get_entry("stock_news_cn", "akshare")

    provider, _ = _make_akshare_stub(monkeypatch, news=None)
    assert asyncio.run(
        entry.func(provider, symbol="600519", limit=10)
    ) is None

    provider2, _ = _make_akshare_stub(monkeypatch, error=RuntimeError("网络中断"))
    assert asyncio.run(
        entry.func(provider2, symbol="600519", limit=10)
    ) is None


def test_adapter_empty_list_returns_empty_dataframe(monkeypatch):
    """空列表 -> 空 DataFrame（不降级语义，与 None 相区别）"""
    entry = registry.get_entry("stock_news_cn", "tushare")
    provider, _ = _make_tushare_stub(monkeypatch, news=[])
    df = asyncio.run(entry.func(provider, symbol="600519", limit=10))
    assert isinstance(df, pd.DataFrame)
    assert df.empty

    ak_entry = registry.get_entry("stock_news_cn", "akshare")
    ak_provider, _ = _make_akshare_stub(monkeypatch, news=[])
    ak_df = asyncio.run(ak_entry.func(ak_provider, symbol="600519", limit=10))
    assert isinstance(ak_df, pd.DataFrame)
    assert ak_df.empty


# ---------------------------------------------------------------- facade 真实能力全链路


def test_facade_end_to_end_media_source_rename(monkeypatch):
    """全链路：媒体源经 field_mapping 改名保留为 media_source，
    门面 source 列覆盖为 provider 名（tushare），两者语义互不污染"""
    provider, _ = _make_tushare_stub(monkeypatch, news=_news_payload())
    _patch_factories(monkeypatch, tushare_provider=provider)
    _fixed_order(monkeypatch, ["tushare", "akshare"])

    df = asyncio.run(
        get_data_facade()
        .get_capability("stock_news_cn")
        .query(symbol="600519", limit=10)
    )

    assert len(df) == 2
    # 媒体源语义保留（未被子面 source 覆盖吞掉）
    assert df.iloc[0]["media_source"] == "新浪财经"
    assert df.iloc[-1]["media_source"] == "东方财富"
    # 门面附加的数据来源标记 = provider 名
    assert df.iloc[-1]["source"] == "tushare"
    assert df.iloc[-1]["quality"] == "ok"
    assert df.iloc[-1]["title"] == "白酒板块盘中拉升"
    # 标准列齐备，非标准列被裁剪
    assert {"title", "media_source", "publish_time", "source", "quality"} <= set(df.columns)


def test_facade_fallback_tushare_to_akshare(monkeypatch):
    """降级链：tushare 付费无权限（None）-> akshare 接管"""
    tushare_stub, _ = _make_tushare_stub(monkeypatch, news=None)
    akshare_stub, _ = _make_akshare_stub(monkeypatch, news=_news_payload())
    _patch_factories(
        monkeypatch, tushare_provider=tushare_stub, akshare_provider=akshare_stub
    )
    _fixed_order(monkeypatch, ["tushare", "akshare"])

    df = asyncio.run(
        get_data_facade()
        .get_capability("stock_news_cn")
        .query(symbol="600519", limit=10)
    )

    assert len(df) == 2
    assert df.iloc[-1]["source"] == "akshare"
    assert df.iloc[0]["media_source"] == "新浪财经"
    assert "sentiment_score" in df.columns


def test_facade_all_sources_fail_returns_empty_with_columns(monkeypatch):
    """全源失败 -> 空 DataFrame（含标准列结构），不抛异常"""
    tushare_stub, _ = _make_tushare_stub(monkeypatch, news=None)
    akshare_stub, _ = _make_akshare_stub(monkeypatch, news=None)
    _patch_factories(
        monkeypatch, tushare_provider=tushare_stub, akshare_provider=akshare_stub
    )
    _fixed_order(monkeypatch, ["tushare", "akshare"])

    df = asyncio.run(
        get_data_facade()
        .get_capability("stock_news_cn")
        .query(symbol="600519", limit=10)
    )

    assert df.empty
    assert {"title", "media_source", "publish_time", "source", "quality"} <= set(df.columns)


def test_query_capability_sync_path(monkeypatch):
    """同步包装路径（工具侧统一新闻/情绪工具同款调用）"""
    provider, _ = _make_tushare_stub(monkeypatch, news=_news_payload())
    _patch_factories(monkeypatch, tushare_provider=provider)
    _fixed_order(monkeypatch, ["tushare", "akshare"])

    df = query_capability_sync("stock_news_cn", symbol="600519", limit=10)

    assert len(df) == 2
    assert df.iloc[-1]["source"] == "tushare"
    assert df.iloc[0]["media_source"] == "新浪财经"
