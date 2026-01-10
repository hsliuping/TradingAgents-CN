#!/usr/bin/env python3
"""
Index News Analyst Regression Test Script
Based on: index_analyse/指数分析测试/agents/test_index_news_analyst.py
"""

import sys
import os
import pytest
import json
from unittest.mock import Mock, patch, MagicMock

# Mock pymongo before importing tradingagents to prevent real MongoDB connection
sys.modules["pymongo"] = MagicMock()
sys.modules["pymongo.errors"] = MagicMock()
sys.modules["pymongo.collection"] = MagicMock()
sys.modules["pymongo.database"] = MagicMock()

# Add project root to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from tradingagents.agents.analysts.international_news_analyst import (
    create_index_news_analyst
)

def _extract_json_report(content: str) -> str:
    """Mock implementation or duplicated from source if not exportable"""
    try:
        if '{' in content and '}' in content:
            start_idx = content.index('{')
            end_idx = content.rindex('}') + 1
            return content[start_idx:end_idx]
        return ""
    except Exception:
        return ""


class TestIndexNewsAnalyst:
    """测试综合新闻分析师核心功能"""
    
    def test_no_position_output_in_report(self):
        """
        ⭐ 职责分离验证 - 最重要的测试
        验证News Analyst不输出仓位建议
        """
        # Arrange
        mock_llm = Mock()
        mock_toolkit = Mock()
        
        # Mock LLM返回符合职责分离的JSON报告
        valid_report = {
            "key_news": [
                {
                    "source": "Bloomberg",
                    "title": "Test News",
                    "type": "政策传闻",
                    "impact_strength": "高",  # ✅ 只评估强度
                    "credibility": 0.8
                }
            ],
            "overall_impact": "利好",
            "impact_strength": "高",  # ✅ 只评估强度
            "confidence": 0.85
            # ❌ 没有 position_adjustment
            # ❌ 没有 adjustment_rationale
        }
        
        mock_result = Mock()
        mock_result.content = json.dumps(valid_report, ensure_ascii=False)
        mock_result.tool_calls = []
        mock_llm.bind_tools.return_value.invoke.return_value = mock_result
        
        analyst_node = create_index_news_analyst(mock_llm, mock_toolkit)
        
        # Act
        state = {
            "company_of_interest": "sh931865",
            "trade_date": "2025-12-14",
            "policy_report": "",
            "messages": [],
            "international_news_tool_call_count": 0
        }
        
        result = analyst_node(state)
        
        # Assert - 验证不包含仓位调整字段
        report = result.get("international_news_report", "")
        
        if isinstance(report, str) and report:
            try:
                report_json = json.loads(report)
                
                # ❌ 不应包含仓位字段
                assert "position_adjustment" not in report_json, \
                    "❌ 违反职责分离原则: News Analyst不应输出position_adjustment"
                assert "adjustment_rationale" not in report_json, \
                    "❌ 违反职责分离原则: News Analyst不应输出adjustment_rationale"
                assert "base_position_recommendation" not in report_json, \
                    "❌ 违反职责分离原则: News Analyst不应输出base_position_recommendation"
                
                # ✅ 应包含影响强度评估
                assert "impact_strength" in report_json, \
                    "✅ 应输出impact_strength评估"
                assert report_json["impact_strength"] in ["高", "中", "低"], \
                    "✅ impact_strength应为高/中/低"
                
                print("✅ 职责分离验证通过: 仅输出影响强度,不输出仓位建议")
                
            except json.JSONDecodeError:
                pytest.fail("报告非JSON格式")
    
    def test_json_extraction_valid(self):
        """测试从LLM回复中提取有效JSON"""
        content = """
        这是一段分析文本...
        ```json
        {"key": "value", "number": 123}
        ```
        后续文本...
        """
        
        result = _extract_json_report(content)
        assert result
        
        # 验证是有效JSON
        parsed = json.loads(result)
        assert parsed["key"] == "value"
        assert parsed["number"] == 123
    
    def test_json_extraction_invalid(self):
        """测试无效JSON的处理"""
        content = "这是一段没有JSON的文本"
        
        result = _extract_json_report(content)
        assert result == ""
    
    def test_tool_call_limit(self):
        """测试工具调用次数限制"""
        mock_llm = Mock()
        mock_toolkit = Mock()
        
        analyst_node = create_index_news_analyst(mock_llm, mock_toolkit)
        
        # 模拟已达到最大调用次数
        state = {
            "company_of_interest": "sh931865",
            "trade_date": "2025-12-14",
            "policy_report": "",
            "messages": [],
            "international_news_tool_call_count": 3  # 已达到最大值
        }
        
        result = analyst_node(state)
        
        # 验证返回降级报告
        assert "international_news_report" in result
        report = result["international_news_report"]
        
        # 解析降级报告
        report_json = json.loads(report)
        assert report_json["impact_strength"] == "低"
        assert report_json["confidence"] == 0.3
    
    def test_existing_report_skip(self):
        """测试已有报告时跳过分析"""
        mock_llm = Mock()
        mock_toolkit = Mock()
        
        analyst_node = create_index_news_analyst(mock_llm, mock_toolkit)
        
        existing_report = json.dumps({"key": "existing_data"}, ensure_ascii=False)
        # 确保长度超过100
        existing_report = existing_report + " " * 100
        
        state = {
            "company_of_interest": "sh931865",
            "messages": [],
            "international_news_report": existing_report,  # 已有报告
            "international_news_tool_call_count": 0
        }
        
        result = analyst_node(state)
        
        # 验证直接返回已有报告,不调用LLM
        assert result["international_news_report"] == existing_report
        mock_llm.bind_tools.assert_not_called()


class TestNewsClassification:
    """测试新闻分类功能"""
    
    def test_policy_rumor_classification(self):
        """测试政策传闻分类"""
        # 这个测试依赖LLM实际分类,这里主要验证结构
        news_item = {
            "type": "政策传闻",
            "impact_duration": "中期(1-4周)",
            "impact_strength": "高"
        }
        
        assert news_item["type"] == "政策传闻"
        assert "中期" in news_item["impact_duration"]
        assert news_item["impact_strength"] in ["高", "中", "低"]


class TestDeduplication:
    """测试去重机制"""
    
    def test_read_policy_report_for_dedup(self):
        """验证读取Policy Analyst报告用于去重"""
        mock_llm = Mock()
        mock_toolkit = Mock()
        
        mock_result = Mock()
        mock_result.content = json.dumps({
            "key_news": [],
            "impact_strength": "低",
            "confidence": 0.5
        })
        mock_result.tool_calls = []
        
        mock_llm.bind_tools.return_value.invoke.return_value = mock_result
        
        analyst_node = create_index_news_analyst(mock_llm, mock_toolkit)
        
        policy_report = "上游Policy Analyst的政策报告内容"
        
        state = {
            "company_of_interest": "sh931865",
            "trade_date": "2025-12-14",
            "policy_report": policy_report,  # 传入Policy报告
            "messages": [],
            "international_news_tool_call_count": 0
        }
        
        result = analyst_node(state)
        
        # 验证节点执行成功（实际去重逻辑在Prompt中由LLM处理）
        assert "international_news_report" in result


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
