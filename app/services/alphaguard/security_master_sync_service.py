"""Targeted, audited CN security-master completion for production inputs.

The service enriches the existing ``stock_basic_info`` repository; it does not
create a second production instrument registry.  Raw provider facts are kept
in an append-only audit collection so a later trading-status record can cite
the exact listing-date observation it used.
"""

from __future__ import annotations

import asyncio
import socket
from datetime import date, datetime
from typing import Any, Protocol
from uuid import NAMESPACE_URL, uuid5

from app.services.alphaguard.paper_storage import clean_document, model_document
from tradingagents.alphaguard.instruments import normalize_instrument
from tradingagents.alphaguard.production_data_schemas import (
    SecurityMasterSourceRecord,
    production_data_hash,
)


class SecurityMasterSyncError(RuntimeError):
    pass


class SecurityMasterIntegrityConflict(SecurityMasterSyncError):
    pass


class SecurityMasterProvider(Protocol):
    name: str
    version: str

    def capability_check(self) -> dict[str, Any]: ...

    def fetch(self, symbols: list[str]) -> dict[str, dict[str, str]]: ...


def _as_date(value: Any) -> date | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        return date.fromisoformat(text[:10])
    except ValueError:
        return None


class BaoStockSecurityMasterProvider:
    name = "baostock"

    def __init__(
        self,
        *,
        timeout_seconds: float = 20,
        retry_attempts: int = 3,
    ):
        self.timeout_seconds = timeout_seconds
        self.retry_attempts = retry_attempts
        try:
            import baostock as bs

            self._bs = bs
            self.version = str(getattr(bs, "__version__", "unknown"))
        except Exception:
            self._bs = None
            self.version = "unavailable"

    def capability_check(self) -> dict[str, Any]:
        return {
            "provider": self.name,
            "provider_version": self.version,
            "available": self._bs is not None and self.version != "unavailable",
            "endpoint": "query_stock_basic",
        }

    @staticmethod
    def _provider_code(symbol: str) -> str:
        if symbol.startswith(("5", "6", "9")):
            return f"sh.{symbol}"
        if symbol.startswith(("0", "1", "2", "3")):
            return f"sz.{symbol}"
        if symbol.startswith(("4", "8")):
            return f"bj.{symbol}"
        raise SecurityMasterSyncError(f"unsupported CN security code: {symbol}")

    def fetch(self, symbols: list[str]) -> dict[str, dict[str, str]]:
        if self._bs is None:
            raise SecurityMasterSyncError("BaoStock package is unavailable")
        previous_timeout = socket.getdefaulttimeout()
        socket.setdefaulttimeout(self.timeout_seconds)
        try:
            last_error: Exception | None = None
            for _attempt in range(1, self.retry_attempts + 1):
                logged_in = False
                try:
                    login = self._bs.login()
                    if login.error_code != "0":
                        raise SecurityMasterSyncError(
                            f"BaoStock login failed: {login.error_code}"
                        )
                    logged_in = True
                    result: dict[str, dict[str, str]] = {}
                    for symbol in symbols:
                        provider_code = self._provider_code(symbol)
                        response = self._bs.query_stock_basic(code=provider_code)
                        if response.error_code != "0":
                            raise SecurityMasterSyncError(
                                f"BaoStock query_stock_basic failed for {symbol}: "
                                f"{response.error_code}"
                            )
                        rows = []
                        while response.error_code == "0" and response.next():
                            rows.append(response.get_row_data())
                        if len(rows) != 1:
                            raise SecurityMasterSyncError(
                                f"BaoStock returned {len(rows)} identities for {symbol}"
                            )
                        row = rows[0]
                        if len(row) < 6:
                            raise SecurityMasterSyncError(
                                f"BaoStock identity row is incomplete for {symbol}"
                            )
                        result[symbol] = {
                            "code": str(row[0]),
                            "code_name": str(row[1]),
                            "ipoDate": str(row[2]),
                            "outDate": str(row[3]),
                            "type": str(row[4]),
                            "status": str(row[5]),
                        }
                    return result
                except Exception as exc:
                    last_error = exc
                finally:
                    if logged_in:
                        try:
                            self._bs.logout()
                        except Exception:
                            pass
            raise SecurityMasterSyncError(
                f"BaoStock security-master fetch failed after "
                f"{self.retry_attempts} attempts: {type(last_error).__name__}"
            ) from last_error
        finally:
            socket.setdefaulttimeout(previous_timeout)


