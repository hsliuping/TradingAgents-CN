#!/usr/bin/env python
"""检查 v2.0 提示词模板"""

import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

from pymongo import MongoClient
import json

# 从环境变量获取数据库连接
host = os.getenv('MONGODB_HOST', 'localhost')
port = os.getenv('MONGODB_PORT', '27017')
username = os.getenv('MONGODB_USERNAME', '')
password = os.getenv('MONGODB_PASSWORD', '')
db_name = os.getenv('MONGODB_DATABASE', 'tradingagents')
auth_source = os.getenv('MONGODB_AUTH_SOURCE', 'admin')

if username and password:
    mongo_uri = f"mongodb://{username}:{password}@{host}:{port}/{db_name}?authSource={auth_source}"
else:
    mongo_uri = f"mongodb://{host}:{port}/{db_name}"

client = MongoClient(mongo_uri)
db = client[db_name]

# 查看 v2.0 分析师的提示词模板
templates = list(db['prompt_templates'].find({
    'agent_type': 'analysts_v2',
    'is_system': True
}, {'agent_name': 1, 'template_name': 1, 'preference_type': 1, 'content': 1, 'version': 1, '_id': 0}).sort([('agent_name', 1), ('preference_type', 1)]))

print(f"找到 {len(templates)} 个 v2.0 分析师模板\n")

# 只显示前4个作为示例
for t in templates[:4]:
    print('='*60)
    print(f"Agent: {t['agent_name']}")
    print(f"Template: {t['template_name']}")
    print(f"Preference: {t.get('preference_type', 'N/A')}")
    print(f"Version: {t.get('version', 'N/A')}")
    content = t.get('content', {})

    system_prompt = content.get('system_prompt', 'N/A')
    user_prompt = content.get('user_prompt', 'N/A')
    tool_guidance = content.get('tool_guidance', 'N/A')

    print(f"\n📋 System Prompt ({len(system_prompt)} chars):")
    print(system_prompt[:400] + "..." if len(system_prompt) > 400 else system_prompt)

    print(f"\n📝 User Prompt ({len(user_prompt)} chars):")
    print(user_prompt[:300] + "..." if len(user_prompt) > 300 else user_prompt)

    print(f"\n🔧 Tool Guidance ({len(tool_guidance)} chars):")
    print(tool_guidance[:250] + "..." if len(tool_guidance) > 250 else tool_guidance)
    print()

# 汇总表
print("\n" + "="*60)
print("📊 模板汇总表")
print("="*60)
print(f"{'Agent':<30} {'Preference':<15} {'Version':<10}")
print("-"*60)
for t in templates:
    print(f"{t['agent_name']:<30} {t.get('preference_type', 'N/A'):<15} {t.get('version', 'N/A'):<10}")

