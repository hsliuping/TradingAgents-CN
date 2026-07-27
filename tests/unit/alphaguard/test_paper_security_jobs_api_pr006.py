from datetime import date, datetime
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.routers.alphaguard_paper import router
from app.services.alphaguard.index_service import ensure_alphaguard_indexes
from app.services.alphaguard.paper_account_service import PaperAccountService
from app.services.alphaguard.paper_calendar_service import (
    PaperTradingCalendarService,
    TradingCalendarUnavailable,
)
from app.services.alphaguard.paper_storage import (
    model_document,
    mongo_date,
    safe_error_message,
)
from app.services.alphaguard.paper_task_service import PaperTaskService
from scripts.init_alphaguard_paper_indexes import PAPER_COLLECTIONS
from tests.unit.alphaguard._fakes import FakeDB
from tests.unit.alphaguard.pr006_helpers import setup_paper
from tests.unit.alphaguard.pr006_helpers import make_intent
from tradingagents.alphaguard.mongo_indexes import ALPHAGUARD_INDEX_SPECS
from tradingagents.alphaguard.paper_schemas import PaperPosition


ROOT = Path(__file__).resolve().parents[3]


@pytest.mark.asyncio
async def test_paper_indexes_are_create_only_and_repeatable():
    db = FakeDB()
    first = await ensure_alphaguard_indexes(
        db,
        collection_names=PAPER_COLLECTIONS,
    )
    second = await ensure_alphaguard_indexes(
        db,
        collection_names=PAPER_COLLECTIONS,
    )
    expected = sum(len(ALPHAGUARD_INDEX_SPECS[name]) for name in PAPER_COLLECTIONS)
    assert len(first) == expected
    assert all(item.startswith("created ") for item in first)
    assert len(second) == expected
    assert all(item.startswith("unchanged ") for item in second)
    assert "paper_accounts" not in db.collections
    assert "paper_orders" not in db.collections


def test_public_paper_api_has_no_creation_or_settlement_endpoint():
    mutations = {
        (route.path, method)
        for route in router.routes
        for method in getattr(route, "methods", set())
        if method in {"POST", "PUT", "PATCH", "DELETE"}
    }
    assert mutations == {
        ("/alphaguard/paper/orders/{order_id}/cancel", "POST")
    }
    source = (ROOT / "app/routers/alphaguard_paper.py").read_text(encoding="utf-8")
    for forbidden in (
        "create_order_intent",
        "create_paper_order",
        "create_paper_fill",
        "settle_fill(",
        "cash_available =",
        "approved_quantity",
    ):
        assert forbidden not in source


def test_automatic_paper_read_and_cancel_api_smoke(monkeypatch):
    import asyncio
    import app.routers.alphaguard_paper as paper_router
    from app.routers.auth_db import get_current_user
    from app.services.alphaguard.paper_order_service import PaperOrderService

    db = FakeDB()

    async def arrange():
        account = (await setup_paper(db))["PAPER_QUANT"]
        intent = await make_intent(db, account)
        order = await PaperOrderService(db).create_reserve_submit(intent)
        return account, order

    account, order = asyncio.run(arrange())
    monkeypatch.setattr(paper_router, "get_mongo_db", lambda: db)
    app = FastAPI()
    app.include_router(paper_router.router, prefix="/api")
    app.dependency_overrides[get_current_user] = lambda: {"id": account.user_id}
    client = TestClient(app)

    accounts = client.get("/api/alphaguard/paper/accounts")
    assert accounts.status_code == 200
    assert len(accounts.json()["data"]["items"]) == 4
    orders = client.get(
        "/api/alphaguard/paper/orders",
        params={"account_id": account.account_id},
    )
    assert orders.status_code == 200
    assert orders.json()["data"]["items"][0]["status"] == "PENDING"
    cancelled = client.post(
        f"/api/alphaguard/paper/orders/{order.order_id}/cancel"
    )
    assert cancelled.status_code == 200
    assert cancelled.json()["data"]["status"] == "CANCELLED"
    repeated = client.post(
        f"/api/alphaguard/paper/orders/{order.order_id}/cancel"
    )
    assert repeated.status_code == 200
    assert client.post("/api/alphaguard/paper/order-intents", json={}).status_code == 404
    assert client.post("/api/alphaguard/paper/orders", json={}).status_code == 405


