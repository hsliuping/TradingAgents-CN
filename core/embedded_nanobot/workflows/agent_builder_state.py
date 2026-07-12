"""
Agent Builder 工作流状态模型

定义 LangGraph Agent Builder 图的状态结构。
状态是图的唯一事实源，不能由 LLM 直接决定结构化字段。
"""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Optional, TypedDict


class AgentBuilderState(TypedDict, total=False):
    """Agent Builder 工作流状态。

    约定：
    - stage / current_node 是唯一阶段事实源
    - pending_options 只能由 plan_generation 节点写入
    - selected_plan_id 只能由 wait_plan_selection 条件函数写入
    - gap_report 只能由 gap_analysis 写入
    - generated_agent 只能由 generate_candidate_agent 写入
    """

    # ── 会话标识 ──
    thread_id: str
    user_id: str
    user_message: str
    channel: str
    chat_id: str

    # ── 图状态 ──
    current_node: str
    stage: str
    awaiting_user: bool
    pending_question: str
    clarification_needed: bool  # 意图无法识别时，让 wait 节点输出澄清提示而非重复上轮内容
    skill_creation_requested: bool  # 用户要求补齐缺失 skill 时设置，让 wait 节点输出 skill 创建提示

    # ── LLM 意图分类（由 classify_intent 节点写入） ──
    user_intent: str  # confirmed / revise / select_option / explore_more / cancel / new_agent / retry
    user_selected_index: int  # LLM 解析的选中方案序号
    user_selected_id: str  # LLM 解析的选中方案 ID
    intent_confidence: float  # LLM 意图分类置信度 (0.0-1.0)
    intent_reason: str  # LLM 意图分类推理说明

    # ── 需求阶段 ──
    spec_id: str
    spec_name: str
    requirement_summary: str
    confirmation_brief: dict
    original_user_request: str
    proposed_plan: dict

    # ── 能力盘点 ──
    capability_inventory: dict
    gap_report: dict

    # ── 方案阶段 ──
    candidate_plans: list
    pending_options: list
    recommended_plan_id: str
    selected_plan_id: str
    acknowledged_gaps: list

    # ── 生成阶段 ──
    generated_agent: dict
    workshop_session_id: str
    version_id: str
    build_status: str
    decision_context: dict  # 版本冲突/迭代决策上下文（pending_user_decision / pending_iteration_decision）

    # ── 测试阶段 ──
    test_symbol: str
    test_result: dict
    official_acceptance_decision: str

    # ── 错误恢复 ──
    errors: list

    # ── 对话记忆 ──
    conversation_summary: str
    tool_events: list
    final_response: str
    message_history: list  # [{role, content}] 最近 N 轮对话，供 LLM 意图分类用

    # ── 运行时注入（不持久化） ──
    _tool_registry: Any
    _llm_client: Any  # UnifiedLLMClient 实例（替代旧的 _provider + _model）
    _event_callback: Any
    _on_stream: Any


def new_agent_builder_state(
    thread_id: str = "",
    user_id: str = "",
    user_message: str = "",
    channel: str = "",
    chat_id: str = "",
) -> AgentBuilderState:
    """创建初始状态。"""
    return AgentBuilderState(
        thread_id=thread_id,
        user_id=user_id,
        user_message=user_message,
        channel=channel,
        chat_id=chat_id,
        current_node="START",
        stage="",
        awaiting_user=False,
        pending_question="",
        clarification_needed=False,
        skill_creation_requested=False,
        spec_id="",
        spec_name="",
        requirement_summary="",
        confirmation_brief={},
        capability_inventory={},
        gap_report={},
        candidate_plans=[],
        pending_options=[],
        recommended_plan_id="",
        selected_plan_id="",
        acknowledged_gaps=[],
        generated_agent={},
        workshop_session_id="",
        version_id="",
        build_status="",
        decision_context={},
        test_symbol="",
        test_result={},
        official_acceptance_decision="",
        errors=[],
        conversation_summary="",
        tool_events=[],
        final_response="",
        message_history=[],
    )