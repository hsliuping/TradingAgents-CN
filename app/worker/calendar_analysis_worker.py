from __future__ import annotations

import asyncio
import logging
import signal
import sys
import uuid
import traceback
from datetime import datetime
from pathlib import Path
from typing import Optional

project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from app.core.database import init_database, close_database
from app.core.redis_client import init_redis, close_redis
from app.core.config import settings
from app.services.calendar.calendar_analysis_service import get_calendar_analysis_service
from app.services.calendar.calendar_queue_service import get_calendar_queue_service


logger = logging.getLogger(__name__)


class CalendarAnalysisWorker:
    def __init__(self, worker_id: Optional[str] = None):
        self.worker_id = worker_id or f"cal-worker-{uuid.uuid4().hex[:8]}"
        self.running = False
        self.current_task: Optional[str] = None
        self.poll_interval = float(getattr(settings, "CALENDAR_QUEUE_POLL_INTERVAL_SECONDS", 1.0))
        self.heartbeat_interval = int(getattr(settings, "CALENDAR_WORKER_HEARTBEAT_INTERVAL", 30))

        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)

    def _signal_handler(self, signum, frame):
        self.running = False

    async def start(self):
        try:
            logging.basicConfig(
                level=logging.INFO,
                format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            )
            logger.info(f"启动日历分析Worker: {self.worker_id}")
            await init_database()
            await init_redis()

            self.queue = get_calendar_queue_service()
            self.service = get_calendar_analysis_service()
            self.running = True

            heartbeat_task = asyncio.create_task(self._heartbeat_loop())
            await self._work_loop()
            heartbeat_task.cancel()
            try:
                await heartbeat_task
            except asyncio.CancelledError:
                pass
        finally:
            await self._cleanup()

    async def _work_loop(self):
        while self.running:
            try:
                payload = await self.queue.dequeue(self.worker_id)
                if payload:
                    self.current_task = str(payload.get("task_id") or "")
                    await self.service.run_task(payload)
                    self.current_task = None
                else:
                    await asyncio.sleep(self.poll_interval)
            except Exception as e:
                logger.error(f"worker循环异常: {e}")
                logger.error(traceback.format_exc())
                await asyncio.sleep(3)

    async def _heartbeat_loop(self):
        while self.running:
            try:
                await self._send_heartbeat()
                await asyncio.sleep(self.heartbeat_interval)
            except asyncio.CancelledError:
                break
            except Exception:
                await asyncio.sleep(5)

    async def _send_heartbeat(self):
        try:
            from app.core.redis_client import get_redis_service
            redis_service = get_redis_service()
            key = f"worker:{self.worker_id}:heartbeat"
            payload = {
                "worker_id": self.worker_id,
                "timestamp": datetime.utcnow().isoformat(),
                "current_task": self.current_task,
                "status": "active" if self.running else "stopping",
            }
            await redis_service.set_json(key, payload, ttl=self.heartbeat_interval * 2)
        except Exception:
            pass

    async def _cleanup(self):
        try:
            await close_database()
            await close_redis()
        except Exception:
            pass


async def main():
    worker = CalendarAnalysisWorker()
    await worker.start()


if __name__ == "__main__":
    asyncio.run(main())

