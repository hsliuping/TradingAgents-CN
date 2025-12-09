# tradingagents/core/engine/contract_validator.py
"""
契约验证器

验证 Agent 数据契约的合法性，包括：
- 输入字段是否存在于数据字典
- 输出字段是否与核心字段冲突
- 依赖关系是否合理
"""

from typing import List, Dict, Optional
from dataclasses import dataclass, field

from tradingagents.core.engine.data_contract import AgentDataContract, DataLayer
from tradingagents.core.engine.data_schema import DynamicDataSchema, data_schema


@dataclass
class ValidationError:
    """验证错误"""
    agent_id: str
    error_type: str  # 'invalid_input', 'core_conflict', 'missing_dependency'
    message: str
    field_name: Optional[str] = None
    layer: Optional[DataLayer] = None


@dataclass
class ValidationResult:
    """验证结果"""
    is_valid: bool
    errors: List[ValidationError] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    
    def add_error(self, error: ValidationError):
        """添加错误"""
        self.errors.append(error)
        self.is_valid = False
    
    def add_warning(self, warning: str):
        """添加警告"""
        self.warnings.append(warning)


class ContractValidator:
    """
    数据契约验证器
    
    验证 Agent 契约的合法性，确保：
    1. 输入字段必须在数据字典中存在
    2. 输出字段不能覆盖核心字段
    3. 依赖的 Agent 必须存在（可选检查）
    """
    
    def __init__(self, schema: DynamicDataSchema = None):
        """
        初始化验证器
        
        Args:
            schema: 数据字典实例，默认使用全局单例
        """
        self.schema = schema or data_schema
        self._registered_agents: Dict[str, AgentDataContract] = {}
    
    def register_contract(self, contract: AgentDataContract) -> None:
        """
        注册契约（用于依赖检查）
        
        Args:
            contract: Agent 数据契约
        """
        self._registered_agents[contract.agent_id] = contract
    
    def validate_contract(
        self, 
        contract: AgentDataContract,
        check_dependencies: bool = False,
        strict_input_check: bool = False
    ) -> ValidationResult:
        """
        验证单个 Agent 契约的合法性
        
        Args:
            contract: 要验证的契约
            check_dependencies: 是否检查依赖的 Agent 是否已注册
            strict_input_check: 是否严格检查输入字段（字段必须预先存在）
            
        Returns:
            ValidationResult 验证结果
        """
        result = ValidationResult(is_valid=True)
        
        # 1. 验证输入字段
        if strict_input_check:
            self._validate_inputs(contract, result)
        
        # 2. 验证输出字段不与核心字段冲突
        self._validate_outputs(contract, result)
        
        # 3. 验证依赖关系
        if check_dependencies:
            self._validate_dependencies(contract, result)
        
        return result
    
    def _validate_inputs(self, contract: AgentDataContract, result: ValidationResult) -> None:
        """验证输入字段"""
        for access in contract.inputs:
            # 如果 fields 为空，表示访问整层，不需要验证具体字段
            if not access.fields:
                continue
            
            for field_name in access.fields:
                if not self.schema.is_valid_field(access.layer, field_name):
                    result.add_error(ValidationError(
                        agent_id=contract.agent_id,
                        error_type="invalid_input",
                        message=f"输入字段无效: {access.layer.value}.{field_name}",
                        field_name=field_name,
                        layer=access.layer
                    ))
    
    def _validate_outputs(self, contract: AgentDataContract, result: ValidationResult) -> None:
        """
        验证输出字段

        规则：
        - DECISIONS 层的核心字段允许写入（这些是预定义的决策输出位置）
        - 其他层的核心字段不允许覆盖（如 CONTEXT 层的 ticker）
        """
        from tradingagents.core.engine.data_contract import DataLayer

        for access in contract.outputs:
            for field_name in access.fields:
                if self.schema.is_core_field(access.layer, field_name):
                    # DECISIONS 层的核心字段允许写入
                    if access.layer == DataLayer.DECISIONS:
                        continue

                    # 其他层的核心字段不允许覆盖
                    result.add_error(ValidationError(
                        agent_id=contract.agent_id,
                        error_type="core_conflict",
                        message=f"不能覆盖核心字段: {access.layer.value}.{field_name}",
                        field_name=field_name,
                        layer=access.layer
                    ))
    
    def _validate_dependencies(self, contract: AgentDataContract, result: ValidationResult) -> None:
        """验证依赖的 Agent 是否已注册"""
        for dep_id in contract.depends_on:
            if dep_id not in self._registered_agents:
                result.add_error(ValidationError(
                    agent_id=contract.agent_id,
                    error_type="missing_dependency",
                    message=f"依赖的 Agent 未注册: {dep_id}"
                ))
    
    def validate_all_contracts(
        self, 
        contracts: List[AgentDataContract],
        check_dependencies: bool = True
    ) -> Dict[str, ValidationResult]:
        """
        验证多个 Agent 契约
        
        Args:
            contracts: 契约列表
            check_dependencies: 是否检查依赖关系
            
        Returns:
            agent_id -> ValidationResult 的字典
        """
        # 先注册所有契约
        for contract in contracts:
            self.register_contract(contract)
        
        # 再逐个验证
        results = {}
        for contract in contracts:
            results[contract.agent_id] = self.validate_contract(
                contract, 
                check_dependencies=check_dependencies
            )
        
        return results

