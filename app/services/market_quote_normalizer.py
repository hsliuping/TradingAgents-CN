"""Normalize provider-specific quote fields to the market_quotes contract."""

from typing import Any, Dict


def normalize_market_quote(quote: Dict[str, Any]) -> Dict[str, Any]:
    normalized = dict(quote)
    if normalized.get("close") is None and normalized.get("price") is not None:
        normalized["close"] = normalized["price"]
    if normalized.get("pct_chg") is None and normalized.get("change_percent") is not None:
        normalized["pct_chg"] = normalized["change_percent"]
    return normalized
