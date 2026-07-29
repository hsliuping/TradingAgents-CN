from __future__ import annotations

from copy import deepcopy
import os

import pytest
from fastapi.testclient import TestClient

import app.demo.alphaguard_ui_demo as demo_app
import app.routers.alphaguard_evaluations as evaluation_router
import app.routers.alphaguard_experiments as experiment_router
import scripts.run_alphaguard_ui_demo as demo_runner
from app.demo.alphaguard_ui_demo_fixture import (
    DEMO_DATABASE_NAME,
    build_demo_fixture,
)
from tests.unit.alphaguard._fakes import FakeDB


def test_demo_fixture_is_deterministic_and_covers_guided_scenarios():
    first = build_demo_fixture()
    second = build_demo_fixture()
    assert first["fixture_hash"] == second["fixture_hash"]
    assert first == second
    assert first["demo_only"] is True
    assert len(first["candidates"]) == 5
    assert first["snapshots"]["600519"]["data_quality"]["status"] == "FAIL"
    assert {item["status"] for item in first["proposals"]} == {"WATCH", "TRIGGERED"}
    assert any(item.get("status") == "REJECT" for item in first["decision_events"])
    assert any(item.get("status") == "HARD_RISK_REJECT" for item in first["decision_events"])
    assert any(item.get("intent_id") for item in first["decision_events"])
    assert all(item.get("input_hash") for item in first["decision_events"])
    assert all(item.get("output_hash") for item in first["decision_events"])
    assert all(item.get("component_version") for item in first["decision_events"])
    assert all(item.get("evidence_refs") for item in first["decision_events"])
    assert first["fills"]["demo-account-top"][0]["trade_date"] == "2026-07-29"
    assert first["lots"]["demo-account-top"][0]["available_from_date"] == "2026-07-30"
    detail = first["experiment_details"]["demo-experiment-leakage-fail"]
    assert detail["risk_reviews"][0]["leakage_audit"]["status"] == "FAIL"
    assert detail["comparison_reports"][0]["status"] == "INSUFFICIENT_DATA"


def test_demo_isolation_refuses_production_database(monkeypatch):
    monkeypatch.setenv("MONGODB_DATABASE_NAME", DEMO_DATABASE_NAME)
    monkeypatch.setenv("USE_MONGODB_STORAGE", "false")
    monkeypatch.setattr(demo_app.settings, "ALPHAGUARD_UI_DEMO", True)
    monkeypatch.setattr(demo_app.settings, "MONGODB_DATABASE_SCOPE", "explicit")
    monkeypatch.setattr(demo_app.settings, "MONGODB_DATABASE", "production")
    with pytest.raises(RuntimeError, match="demo database must be exactly"):
        demo_app.validate_demo_isolation()


def test_demo_isolation_refuses_live_mode(monkeypatch):
    monkeypatch.setenv("MONGODB_DATABASE_NAME", DEMO_DATABASE_NAME)
    monkeypatch.setenv("USE_MONGODB_STORAGE", "false")
    monkeypatch.setattr(demo_app.settings, "ALPHAGUARD_UI_DEMO", True)
    monkeypatch.setattr(demo_app.settings, "MONGODB_DATABASE_SCOPE", "explicit")
    monkeypatch.setattr(demo_app.settings, "MONGODB_DATABASE", DEMO_DATABASE_NAME)
    monkeypatch.setenv("LIVE_TRADING_ENABLED", "true")
    with pytest.raises(RuntimeError, match="refuses to start"):
        demo_app.validate_demo_isolation()


def test_demo_runner_disables_every_existing_production_database_resolver(monkeypatch):
    monkeypatch.setenv("MONGODB_DATABASE", "production")
    monkeypatch.setenv("MONGODB_DATABASE_NAME", "production")
    monkeypatch.setenv("MONGODB_DATABASE_SCOPE", "auto")
    monkeypatch.setenv("USE_MONGODB_STORAGE", "true")
    demo_runner.configure_environment()
    assert os.environ["MONGODB_DATABASE"] == DEMO_DATABASE_NAME
    assert os.environ["MONGODB_DATABASE_NAME"] == DEMO_DATABASE_NAME
    assert os.environ["MONGODB_DATABASE_SCOPE"] == "explicit"
    assert os.environ["USE_MONGODB_STORAGE"] == "false"


