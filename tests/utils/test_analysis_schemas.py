#!/usr/bin/env python3
"""
分析Schema单元测试
测试Pydantic模型定义的正确性
"""

import pytest
import json
from pydantic import ValidationError


class TestMacroAnalysisSchema:
    """测试MacroAnalysis Schema"""
    
    def test_schema_import(self):
        """测试Schema可以正确导入"""
        from tradingagents.agents.utils.analysis_schemas import MacroAnalysis
        
        assert MacroAnalysis is not None
    
    def test_valid_macro_analysis(self):
        """测试有效的宏观分析数据"""
        from tradingagents.agents.utils.analysis_schemas import MacroAnalysis
        
        data = {
            "economic_cycle": "复苏",
            "liquidity": "宽松",
            "key_indicators": ["GDP增速回升", "CPI温和上涨", "PMI持续扩张"],
            "analysis_summary": "当前经济处于复苏阶段，流动性保持宽松，GDP增速回升，通胀温和，PMI保持在扩张区间。",
            "confidence": 0.8,
            "sentiment_score": 0.6
        }
        
        analysis = MacroAnalysis(**data)
        
        assert analysis.economic_cycle == "复苏"
        assert analysis.liquidity == "宽松"
        assert len(analysis.key_indicators) == 3
        assert analysis.confidence == 0.8
        assert analysis.sentiment_score == 0.6
    
    def test_macro_analysis_json_serialization(self):
        """测试JSON序列化"""
        from tradingagents.agents.utils.analysis_schemas import MacroAnalysis
        
        data = {
            "economic_cycle": "扩张",
            "liquidity": "中性",
            "key_indicators": ["GDP", "CPI"],
            "analysis_summary": "经济扩张，流动性中性。",
            "confidence": 0.7,
            "sentiment_score": 0.5
        }
        
        analysis = MacroAnalysis(**data)
        json_str = analysis.model_dump_json()
        
        # 应该可以序列化
        assert isinstance(json_str, str)
        
        # 应该可以反序列化
        parsed = json.loads(json_str)
        assert parsed['economic_cycle'] == "扩张"
    
    def test_macro_analysis_validation(self):
        """测试字段验证"""
        from tradingagents.agents.utils.analysis_schemas import MacroAnalysis
        
        # confidence超出范围应该失败
        with pytest.raises(ValidationError):
            MacroAnalysis(
                economic_cycle="复苏",
                liquidity="宽松",
                key_indicators=["GDP"],
                analysis_summary="test",
                confidence=1.5,  # 超出范围
                sentiment_score=0.5
            )
        
        # sentiment_score超出范围应该失败
        with pytest.raises(ValidationError):
            MacroAnalysis(
                economic_cycle="复苏",
                liquidity="宽松",
                key_indicators=["GDP"],
                analysis_summary="test",
                confidence=0.8,
                sentiment_score=2.0  # 超出范围
            )


class TestPolicyAnalysisSchema:
    """测试PolicyAnalysis Schema"""
    
    def test_schema_import(self):
        """测试Schema可以正确导入"""
        from tradingagents.agents.utils.analysis_schemas import PolicyAnalysis
        
        assert PolicyAnalysis is not None
    
    def test_valid_policy_analysis(self):
        """测试有效的政策分析数据"""
        from tradingagents.agents.utils.analysis_schemas import PolicyAnalysis
        
        data = {
            "monetary_policy": "宽松",
            "fiscal_policy": "积极",
            "industry_policy": ["新能源", "半导体", "人工智能"],
            "key_events": ["降准0.5个百分点", "减税降费政策"],
            "market_impact": "正面",
            "analysis_summary": "货币政策宽松，财政政策积极，产业政策支持新兴产业，对市场影响正面。",
            "confidence": 0.85,
            "sentiment_score": 0.7
        }
        
        analysis = PolicyAnalysis(**data)
        
        assert analysis.monetary_policy == "宽松"
        assert analysis.fiscal_policy == "积极"
        assert len(analysis.industry_policy) == 3
        assert analysis.market_impact == "正面"


class TestSectorAnalysisSchema:
    """测试SectorAnalysis Schema"""
    
    def test_schema_import(self):
        """测试Schema可以正确导入"""
        from tradingagents.agents.utils.analysis_schemas import SectorAnalysis
        
        assert SectorAnalysis is not None
    
    def test_valid_sector_analysis(self):
        """测试有效的板块分析数据"""
        from tradingagents.agents.utils.analysis_schemas import SectorAnalysis
        
        data = {
            "top_sectors": ["新能源车", "半导体", "消费电子"],
            "bottom_sectors": ["房地产", "煤炭", "钢铁"],
            "rotation_trend": "成长→价值",
            "hot_themes": ["AI", "新能源", "自主可控"],
            "analysis_summary": "成长板块领涨，传统周期板块承压，资金向新兴产业流动。",
            "confidence": 0.75,
            "sentiment_score": 0.4
        }
        
        analysis = SectorAnalysis(**data)
        
        assert len(analysis.top_sectors) == 3
        assert len(analysis.bottom_sectors) == 3
        assert analysis.rotation_trend == "成长→价值"


