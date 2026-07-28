from __future__ import annotations

from datetime import date, datetime, time, timedelta
from decimal import Decimal
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from app.schemas.alphaguard import QuantTradeProposal
from app.services.alphaguard.historical_backfill_service import (
    HistoricalBackfillService,
)
from app.services.alphaguard.historical_market_context_service import (
    HistoricalMarketContextConflict,
    HistoricalMarketContextService,
    HistoricalMarketFetchResult,
)
from app.services.alphaguard.historical_shadow_execution_service import (
    HistoricalShadowExecutionService,
)
from app.services.alphaguard.paper_policy_registry import PaperPolicyRegistry
from tests.unit.alphaguard._fakes import FakeDB
from tradingagents.alphaguard.backfill_schemas import (
    HistoricalBackfillRun,
    HistoricalBackfillSample,
    HistoricalCoverageRecord,
    backfill_hash,
)


def _run(*, selected: list[date]) -> HistoricalBackfillRun:
    return HistoricalBackfillRun(
        backfill_run_id="backfill-1",
        status="CREATED",
        user_id="admin-1",
        symbols=["600519"],
        start_trade_date=selected[0],
        end_trade_date=selected[-1],
        sampling_method="WEEKLY_LAST_SESSION",
        selected_trade_dates=selected,
        code_commit="commit",
        code_tree_hash="tree",
        config_hash="a" * 64,
        input_hash="b" * 64,
        version_refs={"factor_set": "factor-set-v1"},
        total_samples=len(selected),
        created_at=datetime(2026, 7, 27),
        updated_at=datetime(2026, 7, 27),
    )


def _weekdays(end: date, count: int) -> list[date]:
    result: list[date] = []
    current = end
    while len(result) < count:
        if current.weekday() < 5:
            result.append(current)
        current -= timedelta(days=1)
    return sorted(result)


async def _seed_price_series(db, symbol: str, sessions: list[date]) -> None:
    for index, session in enumerate(sessions):
        close = Decimal("10") + Decimal(index) / Decimal("100")
        await db["stock_daily_quotes"].insert_one(
            {
                "ref_id": f"{symbol}-{session}",
                "data_ref": f"quote:{symbol}:{session}:qfq-v1",
                "symbol": symbol,
                "market": "CN",
                "trade_date": datetime.combine(session, time()),
                "period": "daily",
                "open": close,
                "high": close + Decimal("0.20"),
                "low": close - Decimal("0.20"),
                "close": close,
                "adjusted_open": close,
                "adjusted_high": close + Decimal("0.20"),
                "adjusted_low": close - Decimal("0.20"),
                "adjusted_close": close,
                "volume": 1_000_000,
                "amount": Decimal("10000000"),
                "price_adjustment_mode": "QFQ",
                "price_data_version": "qfq-v1",
                "adjusted_data_version": "qfq-v1",
                "raw_data_version": "raw-v1",
            }
        )


@pytest.mark.asyncio
async def test_weekly_last_session_uses_persisted_calendar_not_natural_days():
    db = FakeDB()
    sessions = [
        date(2026, 1, 5),
        date(2026, 1, 6),
        date(2026, 1, 9),
        date(2026, 1, 12),
        date(2026, 1, 15),
        date(2026, 1, 16),
    ]
    for session in sessions:
        await db["trading_calendar"].insert_one(
            {"market": "CN", "session_date": session.isoformat(), "is_open": True}
        )
    await db["trading_calendar"].insert_one(
        {"market": "CN", "session_date": "2026-01-10", "is_open": False}
    )
    selected = await HistoricalBackfillService(db).select_trade_dates(
        start_trade_date=date(2026, 1, 1),
        end_trade_date=date(2026, 1, 16),
    )
    assert selected == [date(2026, 1, 9), date(2026, 1, 16)]


