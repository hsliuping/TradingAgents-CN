from __future__ import annotations

import asyncio
from pathlib import Path
from typing import ClassVar
from typing import Any

from core.embedded_nanobot.runtime import EmbeddedNanobotRuntime
from core.tools.context import set_current_assistant_thread_id, set_current_user_id


class EmbeddedNanobotService:
    _runtime_cache: ClassVar[dict[tuple[str, str | None], EmbeddedNanobotRuntime]] = {}
    _runtime_locks: ClassVar[dict[tuple[str, str | None], asyncio.Lock]] = {}

    def __init__(self, db, workspace: str | Path, preferred_model: str | None = None):
        self._db = db
        self._workspace = Path(workspace)
        self._preferred_model = preferred_model

    def _cache_key(self) -> tuple[str, str | None]:
        return (str(self._workspace.resolve()), self._preferred_model)

    async def get_runtime(self) -> EmbeddedNanobotRuntime:
        cache_key = self._cache_key()
        cached = self._runtime_cache.get(cache_key)
        if cached is not None:
            return cached

        lock = self._runtime_locks.setdefault(cache_key, asyncio.Lock())
        async with lock:
            cached = self._runtime_cache.get(cache_key)
            if cached is not None:
                return cached
            runtime = await EmbeddedNanobotRuntime.from_database(
                self._db,
                workspace=self._workspace,
                preferred_model=self._preferred_model,
                restrict_to_workspace=False,
            )
            self._runtime_cache[cache_key] = runtime
            return runtime

    async def chat(
        self,
        user_message: str,
        session_key: str = "embedded:default",
        user_id: str | None = None,
        current_thread_id: str | None = None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        runtime = await self.get_runtime()
        await runtime.sync_tradingagents_capabilities(self._db)

        user_token = set_current_user_id(user_id) if user_id else None
        thread_token = set_current_assistant_thread_id(current_thread_id) if current_thread_id else None
        try:
            return await runtime.handle_message(user_message=user_message, session_key=session_key, **kwargs)
        finally:
            if thread_token is not None:
                thread_token.var.reset(thread_token)
            if user_token is not None:
                user_token.var.reset(user_token)