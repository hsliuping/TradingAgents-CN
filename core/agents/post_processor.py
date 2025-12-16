"""
后处理Agent基类

用于执行分析完成后的后处理操作，如保存报告、发送通知等
v2.0 新增：可配置的后处理Agent架构
"""

import logging
from abc import abstractmethod
from typing import Any, Dict, List, Optional
from enum import Enum

from .base import BaseAgent
from .config import AgentMetadata, AgentCategory

logger = logging.getLogger(__name__)


class PostProcessorType(str, Enum):
    """后处理器类型"""
    SAVE_REPORT = "save_report"           # 保存报告
    SEND_EMAIL = "send_email"             # 发送邮件
    SEND_NOTIFICATION = "send_notification"  # 发送系统通知
    TRIGGER_WEBHOOK = "trigger_webhook"   # 触发Webhook
    GENERATE_PDF = "generate_pdf"         # 生成PDF
    GENERATE_CHART = "generate_chart"     # 生成图表
    UPDATE_CACHE = "update_cache"         # 更新缓存
    RECORD_METRICS = "record_metrics"     # 记录指标


class OperationConfig(dict):
    """
    后处理操作配置
    
    使用字典形式以支持灵活的配置结构
    """
    pass


class ConditionConfig(dict):
    """
    执行条件配置
    
    支持字段比较、逻辑运算等
    """
    pass


class PostProcessorAgent(BaseAgent):
    """
    后处理Agent基类
    
    特点：
    - 不调用LLM（或可选调用LLM生成摘要）
    - 依赖前序Agent的输出
    - 执行外部操作（数据库、邮件、API等）
    - 输出格式：执行状态
    
    工作流程：
    1. 读取分析结果
    2. 检查执行条件
    3. 执行后处理操作
    4. 返回执行状态
    """
    
    # 后处理器类型
    processor_type: PostProcessorType = None
    
    def __init__(
        self,
        config: Optional[Dict[str, Any]] = None,
        operations: Optional[List[OperationConfig]] = None,
        conditions: Optional[List[ConditionConfig]] = None,
        **kwargs
    ):
        """
        初始化后处理Agent
        
        Args:
            config: Agent配置
            operations: 操作配置列表
            conditions: 执行条件列表
            **kwargs: 其他参数传递给BaseAgent
        """
        super().__init__(config=config, **kwargs)
        
        self.operations = operations or []
        self.conditions = conditions or []
        
        logger.debug(f"PostProcessorAgent '{self.agent_id}' 初始化完成")
    
    def execute(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        执行后处理操作
        
        Args:
            state: 工作流状态字典
            
        Returns:
            更新后的状态字典，包含执行状态
        """
        logger.info(f"开始执行后处理Agent: {self.agent_id}")
        
        try:
            # 1. 检查执行条件
            if not self._check_conditions(state):
                logger.info(f"后处理Agent {self.agent_id} 条件不满足，跳过执行")
                return self._create_skip_result(state)
            
            # 2. 执行后处理操作
            results = []
            for operation in self.operations:
                result = self._execute_operation(operation, state)
                results.append(result)
            
            # 3. 返回执行状态
            return self._create_success_result(state, results)
            
        except Exception as e:
            logger.error(f"后处理Agent {self.agent_id} 执行失败: {e}", exc_info=True)
            return self._create_error_result(state, str(e))
    
    def _check_conditions(self, state: Dict[str, Any]) -> bool:
        """
        检查执行条件
        
        Args:
            state: 工作流状态
            
        Returns:
            是否满足所有条件
        """
        if not self.conditions:
            return True
        
        for condition in self.conditions:
            if not self._evaluate_condition(condition, state):
                return False
        
        return True
    
    def _evaluate_condition(self, condition: ConditionConfig, state: Dict[str, Any]) -> bool:
        """
        评估单个条件

        Args:
            condition: 条件配置，格式：
                {
                    "field": "recommendation",
                    "operator": "in",
                    "value": ["买入", "卖出"]
                }
            state: 工作流状态

        Returns:
            条件是否满足
        """
        field = condition.get("field")
        operator = condition.get("operator")
        expected_value = condition.get("value")

        if not field or not operator:
            logger.warning(f"条件配置不完整: {condition}")
            return False

        # 获取实际值（支持嵌套路径）
        actual_value = self._get_nested_value(state, field)

        # 执行比较
        try:
            if operator == "equals":
                return actual_value == expected_value
            elif operator == "not_equals":
                return actual_value != expected_value
            elif operator == "in":
                return actual_value in expected_value
            elif operator == "not_in":
                return actual_value not in expected_value
            elif operator == "greater_than":
                return float(actual_value) > float(expected_value)
            elif operator == "less_than":
                return float(actual_value) < float(expected_value)
            elif operator == "greater_or_equal":
                return float(actual_value) >= float(expected_value)
            elif operator == "less_or_equal":
                return float(actual_value) <= float(expected_value)
            elif operator == "contains":
                return expected_value in str(actual_value)
            elif operator == "not_contains":
                return expected_value not in str(actual_value)
            elif operator == "is_true":
                return bool(actual_value)
            elif operator == "is_false":
                return not bool(actual_value)
            elif operator == "exists":
                return actual_value is not None
            elif operator == "not_exists":
                return actual_value is None
            else:
                logger.warning(f"未知的操作符: {operator}")
                return False
        except Exception as e:
            logger.error(f"条件评估失败: {e}")
            return False
    
    @abstractmethod
    def _execute_operation(self, operation: OperationConfig, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        执行单个操作（子类实现）

        Args:
            operation: 操作配置
            state: 工作流状态

        Returns:
            操作执行结果
        """
        pass

    def _create_success_result(self, state: Dict[str, Any], results: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        创建成功结果

        Args:
            state: 原始状态
            results: 操作结果列表

        Returns:
            更新后的状态
        """
        output_key = f"{self.agent_id}_status"
        state[output_key] = {
            "success": True,
            "agent_id": self.agent_id,
            "processor_type": self.processor_type.value if self.processor_type else None,
            "operations_count": len(results),
            "results": results,
            "error": None
        }
        return state

    def _create_skip_result(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        创建跳过结果

        Args:
            state: 原始状态

        Returns:
            更新后的状态
        """
        output_key = f"{self.agent_id}_status"
        state[output_key] = {
            "success": True,
            "agent_id": self.agent_id,
            "processor_type": self.processor_type.value if self.processor_type else None,
            "skipped": True,
            "reason": "Conditions not met",
            "error": None
        }
        return state

    def _create_error_result(self, state: Dict[str, Any], error: str) -> Dict[str, Any]:
        """
        创建错误结果

        Args:
            state: 原始状态
            error: 错误信息

        Returns:
            更新后的状态
        """
        output_key = f"{self.agent_id}_status"
        state[output_key] = {
            "success": False,
            "agent_id": self.agent_id,
            "processor_type": self.processor_type.value if self.processor_type else None,
            "error": error
        }
        return state

    @property
    def agent_id(self) -> str:
        """获取Agent ID"""
        if self.metadata:
            return self.metadata.agent_id
        return self.__class__.__name__.lower()

    def _get_nested_value(self, data: Dict[str, Any], path: str, default: Any = None) -> Any:
        """
        获取嵌套字典的值

        Args:
            data: 数据字典
            path: 路径，如 "user.email_settings.enabled"
            default: 默认值

        Returns:
            值或默认值
        """
        keys = path.split('.')
        value = data

        for key in keys:
            if isinstance(value, dict) and key in value:
                value = value[key]
            else:
                return default

        return value

