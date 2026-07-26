from datetime import date, datetime
from pathlib import Path

import pytest

from app.schemas.alphaguard.decision import ConsensusDecision, canonical_hash
from app.services.alphaguard.evidence_snapshot_service import (
    calculate_immutable_hash,
)
from app.services.alphaguard.hard_risk_engine import HardRiskEngine
from app.services.alphaguard.risk_policy_registry import builtin_risk_policy
from app.services.alphaguard.snapshot_data_resolver import ResolvedSnapshotData
from tests.unit.alphaguard.pr005_helpers import make_context, make_plan, make_review
from tradingagents.alphaguard.evidence_schemas import (
    DataQualityReport,
    EvidenceSnapshot,
)


def resolved_data(action="BUY", **overrides):
    context = make_context(action)
    quality = DataQualityReport(
        quality_report_id="quality",
        symbol=context.symbol,
        market=context.market,
        trade_date=context.trade_date,
        status="PASS",
        completeness_score=1,
        freshness_score=1,
        consistency_score=1,
        checked_at=datetime(2026, 7, 1),
    )
    draft = EvidenceSnapshot(
        snapshot_id=context.snapshot_id,
        user_id=context.user_id,
        analysis_id=context.analysis_id,
        symbol=context.symbol,
        market=context.market,
        trade_date=context.trade_date,
        price_cutoff_at=datetime(2026, 7, 1, 15),
        news_cutoff_at=datetime(2026, 7, 1, 15),
        announcement_cutoff_at=datetime(2026, 7, 1, 15),
        price_data_version="fixed",
        financial_data_version="fixed",
        news_data_version="fixed",
        data_quality=quality,
        raw_refs={"prices": ["stock_daily_quotes:p1"]},
        factor_version_set={"factor": "1.0.0"},
        strategy_version="strategy-set-v1",
        immutable_hash="0" * 64,
        created_at=datetime(2026, 7, 1),
    )
    snapshot = draft.model_copy(
        update={"immutable_hash": calculate_immutable_hash(draft)}
    )
    account = {
        "_reference": "paper_accounts:account-1",
        "account_id": "account-1",
        "user_id": "user",
        "status": "ACTIVE",
        "market": "CN",
        "currency": "CNY",
        "cash": {"CNY": 800_000},
        "equity": {"CNY": 1_000_000},
        "total_exposure_pct": 0.20,
        "industry_exposure_pct": {"白酒": 0.05},
        "new_positions_today": 0,
        "active_orders_complete": True,
        "updated_at": "2026-07-01T14:00:00",
    }
    price = {
        "_reference": "stock_daily_quotes:p1",
        "symbol": "600519",
        "market": "CN",
        "trade_date": "2026-07-01",
        "close": 100,
        "average_amount_20d": 100_000_000,
    }
    instrument = {
        "_reference": "stock_basic_info:instrument-1",
        "symbol": "600519",
        "market": "CN",
        "industry": "白酒",
        "suspended": False,
        "is_st": False,
        "at_limit_up": False,
        "at_limit_down": False,
        "average_amount_20d": 100_000_000,
    }
    positions = []
    if action in {"SELL", "REDUCE"}:
        positions = [
            {
                "_reference": "paper_positions:position-1",
                "user_id": "user",
                "symbol": "600519",
                "market": "CN",
                "quantity": 550,
                "available_qty": 550,
                "updated_at": "2026-07-01T14:00:00",
            }
        ]
    values = {
        "accounts": [account],
        "prices": [price],
        "instruments": [instrument],
        "positions": positions,
        "portfolio_positions": [],
        "orders": [],
        "trading_calendar": [
            {
                "_reference": "trading_calendar:c1",
                "session_date": "2026-07-02",
                "is_open": True,
                "as_of": "2026-06-01",
            }
        ],
    }
    values.update(overrides)
    data = ResolvedSnapshotData(
        snapshot=snapshot,
        input_refs=["stock_daily_quotes:p1"],
        excluded_refs=[],
        input_hash="9" * 64,
        **values,
    )
    return context, data


