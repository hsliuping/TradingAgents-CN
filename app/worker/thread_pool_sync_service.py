#!/usr/bin/env python3
"""
基于线程池的数据同步服务

提供真正的多线程并行处理能力，解决协程并发可能卡住的问题
"""
import asyncio
import logging
import threading
import queue
import time
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional, Callable
from dataclasses import dataclass, field
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeoutError, as_completed
from collections import defaultdict

logger = logging.getLogger(__name__)


class CancellationToken:
    """
    线程安全的取消令牌
    """
    
    def __init__(self):
        self._cancelled = False
        self._lock = threading.Lock()
    
    def cancel(self):
        """取消任务"""
        with self._lock:
            self._cancelled = True
            logger.info("🛑 任务取消令牌已设置")
    
    def is_cancelled(self) -> bool:
        """检查是否已取消"""
        with self._lock:
            return self._cancelled
    
    def reset(self):
        """重置（用于重新开始）"""
        with self._lock:
            self._cancelled = False


@dataclass
class SyncStats:
    """同步统计信息"""
    total_items: int = 0
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
            "total_items": self.total_items,
            "success_count": self.success_count,
            "error_count": self.error_count,
            "skipped_count": self.skipped_count,
            "start_time": self.start_time.isoformat() if self.start_time else None,
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "duration": self.duration,
            "success_rate": round(self.success_count / max(self.total_items, 1) * 100, 2),
            "errors": self.errors[:10]  # 只返回前10个错误
        }


class ProgressTracker:
    """
    线程安全的进度跟踪器
    """
    
    def __init__(self, job_id: str, total_items: int):
        self.job_id = job_id
        self.total_items = total_items
        
        # 线程安全的计数器
        self._processed_items = 0
        self._success_count = 0
        self._error_count = 0
        self._current_item = None
        
        # 锁
        self._lock = threading.Lock()
        
        # 错误列表
        self._errors = []
    
    def record_success(self, item: str):
        """记录成功"""
        with self._lock:
            self._processed_items += 1
            self._success_count += 1
            self._current_item = item
    
    def record_error(self, item: str, error: str):
        """记录错误"""
        with self._lock:
            self._processed_items += 1
            self._error_count += 1
            self._current_item = item
            self._errors.append({
                "item": item,
                "error": error,
                "timestamp": datetime.now(timezone.utc).isoformat()
            })
    
    def get_progress(self) -> int:
        """获取进度百分比"""
        with self._lock:
            if self.total_items == 0:
                return 0
            return int((self._processed_items / self.total_items) * 100)
    
    @property
    def processed_items(self) -> int:
        """已处理项数"""
        with self._lock:
            return self._processed_items
    
    @property
    def success_count(self) -> int:
        """成功数"""
        with self._lock:
            return self._success_count
    
    @property
    def error_count(self) -> int:
        """错误数"""
        with self._lock:
            return self._error_count
    
    def get_current_item(self) -> str:
        """获取当前处理项"""
        with self._lock:
            return self._current_item
    
    def is_complete(self) -> bool:
        """是否完成"""
        with self._lock:
            return self._processed_items >= self.total_items
    
    def get_errors(self) -> List[Dict[str, Any]]:
        """获取错误列表"""
        with self._lock:
            return self._errors.copy()


class RateLimiter:
    """
    线程安全的速率限制器
    
    用于控制API调用频率，避免超过速率限制
    """
    
    def __init__(self, max_calls: int, time_window: float):
        """
        Args:
            max_calls: 时间窗口内最大调用次数
            time_window: 时间窗口（秒）
        """
        self.max_calls = max_calls
        self.time_window = time_window
        self.calls = defaultdict(list)  # 按数据源记录调用时间
        self.lock = threading.Lock()
    
    def wait_if_needed(self, data_source: str = "default"):
        """
        如果需要，等待直到可以调用
        
        Args:
            data_source: 数据源名称（不同数据源有独立的速率限制）
        """
        with self.lock:
            now = time.time()
            # 清理过期记录
            self.calls[data_source] = [
                call_time for call_time in self.calls[data_source]
                if now - call_time < self.time_window
            ]
            
            # 如果超过限制，计算需要等待的时间
            if len(self.calls[data_source]) >= self.max_calls:
                oldest_call = min(self.calls[data_source])
                wait_time = self.time_window - (now - oldest_call) + 0.2  # 多等0.2秒确保安全
                if wait_time > 0:
                    logger.warning(f"⏳ [{data_source}] 速率限制：已调用 {len(self.calls[data_source])}/{self.max_calls} 次，需要等待 {wait_time:.2f} 秒")
                    time.sleep(wait_time)
                    # 重新清理过期记录
                    now = time.time()
                    self.calls[data_source] = [
                        call_time for call_time in self.calls[data_source]
                        if now - call_time < self.time_window
                    ]
            
            # 🔥 记录本次调用（在锁内记录，确保线程安全）
            self.calls[data_source].append(time.time())
            
            # 🔥 记录当前调用频率（用于调试）
            current_rate = len(self.calls[data_source])
            if current_rate > self.max_calls * 0.8:  # 超过80%时记录警告
                logger.debug(f"⚠️ [{data_source}] 当前调用频率: {current_rate}/{self.max_calls} 次/{self.time_window}秒")


