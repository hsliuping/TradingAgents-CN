from __future__ import annotations

from datetime import date, datetime, timedelta
from decimal import Decimal

import pytest
from fastapi import HTTPException

from app.routers.alphaguard_recommendations import _require_admin
from app.services.alphaguard.candidate_recommendation_policy import (
    builtin_candidate_recommendation_policy,
)
from app.services.alphaguard.candidate_recommendation_service import (
    CandidatePoolLimitReached,
    CandidateRecommendationService,
    RecommendationReviewConflict,
)
from app.worker.alphaguard import recommendation_tasks
from tests.unit.alphaguard._fakes import FakeDB
from tradingagents.alphaguard.candidate_schemas import CandidateSource
from tradingagents.alphaguard.mongo_indexes import ALPHAGUARD_INDEX_SPECS


TRADE_DATE = date(2026, 8, 1)
USER_ID = "user-pr012"


async def _insert(db: FakeDB, collection: str, documents: list[dict]) -> None:
    for document in documents:
        await db[collection].insert_one(document)


def _quote(symbol: str, trade_date: date, offset: int) -> dict:
    close = Decimal("100") + Decimal(offset) / Decimal("10")
    return {
        "ref_id": f"quote-{symbol}-{trade_date}",
        "data_ref": f"stock_daily_quotes:quote-{symbol}-{trade_date}",
        "symbol": symbol,
        "trade_date": datetime.combine(trade_date, datetime.min.time()),
        "open": close - Decimal("0.2"),
        "high": close + Decimal("0.5"),
        "low": close - Decimal("0.5"),
        "close": close,
        "adjusted_open": close - Decimal("0.2"),
        "adjusted_high": close + Decimal("0.5"),
        "adjusted_low": close - Decimal("0.5"),
        "adjusted_close": close,
        "volume": 1_000_000,
        "amount": 100_000_000,
        "price_adjustment_mode": "QFQ",
        "content_hash": f"{offset + 1:064x}",
    }


async def _seed_eligible(db: FakeDB, symbol: str = "600001") -> None:
    await db["stock_basic_info"].insert_one(
        {
            "code": symbol,
            "symbol": symbol,
            "name": "测试股份",
            "category": "stock_cn",
            "market": "主板",
            "list_date": "2020-01-01",
            "source": "akshare",
        }
    )
    calendar_start = TRADE_DATE - timedelta(days=120)
    await _insert(
        db,
        "trading_calendar",
        [
            {"trade_date": calendar_start + timedelta(days=index), "is_open": True}
            for index in range(150)
        ],
    )
    price_start = TRADE_DATE - timedelta(days=60)
    await _insert(
        db,
        "stock_daily_quotes",
        [_quote(symbol, price_start + timedelta(days=index), index) for index in range(61)],
    )
    await db["market_quotes"].insert_one(
        {
            "symbol": symbol,
            "trade_date": TRADE_DATE.strftime("%Y%m%d"),
            "open": 105,
            "high": 107,
            "low": 104,
            "close": 106,
            "volume": 1_000_000,
            "amount": 100_000_000,
        }
    )
    await db["ag_security_trading_statuses"].insert_one(
        {
            "ref_id": f"status-{symbol}",
            "symbol": symbol,
            "market": "CN",
            "trade_date": TRADE_DATE,
            "calculation_status": "READY",
            "is_suspended": False,
            "content_hash": "a" * 64,
        }
    )
    await db["ag_data_quality_reports"].insert_one(
        {
            "quality_report_id": f"quality-{symbol}",
            "symbol": symbol,
            "trade_date": TRADE_DATE,
            "status": "PASS",
            "immutable_hash": "b" * 64,
        }
    )
    snapshot_id = f"snapshot-{symbol}"
    factors = [
        ("trend", "TREND", 82),
        ("momentum", "MOMENTUM", 78),
        ("liquidity", "LIQUIDITY", 85),
        ("volatility", "VOLATILITY_RISK", 20),
        ("event", "EVENT_RISK", 10),
        ("relative_strength_hs300_20d_v1", "INDUSTRY_STRENGTH", 75),
    ]
    await _insert(
        db,
        "ag_factor_results",
        [
            {
                "result_id": f"factor-{symbol}-{factor_id}",
                "factor_id": factor_id,
                "factor_version": "v1",
                "group": group,
                "symbol": symbol,
                "trade_date": TRADE_DATE,
                "snapshot_id": snapshot_id,
                "normalized_score": score,
                "input_hash": f"{index + 20:064x}",
            }
            for index, (factor_id, group, score) in enumerate(factors)
        ],
    )
    await db["ag_regime_results"].insert_one(
        {
            "regime_result_id": f"regime-{symbol}",
            "snapshot_id": snapshot_id,
            "trade_date": TRADE_DATE,
            "calculation_status": "CALCULATED",
            "regime": "TREND_UP",
            "input_hash": "c" * 64,
        }
    )
    await db["ag_quant_proposals"].insert_one(
        {
            "proposal_id": f"proposal-{symbol}",
            "user_id": USER_ID,
            "symbol": symbol,
            "trade_date": TRADE_DATE,
            "snapshot_id": snapshot_id,
            "status": "WATCH",
            "input_hash": "d" * 64,
        }
    )


