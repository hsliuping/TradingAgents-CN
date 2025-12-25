#!/usr/bin/env python3
"""修复 with_plan 模板的 preference_type 字段"""

from pymongo import MongoClient
from urllib.parse import quote_plus
from bson import ObjectId

# MongoDB 连接配置
username = quote_plus("admin")
password = quote_plus("tradingagents123")
MONGO_URI = f"mongodb://{username}:{password}@localhost:27017/"

def fix_preference_type():
    """修复 preference_type 字段"""
    client = MongoClient(MONGO_URI)
    db = client["tradingagents"]
    collection = db["prompt_templates"]

    # 查找需要修复的记录
    template_id = "694cbda51d8ad13d15d322f4"
    
    print(f"🔍 查找模板: {template_id}")
    template = collection.find_one({"_id": ObjectId(template_id)})
    
    if not template:
        print(f"❌ 未找到模板: {template_id}")
        return
    
    print(f"✅ 找到模板:")
    print(f"   - template_name: {template.get('template_name')}")
    print(f"   - agent_type: {template.get('agent_type')}")
    print(f"   - agent_name: {template.get('agent_name')}")
    print(f"   - preference_type: {template.get('preference_type')}")
    
    # 更新 preference_type
    print(f"\n🔧 更新 preference_type 为 'with_plan'...")
    result = collection.update_one(
        {"_id": ObjectId(template_id)},
        {"$set": {"preference_type": "with_plan"}}
    )
    
    if result.modified_count > 0:
        print(f"✅ 成功更新模板")
        
        # 验证更新
        updated = collection.find_one({"_id": ObjectId(template_id)})
        print(f"\n📋 更新后的记录:")
        print(f"   - template_name: {updated.get('template_name')}")
        print(f"   - preference_type: {updated.get('preference_type')}")
    else:
        print(f"⚠️ 未修改任何记录（可能已经是正确的值）")

if __name__ == "__main__":
    fix_preference_type()

