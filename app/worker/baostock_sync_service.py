#!/usr/bin/env python3
"""
BaoStock数据同步服务
提供BaoStock数据的批量同步功能，集成到APScheduler调度系统
"""
import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass

from app.core.config import get_settings
from app.core.database import get_database
from app.services.historical_data_service import get_historical_data_service
from tradingagents.dataflows.providers.china.baostock import BaoStockProvider

logger = logging.getLogger(__name__)


@dataclass
class BaoStockSyncStats:
    """BaoStock同步统计"""
    basic_info_count: int = 0
    quotes_count: int = 0
    historical_records: int = 0
    financial_records: int = 0
    errors: List[str] = None
    
    def __post_init__(self):
        if self.errors is None:
            self.errors = []


class BaoStockSyncService:
    """BaoStock数据同步服务"""

    def __init__(self):
        """
        初始化同步服务

        注意：数据库连接在 initialize() 方法中异步初始化
        """
        try:
            self.settings = get_settings()
            self.provider = BaoStockProvider()
            self.historical_service = None  # 延迟初始化
            self.db = None  # 🔥 延迟初始化，在 initialize() 中设置
            self._current_job_id = None  # 🔥 当前任务ID，用于进度跟踪和停止检查

            logger.info("✅ BaoStock同步服务初始化成功")
        except Exception as e:
            logger.error(f"❌ BaoStock同步服务初始化失败: {e}")
            raise

    async def initialize(self):
        """异步初始化服务"""
        try:
            # 🔥 初始化数据库连接（必须在异步上下文中）
            from app.core.database import get_mongo_db
            self.db = get_mongo_db()

            # 初始化历史数据服务
            if self.historical_service is None:
                from app.services.historical_data_service import get_historical_data_service
                self.historical_service = await get_historical_data_service()

            logger.info("✅ BaoStock同步服务异步初始化完成")
        except Exception as e:
            logger.error(f"❌ BaoStock同步服务异步初始化失败: {e}")
            raise
    
    async def sync_stock_basic_info(self, batch_size: int = 100) -> BaoStockSyncStats:
        """
        同步股票基础信息
        
        Args:
            batch_size: 批处理大小
            
        Returns:
            同步统计信息
        """
        stats = BaoStockSyncStats()
        
        try:
            logger.info("🔄 开始BaoStock股票基础信息同步...")
            
            # 获取股票列表
            stock_list = await self.provider.get_stock_list()
            if not stock_list:
                logger.warning("⚠️ BaoStock股票列表为空")
                return stats
            
            logger.info(f"📋 获取到{len(stock_list)}只股票，开始批量同步...")
            
            # 批量处理
            for i in range(0, len(stock_list), batch_size):
                batch = stock_list[i:i + batch_size]
                batch_stats = await self._sync_basic_info_batch(batch)
                
                stats.basic_info_count += batch_stats.basic_info_count
                stats.errors.extend(batch_stats.errors)
                
                logger.info(f"📊 批次进度: {i + len(batch)}/{len(stock_list)}, "
                          f"成功: {batch_stats.basic_info_count}, "
                          f"错误: {len(batch_stats.errors)}")
                
                # 避免API限制
                await asyncio.sleep(0.1)
            
            logger.info(f"✅ BaoStock基础信息同步完成: {stats.basic_info_count}条记录")
            
            # 🔥 更新任务状态为已完成
            job_id = getattr(self, '_current_job_id', None) or "baostock_basic_info_sync"
            if job_id:
                try:
                    from app.services.scheduler_service import mark_job_completed
                    # 转换 BaoStockSyncStats 为字典格式
                    stats_dict = {
                        "total_processed": stats.basic_info_count,
                        "success_count": stats.basic_info_count,
                        "error_count": len(stats.errors),
                        "errors": [{"error": e} if isinstance(e, str) else e for e in stats.errors]
                    }
                    await mark_job_completed(job_id, stats_dict)
                except Exception as e:
                    logger.warning(f"⚠️ 更新任务完成状态失败: {e}")
            
            return stats
            
        except Exception as e:
            logger.error(f"❌ BaoStock基础信息同步失败: {e}")
            stats.errors.append(str(e))
            
            # 🔥 更新任务状态为失败
            job_id = getattr(self, '_current_job_id', None) or "baostock_basic_info_sync"
            if job_id:
                try:
                    from app.services.scheduler_service import mark_job_completed
                    await mark_job_completed(job_id, None, str(e))
                except Exception as update_error:
                    logger.warning(f"⚠️ 更新任务失败状态时出错: {update_error}")
            
            return stats
    
    async def _sync_basic_info_batch(self, stock_batch: List[Dict[str, Any]]) -> BaoStockSyncStats:
        """同步基础信息批次（包含估值数据和总市值）"""
        stats = BaoStockSyncStats()

        for stock in stock_batch:
            try:
                code = stock['code']

                # 1. 获取基础信息
                basic_info = await self.provider.get_stock_basic_info(code)

                if not basic_info:
                    stats.errors.append(f"获取{code}基础信息失败")
                    continue

                # 2. 获取估值数据（PE、PB、PS、PCF等）
                try:
                    valuation_data = await self.provider.get_valuation_data(code)
                    if valuation_data:
                        # 合并估值数据到基础信息
                        basic_info['pe'] = valuation_data.get('pe_ttm')  # 市盈率（TTM）
                        basic_info['pb'] = valuation_data.get('pb_mrq')  # 市净率（MRQ）
                        basic_info['pe_ttm'] = valuation_data.get('pe_ttm')
                        basic_info['pb_mrq'] = valuation_data.get('pb_mrq')
                        basic_info['ps'] = valuation_data.get('ps_ttm')  # 市销率
                        basic_info['pcf'] = valuation_data.get('pcf_ttm')  # 市现率
                        basic_info['close'] = valuation_data.get('close')  # 最新价格

                        # 3. 计算总市值（需要获取总股本）
                        close_price = valuation_data.get('close')
                        if close_price and close_price > 0:
                            # 尝试从财务数据获取总股本
                            total_shares_wan = await self._get_total_shares(code)
                            if total_shares_wan and total_shares_wan > 0:
                                # 总市值（亿元）= 股价（元）× 总股本（万股）/ 10000
                                total_mv_yi = (close_price * total_shares_wan) / 10000
                                basic_info['total_mv'] = total_mv_yi
                                logger.debug(f"✅ {code} 总市值计算: {close_price}元 × {total_shares_wan}万股 / 10000 = {total_mv_yi:.2f}亿元")
                            else:
                                logger.debug(f"⚠️ {code} 无法获取总股本，跳过市值计算")

                        logger.debug(f"✅ {code} 估值数据: PE={basic_info.get('pe')}, PB={basic_info.get('pb')}, 市值={basic_info.get('total_mv')}")
                except Exception as e:
                    logger.warning(f"⚠️ 获取{code}估值数据失败: {e}")
                    # 估值数据获取失败不影响基础信息同步

                # 4. 更新数据库
                await self._update_stock_basic_info(basic_info)
                stats.basic_info_count += 1

            except Exception as e:
                stats.errors.append(f"处理{stock.get('code', 'unknown')}失败: {e}")

        return stats
    
    async def _get_total_shares(self, code: str) -> Optional[float]:
        """
        获取股票总股本（万股）

        Args:
            code: 股票代码

        Returns:
            总股本（万股），如果获取失败返回 None
        """
        try:
            # 尝试从财务数据获取总股本
            financial_data = await self.provider.get_financial_data(code)

            if financial_data:
                # BaoStock 财务数据中的总股本字段
                # 盈利能力数据中有 totalShare（总股本，单位：万股）
                profit_data = financial_data.get('profit_data', {})
                if profit_data:
                    total_shares = profit_data.get('totalShare')
                    if total_shares:
                        return self._safe_float(total_shares)

                # 成长能力数据中也可能有总股本
                growth_data = financial_data.get('growth_data', {})
                if growth_data:
                    total_shares = growth_data.get('totalShare')
                    if total_shares:
                        return self._safe_float(total_shares)

            # 如果财务数据中没有，尝试从数据库中已有的数据获取
            collection = self.db.stock_financial_data
            doc = await collection.find_one(
                {"code": code},
                {"total_shares": 1, "totalShare": 1},
                sort=[("report_period", -1)]
            )

            if doc:
                total_shares = doc.get('total_shares') or doc.get('totalShare')
                if total_shares:
                    return self._safe_float(total_shares)

            return None

        except Exception as e:
            logger.debug(f"获取{code}总股本失败: {e}")
            return None

    def _safe_float(self, value) -> Optional[float]:
        """安全转换为浮点数"""
        try:
            if value is None or value == '' or value == 'None':
                return None
            return float(value)
        except (ValueError, TypeError):
            return None

    async def _update_stock_basic_info(self, basic_info: Dict[str, Any]):
        """更新股票基础信息到数据库"""
        try:
            collection = self.db.stock_basic_info

            # 确保 symbol 字段存在（标准化字段）
            if "symbol" not in basic_info and "code" in basic_info:
                basic_info["symbol"] = basic_info["code"]

            # 🔥 确保 source 字段存在
            if "source" not in basic_info:
                basic_info["source"] = "baostock"

            # 🔥 使用 (code, source) 联合查询条件
            await collection.update_one(
                {"code": basic_info["code"], "source": "baostock"},
                {"$set": basic_info},
                upsert=True
            )

        except Exception as e:
            logger.error(f"❌ 更新基础信息到数据库失败: {e}")
            raise
    
    async def sync_daily_quotes(self, batch_size: int = 50) -> BaoStockSyncStats:
        """
        同步日K线数据（最新交易日）

        注意：BaoStock不支持实时行情，此方法获取最新交易日的日K线数据

        Args:
            batch_size: 批处理大小

        Returns:
            同步统计信息
        """
        stats = BaoStockSyncStats()

        try:
            logger.info("🔄 开始BaoStock日K线同步（最新交易日）...")
            logger.info("ℹ️ 注意：BaoStock不支持实时行情，此任务同步最新交易日的日K线数据")

            # 从数据库获取股票列表
            collection = self.db.stock_basic_info
            cursor = collection.find({"source": "baostock"}, {"code": 1})
            stock_codes = [doc["code"] async for doc in cursor]

            if not stock_codes:
                logger.warning("⚠️ 数据库中没有BaoStock股票数据")
                return stats

            logger.info(f"📈 开始同步{len(stock_codes)}只股票的日K线数据...")

            # 批量处理
            for i in range(0, len(stock_codes), batch_size):
                batch = stock_codes[i:i + batch_size]
                batch_stats = await self._sync_quotes_batch(batch)

                stats.quotes_count += batch_stats.quotes_count
                stats.errors.extend(batch_stats.errors)

                logger.info(f"📊 批次进度: {i + len(batch)}/{len(stock_codes)}, "
                          f"成功: {batch_stats.quotes_count}, "
                          f"错误: {len(batch_stats.errors)}")

                # 避免API限制
                await asyncio.sleep(0.2)

            logger.info(f"✅ BaoStock日K线同步完成: {stats.quotes_count}条记录")
            
            # 🔥 更新任务状态为已完成
            job_id = getattr(self, '_current_job_id', None) or "baostock_daily_quotes_sync"
            if job_id:
                try:
                    from app.services.scheduler_service import mark_job_completed
                    # 转换 BaoStockSyncStats 为字典格式
                    stats_dict = {
                        "total_processed": len(stock_codes),
                        "success_count": stats.quotes_count,
                        "error_count": len(stats.errors),
                        "errors": [{"error": e} if isinstance(e, str) else e for e in stats.errors]
                    }
                    await mark_job_completed(job_id, stats_dict)
                except Exception as e:
                    logger.warning(f"⚠️ 更新任务完成状态失败: {e}")
            
            return stats

        except Exception as e:
            logger.error(f"❌ BaoStock日K线同步失败: {e}")
            stats.errors.append(str(e))
            
            # 🔥 更新任务状态为失败
            job_id = getattr(self, '_current_job_id', None) or "baostock_daily_quotes_sync"
            if job_id:
                try:
                    from app.services.scheduler_service import mark_job_completed
                    await mark_job_completed(job_id, None, str(e))
                except Exception as update_error:
                    logger.warning(f"⚠️ 更新任务失败状态时出错: {update_error}")
            
            return stats
    
    async def _sync_quotes_batch(self, code_batch: List[str]) -> BaoStockSyncStats:
        """同步日K线批次"""
        stats = BaoStockSyncStats()

        for code in code_batch:
            try:
                # 注意：get_stock_quotes 实际返回的是最新日K线数据，不是实时行情
                quotes = await self.provider.get_stock_quotes(code)

                if quotes:
                    # 更新数据库
                    await self._update_stock_quotes(quotes)
                    stats.quotes_count += 1
                else:
                    stats.errors.append(f"获取{code}日K线失败")

            except Exception as e:
                stats.errors.append(f"处理{code}日K线失败: {e}")

        return stats

    async def _update_stock_quotes(self, quotes: Dict[str, Any]):
        """更新股票日K线到数据库"""
        try:
            collection = self.db.market_quotes

            # 确保 symbol 字段存在
            code = quotes.get("code", "")
            if code and "symbol" not in quotes:
                quotes["symbol"] = code

            # 使用upsert更新或插入
            await collection.update_one(
                {"code": code},
                {"$set": quotes},
                upsert=True
            )

        except Exception as e:
            logger.error(f"❌ 更新日K线到数据库失败: {e}")
            raise
    
    async def sync_historical_data(self, days: int = 30, batch_size: int = 20, period: str = "daily", incremental: bool = True, symbols: List[str] = None) -> BaoStockSyncStats:
        """
        同步历史数据

        Args:
            days: 同步天数（如果>=3650则同步全历史，如果<0则使用增量模式）
            batch_size: 批处理大小
            period: 数据周期 (daily/weekly/monthly)
            incremental: 是否增量同步（每只股票从自己的最后日期开始）

        Returns:
            同步统计信息
        """
        stats = BaoStockSyncStats()

        try:
            # 🔥 在线程池的线程中执行时，需要重新初始化数据库连接
            # 因为数据库连接（Motor）绑定到事件循环，而线程池的线程有独立的事件循环
            # 通过检查是否有运行的事件循环来判断是否在线程池的线程中
            try:
                # 尝试获取当前运行的事件循环
                current_loop = asyncio.get_running_loop()
                # 如果成功获取到事件循环，检查数据库连接是否可用
                # 如果数据库连接不存在，重新创建
                if not hasattr(self, 'db') or self.db is None:
                    from motor.motor_asyncio import AsyncIOMotorClient
                    from app.core.config import settings
                    mongo_client = AsyncIOMotorClient(settings.MONGO_URI)
                    self.db = mongo_client[settings.MONGODB_DATABASE]
                    logger.debug("🔄 [BaoStock] 重新创建数据库连接（db为None）")
                else:
                    # 🔥 尝试使用数据库连接，如果失败则重新创建
                    # 通过尝试获取一个集合来测试连接是否可用
                    try:
                        # 这是一个轻量级的测试操作
                        _ = self.db.stock_basic_info
                    except Exception:
                        # 如果测试失败，重新创建数据库连接
                        from motor.motor_asyncio import AsyncIOMotorClient
                        from app.core.config import settings
                        mongo_client = AsyncIOMotorClient(settings.MONGO_URI)
                        self.db = mongo_client[settings.MONGODB_DATABASE]
                        logger.debug("🔄 [BaoStock] 数据库连接测试失败，重新创建")
            except RuntimeError:
                # 没有运行的事件循环，在线程池的线程中，需要创建新的数据库连接
                from motor.motor_asyncio import AsyncIOMotorClient
                from app.core.config import settings
                mongo_client = AsyncIOMotorClient(settings.MONGO_URI)
                self.db = mongo_client[settings.MONGODB_DATABASE]
                logger.debug("🔄 [BaoStock] 在线程池线程中创建新的数据库连接（无运行循环）")
            
            period_name = {"daily": "日线", "weekly": "周线", "monthly": "月线"}.get(period, "日线")

            # 计算日期范围
            end_date = datetime.now().strftime('%Y-%m-%d')

            # 确定同步模式
            use_incremental = incremental or days < 0

            # 🔥 增量同步时间检查：如果增量同步且结束日期是今天，且当前时间在18:00之前，则跳过同步
            if use_incremental and end_date == datetime.now().strftime('%Y-%m-%d'):
                current_time = datetime.now()
                cutoff_time = current_time.replace(hour=18, minute=0, second=0, microsecond=0)
                
                if current_time < cutoff_time:
                    skip_message = (
                        f"⏰ 增量同步跳过：当前时间 {current_time.strftime('%H:%M:%S')} 早于 18:00，"
                        f"数据源可能还没有当天的数据。建议在 18:00 之后执行增量同步。"
                    )
                    logger.info(skip_message)
                    stats.errors.append(skip_message)
                    return stats

            # 从数据库获取股票列表
            collection = self.db.stock_basic_info
            logger.info(f"🔍 [BaoStock] 查询数据库中的股票列表 (source=baostock)...")
            try:
                cursor = collection.find({"source": "baostock"}, {"code": 1})
                stock_codes = [doc["code"] async for doc in cursor]
                logger.info(f"📊 [BaoStock] 查询结果: 找到 {len(stock_codes)} 只股票")
            except RuntimeError as loop_error:
                # 🔥 如果发生事件循环冲突错误，重新创建数据库连接
                if "attached to a different loop" in str(loop_error) or "different loop" in str(loop_error):
                    logger.warning(f"⚠️ [BaoStock] 检测到事件循环冲突，重新创建数据库连接: {loop_error}")
                    from motor.motor_asyncio import AsyncIOMotorClient
                    from app.core.config import settings
                    mongo_client = AsyncIOMotorClient(settings.MONGO_URI)
                    self.db = mongo_client[settings.MONGODB_DATABASE]
                    # 重试查询
                    collection = self.db.stock_basic_info
                    cursor = collection.find({"source": "baostock"}, {"code": 1})
                    stock_codes = [doc["code"] async for doc in cursor]
                    logger.info(f"📊 [BaoStock] 查询结果: 找到 {len(stock_codes)} 只股票（已重新创建连接）")
                else:
                    raise

            if not stock_codes:
                error_msg = "数据库中没有BaoStock股票数据，请先执行 BaoStock 基础信息同步任务"
                logger.error(f"❌ {error_msg} (source=baostock)")
                
                # 🔥 标记任务为失败
                job_id = getattr(self, '_current_job_id', None) or "baostock_historical_sync"
                if job_id:
                    try:
                        from app.services.scheduler_service import mark_job_completed
                        await mark_job_completed(
                            job_id=job_id,
                            error_message=error_msg
                        )
                    except Exception as e:
                        logger.warning(f"⚠️ 更新任务失败状态失败: {e}")
                
                # 🔥 抛出异常，确保任务被标记为失败
                raise ValueError(error_msg)

            if use_incremental:
                logger.info(f"🔄 开始BaoStock{period_name}历史数据同步 (增量模式: 各股票从最后日期到{end_date})...")
            elif days >= 3650:
                logger.info(f"🔄 开始BaoStock{period_name}历史数据同步 (全历史: 1990-01-01到{end_date})...")
            else:
                logger.info(f"🔄 开始BaoStock{period_name}历史数据同步 (最近{days}天到{end_date})...")

            logger.info(f"📊 开始同步{len(stock_codes)}只股票的历史数据...")

            # 批量处理
            job_id = getattr(self, '_current_job_id', None) or "baostock_historical_sync"
            total_batches = (len(stock_codes) + batch_size - 1) // batch_size
            processed_count = 0  # 🔥 已处理数量（每个股票处理完立即加1）
            
            was_cancelled = False  # 🔥 标记是否因取消而停止
            
            for i in range(0, len(stock_codes), batch_size):
                # 🔥 检查任务是否应该停止
                if job_id and await self._should_stop(job_id):
                    logger.warning(f"⚠️ 任务 {job_id} 收到停止信号，正在退出...")
                    stats.stopped = True
                    was_cancelled = True
                    break

                batch = stock_codes[i:i + batch_size]
                batch_num = i // batch_size + 1
                logger.info(f"🔄 [BaoStock] 处理批次 {batch_num}/{total_batches}: {len(batch)} 只股票")
                
                # 🔥 传递 processed_count 和 total_stocks，让批次处理函数可以实时更新进度
                batch_stats_dict = await self._sync_historical_batch(
                    batch, days, end_date, period, use_incremental, job_id,
                    processed_count=processed_count,  # 🔥 传递当前已处理数量
                    total_stocks=len(stock_codes)  # 🔥 传递总数量
                )
                
                # 🔥 更新统计信息
                batch_records = batch_stats_dict.get("historical_records", 0)
                batch_errors = batch_stats_dict.get("errors", [])
                stats.historical_records += batch_records
                stats.errors.extend(batch_errors)
                
                # 🔥 更新已处理数量（批次处理函数会返回实际处理的股票数量）
                processed_count = batch_stats_dict.get("processed_count", processed_count + len(batch))
                
                # 🔥 检查是否被停止
                if batch_stats_dict.get("stopped", False):
                    stats.stopped = True
                    break
                
                logger.info(f"📊 [BaoStock] 批次进度: {processed_count}/{len(stock_codes)}, "
                          f"记录: {batch_records}, "
                          f"错误: {len(batch_errors)}")
                
                # 避免API限制
                await asyncio.sleep(0.5)
            
            # 🔥 如果任务被取消，更新状态为取消
            if was_cancelled:
                logger.warning(f"🛑 任务 {job_id} 已被取消，更新状态...")
                try:
                    from app.services.scheduler_service import update_job_progress
                    from app.core.database import get_mongo_db_sync, get_redis_sync_client
                    from app.core.redis_client import RedisKeys
                    
                    # 更新MongoDB状态
                    db = get_mongo_db_sync()
                    # 🔥 先查找最新的running记录，然后使用_id更新
                    from pymongo import DESCENDING
                    latest_execution = db.scheduler_executions.find_one(
                        {"job_id": job_id, "status": "running"},
                        sort=[("timestamp", DESCENDING)]
                    )
                    if latest_execution:
                        db.scheduler_executions.update_one(
                            {"_id": latest_execution["_id"]},
                            {
                                "$set": {
                                    "status": "cancelled",
                                    "updated_at": datetime.utcnow(),
                                    "message": f"任务已取消（已处理 {processed_count}/{len(stock_codes)}）",
                                    "progress": int((processed_count / len(stock_codes)) * 100) if len(stock_codes) > 0 else 0,
                                    "processed_items": processed_count,
                                    "total_items": len(stock_codes)
                                }
                            }
                        )
                    else:
                        # 如果没有找到running记录，尝试查找并更新任何状态的记录
                        any_execution = db.scheduler_executions.find_one(
                            {"job_id": job_id},
                            sort=[("timestamp", DESCENDING)]
                        )
                        if any_execution:
                            db.scheduler_executions.update_one(
                                {"_id": any_execution["_id"]},
                                {
                                    "$set": {
                                        "status": "cancelled",
                                        "updated_at": datetime.utcnow(),
                                        "message": f"任务已取消（已处理 {processed_count}/{len(stock_codes)}）",
                                        "progress": int((processed_count / len(stock_codes)) * 100) if len(stock_codes) > 0 else 0,
                                        "processed_items": processed_count,
                                        "total_items": len(stock_codes)
                                    }
                                }
                            )
                    
                    # 🔥 更新Redis进度缓存，将状态设置为"cancelled"，保留当前进度信息
                    redis_client = get_redis_sync_client()
                    if redis_client:
                        redis_key = RedisKeys.SCHEDULER_JOB_PROGRESS.format(job_id=job_id)
                        import json
                        
                        # 🔥 读取当前的进度数据（如果存在）
                        existing_progress_str = redis_client.get(redis_key)
                        if existing_progress_str:
                            try:
                                progress_data = json.loads(existing_progress_str)
                            except:
                                progress_data = {}
                        else:
                            progress_data = {}
                        
                        # 🔥 更新状态为"cancelled"，并保留当前进度信息
                        progress_percent = int((processed_count / len(stock_codes)) * 100) if len(stock_codes) > 0 else 0
                        progress_data.update({
                            "status": "cancelled",
                            "progress": progress_percent,
                            "message": f"任务已取消（已处理 {processed_count}/{len(stock_codes)}）",
                            "processed_items": processed_count,
                            "total_items": len(stock_codes),
                            "updated_at": datetime.utcnow().isoformat()
                        })
                        
                        # 🔥 保存到Redis
                        redis_client.setex(
                            redis_key,
                            3600,  # 1小时TTL
                            json.dumps(progress_data, ensure_ascii=False, default=str)
                        )
                        logger.info(f"✅ 已更新Redis缓存，任务状态为cancelled: job_id={job_id}, progress={progress_percent}%")
                    
                    logger.info(f"✅ 任务 {job_id} 状态已更新为取消")
                except Exception as cancel_error:
                    logger.error(f"❌ 更新任务取消状态失败: {cancel_error}")
                
                return stats
            
            logger.info(f"✅ BaoStock历史数据同步完成: {stats.historical_records}条记录")
            
            # 🔥 更新任务状态为已完成
            job_id = getattr(self, '_current_job_id', None) or "baostock_historical_sync"
            if job_id:
                try:
                    from app.services.scheduler_service import mark_job_completed
                    # 转换 BaoStockSyncStats 为字典格式
                    stats_dict = {
                        "total_processed": len(stats.errors) + stats.historical_records,  # 估算总数
                        "success_count": stats.historical_records,
                        "error_count": len(stats.errors),
                        "errors": [{"error": e} if isinstance(e, str) else e for e in stats.errors]
                    }
                    await mark_job_completed(job_id, stats_dict)
                except Exception as e:
                    logger.warning(f"⚠️ 更新任务完成状态失败: {e}")
            
            return stats
            
        except Exception as e:
            # 🔥 检查是否是任务取消异常
            from app.services.scheduler_service import TaskCancelledException
            if isinstance(e, TaskCancelledException) or "取消" in str(e) or "cancelled" in str(e).lower():
                logger.warning(f"🛑 BaoStock历史数据同步任务已被取消: {e}")
                stats.stopped = True
                
                # 更新状态为取消
                job_id = getattr(self, '_current_job_id', None) or "baostock_historical_sync"
                if job_id:
                    try:
                        from app.core.database import get_mongo_db_sync, get_redis_sync_client
                        from app.core.redis_client import RedisKeys
                        
                        # 更新MongoDB状态
                        db = get_mongo_db_sync()
                        # 🔥 获取当前进度信息（如果存在）
                        from pymongo import DESCENDING
                        current_execution = db.scheduler_executions.find_one(
                            {"job_id": job_id, "status": "running"},
                            sort=[("timestamp", DESCENDING)]
                        )
                        processed_count = current_execution.get("processed_items", 0) if current_execution else 0
                        total_items = current_execution.get("total_items", 0) if current_execution else 0
                        
                        # 🔥 使用找到的记录_id来更新
                        if current_execution:
                            db.scheduler_executions.update_one(
                                {"_id": current_execution["_id"]},
                                {
                                    "$set": {
                                        "status": "cancelled",
                                        "updated_at": datetime.utcnow(),
                                        "message": f"任务已取消: {str(e)}",
                                        "progress": int((processed_count / total_items) * 100) if total_items > 0 else 0,
                                        "processed_items": processed_count,
                                        "total_items": total_items
                                    }
                                }
                            )
                        else:
                            # 如果没有找到running记录，尝试查找并更新任何状态的记录
                            any_execution = db.scheduler_executions.find_one(
                                {"job_id": job_id},
                                sort=[("timestamp", DESCENDING)]
                            )
                            if any_execution:
                                db.scheduler_executions.update_one(
                                    {"_id": any_execution["_id"]},
                                    {
                                        "$set": {
                                            "status": "cancelled",
                                            "updated_at": datetime.utcnow(),
                                            "message": f"任务已取消: {str(e)}",
                                            "progress": int((processed_count / total_items) * 100) if total_items > 0 else 0,
                                            "processed_items": processed_count,
                                            "total_items": total_items
                                        }
                                    }
                                )
                        
                        # 🔥 更新Redis进度缓存
                        redis_client = get_redis_sync_client()
                        if redis_client:
                            redis_key = RedisKeys.SCHEDULER_JOB_PROGRESS.format(job_id=job_id)
                            import json
                            
                            progress_percent = int((processed_count / total_items) * 100) if total_items > 0 else 0
                            progress_data = {
                                "status": "cancelled",
                                "progress": progress_percent,
                                "message": f"任务已取消: {str(e)}",
                                "processed_items": processed_count,
                                "total_items": total_items,
                                "updated_at": datetime.utcnow().isoformat()
                            }
                            
                            redis_client.setex(
                                redis_key,
                                3600,  # 1小时TTL
                                json.dumps(progress_data, ensure_ascii=False, default=str)
                            )
                            logger.info(f"✅ 已更新Redis缓存，任务状态为cancelled: job_id={job_id}, progress={progress_percent}%")
                        
                        logger.info(f"✅ 任务 {job_id} 状态已更新为取消")
                    except Exception as cancel_error:
                        logger.error(f"❌ 更新任务取消状态失败: {cancel_error}")
                
                return stats
            
            # 其他异常才记录为错误
            logger.error(f"❌ BaoStock历史数据同步失败: {e}")
            stats.errors.append(str(e))
            
            # 🔥 更新任务状态为失败
            job_id = getattr(self, '_current_job_id', None) or "baostock_historical_sync"
            if job_id:
                try:
                    from app.services.scheduler_service import mark_job_completed
                    await mark_job_completed(job_id, None, str(e))
                except Exception as update_error:
                    logger.warning(f"⚠️ 更新任务失败状态时出错: {update_error}")
            
            return stats
    
    async def _sync_historical_batch(
        self,
        code_batch: List[str],
        days: int,
        end_date: str,
        period: str = "daily",
        incremental: bool = False,
        job_id: str = None,
        processed_count: int = 0,  # 🔥 当前已处理数量
        total_stocks: int = 0  # 🔥 总股票数量
    ) -> Dict[str, Any]:
        """同步历史数据批次"""
        stats = BaoStockSyncStats()
        stats_dict = {
            "historical_records": 0,
            "errors": [],
            "processed_count": processed_count  # 🔥 保存当前已处理数量
        }

        for idx, code in enumerate(code_batch):
            # 🔥 检查任务是否应该停止
            if job_id and await self._should_stop(job_id):
                logger.warning(f"⚠️ 任务 {job_id} 收到停止信号，正在退出批次处理...")
                stats.stopped = True
                stats_dict["stopped"] = True
                break
            
            # 🔥 每处理一个股票，立即更新已处理数量（无论成功还是失败）
            processed_count += 1
            stats_dict["processed_count"] = processed_count
            
            try:
                # 确定该股票的起始日期
                if incremental:
                    # 增量同步：获取该股票的最后日期
                    start_date = await self._get_last_sync_date(code)
                    logger.debug(f"📅 {code}: 从 {start_date} 开始同步")
                elif days >= 3650:
                    # 全历史同步
                    start_date = "1990-01-01"
                else:
                    # 固定天数同步
                    start_date = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d')

                logger.debug(f"🔄 [BaoStock] 获取 {code} 历史数据: {start_date} 到 {end_date}")
                hist_data = await self.provider.get_historical_data(code, start_date, end_date, period)

                if hist_data is not None and not hist_data.empty:
                    logger.info(f"✅ [BaoStock] {code} 获取到 {len(hist_data)} 条历史数据，开始保存...")
                    # 更新数据库
                    records_count = await self._update_historical_data(code, hist_data, period)
                    stats.historical_records += records_count
                    stats_dict["historical_records"] = stats.historical_records
                    logger.info(f"✅ [BaoStock] {code} 保存成功: {records_count} 条记录")
                else:
                    logger.warning(f"⚠️ [BaoStock] {code} 未获取到历史数据")
                    error_msg = f"获取{code}历史数据失败"
                    stats.errors.append(error_msg)
                    stats_dict["errors"].append(error_msg)

            except Exception as e:
                logger.error(f"❌ [BaoStock] {code} 历史数据同步失败: {e}", exc_info=True)
                error_msg = f"处理{code}历史数据失败: {e}"
                stats.errors.append(error_msg)
                stats_dict["errors"].append(error_msg)
            
            # 🔥 每处理完一个股票（无论成功还是失败），立即更新进度
            if job_id and total_stocks > 0:
                try:
                    from app.services.scheduler_service import update_job_progress, TaskCancelledException
                    
                    # 🔥 计算进度百分比
                    progress_percent = int((processed_count / total_stocks) * 100) if total_stocks > 0 else 0
                    
                    # 🔥 构建进度消息
                    progress_message = f"正在同步 BaoStock 历史数据 ({processed_count}/{total_stocks})"
                    
                    # 🔥 如果有错误，在消息中包含错误信息
                    if len(stats_dict.get("errors", [])) > 0:
                        recent_errors = stats_dict.get("errors", [])[-3:]  # 只取最近3个错误
                        if recent_errors:
                            error_summary = []
                            for error in recent_errors:
                                error_str = error if isinstance(error, str) else str(error)
                                if error_str:
                                    # 提取关键错误信息
                                    if "历史数据为空" in error_str or "未获取到" in error_str:
                                        error_summary.append("数据为空")
                                    elif "网络" in error_str or "连接" in error_str:
                                        error_summary.append("网络问题")
                                    else:
                                        # 截取前30个字符
                                        short_error = error_str[:30] + "..." if len(error_str) > 30 else error_str
                                        error_summary.append(short_error)
                            
                            if error_summary:
                                # 去重并只显示前2个不同的错误类型
                                unique_errors = list(set(error_summary))[:2]
                                progress_message += f" | 遇到错误: {', '.join(unique_errors)}"
                    
                    await update_job_progress(
                        job_id=job_id,
                        progress=progress_percent,
                        message=progress_message,
                        total_items=total_stocks,
                        processed_items=processed_count
                    )
                except TaskCancelledException:
                    logger.warning(f"⚠️ BaoStock历史数据同步任务被用户取消 (已处理 {processed_count}/{total_stocks})")
                    stats.stopped = True
                    stats_dict["stopped"] = True
                    break
                except Exception as progress_error:
                    # 🔥 进度更新失败不应该影响任务执行
                    logger.debug(f"⚠️ 更新进度失败（继续执行）: {progress_error}")

        # 🔥 返回字典格式，包含 processed_count
        stats_dict.update({
            "historical_records": stats.historical_records,
            "errors": stats.errors,
            "stopped": getattr(stats, 'stopped', False)
        })
        return stats_dict

    async def _should_stop(self, job_id: str) -> bool:
        """
        检查任务是否应该停止

        Args:
            job_id: 任务ID

        Returns:
            是否应该停止
        """
        try:
            # 🔥 查询执行记录，检查 cancel_requested 标记和任务状态
            # 不仅检查 running 状态，也检查 failed/cancelled/suspended 状态
            execution = await self.db.scheduler_executions.find_one(
                {"job_id": job_id},
                sort=[("timestamp", -1)]
            )

            if not execution:
                return False

            # 检查取消请求标记
            if execution.get("cancel_requested"):
                logger.info(f"🛑 任务 {job_id} 收到取消请求，应停止执行")
                return True

            # 🔥 检查任务状态：如果任务已被标记为失败、取消或挂起，也应该停止
            status = execution.get("status")
            if status in ["failed", "cancelled", "suspended"]:
                logger.info(f"🛑 任务 {job_id} 状态为 {status}，应停止执行")
                return True

            return False

        except Exception as e:
            logger.error(f"❌ 检查任务停止标记失败: {e}")
            return False

    async def _update_historical_data(self, code: str, hist_data, period: str = "daily") -> int:
        """更新历史数据到数据库"""
        try:
            if hist_data is None or hist_data.empty:
                logger.warning(f"⚠️ {code} 历史数据为空，跳过保存")
                return 0

            # 🔥 确保 historical_service 已初始化（如果为 None，使用当前 db 连接创建）
            if self.historical_service is None:
                from app.services.historical_data_service import get_historical_data_service
                self.historical_service = await get_historical_data_service()
            
            # 🔥 确保 historical_service 使用正确的数据库连接（在线程池中执行时很重要）
            if self.db is not None:
                self.historical_service.db = self.db
                self.historical_service.collection = self.db.stock_daily_quotes

            # 保存到统一历史数据集合
            logger.info(f"💾 [BaoStock] 保存 {code} 历史数据到数据库 ({len(hist_data)} 条记录)...")
            saved_count = await self.historical_service.save_historical_data(
                symbol=code,
                data=hist_data,
                data_source="baostock",
                market="CN",
                period=period
            )
            logger.info(f"✅ [BaoStock] {code} 数据保存完成: {saved_count} 条记录")

            # 同时更新market_quotes集合的元信息（保持兼容性）
            if self.db is not None:
                collection = self.db.market_quotes
                latest_record = hist_data.iloc[-1] if not hist_data.empty else None

                await collection.update_one(
                    {"code": code},
                    {"$set": {
                        "historical_data_updated": datetime.now(),
                        "latest_historical_date": latest_record.get('date') if latest_record is not None else None,
                        "historical_records_count": saved_count
                    }},
                    upsert=True
                )

            return saved_count

        except Exception as e:
            logger.error(f"❌ 更新历史数据到数据库失败: {e}")
            return 0
    
    async def _get_last_sync_date(self, symbol: str = None) -> str:
        """
        获取最后同步日期

        Args:
            symbol: 股票代码，如果提供则返回该股票的最后日期+1天

        Returns:
            日期字符串 (YYYY-MM-DD)
        """
        try:
            # 🔥 确保 historical_service 已初始化（如果为 None，使用当前 db 连接创建）
            if self.historical_service is None:
                from app.services.historical_data_service import get_historical_data_service
                self.historical_service = await get_historical_data_service()
            
            # 🔥 确保 historical_service 使用正确的数据库连接（在线程池中执行时很重要）
            if self.db is not None:
                self.historical_service.db = self.db
                self.historical_service.collection = self.db.stock_daily_quotes

            if symbol:
                # 获取特定股票的最新日期
                latest_date = await self.historical_service.get_latest_date(symbol, "baostock")
                if latest_date:
                    # 返回最后日期的下一天（避免重复同步）
                    try:
                        last_date_obj = datetime.strptime(latest_date, '%Y-%m-%d')
                        next_date = last_date_obj + timedelta(days=1)
                        next_date_str = next_date.strftime('%Y-%m-%d')
                        
                        # 🔥 检查：如果 next_date 大于今天，说明数据已经是最新的，不需要同步
                        # 返回今天的日期（这样 start_date == end_date，BaoStock会返回空数据但不会报错）
                        today_str = datetime.now().strftime('%Y-%m-%d')
                        if next_date_str > today_str:
                            logger.debug(f"📅 {symbol}: 最后日期 {latest_date} 的下一天 {next_date_str} 大于今天 {today_str}，数据已是最新，返回今天日期")
                            return today_str
                        
                        return next_date_str
                    except ValueError:
                        # 如果日期格式不对，直接返回
                        return latest_date
                else:
                    # 🔥 没有历史数据时，从上市日期开始全量同步（而不是只同步30天）
                    if self.db is not None:
                        stock_info = await self.db.stock_basic_info.find_one(
                            {"code": symbol, "source": "baostock"},
                            {"list_date": 1}
                        )
                        if stock_info and stock_info.get("list_date"):
                            list_date = stock_info["list_date"]
                            # 处理不同的日期格式
                            if isinstance(list_date, str):
                                # 尝试解析日期字符串
                                try:
                                    # 尝试 YYYY-MM-DD 格式
                                    if len(list_date) >= 10:
                                        parsed_date = datetime.strptime(list_date[:10], '%Y-%m-%d')
                                        return parsed_date.strftime('%Y-%m-%d')
                                    # 尝试 YYYYMMDD 格式
                                    elif len(list_date) == 8:
                                        parsed_date = datetime.strptime(list_date, '%Y%m%d')
                                        return parsed_date.strftime('%Y-%m-%d')
                                except ValueError:
                                    pass
                            elif isinstance(list_date, datetime):
                                return list_date.strftime('%Y-%m-%d')
                    
                    # 🔥 如果无法获取上市日期，返回1990-01-01（全历史同步）
                    logger.info(f"📅 {symbol}: 未找到历史数据和上市日期，从1990-01-01开始全量同步")
                    return "1990-01-01"

            # 默认返回1990-01-01（全历史同步，而不是30天前）
            return "1990-01-01"

        except Exception as e:
            logger.error(f"❌ 获取最后同步日期失败 {symbol}: {e}")
            # 🔥 出错时返回1990-01-01（全历史同步），确保不漏数据
            return "1990-01-01"

    async def check_service_status(self) -> Dict[str, Any]:
        """检查服务状态"""
        try:
            # 测试BaoStock连接
            connection_ok = await self.provider.test_connection()
            
            # 检查数据库连接
            db_ok = True
            try:
                await self.db.stock_basic_info.count_documents({})
            except Exception:
                db_ok = False
            
            # 统计数据
            basic_info_count = await self.db.stock_basic_info.count_documents({"source": "baostock"})
            quotes_count = await self.db.market_quotes.count_documents({"source": "baostock"})
            
            return {
                "service": "BaoStock同步服务",
                "baostock_connection": connection_ok,
                "database_connection": db_ok,
                "basic_info_count": basic_info_count,
                "quotes_count": quotes_count,
                "status": "healthy" if connection_ok and db_ok else "unhealthy",
                "last_check": datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"❌ BaoStock服务状态检查失败: {e}")
            return {
                "service": "BaoStock同步服务",
                "status": "error",
                "error": str(e),
                "last_check": datetime.now().isoformat()
            }


