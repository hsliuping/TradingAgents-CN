"""
Webhook 推送发送器

支持飞书、钉钉、企业微信三种 Webhook 机器人格式，
协议一致，只有 JSON body 格式略有差异。
"""
import asyncio
import logging
from typing import Any, Dict, Optional

import httpx

from app.models.channel_config import ChannelConfig, ChannelType

logger = logging.getLogger("webapi.channel_senders.webhook")

# HTTP 请求超时（秒）
WEBHOOK_TIMEOUT = 10


def _build_feishu_payload(title: str, content: str) -> Dict[str, Any]:
    """
    飞书自定义机器人消息格式
    https://open.feishu.cn/document/client-docs/bot-v3/add-custom-bot
    """
    return {
        "msg_type": "text",
        "content": {
            "text": f"【{title}】\n{content}"
        }
    }


def _build_dingtalk_payload(title: str, content: str) -> Dict[str, Any]:
    """
    钉钉自定义机器人消息格式
    https://open.dingtalk.com/document/robots/custom-robot-access
    """
    return {
        "msgtype": "text",
        "text": {
            "content": f"【{title}】\n{content}"
        }
    }


def _build_wechatwork_payload(title: str, content: str) -> Dict[str, Any]:
    """
    企业微信自定义机器人消息格式
    https://developer.work.weixin.qq.com/document/path/91770
    """
    return {
        "msgtype": "text",
        "text": {
            "content": f"【{title}】\n{content}"
        }
    }


_BUILDERS = {
    ChannelType.FEISHU: _build_feishu_payload,
    ChannelType.DINGTALK: _build_dingtalk_payload,
    ChannelType.WECHATWORK: _build_wechatwork_payload,
}


async def send_webhook(
    channel: ChannelConfig,
    title: str,
    content: str,
) -> bool:
    """
    发送 Webhook 通知

    Returns:
        True  — 发送成功
        False — 发送失败
    """
    if not channel.webhook_url:
        logger.warning(f"渠道 [{channel.name}] 未配置 Webhook URL，跳过")
        return False

    builder = _BUILDERS.get(channel.type)
    if not builder:
        logger.warning(f"未知渠道类型: {channel.type}，跳过")
        return False

    payload = builder(title, content)

    try:
        async with httpx.AsyncClient(timeout=WEBHOOK_TIMEOUT) as client:
            resp = await client.post(
                channel.webhook_url,
                json=payload,
                headers={"Content-Type": "application/json"},
            )
            resp.raise_for_status()
            result = resp.json()

            # 各平台成功标志不同，但 HTTP 2xx 已足够判断
            logger.info(
                f"✅ Webhook 推送成功: [{channel.name}({channel.type})] "
                f"status={resp.status_code}"
            )
            return True

    except httpx.TimeoutException:
        logger.warning(f"⚠️ Webhook 超时: [{channel.name}] url={channel.webhook_url}")
    except httpx.HTTPStatusError as e:
        logger.warning(
            f"⚠️ Webhook HTTP 错误: [{channel.name}] status={e.response.status_code} "
            f"body={e.response.text[:200]}"
        )
    except Exception as e:
        logger.error(f"❌ Webhook 推送失败: [{channel.name}] {e}")

    return False

