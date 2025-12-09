# tradingagents/core/engine/data_contract.py
"""
数据契约定义

提供 Agent 之间数据交互的声明式契约，包括：
- DataLayer: 数据分层枚举
- DataAccess: 数据访问声明
- AgentDataContract: Agent 数据契约
"""

from enum import Enum
from typing import List, Set, Optional
from dataclasses import dataclass, field


class DataLayer(str, Enum):
    """
    数据分层枚举
    
    定义五层数据结构，每层有不同的职责和访问权限：
    - CONTEXT: 基础上下文信息（股票代码、日期等）
    - RAW_DATA: 原始数据（价格、新闻、财务数据等）
    - ANALYSIS_DATA: 分析结果（结构化技术指标、估值指标等）
    - REPORTS: 分析报告（各分析师生成的文本报告）
    - DECISIONS: 决策数据（辩论历史、交易信号、风险评估等）
    """
    CONTEXT = "context"
    RAW_DATA = "raw_data"
    ANALYSIS_DATA = "analysis_data"
    REPORTS = "reports"
    DECISIONS = "decisions"


@dataclass
class DataAccess:
    """
    数据访问声明
    
    声明 Agent 对某一数据层的访问需求。
    
    Attributes:
        layer: 数据层
        fields: 需要访问的字段列表，空列表表示访问整层所有数据
        required: 是否必需，False 表示可选（数据不存在时不报错）
    
    Examples:
        # 访问特定字段
        DataAccess(layer=DataLayer.CONTEXT, fields=["ticker", "trade_date"])
        
        # 访问整层所有数据
        DataAccess(layer=DataLayer.REPORTS)  # fields 默认为空列表
        
        # 可选访问
        DataAccess(layer=DataLayer.DECISIONS, fields=["debate"], required=False)
    """
    layer: DataLayer
    fields: List[str] = field(default_factory=list)
    required: bool = True
    
    def __post_init__(self):
        """验证字段类型"""
        if not isinstance(self.layer, DataLayer):
            raise ValueError(f"layer must be DataLayer, got {type(self.layer)}")
        if not isinstance(self.fields, list):
            raise ValueError(f"fields must be list, got {type(self.fields)}")


@dataclass
class AgentDataContract:
    """
    Agent 数据契约
    
    定义 Agent 的数据输入输出规范，实现声明式数据依赖。
    
    Attributes:
        agent_id: Agent 唯一标识
        inputs: 输入数据声明列表
        outputs: 输出数据声明列表
        depends_on: 依赖的 Agent ID 集合
        description: 契约描述
    
    Examples:
        MARKET_ANALYST_CONTRACT = AgentDataContract(
            agent_id="market_analyst",
            inputs=[
                DataAccess(layer=DataLayer.CONTEXT, fields=["ticker", "company_name"]),
                DataAccess(layer=DataLayer.RAW_DATA, fields=["price_data"]),
            ],
            outputs=[
                DataAccess(layer=DataLayer.ANALYSIS_DATA, fields=["technical"]),
                DataAccess(layer=DataLayer.REPORTS, fields=["market_report"]),
            ],
            depends_on={"data_collector"},
            description="市场分析师 - 负责技术分析"
        )
    """
    agent_id: str
    inputs: List[DataAccess] = field(default_factory=list)
    outputs: List[DataAccess] = field(default_factory=list)
    depends_on: Set[str] = field(default_factory=set)
    description: str = ""
    
    def __post_init__(self):
        """验证契约完整性"""
        if not self.agent_id:
            raise ValueError("agent_id cannot be empty")
        
        # 确保 depends_on 是集合
        if isinstance(self.depends_on, (list, tuple)):
            self.depends_on = set(self.depends_on)
    
    def get_input_layers(self) -> Set[DataLayer]:
        """获取所有输入数据层"""
        return {access.layer for access in self.inputs}
    
    def get_output_layers(self) -> Set[DataLayer]:
        """获取所有输出数据层"""
        return {access.layer for access in self.outputs}
    
    def get_input_fields(self, layer: DataLayer) -> List[str]:
        """获取指定层的输入字段列表"""
        for access in self.inputs:
            if access.layer == layer:
                return access.fields
        return []
    
    def get_output_fields(self, layer: DataLayer) -> List[str]:
        """获取指定层的输出字段列表"""
        for access in self.outputs:
            if access.layer == layer:
                return access.fields
        return []
    
    def has_input_access(self, layer: DataLayer, field: str = None) -> bool:
        """检查是否有指定层/字段的输入访问权限"""
        for access in self.inputs:
            if access.layer == layer:
                if not field:
                    return True
                if not access.fields or field in access.fields:
                    return True
        return False
    
    def has_output_access(self, layer: DataLayer, field: str = None) -> bool:
        """检查是否有指定层/字段的输出访问权限"""
        for access in self.outputs:
            if access.layer == layer:
                if not field:
                    return True
                if not access.fields or field in access.fields:
                    return True
        return False

