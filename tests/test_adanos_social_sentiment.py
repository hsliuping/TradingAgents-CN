import unittest
from unittest.mock import patch

from tradingagents.dataflows import adanos_social, interface


class AdanosSocialSentimentTests(unittest.TestCase):
    def test_adanos_social_formats_multiple_sources(self):
        payloads = {
            "/reddit/stocks/v1/stock/NVDA": {
                "company_name": "NVIDIA Corporation",
                "buzz_score": 72.4,
                "sentiment_score": 0.31,
                "bullish_pct": 61,
                "bearish_pct": 18,
                "trend": "rising",
                "total_mentions": 142,
            },
            "/news/stocks/v1/stock/NVDA": {
                "source_count": 23,
                "sentiment_score": 0.22,
            },
            "/x/stocks/v1/stock/NVDA": {
                "unique_tweets": 305,
                "sentiment_score": 0.27,
            },
            "/polymarket/stocks/v1/stock/NVDA": {
                "trade_count": 91,
                "market_count": 4,
                "total_liquidity": 120000.0,
                "sentiment_score": 0.14,
            },
        }

        def fake_request(path, *, api_key, base_url, params):
            self.assertEqual(api_key, "test-key")
            self.assertEqual(base_url, "https://api.adanos.org")
            self.assertEqual(params, {"days": 7})
            return payloads[path]

        with patch.dict("os.environ", {"ADANOS_API_KEY": "test-key"}, clear=False):
            with patch("tradingagents.dataflows.adanos_social._request_json", side_effect=fake_request):
                result = adanos_social.get_adanos_social_sentiment("NVDA", "2026-03-25", 7)

        self.assertIn("# NVDA 全球社交情绪补充（Adanos）", result)
        self.assertIn("## Reddit", result)
        self.assertIn("## News", result)
        self.assertIn("## X/Twitter", result)
        self.assertIn("## Polymarket", result)
        self.assertIn("热度分数: 72.4", result)
        self.assertIn("交易笔数: 91", result)

    def test_adanos_social_requires_api_key(self):
        with patch.dict("os.environ", {}, clear=True):
            result = adanos_social.get_adanos_social_sentiment("NVDA", "2026-03-25", 7)

        self.assertIn("ADANOS_API_KEY", result)

    def test_interface_exposes_adanos_helpers(self):
        with patch("tradingagents.dataflows.interface._is_adanos_social_sentiment_enabled", return_value=True):
            self.assertTrue(interface.is_adanos_social_sentiment_enabled())

        with patch("tradingagents.dataflows.interface._supports_adanos_social_sentiment_ticker", return_value=True):
            self.assertTrue(interface.supports_adanos_social_sentiment_ticker("NVDA"))

        with patch("tradingagents.dataflows.interface._get_adanos_social_sentiment", return_value="ok"):
            self.assertEqual(interface.get_adanos_social_sentiment("NVDA", "2026-03-25", 7), "ok")

    def test_unified_sentiment_uses_adanos_for_us_stock(self):
        from tradingagents.agents.utils.agent_utils import Toolkit

        market_info = {
            "is_china": False,
            "is_hk": False,
            "is_us": True,
            "market_name": "美股",
        }
        with patch("tradingagents.utils.stock_utils.StockUtils.get_market_info", return_value=market_info):
            with patch("tradingagents.agents.utils.agent_utils.interface.get_adanos_social_sentiment", return_value="全球情绪"):
                result = Toolkit.get_stock_sentiment_unified.invoke(
                    {"ticker": "NVDA", "curr_date": "2026-03-25"}
                )

        self.assertIn("## 美股社交情绪（Adanos）", result)
        self.assertIn("全球情绪", result)

    def test_unified_sentiment_uses_chinese_source_for_cn_stock(self):
        from tradingagents.agents.utils.agent_utils import Toolkit

        market_info = {
            "is_china": True,
            "is_hk": False,
            "is_us": False,
            "market_name": "A股",
        }
        with patch("tradingagents.utils.stock_utils.StockUtils.get_market_info", return_value=market_info):
            with patch("tradingagents.agents.utils.agent_utils.interface.get_chinese_social_sentiment", return_value="本地中文情绪"):
                with patch("tradingagents.agents.utils.agent_utils.interface.is_adanos_social_sentiment_enabled", return_value=False):
                    result = Toolkit.get_stock_sentiment_unified.invoke(
                        {"ticker": "600519", "curr_date": "2026-03-25"}
                    )

        self.assertIn("## 中文市场情绪", result)
        self.assertIn("本地中文情绪", result)


if __name__ == "__main__":
    unittest.main()
