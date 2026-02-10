"""检查 system_configs 和 llm_providers 中的 API Key"""
import os
import sys
sys.path.insert(0, '.')

from dotenv import load_dotenv
load_dotenv()

from pymongo import MongoClient

MONGO_URI = os.getenv('MONGO_URI', 'mongodb://localhost:27017')
MONGO_DB = os.getenv('MONGO_DB', 'tradingagents')

client = MongoClient(MONGO_URI)
db = client[MONGO_DB]

# 1. 查看 system_configs 中 llm_configs 的 api_key 值
doc = db.system_configs.find_one({"is_active": True}, sort=[("version", -1)])
if doc and "llm_configs" in doc:
    configs = doc["llm_configs"]
    print(f"=== system_configs.llm_configs ({len(configs)} 个模型) ===")
    for i, cfg in enumerate(configs):
        model = cfg.get("model_name", "unknown")
        provider = cfg.get("provider", "unknown")
        api_key = cfg.get("api_key", "")
        if api_key:
            print(f"  [{i}] {provider}/{model}: api_key = {api_key}")
        else:
            print(f"  [{i}] {provider}/{model}: api_key = (空)")
else:
    print("未找到 system_configs")

print()

# 2. 查看 llm_providers 中所有厂家的 api_key
print("=== llm_providers ===")
for provider_doc in db.llm_providers.find():
    name = provider_doc.get("name", "unknown")
    api_key = provider_doc.get("api_key", "")
    if api_key:
        print(f"  {name}: api_key = {api_key}")
    else:
        print(f"  {name}: api_key = (空)")

print()

# 3. 查看环境变量
print("=== 环境变量 ===")
env_key = os.getenv("DASHSCOPE_API_KEY", "")
print(f"  DASHSCOPE_API_KEY = {env_key}")

client.close()

