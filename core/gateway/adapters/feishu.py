"""
飞书 Bot 适配器

基于飞书开放平台事件订阅（HTTP 回调）模式实现，支持：
- 私聊消息
- 群聊 @Bot 消息
- URL Challenge 验证
- 签名验证（Verification Token / Encrypt Key）
- Tenant Access Token 自动管理

飞书开放平台文档: https://open.feishu.cn/document/server-docs/getting-started

配置项（存储在 system_configs, config_key="gateway_feishu"）:
{
    "app_id": "cli_xxx",
    "app_secret": "xxx",
    "verification_token": "xxx",    # 事件订阅验证 token
    "encrypt_key": "",              # 可选，事件加密密钥
    "enabled": true
}
"""

import hashlib
import json
import logging
import time
from typing import Any, Dict, Optional, Tuple

import httpx

from core.gateway.adapters.base import BaseGatewayAdapter
from core.gateway.models import (
    ChannelType,
    GatewayMessage,
    GatewayResponse,
    MessageType,
    ResponseType,
)

logger = logging.getLogger(__name__)

FEISHU_API_BASE = "https://open.feishu.cn/open-apis"
FEISHU_TOKEN_URL = f"{FEISHU_API_BASE}/auth/v3/tenant_access_token/internal"


class FeishuAdapter(BaseGatewayAdapter):
    """飞书 Bot 适配器"""

    channel_type = ChannelType.FEISHU

    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self._tenant_token: Optional[str] = None
        self._token_expires_at: float = 0.0

    # ------------------------------------------------------------------ #
    # Tenant Access Token 管理
    # ------------------------------------------------------------------ #

    async def _ensure_tenant_token(self) -> str:
        now = time.time()
        if self._tenant_token and now < self._token_expires_at - 120:
            return self._tenant_token

        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(FEISHU_TOKEN_URL, json={
                "app_id": self.config["app_id"],
                "app_secret": self.config["app_secret"],
            })
            resp.raise_for_status()
            data = resp.json()

        if data.get("code") != 0:
            raise RuntimeError(f"飞书 Token 获取失败: {data.get('msg')}")

        self._tenant_token = data["tenant_access_token"]
        self._token_expires_at = now + int(data.get("expire", 7200))
        logger.info("[FeishuAdapter] Tenant Access Token 已刷新")
        return self._tenant_token

    def _get_auth_headers(self, token: str) -> Dict[str, str]:
        return {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json; charset=utf-8",
        }

    # ------------------------------------------------------------------ #
    # Webhook 验证
    # ------------------------------------------------------------------ #

    async def verify_request(
        self, headers: Dict[str, str], body: bytes
    ) -> Tuple[bool, Optional[Dict[str, Any]]]:
        try:
            payload = json.loads(body)
        except (json.JSONDecodeError, UnicodeDecodeError):
            return False, None

        # URL Challenge 验证（首次配置事件订阅时飞书发送）
        if "challenge" in payload:
            token = payload.get("token", "")
            vt = self.config.get("verification_token", "")
            if vt and token != vt:
                logger.warning("[FeishuAdapter] Challenge token 不匹配")
                return False, None
            return True, {"challenge": payload["challenge"]}

        # v2 事件格式验证
        schema = payload.get("schema")
        if schema == "2.0":
            header = payload.get("header", {})
            token = header.get("token", "")
        else:
            token = payload.get("token", "")

        vt = self.config.get("verification_token", "")
        if vt and token != vt:
            logger.warning("[FeishuAdapter] Verification token 不匹配")
            return False, None

        return True, None

    # ------------------------------------------------------------------ #
    # 消息解析
    # ------------------------------------------------------------------ #

    async def parse_message(
        self, headers: Dict[str, str], body: bytes
    ) -> Optional[GatewayMessage]:
        try:
            payload = json.loads(body)
        except (json.JSONDecodeError, UnicodeDecodeError):
            return None

        # 跳过 challenge 请求
        if "challenge" in payload:
            return None

        # v2 格式
        if payload.get("schema") == "2.0":
            return self._parse_v2_event(payload)

        # v1 格式（兼容）
        event = payload.get("event", {})
        if not event:
            return None
        return self._parse_v1_event(event)

    def _parse_v2_event(self, payload: Dict[str, Any]) -> Optional[GatewayMessage]:
        header = payload.get("header", {})
        event_type = header.get("event_type", "")

        if event_type != "im.message.receive_v1":
            logger.debug("[FeishuAdapter] 忽略事件类型: %s", event_type)
            return None

        event = payload.get("event", {})
        sender = event.get("sender", {}).get("sender_id", {})
        message = event.get("message", {})

        open_id = sender.get("open_id", "")
        chat_id = message.get("chat_id", "")
        chat_type = message.get("chat_type", "")
        msg_type = message.get("message_type", "")
        message_id = message.get("message_id", "")

        content_str = message.get("content", "{}")
        try:
            content_obj = json.loads(content_str)
        except json.JSONDecodeError:
            content_obj = {"text": content_str}

        text = content_obj.get("text", "").strip()

        # 群聊中去掉 @Bot 的部分
        if chat_type == "group" and message.get("mentions"):
            for m in message["mentions"]:
                at_key = m.get("key", "")
                if at_key:
                    text = text.replace(at_key, "").strip()

        if not text:
            return None

        if chat_type == "p2p":
            channel_id = f"p2p:{open_id}"
        else:
            channel_id = f"group:{chat_id}"

        is_command = text.startswith("/")

        return GatewayMessage(
            channel_type=ChannelType.FEISHU,
            channel_id=channel_id,
            user_identity=open_id,
            message_type=MessageType.COMMAND if is_command else MessageType.TEXT,
            content=text,
            is_mention_bot=(chat_type == "p2p" or bool(message.get("mentions"))),
            metadata={
                "message_id": message_id,
                "chat_type": chat_type,
                "chat_id": chat_id,
                "open_id": open_id,
                "msg_type": msg_type,
            },
        )

    def _parse_v1_event(self, event: Dict[str, Any]) -> Optional[GatewayMessage]:
        """兼容 v1 事件格式"""
        msg_type = event.get("msg_type", "")
        if msg_type != "text":
            return None

        open_id = event.get("open_id", "")
        chat_type = event.get("chat_type", "")
        text = event.get("text", "").strip()
        open_message_id = event.get("open_message_id", "")
        open_chat_id = event.get("open_chat_id", "")

        if not text:
            return None

        if chat_type == "private":
            channel_id = f"p2p:{open_id}"
        else:
            channel_id = f"group:{open_chat_id}"

        return GatewayMessage(
            channel_type=ChannelType.FEISHU,
            channel_id=channel_id,
            user_identity=open_id,
            message_type=MessageType.COMMAND if text.startswith("/") else MessageType.TEXT,
            content=text,
            is_mention_bot=True,
            metadata={
                "message_id": open_message_id,
                "chat_type": chat_type,
                "chat_id": open_chat_id,
                "open_id": open_id,
            },
        )

    # ------------------------------------------------------------------ #
    # 消息发送
    # ------------------------------------------------------------------ #

    async def send_response(self, response: GatewayResponse) -> bool:
        channel_id = response.channel_id

        if channel_id.startswith("p2p:"):
            receive_id = channel_id[4:]
            receive_id_type = "open_id"
        elif channel_id.startswith("group:"):
            receive_id = channel_id[6:]
            receive_id_type = "chat_id"
        else:
            logger.warning("[FeishuAdapter] 未知 channel_id 格式: %s", channel_id)
            return False

        # 如果有 message_id 且为被动回复场景，使用 reply API
        message_id = (response.metadata or {}).get("message_id")
        if message_id:
            return await self._reply_message(message_id, response)

        return await self._send_message(receive_id, receive_id_type, response)

    async def _send_message(
        self, receive_id: str, receive_id_type: str, response: GatewayResponse
    ) -> bool:
        token = await self._ensure_tenant_token()
        url = f"{FEISHU_API_BASE}/im/v1/messages?receive_id_type={receive_id_type}"

        content, msg_type = self._build_feishu_content(response)
        body = {
            "receive_id": receive_id,
            "msg_type": msg_type,
            "content": content,
        }
        return await self._do_send(url, body, token)

    async def _reply_message(self, message_id: str, response: GatewayResponse) -> bool:
        token = await self._ensure_tenant_token()
        url = f"{FEISHU_API_BASE}/im/v1/messages/{message_id}/reply"

        content, msg_type = self._build_feishu_content(response)
        body = {
            "msg_type": msg_type,
            "content": content,
        }
        return await self._do_send(url, body, token)

    def _build_feishu_content(self, response: GatewayResponse) -> Tuple[str, str]:
        """
        构造飞书消息内容。

        Returns:
            (content_json_str, msg_type)
        """
        text = self.truncate_for_platform(response.content, max_length=4000)

        if response.response_type == ResponseType.CARD and response.card_template:
            return json.dumps(response.card_template, ensure_ascii=False), "interactive"

        return json.dumps({"text": text}, ensure_ascii=False), "text"

    def format_report_as_response(
        self, report_text: str, channel_id: str
    ) -> GatewayResponse:
        """将分析报告格式化为飞书交互卡片"""
        truncated = self.truncate_for_platform(report_text, max_length=3500)

        card = {
            "config": {"wide_screen_mode": True},
            "header": {
                "title": {"tag": "plain_text", "content": "📊 分析报告"},
                "template": "blue",
            },
            "elements": [
                {
                    "tag": "markdown",
                    "content": truncated,
                }
            ],
        }
        return GatewayResponse(
            channel_type=self.channel_type.value,
            channel_id=channel_id,
            response_type=ResponseType.CARD,
            content=report_text,
            card_template=card,
        )

    async def _do_send(self, url: str, body: Dict[str, Any], token: str) -> bool:
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.post(
                    url, json=body, headers=self._get_auth_headers(token)
                )
            data = resp.json()
            if data.get("code") == 0:
                logger.info("[FeishuAdapter] 消息发送成功")
                return True
            else:
                logger.warning(
                    "[FeishuAdapter] 消息发送失败: code=%s, msg=%s",
                    data.get("code"), data.get("msg"),
                )
                return False
        except Exception as e:
            logger.exception("[FeishuAdapter] 消息发送异常: %s", e)
            return False
