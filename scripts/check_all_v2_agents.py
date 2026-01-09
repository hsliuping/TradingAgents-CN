#!/usr/bin/env python
"""
检查所有 v2.0 Agent 的模板配置
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


def check_v2_templates():
    """检查所有 v2.0 模板"""
    collection = db['prompt_templates']
    
    # 查找所有 v2.0 相关的模板
    v2_templates = list(collection.find(
        {
            "$or": [
                {"agent_type": {"$regex": "_v2$"}},
                {"agent_name": {"$regex": "_v2$"}}
            ]
        },
        {
            "agent_type": 1,
            "agent_name": 1,
            "preference_type": 1,
            "template_name": 1,
            "content.analysis_requirements": 1,
            "_id": 0
        }
    ).sort([("agent_type", 1), ("agent_name", 1), ("preference_type", 1)]))
    
    print("=" * 100)
    print("所有 v2.0 Agent 模板")
    print("=" * 100)
    
    # 按 agent_type 分组
    by_type = {}
    for t in v2_templates:
        agent_type = t.get("agent_type", "unknown")
        if agent_type not in by_type:
            by_type[agent_type] = []
        by_type[agent_type].append(t)
    
    for agent_type, templates in sorted(by_type.items()):
        print(f"\n📦 Agent Type: {agent_type}")
        print("-" * 100)
        
        # 按 agent_name 分组
        by_name = {}
        for t in templates:
            agent_name = t.get("agent_name", "unknown")
            if agent_name not in by_name:
                by_name[agent_name] = []
            by_name[agent_name].append(t)
        
        for agent_name, agent_templates in sorted(by_name.items()):
            print(f"\n  🤖 Agent: {agent_name}")
            for t in agent_templates:
                pref = t.get("preference_type", "N/A")
                template_name = t.get("template_name", "N/A")
                req_len = len(t.get("content", {}).get("analysis_requirements", ""))
                
                # 评估详细程度
                if req_len > 500:
                    detail = "⭐⭐⭐⭐⭐ 非常详细"
                elif req_len > 300:
                    detail = "⭐⭐⭐⭐ 详细"
                elif req_len > 100:
                    detail = "⭐⭐⭐ 中等"
                elif req_len > 50:
                    detail = "⭐⭐ 简单"
                else:
                    detail = "⭐ 很简单"
                
                print(f"    - {pref:15} | {req_len:4} 字符 | {detail}")
    
    print("\n" + "=" * 100)
    print(f"总计: {len(v2_templates)} 个 v2.0 模板")
    print("=" * 100)
    
    return by_type


def check_v1_templates():
    """检查 v1.x 模板作为对比"""
    collection = db['prompt_templates']
    
    # 查找旧版模板（不包含 _v2 后缀）
    v1_templates = list(collection.find(
        {
            "agent_type": {"$not": {"$regex": "_v2$"}},
            "agent_name": {"$not": {"$regex": "_v2$"}},
            "is_system": True
        },
        {
            "agent_type": 1,
            "agent_name": 1,
            "preference_type": 1,
            "content.analysis_requirements": 1,
            "_id": 0
        }
    ).sort([("agent_type", 1), ("agent_name", 1)]))
    
    print("\n" + "=" * 100)
    print("v1.x Agent 模板（对比参考）")
    print("=" * 100)
    
    # 按 agent_type 分组
    by_type = {}
    for t in v1_templates:
        agent_type = t.get("agent_type", "unknown")
        if agent_type not in by_type:
            by_type[agent_type] = []
        by_type[agent_type].append(t)
    
    for agent_type, templates in sorted(by_type.items()):
        print(f"\n📦 Agent Type: {agent_type}")
        
        # 按 agent_name 分组
        by_name = {}
        for t in templates:
            agent_name = t.get("agent_name", "unknown")
            if agent_name not in by_name:
                by_name[agent_name] = []
            by_name[agent_name].append(t)
        
        for agent_name, agent_templates in sorted(by_name.items()):
            req_len = len(agent_templates[0].get("content", {}).get("analysis_requirements", ""))
            pref_count = len(agent_templates)
            
            # 评估详细程度
            if req_len > 500:
                detail = "⭐⭐⭐⭐⭐"
            elif req_len > 300:
                detail = "⭐⭐⭐⭐"
            elif req_len > 100:
                detail = "⭐⭐⭐"
            elif req_len > 50:
                detail = "⭐⭐"
            else:
                detail = "⭐"
            
            print(f"  🤖 {agent_name:30} | {pref_count} 个偏好 | {req_len:4} 字符 | {detail}")
    
    print("\n" + "=" * 100)
    print(f"总计: {len(v1_templates)} 个 v1.x 模板")
    print("=" * 100)


def main():
    """主函数"""
    print("🔍 检查所有 v2.0 Agent 模板\n")
    
    v2_by_type = check_v2_templates()
    check_v1_templates()
    
    # 总结
    print("\n" + "=" * 100)
    print("📊 总结")
    print("=" * 100)
    
    print("\nv2.0 Agent 类型:")
    for agent_type in sorted(v2_by_type.keys()):
        count = len(v2_by_type[agent_type])
        print(f"  - {agent_type}: {count} 个模板")


if __name__ == "__main__":
    main()

