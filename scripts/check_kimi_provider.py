#!/usr/bin/env python3
"""
检查数据库中 kimi 供应商的配置
"""

import os
import sys
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# 设置默认的 MongoDB 认证信息（如果环境变量未设置）
if not os.getenv('MONGODB_USERNAME'):
    os.environ['MONGODB_USERNAME'] = 'admin'
if not os.getenv('MONGODB_PASSWORD'):
    os.environ['MONGODB_PASSWORD'] = 'tradingagents123'
if not os.getenv('MONGODB_AUTH_SOURCE'):
    os.environ['MONGODB_AUTH_SOURCE'] = 'admin'

import json

from pymongo import MongoClient

from app.core.config import settings

# 连接 MongoDB
print("=" * 80)
print("检查数据库中 kimi 供应商的配置")
print("=" * 80)
print(f"\n连接字符串: {settings.MONGO_URI}")

try:
    client = MongoClient(settings.MONGO_URI)
    db = client[settings.MONGO_DB]
    
    providers_collection = db.llm_providers
    
    # 查找 kimi
    kimi_provider = providers_collection.find_one({"name": "kimi"})
    
    if kimi_provider:
        print("\n✅ 找到 kimi 供应商配置:")
        print(f"   name: {kimi_provider.get('name')}")
        print(f"   display_name: {kimi_provider.get('display_name')}")
        print(f"   is_active: {kimi_provider.get('is_active')}")
        print(f"   default_base_url: {kimi_provider.get('default_base_url')}")
        print(f"   supported_features: {kimi_provider.get('supported_features')}")
        
        if not kimi_provider.get('is_active'):
            print("\n⚠️  问题：kimi 的 is_active 为 False，所以不会显示在前端列表中！")
            print("   解决方案：运行以下命令更新 is_active 为 True")
            print("   python -c \"from pymongo import MongoClient; from app.core.config import settings; client = MongoClient(settings.MONGO_URI); db = client[settings.MONGO_DB]; db.llm_providers.update_one({'name': 'kimi'}, {'$set': {'is_active': True}}); print('✅ 已更新')\"")
        else:
            print("\n✅ kimi 的 is_active 为 True，应该会显示在前端列表中")
    else:
        print("\n❌ 未找到 kimi 供应商配置！")
        print("   解决方案：运行以下命令初始化供应商数据")
        print("   python app/scripts/init_providers.py")
    
    # 列出所有供应商
    print("\n" + "=" * 80)
    print("所有供应商列表:")
    print("=" * 80)
    all_providers = list(providers_collection.find({}, {"name": 1, "display_name": 1, "is_active": 1}))
    print(f"\n总共有 {len(all_providers)} 个供应商:\n")
    for provider in all_providers:
        status = "✅" if provider.get('is_active') else "❌"
        print(f"  {status} {provider.get('display_name')} ({provider.get('name')}) - is_active: {provider.get('is_active')}")
    
    client.close()
    
except Exception as e:
    print(f"\n❌ 错误: {e}")
    import traceback
    traceback.print_exc()

