"""Authenticated WebSocket delivery for non-core notifications and task progress."""

from __future__ import annotations

import asyncio
from datetime import datetime
import json
import logging
from typing import Dict, Iterable, Set

from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect

from app.routers.auth_db import get_current_user
from app.services.auth_service import AuthService


router = APIRouter()
logger = logging.getLogger("webapi.websocket")
WS_PROTOCOL = "alphaguard.notifications.v1"
TASK_WS_PROTOCOL = "alphaguard.tasks.v1"
WS_AUTH_PREFIX = "auth."


def _websocket_token(websocket: WebSocket, required_protocol: str) -> str | None:
    """Read JWT from a subprotocol and keep it out of URLs and logs."""
    offered = websocket.headers.get("sec-websocket-protocol", "")
    protocols = [item.strip() for item in offered.split(",") if item.strip()]
    if required_protocol not in protocols:
        return None
    encoded = next(
        (
            item[len(WS_AUTH_PREFIX) :]
            for item in protocols
            if item.startswith(WS_AUTH_PREFIX)
        ),
        None,
    )
    return encoded or None


def _notification_ws_token(websocket: WebSocket) -> str | None:
    return _websocket_token(websocket, WS_PROTOCOL)


async def _authorized_user(token_data):
    """Resolve an active user while preserving the JWT subject for audit."""
    from app.services.user_service import user_service

    user = await user_service.get_user_by_username(token_data.sub)
    if user is None or not user.is_active:
        return None
    return user


class ConnectionManager:
    """Track notification sockets by JWT subject and database user-id alias."""

    def __init__(self):
        self.active_connections: Dict[str, Set[WebSocket]] = {}
        self.connection_users: Dict[WebSocket, str] = {}
        self.connection_keys: Dict[WebSocket, Set[str]] = {}
        self._lock = asyncio.Lock()
        self.last_success_at: datetime | None = None
        self.last_disconnect_at: datetime | None = None
        self.auth_failure_count = 0
        self.connection_count = 0
        self.last_error_code: str | None = None

    async def connect(
        self,
        websocket: WebSocket,
        user_id: str,
        *,
        aliases: Iterable[str] = (),
        subprotocol: str = WS_PROTOCOL,
    ) -> None:
        await websocket.accept(subprotocol=subprotocol)
        async with self._lock:
            keys = {user_id, *(str(item) for item in aliases if item)}
            for key in keys:
                self.active_connections.setdefault(key, set()).add(websocket)
            self.connection_users[websocket] = user_id
            self.connection_keys[websocket] = keys
            self.connection_count += 1
            self.last_success_at = datetime.utcnow()
            self.last_error_code = None
            logger.info(
                "通知WebSocket连接成功: active_connections=%s",
                len(self.connection_users),
            )

    def _drop_connection_locked(self, websocket: WebSocket) -> None:
        for key in self.connection_keys.pop(websocket, set()):
            connections = self.active_connections.get(key)
            if connections is None:
                continue
            connections.discard(websocket)
            if not connections:
                del self.active_connections[key]
        self.connection_users.pop(websocket, None)

    async def disconnect(self, websocket: WebSocket, user_id: str) -> None:
        del user_id  # The socket identity is authoritative and avoids alias leaks.
        async with self._lock:
            self._drop_connection_locked(websocket)
            self.last_disconnect_at = datetime.utcnow()
            logger.info(
                "通知WebSocket连接断开: active_connections=%s",
                len(self.connection_users),
            )

    async def send_personal_message(self, message: dict, user_id: str) -> None:
        async with self._lock:
            connections = list(self.active_connections.get(user_id, set()))
        if not connections:
            logger.debug("通知WebSocket当前没有目标用户连接")
            return

        message_json = json.dumps(message, ensure_ascii=False)
        dead_connections = []
        for connection in connections:
            try:
                await connection.send_text(message_json)
                logger.debug("通知WebSocket消息发送成功")
            except Exception as exc:
                self.last_error_code = "SEND_FAILED"
                logger.warning(
                    "通知WebSocket发送失败: error_type=%s",
                    type(exc).__name__,
                )
                dead_connections.append(connection)
        if dead_connections:
            async with self._lock:
                for connection in dead_connections:
                    self._drop_connection_locked(connection)

    async def broadcast(self, message: dict) -> None:
        async with self._lock:
            all_connections = set(self.connection_users)
        message_json = json.dumps(message, ensure_ascii=False)
        for connection in all_connections:
            try:
                await connection.send_text(message_json)
            except Exception as exc:
                self.last_error_code = "BROADCAST_FAILED"
                logger.warning(
                    "通知WebSocket广播失败: error_type=%s",
                    type(exc).__name__,
                )

    def get_stats(self) -> dict:
        return {
            "connection_status": "CONNECTED" if self.connection_users else "IDLE",
            "total_users": len(set(self.connection_users.values())),
            "total_connections": len(self.connection_users),
            "last_success_at": self.last_success_at,
            "last_disconnect_at": self.last_disconnect_at,
            "connection_count": self.connection_count,
            "auth_failure_count": self.auth_failure_count,
            "last_error_code": self.last_error_code,
            "degraded": self.last_error_code is not None,
        }