# APScheduler兼容的任务函数
async def _check_task_running(job_id: str) -> Tuple[bool, Optional[str]]:
    """
    检查任务是否已有实例在运行
    
    Args:
        job_id: 任务ID
        
    Returns:
        (is_running, running_instance_id): 是否在运行，运行实例的ID
    """
    try:
        from pymongo import MongoClient
        from app.core.config import settings
        from datetime import timedelta
        from app.services.scheduler_service import get_utc8_now
        
        sync_client = MongoClient(settings.MONGO_URI)
        sync_db = sync_client[settings.MONGODB_DATABASE]
        
        # 🔥 查找是否有正在运行的实例（排除超时的任务）
        # 如果任务运行超过30分钟，认为是僵尸任务，不阻止新任务执行
        threshold_time = get_utc8_now() - timedelta(minutes=30)
        
        running_instance = sync_db.scheduler_executions.find_one(
            {
                "job_id": job_id, 
                "status": "running",
                "timestamp": {"$gte": threshold_time}  # 只考虑最近30分钟内的running任务
            },
            sort=[("timestamp", -1)]
        )
        
        # 🔥 如果找到超时的running任务，自动标记为失败
        if not running_instance:
            # 检查是否有超时的running任务
            zombie_instance = sync_db.scheduler_executions.find_one(
                {
                    "job_id": job_id,
                    "status": "running",
                    "timestamp": {"$lt": threshold_time}
                },
                sort=[("timestamp", -1)]
            )
            
            if zombie_instance:
                # 自动标记为失败
                sync_db.scheduler_executions.update_one(
                    {"_id": zombie_instance["_id"]},
                    {
                        "$set": {
                            "status": "failed",
                            "error_message": "任务执行超时或进程异常终止（自动检测）",
                            "updated_at": get_utc8_now()
                        }
                    }
                )
                logger.warning(f"⚠️ 检测到超时任务并自动标记为失败: {job_id} (开始时间: {zombie_instance.get('timestamp')})")
        
        sync_client.close()
        
        if running_instance:
            return True, str(running_instance["_id"])
        return False, None
    except Exception as e:
        logger.warning(f"⚠️ 检查任务运行状态失败: {e}")
        return False, None


