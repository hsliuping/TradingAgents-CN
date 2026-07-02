"""
Agent Builder LangGraph 工作流定义

定义 Agent Builder 创建流程的有向图。

原理：
- 节点是构建阶段（需求探索、确认、能力盘点、方案、生成、测试）
- 边是条件分支（用户确认、修改、取消、选择方案 A/B/C）
- 状态由 MongoDB checkpoint 持久化
- LLM 只在节点内负责沟通和工具调用
"""

from __future__ import annotations

import logging
from typing import Any, Callable, Optional

from langgraph.graph import StateGraph, START, END

from core.embedded_nanobot.workflows.agent_builder_state import AgentBuilderState
from core.embedded_nanobot.workflows import (
    agent_builder_nodes as nodes,
    agent_builder_conditions as conditions,
)

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────────────────────
# 图构建
# ──────────────────────────────────────────────────────────────

def build_agent_builder_graph() -> StateGraph:
    """构建 Agent Builder 工作流图。

    返回一个编译好的 StateGraph，可直接调用 ainvoke()。
    """
    graph = StateGraph(AgentBuilderState)

    # ── 注册节点 ──
    # LLM 意图分类（从 wait 节点恢复时先跑这个）
    graph.add_node("classify_intent", _make_node_wrapper(nodes.node_classify_user_intent))

    # 需求阶段
    graph.add_node("requirement_intake", _make_node_wrapper(nodes.node_requirement_intake))
    graph.add_node("wait_intake_confirmation", _make_node_wrapper(nodes.node_wait_intake_confirmation))
    graph.add_node("requirement_confirmation", _make_node_wrapper(nodes.node_requirement_confirmation))
    graph.add_node("wait_requirement_confirmation", _make_node_wrapper(nodes.node_wait_requirement_confirmation))

    # 缺口分析阶段
    graph.add_node("gap_analysis", _make_node_wrapper(nodes.node_gap_analysis))

    # 方案阶段
    graph.add_node("plan_generation", _make_node_wrapper(nodes.node_plan_generation))
    graph.add_node("wait_plan_selection", _make_node_wrapper(nodes.node_wait_plan_selection))

    # 生成阶段
    graph.add_node("generate_candidate_agent", _make_node_wrapper(nodes.node_generate_candidate_agent))
    graph.add_node("build_or_ready", _make_node_wrapper(nodes.node_build_or_ready))

    # 测试阶段
    graph.add_node("wait_test_request", _make_node_wrapper(nodes.node_wait_test_request))
    graph.add_node("real_data_test", _make_node_wrapper(nodes.node_real_data_test))

    # 评估 / 发布（测试后等待用户决策）
    graph.add_node("wait_evaluation", _make_node_wrapper(nodes.node_wait_evaluation))
    graph.add_node("evaluate_or_publish", _make_node_wrapper(nodes.node_evaluate_or_publish))
    graph.add_node("iterate_agent_version", _make_node_wrapper(nodes.node_iterate_agent_version))

    # 错误恢复
    graph.add_node("error_recovery", _make_node_wrapper(nodes.node_error_recovery))

    # ── 注册边 ──

    # START → 根据 current_node 决定是新会话还是恢复
    graph.add_conditional_edges(
        START,
        conditions.route_start,
        {
            "classify_intent": "classify_intent",
            "requirement_intake": "requirement_intake",
            "requirement_confirmation": "requirement_confirmation",
            "wait_intake_confirmation": "wait_intake_confirmation",
            "wait_requirement_confirmation": "wait_requirement_confirmation",
            "gap_analysis": "gap_analysis",
            "plan_generation": "plan_generation",
            "wait_plan_selection": "wait_plan_selection",
            "generate_candidate_agent": "generate_candidate_agent",
            "build_or_ready": "build_or_ready",
            "wait_test_request": "wait_test_request",
            "real_data_test": "real_data_test",
            "evaluate_or_publish": "evaluate_or_publish",
            "iterate_agent_version": "iterate_agent_version",
            "wait_evaluation": "wait_evaluation",
            "error_recovery": "error_recovery",
            "end": END,
        },
    )

    # classify_intent → 根据 LLM 意图分类结果路由
    graph.add_conditional_edges(
        "classify_intent",
        conditions.route_after_classify,
        {
            "requirement_intake": "requirement_intake",
            "requirement_confirmation": "requirement_confirmation",
            "wait_intake_confirmation": "wait_intake_confirmation",
            "wait_requirement_confirmation": "wait_requirement_confirmation",
            "gap_analysis": "gap_analysis",
            "plan_generation": "plan_generation",
            "generate_candidate_agent": "generate_candidate_agent",
            "wait_plan_selection": "wait_plan_selection",
            "real_data_test": "real_data_test",
            "wait_test_request": "wait_test_request",
            "evaluate_or_publish": "evaluate_or_publish",
            "iterate_agent_version": "iterate_agent_version",
            "wait_evaluation": "wait_evaluation",
            "error_recovery": "error_recovery",
            "build_or_ready": "build_or_ready",
            "end": END,
        },
    )

    # 需求探索后
    graph.add_conditional_edges(
        "requirement_intake",
        conditions.route_after_intake,
        {
            "requirement_confirmation": "requirement_confirmation",
            "wait_intake_confirmation": "wait_intake_confirmation",
            "end": END,
        },
    )

    # 等待需求确认 → 终端
    graph.add_edge("wait_intake_confirmation", END)

    # 需求确认后
    graph.add_edge("requirement_confirmation", "wait_requirement_confirmation")

    # 等待需求边界确认 → 终端
    graph.add_edge("wait_requirement_confirmation", END)

    # gap 分析 → 方案生成
    graph.add_edge("gap_analysis", "plan_generation")

    # 方案生成 → 等待选择
    graph.add_edge("plan_generation", "wait_plan_selection")

    # 等待方案选择 → 终端
    graph.add_edge("wait_plan_selection", END)

    # 生成 Agent 后
    graph.add_conditional_edges(
        "generate_candidate_agent",
        conditions.route_after_generate,
        {
            "wait_test_request": "wait_test_request",
            "build_or_ready": "build_or_ready",
            "error_recovery": "error_recovery",
        },
    )

    # 构建后
    graph.add_conditional_edges(
        "build_or_ready",
        conditions.route_after_build,
        {
            "wait_test_request": "wait_test_request",
            "error_recovery": "error_recovery",
        },
    )

    # 等待测试请求 → 终端
    graph.add_edge("wait_test_request", END)

    # 测试后 → 等待用户决策（不再自动发布）
    graph.add_conditional_edges(
        "real_data_test",
        conditions.route_after_test,
        {
            "wait_evaluation": "wait_evaluation",
            "error_recovery": "error_recovery",
        },
    )

    # 等待评估决策 → 终端
    graph.add_edge("wait_evaluation", END)

    # 版本迭代创建后 → 终端，等待用户继续补充/确认升级需求
    graph.add_edge("iterate_agent_version", END)

    # 评估/发布后 → 终端
    graph.add_edge("evaluate_or_publish", END)

    # 错误恢复 → 终端
    graph.add_edge("error_recovery", END)

    return graph.compile()


