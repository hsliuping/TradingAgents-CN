#!/usr/bin/env python3
"""
调试数据库统计接口问题
"""

import asyncio
import sys
import os

# 添加项目根目录到 Python 路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

async def test_database_stats():
    """测试数据库统计功能"""
    try:
        from app.core.database import init_database, get_mongo_db
        from app.services.database_service import DatabaseService
        
        print("🔄 初始化数据库连接...")
        await init_database()
        
        print("✅ 数据库连接成功")
        
        # 测试 get_mongo_db() 返回的对象类型
        db = get_mongo_db()
        print(f"📊 数据库对象类型: {type(db)}")
        print(f"📊 数据库对象: {db}")
        
        # 测试 list_collections() 方法
        print("🔍 测试 list_collections()...")
        collections_cursor = db.list_collections()
        print(f"📊 collections_cursor 类型: {type(collections_cursor)}")
        
        # 测试 to_list() 方法
        print("🔍 测试 to_list()...")
        collections_list = await collections_cursor.to_list(length=None)
        print(f"✅ 成功获取集合列表，数量: {len(collections_list)}")
        
        # 测试完整的 get_database_stats 方法
        print("🔍 测试 DatabaseService.get_database_stats()...")
        service = DatabaseService()
        stats = await service.get_database_stats()
        print(f"✅ 成功获取数据库统计: {stats.keys()}")
        
    except Exception as e:
        print(f"❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_database_stats())
