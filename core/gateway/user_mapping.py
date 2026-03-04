"""
Gateway 用户身份映射

IM 平台用户（open_id / QQ 号 / 钉钉 userId）→ 系统 user_id 映射。

绑定流程：
1. 用户在 IM 中发送 /bind
2. 系统生成一次性验证码，存入 pending_bindings
3. 用户在 Web UI 输入验证码，完成绑定
4. 绑定记录写入 user_identity_mappings 集合

集合结构 (user_identity_mappings):
{
    "user_id": "60f1a2b3c4d5e6f7a8b9c0d1",
    "platform": "feishu",
    "platform_identity": "ou_xxxxxxxxx",
    "display_name": "张三",
    "bound_at": ISODate("2026-03-04T08:00:00Z"),
    "is_active": true
}

集合结构 (gateway_pending_bindings):
{
    "code": "A3X9K2",
    "platform": "feishu",
    "platform_identity": "ou_xxxxxxxxx",
    "channel_id": "oc_xxx",
    "display_name": "张三",
    "created_at": ISODate("2026-03-04T08:00:00Z"),
    "expires_at": ISODate("2026-03-04T08:10:00Z")   // TTL 10 分钟
}
"""

import logging
import secrets
import string
from datetime import datetime, timedelta, timezone
from typing import Optional

logger = logging.getLogger(__name__)

MAPPINGS_COLLECTION = "user_identity_mappings"
PENDING_COLLECTION = "gateway_pending_bindings"
BIND_CODE_LENGTH = 6
BIND_CODE_TTL_MINUTES = 10


class UserMappingManager:
    """用户身份映射管理器"""

    def __init__(self, db):
        self.db = db
        self.mappings = db[MAPPINGS_COLLECTION]
        self.pending = db[PENDING_COLLECTION]

    async def ensure_indexes(self) -> None:
        """创建索引（应用启动时调用一次）"""
        # 复合唯一索引：一个平台用户只能绑定一个系统用户
        await self.mappings.create_index(
            [("platform", 1), ("platform_identity", 1)],
            unique=True,
        )
        await self.mappings.create_index("user_id")

        # pending 的 TTL 索引
        await self.pending.create_index(
            "expires_at", expireAfterSeconds=0
        )
        await self.pending.create_index("code", unique=True)
        logger.info("[UserMapping] 索引创建完成")

    # ------------------------------------------------------------------ #
    # 查询
    # ------------------------------------------------------------------ #

    async def get_system_user_id(
        self, platform: str, platform_identity: str
    ) -> Optional[str]:
        """查询 IM 用户对应的系统 user_id"""
        doc = await self.mappings.find_one({
            "platform": platform,
            "platform_identity": platform_identity,
            "is_active": True,
        })
        return doc["user_id"] if doc else None

    async def get_platform_identities(self, user_id: str) -> list:
        """查询系统用户绑定的所有平台身份"""
        cursor = self.mappings.find(
            {"user_id": user_id, "is_active": True},
            {"platform": 1, "platform_identity": 1, "display_name": 1},
        )
        return await cursor.to_list(length=50)

    # ------------------------------------------------------------------ #
    # 绑定流程
    # ------------------------------------------------------------------ #

    async def create_bind_code(
        self,
        platform: str,
        platform_identity: str,
        channel_id: str,
        display_name: Optional[str] = None,
    ) -> str:
        """生成一次性绑定验证码"""
        code = self._generate_code()
        now = datetime.now(timezone.utc)
        expires = now + timedelta(minutes=BIND_CODE_TTL_MINUTES)

        # 如果已有 pending，替换
        await self.pending.delete_many({
            "platform": platform,
            "platform_identity": platform_identity,
        })

        await self.pending.insert_one({
            "code": code,
            "platform": platform,
            "platform_identity": platform_identity,
            "channel_id": channel_id,
            "display_name": display_name,
            "created_at": now,
            "expires_at": expires,
        })
        logger.info(
            "[UserMapping] 生成绑定码: platform=%s, identity=%s, code=%s",
            platform, platform_identity, code,
        )
        return code

    async def confirm_bind(self, code: str, user_id: str) -> Optional[dict]:
        """
        Web 端确认绑定：用 code 找到 pending 记录，创建正式映射。

        Returns:
            绑定信息 dict，或 None（code 不存在/已过期）
        """
        pending = await self.pending.find_one_and_delete({"code": code})
        if not pending:
            return None

        now = datetime.now(timezone.utc)
        mapping = {
            "user_id": user_id,
            "platform": pending["platform"],
            "platform_identity": pending["platform_identity"],
            "display_name": pending.get("display_name"),
            "bound_at": now,
            "is_active": True,
        }

        # upsert：同一平台+identity 只保留一条
        await self.mappings.update_one(
            {
                "platform": pending["platform"],
                "platform_identity": pending["platform_identity"],
            },
            {"$set": mapping},
            upsert=True,
        )
        logger.info(
            "[UserMapping] 绑定成功: user_id=%s, platform=%s, identity=%s",
            user_id, pending["platform"], pending["platform_identity"],
        )
        return mapping


    async def unbind(
        self, user_id: str, platform: str, platform_identity: str
    ) -> bool:
        """解绑平台身份"""
        result = await self.mappings.update_one(
            {
                "user_id": user_id,
                "platform": platform,
                "platform_identity": platform_identity,
            },
            {"$set": {"is_active": False}},
        )
        return result.modified_count > 0

    # ------------------------------------------------------------------ #
    # 工具方法
    # ------------------------------------------------------------------ #

    @staticmethod
    def _generate_code() -> str:
        """生成 6 位大写字母+数字验证码"""
        alphabet = string.ascii_uppercase + string.digits
        return "".join(secrets.choice(alphabet) for _ in range(BIND_CODE_LENGTH))