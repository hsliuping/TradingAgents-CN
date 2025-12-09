# tradingagents/core/__init__.py
"""
Core module - 股票分析引擎核心组件

包含:
- engine: 分析引擎核心实现
- contracts: 数据契约定义
"""

from tradingagents.core.engine import (
    # 数据契约
    DataLayer,
    DataAccess,
    AgentDataContract,
    # 分析上下文
    AnalysisContext,
    # 数据字典
    FieldDefinition,
    DynamicDataSchema,
    data_schema,
    # 数据访问管理器
    DataAccessManager,
    AccessLogEntry,
    # 契约验证器
    ContractValidator,
    ValidationResult,
    ValidationError,
    # 分析引擎
    AnalysisPhase,
    PhaseResult,
    AnalysisResult,
    StockAnalysisEngine,
)

__all__ = [
    # 数据契约
    "DataLayer",
    "DataAccess",
    "AgentDataContract",
    # 分析上下文
    "AnalysisContext",
    # 数据字典
    "FieldDefinition",
    "DynamicDataSchema",
    "data_schema",
    # 数据访问管理器
    "DataAccessManager",
    "AccessLogEntry",
    # 契约验证器
    "ContractValidator",
    "ValidationResult",
    "ValidationError",
    # 分析引擎
    "AnalysisPhase",
    "PhaseResult",
    "AnalysisResult",
    "StockAnalysisEngine",
]

