"""
授权验证服务

[PRO功能] 调用外部认证服务 API 验证 App Token，获取用户权限信息
"""

import logging
import httpx
import hashlib
import platform
import uuid
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

    # 离线缓存有效期：7天
    OFFLINE_CACHE_TTL = 7 * 24 * 3600  # 7天（秒）

    def __init__(self):
        self.base_url = self.BASE_URL  # 使用硬编码的地址
        self.timeout = settings.LICENSE_SERVICE_TIMEOUT
        self.cache_ttl = settings.LICENSE_CACHE_TTL  # 在线缓存：1小时
        self._cache: dict[str, LicenseInfo] = {}  # 内存缓存（在线模式）
        self._machine_id = self._get_machine_id()  # 机器ID

    def _get_machine_id(self) -> str:
        """
        获取机器唯一标识（绑定硬件信息）

        使用多个硬件信息组合生成唯一ID，防止用户复制缓存到其他机器
        """
        try:
            # 获取多个硬件信息
            node = uuid.getnode()  # MAC地址
            machine = platform.machine()  # CPU架构
            system = platform.system()  # 操作系统
            processor = platform.processor()  # 处理器信息

            # 组合生成唯一ID
            machine_info = f"{node}-{machine}-{system}-{processor}"
            machine_id = hashlib.sha256(machine_info.encode()).hexdigest()

            logger.debug(f"🔑 机器ID: {machine_id[:16]}...")
            return machine_id
        except Exception as e:
            logger.warning(f"⚠️ 获取机器ID失败: {e}，使用随机ID")
            return hashlib.sha256(str(uuid.uuid4()).encode()).hexdigest()
    
    async def _load_persistent_cache(self, token: str) -> Optional[LicenseInfo]:
        """
        从数据库加载持久化缓存（7天有效期）

        Args:
            token: 应用令牌

        Returns:
            LicenseInfo: 缓存的授权信息（如果有效）
        """
        try:
            db = get_mongo_db()
            cache_doc = await db.license_cache.find_one({
                "token_hash": hashlib.sha256(token.encode()).hexdigest(),
                "machine_id": self._machine_id
            })

            if not cache_doc:
                return None

            # 检查缓存是否过期（7天）
            cache_expires_at = cache_doc.get("cache_expires_at")
            if not cache_expires_at or datetime.now() > cache_expires_at:
                logger.debug("📦 持久化缓存已过期")
                return None

            # 返回缓存的授权信息
            logger.info(f"✅ 使用持久化缓存: {cache_doc.get('email')}, 剩余 {(cache_expires_at - datetime.now()).days} 天")
            return LicenseInfo(
                email=cache_doc.get("email", ""),
                plan=cache_doc.get("plan", "free"),
                features=cache_doc.get("features", []),
                device_registered=cache_doc.get("device_registered", False),
                is_valid=True,
                verified_at=cache_doc.get("verified_at"),
                trial_end_at=cache_doc.get("trial_end_at"),
                pro_expire_at=cache_doc.get("pro_expire_at"),
                cached=True,
                cache_expires_at=cache_expires_at,
                offline_mode=False
            )
        except Exception as e:
            logger.error(f"❌ 加载持久化缓存失败: {e}")
            return None

    async def _save_persistent_cache(self, token: str, license_info: LicenseInfo):
        """
        保存授权信息到数据库（7天有效期）

        Args:
            token: 应用令牌
            license_info: 授权信息
        """
        try:
            db = get_mongo_db()
            cache_expires_at = datetime.now() + timedelta(seconds=self.OFFLINE_CACHE_TTL)

            await db.license_cache.update_one(
                {
                    "token_hash": hashlib.sha256(token.encode()).hexdigest(),
                    "machine_id": self._machine_id
                },
                {
                    "$set": {
                        "email": license_info.email,
                        "plan": license_info.plan,
                        "features": license_info.features,
                        "device_registered": license_info.device_registered,
                        "verified_at": license_info.verified_at,
                        "trial_end_at": license_info.trial_end_at,
                        "pro_expire_at": license_info.pro_expire_at,
                        "cache_expires_at": cache_expires_at,
                        "updated_at": datetime.now()
                    }
                },
                upsert=True
            )
            logger.info(f"💾 保存持久化缓存成功，有效期至: {cache_expires_at}")
        except Exception as e:
            logger.error(f"❌ 保存持久化缓存失败: {e}")

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
        # 1. 检查内存缓存（在线模式，1小时有效）
        if use_cache and token in self._cache:
            cached_info = self._cache[token]
            if cached_info.cache_expires_at and datetime.now() < cached_info.cache_expires_at:
                logger.debug(f"🔑 使用内存缓存的授权信息: {cached_info.email}")
                return cached_info

        # 2. 检查持久化缓存（离线模式，7天有效）
        if use_cache:
            persistent_cache = await self._load_persistent_cache(token)
            if persistent_cache:
                # 同时更新内存缓存
                self._cache[token] = persistent_cache
                return persistent_cache
        
        # 3. 在线验证
        try:
            # 🔥 增加超时时间和 SSL 验证配置
            # 某些企业网络环境可能需要禁用 SSL 验证或增加超时时间
            timeout_config = httpx.Timeout(
                connect=10.0,  # 连接超时：10秒
                read=30.0,     # 读取超时：30秒
                write=10.0,    # 写入超时：10秒
                pool=10.0      # 连接池超时：10秒
            )
            
            logger.debug(f"🔗 连接授权服务: {self.base_url}/app/verify-token")
            logger.debug(f"   超时配置: connect=10s, read=30s")
            
            async with httpx.AsyncClient(
                timeout=timeout_config,
                verify=True,  # SSL 验证（某些企业网络可能需要设为 False）
                follow_redirects=True  # 跟随重定向
            ) as client:
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

                    # 保存到内存缓存（1小时）
                    self._cache[token] = license_info

                    # 保存到持久化缓存（7天）
                    await self._save_persistent_cache(token, license_info)

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
                    
        except httpx.TimeoutException as e:
            logger.error(f"❌ 授权服务请求超时 (超时时间: {self.timeout}秒)")
            logger.debug(f"   详细错误: {type(e).__name__}: {e}")
            # 尝试使用持久化缓存（离线模式）
            return await self._get_offline_fallback(token, f"授权服务请求超时（{self.timeout}秒）")
        except httpx.ConnectError as e:
            error_detail = str(e)
            logger.error(f"❌ 无法连接到授权服务: {self.base_url}")
            logger.error(f"   错误详情: {error_detail}")
            logger.info(f"   可能的原因:")
            logger.info(f"   1. 网络连接问题（防火墙、代理、VPN）")
            logger.info(f"   2. API 端点不存在或路径错误: {self.base_url}/app/verify-token")
            logger.info(f"   3. SSL/TLS 证书验证失败")
            logger.info(f"   4. 服务器暂时不可用")
            logger.info(f"   系统将使用离线缓存模式（如果可用）")
            # 尝试使用持久化缓存（离线模式）
            return await self._get_offline_fallback(token, f"无法连接到授权服务: {error_detail}")
        except httpx.HTTPStatusError as e:
            logger.error(f"❌ 授权服务返回 HTTP 错误: {e.response.status_code}")
            logger.error(f"   响应内容: {e.response.text[:200]}")
            # 尝试使用持久化缓存（离线模式）
            return await self._get_offline_fallback(token, f"授权服务返回 HTTP {e.response.status_code}")
        except Exception as e:
            error_type = type(e).__name__
            error_msg = str(e)
            logger.error(f"❌ 验证 Token 时发生错误: {error_type}: {error_msg}")
            logger.debug(f"   完整异常信息:", exc_info=True)
            # 尝试使用持久化缓存（离线模式）
            return await self._get_offline_fallback(token, f"{error_type}: {error_msg}")
    
    async def _get_offline_fallback(self, token: str, error_message: str) -> LicenseInfo:
        """
        离线降级处理：使用持久化缓存（7天有效期）

        Args:
            token: 应用令牌
            error_message: 错误信息

        Returns:
            LicenseInfo: 离线模式的授权信息（如果有持久化缓存）或免费版
        """
        # 1. 检查内存缓存
        if token in self._cache:
            cached_info = self._cache[token]
            logger.warning(f"⚠️ 使用离线模式（内存缓存）: {cached_info.email}, plan={cached_info.plan}")
            return LicenseInfo(
                email=cached_info.email,
                plan=cached_info.plan,
                features=cached_info.features,
                device_registered=cached_info.device_registered,
                is_valid=True,
                verified_at=cached_info.verified_at,
                trial_end_at=cached_info.trial_end_at,
                pro_expire_at=cached_info.pro_expire_at,
                cached=True,
                cache_expires_at=cached_info.cache_expires_at,
                offline_mode=True,
                error_message=f"离线模式: {error_message}"
            )

        # 2. 检查持久化缓存（7天有效期）
        persistent_cache = await self._load_persistent_cache(token)
        if persistent_cache:
            logger.warning(f"⚠️ 使用离线模式（持久化缓存）: {persistent_cache.email}, plan={persistent_cache.plan}")
            # 标记为离线模式
            persistent_cache.offline_mode = True
            persistent_cache.error_message = f"离线模式: {error_message}"
            # 更新内存缓存
            self._cache[token] = persistent_cache
            return persistent_cache

        # 3. 没有任何缓存，返回免费版
        logger.warning(f"⚠️ 无可用缓存，降级为免费版")
        return LicenseInfo(
            email="",
            plan="free",
            is_valid=False,
            error_message=f"网络错误且无缓存: {error_message}",
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

