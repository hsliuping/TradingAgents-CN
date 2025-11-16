"""
提示词模板服务
"""

import logging
from typing import Optional, List, Dict, Any
from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorDatabase
from app.core.database import get_mongo_db
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

    def __init__(self, db: Optional[AsyncIOMotorDatabase] = None):
        """
        初始化提示词模板服务

        Args:
            db: MongoDB数据库实例（可选，默认使用全局连接池）
        """
        self.db = db or get_mongo_db()
        self.templates_collection = self.db.prompt_templates
        self.history_collection = self.db.template_history

    async def _create_indexes(self):
        """创建数据库索引"""
        try:
            # 模板集合索引
            await self.templates_collection.create_index([("agent_type", 1), ("agent_name", 1)])
            await self.templates_collection.create_index([("created_by", 1)])
            await self.templates_collection.create_index([("is_system", 1)])
            await self.templates_collection.create_index([("status", 1)])

            # 历史集合索引
            await self.history_collection.create_index([("template_id", 1)])
            await self.history_collection.create_index([("user_id", 1)])

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
                "remark": getattr(template_data, "remark", ""),
                "is_system": user_id is None,
                "created_by": ObjectId(user_id) if user_id else None,
                "base_template_id": ObjectId(base_template_id) if base_template_id else None,
                "base_version": base_version,
                "status": template_data.status,
                "created_at": datetime.utcnow(),
                "updated_at": datetime.utcnow(),
                "version": 1
            }

            result = await self.templates_collection.insert_one(template_doc)
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
            template_doc = await self.templates_collection.find_one({"_id": ObjectId(template_id)})
            if template_doc:
                # 兼容旧数据：确保content包含完整字段
                content = template_doc.get("content") or {}
                if isinstance(content, dict):
                    content.setdefault("system_prompt", "")
                    content.setdefault("tool_guidance", "")
                    content.setdefault("analysis_requirements", "")
                    content.setdefault("output_format", "")
                    content.setdefault("constraints", "")
                    template_doc["content"] = content
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
            # 系统模板不允许直接编辑
            if template.is_system:
                logger.warning(f"系统模板不允许编辑: {template_id}")
                return None
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
            if update_data.remark is not None:
                update_doc["remark"] = update_data.remark
            if update_data.status:
                update_doc["status"] = update_data.status
            
            update_doc["updated_at"] = datetime.utcnow()
            update_doc["version"] = template.version + 1

            await self.templates_collection.update_one(
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

    async def delete_template(
        self,
        template_id: str,
        user_id: Optional[str] = None
    ) -> bool:
        """删除模板（仅允许删除用户模板）"""
        try:
            template = await self.get_template(template_id)
            if not template:
                return False

            if template.is_system:
                logger.warning(f"系统模板不允许删除: {template_id}")
                return False

            if str(template.created_by) != user_id:
                logger.warning(f"用户 {user_id} 无权删除模板 {template_id}")
                return False

            await self.templates_collection.delete_one({"_id": ObjectId(template_id)})

            await self._record_history(
                template_id,
                user_id,
                template.version,
                template.content.model_dump(),
                "delete",
                "deleted"
            )

            return True
        except Exception as e:
            logger.error(f"❌ 删除模板失败: {e}")
            return False

    async def get_system_templates(
        self,
        agent_type: str,
        agent_name: str,
        preference_type: Optional[str] = None
    ) -> List[PromptTemplate]:
        """获取系统模板"""
        try:
            query = {
                "agent_type": agent_type,
                "agent_name": agent_name,
                "is_system": True,
                "status": "active"
            }
            if preference_type:
                query["preference_type"] = preference_type

            cursor = self.templates_collection.find(query)
            templates = await cursor.to_list(length=None)
            result = []
            for template_doc in templates:
                template_doc["id"] = str(template_doc["_id"])
                result.append(PromptTemplate(**template_doc))
            return result
        except Exception as e:
            logger.error(f"❌ 获取系统模板失败: {e}")
            return []

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
            await self.history_collection.insert_one(history_doc)
        except Exception as e:
            logger.error(f"❌ 记录历史失败: {e}")