class SecurityMasterSyncService:
    SOURCE_COLLECTION = "ag_security_master_sources"
    TARGET_COLLECTION = "stock_basic_info"
    NORMALIZATION_VERSION = "security-master-normalization-v1.1"

    def __init__(self, db):
        self.db = db

    async def sync(
        self,
        *,
        symbols: list[str],
        execute: bool,
        provider: SecurityMasterProvider | None = None,
        collected_at: datetime | None = None,
    ) -> dict[str, Any]:
        collected_at = collected_at or datetime.utcnow()
        # MongoDB stores datetimes with millisecond precision.  Canonical hashes
        # must use that same precision or a read-after-write would appear to
        # change otherwise identical content.
        collected_at = collected_at.replace(
            microsecond=(collected_at.microsecond // 1000) * 1000
        )
        normalized = []
        for raw_symbol in sorted(set(symbols)):
            market, symbol = normalize_instrument(raw_symbol, "CN")
            if market != "CN":
                raise SecurityMasterSyncError("security-master sync supports CN only")
            normalized.append(symbol)
        provider = provider or BaoStockSecurityMasterProvider()
        capability = provider.capability_check()
        if capability.get("available") is not True:
            raise SecurityMasterSyncError("security-master provider is unavailable")
        raw_records = await asyncio.to_thread(provider.fetch, normalized)
        results = []
        for symbol in normalized:
            raw = raw_records.get(symbol)
            if raw is None:
                raise SecurityMasterSyncError(
                    f"security-master provider omitted {symbol}"
                )
            expected_code = BaoStockSecurityMasterProvider._provider_code(symbol)
            if str(raw.get("code")) != expected_code:
                raise SecurityMasterIntegrityConflict(
                    f"provider identity mismatch for {symbol}"
                )
            listing_date = _as_date(raw.get("ipoDate"))
            name = str(raw.get("code_name") or "").strip()
            if listing_date is None or not name:
                raise SecurityMasterSyncError(
                    f"provider lacks listing identity for {symbol}"
                )
            if str(raw.get("type")) != "1":
                raise SecurityMasterSyncError(
                    f"provider does not classify {symbol} as an equity"
                )
            source_record_id = f"baostock:query_stock_basic:{expected_code}"
            raw_hash = production_data_hash(raw)
            data_version = (
                f"{provider.name}:{provider.version}:query_stock_basic:"
                f"{self.NORMALIZATION_VERSION}:{raw_hash}"
            )
            existing_sources = [
                clean_document(item)
                for item in await self.db[self.SOURCE_COLLECTION]
                .find(
                    {
                        "symbol": symbol,
                        "market": "CN",
                        "provider": provider.name,
                        "data_version": data_version,
                    }
                )
                .to_list(length=None)
            ]
            if len(existing_sources) > 1:
                raise SecurityMasterIntegrityConflict(
                    f"duplicate security-master source identity for {symbol}"
                )
            first_observed_at = (
                existing_sources[0].get("available_at")
                if existing_sources
                else collected_at
            )
            source_collected_at = (
                existing_sources[0].get("collected_at")
                if existing_sources
                else collected_at
            )
            business = {
                "source_record_id": source_record_id,
                "symbol": symbol,
                "market": "CN",
                "provider": provider.name,
                "provider_version": provider.version,
                "provider_endpoint": "query_stock_basic",
                "normalization_version": self.NORMALIZATION_VERSION,
                "raw_fields": raw,
                "name": name,
                "listing_date": listing_date,
                "security_type": str(raw["type"]),
                "listing_status": str(raw["status"]),
                "available_at": first_observed_at,
                "data_version": data_version,
            }
            business["content_hash"] = production_data_hash(business)
            source = SecurityMasterSourceRecord(
                source_id=str(
                    uuid5(
                        NAMESPACE_URL,
                        f"alphaguard:security-master:{symbol}:"
                        f"{provider.name}:{data_version}",
                    )
                ),
                collected_at=source_collected_at,
                **business,
            )
            if (
                existing_sources
                and str(existing_sources[0].get("content_hash"))
                != source.content_hash
            ):
                raise SecurityMasterIntegrityConflict(
                    f"same security-master version changed for {symbol}: "
                    f"stored={existing_sources[0].get('content_hash')} "
                    f"computed={source.content_hash}"
                )
            existing_target = clean_document(
                await self.db[self.TARGET_COLLECTION].find_one(
                    {"code": symbol, "source": provider.name}
                )
            )
            if existing_target is None:
                existing_target = clean_document(
                    await self.db[self.TARGET_COLLECTION].find_one(
                        {"symbol": symbol, "source": provider.name}
                    )
                )
            if existing_target:
                current_listing = _as_date(
                    existing_target.get("list_date")
                    or existing_target.get("listing_date")
                )
                current_name = str(existing_target.get("name") or "").strip()
                if current_listing is not None and current_listing != listing_date:
                    raise SecurityMasterIntegrityConflict(
                        f"existing listing date conflicts for {symbol}"
                    )
                if current_name and current_name != name:
                    raise SecurityMasterIntegrityConflict(
                        f"existing security name conflicts for {symbol}"
                    )
            source_action = "REUSED" if existing_sources else "WOULD_CREATE"
            target_action = (
                "UNCHANGED"
                if existing_target
                and _as_date(existing_target.get("list_date")) == listing_date
                and str(existing_target.get("security_master_data_version") or "")
                == data_version
                else "WOULD_UPSERT"
            )
            if execute:
                if not existing_sources:
                    await self.db[self.SOURCE_COLLECTION].insert_one(
                        model_document(source)
                    )
                    source_action = "CREATED"
                target_payload = {
                    "code": symbol,
                    "symbol": symbol,
                    "name": name,
                    "list_date": listing_date.isoformat(),
                    "source": provider.name,
                    "market": "CN",
                    "provider": provider.name,
                    "provider_version": provider.version,
                    "source_record_id": source_record_id,
                    "security_master_source_ref": (
                        f"{self.SOURCE_COLLECTION}:{source.source_id}"
                    ),
                    "security_master_data_version": data_version,
                    "security_master_content_hash": source.content_hash,
                    "available_at": source.available_at,
                    "collected_at": source.collected_at,
                    "updated_at": collected_at,
                }
                if target_action != "UNCHANGED":
                    await self.db[self.TARGET_COLLECTION].update_one(
                        {"code": symbol, "source": provider.name},
                        {"$set": target_payload},
                        upsert=True,
                    )
                    target_action = "UPSERTED"
                event_id = str(
                    uuid5(
                        NAMESPACE_URL,
                        f"security-master-source:{source.source_id}",
                    )
                )
                await self.db["ag_production_data_events"].update_one(
                    {"event_id": event_id},
                    {
                        "$setOnInsert": {
                            "event_id": event_id,
                            "event_type": "SECURITY_MASTER_SOURCE_SYNCED",
                            "market": "CN",
                            "symbol": symbol,
                            "source_id": source.source_id,
                            "input_hash": raw_hash,
                            "result_hash": source.content_hash,
                            "created_at": collected_at,
                            "schema_version": (
                                "alphaguard-production-data-event-v1"
                            ),
                        }
                    },
                    upsert=True,
                )
            results.append(
                {
                    "symbol": symbol,
                    "name": name,
                    "listing_date": listing_date,
                    "listing_status": str(raw["status"]),
                    "provider": provider.name,
                    "provider_version": provider.version,
                    "source_record_id": source_record_id,
                    "data_version": data_version,
                    "content_hash": source.content_hash,
                    "source_action": source_action,
                    "target_action": target_action,
                }
            )
        return {
            "market": "CN",
            "write": execute,
            "provider": provider.name,
            "provider_version": provider.version,
            "results": results,
        }
