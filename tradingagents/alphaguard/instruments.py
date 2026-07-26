"""Canonical market and instrument identifiers used by AlphaGuard."""

from __future__ import annotations

import re
from typing import Literal


Market = Literal["CN", "HK", "US"]

_MARKET_ALIASES = {
    "A股": "CN",
    "A_SHARE": "CN",
    "ASHARE": "CN",
    "CN": "CN",
    "SH": "CN",
    "SZ": "CN",
    "SS": "CN",
    "BJ": "CN",
    "港股": "HK",
    "HK": "HK",
    "美股": "US",
    "US": "US",
}


def infer_market(symbol: str) -> Market:
    """Infer the market only from unambiguous symbol decorations."""

    value = str(symbol or "").strip().upper()
    if value.endswith(".HK") or value.startswith("HK"):
        return "HK"
    if re.fullmatch(r"(SH|SZ|BJ)\d{6}", value):
        return "CN"
    if re.fullmatch(r"\d{6}\.(SH|SZ|SS|BJ)", value):
        return "CN"
    if re.fullmatch(r"\d{6}", value):
        return "CN"
    if re.fullmatch(r"[A-Z][A-Z0-9.-]{0,14}", value):
        return "US"
    raise ValueError(f"cannot infer market from symbol: {symbol!r}")


def normalize_market(market: str | None, symbol: str | None = None) -> Market:
    """Normalize project and exchange aliases to CN/HK/US."""

    value = str(market or "").strip().upper().replace("-", "_").replace(" ", "")
    normalized = _MARKET_ALIASES.get(value)
    if normalized:
        return normalized  # type: ignore[return-value]
    if not value and symbol:
        return infer_market(symbol)
    raise ValueError(f"unsupported market: {market!r}")


def normalize_symbol(symbol: str, market: str | None = None) -> str:
    """Return a canonical symbol within the normalized market."""

    value = str(symbol or "").strip().upper().replace(" ", "")
    if not value:
        raise ValueError("symbol must not be empty")
    normalized_market = normalize_market(market, value)

    if normalized_market == "CN":
        value = re.sub(r"^(SH|SZ|BJ)", "", value)
        value = re.sub(r"\.(SH|SZ|SS|BJ)$", "", value)
        if not re.fullmatch(r"\d{6}", value):
            raise ValueError(f"invalid CN symbol: {symbol!r}")
        return value

    if normalized_market == "HK":
        value = re.sub(r"^HK", "", value)
        value = re.sub(r"\.HK$", "", value)
        if not re.fullmatch(r"\d{1,5}", value):
            raise ValueError(f"invalid HK symbol: {symbol!r}")
        return value.zfill(5)

    value = re.sub(r"\.US$", "", value)
    if not re.fullmatch(r"[A-Z][A-Z0-9.-]{0,14}", value):
        raise ValueError(f"invalid US symbol: {symbol!r}")
    return value


def normalize_instrument(symbol: str, market: str | None) -> tuple[Market, str]:
    normalized_market = normalize_market(market, symbol)
    return normalized_market, normalize_symbol(symbol, normalized_market)
