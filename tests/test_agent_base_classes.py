"""
测试Agent基类实现

测试基于5种基类实现的具体Agent
包括：
- 主流程Agent (12个)
- 持仓分析Agent (4个)
- 复盘分析Agent (5个)
"""

import pytest
from unittest.mock import Mock, MagicMock


def test_is_retryable_llm_error_recognizes_timed_out_variant() -> None:
    from core.agents.base import is_retryable_llm_error

    assert is_retryable_llm_error("Request timed out.") is True
    assert is_retryable_llm_error("The read operation timed out") is True
    assert is_retryable_llm_error("validation failed") is False


class TestMarketAnalystV2:
    """测试市场分析师V2"""
    
    def test_import(self):
        """测试导入"""
        from core.agents.adapters import MarketAnalystV2
        assert MarketAnalystV2 is not None
    
    def test_metadata(self):
        """测试元数据"""
        from core.agents.adapters import MarketAnalystV2

        assert MarketAnalystV2.metadata.id == "market_analyst_v2"
        assert MarketAnalystV2.metadata.name == "市场分析师 v2.0"
        assert MarketAnalystV2.analyst_type == "market"
        assert MarketAnalystV2.output_field == "market_report"
    
    def test_system_prompt(self):
        """测试系统提示词生成"""
        from core.agents.adapters import MarketAnalystV2
        
        agent = MarketAnalystV2()
        prompt = agent._build_system_prompt("A股")
        
        assert "市场分析师" in prompt
        assert "技术分析" in prompt
    
    def test_user_prompt(self):
        """测试用户提示词生成"""
        from core.agents.adapters import MarketAnalystV2
        
        agent = MarketAnalystV2()
        prompt = agent._build_user_prompt(
            ticker="000001",
            analysis_date="2024-12-15",
            state={"company_name": "平安银行"}
        )
        
        assert "000001" in prompt
        assert "2024-12-15" in prompt
        assert "平安银行" in prompt


class TestBullResearcherV2:
    """测试乐观情景研究员V2"""
    
    def test_import(self):
        """测试导入"""
        from core.agents.adapters import BullResearcherV2
        assert BullResearcherV2 is not None
    
    def test_metadata(self):
        """测试元数据"""
        from core.agents.adapters import BullResearcherV2

        assert BullResearcherV2.metadata.id == "bull_researcher_v2"
        assert BullResearcherV2.metadata.name == "乐观情景研究员 v2.0"
        assert BullResearcherV2.researcher_type == "bull"
        assert BullResearcherV2.stance == "bull"
    
    def test_required_reports(self):
        """测试需要的报告列表"""
        from core.agents.adapters import BullResearcherV2
        
        agent = BullResearcherV2()
        reports = agent._get_required_reports()
        
        assert "market_report" in reports
        assert "news_report" in reports
        assert "fundamentals_report" in reports
    
    def test_user_prompt(self):
        """测试用户提示词生成"""
        from core.agents.adapters import BullResearcherV2
        
        agent = BullResearcherV2()
        prompt = agent._build_user_prompt(
            ticker="AAPL",
            analysis_date="2024-12-15",
            reports={
                "market_report": "市场偏乐观",
                "news_report": "利好消息"
            },
            historical_context=None,
            state={}
        )
        
        assert "AAPL" in prompt
        assert "乐观" in prompt or "市场" in prompt


