"""
授权验证 API 路由

提供 App Token 验证和授权信息查询接口
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from typing import Optional
from pydantic import BaseModel, Field
import logging

from app.core.database import get_mongo_db
from app.core.response import ok, fail
from app.routers.auth_db import get_current_user
from app.services.license_service import get_license_service, LicenseInfo
from bson import ObjectId

logger = logging.getLogger("app.routers.license")

router = APIRouter(prefix="/api/license", tags=["授权管理"])


class VerifyTokenRequest(BaseModel):
    """验证 Token 请求"""
    token: str = Field(..., description="App Token")
    device_id: Optional[str] = Field(None, description="设备ID")
    app_version: Optional[str] = Field(None, description="应用版本")


class SaveTokenRequest(BaseModel):
    """保存 Token 请求"""
    token: str = Field(..., description="App Token")


@router.post("/verify")
async def verify_license(
    request: VerifyTokenRequest,
    user: dict = Depends(get_current_user)
):
    """
    验证 App Token 并返回授权信息
    
    此接口不需要 PRO 权限，用于验证 token 是否有效
    """
    license_service = get_license_service()
    
    license_info = await license_service.verify_app_token(
        token=request.token,
        device_id=request.device_id,
        app_version=request.app_version
    )
    
    return ok({
        "email": license_info.email,
        "plan": license_info.plan,
        "features": license_info.features,
        "device_registered": license_info.device_registered,
        "is_valid": license_info.is_valid,
        "error_message": license_info.error_message,
        "trial_end_at": license_info.trial_end_at,
        "pro_expire_at": license_info.pro_expire_at
    })


@router.post("/save-token")
async def save_app_token(
    request: SaveTokenRequest,
    user: dict = Depends(get_current_user)
):
    """
    保存 App Token 到用户账户
    
    先验证 token 有效性，再保存到数据库
    """
    license_service = get_license_service()
    
    # 验证 token
    license_info = await license_service.verify_app_token(request.token)
    
    if not license_info.is_valid:
        return fail(f"Token 验证失败: {license_info.error_message}")
    
    # 保存到用户数据库
    db = get_mongo_db()
    user_id = str(user["id"])
    
    try:
        await db.users.update_one(
            {"_id": ObjectId(user_id)},
            {
                "$set": {
                    "app_token": request.token,
                    "license_plan": license_info.plan,
                    "license_email": license_info.email
                }
            }
        )
        
        logger.info(f"✅ 用户 {user_id} 保存了 App Token (plan={license_info.plan})")
        
        return ok({
            "message": "Token 保存成功",
            "plan": license_info.plan,
            "email": license_info.email,
            "features": license_info.features
        })
    except Exception as e:
        logger.error(f"❌ 保存 Token 失败: {e}")
        return fail("保存失败，请重试")


@router.delete("/token")
async def delete_app_token(user: dict = Depends(get_current_user)):
    """删除用户的 App Token"""
    db = get_mongo_db()
    user_id = str(user["id"])
    
    try:
        await db.users.update_one(
            {"_id": ObjectId(user_id)},
            {
                "$unset": {
                    "app_token": "",
                    "license_plan": "",
                    "license_email": ""
                }
            }
        )
        
        # 清除缓存
        license_service = get_license_service()
        license_service.clear_cache()
        
        logger.info(f"✅ 用户 {user_id} 删除了 App Token")
        return ok({"message": "Token 已删除"})
    except Exception as e:
        logger.error(f"❌ 删除 Token 失败: {e}")
        return fail("删除失败，请重试")


@router.get("/status")
async def get_license_status(
    user: dict = Depends(get_current_user),
    force_refresh: bool = Query(False, description="是否强制刷新（跳过缓存）")
):
    """
    获取当前用户的授权状态

    Args:
        force_refresh: 是否强制刷新（跳过缓存）
    """
    db = get_mongo_db()
    user_id = str(user["id"])

    logger.info(f"📋 获取授权状态: user_id={user_id}, force_refresh={force_refresh}")

    # 从数据库获取用户的 token
    user_doc = await db.users.find_one({"_id": ObjectId(user_id)})

    if not user_doc or not user_doc.get("app_token"):
        logger.info(f"📋 用户 {user_id} 没有配置 App Token")
        return ok({
            "has_token": False,
            "plan": "free",
            "is_valid": True,
            "message": "未配置 App Token，使用免费版"
        })

    # 验证 token（强制刷新时跳过缓存）
    license_service = get_license_service()

    # 如果强制刷新，先清除缓存
    if force_refresh:
        license_service.clear_cache(user_doc["app_token"])
        logger.info("🔄 强制刷新：已清除 token 缓存")

    license_info = await license_service.verify_app_token(
        user_doc["app_token"],
        use_cache=not force_refresh  # force_refresh=True 时不使用缓存
    )

    logger.info(f"📋 授权验证结果: email={license_info.email}, plan={license_info.plan}, offline={license_info.offline_mode}")

    return ok({
        "has_token": True,
        "plan": license_info.plan,
        "email": license_info.email,
        "features": license_info.features,
        "is_valid": license_info.is_valid,
        "error_message": license_info.error_message,
        "trial_end_at": license_info.trial_end_at,
        "pro_expire_at": license_info.pro_expire_at,
        "offline_mode": license_info.offline_mode  # 新增：是否离线模式
    })

