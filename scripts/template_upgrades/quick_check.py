import os
from pymongo import MongoClient

# 带认证的连接
client = MongoClient("mongodb://admin:tradingagents123@127.0.0.1:27017/tradingagents?authSource=admin")
db = client["tradingagents"]
collection = db["prompt_templates"]

# 查询所有持仓分析模板
templates = list(collection.find({
    "agent_type": "position_analysis_v2",
    "is_system": True
}, {
    "agent_name": 1,
    "preference_type": 1,
    "_id": 0
}).sort([("agent_name", 1), ("preference_type", 1)]))

print(f"找到 {len(templates)} 个持仓分析模板:\n")
for t in templates:
    print(f"  {t['agent_name']:20s} / {t['preference_type']}")

