"""Resolve only immutable EvidenceSnapshot references within their cutoffs."""

from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from tradingagents.alphaguard.evidence_schemas import EvidenceSnapshot
from tradingagents.alphaguard.instruments import normalize_instrument

from .data_quality_gate import DataQualityGate, _as_datetime
from .evidence_snapshot_service import EvidenceSnapshotService
from .paper_storage import clean_document
from .quant_config import sha256_value


class SnapshotResolutionError(ValueError):
    pass


class ResolvedSnapshotData(BaseModel):
    model_config = ConfigDict(extra="forbid", arbitrary_types_allowed=True)

    snapshot: EvidenceSnapshot
    prices: list[dict[str, Any]] = Field(default_factory=list)
    benchmark_prices: list[dict[str, Any]] = Field(default_factory=list)
    financials: list[dict[str, Any]] = Field(default_factory=list)
    news: list[dict[str, Any]] = Field(default_factory=list)
    announcements: list[dict[str, Any]] = Field(default_factory=list)
    positions: list[dict[str, Any]] = Field(default_factory=list)
    portfolio_positions: list[dict[str, Any]] = Field(default_factory=list)
    accounts: list[dict[str, Any]] = Field(default_factory=list)
    orders: list[dict[str, Any]] = Field(default_factory=list)
    instruments: list[dict[str, Any]] = Field(default_factory=list)
    market_context: list[dict[str, Any]] = Field(default_factory=list)
    market_context_window: list[dict[str, Any]] = Field(default_factory=list)
    trading_calendar: list[dict[str, Any]] = Field(default_factory=list)
    input_refs: list[str]
    excluded_refs: list[str]
    input_hash: str = Field(pattern=r"^[0-9a-f]{64}$")


def _utc(value: datetime) -> datetime:
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


def _first_datetime(document: dict[str, Any], fields: tuple[str, ...]) -> datetime | None:
    for field in fields:
        parsed = _as_datetime(document.get(field))
        if parsed is not None:
            return parsed
    return None


def _on_or_before(value: datetime | None, cutoff: datetime) -> bool:
    return value is not None and _utc(value) <= _utc(cutoff)


def _date_on_or_before(document: dict[str, Any], trade_date: date) -> bool:
    value = _first_datetime(document, ("trade_date", "date", "session_date"))
    return value is not None and value.date() <= trade_date


