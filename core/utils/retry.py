"""
统一重试工具

提供可重试异常判断与同步/异步指数退避重试函数，
供 UnifiedLLMClient、AgentBase 等模块共享。
"""

import asyncio
import logging
import random
import time
from typing import Any, Awaitable, Callable, Optional, TypeVar

logger = logging.getLogger(__name__)

T = TypeVar("T")

RETRYABLE_KEYWORDS = (
    "choices", "null value", "connection", "timeout", "timed out",
    "rate limit", "too many requests", "server error", "500", "502", "503", "529",
    # 京东云等国内网关的限流提示
    "429", "rate_limit", "tokens limit", "rate_limited", "访问限制", "RATE_LIMIT",
)


def is_retryable(exc: Exception) -> bool:
    msg = str(exc).lower()
    return any(kw in msg for kw in RETRYABLE_KEYWORDS)


def retry_sync(
    fn: Callable[..., T],
    *args: Any,
    max_retries: int = 3,
    max_wait: int = 10,
    label: str = "retry_sync",
    retryable: Optional[Callable[[Exception], bool]] = None,
    **kwargs: Any,
) -> T:
    """同步指数退避重试。

    Args:
        fn: 要重试的可调用对象
        max_retries: 最大重试次数（不含首次调用）
        max_wait: 退避上限秒数
        label: 日志标签
        retryable: 自定义可重试判断函数，默认使用 is_retryable
    """
    _retryable = retryable or is_retryable
    last_err: Optional[Exception] = None
    for attempt in range(max_retries + 1):
        try:
            if attempt > 0:
                # 指数退避 + 随机抖动，避免多请求同步重试形成风暴（如 429 限流场景）
                wait = min(2 ** attempt, max_wait) + random.uniform(0, 1)
                logger.info("[%s] 等待 %.1fs 后重试（%d/%d）...", label, wait, attempt, max_retries)
                time.sleep(wait)
            return fn(*args, **kwargs)
        except Exception as e:
            last_err = e
            if _retryable(e) and attempt < max_retries:
                logger.warning("[%s] 调用失败（可重试）: %s", label, e)
                continue
            raise
    raise last_err  # type: ignore[misc]  # pragma: no cover


async def retry_async(
    fn: Callable[..., Awaitable[T]],
    *args: Any,
    max_retries: int = 3,
    max_wait: int = 10,
    label: str = "retry_async",
    retryable: Optional[Callable[[Exception], bool]] = None,
    **kwargs: Any,
) -> T:
    """异步指数退避重试。"""
    _retryable = retryable or is_retryable
    last_err: Optional[Exception] = None
    for attempt in range(max_retries + 1):
        try:
            if attempt > 0:
                # 指数退避 + 随机抖动，避免多请求同步重试形成风暴（如 429 限流场景）
                wait = min(2 ** attempt, max_wait) + random.uniform(0, 1)
                logger.info("[%s] 等待 %.1fs 后重试（%d/%d）...", label, wait, attempt, max_retries)
                await asyncio.sleep(wait)
            return await fn(*args, **kwargs)
        except Exception as e:
            last_err = e
            if _retryable(e) and attempt < max_retries:
                logger.warning("[%s] 调用失败（可重试）: %s", label, e)
                continue
            raise
    raise last_err  # type: ignore[misc]  # pragma: no cover
