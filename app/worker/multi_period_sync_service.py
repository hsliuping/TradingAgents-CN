#!/usr/bin/env python3
"""
多周期历史数据同步服务
支持日线、周线、月线数据的统一同步
"""
import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from dataclasses import dataclass

from app.services.historical_data_service import get_historical_data_service
from app.worker.tushare_sync_service import TushareSyncService
from app.worker.akshare_sync_service import AKShareSyncService
from app.worker.baostock_sync_service import BaoStockSyncService

logger = logging.getLogger(__name__)


@dataclass
class MultiPeriodSyncStats:
    """多周期同步统计"""
    total_symbols: int = 0
    daily_records: int = 0
    weekly_records: int = 0
    monthly_records: int = 0
    success_count: int = 0
    error_count: int = 0
    errors: List[str] = None
    
    def __post_init__(self):
        if self.errors is None:
            self.errors = []


class MultiPeriodSyncService:
    """多周期历史数据同步服务"""
    
    def __init__(self):
        self.historical_service = None
        self.tushare_service = None
        self.akshare_service = None
        self.baostock_service = None
        
    async def initialize(self):
        """初始化服务"""
        try:
            self.historical_service = await get_historical_data_service()
            
            # 初始化各数据源服务
            self.tushare_service = TushareSyncService()
            await self.tushare_service.initialize()
            
            self.akshare_service = AKShareSyncService()
            await self.akshare_service.initialize()
            
            self.baostock_service = BaoStockSyncService()
            await self.baostock_service.initialize()
            
            logger.info("✅ 多周期同步服务初始化完成")
            
        except Exception as e:
            logger.error(f"❌ 多周期同步服务初始化失败: {e}")
            raise
    
    async def sync_multi_period_data(
        self,
        symbols: List[str] = None,
        periods: List[str] = None,
        data_sources: List[str] = None,
        start_date: str = None,
        end_date: str = None,
        all_history: bool = False
    ) -> MultiPeriodSyncStats:
        """
        同步多周期历史数据

        Args:
            symbols: 股票代码列表，None表示所有股票
            periods: 周期列表 (daily/weekly/monthly)
            data_sources: 数据源列表 (tushare/akshare/baostock)
            start_date: 开始日期
            end_date: 结束日期
            all_history: 是否同步所有历史数据（忽略时间范围）
        """
        if self.historical_service is None:
            await self.initialize()
        
        # 默认参数
        if periods is None:
            periods = ["daily", "weekly", "monthly"]
        if data_sources is None:
            data_sources = ["tushare", "akshare", "baostock"]
        if symbols is None:
            symbols = await self._get_all_symbols()

        # 处理all_history参数
        if all_history:
            start_date, end_date = await self._get_full_history_date_range()
            logger.info(f"🔄 启用全历史数据同步模式: {start_date} 到 {end_date}")

        stats = MultiPeriodSyncStats()
        stats.total_symbols = len(symbols)

        logger.info(f"🔄 开始多周期数据同步: {len(symbols)}只股票, "
                   f"周期{periods}, 数据源{data_sources}, "
                   f"时间范围: {start_date or '默认'} 到 {end_date or '今天'}")
        
        try:
            # 🔥 优化：不同数据源可以并行执行（因为它们使用不同的API，互不影响）
            # 同一种数据源的不同周期仍然串行执行（避免API限流）
            
            # 为每个数据源创建任务（每个数据源内部串行处理所有周期）
            tasks = []
            task_info = []  # 保存任务信息，用于结果处理
            
            for data_source in data_sources:
                # 为每个数据源创建一个任务，该任务会串行处理该数据源的所有周期
                task = self._sync_data_source_all_periods(
                    data_source, periods, symbols, start_date, end_date
                )
                tasks.append(task)
                task_info.append(data_source)
            
            # 并行执行所有数据源的同步任务
            if tasks:
                logger.info(f"🚀 开始并行同步 {len(tasks)} 个数据源的历史数据: {task_info}")
                
                # 使用 asyncio.gather 并行执行
                period_results = await asyncio.gather(*tasks, return_exceptions=True)
                
                # 处理结果
                for i, (data_source, result) in enumerate(zip(task_info, period_results)):
                    if isinstance(result, Exception):
                        logger.error(f"❌ {data_source} 历史数据同步失败: {result}", exc_info=True)
                        stats.error_count += len(symbols)  # 假设全部失败
                    else:
                        # result 是一个字典，包含各周期的统计信息
                        for period in periods:
                            period_stats = result.get(period, {})
                            
                            # 累计统计
                            if period == "daily":
                                stats.daily_records += period_stats.get("records", 0)
                            elif period == "weekly":
                                stats.weekly_records += period_stats.get("records", 0)
                            elif period == "monthly":
                                stats.monthly_records += period_stats.get("records", 0)
                            
                            stats.success_count += period_stats.get("success", 0)
                            stats.error_count += period_stats.get("errors", 0)
                            
                            # 进度日志
                            logger.info(f"📊 {data_source}-{period}同步完成: "
                                       f"{period_stats.get('records', 0)}条记录")
            else:
                logger.warning("⚠️ 没有可用的数据源进行历史数据同步")
            
            logger.info(f"✅ 多周期数据同步完成: "
                       f"日线{stats.daily_records}, 周线{stats.weekly_records}, "
                       f"月线{stats.monthly_records}条记录")
            
            return stats
            
        except Exception as e:
            logger.error(f"❌ 多周期数据同步失败: {e}")
            stats.errors.append(str(e))
            return stats
    
    async def _sync_data_source_all_periods(
        self,
        data_source: str,
        periods: List[str],
        symbols: List[str],
        start_date: str = None,
        end_date: str = None
    ) -> Dict[str, Dict[str, Any]]:
        """
        同步某个数据源的所有周期数据（串行执行，避免API限流）
        
        Returns:
            字典，key为周期名称，value为该周期的统计信息
        """
        results = {}
        
        # 同一种数据源的不同周期串行执行（避免API限流）
        for period in periods:
            try:
                period_stats = await self._sync_period_data(
                    data_source, period, symbols, start_date, end_date
                )
                results[period] = period_stats
            except Exception as e:
                logger.error(f"❌ {data_source}-{period}同步失败: {e}")
                results[period] = {"records": 0, "success": 0, "errors": len(symbols)}
        
        return results
    
    async def _sync_period_data(
        self,
        data_source: str,
        period: str,
        symbols: List[str],
        start_date: str = None,
        end_date: str = None
    ) -> Dict[str, Any]:
        """同步特定周期的数据"""
        stats = {"records": 0, "success": 0, "errors": 0}
        
        try:
            logger.info(f"📈 开始同步{data_source}-{period}数据: {len(symbols)}只股票")
            
            # 选择对应的服务
            if data_source == "tushare":
                service = self.tushare_service
            elif data_source == "akshare":
                service = self.akshare_service
            elif data_source == "baostock":
                service = self.baostock_service
            else:
                logger.error(f"❌ 不支持的数据源: {data_source}")
                return stats
            
            # 批量处理
            batch_size = 50
            for i in range(0, len(symbols), batch_size):
                batch = symbols[i:i + batch_size]
                batch_stats = await self._sync_batch_period_data(
                    service, data_source, period, batch, start_date, end_date
                )
                
                stats["records"] += batch_stats["records"]
                stats["success"] += batch_stats["success"]
                stats["errors"] += batch_stats["errors"]
                
                # 进度日志
                progress = min(i + batch_size, len(symbols))
                logger.info(f"📊 {data_source}-{period}进度: {progress}/{len(symbols)}")
                
                # API限流
                await asyncio.sleep(0.5)
            
            return stats
            
        except Exception as e:
            logger.error(f"❌ {data_source}-{period}同步失败: {e}")
            stats["errors"] += 1
            return stats
    
    async def _sync_batch_period_data(
        self,
        service,
        data_source: str,
        period: str,
        symbols: List[str],
        start_date: str = None,
        end_date: str = None
    ) -> Dict[str, Any]:
        """同步批次周期数据"""
        stats = {"records": 0, "success": 0, "errors": 0}
        
        for symbol in symbols:
            try:
                # 获取历史数据
                if data_source == "tushare":
                    hist_data = await service.provider.get_historical_data(
                        symbol, start_date, end_date, period
                    )
                elif data_source == "akshare":
                    hist_data = await service.provider.get_historical_data(
                        symbol, start_date, end_date, period
                    )
                elif data_source == "baostock":
                    hist_data = await service.provider.get_historical_data(
                        symbol, start_date, end_date, period
                    )
                else:
                    continue
                
                if hist_data is not None and not hist_data.empty:
                    # 保存到数据库
                    saved_count = await self.historical_service.save_historical_data(
                        symbol=symbol,
                        data=hist_data,
                        data_source=data_source,
                        market="CN",
                        period=period
                    )
                    
                    stats["records"] += saved_count
                    stats["success"] += 1
                else:
                    stats["errors"] += 1
                    
            except Exception as e:
                logger.error(f"❌ {symbol}-{period}同步失败: {e}")
                stats["errors"] += 1
        
        return stats
    
    async def _get_all_symbols(self) -> List[str]:
        """获取所有股票代码"""
        try:
            # 从数据库获取股票列表
            from app.core.database import get_mongo_db
            db = get_mongo_db()
            collection = db.stock_basic_info

            cursor = collection.find({}, {"symbol": 1})
            symbols = [doc["symbol"] async for doc in cursor]

            logger.info(f"📊 获取股票列表: {len(symbols)}只股票")
            return symbols

        except Exception as e:
            logger.error(f"❌ 获取股票列表失败: {e}")
            return []

    async def _get_full_history_date_range(self) -> tuple[str, str]:
        """获取全历史数据的日期范围"""
        try:
            from datetime import datetime, timedelta

            # 结束日期：今天
            end_date = datetime.now().strftime('%Y-%m-%d')

            # 开始日期：根据数据源确定
            # Tushare: 1990年开始
            # AKShare: 1990年开始
            # BaoStock: 1990年开始
            # 为了安全起见，从1990年开始
            start_date = "1990-01-01"

            logger.info(f"📅 全历史数据范围: {start_date} 到 {end_date}")
            return start_date, end_date

        except Exception as e:
            logger.error(f"❌ 获取全历史日期范围失败: {e}")
            # 默认返回最近5年的数据
            end_date = datetime.now().strftime('%Y-%m-%d')
            start_date = (datetime.now() - timedelta(days=365*5)).strftime('%Y-%m-%d')
            return start_date, end_date
    
    async def get_sync_statistics(self) -> Dict[str, Any]:
        """获取同步统计信息"""
        try:
            if self.historical_service is None:
                await self.initialize()
            
            # 按周期统计
            from app.core.database import get_mongo_db
            db = get_mongo_db()
            collection = db.stock_daily_quotes
            
            pipeline = [
                {"$group": {
                    "_id": {
                        "period": "$period",
                        "data_source": "$data_source"
                    },
                    "count": {"$sum": 1},
                    "latest_date": {"$max": "$trade_date"}
                }}
            ]
            
            results = await collection.aggregate(pipeline).to_list(length=None)
            
            # 格式化统计结果
            stats = {}
            for result in results:
                period = result["_id"]["period"]
                source = result["_id"]["data_source"]
                
                if period not in stats:
                    stats[period] = {}
                
                stats[period][source] = {
                    "count": result["count"],
                    "latest_date": result["latest_date"]
                }
            
            return {
                "period_statistics": stats,
                "last_updated": datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            logger.error(f"❌ 获取同步统计失败: {e}")
            return {}


# 全局服务实例
_multi_period_sync_service = None


async def get_multi_period_sync_service() -> MultiPeriodSyncService:
    """获取多周期同步服务实例"""
    global _multi_period_sync_service
    if _multi_period_sync_service is None:
        _multi_period_sync_service = MultiPeriodSyncService()
        await _multi_period_sync_service.initialize()
    return _multi_period_sync_service


# APScheduler任务函数
async def run_multi_period_sync(periods: List[str] = None):
    """APScheduler任务：多周期数据同步"""
    try:
        service = await get_multi_period_sync_service()
        result = await service.sync_multi_period_data(periods=periods)
        logger.info(f"✅ 多周期数据同步完成: {result}")
        return result
    except Exception as e:
        logger.error(f"❌ 多周期数据同步失败: {e}")
        raise


async def run_daily_sync():
    """APScheduler任务：日线数据同步"""
    return await run_multi_period_sync(["daily"])


async def run_weekly_sync():
    """APScheduler任务：周线数据同步"""
    return await run_multi_period_sync(["weekly"])


async def run_monthly_sync():
    """APScheduler任务：月线数据同步"""
    return await run_multi_period_sync(["monthly"])
