import logging
from datetime import datetime

import pandas as pd


def _patch_a_share_market(monkeypatch):
    from tradingagents.utils import stock_utils as stock_utils_module

    class FakeStockUtils:
        @staticmethod
        def get_market_info(ticker):
            return {
                "is_china": True,
                "is_hk": False,
                "is_us": False,
                "market_name": "中国A股",
            }

    monkeypatch.setattr(stock_utils_module, "StockUtils", FakeStockUtils)


def test_a_share_tool_prefers_akshare_live_when_database_is_empty(monkeypatch):
    from core.tools.implementations.news import stock_news as module

    _patch_a_share_market(monkeypatch)

    monkeypatch.setattr(module, "_get_a_share_enabled_sources", lambda: ["local", "tushare", "akshare"])
    monkeypatch.setattr(
        module,
        "_query_news_from_database",
        lambda symbol, start_date, end_date, limit=20: {
            "news": [],
            "enabled_sources": ["local", "tushare", "akshare"],
            "used_sources": [],
        },
    )
    monkeypatch.setattr(module, "_get_company_name", lambda symbol: "平安银行")
    tushare_calls = {"count": 0}

    def fake_fetch_tushare(*args, **kwargs):
        tushare_calls["count"] += 1
        return [
            {
                "title": "平安银行发布年度业绩快报",
                "summary": "业绩与分红安排同步披露。",
                "publish_time": datetime(2026, 4, 12, 9, 30),
                "source": "新浪财经",
                "category": "company_announcement",
                "sentiment": "positive",
                "importance": "high",
                "keywords": ["业绩", "分红"],
                "data_source": "tushare",
            }
        ]

    monkeypatch.setattr(module, "_fetch_tushare_news_live", fake_fetch_tushare)

    akshare_calls = {"count": 0}

    def fake_fetch_akshare(*args, **kwargs):
        akshare_calls["count"] += 1
        return [
            {
                "title": "平安银行发布年度业绩快报",
                "summary": "业绩与分红安排同步披露。",
                "publish_time": datetime(2026, 4, 12, 9, 30),
                "source": "东方财富",
                "category": "company_announcement",
                "sentiment": "positive",
                "importance": "high",
                "keywords": ["业绩", "分红"],
                "data_source": "akshare",
            }
        ]

    monkeypatch.setattr(module, "_fetch_akshare_news_live", fake_fetch_akshare)

    result = module.get_stock_news_unified.invoke({"ticker": "000001", "curr_date": "2026-04-13"})

    assert "## AKShare东方财富新闻（实时）" in result
    assert "平安银行发布年度业绩快报" in result
    assert "类别: 公司公告 | 情绪: 偏积极 | 重要性: 高" in result
    assert "Tushare多源新闻（实时）" not in result
    assert akshare_calls["count"] == 1
    assert tushare_calls["count"] == 0


def test_fetch_akshare_news_live_filters_outdated_items(monkeypatch):
    from core.tools.implementations.news import stock_news as module
    from tradingagents.dataflows.providers.china import akshare as akshare_module

    class FakeAKShareProvider:
        def is_available(self):
            return True

        async def get_stock_news(self, symbol=None, limit=10):
            return []

    monkeypatch.setattr(akshare_module, "AKShareProvider", FakeAKShareProvider)
    monkeypatch.setattr(
        module,
        "_run_async_in_thread",
        lambda coroutine_factory, timeout=30.0: [
            {
                "title": "窗口内新闻",
                "summary": "分析日期窗口内的新闻。",
                "publish_time": datetime(2026, 4, 12, 10, 0),
                "source": "东方财富",
            },
            {
                "title": "窗口外旧新闻",
                "summary": "明显早于分析日期窗口。",
                "publish_time": datetime(2026, 3, 20, 10, 0),
                "source": "东方财富",
            },
        ],
    )

    news = module._fetch_akshare_news_live(
        symbol="000001",
        start_date=datetime(2026, 4, 7, 0, 0),
        end_date=datetime(2026, 4, 13, 23, 59, 59),
        limit=20,
    )

    assert [item["title"] for item in news] == ["窗口内新闻"]


