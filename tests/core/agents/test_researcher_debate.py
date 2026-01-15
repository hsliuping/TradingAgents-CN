"""
测试 ResearcherAgent 的辩论模式功能

测试内容：
1. 辩论模式检测
2. 辩论上下文构建
3. 辩论状态更新
4. 单次分析模式（向后兼容）
"""

import pytest
from unittest.mock import Mock, MagicMock
from typing import Dict, Any

from core.agents.researcher import ResearcherAgent


class MockResearcherAgent(ResearcherAgent):
    """用于测试的 Mock ResearcherAgent"""
    
    researcher_type = "test"
    output_field = "test_report"
    stance = "bull"
    debate_state_field = "investment_debate_state"
    history_field = "bull_history"
    opponent_history_field = "bear_history"
    
    def _build_system_prompt(self, stance: str, state: Dict[str, Any] = None) -> str:
        return "Test system prompt"
    
    def _build_user_prompt(
        self,
        ticker: str,
        analysis_date: str,
        reports: Dict[str, Any],
        historical_context: str,
        state: Dict[str, Any]
    ) -> str:
        return f"Test user prompt with context: {historical_context}"
    
    def _get_required_reports(self):
        return ["market_report"]


class TestDebateModeDetection:
    """测试辩论模式检测"""
    
    def test_is_debate_mode_true(self):
        """测试检测到辩论模式"""
        agent = MockResearcherAgent()
        
        state = {
            "investment_debate_state": {
                "history": "",
                "bull_history": "",
                "bear_history": "",
                "count": 0,
            }
        }
        
        assert agent._is_debate_mode(state) is True
    
    def test_is_debate_mode_false_no_field(self):
        """测试没有辩论状态字段"""
        agent = MockResearcherAgent()
        
        state = {
            "ticker": "AAPL",
            "analysis_date": "2024-01-15",
        }
        
        assert agent._is_debate_mode(state) is False
    
    def test_is_debate_mode_false_not_dict(self):
        """测试辩论状态字段不是字典"""
        agent = MockResearcherAgent()
        
        state = {
            "investment_debate_state": "not a dict"
        }
        
        assert agent._is_debate_mode(state) is False


class TestDebateContextBuilding:
    """测试辩论上下文构建"""
    
    def test_get_debate_context_with_history(self):
        """测试获取辩论上下文（有历史）"""
        agent = MockResearcherAgent()
        
        state = {
            "investment_debate_state": {
                "history": "Bull: 看涨\nBear: 看跌",
                "bull_history": "Bull: 看涨",
                "bear_history": "Bear: 看跌",
                "current_response": "Bear: 看跌",
            }
        }
        
        context = agent._get_debate_context(state)
        
        assert "【完整辩论历史】" in context
        assert "Bull: 看涨" in context
        assert "Bear: 看跌" in context
        assert "【对方最新观点】" in context
    
    def test_get_debate_context_empty(self):
        """测试获取辩论上下文（空历史）"""
        agent = MockResearcherAgent()
        
        state = {
            "investment_debate_state": {
                "history": "",
                "current_response": "",
            }
        }
        
        context = agent._get_debate_context(state)
        
        assert context == ""
    
    def test_get_debate_context_with_opponent_history(self):
        """测试获取对方历史"""
        agent = MockResearcherAgent()
        agent.opponent_history_field = "bear_history"
        
        state = {
            "investment_debate_state": {
                "history": "Bull: 看涨\nBear: 看跌",
                "bear_history": "Bear: 看跌",
                "current_response": "Bear: 看跌",
            }
        }
        
        context = agent._get_debate_context(state)
        
        # 对方历史应该包含在上下文中（如果与完整历史不同）
        assert "Bear: 看跌" in context


