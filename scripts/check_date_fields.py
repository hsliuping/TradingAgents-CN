"""
检查提示词模板的日期字段类型
"""

from pymongo import MongoClient
from datetime import datetime


def check_date_fields():
    """检查日期字段"""
    
    # 连接 MongoDB
    client = MongoClient(
        "mongodb://admin:tradingagents123@localhost:27017/",
        authSource="admin"
    )
    db = client["tradingagents"]
    collection = db["prompt_templates"]
    
    print("=" * 80)
    print("🔍 检查提示词模板的日期字段类型")
    print("=" * 80)
    
    # 查询所有 v2.0 模板
    templates = list(collection.find(
        {"agent_type": "researchers_v2"},
        {
            "template_name": 1,
            "created_at": 1,
            "updated_at": 1
        }
    ))
    
    print(f"\n找到 {len(templates)} 个模板\n")
    
    for template in templates:
        template_name = template.get("template_name")
        created_at = template.get("created_at")
        updated_at = template.get("updated_at")
        
        print(f"📋 {template_name}")
        print(f"   created_at: {created_at} (类型: {type(created_at).__name__})")
        print(f"   updated_at: {updated_at} (类型: {type(updated_at).__name__})")
        
        # 检查是否是字符串
        if isinstance(created_at, str):
            print(f"   ⚠️ created_at 是字符串，需要转换为 datetime")
        if isinstance(updated_at, str):
            print(f"   ⚠️ updated_at 是字符串，需要转换为 datetime")
        
        print()


if __name__ == "__main__":
    check_date_fields()

