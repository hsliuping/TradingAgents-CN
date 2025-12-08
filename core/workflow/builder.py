"""
工作流构建器

从 WorkflowDefinition 构建 LangGraph 图

核心设计：
1. 辩论节点(DEBATE)不是一个执行节点，而是控制流程的标记
2. 辩论参与者(如 bull_researcher, bear_researcher)通过条件边连接
3. 条件边检查状态中的辩论计数来决定继续辩论还是结束
"""

import logging
from typing import Any, Callable, Dict, List, Optional, Set

logger = logging.getLogger(__name__)

from langgraph.graph import StateGraph, START, END

from .models import (
    WorkflowDefinition,
    NodeDefinition,
    EdgeDefinition,
    NodeType,
    EdgeType,
)
from ..agents import AgentRegistry, AgentFactory, AgentConfig


class WorkflowBuilder:
    """
    工作流构建器
    
    将 WorkflowDefinition 转换为可执行的 LangGraph
    
    用法:
        builder = WorkflowBuilder()
        graph = builder.build(workflow_definition)
        result = graph.invoke({"ticker": "AAPL", "trade_date": "2024-01-15"})
    """
    
    def __init__(
        self,
        registry: Optional[AgentRegistry] = None,
        factory: Optional[AgentFactory] = None,
        default_config: Optional[AgentConfig] = None,
    ):
        from ..agents.registry import get_registry
        
        self.registry = registry or get_registry()
        self.factory = factory or AgentFactory(self.registry)
        self.default_config = default_config or AgentConfig()
        
        self._agents: Dict[str, Any] = {}  # 缓存创建的智能体
    
    def build(
        self,
        definition: WorkflowDefinition,
        state_schema: Optional[type] = None,
    ):
        """
        构建 LangGraph 图

        Args:
            definition: 工作流定义
            state_schema: 状态模式 (默认使用通用字典)

        Returns:
            编译后的 LangGraph
        """
        # 使用默认状态模式
        if state_schema is None:
            state_schema = self._get_default_state_schema()

        # 创建图
        graph = StateGraph(state_schema)

        # 首先识别辩论配置
        debate_configs = self._identify_debate_configs(definition)

        # 构建辩论参与者集合及其对应的 debate_key
        participant_debate_keys: Dict[str, str] = {}
        for debate_id, config in debate_configs.items():
            debate_key = f"_debate_{debate_id}_count"
            for p in config["participants"]:
                participant_debate_keys[p] = debate_key

        # 添加节点
        for node in definition.nodes:
            if node.type in (NodeType.START, NodeType.END):
                continue

            # 如果是辩论参与者，使用包装函数
            if node.id in participant_debate_keys:
                debate_key = participant_debate_keys[node.id]
                node_func = self._create_debate_participant_wrapper(node, debate_key)
            else:
                node_func = self._create_node_function(node)

            graph.add_node(node.id, node_func)

        # 添加边
        self._add_edges(graph, definition, debate_configs)

        # 编译
        return graph.compile()
    
    def _get_default_state_schema(self) -> type:
        """
        获取默认状态模式

        使用 TypedDict 但包含 __extra_items__ 来支持动态字段
        参考 tradingagents 的 AgentState 设计
        """
        from typing import Annotated, Any
        from typing_extensions import TypedDict
        from langgraph.graph import MessagesState
        import operator

        class WorkflowState(MessagesState):
            # 基本信息
            company_of_interest: Annotated[str, "股票代码"]
            trade_date: Annotated[str, "交易日期"]

            # 分析报告
            market_report: Annotated[str, "市场分析报告"]
            fundamentals_report: Annotated[str, "基本面分析报告"]
            news_report: Annotated[str, "新闻分析报告"]
            sentiment_report: Annotated[str, "情绪分析报告"]

            # 研究结果
            bull_report: Annotated[str, "看多研究报告"]
            bear_report: Annotated[str, "看空研究报告"]
            investment_plan: Annotated[str, "投资计划"]

            # 最终决策
            final_decision: Annotated[str, "最终决策"]
            risk_assessment: Annotated[str, "风险评估"]
            final_trade_decision: Annotated[str, "最终交易决策"]

            # 辩论状态 - 注意使用 operator.add 来处理并发更新
            _debate_debate_count: Annotated[int, operator.add]
            _debate_risk_debate_count: Annotated[int, operator.add]

            # 辩论配置
            _max_debate_rounds: Annotated[int, "最大辩论轮数"]
            _max_risk_rounds: Annotated[int, "最大风险讨论轮数"]

        return WorkflowState
    
    def _create_node_function(self, node: NodeDefinition) -> Callable:
        """为节点创建执行函数"""

        if node.type == NodeType.CONDITION:
            return self._create_condition_node(node)
        elif node.type == NodeType.PARALLEL:
            return self._create_parallel_node(node)
        elif node.type == NodeType.MERGE:
            return self._create_merge_node(node)
        elif node.type == NodeType.DEBATE:
            return self._create_debate_node(node)
        else:
            return self._create_agent_node(node)

    def _create_agent_node(self, node: NodeDefinition) -> Callable:
        """创建智能体节点"""
        agent_id = node.agent_id
        node_id = node.id
        node_label = node.label or node_id

        if agent_id is None:
            raise ValueError(f"节点 {node.id} 缺少 agent_id")

        # 合并节点配置
        config = AgentConfig(**{
            **self.default_config.model_dump(),
            **node.config
        })

        # 尝试创建智能体
        if self.registry.is_registered(agent_id):
            agent = self.factory.create(agent_id, config)
            self._agents[node.id] = agent

            # 包装以添加日志
            def logged_agent(state, _agent=agent, _id=node_id, _label=node_label):
                logger.info(f"[节点执行] 🚀 {_id} ({_label}) - 开始执行")
                result = _agent(state)
                logger.info(f"[节点执行] ✅ {_id} ({_label}) - 执行完成")
                return result
            return logged_agent
        else:
            # 智能体未实现，返回占位函数
            def placeholder_node(state, _id=node_id, _label=node_label, _agent_id=agent_id):
                logger.info(f"[节点执行] 🔸 {_id} ({_label}) - 占位执行 (智能体 {_agent_id} 未实现)")
                return {
                    f"{_agent_id}_report": f"[{_agent_id}] 智能体未实现"
                }
            return placeholder_node

    def _create_condition_node(self, node: NodeDefinition) -> Callable:
        """创建条件节点"""
        condition_expr = node.condition or "True"
        node_id = node.id
        node_label = node.label or node_id

        def condition_node(state):
            logger.info(f"[节点执行] 🔀 {node_id} ({node_label}) - 条件判断")
            # 评估条件
            try:
                result = eval(condition_expr, {"state": state})
                logger.info(f"[节点执行] 🔀 {node_id} 结果: {result}")
                return {"_condition_result": bool(result)}
            except Exception as e:
                logger.error(f"[节点执行] ❌ {node_id} 条件评估错误: {e}")
                return {"_condition_result": True, "_condition_error": str(e)}

        return condition_node

    def _create_parallel_node(self, node: NodeDefinition) -> Callable:
        """创建并行节点 (标记开始)"""
        node_id = node.id
        node_label = node.label or node_id

        def parallel_node(state):
            logger.info(f"[节点执行] ⚡ {node_id} ({node_label}) - 并行开始")
            return {"_parallel_start": node_id}
        return parallel_node

    def _create_merge_node(self, node: NodeDefinition) -> Callable:
        """创建合并节点"""
        node_id = node.id
        node_label = node.label or node_id

        def merge_node(state):
            logger.info(f"[节点执行] 🔗 {node_id} ({node_label}) - 合并完成")
            return {"_parallel_end": node_id}
        return merge_node

    def _create_debate_node(self, node: NodeDefinition) -> Callable:
        """
        创建辩论节点 - 协调多个参与者进行多轮辩论

        辩论节点本身不执行分析，而是初始化辩论状态。
        实际的辩论流程通过条件边控制。

        注意：使用 operator.add 作为 reducer，所以不需要初始化计数为0
        """
        participants = node.config.get("participants", [])
        rounds = node.config.get("rounds", 1)
        node_id = node.id
        node_label = node.label or node_id

        def debate_node(state):
            logger.info(f"[节点执行] 💬 {node_id} ({node_label}) - 辩论开始, 参与者: {participants}")
            return {
                f"{node_id}_status": "debate_started",
                "_debate_node": node_id,
                "_debate_participants": participants,
                "_debate_rounds": rounds,
            }
        return debate_node

    def _create_debate_participant_wrapper(
        self,
        node: NodeDefinition,
        debate_key: str
    ) -> Callable:
        """
        为辩论参与者包装执行函数，自动递增辩论计数

        使用 operator.add 作为 reducer，每次返回增量 1
        """
        original_func = self._create_agent_node(node)

        def wrapped(state):
            # 先执行原始函数（已包含日志）
            result = original_func(state)
            # 返回增量 1（会被 operator.add 累加到当前值）
            result[debate_key] = 1
            return result

        return wrapped

    def _add_edges(
        self,
        graph: StateGraph,
        definition: WorkflowDefinition,
        debate_configs: Optional[Dict[str, Dict[str, Any]]] = None
    ) -> None:
        """
        添加边到图

        辩论流程设计：
        - 辩论节点 → 第一个参与者（普通边）
        - 参与者之间使用条件边（检查计数决定继续或结束）
        - 最后一个参与者 → 下一阶段（通过条件边控制）
        """
        start_node = definition.get_start_node()
        added_edges: Set[tuple] = set()

        if debate_configs is None:
            debate_configs = self._identify_debate_configs(definition)

        # 收集所有辩论参与者
        all_participants: Set[str] = set()
        for config in debate_configs.values():
            all_participants.update(config["participants"])

        # 添加 START 边
        if start_node:
            for edge in definition.get_edges_from(start_node.id):
                graph.add_edge(START, edge.target)

        # 1. 先处理辩论流程的边
        for debate_id, config in debate_configs.items():
            participants = config["participants"]

            # 辩论节点 → 第一个参与者
            graph.add_edge(debate_id, participants[0])
            added_edges.add((debate_id, participants[0]))

            # 为每个参与者添加条件边
            for i, participant in enumerate(participants):
                self._add_participant_conditional_edge(
                    graph, participant, config, i, debate_id
                )
                # 标记所有从参与者出发的边为已处理
                for edge in definition.get_edges_from(participant):
                    added_edges.add((participant, edge.target))

        # 2. 处理普通边
        for edge in definition.edges:
            source_node = definition.get_node(edge.source)
            target_node = definition.get_node(edge.target)

            if source_node is None or target_node is None:
                continue
            if source_node.type == NodeType.START:
                continue

            edge_key = (edge.source, edge.target)
            if edge_key in added_edges:
                continue

            # 跳过辩论节点的所有出边（已在上面处理）
            if source_node.type == NodeType.DEBATE:
                continue

            # 跳过参与者的边（已在上面处理）
            if source_node.id in all_participants:
                continue

            # 普通边
            if target_node.type == NodeType.END:
                graph.add_edge(edge.source, END)
            elif edge.type == EdgeType.CONDITIONAL:
                self._add_conditional_edge(graph, edge, definition)
            else:
                graph.add_edge(edge.source, edge.target)
            added_edges.add(edge_key)

    def _add_participant_conditional_edge(
        self,
        graph: StateGraph,
        participant: str,
        debate_config: Dict[str, Any],
        participant_index: int,
        debate_id: str
    ) -> None:
        """为辩论参与者添加条件边"""
        participants = debate_config["participants"]
        max_rounds = int(debate_config["rounds"]) if debate_config["rounds"] else 1
        next_node = debate_config["next_node"]
        debate_key = debate_config["debate_key"]
        num_participants = len(participants)

        # 下一个参与者
        next_idx = (participant_index + 1) % num_participants
        next_participant = participants[next_idx]

        # 根据辩论类型选择动态轮数的 state key
        # "risk" 相关的辩论使用 _max_risk_rounds，其他使用 _max_debate_rounds
        is_risk_debate = "risk" in debate_id.lower()
        dynamic_rounds_key = "_max_risk_rounds" if is_risk_debate else "_max_debate_rounds"

        # 创建路由函数
        def create_router(
            _debate_key: str,
            _max_rounds: int,
            _next_participant: str,
            _next_node: str,
            _num_participants: int,
            _dynamic_rounds_key: str,
            _participant: str
        ):
            def router(state):
                count = state.get(_debate_key, 0)
                dynamic_rounds = state.get(_dynamic_rounds_key, _max_rounds)
                max_count = dynamic_rounds * _num_participants
                logger.info(
                    f"[辩论路由] {_participant}: count={count}, max={max_count} "
                    f"(rounds={dynamic_rounds}, participants={_num_participants})"
                )
                if count >= max_count:
                    logger.info(f"[辩论路由] {_participant} -> {_next_node} (辩论结束)")
                    return _next_node if _next_node else END
                logger.info(f"[辩论路由] {_participant} -> {_next_participant} (继续辩论)")
                return _next_participant
            return router

        router = create_router(
            debate_key, max_rounds, next_participant, next_node,
            num_participants, dynamic_rounds_key, participant
        )

        targets = [next_participant]
        if next_node and next_node != next_participant:
            targets.append(next_node)

        graph.add_conditional_edges(participant, router, targets)

    def _identify_debate_configs(
        self, definition: WorkflowDefinition
    ) -> Dict[str, Dict[str, Any]]:
        """识别工作流中的辩论配置"""
        debate_configs = {}

        for node in definition.nodes:
            if node.type == NodeType.DEBATE:
                participants = node.config.get("participants", [])
                rounds_raw = node.config.get("rounds", 1)

                # 处理 rounds 可能是字符串的情况（如 "auto", "1" 等）
                if isinstance(rounds_raw, str):
                    if rounds_raw.lower() == "auto" or not rounds_raw.isdigit():
                        rounds = 1  # 默认1轮，实际会从 state 读取
                    else:
                        rounds = int(rounds_raw)
                else:
                    rounds = int(rounds_raw) if rounds_raw else 1

                # 找到辩论后的下一个节点
                next_node = None
                for edge in definition.get_edges_from(node.id):
                    target = definition.get_node(edge.target)
                    if target and target.id not in participants:
                        next_node = edge.target
                        break

                debate_configs[node.id] = {
                    "participants": participants,
                    "rounds": rounds,
                    "next_node": next_node,
                    "debate_key": f"_debate_{node.id}_count"
                }

        return debate_configs

    def _add_conditional_edge(
        self,
        graph: StateGraph,
        edge: EdgeDefinition,
        definition: WorkflowDefinition
    ) -> None:
        """添加普通条件边"""
        all_edges = definition.get_edges_from(edge.source)

        def route(state):
            result = state.get("_condition_result", True)
            for e in all_edges:
                if e.condition == "true" and result:
                    return e.target
                if e.condition == "false" and not result:
                    return e.target
            return all_edges[0].target if all_edges else END

        targets = {e.target for e in all_edges}
        graph.add_conditional_edges(edge.source, route, list(targets))

