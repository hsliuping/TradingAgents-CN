"""
Nanobot 上下文注入策略（轻量版）

职责：决定哪些上下文 block 允许注入 Agent Builder 的 prompt。
这是 P0 止血方案，后续演进为完整 ContextAssembler。

核心规则：
- Agent Builder 模式下，禁止注入文件 Memory（MEMORY.md）。
- Agent Builder 模式下，不依赖 Mem0，所有记忆走 MongoDB。
- 所有模式下，注入的 block 必须标注 source / authority。

使用方式：
    from core.embedded_nanobot.agent.context_injection_policy import (
        InjectionPolicy,
        should_inject_file_memory,
        should_inject_mem0_lessons,
        get_agent_builder_hard_rules,
    )
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


class InjectionMode:
    """上下文注入模式"""

    AGENT_BUILDER = "agent_builder"
    GENERAL = "general"
    ANALYSIS = "analysis"


class BlockAuthority:
    """上下文块权威等级"""

    SOURCE_OF_TRUTH = "source_of_truth"
    RUNTIME_STATE = "runtime_state"
    ADVISORY = "advisory"
    CANDIDATE = "candidate"
    AUDIT_ONLY = "audit_only"


class ContextBlock:
    """一个上下文注入块"""

    __slots__ = ("name", "source", "authority", "scope", "validity", "content")

    def __init__(
        self,
        name: str,
        content: str,
        *,
        source: str = "unknown",
        authority: str = BlockAuthority.ADVISORY,
        scope: str = "unknown",
        validity: str = "active",
    ):
        self.name = name
        self.source = source
        self.authority = authority
        self.scope = scope
        self.validity = validity
        self.content = content

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "source": self.source,
            "authority": self.authority,
            "scope": self.scope,
            "validity": self.validity,
            "content_chars": len(self.content),
        }


def detect_injection_mode(
    *,
    channel: str | None = None,
    spec_id: str | None = None,
    tool_selection: dict[str, Any] | None = None,
) -> str:
    """根据上下文检测当前注入模式。

    Returns:
        InjectionMode.AGENT_BUILDER / GENERAL / ANALYSIS
    """
    if channel == "agent_workshop":
        return InjectionMode.AGENT_BUILDER
    if spec_id and str(spec_id).strip():
        return InjectionMode.AGENT_BUILDER
    if tool_selection and tool_selection.get("agent_builder_governance", {}).get("enabled"):
        return InjectionMode.AGENT_BUILDER
    return InjectionMode.GENERAL


def should_inject_file_memory(mode: str) -> bool:
    """Agent Builder 模式下禁止注入文件 Memory（MEMORY.md）。

    文件 Memory 没有结构化生命周期，无法区分 active/deleted，
    会导致旧 Agent 的废弃方案污染当前新建流程。
    """
    if mode == InjectionMode.AGENT_BUILDER:
        logger.info("[InjectionPolicy] ❌ file_memory blocked — agent_builder mode does not allow MEMORY.md injection")
        return False
    return True


def should_inject_mem0_lessons(mode: str) -> bool:
    """Agent Builder 模式下不依赖 Mem0。

    Agent Builder 的记忆检索全部走 MongoDB Ledger，
    Mem0 仅用于通用对话场景。
    """
    if mode == InjectionMode.AGENT_BUILDER:
        logger.info("[InjectionPolicy] ❌ mem0_lessons blocked — agent_builder mode does not use Mem0")
        return False
    return True


def get_agent_builder_hard_rules() -> str:
    """返回 Agent Builder 系统 prompt 硬规则。

    这些规则必须在每轮对话中注入到 Agent Builder 的 system prompt 中。
    """
    return """## Agent Builder 硬规则（必须遵守）

### 需求沟通硬规则：抛砖引玉，不做问卷
1. 你是财经产品专家，不是需求访谈机器人。用户提出常见财经 Agent 方向时，必须先给出专业默认方案草稿。
2. 默认值优先：A 股优先、结构化 Markdown 报告优先、只做研究不给交易建议、自动包含风险提示、默认使用平台内置数据源和工具、默认用真实 A 股样例测试。
3. 一次最多问 1 个真正关键的问题；禁止列出 3 个以上问题让用户逐项回答。
4. 对“多维估值助手”这类常见需求，默认采用：行业估值对比 + 历史估值水位 + DCF 内在价值 + 综合判断 + 风险提示；默认不纳入技术面、资金流、新闻舆情。
5. 正确表达格式：先说“我建议默认这样做”，列出职责/输入/输出章节/边界/测试样例；最后只问“如果这个默认方向可以，我就按它出确认稿；如有特殊偏好告诉我”。
6. 禁止问用户“你用什么数据源/数据终端”。平台内置数据源和工具由系统自动处理，除非需要外部数据源才提示用户。

