from __future__ import annotations

from datetime import date, datetime, timedelta
from decimal import Decimal

import pytest
from bson import BSON

from app.services.alphaguard.candidate_recommendation_policy import (
    builtin_candidate_recommendation_policy,
)
from app.services.alphaguard.recommendation_data_service import (
    ProviderMaster,
    ProviderPriceBatch,
    RecommendationDataIntegrityConflict,
    RecommendationDataService,
    recommendation_data_contract,
)
from tests.unit.alphaguard._fakes import FakeDB
from tradingagents.alphaguard.recommendation_schemas import (
    CandidateUniverseManifest,
    RecommendationDataCoverage,
    recommendation_hash,
)


TRADE_DATE = date(2026, 7, 30)
NORMALIZATION = "recommendation-data-normalization-v1"
SYNC_DATES = [TRADE_DATE - timedelta(days=64 - index) for index in range(65)]
DATES = SYNC_DATES[-61:]


def _quote(symbol: str, trade_date: date, offset: int = 0) -> dict:
    close = Decimal("10") + Decimal(offset) / Decimal("100")
    mode = "INDEX_UNADJUSTED_EQUIVALENT" if symbol == "000300" else "QFQ"
    price_version = f"fake:v1:{mode}:{NORMALIZATION}"
    raw_version = (
        price_version if symbol == "000300" else f"fake:v1:RAW:{NORMALIZATION}"
    )
    ref_id = f"recommendation-{symbol}-{trade_date.isoformat()}"
    content_hash = recommendation_hash(
        {"symbol": symbol, "trade_date": trade_date, "close": close}
    )
    return {
        "ref_id": ref_id,
        "data_ref": f"stock_daily_quotes:{ref_id}",
        "source_record_id": f"fake:{symbol}:{trade_date.isoformat()}",
        "symbol": symbol,
        "code": symbol,
        "market": "CN",
        "trade_date": datetime.combine(trade_date, datetime.min.time()),
        "period": "daily",
        "open": close,
        "high": close + Decimal("0.2"),
        "low": close - Decimal("0.2"),
        "close": close,
        "adjusted_open": close,
        "adjusted_high": close + Decimal("0.2"),
        "adjusted_low": close - Decimal("0.2"),
        "adjusted_close": close,
        "prev_close": close - Decimal("0.1"),
        "volume": 1_000_000,
        "amount": 50_000_000,
        "turnover_rate": Decimal("1.2"),
        "suspended": False,
        "st_status": False,
        "price_adjustment_mode": mode,
        "adjustment_mode": mode,
        "price_data_version": price_version,
        "raw_data_version": raw_version,
        "normalization_version": NORMALIZATION,
        "provider": "fake",
        "provider_version": "v1",
        "content_hash": content_hash,
    }


def _status(symbol: str) -> dict:
    return {
        "trading_status_id": f"status-{symbol}",
        "ref_id": f"status-{symbol}",
        "symbol": symbol,
        "market": "CN",
        "trade_date": TRADE_DATE,
        "calculation_status": "READY",
        "is_suspended": False,
        "content_hash": recommendation_hash({"status": symbol}),
        "collected_at": datetime(2026, 7, 30, 16),
    }


def _instrument(symbol: str) -> dict:
    return {
        "ref_id": f"security-{symbol}",
        "code": symbol,
        "symbol": symbol,
        "name": f"测试{symbol}",
        "category": "stock_cn",
        "market": "CN",
        "list_date": "2020-01-01",
        "listing_status": "LISTED",
        "source": "baostock",
        "security_master_content_hash": recommendation_hash({"master": symbol}),
    }


def _manifest(symbols: list[str]) -> CandidateUniverseManifest:
    return CandidateUniverseManifest(
        manifest_id="manifest-pr013",
        universe_date=TRADE_DATE,
        universe_version="universe-pr013-v1",
        security_types=["A_SHARE"],
        security_count=len(symbols),
        ordered_symbols=sorted(symbols),
        ordered_security_types=["A_SHARE" for _ in symbols],
        ordered_source_refs=[f"stock_basic_info:{item}" for item in sorted(symbols)],
        ordered_security_hashes=[recommendation_hash({"symbol": item}) for item in sorted(symbols)],
        source_hash="a" * 64,
        universe_hash="b" * 64,
        created_at=datetime(2026, 7, 30, 16),
    )


async def _calendar(db: FakeDB) -> None:
    for item in SYNC_DATES:
        await db["trading_calendar"].insert_one(
            {"market": "CN", "trade_date": item, "is_open": True}
        )