def test_research_contract_cannot_authorize_automated_execution():
    with pytest.raises(ValidationError):
        HistoricalBackfillRun(
            **{
                **_run(selected=[date(2026, 1, 9)]).model_dump(mode="python"),
                "research_only": False,
            }
        )
    with pytest.raises(ValidationError):
        HistoricalBackfillRun(
            **{
                **_run(selected=[date(2026, 1, 9)]).model_dump(mode="python"),
                "automated_execution_allowed": True,
            }
        )


@pytest.mark.asyncio
async def test_coverage_strictly_cuts_financial_news_announcement_and_future_prices():
    db = FakeDB()
    trade_date = date(2026, 4, 3)
    historical_sessions = _weekdays(trade_date, 70)
    future_sessions = []
    cursor = trade_date + timedelta(days=1)
    while len(future_sessions) < 25:
        if cursor.weekday() < 5:
            future_sessions.append(cursor)
        cursor += timedelta(days=1)
    for session in historical_sessions + future_sessions:
        await db["trading_calendar"].insert_one(
            {"market": "CN", "session_date": session.isoformat(), "is_open": True}
        )
    await _seed_price_series(db, "600519", historical_sessions)
    await _seed_price_series(db, "000300", historical_sessions)
    await db["stock_daily_quotes"].insert_one(
        {
            "ref_id": "future-price",
            "data_ref": "quote:600519:future:qfq-v1",
            "symbol": "600519",
            "market": "CN",
            "trade_date": datetime.combine(future_sessions[0], time()),
            "period": "daily",
            "price_adjustment_mode": "QFQ",
            "price_data_version": "qfq-v1",
            "raw_data_version": "raw-v1",
        }
    )
    await db["stock_financial_data"].insert_one(
        {
            "ref_id": "financial-known",
            "symbol": "600519",
            "market": "CN",
            "report_period": "2025-12-31",
            "f_ann_date": "2026-03-20",
            "published_at": "2026-03-20T08:00:00",
            "data_version": "financial-v1",
        }
    )
    await db["stock_financial_data"].insert_one(
        {
            "ref_id": "financial-future-disclosure",
            "symbol": "600519",
            "market": "CN",
            "report_period": "2025-12-31",
            "f_ann_date": "2026-04-20",
            "published_at": "2026-03-01T08:00:00",
            "data_version": "financial-v1",
        }
    )
    for collection, known, future, fields in (
        (
            "stock_news",
            "news-known",
            "news-future",
            {"publish_time": "2026-04-03T10:00:00"},
        ),
        (
            "stock_announcements",
            "announcement-known",
            "announcement-future",
            {"announcement_time": "2026-04-03T11:00:00"},
        ),
    ):
        await db[collection].insert_one(
            {
                "ref_id": known,
                "symbol": "600519",
                "market": "CN",
                "data_version": "event-v1",
                **fields,
            }
        )
        future_fields = {
            key: "2026-04-03T16:00:00" for key in fields
        }
        await db[collection].insert_one(
            {
                "ref_id": future,
                "symbol": "600519",
                "market": "CN",
                "data_version": "event-v1",
                **future_fields,
            }
        )
    await db["stock_industry_history"].insert_one(
        {
            "ref_id": "industry-current-only",
            "symbol": "600519",
            "market": "CN",
            "effective_from": "2020-01-01",
            "effective_to": None,
            "history_coverage_status": "CURRENT_ONLY",
        }
    )
    await db["ag_research_market_contexts"].insert_one(
        {
            "context_id": "context-1",
            "market": "CN",
            "trade_date": datetime.combine(trade_date, time()),
            "available_at": datetime.combine(trade_date, time(15)),
            "provider": "baostock",
            "provider_version": "test",
            "data_version": "baostock:test:MARKET_CONTEXT:v1",
            "source_record_id": "source-1",
            "source_refs": ["research_market_context_source:source-1"],
            "advance_count": 3000,
            "decline_count": 2000,
            "unchanged_count": 100,
            "total_amount": Decimal("100000000"),
            "amount_ratio20": Decimal("1.01"),
            "new_high_count": 100,
            "new_low_count": 50,
            "industry_diffusion": Decimal("0.6"),
            "extreme_risk_flag": False,
            "universe_coverage": Decimal("0.99"),
            "high_low_coverage": Decimal("0.95"),
            "sector_coverage": Decimal("1"),
            "calculation_status": "READY",
            "missing_fields": [],
            "methodology": {"breadth": "point-in-time"},
            "content_hash": "c" * 64,
            "created_at": datetime(2026, 7, 27),
            "schema_version": "alphaguard-historical-backfill-v1",
        }
    )

    coverage, resolved = await HistoricalBackfillService(db).coverage_audit(
        run=_run(selected=[trade_date]), symbol="600519", trade_date=trade_date
    )

    assert coverage.replay_allowed is True
    assert [item["ref_id"] for item in resolved["financials"]] == [
        "financial-known"
    ]
    assert [item["ref_id"] for item in resolved["news"]] == ["news-known"]
    assert [item["ref_id"] for item in resolved["announcements"]] == [
        "announcement-known"
    ]
    assert all(
        item["trade_date"].date() <= trade_date for item in resolved["prices"]
    )
    assert resolved["industry_history"] == []
    assert "HISTORICAL_INDUSTRY_MAPPING_UNAVAILABLE" in coverage.warnings

    service = HistoricalBackfillService(db)
    snapshot, data = await service._build_snapshot(
        run=_run(selected=[trade_date]),
        sample_id=service.sample_id("backfill-1", "600519", trade_date),
        symbol="600519",
        trade_date=trade_date,
        coverage=coverage,
        resolved=resolved,
        locked={
            "factor_versions": {"MOMENTUM_20D": "1.0.0"},
            "champion_refs": {},
        },
    )
    assert snapshot.research_only is True
    assert len(data.input_hash) == 64


