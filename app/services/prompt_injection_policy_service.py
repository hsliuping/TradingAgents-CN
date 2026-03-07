"""
Prompt 注入策略服务

管理 prompt_injection_policies 集合的 CRUD 操作，
支持按 Agent + 场景查询策略。
"""

import logging
from typing import Optional, List, Dict, Any

from bson import ObjectId
from app.core.database import get_mongo_db
from app.utils.timezone import now_tz

logger = logging.getLogger(__name__)

COLLECTION = "prompt_injection_policies"


class PromptInjectionPolicyService:
    """Prompt 注入策略服务"""

    async def list_policies(
        self,
        agent_type: Optional[str] = None,
        agent_name: Optional[str] = None,
        scope: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        列表查询，支持 agent_type / agent_name / scope 过滤
        """
        db = get_mongo_db()
        query = {}
        if agent_type:
            query["agent_type"] = agent_type
        if agent_name:
            query["agent_name"] = agent_name
        if scope:
            query["scope"] = scope

        cursor = db[COLLECTION].find(query).sort([
            ("agent_type", 1),
            ("agent_name", 1),
            ("scope", 1),
        ])
        results = []
        async for doc in cursor:
            doc["id"] = str(doc.pop("_id"))
            doc["created_at"] = str(doc.get("created_at", ""))
            doc["updated_at"] = str(doc.get("updated_at", ""))
            results.append(doc)
        return results

    async def get_policy(self, policy_id: str) -> Optional[Dict[str, Any]]:
        """获取单个策略"""
        db = get_mongo_db()
        try:
            doc = await db[COLLECTION].find_one({"_id": ObjectId(policy_id)})
        except Exception:
            return None
        if doc:
            doc["id"] = str(doc.pop("_id"))
            doc["created_at"] = str(doc.get("created_at", ""))
            doc["updated_at"] = str(doc.get("updated_at", ""))
        return doc

    async def get_policy_by_agent_scope(
        self,
        agent_type: str,
        agent_name: str,
        scope: str,
    ) -> Optional[Dict[str, Any]]:
        """
        按 Agent + 场景获取策略（用于组装服务，异步）
        """
        db = get_mongo_db()
        doc = await db[COLLECTION].find_one({
            "agent_type": agent_type,
            "agent_name": agent_name,
            "scope": scope,
            "enabled": True,
        })
        if doc:
            doc["id"] = str(doc.pop("_id"))
        return doc

    def get_policy_by_agent_scope_sync(
        self,
        agent_type: str,
        agent_name: str,
        scope: str,
    ) -> Optional[Dict[str, Any]]:
        """
        按 Agent + 场景获取策略（同步版本，用于 base.py 等同步调用）
        """
        from app.core.database import get_mongo_db_sync
        db = get_mongo_db_sync()
        try:
            doc = db[COLLECTION].find_one({
                "agent_type": agent_type,
                "agent_name": agent_name,
                "scope": scope,
                "enabled": True,
            })
            if doc:
                doc["id"] = str(doc.pop("_id"))
            return doc
        except Exception as e:
            logger.warning(f"⚠️ 获取注入策略失败: {e}")
            return None

    async def create_policy(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """创建策略"""
        db = get_mongo_db()
        now = now_tz()
        data["created_at"] = now
        data["updated_at"] = now
        data.setdefault("enabled", True)
        data.setdefault("injection_mode", "summary")
        data.setdefault("inherit_industry_for_stock", True)
        data.setdefault("include_capability_block", True)
        data.setdefault("include_external_gap_notice", True)
        data.setdefault("include_comparable_companies", True)
        data.setdefault("inject_position", "analysis_requirements")
        data.setdefault("version", 1)

        result = await db[COLLECTION].insert_one(data)
        data["id"] = str(result.inserted_id)
        logger.info(f"✅ 创建注入策略: {data.get('agent_type')}/{data.get('agent_name')}/{data.get('scope')}")
        return data

    async def update_policy(self, policy_id: str, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """更新策略"""
        db = get_mongo_db()
        # 排除不可更新字段
        update_data = {k: v for k, v in data.items() if k not in ("id", "_id", "agent_type", "agent_name", "scope", "created_at")}
        if not update_data:
            return await self.get_policy(policy_id)
        update_data["updated_at"] = now_tz()

        try:
            result = await db[COLLECTION].update_one(
                {"_id": ObjectId(policy_id)},
                {"$set": update_data}
            )
        except Exception:
            return None
        if result.modified_count > 0:
            logger.info(f"✅ 更新注入策略: {policy_id}")
            return await self.get_policy(policy_id)
        return await self.get_policy(policy_id)

    async def delete_policy(self, policy_id: str) -> bool:
        """删除策略"""
        db = get_mongo_db()
        try:
            result = await db[COLLECTION].delete_one({"_id": ObjectId(policy_id)})
            return result.deleted_count > 0
        except Exception:
            return False

    async def upsert_policy(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        创建或更新策略（按 agent_type + agent_name + scope 唯一）
        用于初始化脚本
        """
        db = get_mongo_db()
        agent_type = data.get("agent_type")
        agent_name = data.get("agent_name")
        scope = data.get("scope", "general")
        if not agent_type or not agent_name:
            raise ValueError("agent_type 和 agent_name 必填")

        existing = await db[COLLECTION].find_one({
            "agent_type": agent_type,
            "agent_name": agent_name,
            "scope": scope,
        })
        now = now_tz()
        if existing:
            update_data = {
                "enabled": data.get("enabled", True),
                "injection_mode": data.get("injection_mode", "summary"),
                "inherit_industry_for_stock": data.get("inherit_industry_for_stock", True),
                "include_capability_block": data.get("include_capability_block", True),
                "include_external_gap_notice": data.get("include_external_gap_notice", True),
                "include_comparable_companies": data.get("include_comparable_companies", True),
                "inject_position": data.get("inject_position", "analysis_requirements"),
                "version": existing.get("version", 1),
                "updated_at": now,
            }
            await db[COLLECTION].update_one(
                {"_id": existing["_id"]},
                {"$set": update_data}
            )
            existing["id"] = str(existing.pop("_id"))
            existing.update(update_data)
            return existing
        else:
            data["created_at"] = now
            data["updated_at"] = now
            data.setdefault("enabled", True)
            data.setdefault("injection_mode", "summary")
            data.setdefault("inherit_industry_for_stock", True)
            data.setdefault("include_capability_block", True)
            data.setdefault("include_external_gap_notice", True)
            data.setdefault("include_comparable_companies", True)
            data.setdefault("inject_position", "analysis_requirements")
            data.setdefault("scope", scope)
            data.setdefault("version", 1)
            result = await db[COLLECTION].insert_one(data)
            data["id"] = str(result.inserted_id)
            return data
