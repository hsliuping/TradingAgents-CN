"""
线程池任务处理器
使用 ThreadPoolExecutor 在 Backend 进程内处理队列任务
"""

import asyncio
import logging
import threading
from concurrent.futures import ThreadPoolExecutor
from typing import Optional, Dict, Any
from datetime import datetime

from app.core.database import get_mongo_db, get_redis_client
from app.services.queue_service import QueueService
from app.services.task_analysis_service import TaskAnalysisService
from app.models.analysis import AnalysisTask

logger = logging.getLogger(__name__)


class ThreadWorker:
    """线程池任务处理器"""
    
    def __init__(self, max_workers: int = 3):
        """
        初始化线程池 Worker
        
        Args:
            max_workers: 最大并发线程数（默认 3）
        """
        self.max_workers = max_workers
        self.executor: Optional[ThreadPoolExecutor] = None
        self.running = False
        self.worker_id = f"thread-worker-{threading.get_ident()}"
        self.queue_service: Optional[QueueService] = None
        self.task_service: Optional[TaskAnalysisService] = None
        self._loop_task: Optional[asyncio.Task] = None
        
        logger.info(f"🔧 ThreadWorker 初始化: max_workers={max_workers}")
    
    async def start(self):
        """启动线程池 Worker"""
        if self.running:
            logger.warning("ThreadWorker 已经在运行")
            return
        
        logger.info("=" * 60)
        logger.info("🚀 启动线程池 Worker...")
        logger.info(f"   最大并发数: {self.max_workers}")
        logger.info(f"   Worker ID: {self.worker_id}")
        logger.info("=" * 60)
        
        # 初始化服务
        redis = get_redis_client()
        self.queue_service = QueueService(redis)
        self.task_service = TaskAnalysisService()
        
        # 创建线程池
        self.executor = ThreadPoolExecutor(
            max_workers=self.max_workers,
            thread_name_prefix="analysis-worker"
        )
        
        self.running = True
        
        # 启动队列监听循环
        self._loop_task = asyncio.create_task(self._queue_loop())
        
        logger.info("✅ 线程池 Worker 启动成功")
    
    async def stop(self):
        """停止线程池 Worker"""
        if not self.running:
            return
        
        logger.info("🛑 停止线程池 Worker...")
        self.running = False
        
        # 取消队列循环
        if self._loop_task:
            self._loop_task.cancel()
            try:
                await self._loop_task
            except asyncio.CancelledError:
                pass
        
        # 关闭线程池
        if self.executor:
            logger.info("   等待线程池任务完成...")
            self.executor.shutdown(wait=True, cancel_futures=False)
            logger.info("   线程池已关闭")
        
        logger.info("✅ 线程池 Worker 已停止")
    
    async def _queue_loop(self):
        """队列监听循环"""
        logger.info("📡 队列监听循环启动")

        while self.running:
            try:
                # 从队列获取任务
                task_data = await self.queue_service.dequeue_task(self.worker_id)

                if not task_data:
                    # 队列为空，等待一会儿
                    await asyncio.sleep(1)
                    continue

                # 提交任务到线程池（不等待完成）
                task_id = task_data.get("id")
                logger.info(f"📊 收到任务: {task_id}, 提交到线程池...")

                # 🔥 直接在当前事件循环中处理任务（不使用线程池）
                # 因为任务本身是 I/O 密集型，asyncio 已经提供了并发能力
                asyncio.create_task(self._process_task_async(task_data))

            except asyncio.CancelledError:
                logger.info("队列循环被取消")
                break
            except Exception as e:
                logger.error(f"队列循环错误: {e}", exc_info=True)
                await asyncio.sleep(1)

        logger.info("📡 队列监听循环结束")
    


    async def _process_task_async(self, task_data: Dict[str, Any]):
        """
        异步处理任务

        Args:
            task_data: 任务数据
        """
        task_id = task_data.get("id")
        stock_code = task_data.get("symbol")
        user_id = task_data.get("user")

        logger.info(f"🔧 开始处理任务: {task_id} - {stock_code}")

        success = False

        try:
            # 解析任务参数
            parameters_dict = task_data.get("params", {})
            if isinstance(parameters_dict, str):
                import json
                parameters_dict = json.loads(parameters_dict)

            # 检查引擎类型（默认使用 v2 引擎）
            engine_type = parameters_dict.get("engine", "v2")

            logger.info(f"🔧 使用 {engine_type} 引擎执行任务: {task_id}")

            if engine_type == "v2":
                # 使用 v2.0 统一任务引擎
                from app.models.analysis import AnalysisTaskType
                from bson import ObjectId

                # 创建 AnalysisTask 对象
                task = AnalysisTask(
                    task_id=task_id,
                    user_id=ObjectId(user_id) if user_id else None,
                    symbol=stock_code,  # 🔥 必须字段
                    stock_code=stock_code,  # 🔥 兼容字段
                    task_type=AnalysisTaskType.STOCK_ANALYSIS,
                    status="processing",
                    engine="v2",
                    parameters=parameters_dict,
                    created_at=datetime.now()
                )

                # 执行任务
                await self.task_service.execute_task(task)
                logger.info(f"✅ [v2引擎] 任务完成: {task_id}")

            elif engine_type == "unified":
                # 使用统一分析服务
                from app.services.simple_analysis_service import UnifiedAnalysisService

                unified_service = UnifiedAnalysisService()
                await unified_service.analyze_stock(
                    stock_code=stock_code,
                    user_id=user_id,
                    task_id=task_id,
                    **parameters_dict
                )
                logger.info(f"✅ [unified引擎] 任务完成: {task_id}")

            else:
                # 使用 legacy 引擎
                from app.services.simple_analysis_service import SimpleAnalysisService

                simple_service = SimpleAnalysisService()
                await simple_service.analyze_stock(
                    stock_code=stock_code,
                    user_id=user_id,
                    task_id=task_id,
                    **parameters_dict
                )
                logger.info(f"✅ [legacy引擎] 任务完成: {task_id}")

            success = True

        except Exception as e:
            logger.error(f"❌ 任务执行失败: {task_id} - {e}", exc_info=True)
            success = False

        finally:
            # 确认任务完成（无论成功或失败）
            try:
                await self.queue_service.confirm_task(task_id, success)
                logger.info(f"✅ 任务已确认: {task_id} (成功: {success})")
            except Exception as e:
                logger.error(f"❌ 确认任务失败: {task_id} - {e}")


# 全局 ThreadWorker 实例
_thread_worker: Optional[ThreadWorker] = None


async def start_thread_worker(max_workers: int = 3):
    """启动全局线程池 Worker"""
    global _thread_worker

    if _thread_worker is not None:
        logger.warning("ThreadWorker 已经启动")
        return

    _thread_worker = ThreadWorker(max_workers=max_workers)
    await _thread_worker.start()


async def stop_thread_worker():
    """停止全局线程池 Worker"""
    global _thread_worker

    if _thread_worker is None:
        return

    await _thread_worker.stop()
    _thread_worker = None


def get_thread_worker() -> Optional[ThreadWorker]:
    """获取全局线程池 Worker 实例"""
    return _thread_worker

