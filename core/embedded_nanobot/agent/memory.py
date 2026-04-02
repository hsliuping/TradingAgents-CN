from __future__ import annotations

import asyncio
import json
import logging
import weakref
from datetime import datetime
from pathlib import Path
from typing import Any, Callable


logger = logging.getLogger(__name__)

from core.embedded_nanobot.utils.helpers import ensure_dir, estimate_message_tokens, estimate_prompt_tokens_chain

_SAVE_MEMORY_TOOL = [{
    "type": "function",
    "function": {
        "name": "save_memory",
        "description": "Save the memory consolidation result to persistent storage.",
        "parameters": {
            "type": "object",
            "properties": {
                "history_entry": {"type": "string", "description": "A paragraph summarizing key events. Start with [YYYY-MM-DD HH:MM]."},
                "memory_update": {"type": "string", "description": "Full updated long-term memory as markdown."},
            },
            "required": ["history_entry", "memory_update"],
        },
    },
}]


def _ensure_text(value: Any) -> str:
    return value if isinstance(value, str) else json.dumps(value, ensure_ascii=False)


def _normalize_save_memory_args(args: Any) -> dict[str, Any] | None:
    if isinstance(args, str):
        args = json.loads(args)
    if isinstance(args, list):
        return args[0] if args and isinstance(args[0], dict) else None
    return args if isinstance(args, dict) else None


def _is_tool_choice_unsupported(content: str | None) -> bool:
    text = (content or "").lower()
    return any(marker in text for marker in ("tool_choice", "toolchoice", "does not support", 'should be ["none", "auto"]'))


class MemoryStore:
    _MAX_FAILURES_BEFORE_RAW_ARCHIVE = 3

    def __init__(self, workspace: Path):
        self.memory_dir = ensure_dir(workspace / "memory")
        self.memory_file = self.memory_dir / "MEMORY.md"
        self.history_file = self.memory_dir / "HISTORY.md"
        self._consecutive_failures = 0

    def read_long_term(self) -> str:
        return self.memory_file.read_text(encoding="utf-8") if self.memory_file.exists() else ""

    def write_long_term(self, content: str) -> None:
        self.memory_file.write_text(content, encoding="utf-8")

    def append_history(self, entry: str) -> None:
        with open(self.history_file, "a", encoding="utf-8") as handle:
            handle.write(entry.rstrip() + "\n\n")

    def get_memory_context(self) -> str:
        long_term = self.read_long_term()
        return f"## Long-term Memory\n{long_term}" if long_term else ""

    @staticmethod
    def _format_messages(messages: list[dict[str, Any]]) -> str:
        lines: list[str] = []
        for message in messages:
            if not message.get("content"):
                continue
            tools = f" [tools: {', '.join(message['tools_used'])}]" if message.get("tools_used") else ""
            lines.append(f"[{message.get('timestamp', '?')[:16]}] {message['role'].upper()}{tools}: {message['content']}")
        return "\n".join(lines)

    async def consolidate(self, messages: list[dict[str, Any]], provider, model: str) -> bool:
        if not messages:
            return True
        current_memory = self.read_long_term()
        prompt = f"""Process this conversation and call the save_memory tool with your consolidation.\n\n## Current Long-term Memory\n{current_memory or '(empty)'}\n\n## Conversation to Process\n{self._format_messages(messages)}"""
        chat_messages = [
            {"role": "system", "content": "You are a memory consolidation agent. Call the save_memory tool with your consolidation of the conversation."},
            {"role": "user", "content": prompt},
        ]
        try:
            forced = {"type": "function", "function": {"name": "save_memory"}}
            response = await provider.chat_with_retry(messages=chat_messages, tools=_SAVE_MEMORY_TOOL, model=model, tool_choice=forced)
            if response.finish_reason == "error" and _is_tool_choice_unsupported(response.content):
                response = await provider.chat_with_retry(messages=chat_messages, tools=_SAVE_MEMORY_TOOL, model=model, tool_choice="auto")
            if not response.has_tool_calls:
                return self._fail_or_raw_archive(messages)
            args = _normalize_save_memory_args(response.tool_calls[0].arguments)
            if args is None or "history_entry" not in args or "memory_update" not in args:
                return self._fail_or_raw_archive(messages)
            entry = _ensure_text(args["history_entry"]).strip()
            update = _ensure_text(args["memory_update"])
            if not entry:
                return self._fail_or_raw_archive(messages)
            self.append_history(entry)
            if update != current_memory:
                self.write_long_term(update)
            self._consecutive_failures = 0
            logger.info("Embedded nanobot memory consolidation done for %s messages", len(messages))
            return True
        except Exception:
            logger.exception("Embedded nanobot memory consolidation failed")
            return self._fail_or_raw_archive(messages)

    def _fail_or_raw_archive(self, messages: list[dict[str, Any]]) -> bool:
        self._consecutive_failures += 1
        if self._consecutive_failures < self._MAX_FAILURES_BEFORE_RAW_ARCHIVE:
            return False
        self._raw_archive(messages)
        self._consecutive_failures = 0
        return True

    def _raw_archive(self, messages: list[dict[str, Any]]) -> None:
        ts = datetime.now().strftime("%Y-%m-%d %H:%M")
        self.append_history(f"[{ts}] [RAW] {len(messages)} messages\n{self._format_messages(messages)}")


