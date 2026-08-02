"""检查 system_configs 中的 embedding 配置与 llm_providers。"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env"))

from pymongo import MongoClient

MONGO_HOST = os.environ.get("MONGODB_HOST", "127.0.0.1")
MONGO_USER = os.environ.get("MONGODB_USERNAME", "")
MONGO_PASS = os.environ.get("MONGODB_PASSWORD", "")
MONGO_AUTH_SOURCE = os.environ.get("MONGODB_AUTH_SOURCE", "admin")
MONGO_PORT = 27019
MONGO_DB = os.environ.get("MONGODB_DATABASE", "tradingagents")

if MONGO_USER and MONGO_PASS:
    MONGO_URI = f"mongodb://{MONGO_USER}:{MONGO_PASS}@{MONGO_HOST}:{MONGO_PORT}/?authSource={MONGO_AUTH_SOURCE}"
else:
    MONGO_URI = f"mongodb://{MONGO_HOST}:{MONGO_PORT}/"


def main():
    client = MongoClient(MONGO_URI)
    db = client[MONGO_DB]

    config_doc = db.system_configs.find_one({"is_active": True}, sort=[("version", -1)])
    if not config_doc:
        print("未找到 system_configs")
        return

    db_settings = config_doc.get("system_settings") or {}
    print("system_settings.default_embedding_model:", db_settings.get("default_embedding_model"))
    print("system_settings.quick_analysis_model:", db_settings.get("quick_analysis_model"))
    print("system_settings.deep_analysis_model:", db_settings.get("deep_analysis_model"))

    print("\n所有 llm_providers 中 supported_features 包含 embedding 的：")
    providers = list(db.llm_providers.find({
        "supported_features": {"$in": ["embedding"]},
        "is_active": True,
    }).sort("created_at", 1))

    for p in providers:
        print(f"  - name={p.get('name')} embedding_model={p.get('embedding_model')} api_key_set={bool(p.get('api_key'))} base_url={p.get('default_base_url') or p.get('base_url')}")

    print("\n所有 llm_configs 中 enabled 且可能用于 embedding 的：")
    for cfg in config_doc.get("llm_configs") or []:
        features = cfg.get("features") or []
        if "embedding" in features or cfg.get("role") == "embedding":
            print(f"  - {cfg.get('model_name')} ({cfg.get('provider')}) enabled={cfg.get('enabled', True)} features={features}")


if __name__ == "__main__":
    main()
