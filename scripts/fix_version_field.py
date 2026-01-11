#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
修复 version 字段：从字符串 "v2.1" 恢复为数字 2.0
"""

import os
import sys
from pathlib import Path
from datetime import datetime

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

print('=' * 100)
print('🔧 修复 version 字段：从字符串恢复为数字')
print('=' * 100)

# 查询所有风险分析师模板
templates = list(db.prompt_templates.find({
    'agent_type': 'debators_v2',
    'agent_name': {'$in': ['risky_analyst_v2', 'safe_analyst_v2', 'neutral_analyst_v2']}
}))

print(f'\n✅ 找到 {len(templates)} 个模板\n')

fixed_count = 0

for tmpl in templates:
    agent_name = tmpl.get('agent_name')
    pref = tmpl.get('preference_type')
    version = tmpl.get('version')
    
    print(f'🔍 {agent_name} ({pref}):')
    print(f'   - 当前 version: {version} (类型: {type(version).__name__})')
    
    # 如果 version 是字符串，修复为数字 2.0
    if isinstance(version, str):
        result = db.prompt_templates.update_one(
            {'_id': tmpl['_id']},
            {'$set': {
                'version': 2.0,
                'updated_at': datetime.now()
            }}
        )
        
        if result.modified_count > 0:
            print(f'   ✅ 修复成功：version = 2.0 (float)')
            fixed_count += 1
        else:
            print(f'   ⚠️ 未修复')
    elif isinstance(version, (int, float)):
        print(f'   ✅ 已经是数字类型，无需修复')
    else:
        print(f'   ❌ version 类型未知，跳过')
    
    print()

print('=' * 100)
print(f'✅ 修复完成，共修复 {fixed_count} 个模板')
print('=' * 100)