async def run_baostock_basic_info_sync(**kwargs):
    """运行BaoStock基础信息同步任务"""
    job_id = "baostock_basic_info_sync"
    
    # 🔥 手动触发或强制执行时允许执行（即使有running记录）
    manual_trigger = kwargs.get("_manual_trigger", False)
    force_execute = kwargs.get("_force_execute", False)
    if not manual_trigger and not force_execute:
        # 🔥 检查是否已有实例在运行（非手动触发且非强制执行时才检查）
        is_running, instance_id = await _check_task_running(job_id)
        if is_running:
            logger.warning(f"⚠️ 任务 {job_id} 已有实例在运行（_id={instance_id}），跳过本次执行")
            return {
                "skipped": True,
                "reason": "已有实例在运行",
                "running_instance_id": instance_id
            }
    else:
        if manual_trigger:
            logger.info(f"🔧 [APScheduler] 手动触发执行，允许执行（即使有running记录）")
        if force_execute:
            logger.info(f"🔧 [APScheduler] 强制执行，跳过并发检查")
    
    try:
        service = BaoStockSyncService()
        await service.initialize()  # 🔥 必须先初始化
        # 🔥 设置正确的 job_id，确保进度更新和状态标记使用正确的任务ID
        service._current_job_id = job_id
        stats = await service.sync_stock_basic_info()
        logger.info(f"🎯 BaoStock基础信息同步完成: {stats.basic_info_count}条记录, {len(stats.errors)}个错误")
    except Exception as e:
        logger.error(f"❌ BaoStock基础信息同步任务失败: {e}")


