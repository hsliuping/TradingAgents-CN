"""
检查模板结构
"""

from pymongo import MongoClient
import json

# 连接MongoDB
client = MongoClient("mongodb://admin:tradingagents123@127.0.0.1:27017/tradingagents?authSource=admin")
db = client["tradingagents"]
templates_collection = db["prompt_templates"]

# 获取一个debators模板
template = templates_collection.find_one({"agent_type": "debators", "agent_name": "aggressive_debator"})

if template:
    print("\n模板结构:")
    print("=" * 80)
    for key, value in template.items():
        if key == "_id":
            print(f"  {key}: {value}")
        elif key == "content":
            print(f"  {key}: (长度: {len(str(value))} 字符)")
        else:
            print(f"  {key}: {value}")
else:
    print("❌ 未找到模板")