def test_contract_keeps_pr012_thresholds_and_declares_90_percent_gate():
    policy = builtin_candidate_recommendation_policy()
    contract = recommendation_data_contract()
    assert policy.minimum_data_history == 61
    assert policy.minimum_recommendation_score == Decimal("55")
    assert policy.factor_weights["TREND"] == Decimal("0.20")
    assert contract["required_history_days"] == 61
    assert Decimal(str(contract["coverage_threshold"])) == Decimal("0.90")
    assert contract["industry_required"] is False


@pytest.mark.parametrize(
    ("mutator", "reason"),
    [
        (lambda prices, benchmark: prices.pop(10), "PRICE_HISTORY_SESSION_DISCONTINUITY"),
        (
            lambda prices, benchmark: prices[-1].update(
                {"price_data_version": "other-version"}
            ),
            "PRICE_VERSION_DISCONTINUITY",
        ),
        (
            lambda prices, benchmark: prices.append(
                _quote("600001", TRADE_DATE + timedelta(days=1), 90)
            ),
            "FUTURE_PRICE_DETECTED",
        ),
        (lambda prices, benchmark: benchmark.pop(), "BENCHMARK_NOT_READY"),
    ],
)
def test_quality_rejects_incomplete_future_or_discontinuous_windows(mutator, reason):
    service = RecommendationDataService(FakeDB())
    prices = [_quote("600001", item, index) for index, item in enumerate(DATES)]
    benchmark = [_quote("000300", item, index) for index, item in enumerate(DATES)]
    mutator(prices, benchmark)
    report = service._quality_for(
        symbol="600001",
        trade_date=TRADE_DATE,
        rows=prices,
        status=_status("600001"),
        benchmark_rows=benchmark,
        instrument=_instrument("600001"),
        required_trade_dates=DATES,
        now=datetime(2026, 7, 30, 16),
    )
    assert report.status == "FAIL"
    assert reason in report.blocking_reasons


@pytest.mark.asyncio
async def test_coverage_passes_minimum_contract_without_industry_mapping():
    db = FakeDB()
    await _calendar(db)
    symbol = "600001"
    for index, item in enumerate(DATES):
        await db["stock_daily_quotes"].insert_one(_quote(symbol, item, index))
        await db["stock_daily_quotes"].insert_one(_quote("000300", item, index))
    await db["ag_security_trading_statuses"].insert_one(_status(symbol))
    service = RecommendationDataService(db)
    coverage = await service.prepare_coverage(
        universe=_manifest([symbol]),
        securities={symbol: _instrument(symbol)},
        policy=builtin_candidate_recommendation_policy(),
        trade_date=TRADE_DATE,
        execute=True,
        now=datetime(2026, 7, 30, 16),
    )
    assert coverage.status == "READY"
    assert coverage.recommendation_data_ready is True
    assert coverage.minimum_contract_ready_count == 1
    assert coverage.industry_ready_count == 0
    assert coverage.blocking_reason_counts == {}
    assert len(db[service.QUALITY_COLLECTION].documents) == 1
    BSON.encode(db["ag_security_trading_statuses"].documents[-1])
    second = await service.prepare_coverage(
        universe=_manifest([symbol]),
        securities={symbol: _instrument(symbol)},
        policy=builtin_candidate_recommendation_policy(),
        trade_date=TRADE_DATE,
        execute=True,
        now=datetime(2026, 7, 30, 16, 0, 0, 999999),
    )
    assert second.coverage_id == coverage.coverage_id
    assert len(db["ag_security_trading_statuses"].documents) == 2


def test_coverage_schema_enforces_declared_readiness_gate():
    payload = {
        "coverage_id": "coverage-1",
        "trade_date": TRADE_DATE,
        "universe_manifest_id": "manifest-1",
        "universe_hash": "a" * 64,
        "universe_count": 10,
        "basic_info_ready_count": 9,
        "target_quote_ready_count": 9,
        "trade_status_ready_count": 9,
        "raw_history_ready_count": 9,
        "adjusted_history_ready_count": 9,
        "benchmark_ready_count": 61,
        "industry_ready_count": 0,
        "data_quality_pass_count": 9,
        "minimum_contract_ready_count": 9,
        "eligible_count": 9,
        "failed_symbol_count": 1,
        "required_history_days": 61,
        "coverage_threshold": "0.90",
        "coverage_percentage": "0.90",
        "blocking_reason_counts": {"HISTORICAL_STATUS_UNAVAILABLE": 1},
        "status": "DEGRADED",
        "recommendation_data_ready": True,
        "industry_required": False,
        "data_version": "v1",
        "source_hash": "b" * 64,
        "coverage_hash": "c" * 64,
        "created_at": datetime(2026, 7, 30, 16),
    }
    assert RecommendationDataCoverage.model_validate(payload).recommendation_data_ready
    with pytest.raises(ValueError):
        RecommendationDataCoverage.model_validate(
            {**payload, "recommendation_data_ready": False}
        )