async def run_baostock_daily_quotes_sync(**kwargs):
    """运行BaoStock日K线同步任务（最新交易日）"""
    job_id = "baostock_daily_quotes_sync"
    
    # 🔥 手动触发或强制执行时允许执行（即使有running记录）
    manual_trigger = kwargs.get("_manual_trigger", False)
    force_execute = kwargs.get("_force_execute", False)
    if not manual_trigger and not force_execute:
        # 🔥 检查是否已有实例在运行（非手动触发且非强制执行时才检查）
        is_running, instance_id = await _check_task_running(job_id)
        if is_running:
            logger.warning(f"⚠️ 任务 {job_id} 已有实例在运行（_id={instance_id}），跳过本次执行")
            return {
                "skipped": True,
                "reason": "已有实例在运行",
                "running_instance_id": instance_id
            }
    else:
        if manual_trigger:
            logger.info(f"🔧 [APScheduler] 手动触发执行，允许执行（即使有running记录）")
        if force_execute:
            logger.info(f"🔧 [APScheduler] 强制执行，跳过并发检查")
    
    try:
        service = BaoStockSyncService()
        await service.initialize()  # 🔥 必须先初始化
        # 🔥 设置正确的 job_id，确保进度更新和状态标记使用正确的任务ID
        service._current_job_id = job_id
        stats = await service.sync_daily_quotes()
        logger.info(f"🎯 BaoStock日K线同步完成: {stats.quotes_count}条记录, {len(stats.errors)}个错误")
    except Exception as e:
        logger.error(f"❌ BaoStock日K线同步任务失败: {e}")


