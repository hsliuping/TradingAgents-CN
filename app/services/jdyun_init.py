"""
京东云合作版 - 数据库自动初始化

首次启动时从环境变量读取配置，写入数据库：
- llm_providers: 京东云 Provider
- system_configs: 4个模型配置 + 默认模型 + Tushare 数据源 + Embedding 配置
"""

import os
import logging
from datetime import datetime
from typing import Dict, Any, List

logger = logging.getLogger(__name__)

# 京东云初始化标记 collection（用于避免重复初始化）
_JDYUN_INIT_MARKER = "jdyun_init_marker"


def _get_sync_db():
    """获取同步 MongoDB 连接"""
    try:
        from app.core.database import get_mongo_db_sync
        return get_mongo_db_sync()
    except Exception as e:
        logger.error(f"❌ [京东云初始化] 获取同步数据库连接失败: {e}")
        return None


def _is_jdyun_initialized(db) -> bool:
    """检查京东云配置是否已初始化"""
    try:
        marker = db[_JDYUN_INIT_MARKER].find_one({"_id": "jdyun"})
        return marker is not None
    except Exception:
        return False


def _mark_jdyun_initialized(db):
    """标记京东云配置已初始化"""
    db[_JDYUN_INIT_MARKER].update_one(
        {"_id": "jdyun"},
        {"$set": {"initialized_at": datetime.utcnow(), "version": 1}},
        upsert=True,
    )


def _init_jdyun_provider(db, api_base: str, api_key: str, embedding_model: str):
    """初始化京东云 Provider 到 llm_providers 集合"""
    providers_collection = db.llm_providers

    # 检查是否已存在
    existing = providers_collection.find_one({"name": "jdyun"})
    if existing:
        # 更新已有记录
        providers_collection.update_one(
            {"name": "jdyun"},
            {"$set": {
                "display_name": "京东云",
                "description": "京东云模型服务（OpenAI 兼容接口）",
                "website": "https://www.jdcloud.com",
                "api_doc_url": "https://docs.jdcloud.com",
                "default_base_url": api_base,
                "api_key": api_key,
                "is_active": True,
                "supported_features": ["chat", "completion", "embedding", "function_calling", "streaming"],
                "embedding_model": embedding_model,
                "updated_at": datetime.utcnow(),
            }},
        )
        logger.info("  ✓ 更新京东云 Provider 配置")
    else:
        # 插入新记录
        providers_collection.insert_one({
            "name": "jdyun",
            "display_name": "京东云",
            "description": "京东云模型服务（OpenAI 兼容接口）",
            "website": "https://www.jdcloud.com",
            "api_doc_url": "https://docs.jdcloud.com",
            "default_base_url": api_base,
            "api_key": api_key,
            "is_active": True,
            "supported_features": ["chat", "completion", "embedding", "function_calling", "streaming"],
            "embedding_model": embedding_model,
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow(),
        })
        logger.info("  ✓ 创建京东云 Provider 配置")


def _build_jdyun_llm_configs(chat_models: List[str]) -> List[Dict[str, Any]]:
    """构建 4 个京东云模型的 LLM 配置"""
    configs = []
    for i, model_name in enumerate(chat_models):
        configs.append({
            "config_id": f"jdyun_{model_name.lower().replace('-', '_').replace('.', '_')}",
            "provider": "jdyun",
            "model_name": model_name,
            "model_display_name": model_name,
            "api_key": None,  # 使用厂家配置中的 API Key
            "api_base": None,  # 使用厂家配置中的 default_base_url
            "max_tokens": 8000,
            "temperature": 0.2,
            "timeout": 180,
            "retry_times": 3,
            "enabled": True,
            "description": f"京东云 {model_name} 模型",
            "capability_level": 3,
            "suitable_roles": ["both"],
            "features": ["tool_calling", "function_calling"],
            "recommended_depths": ["快速", "基础", "标准", "深度"],
            "priority": 10 - i,
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow(),
        })
    return configs


