"""
工作流执行引擎

负责工作流的加载、验证和执行
"""

import logging
import uuid
from datetime import datetime
from typing import Any, AsyncIterator, Callable, Dict, List, Optional, Protocol

from .models import (
    NodeType,
    OutputStrategy,
    WorkflowDefinition,
    WorkflowExecution,
    WorkflowExecutionState,
)
from core.state.models import FieldType
from .builder import WorkflowBuilder, ANALYST_TOOL_MAPPING
from .validator import WorkflowValidator, ValidationResult

logger = logging.getLogger(__name__)

_BUILTIN_REPORT_FIELDS = [
    # analyst 阶段
    "market_report",
    "sentiment_report",
    "news_report",
    "fundamentals_report",
    "index_report",
    "sector_report",
    "social_report",
    "chip_report",
    # research 阶段
    "bull_report",
    "bear_report",
    "investment_plan",
    # risk 阶段
    "risky_opinion",
    "safe_opinion",
    "neutral_opinion",
    "risk_assessment",
    # manager 阶段
    "trader_investment_plan",
    "risk_conclusion",
    # trader 阶段
    "final_trade_decision",
    # 持仓分析阶段
    "technical_analysis",
    "fundamental_analysis",
    "risk_analysis",
    "action_advice",
    # 复盘阶段
    "timing_analysis",
    "position_analysis",
    "emotion_analysis",
    "attribution_analysis",
    "review_summary",
]


def _get_dynamic_report_fields(agent_ids: List[str]) -> List[str]:
    """从 Agent metadata 和 agent_configs 动态推导报告字段列表（替代硬编码）

    只返回 show_in_reports=True 的 agent 的 output_field。
    """
    fields = []

    try:
        from core.agents.registry import get_registry
        registry = get_registry()
        for meta in registry.list_all():
            if meta.id in agent_ids and meta.output_field and meta.output_field not in fields:
                # 检查 show_in_reports 标志，默认 True
                if getattr(meta, 'show_in_reports', True):
                    fields.append(meta.output_field)
    except Exception as e:
        logger.warning(f"[动态报告字段] 从 AgentRegistry 获取失败: {e}")

    try:
        from pymongo import MongoClient
        from tradingagents.config.mongodb_utils import build_mongodb_connection_string, get_mongodb_database_name

        client = MongoClient(build_mongodb_connection_string(), serverSelectionTimeoutMS=2000)
        db = client[get_mongodb_database_name()]
        docs = list(db.agent_configs.find({
            "agent_id": {"$in": agent_ids},
            "enabled": True,
            "version_status": "active",
            "runtime_status": "active",
        }))
        client.close()
        for doc in docs:
            output_field = doc.get("output_field") or (doc.get("metadata") or {}).get("output_field")
            if output_field and output_field not in fields:
                # 检查 show_in_reports 标志，默认 True
                show = doc.get("show_in_reports")
                if show is None:
                    show = (doc.get("metadata") or {}).get("show_in_reports", True)
                if show:
                    fields.append(output_field)
    except Exception as e:
        logger.warning(f"[动态报告字段] 从 agent_configs 获取失败: {e}")

    if "final_trade_decision" not in fields:
        fields.append("final_trade_decision")
    return fields if fields else _BUILTIN_REPORT_FIELDS

_AGENT_CATEGORY_DISPLAY = {
    "analyst": "分析师团队",
    "researcher": "研究团队",
    "trader": "交易团队",
    "risk": "风险管理团队",
    "manager": "决策层",
    "post_processor": "后处理",
}


