#!/usr/bin/env python3
"""测试当前新闻链路的回退与 Google News RSS 行为。"""

import sys
import os
import unittest
from unittest.mock import patch
from datetime import datetime
import pandas as pd

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# 导入需要测试的模块
from tradingagents.dataflows.realtime_news_utils import get_realtime_stock_news
from tradingagents.dataflows.news.google_news import getNewsData


class TestNewsTimeoutFix(unittest.TestCase):
    """测试新闻回退与 RSS 搜索"""

    def setUp(self):
        """测试前的准备工作"""
        self.ticker = "600036.SH"  # 招商银行
        self.curr_date = datetime.now().strftime("%Y-%m-%d")

    def test_google_news_rss_timeout_returns_empty_list(self):
        """测试 RSS 请求超时时返回空列表"""
        import requests

        with patch(
            "tradingagents.dataflows.news.google_news.get_news_data_via_rss",
            side_effect=requests.exceptions.Timeout("Connection timed out"),
        ):
            result = getNewsData("招商银行 股票 新闻", "2026-03-20", "2026-03-27")

        self.assertEqual(result, [])

    def test_news_source_fallback(self):
        """测试实时聚合器失败后回退到当前 A 股 AKShare 新闻源"""
        with patch('tradingagents.dataflows.realtime_news_utils.RealtimeNewsAggregator.get_realtime_stock_news') as mock_aggregator:
            mock_aggregator.side_effect = Exception("模拟实时新闻聚合器失败")

            mock_df = pd.DataFrame({
                '新闻标题': ['测试新闻1', '测试新闻2'],
                '发布时间': ['2026-03-27 12:00:00', '2026-03-27 13:00:00'],
                '新闻内容': ['测试内容1', '测试内容2'],
                '新闻链接': ['http://example.com/1', 'http://example.com/2']
            })

            with patch('tradingagents.dataflows.providers.china.akshare.AKShareProvider') as mock_provider_cls:
                mock_provider = mock_provider_cls.return_value
                mock_provider.get_stock_news_sync.return_value = mock_df

                result = get_realtime_stock_news(self.ticker, self.curr_date)

            self.assertIn("东方财富新闻报告", result)
            self.assertIn("测试新闻1", result)
            self.assertIn("测试新闻2", result)
            mock_aggregator.assert_not_called()
            mock_provider.get_stock_news_sync.assert_called_once()

    def test_all_news_sources_fail(self):
        """测试聚合器、AKShare 与 Google 均失败时返回错误信息"""
        with patch('tradingagents.dataflows.realtime_news_utils.RealtimeNewsAggregator.get_realtime_stock_news') as mock_aggregator:
            mock_aggregator.side_effect = Exception("模拟实时新闻聚合器失败")

            with patch('tradingagents.dataflows.providers.china.akshare.AKShareProvider') as mock_provider_cls:
                mock_provider = mock_provider_cls.return_value
                mock_provider.get_stock_news_sync.side_effect = Exception("模拟东方财富新闻获取失败")

                with patch('tradingagents.dataflows.interface.get_google_news', return_value="") as mock_google_news:
                    result = get_realtime_stock_news(self.ticker, self.curr_date)

            self.assertIn("实时新闻获取失败", result)
            self.assertIn("所有可用的新闻源都未能获取到相关新闻", result)
            mock_aggregator.assert_called_once()
            mock_provider.get_stock_news_sync.assert_called_once()
            mock_google_news.assert_called_once()

    def test_google_news_uses_rss_provider(self):
        """测试 Google 新闻主链路直接使用 RSS 提供器"""
        expected = [
            {
                "title": "招商银行获机构看好",
                "link": "https://example.com/1",
                "snippet": "测试摘要",
                "date": "2026-03-27 10:00:00",
                "source": "新浪财经",
            }
        ]

        with patch(
            "tradingagents.dataflows.news.google_news.get_news_data_via_rss",
            return_value=expected,
        ) as mock_rss:
            result = getNewsData("招商银行 股票 新闻", "2026-03-20", "2026-03-27")

        mock_rss.assert_called_once_with("招商银行 股票 新闻", "2026-03-20", "2026-03-27")
        self.assertEqual(result, expected)


if __name__ == "__main__":
    unittest.main()
