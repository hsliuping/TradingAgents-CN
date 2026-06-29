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


class IntentStage(str, Enum):
    """对话阶段枚举。"""
    EXPLORING = "exploring"              # 用户在探索/描述需求
    CAPABILITY_CHECK = "capability_check"  # 正在检查能力缺口
    DRAFT_PREPARING = "draft_preparing"    # 正在准备工坊草稿
    CONFIRMATION_PENDING = "confirmation_pending"  # 等待用户确认生成
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
        task: Optional[Dict[str, str]] = None,
        linked_skill: Optional[Dict[str, str]] = None,
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
            "- 用户说「确认」或「好的」时，如果当前阶段是 confirmation_pending，则执行生成",
            "- 执行任何写操作（create/build/iterate/publish）前，必须确认 spec_id 与 intent context 一致",
            "- 如果一个 agent_id 不是 intent context 中的 spec_id，拒绝操作并提示用户",
            "- 如果当前正在为 Agent 解决 gap 或创建 Skill，完成 Skill 后必须回到父 Agent 继续 build/test/iterate，不要把 Skill 当成最终目标",
            "- 回答进度时必须按任务链说明：父 Agent 状态、当前 gap/skill 状态、下一步动作",
            "",
        ])

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
    task: Optional[Dict[str, str]] = None,
    linked_skill: Optional[Dict[str, str]] = None,
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
            task=task,
            linked_skill=linked_skill,
        )
        ctx["intent"] = intent.to_dict()
        # 同步顶层字段，兼容现有前端/工具过滤逻辑
        if intent.spec_id:
            ctx["spec_id"] = intent.spec_id
        if intent.spec_name:
            ctx["spec_name"] = intent.spec_name
        set_current_assistant_thread_context(ctx)
        logger.info(
            "[IntentContext][Update] action=%s stage=%s spec_id=%s spec_name=%s",
            action, stage, spec_id, spec_name,
        )
        return intent
    except Exception as exc:
        logger.warning("[IntentContext][Update] failed: %s", exc)
        return IntentContext()
