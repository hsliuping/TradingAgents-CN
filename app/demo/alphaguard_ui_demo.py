"""Standalone, isolated AlphaGuard UI acceptance API.

The process refuses to start unless every isolation guard is explicit. It
persists one immutable scenario document in ``alphaguard_ui_demo`` and serves
read-only frontend contracts from that document. No production router,
scheduler, worker, backfill service, trading service, or repository is loaded.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from copy import deepcopy
import os
from typing import Any

from fastapi import Depends, FastAPI, Header, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient

from app.core.config import settings
from app.core.response import ok
from app.demo.alphaguard_ui_demo_fixture import (
    DEMO_DATABASE_NAME,
    DEMO_SCENARIO_ID,
    build_demo_fixture,
)
from app.services.auth_service import AuthService


_client: AsyncIOMotorClient | None = None
_fixture: dict[str, Any] | None = None


def validate_demo_isolation() -> None:
    if not settings.ALPHAGUARD_UI_DEMO:
        raise RuntimeError("ALPHAGUARD_UI_DEMO must be explicitly enabled")
    if settings.MONGO_DB != DEMO_DATABASE_NAME:
        raise RuntimeError(
            f"demo database must be exactly {DEMO_DATABASE_NAME}; got {settings.MONGO_DB}"
        )
    if (settings.MONGODB_DATABASE_SCOPE or "").lower() != "explicit":
        raise RuntimeError("demo database scope must be explicit")
    if os.environ.get("MONGODB_DATABASE_NAME") != DEMO_DATABASE_NAME:
        raise RuntimeError("legacy MongoDB database name must be isolated for the UI demo")
    if os.environ.get("USE_MONGODB_STORAGE", "false").lower() not in {"0", "false", "no", "off"}:
        raise RuntimeError("legacy ConfigManager MongoDB storage must be disabled in the UI demo")
    live_value = str(os.environ.get("LIVE_TRADING_ENABLED", "false")).lower()
    if live_value in {"1", "true", "yes", "on"}:
        raise RuntimeError("UI demo refuses to start while live trading is enabled")


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _client, _fixture
    validate_demo_isolation()
    _client = AsyncIOMotorClient(
        settings.MONGO_URI,
        serverSelectionTimeoutMS=settings.MONGO_SERVER_SELECTION_TIMEOUT_MS,
    )
    await _client.admin.command("ping")
    db = _client[DEMO_DATABASE_NAME]
    if db.name != DEMO_DATABASE_NAME:
        raise RuntimeError("demo MongoDB identity changed unexpectedly")

    fixture = build_demo_fixture()
    collection = db["ag_ui_demo_scenarios"]
    existing = await collection.find_one({"scenario_id": DEMO_SCENARIO_ID})
    if existing is None:
        await collection.insert_one(deepcopy(fixture))
    elif existing.get("fixture_hash") != fixture["fixture_hash"]:
        raise RuntimeError("demo fixture integrity conflict; drop only the demo database explicitly")
    stored = await collection.find_one({"scenario_id": DEMO_SCENARIO_ID}, {"_id": 0})
    if stored is None or stored.get("fixture_hash") != fixture["fixture_hash"]:
        raise RuntimeError("demo fixture persistence verification failed")
    _fixture = stored
    app.state.demo_database = db.name
    app.state.scheduler_started = False
    app.state.workers_started = False
    try:
        yield
    finally:
        _fixture = None
        if _client is not None:
            _client.close()
        _client = None


app = FastAPI(
    title="AlphaGuard Isolated UI Demo",
    version="1.0",
    lifespan=lifespan,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3001", "http://127.0.0.1:3001"],
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-Request-ID", "Accept-Language"],
)


def _data() -> dict[str, Any]:
    if _fixture is None:
        raise HTTPException(status_code=503, detail="demo fixture is not ready")
    return _fixture


def _clean(value: Any) -> Any:
    return deepcopy(value)


def _bearer(authorization: str | None) -> str:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="No authorization header")
    return authorization.split(" ", 1)[1]


async def current_demo_user(authorization: str | None = Header(default=None)) -> dict[str, Any]:
    token_data = AuthService.verify_token(_bearer(authorization))
    if token_data is None or token_data.sub != "alphaguard_demo":
        raise HTTPException(status_code=401, detail="Invalid demo token")
    return _clean(_data()["user"])


@app.get("/health")
@app.get("/api/health")
async def health():
    return ok({
        "status": "ok",
        "service": "AlphaGuard isolated UI demo",
        "database": DEMO_DATABASE_NAME,
        "scheduler_started": False,
        "workers_started": False,
        "live_execution_allowed": False,
    })


@app.post("/api/auth/demo-login")
async def demo_login():
    user = _clean(_data()["user"])
    access = AuthService.create_access_token("alphaguard_demo", expires_minutes=60)
    refresh = AuthService.create_access_token("alphaguard_demo", expires_delta=60 * 60 * 4)
    return ok({
        "access_token": access,
        "refresh_token": refresh,
        "token_type": "bearer",
        "expires_in": 3600,
        "user": user,
    }, "isolated demo session created")


@app.post("/api/auth/refresh")
async def refresh_demo_token(payload: dict[str, Any]):
    token_data = AuthService.verify_token(str(payload.get("refresh_token", "")))
    if token_data is None or token_data.sub != "alphaguard_demo":
        raise HTTPException(status_code=401, detail="Invalid demo refresh token")
    return ok({
        "access_token": AuthService.create_access_token("alphaguard_demo", expires_minutes=60),
        "refresh_token": payload["refresh_token"],
        "expires_in": 3600,
    })


@app.get("/api/auth/me")
async def demo_me(user: dict[str, Any] = Depends(current_demo_user)):
    return ok(user)


@app.post("/api/auth/logout")
async def demo_logout(_user: dict[str, Any] = Depends(current_demo_user)):
    return ok({"revoked": True}, "demo client must discard the token")


@app.get("/api/alphaguard/candidates")
async def candidates(_user: dict[str, Any] = Depends(current_demo_user)):
    return ok({"items": _clean(_data()["candidates"])})


@app.get("/api/alphaguard/evidence/snapshots/{snapshot_id}")
async def snapshot(snapshot_id: str, _user: dict[str, Any] = Depends(current_demo_user)):
    for item in _data()["snapshots"].values():
        if item["snapshot_id"] == snapshot_id:
            return ok(_clean(item))
    raise HTTPException(status_code=404, detail="demo snapshot not found")


@app.get("/api/alphaguard/factors/results/{snapshot_id}")
async def factor_results(snapshot_id: str, _user: dict[str, Any] = Depends(current_demo_user)):
    symbol = snapshot_id.rsplit("-", 1)[-1]
    return ok({"items": _clean(_data()["factors"].get(symbol, []))})


@app.get("/api/alphaguard/regimes/{snapshot_id}")
async def regime(snapshot_id: str, _user: dict[str, Any] = Depends(current_demo_user)):
    symbol = snapshot_id.rsplit("-", 1)[-1]
    item = _data()["regimes"].get(symbol)
    if item is None:
        raise HTTPException(status_code=404, detail="demo regime not found")
    return ok(_clean(item))


@app.get("/api/alphaguard/quant-proposals")
async def proposals(_user: dict[str, Any] = Depends(current_demo_user)):
    return ok({"items": _clean(_data()["proposals"])})


@app.get("/api/alphaguard/decision-events")
async def decision_events(_user: dict[str, Any] = Depends(current_demo_user)):
    return ok({"items": _clean(_data()["decision_events"])})


@app.get("/api/alphaguard/decisions/{plan_id}")
@app.get("/api/alphaguard/reviews/{plan_id}")
@app.get("/api/alphaguard/consensus/{plan_id}")
@app.get("/api/alphaguard/risk-decisions/{plan_id}")
async def decision_detail(plan_id: str, _user: dict[str, Any] = Depends(current_demo_user)):
    for event in _data()["decision_events"]:
        if plan_id in event.values():
            return ok(_clean(event))
    raise HTTPException(status_code=404, detail="demo decision object not found")


def _by_account(key: str, account_id: str) -> list[dict[str, Any]]:
    return _clean(_data()[key].get(account_id, []))


@app.get("/api/alphaguard/paper/accounts")
async def accounts(_user: dict[str, Any] = Depends(current_demo_user)):
    return ok({"items": _clean(_data()["accounts"])})


@app.get("/api/alphaguard/paper/positions")
async def positions(account_id: str, _user: dict[str, Any] = Depends(current_demo_user)):
    return ok({"items": _by_account("positions", account_id)})


@app.get("/api/alphaguard/paper/position-lots")
async def lots(account_id: str, _user: dict[str, Any] = Depends(current_demo_user)):
    return ok({"items": _by_account("lots", account_id)})


@app.get("/api/alphaguard/paper/orders")
async def orders(account_id: str, _user: dict[str, Any] = Depends(current_demo_user)):
    return ok({"items": _by_account("orders", account_id)})


@app.get("/api/alphaguard/paper/fills")
async def fills(account_id: str, _user: dict[str, Any] = Depends(current_demo_user)):
    return ok({"items": _by_account("fills", account_id)})


@app.get("/api/alphaguard/paper/account-snapshots")
async def account_snapshots(account_id: str, _user: dict[str, Any] = Depends(current_demo_user)):
    return ok({"items": _by_account("account_snapshots", account_id)})


@app.get("/api/alphaguard/evaluations/overview")
async def evaluation_overview(_user: dict[str, Any] = Depends(current_demo_user)):
    return ok(_clean(_data()["evaluation"]["overview"]))


@app.get("/api/alphaguard/evaluations/research-summary")
async def research_summary(_user: dict[str, Any] = Depends(current_demo_user)):
    return ok(_clean(_data()["evaluation"]["research_summary"]))


@app.get("/api/alphaguard/evaluations/accounts")
async def evaluation_accounts(_user: dict[str, Any] = Depends(current_demo_user)):
    return ok({"items": _clean(_data()["evaluation"]["accounts"])})


@app.get("/api/alphaguard/evaluations/model-value")
async def model_value(_user: dict[str, Any] = Depends(current_demo_user)):
    return ok({"items": _clean(_data()["evaluation"]["comparisons"])})


@app.get("/api/alphaguard/evaluations/counterfactuals")
async def counterfactuals(_user: dict[str, Any] = Depends(current_demo_user)):
    return ok({"items": _clean(_data()["evaluation"]["counterfactuals"])})


@app.get("/api/alphaguard/attributions")
async def attributions(_user: dict[str, Any] = Depends(current_demo_user)):
    return ok({"items": _clean(_data()["evaluation"]["attributions"])})


@app.get("/api/alphaguard/champions")
async def champions(_user: dict[str, Any] = Depends(current_demo_user)):
    return ok({"items": _clean(_data()["champions"])})


@app.get("/api/alphaguard/experiments")
async def experiments(_user: dict[str, Any] = Depends(current_demo_user)):
    return ok({"items": _clean(_data()["experiments"])})


@app.get("/api/alphaguard/experiments/promotion-policy")
async def promotion_policy(_user: dict[str, Any] = Depends(current_demo_user)):
    return ok({"policy": _clean(_data()["promotion_policy"]), "status": "ACTIVE"})


@app.get("/api/alphaguard/experiments/{experiment_id}")
async def experiment(experiment_id: str, _user: dict[str, Any] = Depends(current_demo_user)):
    item = _data()["experiment_details"].get(experiment_id)
    if item is None:
        raise HTTPException(status_code=404, detail="demo experiment not found")
    return ok(_clean(item))


def _operations() -> dict[str, Any]:
    return _data()["operations"]


@app.get("/api/alphaguard/operations/overview")
async def operations_overview(_user: dict[str, Any] = Depends(current_demo_user)):
    return ok({
        "readiness": _clean(_data()["readiness"]),
        "sample_counts": {
            "ag_candidates": 5,
            "ag_evidence_snapshots": 5,
            "ag_quant_proposals": 4,
            "ag_decision_contexts": 3,
            "ag_risk_decisions": 2,
            "ag_paper_fills": 1,
            "ag_eval_subjects": 5,
            "ag_exp_runs": 1,
        },
        "open_alerts": _clean(_operations()["alerts"]),
        "safety_notice": "Isolated synthetic demo; production database is not referenced",
    })


@app.get("/api/alphaguard/operations/readiness")
async def readiness(_user: dict[str, Any] = Depends(current_demo_user)):
    return ok(_clean(_data()["readiness"]))


@app.get("/api/alphaguard/operations/services")
async def services(_user: dict[str, Any] = Depends(current_demo_user)):
    return ok({"items": _clean(_operations()["services"])})


@app.get("/api/alphaguard/operations/data-readiness")
async def data_readiness(_user: dict[str, Any] = Depends(current_demo_user)):
    return ok({"items": _clean(_operations()["data"])})


@app.get("/api/alphaguard/operations/jobs")
async def jobs(_user: dict[str, Any] = Depends(current_demo_user)):
    return ok({"items": _clean(_operations()["jobs"]), "allowed_manual_jobs": []})


@app.get("/api/alphaguard/operations/alerts")
async def alerts(
    status: str | None = Query(default=None),
    _user: dict[str, Any] = Depends(current_demo_user),
):
    items = _clean(_operations()["alerts"])
    if status:
        items = [item for item in items if item["status"] == status]
    return ok({"items": items})


@app.get("/api/alphaguard/operations/versions")
async def versions(_user: dict[str, Any] = Depends(current_demo_user)):
    return ok({"environment": "DEMO", "fixture_hash": _data()["fixture_hash"], "database": DEMO_DATABASE_NAME})


@app.get("/api/alphaguard/operations/integrity")
async def integrity(_user: dict[str, Any] = Depends(current_demo_user)):
    return ok({
        "status": "PASS",
        "database_isolated": True,
        "scheduler_started": False,
        "workers_started": False,
        "production_writes": 0,
        "fixture_hash": _data()["fixture_hash"],
    })
