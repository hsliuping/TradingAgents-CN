from __future__ import annotations

from dataclasses import replace
from datetime import date, datetime
from decimal import Decimal

import pandas as pd
import pytest
from bson import BSON

from app.services.alphaguard.daily_price_provider import (
    AKShareEastmoneyDailyPriceProvider,
    AKShareTencentDailyPriceProvider,
    DailyPriceIntegrityConflict,
    DailyPriceProviderResolver,
    NormalizedDailyPrice,
    ProviderCapability,
    ProviderProbe,
    ProviderRegistry,
    compare_daily_prices,
)
from app.services.alphaguard.incremental_daily_price_service import (
    IncrementalDailyPriceService,
    build_price_document,
)
from tests.unit.alphaguard._fakes import FakeDB


TRADE_DATE = date(2026, 7, 28)
AFTER_CLOSE = datetime(2026, 7, 28, 16, 30)


def _capability(key: str) -> ProviderCapability:
    source = {
        "BAOSTOCK": "BaoStock",
        "AKSHARE_EASTMONEY": "AKShare/Eastmoney",
        "AKSHARE_TENCENT": "AKShare/Tencent",
    }[key]
    return ProviderCapability(
        provider_name="baostock" if key == "BAOSTOCK" else "akshare",
        provider_version="1.0",
        underlying_source=source,
        supports_market=("CN",),
        supports_equity_daily=True,
        supports_index_daily=True,
        supports_raw=True,
        supports_qfq=True,
        provides_volume=True,
        provides_amount=True,
        provides_provider_update_time=False,
        provides_source_record_id=False,
        network_required=True,
        available=True,
    )


def _record(
    key: str,
    *,
    symbol: str = "600519",
    mode: str = "RAW",
    close: str = "10.00",
    volume: int = 10000,
    amount: str = "100000.00",
) -> NormalizedDailyPrice:
    cap = _capability(key)
    return NormalizedDailyPrice(
        market="CN",
        symbol=symbol,
        trade_date=TRADE_DATE,
        mode=mode,  # type: ignore[arg-type]
        open=Decimal("10.00"),
        high=Decimal("10.20"),
        low=Decimal("9.80"),
        close=Decimal(close),
        volume_shares=volume,
        amount_cny=Decimal(amount),
        provider=cap.provider_name,
        provider_version=cap.provider_version,
        underlying_source=cap.underlying_source,
        source_record_identity=f"{cap.underlying_source}:{symbol}:{mode}",
        provider_update_time=None,
        response_received_at=AFTER_CLOSE,
        update_time_verified=False,
        source_response_hash="a" * 64,
        normalization_version="test-normalization-v1",
        volume_normalization_rule="TEST_SHARES",
        amount_normalization_rule="TEST_CNY",
        content_hash=f"{key[-1].lower() or 'a'}" * 64,
    )


def _probe(
    key: str,
    *,
    mode: str,
    symbol: str = "600519",
    record: NormalizedDailyPrice | None = None,
    status: str = "VALID",
    failure: str | None = None,
) -> ProviderProbe:
    cap = _capability(key)
    return ProviderProbe(
        capability=cap,
        symbol=symbol,
        trade_date=TRADE_DATE,
        mode=mode,  # type: ignore[arg-type]
        status=status,  # type: ignore[arg-type]
        row_count=1 if record else 0,
        returned_trade_dates=(TRADE_DATE.isoformat(),) if record else (),
        response_received_at=AFTER_CLOSE,
        provider_update_time=None,
        source_record_identity=f"{cap.underlying_source}:{symbol}:{mode}",
        record=record,
        failure_reason=failure,
    )


class FixedProvider:
    def __init__(self, key: str, probes: dict[str, ProviderProbe]):
        self.provider_key = key
        self._probes = probes

    def capability_check(self):
        return _capability(self.provider_key)

    def probe(self, *, symbol, trade_date, mode):
        assert trade_date == TRADE_DATE
        probe = self._probes[mode]
        assert probe.symbol == symbol
        return probe


def _valid_provider(key: str, *, symbol: str = "600519", close="10.00"):
    raw = _record(key, symbol=symbol, mode="RAW", close=close)
    qfq = _record(key, symbol=symbol, mode="QFQ", close=close)
    return FixedProvider(
        key,
        {
            "RAW": _probe(key, symbol=symbol, mode="RAW", record=raw),
            "QFQ": _probe(key, symbol=symbol, mode="QFQ", record=qfq),
        },
    )


