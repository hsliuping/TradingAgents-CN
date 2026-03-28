#!/usr/bin/env python3
"""
Seed MongoDB with local model/system config from environment variables.
"""

from __future__ import annotations

import argparse
import hashlib
import os
from datetime import datetime, timezone
from pathlib import Path

from pymongo import MongoClient


REPO_ROOT = Path(__file__).resolve().parents[2]


def _load_env_file(path: Path) -> None:
    if not path.exists():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip())


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _required_env(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise SystemExit(f"Missing required environment variable: {name}")
    return value


def _optional_env(name: str, default: str = "") -> str:
    return os.getenv(name, default).strip()


def _mongo_uri() -> str:
    user = _optional_env("MONGODB_USERNAME")
    password = _optional_env("MONGODB_PASSWORD")
    host = _optional_env("MONGODB_HOST", "localhost")
    port = _optional_env("MONGODB_PORT", "27017")
    database = _optional_env("MONGODB_DATABASE", "tradingagents")
    auth_source = _optional_env("MONGODB_AUTH_SOURCE", "admin")

    if user and password:
        return f"mongodb://{user}:{password}@{host}:{port}/{database}?authSource={auth_source}"
    return f"mongodb://{host}:{port}/{database}"


def _hash_password(password: str) -> str:
    return hashlib.sha256(password.encode("utf-8")).hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser(description="Initialize MongoDB local config from env variables")
    parser.add_argument("--env-file", help="Optional env file to load before seeding MongoDB")
    args = parser.parse_args()

    _load_env_file(REPO_ROOT / ".env")
    _load_env_file(REPO_ROOT / ".env.local")
    if args.env_file:
        _load_env_file(Path(args.env_file).expanduser().resolve())

    provider_name = _required_env("TA_MODEL_PROVIDER").lower()
    model_name = _required_env("TA_MODEL_NAME")
    base_url = _required_env("TA_MODEL_BASE_URL")
    provider_display_name = _optional_env("TA_PROVIDER_DISPLAY_NAME", f"{provider_name} local")
    data_source = _optional_env("TA_DEFAULT_DATA_SOURCE", "AKShare")

    admin_username = _optional_env("ADMIN_USERNAME", "admin")
    admin_password = _optional_env("ADMIN_PASSWORD", "change_me_local_admin_password")
    admin_email = _optional_env("ADMIN_EMAIL", "admin@tradingagents.local")

    client = MongoClient(_mongo_uri(), serverSelectionTimeoutMS=5000)
    client.admin.command("ping")
    db = client[_optional_env("MONGODB_DATABASE", "tradingagents")]
    now = _now()

    db.llm_providers.update_one(
        {"name": provider_name},
        {
            "$set": {
                "name": provider_name,
                "display_name": provider_display_name,
                "description": "Seeded by scripts/startup/init_local_env_db.py",
                "website": "",
                "api_doc_url": "",
                "logo_url": "",
                "is_active": True,
                "supported_features": ["chat", "completion", "function_calling", "streaming", "openai_compatible"],
                "default_base_url": base_url,
                "api_key": "",
                "extra_config": {"source": "local_env_bootstrap"},
                "updated_at": now,
            },
            "$setOnInsert": {
                "created_at": now,
            },
        },
        upsert=True,
    )

    active_config = db.system_configs.find_one({"is_active": True}, sort=[("version", -1)])
    next_version = int(active_config.get("version", 0)) + 1 if active_config else 1
    db.system_configs.update_many({"is_active": True}, {"$set": {"is_active": False}})

    system_config = {
        "config_name": "Local Env Config",
        "config_type": "system",
        "llm_configs": [
            {
                "provider": provider_name,
                "model_name": model_name,
                "model_display_name": model_name,
                "api_key": "",
                "api_base": base_url,
                "max_tokens": 4000,
                "temperature": 0.7,
                "timeout": 180,
                "retry_times": 3,
                "enabled": True,
                "description": "Seeded by scripts/startup/init_local_env_db.py",
                "model_category": None,
                "custom_endpoint": None,
                "enable_memory": False,
                "enable_debug": False,
                "priority": 100,
                "input_price_per_1k": None,
                "output_price_per_1k": None,
                "currency": "USD",
                "capability_level": 5,
                "suitable_roles": ["both"],
                "features": ["chat", "streaming", "openai_compatible"],
                "recommended_depths": ["快速", "基础", "标准", "深度"],
                "performance_metrics": {"source": "local_env_bootstrap"},
            }
        ],
        "default_llm": model_name,
        "data_source_configs": [
            {
                "name": data_source,
                "display_name": data_source,
                "type": data_source.lower(),
                "api_key": None,
                "api_secret": None,
                "endpoint": "",
                "timeout": 30,
                "rate_limit": 100,
                "enabled": True,
                "priority": 1,
                "config_params": {},
                "description": "Seeded default data source",
                "market_categories": ["a_shares", "hk_stocks", "us_stocks"],
                "provider": data_source.lower(),
                "created_at": now,
                "updated_at": now,
            }
        ],
        "default_data_source": data_source,
        "database_configs": [
            {
                "name": "MongoDB主库",
                "type": "mongodb",
                "host": _optional_env("MONGODB_HOST", "localhost"),
                "port": int(_optional_env("MONGODB_PORT", "27017")),
                "username": _optional_env("MONGODB_USERNAME"),
                "password": _optional_env("MONGODB_PASSWORD"),
                "database": _optional_env("MONGODB_DATABASE", "tradingagents"),
                "connection_params": {},
                "pool_size": 10,
                "max_overflow": 20,
                "enabled": True,
                "description": "MongoDB main database",
            },
            {
                "name": "Redis缓存",
                "type": "redis",
                "host": _optional_env("REDIS_HOST", "localhost"),
                "port": int(_optional_env("REDIS_PORT", "6379")),
                "username": None,
                "password": _optional_env("REDIS_PASSWORD"),
                "database": _optional_env("REDIS_DB", "0"),
                "connection_params": {},
                "pool_size": 10,
                "max_overflow": 20,
                "enabled": True,
                "description": "Redis cache",
            },
        ],
        "system_settings": {
            "default_model": model_name,
            "quick_analysis_model": model_name,
            "deep_analysis_model": model_name,
            "quick_think_llm": model_name,
            "deep_think_llm": model_name,
            "log_level": "INFO",
            "enable_monitoring": True,
            "enable_cache": True,
            "cache_ttl": 3600,
            "app_timezone": "Asia/Shanghai",
            "ta_use_app_cache": True,
        },
        "created_at": now,
        "updated_at": now,
        "version": next_version,
        "is_active": True,
    }
    db.system_configs.insert_one(system_config)

    db.users.update_one(
        {"username": admin_username},
        {
            "$set": {
                "email": admin_email,
                "hashed_password": _hash_password(admin_password),
                "is_active": True,
                "is_verified": True,
                "is_admin": True,
                "updated_at": now,
                "last_login": None,
                "preferences": {
                    "default_market": "A股",
                    "default_depth": "3",
                    "default_analysts": ["市场分析师", "基本面分析师"],
                    "auto_refresh": True,
                    "refresh_interval": 30,
                    "ui_theme": "light",
                    "sidebar_width": 240,
                    "language": "zh-CN",
                    "notifications_enabled": True,
                    "email_notifications": False,
                    "desktop_notifications": True,
                    "analysis_complete_notification": True,
                    "system_maintenance_notification": True,
                },
                "daily_quota": 10000,
                "concurrent_limit": 10,
                "total_analyses": 0,
                "successful_analyses": 0,
                "failed_analyses": 0,
                "favorite_stocks": [],
            },
            "$setOnInsert": {
                "created_at": now,
            },
        },
        upsert=True,
    )

    print("MongoDB local config initialized:")
    print(f"  - provider: {provider_name}")
    print(f"  - model: {model_name}")
    print(f"  - base_url: {base_url}")
    print(f"  - data source: {data_source}")
    print(f"  - admin user: {admin_username}")


if __name__ == "__main__":
    main()
