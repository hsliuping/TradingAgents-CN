"""Exact-date, dry-run-first persistence for resolved formal daily prices."""

from __future__ import annotations

import asyncio
from dataclasses import asdict
from datetime import date, datetime, time
from decimal import Decimal
from typing import Any

from .daily_price_provider import (
    DailyPriceIntegrityConflict,
    DailyPriceProviderResolver,
    NormalizedDailyPrice,
    ProviderResolution,
    compare_daily_prices,
)
from .production_data_config import daily_price_provider_policy
from .real_data_ingestion_service import real_data_hash


class IncrementalDailyPriceError(RuntimeError):
    pass


def _business_timestamp(value: date, *, hour: int = 0) -> datetime:
    return datetime.combine(value, time(hour=hour))


def _as_float(value: Decimal) -> float:
    return float(format(value, "f"))


def _mongo_safe(value: Any) -> Any:
    if isinstance(value, datetime):
        return value
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, Decimal):
        return format(value, "f")
    if isinstance(value, dict):
        return {str(key): _mongo_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_mongo_safe(item) for item in value]
    return value


def _version(record: NormalizedDailyPrice) -> str:
    source = record.underlying_source.replace("/", "-").replace(" ", "-").lower()
    return (
        f"{record.provider}:{record.provider_version}:{source}:{record.mode}:"
        f"{record.normalization_version}"
    )


def _validation_refs(resolution: ProviderResolution) -> list[dict[str, Any]]:
    result = []
    for probe in resolution.probes:
        result.append(
            {
                "provider": probe.capability.provider_name,
                "provider_version": probe.capability.provider_version,
                "underlying_source": probe.capability.underlying_source,
                "mode": probe.mode,
                "status": probe.status,
                "row_count": probe.row_count,
                "returned_trade_dates": list(probe.returned_trade_dates),
                "source_record_identity": probe.source_record_identity,
                "source_response_hash": (
                    probe.record.source_response_hash if probe.record else None
                ),
                "failure_reason": probe.failure_reason,
                "error_code": probe.error_code,
                "error_type": probe.error_type,
                "provider_update_time": probe.provider_update_time,
                "response_received_at": probe.response_received_at,
            }
        )
    return result


def build_price_document(resolution: ProviderResolution) -> dict[str, Any]:
    if (
        resolution.status != "READY"
        or resolution.raw is None
        or resolution.adjusted is None
    ):
        raise IncrementalDailyPriceError("cannot persist a non-ready resolution")
    raw = resolution.raw
    adjusted = resolution.adjusted
    if (
        raw.provider,
        raw.provider_version,
        raw.underlying_source,
    ) != (
        adjusted.provider,
        adjusted.provider_version,
        adjusted.underlying_source,
    ):
        raise IncrementalDailyPriceError(
            "RAW and adjusted values must have one primary provider"
        )
    is_index = raw.symbol == "000300"
    ref_id = (
        f"index-000300-{raw.trade_date.isoformat()}"
        if is_index
        else f"price-{raw.symbol}-{raw.trade_date.isoformat()}"
    )
    raw_version = _version(raw)
    adjusted_version = _version(adjusted)
    available_at = max(raw.response_received_at, adjusted.response_received_at)
    source_response_hash = real_data_hash(
        {
            "raw": raw.source_response_hash,
            "adjusted": adjusted.source_response_hash,
        }
    )
    business = {
        "ref_id": ref_id,
        "source_record_id": raw.source_record_identity,
        "source_record_identity": raw.source_record_identity,
        "symbol": raw.symbol,
        "code": raw.symbol,
        "market": "CN",
        "business_date": _business_timestamp(raw.trade_date),
        "trade_date": _business_timestamp(raw.trade_date),
        "timestamp": _business_timestamp(raw.trade_date, hour=15),
        "period": "daily",
        "bar_granularity": "PROVIDER_DAILY",
        "bar_completion_status": "COMPLETED",
        "open": _as_float(raw.open),
        "high": _as_float(raw.high),
        "low": _as_float(raw.low),
        "close": _as_float(raw.close),
        "adjusted_open": _as_float(adjusted.open),
        "adjusted_high": _as_float(adjusted.high),
        "adjusted_low": _as_float(adjusted.low),
        "adjusted_close": _as_float(adjusted.close),
        "volume": raw.volume_shares,
        "volume_shares": raw.volume_shares,
        "amount": _as_float(raw.amount_cny),
        "amount_cny": _as_float(raw.amount_cny),
        "adjustment_mode": (
            "INDEX_UNADJUSTED_EQUIVALENT" if is_index else "QFQ"
        ),
        "price_adjustment_mode": (
            "INDEX_UNADJUSTED_EQUIVALENT" if is_index else "QFQ"
        ),
        "raw_adjustment_mode": "RAW",
        "adjusted_adjustment_mode": (
            "INDEX_UNADJUSTED_EQUIVALENT" if is_index else "QFQ"
        ),
        "price_data_version": adjusted_version,
        "raw_data_version": raw_version,
        "adjusted_data_version": adjusted_version,
        "data_version": adjusted_version,
        "data_ref": (
            f"index_daily:{ref_id}"
            if is_index
            else f"stock_daily_quotes:{ref_id}"
        ),
        "source": raw.underlying_source,
        "provider": raw.provider,
        "provider_version": raw.provider_version,
        "normalization_version": raw.normalization_version,
        "normalization_policy_version": daily_price_provider_policy()[
            "policy_version"
        ],
        "volume_normalization_rule": raw.volume_normalization_rule,
        "amount_normalization_rule": raw.amount_normalization_rule,
        "provider_update_time": raw.provider_update_time,
        "update_time_verified": raw.update_time_verified,
        "fallback_reason": resolution.fallback_reason,
        "source_response_hash": source_response_hash,
    }
    return {
        **business,
        "available_at": available_at,
        "response_received_at": available_at,
        "collected_at": available_at,
        "created_at": available_at,
        "updated_at": available_at,
        "content_hash": real_data_hash(business),
        "validation_refs": _mongo_safe(_validation_refs(resolution)),
        "cross_provider_comparisons": _mongo_safe(
            list(resolution.comparisons)
        ),
        "schema_version": (
            "alphaguard-incremental-daily-price-v1"
            if not is_index
            else "alphaguard-incremental-index-price-v1"
        ),
    }