manager = ConnectionManager()


async def _authenticate_websocket(
    websocket: WebSocket,
    *,
    protocol: str,
):
    token = _websocket_token(websocket, protocol)
    token_data = AuthService.verify_token(token)
    if token_data is None:
        manager.auth_failure_count += 1
        manager.last_error_code = "UNAUTHENTICATED"
        await websocket.close(code=4401, reason="UNAUTHENTICATED")
        return None
    try:
        user = await _authorized_user(token_data)
    except Exception as exc:
        manager.last_error_code = "SERVICE_UNAVAILABLE"
        logger.warning(
            "WebSocket用户状态检查失败: error_type=%s",
            type(exc).__name__,
        )
        await websocket.close(code=1013, reason="SERVICE_UNAVAILABLE")
        return None
    if user is None:
        manager.auth_failure_count += 1
        manager.last_error_code = "FORBIDDEN"
        await websocket.close(code=4403, reason="FORBIDDEN")
        return None
    return token_data, user


@router.websocket("/ws/notifications")
async def websocket_notifications_endpoint(websocket: WebSocket):
    """Deliver notifications; JWT travels only in Sec-WebSocket-Protocol."""
    authenticated = await _authenticate_websocket(websocket, protocol=WS_PROTOCOL)
    if authenticated is None:
        return
    token_data, user = authenticated
    user_id = token_data.sub
    await manager.connect(websocket, user_id, aliases=(str(user.id),))
    await websocket.send_json(
        {
            "type": "connected",
            "data": {
                "user_id": user_id,
                "timestamp": datetime.utcnow().isoformat(),
                "message": "WebSocket 连接成功",
            },
        }
    )

    async def send_heartbeat() -> None:
        while True:
            try:
                await asyncio.sleep(30)
                await websocket.send_json(
                    {
                        "type": "heartbeat",
                        "data": {"timestamp": datetime.utcnow().isoformat()},
                    }
                )
            except Exception as exc:
                manager.last_error_code = "HEARTBEAT_FAILED"
                logger.debug(
                    "通知WebSocket心跳失败: error_type=%s",
                    type(exc).__name__,
                )
                break

    heartbeat_task = asyncio.create_task(send_heartbeat())
    try:
        while True:
            try:
                await websocket.receive_text()
                logger.debug("通知WebSocket收到客户端保活消息")
            except WebSocketDisconnect:
                logger.info("通知WebSocket客户端主动断开")
                break
            except Exception as exc:
                manager.last_error_code = "RECEIVE_FAILED"
                logger.error(
                    "通知WebSocket接收失败: error_type=%s",
                    type(exc).__name__,
                )
                break
    finally:
        heartbeat_task.cancel()
        try:
            await heartbeat_task
        except asyncio.CancelledError:
            pass
        await manager.disconnect(websocket, user_id)


@router.websocket("/ws/tasks/{task_id}")
async def websocket_task_progress_endpoint(websocket: WebSocket, task_id: str):
    """Keep the legacy task-progress stream authenticated without URL tokens."""
    authenticated = await _authenticate_websocket(
        websocket, protocol=TASK_WS_PROTOCOL
    )
    if authenticated is None:
        return
    token_data, _user = authenticated
    await websocket.accept(subprotocol=TASK_WS_PROTOCOL)
    logger.info("任务进度WebSocket连接成功: task=%s", task_id)
    await websocket.send_json(
        {
            "type": "connected",
            "data": {
                "task_id": task_id,
                "user_id": token_data.sub,
                "timestamp": datetime.utcnow().isoformat(),
                "message": "已连接任务进度流",
            },
        }
    )
    try:
        while True:
            try:
                await websocket.receive_text()
                logger.debug(
                    "任务进度WebSocket收到客户端保活消息: task=%s",
                    task_id,
                )
            except WebSocketDisconnect:
                logger.info("任务进度WebSocket客户端主动断开: task=%s", task_id)
                break
            except Exception as exc:
                logger.error(
                    "任务进度WebSocket接收失败: task=%s error_type=%s",
                    task_id,
                    type(exc).__name__,
                )
                break
    finally:
        logger.info("任务进度WebSocket连接断开: task=%s", task_id)


@router.get("/ws/stats")
async def get_websocket_stats(current_user: dict = Depends(get_current_user)):
    """Return aggregate connection health without users, URLs or tokens."""
    del current_user
    return manager.get_stats()


async def send_notification_via_websocket(user_id: str, notification: dict):
    await manager.send_personal_message(
        {"type": "notification", "data": notification}, user_id
    )


async def send_task_progress_via_websocket(task_id: str, progress_data: dict):
    del task_id
    await manager.broadcast({"type": "progress", "data": progress_data})