def _empty_provider(key: str, *, symbol: str = "600519"):
    return FixedProvider(
        key,
        {
            "RAW": _probe(
                key,
                symbol=symbol,
                mode="RAW",
                record=None,
                status="INSUFFICIENT_DATA",
                failure="EXACT_DAILY_ROW_NOT_RETURNED",
            ),
            "QFQ": _probe(
                key,
                symbol=symbol,
                mode="QFQ",
                record=None,
                status="INSUFFICIENT_DATA",
                failure="EXACT_DAILY_ROW_NOT_RETURNED",
            ),
        },
    )


def test_akshare_eastmoney_equity_raw_and_qfq_normalization(monkeypatch):
    import akshare as ak

    calls = []

    def fake_hist(**kwargs):
        calls.append(kwargs)
        return pd.DataFrame(
            [
                {
                    "日期": TRADE_DATE,
                    "股票代码": "600519",
                    "开盘": 10,
                    "收盘": 10.1 if kwargs["adjust"] == "" else 9.9,
                    "最高": 10.2,
                    "最低": 9.8,
                    "成交量": 123,
                    "成交额": 456789,
                }
            ]
        )

    monkeypatch.setattr(ak, "stock_zh_a_hist", fake_hist)
    provider = AKShareEastmoneyDailyPriceProvider()
    raw = provider.probe(symbol="600519", trade_date=TRADE_DATE, mode="RAW")
    qfq = provider.probe(symbol="600519", trade_date=TRADE_DATE, mode="QFQ")
    assert raw.status == qfq.status == "VALID"
    assert raw.record.volume_shares == 12300
    assert raw.record.amount_cny == Decimal("456789.00")
    assert raw.record.provider_update_time is None
    assert raw.record.update_time_verified is False
    assert calls[0]["adjust"] == ""
    assert calls[1]["adjust"] == "qfq"


def test_akshare_eastmoney_index_normalization_and_mapping(monkeypatch):
    import akshare as ak

    captured = {}

    def fake_index(**kwargs):
        captured.update(kwargs)
        return pd.DataFrame(
            [
                {
                    "日期": TRADE_DATE.isoformat(),
                    "开盘": 4000,
                    "收盘": 4010,
                    "最高": 4020,
                    "最低": 3990,
                    "成交量": 200,
                    "成交额": 300000,
                }
            ]
        )

    monkeypatch.setattr(ak, "index_zh_a_hist", fake_index)
    probe = AKShareEastmoneyDailyPriceProvider().probe(
        symbol="000300",
        trade_date=TRADE_DATE,
        mode="INDEX_UNADJUSTED_EQUIVALENT",
    )
    assert probe.status == "VALID"
    assert captured["symbol"] == "000300"
    assert probe.record.volume_shares == 20000
    assert probe.record.mode == "INDEX_UNADJUSTED_EQUIVALENT"


@pytest.mark.parametrize(
    ("symbol", "expected_code", "reported_volume", "expected_shares"),
    [
        ("600519", "sh600519", 12300, 12300),
        ("000333", "sz000333", 123, 12300),
        ("300750", "sz300750", 12300, 12300),
        ("000300", "sh000300", 123, 12300),
    ],
)
def test_akshare_tencent_code_and_volume_normalization(
    monkeypatch,
    symbol,
    expected_code,
    reported_volume,
    expected_shares,
):
    import akshare as ak

    captured = {}

    def fake_tx(**kwargs):
        captured.update(kwargs)
        return pd.DataFrame(
            [
                {
                    "date": TRADE_DATE,
                    "open": 10,
                    "close": 10.1,
                    "high": 10.2,
                    "low": 9.8,
                    "volume": reported_volume,
                    "turnover": 0.01,
                    "amount": 456789,
                }
            ]
        )

    monkeypatch.setattr(ak, "stock_zh_a_hist_tx", fake_tx)
    mode = "INDEX_UNADJUSTED_EQUIVALENT" if symbol == "000300" else "RAW"
    probe = AKShareTencentDailyPriceProvider().probe(
        symbol=symbol,
        trade_date=TRADE_DATE,
        mode=mode,
    )
    assert probe.status == "VALID"
    assert captured["symbol"] == expected_code
    assert probe.record.volume_shares == expected_shares
    assert probe.record.amount_cny == Decimal("456789.00")


