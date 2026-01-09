#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""检查同一个 Agent 不同偏好类型的模板差异"""

import os
import sys
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

from pymongo import MongoClient

# 数据库连接
host = os.getenv('MONGODB_HOST', 'localhost') if 'MONGODB_HOST' in os.environ else 'localhost'
port = os.getenv('MONGODB_PORT', '27017') if 'MONGODB_PORT' in os.environ else '27017'
username = os.getenv('MONGODB_USERNAME', '') if 'MONGODB_USERNAME' in os.environ else ''
password = os.getenv('MONGODB_PASSWORD', '') if 'MONGODB_PASSWORD' in os.environ else ''
db_name = os.getenv('MONGODB_DATABASE', 'tradingagents') if 'MONGODB_DATABASE' in os.environ else 'tradingagents'
auth_source = os.getenv('MONGODB_AUTH_SOURCE', 'admin') if 'MONGODB_AUTH_SOURCE' in os.environ else 'admin'

if username and password:
    mongo_uri = f"mongodb://{username}:{password}@{host}:{port}/{db_name}?authSource={auth_source}"
else:
    mongo_uri = f"mongodb://{host}:{port}/{db_name}"

client = MongoClient(mongo_uri)
db = client[db_name]

# 查看持仓顾问的所有模板
agent_names = ['pa_technical_v2', 'pa_fundamental_v2', 'pa_risk_v2', 'pa_advisor_v2']

for agent_name in agent_names:
    templates = list(db.prompt_templates.find(
        {
            'agent_name': agent_name,
            'is_system': True
        },
        {
            'preference_type': 1,
            'content.analysis_requirements': 1,
            '_id': 0
        }
    ).sort('preference_type', 1))

    print("\n" + "=" * 80)
    print(f"{agent_name} 模板对比")
    print("=" * 80)

    for t in templates:
        pref = t['preference_type']
        req = t.get('content', {}).get('analysis_requirements', '(无)')
        print(f"\n{'-'*80}")
        print(f"{pref} ({len(req)} 字符)")
        print(f"{'-'*80}")
        print(req)
        print()

