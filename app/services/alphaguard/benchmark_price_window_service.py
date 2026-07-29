"""Create-only lock for Snapshot-bound benchmark daily-price evidence."""

from __future__ import annotations

from datetime import date, datetime, time
from typing import Any
from uuid import NAMESPACE_URL, uuid5

from app.services.alphaguard.paper_storage import clean_document, model_document
from app.services.alphaguard.quant_config import regime_config
from tradingagents.alphaguard.production_data_schemas import (
    BenchmarkPriceWindowManifest,
    production_data_hash,
)


BENCHMARK_WINDOW_COMPATIBILITY_POLICY = (
    "same-provider-version-adjustment-semantics-v1"
)


def _business_timestamp(value: date) -> datetime:
    return datetime.combine(value, time())


def _as_date(value: Any) -> date | None:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    try:
        return date.fromisoformat(str(value)[:10])
    except (TypeError, ValueError):
        return None


class BenchmarkPriceWindowError(RuntimeError):
    pass


class BenchmarkPriceWindowConflict(BenchmarkPriceWindowError):
    pass


class BenchmarkPriceWindowService:
    """Lock exact quote identities; downstream consumers never query latest."""

    COLLECTION = "ag_benchmark_price_window_manifests"
    BENCHMARK_SYMBOL = "000300"
    ADJUSTMENT_MODE = "INDEX_UNADJUSTED_EQUIVALENT"

    def __init__(self, db):
        self.db = db

    @staticmethod
    def verify_integrity(manifest: BenchmarkPriceWindowManifest) -> bool:
        payload = manifest.model_dump(mode="python")
        stored_hash = payload.pop("manifest_hash")
        # schema_version is a model default added after the create-time hash.
        payload.pop("schema_version", None)
        return production_data_hash(
            payload,
            exclude={"created_at"},
        ) == stored_hash

    async def build(
        self,
        *,
        as_of_trade_date: date,
        cutoff_at: datetime,
        execute: bool,
        required_count: int | None = None,
    ) -> dict[str, Any]:
        count = int(
            required_count
            if required_count is not None
            else regime_config()["required_benchmark_sessions"]
        )
        if count < 61:
            raise ValueError("required benchmark count cannot be below 61")
        calendar_rows = (
            await self.db["trading_calendar"]
            .find(
                {
                    "market": "CN",
                    "is_open": True,
                    "session_date": {
                        "$lte": _business_timestamp(as_of_trade_date)
                    },
                }
            )
            .sort("session_date", -1)
            .limit(count)
            .to_list(length=count)
        )
        ordered_dates = sorted(
            {
                parsed
                for row in calendar_rows
                if (parsed := _as_date(row.get("session_date"))) is not None
            }
        )
        if (
            len(ordered_dates) != count
            or ordered_dates[-1] != as_of_trade_date
        ):
            raise BenchmarkPriceWindowError(
                "REGIME_EVIDENCE_NOT_READY: persisted calendar window is incomplete"
            )

        quote_rows = await self.db["stock_daily_quotes"].find(
            {
                "symbol": self.BENCHMARK_SYMBOL,
                "market": "CN",
                "period": "daily",
                "trade_date": {
                    "$in": [_business_timestamp(item) for item in ordered_dates]
                },
                "adjustment_mode": self.ADJUSTMENT_MODE,
                "available_at": {"$lte": cutoff_at},
                "collected_at": {"$lte": cutoff_at},
            }
        ).to_list(length=None)
        by_date: dict[date, list[dict[str, Any]]] = {}
        for raw in quote_rows:
            quote = clean_document(raw)
            quote_date = _as_date(quote.get("trade_date") if quote else None)
            if quote is not None and quote_date is not None:
                by_date.setdefault(quote_date, []).append(quote)
        invalid_dates = {
            item.isoformat(): len(by_date.get(item, []))
            for item in ordered_dates
            if len(by_date.get(item, [])) != 1
        }
        if invalid_dates:
            raise BenchmarkPriceWindowError(
                "REGIME_EVIDENCE_NOT_READY: benchmark quote identities are "
                f"missing or ambiguous: {invalid_dates}"
            )
        ordered_quotes = [by_date[item][0] for item in ordered_dates]
        self.validate_quote_semantics(
            ordered_quotes,
            ordered_dates=ordered_dates,
            as_of_trade_date=as_of_trade_date,
            cutoff_at=cutoff_at,
        )

        quote_ids = [str(item.get("ref_id") or "") for item in ordered_quotes]
        quote_hashes = [
            str(item.get("content_hash") or "") for item in ordered_quotes
        ]
        ordered_versions = [
            str(item.get("price_data_version") or item.get("data_version") or "")
            for item in ordered_quotes
        ]
        provider = str(ordered_quotes[0].get("provider") or "")
        provider_version = str(
            ordered_quotes[0].get("provider_version") or ""
        )
        available_at = max(item["available_at"] for item in ordered_quotes)
        source_payload = {
            "market": "CN",
            "benchmark_symbol": self.BENCHMARK_SYMBOL,
            "as_of_trade_date": as_of_trade_date,
            "required_count": count,
            "adjustment_mode": self.ADJUSTMENT_MODE,
            "provider": provider,
            "provider_version": provider_version,
            "price_data_versions": sorted(set(ordered_versions)),
            "ordered_price_data_versions": ordered_versions,
            "version_compatibility_policy": (
                BENCHMARK_WINDOW_COMPATIBILITY_POLICY
            ),
            "version_compatibility_status": "COMPATIBLE",
            "ordered_trade_dates": ordered_dates,
            "ordered_quote_ids": quote_ids,
            "ordered_quote_hashes": quote_hashes,
        }
        source_hash = production_data_hash(source_payload)
        manifest_id = str(
            uuid5(
                NAMESPACE_URL,
                (
                    "alphaguard:benchmark-price-window:"
                    f"CN:{self.BENCHMARK_SYMBOL}:"
                    f"{as_of_trade_date.isoformat()}:{count}:"
                    f"{self.ADJUSTMENT_MODE}"
                ),
            )
        )
        now = datetime.now()
        now = now.replace(microsecond=(now.microsecond // 1000) * 1000)
        business = {
            "manifest_id": manifest_id,
            "ref_id": manifest_id,
            **source_payload,
            "actual_count": len(ordered_quotes),
            "start_trade_date": ordered_dates[0],
            "end_trade_date": ordered_dates[-1],
            "source_hash": source_hash,
            "available_at": available_at,
            "created_at": now,
        }
        business["manifest_hash"] = production_data_hash(
            business,
            exclude={"created_at"},
        )
        manifest = BenchmarkPriceWindowManifest.model_validate(business)

        existing_raw = await self.db[self.COLLECTION].find_one(
            {"manifest_id": manifest_id}
        )
        existing = clean_document(existing_raw)
        if existing is not None:
            stored = BenchmarkPriceWindowManifest.model_validate(existing)
            if (
                not self.verify_integrity(stored)
                or stored.manifest_hash != manifest.manifest_hash
            ):
                raise BenchmarkPriceWindowConflict(
                    "INTEGRITY_CONFLICT: immutable benchmark window changed"
                )
            manifest = stored
            action = "REUSED"
        else:
            action = "WOULD_CREATE"
            if execute:
                document = model_document(manifest)
                document["_id"] = manifest.manifest_id
                await self.db[self.COLLECTION].insert_one(document)
                action = "CREATED"
        return {
            "status": "READY",
            "write": execute,
            "action": action,
            "manifest": manifest.model_dump(mode="json"),
        }

    async def get_ready(
        self,
        *,
        as_of_trade_date: date,
        cutoff_at: datetime,
    ) -> BenchmarkPriceWindowManifest:
        rows = await self.db[self.COLLECTION].find(
            {
                "market": "CN",
                "benchmark_symbol": self.BENCHMARK_SYMBOL,
                "as_of_trade_date": _business_timestamp(as_of_trade_date),
                "available_at": {"$lte": cutoff_at},
            }
        ).limit(2).to_list(length=2)
        if len(rows) != 1:
            raise BenchmarkPriceWindowError(
                "REGIME_EVIDENCE_NOT_READY: exact benchmark manifest is not unique"
            )
        manifest = BenchmarkPriceWindowManifest.model_validate(
            clean_document(rows[0])
        )
        if not self.verify_integrity(manifest):
            raise BenchmarkPriceWindowConflict(
                "INTEGRITY_CONFLICT: benchmark manifest content hash mismatch"
            )
        return manifest

    @classmethod
    def validate_quote_semantics(
        cls,
        quotes: list[dict[str, Any]],
        *,
        ordered_dates: list[date],
        as_of_trade_date: date,
        cutoff_at: datetime,
    ) -> None:
        if len(quotes) != len(ordered_dates):
            raise BenchmarkPriceWindowError(
                "REGIME_EVIDENCE_NOT_READY: quote count does not match calendar"
            )
        providers = {str(item.get("provider") or "") for item in quotes}
        provider_versions = {
            str(item.get("provider_version") or "") for item in quotes
        }
        modes = {
            str(
                item.get("adjustment_mode")
                or item.get("price_adjustment_mode")
                or ""
            )
            for item in quotes
        }
        if "" in providers or len(providers) != 1:
            raise BenchmarkPriceWindowError(
                "REGIME_EVIDENCE_NOT_READY: benchmark provider discontinuity"
            )
        if "" in provider_versions or len(provider_versions) != 1:
            raise BenchmarkPriceWindowError(
                "REGIME_EVIDENCE_NOT_READY: benchmark provider-version discontinuity"
            )
        if modes != {cls.ADJUSTMENT_MODE}:
            raise BenchmarkPriceWindowError(
                "REGIME_EVIDENCE_NOT_READY: benchmark adjustment discontinuity"
            )
        for expected_date, quote in zip(ordered_dates, quotes, strict=True):
            quote_date = _as_date(quote.get("trade_date"))
            if quote_date != expected_date or quote_date > as_of_trade_date:
                raise BenchmarkPriceWindowError(
                    "REGIME_EVIDENCE_NOT_READY: benchmark dates are not locked"
                )
            if str(quote.get("symbol") or "") != cls.BENCHMARK_SYMBOL:
                raise BenchmarkPriceWindowError(
                    "REGIME_EVIDENCE_NOT_READY: benchmark identity mismatch"
                )
            if str(quote.get("period") or "") != "daily":
                raise BenchmarkPriceWindowError(
                    "REGIME_EVIDENCE_NOT_READY: benchmark source is not daily"
                )
            try:
                close = float(quote.get("close"))
            except (TypeError, ValueError):
                close = 0.0
            if close <= 0:
                raise BenchmarkPriceWindowError(
                    "REGIME_EVIDENCE_NOT_READY: benchmark close is invalid"
                )
            if not str(quote.get("ref_id") or ""):
                raise BenchmarkPriceWindowError(
                    "REGIME_EVIDENCE_NOT_READY: benchmark quote identity is absent"
                )
            quote_hash = str(quote.get("content_hash") or "")
            if len(quote_hash) != 64:
                raise BenchmarkPriceWindowError(
                    "REGIME_EVIDENCE_NOT_READY: benchmark quote hash is absent"
                )
            version = str(
                quote.get("price_data_version")
                or quote.get("data_version")
                or ""
            )
            if not version:
                raise BenchmarkPriceWindowError(
                    "REGIME_EVIDENCE_NOT_READY: benchmark version is absent"
                )
            available_at = quote.get("available_at")
            collected_at = quote.get("collected_at")
            if (
                not isinstance(available_at, datetime)
                or not isinstance(collected_at, datetime)
                or available_at > cutoff_at
                or collected_at > cutoff_at
            ):
                raise BenchmarkPriceWindowError(
                    "REGIME_EVIDENCE_NOT_READY: benchmark availability exceeds cutoff"
                )
