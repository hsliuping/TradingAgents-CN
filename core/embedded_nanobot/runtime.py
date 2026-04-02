from __future__ import annotations

import asyncio
import inspect
import json
import re
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Awaitable, Callable

from core.embedded_nanobot.agent.context import ContextBuilder
from core.embedded_nanobot.agent.hook import AgentHook, AgentHookContext
from core.embedded_nanobot.agent.memory import MemoryConsolidator
from core.embedded_nanobot.agent.runner import AgentRunSpec, AgentRunner
from core.embedded_nanobot.agent.tools.filesystem import EditFileTool, ListDirTool, ReadFileTool, WriteFileTool
from core.embedded_nanobot.agent.tools.tradingagents_bridge import TradingAgentsRegistryTool
from core.embedded_nanobot.agent.tools.registry import ToolRegistry
from core.embedded_nanobot.agent.tools.shell import ExecTool
from core.embedded_nanobot.agent.tools.web import WebFetchTool, WebSearchConfig, WebSearchTool
from core.embedded_nanobot.command.builtin import register_builtin_commands
from core.embedded_nanobot.command.router import CommandContext, CommandRouter
from core.embedded_nanobot.cron.service import CronService
from core.embedded_nanobot.providers.unified import TradingAgentsLLMProvider
from core.embedded_nanobot.session.manager import SessionManager
from core.embedded_nanobot.utils.helpers import estimate_prompt_tokens, estimate_prompt_tokens_chain, sanitize_content_blocks, sanitize_tool_result_content, strip_think
from core.tools.config import ToolCategory


@dataclass
class ExecToolConfig:
    enable: bool = True
    timeout: int = 120
    path_append: str = ""


