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

        def add_job(self, func, trigger, *args, **kwargs):
            # record and keep a handle to the callable and trigger
            self.jobs.append({"func": func, "trigger": trigger, "args": args, "kwargs": kwargs})

        def start(self):
            # no-op in tests
            return None

        def pause_job(self, job_id):
            return None

        def shutdown(self, wait=False):
            return None

    import app.main as main_mod
    import apscheduler.schedulers.asyncio as aps_asyncio_mod
    import app.core.config_bridge as config_bridge_mod
    import app.services.multi_source_basics_sync_service as basics_mod
    import app.services.config_provider as config_provider_mod
    import app.services.quotes_ingestion_service as quotes_mod
    import app.services.scheduler_service as scheduler_service_mod

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
        async def run_full_sync(self, force: bool = False, preferred_sources=None):
            return None

    monkeypatch.setattr(main_mod, "init_db", _noop_async, raising=True)
    monkeypatch.setattr(main_mod, "close_db", _noop_async, raising=True)
    monkeypatch.setattr(main_mod, "_print_config_summary", _noop_async, raising=True)
    monkeypatch.setattr(main_mod, "MINIMAL_STARTUP", False, raising=True)
    monkeypatch.setattr(config_bridge_mod, "bridge_config_to_env", lambda: None, raising=True)

    async def _fake_get_effective_system_settings():
        return {"log_level": "INFO", "enable_monitoring": False}

    monkeypatch.setattr(
        config_provider_mod.provider,
        "get_effective_system_settings",
        _fake_get_effective_system_settings,
        raising=True,
    )

    # Patch startup dependencies imported inside lifespan
    monkeypatch.setattr(aps_asyncio_mod, "AsyncIOScheduler", lambda *args, **kwargs: fake_scheduler, raising=True)
    monkeypatch.setattr(basics_mod, "MultiSourceBasicsSyncService", lambda: _FakeBasicsService(), raising=True)
    monkeypatch.setattr(quotes_mod, "QuotesIngestionService", _FakeQuotesIngestion, raising=True)
    monkeypatch.setattr(scheduler_service_mod, "set_scheduler_instance", lambda scheduler: None, raising=True)
    monkeypatch.setattr(main_mod.asyncio, "create_task", _fake_asyncio_create_task, raising=True)

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

    # 启动时会异步触发一次基础信息同步
    assert state.create_task_called is True

    # 实时行情任务应直接注册为协程函数
    job_func = job["func"]
    assert inspect.iscoroutinefunction(job_func)
