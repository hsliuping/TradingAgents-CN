"""
用户会话管理服务

提供会话的创建、验证、撤销等功能，解决 JWT Token 无法撤销的问题
"""

import logging
import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional
from pymongo.database import Database
from app.models.user import UserSession

logger = logging.getLogger(__name__)


class SessionService:
    """用户会话管理服务"""
    
    def __init__(self, db: Database):
        self.db = db
        self.sessions_collection = db.user_sessions
        
        # 创建索引
        self._create_indexes()
    
    def _create_indexes(self):
        """创建索引"""
        try:
            # session_id 唯一索引
            self.sessions_collection.create_index("session_id", unique=True)
            
            # user_id 索引（用于查询用户的所有会话）
            self.sessions_collection.create_index("user_id")
            
            # expires_at 索引（用于自动清理过期会话）
            self.sessions_collection.create_index("expires_at", expireAfterSeconds=0)
            
            logger.debug("✅ Session 索引创建成功")
        except Exception as e:
            logger.warning(f"⚠️ Session 索引创建失败: {e}")
    
    def create_session(
        self,
        user_id: str,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        expires_in_seconds: int = 3600  # 默认 1 小时
    ) -> str:
        """
        创建新会话
        
        Args:
            user_id: 用户ID
            ip_address: IP地址
            user_agent: User-Agent
            expires_in_seconds: 过期时间（秒）
            
        Returns:
            session_id: 会话ID
        """
        try:
            # 生成唯一的 session_id
            session_id = secrets.token_urlsafe(32)

            # 🔥 使用 UTC 时间（naive datetime）存储到 MongoDB
            # 这样可以避免时区比较问题
            now_utc = datetime.now(timezone.utc).replace(tzinfo=None)
            expires_at_utc = now_utc + timedelta(seconds=expires_in_seconds)

            session_doc = {
                "session_id": session_id,
                "user_id": user_id,
                "created_at": now_utc,
                "expires_at": expires_at_utc,
                "last_activity": now_utc,
                "ip_address": ip_address,
                "user_agent": user_agent
            }

            self.sessions_collection.insert_one(session_doc)
            
            logger.info(f"✅ 创建会话: user_id={user_id}, session_id={session_id[:16]}..., expires_at={expires_at_utc} UTC")
            return session_id
            
        except Exception as e:
            logger.error(f"❌ 创建会话失败: {e}")
            raise
    
    def verify_session(self, session_id: str, update_activity: bool = True) -> Optional[UserSession]:
        """
        验证会话是否有效
        
        Args:
            session_id: 会话ID
            update_activity: 是否更新最后活动时间
            
        Returns:
            UserSession: 会话信息，如果无效则返回 None
        """
        try:
            session_doc = self.sessions_collection.find_one({"session_id": session_id})

            if not session_doc:
                logger.debug(f"❌ 会话不存在: {session_id[:16]}...")
                return None

            # 检查是否过期（使用 UTC 时间）
            now_utc = datetime.now(timezone.utc).replace(tzinfo=None)
            expires_at = session_doc["expires_at"]

            if expires_at < now_utc:
                logger.debug(f"⏰ 会话已过期: {session_id[:16]}...")
                # 删除过期会话
                self.sessions_collection.delete_one({"session_id": session_id})
                return None

            # 更新最后活动时间
            if update_activity:
                self.sessions_collection.update_one(
                    {"session_id": session_id},
                    {"$set": {"last_activity": now_utc}}
                )
            
            logger.debug(f"✅ 会话有效: user_id={session_doc['user_id']}, session_id={session_id[:16]}...")
            return UserSession(**session_doc)
            
        except Exception as e:
            logger.error(f"❌ 验证会话失败: {e}")
            return None
    
    def revoke_session(self, session_id: str) -> bool:
        """
        撤销会话（退出登录）

        Args:
            session_id: 会话ID

        Returns:
            bool: 是否成功
        """
        try:
            result = self.sessions_collection.delete_one({"session_id": session_id})

            if result.deleted_count > 0:
                logger.info(f"✅ 撤销会话: {session_id[:16]}...")
                return True
            else:
                logger.warning(f"⚠️ 会话不存在: {session_id[:16]}...")
                return False

        except Exception as e:
            logger.error(f"❌ 撤销会话失败: {e}")
            return False

    def revoke_all_user_sessions(self, user_id: str) -> int:
        """
        撤销用户的所有会话（修改密码、强制登出等场景）

        Args:
            user_id: 用户ID

        Returns:
            int: 撤销的会话数量
        """
        try:
            result = self.sessions_collection.delete_many({"user_id": user_id})
            count = result.deleted_count

            logger.info(f"✅ 撤销用户所有会话: user_id={user_id}, count={count}")
            return count

        except Exception as e:
            logger.error(f"❌ 撤销用户所有会话失败: {e}")
            return 0

    def get_user_sessions(self, user_id: str) -> list[UserSession]:
        """
        获取用户的所有活跃会话

        Args:
            user_id: 用户ID

        Returns:
            list[UserSession]: 会话列表
        """
        try:
            # 🔥 使用 UTC 时间查询（与存储时保持一致）
            now_utc = datetime.now(timezone.utc).replace(tzinfo=None)

            sessions = self.sessions_collection.find({
                "user_id": user_id,
                "expires_at": {"$gt": now_utc}
            }).sort("last_activity", -1)

            return [UserSession(**s) for s in sessions]

        except Exception as e:
            logger.error(f"❌ 获取用户会话失败: {e}")
            return []

    def cleanup_expired_sessions(self) -> int:
        """
        清理过期会话（定时任务）

        Returns:
            int: 清理的会话数量
        """
        try:
            # 🔥 使用 UTC 时间查询
            now_utc = datetime.now(timezone.utc).replace(tzinfo=None)

            result = self.sessions_collection.delete_many({"expires_at": {"$lt": now_utc}})
            count = result.deleted_count

            if count > 0:
                logger.info(f"🧹 清理过期会话: count={count}")

            return count

        except Exception as e:
            logger.error(f"❌ 清理过期会话失败: {e}")
            return 0


# 全局 SessionService 实例
_session_service: Optional[SessionService] = None


def get_session_service(db: Optional[Database] = None) -> SessionService:
    """
    获取 SessionService 单例

    注意：SessionService 使用同步的 MongoDB 操作，
    因此需要使用 get_mongo_db_sync() 而不是 get_mongo_db()
    """
    global _session_service

    if _session_service is None:
        if db is None:
            from app.core.database import get_mongo_db_sync
            db = get_mongo_db_sync()  # 🔥 使用同步的数据库连接

        _session_service = SessionService(db)

    return _session_service

