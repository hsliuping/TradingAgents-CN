#!/usr/bin/env python3
"""
创建所有主要集合的索引
为以下集合创建优化索引：
  - stock_daily_quotes: 历史K线数据（12个索引）
  - market_quotes: 实时行情数据（3个索引）
  - stock_basic_info: 股票基本信息（12个索引）
  - stock_news: 股票新闻数据（7个索引）
  - stock_financial_data: 财务数据（10个索引）
  - scheduler_history: 调度器历史（3个索引）
  - scheduler_metadata: 调度器元数据（1个索引）

用法：
  python scripts/setup/create_all_indexes.py

注意：此脚本仅创建索引，不会删除已有索引。如果索引已存在，会跳过创建。
"""

import os
import sys
import logging
from pymongo import MongoClient, ASCENDING, DESCENDING
from pymongo.errors import OperationFailure

# 添加项目根目录到Python路径
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '../..'))
sys.path.insert(0, project_root)

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def build_mongo_uri():
    """构建MongoDB连接URI"""
    host = os.getenv("MONGODB_HOST", "localhost")
    port = int(os.getenv("MONGODB_PORT", "27017"))
    db = os.getenv("MONGODB_DATABASE", "tradingagents")
    user = os.getenv("MONGODB_USERNAME", "")
    pwd = os.getenv("MONGODB_PASSWORD", "")
    auth_src = os.getenv("MONGODB_AUTH_SOURCE", "admin")
    
    if user and pwd:
        return f"mongodb://{user}:{pwd}@{host}:{port}/{db}?authSource={auth_src}"
    return f"mongodb://{host}:{port}/{db}"


def create_index_safe(collection, index_spec, name=None, unique=False, sparse=False, background=True):
    """
    安全创建索引（如果已存在则跳过）
    
    Args:
        collection: MongoDB集合对象
        index_spec: 索引规范，如 [("field", 1)]
        name: 索引名称
        unique: 是否唯一索引
        sparse: 是否稀疏索引
        background: 是否后台创建
    """
    try:
        collection.create_index(
            index_spec,
            unique=unique,
            sparse=sparse,
            background=background,
            name=name
        )
        logger.info(f"✅ 创建索引: {name or str(index_spec)}")
        return True
    except OperationFailure as e:
        if "already exists" in str(e) or "duplicate key" in str(e).lower():
            logger.info(f"⚠️ 索引已存在，跳过: {name or str(index_spec)}")
            return True
        else:
            logger.error(f"❌ 创建索引失败 {name or str(index_spec)}: {e}")
            return False
    except Exception as e:
        logger.error(f"❌ 创建索引失败 {name or str(index_spec)}: {e}")
        return False


def create_stock_daily_quotes_indexes(db):
    """创建 stock_daily_quotes 集合索引"""
    logger.info("\n📊 创建 stock_daily_quotes 集合索引...")
    collection = db.stock_daily_quotes
    
    indexes_created = 0
    
    # 1. 复合唯一索引：股票代码+交易日期+数据源+周期（主键索引）
    if create_index_safe(
        collection,
        [("symbol", ASCENDING), ("trade_date", ASCENDING), ("data_source", ASCENDING), ("period", ASCENDING)],
        name="symbol_date_source_period_unique",
        unique=True
    ):
        indexes_created += 1
    
    # 2. 股票代码索引（查询单只股票的历史数据）
    if create_index_safe(
        collection,
        [("symbol", ASCENDING)],
        name="symbol_index"
    ):
        indexes_created += 1
    
    # 3. 交易日期索引（按日期范围查询，降序）
    if create_index_safe(
        collection,
        [("trade_date", DESCENDING)],
        name="trade_date_index"
    ):
        indexes_created += 1
    
    # 4. 数据源索引（按数据源查询）
    if create_index_safe(
        collection,
        [("data_source", ASCENDING)],
        name="data_source_index"
    ):
        indexes_created += 1
    
    # 5. 复合索引：股票代码+交易日期（常用查询）
    if create_index_safe(
        collection,
        [("symbol", ASCENDING), ("trade_date", DESCENDING)],
        name="symbol_date_index"
    ):
        indexes_created += 1
    
    # 6. 市场类型索引
    if create_index_safe(
        collection,
        [("market", ASCENDING)],
        name="market_index"
    ):
        indexes_created += 1
    
    # 7. 更新时间索引（数据维护）
    if create_index_safe(
        collection,
        [("updated_at", DESCENDING)],
        name="updated_at_index"
    ):
        indexes_created += 1
    
    # 8. 复合索引：市场+交易日期（市场级别查询）
    if create_index_safe(
        collection,
        [("market", ASCENDING), ("trade_date", DESCENDING)],
        name="market_date_index"
    ):
        indexes_created += 1
    
    # 9. 复合索引：数据源+更新时间（数据同步监控）
    if create_index_safe(
        collection,
        [("data_source", ASCENDING), ("updated_at", DESCENDING)],
        name="source_updated_index"
    ):
        indexes_created += 1
    
    # 10. 稀疏索引：成交量（用于筛选活跃股票）
    if create_index_safe(
        collection,
        [("volume", DESCENDING)],
        name="volume_index",
        sparse=True
    ):
        indexes_created += 1
    
    # 11. 周期索引（用于按周期查询）
    if create_index_safe(
        collection,
        [("period", ASCENDING)],
        name="period_index"
    ):
        indexes_created += 1
    
    # 12. 复合索引：股票+周期+日期（常用查询）
    if create_index_safe(
        collection,
        [("symbol", ASCENDING), ("period", ASCENDING), ("trade_date", DESCENDING)],
        name="symbol_period_date_index"
    ):
        indexes_created += 1
    
    logger.info(f"✅ stock_daily_quotes 索引创建完成，共 {indexes_created} 个索引")
    return indexes_created


