from __future__ import annotations

from datetime import date, datetime, timedelta
from decimal import Decimal
from types import SimpleNamespace

import pytest

import app.services.alphaguard.operations_service as operations_module
from app.services.alphaguard.backfill_label_maturity_service import (
    BackfillLabelMaturityError,
    BackfillLabelMaturityService,
)
from app.services.alphaguard.cn_trading_status_service import (
    CNTradingStatusService,
    derive_security_trading_status,
)
from app.services.alphaguard.execution_market_snapshot_service import (
    ExecutionMarketSnapshotService,
)
from app.services.alphaguard.historical_market_context_service import (
    HistoricalMarketFetchResult,
)
from app.services.alphaguard.horizon_label_service import HorizonLabelService
from app.services.alphaguard.operations_service import (
    AlphaGuardOperationsService,
)
from app.services.alphaguard.paper_storage import model_document
from app.services.alphaguard.production_data_config import (
    cn_price_limit_policy,
)
from app.services.alphaguard.production_market_context_service import (
    ProductionMarketContextService,
)
from app.services.alphaguard.security_master_sync_service import (
    SecurityMasterSyncService,
)
from scripts.alphaguard_readiness_report import readiness_dimensions
from tests.unit.alphaguard._fakes import FakeDB
from tests.unit.alphaguard.pr007_helpers import make_subject
from tradingagents.alphaguard.production_data_schemas import (
    ProductionMarketContextSource,
)


def test_market_context_source_preserves_fallback_lineage():
    source = ProductionMarketContextSource(
        source_id="source-1",
        market="CN",
        trade_date=date(2026, 7, 28),
        provider="akshare-tencent",
        provider_version="1.18.78",
        underlying_source="AKShare/Tencent",
        universe_provider="baostock",
        universe_provider_version="00.9.30",
        normalization_version="v1",
        source_record_count=1,
        expected_universe_count=1,
        normalized_records=[{}],
        market_amount_window=[],
        sector_records=[],
        benchmark_records=[],
        source_response_hashes={"one": "a" * 64},
        available_at=datetime(2026, 7, 28, 15),
        content_hash="b" * 64,
        collected_at=datetime(2026, 7, 28, 19),
    )
    assert source.underlying_source == "AKShare/Tencent"
    assert source.universe_provider == "baostock"


def test_data_ready_does_not_require_optional_attribution_history():
    required = {
        "TRADING_CALENDAR",
        "QFQ_PRICE_DATA",
        "RAW_PRICE_DATA",
        "FINANCIAL_DATA",
        "NEWS_DATA",
        "ANNOUNCEMENT_DATA",
        "MARKET_CONTEXT",
        "MODEL_PROVIDER",
        "CHAMPION_ASSIGNMENTS",
    }
    report = SimpleNamespace(
        service_health=[],
        data_readiness=[
            *[
                SimpleNamespace(component=component, status="READY")
                for component in sorted(required)
            ],
            SimpleNamespace(component="INDUSTRY_HISTORY", status="PARTIAL"),
        ],
        paper_execution_ready=True,
        evaluation_ready=True,
        experiment_ready=True,
        challenger_ready=False,
    )

    assert readiness_dimensions(report)["DATA_READY"] is True


