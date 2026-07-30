"""Agent 断言存储服务（P2: 反思 lesson 升级为可执行断言）

同步 API（load_enabled_assertions_sync / increment_hit_count_sync）供 AssertionExecutor
在同步 agent execute 上下文调用；异步 API 供后台管理/生成器使用。

非阻塞原则：所有方法内部 try/except，异常不外抛，不影响 agent 执行。
进程内缓存：enabled assertions 按 agent_id 缓存 60s，避免每次执行都查 MongoDB。
"""

import logging
import threading
import time
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from app.core.database import get_mongo_db, get_mongo_db_sync
from app.models.agent_assertion import AgentAssertion
from app.utils.timezone import now_tz

logger = logging.getLogger("app.services.agent_assertion_service")


class AgentAssertionService:
    """断言存储服务"""

    COLLECTION_NAME = "agent_assertions"

    def __init__(self):
        # 进程内缓存: agent_id -> (timestamp, assertions)
        self._cache: Dict[str, Tuple[float, List[AgentAssertion]]] = {}
        self._cache_lock = threading.Lock()
        # 默认 TTL，可被 settings.AGENT_ASSERTION_CACHE_TTL_SECONDS 覆盖
        self._cache_ttl_seconds: float = 60.0

    # ==================== 同步 API（agent execute 上下文） ====================

    def load_enabled_assertions_sync(self, agent_id: str) -> List[AgentAssertion]:
        """按 agent 加载启用的断言（带进程内缓存）。

        非阻塞：任何异常都被捕获并返回空列表，不影响 agent 执行。
        """
        if not agent_id:
            return []

        # 1. 查缓存
        now_ts = time.time()
        with self._cache_lock:
            cached = self._cache.get(agent_id)
            if cached is not None:
                cached_ts, cached_assertions = cached
                if now_ts - cached_ts < self._cache_ttl_seconds:
                    return cached_assertions

        # 2. 查 MongoDB
        assertions = self._load_from_db_sync(agent_id)

        # 3. 写缓存
        with self._cache_lock:
            self._cache[agent_id] = (now_ts, assertions)

        return assertions

    def _load_from_db_sync(self, agent_id: str) -> List[AgentAssertion]:
        """从 MongoDB 同步加载启用断言（非阻塞）"""
        try:
            db = get_mongo_db_sync()
            collection = db[self.COLLECTION_NAME]
            cursor = collection.find(
                {"target_agent": agent_id, "enabled": True}
            )
            results: List[AgentAssertion] = []
            for doc in cursor:
                doc.pop("_id", None)
                try:
                    results.append(AgentAssertion(**doc))
                except Exception as parse_exc:
                    logger.warning(
                        f"⚠️ 断言文档解析失败（跳过）: assertion_id={doc.get('assertion_id')}, error={parse_exc}"
                    )
            return results
        except Exception as e:
            logger.warning(f"⚠️ 加载启用断言失败（agent={agent_id}）: {e}")
            return []

    def increment_hit_count_sync(self, assertion_id: str) -> bool:
        """命中计数 +1（fire-and-forget，非阻塞）"""
        if not assertion_id:
            return False
        try:
            db = get_mongo_db_sync()
            collection = db[self.COLLECTION_NAME]
            collection.update_one(
                {"assertion_id": assertion_id},
                {
                    "$inc": {"hit_count": 1},
                    "$set": {"last_hit_at": now_tz(), "updated_at": now_tz()},
                },
            )
            return True
        except Exception as e:
            logger.warning(f"⚠️ 断言命中计数失败（assertion_id={assertion_id}）: {e}")
            return False

    def create_assertion_sync(self, assertion: AgentAssertion) -> bool:
        """同步创建断言（供独立脚本/测试使用，无需 async 上下文）。

        与 create_assertion（异步）等价，使用同步 MongoClient。
        非阻塞：失败返回 False，不抛异常。
        """
        try:
            db = get_mongo_db_sync()
            collection = db[self.COLLECTION_NAME]
            doc = assertion.model_dump()
            collection.insert_one(doc)
            self.invalidate_cache(assertion.target_agent)
            logger.info(
                f"✅ 断言已创建(sync): assertion_id={assertion.assertion_id}, agent={assertion.target_agent}"
            )
            return True
        except Exception as e:
            logger.error(f"❌ 创建断言失败(sync): {e}")
            return False

    def bulk_create_assertions_sync(self, assertions: List[AgentAssertion]) -> int:
        """同步批量创建断言（供断言生成器脚本使用）。"""
        if not assertions:
            return 0
        try:
            db = get_mongo_db_sync()
            collection = db[self.COLLECTION_NAME]
            docs = [a.model_dump() for a in assertions]
            result = collection.insert_many(docs)
            affected_agents = {a.target_agent for a in assertions}
            for agent_id in affected_agents:
                self.invalidate_cache(agent_id)
            logger.info(f"✅ 批量创建(sync) {len(result.inserted_ids)} 条断言")
            return len(result.inserted_ids)
        except Exception as e:
            logger.error(f"❌ 批量创建断言失败(sync): {e}")
            return 0

    def invalidate_cache(self, agent_id: Optional[str] = None) -> None:
        """失效缓存（管理 API 修改断言后调用）"""
        with self._cache_lock:
            if agent_id is None:
                self._cache.clear()
            else:
                self._cache.pop(agent_id, None)

    # ==================== 异步 API（后台/管理） ====================

    async def create_assertion(self, assertion: AgentAssertion) -> Optional[AgentAssertion]:
        """创建断言"""
        try:
            db = get_mongo_db()
            collection = db[self.COLLECTION_NAME]
            doc = assertion.model_dump()
            await collection.insert_one(doc)
            self.invalidate_cache(assertion.target_agent)
            logger.info(f"✅ 断言已创建: assertion_id={assertion.assertion_id}, agent={assertion.target_agent}")
            return assertion
        except Exception as e:
            logger.error(f"❌ 创建断言失败: {e}")
            return None

    async def bulk_create_assertions(self, assertions: List[AgentAssertion]) -> int:
        """批量创建断言"""
        if not assertions:
            return 0
        try:
            db = get_mongo_db()
            collection = db[self.COLLECTION_NAME]
            docs = [a.model_dump() for a in assertions]
            result = await collection.insert_many(docs)
            # 失效所有相关 agent 的缓存
            affected_agents = {a.target_agent for a in assertions}
            for agent_id in affected_agents:
                self.invalidate_cache(agent_id)
            logger.info(f"✅ 批量创建 {len(result.inserted_ids)} 条断言")
            return len(result.inserted_ids)
        except Exception as e:
            logger.error(f"❌ 批量创建断言失败: {e}")
            return 0

    async def update_assertion(self, assertion_id: str, update: Dict[str, Any]) -> bool:
        """更新断言字段"""
        try:
            db = get_mongo_db()
            collection = db[self.COLLECTION_NAME]
            update_doc = dict(update)
            update_doc["updated_at"] = now_tz()
            result = await collection.update_one(
                {"assertion_id": assertion_id},
                {"$set": update_doc},
            )
            if result.modified_count > 0:
                # 失效所有缓存（不知道断言属于哪个 agent，保守全清）
                self.invalidate_cache()
                return True
            return False
        except Exception as e:
            logger.error(f"❌ 更新断言失败: {e}")
            return False

    async def delete_assertion(self, assertion_id: str) -> bool:
        """删除断言"""
        try:
            db = get_mongo_db()
            collection = db[self.COLLECTION_NAME]
            result = await collection.delete_one({"assertion_id": assertion_id})
            if result.deleted_count > 0:
                self.invalidate_cache()
                return True
            return False
        except Exception as e:
            logger.error(f"❌ 删除断言失败: {e}")
            return False

    async def enable_assertion(self, assertion_id: str, enabled: bool) -> bool:
        """启用/禁用断言"""
        return await self.update_assertion(assertion_id, {"enabled": enabled})

    async def get_assertions(
        self,
        agent_id: Optional[str] = None,
        enabled: Optional[bool] = None,
        severity: Optional[str] = None,
        assertion_type: Optional[str] = None,
        limit: int = 100,
    ) -> List[AgentAssertion]:
        """查询断言"""
        try:
            db = get_mongo_db()
            collection = db[self.COLLECTION_NAME]
            query: Dict[str, Any] = {}
            if agent_id:
                query["target_agent"] = agent_id
            if enabled is not None:
                query["enabled"] = enabled
            if severity:
                query["severity"] = severity
            if assertion_type:
                query["assertion_type"] = assertion_type

            cursor = collection.find(query).sort("created_at", -1).limit(limit)
            results: List[AgentAssertion] = []
            async for doc in cursor:
                doc.pop("_id", None)
                try:
                    results.append(AgentAssertion(**doc))
                except Exception as parse_exc:
                    logger.warning(f"⚠️ 断言文档解析失败: {parse_exc}")
            return results
        except Exception as e:
            logger.error(f"❌ 查询断言失败: {e}")
            return []

    async def get_assertion(self, assertion_id: str) -> Optional[AgentAssertion]:
        """获取单条断言"""
        try:
            db = get_mongo_db()
            collection = db[self.COLLECTION_NAME]
            doc = await collection.find_one({"assertion_id": assertion_id})
            if doc is None:
                return None
            doc.pop("_id", None)
            return AgentAssertion(**doc)
        except Exception as e:
            logger.error(f"❌ 获取断言失败: {e}")
            return None

    # ==================== 索引初始化 ====================

    async def create_indexes(self) -> None:
        """创建索引（由 init_database_views_and_indexes 调用）"""
        try:
            db = get_mongo_db()
            collection = db[self.COLLECTION_NAME]
            await collection.create_index([("assertion_id", 1)], unique=True)
            await collection.create_index([("target_agent", 1), ("enabled", 1)])
            await collection.create_index([("severity", 1), ("enabled", 1)])
            await collection.create_index([("source_trace_id", 1)])
            await collection.create_index([("created_at", -1)])
            logger.info(f"✅ {self.COLLECTION_NAME} 索引创建完成")
        except Exception as e:
            logger.warning(f"⚠️ {self.COLLECTION_NAME} 索引创建失败: {e}")


# 全局单例
agent_assertion_service = AgentAssertionService()
