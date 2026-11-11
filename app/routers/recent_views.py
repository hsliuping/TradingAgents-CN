"""
个股浏览足迹（最近研究）API

记录用户最近打开过的个股页，供研究台「最近研究」按真实浏览时间排序。
按 user_id 隔离（跨浏览器/设备跟随账号），前端 localStorage 仅作离线兜底。
"""

import logging
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel

from app.core.database import get_mongo_db
from app.core.response import ok
from app.routers.auth_db import get_current_user

logger = logging.getLogger("webapi")

router = APIRouter(prefix="/recent-views", tags=["浏览足迹"], redirect_slashes=False)

COLLECTION = "recent_views"
MAX_KEEP = 50  # 每用户最多保留条数，防止集合膨胀


class RecentViewRequest(BaseModel):
    code: str
    name: Optional[str] = ""


def _now_iso() -> str:
    return datetime.utcnow().isoformat()


@router.post("", response_model=dict)
async def record_recent_view(
    request: RecentViewRequest,
    current_user: dict = Depends(get_current_user),
):
    """记录一次个股访问（同代码 upsert 置顶）"""
    try:
        code = (request.code or "").strip()
        if not code:
            return ok({"recorded": False})
        db = get_mongo_db()
        await db[COLLECTION].update_one(
            {"user_id": current_user["id"], "code": code},
            {"$set": {"name": (request.name or "").strip(), "viewed_at": _now_iso()}},
            upsert=True,
        )
        # 只保留最近 MAX_KEEP 条
        cursor = (
            db[COLLECTION]
            .find({"user_id": current_user["id"]}, {"_id": 1})
            .sort("viewed_at", -1)
            .skip(MAX_KEEP)
        )
        stale_ids = [doc["_id"] async for doc in cursor]
        if stale_ids:
            await db[COLLECTION].delete_many({"_id": {"$in": stale_ids}})
        return ok({"recorded": True})
    except Exception as e:
        logger.error(f"记录浏览足迹失败: {e}", exc_info=True)
        return ok({"recorded": False})


@router.get("", response_model=dict)
async def list_recent_views(
    limit: int = Query(6, ge=1, le=20),
    current_user: dict = Depends(get_current_user),
):
    """最近浏览的个股（按浏览时间倒序）"""
    try:
        db = get_mongo_db()
        cursor = (
            db[COLLECTION]
            .find({"user_id": current_user["id"]}, {"_id": 0, "code": 1, "name": 1, "viewed_at": 1})
            .sort("viewed_at", -1)
            .limit(limit)
        )
        items = [
            {"code": d.get("code"), "name": d.get("name") or "", "viewed_at": d.get("viewed_at")}
            async for d in cursor
        ]
        return ok(items)
    except Exception as e:
        logger.error(f"读取浏览足迹失败: {e}", exc_info=True)
        return ok([])