async def _seed_trade_day(db: FakeDB, symbol: str, trade_date: date, offset: int) -> None:
    await db["stock_daily_quotes"].insert_one(_quote(symbol, trade_date, offset))
    await db["market_quotes"].insert_one(
        {
            "symbol": symbol,
            "trade_date": trade_date.strftime("%Y%m%d"),
            "open": 106,
            "high": 108,
            "low": 105,
            "close": 107,
            "volume": 1_000_000,
            "amount": 100_000_000,
        }
    )
    await db["ag_security_trading_statuses"].insert_one(
        {
            "ref_id": f"status-{symbol}-{trade_date}",
            "symbol": symbol,
            "market": "CN",
            "trade_date": trade_date,
            "calculation_status": "READY",
            "is_suspended": False,
            "content_hash": f"{offset + 200:064x}",
        }
    )
    await db["ag_data_quality_reports"].insert_one(
        {
            "quality_report_id": f"quality-{symbol}-{trade_date}",
            "symbol": symbol,
            "trade_date": trade_date,
            "status": "PASS",
            "immutable_hash": f"{offset + 300:064x}",
        }
    )


async def _seed_new_factor_evidence(
    db: FakeDB, symbol: str, trade_date: date, *, regime: str
) -> None:
    snapshot_id = f"snapshot-{symbol}-{trade_date}"
    factor_rows = [
        row.copy()
        for row in db["ag_factor_results"].documents
        if row.get("symbol") == symbol
    ]
    for index, row in enumerate(factor_rows):
        row.pop("_id", None)
        row.update(
            {
                "result_id": f"factor-{symbol}-{trade_date}-{index}",
                "trade_date": trade_date,
                "snapshot_id": snapshot_id,
                "input_hash": f"{index + 500:064x}",
            }
        )
        await db["ag_factor_results"].insert_one(row)
    await db["ag_regime_results"].insert_one(
        {
            "regime_result_id": f"regime-{symbol}-{trade_date}",
            "snapshot_id": snapshot_id,
            "trade_date": trade_date,
            "calculation_status": "CALCULATED",
            "regime": regime,
            "input_hash": "e" * 64,
        }
    )
    await db["ag_quant_proposals"].insert_one(
        {
            "proposal_id": f"proposal-{symbol}-{trade_date}",
            "user_id": USER_ID,
            "symbol": symbol,
            "trade_date": trade_date,
            "snapshot_id": snapshot_id,
            "status": "WATCH",
            "input_hash": "f" * 64,
        }
    )


