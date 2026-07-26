from __future__ import annotations

from datetime import date, datetime, timedelta
from decimal import Decimal

from tradingagents.alphaguard.evaluation_schemas import (
    EvaluationSubject,
    HorizonLabel,
    evaluation_hash,
)


OPEN_DATES = (
    date(2026, 7, 1),
    date(2026, 7, 2),
    date(2026, 7, 3),
    date(2026, 7, 6),
    date(2026, 7, 7),
    date(2026, 7, 8),
    date(2026, 7, 9),
    date(2026, 7, 10),
    date(2026, 7, 13),
    date(2026, 7, 14),
    date(2026, 7, 15),
    date(2026, 7, 16),
    date(2026, 7, 17),
    date(2026, 7, 20),
    date(2026, 7, 21),
    date(2026, 7, 22),
    date(2026, 7, 23),
    date(2026, 7, 24),
    date(2026, 7, 27),
    date(2026, 7, 28),
    date(2026, 7, 29),
)


async def seed_calendar(db):
    for session in OPEN_DATES:
        await db["trading_calendar"].insert_one(
            {
                "market": "CN",
                "session_date": session.isoformat(),
                "is_open": True,
            }
        )


async def seed_adjusted_prices(
    db,
    *,
    symbol: str = "600519",
    start_price: Decimal = Decimal("10"),
    step: Decimal = Decimal("0.10"),
    version: str = "qfq-fixture-v1",
    mode: str = "QFQ",
):
    for index, session in enumerate(OPEN_DATES):
        close = start_price + step * index
        await db["stock_daily_quotes"].insert_one(
            {
                "symbol": symbol,
                "market": "CN",
                "trade_date": session.isoformat(),
                "period": "daily",
                "adjusted_open": close - Decimal("0.05"),
                "adjusted_high": close + Decimal("0.20"),
                "adjusted_low": close - Decimal("0.20"),
                "adjusted_close": close,
                "price_adjustment_mode": mode,
                "price_data_version": version,
                "data_ref": f"adjusted:{symbol}:{session}:{version}",
                "volume": 1_000_000,
                "suspended": False,
            }
        )


def make_subject(
    *,
    subject_id: str = "subject-1",
    subject_type: str = "NORMAL_PLAN",
    source_object_id: str = "plan-1",
    stage: str = "NORMAL_MODEL",
    status: str = "PROPOSE_TRADE",
    action: str = "BUY",
    entry_zone=True,
    actual_execution_exists: bool = False,
    lineage_ids: dict[str, str] | None = None,
):
    payload = {
        "subject_id": subject_id,
        "subject_type": subject_type,
        "source_object_id": source_object_id,
        "source_object_version": "1.0.0",
        "user_id": "user-1",
        "candidate_id": "candidate-1",
        "symbol": "600519",
        "market": "CN",
        "snapshot_id": "snapshot-1",
        "analysis_id": "analysis-1",
        "decision_trade_date": date(2026, 7, 1),
        "decision_cutoff_at": datetime(2026, 7, 1, 15, 0),
        "action": action,
        "decision_stage": stage,
        "decision_status": status,
        "selected_for_execution": status in {"PROPOSE_TRADE", "PASS", "REDUCE"},
        "actual_execution_exists": actual_execution_exists,
        "entry_zone": {"lower": 9.9, "upper": 10.1} if entry_zone else None,
        "initial_position_pct": Decimal("0.05"),
        "max_position_pct": Decimal("0.10"),
        "evidence_refs": [],
        "lineage_ids": lineage_ids or {},
        "evaluation_version": "evaluation-v1",
        "created_at": datetime(2026, 7, 1, 15, 1),
        "schema_version": "alphaguard-evaluation-v1",
    }
    payload["immutable_hash"] = evaluation_hash(
        payload,
        exclude={"subject_id", "immutable_hash", "created_at"},
    )
    return EvaluationSubject.model_validate(payload)


def make_label(
    subject_id: str,
    horizon: str,
    *,
    raw: Decimal = Decimal("0.05"),
    aligned: Decimal | None = Decimal("0.05"),
    status: str = "CALCULATED",
    version: str = "qfq-fixture-v1",
):
    offset = {"1D": 1, "5D": 5, "10D": 10, "20D": 20}[horizon]
    end = OPEN_DATES[offset]
    payload = {
        "label_id": f"label-{subject_id}-{horizon}",
        "subject_id": subject_id,
        "horizon": horizon,
        "status": status,
        "anchor_type": "DECISION_CLOSE",
        "anchor_date": OPEN_DATES[0],
        "anchor_price": Decimal("10") if status == "CALCULATED" else None,
        "execution_anchor_price": None,
        "horizon_end_date": end,
        "horizon_close_price": (
            Decimal("10") * (Decimal("1") + raw)
            if status == "CALCULATED"
            else None
        ),
        "raw_forward_return": raw if status == "CALCULATED" else None,
        "action_aligned_return": aligned if status == "CALCULATED" else None,
        "benchmark_symbol": "000300",
        "benchmark_price_adjustment_mode": "QFQ",
        "benchmark_data_version": version,
        "benchmark_return": Decimal("0.01") if status == "CALCULATED" else None,
        "relative_benchmark_return": raw - Decimal("0.01") if status == "CALCULATED" else None,
        "mfe": Decimal("0.08") if status == "CALCULATED" else None,
        "mae": Decimal("-0.02") if status == "CALCULATED" else None,
        "data_refs": [f"price:{horizon}"] if status == "CALCULATED" else [],
        "price_adjustment_mode": "QFQ",
        "price_data_version": version,
        "calculation_version": "horizon-label-v1",
        "calculated_at": datetime(2026, 8, 1) if status == "CALCULATED" else None,
    }
    payload["input_hash"] = evaluation_hash(
        payload,
        exclude={"input_hash", "label_id", "calculated_at"},
    )
    return HorizonLabel.model_validate(payload)
