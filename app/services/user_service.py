"""
用户服务 - 基于数据库的用户管理
"""

import atexit
import hashlib
import sys
import time
from datetime import datetime
from typing import Optional, Dict, Any, List
import bcrypt
from pymongo import MongoClient
from bson import ObjectId

from app.core.config import settings
from app.models.user import User, UserCreate, UserUpdate, UserResponse

# 尝试导入日志管理器
try:
    from tradingagents.utils.logging_manager import get_logger
except ImportError:
    # 如果导入失败，使用标准日志
    import logging
    def get_logger(name: str) -> logging.Logger:
        return logging.getLogger(name)

logger = get_logger('user_service')


# 旧版 SHA-256 哈希前缀，用于识别需要升级的存量密码
# SHA-256 输出为 64 位十六进制字符串；bcrypt 哈希以 $2 开头
_LEGACY_SHA256_PREFIX = "sha256:"
_BCRYPT_PREFIX = "$2"


class UserService:
    """用户服务类"""

    def __init__(self):
        self.client = MongoClient(settings.MONGO_URI)
        self.db = self.client[settings.MONGO_DB]
        self.users_collection = self.db.users
        self._closed = False
        atexit.register(self._close_at_exit)

    def close(self, log: bool = True):
        """关闭数据库连接"""
        if self._closed:
            return

        if hasattr(self, 'client') and self.client:
            try:
                self.client.close()
            except Exception:
                pass

        self._closed = True

        if log and sys.meta_path is not None:
            try:
                logger.info("UserService MongoDB connection closed")
            except Exception:
                pass

    def _close_at_exit(self):
        """解释器正常退出时关闭连接，不写日志。"""
        try:
            self.close(log=False)
        except Exception:
            pass

    def __del__(self):
        """析构函数，确保连接被关闭且不在解释器关闭阶段写日志。"""
        try:
            self.close(log=False)
        except Exception:
            pass
    
    @staticmethod
    def hash_password(password: str) -> str:
        """密码哈希（使用 bcrypt + 自动加盐）

        返回值以 `$2` 开头，可通过 `bcrypt.checkpw` 验证。
        兼容旧版 SHA-256 哈希（验证时自动识别并升级）。
        """
        # bcrypt 自带盐，相同密码每次哈希结果不同，防止彩虹表攻击
        # rounds=12 是 OWASP 2023 推荐值（约 250ms / hash）
        rounds = getattr(settings, "BCRYPT_ROUNDS", 12)
        salt = bcrypt.gensalt(rounds=rounds)
        return bcrypt.hashpw(password.encode("utf-8"), salt).decode("utf-8")

    @staticmethod
    def _hash_legacy_sha256(password: str) -> str:
        """旧版 SHA-256 哈希（无盐，仅用于验证存量密码）"""
        return hashlib.sha256(password.encode("utf-8")).hexdigest()

    @staticmethod
    def _is_bcrypt_hash(hashed: str) -> bool:
        """判断是否为 bcrypt 哈希（以 $2 开头）"""
        return bool(hashed) and hashed.startswith(_BCRYPT_PREFIX)

    @staticmethod
    def verify_password(plain_password: str, hashed_password: str) -> bool:
        """验证密码

        自动识别 bcrypt 哈希和旧版 SHA-256 哈希：
        - bcrypt 哈希：使用 bcrypt.checkpw 验证
        - 旧版 SHA-256 哈希：用 SHA-256 比对（验证成功后调用方应负责升级）
        """
        if not hashed_password:
            return False
        if UserService._is_bcrypt_hash(hashed_password):
            try:
                return bcrypt.checkpw(
                    plain_password.encode("utf-8"),
                    hashed_password.encode("utf-8"),
                )
            except (ValueError, TypeError):
                return False
        # 旧版 SHA-256（无盐）兼容路径
        return UserService._hash_legacy_sha256(plain_password) == hashed_password
    
    async def create_user(self, user_data: UserCreate) -> Optional[User]:
        """创建用户"""
        try:
            # 检查用户名是否已存在
            existing_user = self.users_collection.find_one({"username": user_data.username})
            if existing_user:
                logger.warning(f"用户名已存在: {user_data.username}")
                return None
            
            # 检查邮箱是否已存在
            existing_email = self.users_collection.find_one({"email": user_data.email})
            if existing_email:
                logger.warning(f"邮箱已存在: {user_data.email}")
                return None
            
            # 创建用户文档
            user_doc = {
                "username": user_data.username,
                "email": user_data.email,
                "hashed_password": self.hash_password(user_data.password),
                "is_active": True,
                "is_verified": False,
                "is_admin": False,
                "created_at": datetime.utcnow(),
                "updated_at": datetime.utcnow(),
                "last_login": None,
                "preferences": {
                    # 分析偏好
                    "default_market": "A股",
                    "default_depth": "3",  # 1-5级，3级为标准分析（推荐）
                    "default_analysts": ["市场分析师", "基本面分析师"],
                    "auto_refresh": True,
                    "refresh_interval": 30,
                    # 外观设置
                    "ui_theme": "light",
                    "sidebar_width": 240,
                    # 语言和地区
                    "language": "zh-CN",
                    # 通知设置
                    "notifications_enabled": True,
                    "email_notifications": False,
                    "desktop_notifications": True,
                    "analysis_complete_notification": True,
                    "system_maintenance_notification": True
                },
                "daily_quota": 1000,
                "concurrent_limit": 3,
                "total_analyses": 0,
                "successful_analyses": 0,
                "failed_analyses": 0,
                "favorite_stocks": []
            }
            
            result = self.users_collection.insert_one(user_doc)
            user_doc["_id"] = result.inserted_id
            
            logger.info(f"✅ 用户创建成功: {user_data.username}")
            return User(**user_doc)
            
        except Exception as e:
            logger.error(f"❌ 创建用户失败: {e}")
            return None
    
    async def authenticate_user(self, username: str, password: str) -> Optional[User]:
        """用户认证"""
        try:
            logger.info(f"🔍 [authenticate_user] 开始认证用户: {username}")

            # 查找用户
            user_doc = self.users_collection.find_one({"username": username})
            logger.info(f"🔍 [authenticate_user] 数据库查询结果: {'找到用户' if user_doc else '用户不存在'}")

            if not user_doc:
                logger.warning(f"❌ [authenticate_user] 用户不存在: {username}")
                return None

            logger.info(f"🔍 [authenticate_user] 用户信息: username={user_doc.get('username')}, email={user_doc.get('email')}, is_active={user_doc.get('is_active')}")

            # 验证密码（自动识别 bcrypt / 旧版 SHA-256）
            stored_hash = user_doc.get("hashed_password", "")
            # ⚠️ 安全：禁止在日志中输出任何密码哈希内容（即使是前缀）
            logger.info(f"🔍 [authenticate_user] 存储密码哈希类型: {'bcrypt' if self._is_bcrypt_hash(stored_hash) else 'legacy_sha256' if stored_hash else 'empty'}")

            if not self.verify_password(password, stored_hash):
                logger.warning(f"❌ [authenticate_user] 密码错误: {username}")
                return None

            # 🔐 旧版 SHA-256 哈希自动升级到 bcrypt（透明升级，用户无感知）
            if not self._is_bcrypt_hash(stored_hash):
                try:
                    new_bcrypt_hash = self.hash_password(password)
                    self.users_collection.update_one(
                        {"_id": user_doc["_id"]},
                        {"$set": {
                            "hashed_password": new_bcrypt_hash,
                            "updated_at": datetime.utcnow(),
                            "password_hash_algo": "bcrypt",
                        }}
                    )
                    logger.info(f"🔐 [authenticate_user] 旧版 SHA-256 密码已自动升级到 bcrypt: {username}")
                except Exception as upgrade_err:
                    # 升级失败不影响登录，但需记录告警
                    logger.warning(f"⚠️ [authenticate_user] 密码哈希升级失败（登录继续）: {username} error={upgrade_err}")

            # 检查用户是否激活
            if not user_doc.get("is_active", True):
                logger.warning(f"❌ [authenticate_user] 用户已禁用: {username}")
                return None

            # 更新最后登录时间
            self.users_collection.update_one(
                {"_id": user_doc["_id"]},
                {"$set": {"last_login": datetime.utcnow()}}
            )

            logger.info(f"✅ [authenticate_user] 用户认证成功: {username}")
            return User(**user_doc)

        except Exception as e:
            logger.error(f"❌ 用户认证失败: {e}")
            return None
    
    async def get_user_by_username(self, username: str) -> Optional[User]:
        """根据用户名获取用户"""
        try:
            user_doc = self.users_collection.find_one({"username": username})
            if user_doc:
                return User(**user_doc)
            return None
        except Exception as e:
            logger.error(f"❌ 获取用户失败: {e}")
            return None
    
    async def get_user_by_id(self, user_id: str) -> Optional[User]:
        """根据用户ID获取用户"""
        try:
            if not ObjectId.is_valid(user_id):
                return None
            
            user_doc = self.users_collection.find_one({"_id": ObjectId(user_id)})
            if user_doc:
                return User(**user_doc)
            return None
        except Exception as e:
            logger.error(f"❌ 获取用户失败: {e}")
            return None
    
    async def update_user(self, username: str, user_data: UserUpdate) -> Optional[User]:
        """更新用户信息"""
        try:
            update_data = {"updated_at": datetime.utcnow()}
            
            # 只更新提供的字段
            if user_data.email:
                # 检查邮箱是否已被其他用户使用
                existing_email = self.users_collection.find_one({
                    "email": user_data.email,
                    "username": {"$ne": username}
                })
                if existing_email:
                    logger.warning(f"邮箱已被使用: {user_data.email}")
                    return None
                update_data["email"] = user_data.email
            
            if user_data.preferences:
                update_data["preferences"] = user_data.preferences.model_dump()
            
            if user_data.daily_quota is not None:
                update_data["daily_quota"] = user_data.daily_quota
            
            if user_data.concurrent_limit is not None:
                update_data["concurrent_limit"] = user_data.concurrent_limit
            
            result = self.users_collection.update_one(
                {"username": username},
                {"$set": update_data}
            )
            
            if result.modified_count > 0:
                logger.info(f"✅ 用户信息更新成功: {username}")
                return await self.get_user_by_username(username)
            else:
                logger.warning(f"用户不存在或无需更新: {username}")
                return None
                
        except Exception as e:
            logger.error(f"❌ 更新用户信息失败: {e}")
            return None
    
    async def change_password(self, username: str, old_password: str, new_password: str) -> bool:
        """修改密码"""
        try:
            # 验证旧密码
            user = await self.authenticate_user(username, old_password)
            if not user:
                logger.warning(f"旧密码验证失败: {username}")
                return False
            
            # 更新密码
            new_hashed_password = self.hash_password(new_password)
            result = self.users_collection.update_one(
                {"username": username},
                {
                    "$set": {
                        "hashed_password": new_hashed_password,
                        "updated_at": datetime.utcnow()
                    }
                }
            )
            
            if result.modified_count > 0:
                logger.info(f"✅ 密码修改成功: {username}")
                return True
            else:
                logger.error(f"❌ 密码修改失败: {username}")
                return False
                
        except Exception as e:
            logger.error(f"❌ 修改密码失败: {e}")
            return False
    
    async def reset_password(self, username: str, new_password: str) -> bool:
        """重置密码（管理员操作）"""
        try:
            new_hashed_password = self.hash_password(new_password)
            result = self.users_collection.update_one(
                {"username": username},
                {
                    "$set": {
                        "hashed_password": new_hashed_password,
                        "updated_at": datetime.utcnow()
                    }
                }
            )
            
            if result.modified_count > 0:
                logger.info(f"✅ 密码重置成功: {username}")
                return True
            else:
                logger.error(f"❌ 密码重置失败: {username}")
                return False
                
        except Exception as e:
            logger.error(f"❌ 重置密码失败: {e}")
            return False
    
    async def create_admin_user(
        self,
        username: str = "admin",
        password: Optional[str] = None,  # 🔥 改为可选，必须通过环境变量或参数指定
        email: str = "admin@tradingagents.cn"
    ) -> Optional[User]:
        """创建管理员用户
        
        ⚠️ 安全警告：不再使用硬编码默认密码。
        必须通过以下方式之一指定密码：
        1. 通过参数 password 指定
        2. 通过环境变量 ADMIN_DEFAULT_PASSWORD 指定
        
        如果两者都未指定，将抛出 ValueError。
        """
        # 🔥 从环境变量或参数获取密码，不再使用硬编码默认值
        if password is None:
            import os
            password = os.getenv("ADMIN_DEFAULT_PASSWORD")
        
        if password is None:
            raise ValueError(
                "创建管理员用户必须指定密码。请设置环境变量 ADMIN_DEFAULT_PASSWORD "
                "或在调用 create_admin_user() 时传入 password 参数。"
            )
        
        # 检查密码强度（至少 8 位）
        if len(password) < 8:
            logger.warning(f"⚠️ 管理员密码长度不足（{len(password)} 位），建议至少 8 位")
        
        try:
            # 检查是否已存在管理员
            existing_admin = self.users_collection.find_one({"username": username})
            if existing_admin:
                logger.info(f"管理员用户已存在: {username}")
                return User(**existing_admin)
            
            # 创建管理员用户文档
            admin_doc = {
                "username": username,
                "email": email,
                "hashed_password": self.hash_password(password),
                "is_active": True,
                "is_verified": True,
                "is_admin": True,
                "created_at": datetime.utcnow(),
                "updated_at": datetime.utcnow(),
                "last_login": None,
                "preferences": {
                    "default_market": "A股",
                    "default_depth": "深度",
                    "ui_theme": "light",
                    "language": "zh-CN",
                    "notifications_enabled": True,
                    "email_notifications": False
                },
                "daily_quota": 10000,  # 管理员更高配额
                "concurrent_limit": 10,
                "total_analyses": 0,
                "successful_analyses": 0,
                "failed_analyses": 0,
                "favorite_stocks": []
            }
            
            result = self.users_collection.insert_one(admin_doc)
            admin_doc["_id"] = result.inserted_id

            logger.info(f"✅ 管理员用户创建成功: {username}")
            # ⚠️ 安全：禁止在日志中输出明文密码；密码已通过环境变量传入，请用户自行记录
            logger.info("   🔐 密码已使用 bcrypt 加密存储，请妥善保管您设置的管理员密码")
            logger.info("   ⚠️  建议首次登录后立即修改密码！")

            return User(**admin_doc)
            
        except Exception as e:
            logger.error(f"❌ 创建管理员用户失败: {e}")
            return None
    
    async def list_users(self, skip: int = 0, limit: int = 100) -> List[UserResponse]:
        """获取用户列表"""
        try:
            cursor = self.users_collection.find().skip(skip).limit(limit)
            users = []
            
            for user_doc in cursor:
                user = User(**user_doc)
                users.append(UserResponse(
                    id=str(user.id),
                    username=user.username,
                    email=user.email,
                    is_active=user.is_active,
                    is_verified=user.is_verified,
                    created_at=user.created_at,
                    last_login=user.last_login,
                    preferences=user.preferences,
                    daily_quota=user.daily_quota,
                    concurrent_limit=user.concurrent_limit,
                    total_analyses=user.total_analyses,
                    successful_analyses=user.successful_analyses,
                    failed_analyses=user.failed_analyses
                ))
            
            return users
            
        except Exception as e:
            logger.error(f"❌ 获取用户列表失败: {e}")
            return []
    
    async def deactivate_user(self, username: str) -> bool:
        """禁用用户"""
        try:
            result = self.users_collection.update_one(
                {"username": username},
                {
                    "$set": {
                        "is_active": False,
                        "updated_at": datetime.utcnow()
                    }
                }
            )
            
            if result.modified_count > 0:
                logger.info(f"✅ 用户已禁用: {username}")
                return True
            else:
                logger.warning(f"用户不存在: {username}")
                return False
                
        except Exception as e:
            logger.error(f"❌ 禁用用户失败: {e}")
            return False
    
    async def activate_user(self, username: str) -> bool:
        """激活用户"""
        try:
            result = self.users_collection.update_one(
                {"username": username},
                {
                    "$set": {
                        "is_active": True,
                        "updated_at": datetime.utcnow()
                    }
                }
            )
            
            if result.modified_count > 0:
                logger.info(f"✅ 用户已激活: {username}")
                return True
            else:
                logger.warning(f"用户不存在: {username}")
                return False
                
        except Exception as e:
            logger.error(f"❌ 激活用户失败: {e}")
            return False


# 全局用户服务实例
user_service = UserService()
