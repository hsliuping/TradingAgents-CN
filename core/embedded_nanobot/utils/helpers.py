import base64
import json
import re
import time
from datetime import datetime
from pathlib import Path
from typing import Any

import tiktoken


TOOL_RESULT_MAX_CHARS = 16_000
TRUNCATION_SUFFIX = "\n... (truncated)"


def strip_think(text: str) -> str:
    text = re.sub(r"<think>[\s\S]*?</think>", "", text)
    text = re.sub(r"<think>[\s\S]*$", "", text)
    return text.strip()


def detect_image_mime(data: bytes) -> str | None:
    if data[:8] == b"\x89PNG\r\n\x1a\n":
        return "image/png"
    if data[:3] == b"\xff\xd8\xff":
        return "image/jpeg"
    if data[:6] in (b"GIF87a", b"GIF89a"):
        return "image/gif"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp"
    return None


def build_image_content_blocks(raw: bytes, mime: str, path: str, label: str) -> list[dict[str, Any]]:
    b64 = base64.b64encode(raw).decode()
    return [
        {
            "type": "image_url",
            "image_url": {"url": f"data:{mime};base64,{b64}"},
            "_meta": {"path": path},
        },
        {"type": "text", "text": label},
    ]


def ensure_dir(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path


def current_time_str(timezone: str | None = None) -> str:
    from zoneinfo import ZoneInfo

    try:
        tz = ZoneInfo(timezone) if timezone else None
    except Exception:
        tz = None
    now = datetime.now(tz=tz) if tz else datetime.now().astimezone()
    offset = now.strftime("%z")
    offset_fmt = f"{offset[:3]}:{offset[3:]}" if len(offset) == 5 else offset
    tz_name = timezone or (time.strftime("%Z") or "UTC")
    return f"{now.strftime('%Y-%m-%d %H:%M (%A)')} ({tz_name}, UTC{offset_fmt})"


_UNSAFE_CHARS = re.compile(r'[<>:"/\\|?*]')


def safe_filename(name: str) -> str:
    return _UNSAFE_CHARS.sub("_", name).strip()


def build_assistant_message(
    content: str | None,
    tool_calls: list[dict[str, Any]] | None = None,
    reasoning_content: str | None = None,
    thinking_blocks: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    msg: dict[str, Any] = {"role": "assistant", "content": content}
    if tool_calls:
        msg["tool_calls"] = tool_calls
    if reasoning_content is not None:
        msg["reasoning_content"] = reasoning_content
    if thinking_blocks:
        msg["thinking_blocks"] = thinking_blocks
    return msg


def truncate_text_value(text: str, max_chars: int = TOOL_RESULT_MAX_CHARS) -> str:
    if len(text) <= max_chars:
        return text
    return text[:max_chars] + TRUNCATION_SUFFIX


def build_image_placeholder(block: dict[str, Any]) -> dict[str, str]:
    path = (block.get("_meta") or {}).get("path", "")
    return {"type": "text", "text": f"[image: {path}]" if path else "[image]"}


def sanitize_content_blocks(
    content: list[dict[str, Any]],
    *,
    truncate_text: bool = False,
    drop_runtime: bool = False,
    runtime_context_tag: str | None = None,
    max_chars: int = TOOL_RESULT_MAX_CHARS,
) -> list[dict[str, Any]]:
    filtered: list[dict[str, Any]] = []
    for block in content:
        if not isinstance(block, dict):
            filtered.append(block)
            continue

        if (
            drop_runtime
            and runtime_context_tag
            and block.get("type") == "text"
            and isinstance(block.get("text"), str)
            and block["text"].startswith(runtime_context_tag)
        ):
            continue

        if (
            block.get("type") == "image_url"
            and block.get("image_url", {}).get("url", "").startswith("data:image/")
        ):
            filtered.append(build_image_placeholder(block))
            continue

        if block.get("type") == "text" and isinstance(block.get("text"), str):
            text = block["text"]
            if truncate_text:
                text = truncate_text_value(text, max_chars=max_chars)
            filtered.append({**block, "text": text})
            continue

        filtered.append(block)
    return filtered


def sanitize_tool_result_content(content: Any, max_chars: int = TOOL_RESULT_MAX_CHARS) -> Any:
    if isinstance(content, str):
        return truncate_text_value(content, max_chars=max_chars)
    if isinstance(content, list):
        return sanitize_content_blocks(content, truncate_text=True, max_chars=max_chars)
    return content


def estimate_prompt_tokens(messages: list[dict[str, Any]], tools: list[dict[str, Any]] | None = None) -> int:
    try:
        enc = tiktoken.get_encoding("cl100k_base")
        parts: list[str] = []
        for msg in messages:
            content = msg.get("content")
            if isinstance(content, str):
                parts.append(content)
            elif isinstance(content, list):
                for part in content:
                    if isinstance(part, dict) and part.get("type") == "text":
                        txt = part.get("text", "")
                        if txt:
                            parts.append(txt)
            if msg.get("tool_calls"):
                parts.append(json.dumps(msg["tool_calls"], ensure_ascii=False))
            for key in ("reasoning_content", "name", "tool_call_id"):
                value = msg.get(key)
                if isinstance(value, str) and value:
                    parts.append(value)
        if tools:
            parts.append(json.dumps(tools, ensure_ascii=False))
        return len(enc.encode("\n".join(parts))) + len(messages) * 4
    except Exception:
        return 0


def estimate_message_tokens(message: dict[str, Any]) -> int:
    content = message.get("content")
    parts: list[str] = []
    if isinstance(content, str):
        parts.append(content)
    elif isinstance(content, list):
        for part in content:
            if isinstance(part, dict) and part.get("type") == "text":
                if part.get("text"):
                    parts.append(part["text"])
            else:
                parts.append(json.dumps(part, ensure_ascii=False))
    elif content is not None:
        parts.append(json.dumps(content, ensure_ascii=False))
    if message.get("tool_calls"):
        parts.append(json.dumps(message["tool_calls"], ensure_ascii=False))
    for key in ("name", "tool_call_id", "reasoning_content"):
        value = message.get(key)
        if isinstance(value, str) and value:
            parts.append(value)
    payload = "\n".join(parts)
    if not payload:
        return 4
    try:
        enc = tiktoken.get_encoding("cl100k_base")
        return max(4, len(enc.encode(payload)) + 4)
    except Exception:
        return max(4, len(payload) // 4 + 4)


def estimate_prompt_tokens_chain(
    provider: Any,
    model: str | None,
    messages: list[dict[str, Any]],
    tools: list[dict[str, Any]] | None = None,
) -> tuple[int, str]:
    provider_counter = getattr(provider, "estimate_prompt_tokens", None)
    if callable(provider_counter):
        try:
            tokens, source = provider_counter(messages, tools, model)
            if isinstance(tokens, (int, float)) and tokens > 0:
                return int(tokens), str(source or "provider_counter")
        except Exception:
            pass
    estimated = estimate_prompt_tokens(messages, tools)
    if estimated > 0:
        return int(estimated), "tiktoken"
    return 0, "none"


def build_status_content(
    *,
    version: str,
    model: str,
    start_time: float,
    last_usage: dict[str, int],
    context_window_tokens: int,
    session_msg_count: int,
    context_tokens_estimate: int,
) -> str:
    uptime_s = int(time.time() - start_time)
    uptime = f"{uptime_s // 3600}h {(uptime_s % 3600) // 60}m" if uptime_s >= 3600 else f"{uptime_s // 60}m {uptime_s % 60}s"
    last_in = last_usage.get("prompt_tokens", 0)
    last_out = last_usage.get("completion_tokens", 0)
    ctx_total = max(context_window_tokens, 0)
    ctx_pct = int((context_tokens_estimate / ctx_total) * 100) if ctx_total > 0 else 0
    ctx_used_str = f"{context_tokens_estimate // 1000}k" if context_tokens_estimate >= 1000 else str(context_tokens_estimate)
    ctx_total_str = f"{ctx_total // 1024}k" if ctx_total > 0 else "n/a"
    return "\n".join([
        f"nanobot embedded runtime v{version}",
        f"Model: {model}",
        f"Tokens: {last_in} in / {last_out} out",
        f"Context: {ctx_used_str}/{ctx_total_str} ({ctx_pct}%)",
        f"Session: {session_msg_count} messages",
        f"Uptime: {uptime}",
    ])