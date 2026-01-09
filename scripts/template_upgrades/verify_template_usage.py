#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
验证 Agent 代码中的模板调用是否与数据库一致
"""

import os
import re
from pathlib import Path
from pymongo import MongoClient

# 带认证的连接
client = MongoClient("mongodb://admin:tradingagents123@127.0.0.1:27017/tradingagents?authSource=admin")
db = client["tradingagents"]
collection = db["prompt_templates"]

# 需要检查的 Agent 文件
AGENT_FILES = [
    "core/agents/adapters/bull_researcher_v2.py",
    "core/agents/adapters/bear_researcher_v2.py",
    "core/agents/adapters/risk_manager_v2.py",
    "core/agents/adapters/trader_v2.py",
    "core/agents/adapters/risky_analyst_v2.py",
    "core/agents/adapters/safe_analyst_v2.py",
    "core/agents/adapters/neutral_analyst_v2.py",
]

print("=" * 100)
print("验证 Agent 代码中的模板调用是否与数据库一致")
print("=" * 100)

# 正则表达式匹配 get_agent_prompt 调用
pattern = re.compile(
    r'get_agent_prompt\(\s*'
    r'agent_type="([^"]+)",\s*'
    r'agent_name="([^"]+)",',
    re.MULTILINE
)

errors = []
success = []

for file_path in AGENT_FILES:
    full_path = Path(file_path)
    if not full_path.exists():
        errors.append(f"❌ 文件不存在: {file_path}")
        continue
    
    with open(full_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    matches = pattern.findall(content)
    
    if not matches:
        errors.append(f"⚠️  未找到 get_agent_prompt 调用: {file_path}")
        continue
    
    for agent_type, agent_name in matches:
        # 检查数据库中是否存在对应的模板
        template = collection.find_one({
            "agent_type": agent_type,
            "agent_name": agent_name,
            "is_system": True
        })
        
        if template:
            success.append(f"✅ {file_path:50s} -> {agent_type}/{agent_name}")
        else:
            errors.append(f"❌ {file_path:50s} -> {agent_type}/{agent_name} (数据库中不存在)")

print("\n" + "=" * 100)
print("验证结果")
print("=" * 100)

if success:
    print(f"\n✅ 成功匹配 ({len(success)} 个):\n")
    for msg in success:
        print(f"  {msg}")

if errors:
    print(f"\n❌ 错误 ({len(errors)} 个):\n")
    for msg in errors:
        print(f"  {msg}")
else:
    print("\n🎉 所有 Agent 代码都正确使用了 v2.0 模板！")

print("\n" + "=" * 100)