class _MarketProvider:
    name = "test-provider"

    def __init__(self, *, changed: bool = False):
        self.changed = changed

    def capability_check(self):
        return {"available": True, "provider_version": "1.0"}

    def fetch(self, *, selected_dates, policy, progress=None):
        source_payloads = {}
        context_payloads = {}
        for trade_date in selected_dates:
            source = {
                "market": "CN",
                "trade_date": trade_date,
                "provider": "test-provider",
                "provider_version": "1.0",
                "normalization_version": "v1",
                "source_record_count": 1,
                "expected_universe_count": 1,
                "normalized_records": [
                    {"code": "sh.600519", "pct_change": 2 if self.changed else 1}
                ],
                "market_amount_window": [],
                "sector_records": [{"code": "sector", "pct_change": 1}],
                "source_response_hashes": {"source": "d" * 64},
            }
            source["content_hash"] = backfill_hash(source)
            source_payloads[trade_date] = source
            context_payloads[trade_date] = {
                "market": "CN",
                "trade_date": trade_date,
                "available_at": datetime.combine(trade_date, time(15)),
                "provider": "test-provider",
                "provider_version": "1.0",
                "data_version": "test-provider:1.0:MARKET_CONTEXT:v1",
                "advance_count": 1,
                "decline_count": 0,
                "unchanged_count": 0,
                "total_amount": Decimal("1"),
                "amount_ratio20": None,
                "new_high_count": None,
                "new_low_count": None,
                "industry_diffusion": Decimal("1"),
                "extreme_risk_flag": False,
                "universe_coverage": Decimal("1"),
                "high_low_coverage": Decimal("0"),
                "sector_coverage": Decimal("1"),
                "calculation_status": "READY",
                "missing_fields": [],
                "methodology": {"breadth": "test"},
            }
        return HistoricalMarketFetchResult(
            provider="test-provider",
            provider_version="1.0",
            normalization_version="v1",
            source_payloads=source_payloads,
            context_payloads=context_payloads,
            failures=(),
        )


