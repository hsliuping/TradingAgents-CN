"""智能助手质量架构（A11）—— 质量埋点（阶段 4，S9）。

每次助手对话回合向 ``assistant_quality_events`` 集合写入一条事件，覆盖：
- 路由命中：route_id / route_priority / route_type / passthrough；
- 质量防线：gate 通过与否、失败检查项、是否降级为 fallback_evidence、
  主路径自动纠错重试信号（unsourced/untraced/fabricated 等）；
- 输出形态：streaming、回复长度、data_refs / evidence 数量、耗时、错误。

设计约束：
- **绝不影响主链路**：落库为 fire-and-forget（create_task），任何异常只记
  debug 日志，不向上抛；
- 仅做离线统计的原始事件留存（不设 TTL），聚合/看板属后续工作（D6：
  先拿真实失败分布，再决定是否投入 LLM 意图分类/裁判）。

本模块不 import service；db 以参数传入（service 持有连接）。
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


class AssistantQualityMetrics:
    """质量事件落库器（进程内单例）。"""

    COLLECTION = "assistant_quality_events"

    def __init__(self) -> None:
        self._indexes_ready = False

    async def create_indexes(self, db=None) -> None:
        """初始化集合索引（应用启动时调用；失败不影响启动）。"""
        if db is None:
            from app.core.database import get_mongo_db
            db = get_mongo_db()
        coll = db[self.COLLECTION]
        await coll.create_index([("created_at", -1)])
        await coll.create_index([("route_id", 1), ("created_at", -1)])
        await coll.create_index([("streaming", 1), ("created_at", -1)])
        self._indexes_ready = True

    def record(self, db=None, **fields: Any) -> None:
        """记录一条质量事件（fire-and-forget，永不抛异常）。

        调用方在事件循环内；若当前无运行中的 loop（如单测同步上下文），
        静默放弃——埋点不可阻断也不可拖慢主链路。
        """
        try:
            import asyncio
            loop = asyncio.get_running_loop()
        except RuntimeError:
            logger.debug("[质量埋点] 无运行中事件循环，丢弃事件: %s", fields.get("route_id"))
            return
        if db is None:
            logger.debug("[质量埋点] 无 db 句柄，丢弃事件: %s", fields.get("route_id"))
            return
        event = {"created_at": datetime.now(timezone.utc), **fields}
        loop.create_task(self._insert(db, event))

    async def _insert(self, db, event: Dict[str, Any]) -> None:
        try:
            if not self._indexes_ready:
                await self.create_indexes(db)
            await db[self.COLLECTION].insert_one(event)
        except Exception as exc:  # 埋点失败绝不影响对话
            logger.debug("[质量埋点] 落库失败（忽略）: %s", exc)

    async def recent(self, db=None, limit: int = 50) -> list:
        """读取最近事件（排障/离线统计辅助）。"""
        if db is None:
            from app.core.database import get_mongo_db
            db = get_mongo_db()
        cursor = db[self.COLLECTION].find({}, {"_id": 0}).sort("created_at", -1).limit(limit)
        return [doc async for doc in cursor]


# 模块级单例（service 两个适配器共用）
quality_metrics = AssistantQualityMetrics()
