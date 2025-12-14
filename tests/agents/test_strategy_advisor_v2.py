#!/usr/bin/env python3
"""
Strategy Advisor v2.1 单元测试

测试coverage:
- 决策算法集成
- 报告结构验证
- 职责分离验证
- 降级处理验证
- 完整决策流程

Version: v2.1.0 (阶段三)
"""

import unittest
import json
from unittest.mock import Mock, MagicMock, patch

from tradingagents.agents.analysts.strategy_advisor import (
    create_strategy_advisor,
    _generate_fallback_report,
    _extract_json_report
)


class TestStrategyAdvisorV2(unittest.TestCase):
    """测试Strategy Advisor v2.1重构版"""
    
    def setUp(self):
        """测试前准备"""
        # Mock LLM
        self.mock_llm = Mock()
        
        # 创建Strategy Advisor节点
        self.advisor_node = create_strategy_advisor(self.mock_llm)
    
    def test_complete_decision_flow(self):
        """⭐ 测试完整决策流程"""
        # 准备完整的上游报告
        state = {
            "macro_report": json.dumps({
                "sentiment_score": 0.7,
                "economic_cycle": "复苏期",
                "confidence": 0.8
            }),
            "policy_report": json.dumps({
                "overall_support_strength": "强",
                "long_term_confidence": 0.9,
                "long_term_policies": [
                    {
                        "name": "自主可控",
                        "support_strength": "强"
                    }
                ]
            }),
            "international_news_report": json.dumps({
                "impact_strength": "高",
                "confidence": 0.85,
                "impact_duration": "中期",
                "overall_impact": "国际半导体政策传闻"
            }),
            "sector_report": json.dumps({
                "sentiment_score": 0.75,
                "hot_themes": ["半导体", "AI"]
            }),
            "messages": []
        }
        
        # Mock LLM返回
        mock_response = Mock()
        mock_response.content = json.dumps({
            "market_outlook": "看多",
            "key_risks": ["地缘政治风险", "流动性收紧"],
            "opportunity_sectors": ["半导体", "AI"],
            "rationale": "基于强政策支持和国际新闻利好，建议积极配置。",
            "confidence": 0.85
        }, ensure_ascii=False)
        mock_response.tool_calls = []
        
        self.mock_llm.return_value = mock_response
        
        # 执行决策
        result = self.advisor_node(state)
        
        # 验证返回结构
        self.assertIn("messages", result)
        self.assertIn("strategy_report", result)
        
        # 解析策略报告
        report = json.loads(result["strategy_report"])
        
        # 验证核心字段（v2.1新增）
        self.assertIn("final_position", report)
        self.assertIn("position_breakdown", report)
        self.assertIn("adjustment_triggers", report)
        self.assertIn("decision_rationale", report)
        
        # 验证LLM生成字段
        self.assertIn("market_outlook", report)
        self.assertIn("key_risks", report)
        self.assertIn("opportunity_sectors", report)
        self.assertIn("rationale", report)
        
        # 验证数值合理性
        self.assertGreaterEqual(report["final_position"], 0.0)
        self.assertLessEqual(report["final_position"], 1.0)
    
    def test_position_breakdown_structure(self):
        """⭐ 测试分层持仓策略输出"""
        state = {
            "macro_report": json.dumps({"sentiment_score": 0.6}),
            "policy_report": json.dumps({
                "overall_support_strength": "中",
                "long_term_confidence": 0.7
            }),
            "international_news_report": json.dumps({
                "impact_strength": "中",
                "confidence": 0.7,
                "impact_duration": "中期"
            }),
            "sector_report": json.dumps({"sentiment_score": 0.65}),
            "messages": []
        }
        
        mock_response = Mock()
        mock_response.content = json.dumps({
            "market_outlook": "中性",
            "key_risks": [],
            "opportunity_sectors": [],
            "rationale": "测试",
            "confidence": 0.7
        })
        mock_response.tool_calls = []
        self.mock_llm.return_value = mock_response
        
        result = self.advisor_node(state)
        report = json.loads(result["strategy_report"])
        
        # 验证分层持仓字段
        breakdown = report["position_breakdown"]
        self.assertIn("core_holding", breakdown)
        self.assertIn("tactical_allocation", breakdown)
        self.assertIn("cash_reserve", breakdown)
        
        # 验证数值合理性
        self.assertGreaterEqual(breakdown["core_holding"], 0.0)
        self.assertGreaterEqual(breakdown["tactical_allocation"], 0.0)
        self.assertGreaterEqual(breakdown["cash_reserve"], 0.0)
        
        # 验证三部分之和接近1
        total = breakdown["core_holding"] + breakdown["tactical_allocation"] + breakdown["cash_reserve"]
        self.assertAlmostEqual(total, 1.0, places=1)
    
    def test_adjustment_triggers_output(self):
        """⭐ 测试动态触发条件输出"""
        state = {
            "macro_report": json.dumps({"sentiment_score": 0.5}),
            "policy_report": json.dumps({
                "overall_support_strength": "中",
                "long_term_confidence": 0.6
            }),
            "international_news_report": json.dumps({
                "impact_strength": "低",
                "confidence": 0.6,
                "impact_duration": "短期",
                "key_news": [
                    {"category": "政策传闻", "title": "传闻政策支持"}
                ]
            }),
            "sector_report": json.dumps({"sentiment_score": 0.55}),
            "messages": []
        }
        
        mock_response = Mock()
        mock_response.content = json.dumps({
            "market_outlook": "中性",
            "key_risks": [],
            "opportunity_sectors": [],
            "rationale": "测试",
            "confidence": 0.6
        })
        mock_response.tool_calls = []
        self.mock_llm.return_value = mock_response
        
        result = self.advisor_node(state)
        report = json.loads(result["strategy_report"])
        
        # 验证触发条件字段
        triggers = report["adjustment_triggers"]
        self.assertIn("increase_to", triggers)
        self.assertIn("increase_condition", triggers)
        self.assertIn("decrease_to", triggers)
        self.assertIn("decrease_condition", triggers)
        
        # 检测到政策传闻，应该有特殊触发条件
        self.assertEqual(triggers["increase_to"], 0.90)
        self.assertIn("官宣", triggers["increase_condition"])
    
    def test_no_international_news_fallback(self):
        """测试缺少国际新闻报告时的降级处理"""
        state = {
            "macro_report": json.dumps({"sentiment_score": 0.5}),
            "policy_report": json.dumps({
                "overall_support_strength": "中",
                "long_term_confidence": 0.6
            }),
            "international_news_report": "",  # 空报告
            "sector_report": json.dumps({"sentiment_score": 0.55}),
            "messages": []
        }
        
        mock_response = Mock()
        mock_response.content = json.dumps({
            "market_outlook": "中性",
            "key_risks": [],
            "opportunity_sectors": [],
            "rationale": "测试",
            "confidence": 0.6
        })
        mock_response.tool_calls = []
        self.mock_llm.return_value = mock_response
        
        result = self.advisor_node(state)
        report = json.loads(result["strategy_report"])
        
        # 应该使用默认值，不影响决策流程
        self.assertIn("final_position", report)
        self.assertGreaterEqual(report["final_position"], 0.0)
    
    def test_incomplete_upstream_reports(self):
        """测试上游报告不完整时的降级处理"""
        state = {
            "macro_report": "",  # 缺失
            "policy_report": json.dumps({"overall_support_strength": "中"}),
            "sector_report": "",  # 缺失
            "messages": []
        }
        
        result = self.advisor_node(state)
        report = json.loads(result["strategy_report"])
        
        # 验证降级报告
        self.assertEqual(report["final_position"], 0.5)
        self.assertEqual(report["market_outlook"], "中性")
        self.assertIn("数据不完整", report["key_risks"])
        self.assertEqual(report["confidence"], 0.3)
    
    def test_strong_policy_high_news_scenario(self):
        """场景测试: 强政策 + 高新闻影响"""
        state = {
            "macro_report": json.dumps({"sentiment_score": 0.75}),
            "policy_report": json.dumps({
                "overall_support_strength": "强",
                "long_term_confidence": 0.95
            }),
            "international_news_report": json.dumps({
                "impact_strength": "高",
                "confidence": 0.9,
                "impact_duration": "长期"
            }),
            "sector_report": json.dumps({"sentiment_score": 0.8}),
            "messages": []
        }
        
        mock_response = Mock()
        mock_response.content = json.dumps({
            "market_outlook": "看多",
            "key_risks": [],
            "opportunity_sectors": ["半导体"],
            "rationale": "强政策+高新闻影响",
            "confidence": 0.9
        })
        mock_response.tool_calls = []
        self.mock_llm.return_value = mock_response
        
        result = self.advisor_node(state)
        report = json.loads(result["strategy_report"])
        
        # 强烈看多场景，仓位应该较高
        self.assertGreaterEqual(report["final_position"], 0.70)
        self.assertEqual(report["market_outlook"], "看多")
    
    def test_weak_policy_low_news_scenario(self):
        """场景测试: 弱政策 + 低新闻影响"""
        state = {
            "macro_report": json.dumps({"sentiment_score": 0.3}),
            "policy_report": json.dumps({
                "overall_support_strength": "弱",
                "long_term_confidence": 0.4
            }),
            "international_news_report": json.dumps({
                "impact_strength": "低",
                "confidence": 0.5,
                "impact_duration": "短期"
            }),
            "sector_report": json.dumps({"sentiment_score": 0.35}),
            "messages": []
        }
        
        mock_response = Mock()
        mock_response.content = json.dumps({
            "market_outlook": "看空",
            "key_risks": ["政策支持弱"],
            "opportunity_sectors": [],
            "rationale": "弱政策+低新闻影响",
            "confidence": 0.5
        })
        mock_response.tool_calls = []
        self.mock_llm.return_value = mock_response
        
        result = self.advisor_node(state)
        report = json.loads(result["strategy_report"])
        
        # 弱势场景，仓位应该较低
        self.assertLessEqual(report["final_position"], 0.50)
    
    def test_decision_rationale_format(self):
        """测试决策依据格式"""
        state = {
            "macro_report": json.dumps({"sentiment_score": 0.6}),
            "policy_report": json.dumps({
                "overall_support_strength": "中",
                "long_term_confidence": 0.7
            }),
            "international_news_report": json.dumps({
                "impact_strength": "中",
                "confidence": 0.7,
                "impact_duration": "中期"
            }),
            "sector_report": json.dumps({"sentiment_score": 0.65}),
            "messages": []
        }
        
        mock_response = Mock()
        mock_response.content = json.dumps({
            "market_outlook": "中性",
            "key_risks": [],
            "opportunity_sectors": [],
            "rationale": "测试",
            "confidence": 0.7
        })
        mock_response.tool_calls = []
        self.mock_llm.return_value = mock_response
        
        result = self.advisor_node(state)
        report = json.loads(result["strategy_report"])
        
        # 验证决策依据格式
        rationale = report["decision_rationale"]
        self.assertIn("基于", rationale)
        self.assertIn("政策支持", rationale)
        self.assertIn("新闻影响", rationale)
        self.assertIn("%", rationale)


