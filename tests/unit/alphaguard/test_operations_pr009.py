from __future__ import annotations

import ast
from datetime import datetime
from pathlib import Path

import pytest
from fastapi import HTTPException
from pydantic import ValidationError

import app.routers.alphaguard_operations as operations_router
from app.services.alphaguard.index_service import ensure_alphaguard_indexes
from app.services.alphaguard.operations_alert_service import OperationsAlertService
from app.services.alphaguard.operations_job_service import OperationsJobService
from app.services.alphaguard.operations_service import AlphaGuardOperationsService
from scripts.init_alphaguard_operations_indexes import OPERATIONS_COLLECTIONS
from tests.unit.alphaguard._fakes import FakeDB
from tradingagents.alphaguard.mongo_indexes import ALPHAGUARD_INDEX_SPECS
from tradingagents.alphaguard.operations_schemas import (
    ServiceHealth,
    SystemReadinessReport,
    operations_hash,
    sanitize_operational_value,
)


ROOT = Path(__file__).resolve().parents[3]


def test_operational_schema_redacts_secrets_and_hash_is_deterministic():
    source = {
        "provider": "demo",
        "api_key": "super-secret",
        "message": "Authorization: Bearer abc.def token=xyz",
        "nested": [{"password": "hidden"}],
    }
    sanitized = sanitize_operational_value(source)
    encoded = str(sanitized)
    assert "super-secret" not in encoded
    assert "abc.def" not in encoded
    assert "hidden" not in encoded
    assert operations_hash({"b": 2, "a": 1}) == operations_hash({"a": 1, "b": 2})


def test_readiness_contract_permanently_forbids_live_execution():
    now = datetime(2026, 7, 27, 9)
    service = ServiceHealth(
        service_name="FASTAPI",
        status="HEALTHY",
        required=True,
        reachable=True,
        last_checked_at=now,
    )
    base = {
        "report_id": "report",
        "generated_at": now,
        "overall_status": "NOT_READY",
        "system_mode": "SIM_AUTONOMOUS",
        "live_trading_enabled": False,
        "service_health": [service],
        "data_readiness": [],
        "job_health": [],
        "paper_execution_ready": False,
        "evaluation_ready": False,
        "experiment_ready": False,
        "challenger_ready": False,
        "code_commit": "commit",
        "build_version": "version",
        "config_hash": "a" * 64,
        "report_hash": "b" * 64,
    }
    assert SystemReadinessReport(**base).live_execution_allowed is False
    with pytest.raises(ValidationError):
        SystemReadinessReport(**base, live_execution_allowed=True)
    with pytest.raises(ValidationError):
        SystemReadinessReport(**base, live_ready=True)


@pytest.mark.asyncio
async def test_operations_indexes_are_create_only_and_repeatable():
    db = FakeDB()
    first = await ensure_alphaguard_indexes(
        db, collection_names=OPERATIONS_COLLECTIONS
    )
    second = await ensure_alphaguard_indexes(
        db, collection_names=OPERATIONS_COLLECTIONS
    )
    expected = sum(
        len(ALPHAGUARD_INDEX_SPECS[name]) for name in OPERATIONS_COLLECTIONS
    )
    assert len(first) == len(second) == expected
    assert all(item.startswith("created ") for item in first)
    assert all(item.startswith("unchanged ") for item in second)


@pytest.mark.asyncio
async def test_alerts_aggregate_acknowledge_resolve_and_reopen_with_audit():
    db = FakeDB()
    alerts = OperationsAlertService(db)
    first = await alerts.observe(
        severity="ERROR",
        category="DATA",
        code="QFQ_MISSING",
        title="QFQ missing",
        message="token=secret-value no fixed data",
        source_module="readiness",
    )
    second = await alerts.observe(
        severity="ERROR",
        category="DATA",
        code="QFQ_MISSING",
        title="QFQ missing",
        message="password=secret-value still missing",
        source_module="readiness",
    )
    assert first.alert_id == second.alert_id
    assert second.occurrence_count == 2
    assert "secret-value" not in second.sanitized_message
    acknowledged = await alerts.acknowledge(second.alert_id, actor_id="admin")
    assert acknowledged.status == "ACKNOWLEDGED"
    resolved = await alerts.resolve(
        second.alert_id,
        actor_id="admin",
        resolution_note="source data restored",
    )
    assert resolved.status == "RESOLVED"
    reopened = await alerts.observe(
        severity="WARNING",
        category="DATA",
        code="QFQ_MISSING",
        title="QFQ missing again",
        message="coverage empty",
        source_module="readiness",
    )
    assert reopened.status == "OPEN"
    assert reopened.acknowledged_by is None
    assert reopened.resolved_at is None
    assert db["ag_ops_alerts"].count() == 1
    assert db["ag_ops_events"].count() == 5


