"""
请求ID/Trace-ID 中间件
- 为每个请求生成唯一 ID（trace_id），写入 request.state 与响应头
- 将 trace_id 写入 logging 的 contextvars，使所有日志自动带出
"""

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
import uuid
import time
import logging
from typing import Callable

from app.core.logging_context import trace_id_var

logger = logging.getLogger(__name__)


class RequestIDMiddleware(BaseHTTPMiddleware):
    """请求ID和日志中间件（trace_id）"""

    # 不记录日志的路径（健康检查等高频请求）
    SKIP_LOG_PATHS = {"/api/health", "/health", "/api/ws/notifications"}

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # 生成请求ID/trace_id
        trace_id = str(uuid.uuid4())
        request.state.request_id = trace_id  # 兼容现有字段名
        request.state.trace_id = trace_id

        # 将 trace_id 写入 contextvars
        token = trace_id_var.set(trace_id)

        # 记录请求开始时间
        start_time = time.time()

        # 判断是否需要记录日志
        should_log = request.url.path not in self.SKIP_LOG_PATHS

        try:
            # 处理请求
            response = await call_next(request)

            # 计算处理时间
            process_time = time.time() - start_time

            # 添加响应头
            response.headers["X-Trace-ID"] = trace_id
            response.headers["X-Request-ID"] = trace_id  # 兼容
            response.headers["X-Process-Time"] = f"{process_time:.3f}"

            # 合并为单条日志（跳过高频路径）
            if should_log:
                logger.info(
                    f"{request.method} {request.url.path} - {response.status_code} - {process_time:.3f}s"
                )

            return response

        except Exception as exc:
            # 计算处理时间
            process_time = time.time() - start_time

            # 记录请求异常信息
            logger.error(
                f"{request.method} {request.url.path} - ERROR - {process_time:.3f}s - {str(exc)}"
            )
            raise

        finally:
            # 清理 contextvar，避免泄露到后续请求
            try:
                trace_id_var.reset(token)
            except Exception:
                pass
