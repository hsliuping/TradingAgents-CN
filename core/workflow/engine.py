"""
工作流执行引擎

负责工作流的加载、验证和执行
"""

import uuid
from datetime import datetime
from typing import Any, AsyncIterator, Dict, Optional

from .models import (
    WorkflowDefinition,
    WorkflowExecution,
    WorkflowExecutionState,
)
from .builder import WorkflowBuilder
from .validator import WorkflowValidator, ValidationResult


class WorkflowEngine:
    """
    工作流执行引擎

    用法:
        engine = WorkflowEngine()

        # 加载工作流
        engine.load(workflow_definition)

        # 验证
        result = engine.validate()

        # 执行
        output = engine.execute({"ticker": "AAPL", "trade_date": "2024-01-15"})

        # 或流式执行
        async for event in engine.execute_stream(inputs):
            print(event)
    """

    def __init__(self, legacy_config: Optional[Dict[str, Any]] = None):
        """
        初始化工作流引擎

        Args:
            legacy_config: 遗留智能体配置（用于创建 LLM 和 Toolkit）
        """
        self._definition: Optional[WorkflowDefinition] = None
        self._compiled_graph = None
        self._legacy_config = legacy_config
        self._builder = WorkflowBuilder(legacy_config=legacy_config)
        self._validator = WorkflowValidator()
        self._current_execution: Optional[WorkflowExecution] = None
    
    def load(self, definition: WorkflowDefinition) -> "WorkflowEngine":
        """加载工作流定义"""
        self._definition = definition
        self._compiled_graph = None  # 清除已编译的图
        return self
    
    def load_from_dict(self, data: Dict[str, Any]) -> "WorkflowEngine":
        """从字典加载工作流"""
        definition = WorkflowDefinition.from_dict(data)
        return self.load(definition)
    
    def load_from_json(self, json_str: str) -> "WorkflowEngine":
        """从 JSON 字符串加载工作流"""
        definition = WorkflowDefinition.from_json(json_str)
        return self.load(definition)
    
    def validate(self) -> ValidationResult:
        """验证工作流"""
        if self._definition is None:
            result = ValidationResult()
            result.add_error("NO_DEFINITION", "未加载工作流定义")
            return result
        
        return self._validator.validate(self._definition)
    
    def compile(self) -> "WorkflowEngine":
        """编译工作流"""
        if self._definition is None:
            raise ValueError("未加载工作流定义")
        
        # 先验证
        result = self.validate()
        if not result.is_valid:
            errors = "\n".join(str(e) for e in result.errors)
            raise ValueError(f"工作流验证失败:\n{errors}")
        
        # 构建图
        self._compiled_graph = self._builder.build(self._definition)
        return self
    
    def execute(
        self,
        inputs: Dict[str, Any],
        config: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        同步执行工作流

        Args:
            inputs: 输入参数
            config: 执行配置

        Returns:
            执行结果
        """
        if self._compiled_graph is None:
            self.compile()

        # 创建执行记录
        execution = self._create_execution(inputs)

        try:
            execution.state = WorkflowExecutionState.RUNNING
            execution.started_at = datetime.now().isoformat()

            # 执行图
            result = self._compiled_graph.invoke(inputs, config)
            
            execution.state = WorkflowExecutionState.COMPLETED
            execution.outputs = result
            execution.completed_at = datetime.now().isoformat()
            
            return result
            
        except Exception as e:
            execution.state = WorkflowExecutionState.FAILED
            execution.error = str(e)
            execution.completed_at = datetime.now().isoformat()
            raise
        
        finally:
            self._current_execution = execution
    
    async def execute_async(
        self,
        inputs: Dict[str, Any],
        config: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """异步执行工作流"""
        if self._compiled_graph is None:
            self.compile()

        execution = self._create_execution(inputs)

        try:
            execution.state = WorkflowExecutionState.RUNNING
            execution.started_at = datetime.now().isoformat()

            result = await self._compiled_graph.ainvoke(inputs, config)
            
            execution.state = WorkflowExecutionState.COMPLETED
            execution.outputs = result
            execution.completed_at = datetime.now().isoformat()
            
            return result
            
        except Exception as e:
            execution.state = WorkflowExecutionState.FAILED
            execution.error = str(e)
            execution.completed_at = datetime.now().isoformat()
            raise
        
        finally:
            self._current_execution = execution
    
    async def execute_stream(
        self,
        inputs: Dict[str, Any],
        config: Optional[Dict[str, Any]] = None
    ) -> AsyncIterator[Dict[str, Any]]:
        """
        流式执行工作流
        
        Yields:
            执行事件 {"type": "node_start|node_end|output", ...}
        """
        if self._compiled_graph is None:
            self.compile()
        
        execution = self._create_execution(inputs)
        execution.state = WorkflowExecutionState.RUNNING
        execution.started_at = datetime.now().isoformat()
        
        try:
            async for event in self._compiled_graph.astream(inputs, config):
                # 包装事件
                yield {
                    "type": "node_output",
                    "execution_id": execution.id,
                    "data": event,
                    "timestamp": datetime.now().isoformat(),
                }
            
            execution.state = WorkflowExecutionState.COMPLETED
            execution.completed_at = datetime.now().isoformat()
            
            yield {
                "type": "completed",
                "execution_id": execution.id,
                "timestamp": datetime.now().isoformat(),
            }
            
        except Exception as e:
            execution.state = WorkflowExecutionState.FAILED
            execution.error = str(e)
            
            yield {
                "type": "error",
                "execution_id": execution.id,
                "error": str(e),
                "timestamp": datetime.now().isoformat(),
            }
        
        finally:
            self._current_execution = execution
    
    def _create_execution(self, inputs: Dict[str, Any]) -> WorkflowExecution:
        """创建执行记录"""
        return WorkflowExecution(
            id=str(uuid.uuid4()),
            workflow_id=self._definition.id if self._definition else "",
            inputs=inputs,
        )
    
    @property
    def definition(self) -> Optional[WorkflowDefinition]:
        """当前加载的工作流定义"""
        return self._definition
    
    @property
    def last_execution(self) -> Optional[WorkflowExecution]:
        """最近一次执行记录"""
        return self._current_execution

