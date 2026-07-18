"""
登录失败速率限制器

针对登录端点的专用速率限制，基于失败次数锁定账户/IP。
与通用 API 速率限制（RateLimitMiddleware）不同，本模块关注的是认证失败次数，
而非总请求数 —— 一次成功登录不会重置失败计数，防止攻击者通过间隔成功登录规避限制。

防御策略（双向锁定）：
1. 基于 IP 的失败计数 - 防止单 IP 扫描多个账户（account enumeration）
2. 基于用户名的失败计数 - 防止分布式 IP 暴力破解单个账户（credential stuffing）

存储后端：
- 优先使用 Redis（支持多 worker/多实例共享锁定状态）
- Redis 不可用时降级为进程内内存存储（单实例部署仍可用）

设计参考：
- OWASP Authentication Cheat Sheet: Lockout Mechanism
- NIST SP 800-63B 5.2.2: Rate-limiting (Throttling)
"""

import asyncio
import logging
import time
from collections import defaultdict, deque
from typing import Optional, Tuple

logger = logging.getLogger(__name__)


class LoginRateLimiter:
    """
    登录失败速率限制器

    使用滑动窗口算法跟踪失败次数，超过阈值后锁定一段时间。

    Args:
        max_failures: 时间窗口内最大失败次数（默认 5）
        time_window: 失败计数窗口（秒，默认 300 = 5 分钟）
        lockout_duration: 超过阈值后的锁定时长（秒，默认 900 = 15 分钟）
    """

    def __init__(
        self,
        max_failures: int = 5,
        time_window: int = 300,
        lockout_duration: int = 900,
    ):
        self.max_failures = max_failures
        self.time_window = time_window
        self.lockout_duration = lockout_duration

        # 内存存储（Redis 不可用时降级使用）
        # key: "ip:1.2.3.4" or "user:admin"
        # value: deque[失败时间戳]
        self._failures: dict = defaultdict(deque)
        # key: same as above
        # value: 锁定到期时间戳
        self._lockouts: dict = {}
        self._lock = asyncio.Lock()
        self._redis_available = True  # 懒检测，失败后置 False

    # ------------------------------------------------------------------
    # 内部工具
    # ------------------------------------------------------------------

    def _keys(self, ip: str, username: str) -> Tuple[str, str]:
        """构造 IP 和用户名维度的存储键"""
        return (f"ip:{ip}", f"user:{username}")

    def _purge_expired(self, now: float):
        """清理过期的锁定和失败记录（仅内存模式调用）"""
        expired = [k for k, v in self._lockouts.items() if v <= now]
        for k in expired:
            del self._lockouts[k]
            self._failures.pop(k, None)

    async def _redis_check(self, ip_key: str, user_key: str) -> Optional[Tuple[str, int]]:
        """Redis 模式下的锁定检查。返回 (触发锁定的键, 剩余秒数) 或 None。"""
        try:
            from app.core.redis_client import get_redis_service

            svc = get_redis_service()
            # 同时查两个键的 TTL（如键存在且有过期时间，说明处于锁定状态）
            ip_ttl = await svc.redis.ttl(ip_key)
            user_ttl = await svc.redis.ttl(user_key)

            # ttl=-2 表示键不存在；ttl=-1 表示无过期；>=0 表示剩余秒数
            if ip_ttl and ip_ttl > 0:
                return (ip_key, ip_ttl)
            if user_ttl and user_ttl > 0:
                return (user_key, user_ttl)
            return None
        except Exception as exc:
            self._redis_available = False
            logger.debug(f"Redis 锁定检查失败，降级到内存模式: {exc}")
            return None

    async def _redis_record(self, ip_key: str, user_key: str) -> Optional[int]:
        """Redis 模式下记录失败。返回触发锁定的剩余秒数或 None。"""
        try:
            from app.core.redis_client import get_redis_service

            svc = get_redis_service()
            locked_for = None
            for key in (ip_key, user_key):
                # 使用 Redis 原子操作：INCR + EXPIRE
                # key 命名：login_lock:{ip|user}:{value}
                count = await svc.increment_with_ttl(key, ttl=self.time_window)
                if count >= self.max_failures:
                    # 触发锁定：将 key 的 TTL 延长到 lockout_duration
                    await svc.redis.expire(key, self.lockout_duration)
                    locked_for = self.lockout_duration
                    logger.warning(
                        f"🔒 登录锁定触发(Redis): {key}, "
                        f"失败次数={count}/{self.max_failures}, "
                        f"锁定{self.lockout_duration}秒"
                    )
            return locked_for
        except Exception as exc:
            self._redis_available = False
            logger.debug(f"Redis 失败记录失败，降级到内存模式: {exc}")
            return None

    async def _redis_clear(self, ip_key: str, user_key: str):
        """Redis 模式下清除失败计数（登录成功时调用）。"""
        try:
            from app.core.redis_client import get_redis_service

            svc = get_redis_service()
            await svc.redis.delete(ip_key, user_key)
        except Exception as exc:
            self._redis_available = False
            logger.debug(f"Redis 清除失败计数失败: {exc}")

    # ------------------------------------------------------------------
    # 公共接口
    # ------------------------------------------------------------------

    async def check_lockout(self, ip: str, username: str) -> Optional[Tuple[int, int]]:
        """
        检查是否被锁定。

        Args:
            ip: 客户端 IP 地址
            username: 登录用户名

        Returns:
            None: 未锁定，可以继续认证
            (retry_after_seconds, failure_count): 已锁定，应返回 429
        """
        ip_key, user_key = self._keys(ip, username)

        # 优先尝试 Redis
        if self._redis_available:
            result = await self._redis_check(
                f"login_lock:{ip_key}",
                f"login_lock:{user_key}",
            )
            if result is not None:
                locked_key, ttl = result
                logger.info(
                    f"🔒 登录被锁定: {locked_key}, 剩余 {ttl} 秒"
                )
                return (int(ttl), self.max_failures)
            # Redis 可用且无锁定，直接返回（不查内存）
            if self._redis_available:
                return None

        # 内存降级模式
        async with self._lock:
            now = time.time()
            self._purge_expired(now)

            for key in (ip_key, user_key):
                if key in self._lockouts:
                    retry_after = int(self._lockouts[key] - now) + 1
                    return (retry_after, self.max_failures)
            return None

    async def record_failure(self, ip: str, username: str) -> Optional[int]:
        """
        记录一次登录失败。

        Returns:
            None: 未触发锁定
            int: 已触发锁定，返回锁定时长（秒）
        """
        ip_key, user_key = self._keys(ip, username)

        # 优先尝试 Redis
        if self._redis_available:
            result = await self._redis_record(
                f"login_lock:{ip_key}",
                f"login_lock:{user_key}",
            )
            if result is not None:
                return result
            # Redis 成功记录但未触发锁定
            if self._redis_available:
                return None

        # 内存降级模式
        async with self._lock:
            now = time.time()
            self._purge_expired(now)

            locked_duration = None
            for key in (ip_key, user_key):
                failures = self._failures[key]
                # 清理窗口外记录
                while failures and failures[0] <= now - self.time_window:
                    failures.popleft()

                failures.append(now)

                if len(failures) >= self.max_failures:
                    self._lockouts[key] = now + self.lockout_duration
                    locked_duration = self.lockout_duration
                    logger.warning(
                        f"🔒 登录锁定触发(内存): {key}, "
                        f"失败次数={len(failures)}/{self.max_failures}, "
                        f"锁定{self.lockout_duration}秒"
                    )

            return locked_duration

    async def record_success(self, ip: str, username: str):
        """
        登录成功时清除失败计数。

        注意：不清除已触发的锁定状态 —— 如果某账户已被锁定，
        一次成功登录不应解除锁定，防止攻击者通过一次正确登录重置计数。
        正常用户登录成功时不会处于锁定状态，此调用是无副作用的。
        """
        ip_key, user_key = self._keys(ip, username)

        # 优先尝试 Redis
        if self._redis_available:
            await self._redis_clear(
                f"login_lock:{ip_key}",
                f"login_lock:{user_key}",
            )
            if self._redis_available:
                return

        # 内存降级模式
        async with self._lock:
            # 仅清除失败计数，不清除锁定状态
            self._failures.pop(ip_key, None)
            self._failures.pop(user_key, None)


# 全局单例
_login_rate_limiter: Optional[LoginRateLimiter] = None


def get_login_rate_limiter() -> LoginRateLimiter:
    """获取登录速率限制器单例"""
    global _login_rate_limiter
    if _login_rate_limiter is None:
        _login_rate_limiter = LoginRateLimiter()
    return _login_rate_limiter
