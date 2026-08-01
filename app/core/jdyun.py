"""
京东云合作版配置

通过 JDYUN_MODE=true 环境变量启用京东云合作版模式。
所有 LLM 和数据源配置从京东云平台注入的环境变量读取：
- OPENAI_API_BASE: 京东云模型服务地址
- OPENAI_API_KEY: 京东云 API Key
- OPENAI_MODEL: 默认对话模型
- EMBEDDING_MODEL: Embedding 模型
- TUSHARE_TOKEN: Tushare 数据源 Token
"""

import os
import logging
from typing import Dict

logger = logging.getLogger(__name__)

# 京东云预置的对话模型列表（均可用作 quick_model 或 deep_model）
JDYUN_CHAT_MODELS = [
    "GLM-5",
    "GLM-5.1",
    "GLM-5.2",
    "DeepSeek-V4-Flash",
]

# 默认 Embedding 模型
JDYUN_DEFAULT_EMBEDDING_MODEL = "Qwen3-Embedding-8B"

# Qwen3-Embedding-8B 输出维度
# 🔥 京东云本地模型只支持 [64, 128, 256, 512, 768, 1024, 1536, 2048] 维度
# 为确保兼容性，统一使用 1024 维
JDYUN_EMBEDDING_DIMS = 1024

# 京东云 Provider 名称
JDYUN_PROVIDER_NAME = "jdyun"


def is_jdyun_mode() -> bool:
    """检测是否启用京东云合作版模式"""
    return os.getenv("JDYUN_MODE", "").strip().lower() in ("true", "1", "yes")


def get_jdyun_api_base() -> str:
    """获取京东云模型服务地址"""
    return os.getenv("OPENAI_API_BASE", "").strip()


def get_jdyun_api_key() -> str:
    """获取京东云 API Key"""
    return os.getenv("OPENAI_API_KEY", "").strip()


def get_jdyun_default_model() -> str:
    """获取默认对话模型"""
    model = os.getenv("OPENAI_MODEL", "").strip()
    return model if model else JDYUN_CHAT_MODELS[0]


def get_jdyun_embedding_model() -> str:
    """获取 Embedding 模型"""
    model = os.getenv("EMBEDDING_MODEL", "").strip()
    return model if model else JDYUN_DEFAULT_EMBEDDING_MODEL


def get_jdyun_embedding_api_base() -> str:
    """获取 Embedding 服务地址（留空则使用对话模型服务地址）"""
    base = os.getenv("EMBEDDING_API_BASE", "").strip()
    return base if base else get_jdyun_api_base()


def get_jdyun_embedding_api_key() -> str:
    """获取 Embedding API Key（留空则使用对话模型 API Key）"""
    key = os.getenv("EMBEDDING_API_KEY", "").strip()
    return key if key else get_jdyun_api_key()


def get_jdyun_tushare_token() -> str:
    """获取 Tushare Token"""
    return os.getenv("TUSHARE_TOKEN", "").strip()


def is_jdyun_model(model_name: str) -> bool:
    """判断模型是否属于京东云预置模型"""
    return (model_name or "").strip() in JDYUN_CHAT_MODELS


def get_jdyun_status() -> dict:
    """获取京东云配置状态（不含敏感信息）"""
    basic_auth_users = get_jdyun_basic_auth_users()
    return {
        "jdyun_mode": is_jdyun_mode(),
        "api_base": get_jdyun_api_base(),
        "api_key_configured": bool(get_jdyun_api_key()),
        "current_model": get_jdyun_default_model(),
        "available_models": JDYUN_CHAT_MODELS,
        "embedding_model": get_jdyun_embedding_model(),
        "embedding_dims": JDYUN_EMBEDDING_DIMS,
        "tushare_token_configured": bool(get_jdyun_tushare_token()),
        "akshare_available": True,  # AKShare 是开源免费数据源，始终可用
        # Basic Auth 白名单状态（仅返回计数，不含密码）
        "basic_auth_enabled": bool(basic_auth_users),
        "basic_auth_users_count": len(basic_auth_users),
    }