@pytest.mark.asyncio
async def test_policy_universe_and_run_are_deterministic_and_model_free():
    db = FakeDB()
    await _seed_eligible(db)
    service = CandidateRecommendationService(db)

    policy = builtin_candidate_recommendation_policy()
    assert sum(policy.factor_weights.values(), Decimal("0")) == Decimal("1.00")
    assert policy.candidate_pool_soft_limit == 50

    before_models = await db["ag_model_runs"].count_documents({})
    before_orders = await db["ag_order_intents"].count_documents({})
    run, created = await service.run(
        user_id=USER_ID,
        trade_date=TRADE_DATE,
        now=datetime(2026, 8, 1, 18, 30),
    )
    assert created is True
    assert run.total_securities == 1
    assert run.eligible_securities == 1
    assert run.scored_securities == 1
    assert run.recommended_securities == 1
    assert run.model_call_count_before == run.model_call_count_after == before_models
    assert await db["ag_order_intents"].count_documents({}) == before_orders
    recommendation = db["ag_candidate_recommendations"].documents[0]
    assert recommendation["recommendation_score"].to_decimal() > Decimal("55")
    assert recommendation["recommendation_reasons"]
    assert await db["ag_candidates"].count_documents({}) == 0
    assert db["ag_candidate_recommendation_evaluations"].documents[0]["status"] == "PENDING"

    reused, created_again = await service.run(
        user_id=USER_ID,
        trade_date=TRADE_DATE,
        now=datetime(2026, 8, 1, 18, 31),
    )
    assert created_again is False
    assert reused.recommendation_run_id == run.recommendation_run_id
    assert await db["ag_candidate_recommendations"].count_documents({}) == 1
    assert await db["ag_model_runs"].count_documents({}) == before_models


@pytest.mark.asyncio
async def test_eligibility_records_explicit_reasons_and_existing_candidate_exclusion():
    db = FakeDB()
    await _seed_eligible(db)
    await db["stock_basic_info"].insert_one(
        {
            "code": "600002",
            "symbol": "600002",
            "name": "ST退市整理测试",
            "category": "stock_cn",
            "list_date": "",
            "source": "akshare",
            "status": "DELISTED",
        }
    )
    await db["ag_candidates"].insert_one(
        {
            "candidate_id": "existing-candidate",
            "user_id": USER_ID,
            "symbol": "600001",
            "market": "CN",
            "name": "测试股份",
            "sources": ["USER_SELECTED"],
            "status": "WATCHING",
            "priority": 50,
            "added_at": datetime(2026, 7, 1),
            "updated_at": datetime(2026, 7, 1),
            "active_order_ids": [],
            "held_account_ids": [],
            "removal_requested": False,
            "schema_version": "candidate-entry-v1",
        }
    )
    run, _ = await CandidateRecommendationService(db).run(
        user_id=USER_ID,
        trade_date=TRADE_DATE,
        now=datetime(2026, 8, 1, 18, 30),
    )
    rows = {
        row["symbol"]: row for row in db["ag_candidate_eligibility_results"].documents
    }
    assert "ALREADY_IN_CANDIDATE_POOL" in rows["600001"]["filter_reason_codes"]
    assert {"DELISTED", "DELISTING_PERIOD", "ST_NOT_ALLOWED"} <= set(
        rows["600002"]["filter_reason_codes"]
    )
    assert run.recommended_securities == 0


