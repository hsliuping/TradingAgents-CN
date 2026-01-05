"""
授权验证服务

[PRO功能] 调用外部认证服务 API 验证 App Token，获取用户权限信息
"""

import logging
import httpx
from typing import Optional
from datetime import datetime, timedelta
from pydantic import BaseModel, Field
from functools import lru_cache

from app.core.config import settings
from app.core.database import get_mongo_db

logger = logging.getLogger("app.services.license")


class LicenseInfo(BaseModel):
    """授权信息"""
    email: str
    plan: str  # "free" | "trial" | "pro" | "enterprise"
    features: list[str] = Field(default_factory=list)
    device_registered: bool = False
    is_valid: bool = True
    error_message: Optional[str] = None
    verified_at: Optional[datetime] = None
    # 到期时间
    trial_end_at: Optional[str] = None  # 试用到期时间
    pro_expire_at: Optional[str] = None  # PRO到期时间
    # 缓存相关
    cached: bool = False
    cache_expires_at: Optional[datetime] = None
    # 离线模式
    offline_mode: bool = False  # 是否处于离线模式（使用过期缓存）


class LicenseService:
    """授权验证服务"""

    # 🔐 验证服务器地址（硬编码，防止用户修改）
    # ⚠️ 安全警告：不要从环境变量读取，否则用户可以搭建假服务器绕过验证
    BASE_URL = "https://www.tradingagentscn.com/api"

    def __init__(self):
        self.base_url = self.BASE_URL  # 使用硬编码的地址
        self.timeout = settings.LICENSE_SERVICE_TIMEOUT
        self.cache_ttl = settings.LICENSE_CACHE_TTL
        self._cache: dict[str, LicenseInfo] = {}
    
    async def verify_app_token(
        self,
        token: str,
        device_id: Optional[str] = None,
        app_version: Optional[str] = None,
        use_cache: bool = True
    ) -> LicenseInfo:
        """
        验证 App Token
        
        Args:
            token: 应用令牌
            device_id: 设备ID（可选）
            app_version: 应用版本（可选）
            use_cache: 是否使用缓存
            
        Returns:
            LicenseInfo: 授权信息
        """
        # 检查缓存
        if use_cache and token in self._cache:
            cached_info = self._cache[token]
            if cached_info.cache_expires_at and datetime.now() < cached_info.cache_expires_at:
                logger.debug(f"🔑 使用缓存的授权信息: {cached_info.email}")
                return cached_info
        
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    f"{self.base_url}/app/verify-token",
                    json={
                        "token": token,
                        "device_id": device_id,
                        "app_version": app_version
                    }
                )
                
                if response.status_code == 200:
                    data = response.json()
                    license_info = LicenseInfo(
                        email=data.get("email", ""),
                        plan=data.get("plan", "free"),
                        features=data.get("features", []),
                        device_registered=data.get("device_registered", False),
                        is_valid=True,
                        verified_at=datetime.now(),
                        trial_end_at=data.get("trial_end_at"),
                        pro_expire_at=data.get("pro_expire_at"),
                        cached=False,
                        cache_expires_at=datetime.now() + timedelta(seconds=self.cache_ttl)
                    )

                    # 缓存结果
                    self._cache[token] = license_info
                    logger.info(f"✅ Token 验证成功: {license_info.email}, plan={license_info.plan}")
                    return license_info
                    
                elif response.status_code == 401:
                    logger.warning("❌ Token 无效或已过期")
                    return LicenseInfo(
                        email="",
                        plan="free",
                        is_valid=False,
                        error_message="Token 无效或已过期"
                    )
                else:
                    error_msg = f"授权服务返回错误: {response.status_code}"
                    logger.error(f"❌ {error_msg}")
                    return LicenseInfo(
                        email="",
                        plan="free",
                        is_valid=False,
                        error_message=error_msg
                    )
                    
        except httpx.TimeoutException:
            logger.error("❌ 授权服务请求超时")
            # 尝试使用过期缓存（离线模式）
            return self._get_offline_fallback(token, "授权服务请求超时")
        except httpx.ConnectError:
            logger.error(f"❌ 无法连接到授权服务: {self.base_url}")
            # 尝试使用过期缓存（离线模式）
            return self._get_offline_fallback(token, "无法连接到授权服务")
        except Exception as e:
            logger.error(f"❌ 验证 Token 时发生错误: {e}")
            # 尝试使用过期缓存（离线模式）
            return self._get_offline_fallback(token, str(e))
    
    def _get_offline_fallback(self, token: str, error_message: str) -> LicenseInfo:
        """
        离线降级处理：尝试使用过期缓存

        Args:
            token: 应用令牌
            error_message: 错误信息

        Returns:
            LicenseInfo: 离线模式的授权信息（如果有过期缓存）或免费版
        """
        # 检查是否有过期缓存
        if token in self._cache:
            cached_info = self._cache[token]
            logger.warning(f"⚠️ 使用离线模式，过期缓存: {cached_info.email}, plan={cached_info.plan}")
            # 返回离线模式的缓存信息
            return LicenseInfo(
                email=cached_info.email,
                plan=cached_info.plan,
                features=cached_info.features,
                device_registered=cached_info.device_registered,
                is_valid=True,  # 离线模式下仍然有效
                verified_at=cached_info.verified_at,
                trial_end_at=cached_info.trial_end_at,
                pro_expire_at=cached_info.pro_expire_at,
                cached=True,
                cache_expires_at=cached_info.cache_expires_at,
                offline_mode=True,  # 标记为离线模式
                error_message=f"离线模式: {error_message}"
            )

        # 没有缓存，返回免费版
        logger.warning(f"⚠️ 无可用缓存，降级为免费版")
        return LicenseInfo(
            email="",
            plan="free",
            is_valid=False,
            error_message=f"网络错误: {error_message}",
            offline_mode=True
        )

    def is_pro(self, license_info: LicenseInfo) -> bool:
        """检查是否为 PRO 用户（包括试用版）"""
        return license_info.is_valid and license_info.plan in ("trial", "pro", "enterprise")

    def has_feature(self, license_info: LicenseInfo, feature: str) -> bool:
        """检查是否拥有特定功能"""
        if not license_info.is_valid:
            return False
        # trial、pro、enterprise 拥有所有 PRO 功能
        if license_info.plan in ("trial", "pro", "enterprise"):
            return True
        return False
    
    def clear_cache(self, token: Optional[str] = None):
        """清除缓存"""
        if token:
            self._cache.pop(token, None)
        else:
            self._cache.clear()


# 单例服务
_license_service: Optional[LicenseService] = None


def get_license_service() -> LicenseService:
    """获取授权服务实例"""
    global _license_service
    if _license_service is None:
        _license_service = LicenseService()
    return _license_service

