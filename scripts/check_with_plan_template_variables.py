#!/usr/bin/env python3
"""检查 with_plan 模板的变量"""

from pymongo import MongoClient
from urllib.parse import quote_plus
import re

# 连接数据库
username = quote_plus('tradingagents')
password = quote_plus('tradingagents123')
client = MongoClient(f'mongodb://{username}:{password}@localhost:27017/')
db = client['tradingagents']

# 查找模板
template = db['prompt_templates'].find_one({
    'agent_type': 'reviewers_v2',
    'agent_name': 'review_manager_v2',
    'preference_id': 'with_plan'
})

if not template:
    print("❌ 未找到 with_plan 模板")
    exit(1)

print("=== TEMPLATE INFO ===")
print(f"Name: {template.get('template_name')}")
print(f"Preference: {template.get('preference_id')}")
print(f"Version: {template.get('version')}")

# 提取用户提示词
user_prompt = template.get('content', {}).get('user_prompt', '')

print("\n=== USER PROMPT ===")
print(user_prompt)

# 提取所有变量
variables = re.findall(r'\{\{(\w+)\}\}', user_prompt)
variables.extend(re.findall(r'\{(\w+)\}', user_prompt))

print("\n=== REQUIRED VARIABLES ===")
for var in sorted(set(variables)):
    print(f"  - {var}")

