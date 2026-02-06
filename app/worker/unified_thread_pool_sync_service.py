#!/usr/bin/env python3
"""
统一线程池同步服务
可以执行任何同步方法，处理进度更新、取消、错误等通用逻辑
"""
import asyncio
import logging
import threading
import concurrent.futures
from datetime import datetime, timezone
from typing import Dict, Any, Callable, Optional
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class SyncTaskResult:
    """同步任务结果"""
    success: bool = False
    result: Any = None
    error: Optional[str] = None
    duration: float = 0.0
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None


class UnifiedThreadPoolSyncService:
    """
    统一线程池同步服务
    
    可以执行任何同步方法，统一处理：
    - 进度更新
    - 任务取消
    - 错误处理
    - 断点恢复
    - 速率限制
    
    使用方式：
        service = UnifiedThreadPoolSyncService()
        result = await service.execute_sync_method(
            sync_method=akshare_service.sync_historical_data,
            method_kwargs={"incremental": True, "period": "daily"},
            job_id="akshare_historical_sync",
            progress_callback=update_progress_func
        )
    """
    
    def __init__(self, max_workers: int = 10):
        """
        Args:
            max_workers: 线程池最大工作线程数
        """
        self.max_workers = max_workers
        # 🔥 全局线程池：用于执行同步任务
        self._thread_pool = concurrent.futures.ThreadPoolExecutor(max_workers=max_workers)
        self._shutdown_event = threading.Event()  # 🔥 用于通知线程退出
        self._active_tasks = {}  # 🔥 跟踪活跃任务：{job_id: future}
        
    async def execute_sync_method(
        self,
        sync_method: Callable,
        method_kwargs: Dict[str, Any] = None,
        job_id: str = None,
        progress_callback: Optional[Callable] = None,
        rate_limit_per_minute: int = 80,
        resume_from_index: int = None
    ) -> SyncTaskResult:
        """
        在线程池中执行同步方法
        
        Args:
            sync_method: 要执行的同步方法（可以是同步或异步方法）
            method_kwargs: 传递给同步方法的关键字参数
            job_id: 任务ID，用于进度跟踪和取消
            progress_callback: 进度回调函数（可选）
            rate_limit_per_minute: 速率限制（每分钟最大调用次数）
            resume_from_index: 恢复执行：从哪个位置继续（已处理的项数量）
            
        Returns:
            同步任务结果
        """
        if method_kwargs is None:
            method_kwargs = {}
        
        # 🔥 检查是否收到退出信号
        if self._shutdown_event.is_set():
            logger.warning(f"⚠️ 收到退出信号，任务 {job_id} 将不执行")
            result = SyncTaskResult()
            result.error = "服务正在关闭"
            return result
        
        # 🔥 如果指定了恢复位置，添加到参数中
        if resume_from_index is not None:
            method_kwargs["resume_from_index"] = resume_from_index
        
        result = SyncTaskResult()
        result.start_time = datetime.now(timezone.utc)
        
        loop = asyncio.get_event_loop()
        
        # 🔥 在线程池中执行同步方法
        task_future = loop.run_in_executor(
            self._thread_pool,
            self._execute_sync_method_sync,
            sync_method,
            method_kwargs,
            job_id,
            rate_limit_per_minute
        )
        
        # 🔥 记录活跃任务
        if job_id:
            self._active_tasks[job_id] = task_future
        
        try:
            # 等待任务完成
            method_result = await task_future
            
            result.success = True
            result.result = method_result
            
        except Exception as e:
            # 🔥 检查是否是任务取消异常
            from app.services.scheduler_service import TaskCancelledException
            if isinstance(e, TaskCancelledException) or "取消" in str(e) or "cancelled" in str(e).lower():
                logger.warning(f"🛑 任务 {job_id} 已被取消: {e}")
                result.error = f"任务已取消: {str(e)}"
            else:
                logger.error(f"❌ 任务 {job_id} 执行失败: {e}", exc_info=True)
                result.error = str(e)
        finally:
            # 任务完成后，从活跃任务列表中移除
            if job_id:
                self._active_tasks.pop(job_id, None)
            
            result.end_time = datetime.now(timezone.utc)
            if result.start_time:
                result.duration = (result.end_time - result.start_time).total_seconds()
        
        return result
    
    def _execute_sync_method_sync(
        self,
        sync_method: Callable,
        method_kwargs: Dict[str, Any],
        job_id: str,
        rate_limit_per_minute: int
    ) -> Any:
        """
        在线程池的线程中执行同步方法（同步版本）
        
        注意：这个方法在线程池的线程中运行，需要创建新的事件循环（如果是异步方法）
        """
        # 🔥 检查是否收到退出信号
        if self._shutdown_event.is_set():
            logger.warning(f"⚠️ 收到退出信号，任务 {job_id} 将不执行")
            raise RuntimeError("服务正在关闭")
        
        # 🔥 检查是否是异步方法
        if asyncio.iscoroutinefunction(sync_method):
            # 异步方法：需要创建新的事件循环
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
                # 在新事件循环中运行异步方法
                result = loop.run_until_complete(
                    self._execute_async_method_with_cancellation(
                        sync_method,
                        method_kwargs,
                        job_id
                    )
                )
                return result
            except RuntimeError as e:
                # 🔥 捕获事件循环相关的错误
                if "shutdown" in str(e).lower() or "closed" in str(e).lower():
                    logger.error(f"❌ 事件循环已关闭，无法继续执行: {e}")
                    raise RuntimeError(f"事件循环已关闭: {e}")
                raise
            finally:
                # 🔥 确保所有任务都完成后再关闭事件循环
                try:
                    if not loop.is_closed():
                        # 取消所有未完成的任务
                        pending_tasks = [task for task in asyncio.all_tasks(loop) if not task.done()]
                        if pending_tasks:
                            logger.warning(f"⚠️ 关闭事件循环前，还有 {len(pending_tasks)} 个未完成的任务")
                            for task in pending_tasks:
                                task.cancel()
                            # 等待任务取消完成（使用超时避免无限等待）
                            try:
                                loop.run_until_complete(asyncio.wait_for(
                                    asyncio.gather(*pending_tasks, return_exceptions=True),
                                    timeout=5.0
                                ))
                            except asyncio.TimeoutError:
                                logger.warning(f"⚠️ 等待任务取消超时，强制关闭事件循环")
                except RuntimeError as cleanup_error:
                    # 事件循环已关闭，忽略错误
                    if "shutdown" not in str(cleanup_error).lower() and "closed" not in str(cleanup_error).lower():
                        logger.warning(f"⚠️ 清理未完成任务时出错: {cleanup_error}")
                except Exception as cleanup_error:
                    logger.warning(f"⚠️ 清理未完成任务时出错: {cleanup_error}")
                
                # 关闭事件循环
                try:
                    if not loop.is_closed():
                        loop.close()
                        logger.debug(f"✅ 事件循环已关闭")
                except RuntimeError as close_error:
                    # 事件循环已关闭，忽略错误
                    if "shutdown" not in str(close_error).lower() and "closed" not in str(close_error).lower():
                        logger.warning(f"⚠️ 关闭事件循环时出错: {close_error}")
                except Exception as close_error:
                    logger.warning(f"⚠️ 关闭事件循环时出错: {close_error}")
        else:
            # 同步方法：直接调用
            return sync_method(**method_kwargs)
    
    async def _execute_async_method_with_cancellation(
        self,
        async_method: Callable,
        method_kwargs: Dict[str, Any],
        job_id: str
    ) -> Any:
        """
        执行异步方法，支持取消检查
        """
        # 🔥 检查是否收到退出信号
        if self._shutdown_event.is_set():
            raise RuntimeError("服务正在关闭")
        
        # 🔥 检查任务是否应该停止（通过查询数据库）
        if job_id:
            should_stop = await self._should_stop(job_id)
            if should_stop:
                from app.services.scheduler_service import TaskCancelledException
                raise TaskCancelledException(f"任务 {job_id} 已被取消")
        
        # 🔥 执行异步方法，在方法执行过程中定期检查取消状态
        # 注意：具体的取消检查应该在同步方法内部实现（通过update_job_progress等方法）
        return await async_method(**method_kwargs)
    
    async def _should_stop(self, job_id: str) -> bool:
        """
        检查任务是否应该停止
        
        Args:
            job_id: 任务ID
            
        Returns:
            是否应该停止
        """
        try:
            from app.core.database import get_mongo_db_sync
            from app.core.config import settings
            from pymongo import MongoClient
            
            # 🔥 使用同步客户端查询（避免事件循环冲突）
            sync_client = MongoClient(settings.MONGO_URI)
            sync_db = sync_client[settings.MONGODB_DATABASE]
            
            try:
                # 🔥 查询执行记录，检查 cancel_requested 标记和任务状态
                execution = sync_db.scheduler_executions.find_one(
                    {"job_id": job_id, "status": "running"},
                    sort=[("timestamp", -1)]
                )
                
                if execution:
                    # 检查取消请求标记
                    if execution.get("cancel_requested"):
                        logger.info(f"🛑 任务 {job_id} 收到取消请求，应停止执行")
                        return True
                    
                    # 🔥 检查任务状态：如果任务已被标记为失败或取消，也应该停止
                    status = execution.get("status")
                    if status in ["failed", "cancelled"]:
                        logger.info(f"🛑 任务 {job_id} 状态为 {status}，应停止执行")
                        return True
                
                return False
            finally:
                sync_client.close()
                
        except Exception as e:
            logger.error(f"❌ 检查任务停止标记失败: {e}")
            return False
    
    def shutdown(self, timeout: float = 30.0):
        """
        优雅关闭线程池
        
        Args:
            timeout: 等待线程完成的最大时间（秒）
        """
        logger.info("🛑 开始关闭统一线程池同步服务的线程池...")
        
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
                import time
                time.sleep(1)  # 给取消操作一个小的宽限期
        
        if self._active_tasks:
            logger.warning(f"⚠️ 仍有 {len(self._active_tasks)} 个任务未完成，可能需要强制退出。")
            self._active_tasks.clear()  # 清理活跃任务列表，防止引用泄漏
        else:
            logger.info("✅ 所有活跃任务已完成或已终止。")
            
        logger.info("✅ 统一线程池同步服务线程池已关闭")


# 全局服务实例
_unified_thread_pool_sync_service = None


async def get_unified_thread_pool_sync_service() -> UnifiedThreadPoolSyncService:
    """获取统一线程池同步服务实例（单例）"""
    global _unified_thread_pool_sync_service
    if _unified_thread_pool_sync_service is None:
        _unified_thread_pool_sync_service = UnifiedThreadPoolSyncService()
    return _unified_thread_pool_sync_service
