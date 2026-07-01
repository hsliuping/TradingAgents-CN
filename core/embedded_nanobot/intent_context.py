"""
Intent Context 管理器

管理 Nanobot 对话的意图上下文，确保 LLM 在跨多轮对话、多 Agent
讨论场景下始终知道"当前在处理哪个 Agent、处于什么阶段"。

解决的问题：
  - 需求漂移：讨论 Agent A 多轮后，LLM 创建了 Agent B
  - 阶段跳变：LLM 在确认阶段就尝试构建，或在构建阶段去生成 Skill
  - 多 Agent 混淆：同一线程讨论多个 Agent 时，LLM 搞混目标
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Any, Dict, Optional, List

logger = logging.getLogger(__name__)


def _to_str_list(value: Any) -> List[str]:
    if not value:
        return []
    if isinstance(value, list):
        return [str(item).strip() for item in value if item is not None]
    if isinstance(value, str):
        return [value.strip()] if value.strip() else []
    return []


class IntentStage(str, Enum):
    """对话阶段枚举。"""
    EXPLORING = "exploring"              # 用户在探索/描述需求
    CAPABILITY_CHECK = "capability_check"  # 正在检查能力缺口
    DRAFT_PREPARING = "draft_preparing"    # 正在准备工坊草稿/需求确认稿
    REQUIREMENT_CONFIRMATION_PENDING = "requirement_confirmation_pending"  # 等待用户确认需求
    PLAN_SELECTION_PENDING = "plan_selection_pending"  # 等待用户选择方案
    CONFIRMATION_PENDING = "confirmation_pending"  # 兼容旧名，同 PLAN_SELECTION_PENDING
    GENERATING = "generating"              # 正在生成 Agent
    BUILDING = "building"                  # 正在构建版本
    TESTING = "testing"                    # 正在测试
    ITERATING = "iterating"                # 正在迭代改进
    GAP_RESOLVING = "gap_resolving"        # 正在解决能力缺口
    PUBLISHING = "publishing"              # 正在发布
    IDLE = "idle"                         # 无明确意图


class IntentAction(str, Enum):
    """用户的顶层意图。"""
    CREATE_AGENT = "create_agent"           # 创建新 Agent
    ITERATE_AGENT = "iterate_agent"         # 迭代已有 Agent
    TEST_AGENT = "test_agent"               # 测试 Agent
    PUBLISH_AGENT = "publish_agent"         # 发布 Agent
    ADD_CAPABILITY = "add_capability"       # 添加新能力/Skill
    RESOLVE_GAP = "resolve_gap"             # 解决能力缺口
    CHECK_STATUS = "check_status"           # 查看状态/进度
    GENERAL_QA = "general_qa"               # 一般问题


@dataclass
class IntentContext:
    """当前对话的意图上下文。

    存储在 thread_context.intent 字段中。
    """
    # --- 当前焦点 Agent ---
    spec_id: str = ""
    spec_name: str = ""

    # --- 当前意图 ---
    action: str = ""                        # IntentAction 值
    stage: str = ""                         # IntentStage 值

    # --- 意图描述 ---
    intent_summary: str = ""                # 简短描述用户想做什么 (≤200 字)
    active_subtask: str = ""                # 当前子任务，如：为商誉缺口创建 Skill
    next_action: str = ""                   # 下一步应该做什么

    # --- 父子任务链 ---
    task_stack: List[Dict[str, str]] = field(default_factory=list)
    # [{"type":"agent|gap|skill|test", "id":"...", "name":"...", "status":"...", "parent_id":"..."}]
    linked_skills: List[Dict[str, str]] = field(default_factory=list)
    # [{"skill_id":"...", "skill_name":"...", "gap":"...", "status":"..."}]

    # --- 历史 ---
    agents_discussed: List[Dict[str, str]] = field(default_factory=list)
    # [{"spec_id": "...", "spec_name": "...", "last_action": "create/iterate/test"}]

    # --- 最近一次评估证据（用于 ITERATING 阶段路由） ---
    last_evaluation_decision: str = ""      # pass / revise / reject
    last_evaluation_blockers: List[str] = field(default_factory=list)
    # 从 evaluation report 的 publish_readiness.blockers 提取
    last_evaluation_categories: List[str] = field(default_factory=list)
    # 从 evidence_bundle.findings.category 提取，如 ["tool_usage", "output_coverage", "execution_plan"]

    # --- 待确认选项（解决 LLM 跨轮指代消解问题） ---
    pending_options: List[Dict[str, Any]] = field(default_factory=list)
    # 当前等待用户选择的选项列表，例如：
    # [{"index":1,"id":"plan_a","name":"A方案","description":"..."}, ...]
    pending_question: str = ""              # 当前等待用户回答的问题
    last_proposed_items: List[Dict[str, Any]] = field(default_factory=list)
    # 最近提出的方案/工具/股票等，用于兜底指代消解
    conversation_summary: str = ""          # 上一轮对话的摘要，注入下一轮避免上下文丢失

    # --- 时间戳 ---
    created_at: float = 0.0
    updated_at: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Optional[Dict[str, Any]]) -> "IntentContext":
        if not data or not isinstance(data, dict):
            return cls()
        return cls(
            spec_id=str(data.get("spec_id") or ""),
            spec_name=str(data.get("spec_name") or ""),
            action=str(data.get("action") or ""),
            stage=str(data.get("stage") or ""),
            intent_summary=str(data.get("intent_summary") or ""),
            active_subtask=str(data.get("active_subtask") or ""),
            next_action=str(data.get("next_action") or ""),
            last_evaluation_decision=str(data.get("last_evaluation_decision") or ""),
            last_evaluation_blockers=_to_str_list(data.get("last_evaluation_blockers")),
            last_evaluation_categories=_to_str_list(data.get("last_evaluation_categories")),
            pending_options=[
                {str(k): v for k, v in opt.items() if k is not None}
                for opt in (data.get("pending_options") or [])
                if isinstance(opt, dict) and opt.get("index")
            ],
            pending_question=str(data.get("pending_question") or ""),
            last_proposed_items=[
                {str(k): v for k, v in item.items() if k is not None}
                for item in (data.get("last_proposed_items") or [])
                if isinstance(item, dict)
            ],
            conversation_summary=str(data.get("conversation_summary") or ""),
            task_stack=[
                {
                    "type": str(t.get("type") or ""),
                    "id": str(t.get("id") or ""),
                    "name": str(t.get("name") or ""),
                    "status": str(t.get("status") or ""),
                    "parent_id": str(t.get("parent_id") or ""),
                }
                for t in (data.get("task_stack") or [])
                if isinstance(t, dict) and t.get("id")
            ],
            linked_skills=[
                {
                    "skill_id": str(s.get("skill_id") or ""),
                    "skill_name": str(s.get("skill_name") or ""),
                    "gap": str(s.get("gap") or ""),
                    "status": str(s.get("status") or ""),
                }
                for s in (data.get("linked_skills") or [])
                if isinstance(s, dict) and (s.get("skill_id") or s.get("skill_name"))
            ],
            agents_discussed=[
                {"spec_id": str(a.get("spec_id") or ""), "spec_name": str(a.get("spec_name") or ""), "last_action": str(a.get("last_action") or "")}
                for a in (data.get("agents_discussed") or [])
                if isinstance(a, dict) and a.get("spec_id")
            ],
            created_at=float(data.get("created_at") or 0.0),
            updated_at=float(data.get("updated_at") or 0.0),
        )

    def ensure_timestamps(self) -> None:
        """确保时间戳存在。"""
        now = time.time()
        if self.created_at <= 0:
            self.created_at = now
        self.updated_at = now

    def update_intent(
        self,
        action: str = "",
        stage: str = "",
        spec_id: str = "",
        spec_name: str = "",
        intent_summary: str = "",
        active_subtask: str = "",
        next_action: str = "",
        evaluation_decision: str = "",
        evaluation_blockers: Optional[List[str]] = None,
        evaluation_categories: Optional[List[str]] = None,
        pending_options: Optional[List[Dict[str, Any]]] = None,
        pending_question: str = "",
        proposed_items: Optional[List[Dict[str, Any]]] = None,
        clear_pending_options: bool = False,
        task: Optional[Dict[str, str]] = None,
        linked_skill: Optional[Dict[str, str]] = None,
        conversation_summary: str = "",
    ) -> None:
        """更新意图上下文。"""
        if action:
            self.action = action
        if stage:
            self.stage = stage
        if spec_id:
            self.spec_id = spec_id
        if spec_name:
            self.spec_name = spec_name
        if intent_summary:
            self.intent_summary = intent_summary
        if active_subtask:
            self.active_subtask = active_subtask
        if next_action:
            self.next_action = next_action
        if evaluation_decision:
            self.last_evaluation_decision = evaluation_decision
        if evaluation_blockers is not None:
            self.last_evaluation_blockers = evaluation_blockers
        if evaluation_categories is not None:
            self.last_evaluation_categories = evaluation_categories

        # 待确认选项管理
        if clear_pending_options:
            self.pending_options = []
            self.pending_question = ""
        if pending_options is not None:
            self.pending_options = [
                opt for opt in pending_options
                if isinstance(opt, dict) and opt.get("index")
            ]
            # 同时保存到 last_proposed_items 兜底
            self.last_proposed_items = self.pending_options[-8:]
        if pending_question:
            self.pending_question = pending_question
        if proposed_items is not None:
            self.last_proposed_items = [
                item for item in proposed_items
                if isinstance(item, dict)
            ][-8:]

        if conversation_summary:
            self.conversation_summary = conversation_summary

        if task:
            self.upsert_task(
                task_type=task.get("type", ""),
                task_id=task.get("id", ""),
                name=task.get("name", ""),
                status=task.get("status", ""),
                parent_id=task.get("parent_id", ""),
            )
        if linked_skill:
            self.link_skill(
                skill_id=linked_skill.get("skill_id", ""),
                skill_name=linked_skill.get("skill_name", ""),
                gap=linked_skill.get("gap", ""),
                status=linked_skill.get("status", ""),
            )
        self.ensure_timestamps()

        # 更新 agents_discussed 列表
        if self.spec_id:
            found = False
            for a in self.agents_discussed:
                if a["spec_id"] == self.spec_id:
                    a["spec_name"] = self.spec_name
                    a["last_action"] = self.action
                    found = True
                    break
            if not found:
                self.agents_discussed.append({
                    "spec_id": self.spec_id,
                    "spec_name": self.spec_name,
                    "last_action": self.action,
                })

    def upsert_task(self, task_type: str, task_id: str, name: str = "", status: str = "", parent_id: str = "") -> None:
        """写入/更新父子任务链中的一个任务节点。"""
        if not task_id:
            return
        item = {
            "type": str(task_type or ""),
            "id": str(task_id),
            "name": str(name or task_id),
            "status": str(status or ""),
            "parent_id": str(parent_id or ""),
        }
        for idx, existing in enumerate(self.task_stack):
            if existing.get("id") == task_id and existing.get("type") == task_type:
                self.task_stack[idx] = {**existing, **item}
                break
        else:
            self.task_stack.append(item)
        self.task_stack = self.task_stack[-12:]
        self.ensure_timestamps()

    def link_skill(self, skill_id: str, skill_name: str = "", gap: str = "", status: str = "") -> None:
        """记录某个 Skill 是为当前 Agent 的哪个 gap 创建的。"""
        if not skill_id and not skill_name:
            return
        key = skill_id or skill_name
        item = {
            "skill_id": str(skill_id or ""),
            "skill_name": str(skill_name or key),
            "gap": str(gap or ""),
            "status": str(status or ""),
        }
        for idx, existing in enumerate(self.linked_skills):
            if (existing.get("skill_id") or existing.get("skill_name")) == key:
                self.linked_skills[idx] = {**existing, **item}
                break
        else:
            self.linked_skills.append(item)
        self.linked_skills = self.linked_skills[-12:]
        self.ensure_timestamps()

    def complete_subtask(self, task_id: str, status: str = "completed", next_action: str = "") -> None:
        """标记子任务完成，并设置下一步。"""
        for item in self.task_stack:
            if item.get("id") == task_id:
                item["status"] = status
        if next_action:
            self.next_action = next_action
        self.ensure_timestamps()

    def build_injection_block(self) -> str:
        """构建注入到 System Prompt 的意图上下文块。

        这是给 LLM 看的最重要的上下文提示。
        """
        if not self.spec_id and not self.action:
            return ""

        lines = [
            "",
            "## 🔴 Current Intent Context (SYSTEM-INJECTED — READ BEFORE ACTING)",
            "",
        ]

        if self.spec_name and self.spec_id:
            lines.extend([
                f"**当前焦点 Agent**：「{self.spec_name}」（spec_id={self.spec_id}）",
                "",
            ])

        if self.action:
            action_labels = {
                "create_agent": "创建新 Agent",
                "iterate_agent": "迭代 Agent 版本",
                "test_agent": "测试 Agent",
                "publish_agent": "发布 Agent",
                "add_capability": "添加新能力",
                "resolve_gap": "解决能力缺口",
                "check_status": "查看状态",
                "general_qa": "一般问答",
            }
            label = action_labels.get(self.action, self.action)
            lines.append(f"**当前意图**：{label}")

        if self.stage:
            stage_labels = {
                "exploring": "需求探索",
                "capability_check": "能力检查",
                "draft_preparing": "草稿准备",
                "confirmation_pending": "等待用户确认",
                "generating": "正在生成",
                "building": "正在构建",
                "testing": "正在测试",
                "iterating": "正在迭代",
                "gap_resolving": "缺口解决",
                "publishing": "正在发布",
                "idle": "空闲",
            }
            label = stage_labels.get(self.stage, self.stage)
            lines.append(f"（阶段: {label}）")

        if self.intent_summary:
            lines.append(f"**意图摘要**：{self.intent_summary}")
        if self.active_subtask:
            lines.append(f"**当前子任务**：{self.active_subtask}")
        if self.next_action:
            lines.append(f"**下一步动作**：{self.next_action}")

        if self.task_stack:
            lines.extend(["", "### 当前任务链（Agent → Gap → Skill/Test）"])
            for task in self.task_stack[-8:]:
                parent = f" ← parent={task.get('parent_id')}" if task.get("parent_id") else ""
                lines.append(
                    f"- [{task.get('type')}] {task.get('name')} ({task.get('id')}) "
                    f"status={task.get('status')}{parent}"
                )

        if self.linked_skills:
            lines.extend(["", "### 与当前 Agent 关联的 Skill / 能力补齐"])
            for skill in self.linked_skills[-8:]:
                gap = f"，对应缺口：{skill.get('gap')}" if skill.get("gap") else ""
                lines.append(
                    f"- {skill.get('skill_name') or skill.get('skill_id')} "
                    f"status={skill.get('status')}{gap}"
                )

        lines.append("")

        # 核心约束规则
        lines.extend([
            "### 🔴 CRITICAL SCOPE RULES（必须遵守）",
            "",
        ])

        if self.spec_id:
            lines.append(f"- 所有工具调用（inspect、create、build、test、iterate）都只操作 spec_id={self.spec_id}")
            lines.append(f"- 当用户说「这个 Agent」「它」「现在是什么进度」时，指的就是「{self.spec_name}」")
            lines.append(f"- 不要查询、讨论或操作其他 Agent（除非用户明确提到另一个 Agent 的名称）")
            lines.append(f"- 不要在 save_memory 中保存其他 Agent 的信息")

        lines.extend([
            "- 用户说「确认」或「好的」时，如果当前阶段是 confirmation_pending，必须先解析 pending_options 中用户选择的方案，再按 selected_plan_id 执行；不要把确认理解成无条件生成",
            "- Agent 创建 v2 流程必须遵循：需求澄清 → 能力盘点+gap分析 → 展示 direct/complete/quick/narrow 候选方案 → 用户选择方案 → 按方案生成/补能力/缩小需求",
            "- 用户选择 complete/quick 时，必须把该方案的 acknowledged_gaps **和 gap_report_json**（prepare_agent_generation_confirmation 返回的 gap_report 字段）一并传给 generate_confirmed_candidate_agent；用户选择 narrow 时回到需求澄清，不生成 Agent",
            "💡 如果 gap_report_json 或 capability_inventory_json 数据已丢失（多轮对话后被截断），直接传空即可——后端自动从 Workshop Session 的 builder_contracts 恢复，不要因为数据丢失而重新调用 prepare_agent_generation_confirmation。",
            "- 已在 prepare 阶段形成 gap_report 和 candidate_plans 后，不要在用户确认后重新启动一轮独立 gap 分析；应按用户确认方案执行，执行或测试失败后再迭代",
            "- 执行任何写操作（create/build/iterate/publish）前，必须确认 spec_id 与 intent context 一致",
            "- 如果一个 agent_id 不是 intent context 中的 spec_id，拒绝操作并提示用户",
            "- 如果当前正在为 Agent 解决 gap 或创建 Skill，完成 Skill 后必须回到父 Agent 继续 build/test/iterate，不要把 Skill 当成最终目标",
            "- 回答进度时必须按任务链说明：父 Agent 状态、当前 gap/skill 状态、下一步动作",
            "",
            "### 选项确认与指代消解规则",
            "",
            "当你向用户展示多个互斥选项（方案、工具、操作路径）时：",
            "1. 必须以编号列表呈现，并更新 IntentContext.pending_options",
            "2. 每个选项必须有明确名称和 index（从 1 开始）",
            "3. 你必须记录 pending_question：当前等待用户回答的问题",
            "",
            "当用户用以下方式回复时，必须先解析为具体选项再行动：",
            "- 「第一个」→ index=1，「第二个」→ index=2，以此类推",
            "- 「那个」「刚才说的」「就按这个」→ 最近提出的选项或 pending_options 最后一个",
            "- 「A 方案」「B 方案」→ 匹配 option.id 或 option.name",
            "",
            "在调用任何工具前，必须先用一句话复述你的理解：",
            "「你选择的是：{option.name}。我现在按这个执行。」",
            "如果无法确定用户指的是哪个选项，必须向用户确认，不要猜测执行。",
            "永远不要把用户的简短确认当成新话题。",
            "",
        ])

        # 当前等待确认的选项
        if self.pending_options:
            lines.extend([
                "### 当前等待确认的选项",
                f"问题：{self.pending_question or '请从以下选项中选择'}" if self.pending_question else "",
            ])
            for opt in self.pending_options[-6:]:
                idx = opt.get("index", "?")
                name = opt.get("name") or opt.get("id") or "未命名"
                desc = opt.get("description") or ""
                lines.append(f"  {idx}. {name}" + (f" — {desc}" if desc else ""))
            lines.append("")

        # 上一轮对话摘要（跨轮上下文不丢失）
        if self.conversation_summary:
            lines.extend([
                "### 上一轮对话摘要",
                self.conversation_summary,
                "",
            ])

        if self.last_proposed_items and not self.pending_options:
            lines.extend([
                "### 最近提出的方案/选项（供指代消解参考）",
            ])
            for item in self.last_proposed_items[-4:]:
                name = item.get("name") or item.get("id") or "未命名"
                desc = item.get("description") or ""
                lines.append(f"  - {name}" + (f" — {desc}" if desc else ""))
            lines.append("")

        # 多 Agent 讨论历史（如果存在多个）
        other_agents = [a for a in self.agents_discussed if a["spec_id"] != self.spec_id]
        if other_agents:
            lines.append(f"### ⚠️ 本线程也讨论过其他 Agent（仅作参考，不要操作它们）")
            for a in other_agents[-5:]:  # 最近 5 个
                lines.append(f"- {a['spec_name']}（{a['spec_id']}）— 上次操作: {a['last_action']}")
            lines.append("")

        return "\n".join(lines)

    def validate_action(self, proposed_spec_id: str, action_name: str) -> Optional[str]:
        """验证一个操作是否与当前意图一致。

        Returns:
            不一致时返回错误消息，一致时返回 None。
        """
        if not self.spec_id:
            return None  # 没有焦点 → 允许任何操作

        if proposed_spec_id and proposed_spec_id != self.spec_id:
            return (
                f"意图漂移: 当前焦点 Agent 是「{self.spec_name}」（{self.spec_id}），"
                f"但你试图对「{proposed_spec_id}」执行 {action_name}。"
                f"如果你确实要操作另一个 Agent，请先在对话中明确说明。"
            )

        return None


def get_intent_context_from_thread() -> IntentContext:
    """从当前 contextvar 读取 IntentContext。"""
    try:
        from core.tools.context import get_current_assistant_thread_context
        ctx = get_current_assistant_thread_context() or {}
        intent_data = ctx.get("intent") if isinstance(ctx, dict) else None
        return IntentContext.from_dict(intent_data)
    except Exception:
        return IntentContext()


def update_intent_context_in_thread(
    *,
    action: str = "",
    stage: str = "",
    spec_id: str = "",
    spec_name: str = "",
    intent_summary: str = "",
    active_subtask: str = "",
    next_action: str = "",
    evaluation_decision: str = "",
    evaluation_blockers: Optional[List[str]] = None,
    evaluation_categories: Optional[List[str]] = None,
    pending_options: Optional[List[Dict[str, Any]]] = None,
    pending_question: str = "",
    proposed_items: Optional[List[Dict[str, Any]]] = None,
    clear_pending_options: bool = False,
    task: Optional[Dict[str, str]] = None,
    linked_skill: Optional[Dict[str, str]] = None,
    conversation_summary: str = "",
) -> IntentContext:
    """更新当前线程的意图上下文（contextvar 级别，当前 turn 内生效）。

    返回更新后的 IntentContext。
    """
    try:
        from core.tools.context import get_current_assistant_thread_context, set_current_assistant_thread_context
        ctx = get_current_assistant_thread_context() or {}
        intent = IntentContext.from_dict(ctx.get("intent"))
        intent.update_intent(
            action=action,
            stage=stage,
            spec_id=spec_id or intent.spec_id,
            spec_name=spec_name or intent.spec_name,
            intent_summary=intent_summary or intent.intent_summary,
            active_subtask=active_subtask,
            next_action=next_action,
            evaluation_decision=evaluation_decision,
            evaluation_blockers=evaluation_blockers,
            evaluation_categories=evaluation_categories,
            pending_options=pending_options,
            pending_question=pending_question,
            proposed_items=proposed_items,
            clear_pending_options=clear_pending_options,
            task=task,
            linked_skill=linked_skill,
            conversation_summary=conversation_summary,
        )
        ctx["intent"] = intent.to_dict()
        # 同步顶层字段，兼容现有前端/工具过滤逻辑
        if intent.spec_id:
            ctx["spec_id"] = intent.spec_id
        if intent.spec_name:
            ctx["spec_name"] = intent.spec_name
        # 当阶段进入 building/testing 时，清除 has_blocking_gaps 标记
        # （quick plan 的缺口已确认接受，不应再触发 GAP_RESOLVING 回退）
        if stage in ("building", "testing", "ready_to_build"):
            ctx.pop("has_blocking_gaps", None)
        set_current_assistant_thread_context(ctx)
        logger.info(
            "[IntentContext][Update] action=%s stage=%s spec_id=%s spec_name=%s pending_options=%d",
            action, stage, spec_id, spec_name, len(intent.pending_options),
        )
        # 🔒 写入模块级存储（按 thread_id 隔离，替代不稳定的 contextvar）
        try:
            from core.tools.context import set_latest_nanobot_intent
            set_latest_nanobot_intent(intent.to_dict())
        except Exception:
            pass
        return intent
    except Exception as exc:
        logger.warning("[IntentContext][Update] failed: %s", exc)
        return IntentContext()


def update_evaluation_evidence_in_thread(
    *,
    decision: str = "",
    blockers: Optional[List[str]] = None,
    categories: Optional[List[str]] = None,
) -> IntentContext:
    """更新最近一次评估证据到意图上下文。"""
    try:
        from core.tools.context import get_current_assistant_thread_context, set_current_assistant_thread_context
        ctx = get_current_assistant_thread_context() or {}
        intent = IntentContext.from_dict(ctx.get("intent"))
        intent.update_intent(
            evaluation_decision=decision,
            evaluation_blockers=blockers,
            evaluation_categories=categories,
        )
        ctx["intent"] = intent.to_dict()
        set_current_assistant_thread_context(ctx)
        logger.info(
            "[IntentContext][EvalEvidence] decision=%s categories=%s blockers=%d",
            decision, categories, len(blockers or []),
        )
        return intent
    except Exception as exc:
        logger.warning("[IntentContext][EvalEvidence] failed: %s", exc)
        return IntentContext()
