"""
全局认证守卫中间件
保护所有 /api 路由，仅放行白名单路径。
"""

import logging
from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger(__name__)

PUBLIC_PATH_PREFIXES = (
    "/api/health",
    "/api/auth/login",
    "/api/auth/refresh",
    "/api/auth/register",
    "/api/gateway/",
    "/api/system/info",
    "/docs",
    "/openapi.json",
    "/redoc",
    "/static",
)

PUBLIC_EXACT_PATHS = frozenset({
    "/",
    "/health",
    "/favicon.ico",
})


class AuthGuardMiddleware(BaseHTTPMiddleware):
    """
    全局认证守卫 — 拦截所有未认证的 /api 请求。

    已受保护的端点（使用 Depends(get_current_user)）不受影响，
    此中间件为那些遗漏了 Depends 的路由提供兜底保护。
    """

    async def dispatch(self, request: Request, call_next):
        if request.method == "OPTIONS":
            return await call_next(request)

        path = request.url.path

        if path in PUBLIC_EXACT_PATHS:
            return await call_next(request)

        for prefix in PUBLIC_PATH_PREFIXES:
            if path.startswith(prefix):
                return await call_next(request)

        if not path.startswith("/api"):
            return await call_next(request)

        if request.headers.get("upgrade", "").lower() == "websocket":
            return await call_next(request)

        # --- JWT ---
        auth_header = request.headers.get("authorization", "")
        if auth_header.lower().startswith("bearer "):
            token = auth_header.split(" ", 1)[1]
            try:
                from app.services.auth_service import AuthService
                token_data = AuthService.verify_token(token)
            except Exception:
                logger.warning(
                    "AuthGuard JWT 校验异常: method=%s path=%s",
                    request.method,
                    path,
                    exc_info=True,
                )
            else:
                if token_data:
                    return await call_next(request)
                logger.info(
                    "AuthGuard JWT 校验失败: method=%s path=%s token_prefix=%s",
                    request.method,
                    path,
                    token[:12],
                )
        elif auth_header:
            logger.info(
                "AuthGuard 收到非 Bearer Authorization: method=%s path=%s prefix=%s",
                request.method,
                path,
                auth_header[:24],
            )

        # --- Session cookie ---
        try:
            user_id = request.session.get("user_id") if "session" in request.scope else None
            if user_id:
                return await call_next(request)
        except Exception:
            logger.warning(
                "AuthGuard 读取 Session Cookie 异常: method=%s path=%s",
                request.method,
                path,
                exc_info=True,
            )

        logger.warning(
            "AuthGuard 拦截未认证请求: method=%s path=%s has_authorization=%s has_session=%s",
            request.method,
            path,
            bool(auth_header),
            bool(request.session.get("user_id")) if "session" in request.scope else False,
        )
        return JSONResponse(
            status_code=401,
            content={
                "error": {
                    "code": "UNAUTHORIZED",
                    "message": "Authentication required",
                }
            },
        )
