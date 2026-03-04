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
from app.core.database import init_database, get_mongo_db, close_database

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def create_stock_screening_view():
    """创建股票筛选视图"""
    try:
        db = get_mongo_db()
        
        # 检查视图是否已存在
        collections = await db.list_collection_names()
        if "stock_screening_view" in collections:
            logger.info("📋 视图 stock_screening_view 已存在，先删除...")
            await db.drop_collection("stock_screening_view")
        
        # 创建视图：将 stock_basic_info、market_quotes 和 stock_financial_data 关联
        pipeline = [
            # 第一步：关联实时行情数据 (market_quotes)
            {
                "$lookup": {
                    "from": "market_quotes",
                    "localField": "code",
                    "foreignField": "code",
                    "as": "quote_data"
                }
            },
            # 第二步：展开 quote_data 数组
            {
                "$unwind": {
                    "path": "$quote_data",
                    "preserveNullAndEmptyArrays": True
                }
            },
            # 第三步：关联财务数据 (stock_financial_data)
            {
                "$lookup": {
                    "from": "stock_financial_data",
                    "let": {"stock_code": "$code", "stock_source": "$source"},
                    "pipeline": [
                        {
                            "$match": {
                                "$expr": {
                                    "$and": [
                                        {"$eq": ["$code", "$$stock_code"]},
                                        {"$eq": ["$data_source", "$$stock_source"]}
                                    ]
                                }
                            }
                        },
                        {"$sort": {"report_period": -1}},
                        {"$limit": 1}
                    ],
                    "as": "financial_data"
                }
            },
            # 第四步：展开 financial_data 数组
            {
                "$unwind": {
                    "path": "$financial_data",
                    "preserveNullAndEmptyArrays": True
                }
            },
            # 第五步：重新组织字段结构，将行情数据和财务数据提升到顶层
            {
                "$project": {
                    # 基础信息字段
                    "code": 1,
                    "name": 1,
                    "industry": 1,
                    "area": 1,
                    "market": 1,
                    "list_date": 1,
                    "source": 1,

                    # 市值信息
                    "total_mv": 1,
                    "circ_mv": 1,

                    # 估值指标（从 stock_basic_info）
                    "pe": 1,
                    "pb": 1,
                    "pe_ttm": 1,
                    "pb_mrq": 1,

                    # 财务指标（从 financial_data 提升到顶层）
                    "roe": "$financial_data.roe",
                    "roa": "$financial_data.roa",
                    "netprofit_margin": "$financial_data.netprofit_margin",
                    "gross_margin": "$financial_data.gross_margin",
                    "report_period": "$financial_data.report_period",

                    # 新增财务指标：兼容 flat（baostock/tushare 合并存储）和 nested（financial_indicators 子文档）两种存储方式
                    # 资产负债率 (%)
                    "debt_to_assets": {
                        "$ifNull": [
                            "$financial_data.financial_indicators.debt_to_assets",
                            "$financial_data.debt_to_assets"
                        ]
                    },
                    # 流动比率
                    "current_ratio": {
                        "$ifNull": [
                            "$financial_data.financial_indicators.current_ratio",
                            "$financial_data.current_ratio"
                        ]
                    },
                    # 股息率 (%)
                    "dividend_yield": {
                        "$ifNull": [
                            "$financial_data.financial_indicators.dividend_yield",
                            "$financial_data.dividend_yield"
                        ]
                    },
                    # 净营运资本（亿元）= (流动资产 - 流动负债) / 1e8，两个字段都存在才计算
                    # 兼容 flat (baostock) 和 nested balance_sheet (tushare) 两种存储路径
                    "net_working_capital": {
                        "$let": {
                            "vars": {
                                "cur_assets": {
                                    "$ifNull": [
                                        "$financial_data.balance_sheet.total_cur_assets",
                                        "$financial_data.total_cur_assets"
                                    ]
                                },
                                "cur_liab": {
                                    "$ifNull": [
                                        "$financial_data.balance_sheet.total_cur_liab",
                                        "$financial_data.total_cur_liab"
                                    ]
                                }
                            },
                            "in": {
                                "$cond": {
                                    "if": {
                                        "$and": [
                                            {"$ne": ["$$cur_assets", None]},
                                            {"$ne": ["$$cur_liab", None]}
                                        ]
                                    },
                                    "then": {
                                        "$divide": [
                                            {"$subtract": ["$$cur_assets", "$$cur_liab"]},
                                            100000000
                                        ]
                                    },
                                    "else": None
                                }
                            }
                        }
                    },
                    # ST 状态：名称包含 "ST" 则为 True
                    "is_st": {
                        "$cond": {
                            "if": {
                                "$regexMatch": {
                                    "input": {"$ifNull": ["$name", ""]},
                                    "regex": "ST"
                                }
                            },
                            "then": True,
                            "else": False
                        }
                    },

                    # 交易指标
                    "turnover_rate": 1,
                    "volume_ratio": 1,

                    # 实时行情数据（从 quote_data 提升到顶层）
                    "close": "$quote_data.close",
                    "open": "$quote_data.open",
                    "high": "$quote_data.high",
                    "low": "$quote_data.low",
                    "pre_close": "$quote_data.pre_close",
                    "pct_chg": "$quote_data.pct_chg",
                    "amount": "$quote_data.amount",
                    "volume": "$quote_data.volume",
                    "trade_date": "$quote_data.trade_date",

                    # 时间戳
                    "updated_at": 1,
                    "quote_updated_at": "$quote_data.updated_at",
                    "financial_updated_at": "$financial_data.updated_at"
                }
            }
        ]
        
        # 创建视图
        await db.command({
            "create": "stock_screening_view",
            "viewOn": "stock_basic_info",
            "pipeline": pipeline
        })
        
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

