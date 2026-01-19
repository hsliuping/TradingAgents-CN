"""
分析任务Worker进程
消费队列中的分析任务，调用TradingAgents进行股票分析
"""

import asyncio
import logging
import signal
import sys
import uuid
import traceback
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from app.services.queue_service import get_queue_service
from app.services.analysis_service import get_analysis_service
from app.core.database import init_database, close_database
from app.core.redis_client import init_redis, close_redis
from app.core.config import settings
from app.models.analysis import AnalysisTask, AnalysisParameters
from app.services.config_provider import provider as config_provider
from app.services.queue import DEFAULT_USER_CONCURRENT_LIMIT, GLOBAL_CONCURRENT_LIMIT, VISIBILITY_TIMEOUT_SECONDS

logger = logging.getLogger(__name__)


class AnalysisWorker:
    """分析任务Worker类"""

    def __init__(self, worker_id: Optional[str] = None):
        self.worker_id = worker_id or f"worker-{uuid.uuid4().hex[:8]}"
        self.queue_service = None
        self.running = False
        self.current_task = None

        # 配置参数（可由系统设置覆盖）
        self.heartbeat_interval = int(getattr(settings, 'WORKER_HEARTBEAT_INTERVAL', 30))
        self.max_retries = int(getattr(settings, 'QUEUE_MAX_RETRIES', 3))
        self.poll_interval = float(getattr(settings, 'QUEUE_POLL_INTERVAL_SECONDS', 1))  # 队列轮询间隔（秒）
        self.cleanup_interval = float(getattr(settings, 'QUEUE_CLEANUP_INTERVAL_SECONDS', 60))

        # 注册信号处理器
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)

    def _signal_handler(self, signum, frame):
        """信号处理器，优雅关闭"""
        logger.info(f"收到信号 {signum}，准备关闭Worker...")
        self.running = False

    async def start(self):
        """启动Worker"""
        try:
            logger.info(f"🚀 启动分析Worker: {self.worker_id}")

            # 初始化数据库连接
            await init_database()
            await init_redis()

            # 读取系统设置（ENV 优先 → DB）
            try:
                effective_settings = await config_provider.get_effective_system_settings()
            except Exception:
                effective_settings = {}

            # 获取队列服务
            self.queue_service = get_queue_service()

            self.running = True

            # 应用队列并发/超时配置 + Worker/轮询参数
            try:
                self.queue_service.user_concurrent_limit = int(effective_settings.get("max_concurrent_tasks", DEFAULT_USER_CONCURRENT_LIMIT))
                self.queue_service.global_concurrent_limit = int(effective_settings.get("max_concurrent_tasks", GLOBAL_CONCURRENT_LIMIT))
                self.queue_service.visibility_timeout = int(effective_settings.get("default_analysis_timeout", VISIBILITY_TIMEOUT_SECONDS))
                # Worker intervals
                self.heartbeat_interval = int(effective_settings.get("worker_heartbeat_interval_seconds", self.heartbeat_interval))
                self.poll_interval = float(effective_settings.get("queue_poll_interval_seconds", self.poll_interval))
                self.cleanup_interval = float(effective_settings.get("queue_cleanup_interval_seconds", self.cleanup_interval))
            except Exception:
                pass
            # 启动心跳任务
            heartbeat_task = asyncio.create_task(self._heartbeat_loop())

            # 启动清理任务
            cleanup_task = asyncio.create_task(self._cleanup_loop())

            # 主工作循环
            await self._work_loop()

            # 取消后台任务
            heartbeat_task.cancel()
            cleanup_task.cancel()

            try:
                await heartbeat_task
                await cleanup_task
            except asyncio.CancelledError:
                pass

        except Exception as e:
            logger.error(f"Worker启动失败: {e}")
            raise
        finally:
            await self._cleanup()

    async def _work_loop(self):
        """主工作循环"""
        logger.info(f"✅ Worker {self.worker_id} 开始工作")

        while self.running:
            try:
                # 从队列获取任务
                task_data = await self.queue_service.dequeue_task(self.worker_id)

                if task_data:
                    await self._process_task(task_data)
                else:
                    # 没有任务，短暂休眠
                    await asyncio.sleep(self.poll_interval)

            except Exception as e:
                logger.error(f"工作循环异常: {e}")
                await asyncio.sleep(5)  # 异常后等待5秒再继续

        logger.info(f"🔄 Worker {self.worker_id} 工作循环结束")

    async def _process_task(self, task_data: Dict[str, Any]):
        """处理单个任务"""
        task_id = task_data.get("id")
        stock_code = task_data.get("symbol")
        user_id = task_data.get("user")

        logger.info(f"📊 开始处理任务: {task_id} - {stock_code}")

        self.current_task = task_id
        success = False

        try:
            # 解析任务参数
            parameters_dict = task_data.get("parameters", {})
            if isinstance(parameters_dict, str):
                import json
                parameters_dict = json.loads(parameters_dict)
            
            # 检查引擎类型
            engine_type = parameters_dict.get("engine", "legacy")
            
            if engine_type == "v2":
                # v2 引擎：使用统一任务服务
                logger.info(f"🔧 [Worker] 使用 v2 引擎执行任务: {task_id}")
                from app.services.task_analysis_service import get_task_analysis_service
                task_service = get_task_analysis_service()
                
                # 获取任务对象
                task = await task_service.get_task(task_id)
                if not task:
                    raise ValueError(f"任务不存在: {task_id}")
                
                # 执行任务
                await task_service.execute_task(task, progress_callback=self._progress_callback)
                success = True
                logger.info(f"✅ [v2引擎] 任务完成: {task_id}")
                
            elif engine_type == "unified":
                # unified 引擎：使用统一分析服务
                logger.info(f"🔧 [Worker] 使用 unified 引擎执行任务: {task_id}")
                from app.services.unified_analysis_service import get_unified_analysis_service
                from app.models.analysis import SingleAnalysisRequest
                
                unified_service = get_unified_analysis_service()
                
                # 构建 SingleAnalysisRequest
                single_req = SingleAnalysisRequest(
                    symbol=stock_code,
                    stock_code=stock_code,
                    parameters=AnalysisParameters(**parameters_dict) if parameters_dict else None
                )
                
                # 执行分析
                await unified_service.execute_analysis_for_ab_test(
                    task_id=task_id,
                    user_id=user_id,
                    request=single_req
                )
                success = True
                logger.info(f"✅ [unified引擎] 任务完成: {task_id}")
                
            else:
                # legacy 引擎：使用旧的分析服务
                logger.info(f"🔧 [Worker] 使用 legacy 引擎执行任务: {task_id}")
                parameters = AnalysisParameters(**parameters_dict)

                task = AnalysisTask(
                    task_id=task_id,
                    user_id=user_id,
                    stock_code=stock_code,
                    batch_id=task_data.get("batch_id"),
                    parameters=parameters
                )

                # 执行分析
                result = await get_analysis_service().execute_analysis_task(
                    task,
                    progress_callback=self._progress_callback
                )

                success = True
                logger.info(f"✅ [legacy引擎] 任务完成: {task_id} - 耗时: {result.execution_time:.2f}秒")

        except Exception as e:
            logger.error(f"❌ 任务执行失败: {task_id} - {e}")
            logger.error(traceback.format_exc())

        finally:
            # 确认任务完成
            try:
                await self.queue_service.ack_task(task_id, success)
            except Exception as e:
                logger.error(f"确认任务失败: {task_id} - {e}")

            self.current_task = None

    def _progress_callback(self, progress: int, message: str):
        """进度回调函数"""
        logger.debug(f"任务进度 {self.current_task}: {progress}% - {message}")

    async def _heartbeat_loop(self):
        """心跳循环"""
        while self.running:
            try:
                await self._send_heartbeat()
                await asyncio.sleep(self.heartbeat_interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"心跳异常: {e}")
                await asyncio.sleep(5)

    async def _send_heartbeat(self):
        """发送心跳"""
        try:
            from app.core.redis_client import get_redis_service
            redis_service = get_redis_service()

            heartbeat_data = {
                "worker_id": self.worker_id,
                "timestamp": datetime.utcnow().isoformat(),
                "current_task": self.current_task,
                "status": "active" if self.running else "stopping"
            }

            heartbeat_key = f"worker:{self.worker_id}:heartbeat"
            await redis_service.set_json(heartbeat_key, heartbeat_data, ttl=self.heartbeat_interval * 2)

        except Exception as e:
            logger.error(f"发送心跳失败: {e}")

    async def _cleanup_loop(self):
        """清理循环，定期清理过期任务"""
        while self.running:
            try:
                await asyncio.sleep(self.cleanup_interval)  # 清理间隔（秒），可配
                if self.queue_service:
                    await self.queue_service.cleanup_expired_tasks()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"清理任务异常: {e}")

    async def _cleanup(self):
        """清理资源"""
        logger.info(f"🧹 清理Worker资源: {self.worker_id}")

        try:
            # 清理心跳记录
            from app.core.redis_client import get_redis_service
            redis_service = get_redis_service()
            heartbeat_key = f"worker:{self.worker_id}:heartbeat"
            await redis_service.redis.delete(heartbeat_key)
        except Exception as e:
            logger.error(f"清理心跳记录失败: {e}")

        try:
            # 关闭数据库连接
            await close_database()
            await close_redis()
        except Exception as e:
            logger.error(f"关闭数据库连接失败: {e}")


async def main():
    """主函数"""
    # 设置日志
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    # 创建并启动Worker
    worker = AnalysisWorker()

    try:
        await worker.start()
    except KeyboardInterrupt:
        logger.info("收到中断信号，正在关闭...")
    except Exception as e:
        logger.error(f"Worker异常退出: {e}")
        sys.exit(1)

    logger.info("Worker已安全退出")


if __name__ == "__main__":
    asyncio.run(main())
