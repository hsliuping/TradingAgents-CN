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
    CAPABILITY_CHECK = "capability_check"
    DRAFT_PREPARING = "draft_preparing"
    CONFIRMATION_PENDING = "confirmation_pending"

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
    "prepare_confirmation": "prepare_agent_generation_confirmation",
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


# ── 阶段定义表 ──────────────────────────────────────────────

PHASE_TABLE: Dict[FlowPhase, PhaseRule] = {
    FlowPhase.IDLE: PhaseRule(
        phase=FlowPhase.IDLE,
        description="未选中任何 Agent",
        allowed_tools=[
            _TOOL["search_capability"],
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
        ],
        recommended_next_phase=FlowPhase.CAPABILITY_CHECK,
        preconditions=["用户表达了创建 Agent 的意图"],
        notes=["使用 search_project_capabilities 了解现有能力。",
               "不要在此阶段尝试确认或生成。"],
    ),

    FlowPhase.CAPABILITY_CHECK: PhaseRule(
        phase=FlowPhase.CAPABILITY_CHECK,
        description="能力检查：确认哪些工具和 Skill 可以满足需求",
        allowed_tools=[
            _TOOL["search_capability"],
            _TOOL["inspect_assets"],
            _TOOL["inspect_runtime"],
        ],
        forbidden_tools=[
            _TOOL["generate_confirmed"],
            _TOOL["analyze_gaps"],
            _TOOL["build_version"],
            _TOOL["real_data_test"],
            _TOOL["publish_version"],
            _TOOL["resolve_gaps"],
        ],
        recommended_next_phase=FlowPhase.DRAFT_PREPARING,
        preconditions=["需求基本明确"],
        notes=["向用户展示可用的工具和 Skill，说明哪些能力已有、哪些可能需要新建。",
               "不要在此阶段做正式的缺口分析（那是 BUILDING 阶段的事）。"],
    ),

    FlowPhase.DRAFT_PREPARING: PhaseRule(
        phase=FlowPhase.DRAFT_PREPARING,
        description="准备确认稿：生成 Agent 配置摘要供用户审核",
        allowed_tools=[
            _TOOL["prepare_confirmation"],
            _TOOL["search_capability"],
            _TOOL["inspect_assets"],
            _TOOL["inspect_runtime"],
        ],
        forbidden_tools=[
            _TOOL["generate_confirmed"],
            _TOOL["analyze_gaps"],
            _TOOL["build_version"],
            _TOOL["real_data_test"],
            _TOOL["publish_version"],
            _TOOL["resolve_gaps"],
            _TOOL["iterate_version"],
        ],
        recommended_next_tool=_TOOL["prepare_confirmation"],
        recommended_next_phase=FlowPhase.CONFIRMATION_PENDING,
        preconditions=["能力检查已完成，工具候选已明确"],
        notes=["prepare_agent_generation_confirmation 生成确认稿。",
               "展示给用户后等待明确确认（如'确认'、'启动生成'）。",
               "未确认前不得调用 generate_confirmed_candidate_agent。"],
    ),

    FlowPhase.CONFIRMATION_PENDING: PhaseRule(
        phase=FlowPhase.CONFIRMATION_PENDING,
        description="等待用户确认：确认稿已展示，等待用户批准",
        allowed_tools=[
            _TOOL["generate_confirmed"],
            _TOOL["prepare_confirmation"],
            _TOOL["search_capability"],
            _TOOL["inspect_assets"],
        ],
        forbidden_tools=[
            _TOOL["analyze_gaps"],
            _TOOL["build_version"],
            _TOOL["real_data_test"],
            _TOOL["publish_version"],
            _TOOL["resolve_gaps"],
            _TOOL["iterate_version"],
            _TOOL["debug_version"],
        ],
        recommended_next_tool=_TOOL["generate_confirmed"],
        recommended_next_phase=FlowPhase.GENERATING,
        preconditions=["确认稿已展示", "用户明确表示了确认"],
        transitions=[
            ("用户确认生成", FlowPhase.GENERATING),
            ("用户要求修改需求", FlowPhase.CAPABILITY_CHECK),
        ],
        notes=["此阶段只有一个合法操作：generate_confirmed_candidate_agent。",
               "必须等用户说出'确认'/'好的'/'启动'等明确肯定词才能调用。",
               "不要在用户确认前尝试生成。"],
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
        preconditions=["用户已确认"],
        notes=["generate_confirmed_candidate_agent 内部会自动："
               "创建 Runtime Config → Prompt 模板 → 工具绑定 → Workshop Draft → 自动构建版本。",
               "自动构建内部已运行缺口检查，不要再单独调用 analyze_agent_workshop_gaps。",
               "完成后直接进入 BUILDING 阶段。"],
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
            _TOOL["analyze_gaps"],      # build_version 内部会做
            _TOOL["real_data_test"],    # 尚无版本，不能测试
            _TOOL["publish_version"],
            _TOOL["generate_confirmed"],
            _TOOL["prepare_confirmation"],
        ],
        recommended_next_tool=_TOOL["build_version"],
        recommended_next_phase=FlowPhase.BUILDING,
        preconditions=["Agent Draft 已生成", "尚未生成测试版本"],
        notes=["此阶段应调用 build_agent_workshop_version 生成测试版本。",
               "不要先调用 analyze_agent_workshop_gaps；build_version 内部会完成真实 gap 分析。",
               "版本构建完成后进入 BUILDING，下一步做真数据测试。"],
    ),

    FlowPhase.BUILDING: PhaseRule(
        phase=FlowPhase.BUILDING,
        description="版本已构建：自动构建完成，准备测试",
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
            _TOOL["analyze_gaps"],      # 🚫 自动构建内部已经完成
            _TOOL["build_version"],     # 🚫 已经构建过
            _TOOL["generate_confirmed"],# 🚫 已经生成过
            _TOOL["prepare_confirmation"],# 🚫 已过确认阶段
        ],
        recommended_next_tool=_TOOL["real_data_test"],
        recommended_next_phase=FlowPhase.TESTING,
        preconditions=["generate_confirmed_candidate_agent 已成功完成"],
        transitions=[
            ("有 blocking gap", FlowPhase.GAP_RESOLVING),
            ("无 blocking gap", FlowPhase.TESTING),
        ],
        notes=["自动构建已在内部完成缺口校验。",
               "🚫 严禁再次调用 analyze_agent_workshop_gaps，这会让用户感觉在重复检查。",
               "🚫 严禁再次调用 build_agent_workshop_version，版本已构建。",
               "如果构建时发现 blocking gap，直接进入 GAP_RESOLVING。",
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
        IntentStage.CAPABILITY_CHECK.value: FlowPhase.CAPABILITY_CHECK,
        IntentStage.DRAFT_PREPARING.value: FlowPhase.DRAFT_PREPARING,
        IntentStage.CONFIRMATION_PENDING.value: FlowPhase.CONFIRMATION_PENDING,
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
        phase = FlowPhase.GAP_RESOLVING

    if phase == FlowPhase.EVALUATING and evaluation_status == "pass":
        # 如果用户还没有确认发布，暂不直接跳到 PUBLISHING
        pass  # 保持在 EVALUATING，等用户决策

    if phase == FlowPhase.IDLE and intent.spec_id and has_version:
        # 有 spec 但无明确阶段 → 至少是 BUILDING
        phase = FlowPhase.BUILDING

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
) -> str | None:
    """生成当前阶段的流程约束块，注入 System Prompt。

    只有 IntentContext 有 spec_id 时才输出。
    """

    if not intent.spec_id:
        return None

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
        f"当前 Agent：{intent.spec_name or intent.spec_id}",
    ]

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
    elif recommended_tool_id:
        lines.append("")
        lines.append(f"⭐ **推荐下一步**：调用 `{recommended_tool_id}`")

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
            lines.append("    （缺口分析已在自动构建阶段完成或不需要）")

    if rule.notes:
        lines.append("")
        lines.append("📋 **阶段约束说明**：")
        for note in rule.notes:
            lines.append(f"  - {note}")

    return "\n".join(lines)


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