class TestHelperFunctions(unittest.TestCase):
    """测试辅助函数"""
    
    def test_generate_fallback_report(self):
        """测试降级报告生成"""
        fallback = _generate_fallback_report()
        report = json.loads(fallback)
        
        # 验证必要字段
        self.assertEqual(report["final_position"], 0.5)
        self.assertEqual(report["market_outlook"], "中性")
        self.assertIn("数据不完整", report["key_risks"])
        self.assertEqual(report["confidence"], 0.3)
        
        # 验证v2.1新增字段
        self.assertIn("position_breakdown", report)
        self.assertIn("adjustment_triggers", report)
        self.assertIn("decision_rationale", report)
    
    def test_extract_json_report_valid(self):
        """测试JSON提取 - 有效JSON"""
        content = '这是前缀 {"key": "value", "number": 123} 这是后缀'
        result = _extract_json_report(content)
        
        self.assertIsNotNone(result)
        parsed = json.loads(result)
        self.assertEqual(parsed["key"], "value")
        self.assertEqual(parsed["number"], 123)
    
    def test_extract_json_report_invalid(self):
        """测试JSON提取 - 无效JSON"""
        content = "这里没有JSON"
        result = _extract_json_report(content)
        
        self.assertEqual(result, "")
    
    def test_extract_json_report_malformed(self):
        """测试JSON提取 - 格式错误的JSON"""
        content = '{"key": "value", "number": }'
        result = _extract_json_report(content)
        
        self.assertEqual(result, "")


