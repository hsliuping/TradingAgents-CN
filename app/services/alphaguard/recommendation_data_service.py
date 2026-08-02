"""Versioned, local-first data preparation for full-market recommendations."""

from __future__ import annotations

import asyncio
import time
from collections import Counter
from dataclasses import dataclass
from datetime import date, datetime, time as datetime_time
from decimal import Decimal
from functools import lru_cache
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Protocol
from uuid import NAMESPACE_URL, uuid5

import yaml
from pymongo import InsertOne
from pymongo.errors import BulkWriteError

from app.services.alphaguard.cn_trading_status_service import (
    TradingStatusConflict,
    derive_security_trading_status,
)
from app.services.alphaguard.factor_engine import (
    calculate_factor_value,
    normalize_factor_value,
)
from app.services.alphaguard.factor_registry import builtin_factor_definitions
from app.services.alphaguard.paper_storage import (
    clean_document,
    model_document,
    to_mongo_value,
)
from app.services.alphaguard.production_data_config import cn_price_limit_policy
from app.services.alphaguard.real_data_ingestion_service import real_data_hash
from tradingagents.alphaguard.production_data_schemas import production_data_hash
from tradingagents.alphaguard.recommendation_schemas import (
    CandidateRecommendationPolicy,
    CandidateUniverseManifest,
    RecommendationDataCoverage,
    RecommendationDataQualityReport,
    RecommendationFactorEvidence,
    recommendation_hash,
)


ROOT = Path(__file__).resolve().parents[3]
CONTRACT_PATH = (
    ROOT
    / "config"
    / "alphaguard"
    / "recommendations"
    / "recommendation_data_contract_v1.yaml"
)
PRICE_FIELDS = (
    "date,code,open,high,low,close,preclose,volume,amount,adjustflag,"
    "turn,tradestatus,pctChg,isST,peTTM,pbMRQ,psTTM,pcfNcfTTM"
)
FACTOR_IDS = {
    "close_vs_ma20_v1",
    "close_vs_ma60_v1",
    "ma20_vs_ma60_v1",
    "ma20_slope_5d_v1",
    "momentum_20d_v1",
    "momentum_60d_v1",
    "relative_strength_hs300_20d_v1",
    "volume_confirmation_20d_v1",
    "atr14_pct_v1",
    "volatility20_annualized_v1",
    "average_amount20_v1",
    "turnover20_v1",
    "short_term_excess_return5_v1",
}
RECOMMENDATION_STATUS_DERIVATION_VERSION = "recommendation-status-bson-ms-v1"


class RecommendationDataError(RuntimeError):
    pass


class RecommendationDataIntegrityConflict(RecommendationDataError):
    pass


def _stable_id(namespace: str, identity: str) -> str:
    return str(uuid5(NAMESPACE_URL, f"alphaguard:{namespace}:{identity}"))


def _as_date(value: Any) -> date | None:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    text = str(value or "").strip()
    if not text:
        return None
    if len(text) == 8 and text.isdigit():
        text = f"{text[:4]}-{text[4:6]}-{text[6:]}"
    try:
        return date.fromisoformat(text[:10])
    except ValueError:
        return None


def _business_timestamp(value: date, *, hour: int = 0) -> datetime:
    return datetime.combine(value, datetime_time(hour=hour))


def _number(value: Any) -> float | None:
    if value in (None, "", "None", "nan", "--"):
        return None
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return result


def _integer(value: Any) -> int | None:
    result = _number(value)
    return int(result) if result is not None else None


@lru_cache(maxsize=1)
def recommendation_data_contract() -> dict[str, Any]:
    with CONTRACT_PATH.open("r", encoding="utf-8") as handle:
        value = yaml.safe_load(handle)
    if not isinstance(value, dict):
        raise ValueError("recommendation data contract must be a mapping")
    required = {
        "contract_id",
        "contract_version",
        "normalization_version",
        "market",
        "benchmark_symbol",
        "price_adjustment_mode",
        "required_history_days",
        "sync_history_sessions",
        "coverage_threshold",
        "batch_size",
        "max_attempts",
        "industry_required",
    }
    missing = sorted(required - set(value))
    if missing:
        raise ValueError(f"recommendation data contract lacks {missing}")
    result = dict(value)
    result["contract_hash"] = recommendation_hash(value)
    return result


@dataclass(frozen=True)
class ProviderMaster:
    provider: str
    provider_version: str
    rows: tuple[dict[str, Any], ...]


@dataclass(frozen=True)
class ProviderPriceBatch:
    provider: str
    provider_version: str
    rows_by_symbol: dict[str, tuple[dict[str, Any], ...]]
    failures: tuple[dict[str, str], ...]
    retry_count: int


class RecommendationMarketDataProvider(Protocol):
    name: str

    def fetch_master(self) -> ProviderMaster: ...

    def fetch_prices(
        self,
        provider_codes: dict[str, str],
        *,
        start: date,
        end: date,
        max_attempts: int,
    ) -> ProviderPriceBatch: ...

    def fetch_benchmark(self, *, start: date, end: date) -> ProviderPriceBatch: ...