@pytest.mark.asyncio
async def test_market_context_sync_is_idempotent_and_conflicts_fail_closed():
    db = FakeDB()
    service = HistoricalMarketContextService(db)
    selected = [date(2026, 1, 9)]
    first = await service.sync(selected_dates=selected, provider=_MarketProvider())
    second = await service.sync(selected_dates=selected, provider=_MarketProvider())
    assert first["created"] == 1
    assert second["reused"] == 1
    assert db["ag_research_market_context_sources"].count() == 1
    assert db["ag_research_market_contexts"].count() == 1
    assert db["ag_research_backfill_events"].count() == 1
    with pytest.raises(HistoricalMarketContextConflict):
        await service.sync(
            selected_dates=selected, provider=_MarketProvider(changed=True)
        )


@pytest.mark.asyncio
async def test_failed_sample_can_resume_without_duplicate_terminal_objects(monkeypatch):
    db = FakeDB()
    trade_date = date(2026, 1, 9)
    run = _run(selected=[trade_date])
    sample_id = HistoricalBackfillService.sample_id(
        run.backfill_run_id, "600519", trade_date
    )
    failed = HistoricalBackfillSample(
        sample_id=sample_id,
        backfill_run_id=run.backfill_run_id,
        symbol="600519",
        trade_date=trade_date,
        status="FAILED",
        reason="interrupted",
        version_refs=run.version_refs,
        input_hash=backfill_hash(
            {
                "backfill_run_id": run.backfill_run_id,
                "symbol": "600519",
                "trade_date": trade_date,
                "version_refs": run.version_refs,
                "run_input_hash": run.input_hash,
            }
        ),
        attempt_count=1,
        error_history=[{"error_type": "Interrupted"}],
        created_at=datetime(2026, 7, 27),
        updated_at=datetime(2026, 7, 27),
    )
    await db["ag_research_backfill_samples"].insert_one(
        failed.model_dump(mode="python")
    )
    coverage = HistoricalCoverageRecord(
        coverage_id="coverage-resume",
        backfill_run_id=run.backfill_run_id,
        sample_id=sample_id,
        symbol="600519",
        trade_date=trade_date,
        status="INSUFFICIENT_DATA",
        replay_allowed=False,
        domains={},
        critical_missing=["MARKET_CONTEXT"],
        input_hash="2" * 64,
        created_at=datetime(2026, 7, 27),
    )

    async def blocked_coverage(**kwargs):
        return coverage, {}

    service = HistoricalBackfillService(db)
    monkeypatch.setattr(service, "coverage_audit", blocked_coverage)
    resumed = await service._run_sample(
        run=run,
        symbol="600519",
        trade_date=trade_date,
        as_of_trade_date=date(2026, 7, 27),
        locked={},
        model_replay=False,
    )
    assert resumed.status == "BACKFILL_SKIPPED_INSUFFICIENT_DATA"
    assert resumed.attempt_count == 2
    assert db["ag_research_backfill_samples"].count() == 1
    assert db["ag_research_snapshots"].count() == 0


def _proposal(trade_date: date) -> QuantTradeProposal:
    return QuantTradeProposal(
        proposal_id="proposal-1",
        candidate_id=None,
        user_id="admin-1",
        symbol="600519",
        market="CN",
        trade_date=trade_date,
        snapshot_id="research-snapshot-1",
        strategy_id="SWING_TREND_PULLBACK",
        strategy_version="1.0.0",
        regime_result_id="regime-1",
        factor_set_version="factor-set-v1",
        status="TRIGGERED",
        action_candidate="BUY",
        entry_zone={"lower": 9.5, "upper": 10.0},
        initial_position_pct=0.05,
        max_position_pct=0.1,
        add_conditions=[],
        reduce_conditions=[],
        exit_conditions=[],
        invalidation_conditions=[],
        valid_until=datetime(2026, 1, 5, 23, 59),
        expected_holding_days=(5, 20),
        factor_summary={},
        factor_result_ids=[],
        evidence_refs=[],
        risk_flags=[],
        reason_codes=["test"],
        explanation="fixed research proposal",
        input_hash="e" * 64,
        created_at=datetime(2026, 1, 2, 15),
    )


