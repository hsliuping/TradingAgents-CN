"""
检查所有模板的preference_type
"""

from pymongo import MongoClient

# 连接MongoDB
client = MongoClient("mongodb://admin:tradingagents123@127.0.0.1:27017/tradingagents?authSource=admin")
db = client["tradingagents"]
templates_collection = db["prompt_templates"]

# 获取所有模板
templates = list(templates_collection.find({}))

print("\n所有模板的preference_type:")
print("=" * 80)
for t in templates:
    agent_type = t.get("agent_type", "unknown")
    agent_name = t.get("agent_name", "unknown")
    preference_type = t.get("preference_type", "unknown")
    print(f"  {agent_type}/{agent_name}: {preference_type}")

