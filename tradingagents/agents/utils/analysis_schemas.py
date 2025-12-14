#!/usr/bin/env python3
"""
指数分析Schema定义
定义指数分析各个Agent的输出结构

使用Pydantic BaseModel定义严格的数据结构,
并提供JSON Schema常量供Prompt使用
"""

from pydantic import BaseModel, Field
from typing import List, Optional


# ==================== 宏观经济分析 ====================

class MacroAnalysis(BaseModel):
    """宏观经济分析输出结构"""
    
    economic_cycle: str = Field(
        description="当前经济周期阶段: 复苏/扩张/滞胀/衰退"
    )
    liquidity: str = Field(
        description="流动性状况: 宽松/中性/紧缩"
    )
    key_indicators: List[str] = Field(
        description="关键宏观指标列表，如GDP增速、CPI、PMI等"
    )
    analysis_summary: str = Field(
        description="宏观分析总结，100-200字"
    )
    confidence: float = Field(
        ge=0.0, le=1.0,
        description="分析置信度，0-1之间"
    )
    sentiment_score: float = Field(
        ge=-1.0, le=1.0,
        description="宏观情绪评分，-1(极度悲观)到1(极度乐观)"
    )


# ==================== 政策分析 ====================

class PolicyAnalysis(BaseModel):
    """政策分析输出结构"""
    
    monetary_policy: str = Field(
        description="货币政策判断: 宽松/中性/紧缩"
    )
    fiscal_policy: str = Field(
        description="财政政策判断: 积极/稳健/紧缩"
    )
    industry_policy: List[str] = Field(
        description="产业政策支持方向列表，如自主可控、新能源等"
    )
    key_events: List[str] = Field(
        description="关键政策事件列表"
    )
    market_impact: str = Field(
        description="政策对市场的影响: 正面/中性/负面"
    )
    analysis_summary: str = Field(
        description="政策分析总结，100-200字"
    )
    confidence: float = Field(
        ge=0.0, le=1.0,
        description="分析置信度，0-1之间"
    )
    sentiment_score: float = Field(
        ge=-1.0, le=1.0,
        description="政策情绪评分，-1(极度负面)到1(极度正面)"
    )


# ==================== 板块轮动分析 ====================

class SectorAnalysis(BaseModel):
    """板块轮动分析输出结构"""
    
    top_sectors: List[str] = Field(
        description="领涨板块列表 (Top 3-5)"
    )
    bottom_sectors: List[str] = Field(
        description="领跌板块列表 (Bottom 3-5)"
    )
    rotation_trend: str = Field(
        description="轮动特征: 成长→价值/大盘→小盘/防御→进攻等"
    )
    hot_themes: List[str] = Field(
        description="热点主题列表，如半导体、新能源车等"
    )
    analysis_summary: str = Field(
        description="板块分析总结，100-200字"
    )
    confidence: float = Field(
        ge=0.0, le=1.0,
        description="分析置信度，0-1之间"
    )
    sentiment_score: float = Field(
        ge=-1.0, le=1.0,
        description="板块情绪评分，-1(普跌)到1(普涨)"
    )


# ==================== 策略输出 ====================

class StrategyOutput(BaseModel):
    """策略顾问输出结构"""
    
    market_outlook: str = Field(
        description="市场展望: 看多/中性/看空"
    )
    recommended_position: float = Field(
        ge=0.0, le=1.0,
        description="建议仓位，0.0(空仓)到1.0(满仓)"
    )
    key_risks: List[str] = Field(
        description="关键风险点列表"
    )
    opportunity_sectors: List[str] = Field(
        description="机会板块列表"
    )
    rationale: str = Field(
        description="策略依据，200-300字"
    )
    final_sentiment_score: float = Field(
        ge=-1.0, le=1.0,
        description="最终综合情绪评分，-1(极度悲观)到1(极度乐观)"
    )
    confidence: float = Field(
        ge=0.0, le=1.0,
        description="策略置信度，0-1之间"
    )


# ==================== JSON Schema常量 (用于Prompt) ====================