@pytest.mark.asyncio
async def test_shadow_execution_reuses_matching_and_fee_without_production_writes():
    db = FakeDB()
    await PaperPolicyRegistry(db).register_builtins()
    await db["trading_calendar"].insert_one(
        {"market": "CN", "session_date": "2026-01-05", "is_open": True}
    )
    await db["stock_daily_quotes"].insert_one(
        {
            "ref_id": "raw-execution-1",
            "data_ref": "raw:600519:2026-01-05:raw-v1",
            "symbol": "600519",
            "market": "CN",
            "trade_date": "2026-01-05",
            "period": "daily",
            "open": Decimal("9.50"),
            "high": Decimal("10.20"),
            "low": Decimal("9.40"),
            "close": Decimal("10.00"),
            "pre_close": Decimal("9.45"),
            "volume": 1_000_000,
            "amount": Decimal("10000000"),
            "suspended": False,
            "st_status": False,
            "limit_up_price": Decimal("10.40"),
            "limit_down_price": Decimal("8.50"),
            "raw_data_version": "raw-v1",
            "updated_at": datetime(2026, 7, 27),
        }
    )
    await db["stock_daily_quotes"].insert_one(
        {
            "symbol": "600519",
            "market": "CN",
            "trade_date": "2026-01-16",
            "period": "daily",
            "close": Decimal("10.50"),
        }
    )
    result = await HistoricalShadowExecutionService(db).evaluate(
        backfill_run_id="backfill-1",
        sample_id="sample-1",
        proposal=_proposal(date(2026, 1, 2)),
        primary_label=SimpleNamespace(
            status="CALCULATED", horizon_end_date=date(2026, 1, 16)
        ),
        now=datetime(2026, 7, 27),
    )
    assert result.status == "FILLED"
    assert result.match_payload["matching_engine_version"] == "matching-engine-v1"
    assert result.fee_payload["entry_fee"]["fee_policy_version"] == "1.0.0"
    assert result.fee_payload["exit_fee"]["fee_policy_version"] == "1.0.0"
    assert result.net_return is not None
    assert db["ag_research_execution_snapshots"].count() == 1
    for collection in (
        "ag_execution_outbox",
        "ag_order_intents",
        "ag_paper_orders",
        "ag_paper_fills",
        "ag_paper_accounts",
        "ag_paper_positions",
        "ag_paper_position_lots",
        "ag_paper_reservations",
        "ag_paper_ledger_entries",
        "ag_settlement_records",
    ):
        assert db[collection].count() == 0


@pytest.mark.asyncio
async def test_shadow_execution_fails_closed_without_explicit_limit_prices():
    db = FakeDB()
    await PaperPolicyRegistry(db).register_builtins()
    await db["trading_calendar"].insert_one(
        {"market": "CN", "session_date": "2026-01-05", "is_open": True}
    )
    await db["stock_daily_quotes"].insert_one(
        {
            "ref_id": "raw-execution-1",
            "data_ref": "raw:600519:2026-01-05:raw-v1",
            "symbol": "600519",
            "market": "CN",
            "trade_date": "2026-01-05",
            "period": "daily",
            "open": Decimal("9.50"),
            "high": Decimal("10.20"),
            "low": Decimal("9.40"),
            "close": Decimal("10.00"),
            "volume": 1_000_000,
            "raw_data_version": "raw-v1",
        }
    )
    result = await HistoricalShadowExecutionService(db).evaluate(
        backfill_run_id="backfill-1",
        sample_id="sample-1",
        proposal=_proposal(date(2026, 1, 2)),
        now=datetime(2026, 7, 27),
    )
    assert result.status == "INSUFFICIENT_DATA"
    assert "will not infer board limits" in result.reason
    assert db["ag_research_execution_snapshots"].count() == 0
