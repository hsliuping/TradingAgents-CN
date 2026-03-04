"""
QQ Bot WebSocket 客户端

通过 WebSocket 连接 QQ 网关接收事件，不需要公网 IP。

协议流程:
  Connect → Hello(op=10) → Identify(op=2) → Ready(op=0) → 心跳循环 → Dispatch(op=0)

QQ 官方文档: https://bot.q.qq.com/wiki/develop/api-v2/dev-prepare/interface-framework/event-emit.html
"""

import asyncio
import json
import logging
import time
from typing import Any, Dict, Optional

import aiohttp
import httpx

logger = logging.getLogger(__name__)

QQ_API_BASE = "https://api.sgroup.qq.com"
QQ_SANDBOX_API_BASE = "https://sandbox.api.sgroup.qq.com"
QQ_TOKEN_URL = "https://bots.qq.com/app/getAppAccessToken"

# OpCodes
OP_DISPATCH = 0
OP_HEARTBEAT = 1
OP_IDENTIFY = 2
OP_RESUME = 6
OP_RECONNECT = 7
OP_INVALID_SESSION = 9
OP_HELLO = 10
OP_HEARTBEAT_ACK = 11

# Intents - 需要接收的事件类型
INTENT_GROUP_AND_C2C = 1 << 25       # C2C_MESSAGE_CREATE + GROUP_AT_MESSAGE_CREATE
INTENT_PUBLIC_GUILD_MESSAGES = 1 << 30  # AT_MESSAGE_CREATE (频道公域)


