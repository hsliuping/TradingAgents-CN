"""
工作流执行引擎

负责工作流的加载、验证和执行
"""

import logging
import uuid
from datetime import datetime
from typing import Any, AsyncIterator, Callable, Dict, Optional, Protocol

from .models import (
    WorkflowDefinition,
    WorkflowExecution,
    WorkflowExecutionState,
)
from .builder import WorkflowBuilder
from .validator import WorkflowValidator, ValidationResult

logger = logging.getLogger(__name__)


class ProgressCallback(Protocol):
    """进度回调协议"""
    def __call__(
        self,
        progress: float,
        message: str,
        step_name: Optional[str] = None,
        **kwargs
    ) -> None:
        """
        进度回调

        Args:
            progress: 进度百分比 (0-100)
            message: 进度消息
            step_name: 当前步骤名称
            **kwargs: 额外参数
        """
        ...


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

        # 带进度回调执行
        def on_progress(progress, message, **kwargs):
            print(f"{progress}% - {message}")
        output = engine.execute(inputs, progress_callback=on_progress)
    """

    def __init__(
        self,
        legacy_config: Optional[Dict[str, Any]] = None,
        task_id: Optional[str] = None,
    ):
        """
        初始化工作流引擎

        Args:
            legacy_config: 遗留智能体配置（用于创建 LLM 和 Toolkit）
            task_id: 任务 ID（用于进度跟踪）
        """
        self._definition: Optional[WorkflowDefinition] = None
        self._compiled_graph = None
        self._legacy_config = legacy_config
        self._task_id = task_id or str(uuid.uuid4())
        self._builder = WorkflowBuilder(legacy_config=legacy_config)
        self._validator = WorkflowValidator()
        self._current_execution: Optional[WorkflowExecution] = None
        self._progress_callback: Optional[Callable] = None
    
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
    
    def set_progress_callback(self, callback: Optional[Callable]) -> "WorkflowEngine":
        """设置进度回调"""
        self._progress_callback = callback
        return self

    def _report_progress(
        self,
        progress: float,
        message: str,
        step_name: Optional[str] = None,
        **kwargs
    ) -> None:
        """报告进度"""
        if self._progress_callback:
            try:
                self._progress_callback(
                    progress=progress,
                    message=message,
                    step_name=step_name,
                    task_id=self._task_id,
                    **kwargs
                )
            except Exception as e:
                logger.warning(f"进度回调失败: {e}")

    def execute(
        self,
        inputs: Dict[str, Any],
        config: Optional[Dict[str, Any]] = None,
        progress_callback: Optional[Callable] = None,
    ) -> Dict[str, Any]:
        """
        同步执行工作流

        Args:
            inputs: 输入参数
            config: 执行配置
            progress_callback: 进度回调函数

        Returns:
            执行结果
        """
        if progress_callback:
            self.set_progress_callback(progress_callback)

        if self._compiled_graph is None:
            self._report_progress(5, "编译工作流...", "compile")
            self.compile()

        # 创建执行记录
        execution = self._create_execution(inputs)
        self._report_progress(10, "开始执行工作流", "start")

        try:
            execution.state = WorkflowExecutionState.RUNNING
            execution.started_at = datetime.now().isoformat()

            # 执行图
            logger.info(f"开始执行工作流: {self._definition.id if self._definition else 'unknown'}")
            result = self._compiled_graph.invoke(inputs, config)

            execution.state = WorkflowExecutionState.COMPLETED
            execution.outputs = result
            execution.completed_at = datetime.now().isoformat()

            self._report_progress(100, "工作流执行完成", "completed")
            return result

        except Exception as e:
            execution.state = WorkflowExecutionState.FAILED
            execution.error = str(e)
            execution.completed_at = datetime.now().isoformat()
            self._report_progress(
                progress=execution.outputs.get("progress", 0) if execution.outputs else 0,
                message=f"执行失败: {str(e)}",
                step_name="error",
                error=str(e)
            )
            raise

        finally:
            self._current_execution = execution
    
    async def execute_async(
        self,
        inputs: Dict[str, Any],
        config: Optional[Dict[str, Any]] = None,
        progress_callback: Optional[Callable] = None,
    ) -> Dict[str, Any]:
        """
        异步执行工作流

        Args:
            inputs: 输入参数
            config: 执行配置
            progress_callback: 进度回调函数

        Returns:
            执行结果
        """
        if progress_callback:
            self.set_progress_callback(progress_callback)

        if self._compiled_graph is None:
            self._report_progress(5, "编译工作流...", "compile")
            self.compile()

        execution = self._create_execution(inputs)
        self._report_progress(10, "开始执行工作流", "start")

        try:
            execution.state = WorkflowExecutionState.RUNNING
            execution.started_at = datetime.now().isoformat()

            logger.info(f"开始异步执行工作流: {self._definition.id if self._definition else 'unknown'}")
            result = await self._compiled_graph.ainvoke(inputs, config)

            execution.state = WorkflowExecutionState.COMPLETED
            execution.outputs = result
            execution.completed_at = datetime.now().isoformat()

            self._report_progress(100, "工作流执行完成", "completed")
            return result

        except Exception as e:
            execution.state = WorkflowExecutionState.FAILED
            execution.error = str(e)
            execution.completed_at = datetime.now().isoformat()
            self._report_progress(
                progress=execution.outputs.get("progress", 0) if execution.outputs else 0,
                message=f"执行失败: {str(e)}",
                step_name="error",
                error=str(e)
            )
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
            id=self._task_id,
            workflow_id=self._definition.id if self._definition else "",
            inputs=inputs,
        )

    @property
    def task_id(self) -> str:
        """任务 ID"""
        return self._task_id

    @task_id.setter
    def task_id(self, value: str) -> None:
        """设置任务 ID"""
        self._task_id = value

    @property
    def definition(self) -> Optional[WorkflowDefinition]:
        """当前加载的工作流定义"""
        return self._definition

    @property
    def last_execution(self) -> Optional[WorkflowExecution]:
        """最近一次执行记录"""
        return self._current_execution

