"""Deterministic, non-LLM data quality checks for EvidenceSnapshot creation."""

from __future__ import annotations

import math
from datetime import date, datetime, timezone
from typing import Any
from uuid import uuid4

from bson import ObjectId

from tradingagents.alphaguard.evidence_schemas import DataQualityReport
from tradingagents.alphaguard.instruments import normalize_instrument


_REFERENCE_COLLECTIONS = {
    "market_quotes": "market_quotes",
    "stock_daily_data": "stock_daily_data",
    "stock_historical_data": "stock_historical_data",
    "historical_data": "historical_data",
    "financial_data": "stock_financial_data",
    "stock_financial_data": "stock_financial_data",
    "stock_news": "stock_news",
    "announcements": "stock_announcements",
    "stock_announcements": "stock_announcements",
    "paper_account": "paper_accounts",
    "paper_accounts": "paper_accounts",
    "sync_status": "sync_status",
}

_IDENTITY_FIELDS = (
    "id",
    "news_id",
    "announcement_id",
    "code",
    "symbol",
    "full_symbol",
    "user_id",
    "account_id",
    "job",
    "data_type",
)
_DATE_FIELDS = (
    "trade_date",
    "date",
    "published_at",
    "publish_time",
    "announcement_time",
    "timestamp",
    "updated_at",
)


def _as_datetime(value: Any) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    if isinstance(value, date):
        return datetime.combine(value, datetime.min.time())
    text = str(value).strip()
    if not text:
        return None
    if text.isdigit() and len(text) == 8:
        try:
            return datetime.strptime(text, "%Y%m%d")
        except ValueError:
            return None
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        try:
            return datetime.strptime(text[:10], "%Y-%m-%d")
        except ValueError:
            return None