class BaoStockRecommendationProvider:
    """One-login batch adapter for SH/SZ history and security master facts."""

    name = "baostock"

    @staticmethod
    def _query(result: Any) -> list[dict[str, str]]:
        rows: list[dict[str, str]] = []
        while result.error_code == "0" and result.next():
            rows.append(dict(zip(result.fields, result.get_row_data())))
        if result.error_code != "0":
            raise RecommendationDataError(
                f"BAOSTOCK_PROVIDER_ERROR:{result.error_code}"
            )
        return rows

    def fetch_master(self) -> ProviderMaster:
        import baostock as bs

        login = bs.login()
        if login.error_code != "0":
            raise RecommendationDataError("BAOSTOCK_LOGIN_FAILED")
        try:
            rows = self._query(bs.query_stock_basic())
        finally:
            bs.logout()
        version = str(getattr(bs, "__version__", "unknown"))
        return ProviderMaster(
            provider=self.name,
            provider_version=version,
            rows=tuple(row for row in rows if row.get("type") == "1"),
        )

    def fetch_prices(
        self,
        provider_codes: dict[str, str],
        *,
        start: date,
        end: date,
        max_attempts: int,
    ) -> ProviderPriceBatch:
        import baostock as bs

        login = bs.login()
        if login.error_code != "0":
            raise RecommendationDataError("BAOSTOCK_LOGIN_FAILED")
        values: dict[str, tuple[dict[str, Any], ...]] = {}
        failures: list[dict[str, str]] = []
        retries = 0
        try:
            for symbol, provider_code in sorted(provider_codes.items()):
                last_error = "PROVIDER_ERROR"
                for attempt in range(1, max_attempts + 1):
                    try:
                        raw = self._query(
                            bs.query_history_k_data_plus(
                                provider_code,
                                PRICE_FIELDS,
                                start_date=start.isoformat(),
                                end_date=end.isoformat(),
                                frequency="d",
                                adjustflag="3",
                            )
                        )
                        qfq = self._query(
                            bs.query_history_k_data_plus(
                                provider_code,
                                PRICE_FIELDS,
                                start_date=start.isoformat(),
                                end_date=end.isoformat(),
                                frequency="d",
                                adjustflag="2",
                            )
                        )
                        values[symbol] = tuple(
                            _combine_provider_prices(
                                symbol=symbol,
                                provider_code=provider_code,
                                raw_rows=raw,
                                qfq_rows=qfq,
                                provider=self.name,
                                provider_version=str(
                                    getattr(bs, "__version__", "unknown")
                                ),
                                normalization_version=str(
                                    recommendation_data_contract()[
                                        "normalization_version"
                                    ]
                                ),
                            )
                        )
                        break
                    except Exception as exc:
                        last_error = type(exc).__name__
                        if attempt < max_attempts:
                            retries += 1
                            time.sleep(min(0.25 * attempt, 1.0))
                else:
                    failures.append(
                        {"symbol": symbol, "error_code": last_error}
                    )
        finally:
            bs.logout()
        return ProviderPriceBatch(
            provider=self.name,
            provider_version=str(getattr(bs, "__version__", "unknown")),
            rows_by_symbol=values,
            failures=tuple(failures),
            retry_count=retries,
        )

    def fetch_benchmark(self, *, start: date, end: date) -> ProviderPriceBatch:
        return self.fetch_prices(
            {"000300": "sh.000300"},
            start=start,
            end=end,
            max_attempts=3,
        )


def _combine_provider_prices(
    *,
    symbol: str,
    provider_code: str,
    raw_rows: list[dict[str, Any]],
    qfq_rows: list[dict[str, Any]],
    provider: str,
    provider_version: str,
    normalization_version: str,
) -> list[dict[str, Any]]:
    raw_by_date = {str(row.get("date")): row for row in raw_rows if row.get("date")}
    qfq_by_date = {str(row.get("date")): row for row in qfq_rows if row.get("date")}
    is_index = symbol == "000300"
    qfq_mode = "INDEX_UNADJUSTED_EQUIVALENT" if is_index else "QFQ"
    qfq_version = (
        f"{provider}:{provider_version}:INDEX_RAW:{normalization_version}"
        if is_index
        else f"{provider}:{provider_version}:QFQ:{normalization_version}"
    )
    raw_version = (
        qfq_version
        if is_index
        else f"{provider}:{provider_version}:RAW:{normalization_version}"
    )
    documents: list[dict[str, Any]] = []
    for value in sorted(set(raw_by_date) & set(qfq_by_date)):
        raw = raw_by_date[value]
        qfq = qfq_by_date[value]
        trade_date = date.fromisoformat(value)
        version_identity = recommendation_hash(
            {
                "provider": provider,
                "provider_version": provider_version,
                "normalization_version": normalization_version,
                "adjustment_mode": qfq_mode,
            }
        )[:16]
        ref_id = (
            f"recommendation-index-000300-{value}-{version_identity}"
            if is_index
            else f"recommendation-price-{symbol}-{value}-{version_identity}"
        )
        source_record_id = f"{provider_code}:{value}:daily"
        business = {
            "ref_id": ref_id,
            "source_record_id": source_record_id,
            "symbol": symbol,
            "code": symbol,
            "market": "CN",
            "business_date": _business_timestamp(trade_date),
            "trade_date": _business_timestamp(trade_date),
            "timestamp": _business_timestamp(trade_date, hour=15),
            "period": "daily",
            "bar_granularity": "PROVIDER_DAILY",
            "bar_completion_status": "COMPLETED",
            "open": _number(raw.get("open")),
            "high": _number(raw.get("high")),
            "low": _number(raw.get("low")),
            "close": _number(raw.get("close")),
            "adjusted_open": _number(qfq.get("open")),
            "adjusted_high": _number(qfq.get("high")),
            "adjusted_low": _number(qfq.get("low")),
            "adjusted_close": _number(qfq.get("close")),
            "prev_close": _number(raw.get("preclose")),
            "volume": _integer(raw.get("volume")),
            "volume_shares": _integer(raw.get("volume")),
            "amount": _number(raw.get("amount")),
            "amount_cny": _number(raw.get("amount")),
            "turnover_rate": _number(raw.get("turn")),
            "pct_change": _number(raw.get("pctChg")),
            "pe_ttm": _number(raw.get("peTTM")),
            "pb": _number(raw.get("pbMRQ")),
            "ps_ttm": _number(raw.get("psTTM")),
            "pcf_ttm": _number(raw.get("pcfNcfTTM")),
            "suspended": (
                str(raw.get("tradestatus")).strip() != "1"
                if raw.get("tradestatus") not in (None, "")
                else None
            ),
            "st_status": (
                str(raw.get("isST")).strip() == "1"
                if raw.get("isST") not in (None, "")
                else None
            ),
            "adjustment_mode": qfq_mode,
            "price_adjustment_mode": qfq_mode,
            "price_data_version": qfq_version,
            "adjusted_data_version": qfq_version,
            "raw_data_version": raw_version,
            "data_version": qfq_version,
            "data_ref": (
                f"index_daily:{ref_id}"
                if is_index
                else f"stock_daily_quotes:{ref_id}"
            ),
            "provider": provider,
            "provider_version": provider_version,
            "normalization_version": normalization_version,
        }
        documents.append(
            {
                **business,
                "available_at": _business_timestamp(trade_date, hour=15),
                "collected_at": None,
                "created_at": None,
                "content_hash": real_data_hash(business),
                "source_response_hash": real_data_hash(
                    {"raw": raw, "qfq": qfq}
                ),
                "schema_version": (
                    "alphaguard-real-index-price-v1"
                    if is_index
                    else "alphaguard-real-price-v1"
                ),
            }
        )
    return documents