class TestResponsibilitySeparation(unittest.TestCase):
    """⭐ 职责分离验证测试"""
    
    def setUp(self):
        """测试前准备"""
        self.mock_llm = Mock()
        self.advisor_node = create_strategy_advisor(self.mock_llm)
    
    def test_no_upstream_position_reading(self):
        """⭐ 验证不从上游读取仓位值"""
        # 上游报告包含position字段（旧版遗留）
        state = {
            "macro_report": json.dumps({
                "sentiment_score": 0.7,
                "recommended_position": 0.8  # ❌ 旧版字段
            }),
            "policy_report": json.dumps({
                "overall_support_strength": "强",
                "long_term_confidence": 0.9,
                "base_position_recommendation": 0.75  # ❌ 不应存在的字段
            }),
            "international_news_report": json.dumps({
                "impact_strength": "高",
                "confidence": 0.85,
                "position_adjustment": 0.15  # ❌ 不应存在的字段
            }),
            "sector_report": json.dumps({"sentiment_score": 0.75}),
            "messages": []
        }
        
        mock_response = Mock()
        mock_response.content = json.dumps({
            "market_outlook": "看多",
            "key_risks": [],
            "opportunity_sectors": [],
            "rationale": "测试",
            "confidence": 0.85
        })
        mock_response.tool_calls = []
        self.mock_llm.return_value = mock_response
        
        result = self.advisor_node(state)
        report = json.loads(result["strategy_report"])
        
        # 最终仓位应该由决策算法计算，不应等于上游的position值
        # 决策算法基于"强"政策和"高"新闻，应该在0.70-0.85之间
        final_pos = report["final_position"]
        self.assertNotEqual(final_pos, 0.8)  # 不等于macro的recommended_position
        self.assertNotEqual(final_pos, 0.75)  # 不等于policy的base_position
        
        # 应该是算法计算的结果
        self.assertGreaterEqual(final_pos, 0.65)
        self.assertLessEqual(final_pos, 0.90)
    
    def test_only_extract_indicators(self):
        """⭐ 验证只提取评估指标，不提取仓位"""
        state = {
            "macro_report": json.dumps({
                "sentiment_score": 0.6,  # ✅ 评估指标
                "recommended_position": 0.7  # ❌ 应忽略
            }),
            "policy_report": json.dumps({
                "overall_support_strength": "中",  # ✅ 评估指标
                "long_term_confidence": 0.7  # ✅ 评估指标
            }),
            "international_news_report": json.dumps({
                "impact_strength": "中",  # ✅ 评估指标
                "confidence": 0.7,  # ✅ 评估指标
                "impact_duration": "中期"  # ✅ 评估指标
            }),
            "sector_report": json.dumps({"sentiment_score": 0.65}),
            "messages": []
        }
        
        mock_response = Mock()
        mock_response.content = json.dumps({
            "market_outlook": "中性",
            "key_risks": [],
            "opportunity_sectors": [],
            "rationale": "测试",
            "confidence": 0.7
        })
        mock_response.tool_calls = []
        self.mock_llm.return_value = mock_response
        
        result = self.advisor_node(state)
        report = json.loads(result["strategy_report"])
        
        # 验证决策依据中包含的是评估指标，不是仓位值
        rationale = report["decision_rationale"]
        self.assertIn("中", rationale)  # 政策支持强度
        # 不应该包含0.7这个上游的recommended_position
        

if __name__ == "__main__":
    unittest.main()
