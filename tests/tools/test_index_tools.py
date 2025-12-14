#!/usr/bin/env python3
"""
指数分析工具单元测试
测试index_tools中的LangChain工具
"""

import pytest
from unittest.mock import Mock, patch


class TestFetchMacroData:
    """测试fetch_macro_data工具"""
    
    def test_tool_exists(self):
        """测试工具是否存在"""
        from tradingagents.tools.index_tools import fetch_macro_data
        
        assert fetch_macro_data is not None
        assert callable(fetch_macro_data)
    
    def test_tool_has_correct_attributes(self):
        """测试工具属性"""
        from tradingagents.tools.index_tools import fetch_macro_data
        
        # LangChain @tool装饰器应该设置这些属性
        assert hasattr(fetch_macro_data, 'name')
        assert hasattr(fetch_macro_data, 'description')
    
    def test_tool_returns_string(self):
        """测试工具返回字符串"""
        from tradingagents.tools.index_tools import fetch_macro_data
        
        result = fetch_macro_data.invoke({"query_date": None})
        
        assert isinstance(result, str)
        assert len(result) > 0
    
    def test_tool_with_specific_date(self):
        """测试指定日期调用"""
        from tradingagents.tools.index_tools import fetch_macro_data
        
        result = fetch_macro_data.invoke({"query_date": "2024-12-01"})
        
        assert isinstance(result, str)
        # 应该包含一些关键词
        assert any(keyword in result for keyword in ['GDP', 'CPI', 'PMI', 'M2', 'LPR'])


class TestFetchPolicyNews:
    """测试fetch_policy_news工具"""
    
    def test_tool_exists(self):
        """测试工具是否存在"""
        from tradingagents.tools.index_tools import fetch_policy_news
        
        assert fetch_policy_news is not None
        assert callable(fetch_policy_news)
    
    def test_tool_returns_string(self):
        """测试工具返回字符串"""
        from tradingagents.tools.index_tools import fetch_policy_news
        
        result = fetch_policy_news.invoke({"lookback_days": 7})
        
        assert isinstance(result, str)
        assert len(result) > 0
    
    def test_tool_with_different_lookback(self):
        """测试不同回溯天数"""
        from tradingagents.tools.index_tools import fetch_policy_news
        
        result_7d = fetch_policy_news.invoke({"lookback_days": 7})
        result_14d = fetch_policy_news.invoke({"lookback_days": 14})
        
        assert isinstance(result_7d, str)
        assert isinstance(result_14d, str)


class TestFetchSectorRotation:
    """测试fetch_sector_rotation工具"""
    
    def test_tool_exists(self):
        """测试工具是否存在"""
        from tradingagents.tools.index_tools import fetch_sector_rotation
        
        assert fetch_sector_rotation is not None
        assert callable(fetch_sector_rotation)
    
    def test_tool_returns_string(self):
        """测试工具返回字符串"""
        from tradingagents.tools.index_tools import fetch_sector_rotation
        
        result = fetch_sector_rotation.invoke({"trade_date": None})
        
        assert isinstance(result, str)
        assert len(result) > 0
    
    def test_tool_with_specific_date(self):
        """测试指定日期调用"""
        from tradingagents.tools.index_tools import fetch_sector_rotation
        
        result = fetch_sector_rotation.invoke({"trade_date": "2024-12-01"})
        
        assert isinstance(result, str)
        # 应该包含板块相关关键词
        assert any(keyword in result for keyword in ['板块', '涨', '跌', '资金'])


class TestToolErrorHandling:
    """测试工具错误处理"""
    
    @patch('tradingagents.dataflows.index_data.get_index_data_provider')
    def test_macro_data_error_handling(self, mock_provider):
        """测试宏观数据工具错误处理"""
        from tradingagents.tools.index_tools import fetch_macro_data
        
        # 模拟provider抛出异常
        mock_provider.side_effect = Exception("Test error")
        
        result = fetch_macro_data.invoke({"query_date": None})
        
        # 应该返回错误信息，而不是抛出异常
        assert isinstance(result, str)
        assert "失败" in result or "错误" in result
    
    @patch('tradingagents.dataflows.index_data.get_index_data_provider')
    def test_policy_news_error_handling(self, mock_provider):
        """测试政策新闻工具错误处理"""
        from tradingagents.tools.index_tools import fetch_policy_news
        
        # 模拟provider抛出异常
        mock_provider.side_effect = Exception("Test error")
        
        result = fetch_policy_news.invoke({"lookback_days": 7})
        
        # 应该返回错误信息，而不是抛出异常
        assert isinstance(result, str)
        assert "失败" in result or "错误" in result


class TestMarkdownFormatting:
    """测试Markdown格式化"""
    
    def test_macro_data_markdown(self):
        """测试宏观数据Markdown格式"""
        from tradingagents.tools.index_tools import fetch_macro_data
        
        result = fetch_macro_data.invoke({"query_date": None})
        
        # 应该包含Markdown标记
        assert '#' in result  # 标题
        assert '**' in result or '-' in result  # 加粗或列表
    
    def test_news_markdown(self):
        """测试新闻Markdown格式"""
        from tradingagents.tools.index_tools import fetch_policy_news
        
        result = fetch_policy_news.invoke({"lookback_days": 7})
        
        # 应该包含Markdown标记
        assert '#' in result  # 标题
    
    def test_sector_markdown(self):
        """测试板块数据Markdown格式"""
        from tradingagents.tools.index_tools import fetch_sector_rotation
        
        result = fetch_sector_rotation.invoke({"trade_date": None})
        
        # 应该包含Markdown标记
        assert '#' in result  # 标题


class TestIndexAnalysisToolsList:
    """测试工具列表导出"""
    
    def test_tools_list_exists(self):
        """测试INDEX_ANALYSIS_TOOLS列表存在"""
        from tradingagents.tools.index_tools import INDEX_ANALYSIS_TOOLS
        
        assert INDEX_ANALYSIS_TOOLS is not None
        assert isinstance(INDEX_ANALYSIS_TOOLS, list)
        assert len(INDEX_ANALYSIS_TOOLS) == 3
    
    def test_all_tools_in_list(self):
        """测试所有工具都在列表中"""
        from tradingagents.tools.index_tools import (
            INDEX_ANALYSIS_TOOLS,
            fetch_macro_data,
            fetch_policy_news,
            fetch_sector_rotation
        )
        
        assert fetch_macro_data in INDEX_ANALYSIS_TOOLS
        assert fetch_policy_news in INDEX_ANALYSIS_TOOLS
        assert fetch_sector_rotation in INDEX_ANALYSIS_TOOLS


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
