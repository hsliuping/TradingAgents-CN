from __future__ import annotations

from datetime import datetime

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

import app.routers.alphaguard_operations as operations_router
from app.routers.auth_db import get_current_user
from app.services.alphaguard.index_service import ensure_alphaguard_indexes
from app.services.alphaguard.operations_alert_service import OperationsAlertService
from app.services.alphaguard.operations_job_service import OperationsJobService
from app.services.alphaguard.operations_service import AlphaGuardOperationsService
from tests.unit.alphaguard._fakes import FakeDB


class RedisStub:
    async def ping(self):
        return True

    async def exists(self, _key):
        return False

    async def scan_iter(self, match=None):
        if False:
            yield match


class SchedulerStub:
    running = True

    def get_job(self, _job_id):
        return None


@pytest.mark.asyncio
async def test_operations_readiness_alert_and_job_smoke_is_fail_closed():
    db = FakeDB()
    await ensure_alphaguard_indexes(db)
    service = AlphaGuardOperationsService(
        db, redis_client=RedisStub(), scheduler=SchedulerStub()
    )
    report = await service.readiness(
        now=datetime(2026, 7, 27, 9), persist_alerts=True
    )
    assert report.overall_status == "NOT_READY"
    assert report.system_mode == "SIM_AUTONOMOUS"
    assert report.live_trading_enabled is False
    assert report.live_execution_allowed is False
    assert report.live_ready is False
    assert report.paper_execution_ready is False
    assert "TRADING_CALENDAR_MISSING" in report.blocking_items
    assert db["ag_ops_alerts"].count() > 0

    jobs = OperationsJobService(
        db, redis_client=RedisStub(), scheduler=SchedulerStub()
    )
    request, created = await jobs.enqueue(
        "INTEGRITY_CHECK",
        requested_by="admin",
        idempotency_key="mvp-smoke-integrity",
    )
    assert created is True
    assert request.status == "PENDING"
    assert await jobs.process_pending() == {"completed": 1, "failed": 0}
    assert await jobs.process_pending() == {"completed": 0, "failed": 0}
    terminal = await db["ag_ops_job_requests"].find_one(
        {"job_request_id": request.job_request_id}
    )
    assert terminal["status"] == "COMPLETED"
    for name in (
        "paper_accounts",
        "paper_positions",
        "paper_orders",
        "paper_trades",
        "ag_order_intents",
        "ag_paper_orders",
        "ag_paper_fills",
    ):
        assert db[name].count() == 0


def test_authenticated_operations_api_smoke_and_admin_boundary(monkeypatch):
    db = FakeDB()
    service = AlphaGuardOperationsService(
        db, redis_client=RedisStub(), scheduler=SchedulerStub()
    )
    jobs = OperationsJobService(
        db, redis_client=RedisStub(), scheduler=SchedulerStub()
    )
    monkeypatch.setattr(operations_router, "get_mongo_db", lambda: db)
    app = FastAPI()
    app.include_router(operations_router.router, prefix="/api")
    app.dependency_overrides[get_current_user] = lambda: {
        "id": "user",
        "is_admin": False,
    }
    app.dependency_overrides[operations_router.get_operations_service] = lambda: service
    app.dependency_overrides[operations_router.get_operations_job_service] = lambda: jobs
    client = TestClient(app)

    readiness = client.get("/api/alphaguard/operations/readiness")
    assert readiness.status_code == 200
    assert readiness.json()["data"]["live_ready"] is False
    denied = client.post(
        "/api/alphaguard/operations/jobs/INTEGRITY_CHECK/run",
        json={"idempotency_key": "api-smoke-user"},
    )
    assert denied.status_code == 403

    app.dependency_overrides[get_current_user] = lambda: {
        "id": "admin",
        "is_admin": True,
    }
    allowed = client.post(
        "/api/alphaguard/operations/jobs/INTEGRITY_CHECK/run",
        json={"idempotency_key": "api-smoke-admin"},
    )
    assert allowed.status_code == 200
    assert allowed.json()["data"]["created"] is True
