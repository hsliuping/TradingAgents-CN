from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

import pytest
from bson import BSON

from app.services.alphaguard.account_metric_service import AccountMetricService
from app.services.alphaguard.attribution_engine import AttributionEngine
from app.services.alphaguard.module_metric_service import ModuleMetricService
from app.services.alphaguard.paired_comparison_service import (
    PairedComparisonService,
)
from tests.unit.alphaguard._fakes import FakeDB
from tests.unit.alphaguard.pr007_helpers import make_label, make_subject
from tradingagents.alphaguard.decision_schemas import EvidenceRef


@pytest.mark.asyncio
async def test_account_metrics_use_decimal_drawdown_fees_turnover_and_completeness():
    db = FakeDB()
    account = {
        "account_id": "account-1",
        "user_id": "user-1",
        "account_type": "PAPER_TOP_CONFIRMED",
        "market": "CN",
        "realized_pnl": Decimal("50"),
        "total_fees": Decimal("3"),
    }
    await db["ag_paper_accounts"].insert_one(account)
    equities = [
        (date(2026, 7, 1), "1000", True, "0.10"),
        (date(2026, 7, 2), "900", True, "0.20"),
        (date(2026, 7, 3), "1100", True, "0.30"),
    ]
    for trade_date, equity, complete, exposure in equities:
        await db["ag_paper_account_snapshots"].insert_one(
            {
                "account_snapshot_id": f"snap-{trade_date}",
                "account_id": "account-1",
                "trade_date": (
                    datetime.combine(trade_date, datetime.min.time())
                    if trade_date == date(2026, 7, 2)
                    else trade_date
                ),
                "total_equity": Decimal(equity),
                "realized_pnl": Decimal("50"),
                "unrealized_pnl": Decimal("47"),
                "total_fees": Decimal("3"),
                "gross_exposure_pct": Decimal(exposure),
                "valuation_complete": complete,
            }
        )
    await db["ag_paper_fills"].insert_one(
        {
            "fill_id": "fill-1",
            "account_id": "account-1",
            "trade_date": datetime(2026, 7, 2),
            "notional": Decimal("300"),
        }
    )
    await db["ag_paper_orders"].insert_one(
        {
            "order_id": "order-1",
            "account_id": "account-1",
            "trade_date": date(2026, 7, 2),
            "status": "FILLED",
        }
    )
    await db["ag_settlement_records"].insert_one(
        {
            "settlement_id": "settle-1",
            "account_id": "account-1",
            "status": "COMMITTED",
            "realized_pnl": Decimal("50"),
            "committed_at": datetime(2026, 7, 2, 15, 30),
        }
    )
    metric = await AccountMetricService(db).calculate(
        account,
        period_start=date(2026, 7, 1),
        period_end=date(2026, 7, 3),
    )
    assert metric.status == "CALCULATED"
    assert metric.total_return == Decimal("0.1")
    assert metric.max_drawdown == Decimal("-0.1")
    assert metric.average_exposure_pct == Decimal("0.2")
    assert metric.trade_count == 1
    assert metric.filled_order_count == 1
    assert metric.win_rate == Decimal("1")
    assert metric.total_fees == Decimal("3")


@pytest.mark.asyncio
async def test_account_metric_identity_is_bson_safe_and_idempotent():
    db = FakeDB()
    account = {
        "account_id": "account-1",
        "user_id": "user-1",
        "account_type": "PAPER_QUANT",
        "market": "CN",
        "realized_pnl": 0,
        "total_fees": 0,
    }
    await db["ag_paper_accounts"].insert_one(account)
    service = AccountMetricService(db)

    first = await service.calculate_all(
        period_start=date(2026, 7, 1),
        period_end=date(2026, 7, 3),
        user_id="user-1",
    )
    second = await service.calculate_all(
        period_start=date(2026, 7, 1),
        period_end=date(2026, 7, 3),
        user_id="user-1",
    )

    assert first == second
    assert db["ag_eval_account_metrics"].count() == 1
    BSON.encode(db["ag_eval_account_metrics"].documents[0])