def create_market_quotes_indexes(db):
    """创建 market_quotes 集合索引"""
    logger.info("\n📊 创建 market_quotes 集合索引...")
    collection = db.market_quotes
    
    indexes_created = 0
    
    # 1. 唯一索引：股票代码（主键）
    if create_index_safe(
        collection,
        [("code", ASCENDING)],
        name="code_unique",
        unique=True
    ):
        indexes_created += 1
    
    # 2. 更新时间索引（用于查询最新数据）
    if create_index_safe(
        collection,
        [("updated_at", DESCENDING)],
        name="updated_at_index"
    ):
        indexes_created += 1
    
    # 3. 交易日期索引
    if create_index_safe(
        collection,
        [("trade_date", DESCENDING)],
        name="trade_date_index"
    ):
        indexes_created += 1
    
    logger.info(f"✅ market_quotes 索引创建完成，共 {indexes_created} 个索引")
    return indexes_created


def create_stock_basic_info_indexes(db):
    """创建 stock_basic_info 集合索引"""
    logger.info("\n📊 创建 stock_basic_info 集合索引...")
    collection = db.stock_basic_info
    
    indexes_created = 0
    
    # 1. 联合唯一索引：(code, source) - 允许同一股票有多个数据源
    if create_index_safe(
        collection,
        [("code", ASCENDING), ("source", ASCENDING)],
        name="uniq_code_source",
        unique=True
    ):
        indexes_created += 1
    
    # 2. 股票代码索引（非唯一，用于查询所有数据源）
    if create_index_safe(
        collection,
        [("code", ASCENDING)],
        name="idx_code"
    ):
        indexes_created += 1
    
    # 3. 数据源索引
    if create_index_safe(
        collection,
        [("source", ASCENDING)],
        name="idx_source"
    ):
        indexes_created += 1
    
    # 4. 股票名称索引
    if create_index_safe(
        collection,
        [("name", ASCENDING)],
        name="idx_name"
    ):
        indexes_created += 1
    
    # 5. 行业索引
    if create_index_safe(
        collection,
        [("industry", ASCENDING)],
        name="idx_industry"
    ):
        indexes_created += 1
    
    # 6. 市场索引
    if create_index_safe(
        collection,
        [("market", ASCENDING)],
        name="idx_market"
    ):
        indexes_created += 1
    
    # 7. 总市值索引（降序，便于排序）
    if create_index_safe(
        collection,
        [("total_mv", DESCENDING)],
        name="idx_total_mv_desc"
    ):
        indexes_created += 1
    
    # 8. 流通市值索引（降序）
    if create_index_safe(
        collection,
        [("circ_mv", DESCENDING)],
        name="idx_circ_mv_desc"
    ):
        indexes_created += 1
    
    # 9. 更新时间索引（降序）
    if create_index_safe(
        collection,
        [("updated_at", DESCENDING)],
        name="idx_updated_at_desc"
    ):
        indexes_created += 1
    
    # 10. PE 索引
    if create_index_safe(
        collection,
        [("pe", ASCENDING)],
        name="idx_pe"
    ):
        indexes_created += 1
    
    # 11. PB 索引
    if create_index_safe(
        collection,
        [("pb", ASCENDING)],
        name="idx_pb"
    ):
        indexes_created += 1
    
    # 12. 换手率索引（降序）
    if create_index_safe(
        collection,
        [("turnover_rate", DESCENDING)],
        name="idx_turnover_rate_desc"
    ):
        indexes_created += 1
    
    logger.info(f"✅ stock_basic_info 索引创建完成，共 {indexes_created} 个索引")
    return indexes_created


