"""
权限检查依赖

提供 FastAPI 路由权限检查的依赖函数
"""

import logging
from typing import Optional
from fastapi import Depends, HTTPException, Header, status
from bson import ObjectId

from app.core.database import get_mongo_db
from app.core.jdyun import is_jdyun_mode
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

    Args:
        app_token: 请求头中的 App Token
        user: 当前用户信息

    注意：设备ID由后端基于硬件信息自动生成，用户无法获取或复制
    """
    # 🔧 京东云模式：跳过 License 验证，直接返回 PRO 权限
    if is_jdyun_mode():
        return LicenseInfo(
            email=user.get("email", ""),
            plan="pro",
            is_valid=True,
            error_message=None,
            features=[]
        )

    # 🔧 开发模式：DEBUG=True 且 LICENSE_SKIP_PRO_CHECK=true 时直接返回 PRO 权限，
    # 方便本地开发测试 PRO 功能（工作流、高级课程等）。
    # 生产环境（DEBUG=False）即使误设该开关也不会生效，保证 License 校验不被绕过。
    from app.core.config import settings
    if settings.DEBUG and settings.LICENSE_SKIP_PRO_CHECK:
        logger.debug("🔓 开发模式：跳过 License 校验，直接授予 PRO 权限 (%s)", user.get("email", ""))
        return LicenseInfo(
            email=user.get("email", ""),
            plan="pro",
            is_valid=True,
            error_message=None,
            features=[]
        )

    license_service = get_license_service()
    user_doc = None
    auth_server = None
    
    # 优先使用请求头中的 token
    token = app_token
    
    # 如果请求头没有，尝试从用户数据库获取
    if not token:
        db = get_mongo_db()
        user_id = str(user.get("id", ""))
        user_doc = await db.users.find_one({"_id": ObjectId(user_id)})
        if user_doc:
            token = user_doc.get("app_token")
            auth_server = user_doc.get("license_server")
    else:
        db = get_mongo_db()
        user_id = str(user.get("id", ""))
        user_doc = await db.users.find_one({"_id": ObjectId(user_id)})
        if user_doc:
            auth_server = user_doc.get("license_server")
    
    # 如果没有 token，返回免费用户信息
    if not token:
        logger.debug("📝 用户未配置 App Token，使用免费版")
        return LicenseInfo(
            email=user.get("email", ""),
            plan="free",
            is_valid=True,
            error_message=None
        )
    
    # 验证 token（设备ID由后端自动生成）
    license_info = await license_service.verify_app_token(token, auth_server=auth_server)
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


# 高级学员功能列表
PRO_FEATURES = [
    "advanced_courses",       # 高级学员课程
    "email_notification",      # 邮件通知
    "watchlist_groups",        # 股票关注列表分组
    "scheduled_analysis",      # 定时分析
    "batch_analysis",          # 批量分析
    "export_reports",          # 导出报告
    "trading_plan_check",      # 交易计划一致性检查
    "workflow",                # 分析流
    "workflow_tools",          # 配置Tools
    "workflow_agents",         # 配置Agent
    "prompt_templates",        # 提示词模板
]

