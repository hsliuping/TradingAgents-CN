"""
基于数据库的认证路由 - 改进版
替代原有的基于配置文件的认证机制
"""

import time
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Header, Request
from pydantic import BaseModel

from app.services.auth_service import AuthService
from app.services.user_service import user_service
from app.services.session_service import get_session_service
from app.models.user import UserCreate, UserUpdate
from app.services.operation_log_service import log_operation
from app.models.operation_log import ActionType

# 尝试导入日志管理器
try:
    from tradingagents.utils.logging_manager import get_logger
except ImportError:
    # 如果导入失败，使用标准日志
    import logging
    def get_logger(name: str) -> logging.Logger:
        return logging.getLogger(name)

logger = get_logger('auth_db')

# 统一响应格式
class ApiResponse(BaseModel):
    success: bool = True
    data: dict = {}
    message: str = ""

router = APIRouter()

class LoginRequest(BaseModel):
    username: str
    password: str

class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    user: dict

class RefreshTokenRequest(BaseModel):
    refresh_token: str

class RefreshTokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int

class ChangePasswordRequest(BaseModel):
    old_password: str
    new_password: str

class ResetPasswordRequest(BaseModel):
    username: str
    new_password: str

class CreateUserRequest(BaseModel):
    username: str
    email: str
    password: str
    is_admin: bool = False

async def get_current_user(
    request: Request,
    authorization: Optional[str] = Header(default=None)
) -> dict:
    """
    获取当前用户信息（混合认证）

    支持两种认证方式：
    1. JWT Token（优先）- 用于 API 调用
    2. Session Cookie（回退）- 用于 Web 前端
    """
    logger.debug(f"🔐 认证检查开始")

    # 方式 1: JWT Token 认证（优先）
    if authorization and authorization.lower().startswith("bearer "):
        logger.debug(f"📋 使用 JWT Token 认证")

        token = authorization.split(" ", 1)[1]
        logger.debug(f"🎫 Token长度: {len(token)}")

        token_data = AuthService.verify_token(token)

        if token_data:
            # 验证 session（如果 token 中包含 session_id）
            if token_data.session_id:
                session_service = get_session_service()
                session = session_service.verify_session(token_data.session_id, update_activity=True)

                if not session:
                    logger.warning(f"❌ JWT Session 无效或已过期: {token_data.session_id[:16]}...")
                    raise HTTPException(status_code=401, detail="Session expired or invalid")

                logger.debug(f"✅ JWT Session 验证成功: {token_data.session_id[:16]}...")

            # 从数据库获取用户信息
            user = await user_service.get_user_by_username(token_data.sub)
            if user and user.is_active:
                logger.debug(f"✅ JWT 认证成功，用户: {token_data.sub}")
                return {
                    "id": str(user.id),
                    "username": user.username,
                    "email": user.email,
                    "name": user.username,
                    "is_admin": user.is_admin,
                    "roles": ["admin"] if user.is_admin else ["user"],
                    "preferences": user.preferences.model_dump() if user.preferences else {}
                }

    # 方式 2: Session Cookie 认证（回退）
    user_id = request.session.get("user_id")
    if user_id:
        logger.debug(f"📋 使用 Session Cookie 认证: user_id={user_id}")

        user = await user_service.get_user_by_id(user_id)
        if user and user.is_active:
            logger.debug(f"✅ Session 认证成功，用户: {user.username}")
            return {
                "id": str(user.id),
                "username": user.username,
                "email": user.email,
                "name": user.username,
                "is_admin": user.is_admin,
                "roles": ["admin"] if user.is_admin else ["user"],
                "preferences": user.preferences.model_dump() if user.preferences else {}
            }
        else:
            logger.warning(f"❌ Session 中的用户不存在或已禁用: {user_id}")
            # 清除无效的 session
            request.session.clear()

    # 两种方式都失败
    logger.warning(f"❌ 认证失败：没有有效的 JWT Token 或 Session Cookie (路径: {request.url.path if hasattr(request, 'url') else 'unknown'})")
    raise HTTPException(status_code=401, detail="未登录或登录已过期")

