# tradingagents/core/engine/analysis_context.py
"""
分析上下文 - 分层数据容器

提供股票分析过程中的数据存储和访问，支持：
- 五层数据结构（Context, RawData, AnalysisData, Reports, Decisions）
- 数据血缘追踪
- 向后兼容旧版 AgentState
"""

from dataclasses import dataclass, field
from typing import Dict, Any, Optional
from datetime import datetime
from tradingagents.core.engine.data_contract import DataLayer


@dataclass
class AnalysisContext:
    """
    股票分析上下文 - 分层数据容器
    
    存储分析过程中的所有数据，按五层结构组织：
    - context: 基础上下文信息
    - raw_data: 原始数据
    - analysis_data: 分析结果（结构化）
    - reports: 分析报告（文本）
    - decisions: 决策数据
    
    Attributes:
        context: 基础信息层（ticker, trade_date, market_type 等）
        raw_data: 原始数据层（price_data, news_data 等）
        analysis_data: 分析数据层（technical, sentiment 等结构化数据）
        reports: 报告层（各分析师生成的文本报告）
        decisions: 决策层（辩论历史、交易信号、风险评估等）
        created_at: 创建时间
        updated_at: 更新时间
        data_lineage: 数据血缘追踪（字段 -> 来源 Agent）
    """
    
    # 五层数据结构
    context: Dict[str, Any] = field(default_factory=dict)
    raw_data: Dict[str, Any] = field(default_factory=dict)
    analysis_data: Dict[str, Any] = field(default_factory=dict)
    reports: Dict[str, str] = field(default_factory=dict)
    decisions: Dict[str, Any] = field(default_factory=dict)
    
    # 元数据
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    data_lineage: Dict[str, str] = field(default_factory=dict)
    
    def _get_layer_data(self, layer: DataLayer) -> Dict[str, Any]:
        """获取指定层的数据字典"""
        layer_map = {
            DataLayer.CONTEXT: self.context,
            DataLayer.RAW_DATA: self.raw_data,
            DataLayer.ANALYSIS_DATA: self.analysis_data,
            DataLayer.REPORTS: self.reports,
            DataLayer.DECISIONS: self.decisions,
        }
        return layer_map.get(layer, {})
    
    def get(self, layer: DataLayer, field_name: str, default=None) -> Any:
        """
        获取指定层的指定字段数据
        
        Args:
            layer: 数据层
            field_name: 字段名
            default: 默认值
            
        Returns:
            字段值，不存在时返回 default
        """
        layer_data = self._get_layer_data(layer)
        return layer_data.get(field_name, default)
    
    def set(self, layer: DataLayer, field_name: str, value: Any, source: str = None) -> None:
        """
        设置指定层的指定字段数据
        
        Args:
            layer: 数据层
            field_name: 字段名
            value: 字段值
            source: 数据来源（Agent ID），用于血缘追踪
        """
        layer_data = self._get_layer_data(layer)
        layer_data[field_name] = value
        self.updated_at = datetime.now()
        
        # 记录数据血缘
        if source:
            lineage_key = f"{layer.value}.{field_name}"
            self.data_lineage[lineage_key] = source
    
    def get_layer(self, layer: DataLayer) -> Dict[str, Any]:
        """获取整层数据的副本"""
        return self._get_layer_data(layer).copy()
    
    def get_field_source(self, layer: DataLayer, field_name: str) -> Optional[str]:
        """获取字段的数据来源"""
        lineage_key = f"{layer.value}.{field_name}"
        return self.data_lineage.get(lineage_key)
    
    def get_reports_for_phase(self, phase: int) -> Dict[str, str]:
        """
        根据执行阶段获取可访问的报告

        Args:
            phase: 执行阶段（1-7）

        Returns:
            可访问的报告字典
        """
        # 阶段 3+ 可以访问所有报告
        if phase >= 3:
            return self.reports.copy()
        return {}

    def to_legacy_state(self) -> Dict[str, Any]:
        """
        转换为旧版 AgentState 格式（向后兼容）

        Returns:
            兼容旧版代码的状态字典
        """
        return {
            "company_of_interest": self.context.get("ticker", ""),
            "trade_date": self.context.get("trade_date", ""),
            "market_report": self.reports.get("market_report", ""),
            "sentiment_report": self.reports.get("sentiment_report", ""),
            "news_report": self.reports.get("news_report", ""),
            "fundamentals_report": self.reports.get("fundamentals_report", ""),
            "sector_report": self.reports.get("sector_report", ""),
            "index_report": self.reports.get("index_report", ""),
            "investment_debate_state": self.decisions.get("investment_debate", {}),
            "investment_plan": self.decisions.get("investment_plan", ""),
            "trader_investment_plan": self.decisions.get("trade_signal", ""),
            "risk_debate_state": self.decisions.get("risk_assessment", {}),
            "final_trade_decision": self.decisions.get("final_decision", ""),
        }

    @classmethod
    def from_legacy_state(cls, state: Dict[str, Any]) -> "AnalysisContext":
        """
        从旧版 AgentState 创建上下文（向后兼容）

        Args:
            state: 旧版状态字典

        Returns:
            AnalysisContext 实例
        """
        ctx = cls()

        # 解析 context 层
        ctx.context = {
            "ticker": state.get("company_of_interest", ""),
            "trade_date": state.get("trade_date", ""),
        }

        # 解析 reports 层
        ctx.reports = {
            "market_report": state.get("market_report", ""),
            "sentiment_report": state.get("sentiment_report", ""),
            "news_report": state.get("news_report", ""),
            "fundamentals_report": state.get("fundamentals_report", ""),
            "sector_report": state.get("sector_report", ""),
            "index_report": state.get("index_report", ""),
        }

        # 解析 decisions 层
        ctx.decisions = {
            "investment_debate": state.get("investment_debate_state", {}),
            "investment_plan": state.get("investment_plan", ""),
            "trade_signal": state.get("trader_investment_plan", ""),
            "risk_assessment": state.get("risk_debate_state", {}),
            "final_decision": state.get("final_trade_decision", ""),
        }

        return ctx

    def __repr__(self) -> str:
        """返回上下文的简要描述"""
        ticker = self.context.get("ticker", "N/A")
        date = self.context.get("trade_date", "N/A")
        reports_count = len(self.reports)
        return f"AnalysisContext(ticker={ticker}, date={date}, reports={reports_count})"

