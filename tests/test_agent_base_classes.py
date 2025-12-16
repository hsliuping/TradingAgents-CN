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
            tool_data={"price": "10.5"},
            state={}
        )
        
        assert "000001" in prompt
        assert "2024-12-15" in prompt
        assert "price" in prompt


class TestBullResearcherV2:
    """测试看涨研究员V2"""
    
    def test_import(self):
        """测试导入"""
        from core.agents.adapters import BullResearcherV2
        assert BullResearcherV2 is not None
    
    def test_metadata(self):
        """测试元数据"""
        from core.agents.adapters import BullResearcherV2

        assert BullResearcherV2.metadata.id == "bull_researcher_v2"
        assert BullResearcherV2.metadata.name == "看涨研究员 v2.0"
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
                "market_report": "市场看涨",
                "news_report": "利好消息"
            },
            historical_context=None,
            state={}
        )
        
        assert "AAPL" in prompt
        assert "看涨" in prompt or "市场" in prompt


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
        assert ResearchManagerV2.metadata.name == "研究经理 v2.0"
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
                "bull_report": "看涨观点",
                "bear_report": "看跌观点"
            },
            debate_summary=None,
            state={}
        )
        
        assert "AAPL" in prompt
        assert "看涨" in prompt or "看跌" in prompt


class TestTraderV2:
    """测试交易员V2"""
    
    def test_import(self):
        """测试导入"""
        from core.agents.adapters import TraderV2
        assert TraderV2 is not None
    
    def test_metadata(self):
        """测试元数据"""
        from core.agents.adapters import TraderV2

        assert TraderV2.metadata.id == "trader_v2"
        assert TraderV2.metadata.name == "交易员 v2.0"
        assert TraderV2.output_field == "trading_plan"
    
    def test_user_prompt(self):
        """测试用户提示词生成"""
        from core.agents.adapters import TraderV2
        
        agent = TraderV2()
        prompt = agent._build_user_prompt(
            ticker="AAPL",
            analysis_date="2024-12-15",
            investment_plan={"recommendation": "买入"},
            all_reports={"market_report": "市场分析"},
            historical_trades=None,
            state={}
        )
        
        assert "AAPL" in prompt
        assert "买入" in prompt or "投资计划" in prompt


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


class TestBearResearcherV2:
    """测试看跌研究员V2"""

    def test_import(self):
        """测试导入"""
        from core.agents.adapters import BearResearcherV2
        assert BearResearcherV2 is not None

    def test_metadata(self):
        """测试元数据"""
        from core.agents.adapters import BearResearcherV2

        assert BearResearcherV2.metadata.id == "bear_researcher_v2"
        assert BearResearcherV2.metadata.name == "看跌研究员 v2.0"
        assert BearResearcherV2.researcher_type == "bear"
        assert BearResearcherV2.stance == "bear"


class TestRiskManagerV2:
    """测试风险管理者V2"""

    def test_import(self):
        """测试导入"""
        from core.agents.adapters import RiskManagerV2
        assert RiskManagerV2 is not None

    def test_metadata(self):
        """测试元数据"""
        from core.agents.adapters import RiskManagerV2

        assert RiskManagerV2.metadata.id == "risk_manager_v2"
        assert RiskManagerV2.metadata.name == "风险管理者 v2.0"
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


class TestActionAdvisorV2:
    """测试操作建议师V2 (持仓分析)"""

    def test_import(self):
        """测试导入"""
        from core.agents.adapters import ActionAdvisorV2
        assert ActionAdvisorV2 is not None

    def test_metadata(self):
        """测试元数据"""
        from core.agents.adapters import ActionAdvisorV2

        assert ActionAdvisorV2.metadata.id == "pa_advisor_v2"
        assert ActionAdvisorV2.metadata.name == "操作建议师 v2.0"
        assert ActionAdvisorV2.manager_type == "position_advisor"
        assert ActionAdvisorV2.output_field == "action_advice"


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


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

