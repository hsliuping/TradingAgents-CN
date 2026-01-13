#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""检查研究员模板内容"""

import os
from dotenv import load_dotenv
from pymongo import MongoClient

# 加载 .env 配置
load_dotenv()

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

# 查找看多研究员的系统模板
for agent_name in ['bull_researcher_v2', 'bear_researcher_v2']:
    print("=" * 80)
    print(f"检查 {agent_name}")
    print("=" * 80)
    
    template = db['prompt_templates'].find_one({
        'agent_type': 'researchers_v2',
        'agent_name': agent_name,
        'preference_type': 'neutral',
        'is_system': True,
        'status': 'active'
    })

    if template:
        print(f"✅ 找到系统模板\n")
        content = template.get('content', {})
        
        # 检查 user_prompt
        if 'user_prompt' in content:
            user_prompt = content['user_prompt']
            print(f"用户提示词长度: {len(user_prompt)} 字符\n")
            
            # 检查是否包含当前价格相关的变量
            if '{{current_price}}' in user_prompt or '{{price}}' in user_prompt:
                print("✅ 包含当前价格变量")
            else:
                print("❌ 不包含当前价格变量")
            
            # 检查是否提到"当前价格"
            if '当前价格' in user_prompt or '当前股价' in user_prompt:
                print("✅ 提示词中提到当前价格")
            else:
                print("⚠️ 提示词中未提到当前价格")
            
            print(f"\n用户提示词内容:\n{user_prompt}\n")
        else:
            print("❌ 不包含 user_prompt 字段\n")
    else:
        print(f"❌ 未找到系统模板\n")