class TestResearchManagerV2:
    """测试研究经理V2"""
    
    def test_import(self):
        """测试导入"""
        from core.agents.adapters import ResearchManagerV2
        assert ResearchManagerV2 is not None
    
    def test_metadata(self):
        """测试元数据"""
        from core.agents.adapters import ResearchManagerV2

        assert ResearchManagerV2.metadata.id == "research_manager_v2"
        assert ResearchManagerV2.metadata.name == "研究整合员 v2.0"
        assert ResearchManagerV2.manager_type == "research"
        assert ResearchManagerV2.output_field == "investment_plan"
    
    def test_required_inputs(self):
        """测试需要的输入列表"""
        from core.agents.adapters import ResearchManagerV2
        
        agent = ResearchManagerV2()
        inputs = agent._get_required_inputs()
        
        assert "bull_report" in inputs
        assert "bear_report" in inputs
    
    def test_user_prompt(self):
        """测试用户提示词生成"""
        from core.agents.adapters import ResearchManagerV2
        
        agent = ResearchManagerV2()
        prompt = agent._build_user_prompt(
            ticker="AAPL",
            analysis_date="2024-12-15",
            inputs={
                "bull_report": "积极证据",
                "bear_report": "谨慎证据"
            },
            debate_summary=None,
            state={}
        )
        
        assert "AAPL" in prompt
        assert "积极" in prompt or "谨慎" in prompt

    def test_delegate_to_agent_uses_compatible_invoke_path(self):
        """测试委托子 Agent 时不会因缺少 invoke_agent 而失败"""
        from unittest.mock import Mock, patch
        from core.agents.adapters import ResearchManagerV2

        mock_llm = Mock()
        mock_llm.invoke.return_value = Mock(content="综合结论：继续观察")

        agent = ResearchManagerV2(llm=mock_llm)

        delegated_agent = Mock()
        delegated_agent.execute.return_value = {"chip_report": "筹码集中度较高"}

        with patch("core.agents.factory.AgentFactory.create_with_dynamic_tools", return_value=delegated_agent) as mock_create:
            result = agent._run_delegated_research_agents({
                "ticker": "600519",
                "analysis_date": "2026-05-11",
                "node_config": {
                    "delegated_agent_ids": ["chip_distribution_analyst_v2"],
                },
            })

        mock_create.assert_called_once_with("chip_distribution_analyst_v2", llm=mock_llm)
        delegated_agent.execute.assert_called_once()
        assert result == {"chip_report": "筹码集中度较高"}


class TestTraderV2:
    """测试研究整合员V2"""
    
    def test_import(self):
        """测试导入"""
        from core.agents.adapters import TraderV2
        assert TraderV2 is not None
    
    def test_metadata(self):
        """测试元数据"""
        from core.agents.adapters import TraderV2

        assert TraderV2.metadata.id == "trader_v2"
        assert TraderV2.metadata.name == "研究整合员 v2.0"
        assert TraderV2.output_field == "trader_investment_plan"
    
    def test_user_prompt(self):
        """测试用户提示词生成"""
        from core.agents.adapters import TraderV2
        
        agent = TraderV2()
        prompt = agent._build_user_prompt(
            ticker="AAPL",
            analysis_date="2024-12-15",
            investment_plan={"recommendation": "乐观"},
            all_reports={"market_report": "市场分析"},
            historical_trades=None,
            state={}
        )
        
        assert "AAPL" in prompt
        assert "乐观" in prompt or "研究计划" in prompt


# ============================================================
# 新增分析师类Agent测试
# ============================================================

class TestNewsAnalystV2:
    """测试新闻分析师V2"""

    def test_import(self):
        """测试导入"""
        from core.agents.adapters import NewsAnalystV2
        assert NewsAnalystV2 is not None

    def test_metadata(self):
        """测试元数据"""
        from core.agents.adapters import NewsAnalystV2

        assert NewsAnalystV2.metadata.id == "news_analyst_v2"
        assert NewsAnalystV2.metadata.name == "新闻分析师 v2.0"
        assert NewsAnalystV2.analyst_type == "news"
        assert NewsAnalystV2.output_field == "news_report"

    def test_fallback_user_prompt_uses_research_observation_schema(self):
        """测试新闻分析师降级提示词改为研究观察语义"""
        from core.agents.adapters import NewsAnalystV2

        agent = NewsAnalystV2()
        agent._get_prompt_from_template = lambda *args, **kwargs: None

        prompt = agent._build_user_prompt(
            ticker="000001",
            analysis_date="2024-12-15",
            tool_data={},
            state={"company_name": "平安银行"},
        )

        assert "新闻事件研究" in prompt
        assert "后续观察事项" in prompt
        assert "投资机会窗口判断" not in prompt


