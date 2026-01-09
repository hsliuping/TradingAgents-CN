#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
验证 Agent 代码中使用的 agent_type/agent_name 与数据库模板是否匹配
"""

import os
from pymongo import MongoClient

# 带认证的连接
client = MongoClient("mongodb://admin:tradingagents123@127.0.0.1:27017/tradingagents?authSource=admin")
db = client["tradingagents"]
collection = db["prompt_templates"]

print("=" * 80)
print("验证 Agent 代码与数据库模板的匹配情况")
print("=" * 80)

# 定义 Agent 代码中使用的参数
agent_configs = [
    {
        "file": "technical_analyst_v2.py",
        "agent_type": "position_analysis_v2",
        "agent_name": "pa_technical_v2",
        "preference_ids": ["neutral", "with_cache_aggressive", "with_cache_neutral", "with_cache_conservative", 
                          "without_cache_aggressive", "without_cache_neutral", "without_cache_conservative"]
    },
    {
        "file": "fundamental_analyst_v2.py",
        "agent_type": "position_analysis_v2",
        "agent_name": "pa_fundamental_v2",
        "preference_ids": ["neutral", "with_cache_aggressive", "with_cache_neutral", "with_cache_conservative",
                          "without_cache_aggressive", "without_cache_neutral", "without_cache_conservative"]
    },
    {
        "file": "risk_assessor_v2.py",
        "agent_type": "position_analysis_v2",
        "agent_name": "pa_risk_v2",
        "preference_ids": ["neutral", "aggressive", "conservative"]
    },
    {
        "file": "action_advisor_v2.py",
        "agent_type": "position_analysis_v2",
        "agent_name": "pa_advisor_v2",
        "preference_ids": ["neutral", "aggressive", "conservative"]
    }
]

total_checks = 0
passed_checks = 0
failed_checks = []

for config in agent_configs:
    print(f"\n📄 {config['file']}")
    print(f"   agent_type: {config['agent_type']}")
    print(f"   agent_name: {config['agent_name']}")
    
    for preference_id in config['preference_ids']:
        total_checks += 1
        
        # 查询数据库
        template = collection.find_one({
            "agent_type": config['agent_type'],
            "agent_name": config['agent_name'],
            "preference_type": preference_id,
            "is_system": True
        })
        
        if template:
            print(f"   ✅ {preference_id:30s} - 找到模板")
            passed_checks += 1
        else:
            print(f"   ❌ {preference_id:30s} - 缺失模板")
            failed_checks.append({
                "file": config['file'],
                "agent_type": config['agent_type'],
                "agent_name": config['agent_name'],
                "preference_id": preference_id
            })

print("\n" + "=" * 80)
print(f"📊 检查结果: {passed_checks}/{total_checks} 通过")

if failed_checks:
    print(f"\n❌ 发现 {len(failed_checks)} 个问题:")
    for fail in failed_checks:
        print(f"   - {fail['file']}: {fail['agent_name']}/{fail['preference_id']}")
    print("\n💡 建议:")
    print("   1. 检查数据库中的模板是否存在")
    print("   2. 检查 agent_type 和 agent_name 是否匹配")
    print("   3. 检查 preference_type 字段名是否正确")
else:
    print("\n✅ 所有检查通过！Agent 代码与数据库模板完全匹配")

print("\n" + "=" * 80)
print("🔍 数据库中的实际模板:")
print("=" * 80)

# 查询所有持仓分析模板
templates = list(collection.find({
    "agent_type": "position_analysis_v2",
    "is_system": True
}, {
    "agent_name": 1,
    "preference_type": 1,
    "_id": 0
}).sort([("agent_name", 1), ("preference_type", 1)]))

current_agent = None
for t in templates:
    if t['agent_name'] != current_agent:
        current_agent = t['agent_name']
        print(f"\n{current_agent}:")
    print(f"  - {t['preference_type']}")

print("\n" + "=" * 80)

