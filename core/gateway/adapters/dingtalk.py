"""
钉钉 Bot 适配器

基于钉钉机器人 Outgoing 回调模式实现，支持：
- 单聊消息
- 群聊 @Bot 消息
- 签名验证（timestamp + sign）
- Access Token 自动管理

钉钉开放平台文档: https://open.dingtalk.com/document/orgapp/robot-overview

配置项（存储在 system_configs, config_key="gateway_dingtalk"）:
{
    "app_key": "xxx",              # AppKey
    "app_secret": "xxx",           # AppSecret
    "robot_code": "xxx",           # 机器人编码（用于主动发消息）
    "enabled": true
}
"""

import base64
import hashlib
import hmac
import json
import logging
import time
from typing import Any, Dict, Optional, Tuple
from urllib.parse import quote_plus

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

DINGTALK_API_BASE = "https://api.dingtalk.com"
DINGTALK_OLD_API = "https://oapi.dingtalk.com"


class DingTalkAdapter(BaseGatewayAdapter):
    """钉钉 Bot 适配器"""

    channel_type = ChannelType.DINGTALK

    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self._access_token: Optional[str] = None
        self._token_expires_at: float = 0.0

    # ------------------------------------------------------------------ #
    # Access Token 管理
    # ------------------------------------------------------------------ #

    async def _ensure_access_token(self) -> str:
        now = time.time()
        if self._access_token and now < self._token_expires_at - 120:
            return self._access_token

        url = f"{DINGTALK_API_BASE}/v1.0/oauth2/accessToken"
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(url, json={
                "appKey": self.config["app_key"],
                "appSecret": self.config["app_secret"],
            })
            resp.raise_for_status()
            data = resp.json()

        self._access_token = data.get("accessToken")
        expire_in = data.get("expireIn", 7200)
        self._token_expires_at = now + expire_in
        logger.info("[DingTalkAdapter] Access Token 已刷新，有效期 %ss", expire_in)
        return self._access_token

    def _get_auth_headers(self, token: str) -> Dict[str, str]:
        return {
            "x-acs-dingtalk-access-token": token,
            "Content-Type": "application/json; charset=utf-8",
        }

    # ------------------------------------------------------------------ #
    # Webhook 验证
    # ------------------------------------------------------------------ #

    async def verify_request(
        self, headers: Dict[str, str], body: bytes
    ) -> Tuple[bool, Optional[Dict[str, Any]]]:
        """
        验证钉钉 Outgoing 机器人回调请求。

        钉钉在 header 中传递 timestamp + sign，
        用 AppSecret 对 timestamp + "\\n" + AppSecret 做 HMAC-SHA256 校验。
        """
        timestamp = headers.get("timestamp", "")
        sign = headers.get("sign", "")

        if not timestamp or not sign:
            # 新版钉钉某些模式可能不传签名，放行并在日志中提醒
            logger.warning("[DingTalkAdapter] 缺少签名头，放行")
            return True, None

        app_secret = self.config.get("app_secret", "")
        if not app_secret:
            return True, None

        string_to_sign = f"{timestamp}\n{app_secret}"
        hmac_code = hmac.new(
            app_secret.encode("utf-8"),
            string_to_sign.encode("utf-8"),
            digestmod=hashlib.sha256,
        ).digest()
        expected_sign = quote_plus(base64.b64encode(hmac_code).decode("utf-8"))

        if sign != expected_sign:
            logger.warning("[DingTalkAdapter] 签名验证失败")
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

        msg_type = payload.get("msgtype", "")
        if msg_type != "text":
            logger.debug("[DingTalkAdapter] 忽略消息类型: %s", msg_type)
            return None

        text_content = payload.get("text", {}).get("content", "").strip()
        if not text_content:
            return None

        sender_id = payload.get("senderStaffId") or payload.get("senderId", "")
        sender_nick = payload.get("senderNick", "")
        conversation_id = payload.get("conversationId", "")
        conversation_type = payload.get("conversationType", "")
        # 1 = 单聊, 2 = 群聊
        is_group = str(conversation_type) == "2"
        msg_id = payload.get("msgId", "")
        chatbot_user_id = payload.get("chatbotUserId", "")
        session_webhook = payload.get("sessionWebhook", "")

        if is_group:
            channel_id = f"group:{conversation_id}"
        else:
            channel_id = f"p2p:{sender_id}"

        is_command = text_content.startswith("/")

        return GatewayMessage(
            channel_type=ChannelType.DINGTALK,
            channel_id=channel_id,
            user_identity=sender_id,
            message_type=MessageType.COMMAND if is_command else MessageType.TEXT,
            content=text_content,
            is_mention_bot=True,
            metadata={
                "msg_id": msg_id,
                "conversation_id": conversation_id,
                "conversation_type": conversation_type,
                "sender_nick": sender_nick,
                "chatbot_user_id": chatbot_user_id,
                "session_webhook": session_webhook,
            },
        )

    # ------------------------------------------------------------------ #
    # 消息发送
    # ------------------------------------------------------------------ #

    async def send_response(self, response: GatewayResponse) -> bool:
        """
        发送消息到钉钉。

        优先使用 sessionWebhook（Outgoing 场景下的回复 URL），
        否则使用主动发消息 API。
        """
        session_webhook = (response.metadata or {}).get("session_webhook")
        if session_webhook:
            return await self._send_via_webhook(session_webhook, response)

        return await self._send_via_api(response)

    async def _send_via_webhook(self, webhook_url: str, response: GatewayResponse) -> bool:
        """通过 sessionWebhook 回复（最简方式）"""
        text = self.truncate_for_platform(response.content, max_length=4000)
        body = {
            "msgtype": "text",
            "text": {"content": text},
        }

        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.post(webhook_url, json=body)
            data = resp.json()
            if data.get("errcode", 0) == 0:
                logger.info("[DingTalkAdapter] Webhook 回复成功")
                return True
            else:
                logger.warning(
                    "[DingTalkAdapter] Webhook 回复失败: %s", data.get("errmsg")
                )
                return False
        except Exception as e:
            logger.exception("[DingTalkAdapter] Webhook 回复异常: %s", e)
            return False

    async def _send_via_api(self, response: GatewayResponse) -> bool:
        """通过钉钉开放 API 主动发消息"""
        token = await self._ensure_access_token()

        robot_code = self.config.get("robot_code", "")
        if not robot_code:
            logger.warning("[DingTalkAdapter] 缺少 robot_code，无法主动发消息")
            return False

        channel_id = response.channel_id
        text = self.truncate_for_platform(response.content, max_length=4000)

        if channel_id.startswith("p2p:"):
            user_id = channel_id[4:]
            url = f"{DINGTALK_API_BASE}/v1.0/robot/oToMessages/batchSend"
            body = {
                "robotCode": robot_code,
                "userIds": [user_id],
                "msgKey": "sampleText",
                "msgParam": json.dumps({"content": text}, ensure_ascii=False),
            }
        elif channel_id.startswith("group:"):
            conversation_id = channel_id[6:]
            url = f"{DINGTALK_API_BASE}/v1.0/robot/groupMessages/send"
            body = {
                "robotCode": robot_code,
                "openConversationId": conversation_id,
                "msgKey": "sampleText",
                "msgParam": json.dumps({"content": text}, ensure_ascii=False),
            }
        else:
            logger.warning("[DingTalkAdapter] 未知 channel_id 格式: %s", channel_id)
            return False

        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.post(
                    url, json=body, headers=self._get_auth_headers(token)
                )
            data = resp.json()
            if resp.status_code in (200, 201) and not data.get("code"):
                logger.info("[DingTalkAdapter] API 消息发送成功")
                return True
            else:
                logger.warning(
                    "[DingTalkAdapter] API 消息发送失败: %s",
                    data.get("message") or data.get("errmsg"),
                )
                return False
        except Exception as e:
            logger.exception("[DingTalkAdapter] API 消息发送异常: %s", e)
            return False

    def format_report_as_response(
        self, report_text: str, channel_id: str
    ) -> GatewayResponse:
        """将分析报告格式化为钉钉 Markdown 消息"""
        truncated = self.truncate_for_platform(report_text, max_length=3500)
        return GatewayResponse(
            channel_type=self.channel_type.value,
            channel_id=channel_id,
            response_type=ResponseType.MARKDOWN,
            content=truncated,
        )
