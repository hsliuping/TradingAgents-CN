"""
错误处理中间件
"""

from fastapi import Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
import logging
import traceback
from typing import Callable

logger = logging.getLogger(__name__)


class ErrorHandlerMiddleware(BaseHTTPMiddleware):
    """全局错误处理中间件"""
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        try:
            response = await call_next(request)
            return response
        except Exception as exc:
            return await self.handle_error(request, exc)
    
    async def handle_error(self, request: Request, exc: Exception) -> JSONResponse:
        """处理异常并返回标准化错误响应"""
        
        # 获取请求ID
        request_id = getattr(request.state, "request_id", "unknown")
        
        # 记录错误日志
        logger.error(
            f"请求异常 - ID: {request_id}, "
            f"路径: {request.url.path}, "
            f"方法: {request.method}, "
            f"异常: {str(exc)}",
            exc_info=True
        )
        
        # 根据异常类型返回不同的错误响应
        if isinstance(exc, ValueError):
            return JSONResponse(
                status_code=400,
                content={
                    "error": {
                        "code": "VALIDATION_ERROR",
                        "message": str(exc),
                        "request_id": request_id
                    }
                }
            )
        
        elif isinstance(exc, PermissionError):
            return JSONResponse(
                status_code=403,
                content={
                    "error": {
                        "code": "PERMISSION_DENIED",
                        "message": "权限不足",
                        "request_id": request_id
                    }
                }
            )
        
        elif isinstance(exc, FileNotFoundError):
            return JSONResponse(
                status_code=404,
                content={
                    "error": {
                        "code": "RESOURCE_NOT_FOUND",
                        "message": "请求的资源不存在",
                        "request_id": request_id
                    }
                }
            )
        
        else:
            # 未知异常
            return JSONResponse(
                status_code=500,
                content={
                    "error": {
                        "code": "INTERNAL_SERVER_ERROR",
                        "message": "服务器内部错误，请稍后重试",
                        "request_id": request_id
                    }
                }
            )
