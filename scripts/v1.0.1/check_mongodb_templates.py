"""
直接查询MongoDB中的模板
"""

from pymongo import MongoClient

# 连接MongoDB
client = MongoClient("mongodb://admin:tradingagents123@127.0.0.1:27017/tradingagents?authSource=admin")
db = client["tradingagents"]
templates_collection = db["prompt_templates"]

# 查询所有模板
templates = list(templates_collection.find({}))

print("\n所有模板:")
print("=" * 80)
for t in templates:
    agent_type = t.get("agent_type", "unknown")
    agent_name = t.get("agent_name", "unknown")
    status = t.get("status", "unknown")
    is_system = t.get("is_system", False)
    print(f"  {agent_type}/{agent_name} (status: {status}, is_system: {is_system})")

print("\n" + "=" * 80)
print(f"总计: {len(templates)} 个模板")

# 检查debators模板
print("\n\n检查debators模板:")
print("=" * 80)
debators = list(templates_collection.find({"agent_type": "debators"}))
for t in debators:
    print(f"  {t.get('agent_name')}: {t.get('status')}")

if not debators:
    print("  ❌ 没有找到debators模板")