@pytest.mark.asyncio
async def test_incomplete_or_short_account_history_is_never_called_complete():
    db = FakeDB()
    account = {
        "account_id": "account-1",
        "account_type": "PAPER_CHALLENGER",
        "market": "CN",
        "realized_pnl": 0,
        "total_fees": 0,
    }
    service = AccountMetricService(db)
    metric = await service.calculate(
        account,
        period_start=date(2026, 7, 1),
        period_end=date(2026, 7, 3),
    )
    assert metric.status == "INSUFFICIENT_HISTORY"
    assert metric.total_return is None
    for session, complete in [
        (date(2026, 7, 1), True),
        (date(2026, 7, 2), False),
    ]:
        await db["ag_paper_account_snapshots"].insert_one(
            {
                "account_id": "account-1",
                "trade_date": session,
                "total_equity": Decimal("1000"),
                "valuation_complete": complete,
                "gross_exposure_pct": 0,
            }
        )
    metric = await service.calculate(
        account,
        period_start=date(2026, 7, 1),
        period_end=date(2026, 7, 3),
    )
    assert metric.status == "INCOMPLETE_VALUATION"
    assert metric.valuation_incomplete_days == 1


@pytest.mark.asyncio
async def test_account_returns_are_normalized_across_different_initial_capital():
    db = FakeDB()
    service = AccountMetricService(db)
    results = []
    for account_id, initial in (("small", Decimal("1000")), ("large", Decimal("10000"))):
        for trade_date, equity in (
            (date(2026, 7, 1), initial),
            (date(2026, 7, 2), initial * Decimal("1.10")),
        ):
            await db["ag_paper_account_snapshots"].insert_one(
                {
                    "account_id": account_id,
                    "trade_date": trade_date,
                    "total_equity": equity,
                    "valuation_complete": True,
                    "gross_exposure_pct": Decimal("0"),
                }
            )
        results.append(
            await service.calculate(
                {
                    "account_id": account_id,
                    "account_type": "PAPER_QUANT",
                    "market": "CN",
                    "realized_pnl": 0,
                    "total_fees": 0,
                },
                period_start=date(2026, 7, 1),
                period_end=date(2026, 7, 2),
            )
        )
    assert [item.total_return for item in results] == [
        Decimal("0.10"),
        Decimal("0.10"),
    ]


def test_strict_paired_comparison_requires_same_identity_price_and_horizons():
    left = make_subject(subject_id="left", source_object_id="quant")
    right = make_subject(
        subject_id="right",
        source_object_id="normal",
        stage="NORMAL_MODEL",
    )
    left_labels = [
        make_label("left", horizon, raw=Decimal("0.03"), aligned=Decimal("0.03"))
        for horizon in ("1D", "5D", "10D", "20D")
    ]
    right_labels = [
        make_label("right", horizon, raw=Decimal("0.05"), aligned=Decimal("0.05"))
        for horizon in ("1D", "5D", "10D", "20D")
    ]
    service = PairedComparisonService(FakeDB())
    comparison = service.compare(
        "QUANT_VS_NORMAL",
        left,
        right,
        left_labels,
        right_labels,
    )
    assert comparison.pairing_status == "PAIRED"
    assert comparison.value_added_10d == Decimal("0.02")
    incompatible = [
        make_label("right", horizon, version="qfq-v2")
        for horizon in ("1D", "5D", "10D", "20D")
    ]
    comparison = service.compare(
        "QUANT_VS_NORMAL",
        left,
        right,
        left_labels,
        incompatible,
    )
    assert comparison.pairing_status == "NOT_COMPARABLE"
    assert any("price/evaluation contract" in item for item in comparison.comparability_reasons)


def test_pairing_rejects_snapshot_or_trade_date_mismatch():
    left = make_subject(subject_id="left")
    right = make_subject(subject_id="right").model_copy(
        update={"snapshot_id": "snapshot-2"}
    )
    labels = [
        make_label("left", horizon)
        for horizon in ("1D", "5D", "10D", "20D")
    ]
    right_labels = [
        make_label("right", horizon)
        for horizon in ("1D", "5D", "10D", "20D")
    ]
    result = PairedComparisonService(FakeDB()).compare(
        "NORMAL_VS_TOP", left, right, labels, right_labels
    )
    assert result.pairing_status == "NOT_COMPARABLE"
    assert "snapshot_id differs" in result.comparability_reasons