class MemoryConsolidator:
    _MAX_CONSOLIDATION_ROUNDS = 5
    _SAFETY_BUFFER = 1024

    def __init__(self, workspace: Path, provider, model: str, sessions, context_window_tokens: int, build_messages: Callable[..., list[dict[str, Any]]], get_tool_definitions: Callable[[], list[dict[str, Any]]], max_completion_tokens: int = 4096):
        self.store = MemoryStore(workspace)
        self.provider = provider
        self.model = model
        self.sessions = sessions
        self.context_window_tokens = context_window_tokens
        self.max_completion_tokens = max_completion_tokens
        self._build_messages = build_messages
        self._get_tool_definitions = get_tool_definitions
        self._locks: weakref.WeakValueDictionary[str, asyncio.Lock] = weakref.WeakValueDictionary()

    def get_lock(self, session_key: str) -> asyncio.Lock:
        return self._locks.setdefault(session_key, asyncio.Lock())

    async def consolidate_messages(self, messages: list[dict[str, object]]) -> bool:
        return await self.store.consolidate(messages, self.provider, self.model)

    def pick_consolidation_boundary(self, session, tokens_to_remove: int) -> tuple[int, int] | None:
        start = session.last_consolidated
        if start >= len(session.messages) or tokens_to_remove <= 0:
            return None
        removed_tokens = 0
        last_boundary: tuple[int, int] | None = None
        for index in range(start, len(session.messages)):
            message = session.messages[index]
            if index > start and message.get("role") == "user":
                last_boundary = (index, removed_tokens)
                if removed_tokens >= tokens_to_remove:
                    return last_boundary
            removed_tokens += estimate_message_tokens(message)
        return last_boundary

    def estimate_session_prompt_tokens(self, session) -> tuple[int, str]:
        history = session.get_history(max_messages=0)
        channel, chat_id = (session.key.split(":", 1) if ":" in session.key else (None, None))
        probe_messages = self._build_messages(history=history, current_message="[token-probe]", channel=channel, chat_id=chat_id)
        return estimate_prompt_tokens_chain(self.provider, self.model, probe_messages, self._get_tool_definitions())

    async def archive_messages(self, messages: list[dict[str, object]]) -> bool:
        if not messages:
            return True
        for _ in range(self.store._MAX_FAILURES_BEFORE_RAW_ARCHIVE):
            if await self.consolidate_messages(messages):
                return True
        return True

    async def maybe_consolidate_by_tokens(self, session) -> None:
        if not session.messages or self.context_window_tokens <= 0:
            return
        lock = self.get_lock(session.key)
        async with lock:
            budget = self.context_window_tokens - self.max_completion_tokens - self._SAFETY_BUFFER
            target = budget // 2
            estimated, source = self.estimate_session_prompt_tokens(session)
            if estimated <= 0 or estimated < budget:
                return
            for _ in range(self._MAX_CONSOLIDATION_ROUNDS):
                if estimated <= target:
                    return
                boundary = self.pick_consolidation_boundary(session, max(1, estimated - target))
                if boundary is None:
                    return
                end_index = boundary[0]
                chunk = session.messages[session.last_consolidated:end_index]
                if not chunk:
                    return
                if not await self.consolidate_messages(chunk):
                    return
                session.last_consolidated = end_index
                self.sessions.save(session)
                estimated, source = self.estimate_session_prompt_tokens(session)
                if estimated <= 0:
                    return