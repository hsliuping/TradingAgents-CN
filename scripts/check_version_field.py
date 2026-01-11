#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
检查数据库中 version 字段的类型和值
"""

import os
import sys
from pathlib import Path

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    print("⚠️ dotenv 未安装，使用默认配置")

from pymongo import MongoClient

# 数据库连接
host = os.getenv('MONGODB_HOST', 'localhost')
port = os.getenv('MONGODB_PORT', '27017')
username = os.getenv('MONGODB_USERNAME', '')
password = os.getenv('MONGODB_PASSWORD', '')
db_name = os.getenv('MONGODB_DATABASE', 'tradingagents')
auth_source = os.getenv('MONGODB_AUTH_SOURCE', 'admin')

if username and password:
    mongo_uri = f'mongodb://{username}:{password}@{host}:{port}/{db_name}?authSource={auth_source}'
else:
    mongo_uri = f'mongodb://{host}:{port}/{db_name}'

print(f'📊 连接数据库: {host}:{port}/{db_name}\n')
client = MongoClient(mongo_uri)
db = client[db_name]

# 查询一个风险分析师模板
template = db.prompt_templates.find_one({
    'agent_type': 'debators_v2',
    'agent_name': 'risky_analyst_v2',
    'preference_type': 'neutral'
})

if template:
    print('✅ 找到模板')
    print(f'   - template_name: {template.get("template_name")}')

    version = template.get('version')
    print(f'   - version 值: {version}')
    print(f'   - version 类型: {type(version).__name__}')

    if isinstance(version, str):
        print(f'   ⚠️ version 是字符串类型，应该是数字类型')
    elif isinstance(version, (int, float)):
        print(f'   ✅ version 是数字类型')
    else:
        print(f'   ❌ version 类型未知')

    # 检查 user_prompt
    content = template.get('content', {})
    if isinstance(content, dict):
        user_prompt = content.get('user_prompt', '')
        print(f'\n   - user_prompt 长度: {len(user_prompt)} 字符')

        if user_prompt:
            print(f'   ✅ user_prompt 不为空')
            # 检查是否包含占位符
            if '{{' in user_prompt and '}}' in user_prompt:
                print(f'   ✅ user_prompt 包含占位符（模板格式）')
                # 显示前200字符
                print(f'\n   - user_prompt 预览:\n{user_prompt[:200]}...')
            else:
                print(f'   ⚠️ user_prompt 不包含占位符')
        else:
            print(f'   ❌ user_prompt 为空')
    else:
        print(f'   ⚠️ content 不是字典类型')
else:
    print('❌ 没有找到模板')

