"""
检查 tool_agent_bindings 集合中的数据
"""
import sys
import os
import asyncio

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

async def main():
    from app.core.database import init_database, get_mongo_db

    # 初始化数据库
    await init_database()
    db = get_mongo_db()
    
    print("=" * 100)
    print("检查 tool_agent_bindings 集合")
    print("=" * 100)
    
    # 1. 检查集合是否存在
    collections = await db.list_collection_names()
    if "tool_agent_bindings" not in collections:
        print("\n❌ 集合 tool_agent_bindings 不存在！")
        print(f"\n现有集合: {collections}")
        return
    
    # 2. 检查集合总数
    total_count = await db.tool_agent_bindings.count_documents({})
    print(f"\n📊 集合总记录数: {total_count}")

    if total_count == 0:
        print("\n❌ 集合为空！没有任何绑定记录。")
        return

    # 3. 检查 sector_analyst_v2 的绑定
    agent_id = "sector_analyst_v2"
    print(f"\n" + "=" * 100)
    print(f"查询 agent_id = '{agent_id}' 的绑定")
    print("=" * 100)

    # 3.1 不带任何条件
    all_bindings = await db.tool_agent_bindings.find({"agent_id": agent_id}).to_list(length=None)
    print(f"\n🔍 查询条件: {{'agent_id': '{agent_id}'}}")
    print(f"📦 找到 {len(all_bindings)} 条记录")

    if all_bindings:
        for idx, binding in enumerate(all_bindings, 1):
            print(f"\n[{idx}] 绑定记录:")
            for key, value in binding.items():
                print(f"    {key}: {value}")

    # 3.2 带 is_active 条件
    active_bindings = await db.tool_agent_bindings.find({
        "agent_id": agent_id,
        "is_active": {"$ne": False}
    }).to_list(length=None)
    print(f"\n🔍 查询条件: {{'agent_id': '{agent_id}', 'is_active': {{'$ne': False}}}}")
    print(f"📦 找到 {len(active_bindings)} 条记录")

    # 4. 列出所有 agent_id
    print(f"\n" + "=" * 100)
    print("集合中的所有 agent_id")
    print("=" * 100)

    all_agent_ids = await db.tool_agent_bindings.distinct("agent_id")
    print(f"\n📋 共有 {len(all_agent_ids)} 个不同的 agent_id:\n")

    for aid in sorted(all_agent_ids):
        count = await db.tool_agent_bindings.count_documents({"agent_id": aid})
        active_count = await db.tool_agent_bindings.count_documents({
            "agent_id": aid,
            "is_active": {"$ne": False}
        })
        marker = "👉" if "sector" in aid.lower() else "  "
        print(f"{marker} {aid}: {count} 条记录 ({active_count} 条激活)")

    # 5. 显示前 10 条记录
    print(f"\n" + "=" * 100)
    print("集合中的前 10 条记录")
    print("=" * 100)

    sample_bindings = await db.tool_agent_bindings.find().limit(10).to_list(length=None)
    for idx, binding in enumerate(sample_bindings, 1):
        print(f"\n[{idx}] agent_id: {binding.get('agent_id')}, tool_id: {binding.get('tool_id')}, is_active: {binding.get('is_active', 'N/A')}")

if __name__ == "__main__":
    asyncio.run(main())

