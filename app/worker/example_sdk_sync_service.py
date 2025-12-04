"""
示例SDK数据同步服务 (app层)
展示如何创建数据同步服务，将外部SDK数据写入标准化的MongoDB集合

架构说明:
- tradingagents层: 纯数据获取和标准化，不涉及数据库操作
- app层: 数据同步服务，负责数据库操作和业务逻辑
- 数据流: 外部SDK → tradingagents适配器 → app同步服务 → MongoDB
"""
import asyncio
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional

import os
from app.services.stock_data_service import get_stock_data_service
from app.core.database import get_mongo_db
from tradingagents.dataflows.providers.examples.example_sdk import ExampleSDKProvider

logger = logging.getLogger(__name__)


class ExampleSDKSyncService:
    """
    示例SDK数据同步服务 (app层)

    职责:
    - 调用tradingagents层的SDK适配器获取标准化数据
    - 执行业务逻辑处理和数据验证
    - 将数据写入MongoDB数据库
    - 管理同步状态和错误处理
    - 提供性能监控和统计

    架构分层:
    - tradingagents/dataflows/: 纯数据获取适配器
    - app/worker/: 数据同步服务 (本类)
    - app/services/: 数据访问服务
    """

    def __init__(self):
        # 使用tradingagents层的适配器 (纯数据获取)
        self.provider = ExampleSDKProvider()
        # 使用app层的数据服务 (数据库操作)
        self.stock_service = get_stock_data_service()
        
        # 同步配置
        self.batch_size = int(os.getenv("EXAMPLE_SDK_BATCH_SIZE", "100"))
        self.retry_times = int(os.getenv("EXAMPLE_SDK_RETRY_TIMES", "3"))
        self.retry_delay = int(os.getenv("EXAMPLE_SDK_RETRY_DELAY", "5"))
        
        # 统计信息
        self.sync_stats = {
            "basic_info": {"total": 0, "success": 0, "failed": 0},
            "quotes": {"total": 0, "success": 0, "failed": 0},
            "financial": {"total": 0, "success": 0, "failed": 0}
        }
    
    async def sync_all_data(self):
        """同步所有数据"""
        logger.info("🚀 开始ExampleSDK全量数据同步...")
        
        start_time = datetime.now()
        
        try:
            # 连接数据源
            if not await self.provider.connect():
                logger.error("❌ ExampleSDK连接失败，同步中止")
                return False
            
            # 同步基础信息
            await self.sync_basic_info()
            
            # 同步实时行情
            await self.sync_realtime_quotes()
            
            # 同步财务数据
            await self.sync_financial_data()
            
            # 记录同步状态
            await self._record_sync_status("success", start_time)
            
            logger.info("✅ ExampleSDK全量数据同步完成")
            self._log_sync_stats()
            
            return True
            
        except Exception as e:
            logger.error(f"❌ ExampleSDK数据同步失败: {e}")
            await self._record_sync_status("failed", start_time, str(e))
            return False
            
        finally:
            await self.provider.disconnect()
    
    async def sync_basic_info(self):
        """同步股票基础信息"""
        logger.info("📊 开始同步股票基础信息...")
        
        try:
            # 获取股票列表
            stock_list = await self.provider.get_stock_list()
            
            if not stock_list:
                logger.warning("⚠️ 未获取到股票列表")
                return
            
            self.sync_stats["basic_info"]["total"] = len(stock_list)
            
            # 批量处理
            for i in range(0, len(stock_list), self.batch_size):
                batch = stock_list[i:i + self.batch_size]
                await self._process_basic_info_batch(batch)
                
                # 进度日志
                processed = min(i + self.batch_size, len(stock_list))
                logger.info(f"📈 基础信息同步进度: {processed}/{len(stock_list)}")
                
                # 避免API限制
                await asyncio.sleep(0.1)
            
            logger.info(f"✅ 股票基础信息同步完成: {self.sync_stats['basic_info']['success']}/{self.sync_stats['basic_info']['total']}")
            
        except Exception as e:
            logger.error(f"❌ 股票基础信息同步失败: {e}")
    
    async def sync_realtime_quotes(self):
        """同步实时行情"""
        logger.info("📈 开始同步实时行情...")
        
        try:
            # 获取需要同步的股票代码列表
            db = get_mongo_db()
            cursor = db.stock_basic_info.find({}, {"code": 1})
            stock_codes = [doc["code"] async for doc in cursor]
            
            if not stock_codes:
                logger.warning("⚠️ 未找到需要同步行情的股票")
                return
            
            self.sync_stats["quotes"]["total"] = len(stock_codes)
            
            # 批量处理
            for i in range(0, len(stock_codes), self.batch_size):
                batch = stock_codes[i:i + self.batch_size]
                await self._process_quotes_batch(batch)
                
                # 进度日志
                processed = min(i + self.batch_size, len(stock_codes))
                logger.info(f"📈 实时行情同步进度: {processed}/{len(stock_codes)}")
                
                # 避免API限制
                await asyncio.sleep(0.1)
            
            logger.info(f"✅ 实时行情同步完成: {self.sync_stats['quotes']['success']}/{self.sync_stats['quotes']['total']}")
            
        except Exception as e:
            logger.error(f"❌ 实时行情同步失败: {e}")
    
    async def sync_financial_data(self):
        """同步财务数据"""
        logger.info("💰 开始同步财务数据...")
        
        try:
            # 获取需要更新财务数据的股票
            # 这里可以根据业务需求筛选，比如只同步主要股票或定期更新
            db = get_mongo_db()
            cursor = db.stock_basic_info.find(
                {"total_mv": {"$gte": 100}},  # 只同步市值大于100亿的股票
                {"code": 1}
            ).limit(50)  # 限制数量，避免API调用过多
            
            stock_codes = [doc["code"] async for doc in cursor]
            
            if not stock_codes:
                logger.warning("⚠️ 未找到需要同步财务数据的股票")
                return
            
            self.sync_stats["financial"]["total"] = len(stock_codes)
            
            # 逐个处理（财务数据通常API限制更严格）
            for code in stock_codes:
                await self._process_financial_data(code)
                await asyncio.sleep(1)  # 更长的延迟
            
            logger.info(f"✅ 财务数据同步完成: {self.sync_stats['financial']['success']}/{self.sync_stats['financial']['total']}")
            
        except Exception as e:
            logger.error(f"❌ 财务数据同步失败: {e}")
    
    async def _process_basic_info_batch(self, batch: List[Dict[str, Any]]):
        """处理基础信息批次"""
        for stock_info in batch:
            try:
                code = stock_info.get("code")
                if not code:
                    continue
                
                # 更新到数据库
                success = await self.stock_service.update_stock_basic_info(code, stock_info)
                
                if success:
                    self.sync_stats["basic_info"]["success"] += 1
                else:
                    self.sync_stats["basic_info"]["failed"] += 1
                    logger.warning(f"⚠️ 更新{code}基础信息失败")
                    
            except Exception as e:
                self.sync_stats["basic_info"]["failed"] += 1
                logger.error(f"❌ 处理{stock_info.get('code', 'N/A')}基础信息失败: {e}")
    
    async def _process_quotes_batch(self, batch: List[str]):
        """处理行情批次"""
        for code in batch:
            try:
                # 获取实时行情
                quotes = await self.provider.get_stock_quotes(code)
                
                if quotes:
                    # 更新到数据库
                    success = await self.stock_service.update_market_quotes(code, quotes)
                    
                    if success:
                        self.sync_stats["quotes"]["success"] += 1
                    else:
                        self.sync_stats["quotes"]["failed"] += 1
                        logger.warning(f"⚠️ 更新{code}行情失败")
                else:
                    self.sync_stats["quotes"]["failed"] += 1
                    
            except Exception as e:
                self.sync_stats["quotes"]["failed"] += 1
                logger.error(f"❌ 处理{code}行情失败: {e}")
    
    async def _process_financial_data(self, code: str):
        """处理财务数据"""
        try:
            # 获取财务数据
            financial_data = await self.provider.get_financial_data(code)
            
            if financial_data:
                # 这里需要实现财务数据的存储逻辑
                # 可能需要创建新的集合 stock_financial_data
                db = get_mongo_db()
                
                # 构建更新数据
                update_data = {
                    "code": code,
                    "financial_data": financial_data,
                    "updated_at": datetime.utcnow()
                }
                
                # 更新或插入财务数据
                await db.stock_financial_data.update_one(
                    {"code": code},
                    {"$set": update_data},
                    upsert=True
                )
                
                self.sync_stats["financial"]["success"] += 1
                logger.debug(f"✅ 更新{code}财务数据成功")
            else:
                self.sync_stats["financial"]["failed"] += 1
                
        except Exception as e:
            self.sync_stats["financial"]["failed"] += 1
            logger.error(f"❌ 处理{code}财务数据失败: {e}")
    
    async def _record_sync_status(self, status: str, start_time: datetime, error_msg: str = None):
        """记录同步状态"""
        try:
            db = get_mongo_db()
            
            sync_record = {
                "job": "example_sdk_sync",
                "status": status,
                "started_at": start_time,
                "finished_at": datetime.now(),
                "duration": (datetime.now() - start_time).total_seconds(),
                "stats": self.sync_stats.copy(),
                "error_message": error_msg,
                "created_at": datetime.now()
            }
            
            await db.sync_status.update_one(
                {"job": "example_sdk_sync"},
                {"$set": sync_record},
                upsert=True
            )
            
        except Exception as e:
            logger.error(f"❌ 记录同步状态失败: {e}")
    
    def _log_sync_stats(self):
        """记录同步统计信息"""
        logger.info("📊 ExampleSDK同步统计:")
        for data_type, stats in self.sync_stats.items():
            total = stats["total"]
            success = stats["success"]
            failed = stats["failed"]
            success_rate = (success / total * 100) if total > 0 else 0
            
            logger.info(f"   {data_type}: {success}/{total} ({success_rate:.1f}%) 成功, {failed} 失败")
    
    async def sync_incremental(self):
        """增量同步 - 只同步实时行情"""
        logger.info("🔄 开始ExampleSDK增量同步...")
        
        try:
            if not await self.provider.connect():
                logger.error("❌ ExampleSDK连接失败，增量同步中止")
                return False
            
            # 只同步实时行情
            await self.sync_realtime_quotes()
            
            logger.info("✅ ExampleSDK增量同步完成")
            return True
            
        except Exception as e:
            logger.error(f"❌ ExampleSDK增量同步失败: {e}")
            return False
            
        finally:
            await self.provider.disconnect()


# ==================== 定时任务函数 ====================

async def run_full_sync():
    """运行全量同步 - 供定时任务调用"""
    sync_service = ExampleSDKSyncService()
    return await sync_service.sync_all_data()


async def run_incremental_sync():
    """运行增量同步 - 供定时任务调用"""
    sync_service = ExampleSDKSyncService()
    return await sync_service.sync_incremental()


# ==================== 使用示例 ====================

async def main():
    """主函数 - 用于测试"""
    logging.basicConfig(level=logging.INFO)
    
    sync_service = ExampleSDKSyncService()
    
    # 测试全量同步
    await sync_service.sync_all_data()


if __name__ == "__main__":
    asyncio.run(main())