class SnapshotDataResolver:
    """Fail closed: no symbol/latest queries and no external data access."""

    def __init__(self, db):
        self.db = db
        self.snapshot_service = EvidenceSnapshotService(db=db)
        self.gate = DataQualityGate()

    async def resolve(
        self,
        snapshot_id: str,
        *,
        user_id: str | None = None,
        allow_legacy_unversioned: bool = False,
    ) -> ResolvedSnapshotData:
        snapshot = await self.snapshot_service.get(snapshot_id, user_id)
        if snapshot is None:
            raise SnapshotResolutionError("EvidenceSnapshot not found")
        if not self.snapshot_service.verify_integrity(snapshot):
            raise SnapshotResolutionError("EvidenceSnapshot immutable hash mismatch")
        if (
            not snapshot.factor_version_set or not snapshot.strategy_version
        ) and not allow_legacy_unversioned:
            raise SnapshotResolutionError(
                "legacy unversioned snapshot requires explicit compatibility research mode"
            )

        resolved, invalid = await self.gate.resolve_references(
            self.db, snapshot.raw_refs
        )
        if invalid:
            raise SnapshotResolutionError(
                f"unresolved or ambiguous snapshot references: {sorted(invalid)}"
            )

        accepted: dict[str, list[dict[str, Any]]] = {
            "prices": [],
            "benchmark_prices": [],
            "financials": [],
            "news": [],
            "announcements": [],
            "positions": [],
            "portfolio_positions": [],
            "accounts": [],
            "orders": [],
            "instruments": [],
            "market_context": [],
            "market_context_window": [],
            "trading_calendar": [],
        }
        excluded: list[str] = []
        category_aliases = {
            "prices": "prices",
            "price_history": "prices",
            "benchmark_prices": "benchmark_prices",
            "index_prices": "benchmark_prices",
            "financials": "financials",
            "financial_data": "financials",
            "news": "news",
            "announcements": "announcements",
            "account_positions": "positions",
            "positions": "positions",
            "portfolio_positions": "portfolio_positions",
            "account_portfolio_positions": "portfolio_positions",
            "paper_accounts": "accounts",
            "account": "accounts",
            "accounts": "accounts",
            "paper_orders": "orders",
            "account_orders": "orders",
            "orders": "orders",
            "stock_basic_info": "instruments",
            "instrument": "instruments",
            "market_context": "market_context",
            "market_breadth": "market_context",
            "market_context_window": "market_context_window",
            "trading_calendar": "trading_calendar",
            "calendar": "trading_calendar",
        }
        for source_category, documents in resolved.items():
            category = category_aliases.get(source_category)
            if category is None:
                excluded.extend(str(item.get("_reference")) for item in documents)
                continue
            for document in documents:
                reference = str(document.get("_reference"))
                permitted = self._permitted(snapshot, category, document)
                if permitted:
                    cleaned = clean_document(document)
                    if cleaned is None:
                        raise SnapshotResolutionError(
                            f"resolved reference unexpectedly empty: {reference}"
                        )
                    accepted[category].append(cleaned)
                else:
                    excluded.append(reference)

        for category in accepted:
            accepted[category].sort(
                key=lambda item: str(
                    item.get("trade_date")
                    or item.get("report_period")
                    or item.get("publish_time")
                    or item.get("session_date")
                    or ""
                )
            )
        refs = sorted(
            str(document["_reference"])
            for documents in accepted.values()
            for document in documents
        )
        payload_hash = sha256_value(
            {
                "snapshot_id": snapshot.snapshot_id,
                "immutable_hash": snapshot.immutable_hash,
                "documents": accepted,
            }
        )
        return ResolvedSnapshotData(
            snapshot=snapshot,
            **accepted,
            input_refs=refs,
            excluded_refs=sorted(excluded),
            input_hash=payload_hash,
        )

    @staticmethod
    def _permitted(
        snapshot: EvidenceSnapshot, category: str, document: dict[str, Any]
    ) -> bool:
        if category in {
            "prices",
            "financials",
            "news",
            "announcements",
            "positions",
            "instruments",
        } and not SnapshotDataResolver._matches_target(snapshot, document):
            return False
        if category in {
            "prices",
            "benchmark_prices",
            "market_context",
            "market_context_window",
        }:
            if category == "market_context_window":
                as_of = _first_datetime(document, ("as_of_trade_date",))
                if as_of is None or as_of.date() != snapshot.trade_date:
                    return False
                observed = _first_datetime(
                    document, ("created_at", "available_at")
                )
                return _on_or_before(observed, snapshot.price_cutoff_at)
            if not _date_on_or_before(document, snapshot.trade_date):
                return False
            observed = _first_datetime(
                document, ("timestamp", "as_of", "updated_at", "created_at")
            )
            return observed is None or _on_or_before(observed, snapshot.price_cutoff_at)
        if category == "financials":
            report = _first_datetime(document, ("report_period", "end_date"))
            disclosed = _first_datetime(
                document,
                ("f_ann_date", "ann_date", "publish_date", "published_at"),
            )
            return (
                report is not None
                and report.date() <= snapshot.trade_date
                and _on_or_before(disclosed, snapshot.announcement_cutoff_at)
            )
        if category == "news":
            published = _first_datetime(
                document, ("publish_time", "published_at", "timestamp")
            )
            return _on_or_before(published, snapshot.news_cutoff_at)
        if category == "announcements":
            published = _first_datetime(
                document,
                ("announcement_time", "published_at", "publish_time", "timestamp"),
            )
            return _on_or_before(published, snapshot.announcement_cutoff_at)
        if category == "positions":
            observed = _first_datetime(
                document, ("as_of", "snapshot_at", "updated_at", "created_at")
            )
            return _on_or_before(observed, snapshot.price_cutoff_at)
        if category in {"portfolio_positions", "accounts", "orders"}:
            if str(document.get("user_id") or "") != snapshot.user_id:
                return False
            observed = _first_datetime(
                document,
                (
                    "as_of",
                    "snapshot_at",
                    "updated_at",
                    "created_at",
                    "filled_at",
                ),
            )
            return _on_or_before(observed, snapshot.price_cutoff_at)
        if category == "instruments":
            observed = _first_datetime(
                document, ("as_of", "updated_at", "created_at")
            )
            return observed is None or _on_or_before(
                observed, snapshot.price_cutoff_at
            )
        if category == "trading_calendar":
            published = _first_datetime(
                document, ("as_of", "published_at", "created_at")
            )
            # Future sessions are public calendar facts, but the calendar itself
            # must have existed at the snapshot cutoff.
            return _on_or_before(published, snapshot.price_cutoff_at)
        return False

    @staticmethod
    def _matches_target(
        snapshot: EvidenceSnapshot, document: dict[str, Any]
    ) -> bool:
        raw_symbol = (
            document.get("code")
            or document.get("symbol")
            or document.get("full_symbol")
        )
        if not raw_symbol and document.get("symbols"):
            raw_symbols = document["symbols"]
            if not isinstance(raw_symbols, list):
                return False
            normalized = set()
            for item in raw_symbols:
                try:
                    normalized.add(
                        normalize_instrument(item, snapshot.market)
                    )
                except ValueError:
                    continue
            return (snapshot.market, snapshot.symbol) in normalized
        if raw_symbol:
            try:
                market, symbol = normalize_instrument(
                    raw_symbol, document.get("market") or snapshot.market
                )
            except ValueError:
                return False
            if market != snapshot.market or symbol != snapshot.symbol:
                return False
        if document.get("user_id") and str(document["user_id"]) != snapshot.user_id:
            return False
        return True