@pytest.mark.asyncio
async def test_position_is_excluded_through_user_owned_paper_account():
    db = FakeDB()
    await _seed_eligible(db)
    await db["ag_paper_accounts"].insert_one(
        {"account_id": "paper-account-pr012", "user_id": USER_ID}
    )
    await db["ag_paper_positions"].insert_one(
        {
            "position_id": "position-pr012",
            "account_id": "paper-account-pr012",
            "symbol": "600001",
            "market": "CN",
            "quantity": 100,
        }
    )

    run, _ = await CandidateRecommendationService(db).run(
        user_id=USER_ID,
        trade_date=TRADE_DATE,
        now=datetime(2026, 8, 1, 18, 30),
    )
    eligibility = db["ag_candidate_eligibility_results"].documents[0]

    assert "POSITION_REQUIRES_MONITORING" in eligibility["filter_reason_codes"]
    assert run.recommended_securities == 0


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("case", "reason"),
    [
        ("suspended", "SUSPENDED"),
        ("history", "PRICE_HISTORY_INSUFFICIENT"),
        ("quality", "DATA_QUALITY_FAILED"),
        ("liquidity", "LOW_LIQUIDITY"),
    ],
)
async def test_core_eligibility_filters_are_explicit(case: str, reason: str):
    db = FakeDB()
    await _seed_eligible(db)
    if case == "suspended":
        db["ag_security_trading_statuses"].documents[0]["is_suspended"] = True
    elif case == "history":
        db["stock_daily_quotes"].documents = db["stock_daily_quotes"].documents[-10:]
    elif case == "quality":
        db["ag_data_quality_reports"].documents[0]["status"] = "FAIL"
    elif case == "liquidity":
        for row in db["stock_daily_quotes"].documents:
            row["amount"] = 1

    run, _ = await CandidateRecommendationService(db).run(
        user_id=USER_ID,
        trade_date=TRADE_DATE,
        now=datetime(2026, 8, 1, 18, 30),
    )
    eligibility = db["ag_candidate_eligibility_results"].documents[0]

    assert reason in eligibility["filter_reason_codes"]
    assert run.recommended_securities == 0


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("constraint", "reason"),
    [
        ("order", "UNFINISHED_ORDER"),
        ("plan", "ACTIVE_TRADE_PLAN"),
        ("evaluation", "PENDING_EVALUATION"),
    ],
)
async def test_existing_work_constraints_prevent_duplicate_recommendation(
    constraint: str, reason: str
):
    db = FakeDB()
    await _seed_eligible(db)
    if constraint == "order":
        await db["ag_paper_orders"].insert_one(
            {
                "order_id": "pending-order-pr012",
                "user_id": USER_ID,
                "symbol": "600001",
                "status": "PENDING",
            }
        )
    elif constraint == "plan":
        await db["analysis_reports"].insert_one(
            {
                "analysis_id": "active-plan-pr012",
                "user_id": USER_ID,
                "stock_symbol": "600001",
                "normal_trade_plan": {
                    "symbol": "600001",
                    "status": "PROPOSE_TRADE",
                },
            }
        )
    else:
        await db["ag_eval_horizon_labels"].insert_one(
            {"subject_id": "subject-pr012", "status": "PENDING"}
        )
        await db["ag_eval_subjects"].insert_one(
            {
                "subject_id": "subject-pr012",
                "user_id": USER_ID,
                "symbol": "600001",
            }
        )

    run, _ = await CandidateRecommendationService(db).run(
        user_id=USER_ID,
        trade_date=TRADE_DATE,
        now=datetime(2026, 8, 1, 18, 30),
    )
    eligibility = db["ag_candidate_eligibility_results"].documents[0]

    assert reason in eligibility["filter_reason_codes"]
    assert run.recommended_securities == 0


@pytest.mark.asyncio
async def test_future_factor_evidence_is_not_used_and_result_limit_is_enforced():
    db = FakeDB()
    await _seed_eligible(db, "600001")
    await _seed_eligible(db, "600002")
    future_date = TRADE_DATE + timedelta(days=1)
    await _seed_new_factor_evidence(
        db, "600001", future_date, regime="EXTREME_RISK"
    )
    service = CandidateRecommendationService(db)
    policy = builtin_candidate_recommendation_policy().model_copy(
        update={"daily_result_limit": 1}
    )

    async def limited_policy():
        return policy

    service.policy_registry.get_active = limited_policy
    run, _ = await service.run(
        user_id=USER_ID,
        trade_date=TRADE_DATE,
        now=datetime(2026, 8, 1, 18, 30),
    )
    recommendation = db["ag_candidate_recommendations"].documents[0]

    assert run.scored_securities == 2
    assert run.recommended_securities == 1
    assert recommendation["regime_type"] == "TREND_UP"
    assert all(str(future_date) not in ref for ref in recommendation["factor_result_refs"])