class StubMarketProvider:
    name = "fixed-market"

    @staticmethod
    def capability_check():
        return {
            "provider": "fixed-market",
            "provider_version": "1.0.0",
            "available": True,
        }

    @staticmethod
    def fetch(*, selected_dates, policy, progress=None):
        trade_date = selected_dates[0]
        rows = [
            {
                "source_record_id": f"sh.600{i:03d}:{trade_date}:daily",
                "code": f"sh.600{i:03d}",
                "trade_status": "1",
                "pct_change": 1.0 if i % 2 == 0 else -0.5,
                "amount": Decimal("100"),
                "close": 10.0,
                "new_high_20": False,
                "new_low_20": False,
            }
            for i in range(100)
        ]
        sectors = [
            {
                "source_record_id": f"sector-{i}",
                "code": f"sh.0000{i}",
                "pct_change": 1.0,
                "response_hash": "a" * 64,
            }
            for i in range(10)
        ]
        source = {
            "market": "CN",
            "trade_date": trade_date,
            "provider": "fixed-market",
            "provider_version": "1.0.0",
            "normalization_version": policy["market_context"][
                "normalization_version"
            ],
            "source_record_count": 100,
            "expected_universe_count": 100,
            "normalized_records": rows,
            "market_amount_window": [],
            "sector_records": sectors,
            "source_response_hashes": {"all": "a" * 64},
            "content_hash": "b" * 64,
        }
        context = {
            "market": "CN",
            "trade_date": trade_date,
            "available_at": datetime.combine(trade_date, datetime.min.time()).replace(
                hour=15
            ),
            "provider": "fixed-market",
            "provider_version": "1.0.0",
            "data_version": "provider-context-v1",
            "advance_count": 50,
            "decline_count": 50,
            "unchanged_count": 0,
            "total_amount": Decimal("10000"),
            "amount_ratio20": Decimal("1"),
            "new_high_count": 1,
            "new_low_count": 1,
            "industry_diffusion": Decimal("1"),
            "extreme_risk_flag": False,
            "universe_coverage": Decimal("1"),
            "high_low_coverage": Decimal("1"),
            "sector_coverage": Decimal("1"),
            "calculation_status": "READY",
            "missing_fields": [],
            "methodology": {"breadth": "fixed"},
        }
        return HistoricalMarketFetchResult(
            provider="fixed-market",
            provider_version="1.0.0",
            normalization_version=policy["market_context"][
                "normalization_version"
            ],
            source_payloads={trade_date: source},
            context_payloads={trade_date: context},
            failures=(),
        )


class StubSecurityMasterProvider:
    name = "baostock"
    version = "00.9.30"

    @staticmethod
    def capability_check():
        return {
            "provider": "baostock",
            "provider_version": "00.9.30",
            "available": True,
        }

    @staticmethod
    def fetch(symbols):
        return {
            symbol: {
                "code": (
                    f"sh.{symbol}"
                    if symbol.startswith(("5", "6", "9"))
                    else f"sz.{symbol}"
                ),
                "code_name": f"证券{symbol}",
                "ipoDate": "2010-01-01",
                "outDate": "",
                "type": "1",
                "status": "1",
            }
            for symbol in symbols
        }


@pytest.mark.asyncio
async def test_security_master_sync_enriches_existing_repository_idempotently():
    db = FakeDB()
    await db["stock_basic_info"].insert_one(
        {
            "code": "000333",
            "symbol": "000333",
            "name": "证券000333",
            "source": "baostock",
            "list_date": "",
        }
    )
    service = SecurityMasterSyncService(db)
    kwargs = {
        "symbols": ["000333"],
        "provider": StubSecurityMasterProvider(),
        "collected_at": datetime(2026, 7, 28, 11),
    }
    dry = await service.sync(execute=False, **kwargs)
    assert dry["results"][0]["target_action"] == "WOULD_UPSERT"
    assert db["ag_security_master_sources"].documents == []

    created = await service.sync(execute=True, **kwargs)
    repeated = await service.sync(
        execute=True,
        symbols=["000333"],
        provider=StubSecurityMasterProvider(),
        collected_at=datetime(2026, 7, 28, 12),
    )
    assert created["results"][0]["source_action"] == "CREATED"
    assert repeated["results"][0]["source_action"] == "REUSED"
    assert len(db["ag_security_master_sources"].documents) == 1
    instrument = await db["stock_basic_info"].find_one(
        {"code": "000333", "source": "baostock"}
    )
    assert instrument["list_date"] == "2010-01-01"
    assert instrument["security_master_source_ref"].startswith(
        "ag_security_master_sources:"
    )
    assert instrument["updated_at"] == datetime(2026, 7, 28, 11)


