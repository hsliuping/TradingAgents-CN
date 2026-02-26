"""
渠道推送配置 API

提供飞书/钉钉/企业微信 Webhook + 邮件渠道的 CRUD 和测试推送接口。
端点前缀: /api/channel-configs
"""
import logging
from typing import List

from fastapi import APIRouter, Depends, HTTPException

from app.routers.auth_db import get_current_user
from app.models.channel_config import (
    ChannelConfig, ChannelConfigCreate, ChannelConfigUpdate, TestSendRequest
)
from app.services.channel_notifier import get_channel_notifier

logger = logging.getLogger("webapi.channel_configs")

router = APIRouter(prefix="/api/channel-configs", tags=["channel-configs"])


@router.get("", summary="获取我的渠道列表")
async def list_channels(user: dict = Depends(get_current_user)):
    """获取当前用户配置的所有推送渠道"""
    notifier = get_channel_notifier()
    channels = await notifier.get_channels(user["id"])
    return {"channels": [ch.model_dump() for ch in channels]}


@router.post("", summary="添加渠道")
async def create_channel(
    body: ChannelConfigCreate,
    user: dict = Depends(get_current_user),
):
    """添加一个新的推送渠道"""
    notifier = get_channel_notifier()

    # 邮件渠道必须有 email_address，Webhook 渠道必须有 webhook_url
    if body.type == "email":
        if not body.email_address:
            raise HTTPException(status_code=400, detail="邮件渠道必须提供接收邮箱地址")
    else:
        if not body.webhook_url:
            raise HTTPException(status_code=400, detail="Webhook 渠道必须提供 Webhook URL")

    channel = ChannelConfig(**body.model_dump())
    result = await notifier.add_channel(user["id"], channel)
    return {"channel": result.model_dump()}


@router.put("/{channel_id}", summary="更新渠道配置")
async def update_channel(
    channel_id: str,
    body: ChannelConfigUpdate,
    user: dict = Depends(get_current_user),
):
    """更新指定渠道的配置"""
    notifier = get_channel_notifier()
    updates = {k: v for k, v in body.model_dump().items() if v is not None}
    result = await notifier.update_channel(user["id"], channel_id, updates)
    if not result:
        raise HTTPException(status_code=404, detail="渠道不存在")
    return {"channel": result.model_dump()}


@router.delete("/{channel_id}", summary="删除渠道")
async def delete_channel(
    channel_id: str,
    user: dict = Depends(get_current_user),
):
    """删除指定渠道"""
    notifier = get_channel_notifier()
    ok = await notifier.delete_channel(user["id"], channel_id)
    if not ok:
        raise HTTPException(status_code=404, detail="渠道不存在")
    return {"success": True, "message": "渠道已删除"}


@router.post("/{channel_id}/test", summary="测试推送")
async def test_channel(
    channel_id: str,
    body: TestSendRequest = TestSendRequest(),
    user: dict = Depends(get_current_user),
):
    """向指定渠道发送一条测试消息"""
    notifier = get_channel_notifier()
    channels = await notifier.get_channels(user["id"])
    channel = next((ch for ch in channels if ch.channel_id == channel_id), None)
    if not channel:
        raise HTTPException(status_code=404, detail="渠道不存在")

    # 临时强制启用以测试
    original_enabled = channel.enabled
    channel.enabled = True
    # 发送（不走 dispatch 的事件过滤，直接 _send_one）
    await notifier._send_one(channel, body.title, body.content)
    channel.enabled = original_enabled

    return {"success": True, "message": f"测试消息已发送到渠道「{channel.name}」"}


@router.get("/event-types", summary="获取支持的事件类型")
async def get_event_types():
    """获取系统支持的推送事件类型列表"""
    from app.models.channel_config import EVENT_TYPES
    return {"event_types": EVENT_TYPES}

