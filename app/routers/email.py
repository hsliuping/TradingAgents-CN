"""
邮件通知 API 路由

[PRO功能] 此模块为专业版功能，需要专业版授权
- 支持分析完成后自动发送邮件通知
- 支持SMTP服务器配置
- 支持自定义邮件模板
"""

from fastapi import APIRouter, HTTPException, Query
from typing import Optional
from pydantic import BaseModel, Field

from app.core.config import settings
from app.core.database import get_mongo_db
from app.services.email_service import get_email_service
from app.models.email import EmailNotificationSettings, EmailSettingsUpdate
from app.core.response import ok, fail

router = APIRouter(prefix="/api/email", tags=["邮件通知"])

# 错误消息常量
MSG_INVALID_USER_ID = "无效的用户ID"
MSG_USER_NOT_FOUND = "用户不存在"


class SMTPConfigRequest(BaseModel):
    """SMTP配置请求"""
    enabled: bool = True
    host: str = Field(..., description="SMTP服务器地址")
    port: int = Field(default=587, description="SMTP端口")
    username: str = Field(..., description="SMTP用户名")
    password: str = Field(..., description="SMTP密码")
    from_email: str = Field(..., description="发件人邮箱")
    from_name: str = Field(default="TradingAgents-CN", description="发件人名称")
    use_tls: bool = Field(default=True, description="使用TLS")
    use_ssl: bool = Field(default=False, description="使用SSL")


@router.get("/config")
async def get_smtp_config():
    """获取SMTP配置状态（不返回密码）"""
    email_service = get_email_service()
    smtp_config = await email_service.get_smtp_config()

    if smtp_config:
        return ok({
            "enabled": True,
            "configured": True,
            "host": smtp_config.get("host", ""),
            "port": smtp_config.get("port", 587),
            "from_name": smtp_config.get("from_name", "TradingAgents-CN"),
            "from_email": smtp_config.get("from_email", ""),
            "username": smtp_config.get("username", ""),
            "use_tls": smtp_config.get("use_tls", True),
            "use_ssl": smtp_config.get("use_ssl", False),
            "source": smtp_config.get("source", "unknown")
        })
    else:
        return ok({
            "enabled": False,
            "configured": False,
            "host": "",
            "port": 587,
            "from_name": "TradingAgents-CN",
            "from_email": "",
            "username": "",
            "use_tls": True,
            "use_ssl": False,
            "source": None
        })


@router.put("/config")
async def update_smtp_config(config: SMTPConfigRequest):
    """更新SMTP配置"""
    email_service = get_email_service()

    config_dict = config.model_dump()
    await email_service.save_smtp_config(config_dict)

    return ok({"message": "SMTP配置已保存"})


@router.post("/config/test")
async def test_smtp_config(config: SMTPConfigRequest):
    """测试SMTP连接"""
    email_service = get_email_service()

    result = await email_service.test_smtp_connection(config.model_dump())

    if result.get("success"):
        return ok({"message": result.get("message", "连接成功")})
    else:
        return fail(result.get("message", "连接失败"))


@router.get("/settings/{user_id}")
async def get_email_settings(user_id: str):
    """获取用户邮件通知设置"""
    db = get_mongo_db()
    from bson import ObjectId

    email_service = get_email_service()
    smtp_config = await email_service.get_smtp_config()

    try:
        user = await db.users.find_one({"_id": ObjectId(user_id)})
    except Exception:
        return fail(MSG_INVALID_USER_ID)

    if not user:
        return fail(MSG_USER_NOT_FOUND)

    preferences = user.get("preferences", {})
    email_settings = preferences.get("email_notifications", {})

    # 确保 email_settings 是字典类型
    if not isinstance(email_settings, dict):
        email_settings = {}

    # 如果没有设置，返回默认值
    if not email_settings:
        email_settings = EmailNotificationSettings().model_dump()

    # 如果没有设置接收邮箱，使用注册邮箱
    if not email_settings.get("email_address"):
        email_settings["email_address"] = user.get("email", "")

    return ok({
        "settings": email_settings,
        "smtp_enabled": smtp_config is not None,
        "user_email": user.get("email", "")
    })


@router.put("/settings/{user_id}")
async def update_email_settings(user_id: str, update: EmailSettingsUpdate):
    """更新用户邮件通知设置"""
    db = get_mongo_db()
    from bson import ObjectId

    try:
        user = await db.users.find_one({"_id": ObjectId(user_id)})
    except Exception:
        return fail(MSG_INVALID_USER_ID)

    if not user:
        return fail(MSG_USER_NOT_FOUND)

    # 获取当前设置
    preferences = user.get("preferences", {})
    current_settings = preferences.get("email_notifications", {})

    # 确保 current_settings 是字典类型
    if not isinstance(current_settings, dict):
        current_settings = {}

    # 合并更新
    update_dict = update.model_dump(exclude_unset=True)
    new_settings = {**current_settings, **update_dict}
    
    # 更新数据库
    await db.users.update_one(
        {"_id": ObjectId(user_id)},
        {"$set": {"preferences.email_notifications": new_settings}}
    )
    
    return ok({"message": "邮件设置已更新", "settings": new_settings})


@router.post("/test/{user_id}")
async def send_test_email(user_id: str):
    """发送测试邮件"""
    email_service = get_email_service()

    # 检查 SMTP 是否配置
    smtp_config = await email_service.get_smtp_config()
    if not smtp_config:
        return fail("邮件功能未启用，请先配置 SMTP 设置")

    # 确保测试邮件类型已启用
    db = get_mongo_db()
    from bson import ObjectId

    try:
        user = await db.users.find_one({"_id": ObjectId(user_id)})
    except Exception:
        return fail(MSG_INVALID_USER_ID)

    if not user:
        return fail(MSG_USER_NOT_FOUND)

    # 临时启用邮件功能进行测试
    preferences = user.get("preferences", {})
    email_settings = preferences.get("email_notifications", {})

    # 确保 email_settings 是字典类型
    if not isinstance(email_settings, dict):
        email_settings = {}

    was_enabled = email_settings.get("enabled", False)

    if not was_enabled:
        # 如果未启用，临时启用进行测试
        await db.users.update_one(
            {"_id": ObjectId(user_id)},
            {"$set": {"preferences.email_notifications.enabled": True}}
        )

    try:
        result = await email_service.send_test_email(user_id)

        if result:
            return ok({"message": "测试邮件已发送，请检查邮箱"})
        else:
            return fail("邮件发送失败，请检查SMTP配置和网络连接")
    finally:
        # 恢复原始设置
        if not was_enabled:
            await db.users.update_one(
                {"_id": ObjectId(user_id)},
                {"$set": {"preferences.email_notifications.enabled": False}}
            )


@router.get("/history/{user_id}")
async def get_email_history(
    user_id: str,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100)
):
    """获取邮件发送历史"""
    email_service = get_email_service()
    result = await email_service.get_email_history(user_id, page, page_size)
    return ok(result)