### 选项指代硬规则
7. 用户提到"方案 A/B/C""选项 X""确认""按这个""好的"等指代性表述时，你只能基于**当前线程最近一次你明确给出的选项**解释。
8. 如果当前线程没有给出过对应选项，**禁止从历史 Memory 或旧 Agent 记录中猜测含义**。
9. 无法确定时，必须向用户澄清："请问你指的是我刚才给出的哪一个方案/选项？"
10. **任何情况下**，已删除 Agent 的旧方案、旧工具绑定、旧 gap 结论都不能作为当前选项的依据。
11. 用户回复「可以」「好的」「没问题」「按这个」「行」等简短认可时，如果没有其他明显歧义，视为对**最近一个待确认选项/问题**的认可，不要当成新话题或重新开始对话。
12. 用户回复只包含选项编号（如「1」「第一个」「A」）时，直接解析为 pending_options 中对应选项，不要追问。
13. 如果用户说「刚才那个」「就按之前说的」但当前线程没有 pending_options，可以查看 last_proposed_items；如果两者都没有，必须追问，不能猜测。"""


def build_context_block_audit(
    blocks: list[ContextBlock],
    *,
    thread_id: str = "",
    mode: str = "",
    blocked_reasons: dict[str, str] | None = None,
) -> dict[str, Any]:
    """生成上下文注入审计日志。

    Returns:
        审计日志 dict，供 logger.info 使用。
    """
    included = [b.to_dict() for b in blocks]
    blocked = []
    if blocked_reasons:
        for name, reason in blocked_reasons.items():
            blocked.append({"name": name, "reason": reason})

    return {
        "event": "nanobot_context_injection",
        "thread_id": thread_id,
        "mode": mode,
        "included": included,
        "blocked": blocked,
        "total_chars": sum(len(b.content) for b in blocks),
    }


class InjectionPolicy:
    """上下文注入策略（类封装，方便后续扩展）。"""

    def __init__(self, mode: str = InjectionMode.GENERAL):
        self.mode = mode
        self._blocks: list[ContextBlock] = []
        self._blocked: dict[str, str] = {}

    @property
    def is_agent_builder(self) -> bool:
        return self.mode == InjectionMode.AGENT_BUILDER

    def add_block(self, block: ContextBlock) -> None:
        self._blocks.append(block)

    def try_add_file_memory(self, content: str) -> bool:
        """尝试注入文件 Memory。Agent Builder 模式下被阻止。"""
        if not should_inject_file_memory(self.mode):
            self._blocked["file_memory"] = "agent_builder mode blocks file memory"
            return False
        if not content.strip():
            return False
        self._blocks.append(ContextBlock(
            name="file_memory",
            content=content,
            source="file",
            authority=BlockAuthority.AUDIT_ONLY,
            scope="workspace",
            validity="unknown",
        ))
        return True

    def try_add_mem0_lessons(self, content: str) -> bool:
        """尝试注入 Mem0 历史教训。Agent Builder 模式下被阻止。"""
        if not should_inject_mem0_lessons(self.mode):
            self._blocked["mem0_lessons"] = "agent_builder mode does not use Mem0"
            return False
        if not content.strip():
            return False
        self._blocks.append(ContextBlock(
            name="mem0_lessons",
            content=content,
            source="mem0",
            authority=BlockAuthority.ADVISORY,
            scope="reusable_lesson",
            validity="active",
        ))
        return True

    def add_flow_guidance(self, content: str) -> None:
        if not content.strip():
            return
        self._blocks.append(ContextBlock(
            name="flow_guidance",
            content=content,
            source="flow_controller",
            authority=BlockAuthority.SOURCE_OF_TRUTH,
            scope="current_phase",
            validity="active",
        ))

    def add_project_memory(self, content: str) -> None:
        if not content.strip():
            return
        self._blocks.append(ContextBlock(
            name="project_memory",
            content=content,
            source="mongodb",
            authority=BlockAuthority.SOURCE_OF_TRUTH,
            scope="project_rules",
            validity="active",
        ))

    def add_hard_rules(self, content: str) -> None:
        if not content.strip():
            return
        self._blocks.append(ContextBlock(
            name="hard_rules",
            content=content,
            source="system",
            authority=BlockAuthority.SOURCE_OF_TRUTH,
            scope="agent_builder_rules",
            validity="active",
        ))

    def add_spec_focus(self, content: str) -> None:
        if not content.strip():
            return
        self._blocks.append(ContextBlock(
            name="spec_focus",
            content=content,
            source="mongodb",
            authority=BlockAuthority.SOURCE_OF_TRUTH,
            scope="current_spec",
            validity="active",
        ))

    def get_merged_guidance(self) -> str | None:
        """获取合并后的系统指导文本。"""
        parts = [b.content for b in self._blocks if b.content.strip()]
        if not parts:
            return None
        return "\n\n".join(parts)

    def get_audit(self, thread_id: str = "") -> dict[str, Any]:
        """获取审计日志。"""
        return build_context_block_audit(
            self._blocks,
            thread_id=thread_id,
            mode=self.mode,
            blocked_reasons=self._blocked,
        )