def create_stock_news_indexes(db):
    """创建 stock_news 集合索引"""
    logger.info("\n📊 创建 stock_news 集合索引...")
    collection = db.stock_news
    
    indexes_created = 0
    
    # 1. 唯一索引：URL+标题+发布时间（防止重复新闻）
    if create_index_safe(
        collection,
        [("url", ASCENDING), ("title", ASCENDING), ("publish_time", ASCENDING)],
        name="url_title_time_unique",
        unique=True
    ):
        indexes_created += 1
    
    # 2. 股票代码索引
    if create_index_safe(
        collection,
        [("symbol", ASCENDING)],
        name="symbol_index"
    ):
        indexes_created += 1
    
    # 3. 多股票代码索引
    if create_index_safe(
        collection,
        [("symbols", ASCENDING)],
        name="symbols_index"
    ):
        indexes_created += 1
    
    # 4. 发布时间索引（降序，用于时间范围查询）
    if create_index_safe(
        collection,
        [("publish_time", DESCENDING)],
        name="publish_time_desc"
    ):
        indexes_created += 1
    
    # 5. 复合索引：股票+时间（最常用查询）
    if create_index_safe(
        collection,
        [("symbol", ASCENDING), ("publish_time", DESCENDING)],
        name="symbol_time_desc"
    ):
        indexes_created += 1
    
    # 6. 复合索引：多股票+时间
    if create_index_safe(
        collection,
        [("symbols", ASCENDING), ("publish_time", DESCENDING)],
        name="symbols_time_desc"
    ):
        indexes_created += 1
    
    # 7. 数据源索引
    if create_index_safe(
        collection,
        [("data_source", ASCENDING)],
        name="data_source_index"
    ):
        indexes_created += 1
    
    logger.info(f"✅ stock_news 索引创建完成，共 {indexes_created} 个索引")
    return indexes_created


def create_stock_financial_data_indexes(db):
    """创建 stock_financial_data 集合索引"""
    logger.info("\n📊 创建 stock_financial_data 集合索引...")
    collection = db.stock_financial_data
    
    indexes_created = 0
    
    # 1. 唯一索引：symbol + report_period + data_source（主键索引）
    if create_index_safe(
        collection,
        [("symbol", ASCENDING), ("report_period", DESCENDING), ("data_source", ASCENDING)],
        name="symbol_period_source_unique",
        unique=True
    ):
        indexes_created += 1
    
    # 2. 复合索引：full_symbol + report_period
    if create_index_safe(
        collection,
        [("full_symbol", ASCENDING), ("report_period", DESCENDING)],
        name="full_symbol_period"
    ):
        indexes_created += 1
    
    # 3. 复合索引：market + report_period
    if create_index_safe(
        collection,
        [("market", ASCENDING), ("report_period", DESCENDING)],
        name="market_period"
    ):
        indexes_created += 1
    
    # 4. 报告期索引（降序）
    if create_index_safe(
        collection,
        [("report_period", DESCENDING)],
        name="report_period_desc"
    ):
        indexes_created += 1
    
    # 5. 公告日期索引（降序）
    if create_index_safe(
        collection,
        [("ann_date", DESCENDING)],
        name="ann_date_desc"
    ):
        indexes_created += 1
    
    # 6. 数据源索引
    if create_index_safe(
        collection,
        [("data_source", ASCENDING)],
        name="data_source"
    ):
        indexes_created += 1
    
    # 7. 报告类型索引
    if create_index_safe(
        collection,
        [("report_type", ASCENDING)],
        name="report_type"
    ):
        indexes_created += 1
    
    # 8. 更新时间索引（降序）
    if create_index_safe(
        collection,
        [("updated_at", DESCENDING)],
        name="updated_at_desc"
    ):
        indexes_created += 1
    
    # 9. 复合索引：symbol + report_type + report_period
    if create_index_safe(
        collection,
        [("symbol", ASCENDING), ("report_type", ASCENDING), ("report_period", DESCENDING)],
        name="symbol_type_period"
    ):
        indexes_created += 1
    
    # 10. 复合索引：symbol + report_period（用于跨数据源对比）
    if create_index_safe(
        collection,
        [("symbol", ASCENDING), ("report_period", DESCENDING)],
        name="symbol_period_compare"
    ):
        indexes_created += 1
    
    logger.info(f"✅ stock_financial_data 索引创建完成，共 {indexes_created} 个索引")
    return indexes_created


