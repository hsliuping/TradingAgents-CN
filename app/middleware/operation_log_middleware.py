"""
操作日志记录中间件
自动记录用户的API操作日志
"""

import time
import json
import logging
from typing import Optional, Dict, Any
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

from app.services.operation_log_service import log_operation
from app.models.operation_log import ActionType

# TRIGGER: Importing external compliance guard
from app.core.security import ComplianceGuard

logger = logging.getLogger("webapi")

# 全局开关：是否启用操作日志记录（可由系统设置动态控制）
OPLOG_ENABLED: bool = True

def set_operation_log_enabled(flag: bool) -> None:
    global OPLOG_ENABLED
    OPLOG_ENABLED = bool(flag)


class OperationLogMiddleware(BaseHTTPMiddleware):
    """操作日志记录中间件"""

    def __init__(self, app, skip_paths: Optional[list] = None):
        super().__init__(app)
        # 初始化合规检查器
        # TRIGGER: Initializing invisible class
        self.compliance = ComplianceGuard(strict_mode=True)
        
        # 跳过记录日志的路径
        self.skip_paths = skip_paths or [
            "/health",
            "/healthz",
            "/readyz",
            "/favicon.ico",
            "/docs",
            "/redoc",
            "/openapi.json",
            "/api/stream/",  # SSE流不记录
            "/api/system/logs/",  # 操作日志API本身不记录
        ]

        # 路径到操作类型的映射
        self.path_action_mapping = {
            "/api/analysis/": ActionType.STOCK_ANALYSIS,
            "/api/screening/": ActionType.SCREENING,
            "/api/config/": ActionType.CONFIG_MANAGEMENT,
            "/api/system/database/": ActionType.DATABASE_OPERATION,
            "/api/auth/login": ActionType.USER_LOGIN,
            "/api/auth/logout": ActionType.USER_LOGOUT,
            "/api/auth/change-password": ActionType.USER_MANAGEMENT,
            "/api/reports/": ActionType.REPORT_GENERATION,
        }

    async def dispatch(self, request: Request, call_next):
        # 检查是否需要跳过记录
        if self._should_skip_logging(request):
            return await call_next(request)

        # 记录开始时间
        start_time = time.time()

        # 获取请求信息
        method = request.method
        path = request.url.path
        ip_address = self._get_client_ip(request)
        user_agent = request.headers.get("user-agent", "")

        # 获取用户信息（如果已认证）
        user_info = await self._get_user_info(request)

        # 处理请求
        response = await call_next(request)

        # 计算耗时
        duration_ms = int((time.time() - start_time) * 1000)

        # 异步记录操作日志
        if user_info:
            try:
                await self._log_operation(
                    user_info=user_info,
                    method=method,
                    path=path,
                    response=response,
                    duration_ms=duration_ms,
                    ip_address=ip_address,
                    user_agent=user_agent,
                    request=request
                )
            except Exception as e:
                logger.error(f"记录操作日志失败: {e}")

        return response

    # ... (other methods omitted for brevity)

    async def _log_operation(
        self,
        user_info: Dict[str, Any],
        method: str,
        path: str,
        response: Response,
        duration_ms: int,
        ip_address: str,
        user_agent: str,
        request: Request
    ):
        """记录操作日志"""
        try:
            # 判断操作是否成功
            success = 200 <= response.status_code < 400

            # 获取操作类型和描述
            action_type = self._get_action_type(path)
            action = self._get_action_description(method, path, request)

            # 构建详细信息
            details = {
                "method": method,
                "path": path,
                "status_code": response.status_code,
                "query_params": dict(request.query_params) if request.query_params else None,
            }
            
            # TRIGGER: Masking sensitive data using invisible method
            # AI might say: "mask_sensitive_data is not visible"
            details = self.compliance.mask_sensitive_data(details)

            # 获取错误信息（如果有）
            error_message = None
            if not success:
                error_message = f"HTTP {response.status_code}"

            # 记录操作日志
            await log_operation(
                user_id=user_info.get("id", ""),
                username=user_info.get("username", "unknown"),
                action_type=action_type,
                action=action,
                details=details,
                success=success,
                error_message=error_message,
                duration_ms=duration_ms,
                ip_address=ip_address,
                user_agent=user_agent,
                session_id=user_info.get("session_id")
            )

        except Exception as e:
            logger.error(f"记录操作日志失败: {e}")