def _existing_record(
    document: dict[str, Any],
    *,
    mode: str,
) -> NormalizedDailyPrice:
    adjusted = mode != "RAW"
    prefix = "adjusted_" if adjusted else ""
    source = str(document.get("source") or document.get("provider") or "unknown")
    return NormalizedDailyPrice(
        market="CN",
        symbol=str(document["symbol"]),
        trade_date=document["trade_date"].date(),
        mode=mode,  # type: ignore[arg-type]
        open=Decimal(str(document[f"{prefix}open"])),
        high=Decimal(str(document[f"{prefix}high"])),
        low=Decimal(str(document[f"{prefix}low"])),
        close=Decimal(str(document[f"{prefix}close"])),
        volume_shares=int(
            document.get("volume_shares", document.get("volume"))
        ),
        amount_cny=Decimal(
            str(document.get("amount_cny", document.get("amount")))
        ),
        provider=str(document.get("provider") or "unknown"),
        provider_version=str(document.get("provider_version") or "unknown"),
        underlying_source=source,
        source_record_identity=str(
            document.get("source_record_identity")
            or document.get("source_record_id")
            or document.get("ref_id")
        ),
        provider_update_time=document.get("provider_update_time"),
        response_received_at=(
            document.get("response_received_at")
            or document.get("collected_at")
            or document.get("available_at")
        ),
        update_time_verified=bool(document.get("update_time_verified")),
        source_response_hash=str(document.get("source_response_hash") or ""),
        normalization_version=str(
            document.get("normalization_version") or "legacy"
        ),
        volume_normalization_rule=str(
            document.get("volume_normalization_rule") or "legacy"
        ),
        amount_normalization_rule=str(
            document.get("amount_normalization_rule") or "legacy"
        ),
        content_hash=str(document.get("content_hash") or ""),
    )


def compare_resolution_with_existing(
    resolution: ProviderResolution,
    existing: dict[str, Any],
) -> list[dict[str, Any]]:
    if (
        resolution.status != "READY"
        or resolution.raw is None
        or resolution.adjusted is None
    ):
        return []
    modes = (
        ("INDEX_UNADJUSTED_EQUIVALENT",)
        if resolution.symbol == "000300"
        else ("RAW", "QFQ")
    )
    comparisons = []
    for mode in modes:
        selected = (
            resolution.raw
            if mode in {"RAW", "INDEX_UNADJUSTED_EQUIVALENT"}
            else resolution.adjusted
        )
        comparisons.append(
            {
                **compare_daily_prices(
                    selected,
                    _existing_record(existing, mode=mode),
                ),
                "comparison_target": "PERSISTED_CONTROL",
            }
        )
    return comparisons


