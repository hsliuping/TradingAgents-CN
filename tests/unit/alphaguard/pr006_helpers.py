from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from uuid import uuid4

from app.services.alphaguard.paper_account_service import PaperAccountService
from app.services.alphaguard.paper_policy_registry import PaperPolicyRegistry
from tradingagents.alphaguard.paper_schemas import (
    OrderIntent,
    PAPER_SCHEMA_VERSION,
    paper_canonical_hash,
)


CALENDAR_DATES = (
    date(2026, 7, 1),
    date(2026, 7, 2),
    date(2026, 7, 3),
    date(2026, 7, 6),
    date(2026, 7, 7),
    date(2026, 7, 8),
    date(2026, 7, 9),
    date(2026, 7, 10),
)


async def setup_paper(db, *, user_id: str = "user"):
    await PaperPolicyRegistry(db).register_builtins()
    for session in CALENDAR_DATES:
        await db["trading_calendar"].insert_one(
            {
                "calendar_id": f"cn-{session}",
                "market": "CN",
                "session_date": session.isoformat(),
                "is_open": True,
                "published_at": datetime(2026, 1, 1),
            }
        )
    return await PaperAccountService(db).initialize_user_accounts(
        user_id,
        now=datetime(2026, 7, 1, 8, 0),
    )


async def make_intent(
    db,
    account,
    *,
    action: str = "BUY",
    quantity: int = 1000,
    limit_price: Decimal | None = Decimal("10.00"),
    source_type: str | None = None,
    source_object_id: str = "source-1",
    candidate_id: str | None = "candidate-1",
    earliest: datetime = datetime(2026, 7, 2, 9, 30),
    expires: datetime = datetime(2026, 7, 8, 15, 0),
) -> OrderIntent:
    source_type = source_type or (
        "RISK_DECISION"
        if account.account_type == "PAPER_TOP_CONFIRMED"
        else "QUANT_PROPOSAL"
        if account.account_type == "PAPER_QUANT"
        else "NORMAL_PLAN"
    )
    benchmark = account.account_type in {"PAPER_QUANT", "PAPER_NORMAL"}
    side = "BUY" if action == "BUY" else "SELL"
    order_type = "LIMIT" if action == "BUY" else "MARKET_ON_OPEN"
    policy = await PaperPolicyRegistry(db).execution_policy()
    fee = await PaperPolicyRegistry(db).fee_policy()
    state_hash = await PaperAccountService(db).account_state_hash(account.account_id)
    key_payload = {
        "account_id": account.account_id,
        "source_type": source_type,
        "source_object_id": source_object_id,
        "side": side,
        "execution_policy_version": policy.version,
    }
    payload = {
        "intent_id": str(uuid4()),
        "user_id": account.user_id,
        "account_id": account.account_id,
        "account_type": account.account_type,
        "source_type": source_type,
        "source_object_id": source_object_id,
        "analysis_id": "analysis-1",
        "candidate_id": candidate_id,
        "snapshot_id": "snapshot-1",
        "quant_proposal_id": "proposal-1",
        "plan_id": "plan-1" if source_type != "QUANT_PROPOSAL" else None,
        "consensus_id": "consensus-1" if source_type == "RISK_DECISION" else None,
        "risk_decision_id": "risk-1" if source_type == "RISK_DECISION" else None,
        "symbol": "600519",
        "market": "CN",
        "currency": "CNY",
        "original_action": action,
        "side": side,
        "order_type": order_type,
        "quantity": quantity,
        "limit_price": limit_price if order_type == "LIMIT" else None,
        "earliest_execute_at": earliest,
        "expires_at": expires,
        "execution_policy_version": policy.version,
        "matching_engine_version": policy.matching_engine_version,
        "fee_policy_version": fee.version,
        "account_state_snapshot_id": state_hash,
        "idempotency_key": paper_canonical_hash(key_payload),
        "created_at": datetime(2026, 7, 1, 12, 0),
        "schema_version": PAPER_SCHEMA_VERSION,
        "benchmark_only": benchmark,
        "consensus_approved": not benchmark,
        "hard_risk_approved": not benchmark,
        "execution_environment": "PAPER",
        "live_execution_allowed": False,
    }
    payload["immutable_hash"] = paper_canonical_hash(
        payload,
        exclude={"intent_id", "immutable_hash", "created_at"},
    )
    return OrderIntent.model_validate(payload)


def daily_record(
    *,
    trade_date: date = date(2026, 7, 2),
    open_price: str = "9.90",
    high: str = "10.20",
    low: str = "9.80",
    close: str = "10.10",
    volume: int = 1_000_000,
    suspended: bool = False,
    st_status: bool = False,
    limit_up: str = "11.00",
    limit_down: str = "9.00",
):
    return {
        "_reference": f"stock_daily_quotes:600519:{trade_date}",
        "symbol": "600519",
        "market": "CN",
        "trade_date": trade_date.isoformat(),
        "period": "daily",
        "open": open_price,
        "high": high,
        "low": low,
        "close": close,
        "pre_close": "10.00",
        "volume": volume,
        "amount": str(Decimal(close) * volume),
        "suspended": suspended,
        "isST": st_status,
        "limit_up_price": limit_up,
        "limit_down_price": limit_down,
    }