class TestSocialMediaAnalystV2:
    """测试社交媒体分析师V2"""

    def test_import(self):
        """测试导入"""
        from core.agents.adapters import SocialMediaAnalystV2
        assert SocialMediaAnalystV2 is not None

    def test_metadata(self):
        """测试元数据"""
        from core.agents.adapters import SocialMediaAnalystV2

        assert SocialMediaAnalystV2.metadata.id == "social_analyst_v2"
        assert SocialMediaAnalystV2.metadata.name == "社交媒体分析师 v2.0"
        assert SocialMediaAnalystV2.analyst_type == "social"
        assert SocialMediaAnalystV2.output_field == "sentiment_report"

    def test_fallback_user_prompt_uses_research_observation_schema(self):
        """测试社交媒体分析师降级提示词改为研究观察语义"""
        from core.agents.adapters import SocialMediaAnalystV2

        agent = SocialMediaAnalystV2()
        agent._get_prompt_from_template = lambda *args, **kwargs: None

        prompt = agent._build_user_prompt(
            ticker="000001",
            analysis_date="2024-12-15",
            tool_data={},
            state={"company_name": "平安银行"},
        )

        assert "情绪研究" in prompt
        assert "噪音来源" in prompt
        assert "投资机会" not in prompt


class TestSectorAnalystV2:
    """测试板块分析师V2"""

    def test_import(self):
        """测试导入"""
        from core.agents.adapters import SectorAnalystV2
        assert SectorAnalystV2 is not None

    def test_metadata(self):
        """测试元数据"""
        from core.agents.adapters import SectorAnalystV2

        assert SectorAnalystV2.metadata.id == "sector_analyst_v2"
        assert SectorAnalystV2.metadata.name == "板块分析师 v2.0"
        assert SectorAnalystV2.analyst_type == "sector"
        assert SectorAnalystV2.output_field == "sector_report"

    def test_fallback_user_prompt_avoids_sector_allocation_language(self):
        """测试板块分析师降级提示词不再要求配置建议"""
        from core.agents.adapters import SectorAnalystV2

        agent = SectorAnalystV2()
        agent._get_prompt_from_template = lambda *args, **kwargs: None

        prompt = agent._build_user_prompt(
            ticker="000001",
            analysis_date="2024-12-15",
            tool_data={},
            state={"company_name": "平安银行", "market_type": "A股"},
        )

        assert "后续观察事项" in prompt
        assert "行业成长机会和投资价值" not in prompt
        assert "行业风险和防御策略" not in prompt


class TestIndexAnalystV2:
    """测试大盘分析师V2"""

    def test_import(self):
        """测试导入"""
        from core.agents.adapters import IndexAnalystV2
        assert IndexAnalystV2 is not None

    def test_metadata(self):
        """测试元数据"""
        from core.agents.adapters import IndexAnalystV2

        assert IndexAnalystV2.metadata.id == "index_analyst_v2"
        assert IndexAnalystV2.metadata.name == "大盘分析师 v2.0"
        assert IndexAnalystV2.analyst_type == "index"
        assert IndexAnalystV2.output_field == "index_report"

    def test_fallback_user_prompt_avoids_macro_execution_language(self):
        """测试大盘分析师降级提示词不再要求目标位或配置建议"""
        from core.agents.adapters import IndexAnalystV2

        agent = IndexAnalystV2()
        agent._get_prompt_from_template = lambda *args, **kwargs: None

        prompt = agent._build_user_prompt(
            ticker="000001",
            analysis_date="2024-12-15",
            tool_data={},
            state={"company_name": "平安银行", "market_type": "A股"},
        )

        assert "宏观环境研究" in prompt
        assert "后续观察事项" in prompt
        assert "上涨机会和市场热点" not in prompt
        assert "下跌风险和防御策略" not in prompt


class TestBearResearcherV2:
    """测试审慎情景研究员V2"""

    def test_import(self):
        """测试导入"""
        from core.agents.adapters import BearResearcherV2
        assert BearResearcherV2 is not None

    def test_metadata(self):
        """测试元数据"""
        from core.agents.adapters import BearResearcherV2

        assert BearResearcherV2.metadata.id == "bear_researcher_v2"
        assert BearResearcherV2.metadata.name == "审慎情景研究员 v2.0"
        assert BearResearcherV2.researcher_type == "bear"
        assert BearResearcherV2.stance == "bear"


class TestRiskManagerV2:
    """测试风险评估师V2"""

    def test_import(self):
        """测试导入"""
        from core.agents.adapters import RiskManagerV2
        assert RiskManagerV2 is not None

    def test_metadata(self):
        """测试元数据"""
        from core.agents.adapters import RiskManagerV2

        assert RiskManagerV2.metadata.id == "risk_manager_v2"
        assert RiskManagerV2.metadata.name == "风险评估师 v2.0"
        assert RiskManagerV2.manager_type == "risk"
        assert RiskManagerV2.output_field == "risk_assessment"


