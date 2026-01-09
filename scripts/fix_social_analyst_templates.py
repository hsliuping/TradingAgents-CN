"""
修复社交分析师的提示词模板

问题：
1. 所有 prompt_templates 都没有 agent_id 字段
2. 存在重复的 social_media_analyst_v2 模板
3. 命名不一致

修复：
1. 删除重复的 social_media_analyst_v2 模板
2. 为所有模板添加 agent_id 字段
3. 统一命名规范

使用方法：
    python scripts/fix_social_analyst_templates.py
"""

import asyncio
import sys
from pathlib import Path

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from app.core.database import init_database, get_mongo_db
from bson import ObjectId


async def main():
    print("=" * 80)
    print("修复社交分析师的提示词模板")
    print("=" * 80)
    
    # 初始化数据库
    print("\n📡 连接数据库...")
    await init_database()
    db = get_mongo_db()
    print("✅ 数据库连接成功")
    
    # 1. 删除重复的 social_media_analyst_v2 模板
    print("\n" + "=" * 80)
    print("1. 删除重复的 social_media_analyst_v2 模板")
    print("=" * 80)
    
    duplicate_ids = [
        "6960b212d1ee0cda37cebba8",
        "6960b212d1ee0cda37cebba9",
        "6960b212d1ee0cda37cebbaa"
    ]
    
    for template_id in duplicate_ids:
        template = await db.prompt_templates.find_one({"_id": ObjectId(template_id)})
        if template:
            print(f"\n❌ 删除模板: {template_id}")
            print(f"   agent_name: {template.get('agent_name')}")
            print(f"   template_name: {template.get('template_name')}")
            
            result = await db.prompt_templates.delete_one({"_id": ObjectId(template_id)})
            if result.deleted_count > 0:
                print(f"   ✅ 删除成功")
            else:
                print(f"   ⚠️  删除失败")
        else:
            print(f"   ℹ️  模板不存在: {template_id}")
    
    # 2. 为所有社交分析师模板添加 agent_id 字段
    print("\n" + "=" * 80)
    print("2. 为所有社交分析师模板添加 agent_id 字段")
    print("=" * 80)
    
    # agent_name 到 agent_id 的映射
    name_to_id_mapping = {
        "social_media_analyst": "social_analyst",  # v1.x
        "social_analyst_v2": "social_analyst_v2",  # v2.0
    }
    
    social_templates = await db.prompt_templates.find({
        "$or": [
            {"agent_name": {"$regex": "social", "$options": "i"}},
            {"agent_type": {"$regex": "social", "$options": "i"}}
        ]
    }).to_list(length=None)
    
    for template in social_templates:
        agent_name = template.get('agent_name')
        agent_id = name_to_id_mapping.get(agent_name)
        
        if agent_id:
            print(f"\n📝 更新模板: {template['_id']}")
            print(f"   agent_name: {agent_name}")
            print(f"   agent_id: {agent_id}")
            
            result = await db.prompt_templates.update_one(
                {"_id": template["_id"]},
                {"$set": {"agent_id": agent_id}}
            )
            
            if result.modified_count > 0:
                print(f"   ✅ 更新成功")
            else:
                print(f"   ℹ️  无需更新（可能已有 agent_id）")
        else:
            print(f"\n⚠️  未知的 agent_name: {agent_name}")
    
    # 3. 验证修复
    print("\n" + "=" * 80)
    print("3. 验证修复结果")
    print("=" * 80)
    
    social_templates = await db.prompt_templates.find({
        "$or": [
            {"agent_name": {"$regex": "social", "$options": "i"}},
            {"agent_type": {"$regex": "social", "$options": "i"}}
        ]
    }).to_list(length=None)
    
    print(f"\n📊 剩余的社交分析师模板: {len(social_templates)} 个")
    
    templates_by_agent = {}
    for template in social_templates:
        agent_id = template.get('agent_id', 'N/A')
        if agent_id not in templates_by_agent:
            templates_by_agent[agent_id] = []
        templates_by_agent[agent_id].append(template)
    
    for agent_id, templates in sorted(templates_by_agent.items()):
        print(f"\n🤖 {agent_id}: {len(templates)} 个模板")
        for template in templates:
            print(f"   - {template.get('template_name')} ({template.get('preference_type')})")
    
    # 4. 检查是否还有问题
    print("\n" + "=" * 80)
    print("4. 检查是否还有问题")
    print("=" * 80)
    
    # 检查是否还有没有 agent_id 的模板
    no_agent_id = await db.prompt_templates.count_documents({
        "$or": [
            {"agent_id": {"$exists": False}},
            {"agent_id": None},
            {"agent_id": ""}
        ],
        "$or": [
            {"agent_name": {"$regex": "social", "$options": "i"}},
            {"agent_type": {"$regex": "social", "$options": "i"}}
        ]
    })
    
    if no_agent_id > 0:
        print(f"   ⚠️  还有 {no_agent_id} 个模板没有 agent_id")
    else:
        print(f"   ✅ 所有社交分析师模板都有 agent_id")
    
    # 检查是否还有重复的 social_media_analyst_v2
    duplicate_count = await db.prompt_templates.count_documents({
        "agent_name": "social_media_analyst_v2"
    })
    
    if duplicate_count > 0:
        print(f"   ⚠️  还有 {duplicate_count} 个 social_media_analyst_v2 模板")
    else:
        print(f"   ✅ 已删除所有 social_media_analyst_v2 重复模板")
    
    print("\n" + "=" * 80)
    print("✅ 修复完成！")
    print("=" * 80)


if __name__ == "__main__":
    asyncio.run(main())