async def _seed_benchmark(db, end: date) -> None:
    for offset in range(60, -1, -1):
        session = end - timedelta(days=offset)
        await db["stock_daily_quotes"].insert_one(
            {
                "ref_id": f"index-000300-{session}",
                "source_record_id": f"sh.000300:{session}:daily",
                "symbol": "000300",
                "market": "CN",
                "period": "daily",
                "trade_date": datetime.combine(session, datetime.min.time()),
                "close": Decimal("4000") + Decimal(str(60 - offset)),
                "price_data_version": "index-v1",
                "price_adjustment_mode": "INDEX_UNADJUSTED_EQUIVALENT",
                "available_at": datetime.combine(session, datetime.min.time()).replace(
                    hour=15
                ),
                "provider": "fixed-market",
                "provider_version": "1.0.0",
                "content_hash": "c" * 64,
            }
        )


@pytest.mark.asyncio
async def test_production_market_context_is_dry_run_then_idempotent():
    db = FakeDB()
    trade_date = date(2026, 7, 27)
    await db["trading_calendar"].insert_one(
        {
            "market": "CN",
            "session_date": datetime(2026, 7, 27),
            "is_open": True,
        }
    )
    await _seed_benchmark(db, trade_date)
    service = ProductionMarketContextService(db)
    kwargs = {
        "trade_date": trade_date,
        "provider": StubMarketProvider(),
        "now": datetime(2026, 7, 28, 10),
    }
    dry = await service.sync(execute=False, **kwargs)
    assert dry["calculation_status"] == "READY"
    assert db["ag_market_contexts"].documents == []

    created = await service.sync(execute=True, **kwargs)
    repeated = await service.sync(
        execute=True,
        trade_date=trade_date,
        provider=StubMarketProvider(),
        now=datetime(2026, 7, 28, 12),
    )
    assert created["context_action"] == "CREATED"
    assert repeated["context_action"] == "REUSED"
    assert len(db["ag_market_context_sources"].documents) == 1
    assert len(db["ag_market_contexts"].documents) == 1
    context = db["ag_market_contexts"].documents[0]
    source = db["ag_market_context_sources"].documents[0]
    assert context["advance_count"] == 50
    assert context["decline_count"] == 50
    assert context["benchmark_ma20"] is not None
    assert context["extreme_risk_flag"] is False
    assert context["calculation_status"] == "READY"
    assert context["available_at"] == datetime(2026, 7, 28, 10)
    assert source["available_at"] == datetime(2026, 7, 28, 10)
    assert context["collected_at"] == datetime(2026, 7, 28, 10)
    assert source["collected_at"] == datetime(2026, 7, 28, 10)


@pytest.mark.asyncio
async def test_production_market_context_locks_each_benchmark_session_version():
    db = FakeDB()
    trade_date = date(2026, 7, 27)
    await db["trading_calendar"].insert_one(
        {
            "market": "CN",
            "session_date": datetime(2026, 7, 27),
            "is_open": True,
        }
    )
    await _seed_benchmark(db, trade_date)
    target = await db["stock_daily_quotes"].find_one(
        {"ref_id": f"index-000300-{trade_date}"}
    )
    target["price_data_version"] = "index-v2"
    await db["stock_daily_quotes"].replace_one(
        {"ref_id": f"index-000300-{trade_date}"},
        target,
    )
    result = await ProductionMarketContextService(db).sync(
        trade_date=trade_date,
        provider=StubMarketProvider(),
        now=datetime(2026, 7, 28, 10),
        execute=False,
    )
    assert result["calculation_status"] == "READY"


@pytest.mark.asyncio
async def test_operations_rejects_stale_or_superseded_market_context_version():
    db = FakeDB()
    now = datetime(2026, 7, 28, 12)
    await db["ag_market_contexts"].insert_one(
        {
            "market": "CN",
            "trade_date": datetime(2026, 7, 27),
            "calculation_status": "READY",
            "calculation_version": "production-market-context-calculation-v1",
            "available_at": datetime(2026, 7, 27, 15),
            "collected_at": datetime(2026, 7, 28, 11),
        }
    )
    service = AlphaGuardOperationsService(db)
    blocked = await service._market_context_readiness(now)
    assert blocked.status == "NOT_READY"
    assert blocked.record_count == 0

    await db["ag_market_contexts"].insert_one(
        {
            "market": "CN",
            "trade_date": datetime(2026, 7, 28),
            "calculation_status": "READY",
            "calculation_version": (
                "production-market-context-calculation-v1.1"
            ),
            "available_at": datetime(2026, 7, 28, 11),
            "collected_at": datetime(2026, 7, 28, 11),
        }
    )
    ready = await service._market_context_readiness(now)
    assert ready.status == "READY"
    assert ready.record_count == 1