@router.post("/login")
async def login(payload: LoginRequest, request: Request):
    """用户登录"""
    start_time = time.time()

    # 获取客户端信息
    ip_address = request.client.host if request.client else "unknown"
    user_agent = request.headers.get("user-agent", "")

    logger.info(f"🔐 登录请求 - 用户名: {payload.username}, IP: {ip_address}")

    try:
        # 验证输入
        if not payload.username or not payload.password:
            logger.warning(f"❌ 登录失败 - 用户名或密码为空")
            await log_operation(
                user_id="unknown",
                username=payload.username or "unknown",
                action_type=ActionType.USER_LOGIN,
                action="用户登录",
                details={"reason": "用户名和密码不能为空"},
                success=False,
                error_message="用户名和密码不能为空",
                duration_ms=int((time.time() - start_time) * 1000),
                ip_address=ip_address,
                user_agent=user_agent
            )
            raise HTTPException(status_code=400, detail="用户名和密码不能为空")

        logger.info(f"🔍 开始认证用户: {payload.username}")

        # 使用数据库认证
        user = await user_service.authenticate_user(payload.username, payload.password)

        logger.info(f"🔍 认证结果: user={'存在' if user else '不存在'}")

        if not user:
            logger.warning(f"❌ 登录失败 - 用户名或密码错误: {payload.username}")
            await log_operation(
                user_id="unknown",
                username=payload.username,
                action_type=ActionType.USER_LOGIN,
                action="用户登录",
                details={"reason": "用户名或密码错误"},
                success=False,
                error_message="用户名或密码错误",
                duration_ms=int((time.time() - start_time) * 1000),
                ip_address=ip_address,
                user_agent=user_agent
            )
            raise HTTPException(status_code=401, detail="用户名或密码错误")

        # 方式 1: 设置 Session Cookie（用于 Web 前端）
        request.session["user_id"] = str(user.id)
        request.session["username"] = user.username
        request.session["is_admin"] = user.is_admin
        logger.info(f"✅ Session Cookie 已设置: user_id={user.id}")

        # 方式 2: 创建 JWT Session（用于 API 调用）
        session_service = get_session_service()
        session_id = session_service.create_session(
            user_id=str(user.id),
            ip_address=ip_address,
            user_agent=user_agent,
            expires_in_seconds=60 * 60  # 1 小时
        )

        # 生成 JWT token（包含 session_id）
        token = AuthService.create_access_token(sub=user.username, session_id=session_id)

        # refresh_token 也需要 session（7天有效期）
        refresh_session_id = session_service.create_session(
            user_id=str(user.id),
            ip_address=ip_address,
            user_agent=user_agent,
            expires_in_seconds=60*60*24*7  # 7天
        )
        refresh_token = AuthService.create_access_token(
            sub=user.username,
            expires_delta=60*60*24*7,
            session_id=refresh_session_id
        )

        # 记录登录成功日志
        await log_operation(
            user_id=str(user.id),
            username=user.username,
            action_type=ActionType.USER_LOGIN,
            action="用户登录",
            details={
                "login_method": "password",
                "jwt_session_id": session_id,
                "has_cookie_session": True
            },
            success=True,
            duration_ms=int((time.time() - start_time) * 1000),
            ip_address=ip_address,
            user_agent=user_agent
        )

        return {
            "success": True,
            "data": {
                "access_token": token,
                "refresh_token": refresh_token,
                "expires_in": 60 * 60,
                "user": {
                    "id": str(user.id),
                    "username": user.username,
                    "email": user.email,
                    "name": user.username,
                    "is_admin": user.is_admin
                }
            },
            "message": "登录成功"
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ 登录异常: {e}")
        await log_operation(
            user_id="unknown",
            username=payload.username or "unknown",
            action_type=ActionType.USER_LOGIN,
            action="用户登录",
            details={"error": str(e)},
            success=False,
            error_message=f"系统错误: {str(e)}",
            duration_ms=int((time.time() - start_time) * 1000),
            ip_address=ip_address,
            user_agent=user_agent
        )
        raise HTTPException(status_code=500, detail="登录过程中发生系统错误")

@router.post("/refresh")
async def refresh_token(payload: RefreshTokenRequest):
    """刷新访问令牌"""
    try:
        logger.debug(f"🔄 收到refresh token请求")
        logger.debug(f"📝 Refresh token长度: {len(payload.refresh_token) if payload.refresh_token else 0}")

        if not payload.refresh_token:
            logger.warning("❌ Refresh token为空")
            raise HTTPException(status_code=401, detail="Refresh token is required")

        # 验证refresh token
        token_data = AuthService.verify_token(payload.refresh_token)
        logger.debug(f"🔍 Token验证结果: {token_data is not None}")

        if not token_data:
            logger.warning("❌ Refresh token验证失败")
            raise HTTPException(status_code=401, detail="Invalid refresh token")

        # 验证 refresh token 的 session
        if token_data.session_id:
            session_service = get_session_service()
            session = session_service.verify_session(token_data.session_id, update_activity=False)

            if not session:
                logger.warning(f"❌ Refresh token 的 session 无效: {token_data.session_id[:16]}...")
                raise HTTPException(status_code=401, detail="Refresh token session expired")

        # 验证用户是否仍然存在且激活
        user = await user_service.get_user_by_username(token_data.sub)
        if not user or not user.is_active:
            logger.warning(f"❌ 用户不存在或已禁用: {token_data.sub}")
            raise HTTPException(status_code=401, detail="User not found or inactive")

        logger.debug(f"✅ Token验证成功，用户: {token_data.sub}")

        # 创建新的 session
        session_service = get_session_service()
        new_session_id = session_service.create_session(
            user_id=str(user.id),
            expires_in_seconds=60 * 60  # 1 小时
        )

        # 创建新的 refresh session
        new_refresh_session_id = session_service.create_session(
            user_id=str(user.id),
            expires_in_seconds=60*60*24*7  # 7天
        )

        # 生成新的tokens（包含新的 session_id）
        new_token = AuthService.create_access_token(sub=token_data.sub, session_id=new_session_id)
        new_refresh_token = AuthService.create_access_token(
            sub=token_data.sub,
            expires_delta=60*60*24*7,
            session_id=new_refresh_session_id
        )

        logger.debug(f"🎉 新token生成成功")

        return {
            "success": True,
            "data": {
                "access_token": new_token,
                "refresh_token": new_refresh_token,
                "expires_in": 60 * 60
            },
            "message": "Token刷新成功"
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Refresh token处理异常: {str(e)}")
        raise HTTPException(status_code=401, detail=f"Token refresh failed: {str(e)}")

@router.post("/logout")
async def logout(request: Request, authorization: Optional[str] = Header(default=None), user: dict = Depends(get_current_user)):
    """
    用户登出（混合方式）

    同时清除：
    1. Session Cookie（Web 前端）
    2. JWT Session（API 调用）
    """
    start_time = time.time()

    # 获取客户端信息
    ip_address = request.client.host if request.client else "unknown"
    user_agent = request.headers.get("user-agent", "")

    try:
        # 方式 1: 清除 Session Cookie
        request.session.clear()
        logger.info(f"✅ Session Cookie 已清除: user={user['username']}")

        # 方式 2: 撤销 JWT Session
        if authorization and authorization.lower().startswith("bearer "):
            token = authorization.split(" ", 1)[1]
            token_data = AuthService.verify_token(token)

            if token_data and token_data.session_id:
                session_service = get_session_service()
                session_service.revoke_session(token_data.session_id)
                logger.info(f"✅ JWT Session 已撤销: user={user['username']}, session_id={token_data.session_id[:16]}...")

        # 记录登出日志
        await log_operation(
            user_id=user["id"],
            username=user["username"],
            action_type=ActionType.USER_LOGOUT,
            action="用户登出",
            details={"logout_method": "manual"},
            success=True,
            duration_ms=int((time.time() - start_time) * 1000),
            ip_address=ip_address,
            user_agent=user_agent
        )

        return {
            "success": True,
            "data": {},
            "message": "登出成功"
        }
    except Exception as e:
        logger.error(f"记录登出日志失败: {e}")
        return {
            "success": True,
            "data": {},
            "message": "登出成功"
        }

@router.get("/me")
async def me(user: dict = Depends(get_current_user)):
    """获取当前用户信息"""
    return {
        "success": True,
        "data": user,
        "message": "获取用户信息成功"
    }

@router.put("/me")
async def update_me(
    payload: dict,
    user: dict = Depends(get_current_user)
):
    """更新当前用户信息"""
    try:
        from app.models.user import UserUpdate, UserPreferences

        # 构建更新数据
        update_data = {}

        # 更新邮箱
        if "email" in payload:
            update_data["email"] = payload["email"]

        # 更新偏好设置（支持部分更新）
        if "preferences" in payload:
            # 获取当前偏好
            current_prefs = user.get("preferences", {})

            # 合并新的偏好设置
            merged_prefs = {**current_prefs, **payload["preferences"]}

            # 创建 UserPreferences 对象
            update_data["preferences"] = UserPreferences(**merged_prefs)

        # 如果有语言设置，更新到偏好中
        if "language" in payload:
            if "preferences" not in update_data:
                # 获取当前偏好
                current_prefs = user.get("preferences", {})
                update_data["preferences"] = UserPreferences(**current_prefs)
            update_data["preferences"].language = payload["language"]

        # 如果有时区设置，更新到偏好中（如果需要）
        # 注意：时区通常是系统级设置，不是用户级设置

        # 调用服务更新用户
        user_update = UserUpdate(**update_data)
        updated_user = await user_service.update_user(user["username"], user_update)

        if not updated_user:
            raise HTTPException(status_code=400, detail="更新失败，邮箱可能已被使用")

        # 返回更新后的用户信息
        return {
            "success": True,
            "data": updated_user.model_dump(by_alias=True),
            "message": "用户信息更新成功"
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"更新用户信息失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"更新用户信息失败: {str(e)}")

@router.post("/change-password")
async def change_password(
    payload: ChangePasswordRequest,
    request: Request,
    user: dict = Depends(get_current_user)
):
    """
    修改密码（混合方式）

    修改密码后：
    1. 清除 Session Cookie（Web 前端）
    2. 撤销所有 JWT Session（API 调用）
    强制用户重新登录
    """
    try:
        # 使用数据库服务修改密码
        success = await user_service.change_password(
            user["username"],
            payload.old_password,
            payload.new_password
        )

        if not success:
            raise HTTPException(status_code=400, detail="旧密码错误")

        # 方式 1: 清除 Session Cookie
        request.session.clear()
        logger.info(f"✅ Session Cookie 已清除: user={user['username']}")

        # 方式 2: 撤销用户的所有 JWT Session
        session_service = get_session_service()
        revoked_count = session_service.revoke_all_user_sessions(user["id"])
        logger.info(f"✅ 密码修改成功，撤销了 {revoked_count} 个 JWT Session: user={user['username']}")

        return {
            "success": True,
            "data": {},
            "message": "密码修改成功，请重新登录"
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"修改密码失败: {e}")
        raise HTTPException(status_code=500, detail=f"修改密码失败: {str(e)}")

@router.post("/reset-password")
async def reset_password(
    payload: ResetPasswordRequest,
    request: Request,
    user: dict = Depends(get_current_user)
):
    """重置密码（管理员操作）"""
    try:
        # 检查权限
        if not user.get("is_admin", False):
            raise HTTPException(status_code=403, detail="权限不足")

        # 重置密码
        success = await user_service.reset_password(payload.username, payload.new_password)
        
        if not success:
            raise HTTPException(status_code=404, detail="用户不存在")

        return {
            "success": True,
            "data": {},
            "message": f"用户 {payload.username} 的密码已重置"
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"重置密码失败: {e}")
        raise HTTPException(status_code=500, detail=f"重置密码失败: {str(e)}")

@router.post("/create-user")
async def create_user(
    payload: CreateUserRequest,
    request: Request,
    user: dict = Depends(get_current_user)
):
    """创建用户（管理员操作）"""
    try:
        # 检查权限
        if not user.get("is_admin", False):
            raise HTTPException(status_code=403, detail="权限不足")

        # 创建用户
        user_create = UserCreate(
            username=payload.username,
            email=payload.email,
            password=payload.password
        )
        
        new_user = await user_service.create_user(user_create)
        
        if not new_user:
            raise HTTPException(status_code=400, detail="用户名或邮箱已存在")

        # 如果需要设置为管理员
        if payload.is_admin:
            from pymongo import MongoClient
            from app.core.config import settings
            client = MongoClient(settings.MONGO_URI)
            db = client[settings.MONGO_DB]
            db.users.update_one(
                {"username": payload.username},
                {"$set": {"is_admin": True}}
            )

        return {
            "success": True,
            "data": {
                "id": str(new_user.id),
                "username": new_user.username,
                "email": new_user.email,
                "is_admin": payload.is_admin
            },
            "message": f"用户 {payload.username} 创建成功"
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"创建用户失败: {e}")
        raise HTTPException(status_code=500, detail=f"创建用户失败: {str(e)}")

@router.get("/users")
async def list_users(
    skip: int = 0,
    limit: int = 100,
    user: dict = Depends(get_current_user)
):
    """获取用户列表（管理员操作）"""
    try:
        # 检查权限
        if not user.get("is_admin", False):
            raise HTTPException(status_code=403, detail="权限不足")

        users = await user_service.list_users(skip=skip, limit=limit)
        
        return {
            "success": True,
            "data": {
                "users": [user.model_dump() for user in users],
                "total": len(users)
            },
            "message": "获取用户列表成功"
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取用户列表失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取用户列表失败: {str(e)}")
