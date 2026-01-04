#!/usr/bin/env python3
"""
Sector Analyst Regression Test Script
Based on: index_analyse/指数分析测试/agents/test_sector_analyst.py
"""

import sys
import os
import unittest
import json
from unittest.mock import Mock, MagicMock

# Mock pymongo before importing tradingagents to prevent real MongoDB connection
sys.modules["pymongo"] = MagicMock()
sys.modules["pymongo.errors"] = MagicMock()
sys.modules["pymongo.collection"] = MagicMock()
sys.modules["pymongo.database"] = MagicMock()

# Add project root to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from tradingagents.agents.analysts.sector_analyst import create_sector_analyst

class TestSectorAnalyst(unittest.TestCase):
    """测试板块分析师节点"""
    
    def setUp(self):
        self.mock_llm = Mock()
        self.mock_toolkit = Mock()
        self.analyst_node = create_sector_analyst(self.mock_llm, self.mock_toolkit)
    
    def test_existing_report_skip(self):
        """测试已有报告时跳过分析"""
        existing_report = "Existing Sector Report" * 10 # 确保长度足够
        state = {
            "sector_report": existing_report,
            "sector_tool_call_count": 0,
            "messages": []
        }
        
        # 确保 tool_calls 属性存在
        mock_result = Mock()
        mock_result.tool_calls = []
        mock_result.content = "Mock Content"
        self.mock_llm.bind_tools.return_value.invoke.return_value = mock_result
        
        result = self.analyst_node(state)
        self.assertEqual(result["sector_report"], existing_report)
        self.mock_llm.bind_tools.return_value.invoke.assert_not_called()
        
    def test_fallback_logic(self):
        """测试达到最大调用次数时的降级逻辑"""
        state = {
            "sector_report": "",
            "sector_tool_call_count": 5, # 达到最大值
            "messages": []
        }
        
        result = self.analyst_node(state)
        report = json.loads(result["sector_report"])
        
        self.assertIn("analysis_summary", report)
        # 更新断言文案以匹配实际代码
        self.assertIn("数据获取限制", report["analysis_summary"])
        self.mock_llm.bind_tools.return_value.invoke.assert_not_called()

if __name__ == "__main__":
    unittest.main()