def _comparable(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _document_datetime(document: dict[str, Any]) -> datetime | None:
    for field in _DATE_FIELDS:
        parsed = _as_datetime(document.get(field))
        if parsed is not None:
            return parsed
    return None


def _numeric(document: dict[str, Any], field: str) -> float | None:
    value = document.get(field)
    if value is None:
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


class DataQualityGate:
    """Resolve immutable references and evaluate the first PR-003 ruleset."""

    async def resolve_references(
        self, db, raw_refs: dict[str, list[str]]
    ) -> tuple[dict[str, list[dict[str, Any]]], list[str]]:
        resolved: dict[str, list[dict[str, Any]]] = {}
        invalid: list[str] = []
        for category, references in raw_refs.items():
            resolved[category] = []
            for reference in references:
                parts = str(reference).split(":")
                if len(parts) < 2:
                    invalid.append(reference)
                    continue
                collection_name = _REFERENCE_COLLECTIONS.get(parts[0])
                identifier = parts[1]
                if collection_name is None or not identifier:
                    invalid.append(reference)
                    continue
                clauses: list[dict[str, Any]] = [
                    {field: identifier} for field in _IDENTITY_FIELDS
                ]
                if ObjectId.is_valid(identifier):
                    clauses.append({"_id": ObjectId(identifier)})
                clauses.append({"_id": identifier})
                document = await db[collection_name].find_one({"$or": clauses})
                if document is None:
                    invalid.append(reference)
                    continue
                cleaned = dict(document)
                cleaned["_reference"] = reference
                if len(parts) >= 3:
                    cleaned["_reference_date"] = ":".join(parts[2:])
                resolved[category].append(cleaned)
        return resolved, invalid

    def evaluate_documents(
        self,
        *,
        symbol: str,
        market: str,
        trade_date: date,
        price_cutoff_at: datetime,
        news_cutoff_at: datetime,
        announcement_cutoff_at: datetime,
        resolved: dict[str, list[dict[str, Any]]],
        invalid_refs: list[str],
        required_sources: list[str] | None = None,
    ) -> DataQualityReport:
        normalized_market, normalized_symbol = normalize_instrument(symbol, market)
        missing: list[str] = []
        stale: list[str] = []
        anomalies: list[str] = []
        blocking: list[str] = []
        required_sources = required_sources or ["prices"]

        price_documents = list(resolved.get("prices", []))
        if not price_documents:
            missing.append("prices")
            blocking.append("missing target trade-date price data")

        matching_prices: list[dict[str, Any]] = []
        for document in price_documents:
            document_date = _document_datetime(document)
            reference_date = _as_datetime(document.get("_reference_date"))
            effective_date = document_date or reference_date
            if effective_date and effective_date.date() == trade_date:
                matching_prices.append(document)
        if price_documents and not matching_prices:
            blocking.append("price reference does not identify the target trade date")

        for document in matching_prices:
            values = {
                field: _numeric(document, field)
                for field in ("open", "high", "low", "close")
            }
            invalid_ohlc = [
                field
                for field, value in values.items()
                if value is None or value <= 0
            ]
            if invalid_ohlc:
                missing.extend(f"prices.{field}" for field in invalid_ohlc)
                blocking.append("OHLC values must be finite positive numbers")
                continue
            open_price = values["open"]
            high = values["high"]
            low = values["low"]
            close = values["close"]
            assert None not in (open_price, high, low, close)
            if high < max(open_price, close, low):
                anomalies.append("price.high is below another OHLC value")
                blocking.append("OHLC high value is inconsistent")
            if low > min(open_price, close, high):
                anomalies.append("price.low is above another OHLC value")
                blocking.append("OHLC low value is inconsistent")
            for field in ("volume", "amount"):
                number = _numeric(document, field)
                if number is None:
                    missing.append(f"prices.{field}")
                    blocking.append(f"price {field} is missing or invalid")
                elif number < 0:
                    anomalies.append(f"price.{field} is negative")
                    blocking.append(f"price {field} cannot be negative")
            document_date = _document_datetime(document)
            if document_date and document_date.date() > trade_date:
                blocking.append("price data is later than the decision trade date")
            if document_date and _comparable(document_date) > _comparable(price_cutoff_at):
                blocking.append("price data timestamp exceeds price cutoff")

        for category, cutoff in (
            ("news", news_cutoff_at),
            ("announcements", announcement_cutoff_at),
        ):
            for document in resolved.get(category, []):
                published_at = _document_datetime(document)
                if published_at and _comparable(published_at) > _comparable(cutoff):
                    anomalies.append(f"{category} contains a future timestamp")
                    blocking.append(f"{category} timestamp exceeds evidence cutoff")

        sync_documents = resolved.get("sync", [])
        if "sync" in required_sources and not sync_documents:
            missing.append("sync")
            blocking.append("required data-source sync status is missing")
        for document in sync_documents:
            sync_status = str(document.get("status", "")).lower()
            if sync_status not in {"completed", "success", "succeeded", "healthy"}:
                stale.append(str(document.get("_reference", "sync")))
                blocking.append("required data source has not completed synchronization")

        for category in required_sources:
            if category != "sync" and not resolved.get(category):
                missing.append(category)
                if category == "prices":
                    blocking.append("required price source is unavailable")
                else:
                    stale.append(category)

        if not resolved.get("financials"):
            missing.append("financials")
            stale.append("financials")
        if not resolved.get("news") and not resolved.get("announcements"):
            missing.append("news_or_announcements")

        if invalid_refs:
            anomalies.extend(f"unresolved reference: {ref}" for ref in invalid_refs)
            blocking.append("one or more evidence references cannot be resolved")

        present_categories = sum(
            1
            for category in ("prices", "financials", "news_or_announcements")
            if (
                (category == "prices" and matching_prices)
                or (category == "financials" and resolved.get("financials"))
                or (
                    category == "news_or_announcements"
                    and (resolved.get("news") or resolved.get("announcements"))
                )
            )
        )
        completeness_score = round(present_categories / 3, 4)
        freshness_score = 1.0
        if stale:
            freshness_score = max(0.0, round(1 - 0.2 * len(set(stale)), 4))
        consistency_score = max(
            0.0, round(1 - 0.15 * len(set(anomalies)), 4)
        )
        status = "FAIL" if blocking else ("WARN" if missing or stale or anomalies else "PASS")

        return DataQualityReport(
            quality_report_id=str(uuid4()),
            symbol=normalized_symbol,
            market=normalized_market,
            trade_date=trade_date,
            status=status,
            completeness_score=completeness_score,
            freshness_score=freshness_score,
            consistency_score=consistency_score,
            missing_fields=missing,
            stale_sources=stale,
            anomalies=anomalies,
            blocking_reasons=blocking,
            checked_at=datetime.utcnow(),
        )

    async def evaluate(
        self,
        *,
        db,
        symbol: str,
        market: str,
        trade_date: date,
        price_cutoff_at: datetime,
        news_cutoff_at: datetime,
        announcement_cutoff_at: datetime,
        raw_refs: dict[str, list[str]],
        required_sources: list[str] | None = None,
    ) -> DataQualityReport:
        resolved, invalid_refs = await self.resolve_references(db, raw_refs)
        return self.evaluate_documents(
            symbol=symbol,
            market=market,
            trade_date=trade_date,
            price_cutoff_at=price_cutoff_at,
            news_cutoff_at=news_cutoff_at,
            announcement_cutoff_at=announcement_cutoff_at,
            resolved=resolved,
            invalid_refs=invalid_refs,
            required_sources=required_sources,
        )