@pytest.mark.asyncio
async def test_operations_default_clock_uses_cn_market_wall_time(monkeypatch):
    db = FakeDB()
    await db["ag_market_contexts"].insert_one(
        {
            "market": "CN",
            "trade_date": datetime(2026, 7, 28),
            "calculation_status": "READY",
            "calculation_version": (
                "production-market-context-calculation-v1.1"
            ),
            "available_at": datetime(2026, 7, 28, 19, 55),
            "collected_at": datetime(2026, 7, 28, 19, 55),
        }
    )
    monkeypatch.setattr(
        operations_module,
        "_cn_market_now",
        lambda: datetime(2026, 7, 28, 20),
    )

    statuses = await AlphaGuardOperationsService(db).data_readiness()
    market_context = next(
        item for item in statuses if item.component == "MARKET_CONTEXT"
    )

    assert market_context.status == "READY"
    assert market_context.record_count == 1


def _quote(symbol: str, previous_close: str = "10.03") -> dict:
    return {
        "ref_id": f"price-{symbol}-2026-07-27",
        "source_record_id": f"{symbol}:2026-07-27:daily",
        "symbol": symbol,
        "market": "CN",
        "trade_date": datetime(2026, 7, 27),
        "prev_close": previous_close,
        "suspended": False,
        "st_status": False,
        "provider": "fixed",
        "provider_version": "1",
        "price_data_version": "qfq-v1",
    }


def _instrument(symbol: str, name: str = "正常股票") -> dict:
    return {
        "ref_id": f"instrument-{symbol}",
        "symbol": symbol,
        "name": name,
        "list_date": "20100101",
    }


def test_price_limit_rules_cover_main_chinext_st_and_rounding():
    policy = cn_price_limit_policy()
    main = derive_security_trading_status(
        quote=_quote("600519"),
        instrument=_instrument("600519"),
        trade_date=date(2026, 7, 27),
        listing_session_number=6,
        policy=policy,
    )
    assert main.listing_board == "SSE_MAIN"
    assert main.upper_limit_price == Decimal("11.03")
    assert main.lower_limit_price == Decimal("9.03")

    chinext = derive_security_trading_status(
        quote=_quote("300750", "100"),
        instrument=_instrument("300750"),
        trade_date=date(2026, 7, 27),
        listing_session_number=6,
        policy=policy,
    )
    assert chinext.upper_limit_price == Decimal("120.00")
    assert chinext.lower_limit_price == Decimal("80.00")

    st_quote = _quote("600519", "10")
    st_quote["st_status"] = True
    st = derive_security_trading_status(
        quote=st_quote,
        instrument=_instrument("600519", "ST贵州"),
        trade_date=date(2026, 7, 27),
        listing_session_number=6,
        policy=policy,
    )
    assert st.upper_limit_price == Decimal("10.50")
    assert st.lower_limit_price == Decimal("9.50")


def test_initial_listing_and_unknown_board_fail_closed():
    policy = cn_price_limit_policy()
    recent = _instrument("300999")
    recent["list_date"] = "20260727"
    no_limit = derive_security_trading_status(
        quote=_quote("300999"),
        instrument=recent,
        trade_date=date(2026, 7, 27),
        listing_session_number=1,
        policy=policy,
    )
    assert no_limit.calculation_status == "INSUFFICIENT_DATA"
    assert no_limit.upper_limit_price is None
    assert "execution_snapshot_no_limit_day_unsupported" in no_limit.missing_fields

    unknown = derive_security_trading_status(
        quote=_quote("777777"),
        instrument=_instrument("777777"),
        trade_date=date(2026, 7, 27),
        listing_session_number=6,
        policy=policy,
    )
    assert unknown.calculation_status == "INSUFFICIENT_DATA"
    assert "listing_board" in unknown.missing_fields


