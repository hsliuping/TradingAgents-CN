"""检查数据库中的任务"""
import asyncio
from app.database import get_mongo_db

async def check_tasks():
    db = get_mongo_db()
    
    # 列出所有集合
    collections = await db.list_collection_names()
    print("📚 数据库集合:", collections)
    print()
    
    # 检查 unified_analysis_tasks 集合
    print("=" * 60)
    print("📋 unified_analysis_tasks 集合:")
    print("=" * 60)
    count = await db.unified_analysis_tasks.count_documents({})
    print(f"总任务数: {count}")
    
    tasks = await db.unified_analysis_tasks.find().sort("created_at", -1).limit(10).to_list(10)
    for i, t in enumerate(tasks, 1):
        print(f"\n{i}. 任务ID: {t.get('task_id')}")
        print(f"   状态: {t.get('status')}")
        print(f"   类型: {t.get('task_type')}")
        print(f"   用户ID: {t.get('user_id')}")
        print(f"   创建时间: {t.get('created_at')}")
        print(f"   参数: {t.get('task_params', {}).get('symbol', 'N/A')}")
    
    # 检查 analysis_tasks 集合（旧集合）
    print("\n" + "=" * 60)
    print("📋 analysis_tasks 集合 (旧):")
    print("=" * 60)
    count_old = await db.analysis_tasks.count_documents({})
    print(f"总任务数: {count_old}")
    
    tasks_old = await db.analysis_tasks.find().sort("created_at", -1).limit(5).to_list(5)
    for i, t in enumerate(tasks_old, 1):
        print(f"\n{i}. 任务ID: {t.get('task_id')}")
        print(f"   状态: {t.get('status')}")
        print(f"   股票代码: {t.get('stock_code') or t.get('symbol')}")
        print(f"   创建时间: {t.get('created_at')}")

if __name__ == "__main__":
    asyncio.run(check_tasks())

