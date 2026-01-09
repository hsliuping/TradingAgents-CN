#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
检查数据库中所有 v2.0 模板的命名风格是否一致
"""

import os
from pymongo import MongoClient
from collections import defaultdict

# 带认证的连接
client = MongoClient("mongodb://admin:tradingagents123@127.0.0.1:27017/tradingagents?authSource=admin")
db = client["tradingagents"]
collection = db["prompt_templates"]

print("=" * 100)
print("检查数据库中所有 v2.0 模板的命名风格")
print("=" * 100)

# 查询所有系统模板
all_templates = list(collection.find(
    {"is_system": True},
    {"agent_type": 1, "agent_name": 1, "preference_type": 1, "_id": 0}
).sort([("agent_type", 1), ("agent_name", 1), ("preference_type", 1)]))

# 按 agent_type 分组
by_type = defaultdict(lambda: defaultdict(list))
for t in all_templates:
    agent_type = t.get("agent_type", "unknown")
    agent_name = t.get("agent_name", "unknown")
    preference_type = t.get("preference_type", "unknown")
    by_type[agent_type][agent_name].append(preference_type)

print(f"\n找到 {len(all_templates)} 个系统模板\n")

# 分析命名风格
v1_types = []  # 没有 _v2 后缀的 agent_type
v2_types = []  # 有 _v2 后缀的 agent_type
mixed_types = []  # 混合的（同一个类型下有些有 _v2，有些没有）

for agent_type in sorted(by_type.keys()):
    agents = by_type[agent_type]
    
    print(f"\n📁 {agent_type}")
    
    # 检查这个类型下的所有 agent_name
    has_v2_suffix = agent_type.endswith("_v2")
    
    if has_v2_suffix:
        v2_types.append(agent_type)
    else:
        v1_types.append(agent_type)
    
    for agent_name in sorted(agents.keys()):
        preferences = agents[agent_name]
        agent_has_v2 = agent_name.endswith("_v2")
        
        # 检查一致性
        if has_v2_suffix != agent_has_v2:
            status = "⚠️ 不一致"
            if agent_type not in mixed_types:
                mixed_types.append(agent_type)
        else:
            status = "✅"
        
        print(f"  {status} {agent_name:30s} ({len(preferences)} 个偏好)")

print("\n" + "=" * 100)
print("📊 命名风格统计")
print("=" * 100)

print(f"\n✅ 有 _v2 后缀的 agent_type ({len(v2_types)} 个):")
for t in v2_types:
    print(f"  - {t}")

print(f"\n📝 没有 _v2 后缀的 agent_type ({len(v1_types)} 个):")
for t in v1_types:
    print(f"  - {t}")

if mixed_types:
    print(f"\n⚠️ 命名不一致的 agent_type ({len(mixed_types)} 个):")
    for t in mixed_types:
        print(f"  - {t}")
        print(f"    问题: agent_type 和 agent_name 的 _v2 后缀不匹配")

print("\n" + "=" * 100)
print("🔍 详细分析")
print("=" * 100)

# 检查是否所有 v2.0 相关的模板都使用了一致的命名
v2_related = []
for agent_type in by_type.keys():
    for agent_name in by_type[agent_type].keys():
        if "_v2" in agent_type or "_v2" in agent_name:
            v2_related.append((agent_type, agent_name))

print(f"\n找到 {len(v2_related)} 个 v2.0 相关的 agent:")

consistent_v2 = []
inconsistent_v2 = []

for agent_type, agent_name in sorted(set(v2_related)):
    type_has_v2 = agent_type.endswith("_v2")
    name_has_v2 = agent_name.endswith("_v2")
    
    if type_has_v2 and name_has_v2:
        consistent_v2.append((agent_type, agent_name))
        print(f"  ✅ {agent_type:30s} / {agent_name}")
    else:
        inconsistent_v2.append((agent_type, agent_name))
        print(f"  ⚠️ {agent_type:30s} / {agent_name}")
        if not type_has_v2:
            print(f"     问题: agent_type 缺少 _v2 后缀")
        if not name_has_v2:
            print(f"     问题: agent_name 缺少 _v2 后缀")

print("\n" + "=" * 100)
print("📋 结论")
print("=" * 100)

if inconsistent_v2:
    print(f"\n❌ 数据库命名不一致！")
    print(f"   - 一致的 v2.0 模板: {len(consistent_v2)} 个")
    print(f"   - 不一致的 v2.0 模板: {len(inconsistent_v2)} 个")
    print(f"\n💡 建议: 统一数据库中的命名风格，所有 v2.0 模板都应该使用 _v2 后缀")
else:
    print(f"\n✅ 数据库命名一致！")
    print(f"   - 所有 v2.0 模板都使用了 _v2 后缀")
    print(f"   - 共 {len(consistent_v2)} 个 v2.0 agent")
    print(f"\n💡 建议: 修改代码中的调用，使用 _v2 后缀")

print("\n" + "=" * 100)

