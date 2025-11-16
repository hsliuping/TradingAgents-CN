"""
模板历史服务
"""

import logging
from typing import Optional, List, Dict, Any
from bson import ObjectId
from pymongo import MongoClient
from app.core.config import settings
from app.models.template_history import TemplateHistory, TemplateHistoryCreate
from datetime import datetime

logger = logging.getLogger(__name__)


class TemplateHistoryService:
    """模板历史服务"""

    def __init__(self):
        self.client = MongoClient(settings.MONGO_URI)
        self.db = self.client[settings.MONGO_DB]
        self.history_collection = self.db.template_history
        self._create_indexes()

    def _create_indexes(self):
        """创建数据库索引"""
        try:
            self.history_collection.create_index([("template_id", 1)])
            self.history_collection.create_index([("user_id", 1)])
            self.history_collection.create_index([("template_id", 1), ("version", -1)])
            self.history_collection.create_index([("created_at", -1)])
            logger.info("✅ 模板历史索引创建完成")
        except Exception as e:
            logger.warning(f"⚠️ 创建索引失败: {e}")

    async def create_history(
        self,
        history_data: TemplateHistoryCreate,
        user_id: Optional[str] = None
    ) -> Optional[TemplateHistory]:
        """创建历史记录"""
        try:
            history_doc = {
                "template_id": ObjectId(history_data.template_id),
                "user_id": ObjectId(user_id) if user_id else None,
                "version": history_data.version,
                "content": history_data.content,
                "change_description": history_data.change_description,
                "change_type": history_data.change_type,
                "created_at": datetime.utcnow()
            }

            result = self.history_collection.insert_one(history_doc)
            logger.info(f"✅ 历史记录创建成功: {result.inserted_id}")
            return await self.get_history(str(result.inserted_id))

        except Exception as e:
            logger.error(f"❌ 创建历史记录失败: {e}")
            return None

    async def get_history(self, history_id: str) -> Optional[TemplateHistory]:
        """获取历史记录"""
        try:
            history_doc = self.history_collection.find_one({"_id": ObjectId(history_id)})
            if history_doc:
                history_doc["id"] = str(history_doc["_id"])
                history_doc["template_id"] = str(history_doc["template_id"])
                if history_doc.get("user_id"):
                    history_doc["user_id"] = str(history_doc["user_id"])
                return TemplateHistory(**history_doc)
            return None
        except Exception as e:
            logger.error(f"❌ 获取历史记录失败: {e}")
            return None

    async def get_template_history(
        self,
        template_id: str,
        skip: int = 0,
        limit: int = 20
    ) -> List[TemplateHistory]:
        """获取模板的历史记录"""
        try:
            histories = list(
                self.history_collection
                .find({"template_id": ObjectId(template_id)})
                .sort("version", -1)
                .skip(skip)
                .limit(limit)
            )
            result = []
            for history_doc in histories:
                history_doc["id"] = str(history_doc["_id"])
                history_doc["template_id"] = str(history_doc["template_id"])
                if history_doc.get("user_id"):
                    history_doc["user_id"] = str(history_doc["user_id"])
                result.append(TemplateHistory(**history_doc))
            return result
        except Exception as e:
            logger.error(f"❌ 获取模板历史失败: {e}")
            return []

    async def get_version_by_number(
        self,
        template_id: str,
        version: int
    ) -> Optional[TemplateHistory]:
        """按版本号获取历史记录"""
        try:
            history_doc = self.history_collection.find_one({
                "template_id": ObjectId(template_id),
                "version": version
            })
            if history_doc:
                history_doc["id"] = str(history_doc["_id"])
                history_doc["template_id"] = str(history_doc["template_id"])
                if history_doc.get("user_id"):
                    history_doc["user_id"] = str(history_doc["user_id"])
                return TemplateHistory(**history_doc)
            return None
        except Exception as e:
            logger.error(f"❌ 获取版本历史失败: {e}")
            return None

    async def compare_versions(
        self,
        template_id: str,
        version1: int,
        version2: int
    ) -> Optional[Dict[str, Any]]:
        """对比两个版本"""
        try:
            hist1 = await self.get_version_by_number(template_id, version1)
            hist2 = await self.get_version_by_number(template_id, version2)

            if not hist1 or not hist2:
                return None

            # 简单的差异对比
            differences = {}
            for key in hist1.content:
                if hist1.content.get(key) != hist2.content.get(key):
                    differences[key] = {
                        "version1": hist1.content.get(key),
                        "version2": hist2.content.get(key)
                    }

            return {
                "template_id": template_id,
                "version1": version1,
                "version2": version2,
                "differences": differences,
                "compared_at": datetime.utcnow().isoformat()
            }

        except Exception as e:
            logger.error(f"❌ 对比版本失败: {e}")
            return None

    def close(self):
        """关闭连接"""
        if hasattr(self, 'client') and self.client:
            self.client.close()
            logger.info("✅ TemplateHistoryService 连接已关闭")

