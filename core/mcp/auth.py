"""
MCP Server 认证模块

实现 API Key → user_id 映射：
1. 客户端在 MCP 连接时携带 Bearer Token（即 API Key）
2. TokenVerifier 从 system_configs 集合查找匹配的 mcp_api_keys
3. 验证通过后，将 mapped_user_id 写入 AccessToken.client_id
4. MCP 工具通过 Context.client_id 获取当前用户 ID

数据库结构（system_configs 集合）:
{
    "config_key": "mcp_auth",
    "category": "mcp",
    "api_keys": [
        {
            "key": "sk-mcp-xxxx",
            "user_id": "60f1a2b3c4d5e6f7a8b9c0d1",
            "name": "我的 Claude Desktop",
            "daily_quota": 50,
            "enabled": true
        }
    ]
}
"""

import logging
from datetime import datetime, timezone
from typing import Optional

from mcp.server.auth.provider import AccessToken, TokenVerifier

logger = logging.getLogger(__name__)


class MCPApiKeyVerifier:
    """基于 API Key 的 MCP 认证器

    从 MongoDB system_configs 集合验证 API Key，
    并将关联的 user_id 映射到 AccessToken.client_id。
    """

    def __init__(self, required_scopes: list[str] | None = None):
        self.required_scopes = required_scopes or ["mcp:tools"]
        self._config_cache: Optional[dict] = None
        self._cache_time: Optional[datetime] = None
        self._cache_ttl_seconds = 300  # 5 分钟缓存

    async def verify_token(self, token: str) -> AccessToken | None:
        """验证 Bearer Token（API Key），返回 AccessToken 或 None

        Args:
            token: 客户端传入的 Bearer Token

        Returns:
            AccessToken（client_id 为映射的 user_id）或 None（验证失败）
        """
        if not token:
            logger.warning("🔒 MCP 认证失败: 空 token")
            return None

        key_entry = await self._find_api_key(token)
        if not key_entry:
            logger.warning("🔒 MCP 认证失败: 无效的 API Key")
            return None

        if not key_entry.get("enabled", True):
            logger.warning(f"🔒 MCP 认证失败: API Key 已禁用 ({key_entry.get('name', 'unknown')})")
            return None

        # 检查每日配额
        user_id = key_entry["user_id"]
        daily_quota = key_entry.get("daily_quota", 0)
        if daily_quota > 0:
            within_quota = await self._check_daily_quota(user_id, daily_quota)
            if not within_quota:
                logger.warning(f"🔒 MCP 配额超限: user={user_id}, quota={daily_quota}")
                return None

        logger.info(f"✅ MCP 认证成功: user={user_id}, name={key_entry.get('name', 'N/A')}")

        # 将 user_id 放入 client_id，工具通过 ctx.client_id 获取
        return AccessToken(
            token=token,
            client_id=user_id,
            scopes=self.required_scopes,
        )

    async def _find_api_key(self, token: str) -> Optional[dict]:
        """从数据库查找匹配的 API Key 配置"""
        config = await self._get_mcp_config()
        if not config:
            return None

        api_keys = config.get("api_keys", [])
        for entry in api_keys:
            if entry.get("key") == token:
                return entry
        return None

    async def _get_mcp_config(self) -> Optional[dict]:
        """获取 MCP 认证配置（带缓存）"""
        now = datetime.now(timezone.utc)

        # 检查缓存
        if (
            self._config_cache is not None
            and self._cache_time is not None
            and (now - self._cache_time).total_seconds() < self._cache_ttl_seconds
        ):
            return self._config_cache

        try:
            from app.core.database import get_mongo_db
            db = get_mongo_db()
            config = await db.system_configs.find_one(
                {"config_key": "mcp_auth", "category": "mcp"}
            )
            self._config_cache = config
            self._cache_time = now
            return config
        except Exception as e:
            logger.error(f"❌ 读取 MCP 认证配置失败: {e}")
            return self._config_cache  # 降级使用旧缓存

    async def _check_daily_quota(self, user_id: str, daily_quota: int) -> bool:
        """检查用户今日 MCP 分析次数是否在配额内"""
        try:
            from bson import ObjectId
            from app.core.database import get_mongo_db
            db = get_mongo_db()

            today_start = datetime.now(timezone.utc).replace(
                hour=0, minute=0, second=0, microsecond=0
            )
            # user_id 在数据库中存储为 ObjectId，需要转换
            # 通过 task_params._mcp_source 标记来源（analyze_stock 创建时写入）
            count = await db.unified_analysis_tasks.count_documents({
                "user_id": ObjectId(user_id),
                "created_at": {"$gte": today_start},
                "task_params._mcp_source": True,
            })
            return count < daily_quota
        except Exception as e:
            logger.error(f"❌ 检查配额失败: {e}")
            return True  # 出错时放行，避免阻断服务


# ── 模块级便捷实例 ──
mcp_auth = MCPApiKeyVerifier()