@pytest.mark.asyncio
async def test_controlled_job_queue_is_allowlisted_and_idempotent():
    db = FakeDB()
    jobs = OperationsJobService(db)
    first, created = await jobs.enqueue(
        "INTEGRITY_CHECK",
        requested_by="admin",
        idempotency_key="fixed-job-key",
    )
    repeated, repeated_created = await jobs.enqueue(
        "INTEGRITY_CHECK",
        requested_by="admin",
        idempotency_key="fixed-job-key",
    )
    assert created is True
    assert repeated_created is False
    assert first.job_request_id == repeated.job_request_id
    assert db["ag_ops_job_requests"].count() == 1
    with pytest.raises(ValueError):
        await jobs.enqueue("RUN_ARBITRARY_SCRIPT", requested_by="admin")
    with pytest.raises(ValueError):
        await jobs.enqueue(
            "HEALTH_CHECK",
            requested_by="admin",
            payload={"shell": "rm -rf /"},
        )


@pytest.mark.asyncio
async def test_data_readiness_is_fail_closed_and_integrity_detects_negatives():
    db = FakeDB()
    service = AlphaGuardOperationsService(db)
    service_states = {
        item.service_name: item
        for item in await service.service_health(now=datetime(2026, 7, 27, 9))
    }
    assert service_states["ALPHAGUARD_INDEXES"].status == "UNHEALTHY"
    assert service_states["ALPHAGUARD_INDEXES"].error_code == "REQUIRED_INDEXES_MISSING"
    statuses = await service.data_readiness(now=datetime(2026, 7, 27, 9))
    by_name = {item.component: item for item in statuses}
    assert by_name["TRADING_CALENDAR"].status == "NOT_READY"
    assert by_name["QFQ_PRICE_DATA"].status == "NOT_READY"
    assert by_name["MODEL_PROVIDER"].status == "NOT_CONFIGURED"
    assert by_name["CHALLENGER_PIPELINE"].status == "NOT_READY"
    await db["ag_paper_accounts"].insert_one({"cash_available": -1})
    await db["ag_paper_positions"].insert_one({"quantity": -2})
    integrity = await service.integrity()
    counts = {item["check"]: item["count"] for item in integrity["checks"]}
    assert counts["negative_cash"] == 1
    assert counts["negative_position"] == 1
    assert integrity["status"] == "FAIL"


@pytest.mark.asyncio
async def test_current_only_industry_mapping_is_not_reported_as_history_ready():
    db = FakeDB()
    await db["stock_industry_history"].insert_one(
        {
            "symbol": "600519",
            "effective_from": datetime(2026, 7, 27),
            "history_coverage_status": "CURRENT_ONLY",
        }
    )
    statuses = await AlphaGuardOperationsService(db).data_readiness(
        now=datetime(2026, 7, 27, 9)
    )
    industry = next(
        item for item in statuses if item.component == "INDUSTRY_HISTORY"
    )
    assert industry.status == "PARTIAL"
    assert industry.blocking_reasons == ["INDUSTRY_HISTORY_CURRENT_ONLY"]


def test_operations_api_write_handlers_require_admin_and_expose_no_arbitrary_write():
    routes = {
        (method, route.path)
        for route in operations_router.router.routes
        for method in route.methods
    }
    assert not {item for item in routes if item[0] in {"PUT", "PATCH", "DELETE"}}
    assert ("POST", "/alphaguard/operations/jobs/{job_name}/run") in routes
    forbidden = {
        "/alphaguard/operations/shell",
        "/alphaguard/operations/config",
        "/alphaguard/operations/database/drop",
        "/alphaguard/operations/orders/create",
    }
    assert not {path for _, path in routes} & forbidden
    with pytest.raises(HTTPException) as exc:
        operations_router._require_admin({"id": "user", "is_admin": False})
    assert exc.value.status_code == 403

    source = (
        ROOT / "app/routers/alphaguard_operations.py"
    ).read_text(encoding="utf-8")
    tree = ast.parse(source)
    for node in tree.body:
        if not isinstance(node, (ast.AsyncFunctionDef, ast.FunctionDef)):
            continue
        writes = any(
            isinstance(decorator, ast.Call)
            and isinstance(decorator.func, ast.Attribute)
            and decorator.func.attr == "post"
            for decorator in node.decorator_list
        )
        if writes:
            assert any(
                isinstance(child, ast.Call)
                and isinstance(child.func, ast.Name)
                and child.func.id == "_require_admin"
                for child in ast.walk(node)
            ), node.name


def test_operations_layer_has_no_broker_or_live_order_dependency():
    paths = [
        ROOT / "app/services/alphaguard/operations_service.py",
        ROOT / "app/services/alphaguard/operations_job_service.py",
        ROOT / "app/routers/alphaguard_operations.py",
    ]
    source = "\n".join(path.read_text(encoding="utf-8") for path in paths)
    for forbidden in (
        "BrokerAdapter",
        "broker_sdk",
        "create_order_intent(",
        "create_paper_order(",
        'live_execution_allowed": True',
        "subprocess.run(request",
        "eval(",
        "exec(",
    ):
        assert forbidden not in source
