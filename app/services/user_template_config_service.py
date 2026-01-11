"""
用户模板配置服务
"""

import logging
from typing import Optional, List
from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorDatabase
from app.core.database import get_mongo_db
from app.models.user_template_config import (
    UserTemplateConfig,
    UserTemplateConfigCreate,
    UserTemplateConfigUpdate
)
from datetime import datetime

logger = logging.getLogger(__name__)


class UserTemplateConfigService:
    """用户模板配置服务"""

    def __init__(self, db: Optional[AsyncIOMotorDatabase] = None):
        """
        初始化用户模板配置服务

        Args:
            db: MongoDB数据库实例（可选，默认使用全局连接池）
        """
        self.db = db if db is not None else get_mongo_db()
        self.config_collection = self.db.user_template_configs

    async def _create_indexes(self):
        """创建数据库索引"""
        try:
            await self.config_collection.create_index([("user_id", 1)])
            await self.config_collection.create_index([
                ("user_id", 1),
                ("agent_type", 1),
                ("agent_name", 1),
                ("preference_id", 1)
            ], unique=True)
            await self.config_collection.create_index([("is_active", 1)])
            logger.info("✅ 用户模板配置索引创建完成")
        except Exception as e:
            logger.warning(f"⚠️ 创建索引失败: {e}")

    async def create_config(
        self,
        user_id: str,
        config_data: UserTemplateConfigCreate
    ) -> Optional[UserTemplateConfig]:
        """创建配置（设为当前时自动发布模板）"""
        try:
            # 🔥 检查模板状态，如果是草稿状态，自动改为已发布
            from app.services.prompt_template_service import PromptTemplateService
            template_service = PromptTemplateService(self.db)

            template = await template_service.get_template(config_data.template_id)
            if template and template.status == "draft":
                logger.info(
                    f"🔄 模板 {config_data.template_id} 是草稿状态，"
                    f"设为当前时自动发布"
                )
                # 自动发布模板
                from app.schemas.prompt_template import PromptTemplateUpdate
                await template_service.update_template(
                    config_data.template_id,
                    PromptTemplateUpdate(status="active"),
                    user_id=user_id
                )
                logger.info(f"✅ 模板 {config_data.template_id} 已自动发布")

            # 将同用户同Agent的其他配置设为非激活
            await self.config_collection.update_many(
                {
                    "user_id": ObjectId(user_id),
                    "agent_type": config_data.agent_type,
                    "agent_name": config_data.agent_name
                },
                {"$set": {"is_active": False}}
            )
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

            result = await self.config_collection.insert_one(config_doc)
            logger.info(f"✅ 配置创建成功: {result.inserted_id}")
            return await self.get_config(str(result.inserted_id))

        except Exception as e:
            logger.error(f"❌ 创建配置失败: {e}")
            return None

    async def get_config(self, config_id: str) -> Optional[UserTemplateConfig]:
        """获取配置"""
        try:
            config_doc = await self.config_collection.find_one({"_id": ObjectId(config_id)})
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
            cursor = self.config_collection.find({"user_id": ObjectId(user_id)})
            configs = await cursor.to_list(length=None)
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

            config_doc = await self.config_collection.find_one(query)
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
        """更新配置（设为激活时自动发布模板）"""
        try:
            config = await self.get_config(config_id)
            if not config:
                return None

            update_doc = {}

            # 🔥 如果更新了 template_id，检查新模板状态
            if update_data.template_id:
                from app.services.prompt_template_service import PromptTemplateService
                template_service = PromptTemplateService(self.db)

                template = await template_service.get_template(update_data.template_id)
                if template and template.status == "draft":
                    logger.info(
                        f"🔄 模板 {update_data.template_id} 是草稿状态，"
                        f"设为当前时自动发布"
                    )
                    # 自动发布模板
                    from app.schemas.prompt_template import PromptTemplateUpdate
                    await template_service.update_template(
                        update_data.template_id,
                        PromptTemplateUpdate(status="active"),
                        user_id=str(config.user_id)
                    )
                    logger.info(f"✅ 模板 {update_data.template_id} 已自动发布")

                update_doc["template_id"] = ObjectId(update_data.template_id)

            if update_data.preference_id:
                update_doc["preference_id"] = ObjectId(update_data.preference_id)

            if update_data.is_active is not None:
                # 若设为激活，取消同用户同Agent其他配置的激活
                if update_data.is_active:
                    # 🔥 检查当前配置的模板状态
                    template_id = update_data.template_id or config.template_id
                    from app.services.prompt_template_service import PromptTemplateService
                    template_service = PromptTemplateService(self.db)

                    template = await template_service.get_template(template_id)
                    if template and template.status == "draft":
                        logger.info(
                            f"🔄 模板 {template_id} 是草稿状态，"
                            f"设为激活时自动发布"
                        )
                        # 自动发布模板
                        from app.schemas.prompt_template import PromptTemplateUpdate
                        await template_service.update_template(
                            template_id,
                            PromptTemplateUpdate(status="active"),
                            user_id=str(config.user_id)
                        )
                        logger.info(f"✅ 模板 {template_id} 已自动发布")

                    await self.config_collection.update_many(
                        {
                            "user_id": ObjectId(config.user_id),
                            "agent_type": config.agent_type,
                            "agent_name": config.agent_name
                        },
                        {"$set": {"is_active": False}}
                    )
                update_doc["is_active"] = update_data.is_active

            update_doc["updated_at"] = datetime.utcnow()

            await self.config_collection.update_one(
                {"_id": ObjectId(config_id)},
                {"$set": update_doc}
            )

            return await self.get_config(config_id)

        except Exception as e:
            logger.error(f"❌ 更新配置失败: {e}")
            return None

    async def get_effective_template(
        self,
        user_id: str,
        agent_type: str,
        agent_name: str,
        preference_id: Optional[str] = None
    ) -> Optional[dict]:
        """获取有效模板（用户优先，系统兜底）"""
        try:
            from app.services.prompt_template_service import PromptTemplateService
            template_service = PromptTemplateService(self.db)

            # 1. 先查找用户的活跃配置
            config = await self.get_active_config(user_id, agent_type, agent_name, preference_id)

            if config:
                # 获取用户模板（只使用已发布状态的模板）
                template_doc = await template_service.templates_collection.find_one({
                    "_id": ObjectId(config.template_id),
                    "status": "active"  # 🔥 只使用已发布的模板
                })
                if template_doc:
                    return {
                        "template_id": str(template_doc["_id"]),
                        "content": template_doc.get("content"),
                        "source": "user",
                        "version": template_doc.get("version")
                    }
                else:
                    # 如果用户配置的模板是草稿状态，记录警告并跳过
                    logger.warning(
                        f"⚠️ 用户配置的模板 {config.template_id} 不是已发布状态，跳过使用"
                    )

            # 2. 如果没有用户配置，查找系统默认模板
            system_template = await template_service.templates_collection.find_one({
                "agent_type": agent_type,
                "agent_name": agent_name,
                "preference_type": preference_id,
                "is_system": True,
                "status": "active"
            })

            if system_template:
                return {
                    "template_id": str(system_template["_id"]),
                    "content": system_template.get("content"),
                    "source": "system",
                    "version": system_template.get("version")
                }

            return None

        except Exception as e:
            logger.error(f"❌ 获取有效模板失败: {e}")
            return None

