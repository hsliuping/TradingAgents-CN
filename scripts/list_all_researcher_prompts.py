"""
列出所有研究员提示词模板

查看 v2.0 中有哪些不同偏好类型的提示词
"""

import sys
from pymongo import MongoClient


def list_prompts():
    """列出所有研究员提示词"""
    
    # 连接 MongoDB
    client = MongoClient(
        "mongodb://admin:tradingagents123@localhost:27017/",
        authSource="admin"
    )
    db = client["tradingagents"]
    collection = db["prompt_templates"]
    
    print("=" * 80)
    print("📋 所有研究员提示词模板")
    print("=" * 80)
    
    # 查询所有 researchers_v2 的模板
    templates = list(collection.find(
        {"agent_type": "researchers_v2"},
        {
            "agent_name": 1,
            "template_name": 1,
            "preference_type": 1,
            "version": 1,
            "status": 1
        }
    ).sort([("agent_name", 1), ("preference_type", 1)]))
    
    print(f"\n找到 {len(templates)} 个 v2.0 研究员模板:\n")
    
    current_agent = None
    for t in templates:
        agent_name = t.get('agent_name')
        if agent_name != current_agent:
            current_agent = agent_name
            print(f"\n{'='*60}")
            print(f"📌 {agent_name}")
            print(f"{'='*60}")
        
        print(f"  ├─ 偏好类型: {t.get('preference_type')}")
        print(f"  ├─ 模板名称: {t.get('template_name')}")
        print(f"  ├─ 版本: {t.get('version')}")
        print(f"  └─ 状态: {t.get('status')}")
        print()
    
    print("=" * 80)


if __name__ == "__main__":
    list_prompts()

