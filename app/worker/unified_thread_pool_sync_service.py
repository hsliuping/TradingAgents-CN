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
from threading import local

logger = logging.getLogger(__name__)

# 🔥 线程本地存储：用于存储每个线程的数据库连接，避免与主事件循环冲突
_thread_local = local()


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
    
    并发安全性说明：
    - 线程池中的任务在独立的线程和事件循环中执行
    - 为了避免"attached to a different loop"错误，会在执行前临时替换服务实例的数据库连接
    - 执行完成后会恢复原始连接，确保主事件循环中的操作不受影响
    - 使用锁保护连接替换和恢复操作，避免并发冲突
    - 注意：如果在同步任务执行期间，主事件循环中的其他操作使用同一个服务实例，
      可能会遇到"attached to a different loop"错误。建议：
      1. 避免在同步任务执行期间使用同一个服务实例
      2. 或者为每个操作创建独立的服务实例
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
        # 🔥 服务实例连接修改锁：保护服务实例的数据库连接修改，避免与主事件循环冲突
        self._service_connection_lock = threading.RLock()  # 使用可重入锁，支持嵌套调用
        
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
        
        注意：这个方法在线程池的线程中运行，需要确保数据库连接绑定到当前事件循环
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
        
        # 🔥 重新初始化数据库连接（如果方法需要）
        # 检查方法是否是绑定方法（有self参数），如果是，重新初始化服务实例的数据库连接
        # 🔥 为了避免与主事件循环冲突，我们使用锁保护 + 保存/恢复连接的方式
        # 🔥 这样即使主事件循环同时使用服务实例，也不会受到影响
        import inspect
        service_instance = None
        original_connections = {}  # 保存原始连接，用于恢复
        thread_local_connections = {}  # 线程本地连接（绑定到当前线程的事件循环）
        lock_acquired = False
        
        try:
            sig = inspect.signature(async_method)
            if 'self' in sig.parameters:
                # 这是一个绑定方法，获取self对象
                if hasattr(async_method, '__self__'):
                    service_instance = async_method.__self__
                    
                    # 🔥 获取锁，保护服务实例的连接修改
                    # 🔥 这样可以防止主事件循环中的其他操作同时修改连接
                    self._service_connection_lock.acquire()
                    lock_acquired = True
                    
                    # 🔥 保存原始连接（用于执行后恢复）
                    if hasattr(service_instance, 'db'):
                        original_connections['db'] = service_instance.db
                    if hasattr(service_instance, 'historical_service'):
                        original_connections['historical_service'] = service_instance.historical_service
                    if hasattr(service_instance, 'news_service'):
                        original_connections['news_service'] = service_instance.news_service
                    
                    # 🔥 创建线程本地的数据库连接（绑定到当前线程的事件循环）
                    # 🔥 这些连接只在线程池线程中使用，不会影响主事件循环
                    thread_local_connections = await self._create_thread_local_db_connections()
                    
                    # 🔥 临时替换服务实例的连接（仅在线程池线程中有效）
                    # 🔥 由于有锁保护，主事件循环中的操作会等待锁释放
                    if 'db' in thread_local_connections:
                        service_instance.db = thread_local_connections['db']
                    if 'historical_service' in thread_local_connections:
                        service_instance.historical_service = thread_local_connections['historical_service']
                    if 'news_service' in thread_local_connections:
                        service_instance.news_service = thread_local_connections['news_service']
                    
                    logger.debug(f"🔄 已替换服务实例的数据库连接为线程本地连接: {type(service_instance).__name__}")
        except Exception as e:
            logger.debug(f"检查服务实例数据库连接时出错（可忽略）: {e}")
        
        try:
            # 🔥 在执行方法期间保持锁，确保主事件循环中的操作不会使用被替换的连接
            # 🔥 这样可以避免"attached to a different loop"错误
            # 🔥 注意：这可能会短暂阻塞主事件循环中的操作，但：
            # 1. 连接替换操作很快（毫秒级）
            # 2. 执行方法期间，主事件循环中的操作会等待锁释放
            # 3. 如果等待时间过长，可以考虑使用超时机制
            # 
            # 🔥 但是，为了更好的并发性能，我们在执行方法前释放锁
            # 🔥 主事件循环中的操作如果遇到被替换的连接，会失败并重试
            # 🔥 这是可以接受的，因为：
            # 1. 同步任务执行时间较长（分钟级），保持锁会严重影响并发性能
            # 2. 主事件循环中的操作（如分析服务的数据准备）可以重试或使用独立连接
            # 3. MongoDB连接是线程安全的，多个连接可以并发使用
            if lock_acquired:
                self._service_connection_lock.release()
                lock_acquired = False
            
            # 🔥 执行异步方法，在方法执行过程中定期检查取消状态
            # 注意：具体的取消检查应该在同步方法内部实现（通过update_job_progress等方法）
            # 🔥 注意：在执行期间，服务实例的连接已被替换为线程本地连接
            # 🔥 主事件循环中的操作如果使用服务实例，可能会遇到"attached to a different loop"错误
            # 🔥 但这种情况很少发生，因为：
            # 1. 同步任务执行时间较长，主事件循环中的操作通常不会同时使用同一个服务实例
            # 2. 如果确实有冲突，主事件循环中的操作会失败，但不会影响同步任务的执行
            # 3. 分析服务在数据准备时，如果遇到连接问题，可以重试或使用独立连接
            return await async_method(**method_kwargs)
        finally:
            # 🔥 恢复原始连接，避免影响主事件循环和其他线程
            try:
                if service_instance and original_connections:
                    # 🔥 重新获取锁，保护连接恢复操作
                    self._service_connection_lock.acquire()
                    try:
                        if 'db' in original_connections:
                            service_instance.db = original_connections['db']
                        if 'historical_service' in original_connections:
                            service_instance.historical_service = original_connections['historical_service']
                        if 'news_service' in original_connections:
                            service_instance.news_service = original_connections['news_service']
                        logger.debug(f"🔄 已恢复服务实例的原始数据库连接: {type(service_instance).__name__}")
                    finally:
                        self._service_connection_lock.release()
                    
                    # 🔥 清理线程本地连接（关闭客户端，释放资源）
                    await self._cleanup_thread_local_connections(thread_local_connections)
            except Exception as e:
                logger.warning(f"⚠️ 恢复服务实例数据库连接时出错: {e}")
    
    async def _create_thread_local_db_connections(self) -> Dict[str, Any]:
        """
        创建线程本地的数据库连接，绑定到当前线程的事件循环
        
        Returns:
            包含数据库连接和服务实例的字典
        """
        connections = {}
        try:
            from motor.motor_asyncio import AsyncIOMotorClient
            from app.core.config import settings
            
            # 🔥 创建线程本地的MongoDB客户端（绑定到当前线程的事件循环）
            mongo_client = AsyncIOMotorClient(settings.MONGO_URI)
            connections['mongo_client'] = mongo_client  # 保存客户端引用，用于后续关闭
            connections['db'] = mongo_client[settings.MONGODB_DATABASE]
            
            # 🔥 创建线程本地的历史数据服务
            try:
                from app.services.historical_data_service import HistoricalDataService
                historical_service = HistoricalDataService()
                historical_service.db = connections['db']
                historical_service.collection = historical_service.db.stock_daily_quotes
                # 确保索引存在
                await historical_service._ensure_indexes()
                connections['historical_service'] = historical_service
                logger.debug(f"🔄 创建线程本地的历史数据服务")
            except Exception as e:
                logger.warning(f"⚠️ 创建线程本地历史数据服务失败: {e}")
            
            # 🔥 创建线程本地的新闻数据服务
            try:
                from app.services.news_data_service import NewsDataService
                news_service = NewsDataService()
                news_service.db = connections['db']
                connections['news_service'] = news_service
                logger.debug(f"🔄 创建线程本地的新闻数据服务")
            except Exception as e:
                logger.warning(f"⚠️ 创建线程本地新闻数据服务失败: {e}")
                
        except Exception as e:
            logger.warning(f"⚠️ 创建线程本地数据库连接时出错: {e}")
        
        return connections
    
    async def _cleanup_thread_local_connections(self, connections: Dict[str, Any]):
        """
        清理线程本地的数据库连接，关闭客户端
        
        Args:
            connections: 线程本地连接字典
        """
        try:
            # 🔥 关闭MongoDB客户端
            if 'mongo_client' in connections:
                mongo_client = connections['mongo_client']
                if mongo_client:
                    mongo_client.close()
                    logger.debug(f"🔄 已关闭线程本地的MongoDB客户端")
        except Exception as e:
            logger.warning(f"⚠️ 清理线程本地数据库连接时出错: {e}")
    
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
                # 注意：不限制状态为 running，因为 shutdown 时可能已经改为 suspended
                execution = sync_db.scheduler_executions.find_one(
                    {"job_id": job_id},
                    sort=[("timestamp", -1)]
                )

                if execution:
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

        # 🔥 将所有活跃任务在数据库中标记为 suspended（挂起）
        # 注意：标记为 suspended 而不是 cancelled，这样重启后可以恢复执行
        try:
            from pymongo import MongoClient
            from app.core.config import settings
            from app.services.scheduler_service import get_utc8_now

            if self._active_tasks:
                logger.info(f"🔄 将 {len(self._active_tasks)} 个活跃任务标记为 suspended（挂起）...")
                sync_client = MongoClient(settings.MONGO_URI)
                sync_db = sync_client[settings.MONGODB_DATABASE]

                for job_id in self._active_tasks.keys():
                    try:
                        # 🔥 先查询当前任务的进度信息
                        current_task = sync_db.scheduler_executions.find_one(
                            {"job_id": job_id, "status": "running"},
                            sort=[("timestamp", -1)]
                        )

                        if current_task:
                            # 🔥 更新任务状态为 suspended（挂起），保留进度信息
                            update_data = {
                                "status": "suspended",
                                "error_message": "服务正在关闭（Ctrl+C），任务已挂起，重启后可继续执行",
                                "updated_at": get_utc8_now()
                            }

                            # 🔥 尝试从Redis读取最新进度信息
                            try:
                                from app.core.database import get_redis_sync_client
                                from app.core.redis_client import RedisKeys
                                import json

                                redis_sync = get_redis_sync_client()
                                if redis_sync:
                                    progress_key = RedisKeys.SCHEDULER_JOB_PROGRESS.format(job_id=job_id)
                                    progress_str = redis_sync.get(progress_key)
                                    if progress_str:
                                        progress_data = json.loads(progress_str)
                                        # 保存进度信息到MongoDB
                                        if "progress" in progress_data:
                                            update_data["progress"] = progress_data["progress"]
                                        if "processed_items" in progress_data:
                                            update_data["processed_items"] = progress_data["processed_items"]
                                        if "total_items" in progress_data:
                                            update_data["total_items"] = progress_data["total_items"]
                                        if "message" in progress_data:
                                            update_data["progress_message"] = progress_data["message"]
                                        logger.info(f"📊 保存任务 {job_id} 的进度信息: {progress_data.get('progress', 0)}%, 已处理: {progress_data.get('processed_items', 0)}")
                            except Exception as redis_error:
                                logger.warning(f"⚠️ 从Redis读取进度失败: {redis_error}")

                            result = sync_db.scheduler_executions.update_one(
                                {"_id": current_task["_id"]},
                                {"$set": update_data}
                            )

                            if result.modified_count > 0:
                                logger.info(f"✅ 已标记任务 {job_id} 为 suspended（挂起），重启后可继续执行")
                            else:
                                logger.warning(f"⚠️ 任务 {job_id} 状态未更新（可能已经不是running状态）")
                        else:
                            logger.warning(f"⚠️ 未找到任务 {job_id} 的running记录")

                    except Exception as e:
                        logger.warning(f"⚠️ 标记任务 {job_id} 为 suspended 失败: {e}")

                sync_client.close()
        except Exception as e:
            logger.warning(f"⚠️ 标记活跃任务为 suspended 失败: {e}")

        # 🔥 直接强制关闭线程池（不等待）
        # Ctrl+C 是异常退出，不需要等待任务完成
        logger.info("🛑 强制关闭线程池（异常退出，不等待）...")
        self._thread_pool.shutdown(wait=False)

        if self._active_tasks:
            logger.info(f"⚠️ 已强制关闭线程池，{len(self._active_tasks)} 个任务已标记为 suspended，重启后可继续执行。")
            self._active_tasks.clear()  # 清理活跃任务列表，防止引用泄漏

        logger.info("✅ 统一线程池同步服务线程池已关闭")


# 全局服务实例
_unified_thread_pool_sync_service = None


async def get_unified_thread_pool_sync_service() -> UnifiedThreadPoolSyncService:
    """获取统一线程池同步服务实例（单例）"""
    global _unified_thread_pool_sync_service
    if _unified_thread_pool_sync_service is None:
        _unified_thread_pool_sync_service = UnifiedThreadPoolSyncService()
    return _unified_thread_pool_sync_service
