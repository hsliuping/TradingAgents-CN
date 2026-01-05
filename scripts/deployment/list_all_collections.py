"""
列出数据库中的所有集合及其文档数量
用于确定需要导出哪些集合
"""
import asyncio
from pymongo import MongoClient
from app.core.database import get_mongo_db, init_database


async def list_collections():
    """列出所有集合"""
    # 初始化数据库连接
    await init_database()
    
    db = get_mongo_db()
    
    # 获取所有集合名称
    collection_names = await db.list_collection_names()
    
    # 过滤掉系统集合
    collection_names = [c for c in collection_names if not c.startswith("system.")]
    
    # 按名称排序
    collection_names.sort()
    
    print("\n" + "=" * 80)
    print("📊 数据库集合统计")
    print("=" * 80)
    print(f"\n数据库: tradingagents")
    print(f"总集合数: {len(collection_names)}\n")
    
    # 统计每个集合的文档数量
    collection_stats = []
    for collection_name in collection_names:
        collection = db[collection_name]
        count = await collection.count_documents({})
        collection_stats.append((collection_name, count))
    
    # 按文档数量排序
    collection_stats.sort(key=lambda x: x[1], reverse=True)
    
    # 打印统计信息
    print(f"{'集合名称':<40} {'文档数量':>10}")
    print("-" * 80)
    
    for collection_name, count in collection_stats:
        print(f"{collection_name:<40} {count:>10,}")
    
    print("\n" + "=" * 80)
    
    # 分类显示
    print("\n📋 集合分类建议:\n")
    
    # 配置类集合（文档数量较少，适合导出）
    config_collections = []
    # 数据类集合（文档数量较多，不适合导出）
    data_collections = []
    # 空集合
    empty_collections = []
    
    for collection_name, count in collection_stats:
        if count == 0:
            empty_collections.append(collection_name)
        elif count < 1000:  # 少于1000条记录的视为配置类
            config_collections.append((collection_name, count))
        else:
            data_collections.append((collection_name, count))
    
    print("✅ 配置类集合（建议导出）:")
    for collection_name, count in config_collections:
        print(f"   - {collection_name:<40} ({count:,} 条)")
    
    print(f"\n❌ 数据类集合（不建议导出，数据量大）:")
    for collection_name, count in data_collections:
        print(f"   - {collection_name:<40} ({count:,} 条)")
    
    if empty_collections:
        print(f"\n⚠️  空集合:")
        for collection_name in empty_collections:
            print(f"   - {collection_name}")
    
    print("\n" + "=" * 80)
    
    # 生成导出配置建议
    print("\n📝 导出配置建议:\n")
    print("```python")
    print("# 配置数据集合（用于演示系统）")
    print("config_collections = [")
    for collection_name, count in config_collections:
        print(f"    '{collection_name}',  # {count:,} 条")
    print("]")
    print("```")
    
    print("\n" + "=" * 80)


if __name__ == "__main__":
    asyncio.run(list_collections())

