"""
WebSocket 通知系统
替代 SSE + Redis PubSub，解决连接泄漏问题
"""
import asyncio
import base64
import json
import logging
from typing import Dict, Optional, Set
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query, HTTPException
from datetime import datetime

from app.services.auth_service import AuthService
from app.services.user_service import user_service

router = APIRouter()
logger = logging.getLogger("webapi.websocket")


async def _authenticate_websocket(websocket: WebSocket, token: Optional[str]) -> Optional[str]:
    """
    统一 WebSocket 认证（支持 JWT 和京东云 Basic Auth）

    认证优先级：
    1. JWT token（query 参数）— 非京东云模式的主路径
    2. 京东云 Basic Auth（Authorization 头）— 京东云网关注入，WebSocket 握手时携带

    Args:
        websocket: WebSocket 连接对象
        token: query 参数中的 JWT token（可为空）

    Returns:
        认证成功返回 user_id（字符串），失败返回 None
    """
    # 方式 1: JWT token 认证
    if token:
        token_data = AuthService.verify_token(token)
        if token_data:
            user = await user_service.get_user_by_username(token_data.sub)
            if user:
                return str(user.id)
        logger.warning("❌ [WS] JWT token 验证失败，尝试京东云 Basic Auth")

    # 方式 2: 京东云 Basic Auth 认证（WebSocket 握手时由京东云网关注入 Authorization 头）
    from app.core.jdyun import (
        is_jdyun_mode,
        is_from_jdyun_gateway,
        verify_jdyun_basic_auth,
    )

    if not is_jdyun_mode():
        return None

    authorization = websocket.headers.get("authorization") or websocket.headers.get("Authorization")
    if not authorization or not authorization.lower().startswith("basic "):
        logger.debug("ℹ️ [WS] 京东云模式下未携带 Basic Auth 头")
        return None

    # IP 白名单校验（第二道防线）
    client_ip = websocket.client.host if websocket.client else ""
    if not is_from_jdyun_gateway(client_ip):
        logger.warning(f"❌ [WS] 京东云 Basic Auth IP 不在网关白名单: {client_ip}")
        return None

    try:
        encoded = authorization.split(" ", 1)[1]
        decoded = base64.b64decode(encoded, validate=True).decode("utf-8")
        if ":" not in decoded:
            logger.warning("❌ [WS] 京东云 Basic Auth 格式错误: 缺少分隔符")
            return None
        username, basic_token = decoded.split(":", 1)

        # 分级校验：老用户免令牌，新用户严格校验
        is_existing = user_service.is_existing_jdyun_user(username)
        if is_existing:
            auth_passed = True
            logger.info(f"✅ [WS] 京东云老用户免令牌校验: user={username}")
        else:
            auth_passed = verify_jdyun_basic_auth(username, basic_token)
            if not auth_passed:
                logger.warning(f"❌ [WS] 京东云新用户首次认证失败: user={username}")

        if not auth_passed:
            return None

        # 获取或创建用户
        jdyun_user = await user_service.get_or_create_jdyun_user(
            jdyun_username=username,
            is_admin=True,
        )
        if jdyun_user:
            logger.info(f"✅ [WS] 京东云 Basic Auth 认证成功: user={username} db_id={jdyun_user.id}")
            return str(jdyun_user.id)
        logger.error(f"❌ [WS] 京东云用户建档失败: {username}")
        return None
    except Exception as e:
        logger.warning(f"❌ [WS] 京东云 Basic Auth 解析失败: {e}", exc_info=True)
        return None