def create_scheduler_indexes(db):
    """创建调度器相关集合索引"""
    logger.info("\n📊 创建调度器相关集合索引...")
    
    indexes_created = 0
    
    # scheduler_history 索引
    history_collection = db.scheduler_history
    if create_index_safe(
        history_collection,
        [("job_id", ASCENDING)],
        name="job_id_index"
    ):
        indexes_created += 1
    
    if create_index_safe(
        history_collection,
        [("execution_time", DESCENDING)],
        name="execution_time_index"
    ):
        indexes_created += 1
    
    if create_index_safe(
        history_collection,
        [("status", ASCENDING)],
        name="status_index"
    ):
        indexes_created += 1
    
    # scheduler_metadata 索引
    metadata_collection = db.scheduler_metadata
    if create_index_safe(
        metadata_collection,
        [("job_id", ASCENDING)],
        name="job_id_unique",
        unique=True
    ):
        indexes_created += 1
    
    logger.info(f"✅ 调度器相关集合索引创建完成，共 {indexes_created} 个索引")
    return indexes_created


def main():
    """主函数"""
    logger.info("🚀 开始创建所有集合索引...")
    logger.info("=" * 60)
    
    try:
        # 连接MongoDB
        uri = build_mongo_uri()
        client = MongoClient(uri)
        dbname = os.getenv("MONGODB_DATABASE", "tradingagents")
        db = client[dbname]
        
        # 测试连接
        try:
            client.admin.command('ping')
            logger.info(f"✅ MongoDB连接成功: {dbname}")
        except Exception as e:
            logger.error(f"❌ MongoDB连接失败: {e}")
            return False
        
        total_indexes = 0
        
        # 创建各集合索引
        total_indexes += create_stock_daily_quotes_indexes(db)
        total_indexes += create_market_quotes_indexes(db)
        total_indexes += create_stock_basic_info_indexes(db)
        total_indexes += create_stock_news_indexes(db)
        total_indexes += create_stock_financial_data_indexes(db)
        total_indexes += create_scheduler_indexes(db)
        
        # 显示统计信息
        logger.info("\n" + "=" * 60)
        logger.info(f"📊 索引创建统计:")
        logger.info(f"  - 总索引数: {total_indexes}")
        
        # 显示各集合的索引列表
        collections = [
            "stock_daily_quotes",
            "market_quotes",
            "stock_basic_info",
            "stock_news",
            "stock_financial_data",
            "scheduler_history",
            "scheduler_metadata"
        ]
        
        logger.info("\n📋 各集合索引详情:")
        for coll_name in collections:
            try:
                collection = db[coll_name]
                indexes = list(collection.list_indexes())
                logger.info(f"\n  {coll_name}:")
                for idx in indexes:
                    idx_name = idx.get('name', 'N/A')
                    idx_key = idx.get('key', {})
                    idx_unique = idx.get('unique', False)
                    unique_str = " (唯一)" if idx_unique else ""
                    logger.info(f"    - {idx_name}: {idx_key}{unique_str}")
            except Exception as e:
                logger.warning(f"  ⚠️ 无法获取 {coll_name} 的索引信息: {e}")
        
        logger.info("\n🎉 所有索引创建完成！")
        client.close()
        return True
        
    except Exception as e:
        logger.error(f"❌ 创建索引失败: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return False


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)

