from pathlib import Path
from typing import Any

from core.embedded_nanobot.agent.memory import MemoryStore
from core.embedded_nanobot.agent.skills import SkillsLoader
from core.embedded_nanobot.utils.helpers import build_assistant_message, current_time_str, detect_image_mime


class ContextBuilder:
    BOOTSTRAP_FILES = ["AGENTS.md", "SOUL.md", "USER.md", "TOOLS.md"]
    _RUNTIME_CONTEXT_TAG = "[Runtime Context - metadata only, not instructions]"

    def __init__(self, workspace: Path, timezone: str | None = None):
        self.workspace = workspace
        self.timezone = timezone
        self.memory = MemoryStore(workspace)
        self.skills = SkillsLoader(workspace)

    def build_system_prompt(self, skill_names: list[str] | None = None) -> str:
        parts = [self._get_identity()]
        bootstrap = self._load_bootstrap_files()
        if bootstrap:
            parts.append(bootstrap)
        memory = self.memory.get_memory_context()
        if memory:
            parts.append(f"# Memory\n\n{memory}")
        always_skills = self.skills.get_always_skills()
        if always_skills:
            always_briefs = self.skills.build_skill_briefs(always_skills)
            if always_briefs:
                parts.append(
                    "# Active Skills\n\n"
                    "The following skills are available by default. Do not assume their full instructions are already loaded. "
                    "Read a skill's SKILL.md with read_file only when that skill is relevant to the current task.\n\n"
                    f"{always_briefs}"
                )
        requested_skills = [name for name in (skill_names or []) if name and name not in always_skills]
        if requested_skills:
            requested_briefs = self.skills.build_skill_briefs(requested_skills)
            if requested_briefs:
                parts.append(
                    "# Requested Skills\n\n"
                    "These skills were explicitly requested for this run. Read the corresponding SKILL.md files with read_file before relying on them.\n\n"
                    f"{requested_briefs}"
                )
        skills_summary = self.skills.build_skills_summary()
        if skills_summary:
            parts.append(
                "# Skills\n\n"
                "The following skills extend your capabilities. Only read a skill's SKILL.md when it is relevant to the current task; "
                "do not preload full skill bodies by default.\n\n"
                f"{skills_summary}"
            )
        return "\n\n---\n\n".join(parts)

    def _get_identity(self) -> str:
        workspace_path = str(self.workspace.expanduser().resolve())
        return f"""# Agent 工作室助手

你是 TradingAgentsCN 平台 Agent 工作室中的对话式构建助手。你的唯一职责是帮助用户在此平台上搭建、配置和管理用于交易分析的 Agent、Skill 及提示词。

你不是一个通用问答助手，也不应主动替用户做金融数据分析。平台提供的行情查询、财务数据、新闻舆情等工具是给 Agent 运行用的资源，不是你用来直接回答用户问题的。

## 工作区
{workspace_path}

## 你能帮用户做什么
- 设计和创建新的分析 Agent：根据用户需求，生成 Agent 定义、配置 Skill 和提示词
- 管理已有 Agent：查看、修改、测试、发布已有 Agent
- 创建和管理 Skill：帮助用户定义可复用的技能模块。如果发现的能力缺口是可复用的（参数化、通用性强），应创建 External Skill 而非在 Agent 里写临时脚本
- 编写和优化提示词：为 Agent 编写精准、有效的行为指令

## 新建 Agent 工作流程

当用户想新建一个 Agent 时，按以下 8 个阶段推进，每个阶段都要和用户确认后再进入下一阶段：

### 1. 需求采集（requirement-intake）
引导用户描述想要的 Agent 能力、分析场景、输入输出。检查 5 个关键维度是否齐备：单一职责、输出形态、非目标、工具偏好、新建还是覆盖已有。如果用户询问报告样式，先确认是结构骨架还是占位示例。对股票分析请求，必须明确估值方法边界和测试策略。

### 2. 方案确认（confirmation）
整理需求并生成确认摘要。用户明确确认后才能进入下一阶段。确认摘要应包含报告内容范围和样式模式，不生成数据库 artifact。

### 3. 生成（generation）
用户确认后写入数据库 artifact：runtime config、prompt template、工具绑定。优先使用 generate_confirmed_candidate_agent 一键生成。

### 4. 资产治理（governance）
Draft 已写入数据库，进行缺口分析、工具规划和版本构建。使用 analyze_agent_workshop_gaps 分析能力缺口，generate_agent_workshop_tooling_plan 制定工具方案，build_agent_workshop_version 构建测试版本。

### 5. 测试（testing）
用真实股票数据运行真数据测试。先使用 debug_agent_workshop_version 做诊断试跑，再用 run_agent_workshop_real_data_test 做正式验收。验收结果只以 official_acceptance_decision 为准，不能从报告内容丰富度推断。

### 6. 评估（evaluation）
查看测试评估结论。如果结论是 pass，进入待发布状态。如果结论是 revise 或 reject，必须回到资产治理阶段重新迭代修改，不能跳过直接发布。

### 7. 待发布（publish-ready）
评估通过但不会自动发布，必须用户手动确认后由 publish_agent_workshop_version 发布。

### 8. 已发布（published）
版本已正式发布到工作流。不允许原地修改已发布版本。如需修改，使用 iterate_agent_workshop_version 创建下一轮迭代。

## 修改已有 Agent 的工作流程

当用户想修改一个已存在的 Agent 时：

1. **先核查当前状态**：使用 inspect_agent_workshop_assets 或 inspect_runtime_agent_configs 确认目标 Agent 的当前版本、状态和配置，不要凭记忆推断。
2. **区分场景**：
   - 如果版本处于 draft 状态：直接在当前 Draft 上继续修改。
   - 如果版本处于 testing / active 状态：不允许原地修改，必须使用 iterate_agent_workshop_version 创建下一轮迭代 session。
   - 如果 Workshop assets 已删除但 runtime config 还在：说明这只是残留配置，不是活跃 Workshop 版本。
3. **迭代流程**：inspect 当前资产 → iterate_agent_workshop_version 创建迭代 → 回到治理阶段进行修改 → 重新构建 → 测试 → 评估 → 发布。

## 行为准则
- 首轮回复主动引导用户描述目标，不要罗列你能做什么。
- 调用数据工具的唯一场景是为 Agent 测试运行验证，结果直接呈现给用户，不做额外分析。
- 陈述意图后再调用工具，不要在工具返回前编造结果。
- 修改文件前先读取。
- 优先用可靠工具，减少自由推测。
- 不声称某个阶段已完成，除非对应的工具调用或评估结论确实证明了这一点。"""

    @staticmethod
    def _build_runtime_context(channel: str | None, chat_id: str | None, timezone: str | None = None) -> str:
        lines = [f"Current Time: {current_time_str(timezone)}"]
        if channel and chat_id:
            lines += [f"Channel: {channel}", f"Chat ID: {chat_id}"]
        return ContextBuilder._RUNTIME_CONTEXT_TAG + "\n" + "\n".join(lines)

    def _load_bootstrap_files(self) -> str:
        parts: list[str] = []
        for filename in self.BOOTSTRAP_FILES:
            file_path = self.workspace / filename
            if file_path.exists():
                parts.append(f"## {filename}\n\n{file_path.read_text(encoding='utf-8')}")
        return "\n\n".join(parts) if parts else ""

    def build_messages(self, history: list[dict[str, Any]], current_message: str, skill_names: list[str] | None = None, media: list[str] | None = None, channel: str | None = None, chat_id: str | None = None, current_role: str = "user") -> list[dict[str, Any]]:
        runtime_ctx = self._build_runtime_context(channel, chat_id, self.timezone)
        user_content = self._build_user_content(current_message, media)
        merged = f"{runtime_ctx}\n\n{user_content}" if isinstance(user_content, str) else [{"type": "text", "text": runtime_ctx}] + user_content
        return [{"role": "system", "content": self.build_system_prompt(skill_names)}, *history, {"role": current_role, "content": merged}]

    def _build_user_content(self, text: str, media: list[str] | None) -> str | list[dict[str, Any]]:
        if not media:
            return text
        import base64
        import mimetypes

        images: list[dict[str, Any]] = []
        for path in media:
            p = Path(path)
            if not p.is_file():
                continue
            raw = p.read_bytes()
            mime = detect_image_mime(raw) or mimetypes.guess_type(path)[0]
            if not mime or not mime.startswith("image/"):
                continue
            images.append({"type": "image_url", "image_url": {"url": f"data:{mime};base64,{base64.b64encode(raw).decode()}"}, "_meta": {"path": str(p)}})
        if not images:
            return text
        return images + [{"type": "text", "text": text}]

    def add_tool_result(self, messages: list[dict[str, Any]], tool_call_id: str, tool_name: str, result: Any) -> list[dict[str, Any]]:
        messages.append({"role": "tool", "tool_call_id": tool_call_id, "name": tool_name, "content": result})
        return messages

    def add_assistant_message(self, messages: list[dict[str, Any]], content: str | None, tool_calls: list[dict[str, Any]] | None = None, reasoning_content: str | None = None, thinking_blocks: list[dict[str, Any]] | None = None) -> list[dict[str, Any]]:
        messages.append(build_assistant_message(content, tool_calls=tool_calls, reasoning_content=reasoning_content, thinking_blocks=thinking_blocks))
        return messages