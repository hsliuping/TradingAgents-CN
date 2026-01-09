"""
为 sector_analyst_v2 添加工具绑定
"""
import sys
import os
import asyncio
from datetime import datetime

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

async def main():
    from app.core.database import init_database, get_mongo_db
    
    # 初始化数据库
    await init_database()
    db = get_mongo_db()
    
    agent_id = "sector_analyst_v2"
    tools = ["get_china_market_overview", "get_sector_performance"]
    
    print("=" * 80)
    print(f"为 {agent_id} 添加工具绑定")
    print("=" * 80)
    
    # 1. 检查现有绑定
    existing = await db.tool_agent_bindings.find({"agent_id": agent_id}).to_list(length=None)
    print(f"\n📦 现有绑定: {len(existing)} 条")
    
    if existing:
        print("\n⚠️ 已存在绑定记录，是否删除？(y/n)")
        choice = input().strip().lower()
        if choice == 'y':
            result = await db.tool_agent_bindings.delete_many({"agent_id": agent_id})
            print(f"✅ 已删除 {result.deleted_count} 条记录")
        else:
            print("❌ 取消操作")
            return
    
    # 2. 添加新绑定
    print(f"\n📝 添加工具绑定:")
    bindings = []
    for idx, tool_id in enumerate(tools, 1):
        binding = {
            "agent_id": agent_id,
            "tool_id": tool_id,
            "is_active": True,
            "priority": idx,
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow(),
        }
        bindings.append(binding)
        print(f"   [{idx}] {tool_id}")
    
    result = await db.tool_agent_bindings.insert_many(bindings)
    print(f"\n✅ 成功添加 {len(result.inserted_ids)} 条绑定记录")
    
    # 3. 验证
    print("\n" + "=" * 80)
    print("验证绑定")
    print("=" * 80)
    
    new_bindings = await db.tool_agent_bindings.find({
        "agent_id": agent_id,
        "is_active": {"$ne": False}
    }).to_list(length=None)
    
    print(f"\n📦 查询结果: {len(new_bindings)} 条记录")
    for idx, binding in enumerate(new_bindings, 1):
        print(f"   [{idx}] {binding['tool_id']} (priority: {binding['priority']}, is_active: {binding['is_active']})")
    
    print("\n✅ 完成！")

if __name__ == "__main__":
    asyncio.run(main())

