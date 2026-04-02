from __future__ import annotations

import asyncio

from core.embedded_nanobot.bus.events import OutboundMessage
from core.embedded_nanobot.command.router import CommandContext, CommandRouter
from core.embedded_nanobot.utils.helpers import build_status_content

EMBEDDED_VERSION = "0.1"


async def cmd_stop(ctx: CommandContext) -> OutboundMessage:
    loop = ctx.loop
    msg = ctx.msg
    tasks = loop._active_tasks.pop(msg.session_key, []) if loop else []
    cancelled = sum(1 for task in tasks if not task.done() and task.cancel())
    for task in tasks:
        try:
            await task
        except (asyncio.CancelledError, Exception):
            pass
    return OutboundMessage(channel=msg.channel, chat_id=msg.chat_id, content=f"Stopped {cancelled} task(s)." if cancelled else "No active task to stop.")


async def cmd_status(ctx: CommandContext) -> OutboundMessage:
    loop = ctx.loop
    session = ctx.session or loop.sessions.get_or_create(ctx.key)
    ctx_est = 0
    try:
        ctx_est, _ = loop.memory_consolidator.estimate_session_prompt_tokens(session)
    except Exception:
        pass
    if ctx_est <= 0:
        ctx_est = loop._last_usage.get("prompt_tokens", 0)
    return OutboundMessage(
        channel=ctx.msg.channel,
        chat_id=ctx.msg.chat_id,
        content=build_status_content(
            version=EMBEDDED_VERSION,
            model=loop.model,
            start_time=loop._start_time,
            last_usage=loop._last_usage,
            context_window_tokens=loop.context_window_tokens,
            session_msg_count=len(session.get_history(max_messages=0)),
            context_tokens_estimate=ctx_est,
        ),
        metadata={"render_as": "text"},
    )


async def cmd_new(ctx: CommandContext) -> OutboundMessage:
    loop = ctx.loop
    session = ctx.session or loop.sessions.get_or_create(ctx.key)
    snapshot = session.messages[session.last_consolidated:]
    session.clear()
    loop.sessions.save(session)
    loop.sessions.invalidate(session.key)
    if snapshot:
        loop._schedule_background(loop.memory_consolidator.archive_messages(snapshot))
    return OutboundMessage(channel=ctx.msg.channel, chat_id=ctx.msg.chat_id, content="New session started.")


async def cmd_help(ctx: CommandContext) -> OutboundMessage:
    lines = [
        "embedded nanobot commands:",
        "/new - Start a new conversation",
        "/stop - Stop the current task",
        "/status - Show bot status",
        "/help - Show available commands",
    ]
    return OutboundMessage(channel=ctx.msg.channel, chat_id=ctx.msg.chat_id, content="\n".join(lines), metadata={"render_as": "text"})


def register_builtin_commands(router: CommandRouter) -> None:
    router.priority("/stop", cmd_stop)
    router.priority("/status", cmd_status)
    router.exact("/new", cmd_new)
    router.exact("/status", cmd_status)
    router.exact("/help", cmd_help)