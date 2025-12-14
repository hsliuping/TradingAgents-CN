#!/usr/bin/env python3
"""
国际新闻工具单元测试

测试范围:
- fetch_bloomberg_news 工具
- fetch_reuters_news 工具
- fetch_google_news 工具
- 降级机制
- Markdown格式化
"""

import pytest
from unittest.mock import patch, Mock
import os

from tradingagents.tools.international_news_tools import (
    fetch_bloomberg_news,
    fetch_reuters_news,
    fetch_google_news,
    _format_news_to_markdown
)


class TestBloombergNewsTool:
    """测试彭博社新闻工具"""
    
    @patch('tradingagents.tools.international_news_tools.requests.get')
    @patch.dict(os.environ, {'NEWSAPI_KEY': 'test_api_key'})
    def test_fetch_bloomberg_news_success(self, mock_get):
        """测试成功获取彭博社新闻"""
        # Mock API响应
        mock_response = Mock()
        mock_response.json.return_value = {
            "articles": [
                {
                    "title": "China Plans Billion-Dollar Chip Support",
                    "publishedAt": "2025-12-10T08:00:00Z",
                    "description": "China to boost semiconductor industry",
                    "url": "https://bloomberg.com/test"
                }
            ]
        }
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response
        
        # 执行
        result = fetch_bloomberg_news.invoke({"keywords": "China semiconductor", "lookback_days": 7})
        
        # 验证
        assert "Bloomberg" in result
        assert "China Plans Billion-Dollar Chip Support" in result
        assert "China to boost semiconductor industry" in result
    
    @patch.dict(os.environ, {}, clear=True)
    def test_fetch_bloomberg_news_no_api_key_fallback(self):
        """测试无API Key时降级到Google News"""
        with patch('tradingagents.tools.international_news_tools.fetch_google_news') as mock_google:
            mock_google.return_value = "Google News fallback"
            
            result = fetch_bloomberg_news.invoke({"keywords": "test", "lookback_days": 7})
            
            # 验证调用了Google News降级
            mock_google.assert_called_once()


class TestReutersNewsTool:
    """测试路透社新闻工具"""
    
    @patch('tradingagents.tools.international_news_tools.requests.get')
    @patch.dict(os.environ, {'NEWSAPI_KEY': 'test_api_key'})
    def test_fetch_reuters_news_success(self, mock_get):
        """测试成功获取路透社新闻"""
        mock_response = Mock()
        mock_response.json.return_value = {
            "articles": [
                {
                    "title": "Reuters Test Article",
                    "publishedAt": "2025-12-10",
                    "description": "Test description"
                }
            ]
        }
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response
        
        result = fetch_reuters_news.invoke({"keywords": "test", "lookback_days": 7})
        
        assert "Reuters" in result
        assert "Reuters Test Article" in result


class TestGoogleNewsTool:
    """测试Google News工具"""
    
    @patch('tradingagents.tools.international_news_tools.GoogleNews')
    def test_fetch_google_news_success(self, mock_google_class):
        """测试成功获取Google News"""
        # Mock GoogleNews实例
        mock_instance = Mock()
        mock_instance.results.return_value = [
            {
                "title": "Google News Test",
                "date": "2025-12-10",
                "media": "Test Media",
                "link": "https://test.com"
            }
        ]
        mock_google_class.return_value = mock_instance
        
        result = fetch_google_news.invoke({"keywords": "test", "lookback_days": 7})
        
        assert "Google News" in result
        assert "Google News Test" in result
    
    @patch('tradingagents.tools.international_news_tools.GoogleNews', side_effect=ImportError)
    def test_fetch_google_news_library_not_installed(self, mock_google):
        """测试GoogleNews库未安装的情况"""
        result = fetch_google_news.invoke({"keywords": "test", "lookback_days": 7})
        
        assert "未安装" in result or "not installed" in result.lower()


class TestMarkdownFormatter:
    """测试Markdown格式化"""
    
    def test_format_news_to_markdown(self):
        """测试新闻格式化为Markdown"""
        articles = [
            {
                "title": "Test Article 1",
                "publishedAt": "2025-12-10T08:00:00Z",
                "description": "Test description 1",
                "url": "https://test1.com"
            },
            {
                "title": "Test Article 2",
                "publishedAt": "2025-12-11T09:00:00Z",
                "description": "Test description 2",
                "url": "https://test2.com"
            }
        ]
        
        result = _format_news_to_markdown(articles, "TestSource", "test keywords")
        
        # 验证格式
        assert "## TestSource" in result
        assert "test keywords" in result
        assert "### 1. Test Article 1" in result
        assert "### 2. Test Article 2" in result
        assert "**发布时间**" in result
        assert "**摘要**" in result
        assert "**链接**" in result
    
    def test_format_empty_articles(self):
        """测试空新闻列表"""
        result = _format_news_to_markdown([], "TestSource", "test")
        
        assert "暂无相关新闻" in result


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