@pytest.mark.asyncio
async def test_explicit_accept_creates_linked_candidate_and_is_idempotent():
    db = FakeDB()
    await _seed_eligible(db)
    service = CandidateRecommendationService(db)
    await service.run(
        user_id=USER_ID,
        trade_date=TRADE_DATE,
        now=datetime(2026, 8, 1, 18, 30),
    )
    recommendation_id = db["ag_candidate_recommendations"].documents[0][
        "recommendation_id"
    ]
    event, created = await service.review(
        recommendation_id=recommendation_id,
        user_id=USER_ID,
        action="ACCEPTED",
        trace_id="trace-pr012",
    )
    assert created is True
    candidate = await service.db["ag_candidates"].find_one(
        {"candidate_id": event.candidate_id}
    )
    assert "SYSTEM_RECOMMENDED_CONFIRMED" in candidate["sources"]
    assert candidate["recommendation_id"] == recommendation_id
    assert candidate["recommendation_score"] > 0
    assert CandidateSource.SYSTEM_RECOMMENDED_CONFIRMED.value in candidate["sources"]
    repeated, created_again = await service.review(
        recommendation_id=recommendation_id,
        user_id=USER_ID,
        action="ACCEPTED",
    )
    assert created_again is False
    assert repeated.review_event_id == event.review_event_id
    assert await db["ag_candidates"].count_documents({}) == 1
    assert db["ag_candidate_recommendation_evaluations"].documents[0][
        "accepted_into_candidate_pool"
    ] is True


@pytest.mark.asyncio
async def test_expired_recommendation_and_cross_user_access_fail_closed():
    db = FakeDB()
    await _seed_eligible(db)
    service = CandidateRecommendationService(db)
    await service.run(
        user_id=USER_ID,
        trade_date=TRADE_DATE,
        now=datetime(2026, 8, 1, 18, 30),
    )
    recommendation_id = db["ag_candidate_recommendations"].documents[0][
        "recommendation_id"
    ]
    with pytest.raises(LookupError):
        await service.get_recommendation_detail(
            recommendation_id=recommendation_id,
            user_id="another-user",
        )
    db["ag_candidate_recommendations"].documents[0]["expires_at"] = datetime(
        2020, 1, 1
    )
    with pytest.raises(RecommendationReviewConflict, match="expired"):
        await service.review(
            recommendation_id=recommendation_id,
            user_id=USER_ID,
            action="ACCEPTED",
        )


@pytest.mark.asyncio
@pytest.mark.parametrize("action", ["REJECTED", "IGNORED"])
async def test_review_cooldown_blocks_same_business_evidence(action: str):
    db = FakeDB()
    await _seed_eligible(db)
    service = CandidateRecommendationService(db)
    await service.run(
        user_id=USER_ID,
        trade_date=TRADE_DATE,
        now=datetime(2026, 8, 1, 18, 30),
    )
    recommendation_id = db["ag_candidate_recommendations"].documents[0][
        "recommendation_id"
    ]
    await service.review(
        recommendation_id=recommendation_id,
        user_id=USER_ID,
        action=action,
    )
    next_trade_date = TRADE_DATE + timedelta(days=1)
    await _seed_trade_day(db, "600001", next_trade_date, 61)

    run, created = await service.run(
        user_id=USER_ID,
        trade_date=next_trade_date,
        now=datetime(2026, 8, 2, 18, 30),
    )

    assert created is True
    assert run.recommended_securities == 0
    assert await db["ag_candidate_recommendations"].count_documents({}) == 1


