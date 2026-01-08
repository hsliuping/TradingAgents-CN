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

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # 生成请求ID/trace_id
        trace_id = str(uuid.uuid4())
        request.state.request_id = trace_id  # 兼容现有字段名
        request.state.trace_id = trace_id

        # 将 trace_id 写入 contextvars
        token = trace_id_var.set(trace_id)

        # 记录请求开始时间
        start_time = time.time()

        # 记录请求信息
        logger.info(
            f"请求开始 - trace_id: {trace_id}, "
            f"方法: {request.method}, 路径: {request.url.path}, "
            f"客户端: {request.client.host if request.client else 'unknown'}"
        )

        try:
            # 处理请求
            response = await call_next(request)

            # 计算处理时间
            process_time = time.time() - start_time

            # 添加响应头
            response.headers["X-Trace-ID"] = trace_id
            response.headers["X-Request-ID"] = trace_id  # 兼容
            response.headers["X-Process-Time"] = f"{process_time:.3f}"

            # 记录请求完成信息
            logger.info(
                f"请求完成 - trace_id: {trace_id}, 状态码: {response.status_code}, 处理时间: {process_time:.3f}s"
            )

            return response

        except Exception as exc:
            # 计算处理时间
            process_time = time.time() - start_time

            # 记录请求异常信息
            logger.error(
                f"请求异常 - trace_id: {trace_id}, 处理时间: {process_time:.3f}s, 异常: {str(exc)}"
            )
            raise

        finally:
            # 清理 contextvar，避免泄露到后续请求
            try:
                trace_id_var.reset(token)
            except Exception:
                pass
