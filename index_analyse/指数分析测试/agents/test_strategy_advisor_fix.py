'''
Author: zhengweicheng 46236959+zwczwczwc@users.noreply.github.com
Date: 2026-01-01 02:19:13
LastEditors: zhengweicheng 46236959+zwczwczwc@users.noreply.github.com
LastEditTime: 2026-01-01 02:30:35
FilePath: /TradingAgents-CN-Test/tests/agents/test_strategy_advisor_fix.py
Description: 这是默认设置,请设置`customMade`, 打开koroFileHeader查看配置 进行设置: https://github.com/OBKoro1/koro1FileHeader/wiki/%E9%85%8D%E7%BD%AE
'''
#!/usr/bin/env python3
"""
Strategy Advisor 修复验证测试
专门验证 depth_instruction 变量未定义问题的修复
"""

import unittest
import json
from unittest.mock import Mock

from tradingagents.agents.analysts.strategy_advisor import create_strategy_advisor

class TestStrategyAdvisorFix(unittest.TestCase):
    """验证 Strategy Advisor 的修复"""
    
    def setUp(self):
        self.mock_llm = Mock()
        # 模拟 LLM 返回
        mock_response = Mock()
        mock_response.content = json.dumps({
            "market_outlook": "中性",
            "key_risks": [],
            "opportunity_sectors": [],
            "rationale": "测试",
            "confidence": 0.5
        })
        mock_response.tool_calls = []
        self.mock_llm.return_value = mock_response
        
        self.advisor_node = create_strategy_advisor(self.mock_llm)
    
    def test_depth_instruction_variable(self):
        """测试 depth_instruction 变量是否正确定义和传递"""
        # 构造 state，不包含 research_depth，使用默认值
        state = {
            "macro_report": json.dumps({"sentiment_score": 0.5}),
            "policy_report": json.dumps({"overall_support_strength": "中"}),
            "sector_report": json.dumps({"sentiment_score": 0.5}),
            "international_news_report": json.dumps({"impact_strength": "低"}),
            "messages": []
        }
        
        # 运行节点，如果 depth_instruction 未定义，这里会抛出 NameError
        try:
            result = self.advisor_node(state)
            self.assertIn("strategy_report", result)
            print("✅ 默认深度测试通过")
        except NameError as e:
            self.fail(f"❌ 默认深度测试失败: {e}")
            
    def test_specific_research_depth(self):
        """测试指定 research_depth 的情况"""
        state = {
            "macro_report": json.dumps({"sentiment_score": 0.5}),
            "policy_report": json.dumps({"overall_support_strength": "中"}),
            "sector_report": json.dumps({"sentiment_score": 0.5}),
            "international_news_report": json.dumps({"impact_strength": "低"}),
            "messages": [],
            "research_depth": "快速"  # 指定深度
        }
        
        try:
            result = self.advisor_node(state)
            self.assertIn("strategy_report", result)
            print("✅ 快速深度测试通过")
        except NameError as e:
            self.fail(f"❌ 快速深度测试失败: {e}")

if __name__ == "__main__":
    unittest.main()