def test_demo_api_contract_is_authenticated_and_read_only(monkeypatch):
    monkeypatch.setattr(demo_app, "_fixture", build_demo_fixture())
    client = TestClient(demo_app.app)
    assert client.get("/api/alphaguard/candidates").status_code == 401
    login = client.post("/api/auth/demo-login")
    assert login.status_code == 200
    token = login.json()["data"]["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    candidates = client.get("/api/alphaguard/candidates", headers=headers)
    assert candidates.status_code == 200
    assert len(candidates.json()["data"]["items"]) == 5
    assert client.post("/api/alphaguard/candidates", headers=headers).status_code == 405
    assert client.post(
        "/api/alphaguard/operations/jobs/INTEGRITY_CHECK/run", headers=headers
    ).status_code == 404
    integrity = client.get("/api/alphaguard/operations/integrity", headers=headers)
    assert integrity.json()["data"]["production_writes"] == 0


@pytest.mark.asyncio
async def test_evaluation_overview_separates_research_production_and_trade(monkeypatch):
    db = FakeDB()
    for item in (
        {"subject_id": "research", "user_id": "u1", "source_object_id": "research-proposal", "actual_execution_exists": False},
        {"subject_id": "production", "user_id": "u1", "source_object_id": "prod-proposal", "actual_execution_exists": False},
        {"subject_id": "trade", "user_id": "u1", "source_object_id": "trade-proposal", "actual_execution_exists": True},
    ):
        await db["ag_eval_subjects"].insert_one(item)
    await db["ag_quant_proposals"].insert_one({"proposal_id": "prod-proposal", "user_id": "u1"})
    await db["ag_quant_proposals"].insert_one({"proposal_id": "trade-proposal", "user_id": "u1"})
    await db["ag_eval_horizon_labels"].insert_one({"subject_id": "production", "horizon": "20D", "status": "PENDING"})
    await db["ag_eval_horizon_labels"].insert_one({"subject_id": "trade", "horizon": "1D", "status": "CALCULATED"})
    monkeypatch.setattr(evaluation_router, "get_mongo_db", lambda: db)

    response = await evaluation_router.evaluation_overview({"id": "u1"})
    data = response["data"]
    assert data["historical_research_subjects"] == 1
    assert data["production_subjects"] == 2
    assert data["actual_trade_subjects"] == 1
    assert data["horizon_status"] == {"20D:PENDING": 1, "1D:CALCULATED": 1}


@pytest.mark.asyncio
async def test_research_summary_is_latest_read_only_report(monkeypatch):
    db = FakeDB()
    old = {"report_id": "old", "status": "COMPLETED", "run_mode": "RESEARCH_BACKFILL", "research_only": True, "created_at": "2026-07-28T00:00:00"}
    latest = {"report_id": "latest", "status": "COMPLETED", "run_mode": "RESEARCH_BACKFILL", "research_only": True, "created_at": "2026-07-29T00:00:00"}
    await db["ag_research_backfill_reports"].insert_one(old)
    await db["ag_research_backfill_reports"].insert_one(latest)
    before = deepcopy(db["ag_research_backfill_reports"].documents)
    monkeypatch.setattr(evaluation_router, "get_mongo_db", lambda: db)
    response = await evaluation_router.research_summary({"id": "u1"})
    assert response["data"]["report"]["report_id"] == "latest"
    assert response["data"]["boundary"]["research_only"] is True
    assert db["ag_research_backfill_reports"].documents == before


@pytest.mark.asyncio
async def test_promotion_policy_endpoint_is_latest_and_read_only(monkeypatch):
    db = FakeDB()
    await db["ag_exp_promotion_policies"].insert_one({"policy_id": "old", "created_at": "2026-07-28T00:00:00"})
    await db["ag_exp_promotion_policies"].insert_one({"policy_id": "current", "created_at": "2026-07-29T00:00:00"})
    before = deepcopy(db["ag_exp_promotion_policies"].documents)
    monkeypatch.setattr(experiment_router, "get_mongo_db", lambda: db)
    response = await experiment_router.promotion_policy({"id": "u1"})
    assert response["data"]["policy"]["policy_id"] == "current"
    assert response["data"]["status"] == "READY"
    assert db["ag_exp_promotion_policies"].documents == before
