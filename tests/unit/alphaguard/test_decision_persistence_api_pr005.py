from __future__ import annotations

from datetime import datetime

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.schemas.alphaguard.decision import DecisionPipelineResult
from app.services.alphaguard.index_service import ensure_alphaguard_indexes
from app.services.alphaguard.risk_policy_registry import (
    RiskPolicyConflictError,
    RiskPolicyRegistry,
)
from tests.unit.alphaguard._fakes import FakeDB
from tradingagents.alphaguard.mongo_indexes import ALPHAGUARD_INDEX_SPECS


@pytest.mark.asyncio
async def test_pr005_indexes_are_create_only_idempotent_and_match_contract():
    db = FakeDB()
    first = await ensure_alphaguard_indexes(db)
    second = await ensure_alphaguard_indexes(db)
    required = {
        "ag_decision_contexts",
        "ag_consensus_decisions",
        "ag_risk_policies",
        "ag_risk_decisions",
        "ag_decision_events",
        "ag_revision_requests",
        "ag_decision_runs",
    }
    assert required.issubset(ALPHAGUARD_INDEX_SPECS)
    assert any(item.startswith("created ag_decision_contexts.") for item in first)
    assert all(item.startswith("unchanged ") for item in second)
    assert any(
        spec["name"] == "uniq_decision_context_analysis" and spec["unique"]
        for spec in ALPHAGUARD_INDEX_SPECS["ag_decision_contexts"]
    )
    assert any(
        spec["name"] == "uniq_consensus_analysis" and spec["unique"]
        for spec in ALPHAGUARD_INDEX_SPECS["ag_consensus_decisions"]
    )
    assert any(
        spec["name"] == "uniq_risk_consensus" and spec["unique"]
        for spec in ALPHAGUARD_INDEX_SPECS["ag_risk_decisions"]
    )


@pytest.mark.asyncio
async def test_risk_policy_seed_is_idempotent_and_refuses_same_version_conflict():
    db = FakeDB()
    registry = RiskPolicyRegistry(db)
    first = await registry.register_builtin()
    second = await registry.register_builtin()
    assert first.config_hash == second.config_hash
    assert db["ag_risk_policies"].count() == 1

    document = db["ag_risk_policies"].documents[0]
    document["config_hash"] = "f" * 64
    with pytest.raises(RiskPolicyConflictError, match="different content"):
        await registry.register_builtin()


def test_decision_router_is_authenticated_read_only_except_evaluate():
    from app.routers.alphaguard_decisions import router
    from app.routers.auth_db import get_current_user

    method_paths = {
        (method, route.path)
        for route in router.routes
        for method in route.methods
    }
    expected = {
        ("POST", "/alphaguard/decisions/evaluate/{quant_proposal_id}"),
        ("GET", "/alphaguard/analyses/{analysis_id}"),
        ("GET", "/alphaguard/decisions/{plan_id}"),
        ("GET", "/alphaguard/reviews/{review_id}"),
        ("GET", "/alphaguard/consensus/{consensus_id}"),
        ("GET", "/alphaguard/risk-decisions/{risk_decision_id}"),
        ("GET", "/alphaguard/decision-events"),
    }
    assert expected.issubset(method_paths)
    assert not any(
        method in {"POST", "PUT", "PATCH", "DELETE"}
        and path != "/alphaguard/decisions/evaluate/{quant_proposal_id}"
        for method, path in method_paths
    )
    for route in router.routes:
        assert any(
            dependency.call is get_current_user
            for dependency in route.dependant.dependencies
        )


def test_decision_evaluate_api_smoke_accepts_only_account_id(monkeypatch):
    import app.routers.alphaguard_decisions as decisions_router
    from app.routers.auth_db import get_current_user

    calls = []

    class StubPipeline:
        async def evaluate_quant_proposal(
            self,
            proposal_id,
            *,
            user_id,
            account_id,
            trace_id,
        ):
            calls.append((proposal_id, user_id, account_id, trace_id))
            return DecisionPipelineResult(
                analysis_id="analysis-api",
                decision_run_key="a" * 64,
                attempt_number=1,
                terminal_status="RISK_PASS",
                order_intent_created=False,
            )

    monkeypatch.setattr(
        decisions_router, "get_decision_pipeline", lambda: StubPipeline()
    )
    app = FastAPI()
    app.include_router(decisions_router.router, prefix="/api")
    app.dependency_overrides[get_current_user] = lambda: {"id": "user"}
    client = TestClient(app)
    response = client.post(
        "/api/alphaguard/decisions/evaluate/proposal-1",
        json={"account_id": "account-1"},
    )
    assert response.status_code == 200
    assert response.json()["data"]["order_intent_created"] is False
    assert calls[0][:3] == ("proposal-1", "user", "account-1")

    forbidden = client.post(
        "/api/alphaguard/decisions/evaluate/proposal-1",
        json={
            "account_id": "account-1",
            "normal_trade_plan": {"action": "BUY"},
            "prompt_version": "attacker-controlled",
        },
    )
    assert forbidden.status_code == 422


@pytest.mark.asyncio
async def test_decision_read_apis_enforce_user_ownership(monkeypatch):
    import app.routers.alphaguard_decisions as decisions_router
    from app.routers.auth_db import get_current_user

    db = FakeDB()
    await db["ag_decision_contexts"].insert_one(
        {
            "analysis_id": "analysis-1",
            "user_id": "user",
            "decision_context_id": "context-1",
        }
    )
    await db["ag_consensus_decisions"].insert_one(
        {
            "analysis_id": "analysis-1",
            "consensus_id": "consensus-1",
            "created_at": datetime(2026, 7, 1),
        }
    )
    await db["ag_risk_decisions"].insert_one(
        {
            "analysis_id": "analysis-1",
            "risk_decision_id": "risk-1",
            "order_intent_created": False,
            "created_at": datetime(2026, 7, 1),
        }
    )
    await db["ag_decision_events"].insert_one(
        {
            "analysis_id": "analysis-1",
            "user_id": "user",
            "event_type": "CONSENSUS_PASS",
            "created_at": datetime(2026, 7, 1),
        }
    )
    monkeypatch.setattr(decisions_router, "get_mongo_db", lambda: db)
    app = FastAPI()
    app.include_router(decisions_router.router, prefix="/api")
    app.dependency_overrides[get_current_user] = lambda: {"id": "user"}
    client = TestClient(app)
    assert client.get("/api/alphaguard/consensus/consensus-1").status_code == 200
    assert client.get("/api/alphaguard/risk-decisions/risk-1").status_code == 200
    events = client.get("/api/alphaguard/decision-events")
    assert events.status_code == 200
    assert len(events.json()["data"]["items"]) == 1

    app.dependency_overrides[get_current_user] = lambda: {"id": "other"}
    assert client.get("/api/alphaguard/consensus/consensus-1").status_code == 404
    assert client.get("/api/alphaguard/risk-decisions/risk-1").status_code == 404