# ==================== 持仓分析Agent测试 ====================

class TestTechnicalAnalystV2:
    """测试技术面分析师V2 (持仓分析)"""

    def test_import(self):
        """测试导入"""
        from core.agents.adapters import TechnicalAnalystV2
        assert TechnicalAnalystV2 is not None

    def test_metadata(self):
        """测试元数据"""
        from core.agents.adapters import TechnicalAnalystV2

        assert TechnicalAnalystV2.metadata.id == "pa_technical_v2"
        assert TechnicalAnalystV2.metadata.name == "技术面分析师 v2.0"
        assert TechnicalAnalystV2.researcher_type == "position_technical"
        assert TechnicalAnalystV2.output_field == "technical_analysis"

    def test_fallback_user_prompt_avoids_execution_language(self):
        """测试降级提示词改为研究判断口径"""
        from core.agents.adapters import TechnicalAnalystV2

        agent = TechnicalAnalystV2()
        agent._get_prompt_from_template = lambda *args, **kwargs: None

        prompt = agent._build_user_prompt(
            ticker="000001",
            analysis_date="2024-12-15",
            reports={},
            historical_context=None,
            state={
                "position_info": {
                    "code": "000001",
                    "name": "平安银行",
                    "cost_price": 10.0,
                    "current_price": 10.5,
                    "unrealized_pnl_pct": 5.0,
                },
                "market_data": {
                    "summary": "趋势偏稳，量能一般。",
                    "technical_indicators": "MACD走平，RSI中性。",
                },
                "stock_analysis_report": {"has_cache": False},
            },
        )

        assert "技术验证信号" in prompt
        assert "操作建议" not in prompt
        assert "支撑阻力位" not in prompt


class TestFundamentalAnalystV2:
    """测试基本面分析师V2 (持仓分析)"""

    def test_import(self):
        """测试导入"""
        from core.agents.adapters import FundamentalAnalystV2
        assert FundamentalAnalystV2 is not None

    def test_metadata(self):
        """测试元数据"""
        from core.agents.adapters import FundamentalAnalystV2

        assert FundamentalAnalystV2.metadata.id == "pa_fundamental_v2"
        assert FundamentalAnalystV2.metadata.name == "基本面分析师 v2.0"
        assert FundamentalAnalystV2.researcher_type == "position_fundamental"
        assert FundamentalAnalystV2.output_field == "fundamental_analysis"

    def test_fallback_user_prompt_avoids_execution_language(self):
        """测试降级提示词改为研究判断口径"""
        from core.agents.adapters import FundamentalAnalystV2

        agent = FundamentalAnalystV2()
        agent._get_prompt_from_template = lambda *args, **kwargs: None

        prompt = agent._build_user_prompt(
            ticker="000001",
            analysis_date="2024-12-15",
            reports={},
            historical_context=None,
            state={
                "position_info": {
                    "code": "000001",
                    "name": "平安银行",
                    "industry": "银行",
                    "cost_price": 10.0,
                    "current_price": 10.5,
                    "holding_days": 30,
                },
                "stock_analysis_report": {"has_cache": False},
            },
        )

        assert "公开验证信号" in prompt
        assert "基于持仓的基本面操作建议" not in prompt
        assert "禁止输出买卖建议" in prompt


class TestRiskAssessorV2:
    """测试风险评估师V2 (持仓分析)"""

    def test_import(self):
        """测试导入"""
        from core.agents.adapters import RiskAssessorV2
        assert RiskAssessorV2 is not None

    def test_metadata(self):
        """测试元数据"""
        from core.agents.adapters import RiskAssessorV2

        assert RiskAssessorV2.metadata.id == "pa_risk_v2"
        assert RiskAssessorV2.metadata.name == "风险评估师 v2.0"
        assert RiskAssessorV2.researcher_type == "position_risk"
        assert RiskAssessorV2.output_field == "risk_analysis"

    def test_fallback_user_prompt_avoids_reference_prices(self):
        """测试降级提示词不再要求参考价位"""
        from core.agents.adapters import RiskAssessorV2

        agent = RiskAssessorV2()
        agent._get_prompt_from_template = lambda *args, **kwargs: None

        prompt = agent._build_user_prompt(
            ticker="000001",
            analysis_date="2024-12-15",
            reports={},
            historical_context=None,
            state={
                "position_info": {
                    "code": "000001",
                    "name": "平安银行",
                    "quantity": 100,
                    "cost_price": 10.0,
                    "current_price": 10.5,
                    "market_value": 1050.0,
                    "unrealized_pnl": 50.0,
                    "unrealized_pnl_pct": 5.0,
                },
                "capital_info": {"total_assets": 100000.0},
                "market_data": {"volatility": "中等"},
                "stock_analysis_report": {"has_cache": False},
            },
        )

        assert "后续观察事项" in prompt
        assert "风险控制参考价位（仅供参考）" not in prompt
        assert "收益预期参考价位（仅供参考）" not in prompt
        assert "禁止输出风险控制参考价位" in prompt


