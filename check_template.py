#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""检查模板内容"""

import os
from pymongo import MongoClient

# 加载 .env 配置
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    print("⚠️ dotenv 未安装，使用默认配置")

# 从 .env 读取数据库配置
host = os.getenv('MONGODB_HOST', 'localhost')
port = os.getenv('MONGODB_PORT', '27017')
username = os.getenv('MONGODB_USERNAME', '')
password = os.getenv('MONGODB_PASSWORD', '')
db_name = os.getenv('MONGODB_DATABASE', 'tradingagents')
auth_source = os.getenv('MONGODB_AUTH_SOURCE', 'admin')

# 构建 MongoDB 连接字符串
if username and password:
    mongo_uri = f"mongodb://{username}:{password}@{host}:{port}/{db_name}?authSource={auth_source}"
else:
    mongo_uri = f"mongodb://{host}:{port}/{db_name}"

print(f"📊 连接数据库: {host}:{port}/{db_name}\n")

client = MongoClient(mongo_uri)
db = client[db_name]

# 查找系统模板
system_template = db['prompt_templates'].find_one({
    'agent_type': 'managers_v2',
    'agent_name': 'research_manager_v2',
    'preference_type': 'neutral',
    'is_system': True,
    'status': 'active'
})

if system_template:
    print("✅ 找到系统模板\n")
    print("=" * 80)
    content = system_template.get('content', {})
    print(f"模板字段: {list(content.keys())}\n")

    # 检查是否有 user_prompt
    if 'user_prompt' in content:
        print("✅ 包含 user_prompt 字段")
        print(f"\n用户提示词长度: {len(content['user_prompt'])} 字符")
        print(f"\n用户提示词内容:\n{content['user_prompt']}")
    else:
        print("❌ 不包含 user_prompt 字段")
        print("\n可用字段:")
        for key in content.keys():
            value = content[key]
            if isinstance(value, str):
                print(f"  - {key}: {len(value)} 字符")
            else:
                print(f"  - {key}: {type(value)}")

    print("=" * 80)
else:
    print("❌ 未找到系统模板")