# 🔥 全局 WebSocket 连接管理器
class ConnectionManager:
    """WebSocket 连接管理器"""
    
    def __init__(self):
        # user_id -> Set[WebSocket]
        self.active_connections: Dict[str, Set[WebSocket]] = {}
        self._lock = asyncio.Lock()
    
    async def connect(self, websocket: WebSocket, user_id: str):
        """连接 WebSocket"""
        await websocket.accept()
        
        async with self._lock:
            if user_id not in self.active_connections:
                self.active_connections[user_id] = set()
            self.active_connections[user_id].add(websocket)
            
            total_connections = sum(len(conns) for conns in self.active_connections.values())
            logger.info(f"✅ [WS] 新连接: user={user_id}, "
                       f"该用户连接数={len(self.active_connections[user_id])}, "
                       f"总连接数={total_connections}")
    
    async def disconnect(self, websocket: WebSocket, user_id: str):
        """断开 WebSocket"""
        async with self._lock:
            if user_id in self.active_connections:
                self.active_connections[user_id].discard(websocket)
                if not self.active_connections[user_id]:
                    del self.active_connections[user_id]
            
            total_connections = sum(len(conns) for conns in self.active_connections.values())
            logger.info(f"🔌 [WS] 断开连接: user={user_id}, 总连接数={total_connections}")
    
    async def send_personal_message(self, message: dict, user_id: str):
        """发送消息给指定用户的所有连接"""
        async with self._lock:
            if user_id not in self.active_connections:
                logger.debug(f"⚠️ [WS] 用户 {user_id} 没有活跃连接")
                return
            
            connections = list(self.active_connections[user_id])
        
        # 在锁外发送消息，避免阻塞
        message_json = json.dumps(message, ensure_ascii=False)
        dead_connections = []
        
        for connection in connections:
            try:
                await connection.send_text(message_json)
                logger.debug(f"📤 [WS] 发送消息给 user={user_id}")
            except Exception as e:
                logger.warning(f"❌ [WS] 发送消息失败: {e}")
                dead_connections.append(connection)
        
        # 清理死连接
        if dead_connections:
            async with self._lock:
                if user_id in self.active_connections:
                    for conn in dead_connections:
                        self.active_connections[user_id].discard(conn)
                    if not self.active_connections[user_id]:
                        del self.active_connections[user_id]
    
    async def broadcast(self, message: dict):
        """广播消息给所有连接"""
        async with self._lock:
            all_connections = []
            for connections in self.active_connections.values():
                all_connections.extend(connections)
        
        message_json = json.dumps(message, ensure_ascii=False)
        
        for connection in all_connections:
            try:
                await connection.send_text(message_json)
            except Exception as e:
                logger.warning(f"❌ [WS] 广播消息失败: {e}")
    
    def get_stats(self) -> dict:
        """获取连接统计"""
        return {
            "total_users": len(self.active_connections),
            "total_connections": sum(len(conns) for conns in self.active_connections.values()),
            "users": {user_id: len(conns) for user_id, conns in self.active_connections.items()}
        }


# 全局连接管理器实例
manager = ConnectionManager()


@router.websocket("/ws/notifications")
async def websocket_notifications_endpoint(
    websocket: WebSocket,
    token: Optional[str] = Query(None),
):
    """
    WebSocket 通知端点

    客户端连接:
    - JWT 模式: ws://localhost:8000/api/ws/notifications?token=<jwt_token>
    - 京东云模式: ws://localhost:8000/api/ws/notifications （无需 token，由网关注入 Basic Auth）

    消息格式:
    {
        "type": "notification",  // 消息类型: notification, heartbeat, connected
        "data": {
            "id": "...",
            "title": "...",
            "content": "...",
            "type": "analysis",
            "link": "/stocks/000001",
            "source": "analysis",
            "created_at": "2025-10-23T12:00:00",
            "status": "unread"
        }
    }
    """
    # 统一认证（JWT 或京东云 Basic Auth）
    user_id = await _authenticate_websocket(websocket, token)
    if not user_id:
        await websocket.close(code=1008, reason="Unauthorized")
        return

    # 连接 WebSocket
    await manager.connect(websocket, user_id)
    
    # 发送连接确认
    await websocket.send_json({
        "type": "connected",
        "data": {
            "user_id": user_id,
            "timestamp": datetime.utcnow().isoformat(),
            "message": "WebSocket 连接成功"
        }
    })
    
    try:
        # 心跳任务
        async def send_heartbeat():
            while True:
                try:
                    await asyncio.sleep(30)  # 每 30 秒发送一次心跳
                    await websocket.send_json({
                        "type": "heartbeat",
                        "data": {
                            "timestamp": datetime.utcnow().isoformat()
                        }
                    })
                except Exception as e:
                    logger.debug(f"💓 [WS] 心跳发送失败: {e}")
                    break
        
        # 启动心跳任务
        heartbeat_task = asyncio.create_task(send_heartbeat())
        
        # 接收客户端消息（主要用于保持连接）
        while True:
            try:
                data = await websocket.receive_text()
                # 可以处理客户端发送的消息（如 ping/pong）
                logger.debug(f"📥 [WS] 收到客户端消息: user={user_id}, data={data}")
            except WebSocketDisconnect:
                logger.info(f"🔌 [WS] 客户端主动断开: user={user_id}")
                break
            except Exception as e:
                logger.error(f"❌ [WS] 接收消息错误: {e}")
                break
    
    finally:
        # 取消心跳任务
        if 'heartbeat_task' in locals():
            heartbeat_task.cancel()
            try:
                await heartbeat_task
            except asyncio.CancelledError:
                pass
        
        # 断开连接
        await manager.disconnect(websocket, user_id)


