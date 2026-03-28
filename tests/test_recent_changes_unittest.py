import ast
import asyncio
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pandas as pd

from app.services.favorites_service import (
    FavoritesService,
    _build_batch_quote_lookup_keys,
    _normalize_tags,
    build_historical_quote_fallback,
    infer_favorite_market_metadata,
)
from app.services.foreign_stock_service import ForeignStockService
from app.services.memory_state_manager import TaskState, TaskStatus
from app.services.stock_data_service import StockDataService
from app.services.tags_service import TagsService
from app.services import simple_analysis_service
from tradingagents.dataflows.providers.sina_finance import (
    SinaFinancePageClient,
    infer_sina_page_url,
    normalize_sina_symbol,
    parse_sina_quote_line,
)
from tradingagents.dataflows.news.google_news import getNewsData
from tradingagents.dataflows.news.google_news_rss import parse_google_news_rss
from app.utils.report_language_utils import (
    get_report_section_title,
    normalize_report_markdown,
    normalize_reports_dict,
)
from tradingagents.agents.utils.agent_utils import (
    Toolkit,
    _build_google_query_candidates_for_news,
    _resolve_company_name_for_news,
)


class TestRecentChanges(unittest.TestCase):
    def test_favorites_service_preserves_realtime_trade_date_when_change_uses_historical_fallback(self):
        service = FavoritesService()

        class FakeCursor:
            def __init__(self, items):
                self.items = items

            async def to_list(self, length=None):
                return list(self.items)

        class FakeCollection:
            def __init__(self, items=None, doc=None):
                self.items = items or []
                self.doc = doc

            async def find_one(self, query):
                return self.doc

            def find(self, *args, **kwargs):
                return FakeCursor(self.items)

        class FakeDB(dict):
            def __init__(self):
                super().__init__()
                self.user_favorites = FakeCollection(
                    doc={
                        "user_id": "user-1",
                        "favorites": [
                            {
                                "stock_code": "09992",
                                "stock_name": "泡泡玛特",
                                "market": "港股",
                                "tags": ["港股"],
                            }
                        ],
                    }
                )
                self["stock_basic_info"] = FakeCollection(items=[])
                self["market_quotes"] = FakeCollection(items=[])

        fake_db = FakeDB()

        class FakeDataSourceConfig:
            def __init__(self, ds_type: str, enabled: bool = True):
                self.type = ds_type
                self.enabled = enabled

        class FakeConfigManager:
            async def get_data_source_configs_async(self):
                return [FakeDataSourceConfig("tushare")]

        mock_foreign_service = AsyncMock()
        mock_foreign_service.get_quote = AsyncMock(
            return_value={
                "price": 152.0,
                "change_percent": None,
                "trade_date": "2026-03-27",
                "updated_at": "2026-03-27T13:10:30",
            }
        )
        mock_foreign_service.get_kline = AsyncMock(
            return_value=[
                {"trade_date": "2026-03-25", "close": 138.0},
                {"trade_date": "2026-03-26", "close": 150.0},
            ]
        )

        service.db = fake_db

        with patch("app.core.unified_config.UnifiedConfigManager", return_value=FakeConfigManager()):
            with patch("app.services.foreign_stock_service.ForeignStockService", return_value=mock_foreign_service):
                favorites = asyncio.run(service.get_user_favorites("user-1"))

        self.assertEqual(len(favorites), 1)
        item = favorites[0]
        self.assertEqual(item["current_price"], 152.0)
        self.assertEqual(item["quote_trade_date"], "2026-03-27")
        self.assertEqual(item["change_display_mode"], "historical_close_fallback")
        self.assertIn("最近两根日K估算", item["change_display_hint"])

    def test_industry_backfill_script_is_parseable(self):
        script_path = (
            Path(__file__).resolve().parents[1]
            / "scripts"
            / "补充行业信息_akshare.py"
        )

        source = script_path.read_text(encoding="utf-8")
        ast.parse(source, filename=str(script_path))

    def test_normalize_tags_removes_duplicates_and_blanks(self):
        tags = ["长期", " 短线 ", "", "长期", "短线", "  ", None, "港股"]

        normalized = _normalize_tags(tags)

        self.assertEqual(normalized, ["长期", "短线", "港股"])

    def test_build_batch_quote_lookup_keys_includes_hk_compat_variants(self):
        keys = _build_batch_quote_lookup_keys(
            [
                {"stock_code": "06166", "market": "港股"},
                {"stock_code": "09992", "market": "港股"},
                {"stock_code": "300750", "market": "A股"},
            ]
        )

        self.assertIn("06166", keys)
        self.assertIn("6166", keys)
        self.assertIn("006166", keys)
        self.assertIn("09992", keys)
        self.assertIn("9992", keys)
        self.assertIn("300750", keys)

    def test_report_language_utils_translate_english_headings_to_chinese(self):
        content = "## market_report\n\n### Neutral Analyst\n\n分析内容"

        normalized = normalize_report_markdown(content, "market_report", "zh-CN")

        self.assertIn("## 市场技术分析", normalized)
        self.assertIn("## 中性风险评估", normalized)
        self.assertNotIn("market_report", normalized)
        self.assertNotIn("Neutral Analyst", normalized)

    def test_normalize_reports_dict_applies_report_key_titles(self):
        reports = {
            "fundamentals_report": "fundamentals_report\n\n这是正文",
            "neutral_analyst": "1) neutral analyst",
        }

        normalized = normalize_reports_dict(reports, "zh-CN")

        self.assertEqual(
            get_report_section_title("fundamentals_report", "zh-CN"),
            "基本面分析",
        )
        self.assertTrue(normalized["fundamentals_report"].startswith("## 基本面分析"))
        self.assertIn("### 中性风险评估", normalized["neutral_analyst"])

    def test_favorites_service_format_favorite_normalizes_tags_and_currency(self):
        service = FavoritesService()
        favorite = {
            "stock_code": "09992",
            "stock_name": "泡泡玛特",
            "market": "港股",
            "tags": ["潮玩", "港股", "潮玩", "  港股  ", ""],
            "notes": "测试"
        }

        formatted = service._format_favorite(favorite)

        self.assertEqual(formatted["currency"], "HKD")
        self.assertEqual(formatted["tags"], ["潮玩", "港股"])
        self.assertEqual(formatted["stock_code"], "09992")
        self.assertEqual(formatted["stock_name"], "泡泡玛特")

    def test_foreign_stock_service_format_hk_quote_preserves_change_percent(self):
        service = ForeignStockService.__new__(ForeignStockService)

        formatted = service._format_hk_quote(
            {
                "name": "泡泡玛特",
                "price": 188.6,
                "change_percent": "2.34%",
                "trade_date": "2026-03-26",
            },
            "09992",
            "akshare",
        )

        self.assertEqual(formatted["code"], "09992")
        self.assertEqual(formatted["name"], "泡泡玛特")
        self.assertEqual(formatted["change_percent"], 2.34)
        self.assertEqual(formatted["pct_chg"], 2.34)

    def test_foreign_stock_service_format_hk_quote_does_not_fake_trade_date(self):
        service = ForeignStockService.__new__(ForeignStockService)

        formatted = service._format_hk_quote(
            {
                "name": "剑桥科技",
                "price": 3.21,
                "timestamp": "15:30:00",
            },
            "06166",
            "akshare",
        )

        self.assertIsNone(formatted["trade_date"])
        self.assertIsNotNone(formatted["updated_at"])

    def test_parse_sina_cn_quote_line(self):
        line = (
            'var hq_str_sh600519="贵州茅台,1400.000,1401.180,1414.540,1426.000,1396.660,'
            '1414.540,1414.570,2144070,3033116704.000,100,1414.540,2026-03-27,13:29:00,00,";'
        )

        parsed = parse_sina_quote_line(line)

        self.assertIsNotNone(parsed)
        assert parsed is not None
        self.assertEqual(parsed.symbol, "600519")
        self.assertEqual(parsed.market, "CN")
        self.assertEqual(parsed.name, "贵州茅台")
        self.assertAlmostEqual(parsed.current_price or 0, 1414.54, places=2)
        self.assertEqual(parsed.trade_date, "2026-03-27")

    def test_parse_sina_hk_quote_line(self):
        line = (
            'var hq_str_hk09992="POP MART,泡泡玛特,153.100,150.700,156.900,150.000,151.400,'
            '0.700,0.464,151.39999,151.50000,3989573117,26091600,0.000,0.000,339.800,118.313,2026/03/27,13:06";'
        )

        parsed = parse_sina_quote_line(line)

        self.assertIsNotNone(parsed)
        assert parsed is not None
        self.assertEqual(parsed.symbol, "09992")
        self.assertEqual(parsed.market, "HK")
        self.assertEqual(parsed.name, "泡泡玛特")
        self.assertAlmostEqual(parsed.current_price or 0, 151.4, places=2)
        self.assertAlmostEqual(parsed.change_percent or 0, 46.4, places=2)
        self.assertEqual(parsed.trade_date, "2026-03-27")

    def test_normalize_sina_symbol_supports_cn_and_hk(self):
        self.assertEqual(normalize_sina_symbol("600519"), "sh600519")
        self.assertEqual(normalize_sina_symbol("300750"), "sz300750")
        self.assertEqual(normalize_sina_symbol("9992", "HK"), "hk09992")

    def test_infer_sina_page_url_supports_cn_and_hk(self):
        self.assertEqual(
            infer_sina_page_url("600519"),
            "https://finance.sina.com.cn/realstock/company/sh600519/nc.shtml",
        )
        self.assertEqual(
            infer_sina_page_url("09992", "HK"),
            "https://stock.finance.sina.com.cn/hkstock/quotes/09992.html",
        )

    def test_infer_favorite_market_metadata_recognizes_exchange_and_board(self):
        self.assertEqual(
            infer_favorite_market_metadata("A股", "688001"),
            {"exchange": "上海证券交易所", "board": "科创板"},
        )
        self.assertEqual(
            infer_favorite_market_metadata("A股", "300750"),
            {"exchange": "深圳证券交易所", "board": "创业板"},
        )
        self.assertEqual(
            infer_favorite_market_metadata("港股", "09992"),
            {"exchange": "香港交易所", "board": None},
        )

    def test_build_historical_quote_fallback_uses_recent_close_and_prev_close(self):
        fallback = build_historical_quote_fallback(
            [
                {"trade_date": "2026-03-25", "close": 180.0},
                {"trade_date": "2026-03-26", "close": 189.0},
            ]
        )

        self.assertIsNotNone(fallback)
        self.assertEqual(fallback["current_price"], 189.0)
        self.assertEqual(fallback["trade_date"], "2026-03-26")
        self.assertEqual(fallback["change_percent"], 5.0)

    def test_stock_data_service_akshare_fallback_builds_basic_info(self):
        service = StockDataService()
        fake_df = pd.DataFrame(
            [
                {"symbol": "603083", "name": "剑桥科技", "market": "主板", "ts_code": "603083.SH"}
            ]
        )

        with patch("app.services.data_sources.akshare_adapter.AKShareAdapter") as mock_adapter_cls:
            mock_adapter = mock_adapter_cls.return_value
            mock_adapter.get_stock_list.return_value = fake_df

            result = asyncio.run(service._fetch_a_share_basic_info_from_akshare("603083"))

        self.assertIsNotNone(result)
        self.assertEqual(result["name"], "剑桥科技")
        self.assertEqual(result["source"], "akshare")
        self.assertEqual(result["sse"], "上海证券交易所")
        self.assertEqual(result["full_symbol"], "603083.SH")

    def test_stock_data_service_get_basic_info_uses_akshare_fallback_and_caches(self):
        service = StockDataService()

        class FakeCollection:
            async def find_one(self, *args, **kwargs):
                return None

        class FakeDB(dict):
            def __getitem__(self, key):
                return FakeCollection()

        fallback_doc = {
            "symbol": "603083",
            "code": "603083",
            "name": "剑桥科技",
            "market": "主板",
            "sse": "上海证券交易所",
            "full_symbol": "603083.SH",
            "source": "akshare",
        }

        with patch("app.services.stock_data_service.get_mongo_db", return_value=FakeDB()):
            with patch.object(service, "_fetch_a_share_basic_info_from_akshare", AsyncMock(return_value=fallback_doc)):
                with patch.object(service, "update_stock_basic_info", AsyncMock(return_value=True)) as mock_update:
                    result = asyncio.run(service.get_stock_basic_info("603083"))

        self.assertIsNotNone(result)
        self.assertEqual(result.name, "剑桥科技")
        self.assertEqual(result.symbol, "603083")
        mock_update.assert_awaited_once()

    def test_tags_service_replace_tag_name_deduplicates_per_stock(self):
        service = TagsService()

        updated, changed = service._replace_tag_name_in_favorites(
            [
                {"stock_code": "09992", "tags": ["成长", "长期", "成长"]},
                {"stock_code": "06166", "tags": ["成长", "核心"]},
            ],
            old_name="成长",
            new_name="核心",
        )

        self.assertTrue(changed)
        self.assertEqual(updated[0]["tags"], ["核心", "长期"])
        self.assertEqual(updated[1]["tags"], ["核心"])

    def test_tags_service_update_tag_returns_false_for_invalid_tag_id(self):
        service = TagsService()

        result = asyncio.run(service.update_tag("user-1", "invalid-tag-id", name="新标签"))

        self.assertFalse(result)

    def test_tags_service_delete_tag_returns_false_for_invalid_tag_id(self):
        service = TagsService()

        result = asyncio.run(service.delete_tag("user-1", "invalid-tag-id"))

        self.assertFalse(result)

    def test_stock_data_service_update_methods_do_not_mutate_input_dicts(self):
        service = StockDataService()

        class FakeCollection:
            def __init__(self):
                self.calls = []

            async def update_one(self, query, update, upsert=False):
                self.calls.append((query, update, upsert))
                return SimpleNamespace(modified_count=1, upserted_id=None)

        class FakeDB(dict):
            def __init__(self):
                super().__init__()
                self["stock_basic_info"] = FakeCollection()
                self["market_quotes"] = FakeCollection()

        fake_db = FakeDB()
        basic_payload = {"name": "剑桥科技"}
        quote_payload = {"close": 12.34}

        with patch("app.services.stock_data_service.get_mongo_db", return_value=fake_db):
            basic_updated = asyncio.run(service.update_stock_basic_info("603083", basic_payload, source="akshare"))
            quote_updated = asyncio.run(service.update_market_quotes("603083", quote_payload))

        self.assertTrue(basic_updated)
        self.assertTrue(quote_updated)
        self.assertEqual(basic_payload, {"name": "剑桥科技"})
        self.assertEqual(quote_payload, {"close": 12.34})

    def test_simple_analysis_service_graph_progress_callback_uses_module_datetime(self):
        source = Path(simple_analysis_service.__file__).read_text(encoding="utf-8")

        self.assertIn('progress_tracker.progress_data["last_real_node_at"] = datetime.now().isoformat()', source)
        self.assertNotIn("from datetime import datetime\n", source[source.find("def graph_progress_callback"):source.find("logger.info(f\"🚀 准备调用 trading_graph.propagate")])

    def test_task_state_to_dict_exposes_timing_fields(self):
        task = TaskState(
            task_id="task-1",
            user_id="user-1",
            stock_code="600519",
            status=TaskStatus.RUNNING,
            progress=45,
            start_time=datetime.now() - timedelta(seconds=12),
            estimated_duration=300,
        )

        data = task.to_dict()

        self.assertEqual(data["status"], "running")
        self.assertIn("elapsed_time", data)
        self.assertIn("remaining_time", data)
        self.assertIn("estimated_total_time", data)
        self.assertGreaterEqual(data["elapsed_time"], 11)
        self.assertLessEqual(data["estimated_total_time"], 300)
        self.assertGreaterEqual(data["remaining_time"], 0)

    def test_hk_unified_news_tool_falls_back_to_sync_provider_inside_running_loop(self):
        toolkit = Toolkit(config={})
        class FakeForeignStockService:
            async def get_hk_news(self, code, days=7, limit=10):
                return {
                    "source": "akshare",
                    "items": [
                        {
                            "title": "泡泡玛特09992.HK)3月26日回购6.00亿港元",
                            "publish_time": "2026-03-26 18:00:00",
                            "url": "https://example.com/hk-news-native",
                            "summary": "原生新闻摘要",
                            "source": "AKShare-东方财富",
                        }
                    ],
                }

            def _get_hk_news_from_akshare(self, code, days, limit):
                return [
                    {
                        "title": "泡泡玛特09992.HK)3月26日回购6.00亿港元（fallback）",
                        "publish_time": "2026-03-26 18:00:00",
                        "url": "https://example.com/hk-news",
                    }
                ]

            def _get_hk_news_from_finnhub(self, code, days, limit):
                return []

        async def invoke_in_loop():
            with patch(
                "app.services.foreign_stock_service.ForeignStockService",
                return_value=FakeForeignStockService(),
            ):
                with patch(
                    "tradingagents.dataflows.providers.hk.improved_hk.get_hk_company_name_improved",
                    return_value="泡泡玛特",
                ):
                    with patch(
                        "tradingagents.dataflows.news.google_news.getNewsData",
                        return_value=[
                            {
                                "title": "泡泡玛特(09992.HK)业绩承压后股价波动",
                                "date": "2026-03-27 10:00:00",
                                "link": "https://example.com/google-popmart",
                                "snippet": "Google 新闻摘要",
                                "source": "Google News",
                            }
                        ],
                    ):
                        return toolkit.get_stock_news_unified.invoke(
                            {"ticker": "09992.HK", "curr_date": "2026-03-27"}
                        )

        output = asyncio.run(invoke_in_loop())

        self.assertIn("港股原生新闻源（ForeignStockService/akshare）", output)
        self.assertIn("泡泡玛特09992.HK)3月26日回购6.00亿港元", output)
        self.assertIn("Google新闻（多关键词聚合）", output)
        self.assertIn("泡泡玛特(09992.HK)业绩承压后股价波动", output)
        self.assertNotIn("Cannot run the event loop", output)

    def test_parse_google_news_rss_extracts_items(self):
        xml_text = """
        <rss>
          <channel>
            <item>
              <title>泡泡玛特港股回购创纪录 - 东方财富</title>
              <link>https://example.com/news/1</link>
              <pubDate>Thu, 27 Mar 2026 10:00:00 GMT</pubDate>
              <description><![CDATA[<div>泡泡玛特回购金额创新高</div>]]></description>
              <source url="https://finance.eastmoney.com">东方财富</source>
            </item>
          </channel>
        </rss>
        """

        items = parse_google_news_rss(xml_text)

        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["title"], "泡泡玛特港股回购创纪录 - 东方财富")
        self.assertEqual(items[0]["source"], "东方财富")
        self.assertIn("泡泡玛特回购金额创新高", items[0]["snippet"])

    def test_get_google_news_uses_rss_provider(self):
        rss_items = [
            {
                "title": "腾讯控股获南向资金连续4天净买入",
                "link": "https://example.com/news/tencent",
                "snippet": "测试摘要",
                "date": "2026-03-27 10:00:00",
                "source": "富途牛牛",
            }
        ]

        with patch(
            "tradingagents.dataflows.news.google_news.get_news_data_via_rss",
            return_value=rss_items,
        ) as mock_rss:
            result = getNewsData("腾讯控股 港股 新闻", "2026-03-20", "2026-03-27")

        mock_rss.assert_called_once()
        self.assertEqual(result, rss_items)

    def test_build_google_query_candidates_for_a_share_and_hk(self):
        a_share_queries = _build_google_query_candidates_for_news(
            "600519",
            {"is_china": True, "is_hk": False, "is_us": False},
            "贵州茅台",
        )
        hk_queries = _build_google_query_candidates_for_news(
            "09992.HK",
            {"is_china": False, "is_hk": True, "is_us": False},
            "泡泡玛特",
        )

        self.assertIn("600519 股票 新闻", a_share_queries)
        self.assertIn("贵州茅台 财报 公告 新闻", a_share_queries)
        self.assertIn("09992 港股 股票 新闻", hk_queries)
        self.assertIn("09992 HK stock news", hk_queries)
        self.assertIn("泡泡玛特 HK news", hk_queries)

    def test_resolve_company_name_for_news_uses_akshare_fallback_for_a_share(self):
        fake_df = pd.DataFrame(
            [
                {"code": "600519", "name": "贵州茅台"},
                {"code": "300750", "name": "宁德时代"},
            ]
        )

        with patch(
            "tradingagents.dataflows.interface.get_china_stock_info_unified",
            side_effect=Exception("mock unified failure"),
        ):
            with patch("tradingagents.dataflows.providers.china.akshare.AKShareProvider") as mock_provider_cls:
                mock_provider_cls.return_value.get_stock_list_sync.return_value = fake_df
                company_name = _resolve_company_name_for_news(
                    "600519",
                    {"is_china": True, "is_hk": False, "is_us": False},
                )

        self.assertEqual(company_name, "贵州茅台")

    def test_sina_finance_page_client_extracts_page_snapshot(self):
        client = SinaFinancePageClient(timeout=5)
        html = """
        <html>
          <head>
            <title>泡泡玛特(09992)股票股价,实时行情,新闻,财报数据_新浪财经_新浪网</title>
            <meta name="Keywords" content="泡泡玛特,09992,港股,新浪财经" />
          </head>
          <body>https://hq.sinajs.cn/list=hk09992</body>
        </html>
        """

        class FakeResponse:
            text = html

            def raise_for_status(self):
                return None

        with patch("tradingagents.dataflows.providers.sina_finance.requests.get", return_value=FakeResponse()):
            snapshot = client.fetch_page_snapshot("09992", "HK")

        self.assertEqual(snapshot.market, "HK")
        self.assertEqual(snapshot.page_type, "hk_quote_page")
        self.assertIn("泡泡玛特(09992)", snapshot.title)
        self.assertTrue(snapshot.has_quote_api_reference)

    def test_hk_unified_news_tool_returns_explicit_error_when_both_sources_empty(self):
        toolkit = Toolkit(config={})

        class FakeForeignStockService:
            async def get_hk_news(self, code, days=7, limit=10):
                return {"source": "none", "items": []}

            def _get_hk_news_from_akshare(self, code, days, limit):
                return []

            def _get_hk_news_from_finnhub(self, code, days, limit):
                return []

        with patch(
            "app.services.foreign_stock_service.ForeignStockService",
            return_value=FakeForeignStockService(),
        ):
            with patch(
                "tradingagents.dataflows.providers.hk.improved_hk.get_hk_company_name_improved",
                return_value="泡泡玛特",
            ):
                with patch(
                    "tradingagents.dataflows.news.google_news.getNewsData",
                    return_value=[],
                ):
                    output = toolkit.get_stock_news_unified.invoke(
                        {"ticker": "09992.HK", "curr_date": "2026-03-27"}
                    )

        self.assertIn("## 获取失败", output)
        self.assertIn("原生路径与 Google 新闻都未返回有效的高相关近期新闻", output)
        self.assertIn("Google关键词", output)


if __name__ == "__main__":
    unittest.main()
