import asyncio
import json
import logging
import time
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Coroutine


logger = logging.getLogger(__name__)

from core.embedded_nanobot.cron.types import CronJob, CronJobState, CronPayload, CronRunRecord, CronSchedule, CronStore


def _now_ms() -> int:
    return int(time.time() * 1000)


def _compute_next_run(schedule: CronSchedule, now_ms: int) -> int | None:
    if schedule.kind == "at":
        return schedule.at_ms if schedule.at_ms and schedule.at_ms > now_ms else None
    if schedule.kind == "every":
        return now_ms + schedule.every_ms if schedule.every_ms and schedule.every_ms > 0 else None
    if schedule.kind == "cron" and schedule.expr:
        try:
            from croniter import croniter
            from zoneinfo import ZoneInfo

            base_time = now_ms / 1000
            tz = ZoneInfo(schedule.tz) if schedule.tz else datetime.now().astimezone().tzinfo
            base_dt = datetime.fromtimestamp(base_time, tz=tz)
            return int(croniter(schedule.expr, base_dt).get_next(datetime).timestamp() * 1000)
        except Exception:
            return None
    return None


class CronService:
    _MAX_RUN_HISTORY = 20

    def __init__(self, store_path: Path, on_job: Callable[[CronJob], Coroutine[Any, Any, str | None]] | None = None):
        self.store_path = store_path
        self.on_job = on_job
        self._store: CronStore | None = None
        self._last_mtime = 0.0
        self._timer_task: asyncio.Task | None = None
        self._running = False

    def _load_store(self) -> CronStore:
        if self._store and self.store_path.exists():
            mtime = self.store_path.stat().st_mtime
            if mtime != self._last_mtime:
                self._store = None
        if self._store:
            return self._store
        if self.store_path.exists():
            try:
                data = json.loads(self.store_path.read_text(encoding="utf-8"))
                jobs: list[CronJob] = []
                for item in data.get("jobs", []):
                    jobs.append(CronJob(
                        id=item["id"],
                        name=item["name"],
                        enabled=item.get("enabled", True),
                        schedule=CronSchedule(
                            kind=item["schedule"]["kind"],
                            at_ms=item["schedule"].get("atMs"),
                            every_ms=item["schedule"].get("everyMs"),
                            expr=item["schedule"].get("expr"),
                            tz=item["schedule"].get("tz"),
                        ),
                        payload=CronPayload(
                            kind=item["payload"].get("kind", "agent_turn"),
                            message=item["payload"].get("message", ""),
                            deliver=item["payload"].get("deliver", False),
                            channel=item["payload"].get("channel"),
                            to=item["payload"].get("to"),
                        ),
                        state=CronJobState(
                            next_run_at_ms=item.get("state", {}).get("nextRunAtMs"),
                            last_run_at_ms=item.get("state", {}).get("lastRunAtMs"),
                            last_status=item.get("state", {}).get("lastStatus"),
                            last_error=item.get("state", {}).get("lastError"),
                            run_history=[CronRunRecord(run_at_ms=r["runAtMs"], status=r["status"], duration_ms=r.get("durationMs", 0), error=r.get("error")) for r in item.get("state", {}).get("runHistory", [])],
                        ),
                        created_at_ms=item.get("createdAtMs", 0),
                        updated_at_ms=item.get("updatedAtMs", 0),
                        delete_after_run=item.get("deleteAfterRun", False),
                    ))
                self._store = CronStore(jobs=jobs)
            except Exception as exc:
                logger.warning("Failed to load cron store: %s", exc)
                self._store = CronStore()
        else:
            self._store = CronStore()
        return self._store

    def _save_store(self) -> None:
        if not self._store:
            return
        self.store_path.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "version": self._store.version,
            "jobs": [{
                "id": job.id,
                "name": job.name,
                "enabled": job.enabled,
                "schedule": {
                    "kind": job.schedule.kind,
                    "atMs": job.schedule.at_ms,
                    "everyMs": job.schedule.every_ms,
                    "expr": job.schedule.expr,
                    "tz": job.schedule.tz,
                },
                "payload": {
                    "kind": job.payload.kind,
                    "message": job.payload.message,
                    "deliver": job.payload.deliver,
                    "channel": job.payload.channel,
                    "to": job.payload.to,
                },
                "state": {
                    "nextRunAtMs": job.state.next_run_at_ms,
                    "lastRunAtMs": job.state.last_run_at_ms,
                    "lastStatus": job.state.last_status,
                    "lastError": job.state.last_error,
                    "runHistory": [{"runAtMs": r.run_at_ms, "status": r.status, "durationMs": r.duration_ms, "error": r.error} for r in job.state.run_history],
                },
                "createdAtMs": job.created_at_ms,
                "updatedAtMs": job.updated_at_ms,
                "deleteAfterRun": job.delete_after_run,
            } for job in self._store.jobs],
        }
        self.store_path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
        self._last_mtime = self.store_path.stat().st_mtime

    async def start(self) -> None:
        self._running = True
        self._load_store()
        self._recompute_next_runs()
        self._save_store()
        self._arm_timer()

    def stop(self) -> None:
        self._running = False
        if self._timer_task:
            self._timer_task.cancel()
            self._timer_task = None

    def _recompute_next_runs(self) -> None:
        if not self._store:
            return
        now = _now_ms()
        for job in self._store.jobs:
            if job.enabled:
                job.state.next_run_at_ms = _compute_next_run(job.schedule, now)

    def _get_next_wake_ms(self) -> int | None:
        if not self._store:
            return None
        times = [job.state.next_run_at_ms for job in self._store.jobs if job.enabled and job.state.next_run_at_ms]
        return min(times) if times else None

    def _arm_timer(self) -> None:
        if self._timer_task:
            self._timer_task.cancel()
        next_wake = self._get_next_wake_ms()
        if not next_wake or not self._running:
            return
        delay_s = max(0, next_wake - _now_ms()) / 1000

        async def tick():
            await asyncio.sleep(delay_s)
            if self._running:
                await self._on_timer()

        self._timer_task = asyncio.create_task(tick())

    async def _on_timer(self) -> None:
        self._load_store()
        if not self._store:
            return
        now = _now_ms()
        due_jobs = [job for job in self._store.jobs if job.enabled and job.state.next_run_at_ms and now >= job.state.next_run_at_ms]
        for job in due_jobs:
            await self._execute_job(job)
        self._save_store()
        self._arm_timer()

    async def _execute_job(self, job: CronJob) -> None:
        start_ms = _now_ms()
        try:
            if self.on_job:
                await self.on_job(job)
            job.state.last_status = "ok"
            job.state.last_error = None
        except Exception as exc:
            job.state.last_status = "error"
            job.state.last_error = str(exc)
        finally:
            end_ms = _now_ms()
            job.state.last_run_at_ms = start_ms
            job.state.run_history.insert(0, CronRunRecord(run_at_ms=start_ms, status=job.state.last_status or "skipped", duration_ms=end_ms - start_ms, error=job.state.last_error))
            job.state.run_history = job.state.run_history[:self._MAX_RUN_HISTORY]
            if job.delete_after_run and job.state.last_status == "ok":
                self.delete_job(job.id)
            else:
                job.state.next_run_at_ms = _compute_next_run(job.schedule, end_ms)
                job.updated_at_ms = end_ms

    def list_jobs(self) -> list[CronJob]:
        return list(self._load_store().jobs)

    def add_job(self, name: str, schedule: CronSchedule, payload: CronPayload, enabled: bool = True, delete_after_run: bool = False) -> CronJob:
        store = self._load_store()
        now = _now_ms()
        job = CronJob(id=str(uuid.uuid4()), name=name, enabled=enabled, schedule=schedule, payload=payload, created_at_ms=now, updated_at_ms=now, delete_after_run=delete_after_run)
        job.state.next_run_at_ms = _compute_next_run(schedule, now) if enabled else None
        store.jobs.append(job)
        self._save_store()
        self._arm_timer()
        return job

    def delete_job(self, job_id: str) -> bool:
        store = self._load_store()
        before = len(store.jobs)
        store.jobs = [job for job in store.jobs if job.id != job_id]
        changed = len(store.jobs) != before
        if changed:
            self._save_store()
            self._arm_timer()
        return changed