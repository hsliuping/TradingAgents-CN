#!/usr/bin/env python3
"""
临时脚本：同步新闻数据到增强数据库
用于测试 enhanced database service
"""
import asyncio
import sys
from datetime import datetime, timedelta

# 添加项目路径
sys.path.insert(0, '/app')

from app.core.database import init_database
from app.services.news_database_service import NewsDatabaseService


async def main():
    """主函数"""
    print("初始化数据库连接...")
    await init_database()

    print("创建索引...")
    await NewsDatabaseService.ensure_indexes()

    print("从 market_news 读取数据...")
    from app.core.database import get_mongo_db
    db = get_mongo_db()
    old_collection = db.market_news

    # 获取所有数据（不限制时间）
    query = {}

    count = await old_collection.count_documents(query)
    print(f"找到 {count} 条数据")

    # 读取数据
    cursor = old_collection.find(query)
    news_by_source = {}

    async for doc in cursor:
        source = doc.get("source", "未知")
        if source not in news_by_source:
            news_by_source[source] = []
        news_by_source[source].append(doc)

    # 同步到增强数据库
    total_synced = 0
    for source, news_list in news_by_source.items():
        print(f"\n同步 {source} 的 {len(news_list)} 条数据...")
        synced = await NewsDatabaseService.save_news(news_list, source)
        total_synced += synced
        print(f"  -> 成功保存 {synced} 条")

    print(f"\n总共同步了 {total_synced} 条数据到增强数据库")

    # 验证数据
    enhanced_collection = db.market_news_enhanced
    enhanced_count = await enhanced_collection.count_documents({})
    print(f"增强数据库现在有 {enhanced_count} 条记录")

    # 测试词云API
    print("\n测试词云数据生成...")
    wordcloud = await NewsDatabaseService.get_wordcloud_data(hours=24, top_n=10)
    print(f"生成了 {len(wordcloud)} 个热词:")
    for word_data in wordcloud[:5]:
        print(f"  - {word_data['word']}: {word_data['count']}次")

    # 测试分析API
    print("\n测试新闻分析...")
    analytics = await NewsDatabaseService.get_news_analytics()
    print(f"分析结果: 总数 {analytics.get('total_count', 0)}")
    print(f"来源分布: {analytics.get('source_distribution', {})}")

    print("\n完成!")


if __name__ == "__main__":
    asyncio.run(main())
