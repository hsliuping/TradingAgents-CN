#!/usr/bin/env python3
"""
创建股票筛选视图
将 stock_basic_info 和 market_quotes 两个集合通过 $lookup 关联，创建一个类似 MySQL 视图的 MongoDB View
"""

import sys
import os
from pathlib import Path

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

import asyncio
import logging
from motor.motor_asyncio import AsyncIOMotorClient
from app.core.database import (
    init_database,
    get_mongo_db,
    close_database,
    create_stock_screening_view as create_stock_screening_view_in_db,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def create_stock_screening_view():
    """创建股票筛选视图"""
    try:
        db = get_mongo_db()
        await create_stock_screening_view_in_db(db)
        logger.info("✅ 视图 stock_screening_view 创建成功！")

        # 测试查询视图（用 find + limit 取少量数据，避免 count_documents 全表扫描超时）
        view = db["stock_screening_view"]
        samples = []
        async for doc in view.find({}, {"code": 1, "name": 1, "close": 1, "pct_chg": 1,
                                        "debt_to_assets": 1, "current_ratio": 1,
                                        "dividend_yield": 1, "net_working_capital": 1, "is_st": 1}
                                   ).limit(3):
            samples.append(doc)

        if samples:
            logger.info(f"📊 视图可正常查询，以下展示前 {len(samples)} 条示例：")
            for s in samples:
                logger.info(
                    f"  📝 {s.get('code')} {s.get('name')} | "
                    f"close={s.get('close')} pct_chg={s.get('pct_chg')} | "
                    f"debt_to_assets={s.get('debt_to_assets')} "
                    f"current_ratio={s.get('current_ratio')} "
                    f"dividend_yield={s.get('dividend_yield')} "
                    f"net_working_capital={s.get('net_working_capital')} "
                    f"is_st={s.get('is_st')}"
                )
        else:
            logger.warning("⚠️ 视图查询返回 0 条，请检查源集合是否有数据")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ 创建视图失败: {e}")
        import traceback
        traceback.print_exc()
        return False


async def create_indexes_on_view():
    """在视图上创建索引（注意：MongoDB 视图不支持直接创建索引，但可以在源集合上创建）"""
    try:
        db = get_mongo_db()
        basic_info = db["stock_basic_info"]
        market_quotes = db["market_quotes"]
        
        logger.info("📋 检查并创建必要的索引...")
        
        # stock_basic_info 的索引
        await basic_info.create_index([("code", 1), ("source", 1)], unique=True)
        await basic_info.create_index([("industry", 1)])
        await basic_info.create_index([("total_mv", -1)])
        await basic_info.create_index([("pe", 1)])
        await basic_info.create_index([("pb", 1)])
        await basic_info.create_index([("roe", -1)])
        
        # market_quotes 的索引
        await market_quotes.create_index([("code", 1)], unique=True)
        await market_quotes.create_index([("pct_chg", -1)])
        await market_quotes.create_index([("amount", -1)])
        await market_quotes.create_index([("updated_at", -1)])
        
        logger.info("✅ 索引创建完成！")
        return True
        
    except Exception as e:
        logger.error(f"❌ 创建索引失败: {e}")
        return False


async def main():
    """主函数"""
    logger.info("=" * 60)
    logger.info("  创建股票筛选视图")
    logger.info("=" * 60)

    try:
        # 初始化数据库连接
        logger.info(f"📡 连接 MongoDB...")
        await init_database()

        # 创建视图
        success = await create_stock_screening_view()
        if not success:
            return 1

        # 创建索引
        await create_indexes_on_view()

        logger.info("\n✅ 所有操作完成！")
        logger.info("💡 现在可以使用 stock_screening_view 进行筛选查询了")
        return 0

    finally:
        # 关闭数据库连接
        await close_database()


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    exit(exit_code)