def consensus(context, plan):
    review = make_review(context, plan)
    return ConsensusDecision(
        consensus_id="consensus-1",
        analysis_id=context.analysis_id,
        snapshot_id=context.snapshot_id,
        quant_proposal_id=context.quant_proposal_id,
        plan_id=plan.plan_id,
        review_id=review.review_id,
        status="CONSENSUS_PASS",
        final_plan=plan,
        final_plan_hash=canonical_hash(plan),
        revision_round=plan.revision_round,
        requires_normal_reconfirm=False,
        reasons=["confirmed"],
        validation_errors=[],
        created_at=datetime(2026, 7, 1),
    )


def run(action="BUY", **overrides):
    context, data = resolved_data(action, **overrides)
    plan = make_plan(context)
    return HardRiskEngine().evaluate(
        data=data,
        context=context,
        consensus=consensus(context, plan),
        policy=builtin_risk_policy(),
        account_id="account-1",
        now=datetime(2026, 7, 1, 16),
    )


def rule(result, rule_id):
    return next(item for item in result.triggered_rules if item.rule_id == rule_id)


def evaluate_case(context, data, *, plan=None, policy=None, now=None):
    plan = plan or make_plan(context)
    return HardRiskEngine().evaluate(
        data=data,
        context=context,
        consensus=consensus(context, plan),
        policy=policy or builtin_risk_policy(),
        account_id="account-1",
        now=now or datetime(2026, 7, 1, 16),
    )


def test_buy_passes_with_snapshot_account_state_calendar_and_lot_rounding():
    result = run()
    assert result.status == "PASS"
    assert result.action == "BUY"
    assert result.approved_quantity % 100 == 0
    assert result.order_intent_created is False
    assert result.requires_execution_recheck is True


@pytest.mark.parametrize(
    ("field", "value", "expected"),
    [
        ("suspended", True, "REJECT"),
        ("is_st", True, "REJECT"),
        ("at_limit_up", True, "REJECT"),
    ],
)
def test_fixed_trading_prohibitions_reject_buy(field, value, expected):
    context, data = resolved_data()
    instrument = dict(data.instruments[0])
    instrument[field] = value
    result = run(instruments=[instrument])
    assert rule(result, "AG-RISK-TRADING-STATUS").status == expected
    assert result.status == "REJECT"


@pytest.mark.parametrize(
    "missing",
    ["suspended", "is_st", "at_limit_up"],
)
def test_missing_core_trading_state_suspends(missing):
    context, data = resolved_data()
    instrument = dict(data.instruments[0])
    instrument.pop(missing)
    result = run(instruments=[instrument])
    assert result.status == "SUSPEND"


def test_missing_account_or_calendar_suspends_without_guessing():
    assert run(accounts=[]).status == "SUSPEND"
    assert run(trading_calendar=[]).status == "SUSPEND"


def test_data_quality_snapshot_hash_and_plan_expiry_fail_closed():
    context, data = resolved_data()
    failed_context = context.model_copy(update={"data_quality_status": "FAIL"})
    failed = evaluate_case(failed_context, data)
    assert failed.status == "REJECT"
    assert "DataQuality FAIL" in rule(failed, "AG-RISK-INTEGRITY").reason

    damaged = data.model_copy(
        update={
            "snapshot": data.snapshot.model_copy(
                update={"immutable_hash": "f" * 64}
            )
        }
    )
    assert evaluate_case(context, damaged).status == "REJECT"

    expired_plan = make_plan(context).model_copy(
        update={"valid_until": datetime(2026, 6, 30)}
    )
    expired = evaluate_case(context, data, plan=expired_plan)
    assert rule(expired, "AG-RISK-VALIDITY").status == "REJECT"


def test_hard_risk_refuses_non_pass_consensus():
    context, data = resolved_data()
    plan = make_plan(context)
    denied = consensus(context, plan).model_copy(
        update={
            "status": "CONSENSUS_REJECT",
            "final_plan": None,
            "final_plan_hash": None,
        }
    )
    with pytest.raises(ValueError, match="CONSENSUS_PASS"):
        HardRiskEngine().evaluate(
            data=data,
            context=context,
            consensus=denied,
            policy=builtin_risk_policy(),
            account_id="account-1",
        )