async def run_baostock_historical_sync(**kwargs):
    """运行BaoStock历史数据同步任务"""
    job_id = "baostock_historical_sync"
    
    logger.info(f"🚀 [BaoStock] 开始执行历史数据同步任务 (job_id={job_id}, kwargs={kwargs})")
    
    # 🔥 手动触发或强制执行时允许执行（即使有running记录）
    manual_trigger = kwargs.get("_manual_trigger", False)
    force_execute = kwargs.get("_force_execute", False)
    
    logger.info(f"🔍 [BaoStock] 检查任务状态: manual_trigger={manual_trigger}, force_execute={force_execute}")
    
    if not manual_trigger and not force_execute:
        # 🔥 检查是否已有实例在运行（非手动触发且非强制执行时才检查）
        is_running, instance_id = await _check_task_running(job_id)
        logger.info(f"🔍 [BaoStock] 任务运行状态检查: is_running={is_running}, instance_id={instance_id}")
        if is_running:
            logger.warning(f"⚠️ 任务 {job_id} 已有实例在运行（_id={instance_id}），跳过本次执行")
            return {
                "skipped": True,
                "reason": "已有实例在运行",
                "running_instance_id": instance_id
            }
    else:
        if manual_trigger:
            logger.info(f"🔧 [APScheduler] BaoStock手动触发执行，允许执行（即使有running记录）")
        if force_execute:
            logger.info(f"🔧 [APScheduler] BaoStock强制执行，跳过并发检查")
    
    try:
        # 🔥 使用统一的线程池同步服务
        from app.worker.unified_thread_pool_sync_service import get_unified_thread_pool_sync_service
        
        unified_service = await get_unified_thread_pool_sync_service()
        
        # 🔥 获取BaoStock数据源服务实例
        logger.info(f"🔄 [BaoStock] 初始化同步服务...")
        service = BaoStockSyncService()
        await service.initialize()  # 🔥 必须先初始化
        logger.info(f"✅ [BaoStock] 同步服务初始化完成")
        
        # 🔥 设置正确的 job_id，确保进度更新和状态标记使用正确的任务ID
        service._current_job_id = job_id
        
        # 🔥 检查是否是恢复执行，从kwargs中读取恢复位置
        resume_from_index = kwargs.get("_resume_from_index")
        if resume_from_index is not None:
            logger.info(f"🔄 [恢复执行] 将从第 {resume_from_index} 个股票位置继续同步")
        
        # 🔥 在线程池中执行同步方法
        sync_result = await unified_service.execute_sync_method(
            sync_method=service.sync_historical_data,
            method_kwargs={
                "days": kwargs.get("days", 30),
                "batch_size": kwargs.get("batch_size", 20),
                "period": kwargs.get("period", "daily"),
                "incremental": kwargs.get("incremental", True),
                "symbols": kwargs.get("symbols")
            },
            job_id=job_id,
            rate_limit_per_minute=kwargs.get("rate_limit_per_minute", 200),  # BaoStock速率限制
            resume_from_index=resume_from_index
        )
        
        if sync_result.success:
            stats = sync_result.result
            logger.info(f"🎯 BaoStock历史数据同步完成: {stats.historical_records}条记录, {len(stats.errors)}个错误")
            return stats
        else:
            # 🔥 检查是否是任务取消
            if "取消" in sync_result.error or "cancelled" in sync_result.error.lower():
                logger.info(f"ℹ️ BaoStock历史数据同步任务已被用户取消")
                return {"cancelled": True, "message": sync_result.error}
            else:
                logger.error(f"❌ BaoStock历史数据同步失败: {sync_result.error}")
                raise RuntimeError(sync_result.error)
                
    except Exception as e:
        # 检查是否是任务取消异常（用户主动取消，不应该记录为错误）
        from app.services.scheduler_service import TaskCancelledException
        if isinstance(e, TaskCancelledException):
            logger.info(f"ℹ️ BaoStock历史数据同步任务已被用户取消")
            return {"cancelled": True, "message": "任务已被用户取消"}
        # 其他异常才记录为错误
        logger.error(f"❌ BaoStock历史数据同步任务失败: {e}", exc_info=True)
        raise  # 🔥 重新抛出异常，确保错误能被上层捕获


    async def retry_failed_symbols(
        self,
        errors: List[Dict[str, Any]],
        days: int = 30,
        period: str = "daily",
        job_id: str = None,
        _is_retry: bool = False
    ) -> Dict[str, Any]:
        """
        重试失败的股票（只重试可重试的错误，跳过无数据的错误）
        
        Args:
            errors: 错误列表（从之前的同步结果中获取）
            days: 同步天数（BaoStock使用days参数）
            period: 数据周期 (daily/weekly/monthly)
            job_id: 任务ID（用于进度跟踪）
            _is_retry: 内部标记，表示这是重试任务，避免再次自动重试
            
        Returns:
            重试结果统计
        """
        period_name = {"daily": "日线", "weekly": "周线", "monthly": "月线"}.get(period, period)
        
        # 🔥 BaoStock的错误格式可能是字符串或字典，需要统一处理
        retryable_errors = []
        no_data_errors = []
        
        for error in errors:
            # 处理字符串格式的错误
            if isinstance(error, str):
                # 字符串错误通常表示可重试的错误（网络错误等）
                retryable_errors.append({"error": error, "error_category": "retryable_error"})
            # 处理字典格式的错误
            elif isinstance(error, dict):
                if error.get("error_category") == "retryable_error" or error.get("is_retryable", False):
                    retryable_errors.append(error)
                else:
                    no_data_errors.append(error)
        
        logger.info(f"🔄 开始重试失败的股票...")
        logger.info(f"   可重试的错误: {len(retryable_errors)} 个")
        logger.info(f"   无数据的错误（跳过）: {len(no_data_errors)} 个")
        
        if not retryable_errors:
            logger.info("✅ 没有可重试的错误，所有失败都是无数据的情况")
            return {
                "total_retried": 0,
                "success_count": 0,
                "error_count": 0,
                "no_data_count": len(no_data_errors),
                "errors": []
            }
        
        # 提取可重试的股票代码（从错误信息中提取）
        retry_symbols = []
        for error in retryable_errors:
            if isinstance(error, dict) and error.get("code"):
                retry_symbols.append(error["code"])
            elif isinstance(error, str):
                # 从字符串错误中提取股票代码（格式：处理{code}历史数据失败）
                import re
                match = re.search(r'处理(\d{6})', error)
                if match:
                    retry_symbols.append(match.group(1))
        
        if not retry_symbols:
            logger.warning("⚠️ 无法从错误列表中提取股票代码")
            return {
                "total_retried": 0,
                "success_count": 0,
                "error_count": len(retryable_errors),
                "no_data_count": len(no_data_errors),
                "errors": retryable_errors
            }
        
        logger.info(f"📋 将重试以下 {len(retry_symbols)} 只股票: {', '.join(retry_symbols[:10])}{'...' if len(retry_symbols) > 10 else ''}")
        
        # 调用同步方法，只同步这些失败的股票
        retry_result_stats = await self.sync_historical_data(
            days=days,
            period=period,
            incremental=False,  # 重试时使用全量同步
            symbols=retry_symbols  # 🔥 只同步失败的股票
        )
        
        # 转换为统一格式
        retry_result = {
            "total_retried": len(retry_symbols),
            "success_count": retry_result_stats.historical_records,  # BaoStock使用historical_records表示成功数
            "error_count": len(retry_result_stats.errors),
            "total_records": retry_result_stats.historical_records,
            "no_data_count": len(no_data_errors),
            "retryable_errors_count": len(retryable_errors),
            "errors": retry_result_stats.errors
        }
        
        logger.info(f"✅ 重试完成: 成功 {retry_result['success_count']}/{retry_result['total_retried']}, "
                   f"失败 {retry_result['error_count']}, 无数据 {retry_result['no_data_count']}（已跳过）")
        
        return retry_result


# 全局同步服务实例
_baostock_sync_service = None

async def get_baostock_sync_service() -> BaoStockSyncService:
    """获取BaoStock同步服务实例"""
    global _baostock_sync_service
    if _baostock_sync_service is None:
        _baostock_sync_service = BaoStockSyncService()
        await _baostock_sync_service.initialize()
    return _baostock_sync_service


async def run_baostock_status_check():
    """运行BaoStock状态检查任务"""
    try:
        service = BaoStockSyncService()
        await service.initialize()  # 🔥 必须先初始化
        status = await service.check_service_status()
        logger.info(f"🔍 BaoStock服务状态: {status['status']}")
    except Exception as e:
        logger.error(f"❌ BaoStock状态检查任务失败: {e}")