def test_automatic_execution_has_no_manual_or_live_broker_dependency():
    service_files = [
        path
        for path in (ROOT / "app/services/alphaguard").glob("*.py")
        if path.name.startswith("paper_")
        or path.name
        in {
            "benchmark_execution_safety_gate.py",
            "execution_market_snapshot_service.py",
            "execution_outbox_service.py",
            "fee_engine.py",
            "matching_engine.py",
            "order_intent_factory.py",
            "settlement_service.py",
        }
    ]
    combined = "\n".join(path.read_text(encoding="utf-8") for path in service_files)
    for forbidden in (
        "BrokerAdapter",
        "broker_sdk",
        "app.routers.paper",
        "POST /paper/order",
        'db["paper_accounts"]',
        'db["paper_positions"]',
        'db["paper_orders"]',
        'db["paper_trades"]',
    ):
        assert forbidden not in combined
    decision_pipeline = (
        ROOT / "app/services/alphaguard/decision_pipeline.py"
    ).read_text(encoding="utf-8")
    hard_risk = (
        ROOT / "app/services/alphaguard/hard_risk_engine.py"
    ).read_text(encoding="utf-8")
    assert "PaperOrderService" not in decision_pipeline
    assert "OrderIntentFactory" not in decision_pipeline
    assert "PaperOrderService" not in hard_risk


@pytest.mark.asyncio
async def test_job_run_is_idempotent_and_preserves_single_asset_effect():
    db = FakeDB()
    service = PaperTaskService(db)
    calls = 0

    async def operation():
        nonlocal calls
        calls += 1
        return {"calls": calls}

    first = await service.run_once(
        job_type="fixed",
        trade_date=date(2026, 7, 2),
        idempotency_key="fixed:2026-07-02",
        operation=operation,
    )
    second = await service.run_once(
        job_type="fixed",
        trade_date=date(2026, 7, 2),
        idempotency_key="fixed:2026-07-02",
        operation=operation,
    )
    assert first == second == {"calls": 1}
    assert calls == 1
    assert db["ag_paper_job_runs"].count() == 1


@pytest.mark.asyncio
async def test_calendar_uses_persisted_sessions_not_natural_day_math():
    db = FakeDB()
    await setup_paper(db)
    calendar = PaperTradingCalendarService(db)
    assert await calendar.next_open_date(date(2026, 7, 3)) == date(2026, 7, 6)
    assert await calendar.is_open_date(date(2026, 7, 4)) is False
    with pytest.raises(TradingCalendarUnavailable):
        await calendar.next_open_date(date(2026, 7, 10))


@pytest.mark.asyncio
async def test_daily_snapshot_marks_missing_prices_instead_of_silent_zero():
    db = FakeDB()
    accounts = await setup_paper(db)
    account = accounts["PAPER_TOP_CONFIRMED"]
    position = PaperPosition(
        position_id="position",
        account_id=account.account_id,
        symbol="600519",
        market="CN",
        currency="CNY",
        quantity=100,
        available_quantity=100,
        reserved_quantity=0,
        average_cost="10",
        total_cost="1000",
        realized_pnl="0",
        total_fees="0",
        updated_at=datetime(2026, 7, 2, 16),
    )
    await db["ag_paper_positions"].insert_one(model_document(position))
    snapshot = await PaperAccountService(db).create_daily_snapshot(
        account.account_id,
        date(2026, 7, 2),
    )
    assert snapshot.valuation_complete is False
    assert snapshot.missing_price_symbols == ["600519"]
    stored = await db["ag_paper_account_snapshots"].find_one(
        {
            "account_id": account.account_id,
            "trade_date": mongo_date(date(2026, 7, 2)),
        }
    )
    assert isinstance(stored["trade_date"], datetime)


def test_retry_error_redacts_credentials():
    message = safe_error_message(
        ValueError("api_key=super-secret Authorization:Bearer abc.def token=123")
    )
    assert "super-secret" not in message
    assert "abc.def" not in message
    assert "token=[REDACTED]" in message
