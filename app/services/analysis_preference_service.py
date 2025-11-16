"""
分析偏好服务
"""

import logging
from typing import Optional, List
from bson import ObjectId
from pymongo import MongoClient
from app.core.config import settings
from app.models.analysis_preference import (
    AnalysisPreference,
    AnalysisPreferenceCreate,
    AnalysisPreferenceUpdate
)
from datetime import datetime

logger = logging.getLogger(__name__)


class AnalysisPreferenceService:
    """分析偏好服务"""

    def __init__(self):
        self.client = MongoClient(settings.MONGO_URI)
        self.db = self.client[settings.MONGO_DB]
        self.preferences_collection = self.db.analysis_preferences
        self._create_indexes()

    def _create_indexes(self):
        """创建数据库索引"""
        try:
            self.preferences_collection.create_index([("user_id", 1)])
            self.preferences_collection.create_index([("user_id", 1), ("preference_type", 1)], unique=True)
            self.preferences_collection.create_index([("is_default", 1)])
            logger.info("✅ 分析偏好索引创建完成")
        except Exception as e:
            logger.warning(f"⚠️ 创建索引失败: {e}")

    async def create_preference(
        self,
        user_id: str,
        preference_data: AnalysisPreferenceCreate
    ) -> Optional[AnalysisPreference]:
        """创建偏好"""
        try:
            # 如果设置为默认，取消其他默认
            if preference_data.is_default:
                self.preferences_collection.update_many(
                    {"user_id": ObjectId(user_id)},
                    {"$set": {"is_default": False}}
                )

            preference_doc = {
                "user_id": ObjectId(user_id),
                "preference_type": preference_data.preference_type,
                "risk_level": preference_data.risk_level,
                "confidence_threshold": preference_data.confidence_threshold,
                "position_size_multiplier": preference_data.position_size_multiplier,
                "decision_speed": preference_data.decision_speed,
                "is_default": preference_data.is_default,
                "created_at": datetime.utcnow(),
                "updated_at": datetime.utcnow()
            }

            result = self.preferences_collection.insert_one(preference_doc)
            logger.info(f"✅ 偏好创建成功: {result.inserted_id}")
            return await self.get_preference(str(result.inserted_id))

        except Exception as e:
            logger.error(f"❌ 创建偏好失败: {e}")
            return None

    async def get_preference(self, preference_id: str) -> Optional[AnalysisPreference]:
        """获取偏好"""
        try:
            pref_doc = self.preferences_collection.find_one({"_id": ObjectId(preference_id)})
            if pref_doc:
                pref_doc["id"] = str(pref_doc["_id"])
                pref_doc["user_id"] = str(pref_doc["user_id"])
                return AnalysisPreference(**pref_doc)
            return None
        except Exception as e:
            logger.error(f"❌ 获取偏好失败: {e}")
            return None

    async def get_user_preferences(self, user_id: str) -> List[AnalysisPreference]:
        """获取用户所有偏好"""
        try:
            prefs = list(self.preferences_collection.find({"user_id": ObjectId(user_id)}))
            result = []
            for pref_doc in prefs:
                pref_doc["id"] = str(pref_doc["_id"])
                pref_doc["user_id"] = str(pref_doc["user_id"])
                result.append(AnalysisPreference(**pref_doc))
            return result
        except Exception as e:
            logger.error(f"❌ 获取用户偏好失败: {e}")
            return []

    async def get_default_preference(self, user_id: str) -> Optional[AnalysisPreference]:
        """获取用户默认偏好"""
        try:
            pref_doc = self.preferences_collection.find_one({
                "user_id": ObjectId(user_id),
                "is_default": True
            })
            if pref_doc:
                pref_doc["id"] = str(pref_doc["_id"])
                pref_doc["user_id"] = str(pref_doc["user_id"])
                return AnalysisPreference(**pref_doc)
            return None
        except Exception as e:
            logger.error(f"❌ 获取默认偏好失败: {e}")
            return None

    async def update_preference(
        self,
        preference_id: str,
        update_data: AnalysisPreferenceUpdate
    ) -> Optional[AnalysisPreference]:
        """更新偏好"""
        try:
            pref = await self.get_preference(preference_id)
            if not pref:
                return None

            update_doc = {}
            if update_data.risk_level is not None:
                update_doc["risk_level"] = update_data.risk_level
            if update_data.confidence_threshold is not None:
                update_doc["confidence_threshold"] = update_data.confidence_threshold
            if update_data.position_size_multiplier is not None:
                update_doc["position_size_multiplier"] = update_data.position_size_multiplier
            if update_data.decision_speed is not None:
                update_doc["decision_speed"] = update_data.decision_speed
            if update_data.is_default is not None:
                if update_data.is_default:
                    # 取消其他默认
                    self.preferences_collection.update_many(
                        {"user_id": pref.user_id},
                        {"$set": {"is_default": False}}
                    )
                update_doc["is_default"] = update_data.is_default

            update_doc["updated_at"] = datetime.utcnow()

            self.preferences_collection.update_one(
                {"_id": ObjectId(preference_id)},
                {"$set": update_doc}
            )

            return await self.get_preference(preference_id)

        except Exception as e:
            logger.error(f"❌ 更新偏好失败: {e}")
            return None

    def close(self):
        """关闭连接"""
        if hasattr(self, 'client') and self.client:
            self.client.close()
            logger.info("✅ AnalysisPreferenceService 连接已关闭")

