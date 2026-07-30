"""
通用 HITL checkpoint 服务。

从 core/embedded_nanobot/workflows/agent_builder_store.py 抽离 MongoDB checkpoint 模式，
让非 LangGraph 场景（智能助手 ReAct 循环、Skill 生成异步管线）也能用 HITL。

设计要点：
- 不依赖 LangGraph 的 interrupt()（那是进程内内存）
- 通过 MongoDB 持久化"待确认操作"，跨 HTTP 请求暂停/恢复
- 每个待确认操作有唯一 pending_id，前端弹窗/列表用此 ID 跟踪
- 支持 24h 超时自动过期清理

使用场景：
1. 智能助手关键操作（删除配置/触发批量分析）执行前暂停，等待用户确认
2. Skill 生成完成后不自动绑定，等待用户审核代码和测试结果
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

COLLECTION_NAME = "hitl_pending_operations"


class PendingOperation(BaseModel):
    """待确认操作的统一数据模型。"""

    pending_id: str  # 唯一 ID，前端用此 ID 跟踪
    user_id: str
    thread_id: str  # 会话 ID（智能助手 conversation_id / agent_builder thread_id）
    operation_type: str  # "assistant_critical_action" / "skill_binding_review" / ...
    operation_payload: Dict[str, Any] = Field(default_factory=dict)  # 待执行的操作参数
    display_data: Dict[str, Any] = Field(default_factory=dict)  # 前端展示用数据（标题/描述/风险等级）
    status: str = "pending"  # pending / confirmed / rejected / expired
    created_at: str = ""
    decided_at: str = ""
    decided_by: str = ""  # user / system_timeout


class HITLCheckpointService:
    """通用 HITL 检查点服务。

    通过 MongoDB 持久化待确认操作，实现跨 HTTP 请求的暂停/恢复。
    """

    def __init__(self, db: Any):
        self._db = db
        self._collection = db[COLLECTION_NAME]

    async def save_pending(
        self,
        *,
        pending_id: str,
        user_id: str,
        thread_id: str,
        operation_type: str,
        operation_payload: Dict[str, Any],
        display_data: Dict[str, Any],
    ) -> PendingOperation:
        """写入待确认操作，主流程在此暂停。

        Args:
            pending_id: 唯一 ID（调用方生成，如 f"hitl_{uuid.uuid4().hex[:12]}"）
            user_id: 用户 ID
            thread_id: 会话 ID
            operation_type: 操作类型
            operation_payload: 待执行的操作参数（用户确认后用于执行）
            display_data: 前端展示用数据

        Returns:
            写入的 PendingOperation
        """
        now = datetime.now(timezone.utc).isoformat()
        op = PendingOperation(
            pending_id=pending_id,
            user_id=user_id,
            thread_id=thread_id,
            operation_type=operation_type,
            operation_payload=operation_payload,
            display_data=display_data,
            status="pending",
            created_at=now,
        )
        await self._collection.update_one(
            {"pending_id": pending_id},
            {"$set": op.model_dump()},
            upsert=True,
        )
        logger.info(
            "[HITL] 已保存待确认操作: pending_id=%s type=%s thread=%s",
            pending_id, operation_type, thread_id,
        )
        return op

    async def load_pending(self, pending_id: str) -> Optional[PendingOperation]:
        """加载单个待确认操作。

        Returns:
            PendingOperation 或 None（不存在时）
        """
        doc = await self._collection.find_one({"pending_id": pending_id})
        if not doc:
            return None
        # 过滤 _id 字段
        clean = {k: v for k, v in doc.items() if k != "_id"}
        return PendingOperation(**clean)

    async def list_pending(
        self,
        *,
        user_id: str,
        thread_id: Optional[str] = None,
        operation_type: Optional[str] = None,
    ) -> List[PendingOperation]:
        """列出待确认操作（前端展示用）。

        Args:
            user_id: 用户 ID
            thread_id: 可选，限定会话
            operation_type: 可选，限定操作类型

        Returns:
            PendingOperation 列表（按创建时间倒序，最多 20 条）
        """
        query: Dict[str, Any] = {"user_id": user_id, "status": "pending"}
        if thread_id:
            query["thread_id"] = thread_id
        if operation_type:
            query["operation_type"] = operation_type

        cursor = self._collection.find(query).sort("created_at", -1).limit(20)
        docs = await cursor.to_list(length=20)
        result = []
        for doc in docs:
            clean = {k: v for k, v in doc.items() if k != "_id"}
            try:
                result.append(PendingOperation(**clean))
            except Exception as e:
                logger.warning("[HITL] 跳过无法解析的记录: %s", e)
        return result

    async def decide(
        self,
        *,
        pending_id: str,
        decision: str,  # "confirmed" / "rejected"
        decided_by: str = "user",
    ) -> Optional[PendingOperation]:
        """用户确认/拒绝后更新状态。

        Args:
            pending_id: 待确认操作 ID
            decision: "confirmed" 或 "rejected"
            decided_by: 决策者（默认 "user"）

        Returns:
            更新后的 PendingOperation，或 None（不存在或已处理时）
        """
        now = datetime.now(timezone.utc).isoformat()
        result = await self._collection.update_one(
            {"pending_id": pending_id, "status": "pending"},
            {"$set": {
                "status": decision,
                "decided_at": now,
                "decided_by": decided_by,
            }},
        )
        if result.modified_count == 0:
            # 可能是不存在，或状态已不是 pending
            existing = await self.load_pending(pending_id)
            if existing:
                logger.warning(
                    "[HITL] 操作已处理，无法再次决策: pending_id=%s 当前状态=%s",
                    pending_id, existing.status,
                )
            else:
                logger.warning("[HITL] 操作不存在: pending_id=%s", pending_id)
            return None

        logger.info(
            "[HITL] 操作已决策: pending_id=%s decision=%s by=%s",
            pending_id, decision, decided_by,
        )
        return await self.load_pending(pending_id)

    async def expire_stale(self, hours: int = 24) -> int:
        """清理超时未决的操作（默认 24h）。

        Args:
            hours: 超时小时数

        Returns:
            过期的操作数量
        """
        cutoff_dt = datetime.now(timezone.utc).timestamp() - hours * 3600
        cutoff_str = datetime.fromtimestamp(cutoff_dt, tz=timezone.utc).isoformat()
        result = await self._collection.update_many(
            {"status": "pending", "created_at": {"$lt": cutoff_str}},
            {"$set": {"status": "expired", "decided_by": "system_timeout"}},
        )
        if result.modified_count > 0:
            logger.info("[HITL] 清理超时待确认操作: %d 条（超过 %dh）", result.modified_count, hours)
        return result.modified_count


def get_hitl_service(db: Any) -> "HITLCheckpointService":
    """工厂方法（无单例，调用方按需缓存）。

    Args:
        db: MongoDB 数据库句柄

    Returns:
        HITLCheckpointService 实例
    """
    return HITLCheckpointService(db)