class _Provider:
    name = "fake"

    def __init__(self, supported: list[str]):
        self.supported = supported
        self.price_calls: list[tuple[str, ...]] = []
        self.benchmark_calls = 0

    def fetch_master(self) -> ProviderMaster:
        return ProviderMaster(
            provider="baostock",
            provider_version="v1",
            rows=tuple(
                {
                    "code": f"{'sh' if symbol.startswith('6') else 'sz'}.{symbol}",
                    "code_name": f"测试{symbol}",
                    "ipoDate": "2020-01-01",
                    "outDate": "",
                    "type": "1",
                }
                for symbol in self.supported
            ),
        )

    def fetch_prices(self, provider_codes, *, start, end, max_attempts):
        symbols = tuple(sorted(provider_codes))
        self.price_calls.append(symbols)
        failures = tuple(
            {"symbol": symbol, "error_code": "SOURCE_UNAVAILABLE"}
            for symbol in symbols
            if symbol.endswith("2")
        )
        return ProviderPriceBatch(
            provider="fake",
            provider_version="v1",
            rows_by_symbol={
                symbol: tuple(
                    _quote(symbol, item, index) for index, item in enumerate(SYNC_DATES)
                )
                for symbol in symbols
                if not symbol.endswith("2")
            },
            failures=failures,
            retry_count=len(failures),
        )

    def fetch_benchmark(self, *, start, end):
        self.benchmark_calls += 1
        return ProviderPriceBatch(
            provider="fake",
            provider_version="v1",
            rows_by_symbol={
                "000300": tuple(
                    _quote("000300", item, index)
                    for index, item in enumerate(SYNC_DATES)
                )
            },
            failures=(),
            retry_count=0,
        )


@pytest.mark.asyncio
async def test_sync_is_create_only_resumable_and_isolates_one_symbol_failure():
    db = FakeDB()
    await _calendar(db)
    symbols = ["600001", "600002", "920001"]
    provider = _Provider(symbols[:2])
    service = RecommendationDataService(db)
    first = await service.sync_full_market(
        universe=_manifest(symbols),
        trade_date=TRADE_DATE,
        execute=True,
        provider=provider,
        now=datetime(2026, 7, 30, 16),
    )
    assert first["provider_supported_count"] == 2
    assert first["unsupported_count"] == 1
    assert [item["symbol"] for item in first["failed_symbols"]] == ["600002"]
    assert first["retry_count"] == 1
    stored_sync = db["sync_status"].documents[0]
    assert stored_sync["status"] == "completed"
    assert isinstance(stored_sync["trade_date"], datetime)
    assert isinstance(stored_sync["start_date"], datetime)
    created = len(db["stock_daily_quotes"].documents)

    second = await service.sync_full_market(
        universe=_manifest(symbols),
        trade_date=TRADE_DATE,
        execute=True,
        provider=provider,
        now=datetime(2026, 7, 30, 17),
    )
    assert provider.price_calls == [("600001", "600002"), ("600002",)]
    assert provider.benchmark_calls == 1
    assert second["resumed_count"] == 1
    assert len(db["stock_daily_quotes"].documents) == created


@pytest.mark.asyncio
async def test_price_identity_conflict_never_overwrites():
    db = FakeDB()
    service = RecommendationDataService(db)
    row = _quote("600001", TRADE_DATE)
    await service._persist_price_rows(
        [row], execute=True, collected_at=datetime(2026, 7, 30, 16)
    )
    changed = {**row, "content_hash": "f" * 64}
    with pytest.raises(RecommendationDataIntegrityConflict):
        await service._persist_price_rows(
            [changed], execute=True, collected_at=datetime(2026, 7, 30, 17)
        )
    assert db["stock_daily_quotes"].documents[0]["content_hash"] != "f" * 64


def test_low_cost_factor_evidence_reuses_registered_factor_engine():
    service = RecommendationDataService(FakeDB())
    evidence = service.build_factor_evidence(
        symbol="600001",
        trade_date=TRADE_DATE,
        price_rows=[_quote("600001", item, index) for index, item in enumerate(DATES)],
        benchmark_rows=[_quote("000300", item, index) for index, item in enumerate(DATES)],
        now=datetime(2026, 7, 30, 16),
    )
    assert evidence is not None
    assert evidence.normalized_scores["momentum_60d_v1"] is not None
    assert {"TREND", "MOMENTUM", "LIQUIDITY", "VOLATILITY_RISK"} <= set(
        evidence.group_scores
    )
    assert len(evidence.quote_refs) == len(evidence.benchmark_refs) == 61


