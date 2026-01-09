#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
检查 debators_v2 模板
"""

import os
from pymongo import MongoClient

# 带认证的连接
client = MongoClient("mongodb://admin:tradingagents123@127.0.0.1:27017/tradingagents?authSource=admin")
db = client["tradingagents"]
collection = db["prompt_templates"]

print("=" * 80)
print("检查 debators_v2 模板")
print("=" * 80)

# 查询所有 debators_v2 模板
templates = list(collection.find({
    "agent_type": "debators_v2",
    "is_system": True
}, {
    "agent_name": 1,
    "preference_type": 1,
    "template_name": 1,
    "_id": 0
}).sort([("agent_name", 1), ("preference_type", 1)]))

print(f"\n找到 {len(templates)} 个 debators_v2 模板:\n")
for t in templates:
    print(f"  {t['agent_name']:25s} / {t['preference_type']:15s} - {t.get('template_name', 'N/A')}")

print("\n" + "=" * 80)