def test_resolver_uses_akshare_when_baostock_is_empty():
    resolver = DailyPriceProviderResolver(
        ProviderRegistry(
            [
                _empty_provider("BAOSTOCK"),
                _valid_provider("AKSHARE_EASTMONEY"),
                _empty_provider("AKSHARE_TENCENT"),
            ]
        )
    )
    result = resolver.resolve(symbol="600519", trade_date=TRADE_DATE)
    assert result.status == "READY"
    assert result.primary_provider_key == "AKSHARE_EASTMONEY"
    assert result.fallback_reason == "PRIMARY_PROVIDERS_NOT_READY:BAOSTOCK"


def test_resolver_keeps_baostock_when_akshare_is_empty():
    resolver = DailyPriceProviderResolver(
        ProviderRegistry(
            [
                _valid_provider("BAOSTOCK"),
                _empty_provider("AKSHARE_EASTMONEY"),
                _empty_provider("AKSHARE_TENCENT"),
            ]
        )
    )
    result = resolver.resolve(symbol="600519", trade_date=TRADE_DATE)
    assert result.status == "READY"
    assert result.primary_provider_key == "BAOSTOCK"
    assert result.fallback_reason is None


def test_cross_provider_match_tolerance_and_major_conflict():
    left = _record("BAOSTOCK", close="10.00", volume=10000, amount="100000")
    near = _record(
        "AKSHARE_TENCENT",
        close="10.01",
        volume=10050,
        amount="100050",
    )
    far = replace(near, close=Decimal("11.00"))
    assert compare_daily_prices(left, near)["status"] == (
        "DIFFERENCE_WITHIN_TOLERANCE"
    )
    assert compare_daily_prices(left, far)["status"] == "MAJOR_CONFLICT"


def test_qfq_cross_provider_uses_versioned_tolerance():
    left = _record("BAOSTOCK", mode="QFQ", close="10.00")
    near = _record("AKSHARE_TENCENT", mode="QFQ", close="10.04")
    assert compare_daily_prices(left, near)["status"] == (
        "DIFFERENCE_WITHIN_TOLERANCE"
    )


def test_all_providers_empty_is_insufficient_data():
    resolver = DailyPriceProviderResolver(
        ProviderRegistry(
            [
                _empty_provider("BAOSTOCK"),
                _empty_provider("AKSHARE_EASTMONEY"),
                _empty_provider("AKSHARE_TENCENT"),
            ]
        )
    )
    assert resolver.resolve(
        symbol="600519", trade_date=TRADE_DATE
    ).status == "INSUFFICIENT_DATA"


def test_cross_provider_major_conflict_stops_resolution():
    resolver = DailyPriceProviderResolver(
        ProviderRegistry(
            [
                _valid_provider("BAOSTOCK", close="10.00"),
                _valid_provider("AKSHARE_TENCENT", close="11.00"),
            ]
        )
    )
    assert resolver.resolve(
        symbol="600519", trade_date=TRADE_DATE
    ).status == "INTEGRITY_CONFLICT"


def test_content_hash_is_stable_across_probe_execution_times():
    resolver = DailyPriceProviderResolver(
        ProviderRegistry([_valid_provider("BAOSTOCK")])
    )
    first = resolver.resolve(symbol="600519", trade_date=TRADE_DATE)
    later = replace(
        first,
        raw=replace(
            first.raw,
            response_received_at=datetime(2026, 7, 28, 17),
        ),
        adjusted=replace(
            first.adjusted,
            response_received_at=datetime(2026, 7, 28, 17, 1),
        ),
    )
    first_document = build_price_document(first)
    later_document = build_price_document(later)
    BSON.encode(first_document)
    assert first_document["content_hash"] == later_document["content_hash"]
    assert first_document["collected_at"] != later_document["collected_at"]


@pytest.mark.asyncio
async def test_local_empty_provider_complete_allows_exact_incremental_sync():
    db = FakeDB()
    await db["trading_calendar"].insert_one(
        {
            "market": "CN",
            "session_date": datetime(2026, 7, 28),
            "is_open": True,
        }
    )
    resolver = DailyPriceProviderResolver(
        ProviderRegistry([_valid_provider("BAOSTOCK")])
    )
    service = IncrementalDailyPriceService(db, resolver)
    dry = await service.sync(
        symbols=["600519"],
        trade_date=TRADE_DATE,
        execute=False,
        now=AFTER_CLOSE,
    )
    assert dry["status"] == "READY"
    assert db["stock_daily_quotes"].documents == []
    created = await service.sync(
        symbols=["600519"],
        trade_date=TRADE_DATE,
        execute=True,
        now=AFTER_CLOSE,
    )
    assert created["created"] == 1
    assert (await service.local_gate(
        symbols=["600519"], trade_date=TRADE_DATE
    ))["status"] == "READY"