def test_fetch_tushare_news_live_matches_company_name_without_symbol(monkeypatch):
    from core.tools.implementations.news import stock_news as module
    from tradingagents.dataflows.providers.china import tushare as tushare_module

    class FakeDataFrame:
        empty = False

    class FakeAPI:
        def news(self, src=None, start_date=None, end_date=None):
            return FakeDataFrame()

    class FakeProvider:
        api = FakeAPI()

        def is_available(self):
            return True

        def _process_tushare_news(self, news_df, source, symbol=None, limit=10):
            return [
                {
                    "title": "平安银行发布年报",
                    "summary": "只出现公司名，不出现股票代码。",
                    "publish_time": datetime(2026, 4, 12, 8, 0),
                    "source": "新浪财经",
                    "category": "company_announcement",
                    "sentiment": "positive",
                    "importance": "high",
                    "data_source": "tushare",
                },
                {
                    "title": "无关公司新闻",
                    "summary": "与目标公司无关。",
                    "publish_time": datetime(2026, 4, 12, 9, 0),
                    "source": "新浪财经",
                    "category": "other",
                    "sentiment": "neutral",
                    "importance": "low",
                    "data_source": "tushare",
                },
            ]

    monkeypatch.setattr(module, "TUSHARE_LIVE_SOURCES", ["sina"])
    monkeypatch.setattr(tushare_module, "get_tushare_provider", lambda: FakeProvider())

    news = module._fetch_tushare_news_live(
        symbol="000001",
        company_name="平安银行",
        start_date=datetime(2026, 4, 7, 0, 0),
        end_date=datetime(2026, 4, 13, 23, 59, 59),
        limit=20,
    )

    assert [item["title"] for item in news] == ["平安银行发布年报"]


def test_company_aliases_expand_full_width_share_class_suffix():
    from core.tools.implementations.news import stock_news as module

    aliases = module._get_company_aliases("万科Ａ")

    assert "万科Ａ" in aliases
    assert "万科A" in aliases
    assert "万科" in aliases


def test_fetch_tushare_news_live_scans_full_feed_for_extended_alias_matches(monkeypatch):
    from core.tools.implementations.news import stock_news as module
    from tradingagents.dataflows.providers.china import tushare as tushare_module

    news_df = pd.DataFrame(
        [
            {
                "datetime": "2026-04-12 09:00:00",
                "title": f"无关市场快讯 {index}",
                "content": "与目标公司无关。",
                "channels": "market",
            }
            for index in range(500)
        ]
        + [
            {
                "datetime": "2026-04-12 18:00:00",
                "title": "王石发文辟谣被抓：一切安好，造谣者交给法律",
                "content": "4月12日，网传万科创始人王石被抓消息引发网友热议。傍晚，王石发文辟谣。",
                "channels": "company",
            }
        ]
    )

    class FakeAPI:
        def news(self, src=None, start_date=None, end_date=None):
            return news_df

    class FakeProvider:
        api = FakeAPI()

        def is_available(self):
            return True

        def _process_tushare_news(self, news_df, source, symbol=None, limit=10):
            processed = []
            for _, row in news_df.head(limit * 2).iterrows():
                processed.append(
                    {
                        "title": str(row.get("title", "")),
                        "summary": str(row.get("content", ""))[:200],
                        "content": str(row.get("content", "")),
                        "publish_time": datetime.fromisoformat(str(row.get("datetime"))),
                        "source": "华尔街见闻",
                        "category": "other",
                        "importance": "medium",
                        "data_source": "tushare",
                    }
                )
            return processed

    monkeypatch.setattr(module, "TUSHARE_LIVE_SOURCES", ["wallstreetcn"])
    monkeypatch.setattr(tushare_module, "get_tushare_provider", lambda: FakeProvider())

    news = module._fetch_tushare_news_live(
        symbol="000002",
        company_name="万科Ａ",
        start_date=datetime(2026, 4, 7, 0, 0),
        end_date=datetime(2026, 4, 13, 23, 59, 59),
        limit=20,
    )

    assert [item["title"] for item in news] == ["王石发文辟谣被抓：一切安好，造谣者交给法律"]


def test_relevance_ranking_prefers_direct_company_event_over_macro_mention():
    from core.tools.implementations.news import stock_news as module

    ranked_news = module._rank_a_share_news_items(
        [
            {
                "title": "下周资本市场大事提醒：国家统计局将公布一系列重磅数据 宁德时代、贵州茅台等发布财报",
                "summary": "【下周资本市场大事提醒：国家统计局将公布一系列重磅数据 宁德时代、贵州茅台等发布财报】 1、4月16日，国家统计局将发布一季度国民经济运行数据。",
                "publish_time": datetime(2026, 4, 12, 22, 0),
                "source": "财联社",
                "category": "company_announcement",
                "importance": "high",
                "data_source": "tushare",
            },
            {
                "title": "茅台非标产品代售落地：已有门店执行，首批代售产品已陆续发货",
                "summary": "更直接的公司经营事件。",
                "publish_time": datetime(2026, 4, 8, 16, 30),
                "source": "红星资本局",
                "category": "general",
                "importance": "medium",
                "data_source": "akshare",
            },
        ],
        symbol="600519",
        company_name="贵州茅台",
        limit=20,
    )

    assert ranked_news[0]["title"] == "茅台非标产品代售落地：已有门店执行，首批代售产品已陆续发货"
    assert ranked_news[0]["relevance_score"] > ranked_news[1]["relevance_score"]


