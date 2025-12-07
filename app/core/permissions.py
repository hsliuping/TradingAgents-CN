"""
权限检查依赖

提供 FastAPI 路由权限检查的依赖函数
"""

import logging
from typing import Optional
from fastapi import Depends, HTTPException, Header, status
from bson import ObjectId

from app.core.database import get_mongo_db
from app.routers.auth_db import get_current_user
from app.services.license_service import get_license_service, LicenseInfo

logger = logging.getLogger("app.core.permissions")


async def get_app_token(
    x_app_token: Optional[str] = Header(None, alias="X-App-Token")
) -> Optional[str]:
    """从请求头获取 App Token"""
    return x_app_token


async def get_license_info(
    app_token: Optional[str] = Depends(get_app_token),
    user: dict = Depends(get_current_user)
) -> LicenseInfo:
    """
    获取用户的授权信息
    
    优先级:
    1. 请求头中的 X-App-Token
    2. 用户数据库中保存的 app_token
    """
    license_service = get_license_service()
    
    # 优先使用请求头中的 token
    token = app_token
    
    # 如果请求头没有，尝试从用户数据库获取
    if not token:
        db = get_mongo_db()
        user_id = str(user.get("id", ""))
        user_doc = await db.users.find_one({"_id": ObjectId(user_id)})
        if user_doc:
            token = user_doc.get("app_token")
    
    # 如果没有 token，返回免费用户信息
    if not token:
        logger.debug("📝 用户未配置 App Token，使用免费版")
        return LicenseInfo(
            email=user.get("email", ""),
            plan="free",
            is_valid=True,
            error_message=None
        )
    
    # 验证 token
    license_info = await license_service.verify_app_token(token)
    return license_info


async def require_pro(
    license_info: LicenseInfo = Depends(get_license_info)
) -> LicenseInfo:
    """
    要求 PRO 权限的依赖
    
    使用方式:
        @router.get("/pro-feature")
        async def pro_feature(license: LicenseInfo = Depends(require_pro)):
            ...
    """
    license_service = get_license_service()
    
    if not license_service.is_pro(license_info):
        logger.warning(f"❌ 初级学员尝试访问高级功能: {license_info.email}")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "code": "ADVANCED_REQUIRED",
                "message": "此功能为高级学员专属",
                "plan": license_info.plan,
                "upgrade_url": "/settings/license"
            }
        )
    
    return license_info


def require_feature(feature: str):
    """
    要求特定功能的依赖工厂
    
    使用方式:
        @router.get("/special-feature")
        async def special_feature(license: LicenseInfo = Depends(require_feature("special"))):
            ...
    """
    async def _check_feature(
        license_info: LicenseInfo = Depends(get_license_info)
    ) -> LicenseInfo:
        license_service = get_license_service()
        
        if not license_service.has_feature(license_info, feature):
            logger.warning(f"❌ 用户缺少功能权限: {license_info.email}, feature={feature}")
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "code": "FEATURE_REQUIRED",
                    "message": f"此功能需要 '{feature}' 权限",
                    "feature": feature,
                    "plan": license_info.plan
                }
            )
        
        return license_info
    
    return _check_feature


# PRO 功能列表
PRO_FEATURES = [
    "email_notification",      # 邮件通知
    "watchlist_groups",        # 自选股分组
    "scheduled_analysis",      # 定时分析
    "portfolio_analysis",      # 持仓分析
    "trade_review",            # 操作复盘
    "advanced_screening",      # 高级选股
    "batch_analysis",          # 批量分析
    "export_reports",          # 导出报告
]

