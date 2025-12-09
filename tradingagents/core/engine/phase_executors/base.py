# tradingagents/core/engine/phase_executors/base.py
"""
阶段执行器基类

定义阶段执行的标准接口和通用功能
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from tradingagents.utils.logging_init import get_logger

from ..analysis_context import AnalysisContext
from ..data_access_manager import DataAccessManager
from ..data_contract import AgentDataContract, DataLayer

logger = get_logger("default")


@dataclass
class PhaseContext:
    """
    阶段执行上下文
    
    封装阶段执行所需的所有依赖
    """
    analysis_context: AnalysisContext
    data_manager: DataAccessManager
    llm_provider: Any = None
    config: Dict[str, Any] = field(default_factory=dict)
    
    def get_ticker(self) -> str:
        """获取股票代码"""
        return self.analysis_context.get(DataLayer.CONTEXT, "ticker") or ""
    
    def get_trade_date(self) -> str:
        """获取交易日期"""
        return self.analysis_context.get(DataLayer.CONTEXT, "trade_date") or ""
    
    def get_market_type(self) -> str:
        """获取市场类型"""
        return self.analysis_context.get(DataLayer.CONTEXT, "market_type") or "cn"


class PhaseExecutor(ABC):
    """
    阶段执行器基类
    
    所有阶段执行器都需要继承此类并实现 execute 方法
    
    用法:
        class DataCollectionPhase(PhaseExecutor):
            def execute(self, context, data_manager):
                # 执行数据收集
                return {"collected": True}
    """
    
    # 阶段名称（子类应覆盖）
    phase_name: str = "base"
    
    # 阶段需要的契约列表（子类可覆盖）
    required_contracts: List[AgentDataContract] = []
    
    def __init__(self, llm_provider: Any = None, config: Optional[Dict[str, Any]] = None):
        """
        初始化阶段执行器
        
        Args:
            llm_provider: LLM 提供者实例
            config: 阶段配置
        """
        self.llm_provider = llm_provider
        self.config = config or {}
    
    @abstractmethod
    def execute(
        self,
        context: AnalysisContext,
        data_manager: DataAccessManager
    ) -> Dict[str, Any]:
        """
        执行阶段
        
        Args:
            context: 分析上下文
            data_manager: 数据访问管理器
            
        Returns:
            阶段输出字典
        """
        pass
    
    def validate_inputs(
        self,
        context: AnalysisContext,
        data_manager: DataAccessManager
    ) -> bool:
        """
        验证阶段输入
        
        检查所有必需的输入数据是否存在
        
        Args:
            context: 分析上下文
            data_manager: 数据访问管理器
            
        Returns:
            验证是否通过
        """
        for contract in self.required_contracts:
            for access in contract.inputs:
                if access.required:
                    for field_name in access.fields:
                        value = context.get(access.layer, field_name)
                        if value is None:
                            logger.warning(
                                f"⚠️ [{self.phase_name}] 缺少必需输入: "
                                f"{access.layer.value}.{field_name}"
                            )
                            return False
        return True
    
    def create_phase_context(
        self,
        context: AnalysisContext,
        data_manager: DataAccessManager
    ) -> PhaseContext:
        """创建阶段上下文"""
        return PhaseContext(
            analysis_context=context,
            data_manager=data_manager,
            llm_provider=self.llm_provider,
            config=self.config
        )
    
    def log_start(self) -> None:
        """记录阶段开始"""
        logger.info(f"▶️ [{self.phase_name}] 阶段开始执行")
    
    def log_end(self, outputs: Dict[str, Any]) -> None:
        """记录阶段结束"""
        output_keys = list(outputs.keys()) if outputs else []
        logger.info(f"✅ [{self.phase_name}] 阶段执行完成, 输出: {output_keys}")

