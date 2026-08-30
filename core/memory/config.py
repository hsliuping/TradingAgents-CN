"""
mem0 统一记忆层 — 配置加载

直接复用系统已有的 LLM / Embedding 配置（数据库 system_configs + llm_providers），
不额外维护一套独立配置。

配置优先级：MongoDB system_configs > .env > 代码默认值
"""

import logging
import os
import hashlib
import re
import inspect
from typing import Any, Dict, Optional, Tuple

logger = logging.getLogger(__name__)

_MEM0_COLLECTION_PREFIX = "mem0_memories"

_MEM0_OPENAI_COMPATIBLE_PROVIDERS = {
    "openai",
    "dashscope",
    "siliconflow",
    "302ai",
    "openrouter",
    "localai",
    "lmstudio",
}

_MEM0_DIRECT_PROVIDER_MAP = {
    "google": "gemini",
    "gemini": "gemini",
    "ollama": "ollama",
}

_DEFAULT_EMBEDDING_MODELS = {
    "dashscope": "text-embedding-v3",
    "openai": "text-embedding-3-small",
    "google": "text-embedding-004",
    "gemini": "text-embedding-004",
    "ollama": "nomic-embed-text",
    "zhipu": "embedding-2",
    "siliconflow": "BAAI/bge-large-zh-v1.5",
    "302ai": "text-embedding-3-small",
    "openrouter": "text-embedding-3-small",
    "localai": "text-embedding-3-small",
    "lmstudio": "text-embedding-3-small",
}


def _sanitize_collection_token(value: str, max_length: int = 24) -> str:
    normalized = re.sub(r"[^a-z0-9]+", "_", str(value or "").strip().lower()).strip("_")
    if not normalized:
        return "default"
    return normalized[:max_length]


def _build_mem0_collection_name(embedder: Optional[Dict[str, Any]]) -> str:
    embedder = embedder or {}
    embedder_cfg = embedder.get("config") or {}

    provider = _sanitize_collection_token(embedder.get("provider") or "default", max_length=16)
    model = _sanitize_collection_token(embedder_cfg.get("model") or "default", max_length=24)
    dims = int(embedder_cfg.get("embedding_dims") or 0)
    fingerprint_source = f"{provider}:{embedder_cfg.get('model') or ''}:{dims}"
    fingerprint = hashlib.sha1(fingerprint_source.encode("utf-8")).hexdigest()[:8]
    return f"{_MEM0_COLLECTION_PREFIX}_{provider}_{model}_{dims or '0'}_{fingerprint}"