@pytest.mark.asyncio
async def test_provider_empty_and_incomplete_local_gate_fail_closed():
    db = FakeDB()
    await db["trading_calendar"].insert_one(
        {
            "market": "CN",
            "session_date": datetime(2026, 7, 28),
            "is_open": True,
        }
    )
    service = IncrementalDailyPriceService(
        db,
        DailyPriceProviderResolver(
            ProviderRegistry([_empty_provider("BAOSTOCK")])
        ),
    )
    result = await service.sync(
        symbols=["600519"],
        trade_date=TRADE_DATE,
        execute=True,
        now=AFTER_CLOSE,
    )
    assert result["status"] == "INSUFFICIENT_DATA"
    assert db["stock_daily_quotes"].documents == []
    await db["stock_daily_quotes"].insert_one(
        {
            "ref_id": "price-600519-2026-07-28",
            "symbol": "600519",
            "trade_date": datetime(2026, 7, 28),
        }
    )
    assert (await service.local_gate(
        symbols=["600519"], trade_date=TRADE_DATE
    ))["status"] == "NOT_READY"


@pytest.mark.asyncio
async def test_repeated_sync_reuses_and_changed_content_conflicts():
    db = FakeDB()
    await db["trading_calendar"].insert_one(
        {
            "market": "CN",
            "session_date": datetime(2026, 7, 28),
            "is_open": True,
        }
    )
    service = IncrementalDailyPriceService(
        db,
        DailyPriceProviderResolver(
            ProviderRegistry([_valid_provider("BAOSTOCK")])
        ),
    )
    await service.sync(
        symbols=["600519"],
        trade_date=TRADE_DATE,
        execute=True,
        now=AFTER_CLOSE,
    )
    repeated = await service.sync(
        symbols=["600519"],
        trade_date=TRADE_DATE,
        execute=True,
        now=datetime(2026, 7, 28, 17),
    )
    assert repeated["created"] == 0
    assert repeated["reused"] == 1
    changed = IncrementalDailyPriceService(
        db,
        DailyPriceProviderResolver(
            ProviderRegistry([_valid_provider("BAOSTOCK", close="10.10")])
        ),
    )
    with pytest.raises(DailyPriceIntegrityConflict):
        await changed.sync(
            symbols=["600519"],
            trade_date=TRADE_DATE,
            execute=True,
            now=datetime(2026, 7, 28, 17),
        )
    assert len(db["stock_daily_quotes"].documents) == 1


def test_preclose_provider_response_is_invalid(monkeypatch):
    import akshare as ak
    import app.services.alphaguard.daily_price_provider as module

    class BeforeClose(datetime):
        @classmethod
        def now(cls, tz=None):
            del tz
            return cls(2026, 7, 28, 14, 59)

    monkeypatch.setattr(module, "datetime", BeforeClose)
    monkeypatch.setattr(
        ak,
        "stock_zh_a_hist_tx",
        lambda **kwargs: pd.DataFrame(
            [
                {
                    "date": TRADE_DATE,
                    "open": 10,
                    "close": 10,
                    "high": 11,
                    "low": 9,
                    "volume": 100,
                    "amount": 1000,
                }
            ]
        ),
    )
    result = AKShareTencentDailyPriceProvider().probe(
        symbol="600519",
        trade_date=TRADE_DATE,
        mode="RAW",
    )
    assert result.status == "INVALID"
    assert result.failure_reason == "RESPONSE_RECEIVED_BEFORE_MARKET_CLOSE"


def test_old_trade_date_response_is_invalid(monkeypatch):
    import akshare as ak

    monkeypatch.setattr(
        ak,
        "stock_zh_a_hist_tx",
        lambda **kwargs: pd.DataFrame(
            [
                {
                    "date": date(2026, 7, 24),
                    "open": 10,
                    "close": 10,
                    "high": 11,
                    "low": 9,
                    "volume": 100,
                    "amount": 1000,
                }
            ]
        ),
    )
    result = AKShareTencentDailyPriceProvider().probe(
        symbol="600519",
        trade_date=TRADE_DATE,
        mode="RAW",
    )
    assert result.status == "INVALID"
    assert result.failure_reason == "OLD_OR_WRONG_TRADE_DATE"
