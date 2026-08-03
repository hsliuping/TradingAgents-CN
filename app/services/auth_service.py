import time
from datetime import datetime, timedelta, timezone
from app.utils.timezone import now_tz
from typing import Optional
import jwt
from pydantic import BaseModel, Field
from app.core.config import settings

class TokenData(BaseModel):
    sub: str = Field(min_length=1)
    exp: int

class AuthService:
    @staticmethod
    def create_access_token(sub: str, expires_minutes: int | None = None, expires_delta: int | None = None) -> str:
        if expires_delta:
            # 如果指定了秒数，使用秒数
            expire = now_tz() + timedelta(seconds=expires_delta)
        else:
            # 否则使用分钟数
            expire = now_tz() + timedelta(minutes=expires_minutes or settings.ACCESS_TOKEN_EXPIRE_MINUTES)
        payload = {"sub": sub, "exp": expire}
        token = jwt.encode(payload, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)
        return token

    @staticmethod
    def verify_token(token: str | None) -> Optional[TokenData]:
        import logging
        logger = logging.getLogger(__name__)

        try:
            if not token:
                return None
            payload = jwt.decode(token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM])

            token_data = TokenData(sub=payload.get("sub"), exp=int(payload.get("exp", time.time())))

            # 检查是否过期
            current_time = int(time.time())
            if token_data.exp < current_time:
                logger.warning("访问令牌已过期")
                return None

            return token_data

        except jwt.ExpiredSignatureError:
            logger.warning("⏰ Token已过期")
            return None
        except jwt.InvalidTokenError:
            logger.warning("访问令牌无效")
            return None
        except Exception as exc:
            logger.error("访问令牌验证异常: error_type=%s", type(exc).__name__)
            return None