class TestDebateStateUpdate:
    """测试辩论状态更新"""
    
    def test_update_debate_state_basic(self):
        """测试基本的辩论状态更新"""
        agent = MockResearcherAgent()
        
        state = {
            "investment_debate_state": {
                "history": "",
                "bull_history": "",
                "bear_history": "",
                "count": 0,
            }
        }
        
        response = {"content": "我认为应该买入"}
        result = {}
        
        updated_result = agent._update_debate_state(state, response, result)
        
        assert "investment_debate_state" in updated_result
        debate_state = updated_result["investment_debate_state"]
        
        assert "Bull Analyst: 我认为应该买入" in debate_state["history"]
        assert "Bull Analyst: 我认为应该买入" in debate_state["bull_history"]
        assert debate_state["current_response"] == "Bull Analyst: 我认为应该买入"

    def test_update_debate_state_preserves_count(self):
        """测试更新辩论状态时保留 count（由工作流层管理）"""
        agent = MockResearcherAgent()

        state = {
            "investment_debate_state": {
                "history": "Previous history",
                "bull_history": "",
                "bear_history": "",
                "count": 5,  # 已有的 count
            }
        }

        response = "新的观点"
        result = {}

        updated_result = agent._update_debate_state(state, response, result)
        debate_state = updated_result["investment_debate_state"]

        # count 应该被保留，不应该被修改
        assert debate_state["count"] == 5

    def test_update_debate_state_with_string_response(self):
        """测试字符串响应"""
        agent = MockResearcherAgent()

        state = {
            "investment_debate_state": {
                "history": "",
                "bull_history": "",
                "count": 0,
            }
        }

        response = "直接的字符串响应"
        result = {}

        updated_result = agent._update_debate_state(state, response, result)
        debate_state = updated_result["investment_debate_state"]

        assert "Bull Analyst: 直接的字符串响应" in debate_state["history"]


class TestSpeakerLabel:
    """测试发言者标签"""

    def test_get_speaker_label_bull(self):
        """测试看涨研究员标签"""
        agent = MockResearcherAgent()
        agent.stance = "bull"

        assert agent._get_speaker_label() == "Bull Analyst"

    def test_get_speaker_label_bear(self):
        """测试看跌研究员标签"""
        agent = MockResearcherAgent()
        agent.stance = "bear"

        assert agent._get_speaker_label() == "Bear Analyst"

    def test_get_speaker_label_risky(self):
        """测试风险研究员标签"""
        agent = MockResearcherAgent()
        agent.stance = "risky"

        assert agent._get_speaker_label() == "Risky Analyst"

    def test_get_speaker_label_unknown(self):
        """测试未知立场"""
        agent = MockResearcherAgent()
        agent.stance = "unknown"

        assert agent._get_speaker_label() == "Analyst"


class TestBackwardCompatibility:
    """测试向后兼容性（单次分析模式）"""

    def test_single_analysis_mode(self):
        """测试单次分析模式（无辩论状态）"""
        agent = MockResearcherAgent()

        # Mock LLM
        agent._llm = Mock()
        agent._llm.invoke = Mock(return_value=Mock(content="分析结果"))

        state = {
            "ticker": "AAPL",
            "analysis_date": "2024-01-15",
            "market_report": "市场报告",
        }

        result = agent.execute(state)

        # 应该返回报告，但不包含 investment_debate_state
        assert "test_report" in result
        assert "investment_debate_state" not in result

    def test_memory_context_in_single_mode(self):
        """测试单次分析模式使用 Memory 上下文"""
        agent = MockResearcherAgent()

        # Mock Memory
        agent.memory = Mock()
        agent.memory.get_memories = Mock(return_value=[
            {"recommendation": "历史建议1"},
            {"recommendation": "历史建议2"},
        ])

        reports = {"market_report": "当前市场报告"}
        context = agent._get_memory_context("AAPL", reports)

        assert "【历史经验】" in context
        assert "历史建议1" in context
        assert "历史建议2" in context

    def test_memory_context_no_memory(self):
        """测试没有 Memory 系统"""
        agent = MockResearcherAgent()
        agent.memory = None

        reports = {"market_report": "当前市场报告"}
        context = agent._get_memory_context("AAPL", reports)

        assert context == ""


if __name__ == "__main__":
    pytest.main([__file__, "-v"])


