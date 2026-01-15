"""
集成测试：v2.0 辩论工作流

测试完整的辩论流程：
1. 工作流层初始化辩论状态
2. BullResearcherV2 和 BearResearcherV2 多轮辩论
3. ResearchManagerV2 综合辩论历史做出决策
"""

import pytest
from unittest.mock import Mock, patch
from typing import Dict, Any

from core.agents.adapters.bull_researcher_v2 import BullResearcherV2
from core.agents.adapters.bear_researcher_v2 import BearResearcherV2
from core.agents.adapters.research_manager_v2 import ResearchManagerV2


@pytest.fixture
def mock_llm():
    """Mock LLM"""
    llm = Mock()
    
    # 模拟不同的响应
    responses = [
        "看涨观点：基于强劲的财报，我认为应该买入",
        "看跌观点：但是估值过高，存在回调风险",
        "看涨反驳：高估值反映了市场对未来增长的预期",
        "看跌反驳：市场预期过于乐观，风险被低估",
        "综合决策：建议谨慎买入，设置止损",
    ]
    
    llm.invoke = Mock(side_effect=[Mock(content=r) for r in responses])
    
    return llm


@pytest.fixture
def initial_state():
    """初始状态（模拟工作流层初始化后的状态）"""
    return {
        "ticker": "AAPL",
        "analysis_date": "2024-01-15",
        "market_report": "市场整体向好，科技股表现强劲",
        "news_report": "苹果发布新产品，市场反应积极",
        "fundamentals_report": "营收增长20%，利润率提升",
        # 工作流层初始化的辩论状态
        "investment_debate_state": {
            "history": "",
            "bull_history": "",
            "bear_history": "",
            "current_response": "",
            "judge_decision": "",
            "count": 0,
        }
    }


class TestDebateWorkflowIntegration:
    """测试辩论工作流集成"""
    
    def test_two_round_debate(self, mock_llm, initial_state):
        """测试两轮辩论流程"""
        
        # 创建 Agent 实例
        bull_agent = BullResearcherV2(llm=mock_llm)
        bear_agent = BearResearcherV2(llm=mock_llm)
        manager_agent = ResearchManagerV2(llm=mock_llm)
        
        state = initial_state.copy()
        
        # 第 1 轮：看涨研究员发言
        result1 = bull_agent.execute(state)
        state.update(result1)
        
        # 验证辩论状态更新
        assert "investment_debate_state" in state
        debate_state = state["investment_debate_state"]
        assert "Bull Analyst:" in debate_state["history"]
        assert "看涨观点" in debate_state["bull_history"]
        
        # 第 1 轮：看跌研究员发言
        result2 = bear_agent.execute(state)
        state.update(result2)
        
        # 验证辩论状态更新
        debate_state = state["investment_debate_state"]
        assert "Bear Analyst:" in debate_state["history"]
        assert "看跌观点" in debate_state["bear_history"]
        
        # 第 2 轮：看涨研究员反驳
        result3 = bull_agent.execute(state)
        state.update(result3)
        
        # 验证辩论历史累积
        debate_state = state["investment_debate_state"]
        assert debate_state["history"].count("Bull Analyst:") == 2
        
        # 第 2 轮：看跌研究员反驳
        result4 = bear_agent.execute(state)
        state.update(result4)
        
        # 验证辩论历史累积
        debate_state = state["investment_debate_state"]
        assert debate_state["history"].count("Bear Analyst:") == 2
        
        # 研究经理总结
        result5 = manager_agent.execute(state)
        state.update(result5)
        
        # 验证最终决策
        assert "investment_plan" in state
        assert "judge_decision" in state["investment_debate_state"]
        assert "综合决策" in state["investment_debate_state"]["judge_decision"]
    
    def test_debate_context_propagation(self, mock_llm, initial_state):
        """测试辩论上下文在多轮中传递"""
        
        bull_agent = BullResearcherV2(llm=mock_llm)
        bear_agent = BearResearcherV2(llm=mock_llm)
        
        state = initial_state.copy()
        
        # 第 1 轮
        result1 = bull_agent.execute(state)
        state.update(result1)
        
        # 第 2 轮：看跌研究员应该能看到看涨研究员的观点
        with patch.object(bear_agent, '_get_debate_context') as mock_get_context:
            mock_get_context.return_value = "Mock context"
            
            result2 = bear_agent.execute(state)
            
            # 验证调用了 _get_debate_context
            mock_get_context.assert_called_once()
            
            # 验证传入的 state 包含辩论历史
            call_args = mock_get_context.call_args[0][0]
            assert "investment_debate_state" in call_args
            assert "Bull Analyst:" in call_args["investment_debate_state"]["history"]
    
    def test_single_analysis_mode_fallback(self, mock_llm):
        """测试单次分析模式（无辩论状态）"""
        
        bull_agent = BullResearcherV2(llm=mock_llm)
        
        # 没有 investment_debate_state 的状态
        state = {
            "ticker": "AAPL",
            "analysis_date": "2024-01-15",
            "market_report": "市场报告",
        }
        
        result = bull_agent.execute(state)
        
        # 应该返回报告，但不包含 investment_debate_state
        assert "bull_report" in result
        assert "investment_debate_state" not in result


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

