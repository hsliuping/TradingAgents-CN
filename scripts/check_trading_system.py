# -*- coding: utf-8 -*-
"""检查交易计划的完整数据"""
from pymongo import MongoClient
from urllib.parse import quote_plus
from bson import ObjectId
import json

username = quote_plus("admin")
password = quote_plus("tradingagents123")
client = MongoClient(f"mongodb://{username}:{password}@localhost:27017/")
db = client["tradingagents"]

trading_system_id = "694bc27bd639700ce1d9dbea"

print("=" * 80)
print(f"查询交易计划: {trading_system_id}")
print("=" * 80)

trading_system = db["trading_systems"].find_one({"_id": ObjectId(trading_system_id)})

if not trading_system:
    print(f"❌ 未找到交易计划")
    exit(1)

# 移除 _id 字段以便 JSON 序列化
trading_system_copy = dict(trading_system)
trading_system_copy.pop('_id', None)
trading_system_copy.pop('created_at', None)
trading_system_copy.pop('updated_at', None)

print(json.dumps(trading_system_copy, indent=2, ensure_ascii=False))

client.close()