class QQWebSocketClient:
    """QQ Bot WebSocket 客户端 — 连接 QQ 网关接收事件推送"""

    def __init__(
        self,
        config: Dict[str, Any],
        on_event=None,
        sandbox: bool = False,
    ):
        """
        Args:
            config: 包含 app_id, app_secret 的配置字典
            on_event: 收到 Dispatch 事件时的回调, async def on_event(event_type, data, raw_payload)
            sandbox: 是否使用沙箱环境
        """
        self.config = config
        self.on_event = on_event
        self.sandbox = sandbox

        self._access_token: Optional[str] = None
        self._token_expires_at: float = 0.0
        self._session_id: Optional[str] = None
        self._seq: Optional[int] = None
        self._heartbeat_interval: float = 45.0  # 默认 45s，Hello 中会更新
        self._ws: Optional[aiohttp.ClientWebSocketResponse] = None
        self._heartbeat_task: Optional[asyncio.Task] = None
        self._running: bool = False
        self._reconnect_delay: float = 1.0  # 重连延迟（指数退避）
        self._max_reconnect_delay: float = 60.0

    # ------------------------------------------------------------------ #
    # AccessToken 管理
    # ------------------------------------------------------------------ #

    async def _ensure_access_token(self) -> str:
        now = time.time()
        if self._access_token and now < self._token_expires_at - 120:
            return self._access_token

        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(QQ_TOKEN_URL, json={
                "appId": self.config["app_id"],
                "clientSecret": self.config["app_secret"],
            })
            resp.raise_for_status()
            data = resp.json()

        self._access_token = data["access_token"]
        self._token_expires_at = now + int(data.get("expires_in", 7200))
        logger.info("[QQ-WS] AccessToken 已刷新，有效期 %ss", data.get("expires_in"))
        return self._access_token

    # ------------------------------------------------------------------ #
    # 获取 WebSocket 网关地址
    # ------------------------------------------------------------------ #

    async def _get_gateway_url(self) -> str:
        token = await self._ensure_access_token()
        base = QQ_SANDBOX_API_BASE if self.sandbox else QQ_API_BASE
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(
                f"{base}/gateway",
                headers={"Authorization": f"QQBot {token}"},
            )
            resp.raise_for_status()
            data = resp.json()
        url = data.get("url", "")
        logger.info("[QQ-WS] 网关地址: %s", url)
        return url

    # ------------------------------------------------------------------ #
    # 主运行循环
    # ------------------------------------------------------------------ #

    async def start(self):
        """启动 WebSocket 客户端（阻塞，应在 asyncio.create_task 中调用）"""
        self._running = True
        self._reconnect_delay = 1.0
        logger.info("[QQ-WS] 启动 WebSocket 客户端...")

        while self._running:
            try:
                await self._connect_and_listen()
            except asyncio.CancelledError:
                logger.info("[QQ-WS] 客户端被取消")
                break
            except Exception as e:
                if not self._running:
                    break
                logger.warning("[QQ-WS] 连接异常: %s, %.1fs 后重连", e, self._reconnect_delay)
                await asyncio.sleep(self._reconnect_delay)
                self._reconnect_delay = min(self._reconnect_delay * 2, self._max_reconnect_delay)

        logger.info("[QQ-WS] 客户端已停止")

    async def stop(self):
        """停止 WebSocket 客户端"""
        self._running = False
        if self._heartbeat_task and not self._heartbeat_task.done():
            self._heartbeat_task.cancel()
        if self._ws and not self._ws.closed:
            await self._ws.close()
        logger.info("[QQ-WS] 已发送停止信号")

    # ------------------------------------------------------------------ #
    # WebSocket 连接与监听
    # ------------------------------------------------------------------ #

    async def _connect_and_listen(self):
        """建立一次 WebSocket 连接并监听消息"""
        gateway_url = await self._get_gateway_url()
        if not gateway_url:
            raise RuntimeError("未获取到网关地址")

        async with aiohttp.ClientSession() as session:
            async with session.ws_connect(gateway_url) as ws:
                self._ws = ws
                logger.info("[QQ-WS] 已连接到网关")

                async for msg in ws:
                    if msg.type == aiohttp.WSMsgType.TEXT:
                        await self._handle_message(ws, json.loads(msg.data))
                    elif msg.type == aiohttp.WSMsgType.ERROR:
                        logger.error("[QQ-WS] WebSocket 错误: %s", ws.exception())
                        break
                    elif msg.type in (aiohttp.WSMsgType.CLOSE, aiohttp.WSMsgType.CLOSING, aiohttp.WSMsgType.CLOSED):
                        logger.warning("[QQ-WS] 连接关闭: %s", msg.data)
                        break

        # 清理心跳
        if self._heartbeat_task and not self._heartbeat_task.done():
            self._heartbeat_task.cancel()
            try:
                await self._heartbeat_task
            except asyncio.CancelledError:
                pass

    async def _handle_message(self, ws: aiohttp.ClientWebSocketResponse, payload: Dict[str, Any]):
        """处理从网关收到的消息"""
        op = payload.get("op")
        d = payload.get("d")
        s = payload.get("s")
        t = payload.get("t")

        # 更新序列号
        if s is not None:
            self._seq = s

        if op == OP_HELLO:
            # 收到 Hello，获取心跳间隔并发送 Identify
            self._heartbeat_interval = d.get("heartbeat_interval", 45000) / 1000.0
            logger.info("[QQ-WS] Hello: 心跳间隔 %.1fs", self._heartbeat_interval)

            if self._session_id and self._seq is not None:
                # 断线重连：Resume
                await self._send_resume(ws)
            else:
                # 首次连接：Identify
                await self._send_identify(ws)

            # 启动心跳
            if self._heartbeat_task and not self._heartbeat_task.done():
                self._heartbeat_task.cancel()
            self._heartbeat_task = asyncio.create_task(self._heartbeat_loop(ws))

        elif op == OP_DISPATCH:
            # 事件分发
            self._reconnect_delay = 1.0  # 重置重连延迟
            if t == "READY":
                self._session_id = d.get("session_id")
                user_info = d.get("user", {})
                logger.info(
                    "[QQ-WS] 鉴权成功! session=%s, bot=%s",
                    self._session_id, user_info.get("username", "?"),
                )
            elif t == "RESUMED":
                logger.info("[QQ-WS] 恢复连接成功")
            else:
                # 业务事件（消息等），回调处理
                if self.on_event:
                    try:
                        await self.on_event(t, d, payload)
                    except Exception as e:
                        logger.exception("[QQ-WS] 事件处理异常: %s", e)

        elif op == OP_HEARTBEAT_ACK:
            logger.debug("[QQ-WS] 心跳 ACK")

        elif op == OP_RECONNECT:
            logger.warning("[QQ-WS] 服务端要求重连")
            await ws.close()

        elif op == OP_INVALID_SESSION:
            logger.warning("[QQ-WS] Invalid Session, 重新鉴权")
            self._session_id = None
            self._seq = None
            await ws.close()

        else:
            logger.debug("[QQ-WS] 未处理的 op=%s", op)

    # ------------------------------------------------------------------ #
    # 发送操作
    # ------------------------------------------------------------------ #

    async def _send_identify(self, ws: aiohttp.ClientWebSocketResponse):
        """发送鉴权 Identify"""
        token = await self._ensure_access_token()
        intents = INTENT_GROUP_AND_C2C  # C2C + 群聊 @Bot
        payload = {
            "op": OP_IDENTIFY,
            "d": {
                "token": f"QQBot {token}",
                "intents": intents,
                "shard": [0, 1],
                "properties": {
                    "$os": "windows",
                    "$browser": "TradingAgentsCN",
                    "$device": "TradingAgentsCN",
                },
            },
        }
        await ws.send_json(payload)
        logger.info("[QQ-WS] 已发送 Identify, intents=%d", intents)

    async def _send_resume(self, ws: aiohttp.ClientWebSocketResponse):
        """发送 Resume 恢复连接"""
        token = await self._ensure_access_token()
        payload = {
            "op": OP_RESUME,
            "d": {
                "token": f"QQBot {token}",
                "session_id": self._session_id,
                "seq": self._seq,
            },
        }
        await ws.send_json(payload)
        logger.info("[QQ-WS] 已发送 Resume, session=%s, seq=%s", self._session_id, self._seq)

    async def _heartbeat_loop(self, ws: aiohttp.ClientWebSocketResponse):
        """定期发送心跳"""
        try:
            while self._running and not ws.closed:
                await asyncio.sleep(self._heartbeat_interval)
                if ws.closed:
                    break
                payload = {"op": OP_HEARTBEAT, "d": self._seq}
                await ws.send_json(payload)
                logger.debug("[QQ-WS] 心跳已发送, seq=%s", self._seq)
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.warning("[QQ-WS] 心跳异常: %s", e)

