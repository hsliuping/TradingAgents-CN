#!/usr/bin/env python3
"""
Macro Analyst 单元测试
"""

import unittest
import json
from unittest.mock import Mock

from tradingagents.agents.analysts.macro_analyst import create_macro_analyst

class TestMacroAnalyst(unittest.TestCase):
    """测试宏观分析师节点"""
    
    def setUp(self):
        self.mock_llm = Mock()
        self.mock_toolkit = Mock()
        self.analyst_node = create_macro_analyst(self.mock_llm, self.mock_toolkit)
    
    def test_existing_report_skip(self):
        """测试已有报告时跳过分析"""
        existing_report = "Existing Report Content" * 10 # 确保长度足够
        state = {
            "macro_report": existing_report,
            "macro_tool_call_count": 0,
            "messages": []
        }
        
        # 确保 tool_calls 属性存在，避免 Mock 对象的 len() 错误
        mock_result = Mock()
        mock_result.tool_calls = []
        mock_result.content = "Mock Content"
        self.mock_llm.bind_tools.return_value.invoke.return_value = mock_result
        
        result = self.analyst_node(state)
        self.assertEqual(result["macro_report"], existing_report)
        # 确认没有调用 LLM
        # 注意：由于 bind_tools 的存在，直接 assert_not_called 可能不准确，应该检查 invoke 是否被调用
        # 但如果是已有报告，代码逻辑是在 invoke 之前返回的
        self.mock_llm.bind_tools.return_value.invoke.assert_not_called()
        
    def test_fallback_logic(self):
        """测试达到最大调用次数时的降级逻辑"""
        state = {
            "macro_report": "",
            "macro_tool_call_count": 5, # 达到最大值
            "messages": []
        }
        
        result = self.analyst_node(state)
        report = json.loads(result["macro_report"])
        
        self.assertIn("analysis_summary", report)
        self.assertIn("降级", report["analysis_summary"])
        self.mock_llm.assert_not_called()

if __name__ == "__main__":
    unittest.main()
