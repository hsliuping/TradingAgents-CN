import time
from datetime import datetime, timedelta, timezone
from app.utils.timezone import now_tz
from typing import Optional
import jwt
from pydantic import BaseModel
from app.core.config import settings

class TokenData(BaseModel):
    sub: str
    exp: int
    session_id: Optional[str] = None  # 添加 session_id

class AuthService:
    @staticmethod
    def create_access_token(
        sub: str,
        expires_minutes: int | None = None,
        expires_delta: int | None = None,
        session_id: Optional[str] = None  # 添加 session_id 参数
    ) -> str:
        if expires_delta:
            # 如果指定了秒数，使用秒数
            expire = now_tz() + timedelta(seconds=expires_delta)
        else:
            # 否则使用分钟数
            expire = now_tz() + timedelta(minutes=expires_minutes or settings.ACCESS_TOKEN_EXPIRE_MINUTES)

        payload = {"sub": sub, "exp": expire}

        # 如果提供了 session_id，添加到 payload
        if session_id:
            payload["session_id"] = session_id

        token = jwt.encode(payload, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)
        return token

    @staticmethod
    def verify_token(token: str) -> Optional[TokenData]:
        import logging
        logger = logging.getLogger(__name__)

        try:
            logger.debug(f"🔍 开始验证token")
            logger.debug(f"📝 Token长度: {len(token)}")
            logger.debug(f"🔑 JWT密钥: {settings.JWT_SECRET[:10]}...")
            logger.debug(f"🔧 JWT算法: {settings.JWT_ALGORITHM}")

            payload = jwt.decode(token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM])
            logger.debug(f"✅ Token解码成功")
            logger.debug(f"📋 Payload: {payload}")

            token_data = TokenData(
                sub=payload.get("sub"),
                exp=int(payload.get("exp", time.time())),
                session_id=payload.get("session_id")  # 解析 session_id
            )
            logger.debug(f"🎯 Token数据: sub={token_data.sub}, exp={token_data.exp}, session_id={token_data.session_id[:16] if token_data.session_id else 'None'}...")

            # 检查是否过期
            current_time = int(time.time())
            if token_data.exp < current_time:
                logger.warning(f"⏰ Token已过期: exp={token_data.exp}, now={current_time}")
                return None

            logger.debug(f"✅ Token验证成功")
            return token_data

        except jwt.ExpiredSignatureError:
            logger.warning("⏰ Token已过期")
            return None
        except jwt.InvalidTokenError as e:
            logger.warning(f"❌ Token无效: {str(e)}")
            return None
        except Exception as e:
            logger.error(f"❌ Token验证异常: {str(e)}")
            return None