@pytest.mark.asyncio
async def test_material_regime_evidence_breaks_rejection_cooldown_with_new_version():
    db = FakeDB()
    await _seed_eligible(db)
    service = CandidateRecommendationService(db)
    await service.run(
        user_id=USER_ID,
        trade_date=TRADE_DATE,
        now=datetime(2026, 8, 1, 18, 30),
    )
    prior_id = db["ag_candidate_recommendations"].documents[0]["recommendation_id"]
    await service.review(
        recommendation_id=prior_id,
        user_id=USER_ID,
        action="REJECTED",
    )
    next_trade_date = TRADE_DATE + timedelta(days=1)
    await _seed_trade_day(db, "600001", next_trade_date, 61)
    await _seed_new_factor_evidence(
        db, "600001", next_trade_date, regime="RANGE_STRONG"
    )

    run, _ = await service.run(
        user_id=USER_ID,
        trade_date=next_trade_date,
        now=datetime(2026, 8, 2, 18, 30),
    )
    recommendations = db["ag_candidate_recommendations"].documents

    assert run.recommended_securities == 1
    assert len(recommendations) == 2
    assert recommendations[-1]["supersedes_recommendation_id"] == prior_id
    assert recommendations[-1]["recommendation_id"] != prior_id


@pytest.mark.asyncio
async def test_batch_review_and_candidate_pool_soft_limit_are_fail_closed():
    db = FakeDB()
    await _seed_eligible(db, "600001")
    await _seed_eligible(db, "600002")
    service = CandidateRecommendationService(db)
    await service.run(
        user_id=USER_ID,
        trade_date=TRADE_DATE,
        now=datetime(2026, 8, 1, 18, 30),
    )
    recommendation_ids = [
        row["recommendation_id"]
        for row in db["ag_candidate_recommendations"].documents
    ]
    batch = await service.batch_review(
        recommendation_ids=recommendation_ids,
        user_id=USER_ID,
        action="REJECTED",
    )
    assert batch["processed"] == 2
    assert await db["ag_candidates"].count_documents({}) == 0

    db = FakeDB()
    await _seed_eligible(db)
    service = CandidateRecommendationService(db)
    await service.run(
        user_id=USER_ID,
        trade_date=TRADE_DATE,
        now=datetime(2026, 8, 1, 18, 30),
    )
    recommendation_id = db["ag_candidate_recommendations"].documents[0][
        "recommendation_id"
    ]
    for index in range(50):
        await db["ag_candidates"].insert_one(
            {
                "candidate_id": f"candidate-{index}",
                "user_id": USER_ID,
                "symbol": f"{700000 + index:06d}",
                "market": "CN",
                "name": f"候选{index}",
                "sources": ["USER_SELECTED"],
                "status": "WATCHING",
                "priority": 50,
                "added_at": datetime(2026, 7, 1),
                "updated_at": datetime(2026, 7, 1),
                "active_order_ids": [],
                "held_account_ids": [],
                "removal_requested": False,
                "schema_version": "candidate-entry-v1",
            }
        )
    with pytest.raises(CandidatePoolLimitReached):
        await service.review(
            recommendation_id=recommendation_id,
            user_id=USER_ID,
            action="ACCEPTED",
        )
    assert await db["ag_candidates"].count_documents({}) == 50
    assert await db["ag_candidate_recommendation_review_events"].count_documents(
        {}
    ) == 0