def _prepare_workflow_runtime_inputs(
    inputs: Dict[str, Any],
    workflow_id: Optional[str],
    execution_id: str,
    task_id: Optional[str] = None,
) -> Dict[str, Any]:
    """向工作流初始 state 注入轻量运行时上下文，不污染返回结果。"""
    prepared_inputs = inputs.copy() if inputs else {}
    runtime_context = dict(prepared_inputs.get("_workflow_runtime") or {})
    context = prepared_inputs.get("context")

    context_user_id = None
    context_thread_id = None
    if isinstance(context, dict):
        context_user_id = context.get("user_id")
        context_thread_id = context.get("thread_id") or context.get("session_id")
    elif context is not None:
        context_user_id = getattr(context, "user_id", None)
        context_thread_id = getattr(context, "thread_id", None) or getattr(context, "session_id", None)

    if workflow_id and not runtime_context.get("workflow_id"):
        runtime_context["workflow_id"] = workflow_id
    if execution_id and not runtime_context.get("execution_id"):
        runtime_context["execution_id"] = execution_id
    # 🔑 注入 task_id（任务中心的 task_id，执行轨迹按此关联，前端按 task_id 查轨迹）
    if task_id and not runtime_context.get("task_id"):
        runtime_context["task_id"] = task_id
    if prepared_inputs.get("user_id") and not runtime_context.get("user_id"):
        runtime_context["user_id"] = prepared_inputs.get("user_id")
    if context_user_id and not runtime_context.get("user_id"):
        runtime_context["user_id"] = context_user_id
    if prepared_inputs.get("thread_id") and not runtime_context.get("thread_id"):
        runtime_context["thread_id"] = prepared_inputs.get("thread_id")
    if context_thread_id and not runtime_context.get("thread_id"):
        runtime_context["thread_id"] = context_thread_id

    if prepared_inputs.get("growth_memory_recall"):
        runtime_context["growth_memory_recall"] = prepared_inputs["growth_memory_recall"]

    ticker = prepared_inputs.get("ticker") or prepared_inputs.get("symbol") or prepared_inputs.get("stock_symbol") or prepared_inputs.get("company_of_interest")
    # 🔍 调试日志：排查 ticker 丢失问题
    import logging as _logging
    _logger = _logging.getLogger("core.workflow.engine")
    _logger.info(f"🔍 [_prepare_workflow_runtime_inputs] ticker 映射: ticker={prepared_inputs.get('ticker')}, symbol={prepared_inputs.get('symbol')}, stock_symbol={prepared_inputs.get('stock_symbol')}, company_of_interest={prepared_inputs.get('company_of_interest')}, 最终ticker={ticker}")
    if ticker:
        prepared_inputs.setdefault("ticker", ticker)
        prepared_inputs.setdefault("stock_symbol", ticker)
        prepared_inputs.setdefault("symbol", ticker)
        prepared_inputs.setdefault("company_of_interest", ticker)

    analysis_date = prepared_inputs.get("analysis_date") or prepared_inputs.get("trade_date")
    if analysis_date:
        prepared_inputs.setdefault("analysis_date", analysis_date)
        prepared_inputs.setdefault("trade_date", analysis_date)

    prepared_inputs["_workflow_runtime"] = runtime_context
    return prepared_inputs


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
        use_dynamic_state: bool = True,  # 🔥 改为默认启用，动态 Agent 工作流需要
        llm: Optional[Any] = None
    ):
        """
        初始化工作流引擎

        Args:
            legacy_config: 遗留智能体配置（用于创建 LLM 和 Toolkit）
            task_id: 任务 ID（用于进度跟踪）
            use_dynamic_state: 是否使用动态状态生成（默认 True，支持动态 Agent 字段）
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

        # 🆕 进度跟踪状态（按已完成 agent 数 / 总数计算进度，只增不减）
        self._progress_agent_nodes = []      # 有 agent_id 的 agent 节点列表
        self._progress_node_keys = {}        # {key: node} 映射，匹配 stream 返回的 node_name
        self._progress_completed = set()     # 已完成 agent 的 key 集合
        self._progress_total = 0             # agent 节点总数 N
        self._progress_max = 10              # 已上报的最大进度值（保证只增不减）

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

                internal_state_fields = self._build_internal_state_fields(self._definition)

                # 使用 StateRegistry 获取或构建状态类
                schema = self._state_registry.get_or_build(
                    workflow_id=self._definition.id,
                    agent_ids=agent_ids,
                    internal_state_fields=internal_state_fields,
                )
                state_schema = self._state_registry.get_state_class(self._definition.id)

                logger.info(f"[WorkflowEngine] 状态类生成成功: {state_schema.__name__ if state_schema else 'None'}")
                logger.info(f"[WorkflowEngine] 状态字段: {list(schema.fields.keys())}")

        # 构建图
        self._compiled_graph = self._builder.build(self._definition, state_schema=state_schema)
        return self

    def _extract_agent_ids(self, definition: WorkflowDefinition) -> list:
        """从工作流定义中提取 Agent ID 列表（含辩论参与者和委派 Agent）"""
        agent_ids = []
        for node in definition.nodes:
            candidates = []
            if node.agent_id:
                candidates.append(node.agent_id)

            node_config = getattr(node, "config", None) or {}
            candidates.extend(node_config.get("participants") or [])
            candidates.extend(node_config.get("delegated_agent_ids") or [])

            for agent_id in candidates:
                if agent_id and agent_id not in agent_ids:
                    agent_ids.append(agent_id)
        return agent_ids
    
    def _build_internal_state_fields(self, definition: WorkflowDefinition) -> Dict[str, FieldType]:
        """根据工作流定义补齐动态 State 需要的内部控制字段。"""
        fields: Dict[str, FieldType] = {
            "investment_debate_state": FieldType.OBJECT,
            "risk_debate_state": FieldType.OBJECT,
            "_max_debate_rounds": FieldType.NUMBER,
            "_max_risk_rounds": FieldType.NUMBER,
            # A9-P1: 风险自我辩论开关（True=深度/全面档走单节点自我辩论路径）
            "_risk_self_debate": FieldType.BOOLEAN,
            # A3: 投资辩论并行开局开关（True=第一轮乐观/审慎研究员并行出简报）
            "_parallel_opening": FieldType.BOOLEAN,
            "context": FieldType.OBJECT,
            "skip_cache": FieldType.BOOLEAN,
            "prompt_overrides": FieldType.OBJECT,
            "_workflow_runtime": FieldType.OBJECT,
            "_node_errors": FieldType.OBJECT,
            "tool_call_summaries": FieldType.OBJECT,
            "_condition_result": FieldType.BOOLEAN,
            "_condition_error": FieldType.STRING,
            "_analysis_data_source": FieldType.STRING,
            # 外部事实记忆注入（智能助手联网提取的事实，供辩论/风险评估环节参考）
            "memory_facts_summary": FieldType.STRING,
            # 持仓分析工作流输入：position_info/portfolio_data 若不声明，LangGraph 动态
            # State 会丢弃未声明键，导致 agents 拿不到持仓数据并报 "Missing required parameters: ticker"
            "position_info": FieldType.OBJECT,
            "portfolio_data": FieldType.OBJECT,
            "position_type": FieldType.STRING,
            "analysis_params": FieldType.OBJECT,
            "stock_analysis_report": FieldType.OBJECT,
            "user_preference": FieldType.STRING,
            "trade_info": FieldType.OBJECT,
            "ticker": FieldType.STRING,
            "symbol": FieldType.STRING,
            "company_of_interest": FieldType.STRING,
        }

        for node in definition.nodes:
            node_type = node.type.value if hasattr(node.type, "value") else str(node.type)
            if node_type == "debate":
                fields[f"_debate_{node.id}_count"] = FieldType.NUMBER

            if node.agent_id:
                normalized = node.agent_id.replace("_analyst_v2", "").replace("_analyst", "")
                if normalized:
                    fields[f"_{normalized}_messages"] = FieldType.ARRAY
                    fields[f"{normalized}_tool_call_count"] = FieldType.NUMBER

                analyst_type = ANALYST_TOOL_MAPPING.get(node.agent_id)
                if analyst_type:
                    fields[f"_{analyst_type}_messages"] = FieldType.ARRAY
                    fields[f"{analyst_type}_tool_call_count"] = FieldType.NUMBER

            node_config = getattr(node, "config", None) or {}
            output_field = node_config.get("output_field")
            if output_field:
                fields[output_field] = FieldType.STRING

        return fields
    
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

    def _build_execution_config(
        self,
        config: Optional[Dict[str, Any]],
        inputs: Optional[Dict[str, Any]],
    ) -> Dict[str, Any]:
        execution_config = dict(config or {})
        if "recursion_limit" not in execution_config:
            recursion_limit = None
            if inputs:
                recursion_limit = inputs.get("recursion_limit") or inputs.get("workflow_recursion_limit")
            if recursion_limit is None and self._legacy_config:
                recursion_limit = self._legacy_config.get("recursion_limit")
            execution_config["recursion_limit"] = int(recursion_limit or 100)
        return execution_config

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

        runtime_inputs = _prepare_workflow_runtime_inputs(
            inputs,
            self._definition.id if self._definition else None,
            self._task_id,
            task_id=self._task_id,
        )
        execution_config = self._build_execution_config(config, runtime_inputs)

        # 创建执行记录
        execution = self._create_execution(inputs)
        self._init_progress_tracking()
        self._report_progress(10, "开始执行工作流", "start")

        try:
            execution.state = WorkflowExecutionState.RUNNING
            execution.started_at = datetime.now().isoformat()

            logger.info(f"开始执行工作流: {self._definition.id if self._definition else 'unknown'}")

            # 使用 stream 模式以获取节点级别的进度更新
            # stream_mode 应该作为关键字参数传递，而不是放在 config 字典中
            final_state = inputs.copy() if inputs else {}

            for chunk in self._compiled_graph.stream(runtime_inputs, config=execution_config, stream_mode="updates"):
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
                                logger.debug(f"[执行引擎] 📝 节点 {node_name} 返回字段: {update_keys}")
                                # 检查是否有 index_report 或 sector_report
                                if "index_report" in node_update:
                                    logger.debug(f"[执行引擎] ✅ 检测到 index_report ({len(str(node_update['index_report']))} 字符)")
                                if "sector_report" in node_update:
                                    logger.debug(f"[执行引擎] ✅ 检测到 sector_report ({len(str(node_update['sector_report']))} 字符)")
                                final_state.update(node_update)
                            except Exception:
                                final_state[node_name] = node_update
                        else:
                            final_state[node_name] = node_update

            # 使用累积的最终状态
            result = final_state
            result = self._build_output_results(result)

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
                progress=self._progress_max,
                message=f"执行失败: {str(e)}",
                step_name="error",
                error=str(e)
            )
            raise

        finally:
            self._current_execution = execution
    
    def _init_progress_tracking(self) -> None:
        """初始化进度跟踪：统计 agent 节点总数，建立匹配映射

        以「有 agent_id 的节点」作为 agent 节点（控制节点
        PARALLEL/MERGE/DEBATE/START/END 无 agent_id，自动排除）。
        进度按 已完成agent数/总数 计算，只增不减，自动适应 agent 增减。
        """
        self._progress_completed = set()
        self._progress_max = 10
        self._progress_agent_nodes = []
        self._progress_node_keys = {}

        if not self._definition or not self._definition.nodes:
            self._progress_total = 0
            return

        for node in self._definition.nodes:
            agent_id = getattr(node, "agent_id", None)
            if not agent_id:
                continue  # 控制节点（start/end/parallel/merge/debate）跳过
            self._progress_agent_nodes.append(node)
            # 建立多种 key 的映射，匹配 stream 返回的 node_name
            for key in (agent_id, node.label, node.id):
                if key:
                    self._progress_node_keys[key] = node

        self._progress_total = len(self._progress_agent_nodes)

    def _get_node_progress_info(self, node_name: str) -> tuple:
        """获取节点的进度信息（百分比和友好消息）

        🔥 按「已完成 agent 数 / 总数」计算进度，只增不减：
        - 10% 起（编译/开始），10%-90% 区间按 completed/N 均分，100% 在工作流完成时上报
        - 控制节点不增加 completed，但上报当前进度 + 友好消息
        - 无 definition（N==0）时回退到 node_mapping 固定百分比，兼容单 agent 调试

        Args:
            node_name: 节点名称（从 LangGraph stream 返回）

        Returns:
            (progress_percentage, friendly_message, step_name)
        """
        # 节点名称到友好消息的映射（仅用于展示，进度值不再取自此映射）
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
            "bull_researcher_v2": (50, "🐂 乐观情景研究员正在构建偏乐观论证...", "乐观情景研究员"),
            "bear_researcher_v2": (55, "🐻 审慎情景研究员正在构建偏审慎论证...", "审慎情景研究员"),
            "research_manager_v2": (60, "🔬 研究经理正在综合研究观点...", "研究经理"),

            # === v2.0 研究整合阶段 ===
            "trader_v2": (92, "🧩 研究整合员正在生成用户版研究简报...", "研究整合员"),

            # === v2.0 风险管理团队 ===
            "risky_analyst_v2": (72, "⚡ 高弹性情景分析师正在审阅结论上修条件...", "高弹性情景分析师"),
            "safe_analyst_v2": (78, "🛡️ 防御情景分析师正在审阅脆弱点与关键风险...", "防御情景分析师"),
            "neutral_analyst_v2": (84, "⚖️ 基准情景分析师正在审阅基准情景与证据完整性...", "基准情景分析师"),
            "risk_manager_v2": (90, "👔 风险评估师正在审阅研究结论稳健性...", "风险评估师"),

            # === v1.0 分析师节点（向后兼容）===
            "market_analyst": (15, "📈 市场分析师正在分析技术指标和市场趋势...", "市场分析师"),
            "fundamentals_analyst": (25, "💰 基本面分析师正在分析财务数据...", "基本面分析师"),
            "news_analyst": (35, "📰 新闻分析师正在分析相关新闻和事件...", "新闻分析师"),
            "social_analyst": (40, "💬 社媒分析师正在分析社交媒体情绪...", "社媒分析师"),
            "sentiment_analyst": (40, "💭 情绪分析师正在分析市场情绪...", "情绪分析师"),

            # === v1.0 研究团队 ===
            "bull_researcher": (50, "🐂 乐观情景研究员正在构建偏乐观论证...", "乐观情景研究员"),
            "bear_researcher": (55, "🐻 审慎情景研究员正在构建偏审慎论证...", "审慎情景研究员"),
            "research_manager": (60, "🔬 研究经理正在综合研究观点...", "研究经理"),

            # === v1.0 研究整合阶段 ===
            "trader": (70, "🧩 研究整合员正在汇总研究结论...", "研究整合员"),

            # === v1.0 风险管理团队 ===
            "risky_analyst": (75, "⚡ 高弹性情景研究员正在评估上行空间...", "高弹性情景研究员"),
            "safe_analyst": (80, "🛡️ 防御情景研究员正在评估下行风险...", "防御情景研究员"),
            "neutral_analyst": (82, "⚖️ 中性分析师正在平衡风险收益...", "中性分析师"),
            "risk_manager": (90, "👔 风险评估师正在形成最终研究结论...", "风险评估师"),
            "risk_judge": (90, "👔 风险评估师正在形成最终研究结论...", "风险评估师"),
            "portfolio_manager": (90, "👔 风险评估师正在做最终研究审阅...", "风险评估师"),

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
            "Bull Researcher": (50, "🐂 乐观情景研究员正在构建偏乐观论证...", "乐观情景研究员"),
            "Bear Researcher": (55, "🐻 审慎情景研究员正在构建偏审慎论证...", "审慎情景研究员"),
            "Research Manager": (60, "🔬 研究经理正在综合研究观点...", "研究经理"),
            "Trader": (70, "🧩 研究整合员正在汇总研究结论...", "研究整合员"),
            "Risky Analyst": (75, "⚡ 高弹性情景研究员正在评估上行空间...", "高弹性情景研究员"),
            "Safe Analyst": (80, "🛡️ 防御情景研究员正在评估下行风险...", "防御情景研究员"),
            "Neutral Analyst": (82, "⚖️ 中性分析师正在平衡风险收益...", "中性分析师"),
            "Risk Judge": (90, "👔 风险评估师正在形成最终研究结论...", "风险评估师"),
            "Portfolio Manager": (90, "👔 风险评估师正在做最终研究审阅...", "风险评估师"),
        }

        # 忽略的节点（工具节点、消息清理节点等）
        ignored_patterns = ["tools_", "Msg Clear", "msg_clear_", "__start__", "__end__"]

        for pattern in ignored_patterns:
            if pattern in node_name:
                return (None, None, None)  # 跳过这些节点

        # 从映射取友好消息（命中时；进度值不再取自映射）
        mapped = node_mapping.get(node_name)

        # 匹配 agent 节点并累积完成数（控制节点无 agent_id，不会命中）
        agent_node = self._progress_node_keys.get(node_name)
        if agent_node is not None and node_name not in self._progress_completed:
            self._progress_completed.add(node_name)

        # 计算进度
        if self._progress_total > 0:
            # 按已完成 agent 数均分 10%-90% 区间
            progress = 10 + int(round(80 * len(self._progress_completed) / self._progress_total))
        elif mapped is not None:
            # 无 definition 回退：使用固定百分比（兼容单 agent 调试等场景）
            progress = mapped[0]
        else:
            progress = self._progress_max  # 未知节点，保持当前

        # 只增不减
        if progress < self._progress_max:
            progress = self._progress_max
        else:
            self._progress_max = progress

        # 友好消息与 step_name
        if mapped is not None:
            return (progress, mapped[1], mapped[2])

        # 动态推导：从工作流定义中查找节点 label
        for node in self._progress_agent_nodes:
            agent_id = node.agent_id or ""
            if agent_id == node_name or node.label == node_name or node.id == node_name:
                meta = self._lookup_agent_metadata(agent_id) if agent_id else None
                label = (meta.node_name if meta and meta.node_name
                         else node.label or agent_id.replace("_", " ").title())
                return (progress, f"正在执行: {label}", label)

        friendly_name = node_name.replace("_v2", "").replace("_", " ").title()
        return (progress, f"正在执行: {friendly_name}", friendly_name)

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

        runtime_inputs = _prepare_workflow_runtime_inputs(
            inputs,
            self._definition.id if self._definition else None,
            self._task_id,
            task_id=self._task_id,
        )
        execution_config = self._build_execution_config(config, runtime_inputs)

        execution = self._create_execution(inputs)
        self._init_progress_tracking()
        self._report_progress(10, "开始执行工作流", "start")

        try:
            execution.state = WorkflowExecutionState.RUNNING
            execution.started_at = datetime.now().isoformat()

            logger.info(f"开始异步执行工作流: {self._definition.id if self._definition else 'unknown'}")

            # 使用 astream 模式以获取节点级别的进度更新
            # stream_mode 应该作为关键字参数传递，而不是放在 config 字典中
            final_state = inputs.copy() if inputs else {}

            async for chunk in self._compiled_graph.astream(runtime_inputs, config=execution_config, stream_mode="updates"):
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
            result = self._build_output_results(result)

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
                progress=self._progress_max,
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

        runtime_inputs = _prepare_workflow_runtime_inputs(
            inputs,
            self._definition.id if self._definition else None,
            self._task_id,
            task_id=self._task_id,
        )
        
        execution = self._create_execution(inputs)
        execution.state = WorkflowExecutionState.RUNNING
        execution.started_at = datetime.now().isoformat()
        
        try:
            async for event in self._compiled_graph.astream(runtime_inputs, config):
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

    # ------------------------------------------------------------------
    # 动态产出物收集
    # ------------------------------------------------------------------

    def _is_builtin_workflow(self, definition: WorkflowDefinition) -> bool:
        """判断是否为内置工作流（使用标准报告字段的旧工作流）"""
        if not definition:
            return True
        agent_ids = self._extract_agent_ids(definition)
        if not agent_ids:
            return True
        has_builtin_agents = any(
            aid.endswith("_v2") or aid in (
                "market_analyst", "fundamentals_analyst", "news_analyst",
                "social_analyst", "bull_researcher", "bear_researcher",
                "research_manager", "trader", "risk_manager",
                "risky_analyst", "safe_analyst", "neutral_analyst",
            )
            for aid in agent_ids
        )
        strategy = getattr(definition.output_config, "strategy", "auto")
        if strategy != "auto":
            return False
        return has_builtin_agents

    def _lookup_agent_metadata(self, agent_id: str):
        """查询 Agent 元数据：优先 DB 动态 Agent，再 registry，最后代码常量"""
        # 1. 优先从 MongoDB agent_configs 查找动态 Agent（Agent 工坊创建的自定义 Agent）
        try:
            from app.core.database import get_mongo_db
            db = get_mongo_db()
            doc = db.agent_configs.find_one({"agent_id": agent_id, "enabled": True})
            if doc:
                from core.agents.config import AgentMetadata, AgentCategory
                metadata_fields = doc.get("metadata", {})
                return AgentMetadata(
                    id=agent_id,
                    name=doc.get("name", agent_id),
                    description=doc.get("description", ""),
                    category=AgentCategory(metadata_fields.get("workflow_stage", "analyst")),
                    tools=doc.get("default_tools", []),
                    default_tools=doc.get("default_tools", []),
                    license_tier=metadata_fields.get("license_tier", "pro"),
                    tags=metadata_fields.get("tags", []),
                    icon=metadata_fields.get("icon", "📄"),
                    color=metadata_fields.get("color", "#3498db"),
                    output_field=doc.get("output_field", f"{agent_id}_report"),
                    report_label=doc.get("name", agent_id),
                    show_in_reports=True,
                    node_name=doc.get("name", agent_id),
                )
        except Exception:
            pass

        # 2. 从 AgentRegistry 查找
        try:
            from core.agents.registry import get_registry
            metadata = get_registry().get_metadata(agent_id)
            if metadata:
                return metadata
        except Exception:
            pass

        # 3. 从代码常量回退
        try:
            from core.agents.config import AGENT_METADATA_REGISTRY
            return AGENT_METADATA_REGISTRY.get(agent_id)
        except Exception:
            pass
        return None

    def _collect_output_manifest(
        self,
        state: Dict[str, Any],
        definition: WorkflowDefinition,
    ):
        """
        根据 output_config 从 state 中收集产出物。

        Returns:
            (structured_reports, report_manifest)
        """
        output_config = definition.output_config
        strategy = output_config.strategy

        if strategy == OutputStrategy.SPECIFIED and output_config.fields:
            return self._collect_specified(state, output_config)
        elif strategy == OutputStrategy.LAST_NODE:
            return self._collect_last_node(state, definition)
        elif strategy == OutputStrategy.COLLECT_ALL:
            return self._collect_all_agents(state, definition)
        else:
            return self._collect_auto(state, definition)

    def _collect_auto(self, state, definition):
        """AUTO 策略：自动从工作流拓扑和 Agent 声明推导产出物"""
        agent_nodes = [n for n in definition.nodes if n.agent_id]
        if not agent_nodes:
            return {}, []

        field_infos = []
        for node in agent_nodes:
            meta = self._lookup_agent_metadata(node.agent_id)
            # 检查 show_in_reports 标志，默认 True
            if meta and not getattr(meta, 'show_in_reports', True):
                continue
            field_name = (meta.output_field if meta and meta.output_field
                          else f"{node.agent_id}_report")
            display_name = ""
            if meta:
                display_name = meta.report_label or meta.node_name
            display_name = display_name or node.label or node.agent_id.replace("_", " ").title()

            cat = ""
            if meta:
                cat_val = meta.category.value if hasattr(meta.category, "value") else str(meta.category)
                cat = _AGENT_CATEGORY_DISPLAY.get(cat_val, cat_val)
            cat = cat or "其他"

            order = meta.execution_order if meta else 100
            field_infos.append({
                "field": field_name,
                "display_name": display_name.strip("【】"),
                "category": cat,
                "order": order,
                "is_primary": False,
                "format_hint": "markdown",
                "agent_id": node.agent_id,
                "icon": meta.icon if meta else "📄",
                "description": meta.description if meta else "",
            })

        if field_infos:
            primary = max(field_infos, key=lambda f: f["order"])
            primary["is_primary"] = True

        return self._extract_from_state(state, field_infos)

    def _collect_all_agents(self, state, definition):
        """COLLECT_ALL 策略：收集所有 Agent 节点的 output_field"""
        return self._collect_auto(state, definition)

    def _collect_last_node(self, state, definition):
        """LAST_NODE 策略：只收集 END 节点直接前驱的 Agent 输出"""
        end_nodes = definition.get_end_nodes()
        predecessor_agent_ids = set()
        for end_node in end_nodes:
            incoming = definition.get_edges_to(end_node.id)
            for edge in incoming:
                src_node = definition.get_node(edge.source)
                if src_node and src_node.agent_id:
                    predecessor_agent_ids.add(src_node.agent_id)

        if not predecessor_agent_ids:
            return self._collect_auto(state, definition)

        agent_nodes = [
            n for n in definition.nodes
            if n.agent_id and n.agent_id in predecessor_agent_ids
        ]
        field_infos = []
        for node in agent_nodes:
            meta = self._lookup_agent_metadata(node.agent_id)
            # 检查 show_in_reports 标志，默认 True
            if meta and not getattr(meta, 'show_in_reports', True):
                continue
            field_name = (meta.output_field if meta and meta.output_field
                          else f"{node.agent_id}_report")
            display_name = ""
            if meta:
                display_name = meta.report_label or meta.node_name
            display_name = display_name or node.label or node.agent_id.replace("_", " ").title()
            cat_val = (meta.category.value if meta and hasattr(meta.category, "value")
                       else str(meta.category) if meta else "")
            field_infos.append({
                "field": field_name,
                "display_name": display_name.strip("【】"),
                "category": _AGENT_CATEGORY_DISPLAY.get(cat_val, cat_val) or "其他",
                "order": meta.execution_order if meta else 100,
                "is_primary": True,
                "format_hint": "markdown",
                "agent_id": node.agent_id,
                "icon": meta.icon if meta else "📄",
                "description": meta.description if meta else "",
            })

        return self._extract_from_state(state, field_infos)

    def _collect_specified(self, state, output_config):
        """SPECIFIED 策略：使用用户手动指定的字段列表"""
        field_infos = []
        for fc in output_config.fields:
            field_infos.append({
                "field": fc.field_name,
                "display_name": fc.display_name or fc.field_name.replace("_", " ").title(),
                "category": fc.category or "其他",
                "order": fc.order,
                "is_primary": fc.is_primary,
                "format_hint": fc.format_hint or "markdown",
                "agent_id": "",
                "icon": getattr(fc, "icon", "") or "📄",
                "description": getattr(fc, "description", "") or "",
            })
        if field_infos and not any(f["is_primary"] for f in field_infos):
            max_order = max(field_infos, key=lambda f: f["order"])
            max_order["is_primary"] = True
        return self._extract_from_state(state, field_infos)

    @staticmethod
    def _extract_text_value(v) -> str:
        if isinstance(v, str):
            return v
        if isinstance(v, dict):
            for k in ("content", "markdown", "text", "message", "report"):
                x = v.get(k)
                if isinstance(x, str) and x.strip():
                    return x
        return "" if v is None else str(v)

    def _extract_from_state(self, state, field_infos):
        """从 state 中提取字段内容，构建 structured_reports 和 report_manifest"""
        structured = {}
        manifest = []

        for info in sorted(field_infos, key=lambda f: f["order"]):
            field = info["field"]
            raw = state.get(field)
            text = self._extract_text_value(raw)
            has_content = bool(isinstance(text, str) and text.strip())

            structured[field] = {"content": text, "success": has_content}
            manifest.append({
                "field": field,
                "display_name": info["display_name"],
                "category": info["category"],
                "order": info["order"],
                "is_primary": info["is_primary"],
                "format_hint": info["format_hint"],
                "agent_id": info.get("agent_id", ""),
                "icon": info.get("icon", "📄"),
                "description": info.get("description", ""),
                "has_content": has_content,
            })

        return structured, manifest

    def _build_output_results(self, result: Dict[str, Any]) -> Dict[str, Any]:
        """
        在 execute 完成后构建产出物。
        内置工作流走旧逻辑，自定义工作流走动态收集。
        """
        definition = self._definition
        if not definition:
            return result

        if self._is_builtin_workflow(definition):
            return self._build_builtin_output(result)

        structured, manifest = self._collect_output_manifest(result, definition)
        result["structured_reports"] = structured
        result["report_manifest"] = manifest

        if not result.get("final_trade_decision"):
            primary_items = [m for m in manifest if m.get("is_primary") and m.get("has_content")]
            if primary_items:
                pf = primary_items[0]["field"]
                result["final_trade_decision"] = self._extract_text_value(result.get(pf))
            elif manifest:
                sections = []
                for m in manifest:
                    if m.get("has_content"):
                        text = self._extract_text_value(result.get(m["field"]))
                        sections.append(f"## {m['display_name']}\n\n{text}")
                if sections:
                    result["final_trade_decision"] = "\n\n".join(sections)

        node_errors = result.get("_node_errors")
        if node_errors:
            result["degraded_nodes"] = node_errors
            logger.warning(
                f"[WorkflowEngine] 工作流存在降级节点: "
                f"{list(node_errors.keys())}"
            )

        logger.info(
            f"[WorkflowEngine] 动态产出物收集完成: "
            f"{len(structured)} 个报告, {len(manifest)} 条 manifest"
        )
        return result

    def _build_builtin_output(self, result: Dict[str, Any]) -> Dict[str, Any]:
        """内置工作流的产出物逻辑（动态字段 + 向后兼容）"""
        # 动态推导报告字段列表（新 Agent 的 output_field 自动包含）
        agent_ids = self._extract_agent_ids(self._definition) if self._definition else []
        report_fields = _get_dynamic_report_fields(agent_ids) if agent_ids else _BUILTIN_REPORT_FIELDS
        
        # 内置字段的显示名映射
        builtin_display_names = {
            "market_report": "📈 市场技术研究",
            "sentiment_report": "💭 情绪研究",
            "news_report": "📰 新闻研究",
            "fundamentals_report": "💰 基本面研究",
            "index_report": "📊 大盘环境研究",
            "sector_report": "🏭 行业板块研究",
            "social_report": "💭 社交媒体研究",
            "chip_report": "🧮 筹码分布研究",
            "bull_report": "🐂 乐观情景研究员",
            "bear_report": "🐻 审慎情景研究员",
            "investment_plan": "📋 研究经理简报",
            "trader_investment_plan": "🧩 研究简报",
            "risky_opinion": "🔥 高弹性情景观点",
            "safe_opinion": "🛡️ 防御情景观点",
            "neutral_opinion": "⚖️ 基准情景观点",
            "risk_assessment": "⚠️ 风险审阅结论",
            "risk_management_decision": "⚠️ 风险审阅结论",
            "final_trade_decision": "📝 综合研究结论",
        }
        
        # 工坊 Agent 的显示名缓存（从 agent_configs 读取）
        workshop_display_names = {}
        try:
            from tradingagents.config.mongodb_utils import build_mongodb_connection_string, get_mongodb_database_name
            from pymongo import MongoClient as _MC
            _client = _MC(build_mongodb_connection_string(), serverSelectionTimeoutMS=2000)
            _db = _client[get_mongodb_database_name()]
            _docs = list(_db.agent_configs.find(
                {"enabled": True, "version_status": "active", "runtime_status": "active"},
                {"agent_id": 1, "display_name": 1, "name": 1, "output_field": 1}
            ))
            _client.close()
            for _doc in _docs:
                _output_field = _doc.get("output_field")
                if _output_field:
                    _display_name = _doc.get("display_name") or _doc.get("name")
                    if _display_name:
                        workshop_display_names[_output_field] = f"📊 {_display_name}"
        except Exception as _e:
            logger.warning(f"⚠️ [WorkflowEngine] 读取工坊 Agent 显示名失败: {_e}")
        
        structured = {}
        manifest = []
        
        for idx, f in enumerate(report_fields):
            if f not in result:
                continue
                
            text = self._extract_text_value(result.get(f))
            success = bool(isinstance(text, str) and text.strip())
            
            d = {"content": text, "success": success}
            if f == "bull_report":
                d["stance"] = "bull"
            if f == "bear_report":
                d["stance"] = "bear"
            structured[f] = d
            
            # 获取显示名
            display_name = workshop_display_names.get(f) or builtin_display_names.get(f) or f.replace("_", " ").title()
            
            # 分配 category
            category = "analyst"
            if f in ["bull_report", "bear_report", "investment_plan", "trader_investment_plan", "research_team_decision"]:
                category = "research"
            elif f in ["risky_opinion", "safe_opinion", "neutral_opinion", "risk_assessment", "risk_management_decision"]:
                category = "risk"
            elif f == "final_trade_decision":
                category = "manager"
            
            manifest.append({
                "field": f,
                "display_name": display_name,
                "category": category,
                "order": idx,
                "is_primary": f == "final_trade_decision",
                "format_hint": "markdown",
                "icon": "📊",
                "description": "",
                "has_content": success,
            })
        
        result["structured_reports"] = structured
        result["report_manifest"] = manifest

        existing_ftd = result.get("final_trade_decision")
        has_action = existing_ftd and isinstance(existing_ftd, dict) and (
            existing_ftd.get("action") or existing_ftd.get("analysis_view")
        )
        if has_action:
            action = existing_ftd.get("action") or existing_ftd.get("analysis_view")
            logger.info(
                f"[WorkflowEngine] 使用 RiskManagerV2 的 final_trade_decision: "
                f"action={action}, confidence={existing_ftd.get('confidence')}"
            )
        else:
            final_trade_decision = self._generate_final_trade_decision(result)
            if final_trade_decision:
                result["final_trade_decision"] = final_trade_decision

        node_errors = result.get("_node_errors")
        if node_errors:
            result["degraded_nodes"] = node_errors
            logger.warning(
                f"[WorkflowEngine] 内置工作流存在降级节点: "
                f"{list(node_errors.keys())}"
            )
        return result

    def _generate_final_trade_decision(self, state: Dict[str, Any]) -> str:
        """
        生成最终研究结论

        综合以下内容：
        1. investment_plan (研究整合员的研究观察汇总)
        2. trader_investment_plan (研究整合员的整合意见)
        3. risk_assessment (风险评估师的风险审阅结论)

        Args:
            state: 工作流执行状态

        Returns:
            最终研究结论文本（Markdown 格式）
        """
        # 🔍 调试：打印 state 中的关键字段
        logger.debug(f"🔍 [WorkflowEngine] state 中的字段: {list(state.keys())}")
        logger.debug(f"🔍 [WorkflowEngine] investment_plan 存在: {'investment_plan' in state}")
        logger.debug(f"🔍 [WorkflowEngine] trader_investment_plan 存在: {'trader_investment_plan' in state}")
        logger.debug(f"🔍 [WorkflowEngine] risk_assessment 存在: {'risk_assessment' in state}")

        # 提取各个报告
        investment_plan = self._extract_text_from_state(state, "investment_plan")
        trader_plan = self._extract_text_from_state(state, "trader_investment_plan")
        risk_assessment = self._extract_text_from_state(state, "risk_assessment")

        # 🔍 调试：打印提取结果
        logger.debug(f"🔍 [WorkflowEngine] investment_plan 长度: {len(investment_plan)}")
        logger.debug(f"🔍 [WorkflowEngine] trader_plan 长度: {len(trader_plan)}")
        logger.debug(f"🔍 [WorkflowEngine] risk_assessment 长度: {len(risk_assessment)}")

        # 如果三个都为空，返回空字符串
        if not any([investment_plan, trader_plan, risk_assessment]):
            logger.warning("⚠️ [WorkflowEngine] 无法生成 final_trade_decision：所有输入报告均为空")
            return ""

        # 🔥 新方案：简单拼接三个报告（保持原有行为）
        # 注意：这里只是拼接，不进行综合分析
        # 真正的综合决策由 TaskAnalysisService 从 investment_plan 中提取
        sections = []

        if investment_plan:
            sections.append(f"## 📋 研究结论\n\n{investment_plan}")

        if trader_plan:
            sections.append(f"## 🧩 研究整合意见\n\n{trader_plan}")

        if risk_assessment:
            sections.append(f"## 🛡️ 风险审阅结论\n\n{risk_assessment}")

        final_decision = "\n\n".join(sections)
        logger.info(f"✅ [WorkflowEngine] 生成 final_trade_decision，包含 {len(sections)} 个部分")
        logger.info(f"✅ [WorkflowEngine] 生成 final_trade_decision，长度: {len(final_decision)}")
        logger.debug(f"🔍 [WorkflowEngine] final_trade_decision 内容前500字符:\n{final_decision[:500]}")

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
        logger.debug(f"🔍 [_extract_text_from_state] 提取字段: {field}")
        logger.debug(f"🔍 [_extract_text_from_state] 值类型: {type(value)}")

        if value is None:
            logger.debug(f"🔍 [_extract_text_from_state] {field} 为 None，返回空字符串")
            return ""

        if isinstance(value, str):
            logger.debug(f"🔍 [_extract_text_from_state] {field} 是字符串，长度: {len(value)}")
            logger.debug(f"🔍 [_extract_text_from_state] {field} 内容前200字符: {value[:200]}")
            return value.strip()

        if isinstance(value, dict):
            logger.debug(f"🔍 [_extract_text_from_state] {field} 是字典，字段: {list(value.keys())}")
            # 🛡️ Q1: 失败/空响应形态不进报告——识别 {'success': False, 'error': ...}（节点异常）
            # 与 {'content': '', 'success': True}（空响应被包装成成功）两类异常包装，
            # 渲染友好提示而非裸 dict 字符串
            _content_val = value.get("content")
            if value.get("success") is False or (
                value.get("success") is True
                and not (isinstance(_content_val, str) and _content_val.strip())
            ):
                _err = value.get("error") or "模型响应异常（空内容）"
                logger.warning(
                    f"⚠️ [_extract_text_from_state] {field} 为失败/空响应形态，"
                    f"将以提示替代报告内容: success={value.get('success')}, error={_err}"
                )
                return f"> ⚠️ **本节生成失败**：{_err}。建议重新分析以获取完整报告。"
            # 尝试从字典中提取文本
            for key in ("content", "markdown", "text", "message", "report"):
                text = value.get(key)
                if isinstance(text, str) and text.strip():
                    logger.debug(f"🔍 [_extract_text_from_state] 从 {field}.{key} 提取到文本，长度: {len(text)}")
                    logger.debug(f"🔍 [_extract_text_from_state] 内容前200字符: {text[:200]}")
                    return text.strip()

            logger.debug(f"🔍 [_extract_text_from_state] {field} 字典中未找到文本字段")

        # 其他类型转为字符串
        result = str(value).strip()
        logger.debug(f"🔍 [_extract_text_from_state] {field} 转为字符串，长度: {len(result)}")
        return result

    @property
    def last_execution(self) -> Optional[WorkflowExecution]:
        """最近一次执行记录"""
        return self._current_execution
