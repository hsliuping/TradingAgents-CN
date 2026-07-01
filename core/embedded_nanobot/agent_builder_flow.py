"""
Agent Builder 流程状态机

定义从用户意图到 Agent 发布的完整状态机，确保 Nanobot 在框架内行事：
  - 每个阶段明确允许 / 禁止的操作
  - 知道下一步应该做什么
  - 防止阶段跳变和重复操作

这是 IntentContext 的补充层：
  - IntentContext: 记录"现在在做什么、为谁做"
  - FlowController: 规定"现在能做什么、不能做什么、下一步去哪"

设计的核心原则：
  1. 只有框架定义的状态转换路径，不允许 LLM 自行跳跃
  2. 每个阶段明确禁止的操作，直接注入 System Prompt
  3. 不影响普通聊天（仅有 spec_id 的 Agent Builder 流程才触发）
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

from core.embedded_nanobot.intent_context import IntentContext, IntentStage, IntentAction

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────────────────────
# 流程阶段（覆盖 IntentStage，新增派生状态）
# ──────────────────────────────────────────────────────────────
class FlowPhase(str, Enum):
    """比 IntentStage 更细粒度的流程阶段，包含派生状态。"""
    # ── 无 Agent ──
    IDLE = "idle"

    # ── 需求阶段 ──
    EXPLORING = "exploring"
    DRAFT_PREPARING = "draft_preparing"
    REQUIREMENT_CONFIRMATION_PENDING = "requirement_confirmation_pending"
    CAPABILITY_CHECK = "capability_check"
    PLAN_SELECTION_PENDING = "plan_selection_pending"
    CONFIRMATION_PENDING = "confirmation_pending"  # 兼容旧名

    # ── 生成与构建 ──
    GENERATING = "generating"
    READY_TO_BUILD = "ready_to_build"  # Draft 已生成，但版本尚未构建
    BUILDING = "building"        # 版本已构建/正在构建

    # ── 测试与评估 ──
    TESTING = "testing"          # 等待测试或测试已完成、待评估
    EVALUATING = "evaluating"    # 评估结果已出

    # ── 缺口补齐 ──
    GAP_RESOLVING = "gap_resolving"

    # ── 迭代 ──
    ITERATING = "iterating"

    # ── 发布 ──
    PUBLISHING = "publishing"
    PUBLISHED = "published"


# ──────────────────────────────────────────────────────────────
# 工具标识（用于允许/禁止列表）
# ──────────────────────────────────────────────────────────────
_TOOL = {
    "search_capability": "search_project_capabilities",
    "prepare_intake": "prepare_agent_requirement_intake",
    "prepare_confirmation": "prepare_agent_generation_confirmation",
    "propose_plans": "propose_agent_build_plans",
    "generate_confirmed": "generate_confirmed_candidate_agent",
    "analyze_gaps": "analyze_agent_workshop_gaps",
    "build_version": "build_agent_workshop_version",
    "debug_version": "debug_agent_workshop_version",
    "real_data_test": "run_agent_workshop_real_data_test",
    "evaluate_version": "evaluate_agent_workshop_version",
    "iterate_version": "iterate_agent_workshop_version",
    "publish_version": "publish_agent_workshop_version",
    "resolve_gaps": "resolve_agent_workshop_blocking_gaps",
    "start_gap_resolution": "start_agent_workshop_gap_resolution",
    "inspect_gap_resolution": "inspect_agent_workshop_gap_resolution",
    "cancel_gap_resolution": "cancel_agent_workshop_gap_resolution",
    "retry_gap_resolution": "retry_agent_workshop_gap_resolution_item",
    "generate_tooling_plan": "generate_agent_workshop_tooling_plan",
    "inspect_assets": "inspect_agent_workshop_assets",
    "inspect_runtime": "inspect_runtime_agent_configs",
    "inspect_blueprints": "inspect_agent_blueprints",
    "create_draft": "create_or_update_agent_workshop_draft",
}

# ──────────────────────────────────────────────────────────────
# 阶段定义
# ──────────────────────────────────────────────────────────────

@dataclass
class PhaseRule:
    """单个流程阶段的规则。"""
    phase: FlowPhase
    description: str
    allowed_tools: List[str] = field(default_factory=list)
    forbidden_tools: List[str] = field(default_factory=list)
    recommended_next_tool: str = ""
    recommended_next_phase: FlowPhase | None = None
    preconditions: List[str] = field(default_factory=list)
    notes: List[str] = field(default_factory=list)
    # 阶段转换条件（阶段 → 条件 → 新阶段）
    transitions: List[Tuple[str, FlowPhase]] = field(default_factory=list)


# ──────────────────────────────────────────────────────────────
# ITERATING 阶段动态推荐（依赖 PHASE_TABLE，定义在表前）
# ──────────────────────────────────────────────────────────────
def _derive_iterating_recommendation(intent: IntentContext) -> Tuple[str, str, str]:
    """根据最近一次评估证据，推导 ITERATING 阶段的推荐路径。

    返回：(recommended_tool_id, guidance_text, next_phase_hint)
    """
    cats = set((intent.last_evaluation_categories or []))
    decision = str(intent.last_evaluation_decision or "").strip().lower()
    blockers = intent.last_evaluation_blockers or []

    # 1. 缺能力 / 关键工具未调用 → 补能力
    capability_markers = {"tool_usage"}
    if cats & capability_markers or any("缺口" in b or "能力" in b or "工具" in b for b in blockers):
        return (
            _TOOL["resolve_gaps"],
            "评估证据表明当前版本缺少关键能力或关键工具未被调用。应优先检查/补齐能力缺口，必要时生成/复用 Skill，而不是只改 Prompt。",
            "补齐缺口后回到 BUILDING/READY_TO_BUILD，再测试。",
        )

    # 2. 运行失败 / 缺少运行结果 / 样本问题 → 重跑测试
    rerun_markers = {"runtime_output"}
    if cats & rerun_markers or any(
        kw in " ".join(blockers) for kw in ("运行结果", "样本", "输入偏离", "runtime")
    ):
        return (
            _TOOL["real_data_test"],
            "评估证据指向本次运行本身失败或样本/输入异常。建议先重跑真数据测试，确认问题是否可复现，再决定是否改 Agent。",
            "重跑测试后进入 EVALUATING。",
        )

    # 3. 执行计划 / 输出字段 / 约束 / 可追溯性 / Prompt 绑定 → 迭代版本
    iterate_markers = {"execution_plan", "output_coverage", "reasoning_quality", "constraint_control", "numeric_traceability", "project_memory_binding"}
    if cats & iterate_markers or decision in ("revise", "reject"):
        return (
            _TOOL["iterate_version"],
            "评估证据指向 Prompt、执行计划、输出格式、约束控制或项目记忆绑定问题。应使用 iterate_agent_workshop_version 针对性修改版本，然后重新测试。",
            "迭代后回到 TESTING。",
        )

    # 兜底
    return (
        _TOOL["iterate_version"],
        "评估未通过。请先查看评估报告的具体证据，再选择：补能力（resolve_gaps）、重跑测试（real_data_test）或迭代版本（iterate_version）。",
        "改进后回到 TESTING。",
    )


def _looks_like_plan_selection(user_message: str) -> bool:
    """判断用户本轮是否在选择/确认方案。"""
    text = str(user_message or "").strip().lower()
    if not text:
        return False
    normalized = re.sub(r"\s+", "", text)
    keywords = (
        "方案a", "选a", "选择a", "a方案", "第一个", "第1个", "选第一个",
        "推荐方案", "按推荐", "按这个", "就这个", "可以开始生成", "开始生成",
        "生成agent", "生成 agent", "直接生成", "确认生成", "可以生成",
    )
    if any(k.lower().replace(" ", "") in normalized for k in keywords):
        return True
    if normalized in {"a", "1", "方案1", "方案一", "确认", "可以", "好的", "行", "没问题"}:
        return True
    return False


def _resolve_selected_plan_id(intent: IntentContext, user_message: str) -> str:
    """从用户回复和 pending_options 中解析 selected_plan_id。"""
    text = str(user_message or "").strip().lower()
    normalized = re.sub(r"\s+", "", text)
    if not intent.pending_options:
        return ""

    index_map = {"a": 1, "b": 2, "c": 3, "d": 4}
    selected_index = 0
    for letter, idx in index_map.items():
        if f"方案{letter}" in normalized or f"选{letter}" in normalized or f"选择{letter}" in normalized or normalized == letter:
            selected_index = idx
            break
    if not selected_index:
        if "第一个" in normalized or "第1个" in normalized or normalized in {"1", "方案1", "方案一"}:
            selected_index = 1
        elif "第二个" in normalized or "第2个" in normalized or normalized in {"2", "方案2", "方案二"}:
            selected_index = 2
        elif "第三个" in normalized or "第3个" in normalized or normalized in {"3", "方案3", "方案三"}:
            selected_index = 3

    if selected_index:
        for opt in intent.pending_options:
            if int(opt.get("index") or 0) == selected_index:
                return str(opt.get("id") or "").strip()

    if "推荐" in normalized or "按这个" in normalized or "可以" in normalized or "确认" in normalized or "开始生成" in normalized:
        for opt in intent.pending_options:
            if opt.get("recommended"):
                return str(opt.get("id") or "").strip()
        return str(intent.pending_options[0].get("id") or "").strip()

    return ""


def get_plan_selection_decision(intent: IntentContext, user_message: str) -> Dict[str, Any]:
    """返回方案选择阶段的结构化路由判断，供 runtime 做兜底执行。"""
    user_is_selecting = _looks_like_plan_selection(user_message)
    selected_plan_id = _resolve_selected_plan_id(intent, user_message)
    if intent.stage != FlowPhase.PLAN_SELECTION_PENDING.value:
        return {
            "active": False,
            "pending_options_count": len(intent.pending_options),
            "user_is_selecting": user_is_selecting,
            "selected_plan_id": selected_plan_id,
            "recommended_tool": "",
        }
    if intent.pending_options and selected_plan_id:
        recommended_tool = _TOOL["generate_confirmed"]
    elif intent.pending_options:
        recommended_tool = _TOOL["generate_confirmed"]
    else:
        recommended_tool = _TOOL["propose_plans"]
    return {
        "active": True,
        "pending_options_count": len(intent.pending_options),
        "user_is_selecting": user_is_selecting,
        "selected_plan_id": selected_plan_id,
        "recommended_tool": recommended_tool,
    }


# ── 阶段定义表 ──────────────────────────────────────────────

PHASE_TABLE: Dict[FlowPhase, PhaseRule] = {
    FlowPhase.IDLE: PhaseRule(
        phase=FlowPhase.IDLE,
        description="未选中任何 Agent",
        allowed_tools=[
            _TOOL["search_capability"],
            _TOOL["prepare_intake"],
            _TOOL["inspect_assets"],
            _TOOL["inspect_runtime"],
            _TOOL["inspect_blueprints"],
        ],
        forbidden_tools=[
            _TOOL["analyze_gaps"],
            _TOOL["build_version"],
            _TOOL["real_data_test"],
            _TOOL["publish_version"],
            _TOOL["generate_confirmed"],
            _TOOL["resolve_gaps"],
        ],
        recommended_next_phase=FlowPhase.EXPLORING,
        preconditions=["无"],
        notes=["用户可以自由探索，但不能操作具体 Agent。",
               "用户表达创建 Agent 意图后进入 EXPLORING。"],
    ),

    FlowPhase.EXPLORING: PhaseRule(
        phase=FlowPhase.EXPLORING,
        description="需求探索：用户描述想要什么样的 Agent",
        allowed_tools=[
            _TOOL["search_capability"],
            _TOOL["prepare_intake"],
            _TOOL["inspect_assets"],
            _TOOL["inspect_runtime"],
            _TOOL["inspect_blueprints"],
        ],
        forbidden_tools=[
            _TOOL["analyze_gaps"],
            _TOOL["build_version"],
            _TOOL["real_data_test"],
            _TOOL["publish_version"],
            _TOOL["generate_confirmed"],
            _TOOL["resolve_gaps"],
            _TOOL["prepare_confirmation"],
            _TOOL["propose_plans"],
        ],
        recommended_next_tool=_TOOL["prepare_intake"],
        recommended_next_phase=FlowPhase.DRAFT_PREPARING,
        preconditions=["用户表达了创建 Agent 的意图"],
        notes=["先以财经产品专家的身份给出默认方案草稿（抛砖引玉），然后调用 prepare_agent_requirement_intake 将需求结构化。",
               "不要在此阶段直接口头确认或生成，必须通过工具结构化。",
               "可以使用 search_project_capabilities 了解现有能力。"],
    ),

    FlowPhase.DRAFT_PREPARING: PhaseRule(
        phase=FlowPhase.DRAFT_PREPARING,
        description="准备需求确认稿：整理职责、输出形态、排除项，等待用户确认需求",
        allowed_tools=[
            _TOOL["prepare_confirmation"],
            _TOOL["search_capability"],
            _TOOL["inspect_assets"],
            _TOOL["inspect_runtime"],
        ],
        forbidden_tools=[
            _TOOL["generate_confirmed"],
            _TOOL["analyze_gaps"],
            _TOOL["propose_plans"],
            _TOOL["build_version"],
            _TOOL["real_data_test"],
            _TOOL["publish_version"],
            _TOOL["resolve_gaps"],
            _TOOL["iterate_version"],
        ],
        recommended_next_tool=_TOOL["prepare_confirmation"],
        recommended_next_phase=FlowPhase.REQUIREMENT_CONFIRMATION_PENDING,
        preconditions=["需求基本明确"],
        notes=["prepare_agent_generation_confirmation 只输出需求确认稿（职责、输出、非目标），不展示工具候选，不做 gap 分析。",
               "用户确认需求后进入 CAPABILITY_CHECK 做能力盘点。",
               "未确认需求前不得调用 analyze_agent_workshop_gaps 或 propose_agent_build_plans。"],
    ),

    FlowPhase.REQUIREMENT_CONFIRMATION_PENDING: PhaseRule(
        phase=FlowPhase.REQUIREMENT_CONFIRMATION_PENDING,
        description="等待用户确认需求：需求确认稿已展示，等待用户确认或修改需求",
        allowed_tools=[
            _TOOL["search_capability"],
            _TOOL["inspect_assets"],
            _TOOL["inspect_runtime"],
        ],
        forbidden_tools=[
            _TOOL["generate_confirmed"],
            _TOOL["analyze_gaps"],
            _TOOL["propose_plans"],
            _TOOL["prepare_confirmation"],  # ← 禁止重新确认！需求已确认进入能力盘点
            _TOOL["build_version"],
            _TOOL["real_data_test"],
            _TOOL["publish_version"],
            _TOOL["resolve_gaps"],
            _TOOL["iterate_version"],
        ],
        recommended_next_phase=FlowPhase.CAPABILITY_CHECK,
        preconditions=["需求确认稿已展示"],
        transitions=[
            ("用户确认需求", FlowPhase.CAPABILITY_CHECK),
            ("用户修改需求", FlowPhase.EXPLORING),
        ],
        notes=["用户回复'确认'后，进入 CAPABILITY_CHECK 开始做能力盘点和 gap 分析。",
               "用户修改需求时回到 EXPLORING，不要重新调用 prepare_agent_generation_confirmation。",
               "此阶段不要展示任何工具、能力或方案。"],
    ),

    FlowPhase.CAPABILITY_CHECK: PhaseRule(
        phase=FlowPhase.CAPABILITY_CHECK,
        description="能力盘点：扫描现有工具/Skill，运行真实 gap 分析",
        allowed_tools=[
            _TOOL["create_draft"],
            _TOOL["search_capability"],
            _TOOL["analyze_gaps"],
            _TOOL["inspect_assets"],
            _TOOL["inspect_runtime"],
        ],
        forbidden_tools=[
            _TOOL["generate_confirmed"],
            _TOOL["prepare_confirmation"],
            _TOOL["propose_plans"],
            _TOOL["build_version"],
            _TOOL["real_data_test"],
            _TOOL["publish_version"],
            _TOOL["resolve_gaps"],
            _TOOL["iterate_version"],
        ],
        recommended_next_tool=_TOOL["analyze_gaps"],
        recommended_next_phase=FlowPhase.PLAN_SELECTION_PENDING,
        preconditions=["用户已确认需求"],
        notes=["先用 search_project_capabilities 扫描可用工具/Skill。",
               "再调用 analyze_agent_workshop_gaps 做真实 gap 分析。",
               "能力盘点完成后调用 propose_agent_build_plans 生成候选方案。",
               "不要在此阶段直接生成、构建、测试或发布。"],
    ),

    FlowPhase.PLAN_SELECTION_PENDING: PhaseRule(
        phase=FlowPhase.PLAN_SELECTION_PENDING,
        description="方案阶段：基于 gap 结果生成候选方案并等待用户选择",
        allowed_tools=[
            _TOOL["propose_plans"],
            _TOOL["generate_confirmed"],
            _TOOL["search_capability"],
            _TOOL["inspect_assets"],
        ],
        forbidden_tools=[
            _TOOL["analyze_gaps"],
            _TOOL["prepare_confirmation"],
            _TOOL["build_version"],
            _TOOL["real_data_test"],
            _TOOL["publish_version"],
            _TOOL["resolve_gaps"],
            _TOOL["iterate_version"],
            _TOOL["debug_version"],
        ],
        recommended_next_tool=_TOOL["propose_plans"],
        recommended_next_phase=FlowPhase.GENERATING,
        preconditions=["已完成能力盘点和 gap 分析"],
        transitions=[
            ("已生成候选方案但用户尚未选择", FlowPhase.PLAN_SELECTION_PENDING),
            ("用户选择 direct/complete/quick 并确认", FlowPhase.GENERATING),
            ("用户选择 narrow/缩小需求范围", FlowPhase.EXPLORING),
            ("用户质疑 gap 或要求重新盘点", FlowPhase.CAPABILITY_CHECK),
            ("用户要求修改需求", FlowPhase.EXPLORING),
        ],
        notes=["如果候选方案尚未结构化生成，先调用 propose_agent_build_plans 生成 A/B/C 方案并写入 pending_options。",
               "如果用户已经说‘开始生成/方案A/按推荐’，但 pending_options 为空，也必须先调用 propose_agent_build_plans 补齐结构化方案状态；禁止口头重复方案或重新做能力盘点。",
               "候选方案生成后，等待用户选择；用户选择方案后调用 generate_confirmed_candidate_agent。",
               "❌ 禁止调用 prepare_agent_generation_confirmation 重新确认需求。",
               "❌ 禁止调用 analyze_agent_workshop_gaps 重新做 gap 分析（应回到 CAPABILITY_CHECK）。",
               "只有用户明确选择 direct / complete / quick 并确认时，才调用 generate_confirmed_candidate_agent，并传入 selected_plan_id 与 acknowledged_gaps。",
               "用户选择 narrow/缩小范围时回到 EXPLORING，不要生成或进入 CAPABILITY_CHECK。"],
    ),

    FlowPhase.GENERATING: PhaseRule(
        phase=FlowPhase.GENERATING,
        description="生成中：执行 generate_confirmed_candidate_agent",
        allowed_tools=[
            _TOOL["generate_confirmed"],
            _TOOL["inspect_assets"],
        ],
        forbidden_tools=[
            _TOOL["analyze_gaps"],
            _TOOL["build_version"],
            _TOOL["real_data_test"],
            _TOOL["publish_version"],
            _TOOL["resolve_gaps"],
            _TOOL["iterate_version"],
            _TOOL["prepare_confirmation"],
        ],
        recommended_next_phase=FlowPhase.BUILDING,
        preconditions=["用户已选择并确认 direct/complete/quick 方案"],
        notes=["generate_confirmed_candidate_agent 会按 selected_plan_id 执行已确认方案。",
               "direct/quick 且可构建时进入 BUILDING；complete 且有 acknowledged_gaps 时进入 GAP_RESOLVING；narrow 应回到 EXPLORING。",
               "确认后不要再给用户制造‘又做一次缺口分析再阻塞’的感受。"],
    ),

    FlowPhase.READY_TO_BUILD: PhaseRule(
        phase=FlowPhase.READY_TO_BUILD,
        description="待构建版本：Draft 已生成，但尚未构建测试版本",
        allowed_tools=[
            _TOOL["build_version"],
            _TOOL["inspect_assets"],
            _TOOL["inspect_runtime"],
        ],
        forbidden_tools=[
            _TOOL["analyze_gaps"],      # gap 分析已在 CAPABILITY_CHECK 阶段完成
            _TOOL["real_data_test"],    # 尚无版本，不能测试
            _TOOL["publish_version"],
            _TOOL["generate_confirmed"],
            _TOOL["prepare_confirmation"],
            _TOOL["propose_plans"],
        ],
        recommended_next_tool=_TOOL["build_version"],
        recommended_next_phase=FlowPhase.BUILDING,
        preconditions=["Agent Draft 已生成", "尚未生成测试版本"],
        notes=["此阶段应调用 build_agent_workshop_version 生成测试版本。",
               "gap 分析已在 CAPABILITY_CHECK 阶段完成，build_version 只负责验证并记录 unresolved gaps。",
               "build_version 只允许放行已被用户 acknowledged 且 selected_plan_id 明确允许（complete/quick）的 blocking gaps；未确认缺口仍会阻塞。",
               "版本构建完成后进入 BUILDING，下一步做真数据测试。"],
    ),

    FlowPhase.BUILDING: PhaseRule(
        phase=FlowPhase.BUILDING,
        description="版本已构建：按已选方案完成构建，准备测试",
        allowed_tools=[
            _TOOL["real_data_test"],
            _TOOL["debug_version"],
            _TOOL["inspect_assets"],
            _TOOL["inspect_runtime"],
            # 如果构建时发现 blocking gap，需要进入 GAP_RESOLVING
            _TOOL["resolve_gaps"],
            _TOOL["start_gap_resolution"],
            _TOOL["inspect_gap_resolution"],
        ],
        forbidden_tools=[
            _TOOL["analyze_gaps"],      # 🚫 gap 分析已在 CAPABILITY_CHECK 阶段完成
            _TOOL["build_version"],     # 🚫 已经构建过
            _TOOL["generate_confirmed"],# 🚫 已经生成过
            _TOOL["prepare_confirmation"],# 🚫 已过确认阶段
            _TOOL["propose_plans"],
        ],
        recommended_next_tool=_TOOL["real_data_test"],
        recommended_next_phase=FlowPhase.TESTING,
        preconditions=["generate_confirmed_candidate_agent 已成功完成"],
        transitions=[
            ("有 blocking gap", FlowPhase.GAP_RESOLVING),
            ("无 blocking gap", FlowPhase.TESTING),
        ],
        notes=["版本已按用户选择的方案构建完成。",
               "🚫 严禁再次调用 analyze_agent_workshop_gaps，这会让用户感觉在重复检查。",
               "🚫 严禁再次调用 build_agent_workshop_version，版本已构建。",
               "如果构建时发现未解决的 blocking gap，直接进入 GAP_RESOLVING。",
               "如果无 gap，下一步直接做 run_agent_workshop_real_data_test。"],
    ),

    FlowPhase.TESTING: PhaseRule(
        phase=FlowPhase.TESTING,
        description="测试与评估：运行真数据测试并评估结果",
        allowed_tools=[
            _TOOL["real_data_test"],
            _TOOL["debug_version"],
            _TOOL["evaluate_version"],
            _TOOL["inspect_assets"],
            _TOOL["iterate_version"],
        ],
        forbidden_tools=[
            _TOOL["generate_confirmed"],
            _TOOL["prepare_confirmation"],
            _TOOL["analyze_gaps"],    # 🚫 除非测试证明缺能力
            _TOOL["build_version"],   # 🚫 除非进入迭代
        ],
        recommended_next_tool=_TOOL["real_data_test"],
        preconditions=["版本已构建", "工具已绑定"],
        transitions=[
            ("评估通过(pass)", FlowPhase.PUBLISHING),
            ("评估需改进(revise)", FlowPhase.ITERATING),
            ("评估拒绝(reject)", FlowPhase.ITERATING),
            ("发现缺能力", FlowPhase.GAP_RESOLVING),
        ],
        notes=["先调用 run_agent_workshop_real_data_test 运行测试。",
               "测试完成后，系统会自动评估并产出 official_acceptance_decision。",
               "pass → 可以发布",
               "revise → 进入迭代改进",
               "reject → 检查根本原因，可能需要重新设计"],
    ),

    FlowPhase.EVALUATING: PhaseRule(
        phase=FlowPhase.EVALUATING,
        description="评估结果已出：等待用户决策",
        allowed_tools=[
            _TOOL["real_data_test"],
            _TOOL["debug_version"],
            _TOOL["evaluate_version"],
            _TOOL["iterate_version"],
            _TOOL["publish_version"],
            _TOOL["inspect_assets"],
        ],
        forbidden_tools=[
            _TOOL["generate_confirmed"],
            _TOOL["prepare_confirmation"],
            _TOOL["analyze_gaps"],
            _TOOL["build_version"],
            _TOOL["resolve_gaps"],
        ],
        preconditions=["测试已完成", "评估结果已产出"],
        transitions=[
            ("评估通过 + 用户确认发布", FlowPhase.PUBLISHING),
            ("评估 revise + 用户要求改进", FlowPhase.ITERATING),
            ("评估 reject + 需重新设计", FlowPhase.CAPABILITY_CHECK),
        ],
        notes=["展示评估结果给用户。",
               "说明每个维度的得分和改进建议。",
               "让用户决定下一步：发布 / 改进 / 重新设计。"],
    ),

    FlowPhase.GAP_RESOLVING: PhaseRule(
        phase=FlowPhase.GAP_RESOLVING,
        description="缺口补齐：生成 Skill 填补能力缺口",
        allowed_tools=[
            _TOOL["resolve_gaps"],
            _TOOL["start_gap_resolution"],
            _TOOL["inspect_gap_resolution"],
            _TOOL["cancel_gap_resolution"],
            _TOOL["retry_gap_resolution"],
            _TOOL["search_capability"],
            _TOOL["inspect_assets"],
        ],
        forbidden_tools=[
            _TOOL["real_data_test"],    # 🚫 版本未重建不能测试
            _TOOL["publish_version"],   # 🚫 不能发布有缺口的版本
            _TOOL["generate_confirmed"],# 🚫 已生成过
            _TOOL["prepare_confirmation"],
        ],
        recommended_next_tool=_TOOL["resolve_gaps"],
        preconditions=["发现 blocking gap", "确认需要补齐"],
        transitions=[
            ("所有 gap 补齐且自动续建成功", FlowPhase.BUILDING),
            ("所有 gap 补齐但尚未构建", FlowPhase.READY_TO_BUILD),
            ("部分 gap 补齐失败", FlowPhase.GAP_RESOLVING),
        ],
        notes=["先向用户解释每个 blocking gap 是什么、为什么需要补齐。",
               "获得用户确认后再调用 resolve_agent_workshop_blocking_gaps。",
               "如果补齐工具已自动续建成功，进入 BUILDING 并直接测试。",
               "如果只完成 Skill 生成/绑定但未重建版本，进入 READY_TO_BUILD 再调用 build_agent_workshop_version。",
               "Skill 生成完成后要回到父 Agent 的构建链路，不要停在 Skill 上。"],
    ),

FlowPhase.ITERATING: PhaseRule(
    phase=FlowPhase.ITERATING,
    description="迭代改进：根据评估结果修改 Agent",
    allowed_tools=[
        _TOOL["iterate_version"],
        _TOOL["resolve_gaps"],
        _TOOL["debug_version"],
        _TOOL["real_data_test"],
        _TOOL["inspect_assets"],
    ],
    forbidden_tools=[
        _TOOL["publish_version"],   # 🚫 评估未通过
        _TOOL["generate_confirmed"],
        _TOOL["prepare_confirmation"],
        _TOOL["analyze_gaps"],      # 🚫 由 resolve_gaps 内部处理
        _TOOL["build_version"],     # 🚫 迭代工具内部会重建
    ],
    recommended_next_tool=_TOOL["iterate_version"],  # 动态覆盖，见 build_flow_guidance_block
    preconditions=["评估结果为 revise 或 reject", "用户要求改进"],
    transitions=[
        ("补齐能力后", FlowPhase.BUILDING),
        ("迭代版本后", FlowPhase.TESTING),
        ("重跑测试后", FlowPhase.EVALUATING),
    ],
    notes=["根据评估证据分类处理：",
           "- 缺能力/工具未调用 → resolve_agent_workshop_blocking_gaps",
           "- 运行失败/样本异常 → 重跑 run_agent_workshop_real_data_test",
           "- 执行计划/输出字段/约束/Prompt 绑定问题 → iterate_agent_workshop_version",
           "改进后需要重新测试和评估。"],
),

    FlowPhase.PUBLISHING: PhaseRule(
        phase=FlowPhase.PUBLISHING,
        description="发布：将 Agent 写入 Runtime Config",
        allowed_tools=[
            _TOOL["publish_version"],
            _TOOL["inspect_assets"],
            _TOOL["inspect_runtime"],
        ],
        forbidden_tools=[
            _TOOL["build_version"],     # 🚫 发布前不应再改
            _TOOL["iterate_version"],   # 🚫 已通过不应再改
            _TOOL["real_data_test"],    # 🚫 已通过
            _TOOL["generate_confirmed"],
            _TOOL["resolve_gaps"],
            _TOOL["analyze_gaps"],
        ],
        recommended_next_tool=_TOOL["publish_version"],
        preconditions=["评估结果为 pass", "用户确认发布"],
        transitions=[
            ("发布完成", FlowPhase.PUBLISHED),
        ],
        notes=["评估通过不代表自动发布，仍需用户确认。",
               "发布后版本写入 Runtime Config 成为正式 Agent。",
               "如需继续迭代，应创建新版本而非修改已发布版本。"],
    ),

    FlowPhase.PUBLISHED: PhaseRule(
        phase=FlowPhase.PUBLISHED,
        description="已发布：Agent 已在 Runtime 生效",
        allowed_tools=[
            _TOOL["inspect_assets"],
            _TOOL["inspect_runtime"],
            _TOOL["search_capability"],
        ],
        forbidden_tools=[
            _TOOL["build_version"],
            _TOOL["publish_version"],
            _TOOL["real_data_test"],
            _TOOL["generate_confirmed"],
            _TOOL["iterate_version"],
            _TOOL["resolve_gaps"],
            _TOOL["analyze_gaps"],
        ],
        preconditions=["publish_version 成功"],
        notes=["已发布的 Agent 不建议再直接修改。",
               "如需改进，创建新版本进入 BUILDING → TESTING 流程。"],
    ),
}


# ──────────────────────────────────────────────────────────────
# 阶段推导
# ──────────────────────────────────────────────────────────────

def derive_flow_phase(
    intent: IntentContext,
    *,
    has_version: bool = False,
    evaluation_status: str = "",
    has_blocking_gaps: bool = False,
) -> FlowPhase:
    """从 IntentContext + Workshop 状态推导当前 FlowPhase。

    推导优先级：
      1. IntentContext.stage 已明确阶段
      2. evaluation 结果决定分支
      3. gap 状态
      4. version 存在性
    """
    stage = intent.stage

    # ── 映射 IntentStage → FlowPhase ──
    stage_map: Dict[str, FlowPhase] = {
        IntentStage.IDLE.value: FlowPhase.IDLE,
        IntentStage.EXPLORING.value: FlowPhase.EXPLORING,
        IntentStage.DRAFT_PREPARING.value: FlowPhase.DRAFT_PREPARING,
        IntentStage.REQUIREMENT_CONFIRMATION_PENDING.value: FlowPhase.REQUIREMENT_CONFIRMATION_PENDING,
        IntentStage.CAPABILITY_CHECK.value: FlowPhase.CAPABILITY_CHECK,
        IntentStage.PLAN_SELECTION_PENDING.value: FlowPhase.PLAN_SELECTION_PENDING,
        IntentStage.CONFIRMATION_PENDING.value: FlowPhase.PLAN_SELECTION_PENDING,  # 兼容旧名
        IntentStage.GENERATING.value: FlowPhase.GENERATING,
        "ready_to_build": FlowPhase.READY_TO_BUILD,
        IntentStage.BUILDING.value: FlowPhase.BUILDING,
        IntentStage.TESTING.value: FlowPhase.TESTING,
        IntentStage.ITERATING.value: FlowPhase.ITERATING,
        IntentStage.GAP_RESOLVING.value: FlowPhase.GAP_RESOLVING,
        IntentStage.PUBLISHING.value: FlowPhase.PUBLISHING,
    }

    phase = stage_map.get(stage, FlowPhase.IDLE)

    # ── 派生状态：基于 evaluation/gap/version 覆盖 ──
    if phase == FlowPhase.TESTING and evaluation_status:
        if evaluation_status in ("pass", "reject", "revise"):
            phase = FlowPhase.EVALUATING

    if phase == FlowPhase.BUILDING and has_blocking_gaps:
        # quick plan 的缺口已确认接受，不应回退到 GAP_RESOLVING
        current_task = next((t for t in (intent.task_stack or []) if t.get("status") == "building"), None)
        if not current_task:
            phase = FlowPhase.GAP_RESOLVING

    if phase == FlowPhase.EVALUATING and evaluation_status == "pass":
        # 如果用户还没有确认发布，暂不直接跳到 PUBLISHING
        pass  # 保持在 EVALUATING，等用户决策

    if phase == FlowPhase.IDLE and intent.spec_id and has_version:
        # 有 spec 但无明确阶段 → 至少是 BUILDING
        phase = FlowPhase.BUILDING

    # ── 🔍 追踪日志：阶段推导 ──
    logger.info(
        "[Flow][Derive] spec_id=%s input_stage=%s → derived_phase=%s "
        "has_version=%s eval=%s has_gaps=%s",
        intent.spec_id or "",
        stage,
        phase.value,
        has_version,
        evaluation_status or "none",
        has_blocking_gaps,
    )

    return phase


# ──────────────────────────────────────────────────────────────
# 流程引导块生成（注入 System Prompt）
# ──────────────────────────────────────────────────────────────

def build_flow_guidance_block(
    intent: IntentContext,
    *,
    phase: FlowPhase | None = None,
    has_version: bool = False,
    evaluation_status: str = "",
    has_blocking_gaps: bool = False,
    user_message: str = "",
) -> str | None:
    """生成当前阶段的流程约束块，注入 System Prompt。

    无 spec_id 时（新 Agent 创建），使用 IDLE 阶段约束。
    """

    if phase is None:
        phase = derive_flow_phase(
            intent,
            has_version=has_version,
            evaluation_status=evaluation_status,
            has_blocking_gaps=has_blocking_gaps,
        )

    rule = PHASE_TABLE.get(phase)
    if rule is None:
        return None

    lines: List[str] = [
        "## 🔒 Agent Builder 流程约束（必须遵守）",
        "",
        f"当前阶段：**{rule.description}**",
        "",
        "### 新建 Agent 记忆边界",
        "- 只能把当前线程用户明确表达的内容作为当前需求事实。",
        "- 历史 Memory、旧对话、已删除 Agent、同名 Agent 的方案/工具/gap 只能作为反例提醒，不能当作当前阶段或当前方案。",
        "- 用户说“方案 A/B/确认”等指代不清时，只能对应当前线程最近一次你明确给出的选项；没有当前选项就追问。",
        "- 如果是新建 Agent，严禁从已删除 Agent 或旧 Agent 的记忆里恢复工具绑定、Prompt、gap 结论。",
    ]
    if intent.spec_id:
        lines.append(f"当前 Agent：{intent.spec_name or intent.spec_id}")

    if intent.intent_summary:
        lines.append(f"用户目标：{intent.intent_summary}")

    if rule.preconditions and rule.preconditions != ["无"]:
        lines.append("")
        lines.append("前置条件已满足：")
        for p in rule.preconditions:
            lines.append(f"  ✅ {p}")

    if rule.allowed_tools:
        lines.append("")
        lines.append("✅ **当前阶段可以调用的工具**：")
        for tool_id in rule.allowed_tools:
            lines.append(f"  - `{tool_id}`")

    recommended_tool_id = rule.recommended_next_tool
    if phase == FlowPhase.ITERATING:
        recommended_tool_id, iterating_guidance, _ = _derive_iterating_recommendation(intent)
        lines.append("")
        lines.append("⭐ **基于评估证据的推荐下一步**：")
        lines.append(f"  - 推荐工具：`{recommended_tool_id}`")
        lines.append(f"  - 原因：{iterating_guidance}")
    elif phase == FlowPhase.PLAN_SELECTION_PENDING:
        # 方案阶段动态推荐：未生成方案时先生成结构化方案；已生成方案且用户选择后执行生成
        selected_plan_id = _resolve_selected_plan_id(intent, user_message)
        user_is_selecting = _looks_like_plan_selection(user_message)
        logger.info(
            "[PlanSelection][Route] pending_options=%d user_is_selecting=%s selected_plan_id=%s next_action=%s summary=%s",
            len(intent.pending_options),
            user_is_selecting,
            selected_plan_id or "none",
            intent.next_action[:120],
            intent.intent_summary[:120],
        )
        if intent.pending_options and selected_plan_id:
            recommended_tool_id = _TOOL["generate_confirmed"]
            lines.append("")
            lines.append(f"⭐ **推荐下一步**：用户已选择方案 `{selected_plan_id}`，必须调用 `{recommended_tool_id}` 并传入 selected_plan_id、acknowledged_gaps 与 gap_report_json")
            lines.append("🚫 此时禁止再次生成候选方案、重新盘点能力或口头重复方案。")
        elif intent.pending_options:
            recommended_tool_id = _TOOL["generate_confirmed"]
            lines.append("")
            lines.append(f"⭐ **推荐下一步**：候选方案已生成，等待用户选择；用户选择 A/B/C 后调用 `{recommended_tool_id}`")
            lines.append("当前待选方案：")
            for opt in intent.pending_options:
                lines.append(f"  - 方案 {opt.get('index', '?')}: {opt.get('name', '')}（id={opt.get('id', '')}）")
        else:
            recommended_tool_id = _TOOL["propose_plans"]
            lines.append("")
            if user_is_selecting:
                lines.append(f"⭐ **推荐下一步**：用户已经表达想按方案生成，但系统还没有结构化候选方案；必须先调用 `{recommended_tool_id}` 生成 pending_options，不能口头重复方案或重新做能力盘点。")
            else:
                lines.append(f"⭐ **推荐下一步**：候选方案尚未结构化生成，先调用 `{recommended_tool_id}` 生成 A/B/C 方案并写入 pending_options。")
    elif recommended_tool_id:
        lines.append("")
        lines.append(f"⭐ **推荐下一步**：调用 `{recommended_tool_id}`")

    # ── 注入待确认项（跨轮上下文不丢失） ──
    if phase == FlowPhase.EXPLORING and intent.pending_question:
        lines.append("")
        lines.append("## ⚠️ 待确认上下文（上一轮未完成的对话）")
        lines.append(f"上一轮你向用户提出的问题：**{intent.pending_question}**")
        if intent.pending_options:
            lines.append("上一轮你给出的选项：")
            for opt in intent.pending_options:
                lines.append(f"  - 选项 {opt.get('index', '?')}: {opt.get('name', '')} — {opt.get('description', '')}")
        lines.append("用户刚才的回复是针对这个问题的，请基于此继续对话，不要重新开始。")
        lines.append("如果用户回复了确认/认可（如「可以」「好的」「没问题」），请调用 `prepare_agent_requirement_intake` 传入用户已确认的偏好参数，推进到需求确认阶段。")

    for transition_desc, target_phase in rule.transitions:
        target_rule = PHASE_TABLE.get(target_phase)
        target_desc = target_rule.description if target_rule else target_phase.value
        lines.append(f"  ➡️ {transition_desc} → {target_desc}")

    if rule.forbidden_tools:
        lines.append("")
        lines.append("🚫 **严禁在当前阶段调用以下工具**：")
        for tool_id in rule.forbidden_tools:
            lines.append(f"  - ❌ `{tool_id}`")
        if _TOOL["analyze_gaps"] in rule.forbidden_tools:
            lines.append("    （缺口分析已在能力盘点阶段完成，执行阶段不再重复）")

    if rule.notes:
        lines.append("")
        lines.append("📋 **阶段约束说明**：")
        for note in rule.notes:
            lines.append(f"  - {note}")

    # ── 财经产品专家沟通风格（所有阶段） ──
    comm_style = _get_communication_style_guidance(phase)
    if comm_style:
        lines.append("")
        lines.append(comm_style)

    guidance = "\n".join(lines)
    logger.info(
        "[Flow][Guidance] phase=%s allowed=%s forbidden=%s next=%s guidance_len=%d",
        phase.value,
        rule.allowed_tools,
        rule.forbidden_tools,
        recommended_tool_id or "none",
        len(guidance),
    )
    return guidance


# ──────────────────────────────────────────────────────────────
# 沟通风格指南
# ──────────────────────────────────────────────────────────────

def _get_communication_style_guidance(phase: FlowPhase) -> str:
    """为当前阶段返回财经产品专家的沟通风格指导。

    核心原则：你是财经分析产品专家，不是技术架构师。
    用户看到的是分析框架和业务价值，不是工具数量和绑定策略。
    """
    base = (
        "## 💬 沟通风格（财经产品专家模式）\n\n"
        "**你的身份**：财经分析产品专家，帮助用户设计和定制专业的投资分析 Agent。\n\n"
        "**核心原则**：\n"
        "1. 讲分析框架和业务价值，不讲技术细节。"
        "不要说「绑定了 3 个工具」或列出 tool_id，"
        "要说「从三个维度交叉验证——同行对比、历史水位、内在价值」。\n"
        "2. 使用业务术语而非技术代号。"
        "不要说「direct 方案」，要说「推荐方案」。"
        "不要说「capability_gap」，要说「当前覆盖的分析维度」。\n"
        "3. 主动给出专业判断，不要只抛选择题——"
        "告诉用户不同选项的利弊和你的推荐理由。"
        "需求沟通阶段必须先给成熟默认方案草稿，再让用户纠正；"
        "一次最多问 1 个关键问题，禁止列出一串问题让用户逐项回答。\n"
        "4. 工具/能力/缺口等技术信息只在心里记着，"
        "对外只说分析维度、估值逻辑、风险视角等业务概念。"
    )

    confirmation_extra = (
        "\n**确认阶段特别提醒**：\n"
        "你收到的 capability_inventory 和 gap_report 是给后端的技术数据。"
        "给用户沟通时，务必翻译成业务语言：\n"
        "- 「行业估值对比」→ PE/PB/PS 相对行业中位数和分位\n"
        "- 「历史估值分位」→ 当前 PE 处于过去 5-10 年什么水平\n"
        "- 「DCF 绝对估值」→ 用自由现金流贴现算出企业内在价值\n"
        "多方案对比时，用「推荐方案」「精简方案」「深度方案」这类用户能懂的名称，"
        "不要暴露 direct/complete/quick/narrow 这些内部标识。"
    )

    if phase in (FlowPhase.CAPABILITY_CHECK, FlowPhase.PLAN_SELECTION_PENDING, FlowPhase.REQUIREMENT_CONFIRMATION_PENDING):
        return base + confirmation_extra
    return base


# ──────────────────────────────────────────────────────────────
# 阶段转换验证
# ──────────────────────────────────────────────────────────────

def validate_tool_call(
    tool_id: str,
    intent: IntentContext,
    *,
    has_version: bool = False,
    evaluation_status: str = "",
    has_blocking_gaps: bool = False,
) -> Tuple[bool, str]:
    """验证工具调用是否在允许范围内。

    返回 (合法, 原因说明)。
    """
    phase = derive_flow_phase(
        intent,
        has_version=has_version,
        evaluation_status=evaluation_status,
        has_blocking_gaps=has_blocking_gaps,
    )
    rule = PHASE_TABLE.get(phase)
    if rule is None:
        return True, ""

    if tool_id in rule.forbidden_tools:
        return False, (
            f"当前处于「{rule.description}」阶段，"
            f"`{tool_id}` 在此阶段被禁止调用。"
            f"{'建议改为：' + rule.recommended_next_tool if rule.recommended_next_tool else ''}"
        )

    return True, ""


# ──────────────────────────────────────────────────────────────
# 获取所有阶段信息（用于文档/诊断）
# ──────────────────────────────────────────────────────────────

def get_all_phases() -> List[PhaseRule]:
    """返回所有流程阶段的规则列表。"""
    return list(PHASE_TABLE.values())


def get_phase_rule(phase: FlowPhase) -> PhaseRule | None:
    """获取单个阶段的规则。"""
    return PHASE_TABLE.get(phase)
