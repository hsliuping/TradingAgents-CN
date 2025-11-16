"""
用户模板配置服务
"""

import logging
from typing import Optional, List
from bson import ObjectId
from pymongo import MongoClient
from app.core.config import settings
from app.models.user_template_config import (
    UserTemplateConfig,
    UserTemplateConfigCreate,
    UserTemplateConfigUpdate
)
from datetime import datetime

logger = logging.getLogger(__name__)


class UserTemplateConfigService:
    """用户模板配置服务"""

    def __init__(self):
        self.client = MongoClient(settings.MONGO_URI)
        self.db = self.client[settings.MONGO_DB]
        self.config_collection = self.db.user_template_configs
        self._create_indexes()

    def _create_indexes(self):
        """创建数据库索引"""
        try:
            self.config_collection.create_index([("user_id", 1)])
            self.config_collection.create_index([
                ("user_id", 1),
                ("agent_type", 1),
                ("agent_name", 1),
                ("preference_id", 1)
            ], unique=True)
            self.config_collection.create_index([("is_active", 1)])
            logger.info("✅ 用户模板配置索引创建完成")
        except Exception as e:
            logger.warning(f"⚠️ 创建索引失败: {e}")

    async def create_config(
        self,
        user_id: str,
        config_data: UserTemplateConfigCreate
    ) -> Optional[UserTemplateConfig]:
        """创建配置"""
        try:
            config_doc = {
                "user_id": ObjectId(user_id),
                "agent_type": config_data.agent_type,
                "agent_name": config_data.agent_name,
                "template_id": ObjectId(config_data.template_id),
                "preference_id": ObjectId(config_data.preference_id) if config_data.preference_id else None,
                "is_active": True,
                "created_at": datetime.utcnow(),
                "updated_at": datetime.utcnow()
            }

            result = self.config_collection.insert_one(config_doc)
            logger.info(f"✅ 配置创建成功: {result.inserted_id}")
            return await self.get_config(str(result.inserted_id))

        except Exception as e:
            logger.error(f"❌ 创建配置失败: {e}")
            return None

    async def get_config(self, config_id: str) -> Optional[UserTemplateConfig]:
        """获取配置"""
        try:
            config_doc = self.config_collection.find_one({"_id": ObjectId(config_id)})
            if config_doc:
                config_doc["id"] = str(config_doc["_id"])
                config_doc["user_id"] = str(config_doc["user_id"])
                config_doc["template_id"] = str(config_doc["template_id"])
                if config_doc.get("preference_id"):
                    config_doc["preference_id"] = str(config_doc["preference_id"])
                return UserTemplateConfig(**config_doc)
            return None
        except Exception as e:
            logger.error(f"❌ 获取配置失败: {e}")
            return None

    async def get_user_configs(self, user_id: str) -> List[UserTemplateConfig]:
        """获取用户所有配置"""
        try:
            configs = list(self.config_collection.find({"user_id": ObjectId(user_id)}))
            result = []
            for config_doc in configs:
                config_doc["id"] = str(config_doc["_id"])
                config_doc["user_id"] = str(config_doc["user_id"])
                config_doc["template_id"] = str(config_doc["template_id"])
                if config_doc.get("preference_id"):
                    config_doc["preference_id"] = str(config_doc["preference_id"])
                result.append(UserTemplateConfig(**config_doc))
            return result
        except Exception as e:
            logger.error(f"❌ 获取用户配置失败: {e}")
            return []

    async def get_active_config(
        self,
        user_id: str,
        agent_type: str,
        agent_name: str,
        preference_id: Optional[str] = None
    ) -> Optional[UserTemplateConfig]:
        """获取活跃配置"""
        try:
            query = {
                "user_id": ObjectId(user_id),
                "agent_type": agent_type,
                "agent_name": agent_name,
                "is_active": True
            }
            if preference_id:
                query["preference_id"] = ObjectId(preference_id)
            else:
                query["preference_id"] = None

            config_doc = self.config_collection.find_one(query)
            if config_doc:
                config_doc["id"] = str(config_doc["_id"])
                config_doc["user_id"] = str(config_doc["user_id"])
                config_doc["template_id"] = str(config_doc["template_id"])
                if config_doc.get("preference_id"):
                    config_doc["preference_id"] = str(config_doc["preference_id"])
                return UserTemplateConfig(**config_doc)
            return None
        except Exception as e:
            logger.error(f"❌ 获取活跃配置失败: {e}")
            return None

    async def update_config(
        self,
        config_id: str,
        update_data: UserTemplateConfigUpdate
    ) -> Optional[UserTemplateConfig]:
        """更新配置"""
        try:
            config = await self.get_config(config_id)
            if not config:
                return None

            update_doc = {}
            if update_data.template_id:
                update_doc["template_id"] = ObjectId(update_data.template_id)
            if update_data.preference_id:
                update_doc["preference_id"] = ObjectId(update_data.preference_id)
            if update_data.is_active is not None:
                update_doc["is_active"] = update_data.is_active

            update_doc["updated_at"] = datetime.utcnow()

            self.config_collection.update_one(
                {"_id": ObjectId(config_id)},
                {"$set": update_doc}
            )

            return await self.get_config(config_id)

        except Exception as e:
            logger.error(f"❌ 更新配置失败: {e}")
            return None

    def close(self):
        """关闭连接"""
        if hasattr(self, 'client') and self.client:
            self.client.close()
            logger.info("✅ UserTemplateConfigService 连接已关闭")

