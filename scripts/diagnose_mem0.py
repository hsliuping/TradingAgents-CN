"""诊断 mem0 / Qdrant 本地存储状态。"""
import asyncio
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# 加载项目 .env（如果存在）
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env"))

from pymongo import MongoClient

# v3.0 端口与认证（默认 27019，仅 MEM0_DIAGNOSE_MONGODB_PORT 可覆盖）
MONGO_HOST = os.environ.get("MONGODB_HOST", "127.0.0.1")
MONGO_PORT = int(os.environ.get("MEM0_DIAGNOSE_MONGODB_PORT", "27019"))
MONGO_DB = os.environ.get("MONGODB_DATABASE", "tradingagents")
MONGO_USER = os.environ.get("MONGODB_USERNAME", "")
MONGO_PASS = os.environ.get("MONGODB_PASSWORD", "")
MONGO_AUTH_SOURCE = os.environ.get("MONGODB_AUTH_SOURCE", "admin")

if MONGO_USER and MONGO_PASS:
    MONGO_URI = f"mongodb://{MONGO_USER}:{MONGO_PASS}@{MONGO_HOST}:{MONGO_PORT}/?authSource={MONGO_AUTH_SOURCE}"
else:
    MONGO_URI = f"mongodb://{MONGO_HOST}:{MONGO_PORT}/"


def main():
    print(f"连接 MongoDB: {MONGO_URI}/{MONGO_DB}")
    client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)
    db = client[MONGO_DB]

    print("\n--- system_configs 中的关键配置 ---")
    config_doc = db.system_configs.find_one({"is_active": True}, sort=[("version", -1)])
    if not config_doc:
        print("未找到 system_configs 文档")
        return

    db_settings = config_doc.get("system_settings") or {}
    llm_configs = config_doc.get("llm_configs") or []

    print(f"default_embedding_model: {db_settings.get('default_embedding_model')}")
    print(f"quick_analysis_model: {db_settings.get('quick_analysis_model')}")
    print(f"deep_analysis_model: {db_settings.get('deep_analysis_model')}")
    print(f"llm_configs count: {len(llm_configs)}")
    for cfg in llm_configs:
        print(
            f"  - {cfg.get('model_name')} ({cfg.get('provider')}) enabled={cfg.get('enabled', True)}"
        )

    print("\n--- mem0 配置摘要 ---")
    from core.memory.config import build_mem0_config, summarize_mem0_config

    config = build_mem0_config(db)
    summary = summarize_mem0_config(config)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print("\n--- mem0 完整 vector_store 配置 ---")
    print(json.dumps(config.get("vector_store", {}), ensure_ascii=False, indent=2))

    print("\n--- 磁盘上 mem0 集合 ---")
    mem0_base = os.path.abspath("./data/qdrant/mem0/collection")
    if os.path.isdir(mem0_base):
        for name in os.listdir(mem0_base):
            full = os.path.join(mem0_base, name)
            if os.path.isdir(full):
                print(f"  - {name}")
    else:
        print(f"  目录不存在: {mem0_base}")

    print("\n--- 尝试初始化 AsyncMemory ---")

    async def _init():
        from mem0 import AsyncMemory

        mem_client = AsyncMemory.from_config(config)
        if hasattr(mem_client, "__await__"):
            mem_client = await mem_client
        print("AsyncMemory 初始化成功")
        return mem_client

    try:
        mem = asyncio.run(_init())
    except Exception as e:
        print(f"AsyncMemory 初始化失败: {type(e).__name__}: {e}")
        import traceback

        traceback.print_exc()
        return

    print("\n--- 尝试写入一条测试记忆 ---")

    async def _store():
        try:
            result = await mem.add(
                [{"role": "user", "content": "诊断测试：风险治理结论示例"}],
                user_id="diagnose_user",
                agent_id="diagnose_agent",
                run_id="diagnose_run",
                metadata={"scope": "diagnose", "memory_kind": "diagnose_test"},
                infer=False,
            )
            print(f"store result: {result}")
        except Exception as e:
            print(f"store 失败: {type(e).__name__}: {e}")
            import traceback

            traceback.print_exc()

    asyncio.run(_store())

    print("\n--- 尝试召回测试记忆 ---")

    async def _search():
        try:
            results = await mem.search(
                "风险治理",
                filters={"user_id": "diagnose_user", "agent_id": "diagnose_agent"},
                limit=5,
            )
            print(f"search result: {results}")
        except Exception as e:
            print(f"search 失败: {type(e).__name__}: {e}")
            import traceback

            traceback.print_exc()

    asyncio.run(_search())


if __name__ == "__main__":
    main()