# ============================================================================
# LLM 限速配置（应对京东云 API 限速）
# ============================================================================

def get_jdyun_llm_max_retries() -> int:
    """获取 LLM 调用最大重试次数（京东云模式默认 8，应对 429 限速）"""
    return int(os.getenv("JDYUN_LLM_MAX_RETRIES", "8"))


def get_jdyun_llm_max_rpm() -> int:
    """获取 LLM 每分钟最大请求数（用于限速器配置，默认 30）"""
    return int(os.getenv("JDYUN_LLM_MAX_RPM", "30"))


def get_jdyun_batch_max_concurrent() -> int:
    """获取批量分析最大并发数（京东云模式默认 1，避免 LLM 限速）"""
    return int(os.getenv("JDYUN_BATCH_MAX_CONCURRENT", "1"))


def get_jdyun_worker_max_concurrent() -> int:
    """获取 Worker 最大并发任务数（京东云模式默认 1，避免 LLM 限速）"""
    return int(os.getenv("JDYUN_WORKER_MAX_CONCURRENT", "1"))


def get_jdyun_stock_interval_seconds() -> int:
    """获取定时分析股票间的间隔秒数（京东云模式默认 10 秒）"""
    return int(os.getenv("JDYUN_STOCK_INTERVAL_SECONDS", "10"))


def get_llm_max_retries(default: int = 2) -> int:
    """
    获取 LLM 最大重试次数（兼容京东云和非京东云模式）

    Args:
        default: 非京东云模式下的默认重试次数（默认 2）

    Returns:
        京东云模式返回 get_jdyun_llm_max_retries()，否则返回 default
    """
    if is_jdyun_mode():
        return get_jdyun_llm_max_retries()
    return default


# ============================================================================
# Basic Auth 白名单配置（京东云网关代理场景）
# ============================================================================

def get_jdyun_basic_auth_users() -> Dict[str, str]:
    """
    解析京东云 Basic Auth 白名单

    环境变量格式: JDYUN_BASIC_AUTH_USERS=user1:pass1,user2:pass2
    - 多个账户用英文逗号分隔
    - 用户名和密码用英文冒号分隔
    - 密码中的冒号用第一个冒号切分（避免歧义）

    Returns:
        {"user1": "pass1", "user2": "pass2"} 形式的用户-密码字典

    安全性:
    - 密码以明文存储在 env 中，等同 OPENAI_API_KEY 的处理方式
    - 建议仅在京东云注入的环境使用，不要写入 .env.jdyun 提交到 Git
    - 京东云网关负责 https 加密传输，明文只在容器内可见
    """
    raw = os.getenv("JDYUN_BASIC_AUTH_USERS", "").strip()
    if not raw:
        return {}
    result: Dict[str, str] = {}
    for entry in raw.split(","):
        entry = entry.strip()
        if not entry or ":" not in entry:
            logger.warning("⚠️ [京东云 Basic Auth] 跳过格式错误的账户配置项: %s", entry)
            continue
        user, password = entry.split(":", 1)
        user = user.strip()
        password = password.strip()
        if user and password:
            result[user] = password
        else:
            logger.warning("⚠️ [京东云 Basic Auth] 跳过空用户名或密码的账户: %s", entry)
    if result:
        logger.info("🔐 [京东云 Basic Auth] 已加载 %d 个白名单账户", len(result))
    return result


def verify_jdyun_basic_auth(username: str, password: str) -> bool:
    """
    验证京东云 Basic Auth 凭据

    Args:
        username: 用户名
        password: 明文密码

    Returns:
        凭据有效返回 True，否则 False

    安全性:
    - 使用 hmac.compare_digest 做恒定时间比较（避免时序攻击）
    - 用户名不在白名单时直接返回 False，不进行密码比较
    """
    import hmac

    white_list = get_jdyun_basic_auth_users()
    expected_password = white_list.get(username, "")
    if not expected_password:
        return False
    return hmac.compare_digest(
        password.encode("utf-8"),
        expected_password.encode("utf-8"),
    )