@pytest.mark.asyncio
async def test_trading_status_uses_only_persisted_facts_when_quote_omits_status():
    db = FakeDB()
    await db["trading_calendar"].insert_one(
        {
            "market": "CN",
            "session_date": datetime(2026, 7, 27),
            "is_open": True,
        }
    )
    await db["trading_calendar"].insert_one(
        {
            "market": "CN",
            "session_date": datetime(2026, 7, 28),
            "is_open": True,
        }
    )
    await db["stock_basic_info"].insert_one(
        {
            "ref_id": "instrument-600519",
            "symbol": "600519",
            "name": "贵州茅台",
            "list_date": "20010827",
        }
    )
    await db["stock_daily_quotes"].insert_one(
        {
            "ref_id": "price-600519-2026-07-27",
            "symbol": "600519",
            "market": "CN",
            "period": "daily",
            "trade_date": datetime(2026, 7, 27),
            "close": Decimal("1297.41"),
            "data_version": "qfq-v1",
        }
    )
    await db["stock_daily_quotes"].insert_one(
        {
            "ref_id": "price-600519-2026-07-28",
            "source_record_id": "provider-600519-2026-07-28",
            "symbol": "600519",
            "market": "CN",
            "period": "daily",
            "trade_date": datetime(2026, 7, 28),
            "close": Decimal("1320"),
            "volume_shares": 100,
            "data_version": "qfq-v2",
            "provider": "baostock",
            "provider_version": "1",
            "available_at": datetime(2026, 7, 28, 16),
        }
    )
    result = await CNTradingStatusService(db).sync(
        symbols=["600519"],
        trade_date=date(2026, 7, 28),
        execute=False,
        collected_at=datetime(2026, 7, 28, 17),
    )
    status = result["results"][0]
    assert status["previous_close"] == Decimal("1297.41")
    assert status["is_st"] is False
    assert status["is_suspended"] is False
    assert status["calculation_status"] == "READY"
    assert (
        "stock_daily_quotes:price-600519-2026-07-27"
        in status["source_refs"]
    )


@pytest.mark.asyncio
async def test_execution_snapshot_resolves_versioned_status_without_rule_changes():
    db = FakeDB()
    quote = {
        **_quote("600519", "10"),
        "open": Decimal("10"),
        "high": Decimal("10.20"),
        "low": Decimal("9.80"),
        "close": Decimal("10.10"),
        "volume": 100000,
        "amount": Decimal("1010000"),
        "updated_at": datetime(2026, 7, 27, 15),
        "period": "daily",
    }
    await db["stock_daily_quotes"].insert_one(quote)
    status = derive_security_trading_status(
        quote=quote,
        instrument=_instrument("600519"),
        trade_date=date(2026, 7, 27),
        listing_session_number=6,
        collected_at=datetime(2026, 7, 27, 15),
    )
    await db["ag_security_trading_statuses"].insert_one(model_document(status))

    snapshot = await ExecutionMarketSnapshotService(db).build_for_trade_date(
        symbol="600519",
        trade_date=date(2026, 7, 27),
        cutoff_at=datetime(2026, 7, 27, 15, 30),
        data_version="qfq-v1",
    )
    assert snapshot.limit_up_price == Decimal("11.00")
    assert snapshot.limit_down_price == Decimal("9.00")
    assert len(snapshot.source_refs) == 2
    assert snapshot.live_execution_allowed is False


@pytest.mark.asyncio
async def test_backfill_label_maturity_rejects_current_day_before_close():
    with pytest.raises(
        BackfillLabelMaturityError,
        match="has not completed",
    ):
        await BackfillLabelMaturityService(FakeDB()).plan(
            backfill_run_id="canonical",
            as_of_trade_date=date(2026, 7, 28),
            now=datetime(2026, 7, 28, 10),
        )