@pytest.mark.asyncio
async def test_module_metrics_report_small_sample_without_significance_claim():
    subject = make_subject()
    labels = {
        subject.subject_id: [
            make_label(subject.subject_id, "10D")
        ]
    }
    metrics = await ModuleMetricService(FakeDB()).calculate_all(
        [subject],
        labels,
        period_start=date(2026, 7, 1),
        period_end=date(2026, 7, 31),
        scope_user_id="user-1",
    )
    normal = next(item for item in metrics if item.module_type == "NORMAL_MODEL")
    assert normal.status == "INSUFFICIENT_SAMPLE"
    assert normal.scope_user_id == "user-1"
    assert "significant" not in str(normal.metrics).lower()


@pytest.mark.asyncio
async def test_factor_metrics_use_real_factor_result_fields_and_all_horizons():
    db = FakeDB()
    subject = make_subject(
        subject_id="factor-subject",
        subject_type="QUANT_PROPOSAL",
        source_object_id="proposal-factor",
        stage="QUANT",
    )
    await db["ag_factor_results"].insert_one(
        {
            "result_id": "factor-result-1",
            "snapshot_id": subject.snapshot_id,
            "factor_id": "MOMENTUM",
            "factor_version": "1.0.0",
            "raw_value": Decimal("0.12"),
            "normalized_score": Decimal("80"),
            "direction": "POSITIVE",
        }
    )
    labels = {
        subject.subject_id: [
            make_label(subject.subject_id, horizon)
            for horizon in ("1D", "5D", "10D", "20D")
        ]
    }
    metrics = await ModuleMetricService(db).calculate_all(
        [subject],
        labels,
        period_start=date(2026, 7, 1),
        period_end=date(2026, 7, 31),
        scope_user_id="user-1",
    )
    factor = next(item for item in metrics if item.module_type == "FACTOR")
    assert factor.comparable_count == 1
    assert factor.metrics["coverage_rate"] == Decimal("1")
    assert factor.metrics["direction_hit_rate"] == Decimal("1")
    assert factor.metrics["average_1d_return"] == Decimal("0.05")
    assert factor.metrics["average_20d_return"] == Decimal("0.05")
    assert factor.metrics["rank_ic"] is None


def _label_for_category(
    subject_id: str,
    *,
    raw: str = "-0.06",
    benchmark: str = "0",
    entry_touched=None,
    status: str = "CALCULATED",
):
    label = make_label(
        subject_id,
        "10D",
        raw=Decimal(raw),
        aligned=Decimal(raw),
        status=status,
    )
    if status != "CALCULATED":
        return label
    return label.model_copy(
        update={
            "benchmark_return": Decimal(benchmark),
            "relative_benchmark_return": Decimal(raw) - Decimal(benchmark),
            "entry_zone_touched": entry_touched,
        }
    )