class TestActionAdvisorV2:
    """测试持仓研究整合师V2 (持仓分析)"""

    def test_import(self):
        """测试导入"""
        from core.agents.adapters import ActionAdvisorV2
        assert ActionAdvisorV2 is not None

    def test_metadata(self):
        """测试元数据"""
        from core.agents.adapters import ActionAdvisorV2

        assert ActionAdvisorV2.metadata.id == "pa_advisor_v2"
        assert ActionAdvisorV2.metadata.name == "持仓研究整合师 v2.0"
        assert ActionAdvisorV2.manager_type == "position_advisor"
        assert ActionAdvisorV2.output_field == "action_advice"

    def test_fallback_user_prompt_uses_research_schema(self):
        """测试降级提示词输出研究判断格式"""
        from core.agents.adapters import ActionAdvisorV2

        agent = ActionAdvisorV2()
        agent._get_prompt_from_template = lambda *args, **kwargs: None

        prompt = agent._build_user_prompt(
            ticker="000001",
            analysis_date="2024-12-15",
            inputs={},
            debate_summary=None,
            state={
                "position_info": {
                    "code": "000001",
                    "name": "平安银行",
                    "cost_price": 10.0,
                    "current_price": 10.5,
                    "unrealized_pnl_pct": 5.0,
                },
                "technical_analysis": "趋势偏稳，量价配合一般。",
                "fundamental_analysis": "盈利能力稳定，估值中性。",
                "risk_analysis": "需关注行业景气与资产质量变化。",
                "user_goal": {"target_return": 10, "stop_loss": -8},
            },
        )

        assert "持仓研究结论" in prompt
        assert "observation_factors" in prompt
        assert "价格分析区间" not in prompt
        assert "风险控制参考价" not in prompt


# ==================== 复盘分析Agent测试 ====================

class TestTimingAnalystV2:
    """测试时机分析师V2 (复盘分析)"""

    def test_import(self):
        """测试导入"""
        from core.agents.adapters import TimingAnalystV2
        assert TimingAnalystV2 is not None

    def test_metadata(self):
        """测试元数据"""
        from core.agents.adapters import TimingAnalystV2

        assert TimingAnalystV2.metadata.id == "timing_analyst_v2"
        assert TimingAnalystV2.metadata.name == "时机分析师 v2.0"
        assert TimingAnalystV2.researcher_type == "review_timing"
        assert TimingAnalystV2.output_field == "timing_analysis"

    def test_fallback_user_prompt_avoids_execution_language(self):
        """测试时机复盘降级提示词不再要求最优买卖点"""
        from core.agents.adapters import TimingAnalystV2

        agent = TimingAnalystV2()
        agent._get_prompt_from_template = lambda *args, **kwargs: None

        prompt = agent._build_user_prompt(
            ticker="000001",
            analysis_date="2024-12-15",
            reports={},
            historical_context=None,
            state={
                "trade_info": {
                    "code": "000001",
                    "name": "平安银行",
                    "holding_days": 12,
                    "realized_pnl": 120.0,
                    "realized_pnl_pct": 3.2,
                    "trades": [{"date": "2024-12-01", "side": "buy", "quantity": 100, "price": 10.2}],
                },
                "market_data": {"summary": "市场震荡，量能一般。"},
            },
        )

        assert "时机复盘" in prompt
        assert "证据完整性与纪律偏差" in prompt
        assert "与最优点的差距" not in prompt