MACRO_ANALYSIS_SCHEMA = {
    "type": "object",
    "properties": {
        "economic_cycle": {
            "type": "string",
            "description": "当前经济周期阶段",
            "enum": ["复苏", "扩张", "滞胀", "衰退"]
        },
        "liquidity": {
            "type": "string",
            "description": "流动性状况",
            "enum": ["宽松", "中性", "紧缩"]
        },
        "key_indicators": {
            "type": "array",
            "items": {"type": "string"},
            "description": "关键宏观指标列表"
        },
        "analysis_summary": {
            "type": "string",
            "description": "宏观分析总结，100-200字"
        },
        "confidence": {
            "type": "number",
            "minimum": 0.0,
            "maximum": 1.0,
            "description": "分析置信度"
        },
        "sentiment_score": {
            "type": "number",
            "minimum": -1.0,
            "maximum": 1.0,
            "description": "宏观情绪评分"
        }
    },
    "required": ["economic_cycle", "liquidity", "key_indicators", "analysis_summary", "confidence", "sentiment_score"]
}


POLICY_ANALYSIS_SCHEMA = {
    "type": "object",
    "properties": {
        "monetary_policy": {
            "type": "string",
            "description": "货币政策判断",
            "enum": ["宽松", "中性", "紧缩"]
        },
        "fiscal_policy": {
            "type": "string",
            "description": "财政政策判断",
            "enum": ["积极", "稳健", "紧缩"]
        },
        "industry_policy": {
            "type": "array",
            "items": {"type": "string"},
            "description": "产业政策支持方向列表"
        },
        "key_events": {
            "type": "array",
            "items": {"type": "string"},
            "description": "关键政策事件列表"
        },
        "market_impact": {
            "type": "string",
            "description": "政策对市场的影响",
            "enum": ["正面", "中性", "负面"]
        },
        "analysis_summary": {
            "type": "string",
            "description": "政策分析总结，100-200字"
        },
        "confidence": {
            "type": "number",
            "minimum": 0.0,
            "maximum": 1.0,
            "description": "分析置信度"
        },
        "sentiment_score": {
            "type": "number",
            "minimum": -1.0,
            "maximum": 1.0,
            "description": "政策情绪评分"
        }
    },
    "required": ["monetary_policy", "fiscal_policy", "industry_policy", "key_events", "market_impact", "analysis_summary", "confidence", "sentiment_score"]
}


SECTOR_ANALYSIS_SCHEMA = {
    "type": "object",
    "properties": {
        "top_sectors": {
            "type": "array",
            "items": {"type": "string"},
            "description": "领涨板块列表"
        },
        "bottom_sectors": {
            "type": "array",
            "items": {"type": "string"},
            "description": "领跌板块列表"
        },
        "rotation_trend": {
            "type": "string",
            "description": "轮动特征"
        },
        "hot_themes": {
            "type": "array",
            "items": {"type": "string"},
            "description": "热点主题列表"
        },
        "analysis_summary": {
            "type": "string",
            "description": "板块分析总结，100-200字"
        },
        "confidence": {
            "type": "number",
            "minimum": 0.0,
            "maximum": 1.0,
            "description": "分析置信度"
        },
        "sentiment_score": {
            "type": "number",
            "minimum": -1.0,
            "maximum": 1.0,
            "description": "板块情绪评分"
        }
    },
    "required": ["top_sectors", "bottom_sectors", "rotation_trend", "hot_themes", "analysis_summary", "confidence", "sentiment_score"]
}


STRATEGY_OUTPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "market_outlook": {
            "type": "string",
            "description": "市场展望",
            "enum": ["看多", "中性", "看空"]
        },
        "recommended_position": {
            "type": "number",
            "minimum": 0.0,
            "maximum": 1.0,
            "description": "建议仓位"
        },
        "key_risks": {
            "type": "array",
            "items": {"type": "string"},
            "description": "关键风险点列表"
        },
        "opportunity_sectors": {
            "type": "array",
            "items": {"type": "string"},
            "description": "机会板块列表"
        },
        "rationale": {
            "type": "string",
            "description": "策略依据，200-300字"
        },
        "final_sentiment_score": {
            "type": "number",
            "minimum": -1.0,
            "maximum": 1.0,
            "description": "最终综合情绪评分"
        },
        "confidence": {
            "type": "number",
            "minimum": 0.0,
            "maximum": 1.0,
            "description": "策略置信度"
        }
    },
    "required": ["market_outlook", "recommended_position", "key_risks", "opportunity_sectors", "rationale", "final_sentiment_score", "confidence"]
}
