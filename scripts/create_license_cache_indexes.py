"""
创建许可证缓存集合的索引

用途：
1. 为 license_cache 集合创建索引
2. 支持基于 token_hash 和 machine_id 的快速查询
3. 自动清理过期缓存
"""

import asyncio
import logging
from datetime import datetime

from app.core.database import init_database, get_mongo_db

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def create_indexes():
    """创建许可证缓存索引"""
    try:
        # 初始化数据库连接
        await init_database()
        db = get_mongo_db()
        
        logger.info("📦 开始创建 license_cache 集合索引...")
        
        # 1. 创建复合唯一索引（token_hash + machine_id）
        await db.license_cache.create_index(
            [("token_hash", 1), ("machine_id", 1)],
            unique=True,
            name="token_machine_unique"
        )
        logger.info("✅ 创建复合唯一索引: token_hash + machine_id")
        
        # 2. 创建过期时间索引（用于自动清理）
        await db.license_cache.create_index(
            [("cache_expires_at", 1)],
            name="cache_expires_at_index",
            expireAfterSeconds=0  # MongoDB TTL 索引，自动删除过期文档
        )
        logger.info("✅ 创建 TTL 索引: cache_expires_at（自动清理过期缓存）")
        
        # 3. 创建更新时间索引
        await db.license_cache.create_index(
            [("updated_at", -1)],
            name="updated_at_index"
        )
        logger.info("✅ 创建索引: updated_at")
        
        # 显示所有索引
        indexes = await db.license_cache.list_indexes().to_list(length=None)
        logger.info("\n📋 license_cache 集合的所有索引:")
        for idx in indexes:
            logger.info(f"  - {idx['name']}: {idx.get('key', {})}")
        
        logger.info("\n✅ 所有索引创建完成！")
        
    except Exception as e:
        logger.error(f"❌ 创建索引失败: {e}")
        raise


if __name__ == "__main__":
    asyncio.run(create_indexes())