@pytest.mark.asyncio
async def test_evaluation_matures_without_account_or_order_side_effects():
    db = FakeDB()
    await _seed_eligible(db)
    service = CandidateRecommendationService(db)
    await service.run(
        user_id=USER_ID,
        trade_date=TRADE_DATE,
        now=datetime(2026, 8, 1, 18, 30),
    )
    db["ag_quant_proposals"].documents[0]["trade_date"] = datetime.combine(
        TRADE_DATE, datetime.min.time()
    )
    benchmark_dates = [TRADE_DATE + timedelta(days=index) for index in range(21)]
    for index, trade_date in enumerate(benchmark_dates):
        if index:
            await db["stock_daily_quotes"].insert_one(
                _quote("600001", trade_date, 61 + index)
            )
        await db["stock_daily_quotes"].insert_one(
            {
                "ref_id": f"benchmark-{trade_date}",
                "symbol": "000300",
                "trade_date": datetime.combine(trade_date, datetime.min.time()),
                "open": 4000 + index,
                "high": 4010 + index,
                "low": 3990 + index,
                "close": 4000 + index,
                "volume": 1,
                "amount": 1,
                "price_adjustment_mode": "INDEX_UNADJUSTED_EQUIVALENT",
                "content_hash": f"{900 + index:064x}",
            }
        )
    before = {
        name: await db[name].count_documents({})
        for name in (
            "ag_order_intents",
            "ag_paper_orders",
            "ag_paper_fills",
            "ag_paper_positions",
            "ag_paper_ledger_entries",
        )
    }

    result = await service.refresh_evaluations(
        as_of_trade_date=TRADE_DATE + timedelta(days=20)
    )
    evaluation = db["ag_candidate_recommendation_evaluations"].documents[0]

    assert result == {"calculated": 1, "partial": 0, "insufficient": 0}
    assert evaluation["status"] == "CALCULATED"
    assert all(
        item["status"] == "CALCULATED"
        for item in evaluation["horizon_results"].values()
    )
    after = {
        name: await db[name].count_documents({}) for name in before
    }
    assert after == before


@pytest.mark.asyncio
async def test_operations_metrics_are_read_only_and_scheduler_restart_is_idempotent(
    monkeypatch,
):
    db = FakeDB()
    await _seed_eligible(db)
    service = CandidateRecommendationService(db)
    assert await db["ag_candidate_recommendation_policies"].count_documents({}) == 0
    metrics = await service.metrics()
    assert metrics["recommendation_ready"] is True
    assert await db["ag_candidate_recommendation_policies"].count_documents({}) == 0

    db["ag_quant_proposals"].documents[0]["trade_date"] = datetime.combine(
        TRADE_DATE, datetime.min.time()
    )
    await db["stock_basic_info"].insert_one(
        {
            "code": "600001",
            "symbol": "600001",
            "name": "测试股份",
            "category": "stock_cn",
            "market": "CN",
            "list_date": "2020-01-01",
            "source": "baostock",
        }
    )
    await db["users"].insert_one({"username": "first", "is_active": True})
    await db["users"].insert_one({"username": "second", "is_active": True})
    monkeypatch.setattr(recommendation_tasks, "get_mongo_db", lambda: db)
    first = await recommendation_tasks.scheduled_candidate_recommendation_scan()
    model_count = await db["ag_model_runs"].count_documents({})
    recommendation_count = await db["ag_candidate_recommendations"].count_documents({})
    second = await recommendation_tasks.scheduled_candidate_recommendation_scan()

    assert first == {"created": 2, "reused": 0, "failed": 0}
    assert second == {"created": 0, "reused": 2, "failed": 0}
    assert (await service.metrics())["security_count"] == 1
    assert await db["ag_model_runs"].count_documents({}) == model_count == 0
    assert (
        await db["ag_candidate_recommendations"].count_documents({})
        == recommendation_count
        == 2
    )


def test_admin_gate_and_index_contract():
    _require_admin({"is_admin": True})
    with pytest.raises(HTTPException) as denied:
        _require_admin({"is_admin": False})
    assert denied.value.status_code == 403
    for name in (
        "ag_candidate_universe_manifests",
        "ag_candidate_eligibility_results",
        "ag_candidate_recommendation_runs",
        "ag_candidate_recommendations",
        "ag_candidate_recommendation_review_events",
        "ag_candidate_recommendation_evaluations",
    ):
        assert name in ALPHAGUARD_INDEX_SPECS


def test_frontend_is_chinese_review_flow_without_model_or_order_entry():
    page = open(
        "frontend/src/views/AlphaGuard/Recommendations.vue", encoding="utf-8"
    ).read()
    for text in (
        "股票推荐",
        "查看今日推荐",
        "加入候选池",
        "暂不处理",
        "拒绝推荐",
        "推荐仅用于筛选研究对象",
    ):
        assert text in page
    assert "TradingAgents" not in page
    assert "OrderIntent" not in page