@router.websocket("/ws/tasks/{task_id}")
async def websocket_task_progress_endpoint(
    websocket: WebSocket,
    task_id: str,
    token: Optional[str] = Query(None),
):
    """
    WebSocket 任务进度端点

    客户端连接:
    - JWT 模式: ws://localhost:8000/api/ws/tasks/<task_id>?token=<jwt_token>
    - 京东云模式: ws://localhost:8000/api/ws/tasks/<task_id> （无需 token，由网关注入 Basic Auth）

    消息格式:
    {
        "type": "progress",  // 消息类型: progress, completed, error, heartbeat
        "data": {
            "task_id": "...",
            "message": "正在分析...",
            "step": 1,
            "total_steps": 5,
            "progress": 20.0,
            "timestamp": "2025-10-23T12:00:00"
        }
    }
    """
    # 统一认证（JWT 或京东云 Basic Auth）
    user_id = await _authenticate_websocket(websocket, token)
    if not user_id:
        await websocket.close(code=1008, reason="Unauthorized")
        return
    channel = f"task_progress:{task_id}"
    
    # 连接 WebSocket
    await websocket.accept()
    logger.info(f"✅ [WS-Task] 新连接: task={task_id}, user={user_id}")
    
    # 发送连接确认
    await websocket.send_json({
        "type": "connected",
        "data": {
            "task_id": task_id,
            "timestamp": datetime.utcnow().isoformat(),
            "message": "已连接任务进度流"
        }
    })
    
    try:
        # 这里可以从 Redis 或数据库获取任务进度
        # 暂时保持连接，等待任务完成
        while True:
            try:
                data = await websocket.receive_text()
                logger.debug(f"📥 [WS-Task] 收到客户端消息: task={task_id}, data={data}")
            except WebSocketDisconnect:
                logger.info(f"🔌 [WS-Task] 客户端主动断开: task={task_id}")
                break
            except Exception as e:
                logger.error(f"❌ [WS-Task] 接收消息错误: {e}")
                break
    
    finally:
        logger.info(f"🔌 [WS-Task] 断开连接: task={task_id}")


@router.get("/ws/stats")
async def get_websocket_stats():
    """获取 WebSocket 连接统计"""
    return manager.get_stats()


# 🔥 辅助函数：供其他模块调用，发送通知
async def send_notification_via_websocket(user_id: str, notification: dict):
    """
    通过 WebSocket 发送通知
    
    Args:
        user_id: 用户 ID
        notification: 通知数据
    """
    message = {
        "type": "notification",
        "data": notification
    }
    await manager.send_personal_message(message, user_id)


async def send_task_progress_via_websocket(task_id: str, progress_data: dict):
    """
    通过 WebSocket 发送任务进度
    
    Args:
        task_id: 任务 ID
        progress_data: 进度数据
    """
    # 注意：这里需要知道任务属于哪个用户
    # 可以从数据库查询或在 progress_data 中传递
    # 暂时简化处理
    message = {
        "type": "progress",
        "data": progress_data
    }
    # 广播给所有连接（生产环境应该只发给任务所属用户）
    await manager.broadcast(message)

