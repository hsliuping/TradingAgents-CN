#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
检查缓存场景模板的状态
"""

import os
import sys
from pathlib import Path

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    print("⚠️ dotenv 未安装，使用默认配置")

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

print(f"📊 连接数据库: {host}:{port}/{db_name}\n")
client = MongoClient(mongo_uri)
db = client[db_name]


def check_cache_templates():
    """检查缓存场景模板"""
    collection = db['prompt_templates']
    
    print("=" * 80)
    print("缓存场景模板检查")
    print("=" * 80)
    
    agents = ["pa_technical_v2", "pa_fundamental_v2"]
    cache_scenarios = ["with_cache", "without_cache"]
    styles = ["aggressive", "neutral", "conservative"]
    
    total = 0
    found = 0
    missing = []
    
    for agent_name in agents:
        print(f"\n📋 {agent_name}:")
        for cache_scenario in cache_scenarios:
            print(f"  {cache_scenario}:")
            for style in styles:
                preference_type = f"{cache_scenario}_{style}"
                total += 1
                
                template = collection.find_one({
                    "agent_type": "position_analysis_v2",
                    "agent_name": agent_name,
                    "preference_type": preference_type,
                    "is_system": True
                })
                
                if template:
                    print(f"    ✅ {preference_type}")
                    found += 1
                else:
                    print(f"    ❌ {preference_type} (缺失)")
                    missing.append(f"{agent_name}/{preference_type}")
    
    print("\n" + "=" * 80)
    print(f"📊 统计: 找到 {found}/{total} 个模板")
    
    if missing:
        print(f"\n⚠️ 缺失的模板:")
        for m in missing:
            print(f"  - {m}")
        print(f"\n💡 运行以下命令恢复:")
        print(f"  python scripts\\template_upgrades\\restore_cache_templates.py")
    else:
        print(f"\n✅ 所有缓存场景模板都存在！")
    
    return found, total, missing


def main():
    """主函数"""
    print("🔍 检查缓存场景模板状态\n")
    
    found, total, missing = check_cache_templates()
    
    print("\n" + "=" * 80)
    if missing:
        print("❌ 检查失败：有模板缺失")
        sys.exit(1)
    else:
        print("✅ 检查通过：所有模板都存在")
        sys.exit(0)


if __name__ == "__main__":
    main()

