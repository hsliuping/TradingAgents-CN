"""Create-only execution OHLCV snapshots for deterministic daily matching."""

from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Any
from uuid import NAMESPACE_URL, uuid5

from app.services.alphaguard.paper_audit_service import PaperAuditService
from app.services.alphaguard.paper_storage import (
    clean_document,
    model_document,
    mongo_date,
)
from tradingagents.alphaguard.instruments import normalize_instrument
from tradingagents.alphaguard.paper_schemas import (
    ExecutionMarketSnapshot,
    PAPER_SCHEMA_VERSION,
    paper_canonical_hash,
)


class ExecutionSnapshotError(ValueError):
    pass


class ExecutionSnapshotConflictError(ValueError):
    pass


def _comparable_timestamp(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value
    return value.astimezone(timezone.utc).replace(tzinfo=None)


def _required_decimal(document: dict[str, Any], field: str) -> Decimal:
    value = document.get(field)
    if value is None:
        raise ExecutionSnapshotError(f"execution daily data lacks {field}")
    try:
        result = Decimal(str(value))
    except Exception as exc:
        raise ExecutionSnapshotError(f"invalid execution {field}") from exc
    if result <= 0:
        raise ExecutionSnapshotError(f"execution {field} must be positive")
    return result


def _required_bool(document: dict[str, Any], *fields: str) -> bool:
    for field in fields:
        if field not in document:
            continue
        value = document[field]
        # Existing CN daily records use tradestatus=1 for trading and 0 for
        # suspended. Interpret that source field before generic booleans.
        if field == "tradestatus":
            normalized = str(value).strip().upper()
            if normalized in {"0", "FALSE", "N", "NO", "SUSPENDED", "停牌"}:
                return True
            if normalized in {"1", "TRUE", "Y", "YES", "NORMAL", "交易"}:
                return False
            raise ExecutionSnapshotError("execution tradestatus is not recognized")
        if isinstance(value, str):
            normalized = value.strip().upper()
            if normalized in {"1", "TRUE", "Y", "YES", "ST", "SUSPENDED", "停牌"}:
                return True
            if normalized in {"0", "FALSE", "N", "NO", "NORMAL", "交易"}:
                return False
        return bool(value)
    raise ExecutionSnapshotError(
        f"execution daily data lacks explicit {'/'.join(fields)}"
    )


class ExecutionMarketSnapshotService:
    def __init__(self, db):
        self.db = db
        self.collection = db["ag_execution_market_snapshots"]
        self.audit = PaperAuditService(db)

    async def build_for_trade_date(
        self,
        *,
        symbol: str,
        trade_date: date,
        cutoff_at: datetime,
        data_version: str,
    ) -> ExecutionMarketSnapshot:
        market, symbol = normalize_instrument(symbol, "CN")
        source_document = await self.db["stock_daily_quotes"].find_one(
            {
                "$or": [{"symbol": symbol}, {"code": symbol}],
                "trade_date": {
                    "$in": [mongo_date(trade_date), trade_date.isoformat()]
                },
                "period": "daily",
            },
            sort=[("updated_at", -1)],
        )
        source_ref = (
            str(source_document.get("_id"))
            if source_document and source_document.get("_id") is not None
            else None
        )
        raw = clean_document(source_document)
        if raw is None:
            raise ExecutionSnapshotError(
                "exact-date stock_daily_quotes record does not exist"
            )
        return await self.create_from_daily_record(
            record=raw,
            symbol=symbol,
            trade_date=trade_date,
            cutoff_at=cutoff_at,
            data_version=data_version,
            source_ref=source_ref,
        )

    async def create_from_daily_record(
        self,
        *,
        record: dict[str, Any],
        symbol: str,
        trade_date: date,
        cutoff_at: datetime,
        data_version: str,
        source_ref: str | None = None,
        now: datetime | None = None,
    ) -> ExecutionMarketSnapshot:
        market, symbol = normalize_instrument(symbol, "CN")
        record_market, record_symbol = normalize_instrument(
            record.get("symbol") or record.get("code"),
            record.get("market") or "CN",
        )
        raw_date = str(record.get("trade_date") or "")[:10]
        if record_market != market or record_symbol != symbol:
            raise ExecutionSnapshotError("execution record symbol/market mismatch")
        if raw_date != trade_date.isoformat():
            raise ExecutionSnapshotError("execution record trade_date mismatch")
        if trade_date > cutoff_at.date():
            raise ExecutionSnapshotError("future daily data cannot create a snapshot")
        if cutoff_at.date() == trade_date and cutoff_at.time() < datetime.strptime(
            "15:00", "%H:%M"
        ).time():
            raise ExecutionSnapshotError(
                "DAILY_OHLCV execution snapshot requires an after-close cutoff"
            )
        observed = record.get("updated_at") or record.get("as_of")
        if observed is not None:
            try:
                observed_at = (
                    observed
                    if isinstance(observed, datetime)
                    else datetime.fromisoformat(str(observed).replace("Z", "+00:00"))
                )
                comparable_observed = _comparable_timestamp(observed_at)
                comparable_cutoff = _comparable_timestamp(cutoff_at)
                if comparable_observed > comparable_cutoff:
                    raise ExecutionSnapshotError(
                        "daily record was updated after the execution cutoff"
                    )
            except ValueError as exc:
                raise ExecutionSnapshotError(
                    "daily record updated_at is invalid"
                ) from exc
        source_ref = source_ref or str(
            record.get("_reference")
            or record.get("ref_id")
            or record.get("_id")
            or ""
        )
        if not source_ref:
            raise ExecutionSnapshotError("execution record lacks a source reference")
        open_price = _required_decimal(record, "open")
        high = _required_decimal(record, "high")
        low = _required_decimal(record, "low")
        close = _required_decimal(record, "close")
        limit_up = _required_decimal(record, "limit_up_price")
        limit_down = _required_decimal(record, "limit_down_price")
        suspended = _required_bool(record, "suspended", "tradestatus")
        st_status = _required_bool(record, "st_status", "isST", "is_st")
        volume_raw = record.get("volume")
        if volume_raw is None:
            raise ExecutionSnapshotError("execution daily data lacks volume")
        volume = int(Decimal(str(volume_raw)))
        if volume < 0:
            raise ExecutionSnapshotError("execution volume cannot be negative")
        payload = {
            "execution_snapshot_id": str(
                uuid5(
                    NAMESPACE_URL,
                    f"alphaguard:execution-snapshot:{symbol}:CN:{trade_date}:{data_version}",
                )
            ),
            "symbol": symbol,
            "market": "CN",
            "trade_date": trade_date,
            "open": open_price,
            "high": high,
            "low": low,
            "close": close,
            "prev_close": (
                Decimal(str(record.get("pre_close") or record.get("prev_close")))
                if (record.get("pre_close") or record.get("prev_close")) is not None
                else None
            ),
            "volume": volume,
            "amount": (
                Decimal(str(record["amount"]))
                if record.get("amount") is not None
                else None
            ),
            "suspended": suspended,
            "st_status": st_status,
            "limit_up_price": limit_up,
            "limit_down_price": limit_down,
            "source_refs": [source_ref],
            "data_version": data_version,
            "cutoff_at": cutoff_at,
            "simulation_granularity": "DAILY_OHLCV",
            "matched_after_market_close": True,
            "created_at": now or datetime.utcnow(),
            "schema_version": PAPER_SCHEMA_VERSION,
            "execution_environment": "PAPER",
            "live_execution_allowed": False,
        }
        payload["immutable_hash"] = paper_canonical_hash(
            payload,
            exclude={"execution_snapshot_id", "immutable_hash", "created_at"},
        )
        snapshot = ExecutionMarketSnapshot.model_validate(payload)
        identity = {
            "symbol": symbol,
            "market": "CN",
            "trade_date": mongo_date(trade_date),
            "data_version": data_version,
        }
        existing = clean_document(await self.collection.find_one(identity))
        if existing:
            stored = ExecutionMarketSnapshot.model_validate(existing)
            if stored.immutable_hash != snapshot.immutable_hash:
                await self.audit.record(
                    "EXECUTION_SNAPSHOT_INVALID",
                    "same execution snapshot identity has different content",
                    symbol=symbol,
                    trade_date=trade_date,
                )
                raise ExecutionSnapshotConflictError(
                    "same execution snapshot identity has different content"
                )
            return stored
        await self.collection.insert_one(model_document(snapshot))
        await self.audit.record(
            "EXECUTION_SNAPSHOT_CREATED",
            "immutable exact-date DAILY_OHLCV execution snapshot created",
            symbol=symbol,
            trade_date=trade_date,
        )
        return snapshot
