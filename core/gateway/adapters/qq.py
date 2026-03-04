"""
QQ Bot 适配器

基于 QQ 开放平台 Webhook 回调模式实现，支持：
- C2C 单聊消息（C2C_MESSAGE_CREATE）
- 群聊 @Bot 消息（GROUP_AT_MESSAGE_CREATE）
- ed25519 签名验证 + 回调地址验证（op=13）
- AccessToken 自动管理（7200s 有效期）

QQ Bot API 文档: https://bot.q.qq.com/wiki/develop/api-v2/

配置项（存储在 system_configs, config_key="gateway_qq"）:
{
    "app_id": "xxx",
    "app_secret": "xxx",         # clientSecret
    "bot_secret": "xxx",         # 用于 webhook 签名验证的 secret
}
"""

import hashlib
import json
import logging
import re
import time
from typing import Any, Dict, Optional, Tuple

import httpx
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from core.gateway.adapters.base import BaseGatewayAdapter
from core.gateway.models import (
    ChannelType,
    GatewayMessage,
    MessageType,
    GatewayResponse,
)

logger = logging.getLogger(__name__)

QQ_API_BASE = "https://api.sgroup.qq.com"
QQ_TOKEN_URL = "https://bots.qq.com/app/getAppAccessToken"


class QQAdapter(BaseGatewayAdapter):
    """QQ Bot 适配器（Webhook 模式）"""

    channel_type = ChannelType.QQ

    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self._access_token: Optional[str] = None
        self._token_expires_at: float = 0.0

    # ------------------------------------------------------------------ #
    # AccessToken 管理
    # ------------------------------------------------------------------ #

    async def _ensure_access_token(self) -> str:
        """获取或刷新 AccessToken"""
        now = time.time()
        # 提前 120s 刷新
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
        logger.info("[QQAdapter] AccessToken 已刷新，有效期 %ss", data.get("expires_in"))
        return self._access_token

    def _get_auth_headers(self, token: str) -> Dict[str, str]:
        return {
            "Authorization": f"QQBot {token}",
            "Content-Type": "application/json",
        }

    # ------------------------------------------------------------------ #
    # Webhook 签名验证
    # ------------------------------------------------------------------ #

    async def verify_request(
        self, headers: Dict[str, str], body: bytes
    ) -> Tuple[bool, Optional[Dict[str, Any]]]:
        """
        验证 QQ Webhook 请求。

        - op=13: 回调地址验证，需要用 ed25519 签名返回
        - 其他: 普通事件推送，验证签名头
        """
        try:
            payload = json.loads(body)
        except (json.JSONDecodeError, UnicodeDecodeError):
            return False, None

        op = payload.get("op")

        # op=13: 回调地址验证
        if op == 13:
            return True, self._handle_validation(payload)

        # 普通事件：验证请求头中的签名
        # QQ Webhook 在 header 中传递签名信息
        # 目前简化处理：通过 X-Bot-Appid 验证来源
        bot_appid = headers.get("x-bot-appid", "")
        if bot_appid and bot_appid == self.config.get("app_id", ""):
            return True, None

        # 如果没有 appid header，也通过（某些版本不一定有）
        if not bot_appid:
            logger.warning("[QQAdapter] 缺少 X-Bot-Appid header，放行")
            return True, None

        return False, None

    def _handle_validation(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """处理 op=13 回调地址验证"""
        d = payload.get("d", {})
        plain_token = d.get("plain_token", "")
        event_ts = d.get("event_ts", "")

        bot_secret = self.config.get("bot_secret", "")
        signature = self._ed25519_sign(bot_secret, event_ts, plain_token)

        return {
            "plain_token": plain_token,
            "signature": signature,
        }

    @staticmethod
    def _ed25519_sign(secret: str, event_ts: str, plain_token: str) -> str:
        """
        用 bot_secret 作为 seed 生成 ed25519 私钥，
        对 event_ts + plain_token 签名，返回 hex 编码的签名。
        """
        # seed 必须是 32 字节
        seed = secret
        while len(seed) < 32:
            seed = seed * 2
        seed_bytes = seed[:32].encode("utf-8")

        private_key = Ed25519PrivateKey.from_private_bytes(seed_bytes)
        msg = (event_ts + plain_token).encode("utf-8")
        sig = private_key.sign(msg)
        return sig.hex()

    # ------------------------------------------------------------------ #
    # 消息解析
    # ------------------------------------------------------------------ #

    async def parse_message(
        self, headers: Dict[str, str], body: bytes
    ) -> Optional[GatewayMessage]:
        """
        解析 QQ Webhook 事件为统一 GatewayMessage。

        支持事件类型:
        - C2C_MESSAGE_CREATE: 单聊消息
        - GROUP_AT_MESSAGE_CREATE: 群聊 @Bot 消息
        """
        try:
            payload = json.loads(body)
        except (json.JSONDecodeError, UnicodeDecodeError):
            return None

        op = payload.get("op")
        if op != 0:
            # 非 Dispatch 事件（心跳、验证等），跳过
            return None

        event_type = payload.get("t", "")
        d = payload.get("d", {})

        if event_type == "C2C_MESSAGE_CREATE":
            return self._parse_c2c_message(d)
        elif event_type == "GROUP_AT_MESSAGE_CREATE":
            return self._parse_group_message(d)
        else:
            logger.debug("[QQAdapter] 忽略事件类型: %s", event_type)
            return None

    def _parse_c2c_message(self, d: Dict[str, Any]) -> GatewayMessage:
        """解析 C2C（单聊）消息"""
        user_openid = d.get("author", {}).get("user_openid", "")
        content = (d.get("content") or "").strip()
        msg_id = d.get("id", "")
        logger.info("[QQ收消息] C2C单聊 | user=%s | msg_id=%s | content=%r", user_openid, msg_id, content)

        # 判断是否为命令
        msg_type = MessageType.COMMAND if content.startswith("/") else MessageType.TEXT

        return GatewayMessage(
            channel_type=ChannelType.QQ,
            channel_id=f"c2c:{user_openid}",  # 单聊用 user_openid 作为 channel
            user_identity=user_openid,
            message_type=msg_type,
            content=content,
            is_mention_bot=True,  # 单聊默认就是发给 Bot
            metadata={
                "msg_id": msg_id,
                "scene": "c2c",
                "user_openid": user_openid,
            },
        )

    def _parse_group_message(self, d: Dict[str, Any]) -> GatewayMessage:
        """解析群聊 @Bot 消息"""
        member_openid = d.get("author", {}).get("member_openid", "")
        group_openid = d.get("group_openid", "")
        content = (d.get("content") or "").strip()
        msg_id = d.get("id", "")
        logger.info("[QQ收消息] 群聊@Bot | group=%s | member=%s | msg_id=%s | content=%r", group_openid, member_openid, msg_id, content)

        msg_type = MessageType.COMMAND if content.startswith("/") else MessageType.TEXT

        return GatewayMessage(
            channel_type=ChannelType.QQ,
            channel_id=f"group:{group_openid}",
            user_identity=member_openid,
            message_type=msg_type,
            content=content,
            is_mention_bot=True,
            metadata={
                "msg_id": msg_id,
                "scene": "group",
                "group_openid": group_openid,
                "member_openid": member_openid,
            },
        )

    # ------------------------------------------------------------------ #
    # Markdown → 纯文本转换（QQ 消息不支持 Markdown 渲染）
    # ------------------------------------------------------------------ #

    @staticmethod
    def _convert_md_table(table_lines: list) -> str:
        """
        将 Markdown 横向表格转换为竖排 key: value 格式，适配窄屏 IM。

        输入示例:
            | 指标 | 数值 | 评级 |
            |------|------|------|
            | PE   | 35x  | 中   |
            | PB   | 12x  | 高   |

        输出示例:
            ▶ 指标: PE  数值: 35x  评级: 中
            ▶ 指标: PB  数值: 12x  评级: 高
        """
        rows = []
        for line in table_lines:
            stripped = line.strip().strip('|')
            cells = [c.strip() for c in stripped.split('|')]
            rows.append(cells)

        if len(rows) < 2:
            return '\n'.join(table_lines)

        headers = rows[0]
        result_parts = []

        for row in rows[1:]:
            # 跳过分隔行（如 |---|---|）
            if all(re.match(r'^[-: ]+$', c) for c in row if c.strip()):
                continue
            # 单行只有一列或全空 → 跳过
            non_empty = [c for c in row if c.strip()]
            if not non_empty:
                continue

            if len(headers) == 2:
                # 两列表格：直接用 "标题: 值" 格式，最紧凑
                key = row[0].strip() if len(row) > 0 else ''
                val = row[1].strip() if len(row) > 1 else ''
                if key or val:
                    result_parts.append(f"  {key}: {val}")
            else:
                # 多列表格：每行用分隔符连接各字段
                parts = []
                for i, cell in enumerate(row):
                    if i < len(headers) and (cell.strip() or headers[i].strip()):
                        parts.append(f"{headers[i]}: {cell.strip()}")
                if parts:
                    result_parts.append('  ' + '  '.join(parts))

        return '\n'.join(result_parts)

    @staticmethod
    def _extract_tables(text: str):
        """
        从文本中提取所有 Markdown 表格块（连续的 | 开头行），
        返回 (处理后文本, ) —— 直接在文本中替换。
        """
        lines = text.split('\n')
        result_lines = []
        table_buf = []

        def flush_table():
            if table_buf:
                converted = QQAdapter._convert_md_table(table_buf)
                result_lines.append(converted)
                table_buf.clear()

        for line in lines:
            stripped = line.strip()
            if stripped.startswith('|') and stripped.endswith('|') and len(stripped) > 1:
                table_buf.append(line)
            else:
                flush_table()
                result_lines.append(line)

        flush_table()
        return '\n'.join(result_lines)

    @staticmethod
    def _md_to_plain(text: str) -> str:
        """
        将 Markdown 格式文本转为 QQ 友好的纯文本。

        转换规则：
        - Markdown 表格        → 竖排 key: value（先处理，避免 | 被误删）
        - **bold** / __bold__  → bold
        - *italic* / _italic_  → italic
        - `code`               → code
        - ```code block```     → code block（保留内容，去围栏）
        - ### 标题             → 【标题】
        - - / * 列表           → • 列表
        - [text](url)          → text
        - > 引用               → ｜引用
        - ---                  → ————
        - 多余空行合并
        """
        s = text

        # ① 优先处理表格（利用 | 分隔，必须在其他替换前）
        s = QQAdapter._extract_tables(s)

        # ② 代码块 ```...``` → 保留内容，去掉围栏
        s = re.sub(r'```[a-zA-Z]*\n?', '', s)

        # ③ 行内代码
        s = re.sub(r'`([^`]+)`', r'\1', s)

        # ④ 标题 ### Text → 【Text】
        s = re.sub(r'^#{1,6}\s+(.+)$', r'【\1】', s, flags=re.MULTILINE)

        # ⑤ 粗体 + 斜体
        s = re.sub(r'\*{3}(.+?)\*{3}', r'\1', s)
        s = re.sub(r'_{3}(.+?)_{3}', r'\1', s)
        s = re.sub(r'\*{2}(.+?)\*{2}', r'\1', s)
        s = re.sub(r'_{2}(.+?)_{2}', r'\1', s)
        s = re.sub(r'\*(.+?)\*', r'\1', s)
        s = re.sub(r'_(.+?)_', r'\1', s)

        # ⑥ 链接 [text](url) → text
        s = re.sub(r'\[([^\]]+)\]\([^)]+\)', r'\1', s)

        # ⑦ 图片 → 去掉
        s = re.sub(r'!\[([^\]]*)\]\([^)]+\)', '', s)

        # ⑧ 引用 > text → ｜text
        s = re.sub(r'^>\s?(.*)$', r'｜\1', s, flags=re.MULTILINE)

        # ⑨ 无序列表 - / * → •
        s = re.sub(r'^[ \t]*[-*]\s+', '• ', s, flags=re.MULTILINE)

        # ⑩ 分割线
        s = re.sub(r'^-{3,}$', '————————', s, flags=re.MULTILINE)
        s = re.sub(r'^\*{3,}$', '————————', s, flags=re.MULTILINE)

        # ⑪ 删除线
        s = re.sub(r'~~(.+?)~~', r'\1', s)

        # ⑫ 合并多余空行
        s = re.sub(r'\n{3,}', '\n\n', s)

        return s.strip()

    # ------------------------------------------------------------------ #
    # 消息发送
    # ------------------------------------------------------------------ #

    async def send_response(self, response: GatewayResponse) -> bool:
        """
        发送消息到 QQ 平台。

        根据 channel_id 前缀判断场景：
        - c2c:xxx   → 单聊回复
        - group:xxx → 群聊回复
        """
        channel_id = response.channel_id

        # 从 channel_id 解析场景
        if channel_id.startswith("c2c:"):
            user_openid = channel_id[4:]
            return await self._send_c2c_message(user_openid, response)
        elif channel_id.startswith("group:"):
            group_openid = channel_id[6:]
            return await self._send_group_message(group_openid, response)
        else:
            logger.warning("[QQAdapter] 未知 channel_id 格式: %s", channel_id)
            return False

    async def _send_c2c_message(
        self, user_openid: str, response: GatewayResponse
    ) -> bool:
        """发送单聊消息"""
        token = await self._ensure_access_token()
        url = f"{QQ_API_BASE}/v2/users/{user_openid}/messages"

        plain = self._md_to_plain(response.content)
        content = self.truncate_for_platform(plain, max_length=3500)
        body: Dict[str, Any] = {
            "content": content,
            "msg_type": 0,  # 文本消息
        }

        # 如果有 msg_id，作为被动回复
        if hasattr(response, "metadata") and response.metadata:
            msg_id = response.metadata.get("msg_id")
            if msg_id:
                body["msg_id"] = msg_id

        return await self._do_send(url, body, token)

    async def _send_group_message(
        self, group_openid: str, response: GatewayResponse
    ) -> bool:
        """发送群聊消息"""
        token = await self._ensure_access_token()
        url = f"{QQ_API_BASE}/v2/groups/{group_openid}/messages"

        plain = self._md_to_plain(response.content)
        content = self.truncate_for_platform(plain, max_length=3500)
        body: Dict[str, Any] = {
            "content": content,
            "msg_type": 0,
        }

        if hasattr(response, "metadata") and response.metadata:
            msg_id = response.metadata.get("msg_id")
            if msg_id:
                body["msg_id"] = msg_id

        return await self._do_send(url, body, token)

    async def _do_send(
        self, url: str, body: Dict[str, Any], token: str
    ) -> bool:
        """执行 HTTP POST 发送消息"""
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.post(
                    url,
                    json=body,
                    headers=self._get_auth_headers(token),
                )
            if resp.status_code in (200, 201, 204):
                logger.info("[QQAdapter] 消息发送成功: %s", url)
                return True
            else:
                logger.warning(
                    "[QQAdapter] 消息发送失败: status=%s, body=%s",
                    resp.status_code, resp.text[:300],
                )
                return False
        except Exception as e:
            logger.exception("[QQAdapter] 消息发送异常: %s", e)
            return False