@pytest.mark.parametrize(
    ("subject", "label", "expected"),
    [
        (
            make_subject(
                subject_id="candidate",
                stage="QUANT",
                status="WATCH",
                action="WAIT",
            ),
            _label_for_category("candidate"),
            "CANDIDATE_SELECTION",
        ),
        (
            make_subject(subject_id="factor", stage="QUANT", status="TRIGGERED"),
            _label_for_category("factor"),
            "FACTOR_FAILURE",
        ),
        (
            make_subject(subject_id="regime", stage="QUANT", status="TRIGGERED"),
            _label_for_category("regime", benchmark="-0.06"),
            "REGIME_MISCLASSIFICATION",
        ),
        (
            make_subject(subject_id="entry"),
            _label_for_category("entry", raw="0.06", entry_touched=False),
            "STRATEGY_ENTRY",
        ),
        (
            make_subject(subject_id="normal", stage="NORMAL_MODEL"),
            _label_for_category("normal"),
            "NORMAL_MODEL",
        ),
        (
            make_subject(subject_id="top", stage="TOP_MODEL"),
            _label_for_category("top"),
            "TOP_MODEL",
        ),
        (
            make_subject(subject_id="consensus", stage="CONSENSUS"),
            _label_for_category("consensus"),
            "CONSENSUS",
        ),
        (
            make_subject(subject_id="risk", stage="HARD_RISK"),
            _label_for_category("risk"),
            "HARD_RISK",
        ),
        (
            make_subject(
                subject_id="execution",
                subject_type="PAPER_ORDER",
                stage="EXECUTION",
                status="EXPIRED",
            ),
            _label_for_category("execution"),
            "EXECUTION",
        ),
    ],
)
def test_rule_registry_covers_stage_diagnostics(subject, label, expected):
    record = AttributionEngine(FakeDB()).evaluate(subject, [label], [], [])
    assert record.status == "ATTRIBUTED"
    assert record.primary_category == expected
    assert record.rule_ids
    assert "not a causal claim" in record.machine_explanation


def test_data_quality_pending_market_shock_and_unknown_rules():
    engine = AttributionEngine(FakeDB())
    subject = make_subject(subject_id="pending")
    pending = make_label("pending", "10D", status="PENDING")
    record = engine.evaluate(subject, [pending], [], [])
    assert record.status == "PENDING_HORIZON"
    insufficient = make_label(
        "pending", "10D", status="INSUFFICIENT_DATA"
    )
    record = engine.evaluate(subject, [insufficient], [], [])
    assert record.primary_category == "DATA_QUALITY"

    shock_subject = make_subject(subject_id="shock").model_copy(
        update={
            "evidence_refs": [
                EvidenceRef(
                    evidence_id="shock-1",
                    summary="structured market interruption",
                    source="market_shock",
                    as_of=datetime(2026, 7, 2),
                )
            ]
        }
    )
    record = engine.evaluate(
        shock_subject,
        [_label_for_category("shock")],
        [],
        [],
    )
    assert record.primary_category == "MARKET_SHOCK"

    unknown = make_subject(
        subject_id="unknown",
        subject_type="PAPER_FILL",
        stage="EXECUTION",
        status="FILLED",
        actual_execution_exists=True,
    )
    record = engine.evaluate(unknown, [_label_for_category("unknown")], [], [])
    assert record.primary_category == "UNKNOWN"
    assert record.confidence == Decimal("0.25")


def test_reject_outcomes_distinguish_avoided_loss_and_missed_opportunity():
    engine = AttributionEngine(FakeDB())
    reject = make_subject(
        subject_id="reject",
        stage="TOP_MODEL",
        status="REJECT",
        action="REJECT",
    )
    avoided = engine.evaluate(
        reject,
        [_label_for_category("reject", raw="-0.06")],
        [],
        [],
    )
    missed = engine.evaluate(
        reject.model_copy(update={"subject_id": "reject-2"}),
        [_label_for_category("reject-2", raw="0.06")],
        [],
        [],
    )
    assert avoided.outcome_class == "AVOIDED_LOSS"
    assert missed.outcome_class == "MISSED_OPPORTUNITY"


@pytest.mark.asyncio
async def test_attribution_override_is_append_only_and_keeps_machine_record():
    db = FakeDB()
    engine = AttributionEngine(db)
    subject = make_subject(subject_id="override")
    attribution = engine.evaluate(
        subject,
        [_label_for_category("override")],
        [],
        [],
    )
    await db["ag_eval_attributions"].insert_one(
        attribution.model_dump(mode="python")
    )
    first = await engine.append_override(
        attribution=attribution,
        user_id="user-1",
        category="UNKNOWN",
        reason="manual review found ambiguity",
    )
    second = await engine.append_override(
        attribution=attribution,
        user_id="user-1",
        category="MARKET_SHOCK",
        reason="new structured evidence reviewed",
    )
    assert first.override_id != second.override_id
    assert db["ag_eval_attribution_overrides"].count() == 2
    stored = db["ag_eval_attributions"].documents[0]
    assert stored["primary_category"] == attribution.primary_category
