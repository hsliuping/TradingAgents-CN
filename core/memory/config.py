"""
mem0 统一记忆层 — 配置加载

直接复用系统已有的 LLM / Embedding 配置（数据库 system_configs + llm_providers），
不额外维护一套独立配置。

配置优先级：MongoDB system_configs > .env > 代码默认值
"""

import logging
import os
from typing import Any, Dict, Optional, Tuple

logger = logging.getLogger(__name__)

_QDRANT_COLLECTION = "mem0_memories"


def _env(key: str, default: str = "") -> str:
    return (os.environ.get(key) or "").strip() or default


def _get_sync_db():
    """获取同步 MongoDB 连接"""
    try:
        from app.core.database import get_mongo_db_sync
        return get_mongo_db_sync()
    except Exception:
        return None


def _read_system_settings(db=None) -> Tuple[dict, list]:
    """从 system_configs 读取 system_settings 和 llm_configs"""
    sync_db = None
    try:
        if db is not None:
            from motor.motor_asyncio import AsyncIOMotorDatabase
            if isinstance(db, AsyncIOMotorDatabase):
                sync_db = _get_sync_db()
            else:
                sync_db = db
        else:
            sync_db = _get_sync_db()

        if sync_db is None:
            return {}, []

        doc = sync_db.system_configs.find_one(
            {"is_active": True}, sort=[("version", -1)]
        )
        if not doc:
            return {}, []
        return doc.get("system_settings") or {}, doc.get("llm_configs") or []
    except Exception as e:
        logger.debug("mem0 config: 无法从数据库读取配置: %s", e)
        return {}, []


def _resolve_model_credentials(model_name: str) -> Optional[Dict[str, str]]:
    """复用系统已有的模型解析逻辑，返回 {provider, api_key, backend_url}"""
    if not model_name:
        return None
    try:
        from app.services.simple_analysis_service import get_provider_and_url_by_model_sync
        info = get_provider_and_url_by_model_sync(model_name)
        if info and info.get("api_key"):
            return info
    except Exception as e:
        logger.debug("mem0 config: 模型 %s 凭证解析失败: %s", model_name, e)
    return None


def _resolve_embedding_from_db(db_settings: dict) -> dict:
    """从数据库 default_embedding_model 解析 embedding 配置"""
    default_emb = db_settings.get("default_embedding_model", "")
    if not default_emb or ":" not in default_emb:
        return {}

    provider_name, model_name = default_emb.split(":", 1)
    sync_db = _get_sync_db()
    if not sync_db:
        return {}

    try:
        provider_doc = sync_db.llm_providers.find_one(
            {"name": {"$regex": f"^{provider_name}$", "$options": "i"}, "is_active": True}
        )
        if not provider_doc or not provider_doc.get("api_key"):
            return {}

        api_key = provider_doc["api_key"]
        base_url = provider_doc.get("default_base_url") or ""
        if base_url and "/v1" not in base_url:
            base_url = f"{base_url.rstrip('/')}/v1"

        return {
            "provider": "openai",
            "config": {
                "api_key": api_key,
                "openai_base_url": base_url,
                "model": model_name,
            },
        }
    except Exception as e:
        logger.debug("mem0 config: embedding 解析失败: %s", e)
        return {}


def build_mem0_config(db=None) -> Dict[str, Any]:
    """
    构建 mem0 Memory.from_config() 所需的完整 config dict。

    LLM / Embedding 配置直接从数据库 system_configs + llm_providers 读取，
    与分析流程使用相同的模型和凭证。
    """
    db_settings, llm_configs = _read_system_settings(db)

    # --- Vector Store: 复用现有 Qdrant ---
    qdrant_path = _env("QDRANT_DATA_DIR", "./data/qdrant")
    vector_store = {
        "provider": "qdrant",
        "config": {
            "path": qdrant_path,
            "collection_name": _QDRANT_COLLECTION,
            "on_disk": True,
        },
    }

    # --- LLM: 复用系统 quick_analysis_model ---
    target_model = (
        db_settings.get("quick_analysis_model")
        or db_settings.get("deep_analysis_model")
    )
    # 如果 system_settings 里没配，从 llm_configs 找第一个启用的模型
    if not target_model and llm_configs:
        for cfg in llm_configs:
            if cfg.get("enabled", True) and cfg.get("model_name"):
                target_model = cfg["model_name"]
                break

    llm_creds = _resolve_model_credentials(target_model) if target_model else None

    if llm_creds and llm_creds.get("api_key"):
        backend_url = llm_creds.get("backend_url", "")
        if backend_url and "/v1" not in backend_url:
            backend_url = f"{backend_url.rstrip('/')}/v1"
        llm = {
            "provider": "openai",
            "config": {
                "api_key": llm_creds["api_key"],
                "openai_base_url": backend_url,
                "model": target_model,
                "temperature": 0.1,
                "max_tokens": 2000,
            },
        }
    else:
        llm = {
            "provider": "openai",
            "config": {
                "api_key": "",
                "model": target_model or "deepseek-chat",
                "temperature": 0.1,
                "max_tokens": 2000,
            },
        }

    # --- Embedder: 复用系统 default_embedding_model ---
    embedder = _resolve_embedding_from_db(db_settings)

    # --- 组装 ---
    from .prompts import FINANCIAL_FACT_EXTRACTION_PROMPT

    config: Dict[str, Any] = {
        "vector_store": vector_store,
        "llm": llm,
        "custom_prompt": FINANCIAL_FACT_EXTRACTION_PROMPT,
        "version": "v1.1",
    }
    if embedder:
        config["embedder"] = embedder

    return config
