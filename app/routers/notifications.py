"""
通知 REST API
"""
import logging
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query

from app.routers.auth_db import get_current_user
from app.core.response import ok
from app.core.database import get_redis_client
from app.services.notifications_service import get_notifications_service

router = APIRouter()
logger = logging.getLogger("webapi.notifications")


@router.get("/notifications")
async def list_notifications(
    status: Optional[str] = Query(None, description="状态: unread|read|all"),
    type: Optional[str] = Query(None, description="类型: analysis|alert|system"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    user: dict = Depends(get_current_user)
):
    svc = get_notifications_service()
    s = status if status in ("read","unread") else None
    t = type if type in ("analysis","alert","system") else None
    try:
        data = await svc.list(
            user_id=user["id"], status=s, ntype=t, page=page, page_size=page_size
        )
    except Exception as exc:
        logger.warning(
            "通知列表服务降级: error_type=%s", exc.__class__.__name__
        )
        return ok(
            data={
                "items": [],
                "total": 0,
                "page": page,
                "page_size": page_size,
                "service_status": "DEGRADED",
                "error_code": "NOTIFICATION_SERVICE_UNAVAILABLE",
            },
            message="通知服务暂不可用，不影响AlphaGuard核心功能",
        )
    payload = data.model_dump()
    payload.update({"service_status": "READY", "error_code": None})
    return ok(data=payload, message="ok")


@router.get("/notifications/unread_count")
async def get_unread_count(user: dict = Depends(get_current_user)):
    svc = get_notifications_service()
    try:
        cnt = await svc.unread_count(user_id=user["id"])
    except Exception as exc:
        logger.warning(
            "通知未读数服务降级: error_type=%s", exc.__class__.__name__
        )
        return ok(
            data={
                "count": 0,
                "service_status": "DEGRADED",
                "error_code": "NOTIFICATION_SERVICE_UNAVAILABLE",
            },
            message="通知服务暂不可用，不影响AlphaGuard核心功能",
        )
    return ok(
        data={"count": cnt, "service_status": "READY", "error_code": None}
    )


@router.post("/notifications/{notif_id}/read")
async def mark_read(notif_id: str, user: dict = Depends(get_current_user)):
    svc = get_notifications_service()
    ok_flag = await svc.mark_read(user_id=user["id"], notif_id=notif_id)
    if not ok_flag:
        raise HTTPException(status_code=404, detail="Notification not found")
    return ok()


@router.post("/notifications/read_all")
async def mark_all_read(user: dict = Depends(get_current_user)):
    svc = get_notifications_service()
    n = await svc.mark_all_read(user_id=user["id"])
    return ok(data={"updated": n})


@router.get("/notifications/debug/redis_pool")
async def debug_redis_pool(user: dict = Depends(get_current_user)):
    """调试端点：查看 Redis 连接池状态"""
    try:
        r = get_redis_client()
        pool = r.connection_pool

        # 获取连接池信息
        pool_info = {
            "max_connections": pool.max_connections,
            "connection_class": str(pool.connection_class),
            "available_connections": len(pool._available_connections) if hasattr(pool, '_available_connections') else "N/A",
            "in_use_connections": len(pool._in_use_connections) if hasattr(pool, '_in_use_connections') else "N/A",
        }

        # 获取 Redis 服务器信息
        info = await r.info("clients")
        redis_info = {
            "connected_clients": info.get("connected_clients", "N/A"),
            "client_recent_max_input_buffer": info.get("client_recent_max_input_buffer", "N/A"),
            "client_recent_max_output_buffer": info.get("client_recent_max_output_buffer", "N/A"),
            "blocked_clients": info.get("blocked_clients", "N/A"),
        }

        # 🔥 新增：获取 PubSub 频道信息
        try:
            pubsub_info = await r.execute_command("PUBSUB", "CHANNELS", "notifications:*")
            pubsub_channels = {
                "active_channels": len(pubsub_info) if pubsub_info else 0,
                "channels": pubsub_info if pubsub_info else []
            }
        except Exception as e:
            logger.warning(f"获取 PubSub 频道信息失败: {e}")
            pubsub_channels = {"error": str(e)}

        return ok(data={
            "pool": pool_info,
            "redis_server": redis_info,
            "pubsub": pubsub_channels
        })
    except Exception as e:
        logger.error(f"获取 Redis 连接池信息失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