# ──────────────────────────────────────────────────────────────
# 节点包装器
# ──────────────────────────────────────────────────────────────

def _make_node_wrapper(node_func):
    """将节点函数包装为 LangGraph 节点。

    根据节点函数签名动态注入参数。
    - action 节点：注入 tool_registry, llm_client, event_callback, on_stream
    - wait 节点：只注入 event_callback, on_stream
    """
    import inspect
    sig = inspect.signature(node_func)
    param_names = set(sig.parameters.keys())
    node_name = node_func.__name__

    async def wrapper(state: AgentBuilderState) -> AgentBuilderState:
        logger.info("[Node][Enter] %s stage=%s spec=%s", node_name, state.get("stage", ""), state.get("spec_id", ""))

        kwargs = {"state": state}

        if "event_callback" in param_names:
            kwargs["event_callback"] = state.get("_event_callback")
        if "on_stream" in param_names:
            kwargs["on_stream"] = state.get("_on_stream")
        if "tool_registry" in param_names:
            kwargs["tool_registry"] = state.get("_tool_registry")
        if "llm_client" in param_names:
            kwargs["llm_client"] = state.get("_llm_client")

        result = await node_func(**kwargs)

        logger.info(
            "[Node][Exit] %s → stage=%s awaiting=%s pending=%s",
            node_name,
            result.get("stage", ""),
            result.get("awaiting_user", False),
            result.get("pending_question", "")[:80],
        )
        return result

    return wrapper


# ──────────────────────────────────────────────────────────────
# 图执行器
# ──────────────────────────────────────────────────────────────

async def execute_graph(
    graph: StateGraph,
    state: AgentBuilderState,
    tool_registry: Any,
    llm_client: Any,
    event_callback: Optional[Callable] = None,
    on_stream: Optional[Callable] = None,
    max_steps: int = 10,
) -> AgentBuilderState:
    """执行 Agent Builder 图。

    在 state 中注入运行时依赖，然后执行图。
    遇到 wait_* 节点时暂停，保存 checkpoint。

    返回最终 state。
    """
    # 注入运行时依赖
    state["_tool_registry"] = tool_registry
    state["_llm_client"] = llm_client
    state["_event_callback"] = event_callback
    state["_on_stream"] = on_stream

    logger.info(
        "[Graph][Invoke] node=%s stage=%s awaiting=%s",
        state.get("current_node", "START"),
        state.get("stage", "?"),
        state.get("awaiting_user", False),
    )

    # 图执行：START → route_start → ... → wait_* → END
    # 不需要循环，图一次性跑完
    result = await graph.ainvoke(
        state,
        config={"recursion_limit": 50},
    )

    logger.info(
        "[Graph][Done] node=%s stage=%s awaiting=%s",
        result.get("current_node", "?"),
        result.get("stage", "?"),
        result.get("awaiting_user", False),
    )

    return result