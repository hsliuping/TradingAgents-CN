"""
提示词模板服务
"""

import logging
from typing import Optional, List, Dict, Any, Tuple
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
        self.db = db if db is not None else get_mongo_db()
        self.templates_collection = self.db.prompt_templates
        self.history_collection = self.db.template_history

    async def _create_indexes(self):
        """创建数据库索引"""
        try:
            # 模板集合索引
            await self.templates_collection.create_index([("agent_type", 1), ("agent_name", 1)])
            await self.templates_collection.create_index([("workflow_id", 1)])  # 流程专属模板查询
            await self.templates_collection.create_index([("node_id", 1)])  # 节点专属模板查询
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

    def _merge_remark_suffix(self, remark: str, remark_suffix: Optional[str] = None) -> str:
        """将同步备注追加到 remark，避免重复追加。"""
        merged_remark = (remark or "").strip()
        if not remark_suffix:
            return merged_remark

        suffix = remark_suffix.strip()
        if not suffix:
            return merged_remark
        if suffix in merged_remark:
            return merged_remark
        return f"{merged_remark}\n{suffix}".strip()

    async def upsert_system_template(
        self,
        template_data: PromptTemplateCreate,
        remark_suffix: Optional[str] = None,
    ) -> Tuple[Optional[PromptTemplate], str]:
        """按 agent_type/agent_name/preference_type 幂等同步系统模板。"""
        try:
            content_doc = template_data.content.model_dump()
            if not self._validate_template_length(content_doc):
                logger.error(f"模板内容超过长度限制 ({MAX_TEMPLATE_LENGTH} bytes)")
                return None, "error"

            template_key = {
                "agent_type": template_data.agent_type,
                "agent_name": template_data.agent_name,
                "preference_type": template_data.preference_type,
                "is_system": True,
            }
            existing_docs = await self.templates_collection.find(template_key).to_list(length=10)

            if len(existing_docs) > 1:
                logger.error(
                    "❌ 系统模板存在重复记录，拒绝自动同步: %s/%s/%s",
                    template_data.agent_type,
                    template_data.agent_name,
                    template_data.preference_type,
                )
                return None, "conflict"

            existing_doc = existing_docs[0] if existing_docs else None
            now = datetime.utcnow()
            remark = self._merge_remark_suffix(getattr(template_data, "remark", "") or "", remark_suffix)

            if existing_doc:
                unchanged = (
                    existing_doc.get("template_name") == template_data.template_name
                    and (existing_doc.get("content") or {}) == content_doc
                    and (existing_doc.get("remark") or "") == remark
                    and existing_doc.get("status") == template_data.status
                    and existing_doc.get("is_system") is True
                    and existing_doc.get("created_by") is None
                )
                if unchanged:
                    return await self.get_template(str(existing_doc["_id"])), "unchanged"

                version = int(existing_doc.get("version") or 1) + 1
                query = {"_id": existing_doc["_id"]}
                template_id = str(existing_doc["_id"])
                created_at = existing_doc.get("created_at") or now
                operation = "updated"
            else:
                version = 1
                query = template_key
                template_id = None
                created_at = now
                operation = "created"

            result = await self.templates_collection.update_one(
                query,
                {
                    "$set": {
                        "agent_type": template_data.agent_type,
                        "agent_name": template_data.agent_name,
                        "template_name": template_data.template_name,
                        "preference_type": template_data.preference_type,
                        "content": content_doc,
                        "remark": remark,
                        "is_system": True,
                        "created_by": None,
                        "base_template_id": None,
                        "base_version": None,
                        "status": template_data.status,
                        "updated_at": now,
                        "version": version,
                    },
                    "$setOnInsert": {
                        "created_at": created_at,
                    },
                },
                upsert=True,
            )

            if template_id is None:
                template_id = str(result.upserted_id) if result.upserted_id else None
                if template_id is None:
                    created_doc = await self.templates_collection.find_one(template_key)
                    template_id = str(created_doc["_id"]) if created_doc else None

            if template_id is None:
                logger.error(
                    "❌ 系统模板同步后无法定位模板记录: %s/%s/%s",
                    template_data.agent_type,
                    template_data.agent_name,
                    template_data.preference_type,
                )
                return None, "error"

            await self._record_history(
                template_id,
                None,
                version,
                content_doc,
                "create" if operation == "created" else "update",
            )

            return await self.get_template(template_id), operation

        except Exception as e:
            logger.error(f"❌ 同步系统模板失败: {e}", exc_info=True)
            return None, "error"

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
            # 流程专属提示词：支持与工作流绑定
            if getattr(template_data, "workflow_id", None):
                template_doc["workflow_id"] = template_data.workflow_id
            # 节点专属提示词：支持与节点绑定
            if getattr(template_data, "node_id", None):
                template_doc["node_id"] = template_data.node_id

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
            logger.info(f"🔍 获取模板: template_id={template_id}")

            # 尝试转换为 ObjectId
            try:
                oid = ObjectId(template_id)
                logger.info(f"🔍 ObjectId 转换成功: {oid}")
            except Exception as e:
                logger.error(f"❌ ObjectId 转换失败: {e}")
                return None

            template_doc = await self.templates_collection.find_one({"_id": oid})
            logger.info(f"🔍 查询结果: {template_doc is not None}")

            if template_doc:
                # 兼容旧数据：确保content包含完整字段
                content = template_doc.get("content") or {}
                if isinstance(content, dict):
                    content.setdefault("system_prompt", "")
                    content.setdefault("user_prompt", "")
                    content.setdefault("tool_guidance", "")
                    content.setdefault("analysis_requirements", "")
                    content.setdefault("output_format", "")
                    content.setdefault("constraints", "")
                    template_doc["content"] = content
                template_doc["id"] = str(template_doc["_id"])
                return PromptTemplate(**template_doc)
            else:
                # 尝试用字符串 ID 查询（兼容旧数据）
                logger.warning(f"⚠️ ObjectId 查询无结果，尝试字符串查询...")
                template_doc = await self.templates_collection.find_one({"_id": template_id})
                if template_doc:
                    logger.info(f"✅ 字符串查询成功")
                    content = template_doc.get("content") or {}
                    if isinstance(content, dict):
                        content.setdefault("system_prompt", "")
                        content.setdefault("user_prompt", "")
                        content.setdefault("tool_guidance", "")
                        content.setdefault("analysis_requirements", "")
                        content.setdefault("output_format", "")
                        content.setdefault("constraints", "")
                        template_doc["content"] = content
                    template_doc["id"] = str(template_doc["_id"])
                    return PromptTemplate(**template_doc)
            return None
        except Exception as e:
            logger.error(f"❌ 获取模板失败: {e}", exc_info=True)
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
            if update_data.workflow_id is not None:
                update_doc["workflow_id"] = update_data.workflow_id
            if update_data.node_id is not None:
                update_doc["node_id"] = update_data.node_id

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

