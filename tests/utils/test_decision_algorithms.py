#!/usr/bin/env python3
"""
决策算法模块单元测试

测试coverage:
- 指标提取函数
- 基础仓位决策算法
- 短期调整决策算法
- 分层持仓策略生成
- 动态触发条件生成
- 综合决策函数

Version: v2.1.0 (阶段三)
"""

import unittest
import json
from unittest.mock import patch

from tradingagents.agents.utils.decision_algorithms import (
    extract_macro_sentiment_score,
    extract_economic_cycle,
    extract_policy_support_strength,
    extract_policy_continuity,
    extract_news_impact_strength,
    extract_news_credibility,
    extract_news_duration,
    extract_sector_heat_score,
    calculate_base_position,
    calculate_short_term_adjustment,
    generate_position_breakdown,
    generate_adjustment_triggers,
    make_strategy_decision
)


class TestIndicatorExtraction(unittest.TestCase):
    """测试指标提取函数"""
    
    def test_extract_macro_sentiment_score(self):
        """测试宏观情绪评分提取"""
        report = json.dumps({"sentiment_score": 0.75})
        self.assertEqual(extract_macro_sentiment_score(report), 0.75)
        
        # 测试边界值
        report_high = json.dumps({"sentiment_score": 1.5})  # 超出范围
        self.assertEqual(extract_macro_sentiment_score(report_high), 1.0)
        
        report_low = json.dumps({"sentiment_score": -0.5})  # 低于范围
        self.assertEqual(extract_macro_sentiment_score(report_low), 0.0)
        
        # 测试异常情况
        self.assertEqual(extract_macro_sentiment_score("invalid json"), 0.5)
    
    def test_extract_policy_support_strength(self):
        """测试政策支持强度提取"""
        report = json.dumps({"overall_support_strength": "强"})
        self.assertEqual(extract_policy_support_strength(report), "强")
        
        report_mid = json.dumps({"overall_support_strength": "中"})
        self.assertEqual(extract_policy_support_strength(report_mid), "中")
        
        # 测试异常情况
        self.assertEqual(extract_policy_support_strength("invalid"), "中")
    
    def test_extract_policy_continuity(self):
        """测试政策连续性提取"""
        report = json.dumps({"long_term_confidence": 0.9})
        self.assertEqual(extract_policy_continuity(report), 0.9)
        
        # 测试向后兼容
        report_old = json.dumps({"confidence": 0.8})
        self.assertEqual(extract_policy_continuity(report_old), 0.8)
    
    def test_extract_news_impact_strength(self):
        """测试新闻影响强度提取"""
        report = json.dumps({"impact_strength": "高"})
        self.assertEqual(extract_news_impact_strength(report), "高")
        
        # 测试异常值降级
        report_invalid = json.dumps({"impact_strength": "超高"})
        self.assertEqual(extract_news_impact_strength(report_invalid), "低")
    
    def test_extract_news_duration(self):
        """测试新闻影响持续期提取"""
        report = json.dumps({"impact_duration": "中期"})
        self.assertEqual(extract_news_duration(report), "中期")
        
        # 测试从overall_impact提取
        report2 = json.dumps({"overall_impact": "影响持续中期1-2个月"})
        self.assertIn("中期", extract_news_duration(report2))


class TestBasePositionAlgorithm(unittest.TestCase):
    """测试基础仓位决策算法"""
    
    def test_strong_policy_high_macro(self):
        """场景1: 强政策 + 高宏观"""
        position = calculate_base_position("强", 0.9, 0.7)
        self.assertGreaterEqual(position, 0.60)
        self.assertLessEqual(position, 0.75)
    
    def test_strong_policy_mid_macro(self):
        """场景2: 强政策 + 中宏观"""
        position = calculate_base_position("强", 0.8, 0.5)
        self.assertGreaterEqual(position, 0.55)
        self.assertLessEqual(position, 0.70)
    
    def test_mid_policy_high_macro(self):
        """场景3: 中政策 + 高宏观"""
        position = calculate_base_position("中", 0.7, 0.6)
        self.assertGreaterEqual(position, 0.45)
        self.assertLessEqual(position, 0.60)
    
    def test_weak_policy_low_macro(self):
        """场景4: 弱政策 + 低宏观"""
        position = calculate_base_position("弱", 0.4, 0.3)
        self.assertGreaterEqual(position, 0.35)
        self.assertLessEqual(position, 0.50)
    
    def test_policy_continuity_adjustment(self):
        """测试政策连续性调整"""
        # 高连续性应该提升仓位
        pos_high = calculate_base_position("中", 0.9, 0.5)
        pos_low = calculate_base_position("中", 0.3, 0.5)
        self.assertGreater(pos_high, pos_low)
    
    def test_boundary_values(self):
        """测试边界值处理"""
        # 最小值
        position_min = calculate_base_position("弱", 0.0, 0.0)
        self.assertGreaterEqual(position_min, 0.40)
        
        # 最大值
        position_max = calculate_base_position("强", 1.0, 1.0)
        self.assertLessEqual(position_max, 0.80)