@pytest.mark.asyncio
async def test_factor_evidence_batch_persistence_is_create_only_and_idempotent():
    db = FakeDB()
    service = RecommendationDataService(db)
    evidences = [
        service.build_factor_evidence(
            symbol=symbol,
            trade_date=TRADE_DATE,
            price_rows=[_quote(symbol, item, index) for index, item in enumerate(DATES)],
            benchmark_rows=[
                _quote("000300", item, index) for index, item in enumerate(DATES)
            ],
            now=datetime(2026, 7, 30, 16),
        )
        for symbol in ("600001", "600002")
    ]
    typed = [item for item in evidences if item is not None]

    first = await service.persist_factor_evidence_many(typed)
    second = await service.persist_factor_evidence_many(typed)

    assert sorted(first) == sorted(second) == ["600001", "600002"]
    assert len(db[service.FACTOR_COLLECTION].documents) == 2
    changed = typed[0].model_copy(update={"output_hash": "f" * 64})
    with pytest.raises(RecommendationDataIntegrityConflict):
        await service.persist_factor_evidence_many([changed])


def test_frontend_and_operations_expose_chinese_coverage_contract():
    root = __import__("pathlib").Path(__file__).resolve().parents[3]
    recommendations = (root / "frontend/src/views/AlphaGuard/Recommendations.vue").read_text()
    operations = (root / "frontend/src/views/AlphaGuard/Operations.vue").read_text()
    jobs = (root / "app/services/alphaguard/operations_job_service.py").read_text()
    for label in ("数据覆盖", "证券总数", "行情完整", "交易状态完整", "数据质量通过"):
        assert label in recommendations
    for label in ("推荐运行时", "推荐数据", "全市场覆盖率", "主要阻断", "启动全市场数据同步"):
        assert label in operations
    assert "RECOMMENDATION_DATA_SYNC" in jobs
    assert "CandidateRecommendationService(self.db).run" not in (
        jobs.split('if request.job_name == "RECOMMENDATION_DATA_SYNC":', 1)[1]
        .split('if request.job_name == "CANDIDATE_RECOMMENDATION_SCAN":', 1)[0]
    )


def test_production_frontend_proxies_same_origin_api_and_websockets():
    root = __import__("pathlib").Path(__file__).resolve().parents[3]
    nginx = (root / "docker/nginx.conf").read_text()
    compose = (root / "docker-compose.yml").read_text()
    operations = (root / "frontend/src/views/AlphaGuard/Operations.vue").read_text()

    api_location = nginx.split("location /api/ {", 1)[1].split("}", 1)[0]
    assert "proxy_pass http://backend:8000;" in api_location
    assert "proxy_http_version 1.1;" in api_location
    assert "proxy_set_header Upgrade $http_upgrade;" in api_location
    assert 'proxy_set_header Connection "upgrade";' in api_location
    assert "http://127.0.0.1/health" in compose
    load_operations = operations.split("async function loadOperations()", 1)[1].split(
        "async function runJob", 1
    )[0]
    assert "alphaguardOperationsApi.overview()" in load_operations
    assert "overviewResponse.data.readiness.service_health" in load_operations
    assert "alphaguardOperationsApi.readiness()" not in load_operations
    assert "alphaguardOperationsApi.services()" not in load_operations
    assert "alphaguardOperationsApi.dataReadiness()" not in load_operations


def test_operations_readiness_uses_bounded_market_data_queries():
    root = __import__("pathlib").Path(__file__).resolve().parents[3]
    source = (root / "app/services/alphaguard/operations_service.py").read_text()
    for start, end in (
        ("async def _industry_readiness", "async def _collection_readiness"),
        ("async def _collection_readiness", "async def _qfq_readiness"),
        ("async def _qfq_readiness", "async def _market_context_readiness"),
        ("async def _market_context_readiness", "async def _model_readiness"),
    ):
        block = source.split(start, 1)[1].split(end, 1)[0]
        assert "to_list(length=None)" not in block
    date_bounds = source.split("async def _date_bounds", 1)[1].split(
        "def _as_datetime", 1
    )[0]
    assert ".limit(16)" in date_bounds
    assert "to_list(length=16)" in date_bounds