def test_position_and_cash_caps_can_reduce_and_zero_cap_rejects():
    context, data = resolved_data()
    account = dict(data.accounts[0])
    account["total_exposure_pct"] = 0.58
    reduced = run(accounts=[account])
    assert reduced.status == "REDUCE"
    assert reduced.approved_position_pct < reduced.original_position_pct

    account["total_exposure_pct"] = 0.60
    rejected = run(accounts=[account])
    assert rejected.status == "REJECT"


def test_cash_single_name_and_industry_caps_only_reduce_or_reject():
    context, data = resolved_data()
    account = dict(data.accounts[0])
    account["cash"] = {"CNY": 250_000}
    cash_reduced = run(accounts=[account])
    assert cash_reduced.status == "REDUCE"
    account["cash"] = {"CNY": 200_000}
    assert run(accounts=[account]).status == "REJECT"

    policy = builtin_risk_policy().model_copy(
        update={"max_single_position_pct": 0.05}
    )
    single = evaluate_case(context, data, policy=policy)
    assert single.status == "REDUCE"
    assert single.approved_position_pct == 0.05

    account = dict(data.accounts[0])
    account["industry_exposure_pct"] = {"白酒": 0.23}
    industry = run(accounts=[account])
    assert industry.status == "REDUCE"
    account["industry_exposure_pct"] = {"白酒": 0.25}
    assert run(accounts=[account]).status == "REJECT"


def test_new_position_and_duplicate_order_rules_reject():
    context, data = resolved_data()
    account = dict(data.accounts[0])
    account["new_positions_today"] = 3
    assert run(accounts=[account]).status == "REJECT"
    active = {
        "_reference": "paper_orders:o1",
        "order_id": "o1",
        "user_id": "user",
        "code": "600519",
        "side": "BUY",
        "status": "pending",
    }
    assert run(orders=[active]).status == "REJECT"


def test_liquidity_and_configured_factor_risk_rules_are_explicit():
    context, data = resolved_data()
    liquidity_policy = builtin_risk_policy().model_copy(
        update={"minimum_average_amount_20d": 200_000_000}
    )
    liquidity = evaluate_case(context, data, policy=liquidity_policy)
    assert rule(liquidity, "AG-RISK-LIQUIDITY").status == "REJECT"

    assert (
        rule(run(), "AG-RISK-VOLATILITY").status == "NOT_APPLICABLE"
    )
    configured = builtin_risk_policy().model_copy(
        update={"maximum_volatility_risk_score": 20}
    )
    missing = evaluate_case(context, data, policy=configured)
    assert rule(missing, "AG-RISK-VOLATILITY").status == "SUSPEND"

    risky_context = context.model_copy(
        update={"factor_summary": {**context.factor_summary, "VOLATILITY_RISK": 80}}
    )
    risky = evaluate_case(risky_context, data, policy=configured)
    assert rule(risky, "AG-RISK-VOLATILITY").status == "REJECT"


def test_sell_respects_t1_available_qty_and_odd_lot_exit():
    result = run("SELL")
    assert result.action == "SELL"
    assert result.approved_quantity == 550
    assert result.status == "PASS"
    context, data = resolved_data("SELL")
    position = dict(data.positions[0])
    position["available_qty"] = 0
    assert run("SELL", positions=[position]).status == "REJECT"


def test_sell_limit_down_rejects_but_st_does_not_block_exit():
    context, data = resolved_data("SELL")
    instrument = dict(data.instruments[0])
    instrument["is_st"] = True
    assert run("SELL", instruments=[instrument]).status == "PASS"
    instrument["at_limit_down"] = True
    assert run("SELL", instruments=[instrument]).status == "REJECT"


@pytest.mark.parametrize("action", ["BUY", "SELL", "REDUCE"])
def test_hard_risk_never_changes_direction(action):
    result = run(action)
    assert result.action == action


def test_hard_risk_modules_do_not_import_order_or_paper_execution_services():
    root = Path(__file__).resolve().parents[3]
    for relative in (
        "app/services/alphaguard/hard_risk_engine.py",
        "app/services/alphaguard/decision_pipeline.py",
    ):
        source = (root / relative).read_text(encoding="utf-8")
        assert "OrderService" not in source
        assert "/paper/order" not in source
        assert "place_order" not in source
