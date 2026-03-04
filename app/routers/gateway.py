"""
Gateway Webhook 路由

接收 IM 平台（飞书/QQ/钉钉）的 Webhook 回调，
委托 GatewayRouter 进行签名验证、消息解析、助理调用、回复发送。

端点: POST /api/gateway/{platform}
"""

import logging

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from app.core.database import get_mongo_db
from core.gateway.router import gateway_router

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/gateway", tags=["gateway"])


@router.post("/{platform}")
async def gateway_webhook(platform: str, request: Request):
    """
    IM 平台 Webhook 回调统一入口

    - 飞书: POST /api/gateway/feishu
    - QQ:   POST /api/gateway/qq
    - 钉钉: POST /api/gateway/dingtalk
    """
    body = await request.body()
    headers = dict(request.headers)

    db = await get_mongo_db()

    resp_json, status_code = await gateway_router.handle_webhook(
        platform=platform,
        headers=headers,
        body=body,
        db=db,
    )

    return JSONResponse(content=resp_json, status_code=status_code)


@router.get("/platforms")
async def list_supported_platforms():
    """列出当前已注册的 IM 平台适配器"""
    return {
        "platforms": gateway_router.supported_platforms,
    }

