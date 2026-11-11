import inspect
from types import SimpleNamespace

from apscheduler.triggers.interval import IntervalTrigger
from fastapi import FastAPI


def test_scheduler_adds_quotes_job(monkeypatch):
    # Flags to assert behavior
    state = SimpleNamespace(
        ensure_indexes_called=False,
        create_task_called=False,
    )

    # Fake QuotesIngestionService used by app.main during startup
    class _FakeQuotesIngestion:
        async def ensure_indexes(self):
            state.ensure_indexes_called = True

        async def run_once(self):
            # simple async no-op
            return None

    # Capture added jobs from scheduler
    class _FakeScheduler:
        def __init__(self):
            self.jobs = []
            self.paused_ids = []

        def add_job(self, func, trigger, *args, **kwargs):
            # record and keep a handle to the callable and trigger
            self.jobs.append({"func": func, "trigger": trigger, "args": args, "kwargs": kwargs})

        def pause_job(self, job_id, *args, **kwargs):
            # 现役 lifespan 会对被禁用的定时任务调用 pause_job
            self.paused_ids.append(job_id)

        def start(self):
            # no-op in tests
            return None

        def shutdown(self, wait=False):
            return None

    # Patch scheduler and service in app.main before startup runs
    import app.main as main_mod

    fake_scheduler = _FakeScheduler()

    def _fake_asyncio_create_task(coro):
        # We don't need a running loop; just record and close the coroutine to avoid warnings
        state.create_task_called = True
        assert inspect.iscoroutine(coro)
        try:
            coro.close()
        except Exception:
            pass
        return None

    # Patch blocking init/close DB and basic sync service
    async def _noop_async(*args, **kwargs):
        return None

    class _FakeBasicsService:
        async def run_full_sync(self, force: bool = False):
            return None

    monkeypatch.setattr(main_mod, "init_db", _noop_async, raising=True)
    monkeypatch.setattr(main_mod, "close_db", _noop_async, raising=True)
    monkeypatch.setattr(main_mod, "get_basics_sync_service", lambda: _FakeBasicsService(), raising=True)

    # Patch scheduler, quotes service and asyncio.create_task
    monkeypatch.setattr(main_mod, "AsyncIOScheduler", lambda *args, **kwargs: fake_scheduler, raising=True)
    monkeypatch.setattr(main_mod, "QuotesIngestionService", _FakeQuotesIngestion, raising=True)
    monkeypatch.setattr(main_mod.asyncio, "create_task", _fake_asyncio_create_task, raising=True)

    # lifespan shutdown 段会对真身单例执行 user_service.close()（关闭共享 pymongo client），
    # 该关闭会泄漏到同进程后续测试（test_config_summary 查库失败 → 401）；测试隔离起见屏蔽之
    from app.services.user_service import UserService

    monkeypatch.setattr(UserService, "close", lambda self, log=True: None, raising=True)

    # Directly drive the lifespan to avoid importing full router stack
    import asyncio as _asyncio

    async def _run():
        async with main_mod.lifespan(FastAPI()):
            return

    _asyncio.run(_run())

    # Assert a job with IntervalTrigger was scheduled
    assert fake_scheduler.jobs, "No jobs scheduled for quotes ingestion"
    job = None
    for j in fake_scheduler.jobs:
        if isinstance(j["trigger"], IntervalTrigger):
            job = j
            break
    assert job is not None, "Quotes ingestion IntervalTrigger job not found"

    # Ensure ensure_indexes called during startup
    assert state.ensure_indexes_called is True

    # Simulate scheduler tick: 现役实现直接注册协程函数（AsyncIOScheduler 会 await 它）
    job_func = job["func"]
    coro = job_func()
    assert inspect.iscoroutine(coro)
    coro.close()  # 不真正执行，避免未 await 警告

    # quotes 任务注册后保持 active（不应出现在 pause_job 名单中）
    assert job["kwargs"].get("id") not in fake_scheduler.paused_ids

    # startup 期间的后台任务经 asyncio.create_task 派发
    assert state.create_task_called is True

