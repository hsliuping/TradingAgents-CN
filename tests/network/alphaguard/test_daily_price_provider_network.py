"""Explicit operator-run connectivity probes; excluded from offline CI."""

from datetime import date

import pytest

from app.services.alphaguard.daily_price_provider import (
    AKShareEastmoneyDailyPriceProvider,
    AKShareTencentDailyPriceProvider,
    BaoStockDailyPriceProvider,
)


@pytest.mark.network
@pytest.mark.parametrize(
    "provider",
    [
        BaoStockDailyPriceProvider(timeout_seconds=15),
        AKShareEastmoneyDailyPriceProvider(timeout_seconds=15),
        AKShareTencentDailyPriceProvider(timeout_seconds=15),
    ],
)
def test_known_completed_daily_provider_returns_structured_probe(provider):
    probe = provider.probe(
        symbol="600519",
        trade_date=date(2026, 7, 24),
        mode="RAW",
    )
    assert probe.status in {"VALID", "INSUFFICIENT_DATA", "INVALID", "ERROR"}
    assert probe.capability.network_required is True
    assert probe.source_record_identity