def _init_system_config(db, chat_models: List[str], default_model: str, embedding_model: str, tushare_token: str):
    """初始化系统配置到 system_configs 集合"""
    from app.core.jdyun import JDYUN_EMBEDDING_DIMS

    configs_collection = db.system_configs

    # 构建 LLM 配置列表
    llm_configs = _build_jdyun_llm_configs(chat_models)

    # 构建系统设置
    system_settings = {
        "quick_analysis_model": default_model,
        "deep_analysis_model": default_model,
        "default_embedding_model": f"jdyun:{embedding_model}",
        "default_embedding_dims": JDYUN_EMBEDDING_DIMS,
    }

    # 构建 Tushare 数据源配置
    data_source_configs = [{
        "name": "tushare",
        "type": "tushare",
        "api_key": tushare_token,
        "enabled": True,
        "priority": 100,
        "timeout": 30,
        "rate_limit": 100,
        "description": "Tushare A股数据源（京东云统一提供）",
        "config_params": {},
        "market_categories": ["china"],
        "display_name": "Tushare",
        "provider": "tushare",
        "created_at": datetime.utcnow(),
        "updated_at": datetime.utcnow(),
    }]

    # 检查是否已有活跃配置
    existing_config = configs_collection.find_one({"is_active": True}, sort=[("version", -1)])

    if existing_config:
        # 更新已有配置
        configs_collection.update_one(
            {"_id": existing_config["_id"]},
            {"$set": {
                "llm_configs": llm_configs,
                "system_settings": system_settings,
                "data_source_configs": data_source_configs,
                "updated_at": datetime.utcnow(),
            }},
        )
        logger.info(f"  ✓ 更新系统配置: {len(llm_configs)} 个模型, 默认模型={default_model}")
    else:
        # 创建新配置
        configs_collection.insert_one({
            "config_name": "jdyun_default",
            "config_type": "system",
            "llm_configs": llm_configs,
            "default_llm": default_model,
            "data_source_configs": data_source_configs,
            "database_configs": [],
            "system_settings": system_settings,
            "version": 1,
            "is_active": True,
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow(),
        })
        logger.info(f"  ✓ 创建系统配置: {len(llm_configs)} 个模型, 默认模型={default_model}")


def init_jdyun_config():
    """
    京东云版启动时从环境变量同步数据库配置

    每次启动都会执行同步（幂等操作）：
    - 更新 llm_providers 中的 jdyun Provider（base_url / api_key / embedding_model）
    - 更新 system_configs 中的模型列表（从 OPENAI_MODEL 逗号分隔解析）和默认模型
    - 这样换模型时只需修改 OPENAI_MODEL 环境变量，重启即可生效，无需手动改数据库
    """
    from app.core.jdyun import (
        is_jdyun_mode, get_jdyun_api_base, get_jdyun_api_key,
        get_jdyun_default_model, get_jdyun_embedding_model,
        get_jdyun_tushare_token, get_jdyun_chat_models,
    )

    if not is_jdyun_mode():
        return False

    logger.info("🔧 [京东云初始化] 开始从环境变量同步数据库配置...")

    db = _get_sync_db()
    if db is None:
        logger.error("❌ [京东云初始化] 无法获取数据库连接，跳过初始化")
        return False

    # 读取环境变量
    api_base = get_jdyun_api_base()
    api_key = get_jdyun_api_key()
    default_model = get_jdyun_default_model()
    embedding_model = get_jdyun_embedding_model()
    tushare_token = get_jdyun_tushare_token()
    chat_models = get_jdyun_chat_models()

    if not api_base or not api_key:
        logger.error("❌ [京东云初始化] OPENAI_API_BASE 或 OPENAI_API_KEY 未设置，跳过初始化")
        return False

    if not tushare_token:
        logger.warning("⚠️ [京东云初始化] TUSHARE_TOKEN 未设置，数据源功能可能不可用")

    try:
        # 1. 同步 Provider（幂等更新）
        _init_jdyun_provider(db, api_base, api_key, embedding_model)

        # 2. 同步系统配置（模型列表 + 默认模型 + 数据源）
        _init_system_config(db, chat_models, default_model, embedding_model, tushare_token)

        # 3. 标记已初始化
        _mark_jdyun_initialized(db)

        logger.info("✅ [京东云初始化] 数据库配置同步完成")
        logger.info(f"  - Provider: jdyun ({api_base})")
        logger.info(f"  - 模型: {', '.join(chat_models)}")
        logger.info(f"  - 默认模型: {default_model}")
        logger.info(f"  - Embedding: {embedding_model}")
        logger.info(f"  - Tushare: {'已配置' if tushare_token else '未配置'}")
        return True

    except Exception as e:
        logger.error(f"❌ [京东云初始化] 同步失败: {e}", exc_info=True)
        return False
