# tradingagents/core/engine/__init__.py
"""
Engine module - 股票分析引擎

提供:
- 数据契约定义 (DataLayer, DataAccess, AgentDataContract)
- 分析上下文 (AnalysisContext)
- 数据访问管理器 (DataAccessManager)
- 动态数据字典 (DynamicDataSchema)
- 契约验证器 (ContractValidator)
"""

from tradingagents.core.engine.data_contract import (
    DataLayer,
    DataAccess,
    AgentDataContract,
)
from tradingagents.core.engine.analysis_context import AnalysisContext
from tradingagents.core.engine.data_schema import (
    FieldDefinition,
    DynamicDataSchema,
    data_schema,
)
from tradingagents.core.engine.data_access_manager import (
    DataAccessManager,
    AccessLogEntry,
)
from tradingagents.core.engine.contract_validator import (
    ContractValidator,
    ValidationResult,
    ValidationError,
)
from tradingagents.core.engine.stock_analysis_engine import (
    AnalysisPhase,
    PhaseResult,
    AnalysisResult,
    StockAnalysisEngine,
)
from tradingagents.core.engine.agent_integrator import AgentIntegrator

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
    # Agent 集成
    "AgentIntegrator",
]

