"""Read explicit, versioned adjusted daily OHLC without network fallback."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from app.services.alphaguard.paper_storage import clean_document


class AdjustedPriceUnavailable(LookupError):
    pass


def _as_date(value: Any) -> date | None:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    try:
        return date.fromisoformat(str(value)[:10])
    except (TypeError, ValueError):
        return None


def _positive_decimal(document: dict[str, Any], field: str) -> Decimal:
    value = document.get(field)
    if value is None:
        raise AdjustedPriceUnavailable(f"adjusted price lacks {field}")
    result = Decimal(str(value))
    if result <= 0:
        raise AdjustedPriceUnavailable(f"adjusted price {field} is not positive")
    return result


@dataclass(frozen=True)
class AdjustedPriceBar:
    symbol: str
    market: str
    trade_date: date
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    adjustment_mode: str
    data_version: str
    data_ref: str
    suspended: bool | None
    volume: int | None


class AdjustedPriceResolver:
    """Only accepts records that explicitly prove their adjustment contract."""

    def __init__(self, db, *, collection: str = "stock_daily_quotes"):
        self.db = db
        self.collection = db[collection]

    async def series(
        self,
        *,
        symbol: str,
        market: str,
        start: date,
        end: date,
        required_mode: str,
        required_version: str | None = None,
    ) -> list[AdjustedPriceBar]:
        documents = await self.collection.find(
            {
                "$or": [{"symbol": symbol}, {"code": symbol}],
                "period": "daily",
            }
        ).to_list(length=None)
        bars: list[AdjustedPriceBar] = []
        for raw in documents:
            document = clean_document(raw)
            if str(document.get("market") or "").upper() != market.upper():
                continue
            trade_date = _as_date(document.get("trade_date"))
            if trade_date is None or not (start <= trade_date <= end):
                continue
            mode = str(
                document.get("price_adjustment_mode")
                or document.get("adjustment_mode")
                or ""
            ).upper()
            version = str(
                document.get("price_data_version")
                or document.get("adjusted_data_version")
                or ""
            )
            if mode != required_mode.upper() or not version:
                continue
            if required_version is not None and version != required_version:
                continue
            reference = str(
                document.get("data_ref")
                or document.get("_reference")
                or document.get("_id")
                or ""
            )
            if not reference:
                raise AdjustedPriceUnavailable("adjusted price lacks data reference")
            bars.append(
                AdjustedPriceBar(
                    symbol=symbol,
                    market=market,
                    trade_date=trade_date,
                    open=_positive_decimal(document, "adjusted_open"),
                    high=_positive_decimal(document, "adjusted_high"),
                    low=_positive_decimal(document, "adjusted_low"),
                    close=_positive_decimal(document, "adjusted_close"),
                    adjustment_mode=mode,
                    data_version=version,
                    data_ref=reference,
                    suspended=(
                        bool(document["suspended"])
                        if document.get("suspended") is not None
                        else None
                    ),
                    volume=(
                        int(document["volume"])
                        if document.get("volume") is not None
                        else None
                    ),
                )
            )
        bars.sort(key=lambda item: item.trade_date)
        if not bars:
            raise AdjustedPriceUnavailable(
                "no explicit versioned adjusted OHLC exists for requested range"
            )
        versions = {bar.data_version for bar in bars}
        modes = {bar.adjustment_mode for bar in bars}
        if len(versions) != 1 or len(modes) != 1:
            raise AdjustedPriceUnavailable(
                "adjusted price series mixes data versions or adjustment modes"
            )
        identities: dict[date, AdjustedPriceBar] = {}
        for bar in bars:
            existing = identities.get(bar.trade_date)
            if existing is not None and existing != bar:
                raise AdjustedPriceUnavailable(
                    "adjusted price series has conflicting rows for one trade date"
                )
            identities[bar.trade_date] = bar
        bars = [identities[key] for key in sorted(identities)]
        return bars
