#!/usr/bin/env python3
"""
财务数据同步服务
统一管理三数据源的财务数据同步
"""
import asyncio
import logging
import time
import threading
import concurrent.futures
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field

from app.core.database import get_mongo_db
from app.services.financial_data_service import get_financial_data_service
from tradingagents.dataflows.providers.china.tushare import get_tushare_provider
from tradingagents.dataflows.providers.china.akshare import get_akshare_provider
from tradingagents.dataflows.providers.china.baostock import get_baostock_provider

logger = logging.getLogger(__name__)


@dataclass
class FinancialSyncStats:
    """财务数据同步统计"""
    total_symbols: int = 0
    success_count: int = 0
    error_count: int = 0
    skipped_count: int = 0
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    duration: float = 0.0
    errors: List[Dict[str, Any]] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "total_symbols": self.total_symbols,
            "success_count": self.success_count,
            "error_count": self.error_count,
            "skipped_count": self.skipped_count,
            "start_time": self.start_time.isoformat() if self.start_time else None,
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "duration": self.duration,
            "success_rate": round(self.success_count / max(self.total_symbols, 1) * 100, 2),
            "errors": self.errors[:10]  # 只返回前10个错误
        }


class FinancialDataSyncService:
    """财务数据同步服务"""
    
    def __init__(self):
        self.db = None
        self.financial_service = None
        self.providers = {}
        # 🔥 全局线程池：用于为每个任务分配一个线程
        self._thread_pool = concurrent.futures.ThreadPoolExecutor(max_workers=10)
        self._shutdown_event = threading.Event()  # 🔥 用于通知线程退出
        self._active_tasks = {}  # 🔥 跟踪活跃任务：{job_id: thread}
        
    async def initialize(self):
        """初始化服务"""
        try:
            self.db = get_mongo_db()
            self.financial_service = await get_financial_data_service()
            
            # 初始化数据源提供者
            self.providers = {
                "tushare": get_tushare_provider(),
                "akshare": get_akshare_provider(),
                "baostock": get_baostock_provider()
            }
            
            logger.info("✅ 财务数据同步服务初始化成功")
            
        except Exception as e:
            logger.error(f"❌ 财务数据同步服务初始化失败: {e}")
            raise
    
    async def sync_financial_data(
        self,
        symbols: List[str] = None,
        data_sources: List[str] = None,
        report_types: List[str] = None,
        batch_size: int = 50,
        delay_seconds: float = 1.0,
        job_id: str = None,
        rate_limit_per_minute: int = 80,  # 🔥 速率限制：每分钟最大调用次数
        _resume_from_index: int = None  # 🔥 恢复执行：从哪个位置继续（已处理的股票数量）
    ) -> Dict[str, FinancialSyncStats]:
        """
        同步财务数据（使用线程池）
        
        Args:
            symbols: 股票代码列表，None表示同步所有股票
            data_sources: 数据源列表 ["tushare", "akshare", "baostock"]
            report_types: 报告类型列表 ["quarterly", "annual"]
            batch_size: 批处理大小（已废弃，保留兼容性）
            delay_seconds: API调用延迟（已废弃，保留兼容性）
            job_id: 任务ID，用于进度跟踪
            
        Returns:
            各数据源的同步统计结果
        """
        if self.db is None:
            await self.initialize()
        
        # 默认参数
        if data_sources is None:
            data_sources = ["tushare", "akshare", "baostock"]
        if report_types is None:
            report_types = ["quarterly", "annual"]  # 同时同步季报和年报
        
        logger.info(f"🔄 开始财务数据同步（线程池模式）: 数据源={data_sources}, 报告类型={report_types}")
        
        # 获取股票列表
        if symbols is None:
            symbols = await self._get_stock_symbols()
        
        if not symbols:
            logger.warning("⚠️ 没有找到要同步的股票")
            return {}
        
        logger.info(f"📊 准备同步 {len(symbols)} 只股票的财务数据")
        
        # 为每个数据源执行同步
        results = {}
        
        # 🔥 使用线程池并行处理每个数据源
        # 不同数据源可以并行执行（因为它们使用不同的API，互不影响）
        tasks = []
        for data_source in data_sources:
            if data_source not in self.providers:
                logger.warning(f"⚠️ 不支持的数据源: {data_source}")
                continue
            
            # 🔥 创建并发任务：每个数据源任务在独立线程中运行，任务内部串行处理
            # 🔥 使用原始job_id，而不是修改后的job_id，这样进度更新会更新到正确的执行记录
            # 在任务内部，通过消息区分不同的数据源
            task = self._run_task_in_thread(
                data_source=data_source,
                symbols=symbols,
                report_types=report_types,
                job_id=job_id if job_id else f"financial_{data_source}",  # 🔥 使用原始job_id
                rate_limit_per_minute=rate_limit_per_minute,  # 🔥 传递速率限制参数
                resume_from_index=_resume_from_index  # 🔥 传递恢复位置参数
            )
            tasks.append((data_source, task))
        
        # 并行执行所有数据源的同步任务
        if tasks:
            logger.info(f"🚀 开始并行同步 {len(tasks)} 个数据源的财务数据: {[ds for ds, _ in tasks]}")
            
            # 使用 asyncio.gather 并行执行
            task_results = await asyncio.gather(
                *[task for _, task in tasks],
                return_exceptions=True
            )
            
            # 处理结果
            for i, ((data_source, _), result) in enumerate(zip(tasks, task_results)):
                if isinstance(result, Exception):
                    logger.error(f"❌ {data_source} 财务数据同步失败: {result}", exc_info=True)
                    # 创建失败的统计信息
                    failed_stats = FinancialSyncStats()
                    failed_stats.total_symbols = len(symbols) if symbols else 0
                    failed_stats.error_count = failed_stats.total_symbols
                    failed_stats.errors.append({
                        "error": str(result),
                        "data_source": data_source
                    })
                    results[data_source] = failed_stats
                else:
                    results[data_source] = result
                    logger.info(f"✅ {data_source} 财务数据同步完成: "
                               f"成功 {result.success_count}/{result.total_symbols} "
                               f"({result.success_count/max(result.total_symbols,1)*100:.1f}%)")
        else:
            logger.warning("⚠️ 没有可用的数据源进行财务数据同步")
        
        return results
    
    async def _run_task_in_thread(
        self,
        data_source: str,
        symbols: List[str],
        report_types: List[str],
        job_id: str,
        rate_limit_per_minute: int = 80,
        resume_from_index: int = None  # 🔥 恢复执行：从哪个位置继续
    ) -> FinancialSyncStats:
        """
        在线程池中运行任务：每个任务分配一个线程，任务内部串行处理
        
        Args:
            data_source: 数据源名称
            symbols: 股票代码列表
            report_types: 报告类型列表
            job_id: 任务ID，用于进度跟踪
            rate_limit_per_minute: 速率限制（每分钟最大调用次数）
        """
        loop = asyncio.get_event_loop()
        
        # 🔥 记录活跃任务
        task_future = loop.run_in_executor(
            self._thread_pool,
            self._sync_source_financial_data_serial_sync,
            data_source,
            symbols,
            report_types,
            job_id,
            rate_limit_per_minute,
            resume_from_index  # 🔥 传递恢复位置参数
        )
        
        # 🔥 将任务添加到活跃任务列表
        self._active_tasks[job_id] = task_future
        
        # 🔥 等待任务完成，并在完成后清理
        try:
            result = await task_future
            return result
        finally:
            # 任务完成后，从活跃任务列表中移除
            self._active_tasks.pop(job_id, None)
    
    def _sync_source_financial_data_serial_sync(
        self,
        data_source: str,
        symbols: List[str],
        report_types: List[str],
        job_id: str,
        rate_limit_per_minute: int = 80,
        resume_from_index: int = None  # 🔥 恢复执行：从哪个位置继续
    ) -> FinancialSyncStats:
        """
        串行同步单个数据源的财务数据（在线程池的线程中执行）
        
        注意：这个方法在线程池的线程中运行，需要创建新的事件循环
        
        Args:
            data_source: 数据源名称
            symbols: 股票代码列表
            report_types: 报告类型列表
            job_id: 任务ID，用于进度跟踪
            rate_limit_per_minute: 速率限制（每分钟最大调用次数）
        """
        # 🔥 检查是否收到退出信号
        if self._shutdown_event.is_set():
            logger.warning(f"⚠️ [{data_source}] 收到退出信号，任务 {job_id} 将不执行")
            stats = FinancialSyncStats()
            stats.total_symbols = len(symbols)
            stats.skipped_count = len(symbols)
            return stats
        
        provider = self.providers[data_source]
        
        # 检查数据源可用性
        if not provider.is_available():
            logger.warning(f"⚠️ {data_source} 数据源不可用")
            stats = FinancialSyncStats()
            stats.total_symbols = len(symbols)
            stats.skipped_count = len(symbols)
            return stats
        
        # 计算延迟时间（确保不超过速率限制）
        # 例如：80次/分钟 = 60/80 = 0.75秒/次
        delay_between_calls = 60.0 / rate_limit_per_minute if rate_limit_per_minute > 0 else 0.5
        
        logger.info(f"🔧 [{data_source}] 串行同步配置: 股票数={len(symbols)}, "
                   f"速率限制={rate_limit_per_minute}次/分钟, "
                   f"延迟={delay_between_calls:.2f}秒/请求")
        
        # 🔥 在线程池的线程中创建新的事件循环
        try:
            loop = asyncio.get_event_loop()
            if loop.is_closed():
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
        except RuntimeError:
            # 线程池的线程没有事件循环，创建新的
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        
        try:
            # 在新事件循环中运行异步逻辑
            result = loop.run_until_complete(
                self._sync_source_financial_data_serial_async(
                    data_source, symbols, report_types, job_id, rate_limit_per_minute, loop, resume_from_index
                )
            )
            return result
        except RuntimeError as e:
            # 🔥 捕获事件循环相关的错误
            if "shutdown" in str(e).lower() or "closed" in str(e).lower():
                logger.error(f"❌ [{data_source}] 事件循环已关闭，无法继续执行: {e}")
                # 创建失败的统计信息
                stats = FinancialSyncStats()
                stats.total_symbols = len(symbols)
                stats.error_count = len(symbols)
                stats.errors.append({
                    "error": f"事件循环已关闭: {e}",
                    "data_source": data_source
                })
                return stats
            raise
        except Exception as e:
            logger.error(f"❌ [{data_source}] 同步任务执行失败: {e}", exc_info=True)
            raise
        finally:
            # 🔥 确保所有任务都完成后再关闭事件循环
            try:
                if not loop.is_closed():
                    # 取消所有未完成的任务
                    pending_tasks = [task for task in asyncio.all_tasks(loop) if not task.done()]
                    if pending_tasks:
                        logger.warning(f"⚠️ [{data_source}] 关闭事件循环前，还有 {len(pending_tasks)} 个未完成的任务")
                        for task in pending_tasks:
                            task.cancel()
                        # 等待任务取消完成（使用超时避免无限等待）
                        try:
                            loop.run_until_complete(asyncio.wait_for(
                                asyncio.gather(*pending_tasks, return_exceptions=True),
                                timeout=5.0
                            ))
                        except asyncio.TimeoutError:
                            logger.warning(f"⚠️ [{data_source}] 等待任务取消超时，强制关闭事件循环")
            except RuntimeError as cleanup_error:
                # 事件循环已关闭，忽略错误
                if "shutdown" not in str(cleanup_error).lower() and "closed" not in str(cleanup_error).lower():
                    logger.warning(f"⚠️ [{data_source}] 清理未完成任务时出错: {cleanup_error}")
            except Exception as cleanup_error:
                logger.warning(f"⚠️ [{data_source}] 清理未完成任务时出错: {cleanup_error}")
            
            # 关闭事件循环
            try:
                if not loop.is_closed():
                    loop.close()
                    logger.debug(f"✅ [{data_source}] 事件循环已关闭")
            except RuntimeError as close_error:
                # 事件循环已关闭，忽略错误
                if "shutdown" not in str(close_error).lower() and "closed" not in str(close_error).lower():
                    logger.warning(f"⚠️ [{data_source}] 关闭事件循环时出错: {close_error}")
            except Exception as close_error:
                logger.warning(f"⚠️ [{data_source}] 关闭事件循环时出错: {close_error}")
    
    def shutdown(self, timeout: float = 30.0):
        """
        优雅关闭线程池
        
        Args:
            timeout: 等待线程完成的最大时间（秒）
        """
        logger.info("🛑 开始关闭财务数据同步服务的线程池...")
        
        # 🔥 设置退出信号
        self._shutdown_event.set()
        
        # 🔥 关闭线程池（不再接受新任务）
        self._thread_pool.shutdown(wait=False)
        
        # 🔥 等待所有任务完成或超时
        logger.info(f"⏳ 等待最多 {timeout} 秒，让所有活跃任务完成...")
        
        futures_to_wait = list(self._active_tasks.values())
        if futures_to_wait:
            done, not_done = concurrent.futures.wait(futures_to_wait, timeout=timeout)
            
            for future in not_done:
                if not future.done():
                    logger.warning(f"⚠️ 任务未能在 {timeout} 秒内完成，将被取消。Future: {future}")
                    future.cancel()  # 尝试取消剩余的任务
            
            if not_done:
                time.sleep(1)  # 给取消操作一个小的宽限期
        
        if self._active_tasks:
            logger.warning(f"⚠️ 仍有 {len(self._active_tasks)} 个任务未完成，可能需要强制退出。")
            self._active_tasks.clear()  # 清理活跃任务列表，防止引用泄漏
        else:
            logger.info("✅ 所有活跃任务已完成或已终止。")
            
        logger.info("✅ 财务数据同步服务线程池已关闭")
    
    async def _sync_source_financial_data_serial_async(
        self,
        data_source: str,
        symbols: List[str],
        report_types: List[str],
        job_id: str,
        rate_limit_per_minute: int,
        loop: asyncio.AbstractEventLoop,
        resume_from_index: int = None  # 🔥 恢复执行：从哪个位置继续
    ) -> FinancialSyncStats:
        """
        串行同步单个数据源的财务数据（异步版本，在线程池的线程中运行）
        """
        provider = self.providers[data_source]
        
        # 检查数据源可用性
        if not provider.is_available():
            logger.warning(f"⚠️ {data_source} 数据源不可用")
            stats = FinancialSyncStats()
            stats.total_symbols = len(symbols)
            stats.skipped_count = len(symbols)
            return stats
        
        # 计算延迟时间（确保不超过速率限制）
        # 例如：80次/分钟 = 60/80 = 0.75秒/次
        delay_between_calls = 60.0 / rate_limit_per_minute if rate_limit_per_minute > 0 else 0.5
        
        # 🔥 保存原始股票总数（用于进度计算）
        original_total_symbols = len(symbols)
        
        # 🔥 如果指定了恢复位置，跳过已处理的股票
        start_index = resume_from_index if resume_from_index is not None and resume_from_index > 0 else 0
        if start_index > 0:
            logger.info(f"🔄 [{data_source}] 恢复执行：从第 {start_index} 个股票开始（已处理 {start_index}/{original_total_symbols}）")
            # 跳过已处理的股票
            symbols = symbols[start_index:]
            if not symbols:
                logger.warning(f"⚠️ [{data_source}] 所有股票已处理完成，无需继续同步")
                stats = FinancialSyncStats()
                stats.total_symbols = original_total_symbols
                stats.success_count = start_index
                return stats
        
        logger.info(f"🔧 [{data_source}] 串行同步配置: 剩余股票数={len(symbols)}, 总股票数={original_total_symbols}, "
                   f"速率限制={rate_limit_per_minute}次/分钟, "
                   f"延迟={delay_between_calls:.2f}秒/请求, "
                   f"起始位置={start_index}")
        
        # 初始化统计信息
        stats = FinancialSyncStats()
        stats.total_symbols = original_total_symbols  # 🔥 总股票数（包括已处理的）
        stats.start_time = datetime.now(timezone.utc)
        
        # 🔥 在线程池的线程中创建新的服务实例（避免事件循环冲突）
        # 使用当前线程的事件循环创建新的异步数据库连接
        from app.services.financial_data_service import FinancialDataService
        from motor.motor_asyncio import AsyncIOMotorClient
        from app.core.config import settings
        
        # 在当前线程的事件循环中创建新的异步 MongoDB 客户端
        # 这样数据库连接就绑定到当前线程的事件循环，而不是主事件循环
        mongo_client = AsyncIOMotorClient(settings.MONGO_URI)
        mongo_db = mongo_client[settings.MONGODB_DATABASE]
        
        # 创建新的服务实例，使用当前线程事件循环的数据库连接
        financial_service = FinancialDataService()
        financial_service.db = mongo_db
        
        # 确保索引存在（异步方式，在当前线程的事件循环中执行）
        try:
            collection = financial_service.db[financial_service.collection_name]
            # 创建索引（异步操作）
            await collection.create_indexes([
                # 复合唯一索引
                [("symbol", 1), ("report_period", 1), ("data_source", 1)],
                # 其他索引
                [("symbol", 1)],
                [("report_period", -1)],
                [("data_source", 1)]
            ])
        except Exception as e:
            logger.debug(f"索引创建检查: {e}")  # 索引可能已存在，忽略错误
        
        # 串行处理每个股票
        processed_count = start_index  # 🔥 从恢复位置开始计数
        for i, symbol in enumerate(symbols):
            # 🔥 检查是否收到退出信号
            if self._shutdown_event.is_set():
                logger.info(f"🛑 [{data_source}] 收到退出信号，停止同步")
                # 更新进度为当前进度
                try:
                    from app.services.scheduler_service import update_job_progress
                    # 🔥 计算进度时需要考虑已处理的股票数（恢复执行时）
                    total_items = stats.total_symbols  # 使用总股票数（包括已处理的）
                    progress_int = int((processed_count / total_items) * 100) if total_items > 0 else 0
                    progress_int = min(progress_int, 100)
                    await update_job_progress(
                        job_id=job_id,
                        progress=progress_int,
                        current_item=f"[{data_source}] {symbol}",
                        total_items=total_items,
                        processed_items=processed_count,
                        message=f"[{data_source}] 任务已收到退出信号，正在停止"
                    )
                except Exception as e:
                    logger.warning(f"⚠️ 更新进度失败: {e}")
                break
            
            try:
                # 🔥 检查任务是否被取消（在每次循环开始时检查）
                should_stop = await self._should_stop_sync(job_id, loop)
                if should_stop:
                    logger.warning(f"🛑 [{data_source}] 检测到取消请求，任务已取消，停止同步 (job_id={job_id})")
                    # 更新进度为当前进度
                    try:
                        from app.services.scheduler_service import update_job_progress, TaskCancelledException
                        progress_int = int((processed_count / len(symbols)) * 100) if len(symbols) > 0 else 0
                        progress_int = min(progress_int, 100)
                        await update_job_progress(
                            job_id=job_id,
                            progress=progress_int,
                            current_item=f"[{data_source}] {symbol}",
                            total_items=len(symbols),
                            processed_items=processed_count,
                            message=f"[{data_source}] 任务已被用户取消"
                        )
                    except TaskCancelledException:
                        # 如果update_job_progress也检测到取消，直接退出
                        logger.warning(f"🛑 [{data_source}] update_job_progress也检测到取消请求，立即停止")
                        break
                    except Exception as e:
                        logger.warning(f"⚠️ 更新进度失败: {e}")
                    break
                
                # 🔥 速率限制：在调用API之前等待（等待期间也检查取消）
                if delay_between_calls > 0:
                    # 分段等待，每0.5秒检查一次取消状态
                    wait_time = 0
                    check_interval = 0.5
                    while wait_time < delay_between_calls:
                        await asyncio.sleep(min(check_interval, delay_between_calls - wait_time))
                        wait_time += check_interval
                        # 检查取消状态
                        should_stop = await self._should_stop_sync(job_id, loop)
                        if should_stop:
                            logger.warning(f"🛑 [{data_source}] 在等待期间检测到取消请求，停止同步 (job_id={job_id})")
                            # 更新进度并退出循环
                            try:
                                from app.services.scheduler_service import update_job_progress
                                # 🔥 计算进度时需要考虑已处理的股票数（恢复执行时）
                                total_items = stats.total_symbols  # 使用总股票数（包括已处理的）
                                progress_int = int((processed_count / total_items) * 100) if total_items > 0 else 0
                                progress_int = min(progress_int, 100)
                                await update_job_progress(
                                    job_id=job_id,
                                    progress=progress_int,
                                    current_item=f"[{data_source}] {symbol}",
                                    total_items=total_items,
                                    processed_items=processed_count,
                                    message=f"[{data_source}] 任务已被用户取消"
                                )
                            except Exception as e:
                                logger.warning(f"⚠️ 更新进度失败: {e}")
                            break
                
                # 🔥 在同步股票数据之前，再次检查取消标记（防止在同步过程中收到取消请求）
                should_stop = await self._should_stop_sync(job_id, loop)
                if should_stop:
                    logger.warning(f"🛑 [{data_source}] 在同步前检测到取消请求，停止同步 (job_id={job_id})")
                    break
                
                # 同步单只股票的财务数据
                success = await self._sync_symbol_financial_data_async(
                    symbol=symbol,
                    data_source=data_source,
                    provider=provider,
                    report_types=report_types,
                    financial_service=financial_service
                )
                
                if success:
                    stats.success_count += 1
                else:
                    stats.skipped_count += 1
                
                processed_count += 1
                
                # 🔥 在同步完成后，再次检查取消标记
                should_stop = await self._should_stop_sync(job_id, loop)
                if should_stop:
                    logger.warning(f"🛑 [{data_source}] 在同步后检测到取消请求，停止同步 (job_id={job_id})")
                    break
                
                # 🔥 每处理1个股票或完成时更新一次进度（更频繁的更新）
                # 计算进度百分比：确保即使进度很小也能正确显示（至少显示1%）
                # 🔥 计算进度时需要考虑已处理的股票数（恢复执行时）
                total_items = stats.total_symbols  # 使用总股票数（包括已处理的）
                if total_items > 0:
                    progress_float = (processed_count / total_items) * 100
                    # 🔥 如果进度大于0但小于1%，至少显示1%，避免显示0%
                    if progress_float > 0 and progress_float < 1:
                        progress_int = 1
                    else:
                        progress_int = int(round(progress_float))
                    # 确保不超过100%
                    progress_int = min(progress_int, 100)
                else:
                    progress_int = 0
                
                # update_job_progress 是独立的异步函数
                try:
                    from app.services.scheduler_service import update_job_progress, TaskCancelledException
                    # 🔥 记录进度更新调用（用于调试）
                    logger.debug(f"📊 [{data_source}] 准备更新进度: job_id={job_id}, progress={progress_int}%, "
                               f"processed={processed_count}/{total_items}, current_item={symbol}")
                    
                    await update_job_progress(
                        job_id=job_id,
                        progress=progress_int,  # 使用整数百分比
                        current_item=f"[{data_source}] {symbol}",  # 🔥 在current_item中标注数据源
                        total_items=total_items,  # 🔥 使用总股票数（包括已处理的）
                        processed_items=processed_count,
                        message=f"[{data_source}] 正在同步: {symbol} ({processed_count}/{total_items})"  # 🔥 在消息中标注数据源和总股票数
                    )
                    
                    # 🔥 每10个股票记录一次详细日志，避免日志过多
                    if processed_count % 10 == 0 or (i + 1) == len(symbols):
                        logger.info(f"📊 [{data_source}] 进度更新成功: {processed_count}/{total_items} "
                                   f"({progress_int}%), 成功={stats.success_count}, 跳过={stats.skipped_count}")
                except TaskCancelledException as cancel_error:
                    # 🔥 如果收到取消请求，立即停止任务
                    logger.warning(f"🛑 [{data_source}] 收到取消请求（通过update_job_progress），停止同步: {cancel_error}")
                    # 🔥 设置一个标志，确保循环退出
                    should_stop = True
                    # 🔥 立即跳出循环
                    break
                except Exception as progress_error:
                    # 🔥 检查是否是取消相关的异常（可能是其他形式的取消异常）
                    error_msg = str(progress_error)
                    error_type = type(progress_error).__name__
                    logger.warning(f"🔍 [{data_source}] 进度更新异常类型: {error_type}, 消息: {error_msg}")
                    
                    error_lower = error_msg.lower()
                    if "取消" in error_lower or "cancel" in error_lower or "cancelled" in error_lower or "TaskCancelledException" in error_type:
                        logger.warning(f"🛑 [{data_source}] 进度更新时检测到取消相关异常，停止同步: {progress_error}")
                        break
                    # 🔥 进度更新失败不应该影响主流程，但需要记录日志
                    logger.error(f"❌ [{data_source}] 进度更新失败: job_id={job_id}, error={progress_error}", exc_info=True)
                    # 每10个股票记录一次错误，避免日志过多
                    if processed_count % 10 == 0:
                        logger.warning(f"⚠️ [{data_source}] 进度更新失败，但继续执行: {progress_error}")
                
            except Exception as e:
                # 🔥 检查是否是取消相关的异常
                error_msg = str(e)
                error_type = type(e).__name__
                error_lower = error_msg.lower()
                
                # 🔥 检查是否是TaskCancelledException或其子类
                from app.services.scheduler_service import TaskCancelledException
                if isinstance(e, TaskCancelledException):
                    logger.warning(f"🛑 [{data_source}] 检测到TaskCancelledException，停止同步: {error_msg}")
                    break
                
                # 🔥 检查异常类型名称或消息中是否包含取消相关关键词
                if "取消" in error_lower or "cancel" in error_lower or "cancelled" in error_lower or "TaskCancelledException" in error_type:
                    logger.warning(f"🛑 [{data_source}] 检测到取消相关异常，停止同步: 类型={error_type}, 消息={error_msg}")
                    break
                
                stats.error_count += 1
                stats.errors.append({
                    "symbol": symbol,
                    "error": error_msg,
                    "data_source": data_source
                })
                logger.error(f"❌ [{data_source}] {symbol} 财务数据同步失败: {error_msg}")
                processed_count += 1
        
        # 🔥 检查任务是否因为取消而停止
        was_cancelled = False
        try:
            should_stop = await self._should_stop_sync(job_id, loop)
            if should_stop:
                was_cancelled = True
                logger.warning(f"🛑 [{data_source}] 任务因取消而停止，将更新状态为cancelled (job_id={job_id})")
        except Exception as e:
            logger.warning(f"⚠️ [{data_source}] 检查取消状态失败: {e}")
        
        # 完成统计
        stats.end_time = datetime.now(timezone.utc)
        stats.duration = (stats.end_time - stats.start_time).total_seconds()
        
        # 🔥 如果任务被取消，更新状态为cancelled
        if was_cancelled:
            try:
                # 使用同步方式更新状态（因为在线程池的线程中，事件循环可能已关闭）
                from pymongo import MongoClient
                from app.core.config import settings
                sync_client = MongoClient(settings.MONGO_URI)
                sync_db = sync_client[settings.MONGODB_DATABASE]
                try:
                    # 提取原始job_id
                    original_job_id = job_id
                    for ds in ["tushare", "akshare", "baostock"]:
                        if job_id.endswith(f"_{ds}"):
                            original_job_id = job_id[:-len(f"_{ds}")]
                            break
                    
                    # 更新所有相关的执行记录为cancelled状态
                    update_result = sync_db.scheduler_executions.update_many(
                        {
                            "job_id": {"$regex": f"^{original_job_id}(_|$)"},
                            "status": "running"
                        },
                        {
                            "$set": {
                                "status": "cancelled",
                                "error_message": f"[{data_source}] 任务已被用户取消",
                                "updated_at": datetime.now(timezone.utc).replace(tzinfo=None)
                            }
                        }
                    )
                    logger.info(f"✅ [{data_source}] 已更新 {update_result.modified_count} 个执行记录状态为cancelled (job_id={job_id})")
                    
                    # 🔥 同时更新Redis缓存中的状态
                    try:
                        from app.core.redis_client import RedisKeys
                        from app.core.database import get_redis_sync_client
                        import json
                        redis_sync_client = get_redis_sync_client()
                        if redis_sync_client:
                            progress_key = RedisKeys.SCHEDULER_JOB_PROGRESS.format(job_id=original_job_id)
                            # 获取当前进度数据
                            progress_data_str = redis_sync_client.get(progress_key)
                            if progress_data_str:
                                progress_data = json.loads(progress_data_str)
                                progress_data["status"] = "cancelled"
                                progress_data["message"] = f"[{data_source}] 任务已被用户取消"
                                redis_sync_client.setex(
                                    progress_key,
                                    86400,  # 24小时过期
                                    json.dumps(progress_data, ensure_ascii=False)
                                )
                                logger.info(f"✅ [{data_source}] 已更新Redis缓存状态为cancelled")
                    except Exception as redis_error:
                        logger.warning(f"⚠️ [{data_source}] 更新Redis缓存失败: {redis_error}")
                finally:
                    sync_client.close()
            except Exception as e:
                logger.error(f"❌ [{data_source}] 更新任务状态为cancelled失败: {e}", exc_info=True)
        
        logger.info(f"✅ [{data_source}] 财务数据同步完成: "
                   f"成功={stats.success_count}, 失败={stats.error_count}, "
                   f"跳过={stats.skipped_count}, 耗时={stats.duration:.2f}秒, "
                   f"取消={was_cancelled}")
        
        return stats
    
    async def _should_stop_sync(self, job_id: str, loop: asyncio.AbstractEventLoop) -> bool:
        """
        检查任务是否应该停止（在线程池的线程中调用）
        
        Args:
            job_id: 任务ID（可能是修改后的job_id，如 tushare_financial_sync_tushare）
            loop: 事件循环
            
        Returns:
            如果任务应该停止，返回True
        """
        try:
            # 🔥 检查事件循环是否已关闭
            if loop.is_closed():
                logger.warning(f"⚠️ 事件循环已关闭，无法检查任务状态: {job_id}")
                return False
            
            # 🔥 提取原始job_id（如果job_id是 tushare_financial_sync_tushare，则原始是 tushare_financial_sync）
            # 检查job_id是否以数据源名称结尾（tushare、akshare、baostock）
            original_job_id = job_id
            for data_source in ["tushare", "akshare", "baostock"]:
                if job_id.endswith(f"_{data_source}"):
                    original_job_id = job_id[:-len(f"_{data_source}")]
                    break
            
            # 使用同步的 MongoDB 客户端查询（避免事件循环冲突）
            from pymongo import MongoClient
            from app.core.config import settings
            
            def query_execution():
                sync_client = MongoClient(settings.MONGO_URI)
                sync_db = sync_client[settings.MONGODB_DATABASE]
                try:
                    # 🔥 只查询当前正在运行的任务（running状态），不查询suspended状态的旧记录
                    # 因为suspended记录可能是之前被取消的旧任务，不应该影响新任务
                    query = {
                        "job_id": {"$regex": f"^{original_job_id}(_|$)"},
                        "status": "running"  # 🔥 只查询running状态，忽略suspended状态
                    }
                    execution = sync_db.scheduler_executions.find_one(
                        query,
                        sort=[("started_at", -1)]
                    )
                    
                    # 🔥 如果找到了执行记录，检查是否是当前任务的执行记录
                    # 通过检查时间戳，如果执行记录是最近1分钟内创建的，才认为是当前任务
                    if execution:
                        from datetime import datetime, timedelta
                        execution_time = execution.get("started_at") or execution.get("timestamp") or execution.get("scheduled_time")
                        if execution_time:
                            # 如果是datetime对象，直接比较；如果是字符串，需要转换
                            if isinstance(execution_time, str):
                                try:
                                    execution_time = datetime.fromisoformat(execution_time.replace('Z', '+00:00'))
                                except:
                                    execution_time = None
                            
                            if execution_time:
                                time_diff = (datetime.now() - execution_time.replace(tzinfo=None)).total_seconds()
                                # 如果执行记录超过5分钟，认为是旧任务，不检查取消标记
                                if time_diff > 300:  # 5分钟
                                    logger.debug(f"🔍 执行记录太旧（{time_diff:.0f}秒前），忽略取消标记检查")
                                    return None
                    
                    return execution
                finally:
                    sync_client.close()
            
            # 🔥 检查事件循环状态后再执行
            if not loop.is_closed():
                execution = await loop.run_in_executor(None, query_execution)
            else:
                # 如果事件循环已关闭，直接使用同步查询
                sync_client = MongoClient(settings.MONGO_URI)
                sync_db = sync_client[settings.MONGODB_DATABASE]
                try:
                    # 🔥 只查询当前正在运行的任务（running状态），不查询suspended状态的旧记录
                    query = {
                        "job_id": {"$regex": f"^{original_job_id}(_|$)"},
                        "status": "running"  # 🔥 只查询running状态，忽略suspended状态
                    }
                    execution = sync_db.scheduler_executions.find_one(
                        query,
                        sort=[("started_at", -1)]
                    )
                    
                    # 🔥 如果找到了执行记录，检查是否是当前任务的执行记录
                    if execution:
                        from datetime import datetime, timedelta
                        execution_time = execution.get("started_at") or execution.get("timestamp") or execution.get("scheduled_time")
                        if execution_time:
                            if isinstance(execution_time, str):
                                try:
                                    execution_time = datetime.fromisoformat(execution_time.replace('Z', '+00:00'))
                                except:
                                    execution_time = None
                            
                            if execution_time:
                                time_diff = (datetime.now() - execution_time.replace(tzinfo=None)).total_seconds()
                                if time_diff > 300:  # 5分钟
                                    logger.debug(f"🔍 执行记录太旧（{time_diff:.0f}秒前），忽略取消标记检查")
                                    execution = None
                finally:
                    sync_client.close()
            
            if execution:
                execution_id = str(execution.get("_id", ""))
                execution_job_id = execution.get("job_id", "")
                cancel_requested = execution.get("cancel_requested", False)
                execution_status = execution.get("status", "")
                
                # 🔥 只在检测到取消或异常状态时才输出INFO级别日志，正常检查使用DEBUG级别
                if cancel_requested or execution_status in ["failed", "cancelled"]:
                    logger.info(f"🔍 检查任务状态: job_id={job_id}, original_job_id={original_job_id}, "
                               f"找到记录: execution_id={execution_id}, execution_job_id={execution_job_id}, "
                               f"cancel_requested={cancel_requested}, status={execution_status}")
                else:
                    # 正常检查时使用DEBUG级别，减少日志输出
                    logger.debug(f"🔍 检查任务状态: job_id={job_id}, original_job_id={original_job_id}, "
                               f"找到记录: execution_id={execution_id}, execution_job_id={execution_job_id}, "
                               f"cancel_requested={cancel_requested}, status={execution_status}")
                
                # 检查是否被取消
                if cancel_requested:
                    logger.warning(f"🛑 检测到取消请求: job_id={job_id}, original_job_id={original_job_id}, "
                                 f"execution_id={execution_id}, execution_job_id={execution_job_id}")
                    return True
                
                # 检查状态是否为失败或已取消
                if execution_status in ["failed", "cancelled"]:
                    logger.warning(f"🛑 检测到任务状态为 {execution_status}: job_id={job_id}, "
                                 f"original_job_id={original_job_id}, execution_job_id={execution_job_id}")
                    return True
            else:
                # 🔥 如果没有找到执行记录，记录日志
                logger.debug(f"⚠️ 未找到执行记录: job_id={job_id}, original_job_id={original_job_id}")
            
            return False
        except RuntimeError as e:
            # 🔥 捕获事件循环相关的错误
            if "shutdown" in str(e).lower() or "closed" in str(e).lower():
                logger.warning(f"⚠️ 事件循环已关闭，跳过任务状态检查: {job_id}")
                return False
            logger.error(f"❌ 检查任务状态失败: {e}")
            return False
        except Exception as e:
            logger.error(f"❌ 检查任务状态失败: {e}")
            return False
    
    async def _sync_symbol_financial_data_async(
        self,
        symbol: str,
        data_source: str,
        provider: Any,
        report_types: List[str],
        financial_service: Any
    ) -> bool:
        """
        同步单只股票的财务数据（异步版本）
        """
        try:
            # 🔥 检查事件循环是否已关闭
            try:
                loop = asyncio.get_running_loop()
                if loop.is_closed():
                    logger.warning(f"⚠️ {symbol} 事件循环已关闭，无法获取财务数据 ({data_source})")
                    return False
            except RuntimeError:
                logger.warning(f"⚠️ {symbol} 无法获取事件循环，可能已关闭 ({data_source})")
                return False
            
            # 获取财务数据
            financial_data = await provider.get_financial_data(symbol)
            
            if not financial_data:
                logger.debug(f"⚠️ {symbol} 无财务数据 ({data_source})")
                return False
            
            # 为每种报告类型保存数据
            saved_count = 0
            for report_type in report_types:
                try:
                    count = await financial_service.save_financial_data(
                        symbol=symbol,
                        financial_data=financial_data,
                        data_source=data_source,
                        report_type=report_type
                    )
                    saved_count += count
                except RuntimeError as e:
                    # 🔥 捕获事件循环关闭错误
                    if "shutdown" in str(e).lower() or "closed" in str(e).lower():
                        logger.warning(f"⚠️ {symbol} 保存财务数据时事件循环已关闭 ({data_source}): {e}")
                        break
                    raise
            
            return saved_count > 0
            
        except RuntimeError as e:
            # 🔥 捕获事件循环相关的错误
            if "shutdown" in str(e).lower() or "closed" in str(e).lower():
                logger.warning(f"⚠️ {symbol} 财务数据同步时事件循环已关闭 ({data_source}): {e}")
                return False
            logger.error(f"❌ {symbol} 财务数据同步异常 ({data_source}): {e}")
            raise
        except Exception as e:
            logger.error(f"❌ {symbol} 财务数据同步异常 ({data_source}): {e}")
            raise
    
    async def _sync_source_financial_data(
        self,
        data_source: str,
        symbols: List[str],
        report_types: List[str],
        batch_size: int,
        delay_seconds: float
    ) -> FinancialSyncStats:
        """同步单个数据源的财务数据"""
        stats = FinancialSyncStats()
        stats.total_symbols = len(symbols)
        stats.start_time = datetime.now(timezone.utc)
        
        provider = self.providers[data_source]
        
        # 检查数据源可用性
        if not provider.is_available():
            logger.warning(f"⚠️ {data_source} 数据源不可用")
            stats.skipped_count = len(symbols)
            stats.end_time = datetime.now(timezone.utc)
            return stats
        
        # 批量处理股票
        for i in range(0, len(symbols), batch_size):
            batch_symbols = symbols[i:i + batch_size]
            
            logger.info(f"📈 {data_source} 处理批次 {i//batch_size + 1}: "
                       f"{len(batch_symbols)} 只股票")
            
            # 并发处理批次内的股票
            tasks = []
            for symbol in batch_symbols:
                task = self._sync_symbol_financial_data(
                    symbol=symbol,
                    data_source=data_source,
                    provider=provider,
                    report_types=report_types
                )
                tasks.append(task)
            
            # 执行并发任务
            batch_results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # 统计批次结果
            for j, result in enumerate(batch_results):
                symbol = batch_symbols[j]
                
                if isinstance(result, Exception):
                    stats.error_count += 1
                    stats.errors.append({
                        "symbol": symbol,
                        "data_source": data_source,
                        "error": str(result),
                        "timestamp": datetime.now(timezone.utc).isoformat()
                    })
                    logger.error(f"❌ {symbol} 财务数据同步失败 ({data_source}): {result}")
                elif result:
                    stats.success_count += 1
                    logger.debug(f"✅ {symbol} 财务数据同步成功 ({data_source})")
                else:
                    stats.skipped_count += 1
                    logger.debug(f"⏭️ {symbol} 财务数据跳过 ({data_source})")
            
            # API限流延迟
            if i + batch_size < len(symbols):
                await asyncio.sleep(delay_seconds)
        
        stats.end_time = datetime.now(timezone.utc)
        stats.duration = (stats.end_time - stats.start_time).total_seconds()
        
        return stats
    
    async def _sync_symbol_financial_data(
        self,
        symbol: str,
        data_source: str,
        provider: Any,
        report_types: List[str]
    ) -> bool:
        """同步单只股票的财务数据"""
        try:
            # 获取财务数据
            financial_data = await provider.get_financial_data(symbol)
            
            if not financial_data:
                logger.debug(f"⚠️ {symbol} 无财务数据 ({data_source})")
                return False
            
            # 为每种报告类型保存数据
            saved_count = 0
            for report_type in report_types:
                count = await self.financial_service.save_financial_data(
                    symbol=symbol,
                    financial_data=financial_data,
                    data_source=data_source,
                    report_type=report_type
                )
                saved_count += count
            
            return saved_count > 0
            
        except Exception as e:
            logger.error(f"❌ {symbol} 财务数据同步异常 ({data_source}): {e}")
            raise
    
    async def _get_stock_symbols(self) -> List[str]:
        """获取股票代码列表（去重）"""
        try:
            # 🔥 使用聚合查询去重，确保每个股票代码只计算一次
            # 因为同一个股票可能来自多个数据源（tushare、akshare、baostock），会有重复记录
            pipeline = [
                {
                    "$match": {
                        "$or": [
                            {"market_info.market": "CN"},  # 新数据结构
                            {"category": "stock_cn"},      # 旧数据结构
                            {"market": {"$in": ["主板", "创业板", "科创板", "北交所"]}}  # 按市场类型
                        ]
                    }
                },
                {
                    "$group": {
                        "_id": "$code"  # 按股票代码分组去重
                    }
                },
                {
                    "$project": {
                        "_id": 0,
                        "code": "$_id"
                    }
                }
            ]
            cursor = self.db.stock_basic_info.aggregate(pipeline)
            symbols = [doc["code"] async for doc in cursor]
            logger.info(f"📋 从 stock_basic_info 获取到 {len(symbols)} 只唯一股票代码（已去重）")

            return symbols

        except Exception as e:
            logger.error(f"❌ 获取股票代码列表失败: {e}")
            return []
    
    async def get_sync_statistics(self) -> Dict[str, Any]:
        """获取同步统计信息"""
        try:
            if self.financial_service is None:
                await self.initialize()
            
            return await self.financial_service.get_financial_statistics()
            
        except Exception as e:
            logger.error(f"❌ 获取同步统计失败: {e}")
            return {}
    
    async def sync_single_stock(
        self,
        symbol: str,
        data_sources: List[str] = None
    ) -> Dict[str, bool]:
        """同步单只股票的财务数据"""
        if self.db is None:
            await self.initialize()
        
        if data_sources is None:
            data_sources = ["tushare", "akshare", "baostock"]
        
        results = {}
        
        for data_source in data_sources:
            if data_source not in self.providers:
                results[data_source] = False
                continue
            
            try:
                provider = self.providers[data_source]
                
                if not provider.is_available():
                    results[data_source] = False
                    continue
                
                result = await self._sync_symbol_financial_data(
                    symbol=symbol,
                    data_source=data_source,
                    provider=provider,
                    report_types=["quarterly"]
                )
                
                results[data_source] = result
                
            except Exception as e:
                logger.error(f"❌ {symbol} 单股票财务数据同步失败 ({data_source}): {e}")
                results[data_source] = False
        
        return results


# 全局服务实例
_financial_sync_service = None


async def get_financial_sync_service() -> FinancialDataSyncService:
    """获取财务数据同步服务实例"""
    global _financial_sync_service
    if _financial_sync_service is None:
        _financial_sync_service = FinancialDataSyncService()
        await _financial_sync_service.initialize()
    return _financial_sync_service