class TestShortTermAdjustment(unittest.TestCase):
    """测试短期调整决策算法"""
    
    def test_high_impact_long_duration(self):
        """场景1: 高影响 + 长期"""
        adj = calculate_short_term_adjustment("高", 0.9, "长期")
        self.assertGreaterEqual(adj, 0.15)
        self.assertLessEqual(adj, 0.20)
    
    def test_high_impact_mid_duration(self):
        """场景2: 高影响 + 中期"""
        adj = calculate_short_term_adjustment("高", 0.8, "中期")
        self.assertGreaterEqual(adj, 0.10)
        self.assertLessEqual(adj, 0.18)
    
    def test_high_impact_short_duration(self):
        """场景3: 高影响 + 短期"""
        adj = calculate_short_term_adjustment("高", 0.7, "短期")
        self.assertGreaterEqual(adj, 0.05)
        self.assertLessEqual(adj, 0.15)
    
    def test_mid_impact(self):
        """场景4: 中影响"""
        adj = calculate_short_term_adjustment("中", 0.8, "中期")
        self.assertGreaterEqual(adj, 0.03)
        self.assertLessEqual(adj, 0.10)
    
    def test_low_impact(self):
        """场景5: 低影响"""
        adj = calculate_short_term_adjustment("低", 0.9, "长期")
        self.assertEqual(adj, 0.0)
    
    def test_credibility_discount(self):
        """测试可信度折扣"""
        # 高可信度
        adj_high = calculate_short_term_adjustment("高", 0.9, "中期")
        # 低可信度
        adj_low = calculate_short_term_adjustment("高", 0.3, "中期")
        self.assertGreater(adj_high, adj_low)
    
    def test_boundary_values(self):
        """测试边界值"""
        # 最大调整
        adj_max = calculate_short_term_adjustment("高", 1.0, "长期")
        self.assertLessEqual(adj_max, 0.20)
        
        # 最小调整
        adj_min = calculate_short_term_adjustment("低", 0.0, "短期")
        self.assertGreaterEqual(adj_min, -0.20)


class TestPositionBreakdown(unittest.TestCase):
    """测试分层持仓策略生成"""
    
    def test_position_breakdown_calculation(self):
        """测试分层计算逻辑"""
        base = 0.60
        adj = 0.10
        final = 0.70
        
        breakdown = generate_position_breakdown(base, adj, final)
        
        # 验证字段存在
        self.assertIn("core_holding", breakdown)
        self.assertIn("tactical_allocation", breakdown)
        self.assertIn("cash_reserve", breakdown)
        
        # 验证计算逻辑
        expected_core = round(base * 0.67, 2)
        expected_tactical = round(base * 0.33 + adj, 2)
        expected_cash = round(1.0 - final, 2)
        
        self.assertEqual(breakdown["core_holding"], expected_core)
        self.assertEqual(breakdown["tactical_allocation"], expected_tactical)
        self.assertEqual(breakdown["cash_reserve"], expected_cash)
    
    def test_sum_equals_one(self):
        """测试三部分之和接近100%"""
        breakdown = generate_position_breakdown(0.50, 0.05, 0.55)
        total = breakdown["core_holding"] + breakdown["tactical_allocation"] + breakdown["cash_reserve"]
        self.assertAlmostEqual(total, 1.0, places=1)
    
    def test_negative_handling(self):
        """测试负值处理"""
        # 极端情况：短期调整为负
        breakdown = generate_position_breakdown(0.45, -0.15, 0.30)
        # 确保所有部分非负
        self.assertGreaterEqual(breakdown["core_holding"], 0.0)
        self.assertGreaterEqual(breakdown["tactical_allocation"], 0.0)
        self.assertGreaterEqual(breakdown["cash_reserve"], 0.0)