def test_relevance_ranking_keeps_body_only_clarification_news_above_zero():
    from core.tools.implementations.news import stock_news as module

    ranked_news = module._rank_a_share_news_items(
        [
            {
                "title": "王石发文辟谣被抓：一切安好，造谣者交给法律",
                "summary": "4月12日，网传万科创始人王石被抓消息引发网友热议。傍晚，王石发文辟谣。",
                "publish_time": datetime(2026, 4, 12, 18, 0),
                "source": "华尔街见闻",
                "category": "other",
                "importance": "medium",
                "data_source": "tushare",
            }
        ],
        symbol="000002",
        company_name="万科Ａ",
        limit=20,
    )

    assert [item["title"] for item in ranked_news] == ["王石发文辟谣被抓：一切安好，造谣者交给法律"]
    assert ranked_news[0]["relevance_score"] > 0


def test_relevance_ranking_prefers_title_company_anchor_over_body_only_mention():
    from core.tools.implementations.news import stock_news as module

    ranked_news = module._rank_a_share_news_items(
        [
            {
                "title": "股票回购：两年万亿强信心 千亿注销增回报",
                "summary": "行业龙头积极开展回购注销。2026年4月2日，贵州茅台（600519.SH）披露《关于回购股份实施进展的公告》显示，截至",
                "publish_time": datetime(2026, 4, 11, 2, 15),
                "source": "中国经营网",
                "category": "company_announcement",
                "importance": "high",
                "data_source": "akshare",
            },
            {
                "title": "茅台非标产品代售落地：已有门店执行，首批代售产品已陆续发货",
                "summary": "更直接的公司经营事件。",
                "publish_time": datetime(2026, 4, 8, 16, 30),
                "source": "红星资本局",
                "category": "general",
                "importance": "medium",
                "data_source": "akshare",
            },
        ],
        symbol="600519",
        company_name="贵州茅台",
        limit=20,
    )

    assert ranked_news[0]["title"] == "茅台非标产品代售落地：已有门店执行，首批代售产品已陆续发货"
    assert ranked_news[0]["relevance_score"] > ranked_news[1]["relevance_score"]


def test_a_share_tool_uses_akshare_live_even_when_tushare_is_configured(monkeypatch):
    from core.tools.implementations.news import stock_news as module

    _patch_a_share_market(monkeypatch)

    monkeypatch.setattr(module, "_get_a_share_enabled_sources", lambda: ["tushare", "akshare", "local"])
    monkeypatch.setattr(
        module,
        "_query_news_from_database",
        lambda symbol, start_date, end_date, limit=20: {
            "news": [],
            "enabled_sources": ["tushare", "akshare", "local"],
            "used_sources": [],
        },
    )
    monkeypatch.setattr(module, "_get_company_name", lambda symbol: "贵州茅台")
    tushare_calls = {"count": 0}

    def fake_fetch_tushare(*args, **kwargs):
        tushare_calls["count"] += 1
        return [
            {
                "title": "下周资本市场大事提醒：国家统计局将公布一系列重磅数据 宁德时代、贵州茅台等发布财报",
                "summary": "【下周资本市场大事提醒：国家统计局将公布一系列重磅数据 宁德时代、贵州茅台等发布财报】 1、4月16日，国家统计局将发布一季度国民经济运行数据。",
                "publish_time": datetime(2026, 4, 12, 22, 0),
                "source": "财联社",
                "category": "company_announcement",
                "importance": "high",
                "data_source": "tushare",
            }
        ]

    monkeypatch.setattr(module, "_fetch_tushare_news_live", fake_fetch_tushare)
    monkeypatch.setattr(
        module,
        "_fetch_akshare_news_live",
        lambda symbol, start_date, end_date, limit=20: [
            {
                "title": "茅台非标产品代售落地：已有门店执行，首批代售产品已陆续发货",
                "summary": "更直接的公司经营事件。",
                "publish_time": datetime(2026, 4, 8, 16, 30),
                "source": "红星资本局",
                "category": "general",
                "importance": "medium",
                "data_source": "akshare",
            }
        ],
    )

    result = module.get_stock_news_unified.invoke({"ticker": "600519", "curr_date": "2026-04-13"})

    assert "## AKShare东方财富新闻（实时）" in result
    assert "茅台非标产品代售落地" in result
    assert "## Tushare多源新闻（实时）" not in result
    assert tushare_calls["count"] == 0


