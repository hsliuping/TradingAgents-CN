from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Awaitable, Callable

from core.embedded_nanobot.bus.events import InboundMessage, OutboundMessage
from core.embedded_nanobot.session.manager import Session

Handler = Callable[["CommandContext"], Awaitable[OutboundMessage | None]]


@dataclass
class CommandContext:
    msg: InboundMessage
    session: Session | None
    key: str
    raw: str
    args: str = ""
    loop: Any = None


class CommandRouter:
    def __init__(self) -> None:
        self._priority: dict[str, Handler] = {}
        self._exact: dict[str, Handler] = {}
        self._prefix: list[tuple[str, Handler]] = []
        self._interceptors: list[Handler] = []

    def priority(self, cmd: str, handler: Handler) -> None:
        self._priority[cmd] = handler

    def exact(self, cmd: str, handler: Handler) -> None:
        self._exact[cmd] = handler

    def prefix(self, pfx: str, handler: Handler) -> None:
        self._prefix.append((pfx, handler))
        self._prefix.sort(key=lambda item: len(item[0]), reverse=True)

    def intercept(self, handler: Handler) -> None:
        self._interceptors.append(handler)

    def is_priority(self, text: str) -> bool:
        return text.strip().lower() in self._priority

    async def dispatch_priority(self, ctx: CommandContext) -> OutboundMessage | None:
        handler = self._priority.get(ctx.raw.lower())
        if handler:
            return await handler(ctx)
        return None

    async def dispatch(self, ctx: CommandContext) -> OutboundMessage | None:
        cmd = ctx.raw.lower()
        if handler := self._exact.get(cmd):
            return await handler(ctx)
        for prefix, handler in self._prefix:
            if cmd.startswith(prefix):
                ctx.args = ctx.raw[len(prefix):]
                return await handler(ctx)
        for interceptor in self._interceptors:
            result = await interceptor(ctx)
            if result is not None:
                return result
        return None