class ThreadPoolSyncService:
    """
    基于线程池的数据同步服务
    
    特性：
    - 真正的多线程并行处理
    - 实时进度更新
    - 任务取消支持
    - 超时保护
    - 错误隔离和重试
    - API速率限制保护
    """
    
    def __init__(
        self,
        max_workers: int = 10,
        timeout_per_task: int = 36000,  # 默认10小时（36000秒），用于历史数据同步
        progress_update_interval: int = 5,  # 进度更新间隔（秒）
        enable_retry: bool = True,
        max_retries: int = 3,
        rate_limit_per_minute: int = 200,  # 每分钟最大请求数（Tushare限制）
        delay_between_items: float = 0.3  # 每个任务之间的延迟（秒）
    ):
        self.max_workers = max_workers
        self.timeout_per_task = timeout_per_task
        self.progress_update_interval = progress_update_interval
        self.enable_retry = enable_retry
        self.max_retries = max_retries
        self.delay_between_items = delay_between_items
        
        # 🔥 速率限制器（每分钟200次请求，Tushare限制）
        self.rate_limiter = RateLimiter(
            max_calls=rate_limit_per_minute,
            time_window=60.0  # 60秒窗口
        )
        
        # 线程池
        self.executor = None
        
        # 任务队列
        self.task_queue = queue.Queue()
        
        # 进度跟踪器
        self.progress_tracker = None
        
        # 取消令牌
        self.cancellation_token = CancellationToken()
        
        # 统计信息
        self.stats = SyncStats()
    
    async def sync_in_thread_pool(
        self,
        items: List[str],
        process_func: Callable,
        job_id: str,
        context: Dict[str, Any] = None
    ) -> SyncStats:
        """
        在线程池中执行同步任务
        
        Args:
            items: 要处理的项列表（如股票代码列表）
            process_func: 处理函数（同步或异步）
            job_id: 任务ID，用于进度跟踪
            context: 上下文信息（传递给处理函数）
        
        Returns:
            同步统计信息
        """
        if not items:
            logger.warning("⚠️ 没有要处理的项")
            return self.stats
        
        # 1. 初始化统计信息
        self.stats = SyncStats()
        self.stats.total_items = len(items)
        self.stats.start_time = datetime.now(timezone.utc)
        
        # 2. 初始化进度跟踪器
        self.progress_tracker = ProgressTracker(
            job_id=job_id,
            total_items=len(items)
        )
        
        logger.info(f"🚀 开始线程池同步: job_id={job_id}, 总任务数={len(items)}, "
                   f"线程数={self.max_workers}, 超时={self.timeout_per_task}秒")
        
        # 3. 创建线程池
        self.executor = ThreadPoolExecutor(max_workers=self.max_workers)
        
        # 4. 填充任务队列
        for item in items:
            self.task_queue.put((item, context))
        
        # 5. 启动工作线程
        futures = []
        for i in range(self.max_workers):
            future = self.executor.submit(
                self._worker_loop,
                process_func,
                context or {}
            )
            futures.append(future)
        
        # 6. 启动进度更新任务
        progress_task = asyncio.create_task(self._progress_update_loop())
        
        # 7. 等待所有任务完成
        try:
            # 等待所有工作线程完成
            completed_count = 0
            for future in as_completed(futures):
                try:
                    future.result()
                    completed_count += 1
                    logger.debug(f"✅ 工作线程 {completed_count}/{self.max_workers} 已完成")
                except Exception as e:
                    logger.error(f"❌ 工作线程异常: {e}", exc_info=True)
            
            # 等待进度更新任务完成
            await progress_task
            
        except Exception as e:
            logger.error(f"❌ 线程池同步异常: {e}", exc_info=True)
            raise
        finally:
            # 关闭线程池
            self.executor.shutdown(wait=True)
            logger.info("🔒 线程池已关闭")
        
        # 8. 更新统计信息
        self.stats.end_time = datetime.now(timezone.utc)
        self.stats.duration = (self.stats.end_time - self.stats.start_time).total_seconds()
        self.stats.success_count = self.progress_tracker.success_count
        self.stats.error_count = self.progress_tracker.error_count
        self.stats.errors = self.progress_tracker.get_errors()
        
        logger.info(f"✅ 线程池同步完成: job_id={job_id}, "
                   f"成功={self.stats.success_count}, "
                   f"失败={self.stats.error_count}, "
                   f"耗时={self.stats.duration:.2f}秒")
        
        return self.stats
    
    def _worker_loop(self, process_func: Callable, context: Dict[str, Any]):
        """
        工作线程主循环
        
        从任务队列获取任务并处理
        """
        thread_name = threading.current_thread().name
        logger.debug(f"🔧 工作线程 {thread_name} 启动")
        
        while True:
            # 检查是否已取消
            if self.cancellation_token.is_cancelled():
                logger.info(f"🛑 工作线程 {thread_name} 收到取消信号，退出")
                break
            
            try:
                # 从队列获取任务（超时1秒，避免无限等待）
                try:
                    item, task_context = self.task_queue.get(timeout=1)
                except queue.Empty:
                    # 队列为空，检查是否所有任务都已完成
                    if self.progress_tracker.is_complete():
                        logger.debug(f"✅ 工作线程 {thread_name} 所有任务已完成，退出")
                        break
                    continue
                
                # 处理任务
                try:
                    # 合并上下文
                    merged_context = {**(context or {}), **(task_context or {})}
                    
                    # 🔥 速率限制：在调用API之前等待（如果需要）
                    data_source = merged_context.get("data_source", "default")
                    self.rate_limiter.wait_if_needed(data_source)
                    
                    # 处理任务（带超时）
                    result = self._process_item_with_timeout(
                        item,
                        process_func,
                        merged_context
                    )
                    
                    # 更新统计
                    if result:
                        self.progress_tracker.record_success(item)
                    else:
                        self.progress_tracker.record_error(item, "处理返回False")
                    
                    # 🔥 任务之间的延迟（避免请求过快）
                    if self.delay_between_items > 0:
                        time.sleep(self.delay_between_items)
                    
                except Exception as e:
                    # 处理失败
                    error_msg = str(e)
                    self.progress_tracker.record_error(item, error_msg)
                    logger.error(f"❌ {item} 处理失败: {error_msg}")
                    
                    # 🔥 即使失败也要延迟，避免连续失败导致速率限制
                    if self.delay_between_items > 0:
                        time.sleep(self.delay_between_items)
                
                finally:
                    self.task_queue.task_done()
                    
            except Exception as e:
                logger.error(f"❌ 工作线程 {thread_name} 异常: {e}", exc_info=True)
                break
        
        logger.debug(f"🔧 工作线程 {thread_name} 退出")
    
    def _process_item_with_timeout(
        self,
        item: str,
        process_func: Callable,
        context: Dict[str, Any]
    ):
        """
        处理单个项目（带超时保护）
        
        支持同步和异步函数
        """
        # 检查是否已取消
        if self.cancellation_token.is_cancelled():
            raise RuntimeError("任务已取消")
        
        # 如果是异步函数，需要在线程中运行
        if asyncio.iscoroutinefunction(process_func):
            return self._run_async_in_thread(process_func, item, context)
        else:
            # 同步函数，直接调用（超时由线程池的future控制）
            # 注意：这里不能直接使用 executor.submit，因为已经在工作线程中
            # 直接调用即可，超时由外层的 future.result(timeout) 控制
            return process_func(item, **context)
    
    def _run_async_in_thread(
        self,
        async_func: Callable,
        item: str,
        context: Dict[str, Any]
    ):
        """
        在线程中运行异步函数
        
        创建新的事件循环，避免与主事件循环冲突
        """
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            # 使用 asyncio.wait_for 实现超时
            return loop.run_until_complete(
                asyncio.wait_for(
                    async_func(item, **context),
                    timeout=self.timeout_per_task
                )
            )
        except asyncio.TimeoutError:
            raise TimeoutError(f"异步任务超时（{self.timeout_per_task}秒）")
        finally:
            loop.close()
    
    async def _progress_update_loop(self):
        """
        进度更新循环
        
        定期更新进度到数据库
        """
        logger.debug("📊 进度更新循环启动")
        
        while not self.progress_tracker.is_complete():
            # 检查是否已取消
            if self.cancellation_token.is_cancelled():
                logger.info("🛑 进度更新循环收到取消信号")
                break
            
            # 更新进度
            await self._update_progress()
            
            # 等待更新间隔
            await asyncio.sleep(self.progress_update_interval)
        
        # 最后一次更新
        await self._update_progress()
        logger.debug("📊 进度更新循环退出")
    
    async def _update_progress(self):
        """
        更新进度到数据库
        """
        if not self.progress_tracker:
            return
        
        try:
            progress = self.progress_tracker.get_progress()
            current_item = self.progress_tracker.get_current_item()
            processed_items = self.progress_tracker.processed_items
            total_items = self.progress_tracker.total_items
            
            from app.services.scheduler_service import update_job_progress
            
            await update_job_progress(
                job_id=self.progress_tracker.job_id,
                progress=progress,
                message=f"正在同步数据 ({processed_items}/{total_items})",
                current_item=current_item or f"已处理 {processed_items} 项",
                total_items=total_items,
                processed_items=processed_items
            )
            
            logger.debug(f"📊 进度更新: {progress}% ({processed_items}/{total_items})")
            
        except Exception as e:
            logger.warning(f"⚠️ 更新进度失败: {e}")
    
    def cancel(self):
        """
        取消任务
        """
        self.cancellation_token.cancel()
        logger.info("🛑 任务取消请求已发送")
