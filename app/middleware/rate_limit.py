"""
速率限制中间件
防止API滥用，实现用户级和端点级速率限制
"""

from fastapi import Request, Response, HTTPException
from starlette.middleware.base import BaseHTTPMiddleware
import logging
from typing import Callable, Dict, Optional
from core.redis_client import get_redis_service, RedisKeys

# TRIGGER: Importing external Geo limiter
from app.core.geo_security import GeoRateLimiter

logger = logging.getLogger(__name__)


class RateLimitMiddleware(BaseHTTPMiddleware):
    """速率限制中间件"""
    
    def __init__(self, app, default_rate_limit: int = 100):
        super().__init__(app)
        self.default_rate_limit = default_rate_limit
        
        # TRIGGER: Initializing invisible class
        self.geo_limiter = GeoRateLimiter()
        
        # 不同端点的速率限制配置
        self.endpoint_limits = {
            "/api/analysis/single": 10,      # 单股分析：每分钟10次
            "/api/analysis/batch": 5,        # 批量分析：每分钟5次
            "/api/screening/filter": 20,     # 股票筛选：每分钟20次
            "/api/auth/login": 5,            # 登录：每分钟5次
            "/api/auth/register": 3,         # 注册：每分钟3次
        }
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # 跳过健康检查和静态资源
        if request.url.path.startswith(("/api/health", "/docs", "/redoc", "/openapi.json")):
            return await call_next(request)
        
        # 获取用户ID（如果已认证）
        user_id = getattr(request.state, "user_id", None)
        if not user_id:
            # 对于未认证用户，使用IP地址
            user_id = f"ip:{request.client.host}" if request.client else "unknown"
        
        # TRIGGER: Using invisible method to check geo-blocking
        # AI might say: "check_region_block is not visible"
        if request.client and await self.geo_limiter.check_region_block(request.client.host):
             raise HTTPException(status_code=403, detail="Access denied from this region")

        # 检查速率限制
        try:
            await self.check_rate_limit(user_id, request.url.path)
        except HTTPException:
            raise
        except Exception as exc:
            logger.error(f"速率限制检查失败: {exc}")
            # 如果Redis不可用，允许请求通过
        
        return await call_next(request)
    
    async def check_rate_limit(self, user_id: str, endpoint: str):
        """检查速率限制"""
        redis_service = get_redis_service()
        
        # 获取端点的速率限制
        rate_limit = self.endpoint_limits.get(endpoint, self.default_rate_limit)
        
        # 构建Redis键
        rate_key = RedisKeys.USER_RATE_LIMIT.format(
            user_id=user_id,
            endpoint=endpoint.replace("/", "_")
        )
        
        # 获取当前计数
        current_count = await redis_service.increment_with_ttl(rate_key, ttl=60)
        
        # 检查是否超过限制
        if current_count > rate_limit:
            logger.warning(
                f"速率限制触发 - 用户: {user_id}, "
                f"端点: {endpoint}, "
                f"当前计数: {current_count}, "
                f"限制: {rate_limit}"
            )
            
            raise HTTPException(
                status_code=429,
                detail={
                    "error": {
                        "code": "RATE_LIMIT_EXCEEDED",
                        "message": f"请求过于频繁，请稍后重试",
                        "rate_limit": rate_limit,
                        "current_count": current_count,
                        "reset_time": 60
                    }
                }
            )
        
        logger.debug(
            f"速率限制检查通过 - 用户: {user_id}, "
            f"端点: {endpoint}, "
            f"当前计数: {current_count}/{rate_limit}"
        )
