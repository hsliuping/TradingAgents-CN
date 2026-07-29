"""Agent 执行轨迹存储服务

同步 API（save_trace_sync / update_validation_sync）供同步 agent execute 上下文使用；
异步 API 供后台扫描/查询使用（P2 反思机制入口）。

非阻塞原则：所有方法内部 try/except，异常不外抛，不影响 agent 执行。
"""

import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from app.core.database import get_mongo_db, get_mongo_db_sync
from app.models.execution_trace import AgentExecutionTrace
from app.utils.timezone import now_tz

logger = logging.getLogger("app.services.execution_trace_service")


class ExecutionTraceService:
    """执行轨迹存储服务"""

    COLLECTION_NAME = "agent_execution_traces"

    # ==================== 同步 API（agent execute 上下文） ====================

    def save_trace_sync(self, trace: AgentExecutionTrace) -> bool:
        """同步写入轨迹（供 ManagerAgent.execute 调用）

        非阻塞：任何异常都被捕获并记录，不影响 agent 执行。
        """
        try:
            db = get_mongo_db_sync()
            collection = db[self.COLLECTION_NAME]
            # 🔍 INFO 日志：确认 save_trace_sync 被调用及连接的数据库（排查端口问题）
            db_name = db.name
            from app.core.config import settings
            mongo_port = settings.MONGODB_PORT
            logger.info(
                f"📋 [轨迹写入] save_trace_sync 调用: agent={trace.agent_id}, "
                f"trace_id={trace.trace_id}, db={db_name}, MONGODB_PORT={mongo_port}"
            )
            doc = trace.model_dump()
            # datetime 字段保持原生 datetime 类型，PyMongo 会自动转为 BSON
            collection.insert_one(doc)
            logger.info(
                f"✅ [轨迹写入] 成功: trace_id={trace.trace_id}, agent={trace.agent_id}, "
                f"db={db_name}, port={mongo_port}"
            )
            return True
        except Exception as e:
            logger.warning(f"⚠️ 执行轨迹保存失败（不影响 agent 执行）: {e}")
            return False

    def update_validation_sync(
        self,
        trace_id: str,
        validation_status: str,
        validation_error: Optional[str] = None,
        validation_details: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """同步回填校验结果（供子类 execute 调用）"""
        try:
            db = get_mongo_db_sync()
            collection = db[self.COLLECTION_NAME]
            update_doc: Dict[str, Any] = {
                "validation.validation_status": validation_status,
            }
            if validation_error is not None:
                update_doc["validation.validation_error"] = validation_error
            if validation_details is not None:
                update_doc["validation.validation_details"] = validation_details

            collection.update_one({"trace_id": trace_id}, {"$set": update_doc})
            logger.debug(f"✅ 校验结果已回填: trace_id={trace_id}, status={validation_status}")
            return True
        except Exception as e:
            logger.warning(f"⚠️ 校验结果回填失败（不影响 agent 执行）: {e}")
            return False

    @staticmethod
    def _build_query(
        agent_id: Optional[str] = None,
        workflow_id: Optional[str] = None,
        task_id: Optional[str] = None,
        validation_status: Optional[str] = None,
        success: Optional[bool] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        """构建查询条件（同步/异步/计数复用）"""
        query: Dict[str, Any] = {}
        if agent_id:
            query["agent_id"] = agent_id
        if workflow_id:
            query["workflow_id"] = workflow_id
        if task_id:
            query["task_id"] = task_id
        if validation_status:
            query["validation.validation_status"] = validation_status
        if success is not None:
            query["success"] = success
        if start_date or end_date:
            query["started_at"] = {}
            if start_date:
                query["started_at"]["$gte"] = start_date
            if end_date:
                query["started_at"]["$lte"] = end_date
        return query

    def get_traces_sync(
        self,
        agent_id: Optional[str] = None,
        workflow_id: Optional[str] = None,
        task_id: Optional[str] = None,
        validation_status: Optional[str] = None,
        success: Optional[bool] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        skip: int = 0,
        limit: int = 100,
    ) -> List[AgentExecutionTrace]:
        """同步查询轨迹（供独立脚本/回归测试使用，无需 async 上下文）。"""
        try:
            db = get_mongo_db_sync()
            collection = db[self.COLLECTION_NAME]
            query = self._build_query(
                agent_id=agent_id, workflow_id=workflow_id, task_id=task_id,
                validation_status=validation_status, success=success,
                start_date=start_date, end_date=end_date,
            )
            cursor = collection.find(query).sort("started_at", -1).skip(skip).limit(limit)
            traces: List[AgentExecutionTrace] = []
            for doc in cursor:
                doc.pop("_id", None)
                try:
                    traces.append(AgentExecutionTrace(**doc))
                except Exception as parse_exc:
                    logger.warning(f"⚠️ 轨迹解析失败（跳过）: {parse_exc}")
            return traces
        except Exception as e:
            logger.error(f"❌ 同步查询轨迹失败: {e}")
            return []

    def get_failure_patterns_sync(
        self,
        agent_id: Optional[str] = None,
        days: int = 7,
        limit: int = 100,
    ) -> List[AgentExecutionTrace]:
        """同步获取失败模式（供断言生成器脚本使用）。

        返回 validation_status="failed" 的轨迹。
        """
        end_date = now_tz()
        start_date = end_date - timedelta(days=days)
        return self.get_traces_sync(
            agent_id=agent_id,
            validation_status="failed",
            start_date=start_date,
            end_date=end_date,
            limit=limit,
        )

    # ==================== 异步 API（后台扫描/查询/P2 反思） ====================

    async def get_traces(
        self,
        agent_id: Optional[str] = None,
        workflow_id: Optional[str] = None,
        task_id: Optional[str] = None,
        validation_status: Optional[str] = None,
        success: Optional[bool] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        skip: int = 0,
        limit: int = 100,
    ) -> List[AgentExecutionTrace]:
        """查询轨迹（前端查看 / P2 反思扫描用）"""
        try:
            db = get_mongo_db()
            collection = db[self.COLLECTION_NAME]
            query = self._build_query(
                agent_id=agent_id, workflow_id=workflow_id, task_id=task_id,
                validation_status=validation_status, success=success,
                start_date=start_date, end_date=end_date,
            )
            cursor = collection.find(query).sort("started_at", -1).skip(skip).limit(limit)
            traces = []
            async for doc in cursor:
                doc.pop("_id", None)
                traces.append(AgentExecutionTrace(**doc))
            return traces
        except Exception as e:
            logger.error(f"❌ 查询轨迹失败: {e}")
            return []

    async def get_trace_by_id(self, trace_id: str) -> Optional[AgentExecutionTrace]:
        """按 trace_id 查单条详情（含全文，供前端详情页）"""
        try:
            db = get_mongo_db()
            collection = db[self.COLLECTION_NAME]
            doc = await collection.find_one({"trace_id": trace_id})
            if not doc:
                return None
            doc.pop("_id", None)
            return AgentExecutionTrace(**doc)
        except Exception as e:
            logger.error(f"❌ 查询单条轨迹失败: {e}")
            return None

    async def count_traces(
        self,
        agent_id: Optional[str] = None,
        workflow_id: Optional[str] = None,
        task_id: Optional[str] = None,
        validation_status: Optional[str] = None,
        success: Optional[bool] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> int:
        """统计轨迹总数（分页用）"""
        try:
            db = get_mongo_db()
            collection = db[self.COLLECTION_NAME]
            query = self._build_query(
                agent_id=agent_id, workflow_id=workflow_id, task_id=task_id,
                validation_status=validation_status, success=success,
                start_date=start_date, end_date=end_date,
            )
            return await collection.count_documents(query)
        except Exception as e:
            logger.error(f"❌ 统计轨迹失败: {e}")
            return 0

    async def get_failure_patterns(
        self,
        agent_id: Optional[str] = None,
        days: int = 7,
        limit: int = 100,
    ) -> List[AgentExecutionTrace]:
        """获取失败模式（P2 反思机制入口）

        返回 validation_status="failed" 的轨迹。
        """
        end_date = now_tz()
        start_date = end_date - timedelta(days=days)
        return await self.get_traces(
            agent_id=agent_id,
            validation_status="failed",
            start_date=start_date,
            end_date=end_date,
            limit=limit,
        )

    async def delete_old_traces(self, days: int = 90) -> int:
        """清理旧轨迹"""
        try:
            db = get_mongo_db()
            collection = db[self.COLLECTION_NAME]
            cutoff = now_tz() - timedelta(days=days)
            result = await collection.delete_many({"started_at": {"$lt": cutoff}})
            logger.info(f"✅ 清理 {result.deleted_count} 条旧执行轨迹（>{days}天）")
            return result.deleted_count
        except Exception as e:
            logger.error(f"❌ 清理旧轨迹失败: {e}")
            return 0

    # ==================== 索引初始化 ====================

    async def create_indexes(self) -> None:
        """创建索引（由 init_database_views_and_indexes 调用）"""
        try:
            db = get_mongo_db()
            collection = db[self.COLLECTION_NAME]
            await collection.create_index([("trace_id", 1)], unique=True)
            await collection.create_index([("agent_id", 1), ("started_at", -1)])
            await collection.create_index([("workflow_id", 1), ("started_at", -1)])
            await collection.create_index([("execution_id", 1), ("started_at", -1)])
            # 前端按 task_id 查询（任务中心跳转核心索引）
            await collection.create_index([("task_id", 1), ("started_at", -1)])
            # P2 反思扫描：按校验失败/执行失败检索
            await collection.create_index([("validation.validation_status", 1), ("started_at", -1)])
            await collection.create_index([("success", 1), ("started_at", -1)])
            await collection.create_index([("started_at", -1)])  # 排序查询用
            # TTL 清理：90 天自动过期（全文存储后避免数据膨胀）
            await collection.create_index([("started_at", 1)], expireAfterSeconds=90 * 24 * 3600)
            logger.info(f"✅ {self.COLLECTION_NAME} 索引创建完成")
        except Exception as e:
            logger.warning(f"⚠️ {self.COLLECTION_NAME} 索引创建失败: {e}")


# 全局单例
execution_trace_service = ExecutionTraceService()