def _backup_collection_payload(client, collection_name: str, base_path: str) -> Optional[str]:
    """[已废弃] MongoDB 迁移后不再需要 Qdrant 备份逻辑。

    保留此函数以备未来回退到 Qdrant 时使用。
    """
    import json
    from datetime import datetime

    backup_dir = os.path.join(base_path, "backups")
    os.makedirs(backup_dir, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_file = os.path.join(backup_dir, f"{collection_name}_{timestamp}.json")

    points = []
    offset = None
    while True:
        batch, offset = client.scroll(
            collection_name=collection_name,
            limit=256,
            offset=offset,
            with_payload=True,
            with_vectors=False,
        )
        if not batch:
            break
        for p in batch:
            points.append({"id": str(p.id), "payload": p.payload})
        if offset is None:
            break

    with open(backup_file, "w", encoding="utf-8") as f:
        json.dump(
            {"collection": collection_name, "count": len(points), "points": points},
            f, ensure_ascii=False, indent=2,
        )
    return backup_file


def _ensure_qdrant_collection_dimension(vector_store_cfg: Dict[str, Any], expected_dims: int) -> None:
    """
    [已废弃] MongoDB 迁移后不再调用此函数。

    保留以备未来回退到 Qdrant 时使用。
    """
    from qdrant_client import QdrantClient

    path = vector_store_cfg.get("path")
    collection_name = vector_store_cfg.get("collection_name")
    if not path or not collection_name:
        return

    try:
        client = QdrantClient(path=path)
        try:
            collections = client.get_collections().collections

            # 问题 5：扫描遗留的旧命名 collection，提示用户迁移
            for col in collections:
                name = col.name
                if name == collection_name or not name.startswith(_MEM0_COLLECTION_PREFIX):
                    continue
                logger.info(
                    "mem0 config: 检测到历史 collection '%s'（当前使用 '%s'）。"
                    "如需迁移数据，请执行：python app/scripts/migrate_mem0_collection.py --source %s",
                    name, collection_name, name,
                )

            # 检查当前 collection 维度
            if not any(col.name == collection_name for col in collections):
                return  # collection 不存在，mem0 会自动创建

            info = client.get_collection(collection_name)
            actual_dims = int(info.config.params.vectors.size)
            if actual_dims == expected_dims:
                return  # 维度匹配，无需处理

            # 问题 3：维度不匹配 → 先备份 payload，再删除
            logger.warning(
                "mem0 config: Qdrant collection %s 维度不匹配 (实际 %d, 期望 %d)，"
                "先备份 payload 再删除旧集合并重建",
                collection_name, actual_dims, expected_dims,
            )
            backup_path = _backup_collection_payload(client, collection_name, path)
            if backup_path:
                logger.warning(
                    "mem0 config: 旧 collection payload 已备份到 %s",
                    backup_path,
                )
            else:
                logger.error(
                    "mem0 config: 备份失败，拒绝删除 collection %s。"
                    "请手动迁移后重启服务。",
                    collection_name,
                )
                return  # 备份失败就不删除

            client.delete_collection(collection_name)
            # mem0 初始化时会按 expected_dims 自动创建新集合
        finally:
            client.close()
    except Exception as e:
        # 文件锁冲突（AlreadyLocked）说明 mem0 已初始化并在用此 collection，
        # 维度必然匹配（否则写入早就报错），可安全忽略。
        logger.debug("mem0 config: 检查/重建 Qdrant collection 时出错（已忽略）: %s", e)


def _env(key: str, default: str = "") -> str:
    return (os.environ.get(key) or "").strip() or default


def _get_mongo_connection_info() -> Tuple[str, str]:
    """获取 MongoDB 连接 URI 和数据库名（用于 mem0 向量存储）。

    优先从 app.core.config.settings 读取，回退到环境变量。
    """
    try:
        from app.core.config import settings
        return settings.MONGO_URI, settings.MONGO_DB
    except Exception:
        # 回退：从环境变量构建
        host = _env("MONGODB_HOST", "localhost")
        port = _env("MONGODB_PORT", "27017")
        db_name = _env("MONGODB_DATABASE", "tradingagents")
        username = _env("MONGODB_USERNAME", "")
        password = _env("MONGODB_PASSWORD", "")
        auth_source = _env("MONGODB_AUTH_SOURCE", "admin")
        # 也支持直接传入完整连接串
        conn_str = _env("MONGODB_CONNECTION_STRING", "") or _env("MONGODB_URL", "")
        if conn_str:
            return conn_str, db_name
        if username and password:
            return (
                f"mongodb://{username}:{password}@{host}:{port}/{db_name}?authSource={auth_source}",
                db_name,
            )
        return f"mongodb://{host}:{port}/{db_name}", db_name


def _get_sync_db():
    """获取同步 MongoDB 连接"""
    try:
        from app.core.database import get_mongo_db_sync
        return get_mongo_db_sync()
    except Exception:
        return None


def _read_active_system_config(db=None) -> Dict[str, Any]:
    """读取当前生效的 system_configs 文档。"""
    sync_db = None
    try:
        if db is not None:
            from pymongo.database import Database as SyncDatabase

            if isinstance(db, SyncDatabase):
                sync_db = db
            else:
                sync_db = _get_sync_db()
        else:
            sync_db = _get_sync_db()

        if sync_db is None:
            return {}

        doc = sync_db.system_configs.find_one(
            {"is_active": True}, sort=[("version", -1)]
        )
        if inspect.isawaitable(doc):
            logger.warning("mem0 config: 检测到异步数据库代理，自动回退到同步配置读取")
            fallback_db = _get_sync_db()
            if fallback_db is None:
                return {}
            doc = fallback_db.system_configs.find_one(
                {"is_active": True}, sort=[("version", -1)]
            )
        return doc or {}
    except Exception as e:
        logger.debug("mem0 config: 无法从数据库读取配置: %s", e)
        return {}


def _read_system_settings(db=None) -> Tuple[dict, list]:
    """从 system_configs 读取 system_settings 和 llm_configs"""
    doc = _read_active_system_config(db)
    return doc.get("system_settings") or {}, doc.get("llm_configs") or []


def _get_embedding_dimension(model_name: str) -> int:
    try:
        from core.llm.embedding_manager import EMBEDDING_DIMENSIONS

        model_key = (model_name or "").strip()
        dims = EMBEDDING_DIMENSIONS.get(model_key)
        if dims is not None:
            return int(dims)
        logger.warning(
            "mem0 config: Embedding 模型 '%s' 不在维度表中，默认使用 1024 维。"
            "若实际维度不符（写入时报 ValueError: shapes not aligned），"
            "请在 core/llm/embedding_manager.py 的 EMBEDDING_DIMENSIONS 中补充该模型的维度。",
            model_key,
        )
        return int(EMBEDDING_DIMENSIONS.get("default", 1024))
    except Exception:
        return 1024


def _normalize_openai_base_url(base_url: str) -> str:
    normalized = (base_url or "").strip()
    if not normalized:
        return ""
    if normalized.rstrip("/").endswith("/v1"):
        return normalized.rstrip("/")
    return f"{normalized.rstrip('/')}/v1"


def _parse_default_embedding_model(db_settings: dict) -> Tuple[str, str]:
    default_emb = str(db_settings.get("default_embedding_model") or "").strip()
    if not default_emb or ":" not in default_emb:
        return "", ""
    provider_name, model_name = default_emb.split(":", 1)
    return provider_name.strip().lower(), model_name.strip()


def _get_embedding_provider_candidates(sync_db) -> list:
    try:
        cursor = sync_db.llm_providers.find(
            {
                "supported_features": "embedding",  # 🔥 直接匹配，避免 $in 在某些 MongoDB 版本上返回空结果
                "is_active": True,
            }
        ).sort("created_at", 1)
        return list(cursor)
    except Exception as e:
        logger.debug("mem0 config: 无法读取 embedding provider 列表: %s", e)
        return []


def _resolve_mem0_provider(provider_name: str) -> Optional[str]:
    normalized = (provider_name or "").strip().lower()
    if normalized in _MEM0_OPENAI_COMPATIBLE_PROVIDERS:
        return "openai"
    return _MEM0_DIRECT_PROVIDER_MAP.get(normalized)


def _build_embedder_config_from_provider_doc(provider_doc: dict, model_name: str) -> dict:
    provider_name = str(provider_doc.get("name") or "").strip().lower()
    mem0_provider = _resolve_mem0_provider(provider_name)
    if not mem0_provider:
        return {}

    selected_model = (model_name or "").strip() or str(provider_doc.get("embedding_model") or "").strip()
    if not selected_model:
        selected_model = _DEFAULT_EMBEDDING_MODELS.get(provider_name, _DEFAULT_EMBEDDING_MODELS.get(mem0_provider, ""))
    if not selected_model:
        return {}

    config: Dict[str, Any] = {
        "model": selected_model,
        "embedding_dims": _get_embedding_dimension(selected_model),
    }

    api_key = str(provider_doc.get("api_key") or "").strip()
    base_url = str(provider_doc.get("default_base_url") or provider_doc.get("base_url") or "").strip()

    if mem0_provider == "openai":
        if not api_key:
            return {}
        config["api_key"] = api_key
        config["openai_base_url"] = _normalize_openai_base_url(base_url)
    elif mem0_provider == "gemini":
        if not api_key:
            return {}
        config["api_key"] = api_key
        if not selected_model.startswith("models/"):
            config["model"] = f"models/{selected_model}"
    elif mem0_provider == "ollama":
        config["ollama_base_url"] = base_url or "http://localhost:11434"

    return {
        "provider": mem0_provider,
        "config": config,
    }


def _build_mem0_llm_config_from_unified_config(llm_config: Any) -> dict:
    """将统一 LLMConfig 转换为 mem0 所需的 LLM 配置。"""
    provider_name = str(getattr(llm_config, "provider", "") or "").strip().lower()
    model_name = str(getattr(llm_config, "model", "") or "").strip() or "deepseek-chat"
    api_key = str(getattr(llm_config, "api_key", "") or "").strip()
    base_url = str(getattr(llm_config, "base_url", "") or "").strip()

    mem0_provider = "openai"
    if provider_name in {"google", "gemini"}:
        mem0_provider = "gemini"
    elif provider_name == "ollama":
        mem0_provider = "ollama"

    config: Dict[str, Any] = {
        "model": model_name,
        "temperature": float(getattr(llm_config, "temperature", 0.1) or 0.1),
        "max_tokens": int(getattr(llm_config, "max_tokens", 2000) or 2000),
    }

    if mem0_provider == "openai":
        config["api_key"] = api_key
        if base_url:
            config["openai_base_url"] = _normalize_openai_base_url(base_url)
    elif mem0_provider == "gemini":
        config["api_key"] = api_key
        if not model_name.startswith("models/"):
            config["model"] = f"models/{model_name}"
    else:
        config["ollama_base_url"] = base_url or "http://localhost:11434"

    return {
        "provider": mem0_provider,
        "config": config,
    }


def _resolve_embedding_from_db(db_settings: dict) -> dict:
    """从数据库 default_embedding_model 解析 embedding 配置"""
    preferred_provider_name, preferred_model_name = _parse_default_embedding_model(db_settings)

    sync_db = _get_sync_db()
    if sync_db is None:
        return {}

    try:
        provider_docs = _get_embedding_provider_candidates(sync_db)
        if not provider_docs:
            return {}

        preferred_doc = None
        if preferred_provider_name:
            for provider_doc in provider_docs:
                provider_name = str(provider_doc.get("name") or "").strip().lower()
                if provider_name == preferred_provider_name:
                    preferred_doc = provider_doc
                    break

        if preferred_doc:
            embedder = _build_embedder_config_from_provider_doc(preferred_doc, preferred_model_name)
            if embedder:
                return embedder
            logger.warning(
                "mem0 config: 默认 Embedding 模型 %s:%s 不兼容 mem0 或缺少凭证，尝试回退到其他可用 provider",
                preferred_provider_name,
                preferred_model_name,
            )

        for provider_doc in provider_docs:
            provider_name = str(provider_doc.get("name") or "").strip().lower()
            if preferred_provider_name and provider_name == preferred_provider_name:
                continue
            embedder = _build_embedder_config_from_provider_doc(provider_doc, "")
            if embedder:
                logger.info("mem0 config: Embedding provider 回退到 %s", provider_name)
                return embedder

        return {}
    except Exception as e:
        logger.debug("mem0 config: embedding 解析失败: %s", e)
        return {}


def build_mem0_config(db=None) -> Dict[str, Any]:
    """
    构建 mem0 Memory.from_config() 所需的完整 config dict。

    LLM / Embedding 配置直接从数据库 system_configs + llm_providers 读取，
    与分析流程使用相同的模型和凭证。
    """
    # 🔧 京东云模式：使用环境变量配置，跳过数据库查询
    from app.core.jdyun import (
        is_jdyun_mode, get_jdyun_api_base, get_jdyun_api_key,
        get_jdyun_embedding_model, get_jdyun_default_model,
        JDYUN_EMBEDDING_DIMS, JDYUN_PROVIDER_NAME,
    )
    if is_jdyun_mode():
        jdyun_api_base = get_jdyun_api_base()
        jdyun_api_key = get_jdyun_api_key()
        jdyun_embedding_model = get_jdyun_embedding_model()
        jdyun_chat_model = get_jdyun_default_model()

        logger.info(
            "mem0 config: 京东云模式 — embedding=%s, chat=%s, api_base=%s",
            jdyun_embedding_model, jdyun_chat_model, jdyun_api_base,
        )

        # Embedder: 使用京东云 OpenAI 兼容接口
        embedder = {
            "provider": "openai",
            "config": {
                "model": jdyun_embedding_model,
                "api_key": jdyun_api_key,
                "openai_base_url": _normalize_openai_base_url(jdyun_api_base),
                "embedding_dims": JDYUN_EMBEDDING_DIMS,
            },
        }
        collection_name = _build_mem0_collection_name(embedder)

        # Vector Store: MongoDB（与业务数据统一存储，客户端 cosine 相似度）
        mongo_uri, mongo_db_name = _get_mongo_connection_info()
        vector_store = {
            "provider": "mongodb",
            "config": {
                "mongo_uri": mongo_uri,
                "db_name": mongo_db_name,
                "collection_name": collection_name,
                "embedding_model_dims": JDYUN_EMBEDDING_DIMS,
            },
        }

        # LLM: 使用京东云 OpenAI 兼容接口
        llm = {
            "provider": "openai",
            "config": {
                "api_key": jdyun_api_key,
                "model": jdyun_chat_model,
                "openai_base_url": _normalize_openai_base_url(jdyun_api_base),
                "temperature": 0.1,
                "max_tokens": 2000,
            },
        }

        from .prompts import FINANCIAL_FACT_EXTRACTION_PROMPT

        return {
            "vector_store": vector_store,
            "llm": llm,
            "embedder": embedder,
            "custom_prompt": FINANCIAL_FACT_EXTRACTION_PROMPT,
            "version": "v1.1",
        }

    # ===== 非京东云模式：原有逻辑 =====
    config_doc = _read_active_system_config(db)
    db_settings = config_doc.get("system_settings") or {}
    llm_configs = config_doc.get("llm_configs") or []

    # --- Embedder: 复用系统 default_embedding_model ---
    embedder = _resolve_embedding_from_db(db_settings)
    collection_name = _build_mem0_collection_name(embedder)

    # --- Vector Store: MongoDB（与业务数据统一存储，客户端 cosine 相似度）---
    # 不再使用 Qdrant，向量和业务数据统一存储在 MongoDB 中。
    # 维度不匹配时由客户端 cosine 自动处理（跳过维度不兼容的向量）。
    embedding_dims = 1024
    if embedder:
        embedding_dims = int(embedder.get("config", {}).get("embedding_dims") or embedding_dims)

    mongo_uri, mongo_db_name = _get_mongo_connection_info()
    vector_store = {
        "provider": "mongodb",
        "config": {
            "mongo_uri": mongo_uri,
            "db_name": mongo_db_name,
            "collection_name": collection_name,
            "embedding_model_dims": embedding_dims,
        },
    }

    # --- LLM: 复用统一的系统模型选择与凭证解析逻辑 ---
    llm = None
    try:
        from app.services.intelligent_assistant_service import get_system_llm_config_from_config_doc

        resolved_llm_config = get_system_llm_config_from_config_doc(
            config_doc,
            model_keys=["quick_analysis_model", "deep_analysis_model"],
        )
        if resolved_llm_config is not None:
            llm = _build_mem0_llm_config_from_unified_config(resolved_llm_config)
    except Exception as e:
        logger.debug("mem0 config: 统一 LLM 解析失败: %s", e)

    if llm is None:
        target_model = (
            db_settings.get("quick_analysis_model")
            or db_settings.get("deep_analysis_model")
        )
        if not target_model and llm_configs:
            for cfg in llm_configs:
                if cfg.get("enabled", True) and cfg.get("model_name"):
                    target_model = cfg["model_name"]
                    break

        llm = {
            "provider": "openai",
            "config": {
                "api_key": "",
                "model": target_model or "deepseek-chat",
                "temperature": 0.1,
                "max_tokens": 2000,
            },
        }

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


def summarize_mem0_config(config: Dict[str, Any]) -> Dict[str, Any]:
    """返回 mem0 配置的安全摘要，不包含明文密钥。"""
    vector_store = config.get("vector_store") or {}
    vector_store_cfg = vector_store.get("config") or {}

    llm = config.get("llm") or {}
    llm_cfg = llm.get("config") or {}

    embedder = config.get("embedder") or {}
    embedder_cfg = embedder.get("config") or {}

    return {
        "vector_store": {
            "provider": vector_store.get("provider") or "",
            "collection_name": vector_store_cfg.get("collection_name") or "",
            "db_name": vector_store_cfg.get("db_name") or "",
            "embedding_model_dims": vector_store_cfg.get("embedding_model_dims") or 0,
        },
        "llm": {
            "provider": llm.get("provider") or "",
            "model": llm_cfg.get("model") or "",
            "base_url": llm_cfg.get("openai_base_url") or "",
            "has_api_key": bool(llm_cfg.get("api_key")),
        },
        "embedder": {
            "provider": embedder.get("provider") or "",
            "model": embedder_cfg.get("model") or "",
            "base_url": embedder_cfg.get("openai_base_url") or embedder_cfg.get("ollama_base_url") or "",
            "embedding_dims": embedder_cfg.get("embedding_dims") or 0,
            "has_api_key": bool(embedder_cfg.get("api_key")),
        },
    }


def describe_mem0_config(db=None) -> Dict[str, Any]:
    """返回 mem0 当前解析配置的安全摘要，不包含明文密钥。"""
    return summarize_mem0_config(build_mem0_config(db))
