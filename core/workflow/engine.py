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
        use_dynamic_state: bool = False,
        llm: Optional[Any] = None
    ):
        """
        初始化工作流引擎

        Args:
            legacy_config: 遗留智能体配置（用于创建 LLM 和 Toolkit）
            task_id: 任务 ID（用于进度跟踪）
            use_dynamic_state: 是否使用动态状态生成（默认 False 保持向后兼容）
            llm: 可选的 LLM 实例（优先于 legacy_config）
        """
        self._definition: Optional[WorkflowDefinition] = None
        self._compiled_graph = None
        self._legacy_config = legacy_config
        self._task_id = task_id or str(uuid.uuid4())
        self._builder = WorkflowBuilder(legacy_config=legacy_config, llm_override=llm)
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

            def _extract_text(v):
                if isinstance(v, str):
                    return v
                if isinstance(v, dict):
                    for k in ("content", "markdown", "text", "message", "report"):
                        x = v.get(k)
                        if isinstance(x, str) and x.strip():
                            return x
                return "" if v is None else str(v)

            fields = [
                "market_report",
                "sentiment_report",
                "news_report",
                "fundamentals_report",
                "index_report",
                "sector_report",
                "bull_report",
                "bear_report",
                "investment_plan",
                "trader_investment_plan",
                "final_trade_decision",
            ]
            structured = {}
            for f in fields:
                if f in result:
                    text = _extract_text(result.get(f))
                    success = bool(isinstance(text, str) and text.strip())
                    d = {"content": text, "success": success}
                    if f == "bull_report":
                        d["stance"] = "bull"
                    if f == "bear_report":
                        d["stance"] = "bear"
                    structured[f] = d
            result["structured_reports"] = structured

            # 🔥 修改：优先使用 RiskManagerV2 生成的结构化 final_trade_decision
            # 只有当 final_trade_decision 不存在或不是字典时，才进行拼接
            existing_ftd = result.get("final_trade_decision")
            # 🔥 修复：检查 action 或 analysis_view 字段（兼容新旧字段名）
            has_action = existing_ftd and isinstance(existing_ftd, dict) and (
                existing_ftd.get("action") or existing_ftd.get("analysis_view")
            )
            if has_action:
                # ✅ RiskManagerV2 已经生成了结构化的 final_trade_decision，保留它
                action = existing_ftd.get("action") or existing_ftd.get("analysis_view")
                logger.info(f"✅ [WorkflowEngine] 使用 RiskManagerV2 生成的 final_trade_decision: action/analysis_view={action}, confidence={existing_ftd.get('confidence')}")
            else:
                # ⚠️ 没有结构化的 final_trade_decision，使用旧的拼接逻辑
                final_trade_decision = self._generate_final_trade_decision(result)
                if final_trade_decision:
                    result["final_trade_decision"] = final_trade_decision
                    logger.info(f"✅ [WorkflowEngine] 生成拼接的 final_trade_decision，长度: {len(final_trade_decision)}")
                    # 🔥 打印完整内容（不截断）
                    logger.info(f"🔍 [WorkflowEngine] final_trade_decision 完整内容:\n{final_trade_decision}")

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
        # 支持三种格式：旧格式（"Market Analyst"）、v1格式（"market_analyst"）、v2格式（"market_analyst_v2"）
        # 格式：(progress_percentage, friendly_message, step_name)
        # - progress_percentage: 进度百分比
        # - friendly_message: 详细描述（显示在 message 字段）
        # - step_name: 简短名称（显示在 current_step_name 字段）
        node_mapping = {
            # === v2.0 分析师节点 ===
            "market_analyst_v2": (15, "📈 市场分析师正在分析技术指标和市场趋势...", "市场分析师"),
            "fundamentals_analyst_v2": (25, "💰 基本面分析师正在分析财务数据...", "基本面分析师"),
            "news_analyst_v2": (35, "📰 新闻分析师正在分析相关新闻和事件...", "新闻分析师"),
            "social_analyst_v2": (40, "💬 社媒分析师正在分析社交媒体情绪...", "社媒分析师"),
            "sector_analyst_v2": (20, "📊 板块分析师正在分析行业趋势...", "板块分析师"),
            "index_analyst_v2": (10, "📈 大盘分析师正在分析市场环境...", "大盘分析师"),

            # === v2.0 研究团队 ===
            "bull_researcher_v2": (50, "🐂 看多研究员正在构建看多观点...", "看多研究员"),
            "bear_researcher_v2": (55, "🐻 看空研究员正在构建看空观点...", "看空研究员"),
            "research_manager_v2": (60, "🔬 研究经理正在综合研究观点...", "研究经理"),

            # === v2.0 交易团队 ===
            "trader_v2": (70, "💼 交易员正在制定交易计划...", "交易员"),

            # === v2.0 风险管理团队 ===
            "risky_analyst_v2": (75, "⚡ 激进分析师正在评估高风险机会...", "激进分析师"),
            "safe_analyst_v2": (80, "🛡️ 保守分析师正在评估风险因素...", "保守分析师"),
            "neutral_analyst_v2": (82, "⚖️ 中性分析师正在平衡风险收益...", "中性分析师"),
            "risk_manager_v2": (90, "👔 风险管理者正在做最终决策...", "风险管理者"),

            # === v1.0 分析师节点（向后兼容）===
            "market_analyst": (15, "📈 市场分析师正在分析技术指标和市场趋势...", "市场分析师"),
            "fundamentals_analyst": (25, "💰 基本面分析师正在分析财务数据...", "基本面分析师"),
            "news_analyst": (35, "📰 新闻分析师正在分析相关新闻和事件...", "新闻分析师"),
            "social_analyst": (40, "💬 社媒分析师正在分析社交媒体情绪...", "社媒分析师"),
            "sentiment_analyst": (40, "💭 情绪分析师正在分析市场情绪...", "情绪分析师"),

            # === v1.0 研究团队 ===
            "bull_researcher": (50, "🐂 多头研究员正在构建看多观点...", "多头研究员"),
            "bear_researcher": (55, "🐻 空头研究员正在构建看空观点...", "空头研究员"),
            "research_manager": (60, "🔬 研究经理正在综合研究观点...", "研究经理"),

            # === v1.0 交易团队 ===
            "trader": (70, "💼 交易员正在制定交易计划...", "交易员"),

            # === v1.0 风险管理团队 ===
            "risky_analyst": (75, "⚡ 激进分析师正在评估高风险机会...", "激进分析师"),
            "safe_analyst": (80, "🛡️ 保守分析师正在评估风险因素...", "保守分析师"),
            "neutral_analyst": (82, "⚖️ 中性分析师正在平衡风险收益...", "中性分析师"),
            "risk_manager": (90, "👔 风险管理者正在做最终决策...", "风险管理者"),
            "risk_judge": (90, "👔 风险管理者正在做最终决策...", "风险管理者"),
            "portfolio_manager": (90, "👔 投资组合经理正在做最终决策...", "投资组合经理"),

            # === 工作流控制节点 ===
            "start": (5, "🚀 开始分析...", "开始"),
            "parallel_analysts": (10, "📊 启动分析师团队...", "启动分析师"),
            "merge_analysts": (42, "📋 汇总分析师报告...", "汇总报告"),
            "debate": (45, "💬 研究团队开始讨论...", "研究讨论"),
            "risk_debate": (72, "⚖️ 风险评估团队开始讨论...", "风险讨论"),
            "end": (95, "✅ 分析即将完成...", "完成"),

            # === 旧格式（向后兼容）===
            "Market Analyst": (15, "📈 市场分析师正在分析技术指标和市场趋势...", "市场分析师"),
            "Fundamentals Analyst": (25, "💰 基本面分析师正在分析财务数据...", "基本面分析师"),
            "News Analyst": (35, "📰 新闻分析师正在分析相关新闻和事件...", "新闻分析师"),
            "Social Analyst": (40, "💬 社媒分析师正在分析社交媒体情绪...", "社媒分析师"),
            "Bull Researcher": (50, "🐂 多头研究员正在构建看多观点...", "多头研究员"),
            "Bear Researcher": (55, "🐻 空头研究员正在构建看空观点...", "空头研究员"),
            "Research Manager": (60, "🔬 研究经理正在综合研究观点...", "研究经理"),
            "Trader": (70, "💼 交易员正在制定交易计划...", "交易员"),
            "Risky Analyst": (75, "⚡ 激进分析师正在评估高风险机会...", "激进分析师"),
            "Safe Analyst": (80, "🛡️ 保守分析师正在评估风险因素...", "保守分析师"),
            "Neutral Analyst": (82, "⚖️ 中性分析师正在平衡风险收益...", "中性分析师"),
            "Risk Judge": (90, "👔 风险管理者正在做最终决策...", "风险管理者"),
            "Portfolio Manager": (90, "👔 投资组合经理正在做最终决策...", "投资组合经理"),
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
        # 尝试生成一个友好的中文名称
        friendly_name = node_name.replace("_v2", "").replace("_", " ").title()
        return (50, f"🔍 正在执行: {friendly_name}", friendly_name)

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

                        # 🔥 关键：在每个节点执行后检查取消标记
                        # 通过调用 progress_callback 来触发取消检查
                        # 获取进度信息
                        progress_info = self._get_node_progress_info(node_name)
                        progress, message, step_name = progress_info

                        if progress is not None:
                            # 🔥 关键：调用 progress_callback 会触发取消检查
                            # 如果任务被取消，wrapped_progress_callback 会抛出 TaskCancelledException
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

    def _generate_final_trade_decision(self, state: Dict[str, Any]) -> str:
        """
        生成最终分析结果

        综合以下内容：
        1. investment_plan (研究经理的市场分析)
        2. trader_investment_plan (交易员的交易分析计划)
        3. risk_assessment (风险经理的风险评估)

        Args:
            state: 工作流执行状态

        Returns:
            最终分析结果文本（Markdown 格式）
        """
        # 🔍 调试：打印 state 中的关键字段
        logger.info(f"🔍 [WorkflowEngine] state 中的字段: {list(state.keys())}")
        logger.info(f"🔍 [WorkflowEngine] investment_plan 存在: {'investment_plan' in state}")
        logger.info(f"🔍 [WorkflowEngine] trader_investment_plan 存在: {'trader_investment_plan' in state}")
        logger.info(f"🔍 [WorkflowEngine] risk_assessment 存在: {'risk_assessment' in state}")

        # 提取各个报告
        investment_plan = self._extract_text_from_state(state, "investment_plan")
        trader_plan = self._extract_text_from_state(state, "trader_investment_plan")
        risk_assessment = self._extract_text_from_state(state, "risk_assessment")

        # 🔍 调试：打印提取结果
        logger.info(f"🔍 [WorkflowEngine] investment_plan 长度: {len(investment_plan)}")
        logger.info(f"🔍 [WorkflowEngine] trader_plan 长度: {len(trader_plan)}")
        logger.info(f"🔍 [WorkflowEngine] risk_assessment 长度: {len(risk_assessment)}")

        # 如果三个都为空，返回空字符串
        if not any([investment_plan, trader_plan, risk_assessment]):
            logger.warning("⚠️ [WorkflowEngine] 无法生成 final_trade_decision：所有输入报告均为空")
            return ""

        # 🔥 新方案：简单拼接三个报告（保持原有行为）
        # 注意：这里只是拼接，不进行综合分析
        # 真正的综合决策由 TaskAnalysisService 从 investment_plan 中提取
        sections = []

        if investment_plan:
            sections.append(f"## 📋 市场分析\n\n{investment_plan}")

        if trader_plan:
            sections.append(f"## 💼 交易分析计划\n\n{trader_plan}")

        if risk_assessment:
            sections.append(f"## ⚠️ 风险评估\n\n{risk_assessment}")

        final_decision = "\n\n".join(sections)
        logger.info(f"✅ [WorkflowEngine] 生成 final_trade_decision，包含 {len(sections)} 个部分")
        logger.info(f"✅ [WorkflowEngine] 生成 final_trade_decision，长度: {len(final_decision)}")
        logger.info(f"🔍 [WorkflowEngine] final_trade_decision 内容前500字符:\n{final_decision[:500]}")

        return final_decision

    def _extract_text_from_state(self, state: Dict[str, Any], field: str) -> str:
        """
        从 state 中提取文本内容

        Args:
            state: 工作流执行状态
            field: 字段名

        Returns:
            提取的文本内容
        """
        value = state.get(field)

        # 🔍 调试日志
        logger.info(f"🔍 [_extract_text_from_state] 提取字段: {field}")
        logger.info(f"🔍 [_extract_text_from_state] 值类型: {type(value)}")

        if value is None:
            logger.info(f"🔍 [_extract_text_from_state] {field} 为 None，返回空字符串")
            return ""

        if isinstance(value, str):
            logger.info(f"🔍 [_extract_text_from_state] {field} 是字符串，长度: {len(value)}")
            logger.info(f"🔍 [_extract_text_from_state] {field} 内容前200字符: {value[:200]}")
            return value.strip()

        if isinstance(value, dict):
            logger.info(f"🔍 [_extract_text_from_state] {field} 是字典，字段: {list(value.keys())}")
            # 尝试从字典中提取文本
            for key in ("content", "markdown", "text", "message", "report"):
                text = value.get(key)
                if isinstance(text, str) and text.strip():
                    logger.info(f"🔍 [_extract_text_from_state] 从 {field}.{key} 提取到文本，长度: {len(text)}")
                    logger.info(f"🔍 [_extract_text_from_state] 内容前200字符: {text[:200]}")
                    return text.strip()

            logger.info(f"🔍 [_extract_text_from_state] {field} 字典中未找到文本字段")

        # 其他类型转为字符串
        result = str(value).strip()
        logger.info(f"🔍 [_extract_text_from_state] {field} 转为字符串，长度: {len(result)}")
        return result

    @property
    def last_execution(self) -> Optional[WorkflowExecution]:
        """最近一次执行记录"""
        return self._current_execution
