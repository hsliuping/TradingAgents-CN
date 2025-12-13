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
        use_dynamic_state: bool = False,  # 🆕 是否使用动态状态生成
    ):
        """
        初始化工作流引擎

        Args:
            legacy_config: 遗留智能体配置（用于创建 LLM 和 Toolkit）
            task_id: 任务 ID（用于进度跟踪）
            use_dynamic_state: 是否使用动态状态生成（默认 False 保持向后兼容）
        """
        self._definition: Optional[WorkflowDefinition] = None
        self._compiled_graph = None
        self._legacy_config = legacy_config
        self._task_id = task_id or str(uuid.uuid4())
        self._builder = WorkflowBuilder(legacy_config=legacy_config)
        self._validator = WorkflowValidator()
        self._current_execution: Optional[WorkflowExecution] = None
        self._progress_callback: Optional[Callable] = None

        # 🆕 动态状态生成
        self._use_dynamic_state = use_dynamic_state
        self._state_schema = None
        if use_dynamic_state:
            from ..state.builder import StateSchemaBuilder
            from ..state.registry import StateRegistry
            self._state_builder = StateSchemaBuilder()
            self._state_registry = StateRegistry()
            logger.info("[WorkflowEngine] 启用动态状态生成")
    
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

        # 🆕 如果启用动态状态，生成状态 Schema
        state_schema = None
        if self._use_dynamic_state:
            agent_ids = self._extract_agent_ids(self._definition)
            if agent_ids:
                logger.info(f"[WorkflowEngine] 为工作流 {self._definition.id} 生成动态状态，Agent 列表: {agent_ids}")

                # 使用 StateRegistry 获取或构建状态类
                schema = self._state_registry.get_or_build(
                    workflow_id=self._definition.id,
                    agent_ids=agent_ids
                )
                state_schema = self._state_registry.get_state_class(self._definition.id)

                logger.info(f"[WorkflowEngine] 状态类生成成功: {state_schema.__name__ if state_schema else 'None'}")
                logger.info(f"[WorkflowEngine] 状态字段: {list(schema.fields.keys())}")

        # 构建图
        self._compiled_graph = self._builder.build(self._definition, state_schema=state_schema)
        return self

    def _extract_agent_ids(self, definition: WorkflowDefinition) -> list:
        """从工作流定义中提取 Agent ID 列表"""
        agent_ids = []
        for node in definition.nodes:
            if node.agent_id and node.agent_id not in agent_ids:
                agent_ids.append(node.agent_id)
        return agent_ids
    
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
        同步执行工作流（使用 stream 模式以获取节点级进度更新）

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

            logger.info(f"开始执行工作流: {self._definition.id if self._definition else 'unknown'}")

            # 使用 stream 模式以获取节点级别的进度更新
            # stream_mode 应该作为关键字参数传递，而不是放在 config 字典中
            final_state = inputs.copy() if inputs else {}

            for chunk in self._compiled_graph.stream(inputs, config=config, stream_mode="updates"):
                # chunk 格式: {node_name: state_update}
                if isinstance(chunk, dict):
                    for node_name, node_update in chunk.items():
                        if node_name.startswith('__'):
                            continue  # 跳过特殊节点

                        # 获取进度信息
                        progress_info = self._get_node_progress_info(node_name)
                        progress, message, step_name = progress_info

                        if progress is not None:
                            self._report_progress(progress, message, step_name)

                        # 累积状态更新
                        if isinstance(node_update, dict):
                            try:
                                # 🔍 调试：打印节点更新的字段
                                update_keys = list(node_update.keys())
                                logger.info(f"[执行引擎] 📝 节点 {node_name} 返回字段: {update_keys}")
                                # 检查是否有 index_report 或 sector_report
                                if "index_report" in node_update:
                                    logger.info(f"[执行引擎] ✅ 检测到 index_report ({len(str(node_update['index_report']))} 字符)")
                                if "sector_report" in node_update:
                                    logger.info(f"[执行引擎] ✅ 检测到 sector_report ({len(str(node_update['sector_report']))} 字符)")
                                final_state.update(node_update)
                            except Exception:
                                final_state[node_name] = node_update
                        else:
                            final_state[node_name] = node_update

            # 使用累积的最终状态
            result = final_state

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
    
    def _get_node_progress_info(self, node_name: str) -> tuple:
        """获取节点的进度信息（百分比和友好消息）

        Args:
            node_name: 节点名称（从 LangGraph stream 返回）

        Returns:
            (progress_percentage, friendly_message, step_name)
        """
        # 节点名称到友好消息的映射
        # 支持两种格式：旧格式（"Market Analyst"）和新格式（"market_analyst"）
        node_mapping = {
            # 分析师节点（新格式 - 工作流定义中的 id）
            "market_analyst": (15, "📈 市场分析师正在分析技术指标和市场趋势...", "market_analyst"),
            "fundamentals_analyst": (25, "💰 基本面分析师正在分析财务数据...", "fundamentals_analyst"),
            "news_analyst": (35, "📰 新闻分析师正在分析相关新闻和事件...", "news_analyst"),
            "social_analyst": (40, "💬 社媒分析师正在分析社交媒体情绪...", "social_analyst"),
            "sentiment_analyst": (40, "💭 情绪分析师正在分析市场情绪...", "sentiment_analyst"),

            # 研究团队
            "bull_researcher": (50, "🐂 多头研究员正在构建看多观点...", "bull_researcher"),
            "bear_researcher": (55, "🐻 空头研究员正在构建看空观点...", "bear_researcher"),
            "research_manager": (60, "🔬 研究经理正在综合研究观点...", "research_manager"),

            # 交易团队
            "trader": (70, "💼 交易员正在制定交易计划...", "trader"),

            # 风险管理团队
            "risky_analyst": (75, "⚡ 激进分析师正在评估高风险机会...", "risky_analyst"),
            "safe_analyst": (80, "🛡️ 保守分析师正在评估风险因素...", "safe_analyst"),
            "neutral_analyst": (82, "⚖️ 中性分析师正在平衡风险收益...", "neutral_analyst"),
            "risk_manager": (90, "👔 风险管理者正在做最终决策...", "risk_manager"),
            "risk_judge": (90, "👔 风险管理者正在做最终决策...", "risk_judge"),
            "portfolio_manager": (90, "👔 投资组合经理正在做最终决策...", "portfolio_manager"),

            # 工作流控制节点
            "start": (5, "🚀 开始分析...", "start"),
            "parallel_analysts": (10, "📊 启动分析师团队...", "parallel_analysts"),
            "merge_analysts": (42, "📋 汇总分析师报告...", "merge_analysts"),
            "debate": (45, "💬 研究团队开始讨论...", "debate"),
            "risk_debate": (72, "⚖️ 风险评估团队开始讨论...", "risk_debate"),
            "end": (95, "✅ 分析即将完成...", "end"),

            # 旧格式（向后兼容）
            "Market Analyst": (15, "📈 市场分析师正在分析技术指标和市场趋势...", "market_analyst"),
            "Fundamentals Analyst": (25, "💰 基本面分析师正在分析财务数据...", "fundamentals_analyst"),
            "News Analyst": (35, "📰 新闻分析师正在分析相关新闻和事件...", "news_analyst"),
            "Social Analyst": (40, "💬 社媒分析师正在分析社交媒体情绪...", "social_analyst"),
            "Bull Researcher": (50, "🐂 多头研究员正在构建看多观点...", "bull_researcher"),
            "Bear Researcher": (55, "🐻 空头研究员正在构建看空观点...", "bear_researcher"),
            "Research Manager": (60, "🔬 研究经理正在综合研究观点...", "research_manager"),
            "Trader": (70, "💼 交易员正在制定交易计划...", "trader"),
            "Risky Analyst": (75, "⚡ 激进分析师正在评估高风险机会...", "risky_analyst"),
            "Safe Analyst": (80, "🛡️ 保守分析师正在评估风险因素...", "safe_analyst"),
            "Neutral Analyst": (82, "⚖️ 中性分析师正在平衡风险收益...", "neutral_analyst"),
            "Risk Judge": (90, "👔 风险管理者正在做最终决策...", "risk_judge"),
            "Portfolio Manager": (90, "👔 投资组合经理正在做最终决策...", "portfolio_manager"),
        }

        # 忽略的节点（工具节点、消息清理节点等）
        ignored_patterns = ["tools_", "Msg Clear", "msg_clear_", "__start__", "__end__"]

        for pattern in ignored_patterns:
            if pattern in node_name:
                return (None, None, None)  # 跳过这些节点

        if node_name in node_mapping:
            return node_mapping[node_name]

        # 未知节点，使用默认进度
        logger.debug(f"[进度] 未知节点: {node_name}")
        return (50, f"🔍 正在执行: {node_name}", node_name.lower().replace(" ", "_"))

    async def execute_async(
        self,
        inputs: Dict[str, Any],
        config: Optional[Dict[str, Any]] = None,
        progress_callback: Optional[Callable] = None,
    ) -> Dict[str, Any]:
        """
        异步执行工作流（使用 stream 模式以获取节点级进度更新）

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

            # 使用 astream 模式以获取节点级别的进度更新
            # stream_mode 应该作为关键字参数传递，而不是放在 config 字典中
            final_state = inputs.copy() if inputs else {}

            async for chunk in self._compiled_graph.astream(inputs, config=config, stream_mode="updates"):
                # chunk 格式: {node_name: state_update}
                if isinstance(chunk, dict):
                    for node_name, node_update in chunk.items():
                        if node_name.startswith('__'):
                            continue  # 跳过特殊节点

                        # 获取进度信息
                        progress_info = self._get_node_progress_info(node_name)
                        progress, message, step_name = progress_info

                        if progress is not None:
                            self._report_progress(progress, message, step_name)

                        # 累积状态更新
                        if isinstance(node_update, dict):
                            try:
                                final_state.update(node_update)
                            except Exception:
                                final_state[node_name] = node_update
                        else:
                            final_state[node_name] = node_update

            # 使用累积的最终状态
            result = final_state

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