@pytest.mark.asyncio
async def test_backfill_label_maturity_changes_pending_only_and_is_idempotent():
    db = FakeDB()
    sessions = [date(2026, 7, 1) + timedelta(days=index) for index in range(28)]
    open_sessions = [item for item in sessions if item.weekday() < 5][:20]
    assert open_sessions[-1] == date(2026, 7, 28)
    for session in open_sessions:
        await db["trading_calendar"].insert_one(
            {"market": "CN", "session_date": session.isoformat(), "is_open": True}
        )
    subject = make_subject(
        entry_zone=False,
        lineage_ids={
            "backfill_run_id": "canonical",
            "sample_id": "sample-1",
        },
    ).model_copy(update={"decision_trade_date": date(2026, 6, 30)})
    await db["ag_eval_subjects"].insert_one(
        subject.model_dump(mode="python")
    )
    for symbol, mode in (("600519", "QFQ"), ("000300", "INDEX_UNADJUSTED_EQUIVALENT")):
        for index, session in enumerate([date(2026, 6, 30), *open_sessions]):
            close = Decimal("10") + Decimal(index) / Decimal("10")
            await db["stock_daily_quotes"].insert_one(
                {
                    "ref_id": f"price-{symbol}-{session}",
                    "symbol": symbol,
                    "market": "CN",
                    "period": "daily",
                    "trade_date": datetime.combine(session, datetime.min.time()),
                    "adjusted_open": close,
                    "adjusted_high": close + Decimal("0.1"),
                    "adjusted_low": close - Decimal("0.1"),
                    "adjusted_close": close,
                    "price_adjustment_mode": mode,
                    "price_data_version": f"{symbol}-v1",
                    "data_ref": f"stock_daily_quotes:price-{symbol}-{session}",
                    "available_at": datetime.combine(session, datetime.min.time()).replace(
                        hour=15
                    ),
                    "collected_at": datetime(2026, 7, 28, 15, 1),
                    "content_hash": "d" * 64,
                    "volume": 100,
                    "suspended": False,
                }
            )
    initial_labels = await HorizonLabelService(db).calculate_all(
        subject,
        as_of_trade_date=date(2026, 7, 27),
    )
    mature = next(
        item
        for item in initial_labels
        if item.horizon == "1D" and item.anchor_type == "DECISION_CLOSE"
    )
    pending = next(
        item
        for item in initial_labels
        if item.horizon == "20D" and item.anchor_type == "DECISION_CLOSE"
    )
    assert mature.status == "CALCULATED"
    assert pending.status == "PENDING"
    service = BackfillLabelMaturityService(db)
    result = await service.mature(
        backfill_run_id="canonical",
        as_of_trade_date=date(2026, 7, 28),
        execute=True,
        now=datetime(2026, 7, 28, 16),
    )
    assert result["matured_20d_count"] == 1
    stored_mature = await db["ag_eval_horizon_labels"].find_one(
        {"label_id": mature.label_id}
    )
    assert stored_mature["input_hash"] == mature.input_hash
    repeated = await service.mature(
        backfill_run_id="canonical",
        as_of_trade_date=date(2026, 7, 28),
        execute=True,
        now=datetime(2026, 7, 28, 16),
    )
    assert repeated["pending_20d_count"] == 0
    assert repeated["matured_20d_count"] == 0


