"""
Gateway 多通道 Session 管理

Session Key 格式: {user_id}:{channel_type}:{channel_id}

- 同一用户从 Web 和飞书的会话完全独立
- Session 存储在 MongoDB `gateway_sessions` 集合
- 对话历史自动裁剪（保留最近 N 轮）
- TTL 索引自动清理过期 Session
"""

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# 默认保留最近 20 轮对话
DEFAULT_MAX_HISTORY = 20
# Session 过期时间（秒）— 7 天
SESSION_TTL_SECONDS = 7 * 24 * 3600

COLLECTION_NAME = "gateway_sessions"


def build_session_key(user_id: str, channel_type: str, channel_id: str) -> str:
    """构造 Gateway Session Key。"""
    return f"{user_id}:{channel_type}:{channel_id}"


class SessionManager:
    """
    Gateway Session 管理器

    每个 Session 包含:
    - session_key: "{user_id}:{channel_type}:{channel_id}"
    - user_id: 系统用户 ID
    - channel_type: 平台类型
    - channel_id: 平台会话 ID
    - messages: 对话历史列表
    - context: 上下文状态（如上一个 task_id 等）
    - created_at / updated_at
    """

    def __init__(self, db, max_history: int = DEFAULT_MAX_HISTORY):
        self.db = db
        self.collection = db[COLLECTION_NAME]
        self.max_history = max_history

    async def ensure_indexes(self) -> None:
        """创建索引（应用启动时调用一次）"""
        # 唯一索引：按 session_key 快速查找
        await self.collection.create_index("session_key", unique=True)
        # TTL 索引：自动清理过期 Session
        await self.collection.create_index(
            "updated_at", expireAfterSeconds=SESSION_TTL_SECONDS
        )
        logger.info("[SessionManager] 索引创建完成")

    async def get_or_create(
        self,
        user_id: str,
        channel_type: str,
        channel_id: str,
    ) -> Dict[str, Any]:
        """获取或创建 Session"""
        session_key = build_session_key(user_id, channel_type, channel_id)
        now = datetime.now(timezone.utc)

        session = await self.collection.find_one({"session_key": session_key})
        if session:
            # 更新最后活跃时间
            await self.collection.update_one(
                {"session_key": session_key},
                {"$set": {"updated_at": now}},
            )
            return session

        # 创建新 Session
        new_session = {
            "session_key": session_key,
            "user_id": user_id,
            "channel_type": channel_type,
            "channel_id": channel_id,
            "messages": [],
            "context": {},
            "created_at": now,
            "updated_at": now,
        }
        await self.collection.insert_one(new_session)
        logger.info("[SessionManager] 新建 Session: %s", session_key)
        return new_session

    async def get_current_topic_id(self, session_key: str) -> Optional[str]:
        """获取当前 Session 绑定的研究主题 ID。"""
        session = await self.collection.find_one(
            {"session_key": session_key},
            {"context.current_topic_id": 1},
        )
        if not session:
            return None
        context = session.get("context") or {}
        current_topic_id = (context.get("current_topic_id") or "").strip()
        return current_topic_id or None

    async def set_current_topic_id(self, session_key: str, topic_id: Optional[str]) -> None:
        """设置当前 Session 绑定的研究主题 ID。"""
        await self.update_context(session_key, {"current_topic_id": topic_id or None})

    async def append_message(
        self,
        session_key: str,
        role: str,
        content: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """追加一条消息到 Session 对话历史"""
        now = datetime.now(timezone.utc)
        msg = {
            "role": role,
            "content": content,
            "timestamp": now,
        }
        if metadata:
            msg["metadata"] = metadata

        await self.collection.update_one(
            {"session_key": session_key},
            {
                "$push": {
                    "messages": {
                        "$each": [msg],
                        "$slice": -self.max_history,  # 保留最近 N 条
                    }
                },
                "$set": {"updated_at": now},
            },
        )

    async def get_history(
        self, session_key: str
    ) -> List[Dict[str, Any]]:
        """获取 Session 的对话历史"""
        session = await self.collection.find_one(
            {"session_key": session_key},
            {"messages": 1},
        )
        return session.get("messages", []) if session else []

    async def update_context(
        self, session_key: str, context_updates: Dict[str, Any]
    ) -> None:
        """更新 Session 上下文（如最近的 task_id）"""
        now = datetime.now(timezone.utc)
        set_fields = {f"context.{k}": v for k, v in context_updates.items()}
        set_fields["updated_at"] = now
        await self.collection.update_one(
            {"session_key": session_key},
            {"$set": set_fields},
        )

    async def clear_session(self, session_key: str) -> bool:
        """清空 Session 对话历史和上下文"""
        result = await self.collection.update_one(
            {"session_key": session_key},
            {"$set": {
                "messages": [],
                "context": {},
                "updated_at": datetime.now(timezone.utc),
            }},
        )
        return result.modified_count > 0

    async def delete_session(self, session_key: str) -> bool:
        """删除 Session"""
        result = await self.collection.delete_one({"session_key": session_key})
        return result.deleted_count > 0