class TestStrategyOutputSchema:
    """测试StrategyOutput Schema"""
    
    def test_schema_import(self):
        """测试Schema可以正确导入"""
        from tradingagents.agents.utils.analysis_schemas import StrategyOutput
        
        assert StrategyOutput is not None
    
    def test_valid_strategy_output(self):
        """测试有效的策略输出数据"""
        from tradingagents.agents.utils.analysis_schemas import StrategyOutput
        
        data = {
            "market_outlook": "看多",
            "recommended_position": 0.7,
            "key_risks": ["流动性收紧风险", "政策不确定性"],
            "opportunity_sectors": ["新能源", "半导体", "AI"],
            "rationale": "宏观经济复苏，政策支持新兴产业，板块轮动向成长股转移，建议适度加仓。",
            "final_sentiment_score": 0.6,
            "confidence": 0.8
        }
        
        strategy = StrategyOutput(**data)
        
        assert strategy.market_outlook == "看多"
        assert strategy.recommended_position == 0.7
        assert len(strategy.key_risks) == 2
        assert len(strategy.opportunity_sectors) == 3
    
    def test_strategy_position_validation(self):
        """测试仓位字段验证"""
        from tradingagents.agents.utils.analysis_schemas import StrategyOutput
        
        # 仓位超出范围应该失败
        with pytest.raises(ValidationError):
            StrategyOutput(
                market_outlook="看多",
                recommended_position=1.5,  # 超出范围
                key_risks=["风险1"],
                opportunity_sectors=["板块1"],
                rationale="测试",
                final_sentiment_score=0.5,
                confidence=0.8
            )


class TestJSONSchemaConstants:
    """测试JSON Schema常量"""
    
    def test_macro_schema_constant(self):
        """测试宏观分析JSON Schema常量"""
        from tradingagents.agents.utils.analysis_schemas import MACRO_ANALYSIS_SCHEMA
        
        assert MACRO_ANALYSIS_SCHEMA is not None
        assert isinstance(MACRO_ANALYSIS_SCHEMA, dict)
        assert 'type' in MACRO_ANALYSIS_SCHEMA
        assert 'properties' in MACRO_ANALYSIS_SCHEMA
        assert 'required' in MACRO_ANALYSIS_SCHEMA
        
        # 验证必需字段
        required_fields = MACRO_ANALYSIS_SCHEMA['required']
        assert 'economic_cycle' in required_fields
        assert 'confidence' in required_fields
        assert 'sentiment_score' in required_fields
    
    def test_policy_schema_constant(self):
        """测试政策分析JSON Schema常量"""
        from tradingagents.agents.utils.analysis_schemas import POLICY_ANALYSIS_SCHEMA
        
        assert POLICY_ANALYSIS_SCHEMA is not None
        assert isinstance(POLICY_ANALYSIS_SCHEMA, dict)
        
        # 验证必需字段
        required_fields = POLICY_ANALYSIS_SCHEMA['required']
        assert 'monetary_policy' in required_fields
        assert 'fiscal_policy' in required_fields
    
    def test_sector_schema_constant(self):
        """测试板块分析JSON Schema常量"""
        from tradingagents.agents.utils.analysis_schemas import SECTOR_ANALYSIS_SCHEMA
        
        assert SECTOR_ANALYSIS_SCHEMA is not None
        assert isinstance(SECTOR_ANALYSIS_SCHEMA, dict)
        
        # 验证必需字段
        required_fields = SECTOR_ANALYSIS_SCHEMA['required']
        assert 'top_sectors' in required_fields
        assert 'hot_themes' in required_fields
    
    def test_strategy_schema_constant(self):
        """测试策略输出JSON Schema常量"""
        from tradingagents.agents.utils.analysis_schemas import STRATEGY_OUTPUT_SCHEMA
        
        assert STRATEGY_OUTPUT_SCHEMA is not None
        assert isinstance(STRATEGY_OUTPUT_SCHEMA, dict)
        
        # 验证必需字段
        required_fields = STRATEGY_OUTPUT_SCHEMA['required']
        assert 'market_outlook' in required_fields
        assert 'recommended_position' in required_fields
        assert 'final_sentiment_score' in required_fields


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
