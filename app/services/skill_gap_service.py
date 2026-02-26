"""
Skill 缺口管理服务

负责：
- 将工具缺口报告持久化到 MongoDB skill_gap_reports 集合
- 推送 WebSocket + 通知中心通知
- 提供列表 / 详情 / 忽略 / 解决 CRUD
"""
import logging
import uuid
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from app.core.database import get_mongo_db
from app.models.notification import NotificationCreate
from app.utils.timezone import now_tz

logger = logging.getLogger("skill_gap_service")

COLLECTION = "skill_gap_reports"


class SkillGapService:
    """Skill 缺口管理服务"""

    # ------------------------------------------------------------------
    # 写操作
    # ------------------------------------------------------------------

    async def create_report(
        self,
        gap_type: str,
        tool_name: str,
        agent_id: str,
        error: str = "",
        context: Optional[Dict[str, Any]] = None,
        user_id: str = "admin",
    ) -> str:
        """创建缺口报告并推送通知"""
        db = get_mongo_db()
        report_id = f"gap_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6]}"
        now = now_tz()

        # 从 context 中提取工作流/任务信息
        workflow_id = context.get("workflow_id", "") if context else ""
        workflow_name = context.get("workflow_name", "") if context else ""
        task_id = context.get("task_id", "") if context else ""
        node_id = context.get("node_id", "") if context else ""

        doc = {
            "report_id": report_id,
            "user_id": user_id,
            "status": "pending",
            "source": {
                "agent_id": agent_id,
                "agent_name": context.get("agent_name", agent_id) if context else agent_id,
                "workflow_id": workflow_id,
                "workflow_name": workflow_name,
                "task_id": task_id,
                "node_id": node_id,
            },
            "gap": {
                "type": gap_type,
                "tool_name": tool_name,
                "error_message": error,
                "tool_call_args": context.get("tool_call_args", {}) if context else {},
                "context_summary": context.get("context_summary", "") if context else "",
            },
            "analysis": None,
            "created_at": now,
            "updated_at": now,
            "resolved_at": None,
            "expires_at": now + timedelta(days=7),
        }

        await db[COLLECTION].insert_one(doc)
        logger.info(f"[SkillGapService] 缺口报告已保存: {report_id}")

        # 推送通知
        await self._send_notification(user_id, report_id, tool_name, agent_id, gap_type)
        return report_id

    async def _send_notification(
        self, user_id: str, report_id: str, tool_name: str, agent_id: str, gap_type: str
    ) -> None:
        """通过 NotificationsService 推送通知"""
        try:
            from app.services.notifications_service import get_notifications_service
            svc = get_notifications_service()
            gap_label = "工具未找到" if gap_type == "tool_not_found" else "工具执行失败"
            await svc.create_and_publish(
                payload=NotificationCreate(
                    user_id=user_id,
                    type="alert",
                    title=f"🔧 发现工具缺口 [{gap_label}]",
                    content=f"Agent {agent_id} 需要工具 `{tool_name}`，但该工具{gap_label}。点击查看详情并决定是否创建 Skill。",
                    link=f"/workflow/skill-gaps/{report_id}",
                    source="skill_gap_detector",
                    severity="warning",
                    metadata={"report_id": report_id, "tool_name": tool_name},
                )
            )
        except Exception as e:
            logger.warning(f"[SkillGapService] 推送通知失败（已忽略）: {e}")

    # ------------------------------------------------------------------
    # 读操作
    # ------------------------------------------------------------------

    async def list_gaps(
        self, user_id: str, status: Optional[str] = None, page: int = 1, page_size: int = 20
    ) -> Dict[str, Any]:
        db = get_mongo_db()
        query: Dict[str, Any] = {"user_id": user_id}
        if status:
            query["status"] = status
        total = await db[COLLECTION].count_documents(query)
        items = []
        async for doc in (
            db[COLLECTION].find(query).sort("created_at", -1)
            .skip((page - 1) * page_size).limit(page_size)
        ):
            doc["_id"] = str(doc["_id"])
            items.append(doc)
        return {"items": items, "total": total, "page": page, "page_size": page_size}

    async def get_gap(self, report_id: str) -> Optional[Dict[str, Any]]:
        db = get_mongo_db()
        doc = await db[COLLECTION].find_one({"report_id": report_id})
        if doc:
            doc["_id"] = str(doc["_id"])
        return doc

    async def dismiss_gap(self, report_id: str, user_id: str) -> bool:
        db = get_mongo_db()
        now = now_tz()
        res = await db[COLLECTION].find_one_and_update(
            {"report_id": report_id, "user_id": user_id},
            {"$set": {"status": "dismissed", "updated_at": now}},
        )
        if res:
            # 通知检测器记录忽略
            tool_name = res.get("gap", {}).get("tool_name", "")
            if tool_name:
                from core.tools.external.skill_gap_detector import SkillGapDetector
                SkillGapDetector.mark_dismissed(tool_name)
        return res is not None

    async def resolve_gap(self, report_id: str, user_id: str, skill_id: str = "") -> bool:
        db = get_mongo_db()
        now = now_tz()
        update = {"$set": {"status": "resolved", "updated_at": now, "resolved_at": now}}
        if skill_id:
            update["$set"]["analysis.resolved_skill_id"] = skill_id
        res = await db[COLLECTION].update_one(
            {"report_id": report_id, "user_id": user_id}, update
        )
        return res.modified_count > 0

    async def get_stats(self, user_id: str) -> Dict[str, Any]:
        db = get_mongo_db()
        pipeline = [
            {"$match": {"user_id": user_id}},
            {"$group": {"_id": "$status", "count": {"$sum": 1}}},
        ]
        status_counts: Dict[str, int] = {}
        async for doc in db[COLLECTION].aggregate(pipeline):
            status_counts[doc["_id"]] = doc["count"]

        pipeline2 = [
            {"$match": {"user_id": user_id}},
            {"$group": {"_id": "$gap.type", "count": {"$sum": 1}}},
        ]
        type_counts: Dict[str, int] = {}
        async for doc in db[COLLECTION].aggregate(pipeline2):
            type_counts[doc["_id"]] = doc["count"]

        return {
            "by_status": status_counts,
            "by_type": type_counts,
            "total": sum(status_counts.values()),
        }


_skill_gap_service: Optional[SkillGapService] = None


def get_skill_gap_service() -> SkillGapService:
    global _skill_gap_service
    if _skill_gap_service is None:
        _skill_gap_service = SkillGapService()
    return _skill_gap_service