class RecommendationDataService:
    QUALITY_COLLECTION = "ag_recommendation_data_quality_reports"
    COVERAGE_COLLECTION = "ag_recommendation_data_coverages"
    FACTOR_COLLECTION = "ag_recommendation_factor_evidence"

    def __init__(self, db):
        self.db = db
        self.contract = recommendation_data_contract()

    @property
    def normalization_version(self) -> str:
        return str(self.contract["normalization_version"])

    async def _open_dates(self, trade_date: date) -> list[date]:
        rows = await self.db["trading_calendar"].find(
            {"is_open": True}
        ).to_list(length=None)
        values = sorted(
            {
                item
                for row in rows
                if str(row.get("market") or "CN").upper() == "CN"
                and (item := _as_date(
                    row.get("session_date")
                    or row.get("trade_date")
                    or row.get("date")
                ))
                is not None
                and item <= trade_date
            }
        )
        if not values or values[-1] != trade_date:
            raise RecommendationDataError("PERSISTED_TRADING_CALENDAR_GATE_FAILED")
        return values

    @staticmethod
    def _master_document(
        row: dict[str, Any], *, provider_version: str, collected_at: datetime
    ) -> dict[str, Any]:
        provider_code = str(row.get("code") or "")
        symbol = provider_code.split(".")[-1]
        listing_date = str(row.get("ipoDate") or "")
        out_date = str(row.get("outDate") or "")
        business = {
            "ref_id": f"security-master-{symbol}-baostock",
            "source_record_id": f"baostock:{provider_code}:stock-basic",
            "code": symbol,
            "symbol": symbol,
            "name": str(row.get("code_name") or symbol),
            "category": "stock_cn",
            "security_type": "A_SHARE",
            "market": "CN",
            "list_date": listing_date,
            "listing_date": listing_date,
            "delist_date": out_date,
            "listing_status": (
                "DELISTED" if out_date else "LISTED"
            ),
            "provider_code": provider_code,
            "source": "baostock",
            "provider": "baostock",
            "provider_version": provider_version,
            "security_master_data_version": (
                f"baostock:{provider_version}:SECURITY_MASTER:recommendation-v1"
            ),
        }
        return {
            **business,
            "available_at": collected_at,
            "collected_at": collected_at,
            "created_at": collected_at,
            "security_master_content_hash": real_data_hash(business),
            "content_hash": real_data_hash(business),
            "schema_version": "alphaguard-recommendation-security-master-v1",
        }

    async def _persist_master(
        self, documents: list[dict[str, Any]], *, execute: bool
    ) -> dict[str, int]:
        summary = {"created": 0, "reused": 0, "conflicts": 0}
        for offset in range(0, len(documents), 500):
            chunk = documents[offset : offset + 500]
            symbols = [row["symbol"] for row in chunk]
            existing = await self.db["stock_basic_info"].find(
                {"code": {"$in": symbols}, "source": "baostock"}
            ).to_list(length=None)
            by_symbol = {str(row.get("code")): clean_document(row) for row in existing}
            missing = []
            for document in chunk:
                previous = by_symbol.get(document["symbol"])
                if previous is None:
                    missing.append(document)
                    continue
                if not _as_date(
                    previous.get("list_date") or previous.get("listing_date")
                ):
                    summary["conflicts"] += 1
                else:
                    summary["reused"] += 1
            if execute and missing:
                collection = self.db["stock_basic_info"]
                if hasattr(collection, "bulk_write"):
                    try:
                        await collection.bulk_write(
                            [InsertOne(document) for document in missing], ordered=False
                        )
                    except BulkWriteError as exc:
                        raise RecommendationDataIntegrityConflict(
                            "security-master create-only bulk write conflict"
                        ) from exc
                else:
                    for document in missing:
                        await collection.insert_one(document)
                summary["created"] += len(missing)
        return summary

    async def _persist_price_rows(
        self,
        documents: list[dict[str, Any]],
        *,
        execute: bool,
        collected_at: datetime,
    ) -> dict[str, int]:
        summary = {"created": 0, "reused": 0, "conflicts": 0}
        if not documents:
            return summary
        for document in documents:
            document["collected_at"] = collected_at
            document["created_at"] = collected_at
        for offset in range(0, len(documents), 500):
            chunk = documents[offset : offset + 500]
            refs = [row["ref_id"] for row in chunk]
            existing = await self.db["stock_daily_quotes"].find(
                {"ref_id": {"$in": refs}}
            ).to_list(length=None)
            by_ref = {str(row.get("ref_id")): row for row in existing}
            missing = []
            for document in chunk:
                previous = by_ref.get(document["ref_id"])
                if previous is None:
                    missing.append(document)
                elif str(previous.get("content_hash")) == document["content_hash"]:
                    summary["reused"] += 1
                else:
                    summary["conflicts"] += 1
            if summary["conflicts"]:
                raise RecommendationDataIntegrityConflict(
                    "immutable recommendation daily-price identity conflict"
                )
            if execute and missing:
                collection = self.db["stock_daily_quotes"]
                if hasattr(collection, "bulk_write"):
                    try:
                        await collection.bulk_write(
                            [InsertOne(row) for row in missing], ordered=False
                        )
                    except BulkWriteError as exc:
                        raise RecommendationDataIntegrityConflict(
                            "daily-price bulk write conflict"
                        ) from exc
                else:
                    for row in missing:
                        await collection.insert_one(row)
                summary["created"] += len(missing)
        return summary

    async def _locally_ready_symbols(
        self,
        symbols: list[str],
        *,
        start: date,
        trade_date: date,
    ) -> set[str]:
        """Return symbols whose local immutable window already satisfies this contract."""

        if not symbols:
            return set()
        rows = await self.db["stock_daily_quotes"].find(
            {
                "symbol": {"$in": symbols},
                "normalization_version": self.normalization_version,
                "trade_date": {
                    "$gte": _business_timestamp(start),
                    "$lte": _business_timestamp(trade_date),
                },
            },
            {
                "symbol": 1,
                "trade_date": 1,
                "open": 1,
                "high": 1,
                "low": 1,
                "close": 1,
                "adjusted_open": 1,
                "adjusted_high": 1,
                "adjusted_low": 1,
                "adjusted_close": 1,
                "volume": 1,
                "amount": 1,
                "price_data_version": 1,
                "raw_data_version": 1,
            },
        ).to_list(length=None)
        required = int(self.contract["required_history_days"])
        by_symbol: dict[str, list[dict[str, Any]]] = {
            symbol: [] for symbol in symbols
        }
        for row in rows:
            by_symbol.setdefault(str(row.get("symbol") or ""), []).append(row)
        ready: set[str] = set()
        for symbol, values in by_symbol.items():
            ordered = sorted(
                values, key=lambda item: _as_date(item.get("trade_date")) or date.min
            )
            versions = {
                str(item.get("price_data_version") or "") for item in ordered
            }
            raw_versions = {
                str(item.get("raw_data_version") or "") for item in ordered
            }
            complete_rows = [
                item
                for item in ordered
                if all(
                    _number(item.get(field)) is not None
                    for field in (
                        "open",
                        "high",
                        "low",
                        "close",
                        "adjusted_open",
                        "adjusted_high",
                        "adjusted_low",
                        "adjusted_close",
                        "volume",
                        "amount",
                    )
                )
            ]
            if (
                len(complete_rows) >= required
                and any(
                    _as_date(item.get("trade_date")) == trade_date
                    for item in complete_rows
                )
                and len(versions) == 1
                and "" not in versions
                and len(raw_versions) == 1
                and "" not in raw_versions
            ):
                ready.add(symbol)
        return ready

    async def sync_full_market(
        self,
        *,
        universe: CandidateUniverseManifest,
        trade_date: date,
        execute: bool,
        provider: RecommendationMarketDataProvider | None = None,
        now: datetime | None = None,
    ) -> dict[str, Any]:
        now = now or datetime.utcnow()
        started = time.perf_counter()
        provider = provider or BaoStockRecommendationProvider()
        open_dates = await self._open_dates(trade_date)
        session_count = int(self.contract["sync_history_sessions"])
        if len(open_dates) < session_count:
            raise RecommendationDataError("RECOMMENDATION_HISTORY_CALENDAR_INSUFFICIENT")
        start = open_dates[-session_count]
        master = await asyncio.to_thread(provider.fetch_master)
        master_rows = {
            str(row.get("code") or "").split(".")[-1]: row
            for row in master.rows
        }
        selected = [
            master_rows[symbol]
            for symbol in universe.ordered_symbols
            if symbol in master_rows
        ]
        master_summary = await self._persist_master(
            [
                self._master_document(
                    row,
                    provider_version=master.provider_version,
                    collected_at=now,
                )
                for row in selected
            ],
            execute=execute,
        )
        benchmark_symbol = str(self.contract["benchmark_symbol"])
        local_benchmark_ready = await self._locally_ready_symbols(
            [benchmark_symbol], start=start, trade_date=trade_date
        )
        price_summary = {"created": 0, "reused": 0, "conflicts": 0}
        failures: list[dict[str, str]] = []
        retries = 0
        if benchmark_symbol not in local_benchmark_ready:
            benchmark = await asyncio.to_thread(
                provider.fetch_benchmark, start=start, end=trade_date
            )
            benchmark_documents = list(
                benchmark.rows_by_symbol.get(benchmark_symbol, ())
            )
            price_summary = await self._persist_price_rows(
                benchmark_documents, execute=execute, collected_at=now
            )
            failures.extend(benchmark.failures)
            retries += benchmark.retry_count
        batch_size = int(self.contract["batch_size"])
        ordered_provider_symbols = [
            symbol for symbol in universe.ordered_symbols if symbol in master_rows
        ]
        processed = 0
        resumed = 0
        batch_metrics: list[dict[str, Any]] = []
        for offset in range(0, len(ordered_provider_symbols), batch_size):
            symbols = ordered_provider_symbols[offset : offset + batch_size]
            batch_started = time.perf_counter()
            locally_ready = await self._locally_ready_symbols(
                symbols, start=start, trade_date=trade_date
            )
            pending_symbols = [
                symbol for symbol in symbols if symbol not in locally_ready
            ]
            provider_codes = {
                symbol: str(master_rows[symbol]["code"])
                for symbol in pending_symbols
            }
            batch_failure_count = 0
            batch_retry_count = 0
            if pending_symbols:
                batch = await asyncio.to_thread(
                    provider.fetch_prices,
                    provider_codes,
                    start=start,
                    end=trade_date,
                    max_attempts=int(self.contract["max_attempts"]),
                )
                documents = [
                    row
                    for symbol in pending_symbols
                    for row in batch.rows_by_symbol.get(symbol, ())
                    if (_as_date(row.get("trade_date")) or date.max) <= trade_date
                ]
                persisted = await self._persist_price_rows(
                    documents, execute=execute, collected_at=now
                )
                for key in price_summary:
                    price_summary[key] += persisted[key]
                failures.extend(batch.failures)
                retries += batch.retry_count
                batch_failure_count = len(batch.failures)
                batch_retry_count = batch.retry_count
            processed += len(symbols)
            resumed += len(locally_ready)
            batch_metric = {
                "batch_number": offset // batch_size + 1,
                "symbol_count": len(symbols),
                "provider_request_count": len(pending_symbols),
                "resumed_symbol_count": len(locally_ready),
                "failed_symbol_count": batch_failure_count,
                "retry_count": batch_retry_count,
                "duration_ms": max(
                    0, int((time.perf_counter() - batch_started) * 1000)
                ),
            }
            batch_metrics.append(batch_metric)
            if execute:
                await self.db["sync_status"].update_one(
                    {
                        "job": (
                            f"alphaguard_recommendation_data:{trade_date.isoformat()}"
                        ),
                        "data_type": "RECOMMENDATION_DATA",
                    },
                    {
                        "$set": {
                            "job": (
                                f"alphaguard_recommendation_data:{trade_date.isoformat()}"
                            ),
                            "data_type": "RECOMMENDATION_DATA",
                            "status": "running",
                            "trade_date": _business_timestamp(trade_date),
                            "provider": master.provider,
                            "provider_version": master.provider_version,
                            "processed_symbols": processed,
                            "total_symbols": len(universe.ordered_symbols),
                            "failed_symbols": len(failures),
                            "retry_count": retries,
                            "resumed_symbols": resumed,
                            "last_batch": batch_metric,
                            "updated_at": datetime.utcnow(),
                            "schema_version": "recommendation-data-sync-v1",
                        }
                    },
                    upsert=True,
                )
        completed = datetime.utcnow()
        sync_run_id = _stable_id(
            "recommendation-data-sync",
            f"{trade_date}:{universe.universe_hash}:{master.provider_version}",
        )
        sync_summary = {
            "sync_run_id": sync_run_id,
            "trade_date": trade_date,
            "start_date": start,
            "provider": master.provider,
            "provider_version": master.provider_version,
            "universe_count": len(universe.ordered_symbols),
            "provider_supported_count": len(ordered_provider_symbols),
            "unsupported_count": len(universe.ordered_symbols)
            - len(ordered_provider_symbols),
            "processed_count": processed,
            "resumed_count": resumed,
            "failed_symbols": failures,
            "retry_count": retries,
            "created_count": master_summary["created"] + price_summary["created"],
            "reused_count": master_summary["reused"] + price_summary["reused"],
            "conflict_count": master_summary["conflicts"] + price_summary["conflicts"],
            "started_at": now,
            "completed_at": completed,
            "duration_ms": max(0, int((time.perf_counter() - started) * 1000)),
            "batch_metrics": batch_metrics,
            "write": execute,
        }
        if execute:
            stored_summary = {
                **sync_summary,
                "trade_date": _business_timestamp(trade_date),
                "start_date": _business_timestamp(start),
            }
            await self.db["sync_status"].update_one(
                {
                    "job": f"alphaguard_recommendation_data:{trade_date.isoformat()}",
                    "data_type": "RECOMMENDATION_DATA",
                },
                {
                    "$set": {
                        **stored_summary,
                        "status": "completed",
                        "updated_at": completed,
                    }
                },
                upsert=True,
            )
        return sync_summary

    async def _status_for(
        self,
        *,
        symbol: str,
        trade_date: date,
        quote: dict[str, Any] | None,
        instrument: dict[str, Any],
        execute: bool,
        now: datetime,
        open_dates: list[date] | None = None,
        existing_by_id: dict[str, dict[str, Any]] | None = None,
    ) -> dict[str, Any] | None:
        if quote is None:
            return None
        instrument = dict(instrument)
        security_master_version = str(
            instrument.get("security_master_data_version")
            or instrument.get("ref_id")
            or instrument.get("source_record_id")
            or "unknown"
        )
        instrument["security_master_data_version"] = (
            f"{security_master_version}:{RECOMMENDATION_STATUS_DERIVATION_VERSION}"
        )
        listing_date = _as_date(
            instrument.get("list_date") or instrument.get("listing_date")
        )
        if listing_date is None:
            return None
        session_number = 6 if (trade_date - listing_date).days > 30 else None
        if session_number is None:
            calendar = open_dates or await self._open_dates(trade_date)
            sessions = [item for item in calendar if item >= listing_date]
            if sessions and sessions[0] == listing_date:
                session_number = len(sessions)
        if session_number is None:
            return None
        status = derive_security_trading_status(
            quote=quote,
            instrument=instrument,
            trade_date=trade_date,
            listing_session_number=session_number,
            policy=cn_price_limit_policy(),
            collected_at=now,
        )
        identity = {
            "symbol": symbol,
            "market": "CN",
            "trade_date": _business_timestamp(trade_date),
            "data_version": status.data_version,
        }
        existing = (
            clean_document(existing_by_id.get(status.trading_status_id))
            if existing_by_id is not None
            else clean_document(
                await self.db["ag_security_trading_statuses"].find_one(identity)
            )
        )
        if existing:
            stored_at = existing.get("collected_at")
            if not isinstance(stored_at, datetime):
                raise TradingStatusConflict("existing status lacks collected_at")
            status = derive_security_trading_status(
                quote=quote,
                instrument=instrument,
                trade_date=trade_date,
                listing_session_number=session_number,
                policy=cn_price_limit_policy(),
                collected_at=stored_at,
            )
            if str(existing.get("content_hash")) != status.content_hash:
                raise TradingStatusConflict("recommendation trading status conflict")
            return existing
        if execute:
            await self.db["ag_security_trading_statuses"].insert_one(
                model_document(status)
            )
        return clean_document(model_document(status))

    async def _persist_create_only_documents(
        self,
        collection_name: str,
        documents: list[dict[str, Any]],
        *,
        id_field: str,
        hash_field: str,
        execute: bool,
    ) -> None:
        if not documents:
            return
        collection = self.db[collection_name]
        identifiers = [str(item[id_field]) for item in documents]
        existing_rows = await collection.find(
            {id_field: {"$in": identifiers}}
        ).to_list(length=None)
        existing = {str(item.get(id_field)): item for item in existing_rows}
        missing: list[dict[str, Any]] = []
        for document in documents:
            stored = existing.get(str(document[id_field]))
            if stored is None:
                missing.append(document)
            elif str(stored.get(hash_field)) != str(document.get(hash_field)):
                raise RecommendationDataIntegrityConflict(
                    f"{collection_name} immutable identity conflict"
                )
        if not execute or not missing:
            return
        mongo_documents = [to_mongo_value(item) for item in missing]
        if hasattr(collection, "bulk_write"):
            try:
                await collection.bulk_write(
                    [InsertOne(item) for item in mongo_documents], ordered=False
                )
            except BulkWriteError as exc:
                raise RecommendationDataIntegrityConflict(
                    f"{collection_name} create-only bulk write conflict"
                ) from exc
        else:
            for item in mongo_documents:
                await collection.insert_one(item)

    def _quality_for(
        self,
        *,
        symbol: str,
        trade_date: date,
        rows: list[dict[str, Any]],
        status: dict[str, Any] | None,
        benchmark_rows: list[dict[str, Any]],
        instrument: dict[str, Any],
        required_trade_dates: list[date],
        now: datetime,
    ) -> RecommendationDataQualityReport:
        required = int(self.contract["required_history_days"])
        ordered = sorted(rows, key=lambda row: _as_date(row.get("trade_date")) or date.min)
        target = next(
            (row for row in reversed(ordered) if _as_date(row.get("trade_date")) == trade_date),
            None,
        )
        versions = sorted(
            {
                str(row.get("price_data_version") or row.get("data_version") or "")
                for row in ordered
                if row.get("price_data_version") or row.get("data_version")
            }
        )
        raw_versions = sorted(
            {str(row.get("raw_data_version") or "") for row in ordered if row.get("raw_data_version")}
        )
        missing: list[str] = []
        blockers: list[str] = []
        expected_dates = required_trade_dates[-required:]
        actual_dates = [
            item
            for row in ordered
            if (item := _as_date(row.get("trade_date"))) is not None
        ]
        benchmark_dates = [
            item
            for row in benchmark_rows
            if (item := _as_date(row.get("trade_date"))) is not None
        ]
        if any(item > trade_date for item in actual_dates + benchmark_dates):
            missing.append("future_price")
            blockers.append("FUTURE_PRICE_DETECTED")
        if actual_dates[-required:] != expected_dates:
            missing.append("price_trade_dates")
            blockers.append("PRICE_HISTORY_SESSION_DISCONTINUITY")
        if benchmark_dates[-required:] != expected_dates:
            missing.append("benchmark_trade_dates")
            blockers.append("BENCHMARK_HISTORY_SESSION_DISCONTINUITY")
        if _as_date(instrument.get("list_date") or instrument.get("listing_date")) is None:
            missing.append("listing_date")
            blockers.append("LISTING_DATE_MISSING")
        if len(ordered) < required:
            missing.append(f"qfq_history[{len(ordered)}/{required}]")
            blockers.append("ADJUSTED_HISTORY_INSUFFICIENT")
        raw_count = len(
            [
                row
                for row in ordered
                if all(
                    row.get(field) is not None
                    for field in ("open", "high", "low", "close")
                )
            ]
        )
        if raw_count < required:
            missing.append(f"raw_history[{raw_count}/{required}]")
            blockers.append("RAW_HISTORY_INSUFFICIENT")
        if target is None:
            missing.append("target_quote")
            blockers.append("TARGET_QUOTE_MISSING")
        if len(versions) != 1 or len(raw_versions) != 1:
            missing.append("price_data_version")
            blockers.append("PRICE_VERSION_DISCONTINUITY")
        if status is None or str(status.get("calculation_status")) != "READY":
            missing.append("trading_status")
            blockers.append("TRADING_STATUS_NOT_READY")
        if len(benchmark_rows) < required or not any(
            _as_date(row.get("trade_date")) == trade_date for row in benchmark_rows
        ):
            missing.append(f"benchmark_history[{len(benchmark_rows)}/{required}]")
            blockers.append("BENCHMARK_NOT_READY")
        for row in ordered[-required:]:
            raw_values = [_number(row.get(key)) for key in ("open", "high", "low", "close")]
            qfq_values = [
                _number(row.get(key))
                for key in ("adjusted_open", "adjusted_high", "adjusted_low", "adjusted_close")
            ]
            if any(value is None or value <= 0 for value in raw_values + qfq_values):
                blockers.append("PRICE_DATA_ANOMALY")
                missing.append("price_ohlc")
                break
            if _number(row.get("volume")) is None or _number(row.get("amount")) is None:
                blockers.append("PRICE_DATA_ANOMALY")
                missing.append("price_volume_or_amount")
                break
        missing = sorted(set(missing))
        blockers = sorted(set(blockers))
        target_ref = str((target or {}).get("ref_id") or "") or None
        target_hash = str((target or {}).get("content_hash") or "") or None
        status_id = str((status or {}).get("trading_status_id") or "") or None
        status_hash = str((status or {}).get("content_hash") or "") or None
        input_payload = {
            "symbol": symbol,
            "trade_date": trade_date,
            "contract_hash": self.contract["contract_hash"],
            "quote_hashes": [str(row.get("content_hash") or "") for row in ordered[-required:]],
            "status_hash": status_hash,
            "benchmark_hashes": [str(row.get("content_hash") or "") for row in benchmark_rows[-required:]],
            "listing_date": str(instrument.get("list_date") or instrument.get("listing_date") or ""),
        }
        input_hash = recommendation_hash(input_payload)
        data_version = (
            f"{self.contract['contract_version']}:"
            f"{recommendation_hash({'price': versions, 'raw': raw_versions, 'status': status_hash})[:24]}"
        )
        identity = f"{symbol}:{trade_date}:{data_version}"
        payload = {
            "quality_report_id": _stable_id("recommendation-data-quality", identity),
            "symbol": symbol,
            "market": "CN",
            "trade_date": trade_date,
            "status": "PASS" if not blockers else "FAIL",
            "required_history_days": required,
            "available_history_days": len(ordered),
            "price_adjustment_mode": "QFQ",
            "price_data_versions": versions,
            "target_quote_ref": target_ref,
            "target_quote_hash": target_hash,
            "trading_status_id": status_id,
            "trading_status_hash": status_hash,
            "benchmark_count": len(benchmark_rows),
            "benchmark_manifest_ref": None,
            "missing_fields": missing,
            "blocking_reasons": blockers,
            "data_version": data_version,
            "input_hash": input_hash,
            "immutable_hash": "0" * 64,
            "checked_at": now,
        }
        payload["immutable_hash"] = recommendation_hash(
            payload, exclude={"immutable_hash", "checked_at", "schema_version"}
        )
        return RecommendationDataQualityReport.model_validate(payload)

    async def prepare_coverage(
        self,
        *,
        universe: CandidateUniverseManifest,
        securities: dict[str, dict[str, Any]],
        policy: CandidateRecommendationPolicy,
        trade_date: date,
        execute: bool,
        now: datetime | None = None,
        sync_summary: dict[str, Any] | None = None,
    ) -> RecommendationDataCoverage:
        now = now or datetime.utcnow()
        now = now.replace(microsecond=(now.microsecond // 1000) * 1000)
        open_dates = await self._open_dates(trade_date)
        required = int(self.contract["required_history_days"])
        start = open_dates[-required] if len(open_dates) >= required else open_dates[0]
        benchmark_rows = [
            clean_document(row)
            for row in await self.db["stock_daily_quotes"].find(
                {
                    "symbol": str(self.contract["benchmark_symbol"]),
                    "normalization_version": self.normalization_version,
                }
            ).to_list(length=None)
            if str(row.get("market") or "CN").upper() == "CN"
            and str(row.get("period") or "daily").lower() == "daily"
            and start <= (_as_date(row.get("trade_date")) or date.min) <= trade_date
        ]
        benchmark_rows.sort(key=lambda row: _as_date(row.get("trade_date")) or date.min)
        industry_symbols = {
            str(row.get("symbol") or row.get("code") or "")
            for row in await self.db["stock_industry_history"].find(
                {"effective_from": {"$lte": _business_timestamp(trade_date)}}
            ).to_list(length=None)
        }
        counts = Counter()
        blockers = Counter()
        quality_hashes: list[str] = []
        batch_size = int(self.contract["batch_size"])
        for offset in range(0, len(universe.ordered_symbols), batch_size):
            symbols = universe.ordered_symbols[offset : offset + batch_size]
            rows = [
                clean_document(row)
                for row in await self.db["stock_daily_quotes"].find(
                    {
                        "symbol": {"$in": symbols},
                        "normalization_version": self.normalization_version,
                    }
                ).to_list(length=None)
                if str(row.get("market") or "CN").upper() == "CN"
                and str(row.get("period") or "daily").lower() == "daily"
                and str(
                    row.get("price_adjustment_mode")
                    or row.get("adjustment_mode")
                    or ""
                ).upper()
                == "QFQ"
                and start
                <= (_as_date(row.get("trade_date")) or date.min)
                <= trade_date
            ]
            rows_by_symbol: dict[str, list[dict[str, Any]]] = {
                symbol: [] for symbol in symbols
            }
            for row in rows:
                rows_by_symbol.setdefault(str(row.get("symbol")), []).append(row)
            status_rows = [
                clean_document(row)
                for row in await self.db["ag_security_trading_statuses"].find(
                    {"symbol": {"$in": symbols}, "market": "CN"}
                ).to_list(length=None)
                if _as_date(row.get("trade_date")) == trade_date
            ]
            status_by_id = {
                str(row.get("trading_status_id") or ""): row
                for row in status_rows
                if row.get("trading_status_id")
            }
            new_status_documents: list[dict[str, Any]] = []
            quality_reports: list[RecommendationDataQualityReport] = []
            for symbol in symbols:
                instrument = securities[symbol]
                symbol_rows = sorted(
                    rows_by_symbol.get(symbol, []),
                    key=lambda row: _as_date(row.get("trade_date")) or date.min,
                )
                target = next(
                    (
                        row
                        for row in reversed(symbol_rows)
                        if _as_date(row.get("trade_date")) == trade_date
                    ),
                    None,
                )
                status = None
                if target is not None:
                    try:
                        status = await self._status_for(
                            symbol=symbol,
                            trade_date=trade_date,
                            quote=target,
                            instrument=instrument,
                            execute=False,
                            now=now,
                            open_dates=open_dates,
                            existing_by_id=status_by_id,
                        )
                    except Exception:
                        status = None
                if (
                    status is not None
                    and str(status.get("trading_status_id") or "")
                    not in status_by_id
                ):
                    new_status_documents.append(status)
                report = self._quality_for(
                    symbol=symbol,
                    trade_date=trade_date,
                    rows=symbol_rows,
                    status=status,
                    benchmark_rows=benchmark_rows,
                    instrument=instrument,
                    required_trade_dates=open_dates,
                    now=now,
                )
                quality_reports.append(report)
                quality_hashes.append(report.immutable_hash)
                listing_date = _as_date(
                    instrument.get("list_date") or instrument.get("listing_date")
                )
                if listing_date is not None:
                    counts["basic"] += 1
                if target is not None:
                    counts["target"] += 1
                if status and status.get("calculation_status") == "READY":
                    counts["status"] += 1
                raw_ready = sum(row.get("open") is not None for row in symbol_rows) >= required
                qfq_ready = sum(row.get("adjusted_close") is not None for row in symbol_rows) >= required
                if raw_ready:
                    counts["raw"] += 1
                if qfq_ready:
                    counts["qfq"] += 1
                if symbol in industry_symbols:
                    counts["industry"] += 1
                if report.status == "PASS":
                    counts["quality"] += 1
                    counts["contract"] += 1
                listing_status = str(
                    instrument.get("listing_status")
                    or instrument.get("status")
                    or ""
                ).upper()
                name = str(instrument.get("name") or "")
                if (
                    any(
                        token in listing_status
                        for token in ("DELIST", "TERMINATED", "退市")
                    )
                    or "退市整理" in name
                    or name.startswith("退")
                ):
                    counts["resolved_exclusion"] += 1
                for reason in report.blocking_reasons:
                    blockers[reason] += 1
            await self._persist_create_only_documents(
                "ag_security_trading_statuses",
                new_status_documents,
                id_field="trading_status_id",
                hash_field="content_hash",
                execute=execute,
            )
            await self._persist_create_only_documents(
                self.QUALITY_COLLECTION,
                [model_document(report) for report in quality_reports],
                id_field="quality_report_id",
                hash_field="immutable_hash",
                execute=execute,
            )
        universe_count = len(universe.ordered_symbols)
        coverage_value = (
            Decimal(counts["contract"] + counts["resolved_exclusion"])
            / Decimal(universe_count)
            if universe_count
            else Decimal("0")
        )
        threshold = Decimal(str(self.contract["coverage_threshold"]))
        benchmark_count = len(benchmark_rows)
        data_ready = coverage_value >= threshold and benchmark_count >= required
        failed = max(
            0,
            universe_count - counts["contract"] - counts["resolved_exclusion"],
        )
        status = (
            "READY"
            if data_ready and failed == 0
            else "DEGRADED"
            if data_ready
            else "PARTIAL"
            if counts["contract"]
            else "NOT_READY"
        )
        source_hash = recommendation_hash(
            {
                "universe_hash": universe.universe_hash,
                "quality_hashes": sorted(quality_hashes),
                "benchmark_hashes": [
                    str(row.get("content_hash") or "") for row in benchmark_rows
                ],
                "contract_hash": self.contract["contract_hash"],
            }
        )
        data_version = f"{self.contract['contract_version']}:{source_hash[:24]}"
        payload = {
            "coverage_id": _stable_id(
                "recommendation-data-coverage",
                f"{trade_date}:{universe.manifest_id}:{data_version}",
            ),
            "market": "CN",
            "trade_date": trade_date,
            "universe_manifest_id": universe.manifest_id,
            "universe_hash": universe.universe_hash,
            "universe_count": universe_count,
            "basic_info_ready_count": counts["basic"],
            "target_quote_ready_count": counts["target"],
            "trade_status_ready_count": counts["status"],
            "raw_history_ready_count": counts["raw"],
            "adjusted_history_ready_count": counts["qfq"],
            "benchmark_ready_count": benchmark_count,
            "industry_ready_count": counts["industry"],
            "data_quality_pass_count": counts["quality"],
            "minimum_contract_ready_count": counts["contract"],
            "eligible_count": counts["contract"],
            "failed_symbol_count": failed,
            "required_history_days": required,
            "coverage_threshold": threshold,
            "coverage_percentage": coverage_value,
            "blocking_reason_counts": dict(sorted(blockers.items())),
            "status": status,
            "recommendation_data_ready": data_ready,
            "industry_required": bool(self.contract["industry_required"]),
            "data_version": data_version,
            "source_hash": source_hash,
            "coverage_hash": "0" * 64,
            "sync_run_id": (sync_summary or {}).get("sync_run_id"),
            "sync_started_at": (sync_summary or {}).get("started_at"),
            "sync_completed_at": (sync_summary or {}).get("completed_at"),
            "sync_duration_ms": int((sync_summary or {}).get("duration_ms") or 0),
            "sync_created_count": int((sync_summary or {}).get("created_count") or 0),
            "sync_reused_count": int((sync_summary or {}).get("reused_count") or 0),
            "sync_retry_count": int((sync_summary or {}).get("retry_count") or 0),
            "sync_resumed_count": int((sync_summary or {}).get("resumed_count") or 0),
            "created_at": now,
        }
        payload["coverage_hash"] = recommendation_hash(
            payload,
            exclude={
                "coverage_hash",
                "created_at",
                "schema_version",
                "sync_run_id",
                "sync_started_at",
                "sync_completed_at",
                "sync_duration_ms",
                "sync_created_count",
                "sync_reused_count",
                "sync_retry_count",
                "sync_resumed_count",
            },
        )
        coverage = RecommendationDataCoverage.model_validate(payload)
        existing = clean_document(
            await self.db[self.COVERAGE_COLLECTION].find_one(
                {"coverage_id": coverage.coverage_id}
            )
        )
        if existing:
            stored = RecommendationDataCoverage.model_validate(existing)
            if stored.coverage_hash != coverage.coverage_hash:
                raise RecommendationDataIntegrityConflict(
                    "recommendation coverage identity conflict"
                )
            return stored
        if execute:
            await self.db[self.COVERAGE_COLLECTION].insert_one(
                model_document(coverage)
            )
        return coverage

    async def latest_coverage(
        self, *, trade_date: date | None = None
    ) -> RecommendationDataCoverage | None:
        query = (
            {"trade_date": _business_timestamp(trade_date)} if trade_date else {}
        )
        row = clean_document(
            await self.db[self.COVERAGE_COLLECTION].find_one(
                query, sort=[("created_at", -1)]
            )
        )
        return RecommendationDataCoverage.model_validate(row) if row else None

    def build_factor_evidence(
        self,
        *,
        symbol: str,
        trade_date: date,
        price_rows: list[dict[str, Any]],
        benchmark_rows: list[dict[str, Any]],
        now: datetime,
    ) -> RecommendationFactorEvidence | None:
        required = int(self.contract["required_history_days"])
        if len(price_rows) < required or len(benchmark_rows) < required:
            return None
        ordered_price_rows = sorted(
            price_rows, key=lambda item: _as_date(item.get("trade_date")) or date.min
        )[-required:]
        ordered_benchmark_rows = sorted(
            benchmark_rows,
            key=lambda item: _as_date(item.get("trade_date")) or date.min,
        )[-required:]
        prices = []
        for row in ordered_price_rows:
            prices.append(
                {
                    **row,
                    "trade_date": str(_as_date(row.get("trade_date"))),
                    "open": row.get("adjusted_open"),
                    "high": row.get("adjusted_high"),
                    "low": row.get("adjusted_low"),
                    "close": row.get("adjusted_close"),
                }
            )
        benchmark = [
            {**row, "trade_date": str(_as_date(row.get("trade_date")))}
            for row in ordered_benchmark_rows
        ]
        data = SimpleNamespace(
            prices=prices,
            benchmark_prices=benchmark,
            financials=[],
            news=[],
            announcements=[],
        )
        factor_set, definitions, _ = builtin_factor_definitions()
        selected = [item for item in definitions if item.factor_id in FACTOR_IDS]
        scores: dict[str, Decimal | None] = {}
        groups: dict[str, list[Decimal]] = {}
        for definition in selected:
            raw = calculate_factor_value(
                definition.factor_id, data, definition.parameters
            )
            normalized = (
                None
                if raw is None
                else normalize_factor_value(
                    raw,
                    definition.normalization_method,
                    definition.parameters,
                )
            )
            value = Decimal(str(normalized)) if normalized is not None else None
            scores[definition.factor_id] = value
            if value is not None:
                groups.setdefault(definition.group, []).append(value)
        group_scores = {
            group: (
                sum(values, Decimal("0")) / Decimal(len(values))
                if values
                else None
            )
            for group, values in groups.items()
        }
        required_groups = ("TREND", "MOMENTUM", "LIQUIDITY", "VOLATILITY_RISK")
        if any(group_scores.get(group) is None for group in required_groups):
            return None
        quote_refs = [str(row.get("ref_id") or "") for row in ordered_price_rows]
        quote_hashes = [str(row.get("content_hash") or "") for row in ordered_price_rows]
        benchmark_refs = [
            str(row.get("ref_id") or "") for row in ordered_benchmark_rows
        ]
        benchmark_hashes = [
            str(row.get("content_hash") or "") for row in ordered_benchmark_rows
        ]
        input_hash = recommendation_hash(
            {
                "symbol": symbol,
                "trade_date": trade_date,
                "factor_set": factor_set,
                "definitions": {
                    item.factor_id: {
                        "version": item.factor_version,
                        "code_hash": item.code_hash,
                        "parameter_hash": item.parameter_hash,
                    }
                    for item in selected
                },
                "quote_hashes": quote_hashes,
                "benchmark_hashes": benchmark_hashes,
            }
        )
        output_hash = recommendation_hash(
            {"normalized_scores": scores, "group_scores": group_scores}
        )
        return RecommendationFactorEvidence(
            evidence_id=_stable_id(
                "recommendation-factor-evidence",
                f"{symbol}:{trade_date}:{factor_set}:{input_hash}",
            ),
            symbol=symbol,
            market="CN",
            trade_date=trade_date,
            factor_set_version=factor_set,
            factor_definition_versions={
                item.factor_id: item.factor_version for item in selected
            },
            factor_code_hashes={item.factor_id: item.code_hash for item in selected},
            normalized_scores=scores,
            group_scores=group_scores,
            quote_refs=quote_refs,
            quote_hashes=quote_hashes,
            benchmark_refs=benchmark_refs,
            benchmark_hashes=benchmark_hashes,
            input_hash=input_hash,
            output_hash=output_hash,
            created_at=now,
        )

    async def persist_factor_evidence(
        self, evidence: RecommendationFactorEvidence
    ) -> RecommendationFactorEvidence:
        stored = await self.persist_factor_evidence_many([evidence])
        return stored[evidence.symbol]

    async def persist_factor_evidence_many(
        self, evidences: list[RecommendationFactorEvidence]
    ) -> dict[str, RecommendationFactorEvidence]:
        if not evidences:
            return {}
        identifiers = [item.evidence_id for item in evidences]
        rows = await self.db[self.FACTOR_COLLECTION].find(
            {"evidence_id": {"$in": identifiers}}
        ).to_list(length=None)
        existing = {
            str(row.get("evidence_id")): RecommendationFactorEvidence.model_validate(
                clean_document(row)
            )
            for row in rows
        }
        missing: list[RecommendationFactorEvidence] = []
        result: dict[str, RecommendationFactorEvidence] = {}
        for evidence in evidences:
            stored = existing.get(evidence.evidence_id)
            if stored is not None:
                if stored.output_hash != evidence.output_hash:
                    raise RecommendationDataIntegrityConflict(
                        "recommendation factor evidence conflict"
                    )
                result[evidence.symbol] = stored
            else:
                missing.append(evidence)
                result[evidence.symbol] = evidence
        if missing:
            collection = self.db[self.FACTOR_COLLECTION]
            if hasattr(collection, "bulk_write"):
                try:
                    await collection.bulk_write(
                        [InsertOne(model_document(item)) for item in missing],
                        ordered=False,
                    )
                except BulkWriteError as exc:
                    raise RecommendationDataIntegrityConflict(
                        "recommendation factor evidence create-only bulk write conflict"
                    ) from exc
            else:
                for item in missing:
                    await collection.insert_one(model_document(item))
        return result
