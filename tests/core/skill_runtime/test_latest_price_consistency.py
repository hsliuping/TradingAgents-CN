from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from app.routers import stock_sync
from core.skill_runtime import data_access


def test_get_latest_stock_price_prefers_close_when_current_price_is_stale(monkeypatch) -> None:
    monkeypatch.setattr(
        data_access,
        "get_market_quotes",
        lambda symbol: {
            "symbol": symbol,
            "close": 1459.44,
            "current_price": 1399.0,
            "pre_close": 1450.0,
        },
        raising=True,
    )
    monkeypatch.setattr(data_access, "get_stock_basic_info", lambda symbol: None, raising=True)

    assert data_access.get_latest_stock_price("600519") == 1459.44


@pytest.mark.asyncio
async def test_sync_latest_to_market_quotes_aligns_price_fields(monkeypatch) -> None:
    latest_doc = {
        "symbol": "600519",
        "close": 1459.44,
        "open": 1464.49,
        "high": 1469.99,
        "low": 1452.88,
        "volume": 123456,
        "amount": 78901234,
        "pct_chg": 0.65,
        "pre_close": 1450.0,
        "trade_date": "2025-11-05",
    }
    existing_quote = {
        "code": "600519",
        "trade_date": "2025-11-04",
        "current_price": 1399.0,
    }

    stock_daily_quotes = type("StockDailyQuotesCollection", (), {
        "find_one": AsyncMock(return_value=latest_doc),
    })()
    market_quotes = type("MarketQuotesCollection", (), {
        "find_one": AsyncMock(return_value=existing_quote),
        "update_one": AsyncMock(),
    })()
    fake_db = type("FakeDb", (), {
        "stock_daily_quotes": stock_daily_quotes,
        "market_quotes": market_quotes,
    })()

    monkeypatch.setattr(stock_sync, "get_mongo_db", lambda: fake_db, raising=True)

    await stock_sync._sync_latest_to_market_quotes("600519")

    market_quotes.update_one.assert_awaited_once()
    _, update_doc = market_quotes.update_one.await_args.args[:2]
    quote_data = update_doc["$set"]
    assert quote_data["close"] == 1459.44
    assert quote_data["price"] == 1459.44
    assert quote_data["current_price"] == 1459.44