"""
为所有 prompt_templates 添加 agent_id 字段

问题：
- 所有 prompt_templates 都没有 agent_id 字段
- 只有 agent_type 和 agent_name

修复：
- 根据 agent_name 推断 agent_id
- 为所有模板添加 agent_id 字段

使用方法：
    python scripts/add_agent_id_to_all_templates.py
"""

import asyncio
import sys
from pathlib import Path

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from app.core.database import init_database, get_mongo_db


async def main():
    print("=" * 80)
    print("为所有 prompt_templates 添加 agent_id 字段")
    print("=" * 80)
    
    # 初始化数据库
    print("\n📡 连接数据库...")
    await init_database()
    db = get_mongo_db()
    print("✅ 数据库连接成功")
    
    # agent_name 到 agent_id 的映射规则
    name_to_id_mapping = {
        # v1.x Analysts
        "market_analyst": "market_analyst",
        "sector_analyst": "sector_analyst",
        "fundamental_analyst": "fundamental_analyst",
        "technical_analyst": "technical_analyst",
        "social_media_analyst": "social_analyst",  # 特殊映射
        "news_analyst": "news_analyst",
        
        # v2.0 Analysts
        "market_analyst_v2": "market_analyst_v2",
        "sector_analyst_v2": "sector_analyst_v2",
        "fundamental_analyst_v2": "fundamentals_analyst_v2",  # 注意：fundamentals
        "technical_analyst_v2": "technical_analyst_v2",
        "social_analyst_v2": "social_analyst_v2",
        "news_analyst_v2": "news_analyst_v2",
        
        # v2.0 Strategists
        "strategy_analyst_v2": "strategy_analyst_v2",
        "risk_analyst_v2": "risk_analyst_v2",
        
        # v2.0 Reporters
        "report_writer_v2": "report_writer_v2",
        
        # v2.0 Trade Review
        "review_manager_v2": "review_manager_v2",
        "position_analyst_v2": "position_analyst_v2",
        "timing_analyst_v2": "timing_analyst_v2",
        "emotion_analyst_v2": "emotion_analyst_v2",
        "attribution_analyst_v2": "attribution_analyst_v2",
    }
    
    # 1. 查询所有没有 agent_id 的模板
    print("\n" + "=" * 80)
    print("1. 查询所有没有 agent_id 的模板")
    print("=" * 80)
    
    templates = await db.prompt_templates.find({
        "$or": [
            {"agent_id": {"$exists": False}},
            {"agent_id": None},
            {"agent_id": ""}
        ]
    }).to_list(length=None)
    
    print(f"   📊 找到 {len(templates)} 个没有 agent_id 的模板")
    
    # 2. 为每个模板添加 agent_id
    print("\n" + "=" * 80)
    print("2. 为每个模板添加 agent_id")
    print("=" * 80)
    
    updated_count = 0
    unknown_count = 0
    
    for template in templates:
        agent_name = template.get('agent_name', '')
        agent_type = template.get('agent_type', '')
        
        # 推断 agent_id
        agent_id = name_to_id_mapping.get(agent_name)
        
        if not agent_id:
            # 尝试根据 agent_type 推断
            if agent_type == "analysts_v2":
                agent_id = f"{agent_name}"  # 使用 agent_name 作为 agent_id
            elif agent_type == "analysts":
                agent_id = agent_name  # v1.x 使用 agent_name
            else:
                agent_id = agent_name  # 默认使用 agent_name
        
        if agent_id:
            print(f"\n📝 更新模板: {template['_id']}")
            print(f"   agent_name: {agent_name}")
            print(f"   agent_type: {agent_type}")
            print(f"   → agent_id: {agent_id}")
            
            result = await db.prompt_templates.update_one(
                {"_id": template["_id"]},
                {"$set": {"agent_id": agent_id}}
            )
            
            if result.modified_count > 0:
                print(f"   ✅ 更新成功")
                updated_count += 1
            else:
                print(f"   ℹ️  无需更新")
        else:
            print(f"\n⚠️  无法推断 agent_id:")
            print(f"   agent_name: {agent_name}")
            print(f"   agent_type: {agent_type}")
            unknown_count += 1
    
    # 3. 统计结果
    print("\n" + "=" * 80)
    print("3. 统计结果")
    print("=" * 80)
    print(f"   ✅ 成功更新: {updated_count} 个模板")
    print(f"   ⚠️  无法推断: {unknown_count} 个模板")
    
    # 4. 验证修复
    print("\n" + "=" * 80)
    print("4. 验证修复")
    print("=" * 80)
    
    remaining = await db.prompt_templates.count_documents({
        "$or": [
            {"agent_id": {"$exists": False}},
            {"agent_id": None},
            {"agent_id": ""}
        ]
    })
    
    total = await db.prompt_templates.count_documents({})
    
    print(f"   📊 总模板数: {total}")
    print(f"   ✅ 有 agent_id: {total - remaining}")
    print(f"   ❌ 无 agent_id: {remaining}")
    
    if remaining == 0:
        print("\n✅ 所有模板都已添加 agent_id！")
    else:
        print(f"\n⚠️  还有 {remaining} 个模板没有 agent_id")
    
    print("\n" + "=" * 80)
    print("✅ 修复完成！")
    print("=" * 80)


if __name__ == "__main__":
    asyncio.run(main())

