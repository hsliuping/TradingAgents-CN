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
JDYUN_EMBEDDING_DIMS = 4096

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


def get_jdyun_tushare_token() -> str:
    """获取 Tushare Token"""
    return os.getenv("TUSHARE_TOKEN", "").strip()


def is_jdyun_model(model_name: str) -> bool:
    """判断模型是否属于京东云预置模型"""
    return (model_name or "").strip() in JDYUN_CHAT_MODELS


def get_jdyun_status() -> dict:
    """获取京东云配置状态（不含敏感信息）"""
    return {
        "jdyun_mode": is_jdyun_mode(),
        "api_base": get_jdyun_api_base(),
        "api_key_configured": bool(get_jdyun_api_key()),
        "current_model": get_jdyun_default_model(),
        "available_models": JDYUN_CHAT_MODELS,
        "embedding_model": get_jdyun_embedding_model(),
        "embedding_dims": JDYUN_EMBEDDING_DIMS,
        "tushare_token_configured": bool(get_jdyun_tushare_token()),
    }
