"""
TradingAgents-CN WebAPI Worker

Consumes tasks from Redis queue and processes them using actual stock analysis.
"""

import asyncio
import json
import logging
import signal
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Optional

# Add project root to path for importing analysis runner
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from app.core.logging_config import setup_logging
from app.core.database import init_db, close_db, get_redis_client
from app.core.config import settings

# Redis keys (must match queue_service)
READY_LIST = "qa:ready"
TASK_PREFIX = "qa:task:"
SET_PROCESSING = "qa:processing"
SET_COMPLETED = "qa:completed"
SET_FAILED = "qa:failed"

logger = logging.getLogger("worker")


async def publish_progress(task_id: str, message: str, step: Optional[int] = None, total_steps: Optional[int] = None):
    """Publish progress updates to Redis pubsub for SSE streaming"""
    r = get_redis_client()
    progress_data = {
        "task_id": task_id,
        "message": message,
        "timestamp": datetime.now().isoformat(),
    }
    if step is not None and total_steps is not None:
        progress_data["step"] = step
        progress_data["total_steps"] = total_steps
        progress_data["progress"] = round((step / total_steps) * 100, 1)

    try:
        await r.publish(f"task_progress:{task_id}", json.dumps(progress_data, ensure_ascii=False))
    except Exception as e:
        logger.warning(f"Failed to publish progress for task {task_id}: {e}")


async def process_task(task_id: str) -> None:
    r = get_redis_client()
    key = TASK_PREFIX + task_id

    # Load task
    data = await r.hgetall(key)
    if not data:
        logger.warning(f"Task not found: {task_id}")
        return

    # Mark processing
    now = int(time.time())
    await r.hset(key, mapping={"status": "processing", "started_at": str(now)})
    await r.sadd(SET_PROCESSING, task_id)
    logger.info(f"Processing task {task_id} | user={data.get('user')} symbol={data.get('symbol')}")

    try:
        # Parse params
        params = {}
        if "params" in data:
            try:
                params = json.loads(data["params"]) if isinstance(data["params"], str) else {}
            except Exception:
                params = {}

        symbol = data.get("symbol", "")
        user_id = data.get("user", "")

        # Extract analysis parameters with defaults
        analysts = params.get("analysts", ["Bull Analyst", "Bear Analyst", "Research Manager"])
        research_depth = params.get("research_depth", 2)
        llm_provider = params.get("llm_provider", "dashscope")
        llm_model = params.get("llm_model", "qwen-plus")
        market_type = params.get("market_type", "美股")
        analysis_date = params.get("analysis_date", datetime.now().strftime("%Y-%m-%d"))

        # Progress callback function
        async def progress_callback(message: str, step: Optional[int] = None, total_steps: Optional[int] = None):
            await publish_progress(task_id, message, step, total_steps)

        await progress_callback("🚀 开始执行股票分析...")

        # Import and call the actual analysis function
        try:
            from web.utils.analysis_runner import run_stock_analysis

            loop = asyncio.get_running_loop()

            # Wrap the sync function in an async executor
            def sync_analysis():
                # Define a thread-safe callback to publish progress from worker thread
                def safe_progress(msg, step=None, total=None):
                    asyncio.run_coroutine_threadsafe(
                        progress_callback(msg, step, total), loop
                    )
                return run_stock_analysis(
                    stock_symbol=symbol,
                    analysis_date=analysis_date,
                    analysts=analysts,
                    research_depth=research_depth,
                    llm_provider=llm_provider,
                    llm_model=llm_model,
                    market_type=market_type,
                    progress_callback=safe_progress,
                )

            # Run analysis in thread pool to avoid blocking
            analysis_result = await loop.run_in_executor(None, sync_analysis)

            await progress_callback("✅ 分析完成，正在保存结果...")

            # Prepare result
            if analysis_result and analysis_result.get('success', False):
                result = {
                    "symbol": symbol,
                    "analysis_result": analysis_result,
                    "completed_at": datetime.now().isoformat(),
                    "success": True
                }
                status = "completed"
                await progress_callback("🎉 任务成功完成")
            else:
                error_msg = analysis_result.get('error', '分析失败') if analysis_result else '分析返回空结果'
                result = {
                    "symbol": symbol,
                    "error": error_msg,
                    "completed_at": datetime.now().isoformat(),
                    "success": False
                }
                status = "failed"
                await progress_callback(f"❌ 任务失败: {error_msg}")

        except Exception as analysis_error:
            logger.exception(f"Analysis execution failed for task {task_id}: {analysis_error}")
            result = {
                "symbol": symbol,
                "error": f"分析执行异常: {str(analysis_error)}",
                "completed_at": datetime.now().isoformat(),
                "success": False
            }
            status = "failed"
            await progress_callback(f"❌ 分析执行异常: {str(analysis_error)}")

        # Mark completed/failed
        finished = int(time.time())
        await r.hset(key, mapping={
            "status": status,
            "completed_at": str(finished),
            "result": json.dumps(result, ensure_ascii=False),
        })
        await r.srem(SET_PROCESSING, task_id)
        if status == "completed":
            await r.sadd(SET_COMPLETED, task_id)
        else:
            await r.sadd(SET_FAILED, task_id)

        logger.info(f"Task {task_id} {status}")

    except Exception as e:
        logger.exception(f"Task {task_id} processing failed: {e}")
        finished = int(time.time())
        await r.hset(key, mapping={
            "status": "failed",
            "completed_at": str(finished),
            "error": str(e),
        })
        await r.srem(SET_PROCESSING, task_id)
        await r.sadd(SET_FAILED, task_id)
        await publish_progress(task_id, f"❌ 处理失败: {str(e)}")


async def worker_loop(stop_event: asyncio.Event):
    r = get_redis_client()
    logger.info("Worker loop started")
    while not stop_event.is_set():
        try:
            # BLPOP returns (list, task_id) when an item is available
            item: Optional[list] = await r.blpop(READY_LIST, timeout=5)
            if not item:
                continue
            _, task_id = item
            await process_task(task_id)
        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.exception(f"Worker loop error: {e}")
            await asyncio.sleep(1)
    logger.info("Worker loop stopped")


async def main():
    setup_logging("INFO")
    await init_db()
    # Apply dynamic log level from system settings
    try:
        from app.services.config_provider import provider as config_provider
        eff = await config_provider.get_effective_system_settings()
        desired_level = str(eff.get("log_level", "INFO")).upper()
        setup_logging(desired_level)
        for name in ("worker", "webapi", "uvicorn", "fastapi"):
            logging.getLogger(name).setLevel(desired_level)
    except Exception as e:
        logging.getLogger("worker").warning(f"Failed to apply dynamic log level: {e}")


    stop_event = asyncio.Event()

    def _handle_signal(*_):
        logger.info("Shutdown signal received")
        stop_event.set()

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, _handle_signal)
        except NotImplementedError:
            # Windows may not support signal handlers in event loop
            pass

    try:
        await worker_loop(stop_event)
    finally:
        await close_db()


if __name__ == "__main__":
    asyncio.run(main())