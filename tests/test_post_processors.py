"""
后处理Agent测试

测试ReportSaver、EmailNotifier、SystemNotifier等后处理Agent
"""

import pytest
from datetime import datetime
from pathlib import Path
import json

from core.agents.post_processors import (
    ReportSaverAgent,
    EmailNotifierAgent,
    SystemNotifierAgent
)


class TestReportSaverAgent:
    """测试报告保存Agent"""
    
    def test_save_to_file(self, tmp_path):
        """测试保存到文件"""
        # 创建Agent
        agent = ReportSaverAgent(
            operations=[
                {
                    "type": "save_to_file",
                    "path": str(tmp_path / "{ticker}_{date}.json"),
                    "format": "json"
                }
            ]
        )
        
        # 准备测试数据
        state = {
            "ticker": "AAPL",
            "analysis_date": "20231215",
            "market_report": "市场分析报告...",
            "news_report": "新闻分析报告...",
            "investment_plan": {
                "recommendation": "买入",
                "confidence_score": 0.85
            }
        }
        
        # 执行保存
        result = agent.execute(state)
        
        # 验证结果
        assert result["report_saver_status"]["success"] is True
        assert len(result["report_saver_status"]["results"]) == 1
        
        # 验证文件已创建
        saved_file = tmp_path / "AAPL_20231215.json"
        assert saved_file.exists()
        
        # 验证文件内容
        with open(saved_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
            assert data["ticker"] == "AAPL"
            assert data["analysis_date"] == "20231215"
    
    def test_condition_check(self):
        """测试条件检查"""
        # 创建带条件的Agent
        agent = ReportSaverAgent(
            operations=[
                {
                    "type": "save_to_file",
                    "path": "test.json",
                    "format": "json"
                }
            ],
            conditions=[
                {
                    "field": "success",
                    "operator": "equals",
                    "value": True
                }
            ]
        )
        
        # 测试条件满足
        state_success = {"success": True, "ticker": "AAPL"}
        result = agent.execute(state_success)
        assert result["report_saver_status"]["success"] is True
        
        # 测试条件不满足
        state_fail = {"success": False, "ticker": "AAPL"}
        result = agent.execute(state_fail)
        assert result["report_saver_status"]["skipped"] is True


class TestEmailNotifierAgent:
    """测试邮件通知Agent"""
    
    def test_template_rendering(self):
        """测试模板渲染"""
        agent = EmailNotifierAgent(
            operations=[
                {
                    "type": "send_email",
                    "to": "user@example.com",
                    "subject": "{ticker} 分析完成 - {recommendation}",
                    "template": "analysis_complete"
                }
            ]
        )
        
        state = {
            "ticker": "AAPL",
            "investment_plan": {
                "recommendation": "买入"
            }
        }
        
        # 测试模板渲染
        rendered = agent._render_template("{ticker} 分析完成 - {recommendation}", state)
        assert "AAPL" in rendered
        assert "买入" in rendered
    
    def test_conditional_email(self):
        """测试条件邮件发送"""
        agent = EmailNotifierAgent(
            operations=[
                {
                    "type": "send_email",
                    "to": "user@example.com",
                    "subject": "重要信号",
                    "template": "important_signal"
                }
            ],
            conditions=[
                {
                    "field": "investment_plan.recommendation",
                    "operator": "in",
                    "value": ["买入", "卖出"]
                },
                {
                    "field": "investment_plan.confidence_score",
                    "operator": "greater_than",
                    "value": 0.7
                }
            ]
        )
        
        # 测试条件满足
        state_match = {
            "investment_plan": {
                "recommendation": "买入",
                "confidence_score": 0.85
            }
        }
        result = agent.execute(state_match)
        assert result["email_notifier_status"]["success"] is True
        
        # 测试条件不满足（置信度低）
        state_no_match = {
            "investment_plan": {
                "recommendation": "买入",
                "confidence_score": 0.5
            }
        }
        result = agent.execute(state_no_match)
        assert result["email_notifier_status"]["skipped"] is True


class TestSystemNotifierAgent:
    """测试系统通知Agent"""
    
    def test_notification_creation(self):
        """测试通知创建"""
        agent = SystemNotifierAgent(
            operations=[
                {
                    "type": "send_notification",
                    "notification_type": "analysis",
                    "title": "{ticker} 分析完成",
                    "content": "{summary}",
                    "severity": "info"
                }
            ]
        )
        
        state = {
            "user_id": "user123",
            "ticker": "AAPL",
            "investment_plan": {
                "recommendation": "买入",
                "confidence_score": 0.85
            }
        }
        
        result = agent.execute(state)
        assert result["system_notifier_status"]["success"] is True
        assert result["system_notifier_status"]["user_id"] == "user123"


class TestConditionEvaluation:
    """测试条件评估"""
    
    def test_operators(self):
        """测试各种操作符"""
        agent = ReportSaverAgent()
        
        state = {
            "score": 0.85,
            "recommendation": "买入",
            "tags": ["tech", "growth"]
        }
        
        # equals
        assert agent._evaluate_condition(
            {"field": "recommendation", "operator": "equals", "value": "买入"},
            state
        ) is True
        
        # in
        assert agent._evaluate_condition(
            {"field": "recommendation", "operator": "in", "value": ["买入", "卖出"]},
            state
        ) is True
        
        # greater_than
        assert agent._evaluate_condition(
            {"field": "score", "operator": "greater_than", "value": 0.7},
            state
        ) is True
        
        # less_than
        assert agent._evaluate_condition(
            {"field": "score", "operator": "less_than", "value": 0.9},
            state
        ) is True


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

