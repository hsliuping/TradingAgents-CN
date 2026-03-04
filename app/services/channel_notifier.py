"""
渠道推送调度器 (ChannelNotifier)

核心职责：
1. 读取用户在 MongoDB `user_channel_configs` 中配置的渠道列表
2. 过滤：只推送启用的渠道 + 该渠道订阅了此 event_type 的渠道
3. 并发 fire-and-forget 发送，不阻塞调用方

集成点：NotificationsService.create_and_publish() 末尾调用 dispatch()
"""
import asyncio
import logging
import uuid
from typing import Any, Dict, List, Optional

from app.core.database import get_mongo_db
from app.models.channel_config import ChannelConfig, ChannelType
from app.utils.timezone import now_tz

logger = logging.getLogger("webapi.channel_notifier")

COLLECTION = "user_channel_configs"


class ChannelNotifier:
    """统一渠道推送调度器（单例）"""

    # -------------------------------------------------------------------------
    # MongoDB CRUD helpers
    # -------------------------------------------------------------------------

    async def get_channels(self, user_id: str) -> List[ChannelConfig]:
        """获取用户所有渠道配置"""
        db = get_mongo_db()
        doc = await db[COLLECTION].find_one({"user_id": user_id})
        if not doc:
            return []
        return [ChannelConfig(**ch) for ch in doc.get("channels", [])]

    async def save_channels(self, user_id: str, channels: List[ChannelConfig]) -> None:
        """保存用户渠道配置（覆盖写）"""
        db = get_mongo_db()
        await db[COLLECTION].update_one(
            {"user_id": user_id},
            {"$set": {
                "user_id": user_id,
                "channels": [ch.model_dump() for ch in channels],
                "updated_at": now_tz().isoformat(),
            }},
            upsert=True,
        )

    async def add_channel(self, user_id: str, channel: ChannelConfig) -> ChannelConfig:
        channels = await self.get_channels(user_id)
        channel.channel_id = str(uuid.uuid4())
        channel.created_at = now_tz().isoformat()
        channel.updated_at = channel.created_at
        channels.append(channel)
        await self.save_channels(user_id, channels)
        return channel

    async def update_channel(
        self, user_id: str, channel_id: str, updates: Dict[str, Any]
    ) -> Optional[ChannelConfig]:
        channels = await self.get_channels(user_id)
        for ch in channels:
            if ch.channel_id == channel_id:
                for k, v in updates.items():
                    if v is not None and hasattr(ch, k):
                        setattr(ch, k, v)
                ch.updated_at = now_tz().isoformat()
                await self.save_channels(user_id, channels)
                return ch
        return None

    async def delete_channel(self, user_id: str, channel_id: str) -> bool:
        channels = await self.get_channels(user_id)
        new_channels = [ch for ch in channels if ch.channel_id != channel_id]
        if len(new_channels) == len(channels):
            return False
        await self.save_channels(user_id, new_channels)
        return True

    # -------------------------------------------------------------------------
    # 核心推送逻辑
    # -------------------------------------------------------------------------

    async def dispatch(
        self,
        user_id: str,
        title: str,
        content: str,
        event_type: str = "system",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """
        调度推送到用户的所有匹配渠道（fire-and-forget）

        Args:
            user_id:    用户 ID
            title:      通知标题
            content:    通知内容
            event_type: 事件类型，见 channel_config.EVENT_TYPES
            metadata:   扩展元数据。若包含 _im_channel，则自动推送 QQ IM 通知
        """
        metadata = metadata or {}

        # ① QQ IM 自动回调渠道（由触发来源决定，无需用户手动配置）
        im_channel = metadata.get("_im_channel")
        if im_channel:
            asyncio.ensure_future(self._send_im_notification(im_channel, title, content))

        # ② 用户配置的外部渠道（飞书/钉钉/企微/邮件）
        try:
            channels = await self.get_channels(user_id)
        except Exception as e:
            logger.warning(f"获取渠道配置失败(忽略): {e}")
            return

        # 过滤：启用 + 订阅了该事件类型
        matched = [
            ch for ch in channels
            if ch.enabled and event_type in ch.events
        ]

        if not matched:
            return

        # 并发发送，错误不传播
        tasks = [self._send_one(ch, title, content) for ch in matched]
        await asyncio.gather(*tasks, return_exceptions=True)

    async def _send_one(self, channel: ChannelConfig, title: str, content: str) -> None:
        """向单个渠道发送，异常自动捕获"""
        try:
            if channel.type in (
                ChannelType.FEISHU, ChannelType.DINGTALK, ChannelType.WECHATWORK
            ):
                from app.services.channel_senders.webhook_sender import send_webhook
                await send_webhook(channel, title, content)

            elif channel.type == ChannelType.EMAIL:
                await self._send_email(channel, title, content)

        except Exception as e:
            logger.error(f"❌ 渠道推送异常 [{channel.name}]: {e}")

    async def _send_im_notification(
        self, im_channel: Dict[str, Any], title: str, content: str
    ) -> None:
        """通过 GatewayRouter 向 IM 频道主动推送通知（QQ / 飞书 Bot 等）"""
        try:
            from core.gateway.router import get_gateway_router
            gateway_router = get_gateway_router()
            if gateway_router is None:
                logger.warning("[ChannelNotifier] GatewayRouter 未初始化，跳过 IM 推送")
                return

            channel_type = im_channel.get("channel_type", "")
            channel_id = im_channel.get("channel_id", "")
            if not channel_type or not channel_id:
                logger.warning("[ChannelNotifier] _im_channel 格式不完整: %s", im_channel)
                return

            text = f"{title}\n{content}" if content else title
            logger.info("[ChannelNotifier] 推送 IM 通知: %s/%s", channel_type, channel_id)
            await gateway_router.send_im_notification(channel_type, channel_id, text)
        except Exception as e:
            logger.error("[ChannelNotifier] IM 推送失败: %s", e)

    async def _send_email(self, channel: ChannelConfig, title: str, content: str) -> None:
        """通过现有 EmailService 发送邮件渠道通知"""
        if not channel.email_address:
            logger.warning(f"邮件渠道 [{channel.name}] 未配置邮箱地址，跳过")
            return

        from app.services.email_service import get_email_service
        from app.models.email import EmailType

        email_service = get_email_service()
        smtp_config = await email_service.get_smtp_config()
        if not smtp_config:
            logger.debug("SMTP 未配置，跳过邮件渠道推送")
            return

        await email_service._send_smtp(
            to_email=channel.email_address,
            subject=f"[TradingAgents-CN] {title}",
            html_content=f"<p>{content}</p>",
            text_content=content,
            smtp_config=smtp_config,
        )
        logger.info(f"✅ 邮件渠道推送成功: [{channel.name}] -> {channel.email_address}")


# ---------------------------------------------------------------------------
# 单例
# ---------------------------------------------------------------------------
_channel_notifier: Optional[ChannelNotifier] = None


def get_channel_notifier() -> ChannelNotifier:
    global _channel_notifier
    if _channel_notifier is None:
        _channel_notifier = ChannelNotifier()
    return _channel_notifier