class TestPositionAnalystV2:
    """测试仓位分析师V2 (复盘分析)"""

    def test_import(self):
        """测试导入"""
        from core.agents.adapters import PositionAnalystV2
        assert PositionAnalystV2 is not None

    def test_metadata(self):
        """测试元数据"""
        from core.agents.adapters import PositionAnalystV2

        assert PositionAnalystV2.metadata.id == "position_analyst_v2"
        assert PositionAnalystV2.metadata.name == "仓位分析师 v2.0"
        assert PositionAnalystV2.researcher_type == "review_position"
        assert PositionAnalystV2.output_field == "position_analysis"

    def test_fallback_user_prompt_avoids_future_position_plan(self):
        """测试仓位复盘降级提示词不再要求未来加减仓方案"""
        from core.agents.adapters import PositionAnalystV2

        agent = PositionAnalystV2()
        agent._get_prompt_from_template = lambda *args, **kwargs: None

        prompt = agent._build_user_prompt(
            ticker="000001",
            analysis_date="2024-12-15",
            reports={},
            historical_context=None,
            state={
                "trade_info": {
                    "code": "000001",
                    "name": "平安银行",
                    "realized_pnl": 120.0,
                    "realized_pnl_pct": 3.2,
                    "trades": [{"date": "2024-12-01", "side": "buy", "quantity": 100}],
                },
            },
        )

        assert "仓位复盘" in prompt
        assert "仓位变化依据分析" in prompt
        assert "加减仓策略分析" not in prompt


class TestEmotionAnalystV2:
    """测试情绪分析师V2 (复盘分析)"""

    def test_import(self):
        """测试导入"""
        from core.agents.adapters import EmotionAnalystV2
        assert EmotionAnalystV2 is not None

    def test_metadata(self):
        """测试元数据"""
        from core.agents.adapters import EmotionAnalystV2

        assert EmotionAnalystV2.metadata.id == "emotion_analyst_v2"
        assert EmotionAnalystV2.metadata.name == "情绪分析师 v2.0"
        assert EmotionAnalystV2.researcher_type == "review_emotion"
        assert EmotionAnalystV2.output_field == "emotion_analysis"


class TestAttributionAnalystV2:
    """测试归因分析师V2 (复盘分析)"""

    def test_import(self):
        """测试导入"""
        from core.agents.adapters import AttributionAnalystV2
        assert AttributionAnalystV2 is not None

    def test_metadata(self):
        """测试元数据"""
        from core.agents.adapters import AttributionAnalystV2

        assert AttributionAnalystV2.metadata.id == "attribution_analyst_v2"
        assert AttributionAnalystV2.metadata.name == "归因分析师 v2.0"
        assert AttributionAnalystV2.researcher_type == "review_attribution"
        assert AttributionAnalystV2.output_field == "attribution_analysis"


class TestReviewManagerV2:
    """测试复盘总结师V2 (复盘分析)"""

    def test_import(self):
        """测试导入"""
        from core.agents.adapters import ReviewManagerV2
        assert ReviewManagerV2 is not None

    def test_metadata(self):
        """测试元数据"""
        from core.agents.adapters import ReviewManagerV2

        assert ReviewManagerV2.metadata.id == "review_manager_v2"
        assert ReviewManagerV2.metadata.name == "复盘总结师 v2.0"
        assert ReviewManagerV2.manager_type == "review_manager"
        assert ReviewManagerV2.output_field == "review_summary"

    def test_fallback_user_prompt_avoids_future_trade_actions(self):
        """测试复盘总结降级提示词不要求未来交易动作"""
        from core.agents.adapters import ReviewManagerV2

        agent = ReviewManagerV2()
        agent._get_prompt_from_template = lambda *args, **kwargs: None

        prompt = agent._build_user_prompt(
            ticker="000001",
            analysis_date="2024-12-15",
            inputs={},
            debate_summary=None,
            state={
                "trade_info": {
                    "code": "000001",
                    "name": "平安银行",
                    "realized_pnl": 120.0,
                    "realized_pnl_pct": 3.2,
                    "holding_days": 12,
                },
                "timing_analysis": "入场证据基本充分，但退出依据略显仓促。",
                "position_analysis": "仓位暴露与账户规模基本匹配。",
                "emotion_analysis": "盘中受短期波动影响出现犹豫。",
                "attribution_analysis": "收益主要来自行业回暖与个股基本面改善。",
            },
        )

        assert "禁止把 suggestions 写成买卖" in prompt
        assert "下次应在某价位执行" in prompt


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

