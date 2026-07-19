"""
GatewayRouter — 路由分发与消息处理

职责：
1. 注册和管理各平台适配器
2. 接收原始 Webhook / WebSocket 事件，委托适配器解析为 GatewayMessage
3. 执行用户身份映射（IM user → system user）
4. 调用 IntelligentAssistantService 处理消息
5. 将助理回复格式化为 GatewayResponse，委托适配器发送
"""

import asyncio
import json
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
        self._ws_client = None          # QQWebSocketClient 实例
        self._ws_task: Optional[asyncio.Task] = None  # WebSocket 后台任务

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

        # 4. 单用户模式：自动关联系统第一个用户
        system_user_id = await self._resolve_user(db)
        if not system_user_id:
            logger.error("[Gateway] 系统中没有用户，无法处理消息")
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

    async def _resolve_user(self, db) -> Optional[str]:
        """单用户模式：返回系统中第一个活跃用户的 ID"""
        user = await db.users.find_one(
            {"is_active": {"$ne": False}},
            {"_id": 1},
            sort=[("created_at", 1)],
        )
        if user:
            return str(user["_id"])
        return None

    async def _invoke_assistant(
        self,
        message: GatewayMessage,
        user_id: str,
        db,
    ) -> GatewayResponse:
        """调用 IntelligentAssistantService 处理消息"""
        from app.services.intelligent_assistant_service import chat_with_assistant
        from core.gateway.session import SessionManager, build_session_key
        from core.tools.context import set_current_im_channel

        channel_type_str = (
            message.channel_type.value
            if hasattr(message.channel_type, "value")
            else str(message.channel_type)
        )
        session_key = build_session_key(user_id, channel_type_str, message.channel_id)
        session_manager = SessionManager(db)
        session = await session_manager.get_or_create(user_id, channel_type_str, message.channel_id)
        current_topic_id = ((session.get("context") or {}).get("current_topic_id") or "").strip() or None

        # 设置 IM 渠道上下文，供 assistant_ops 工具（如 trigger_stock_analysis）在
        # 创建后台任务时保存回调渠道信息，任务完成后可主动推送通知到此渠道
        set_current_im_channel(channel_type_str, message.channel_id)

        result = await chat_with_assistant(
            db=db,
            user_message=message.content,
            user_id=user_id,
            conversation_id=session_key,
            current_thread_id=current_topic_id,
            is_im=True,  # IM 渠道：注入移动端格式规范，LLM 避免输出表格和 Markdown
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
        """处理斜杠命令（/help 等）"""
        cmd = message.content.strip().lower()

        if cmd == "/help":
            help_text = (
                "📋 可用命令：\n"
                "/help — 显示帮助\n\n"
                "直接发送文字即可与分析助理对话，例如：\n"
                "• 分析贵州茅台\n"
                "• 上周分析过哪些股票\n"
                "• 查看我的股票关注列表\n"
                "• 当前主题是什么\n"
                "• 切换到新能源车研究"
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

        # 未知命令，当普通消息处理
        message.message_type = MessageType.TEXT
        return self._ack_response(platform), 200

    # ------------------------------------------------------------------ #
    # 主动推送（分析完成等事件通知）
    # ------------------------------------------------------------------ #

    async def send_im_notification(
        self, channel_type: str, channel_id: str, text: str
    ) -> bool:
        """主动向 IM 渠道推送文本消息（无需 msg_id，不依赖用户消息触发）

        Args:
            channel_type: 平台类型，如 "qq"、"feishu"
            channel_id:   平台侧会话 ID，如 "c2c:openid"、"group:group_openid"
            text:         纯文本内容

        Returns:
            True 表示发送成功，False 表示失败
        """
        adapter = self.get_adapter(channel_type)
        if not adapter:
            logger.warning("[Gateway] 平台 %s 没有注册适配器，无法发送 IM 通知", channel_type)
            return False

        response = GatewayResponse(
            channel_type=channel_type,
            channel_id=channel_id,
            response_type=ResponseType.TEXT,
            content=text,
            metadata={},  # 不带 msg_id → 主动推送
        )
        try:
            result = await adapter.send_response(response)
            if result:
                logger.info("[Gateway] ✅ IM 通知发送成功: %s/%s", channel_type, channel_id)
            else:
                logger.warning("[Gateway] IM 通知发送失败: %s/%s", channel_type, channel_id)
            return result
        except Exception as e:
            logger.exception("[Gateway] IM 通知发送异常: %s", e)
            return False

    # ------------------------------------------------------------------ #
    # WebSocket 模式管理
    # ------------------------------------------------------------------ #

    async def start_ws_client(self, config: Dict[str, Any], db):
        """启动 QQ WebSocket 客户端后台任务"""
        await self.stop_ws_client()  # 先停掉已有的

        from core.gateway.adapters.qq_ws import QQWebSocketClient
        from core.gateway.adapters.qq import QQAdapter

        # 确保 QQ 适配器已注册（用于发送回复）
        if "qq" not in self._adapters:
            adapter = QQAdapter(config=config)
            self.register_adapter(adapter)

        async def on_event(event_type: str, data: dict, raw: dict):
            await self._handle_ws_event(event_type, data, raw, db)

        self._ws_client = QQWebSocketClient(
            config=config,
            on_event=on_event,
            sandbox=config.get("sandbox", False),
        )
        self._ws_task = asyncio.create_task(self._ws_client.start())
        logger.info("[Gateway] QQ WebSocket 后台任务已启动")

    async def stop_ws_client(self):
        """停止 QQ WebSocket 客户端"""
        if self._ws_client:
            await self._ws_client.stop()
            self._ws_client = None
        if self._ws_task and not self._ws_task.done():
            self._ws_task.cancel()
            try:
                await self._ws_task
            except asyncio.CancelledError:
                pass
            self._ws_task = None
            logger.info("[Gateway] QQ WebSocket 后台任务已停止")

    @property
    def ws_running(self) -> bool:
        return self._ws_task is not None and not self._ws_task.done()

    async def _handle_ws_event(
        self, event_type: str, data: dict, raw: dict, db
    ):
        """处理从 WebSocket 收到的 Dispatch 事件"""
        adapter = self.get_adapter("qq")
        if not adapter:
            logger.warning("[Gateway] QQ 适配器未注册，无法处理 WS 事件")
            return

        # 复用 QQAdapter 的消息解析逻辑
        # 构造一个与 Webhook 相同格式的 payload 以复用 parse_message
        fake_body = json.dumps(raw).encode("utf-8")
        message = await adapter.parse_message({}, fake_body)
        if message is None:
            return

        # 命令处理
        if message.message_type == MessageType.COMMAND:
            await self._handle_command(message, adapter, db, "qq")
            if message.message_type == MessageType.COMMAND:
                return  # 命令已处理

        # 用户解析
        system_user_id = await self._resolve_user(db)
        if not system_user_id:
            logger.error("[Gateway] 系统中没有用户，无法处理 WS 消息")
            return

        # 调用助理
        response = await self._invoke_assistant(message, system_user_id, db)

        # 发送回复
        try:
            await adapter.send_response(response)
        except Exception as e:
            logger.exception("[Gateway] WS 消息回复失败: %s", e)


# 全局单例
gateway_router = GatewayRouter()


def get_gateway_router() -> GatewayRouter:
    """获取 GatewayRouter 全局单例"""
    return gateway_router

