"""
GatewayRouter — 路由分发与消息处理

职责：
1. 注册和管理各平台适配器
2. 接收原始 Webhook，委托适配器解析为 GatewayMessage
3. 执行用户身份映射（IM user → system user）
4. 调用 IntelligentAssistantService 处理消息
5. 将助理回复格式化为 GatewayResponse，委托适配器发送
"""

import logging
from typing import Any, Dict, Optional, Tuple

from core.gateway.adapters.base import BaseGatewayAdapter
from core.gateway.models import (
    GatewayMessage,
    GatewayResponse,
    MessageType,
    ResponseType,
)

logger = logging.getLogger(__name__)


class GatewayRouter:
    """Gateway 路由分发器（单例）"""

    def __init__(self):
        self._adapters: Dict[str, BaseGatewayAdapter] = {}

    # ------------------------------------------------------------------ #
    # 适配器管理
    # ------------------------------------------------------------------ #

    def register_adapter(self, adapter: BaseGatewayAdapter) -> None:
        """注册一个平台适配器"""
        key = adapter.channel_type.value if hasattr(adapter.channel_type, "value") else str(adapter.channel_type)
        self._adapters[key] = adapter
        logger.info("[Gateway] 已注册适配器: %s", key)

    def get_adapter(self, platform: str) -> Optional[BaseGatewayAdapter]:
        return self._adapters.get(platform)

    @property
    def supported_platforms(self) -> list:
        return list(self._adapters.keys())

    # ------------------------------------------------------------------ #
    # 核心处理流程
    # ------------------------------------------------------------------ #

    async def handle_webhook(
        self,
        platform: str,
        headers: Dict[str, str],
        body: bytes,
        db,
    ) -> Tuple[Optional[Dict[str, Any]], int]:
        """
        处理来自 IM 平台的 Webhook 请求。

        Returns:
            (response_json, http_status_code)
            - response_json: 需要立即返回给平台的 JSON（Challenge 或 ack）
            - http_status_code: HTTP 状态码
        """
        adapter = self.get_adapter(platform)
        if not adapter:
            logger.warning("[Gateway] 未知平台: %s", platform)
            return {"error": f"Unsupported platform: {platform}"}, 400

        # 1. 验证签名 / Challenge
        is_valid, challenge_resp = await adapter.verify_request(headers, body)
        if challenge_resp is not None:
            # 飞书等平台的 URL 验证请求，直接返回
            return challenge_resp, 200
        if not is_valid:
            logger.warning("[Gateway] 签名验证失败: platform=%s", platform)
            return {"error": "Invalid signature"}, 403

        # 2. 解析消息
        message = await adapter.parse_message(headers, body)
        if message is None:
            # 不需要处理的事件类型（如消息撤回、用户进群等）
            return self._ack_response(platform), 200

        # 3. 处理 /command 类型消息
        if message.message_type == MessageType.COMMAND:
            cmd_result = await self._handle_command(message, adapter, db, platform)
            # 如果不是 pass_through（未知命令当普通消息处理），直接返回
            if message.message_type == MessageType.COMMAND:
                return cmd_result

        # 4. 用户映射
        system_user_id = await self._resolve_user(
            message.channel_type, message.user_identity, db
        )
        if not system_user_id:
            # 未绑定用户，发送引导消息
            await self._send_bind_guide(message, adapter)
            return self._ack_response(platform), 200

        # 5. 调用助理
        response = await self._invoke_assistant(
            message, system_user_id, db
        )

        # 6. 回复到平台（异步，不阻塞 Webhook 响应）
        try:
            await adapter.send_response(response)
        except Exception as e:
            logger.exception("[Gateway] 发送回复失败: %s", e)

        return self._ack_response(platform), 200

    @staticmethod
    def _ack_response(platform: str) -> Dict[str, Any]:
        """生成平台对应的 ACK 响应"""
        if platform == "qq":
            # QQ 要求返回 op=12 表示收到事件
            return {"op": 12}
        return {"status": "ok"}

    # ------------------------------------------------------------------ #
    # 内部方法
    # ------------------------------------------------------------------ #

    async def _resolve_user(
        self, channel_type: str, platform_identity: str, db
    ) -> Optional[str]:
        """从 user_identity_mappings 集合查找系统用户"""
        from core.gateway.user_mapping import UserMappingManager
        mgr = UserMappingManager(db)
        return await mgr.get_system_user_id(channel_type, platform_identity)

    async def _invoke_assistant(
        self,
        message: GatewayMessage,
        user_id: str,
        db,
    ) -> GatewayResponse:
        """调用 IntelligentAssistantService 处理消息"""
        from app.services.intelligent_assistant_service import chat_with_assistant

        session_key = f"{user_id}:{message.channel_type}:{message.channel_id}"

        result = await chat_with_assistant(
            db=db,
            user_message=message.content,
            user_id=user_id,
            conversation_id=session_key,
        )

        reply_text = result.get("reply", "抱歉，处理消息时出现问题。")
        return GatewayResponse(
            channel_type=message.channel_type,
            channel_id=message.channel_id,
            response_type=ResponseType.MARKDOWN,
            content=reply_text,
            metadata=message.metadata,  # 透传平台元数据（如 msg_id）
        )

    async def _handle_command(
        self,
        message: GatewayMessage,
        adapter: BaseGatewayAdapter,
        db,
        platform: str = "",
    ) -> Tuple[Optional[Dict[str, Any]], int]:
        """处理斜杠命令（/bind, /help 等）"""
        cmd = message.content.strip().lower()

        if cmd == "/help":
            help_text = (
                "📋 可用命令：\n"
                "/bind — 绑定系统账号\n"
                "/help — 显示帮助\n\n"
                "直接发送文字即可与分析助理对话，例如：\n"
                "• 分析贵州茅台\n"
                "• 上周分析过哪些股票\n"
                "• 查看我的自选股"
            )
            resp = GatewayResponse(
                channel_type=message.channel_type,
                channel_id=message.channel_id,
                response_type=ResponseType.TEXT,
                content=help_text,
                metadata=message.metadata,
            )
            await adapter.send_response(resp)
            return self._ack_response(platform), 200

        if cmd == "/bind":
            from core.gateway.user_mapping import UserMappingManager
            mgr = UserMappingManager(db)

            # 检查是否已绑定
            existing = await mgr.get_system_user_id(
                message.channel_type, message.user_identity
            )
            if existing:
                resp = GatewayResponse(
                    channel_type=message.channel_type,
                    channel_id=message.channel_id,
                    response_type=ResponseType.TEXT,
                    content="✅ 你已绑定系统账号，可以直接对话。",
                    metadata=message.metadata,
                )
                await adapter.send_response(resp)
                return self._ack_response(platform), 200

            # 生成验证码
            code = await mgr.create_bind_code(
                platform=message.channel_type,
                platform_identity=message.user_identity,
                channel_id=message.channel_id,
                display_name=message.metadata.get("display_name"),
            )
            resp = GatewayResponse(
                channel_type=message.channel_type,
                channel_id=message.channel_id,
                response_type=ResponseType.TEXT,
                content=(
                    f"🔗 你的绑定验证码: **{code}**\n\n"
                    f"请在 10 分钟内到 Web 端「设置 → IM 绑定」输入此验证码完成绑定。"
                ),
                metadata=message.metadata,
            )
            await adapter.send_response(resp)
            return self._ack_response(platform), 200

        # 未知命令，当普通消息处理
        message.message_type = MessageType.TEXT
        return self._ack_response(platform), 200

    async def _send_bind_guide(
        self,
        message: GatewayMessage,
        adapter: BaseGatewayAdapter,
    ) -> None:
        """发送绑定引导消息"""
        guide = (
            "👋 你好！我是 TradingAgents-CN 分析助理。\n\n"
            "检测到你还没有绑定系统账号，请先完成绑定：\n"
            "1. 发送 /bind 获取验证码\n"
            "2. 在 Web 端「设置 → IM 绑定」中输入验证码\n\n"
            "绑定后即可在这里直接对话、触发分析、查看报告。"
        )
        resp = GatewayResponse(
            channel_type=message.channel_type,
            channel_id=message.channel_id,
            response_type=ResponseType.TEXT,
            content=guide,
            metadata=message.metadata,
        )
        try:
            await adapter.send_response(resp)
        except Exception as e:
            logger.warning("[Gateway] 发送绑定引导失败: %s", e)


# 全局单例
gateway_router = GatewayRouter()