class TestAdjustmentTriggers(unittest.TestCase):
    """测试动态触发条件生成"""
    
    def test_policy_rumor_detected(self):
        """测试检测到政策传闻"""
        news_report = json.dumps({
            "key_news": [
                {"category": "政策传闻", "title": "某政策可能出台"}
            ]
        })
        
        triggers = generate_adjustment_triggers("", news_report)
        
        self.assertEqual(triggers["increase_to"], 0.90)
        self.assertIn("官宣", triggers["increase_condition"])
        self.assertEqual(triggers["decrease_to"], 0.40)
        self.assertIn("证伪", triggers["decrease_condition"])
    
    def test_policy_rumor_in_overall_impact(self):
        """测试从overall_impact检测政策传闻"""
        news_report = json.dumps({
            "overall_impact": "近期出现政策传闻，市场反应积极"
        })
        
        triggers = generate_adjustment_triggers("", news_report)
        self.assertEqual(triggers["increase_to"], 0.90)
    
    def test_no_policy_rumor(self):
        """测试无政策传闻场景"""
        news_report = json.dumps({
            "key_news": [
                {"category": "行业事件", "title": "某公司业绩"}
            ]
        })
        
        triggers = generate_adjustment_triggers("", news_report)
        
        self.assertEqual(triggers["increase_to"], 0.80)
        self.assertIn("加码", triggers["increase_condition"])
        self.assertEqual(triggers["decrease_to"], 0.50)
        self.assertIn("恶化", triggers["decrease_condition"])
    
    def test_invalid_input_fallback(self):
        """测试异常输入降级"""
        triggers = generate_adjustment_triggers("", "invalid json")
        # 应该返回默认触发条件
        self.assertIn("increase_to", triggers)
        self.assertIn("decrease_to", triggers)


class TestIntegratedDecision(unittest.TestCase):
    """测试综合决策函数"""
    
    def test_complete_decision_flow(self):
        """测试完整决策流程"""
        macro_report = json.dumps({"sentiment_score": 0.7, "economic_cycle": "复苏期"})
        policy_report = json.dumps({
            "overall_support_strength": "强",
            "long_term_confidence": 0.9
        })
        news_report = json.dumps({
            "impact_strength": "高",
            "confidence": 0.8,
            "impact_duration": "中期"
        })
        sector_report = json.dumps({"sentiment_score": 0.75})
        
        (
            base_position,
            short_term_adjustment,
            final_position,
            position_breakdown,
            adjustment_triggers
        ) = make_strategy_decision(
            macro_report,
            policy_report,
            news_report,
            sector_report
        )
        
        # 验证基础仓位
        self.assertGreaterEqual(base_position, 0.40)
        self.assertLessEqual(base_position, 0.80)
        
        # 验证短期调整
        self.assertGreaterEqual(short_term_adjustment, -0.20)
        self.assertLessEqual(short_term_adjustment, 0.20)
        
        # 验证最终仓位
        self.assertGreaterEqual(final_position, 0.0)
        self.assertLessEqual(final_position, 1.0)
        
        # 验证分层持仓
        self.assertIn("core_holding", position_breakdown)
        self.assertIn("tactical_allocation", position_breakdown)
        self.assertIn("cash_reserve", position_breakdown)
        
        # 验证触发条件
        self.assertIn("increase_to", adjustment_triggers)
        self.assertIn("decrease_to", adjustment_triggers)
    
    def test_strong_bullish_scenario(self):
        """场景测试: 强烈看多（强政策+高新闻影响）"""
        macro_report = json.dumps({"sentiment_score": 0.8})
        policy_report = json.dumps({
            "overall_support_strength": "强",
            "long_term_confidence": 0.95
        })
        news_report = json.dumps({
            "impact_strength": "高",
            "confidence": 0.9,
            "impact_duration": "长期"
        })
        sector_report = json.dumps({"sentiment_score": 0.85})
        
        (_, _, final_position, _, _) = make_strategy_decision(
            macro_report, policy_report, news_report, sector_report
        )
        
        # 强烈看多场景，最终仓位应该较高
        self.assertGreaterEqual(final_position, 0.70)
    
    def test_weak_bearish_scenario(self):
        """场景测试: 弱势看空（弱政策+低新闻影响）"""
        macro_report = json.dumps({"sentiment_score": 0.3})
        policy_report = json.dumps({
            "overall_support_strength": "弱",
            "long_term_confidence": 0.4
        })
        news_report = json.dumps({
            "impact_strength": "低",
            "confidence": 0.5,
            "impact_duration": "短期"
        })
        sector_report = json.dumps({"sentiment_score": 0.35})
        
        (_, _, final_position, _, _) = make_strategy_decision(
            macro_report, policy_report, news_report, sector_report
        )
        
        # 弱势场景，最终仓位应该较低
        self.assertLessEqual(final_position, 0.50)


if __name__ == "__main__":
    unittest.main()
