"""
分析师注册表

专门管理分析师类型的 Agent，提供工作流构建相关功能

扩展功能：
- 支持数据契约注册和验证
- 自动将 Agent 输出字段注册到数据字典
"""

from typing import Dict, List, Optional, Type, Callable, Any
from .base import BaseAgent
from .config import AgentCategory, AgentMetadata, BUILTIN_AGENTS
from .registry import AgentRegistry, get_registry

# 数据契约相关导入
from tradingagents.core.engine.data_contract import AgentDataContract
from tradingagents.core.engine.data_schema import data_schema
from tradingagents.core.engine.contract_validator import ContractValidator

# 导入日志
from tradingagents.utils.logging_init import get_logger
logger = get_logger("default")


class AnalystRegistry:
    """
    分析师注册表
    
    扩展 AgentRegistry，专门管理分析师类型的 Agent，
    提供工作流构建和报告聚合相关功能
    
    用法:
        registry = AnalystRegistry()
        
        # 注册分析师
        registry.register("sector", SectorAnalystAgent, metadata)
        
        # 获取所有分析师（按执行顺序）
        analysts = registry.get_analysts_ordered()
        
        # 获取分析师元数据
        meta = registry.get_analyst_metadata("sector")
    """
    
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(AnalystRegistry, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if not self._initialized:
            self._analysts: Dict[str, Type[BaseAgent]] = {}
            self._analyst_factories: Dict[str, Callable] = {}  # 工厂函数
            self._analyst_metadata: Dict[str, AgentMetadata] = {}
            self._contracts: Dict[str, AgentDataContract] = {}  # 数据契约
            self._contract_validator = ContractValidator()  # 契约验证器
            self._load_builtin_analysts()
            self._initialized = True
    
    def _load_builtin_analysts(self) -> None:
        """加载内置分析师元数据"""
        for agent_id, metadata in BUILTIN_AGENTS.items():
            if metadata.category == AgentCategory.ANALYST:
                self._analyst_metadata[agent_id] = metadata
    
    def register(
        self,
        analyst_id: str,
        agent_class: Optional[Type[BaseAgent]] = None,
        factory: Optional[Callable] = None,
        metadata: Optional[AgentMetadata] = None,
        contract: Optional[AgentDataContract] = None,
        override: bool = False
    ) -> None:
        """
        注册分析师

        Args:
            analyst_id: 分析师ID，如 "sector"
            agent_class: Agent 类（可选）
            factory: 工厂函数（可选），用于创建 Agent 实例
            metadata: 元数据（可选，如果未提供则使用内置元数据）
            contract: 数据契约（可选），定义输入输出字段
            override: 是否覆盖已存在的注册
        """
        if analyst_id in self._analysts and not override:
            raise ValueError(f"分析师 '{analyst_id}' 已注册，使用 override=True 覆盖")

        if agent_class:
            self._analysts[analyst_id] = agent_class
        if factory:
            self._analyst_factories[analyst_id] = factory
        if metadata:
            self._analyst_metadata[analyst_id] = metadata

        # 注册数据契约
        if contract:
            self._register_contract(analyst_id, contract)

        logger.debug(f"📋 [AnalystRegistry] 注册分析师: {analyst_id}")

    def _register_contract(self, analyst_id: str, contract: AgentDataContract) -> None:
        """
        注册数据契约

        1. 验证契约合法性
        2. 将输出字段注册到数据字典
        3. 保存契约到注册表

        Args:
            analyst_id: 分析师ID
            contract: 数据契约
        """
        # 验证契约
        result = self._contract_validator.validate_contract(contract)
        if not result.is_valid:
            error_msgs = [e.message for e in result.errors]
            raise ValueError(f"契约验证失败 [{analyst_id}]: {error_msgs}")

        # 将输出字段注册到数据字典
        data_schema.register_agent_fields(analyst_id, contract.outputs)

        # 保存契约
        self._contracts[analyst_id] = contract
        self._contract_validator.register_contract(contract)

        logger.debug(f"📋 [AnalystRegistry] 注册契约: {analyst_id}")
    
    def get_analyst_class(self, analyst_id: str) -> Optional[Type[BaseAgent]]:
        """获取分析师类"""
        return self._analysts.get(analyst_id)
    
    def get_analyst_factory(self, analyst_id: str) -> Optional[Callable]:
        """获取分析师工厂函数"""
        return self._analyst_factories.get(analyst_id)
    
    def get_analyst_metadata(self, analyst_id: str) -> Optional[AgentMetadata]:
        """获取分析师元数据"""
        return self._analyst_metadata.get(analyst_id)
    
    def get_analysts_ordered(self, selected: Optional[List[str]] = None) -> List[AgentMetadata]:
        """
        获取分析师列表（按 execution_order 排序）
        
        Args:
            selected: 指定的分析师ID列表，如果为 None 则返回所有
            
        Returns:
            按执行顺序排列的分析师元数据列表
        """
        analysts = []
        for analyst_id, metadata in self._analyst_metadata.items():
            if selected is None or analyst_id in selected:
                # 确保只包含已注册实现的分析师，或内置分析师
                if analyst_id in self._analysts or analyst_id in self._analyst_factories:
                    analysts.append(metadata)
                elif metadata.category == AgentCategory.ANALYST:
                    # 内置但未注册实现的分析师也包含（由原始 setup.py 处理）
                    analysts.append(metadata)
        
        # 按 execution_order 排序
        return sorted(analysts, key=lambda m: m.execution_order)
    
    def get_output_fields(self, selected: Optional[List[str]] = None) -> Dict[str, str]:
        """
        获取所有分析师的输出字段映射
        
        Args:
            selected: 指定的分析师ID列表
            
        Returns:
            {analyst_id: output_field} 映射
        """
        result = {}
        for analyst_id, metadata in self._analyst_metadata.items():
            if selected is None or analyst_id in selected:
                if metadata.output_field:
                    result[analyst_id] = metadata.output_field
        return result
    
    def is_registered(self, analyst_id: str) -> bool:
        """检查分析师是否已注册实现"""
        return analyst_id in self._analysts or analyst_id in self._analyst_factories

    def list_all(self) -> List[str]:
        """列出所有已知的分析师ID"""
        return list(self._analyst_metadata.keys())

    # =========================================
    # 契约相关方法
    # =========================================

    def get_contract(self, analyst_id: str) -> Optional[AgentDataContract]:
        """获取分析师的数据契约"""
        return self._contracts.get(analyst_id)

    def get_all_contracts(self) -> Dict[str, AgentDataContract]:
        """获取所有已注册的契约"""
        return self._contracts.copy()

    def has_contract(self, analyst_id: str) -> bool:
        """检查分析师是否有数据契约"""
        return analyst_id in self._contracts

    def validate_all_contracts(self) -> Dict[str, Any]:
        """
        验证所有已注册契约的依赖关系

        Returns:
            验证结果字典 {analyst_id: ValidationResult}
        """
        contracts = list(self._contracts.values())
        return self._contract_validator.validate_all_contracts(contracts)


# 全局实例
_analyst_registry: Optional[AnalystRegistry] = None


def get_analyst_registry() -> AnalystRegistry:
    """获取全局分析师注册表实例"""
    global _analyst_registry
    if _analyst_registry is None:
        _analyst_registry = AnalystRegistry()
    return _analyst_registry

