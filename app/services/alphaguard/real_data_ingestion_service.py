"""Versioned real-data ingestion into the existing AlphaGuard source collections."""

from __future__ import annotations

import asyncio
import hashlib
import json
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from typing import Any, Protocol


class RealDataProviderError(RuntimeError):
    pass


class RealDataIntegrityConflict(RuntimeError):
    pass


def _canonical(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, dict):
        return {
            str(key): _canonical(item)
            for key, item in sorted(value.items(), key=lambda pair: str(pair[0]))
            if key not in {"_id", "collected_at", "created_at", "updated_at"}
        }
    if isinstance(value, (list, tuple)):
        return [_canonical(item) for item in value]
    return value


def real_data_hash(value: Any) -> str:
    payload = json.dumps(
        _canonical(value),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class CalendarSourceRecord:
    session_date: date
    is_open: bool
    source_record_id: str


@dataclass(frozen=True)
class CalendarFetchResult:
    provider: str
    provider_version: str
    records: tuple[CalendarSourceRecord, ...]
    raw_response_hash: str


class CalendarProvider(Protocol):
    name: str

    def capability_check(self) -> dict[str, Any]: ...

    def fetch(self, start: date, end: date) -> CalendarFetchResult: ...


class AKShareCalendarProvider:
    name = "akshare"

    @staticmethod
    def capability_check() -> dict[str, Any]:
        try:
            import akshare as ak

            return {
                "provider": "akshare",
                "available": True,
                "provider_version": getattr(ak, "__version__", "unknown"),
                "capabilities": ["TRADING_CALENDAR"],
            }
        except Exception as exc:
            return {
                "provider": "akshare",
                "available": False,
                "provider_version": "unavailable",
                "error_type": type(exc).__name__,
            }

    @staticmethod
    def fetch(start: date, end: date) -> CalendarFetchResult:
        import akshare as ak

        frame = ak.tool_trade_date_hist_sina()
        if frame is None or frame.empty or "trade_date" not in frame.columns:
            raise RealDataProviderError("AKShare calendar response is empty or malformed")
        all_open_dates = sorted(
            {
                value.date() if hasattr(value, "date") else date.fromisoformat(str(value)[:10])
                for value in frame["trade_date"].tolist()
            }
        )
        if not all_open_dates:
            raise RealDataProviderError("AKShare returned no open dates")
        effective_end = min(end, all_open_dates[-1])
        if effective_end < start:
            raise RealDataProviderError("AKShare calendar does not cover requested range")
        open_dates = {
            item for item in all_open_dates if start <= item <= effective_end
        }
        records: list[CalendarSourceRecord] = []
        current = start
        while current <= effective_end:
            records.append(
                CalendarSourceRecord(
                    session_date=current,
                    is_open=current in open_dates,
                    source_record_id=f"CN:{current.isoformat()}",
                )
            )
            current += timedelta(days=1)
        return CalendarFetchResult(
            provider="akshare",
            provider_version=getattr(ak, "__version__", "unknown"),
            records=tuple(records),
            raw_response_hash=real_data_hash(
                {
                    "source": "tool_trade_date_hist_sina",
                    "open_dates": sorted(open_dates),
                }
            ),
        )


class BaoStockCalendarProvider:
    name = "baostock"

    @staticmethod
    def capability_check() -> dict[str, Any]:
        try:
            import baostock as bs

            return {
                "provider": "baostock",
                "available": True,
                "provider_version": getattr(bs, "__version__", "unknown"),
                "capabilities": ["TRADING_CALENDAR"],
            }
        except Exception as exc:
            return {
                "provider": "baostock",
                "available": False,
                "provider_version": "unavailable",
                "error_type": type(exc).__name__,
            }

    @staticmethod
    def fetch(start: date, end: date) -> CalendarFetchResult:
        import baostock as bs

        login = bs.login()
        if login.error_code != "0":
            raise RealDataProviderError("BaoStock login failed")
        rows: list[dict[str, str]] = []
        try:
            result = bs.query_trade_dates(
                start_date=start.isoformat(),
                end_date=end.isoformat(),
            )
            while result.error_code == "0" and result.next():
                rows.append(dict(zip(result.fields, result.get_row_data())))
            if result.error_code != "0":
                raise RealDataProviderError("BaoStock calendar query failed")
        finally:
            bs.logout()
        if not rows:
            raise RealDataProviderError("BaoStock returned no calendar records")
        records = tuple(
            CalendarSourceRecord(
                session_date=date.fromisoformat(row["calendar_date"]),
                is_open=str(row["is_trading_day"]).strip() == "1",
                source_record_id=f"CN:{row['calendar_date']}",
            )
            for row in rows
        )
        return CalendarFetchResult(
            provider="baostock",
            provider_version=getattr(bs, "__version__", "unknown"),
            records=records,
            raw_response_hash=real_data_hash(rows),
        )


class RealDataIngestionService:
    """Fail-closed ingestion with provider fallback and immutable row conflicts."""

    def __init__(self, db):
        self.db = db

    async def _fetch_calendar(
        self,
        providers: list[CalendarProvider],
        *,
        start: date,
        end: date,
        timeout_seconds: float,
        max_attempts: int,
    ) -> tuple[CalendarFetchResult, list[dict[str, str]]]:
        failures: list[dict[str, str]] = []
        for provider in providers:
            capability = provider.capability_check()
            if capability.get("available") is not True:
                failures.append(
                    {
                        "provider": provider.name,
                        "error_type": str(capability.get("error_type") or "UNAVAILABLE"),
                        "error_message": "provider capability check failed",
                    }
                )
                continue
            for attempt in range(1, max_attempts + 1):
                try:
                    result = await asyncio.wait_for(
                        asyncio.to_thread(provider.fetch, start, end),
                        timeout=timeout_seconds,
                    )
                    return result, failures
                except Exception as exc:
                    failures.append(
                        {
                            "provider": provider.name,
                            "error_type": type(exc).__name__,
                            "error_message": str(exc)[:300],
                            "attempt": str(attempt),
                        }
                    )
                    if attempt < max_attempts:
                        await asyncio.sleep(min(attempt, 2))
        raise RealDataProviderError(
            "all configured calendar providers failed: "
            + ", ".join(
                f"{item['provider']}:{item['error_type']}" for item in failures
            )
        )

    async def sync_calendar(
        self,
        *,
        start: date,
        end: date,
        execute: bool,
        providers: list[CalendarProvider] | None = None,
        timeout_seconds: float = 30,
        max_attempts: int = 3,
        collected_at: datetime | None = None,
    ) -> dict[str, Any]:
        if end < start:
            raise ValueError("calendar end date precedes start date")
        providers = providers or [
            AKShareCalendarProvider(),
            BaoStockCalendarProvider(),
        ]
        started_at = datetime.utcnow()
        result, provider_failures = await self._fetch_calendar(
            providers,
            start=start,
            end=end,
            timeout_seconds=timeout_seconds,
            max_attempts=max_attempts,
        )
        collected_at = collected_at or datetime.utcnow()
        documents = []
        for source in result.records:
            session_timestamp = datetime.combine(source.session_date, time.min)
            business = {
                "calendar_id": f"CN:{source.session_date.isoformat()}",
                "ref_id": f"CN:{source.session_date.isoformat()}",
                "source_record_id": source.source_record_id,
                "market": "CN",
                "symbol": None,
                "business_date": session_timestamp,
                "session_date": session_timestamp,
                "calendar_date": session_timestamp,
                "is_open": source.is_open,
                "is_trading_day": source.is_open,
                "provider": result.provider,
                "provider_version": result.provider_version,
                "normalization_version": "alphaguard-calendar-normalization-v1",
            }
            content_hash = real_data_hash(business)
            documents.append(
                {
                    **business,
                    "data_version": (
                        f"calendar:{result.provider}:{result.provider_version}:"
                        f"{content_hash[:16]}"
                    ),
                    "available_at": collected_at,
                    "collected_at": collected_at,
                    "as_of": collected_at,
                    "created_at": collected_at,
                    "content_hash": content_hash,
                    "source_response_hash": result.raw_response_hash,
                    "schema_version": "alphaguard-real-calendar-v1",
                }
            )

        manifest_hash = real_data_hash(
            {
                "provider": result.provider,
                "provider_version": result.provider_version,
                "start": start,
                "end": end,
                "records": [
                    {
                        "session_date": item.session_date,
                        "is_open": item.is_open,
                    }
                    for item in result.records
                ],
            }
        )
        summary = {
            "domain": "TRADING_CALENDAR",
            "provider": result.provider,
            "provider_version": result.provider_version,
            "data_version": f"calendar-manifest:{manifest_hash}",
            "start_date": result.records[0].session_date,
            "end_date": result.records[-1].session_date,
            "record_count": len(documents),
            "open_count": sum(bool(item["is_open"]) for item in documents),
            "closed_count": sum(not bool(item["is_open"]) for item in documents),
            "created": 0,
            "reused": 0,
            "conflicts": 0,
            "write": execute,
            "provider_failures": provider_failures,
        }
        if not execute:
            return summary

        collection = self.db["trading_calendar"]
        existing_rows = await collection.find(
            {
                "market": "CN",
                "session_date": {
                    "$gte": datetime.combine(result.records[0].session_date, time.min),
                    "$lte": datetime.combine(result.records[-1].session_date, time.min),
                },
            }
        ).to_list(length=None)
        existing_by_id = {
            str(item.get("calendar_id") or item.get("ref_id")): item
            for item in existing_rows
        }
        for document in documents:
            existing = existing_by_id.get(document["calendar_id"])
            if existing is None:
                continue
            if existing.get("content_hash") != document["content_hash"]:
                summary["conflicts"] += 1
        if summary["conflicts"]:
            await self._record_sync_status(
                summary,
                status="failed",
                started_at=started_at,
                completed_at=datetime.utcnow(),
                error_type="INTEGRITY_CONFLICT",
                error_message="calendar identity exists with different content",
            )
            raise RealDataIntegrityConflict(
                f"{summary['conflicts']} calendar rows conflict with immutable content"
            )

        await collection.create_index(
            [("calendar_id", 1)],
            name="uniq_real_calendar_id",
            unique=True,
        )
        await collection.create_index(
            [("market", 1), ("session_date", 1)],
            name="uniq_real_calendar_market_session",
            unique=True,
        )
        for document in documents:
            if document["calendar_id"] in existing_by_id:
                summary["reused"] += 1
                continue
            await collection.insert_one(document)
            summary["created"] += 1
        await self._record_sync_status(
            summary,
            status="completed",
            started_at=started_at,
            completed_at=datetime.utcnow(),
        )
        return summary

    async def _record_sync_status(
        self,
        summary: dict[str, Any],
        *,
        status: str,
        started_at: datetime,
        completed_at: datetime,
        error_type: str | None = None,
        error_message: str | None = None,
    ) -> None:
        identity = {
            "job": "alphaguard_real_data:TRADING_CALENDAR:CN",
            "data_type": "TRADING_CALENDAR",
        }
        await self.db["sync_status"].update_one(
            identity,
            {
                "$set": {
                    **identity,
                    "status": status,
                    "provider": summary["provider"],
                    "provider_version": summary["provider_version"],
                    "data_version": summary["data_version"],
                    "record_count": summary["record_count"],
                    "start_date": datetime.combine(summary["start_date"], time.min),
                    "end_date": datetime.combine(summary["end_date"], time.min),
                    "started_at": started_at,
                    "completed_at": completed_at,
                    "updated_at": completed_at,
                    "error_type": error_type,
                    "error_message": error_message,
                    "schema_version": "alphaguard-real-data-sync-v1",
                }
            },
            upsert=True,
        )