def test_a_share_tool_logs_only_akshare_live_selection(monkeypatch, caplog):
    from core.tools.implementations.news import stock_news as module

    _patch_a_share_market(monkeypatch)

    monkeypatch.setattr(module, "_get_a_share_enabled_sources", lambda: ["local", "tushare", "akshare"])
    monkeypatch.setattr(
        module,
        "_query_news_from_database",
        lambda symbol, start_date, end_date, limit=20: {
            "news": [],
            "enabled_sources": ["local", "tushare", "akshare"],
            "used_sources": [],
        },
    )
    monkeypatch.setattr(module, "_get_company_name", lambda symbol: "万科A")
    tushare_calls = {"count": 0}

    def fake_fetch_tushare(*args, **kwargs):
        tushare_calls["count"] += 1
        return []

    monkeypatch.setattr(module, "_fetch_tushare_news_live", fake_fetch_tushare)
    monkeypatch.setattr(
        module,
        "_fetch_akshare_news_live",
        lambda symbol, start_date, end_date, limit=20: [
            {
                "title": "万科A披露一季度销售数据",
                "summary": "销售与回款情况更新。",
                "publish_time": datetime(2026, 4, 12, 10, 0),
                "source": "东方财富",
                "category": "company_announcement",
                "importance": "high",
                "data_source": "akshare",
            }
        ],
    )

    with caplog.at_level(logging.INFO):
        result = module.get_stock_news_unified.invoke({"ticker": "000002", "curr_date": "2026-04-13"})

    assert "开始尝试实时新闻源: akshare" in caplog.text
    assert "## AKShare东方财富新闻（实时）" in result
    assert "开始尝试实时新闻源: tushare" not in caplog.text
    assert tushare_calls["count"] == 0


def test_database_news_output_includes_structured_fields(monkeypatch):
    from core.tools.implementations.news import stock_news as module

    _patch_a_share_market(monkeypatch)

    monkeypatch.setattr(module, "_get_a_share_enabled_sources", lambda: ["local", "tushare", "akshare"])
    monkeypatch.setattr(
        module,
        "_query_news_from_database",
        lambda symbol, start_date, end_date, limit=20: {
            "news": [
                {
                    "title": "平安银行披露季度报告",
                    "summary": "营收和利润表现平稳。",
                    "publish_time": datetime(2026, 4, 11, 18, 0),
                    "url": "https://example.com/news/1",
                    "source": "上证公告",
                    "category": "company_announcement",
                    "sentiment": "positive",
                    "importance": "high",
                    "keywords": ["季报", "营收"],
                    "data_source": "tushare",
                }
            ],
            "enabled_sources": ["local", "tushare", "akshare"],
            "used_sources": ["tushare"],
        },
    )

    result = module.get_stock_news_unified.invoke({"ticker": "000001", "curr_date": "2026-04-13"})

    assert "## 数据库缓存" in result
    assert "**说明**: 命中来源: Tushare（数据库缓存）" in result
    assert "摘要: 营收和利润表现平稳。" in result
    assert "类别: 公司公告 | 情绪: 偏积极 | 重要性: 高" in result
    assert "关键词: 季报, 营收" in result
    assert "当前分析优先级: local > akshare" in result
    assert "Tushare 新闻源当前仅用于同步入库，不参与实时新闻分析调用。" in result


