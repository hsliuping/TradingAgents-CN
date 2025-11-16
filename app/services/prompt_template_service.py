"""
提示词模板服务
"""

import logging
from typing import Optional, List, Dict, Any
from bson import ObjectId
from pymongo import MongoClient
from app.core.config import settings
from app.models.prompt_template import PromptTemplate, PromptTemplateCreate, PromptTemplateUpdate
from app.models.template_history import TemplateHistory, TemplateHistoryCreate
from datetime import datetime

logger = logging.getLogger(__name__)

# 配置常量
MAX_TEMPLATE_LENGTH = 65536  # 64KB
MAX_DRAFT_TEMPLATES_PER_CONFIG = 5
MAX_ACTIVE_TEMPLATES_PER_CONFIG = 1


class PromptTemplateService:
    """提示词模板服务"""

    def __init__(self):
        self.client = MongoClient(settings.MONGO_URI)
        self.db = self.client[settings.MONGO_DB]
        self.templates_collection = self.db.prompt_templates
        self.history_collection = self.db.template_history
        self._create_indexes()

    def _create_indexes(self):
        """创建数据库索引"""
        try:
            # 模板集合索引
            self.templates_collection.create_index([("agent_type", 1), ("agent_name", 1)])
            self.templates_collection.create_index([("created_by", 1)])
            self.templates_collection.create_index([("is_system", 1)])
            self.templates_collection.create_index([("status", 1)])
            
            # 历史集合索引
            self.history_collection.create_index([("template_id", 1)])
            self.history_collection.create_index([("user_id", 1)])
            
            logger.info("✅ 提示词模板索引创建完成")
        except Exception as e:
            logger.warning(f"⚠️ 创建索引失败: {e}")

    def _validate_template_length(self, content: Dict[str, str]) -> bool:
        """验证模板内容长度"""
        total_length = sum(len(str(v)) for v in content.values())
        return total_length <= MAX_TEMPLATE_LENGTH

    async def create_template(
        self,
        template_data: PromptTemplateCreate,
        user_id: Optional[str] = None,
        base_template_id: Optional[str] = None,
        base_version: Optional[int] = None
    ) -> Optional[PromptTemplate]:
        """创建模板"""
        try:
            # 验证内容长度
            if not self._validate_template_length(template_data.content.model_dump()):
                logger.error(f"模板内容超过长度限制 ({MAX_TEMPLATE_LENGTH} bytes)")
                return None

            template_doc = {
                "agent_type": template_data.agent_type,
                "agent_name": template_data.agent_name,
                "template_name": template_data.template_name,
                "preference_type": template_data.preference_type,
                "content": template_data.content.model_dump(),
                "is_system": user_id is None,
                "created_by": ObjectId(user_id) if user_id else None,
                "base_template_id": ObjectId(base_template_id) if base_template_id else None,
                "base_version": base_version,
                "status": template_data.status,
                "created_at": datetime.utcnow(),
                "updated_at": datetime.utcnow(),
                "version": 1
            }

            result = self.templates_collection.insert_one(template_doc)
            logger.info(f"✅ 模板创建成功: {result.inserted_id}")
            
            # 记录历史
            await self._record_history(
                str(result.inserted_id),
                user_id,
                1,
                template_data.content.model_dump(),
                "create"
            )
            
            return await self.get_template(str(result.inserted_id))

        except Exception as e:
            logger.error(f"❌ 创建模板失败: {e}")
            return None

    async def get_template(self, template_id: str) -> Optional[PromptTemplate]:
        """获取模板"""
        try:
            template_doc = self.templates_collection.find_one({"_id": ObjectId(template_id)})
            if template_doc:
                template_doc["id"] = str(template_doc["_id"])
                return PromptTemplate(**template_doc)
            return None
        except Exception as e:
            logger.error(f"❌ 获取模板失败: {e}")
            return None

    async def update_template(
        self,
        template_id: str,
        update_data: PromptTemplateUpdate,
        user_id: Optional[str] = None
    ) -> Optional[PromptTemplate]:
        """更新模板"""
        try:
            template = await self.get_template(template_id)
            if not template:
                return None

            # 验证权限
            if not template.is_system and str(template.created_by) != user_id:
                logger.warning(f"用户 {user_id} 无权修改模板 {template_id}")
                return None

            # 验证内容长度
            if update_data.content and not self._validate_template_length(update_data.content.model_dump()):
                logger.error(f"模板内容超过长度限制")
                return None

            update_doc = {}
            if update_data.template_name:
                update_doc["template_name"] = update_data.template_name
            if update_data.content:
                update_doc["content"] = update_data.content.model_dump()
            if update_data.status:
                update_doc["status"] = update_data.status
            
            update_doc["updated_at"] = datetime.utcnow()
            update_doc["version"] = template.version + 1

            self.templates_collection.update_one(
                {"_id": ObjectId(template_id)},
                {"$set": update_doc}
            )

            # 记录历史
            await self._record_history(
                template_id,
                user_id,
                update_doc["version"],
                update_doc.get("content", template.content.model_dump()),
                "update",
                update_data.change_description
            )

            return await self.get_template(template_id)

        except Exception as e:
            logger.error(f"❌ 更新模板失败: {e}")
            return None

    async def _record_history(
        self,
        template_id: str,
        user_id: Optional[str],
        version: int,
        content: Dict[str, str],
        change_type: str,
        change_description: Optional[str] = None
    ):
        """记录模板历史"""
        try:
            history_doc = {
                "template_id": ObjectId(template_id),
                "user_id": ObjectId(user_id) if user_id else None,
                "version": version,
                "content": content,
                "change_description": change_description,
                "change_type": change_type,
                "created_at": datetime.utcnow()
            }
            self.history_collection.insert_one(history_doc)
        except Exception as e:
            logger.error(f"❌ 记录历史失败: {e}")

    def close(self):
        """关闭连接"""
        if hasattr(self, 'client') and self.client:
            self.client.close()
            logger.info("✅ PromptTemplateService 连接已关闭")