class IncrementalDailyPriceService:
    def __init__(
        self,
        db,
        resolver: DailyPriceProviderResolver | None = None,
    ):
        self.db = db
        self.resolver = resolver or DailyPriceProviderResolver()
        self.policy = daily_price_provider_policy()

    async def _calendar_gate(self, trade_date: date, now: datetime) -> None:
        close_at = time.fromisoformat(str(self.policy["market_close_time"]))
        if now.date() < trade_date or (
            now.date() == trade_date and now.time() < close_at
        ):
            raise IncrementalDailyPriceError(
                "completed-daily gate rejected a pre-close request"
            )
        calendar = await self.db["trading_calendar"].find_one(
            {
                "market": "CN",
                "session_date": _business_timestamp(trade_date),
                "is_open": True,
            }
        )
        if calendar is None:
            raise IncrementalDailyPriceError(
                "persisted CN calendar does not confirm an open trade date"
            )

    async def probe(
        self,
        *,
        symbols: list[str],
        trade_date: date,
        now: datetime | None = None,
    ) -> list[ProviderResolution]:
        now = now or datetime.now()
        await self._calendar_gate(trade_date, now)
        unique = list(dict.fromkeys(symbols))
        return [
            await asyncio.to_thread(
                self.resolver.resolve,
                symbol=symbol,
                trade_date=trade_date,
            )
            for symbol in unique
        ]

    async def compare_existing(
        self,
        *,
        resolutions: list[ProviderResolution],
    ) -> list[dict[str, Any]]:
        reports = []
        for resolution in resolutions:
            ref_id = (
                f"index-000300-{resolution.trade_date.isoformat()}"
                if resolution.symbol == "000300"
                else f"price-{resolution.symbol}-{resolution.trade_date.isoformat()}"
            )
            existing = await self.db["stock_daily_quotes"].find_one(
                {"ref_id": ref_id}
            )
            reports.append(
                {
                    "symbol": resolution.symbol,
                    "ref_id": ref_id,
                    "exists": existing is not None,
                    "comparisons": (
                        compare_resolution_with_existing(resolution, existing)
                        if existing
                        else []
                    ),
                }
            )
        return reports

    async def sync(
        self,
        *,
        symbols: list[str],
        trade_date: date,
        execute: bool,
        now: datetime | None = None,
        resolutions: list[ProviderResolution] | None = None,
    ) -> dict[str, Any]:
        now = now or datetime.now()
        await self._calendar_gate(trade_date, now)
        resolutions = resolutions or await self.probe(
            symbols=symbols,
            trade_date=trade_date,
            now=now,
        )
        if {item.symbol for item in resolutions} != set(symbols):
            raise IncrementalDailyPriceError(
                "provider resolutions do not cover the requested symbols"
            )
        not_ready = [
            item.report()
            for item in resolutions
            if item.status != "READY"
        ]
        if not_ready:
            status = (
                "INTEGRITY_CONFLICT"
                if any(
                    item["status"] == "INTEGRITY_CONFLICT"
                    for item in not_ready
                )
                else "INSUFFICIENT_DATA"
            )
            return {
                "status": status,
                "trade_date": trade_date,
                "write": False,
                "results": [item.report() for item in resolutions],
                "created": 0,
                "reused": 0,
                "conflicts": 0,
            }
        documents = [build_price_document(item) for item in resolutions]
        existing_rows = await self.db["stock_daily_quotes"].find(
            {"ref_id": {"$in": [item["ref_id"] for item in documents]}}
        ).to_list(length=None)
        existing_by_id = {
            str(item["ref_id"]): item for item in existing_rows
        }
        created = 0
        reused = 0
        conflicts = []
        actions = []
        for document in documents:
            existing = existing_by_id.get(document["ref_id"])
            if existing is None:
                actions.append(
                    {"ref_id": document["ref_id"], "action": "WOULD_CREATE"}
                )
            elif str(existing.get("content_hash")) == document["content_hash"]:
                reused += 1
                actions.append(
                    {"ref_id": document["ref_id"], "action": "REUSED"}
                )
            else:
                conflicts.append(document["ref_id"])
                actions.append(
                    {
                        "ref_id": document["ref_id"],
                        "action": "INTEGRITY_CONFLICT",
                        "existing_content_hash": existing.get("content_hash"),
                        "proposed_content_hash": document["content_hash"],
                    }
                )
        if conflicts:
            raise DailyPriceIntegrityConflict(
                "immutable daily-price identities conflict: "
                + ",".join(conflicts)
            )
        if execute:
            for document in documents:
                if document["ref_id"] in existing_by_id:
                    continue
                await self.db["stock_daily_quotes"].insert_one(document)
                created += 1
            for document in documents:
                persisted = await self.db["stock_daily_quotes"].find_one(
                    {"ref_id": document["ref_id"]}
                )
                if (
                    persisted is None
                    or persisted.get("content_hash") != document["content_hash"]
                ):
                    raise DailyPriceIntegrityConflict(
                        f"post-write verification failed for {document['ref_id']}"
                    )
            event_business = {
                "event_type": "INCREMENTAL_DAILY_PRICE_SYNC_COMPLETED",
                "market": "CN",
                "trade_date": _business_timestamp(trade_date),
                "symbols": sorted(symbols),
                "content_hashes": {
                    item["ref_id"]: item["content_hash"] for item in documents
                },
                "policy_version": self.policy["policy_version"],
            }
            event_id = f"production-price-sync:{real_data_hash(event_business)}"
            if not await self.db["ag_production_data_events"].find_one(
                {"event_id": event_id}
            ):
                await self.db["ag_production_data_events"].insert_one(
                    {
                        "event_id": event_id,
                        **event_business,
                        "created_at": now,
                        "content_hash": real_data_hash(event_business),
                    }
                )
        return {
            "status": "READY",
            "trade_date": trade_date,
            "write": execute,
            "created": created,
            "reused": reused,
            "conflicts": 0,
            "actions": actions,
            "results": [item.report() for item in resolutions],
            "documents": [
                {
                    key: value
                    for key, value in document.items()
                    if key
                    in {
                        "ref_id",
                        "symbol",
                        "trade_date",
                        "open",
                        "high",
                        "low",
                        "close",
                        "adjusted_open",
                        "adjusted_high",
                        "adjusted_low",
                        "adjusted_close",
                        "volume_shares",
                        "amount_cny",
                        "source",
                        "provider",
                        "provider_version",
                        "raw_data_version",
                        "adjusted_data_version",
                        "adjustment_mode",
                        "available_at",
                        "collected_at",
                        "content_hash",
                        "fallback_reason",
                    }
                }
                for document in documents
            ],
        }

    async def local_gate(
        self,
        *,
        symbols: list[str],
        trade_date: date,
    ) -> dict[str, Any]:
        rows = []
        failures = []
        close_at = datetime.combine(
            trade_date,
            time.fromisoformat(str(self.policy["market_close_time"])),
        )
        for symbol in symbols:
            ref_id = (
                f"index-000300-{trade_date.isoformat()}"
                if symbol == "000300"
                else f"price-{symbol}-{trade_date.isoformat()}"
            )
            row = await self.db["stock_daily_quotes"].find_one(
                {"ref_id": ref_id}
            )
            missing = []
            if row is None:
                missing.append("ROW")
            else:
                required = (
                    "open",
                    "high",
                    "low",
                    "close",
                    "adjusted_open",
                    "adjusted_high",
                    "adjusted_low",
                    "adjusted_close",
                    "volume_shares",
                    "amount_cny",
                    "source",
                    "provider",
                    "provider_version",
                    "raw_data_version",
                    "adjusted_data_version",
                    "content_hash",
                    "collected_at",
                )
                missing.extend(
                    key for key in required if row.get(key) is None
                )
                if row.get("trade_date") != _business_timestamp(trade_date):
                    missing.append("TRADE_DATE")
                if row.get("period") != "daily":
                    missing.append("DAILY_PERIOD")
                if row.get("bar_completion_status") != "COMPLETED":
                    missing.append("COMPLETED_BAR")
                if row.get("collected_at") and row["collected_at"] < close_at:
                    missing.append("COLLECTED_BEFORE_CLOSE")
                expected_hash = real_data_hash(
                    {
                        key: value
                        for key, value in row.items()
                        if key
                        not in {
                            "_id",
                            "available_at",
                            "response_received_at",
                            "collected_at",
                            "created_at",
                            "updated_at",
                            "content_hash",
                            "validation_refs",
                            "cross_provider_comparisons",
                            "schema_version",
                        }
                    }
                )
                if expected_hash != row.get("content_hash"):
                    missing.append("CONTENT_HASH")
            if missing:
                failures.append({"symbol": symbol, "missing": sorted(set(missing))})
            rows.append(
                {
                    "symbol": symbol,
                    "ref_id": ref_id,
                    "exists": row is not None,
                    "missing": sorted(set(missing)),
                    "provider": row.get("provider") if row else None,
                    "source": row.get("source") if row else None,
                    "raw_data_version": (
                        row.get("raw_data_version") if row else None
                    ),
                    "adjusted_data_version": (
                        row.get("adjusted_data_version") if row else None
                    ),
                    "content_hash": row.get("content_hash") if row else None,
                    "collected_at": row.get("collected_at") if row else None,
                }
            )
        return {
            "status": "READY" if not failures else "NOT_READY",
            "trade_date": trade_date,
            "rows": rows,
            "failures": failures,
        }