def test_headlines_tool_deduplicates_titles_and_merges_sources(monkeypatch):
    from core.tools.implementations.news import stock_news as module

    _patch_a_share_market(monkeypatch)

    monkeypatch.setattr(module, "_get_a_share_enabled_sources", lambda: ["tushare", "akshare", "local"])
    monkeypatch.setattr(
        module,
        "_query_news_from_database",
        lambda symbol, start_date, end_date, limit=20: {
            "news": [],
            "enabled_sources": ["tushare", "akshare", "local"],
            "used_sources": [],
        },
    )
    monkeypatch.setattr(module, "_get_company_name", lambda symbol: "贵州茅台")
    monkeypatch.setattr(
        module,
        "_fetch_akshare_news_live",
        lambda symbol, start_date, end_date, limit=20: [
            {
                "title": "茅台非标产品代售落地：已有门店执行，首批代售产品已陆续发货",
                "summary": "财联社版本摘要。",
                "publish_time": datetime(2026, 4, 8, 16, 32),
                "source": "财联社",
                "category": "company_announcement",
                "importance": "high",
                "data_source": "akshare",
            },
            {
                "title": "茅台非标产品代售落地：已有门店执行，首批代售产品已陆续发货",
                "summary": "AKShare版本摘要。",
                "publish_time": datetime(2026, 4, 8, 16, 30),
                "source": "红星资本局",
                "category": "general",
                "importance": "medium",
                "data_source": "akshare",
            },
            {
                "title": "股票回购：两年万亿强信心 千亿注销增回报",
                "summary": "行业龙头积极开展回购注销。",
                "publish_time": datetime(2026, 4, 11, 2, 15),
                "source": "中国经营网",
                "category": "company_announcement",
                "importance": "high",
                "data_source": "akshare",
            },
        ],
    )

    result = module.get_stock_news_headlines_unified.invoke(
        {"ticker": "600519", "curr_date": "2026-04-13", "limit": 10}
    )

    assert result.count("茅台非标产品代售落地：已有门店执行，首批代售产品已陆续发货") == 1
    assert "来源: 财联社 / 红星资本局" in result
    assert "去重合并: 已合并 2 条同标题新闻" in result
    assert "news_id:" in result
    assert "get_stock_news_details_unified" in result


def test_details_tool_returns_selected_news_by_news_id(monkeypatch):
    from core.tools.implementations.news import stock_news as module

    _patch_a_share_market(monkeypatch)

    monkeypatch.setattr(module, "_get_a_share_enabled_sources", lambda: ["tushare", "akshare", "local"])
    monkeypatch.setattr(
        module,
        "_query_news_from_database",
        lambda symbol, start_date, end_date, limit=20: {
            "news": [],
            "enabled_sources": ["tushare", "akshare", "local"],
            "used_sources": [],
        },
    )
    monkeypatch.setattr(module, "_get_company_name", lambda symbol: "贵州茅台")
    monkeypatch.setattr(
        module,
        "_fetch_akshare_news_live",
        lambda symbol, start_date, end_date, limit=20: [
            {
                "title": "茅台非标产品代售落地：已有门店执行，首批代售产品已陆续发货",
                "summary": "更直接的公司经营事件。",
                "content": "3月贵州茅台向经销商征求合作意向，首批代售产品已陆续发货。",
                "publish_time": datetime(2026, 4, 8, 16, 30),
                "source": "红星资本局",
                "category": "general",
                "importance": "medium",
                "data_source": "akshare",
                "url": "https://example.com/news/maotai-detail",
            }
        ],
    )

    bundle = module._build_stock_news_bundle("600519", "2026-04-13", limit=10)
    news_id = bundle["items"][0]["news_id"]

    result = module.get_stock_news_details_unified.invoke(
        {"ticker": "600519", "curr_date": "2026-04-13", "news_ids": news_id}
    )

    assert f"[news_id: {news_id}]" in result
    assert "茅台非标产品代售落地" in result
    assert "正文要点: 3月贵州茅台向经销商征求合作意向" in result
    assert "链接: https://example.com/news/maotai-detail" in result


def test_headlines_tool_deprioritizes_macro_reminder_detail_recommendation(monkeypatch):
    from core.tools.implementations.news import stock_news as module

    _patch_a_share_market(monkeypatch)

    monkeypatch.setattr(module, "_get_a_share_enabled_sources", lambda: ["tushare", "akshare", "local"])
    monkeypatch.setattr(
        module,
        "_query_news_from_database",
        lambda symbol, start_date, end_date, limit=20: {
            "news": [],
            "enabled_sources": ["tushare", "akshare", "local"],
            "used_sources": [],
        },
    )
    monkeypatch.setattr(module, "_get_company_name", lambda symbol: "贵州茅台")
    monkeypatch.setattr(
        module,
        "_fetch_akshare_news_live",
        lambda symbol, start_date, end_date, limit=20: [
            {
                "title": "下周资本市场大事提醒：国家统计局将公布一系列重磅数据 宁德时代、贵州茅台等发布财报",
                "summary": "宏观与多家公司日历提醒。",
                "publish_time": datetime(2026, 4, 12, 22, 0),
                "source": "财联社",
                "category": "company_announcement",
                "importance": "high",
                "data_source": "akshare",
            }
        ],
    )

    result = module.get_stock_news_headlines_unified.invoke(
        {"ticker": "600519", "curr_date": "2026-04-13", "limit": 10}
    )

    assert "明细建议: 可暂不展开（更像宏观提醒或多公司枚举新闻）" in result