class EmbeddedNanobotRuntime:
    CORE_TOOL_NAMES = {
        "read_file",
        "write_file",
        "edit_file",
        "list_dir",
        "exec",
        "web_search",
        "web_fetch",
    }
    MAX_DYNAMIC_TOOLS = 16
    AGENT_BUILDER_TOOL_IDS = {
        "prepare_agent_requirement_intake",
        "prepare_agent_generation_confirmation",
        "search_project_capabilities",
        "inspect_runtime_agent_configs",
        "inspect_agent_blueprints",
        "get_agent_blueprint_details",
        "inspect_agent_workshop_assets",
        "create_or_update_runtime_agent_config",
        "create_or_update_universal_agent_prompt_template",
        "bind_agent_tools_and_validate_candidate",
        "generate_confirmed_candidate_agent",
    }
    SKILL_CREATION_TOOL_IDS = {
        "start_external_skill_generation_session",
        "respond_to_external_skill_generation_session",
        "preview_external_skill_spec",
        "generate_confirmed_external_skill",
        "inspect_external_skill_generation_session",
    }
    CATEGORY_KEYWORDS = {
        ToolCategory.FUNDAMENTALS.value: ["估值", "基本面", "财务", "利润", "现金流", "分红", "roe", "pe", "pb", "peg", "ps", "股息"],
        ToolCategory.MARKET.value: ["行情", "市场", "板块", "指数", "大盘", "k线", "技术面", "成交量", "资金流", "北向"],
        ToolCategory.NEWS.value: ["新闻", "公告", "资讯", "消息", "舆情"],
        ToolCategory.SOCIAL.value: ["情绪", "社交", "热度", "讨论", "舆论"],
        ToolCategory.ASSISTANT_OPS.value: ["持仓", "报告", "计划", "自选股", "提醒", "主题", "会话", "agent", "智能体", "蓝图", "工作流"],
        ToolCategory.SCREENING.value: ["筛选", "选股", "条件", "批量"],
        ToolCategory.TRADE_REVIEW.value: ["复盘", "交易记录", "回顾"],
        ToolCategory.MCP.value: ["mcp"],
        ToolCategory.UTILITY.value: ["工具", "文件", "目录", "执行命令"],
        ToolCategory.EXTERNAL.value: ["外部", "skill", "技能", "复用", "可复用", "能力缺口", "能力沉淀"],
    }
    QUERY_STOP_TERMS = {
        "你好", "请问", "帮我", "一下", "一个", "这个", "那个", "现在", "最新", "当前", "什么", "怎么", "可以", "需要", "分析", "看看",
    }

    def __init__(self, provider: TradingAgentsLLMProvider, workspace: Path, model: str | None = None, max_iterations: int = 24, context_window_tokens: int = 65536, web_search_config: WebSearchConfig | None = None, web_proxy: str | None = None, exec_config: ExecToolConfig | None = None, cron_service: CronService | None = None, restrict_to_workspace: bool = False, timezone: str | None = None, max_session_messages: int | None = 1000):
        self.provider = provider
        self.workspace = workspace
        self.model = model or provider.get_default_model()
        self.max_iterations = max_iterations
        self.context_window_tokens = context_window_tokens
        self.web_search_config = web_search_config or WebSearchConfig()
        self.web_proxy = web_proxy
        self.exec_config = exec_config or ExecToolConfig()
        self.cron_service = cron_service
        self.restrict_to_workspace = restrict_to_workspace
        self.max_session_messages = max_session_messages
        self._start_time = time.time()
        self._last_usage: dict[str, int] = {}
        self._active_tasks: dict[str, list[asyncio.Task]] = {}
        self._background_tasks: list[asyncio.Task] = []
        self.context = ContextBuilder(workspace, timezone=timezone)
        self.sessions = SessionManager(workspace)
        self.tools = ToolRegistry()
        self.runner = AgentRunner(provider)
        self.memory_consolidator = MemoryConsolidator(workspace=workspace, provider=provider, model=self.model, sessions=self.sessions, context_window_tokens=context_window_tokens, build_messages=self.context.build_messages, get_tool_definitions=self.tools.get_definitions, max_completion_tokens=provider.generation.max_tokens)
        self.commands = CommandRouter()
        register_builtin_commands(self.commands)
        self._capability_sync_lock = asyncio.Lock()
        self._dynamic_tool_names: set[str] = set()
        self._register_default_tools()
        self._default_tool_names = set(self.tools.tool_names)

    @staticmethod
    def _extract_query_terms(text: str) -> list[str]:
        lowered = text.lower()
        terms: list[str] = []
        terms.extend(re.findall(r"[a-z0-9_]{2,}", lowered))
        for chunk in re.findall(r"[\u4e00-\u9fff]{2,}", text):
            if len(chunk) <= 4:
                terms.append(chunk)
            else:
                for size in (2, 3, 4):
                    for index in range(0, len(chunk) - size + 1):
                        terms.append(chunk[index:index + size])
        deduped: list[str] = []
        seen: set[str] = set()
        for term in terms:
            if term in seen or term in EmbeddedNanobotRuntime.QUERY_STOP_TERMS:
                continue
            seen.add(term)
            deduped.append(term)
        return deduped

    def _build_scoped_tools(self, user_message: str, skill_names: list[str] | None = None) -> tuple[ToolRegistry, dict[str, Any]]:
        scoped = ToolRegistry()
        selected_names = set(self.CORE_TOOL_NAMES)
        query = user_message.strip()
        query_lower = query.lower()
        query_terms = self._extract_query_terms(query)
        registry_scores: list[tuple[int, str, dict[str, Any]]] = []

        if skill_names and "nanobot-agent-design" in skill_names:
            selected_names.update(self.AGENT_BUILDER_TOOL_IDS)
            selected_names.update(self.SKILL_CREATION_TOOL_IDS)

        if "agent" in query_lower or "智能体" in query or "蓝图" in query or "工作流" in query:
            selected_names.update(self.AGENT_BUILDER_TOOL_IDS)

        if (
            "skill" in query_lower
            or "技能" in query
            or "复用" in query
            or "可复用" in query
            or "能力缺口" in query
            or "external skill" in query_lower
        ):
            selected_names.update(self.SKILL_CREATION_TOOL_IDS)

        for tool_name in self.tools.tool_names:
            if tool_name not in self.CORE_TOOL_NAMES and tool_name not in selected_names:
                tool = self.tools.get(tool_name)
                metadata = getattr(tool, "metadata", None)
                if metadata is None:
                    selected_names.add(tool_name)
                    continue

                score = 0
                haystack = " ".join(filter(None, [
                    str(getattr(metadata, "id", "")),
                    str(getattr(metadata, "name", "")),
                    str(getattr(metadata, "description", "")),
                    str(getattr(metadata, "when_to_use", "")),
                    str(getattr(metadata, "returns", "")),
                    " ".join(getattr(metadata, "related_tools", []) or []),
                ])).lower()
                category = str(getattr(metadata, "category", "") or "")

                for keyword in self.CATEGORY_KEYWORDS.get(category, []):
                    if keyword.lower() in query_lower or keyword in query:
                        score += 10

                if tool_name in self.AGENT_BUILDER_TOOL_IDS or tool_name in self.SKILL_CREATION_TOOL_IDS:
                    if tool_name in selected_names:
                        score += 120

                if tool_name.lower() in query_lower:
                    score += 60

                for term in query_terms:
                    if term.lower() in haystack:
                        score += 4 if len(term) <= 2 else 8

                related_tools = getattr(metadata, "related_tools", []) or []
                if any(related in query_lower for related in related_tools):
                    score += 12

                if score > 0:
                    registry_scores.append((score, tool_name, {
                        "category": category,
                        "description": getattr(metadata, "description", ""),
                    }))

        registry_scores.sort(key=lambda item: (-item[0], item[1]))
        selected_dynamic = registry_scores[:self.MAX_DYNAMIC_TOOLS]
        selected_names.update(name for _, name, _ in selected_dynamic)

        for tool_name in self.tools.tool_names:
            if tool_name in selected_names:
                tool = self.tools.get(tool_name)
                if tool is not None:
                    scoped.register(tool)

        return scoped, {
            "query_terms": query_terms,
            "selected_tool_names": list(scoped.tool_names),
            "selected_dynamic_tools": [
                {"name": name, "score": score, **meta}
                for score, name, meta in selected_dynamic
            ],
            "core_tool_names": sorted(self.CORE_TOOL_NAMES),
            "dynamic_tool_limit": self.MAX_DYNAMIC_TOOLS,
        }

    @classmethod
    async def from_database(cls, db, workspace: str | Path, preferred_model: str | None = None, **kwargs: Any) -> "EmbeddedNanobotRuntime":
        provider = await TradingAgentsLLMProvider.from_database(db, preferred_model=preferred_model)
        runtime = cls(provider=provider, workspace=Path(workspace), **kwargs)
        await runtime.sync_tradingagents_capabilities(db)
        return runtime

    def _register_default_tools(self) -> None:
        allowed_dir = self.workspace if self.restrict_to_workspace else None
        self.tools.register(ReadFileTool(workspace=self.workspace, allowed_dir=allowed_dir))
        self.tools.register(WriteFileTool(workspace=self.workspace, allowed_dir=allowed_dir))
        self.tools.register(EditFileTool(workspace=self.workspace, allowed_dir=allowed_dir))
        self.tools.register(ListDirTool(workspace=self.workspace, allowed_dir=allowed_dir))
        if self.exec_config.enable:
            self.tools.register(ExecTool(working_dir=str(self.workspace), timeout=self.exec_config.timeout, restrict_to_workspace=self.restrict_to_workspace, path_append=self.exec_config.path_append))
        self.tools.register(WebSearchTool(config=self.web_search_config, proxy=self.web_proxy))
        self.tools.register(WebFetchTool(proxy=self.web_proxy))

    async def sync_tradingagents_capabilities(self, db: Any | None = None) -> None:
        from core.tools.registry import get_tool_registry

        async with self._capability_sync_lock:
            registry = get_tool_registry()
            if db is not None:
                await self._hydrate_registry_capabilities(db, registry)
            self._register_registry_tools(registry)

    async def _hydrate_registry_capabilities(self, db: Any, registry: Any) -> None:
        try:
            from core.skills.models import SkillMetadata
            from core.skills.executor import SkillExecutor

            cursor = db.skills.find({"enabled": True})
            async for doc in cursor:
                impl = doc.get("implementation")
                params = doc.get("parameters", [])
                if not impl or not params:
                    continue
                payload = dict(doc)
                payload.pop("_id", None)
                skill = SkillMetadata(**payload)
                registry.register_function(
                    tool_id=skill.name.replace("-", "_"),
                    func=SkillExecutor.create_sync_wrapper(skill),
                    name=skill.description[:50],
                    category=skill.category,
                    description=skill.description,
                    is_online=True,
                    override=True,
                )
        except Exception:
            pass

        try:
            from core.tools.external_skill_loader import load_external_skills_to_registry

            await load_external_skills_to_registry(db, registry)
        except Exception:
            pass

        try:
            from app.services.mcp_service import MCPService

            await MCPService(db).restore_enabled_servers()
        except Exception:
            pass

    def _register_registry_tools(self, registry: Any) -> None:
        desired: set[str] = set()
        for metadata in registry.list_all():
            if not getattr(metadata, "fc_enabled", True):
                continue
            tool_name = metadata.id
            if tool_name in self._default_tool_names:
                continue
            func = registry.get_function(tool_name)
            if func is None:
                continue
            self.tools.register(TradingAgentsRegistryTool(metadata=metadata, func=func))
            desired.add(tool_name)

        for tool_name in list(self._dynamic_tool_names - desired):
            self.tools.unregister(tool_name)
        self._dynamic_tool_names = desired

    def _schedule_background(self, coro: Awaitable[Any]) -> None:
        task = asyncio.create_task(coro)
        self._background_tasks.append(task)
        task.add_done_callback(lambda item: self._background_tasks.remove(item) if item in self._background_tasks else None)

    @staticmethod
    def _drop_oldest_turn(history: list[dict[str, Any]]) -> list[dict[str, Any]]:
        if not history:
            return []
        for index in range(1, len(history)):
            if history[index].get("role") == "user":
                return history[index:]
        return []

    async def _build_capped_initial_messages(
        self,
        session,
        active_tools: ToolRegistry,
        *,
        user_message: str,
        skill_names: list[str] | None,
        media: list[str] | None,
        channel: str,
        chat_id: str,
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]], int]:
        await self.memory_consolidator.maybe_consolidate_by_tokens(session)

        history = session.get_history(max_messages=500)
        initial_messages = self.context.build_messages(
            history=history[:-1],
            current_message=user_message,
            skill_names=skill_names,
            media=media,
            channel=channel,
            chat_id=chat_id,
        )

        token_budget = max(0, self.context_window_tokens - self.provider.generation.max_tokens - 1024)
        estimated_tokens, _ = estimate_prompt_tokens_chain(
            self.provider,
            self.model,
            initial_messages,
            active_tools.get_definitions(),
        )

        while token_budget > 0 and estimated_tokens > token_budget and history:
            next_history = self._drop_oldest_turn(history)
            if next_history == history:
                break
            history = next_history
            initial_messages = self.context.build_messages(
                history=history,
                current_message=user_message,
                skill_names=skill_names,
                media=media,
                channel=channel,
                chat_id=chat_id,
            )
            estimated_tokens, _ = estimate_prompt_tokens_chain(
                self.provider,
                self.model,
                initial_messages,
                active_tools.get_definitions(),
            )

        return initial_messages, history, estimated_tokens

    def _dump_prompt_context(
        self,
        *,
        session_key: str,
        active_tools: ToolRegistry,
        tool_selection: dict[str, Any],
        initial_messages: list[dict[str, Any]],
        estimated_tokens: int,
        history: list[dict[str, Any]],
        skill_names: list[str] | None,
        channel: str,
        chat_id: str,
    ) -> Path:
        dump_dir = self.workspace / "logs" / "embedded_nanobot_context"
        dump_dir.mkdir(parents=True, exist_ok=True)

        safe_session = "".join(ch if ch.isalnum() or ch in {"-", "_", ":"} else "_" for ch in session_key).replace(":", "_")
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        dump_path = dump_dir / f"{safe_session}_{timestamp}.json"

        tool_definitions = active_tools.get_definitions()
        system_prompt = initial_messages[0].get("content") if initial_messages else ""
        payload = {
            "generated_at": datetime.now().isoformat(),
            "session_key": session_key,
            "model": self.model,
            "channel": channel,
            "chat_id": chat_id,
            "skill_names": skill_names or [],
            "estimated_prompt_tokens": estimated_tokens,
            "context_window_tokens": self.context_window_tokens,
            "max_completion_tokens": self.provider.generation.max_tokens,
            "history_message_count": len(history),
            "initial_message_count": len(initial_messages),
            "tool_definition_count": len(tool_definitions),
            "tool_selection": tool_selection,
            "token_breakdown": {
                "system_prompt": estimate_prompt_tokens([
                    {"role": "system", "content": system_prompt}
                ]),
                "messages_without_tools": estimate_prompt_tokens(initial_messages),
                "tool_definitions": estimate_prompt_tokens([], tool_definitions),
            },
            "message_summaries": [
                {
                    "index": index,
                    "role": message.get("role"),
                    "content_type": type(message.get("content")).__name__,
                    "content_chars": len(message.get("content")) if isinstance(message.get("content"), str) else 0,
                    "has_tool_calls": bool(message.get("tool_calls")),
                }
                for index, message in enumerate(initial_messages)
            ],
            "messages": initial_messages,
            "tool_definitions": tool_definitions,
        }
        dump_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        return dump_path

    def _save_turn(self, session, messages: list[dict[str, Any]], skip: int) -> None:
        runtime_tag = self.context._RUNTIME_CONTEXT_TAG
        for message in messages[skip:]:
            entry = dict(message)
            role = entry.get("role")
            content = entry.get("content")
            if role == "assistant" and not content and not entry.get("tool_calls"):
                continue
            if role == "tool":
                entry["content"] = sanitize_tool_result_content(content)
                if isinstance(entry.get("content"), list) and not entry["content"]:
                    continue
            elif role == "user":
                if isinstance(content, str) and content.startswith(runtime_tag):
                    parts = content.split("\n\n", 1)
                    if len(parts) > 1 and parts[1].strip():
                        entry["content"] = parts[1]
                    else:
                        continue
                elif isinstance(content, list):
                    filtered = sanitize_content_blocks(content, drop_runtime=True, runtime_context_tag=runtime_tag)
                    if not filtered:
                        continue
                    entry["content"] = filtered
            entry.setdefault("timestamp", datetime.now().isoformat())
            session.messages.append(entry)
        session.updated_at = datetime.now()

    async def _invoke_callback(self, callback: Callable[[str], Awaitable[None]] | None, value: str) -> None:
        if callback is None:
            return
        result = callback(value)
        if inspect.isawaitable(result):
            await result

    async def handle_message(self, user_message: str, session_key: str = "embedded:default", channel: str = "embedded", chat_id: str = "default", media: list[str] | None = None, skill_names: list[str] | None = None, on_progress: Callable[[str], Awaitable[None]] | None = None, on_stream: Callable[[str], Awaitable[None]] | None = None, on_tool_event: Callable[[dict[str, Any]], Awaitable[None]] | None = None) -> dict[str, Any]:
        raw = user_message.strip()
        session = self.sessions.get_or_create(session_key)
        if self.commands.is_priority(raw):
            outbound = await self.commands.dispatch_priority(CommandContext(msg=type("Msg", (), {"channel": channel, "chat_id": chat_id, "session_key": session_key})(), session=session, key=session_key, raw=raw, loop=self))
            return {"content": outbound.content if outbound else "", "tools_used": [], "messages": session.get_history(max_messages=0), "stop_reason": "command"}
        if on_progress:
            await self._invoke_callback(on_progress, "正在准备上下文和可用能力")
        active_tools, tool_selection = self._build_scoped_tools(raw, skill_names)
        if on_progress:
            await self._invoke_callback(on_progress, f"已选择 {len(active_tools.tool_names)} 个可用工具（核心 {len(self.CORE_TOOL_NAMES)} + 动态 {len(tool_selection['selected_dynamic_tools'])}）")
        initial_messages, history, estimated_tokens = await self._build_capped_initial_messages(
            session,
            active_tools,
            user_message=user_message,
            skill_names=skill_names,
            media=media,
            channel=channel,
            chat_id=chat_id,
        )
        if on_progress and estimated_tokens > 0:
            await self._invoke_callback(on_progress, f"上下文已准备完成，估算输入约 {estimated_tokens} tokens")
            dump_path = self._dump_prompt_context(
                session_key=session_key,
                active_tools=active_tools,
                tool_selection=tool_selection,
                initial_messages=initial_messages,
                estimated_tokens=estimated_tokens,
                history=history,
                skill_names=skill_names,
                channel=channel,
                chat_id=chat_id,
            )
            await self._invoke_callback(on_progress, f"上下文快照已写入 {dump_path}")
        runtime = self

        class _RuntimeHook(AgentHook):
            def __init__(self):
                self._stream_buf = ""

            def wants_streaming(self) -> bool:
                return on_stream is not None

            async def on_stream(self, context: AgentHookContext, delta: str) -> None:
                prev_clean = strip_think(self._stream_buf)
                self._stream_buf += delta
                new_clean = strip_think(self._stream_buf)
                incremental = new_clean[len(prev_clean):]
                if incremental and on_stream:
                    await runtime._invoke_callback(on_stream, incremental)

            async def on_stream_end(self, context: AgentHookContext, *, resuming: bool) -> None:
                self._stream_buf = ""

            async def before_execute_tools(self, context: AgentHookContext) -> None:
                if on_progress and context.tool_calls:
                    await runtime._invoke_callback(on_progress, f"准备调用工具: {', '.join(tc.name for tc in context.tool_calls)}")
                if on_tool_event and context.tool_calls:
                    for tool_call in context.tool_calls:
                        await runtime._invoke_callback(on_tool_event, {
                            "name": tool_call.name,
                            "status": "started",
                            "detail": "工具已开始执行",
                        })

            async def after_iteration(self, context: AgentHookContext) -> None:
                if on_progress and context.tool_events:
                    summaries = []
                    for event in context.tool_events:
                        name = str(event.get("name") or "unknown")
                        status = str(event.get("status") or "ok")
                        summaries.append(f"{name}({status})")
                    if summaries:
                        await runtime._invoke_callback(on_progress, f"工具执行完成: {', '.join(summaries)}")
                if on_tool_event and context.tool_events:
                    for event in context.tool_events:
                        await runtime._invoke_callback(on_tool_event, event)
                elif on_progress and context.final_content:
                    await runtime._invoke_callback(on_progress, "正在整理最终答复")

            def finalize_content(self, context: AgentHookContext, content: str | None) -> str | None:
                return strip_think(content or "") or None

        result = await self.runner.run(AgentRunSpec(initial_messages=initial_messages, tools=active_tools, model=self.model, max_iterations=self.max_iterations, hook=_RuntimeHook(), concurrent_tools=True))
        if result.stop_reason == "completed" and not (result.final_content or "").strip():
            result.stop_reason = "empty_response"
            result.final_content = "本轮模型调用已结束，但没有返回可显示的正文内容。请重试；如果问题持续出现，请检查 logs/embedded_nanobot_llm.log 中对应请求的原始响应。"
        self._last_usage = result.usage
        self._save_turn(session, result.messages, skip=1 + len(history))
        if result.tools_used:
            for message in reversed(session.messages):
                if message.get("role") == "assistant":
                    message["tools_used"] = result.tools_used
                    break
        if self.max_session_messages is not None:
            session.retain_recent_legal_suffix(self.max_session_messages)
        self.sessions.save(session)
        self._schedule_background(self.memory_consolidator.maybe_consolidate_by_tokens(session))
        return {"content": result.final_content or "", "tools_used": result.tools_used, "messages": result.messages, "stop_reason": result.stop_reason, "usage": result.usage, "tool_events": result.tool_events}