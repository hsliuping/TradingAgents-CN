from time import time
from typing import Any, Iterable

from langchain_core.messages import AIMessage

from tradingagents.utils.logging_init import get_logger

logger = get_logger("default")


def _chunk_to_text(chunk: Any) -> str:
    """Extract text from a LangChain streaming chunk."""
    content = getattr(chunk, "content", "")
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for item in content:
            if isinstance(item, str):
                parts.append(item)
                continue
            if isinstance(item, dict):
                text = item.get("text")
                if isinstance(text, str):
                    parts.append(text)
        return "".join(parts)
    return ""


def stream_text_response(llm: Any, prompt: Any, stage_name: str) -> AIMessage:
    """
    Stream a text-only LLM response and rebuild it into an AIMessage.

    Falls back to invoke() if the model or gateway does not support streaming
    cleanly for the current request shape.
    """
    start_time = time()
    chunk_count = 0
    collected_parts = []

    try:
        for chunk in llm.stream(prompt):
            text = _chunk_to_text(chunk)
            if text:
                collected_parts.append(text)
            chunk_count += 1

        content = "".join(collected_parts).strip()
        elapsed = time() - start_time

        if not content:
            logger.warning(
                f"⚠️ [{stage_name}] 流式响应为空，回退到非流式调用 (chunks={chunk_count}, 耗时={elapsed:.2f}秒)"
            )
            return llm.invoke(prompt)

        logger.info(
            f"🌊 [{stage_name}] 流式响应完成: chunks={chunk_count}, 长度={len(content)} 字符, 耗时={elapsed:.2f}秒"
        )
        return AIMessage(content=content)
    except Exception as exc:
        elapsed = time() - start_time
        logger.warning(
            f"⚠️ [{stage_name}] 流式调用失败，回退到非流式调用: {exc} (已耗时 {elapsed:.2f}秒)"
        )
        return llm.invoke(prompt)
