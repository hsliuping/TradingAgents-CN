"""
Worker 服务 - 基于 FastAPI 的分析任务处理服务

使用 Uvicorn 运行，与 Backend 相同的架构，更稳定可靠。

启动方式：
    python -m uvicorn app.worker.worker_app:app --host 0.0.0.0 --port 8001
"""

import asyncio
import logging
import sys
from pathlib import Path
from datetime import datetime
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI
from fastapi.responses import JSONResponse

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from app.core.database import init_database, close_database
from app.core.redis_client import init_redis, close_redis
from app.core.config import settings
from app.worker.analysis_worker import AnalysisWorker

logger = logging.getLogger(__name__)

# Worker 实例
_worker: Optional[AnalysisWorker] = None
_worker_task: Optional[asyncio.Task] = None
_start_time: Optional[datetime] = None


async def start_worker():
    """启动 Worker 任务处理循环"""
    global _worker, _worker_task
    
    logger.info("🚀 启动 Worker 任务处理...")
    
    _worker = AnalysisWorker()
    
    # 在后台运行 worker
    _worker_task = asyncio.create_task(_worker.start())
    
    logger.info("✅ Worker 任务处理已启动")


async def stop_worker():
    """停止 Worker"""
    global _worker, _worker_task
    
    logger.info("🛑 停止 Worker...")
    
    if _worker:
        _worker.running = False
    
    if _worker_task:
        _worker_task.cancel()
        try:
            await _worker_task
        except asyncio.CancelledError:
            pass
    
    logger.info("✅ Worker 已停止")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """FastAPI 生命周期管理"""
    global _start_time
    _start_time = datetime.now()
    
    # 启动时
    logger.info("=" * 60)
    logger.info("🔧 Worker 服务启动中...")
    logger.info(f"   Python: {sys.executable}")
    logger.info(f"   工作目录: {Path.cwd()}")
    logger.info("=" * 60)
    
    # 初始化数据库和 Redis
    await init_database()
    await init_redis()
    
    # 启动 Worker
    await start_worker()
    
    logger.info("✅ Worker 服务启动完成")
    
    yield
    
    # 关闭时
    logger.info("🛑 Worker 服务关闭中...")
    
    await stop_worker()
    await close_redis()
    await close_database()
    
    logger.info("✅ Worker 服务已关闭")


# 创建 FastAPI 应用
app = FastAPI(
    title="TradingAgents Worker Service",
    description="分析任务处理服务",
    version="2.0.0",
    lifespan=lifespan,
)


@app.get("/")
async def root():
    """根路径"""
    return {"service": "worker", "status": "running"}


@app.get("/health")
async def health_check():
    """健康检查"""
    global _worker, _worker_task, _start_time

    status = "healthy"
    worker_status = "unknown"

    if _worker:
        if _worker.running:
            worker_status = "running"
        elif _worker_task and not _worker_task.done():
            worker_status = "initializing"
            status = "starting"
        else:
            worker_status = "stopped"
            status = "degraded"
    else:
        status = "starting"
        worker_status = "not_created"

    uptime = None
    if _start_time:
        uptime = (datetime.now() - _start_time).total_seconds()

    return {
        "status": status,
        "worker_status": worker_status,
        "uptime_seconds": uptime,
        "timestamp": datetime.now().isoformat(),
    }


@app.get("/status")
async def worker_status():
    """Worker 详细状态"""
    global _worker, _start_time
    
    if not _worker:
        return JSONResponse(
            status_code=503,
            content={"error": "Worker not initialized"}
        )
    
    return {
        "worker_id": _worker.worker_id,
        "running": _worker.running,
        "current_task": str(_worker.current_task) if _worker.current_task else None,
        "running_tasks_count": len(_worker.running_tasks) if hasattr(_worker, 'running_tasks') else 0,
        "max_concurrent_tasks": _worker.max_concurrent_tasks,
        "start_time": _start_time.isoformat() if _start_time else None,
        "uptime_seconds": (datetime.now() - _start_time).total_seconds() if _start_time else None,
    }

