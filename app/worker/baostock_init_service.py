#!/usr/bin/env python3
"""
BaoStock数据初始化服务
提供BaoStock数据的完整初始化功能
"""
import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field

from app.core.config import get_settings
from app.core.database import get_database
from app.worker.baostock_sync_service import BaoStockSyncService, BaoStockSyncStats

logger = logging.getLogger(__name__)


@dataclass
class BaoStockInitializationStats:
    """BaoStock初始化统计"""
    completed_steps: int = 0
    total_steps: int = 6
    current_step: str = ""
    basic_info_count: int = 0
    quotes_count: int = 0
    historical_records: int = 0
    weekly_records: int = 0
    monthly_records: int = 0
    financial_records: int = 0
    errors: List[str] = field(default_factory=list)
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    
    @property
    def duration(self) -> float:
        """计算耗时（秒）"""
        if self.start_time and self.end_time:
            return (self.end_time - self.start_time).total_seconds()
        return 0.0
    
    @property
    def progress(self) -> str:
        """进度字符串"""
        return f"{self.completed_steps}/{self.total_steps}"


class BaoStockInitService:
    """BaoStock数据初始化服务"""

    def __init__(self):
        """
        初始化服务

        注意：数据库连接在 initialize() 方法中异步初始化
        """
        try:
            self.settings = get_settings()
            self.db = None  # 🔥 延迟初始化
            self.sync_service = BaoStockSyncService()
            logger.info("✅ BaoStock初始化服务初始化成功")
        except Exception as e:
            logger.error(f"❌ BaoStock初始化服务初始化失败: {e}")
            raise

    async def initialize(self):
        """异步初始化服务"""
        try:
            # 🔥 初始化数据库连接
            from app.core.database import get_mongo_db
            self.db = get_mongo_db()

            # 🔥 初始化同步服务
            await self.sync_service.initialize()

            logger.info("✅ BaoStock初始化服务异步初始化完成")
        except Exception as e:
            logger.error(f"❌ BaoStock初始化服务异步初始化失败: {e}")
            raise
    
    async def check_database_status(self) -> Dict[str, Any]:
        """检查数据库状态"""
        try:
            # 检查基础信息
            basic_info_count = await self.db.stock_basic_info.count_documents({"source": "baostock"})
            basic_info_latest = None
            if basic_info_count > 0:
                latest_doc = await self.db.stock_basic_info.find_one(
                    {"source": "baostock"},
                    sort=[("last_sync", -1)]
                )
                if latest_doc:
                    basic_info_latest = latest_doc.get("last_sync")
            
            # 检查行情数据
            quotes_count = await self.db.market_quotes.count_documents({"source": "baostock"})
            quotes_latest = None
            if quotes_count > 0:
                latest_doc = await self.db.market_quotes.find_one(
                    {"source": "baostock"},
                    sort=[("last_sync", -1)]
                )
                if latest_doc:
                    quotes_latest = latest_doc.get("last_sync")
            
            return {
                "basic_info_count": basic_info_count,
                "basic_info_latest": basic_info_latest,
                "quotes_count": quotes_count,
                "quotes_latest": quotes_latest,
                "status": "ready" if basic_info_count > 0 else "empty"
            }
            
        except Exception as e:
            logger.error(f"❌ 检查数据库状态失败: {e}")
            return {"status": "error", "error": str(e)}
    
    async def full_initialization(self, historical_days: int = 365,
                                force: bool = False,
                                enable_multi_period: bool = False) -> BaoStockInitializationStats:
        """
        完整数据初始化

        Args:
            historical_days: 历史数据天数
            force: 是否强制重新初始化
            enable_multi_period: 是否启用多周期数据同步（日线、周线、月线）

        Returns:
            初始化统计信息
        """
        stats = BaoStockInitializationStats()
        stats.total_steps = 8 if enable_multi_period else 6
        stats.start_time = datetime.now()
        
        try:
            logger.info("🚀 开始BaoStock完整数据初始化...")
            
            # 步骤1: 检查数据库状态
            stats.current_step = "检查数据库状态"
            logger.info(f"1️⃣ {stats.current_step}...")
            
            db_status = await self.check_database_status()
            if db_status["status"] != "empty" and not force:
                logger.info("ℹ️ 数据库已有数据，跳过初始化（使用--force强制重新初始化）")
                stats.completed_steps = 6
                stats.end_time = datetime.now()
                return stats
            
            stats.completed_steps += 1
            
            # 步骤2: 初始化股票基础信息
            stats.current_step = "初始化股票基础信息"
            logger.info(f"2️⃣ {stats.current_step}...")
            
            basic_stats = await self.sync_service.sync_stock_basic_info()
            stats.basic_info_count = basic_stats.basic_info_count
            stats.errors.extend(basic_stats.errors)
            stats.completed_steps += 1
            
            if stats.basic_info_count == 0:
                raise Exception("基础信息同步失败，无法继续")
            
            # 步骤3: 同步历史数据（日线）
            stats.current_step = "同步历史数据（日线）"
            logger.info(f"3️⃣ {stats.current_step} (最近{historical_days}天)...")

            historical_stats = await self.sync_service.sync_historical_data(days=historical_days, period="daily")
            stats.historical_records = historical_stats.historical_records
            stats.errors.extend(historical_stats.errors)
            stats.completed_steps += 1

            # 步骤4: 同步多周期数据（如果启用）
            if enable_multi_period:
                # 同步周线数据
                stats.current_step = "同步周线数据"
                logger.info(f"4️⃣a {stats.current_step} (最近{historical_days}天)...")
                try:
                    weekly_stats = await self.sync_service.sync_historical_data(days=historical_days, period="weekly")
                    stats.weekly_records = weekly_stats.historical_records
                    stats.errors.extend(weekly_stats.errors)
                    logger.info(f"✅ 周线数据同步完成: {stats.weekly_records}条记录")
                except Exception as e:
                    logger.warning(f"⚠️ 周线数据同步失败: {e}（继续后续步骤）")
                stats.completed_steps += 1

                # 同步月线数据
                stats.current_step = "同步月线数据"
                logger.info(f"4️⃣b {stats.current_step} (最近{historical_days}天)...")
                try:
                    monthly_stats = await self.sync_service.sync_historical_data(days=historical_days, period="monthly")
                    stats.monthly_records = monthly_stats.historical_records
                    stats.errors.extend(monthly_stats.errors)
                    logger.info(f"✅ 月线数据同步完成: {stats.monthly_records}条记录")
                except Exception as e:
                    logger.warning(f"⚠️ 月线数据同步失败: {e}（继续后续步骤）")
                stats.completed_steps += 1
            
            # 步骤4: 同步财务数据
            stats.current_step = "同步财务数据"
            logger.info(f"4️⃣ {stats.current_step}...")
            
            financial_stats = await self._sync_financial_data()
            stats.financial_records = financial_stats
            stats.completed_steps += 1
            
            # 步骤5: 同步最新行情
            stats.current_step = "同步最新行情"
            logger.info(f"5️⃣ {stats.current_step}...")
            
            quotes_stats = await self.sync_service.sync_realtime_quotes()
            stats.quotes_count = quotes_stats.quotes_count
            stats.errors.extend(quotes_stats.errors)
            stats.completed_steps += 1
            
            # 步骤6: 验证数据完整性
            stats.current_step = "验证数据完整性"
            logger.info(f"6️⃣ {stats.current_step}...")
            
            await self._verify_data_integrity(stats)
            stats.completed_steps += 1
            
            stats.end_time = datetime.now()
            logger.info(f"🎉 BaoStock完整初始化成功完成！耗时: {stats.duration:.1f}秒")
            
            return stats
            
        except Exception as e:
            stats.end_time = datetime.now()
            error_msg = f"BaoStock初始化失败: {e}"
            logger.error(f"❌ {error_msg}")
            stats.errors.append(error_msg)
            return stats
    
    async def _sync_financial_data(self) -> int:
        """同步财务数据"""
        try:
            # 获取股票列表
            collection = self.db.stock_basic_info
            cursor = collection.find({"source": "baostock"}, {"code": 1})
            stock_codes = [doc["code"] async for doc in cursor]
            
            if not stock_codes:
                return 0
            
            # 限制数量以避免超时
            limited_codes = stock_codes[:50]  # 只处理前50只股票
            financial_count = 0
            
            for code in limited_codes:
                try:
                    financial_data = await self.sync_service.provider.get_financial_data(code)
                    if financial_data:
                        # 更新到数据库
                        await collection.update_one(
                            {"code": code},
                            {"$set": {
                                "financial_data": financial_data,
                                "financial_data_updated": datetime.now()
                            }}
                        )
                        financial_count += 1
                    
                    # 避免API限制
                    await asyncio.sleep(0.5)
                    
                except Exception as e:
                    logger.debug(f"获取{code}财务数据失败: {e}")
                    continue
            
            logger.info(f"✅ 财务数据同步完成: {financial_count}条记录")
            return financial_count
            
        except Exception as e:
            logger.error(f"❌ 财务数据同步失败: {e}")
            return 0
    
    async def _verify_data_integrity(self, stats: BaoStockInitializationStats):
        """验证数据完整性"""
        try:
            # 检查基础信息
            basic_count = await self.db.stock_basic_info.count_documents({"source": "baostock"})
            if basic_count != stats.basic_info_count:
                logger.warning(f"⚠️ 基础信息数量不匹配: 预期{stats.basic_info_count}, 实际{basic_count}")
            
            # 检查行情数据
            quotes_count = await self.db.market_quotes.count_documents({"source": "baostock"})
            if quotes_count != stats.quotes_count:
                logger.warning(f"⚠️ 行情数据数量不匹配: 预期{stats.quotes_count}, 实际{quotes_count}")
            
            logger.info("✅ 数据完整性验证完成")
            
        except Exception as e:
            logger.error(f"❌ 数据完整性验证失败: {e}")
            stats.errors.append(f"数据完整性验证失败: {e}")
    
    async def basic_initialization(self) -> BaoStockInitializationStats:
        """基础数据初始化（仅基础信息和行情）"""
        stats = BaoStockInitializationStats()
        stats.start_time = datetime.now()
        stats.total_steps = 3
        
        try:
            logger.info("🚀 开始BaoStock基础数据初始化...")
            
            # 步骤1: 初始化股票基础信息
            stats.current_step = "初始化股票基础信息"
            logger.info(f"1️⃣ {stats.current_step}...")
            
            basic_stats = await self.sync_service.sync_stock_basic_info()
            stats.basic_info_count = basic_stats.basic_info_count
            stats.errors.extend(basic_stats.errors)
            stats.completed_steps += 1
            
            # 步骤2: 同步最新行情
            stats.current_step = "同步最新行情"
            logger.info(f"2️⃣ {stats.current_step}...")
            
            quotes_stats = await self.sync_service.sync_realtime_quotes()
            stats.quotes_count = quotes_stats.quotes_count
            stats.errors.extend(quotes_stats.errors)
            stats.completed_steps += 1
            
            # 步骤3: 验证数据
            stats.current_step = "验证数据完整性"
            logger.info(f"3️⃣ {stats.current_step}...")
            
            await self._verify_data_integrity(stats)
            stats.completed_steps += 1
            
            stats.end_time = datetime.now()
            logger.info(f"🎉 BaoStock基础初始化完成！耗时: {stats.duration:.1f}秒")
            
            return stats
            
        except Exception as e:
            stats.end_time = datetime.now()
            error_msg = f"BaoStock基础初始化失败: {e}"
            logger.error(f"❌ {error_msg}")
            stats.errors.append(error_msg)
            return stats


# APScheduler兼容的初始化函数
async def run_baostock_full_initialization():
    """运行BaoStock完整初始化"""
    try:
        service = BaoStockInitService()
        await service.initialize()  # 🔥 必须先初始化
        stats = await service.full_initialization()
        logger.info(f"🎯 BaoStock完整初始化完成: {stats.progress}, 耗时: {stats.duration:.1f}秒")
    except Exception as e:
        logger.error(f"❌ BaoStock完整初始化任务失败: {e}")


async def run_baostock_basic_initialization():
    """运行BaoStock基础初始化"""
    try:
        service = BaoStockInitService()
        await service.initialize()  # 🔥 必须先初始化
        stats = await service.basic_initialization()
        logger.info(f"🎯 BaoStock基础初始化完成: {stats.progress}, 耗时: {stats.duration:.1f}秒")
    except Exception as e:
        logger.error(f"❌ BaoStock基础初始化任务失败: {e}")
