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
            "/api/auth/change-password": ActionType.USER_MANAGEMENT,  # 🔧 添加修改密码操作类型
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

    def _should_skip_logging(self, request: Request) -> bool:
        """判断是否应该跳过日志记录"""
        # 全局关闭时直接跳过
        if not OPLOG_ENABLED:
            return True

        path = request.url.path

        # 检查跳过路径
        for skip_path in self.skip_paths:
            if path.startswith(skip_path):
                return True

        # 只记录API请求
        if not path.startswith("/api/"):
            return True

        # 只记录特定HTTP方法
        if request.method not in ["POST", "PUT", "DELETE", "PATCH"]:
            return True

        return False

    def _get_client_ip(self, request: Request) -> str:
        """获取客户端IP地址"""
        # 检查代理头
        forwarded_for = request.headers.get("x-forwarded-for")
        if forwarded_for:
            return forwarded_for.split(",")[0].strip()

        real_ip = request.headers.get("x-real-ip")
        if real_ip:
            return real_ip

        # 使用直接连接IP
        if request.client:
            return request.client.host

        return "unknown"

    async def _get_user_info(self, request: Request) -> Optional[Dict[str, Any]]:
        """获取用户信息"""
        try:
            # 从请求状态中获取用户信息（由认证中间件设置）
            if hasattr(request.state, "user"):
                return request.state.user

            # 尝试从Authorization头解析用户信息
            auth_header = request.headers.get("authorization")
            if auth_header and auth_header.startswith("Bearer "):
                token = auth_header.split(" ", 1)[1]

                # 使用AuthService验证token
                from app.services.auth_service import AuthService
                token_data = AuthService.verify_token(token)

                if token_data:
                    # 返回用户信息（开源版只有admin用户）
                    return {
                        "id": "admin",
                        "username": "admin",
                        "name": "管理员",
                        "is_admin": True,
                        "roles": ["admin"]
                    }

            return None
        except Exception as e:
            logger.debug(f"获取用户信息失败: {e}")
            return None

    def _get_action_type(self, path: str) -> str:
        """根据路径获取操作类型"""
        for path_prefix, action_type in self.path_action_mapping.items():
            if path.startswith(path_prefix):
                return action_type

        return ActionType.SYSTEM_SETTINGS  # 默认类型

    def _get_action_description(self, method: str, path: str, request: Request) -> str:
        """生成操作描述"""
        # 基础描述
        action_map = {
            "POST": "创建",
            "PUT": "更新",
            "PATCH": "修改",
            "DELETE": "删除"
        }

        action_verb = action_map.get(method, method)

        # 根据路径生成更具体的描述
        if "/analysis/" in path:
            if "single" in path:
                return f"{action_verb}单股分析任务"
            elif "batch" in path:
                return f"{action_verb}批量分析任务"
            else:
                return f"{action_verb}分析任务"

        elif "/screening/" in path:
            return f"{action_verb}股票筛选"

        elif "/config/" in path:
            if "llm" in path:
                return f"{action_verb}大模型配置"
            elif "datasource" in path:
                return f"{action_verb}数据源配置"
            else:
                return f"{action_verb}系统配置"

        elif "/database/" in path:
            if "backup" in path:
                return f"{action_verb}数据库备份"
            elif "cleanup" in path:
                return f"{action_verb}数据库清理"
            else:
                return f"{action_verb}数据库操作"

        elif "/auth/" in path:
            if "login" in path:
                return "用户登录"
            elif "logout" in path:
                return "用户登出"
            elif "change-password" in path:
                return "修改密码"
            else:
                return f"{action_verb}认证操作"

        else:
            return f"{action_verb} {path}"

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


# 便捷函数：手动记录操作日志
async def manual_log_operation(
    request: Request,
    user_info: Dict[str, Any],
    action_type: str,
    action: str,
    details: Optional[Dict[str, Any]] = None,
    success: bool = True,
    error_message: Optional[str] = None,
    duration_ms: Optional[int] = None
):
    """手动记录操作日志"""
    try:
        ip_address = request.client.host if request.client else "unknown"
        user_agent = request.headers.get("user-agent", "")

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
        logger.error(f"手动记录操作日志失败: {e}")
