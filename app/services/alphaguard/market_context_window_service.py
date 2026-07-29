"""Create-only lock for the ordered production MarketContext input window."""

from __future__ import annotations

from datetime import date, datetime, time
from typing import Any
from uuid import NAMESPACE_URL, uuid5

from app.services.alphaguard.paper_storage import clean_document, model_document
from app.services.alphaguard.production_data_config import (
    production_market_context_history_policy,
    production_market_context_policy,
)
from tradingagents.alphaguard.production_data_schemas import (
    MarketContextWindowManifest,
    production_data_hash,
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


class MarketContextWindowError(RuntimeError):
    pass


class MarketContextWindowConflict(MarketContextWindowError):
    pass


class MarketContextWindowService:
    """Lock prior production contexts plus the current as-of context."""

    COLLECTION = "ag_market_context_window_manifests"

    def __init__(self, db):
        self.db = db
        self.context_policy = production_market_context_policy()
        self.history_policy = production_market_context_history_policy()

    @staticmethod
    def verify_integrity(manifest: MarketContextWindowManifest) -> bool:
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
        prior_session_count: int | None = None,
    ) -> dict[str, Any]:
        prior_count = (
            int(prior_session_count)
            if prior_session_count is not None
            else int(self.history_policy["prior_session_count"])
        )
        if prior_count <= 0:
            raise ValueError("prior_session_count must be positive")
        calculation_version = str(self.context_policy["calculation_version"])
        if calculation_version != str(self.history_policy["calculation_version"]):
            raise MarketContextWindowError(
                "REGIME_INPUT_NOT_READY: current and history context versions differ"
            )

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
            .limit(prior_count + 1)
            .to_list(length=prior_count + 1)
        )
        ordered_dates = sorted(
            {
                parsed
                for row in calendar_rows
                if (parsed := _as_date(row.get("session_date"))) is not None
            }
        )
        required_count = prior_count + 1
        if (
            len(ordered_dates) != required_count
            or ordered_dates[-1] != as_of_trade_date
        ):
            raise MarketContextWindowError(
                "REGIME_INPUT_NOT_READY: persisted calendar window is incomplete"
            )

        context_rows = await self.db["ag_market_contexts"].find(
            {
                "market": "CN",
                "trade_date": {
                    "$in": [_business_timestamp(item) for item in ordered_dates]
                },
                "calculation_status": "READY",
                "calculation_version": calculation_version,
                "available_at": {"$lte": cutoff_at},
                "collected_at": {"$lte": cutoff_at},
            }
        ).to_list(length=None)
        contexts_by_date: dict[date, list[dict[str, Any]]] = {}
        for raw in context_rows:
            context = clean_document(raw)
            context_date = _as_date(context.get("trade_date"))
            if context_date is not None:
                contexts_by_date.setdefault(context_date, []).append(context)
        invalid_dates = {
            item.isoformat(): len(contexts_by_date.get(item, []))
            for item in ordered_dates
            if len(contexts_by_date.get(item, [])) != 1
        }
        if invalid_dates:
            raise MarketContextWindowError(
                "REGIME_INPUT_NOT_READY: production MarketContext identities "
                f"are missing or ambiguous: {invalid_dates}"
            )

        ordered_contexts = [contexts_by_date[item][0] for item in ordered_dates]
        context_ids = [str(item.get("context_id") or "") for item in ordered_contexts]
        context_hashes = [
            str(item.get("content_hash") or "") for item in ordered_contexts
        ]
        if any(not item for item in context_ids) or any(
            len(item) != 64 for item in context_hashes
        ):
            raise MarketContextWindowError(
                "REGIME_INPUT_NOT_READY: context identity or hash is incomplete"
            )
        if any(
            str(item.get("calculation_version")) != calculation_version
            for item in ordered_contexts
        ):
            raise MarketContextWindowError(
                "REGIME_INPUT_NOT_READY: context version incompatibility"
            )
        latest_available_at = max(
            item["available_at"] for item in ordered_contexts
        )
        source_payload = {
            "market": "CN",
            "as_of_trade_date": as_of_trade_date,
            "required_count": required_count,
            "ordered_trade_dates": ordered_dates,
            "ordered_context_ids": context_ids,
            "ordered_context_hashes": context_hashes,
            "context_version": calculation_version,
        }
        source_hash = production_data_hash(source_payload)
        manifest_id = str(
            uuid5(
                NAMESPACE_URL,
                (
                    "alphaguard:production-market-context-window:"
                    f"CN:{as_of_trade_date.isoformat()}:"
                    f"{calculation_version}:{required_count}"
                ),
            )
        )
        now = datetime.now()
        created_at = now.replace(
            microsecond=(now.microsecond // 1000) * 1000
        )
        business = {
            "manifest_id": manifest_id,
            "ref_id": manifest_id,
            **source_payload,
            "actual_count": len(ordered_contexts),
            "window_start": ordered_dates[0],
            "window_end": ordered_dates[-1],
            "source_hash": source_hash,
            "available_at": latest_available_at,
            "created_at": created_at,
        }
        business["manifest_hash"] = production_data_hash(
            business,
            exclude={"created_at"},
        )
        manifest = MarketContextWindowManifest.model_validate(business)

        existing_raw = await self.db[self.COLLECTION].find_one(
            {"manifest_id": manifest_id}
        )
        existing = clean_document(existing_raw)
        if existing is not None:
            stored = MarketContextWindowManifest.model_validate(existing)
            if (
                not self.verify_integrity(stored)
                or stored.manifest_hash != manifest.manifest_hash
            ):
                raise MarketContextWindowConflict(
                    "INTEGRITY_CONFLICT: immutable context window changed"
                )
            action = "REUSED"
            manifest = stored
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
    ) -> MarketContextWindowManifest:
        rows = await self.db[self.COLLECTION].find(
            {
                "market": "CN",
                "as_of_trade_date": _business_timestamp(as_of_trade_date),
                "available_at": {"$lte": cutoff_at},
                "created_at": {"$lte": cutoff_at},
            }
        ).limit(2).to_list(length=2)
        if len(rows) != 1:
            raise MarketContextWindowError(
                "REGIME_INPUT_NOT_READY: exact context window manifest is not unique"
            )
        manifest = MarketContextWindowManifest.model_validate(
            clean_document(rows[0])
        )
        if not self.verify_integrity(manifest):
            raise MarketContextWindowConflict(
                "INTEGRITY_CONFLICT: context manifest content hash mismatch"
            )
        expected_version = str(self.context_policy["calculation_version"])
        if manifest.context_version != expected_version:
            raise MarketContextWindowError(
                "REGIME_INPUT_NOT_READY: context window version is incompatible"
            )
        return manifest
