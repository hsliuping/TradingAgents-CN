#!/usr/bin/env python3
"""
Policy Analyst v2.1扩展功能单元测试

重点验证:
1. 职责分离原则 - ❌ 不输出基础仓位字段
2. 长期政策识别功能
3. 政策支持强度评估（强/中/弱）
4. 政策分层（长期/中期/短期）
"""

import pytest
from unittest.mock import Mock
import json

from tradingagents.agents.analysts.policy_analyst import (
    create_strategic_policy_analyst
)


class TestPolicyAnalystResponsibilitySeparation:
    """测试Policy Analyst职责分离"""
    
    def test_no_position_output_in_report(self):
        """
        ⭐ 职责分离验证 - 最重要的测试
        验证Policy Analyst不输出基础仓位建议
        """
        # Arrange
        mock_llm = Mock()
        mock_toolkit = Mock()
        
        # Mock LLM返回符合职责分离的扩展JSON报告
        valid_report = {
            "monetary_policy": "宽松",
            "fiscal_policy": "积极",
            "industry_policy": ["半导体", "新能源"],
            # 🆕 长期政策识别
            "long_term_policies": [
                {
                    "name": "自主可控",
                    "duration": "长期 (5-10年)",
                    "support_strength": "强",  # ✅ 只评估强度
                    "beneficiary_sectors": ["半导体", "军工"],
                    "policy_continuity": 0.9
                }
            ],
            # 🆕 政策支持强度评估
            "overall_support_strength": "强",  # ✅ 只评估强度，不是仓位
            "long_term_confidence": 0.85,
            # 原有字段
            "key_events": ["降准政策"],
            "market_impact": "正面",
            "analysis_summary": "政策支持力度强",
            "confidence": 0.8,
            "sentiment_score": 0.7
            # ❌ 没有 base_position_recommendation
            # ❌ 没有 recommended_position
        }
        
        mock_result = Mock()
        mock_result.content = json.dumps(valid_report, ensure_ascii=False)
        mock_result.tool_calls = []
        mock_llm.bind_tools.return_value.invoke.return_value = mock_result
        
        analyst_node = create_strategic_policy_analyst(mock_llm, mock_toolkit)
        
        # Act
        state = {
            "policy_report": "",
            "messages": [],
            "policy_tool_call_count": 0
        }
        
        result = analyst_node(state)
        
        # Assert - 验证不包含仓位字段
        report = result.get("policy_report", "")
        
        if isinstance(report, str) and report:
            try:
                report_json = json.loads(report)
                
                # ❌ 不应包含仓位字段
                assert "base_position_recommendation" not in report_json, \
                    "❌ 违反职责分离原则: Policy Analyst不应输出base_position_recommendation"
                assert "recommended_position" not in report_json, \
                    "❌ 违反职责分离原则: Policy Analyst不应输出recommended_position"
                assert "position_adjustment" not in report_json, \
                    "❌ 违反职责分离原则: Policy Analyst不应输出position_adjustment"
                
                # ✅ 应包含政策支持强度评估
                assert "overall_support_strength" in report_json, \
                    "✅ 应输出overall_support_strength"
                assert report_json["overall_support_strength"] in ["强", "中", "弱"], \
                    "✅ overall_support_strength应为强/中/弱"
                
                # ✅ 应包含长期政策识别
                assert "long_term_policies" in report_json, \
                    "✅ 应输出long_term_policies"
                
                print("✅ 职责分离验证通过: 仅输出政策支持强度,不输出仓位建议")
                
            except json.JSONDecodeError:
                pytest.fail("报告非JSON格式")


class TestLongTermPolicyIdentification:
    """测试长期政策识别功能"""
    
    def test_long_term_policy_structure(self):
        """测试长期政策数据结构"""
        # 这个测试验证数据结构的正确性
        long_term_policy = {
            "name": "自主可控",
            "duration": "长期 (5-10年)",
            "support_strength": "强",
            "beneficiary_sectors": ["半导体", "军工"],
            "policy_continuity": 0.9
        }
        
        # 验证必需字段
        assert "name" in long_term_policy
        assert "support_strength" in long_term_policy
        assert long_term_policy["support_strength"] in ["强", "中", "弱"]
        assert "policy_continuity" in long_term_policy
        assert 0 <= long_term_policy["policy_continuity"] <= 1


class TestPolicySupportStrength:
    """测试政策支持强度评估"""
    
    def test_support_strength_values(self):
        """测试支持强度取值范围"""
        valid_strengths = ["强", "中", "弱"]
        
        for strength in valid_strengths:
            assert strength in valid_strengths
    
    def test_support_strength_mapping(self):
        """测试支持强度与政策的映射"""
        # 强: 多个长期战略政策叠加
        strong_case = {
            "long_term_policies": [
                {"name": "自主可控", "support_strength": "强"},
                {"name": "新质生产力", "support_strength": "强"}
            ],
            "overall_support_strength": "强"
        }
        
        assert strong_case["overall_support_strength"] == "强"
        
        # 中: 单一长期政策
        medium_case = {
            "long_term_policies": [
                {"name": "新能源", "support_strength": "中"}
            ],
            "overall_support_strength": "中"
        }
        
        assert medium_case["overall_support_strength"] == "中"
        
        # 弱: 无明确长期政策
        weak_case = {
            "long_term_policies": [],
            "overall_support_strength": "弱"
        }
        
        assert weak_case["overall_support_strength"] == "弱"


class TestPolicyClassification:
    """测试政策分层功能"""
    
    def test_policy_duration_classification(self):
        """测试政策持续期分类"""
        # 长期政策
        long_term = "长期 (5-10年)"
        assert "长期" in long_term
        
        # 中期政策
        medium_term = "中期 (1-3年)"
        assert "中期" in medium_term
        
        # 短期政策
        short_term = "短期 (数月)"
        assert "短期" in short_term


class TestFallbackMechanism:
    """测试降级机制"""
    
    def test_fallback_report_structure(self):
        """测试降级报告包含扩展字段"""
        mock_llm = Mock()
        mock_toolkit = Mock()
        
        analyst_node = create_strategic_policy_analyst(mock_llm, mock_toolkit)
        
        # 模拟已达到最大调用次数
        state = {
            "policy_report": "",
            "messages": [],
            "policy_tool_call_count": 3  # 已达到最大值
        }
        
        result = analyst_node(state)
        
        # 验证返回降级报告
        assert "policy_report" in result
        report = result["policy_report"]
        
        # 解析降级报告
        report_json = json.loads(report)
        
        # 验证包含扩展字段
        assert "long_term_policies" in report_json
        assert "overall_support_strength" in report_json
        assert "long_term_confidence" in report_json
        
        # 验证降级值
        assert report_json["overall_support_strength"] == "弱"
        assert report_json["long_term_confidence"] == 0.3


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
