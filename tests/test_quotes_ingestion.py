import asyncio

import pytest
from unittest.mock import AsyncMock, Mock, patch

from app.services.quotes_ingestion_service import QuotesIngestionService


@pytest.mark.parametrize(
    ("raw_code", "expected"),
    [
        ("sz000001", "000001"),
        ("sh600036", "600036"),
        ("000001", "000001"),
        ("1", "000001"),
        ("600036", "600036"),
        ("sz002594", "002594"),
        ("", ""),
        ("abc123", "000123"),
        ("sz000000", "000000"),
    ],
)
def test_normalize_stock_code(raw_code: str, expected: str) -> None:
    assert QuotesIngestionService._normalize_stock_code(raw_code) == expected


def test_backfill_from_historical_data_imports_latest_trade_date_records() -> None:
    service = QuotesIngestionService()
    service._collection_empty = AsyncMock(return_value=True)

    history_docs = [
        {
            "symbol": "1",
            "close": 10.5,
            "pct_chg": 1.2,
            "amount": 2000,
            "volume": 100,
            "open": 10.0,
            "high": 10.8,
            "low": 9.9,
            "pre_close": 10.38,
            "trade_date": "20260326",
            "period": "daily",
        },
        {
            "code": "600036",
            "close": 44.2,
            "pct_chg": -0.5,
            "amount": 5000,
            "vol": 300,
            "open": 44.5,
            "high": 45.0,
            "low": 43.8,
            "pre_close": 44.42,
            "trade_date": "20260326",
            "period": "daily",
        },
    ]

    mock_cursor = AsyncMock()
    mock_cursor.to_list.return_value = history_docs
    mock_daily_quotes = Mock()
    mock_daily_quotes.find.return_value = mock_cursor
    fake_db = {"stock_daily_quotes": mock_daily_quotes}

    with patch("app.services.quotes_ingestion_service.get_mongo_db", return_value=fake_db):
        with patch("app.services.quotes_ingestion_service.DataSourceManager") as mock_manager_cls:
            mock_manager = mock_manager_cls.return_value
            mock_manager.find_latest_trade_date_with_fallback.return_value = "20260326"
            service._bulk_upsert = AsyncMock()

            asyncio.run(service.backfill_from_historical_data())

    service._bulk_upsert.assert_awaited_once()
    quotes_map, trade_date, source = service._bulk_upsert.await_args.args
    assert trade_date == "20260326"
    assert source == "historical_data"
    assert quotes_map == {
        "000001": {
            "close": 10.5,
            "pct_chg": 1.2,
            "amount": 2000,
            "volume": 100,
            "open": 10.0,
            "high": 10.8,
            "low": 9.9,
            "pre_close": 10.38,
        },
        "600036": {
            "close": 44.2,
            "pct_chg": -0.5,
            "amount": 5000,
            "volume": 300,
            "open": 44.5,
            "high": 45.0,
            "low": 43.8,
            "pre_close": 44.42,
        },
    }


def test_backfill_from_historical_data_checks_missing_volume_when_collection_not_empty() -> None:
    service = QuotesIngestionService()
    service._collection_empty = AsyncMock(return_value=False)
    service._fix_missing_volume = AsyncMock()

    asyncio.run(service.backfill_from_historical_data())

    service._fix_missing_volume.assert_awaited_once()