async def _mixed_version_label_fixture(db):
    sessions = [
        date(2026, 7, 1) + timedelta(days=index) for index in range(28)
    ]
    open_sessions = [item for item in sessions if item.weekday() < 5][:20]
    for session in open_sessions:
        await db["trading_calendar"].insert_one(
            {
                "market": "CN",
                "session_date": session.isoformat(),
                "is_open": True,
            }
        )
    subject = make_subject(
        entry_zone=False,
        lineage_ids={
            "backfill_run_id": "mixed-version",
            "sample_id": "sample-mixed",
        },
    ).model_copy(update={"decision_trade_date": date(2026, 6, 30)})
    await db["ag_eval_subjects"].insert_one(
        subject.model_dump(mode="python")
    )
    for symbol, mode in (
        ("600519", "QFQ"),
        ("000300", "INDEX_UNADJUSTED_EQUIVALENT"),
    ):
        dates = [date(2026, 6, 30), *open_sessions]
        for index, session in enumerate(dates):
            close = Decimal("10") + Decimal(index) / Decimal("10")
            version = f"{symbol}-v2" if session == dates[-1] else f"{symbol}-v1"
            await db["stock_daily_quotes"].insert_one(
                {
                    "ref_id": f"mixed-{symbol}-{session}",
                    "symbol": symbol,
                    "market": "CN",
                    "period": "daily",
                    "trade_date": datetime.combine(
                        session, datetime.min.time()
                    ),
                    "adjusted_open": close,
                    "adjusted_high": close + Decimal("0.1"),
                    "adjusted_low": close - Decimal("0.1"),
                    "adjusted_close": close,
                    "price_adjustment_mode": mode,
                    "price_data_version": version,
                    "data_ref": f"stock_daily_quotes:mixed-{symbol}-{session}",
                    "available_at": datetime.combine(
                        session, datetime.min.time()
                    ).replace(hour=15),
                    "collected_at": datetime(2026, 7, 28, 15, 1),
                    "content_hash": "e" * 64,
                    "volume": 100,
                    "suspended": False,
                }
            )
    labels = await HorizonLabelService(db).calculate_all(
        subject,
        as_of_trade_date=date(2026, 7, 27),
    )
    pending = next(
        item
        for item in labels
        if item.horizon == "20D" and item.anchor_type == "DECISION_CLOSE"
    )
    assert pending.status == "PENDING"
    return subject, pending


@pytest.mark.asyncio
async def test_backfill_label_maturity_keeps_mixed_versions_pending():
    db = FakeDB()
    _, pending = await _mixed_version_label_fixture(db)
    service = BackfillLabelMaturityService(db)
    plan = await service.plan(
        backfill_run_id="mixed-version",
        as_of_trade_date=date(2026, 7, 28),
        now=datetime(2026, 7, 28, 16),
    )
    assert plan["ready_20d_count"] == 0
    assert plan["blocked_20d_count"] == 1
    assert (
        plan["blockers"][0]["reason"]
        == "VERSION_LOCKED_QFQ_SERIES_UNAVAILABLE"
    )
    with pytest.raises(
        BackfillLabelMaturityError,
        match="lack completed persisted QFQ",
    ):
        await service.mature(
            backfill_run_id="mixed-version",
            as_of_trade_date=date(2026, 7, 28),
            execute=True,
            now=datetime(2026, 7, 28, 16),
        )
    stored = await db["ag_eval_horizon_labels"].find_one(
        {"label_id": pending.label_id}
    )
    assert stored["status"] == "PENDING"


@pytest.mark.asyncio
async def test_backfill_label_recovery_is_narrow_and_compare_and_set():
    db = FakeDB()
    subject, pending = await _mixed_version_label_fixture(db)
    terminal = await HorizonLabelService(db).calculate_all(
        subject,
        as_of_trade_date=date(2026, 7, 28),
    )
    invalid = next(
        item
        for item in terminal
        if item.horizon == "20D" and item.anchor_type == "DECISION_CLOSE"
    )
    assert invalid.status == "INSUFFICIENT_DATA"
    service = BackfillLabelMaturityService(db)
    dry = await service.recover_invalid_incomplete_to_pending(
        backfill_run_id="mixed-version",
        as_of_trade_date=date(2026, 7, 28),
        execute=False,
    )
    assert dry["eligible_recovery_count"] == 1
    repaired = await service.recover_invalid_incomplete_to_pending(
        backfill_run_id="mixed-version",
        as_of_trade_date=date(2026, 7, 28),
        execute=True,
    )
    assert repaired["recovered_pending_count"] == 1
    stored = await db["ag_eval_horizon_labels"].find_one(
        {"label_id": pending.label_id}
    )
    assert stored["status"] == "PENDING"
