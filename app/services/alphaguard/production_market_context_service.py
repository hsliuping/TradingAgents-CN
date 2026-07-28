"""Build independent, versioned production MarketContext records.

The provider adapter is shared with historical research, but every production
sync performs a fresh source fetch and persists it under production-only
identities.  No ``ag_research_*`` document is read or copied.
"""

from __future__ import annotations

import asyncio
import math
import statistics
from datetime import date, datetime, time
from decimal import Decimal
from typing import Any, Callable
from uuid import NAMESPACE_URL, uuid5
from zoneinfo import ZoneInfo

from bson import BSON

from app.services.alphaguard.historical_market_context_service import (
    BaoStockHistoricalMarketProvider,
    HistoricalMarketProvider,
)
from app.services.alphaguard.paper_storage import clean_document, model_document
from app.services.alphaguard.quant_config import regime_config
from tradingagents.alphaguard.production_data_schemas import (
    ProductionMarketContext,
    ProductionMarketContextSource,
    production_data_hash,
)

from .production_data_config import production_market_context_policy


CN_MARKET_TIMEZONE = ZoneInfo("Asia/Shanghai")


class ProductionMarketContextError(RuntimeError):
    pass


class ProductionMarketContextConflict(ProductionMarketContextError):
    pass


def _business_timestamp(value: date, *, hour: int = 0) -> datetime:
    return datetime.combine(value, time(hour=hour))


def _as_date(value: Any) -> date | None:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    try:
        return date.fromisoformat(str(value)[:10])
    except (TypeError, ValueError):
        return None


def _as_decimal(value: Any) -> Decimal | None:
    if value is None:
        return None
    try:
        result = Decimal(str(value))
    except Exception:
        return None
    return result if result.is_finite() else None


def _after_close(trade_date: date, now: datetime) -> bool:
    if trade_date < now.date():
        return True
    if trade_date > now.date():
        return False
    return now.time() >= time(15, 0)


class ProductionMarketContextService:
    SOURCE_COLLECTION = "ag_market_context_sources"
    CONTEXT_COLLECTION = "ag_market_contexts"

    def __init__(self, db):
        self.db = db
        self.policy = production_market_context_policy()

    async def _benchmark_records(
        self,
        trade_date: date,
        cutoff_at: datetime,
    ) -> tuple[list[dict[str, Any]], list[str]]:
        required = int(self.policy["required_benchmark_sessions"])
        target = await self.db["stock_daily_quotes"].find_one(
            {
                "symbol": "000300",
                "market": "CN",
                "period": "daily",
                "trade_date": _business_timestamp(trade_date),
            }
        )
        if target is None:
            return [], ["benchmark target-date row"]
        target_version = str(target.get("price_data_version") or "")
        if not target_version:
            return [], ["benchmark price_data_version"]
        rows = (
            await self.db["stock_daily_quotes"]
            .find(
                {
                    "symbol": "000300",
                    "market": "CN",
                    "period": "daily",
                    "trade_date": {"$lte": _business_timestamp(trade_date)},
                    "available_at": {"$lte": cutoff_at},
                    "price_adjustment_mode": "INDEX_UNADJUSTED_EQUIVALENT",
                }
            )
            .sort("trade_date", -1)
            .limit(required * 3)
            .to_list(length=required * 3)
        )
        by_date: dict[date, dict[str, Any]] = {}
        duplicate_dates: set[date] = set()
        for row in rows:
            row_date = _as_date(row.get("trade_date"))
            if row_date is None:
                continue
            if row_date in by_date:
                duplicate_dates.add(row_date)
            else:
                by_date[row_date] = row
        if duplicate_dates:
            return [], [
                "ambiguous benchmark trade dates:"
                + ",".join(item.isoformat() for item in sorted(duplicate_dates))
            ]
        selected_dates = sorted(by_date)[-required:]
        rows = [by_date[item] for item in selected_dates]
        normalized: list[dict[str, Any]] = []
        for row in rows:
            row_date = _as_date(row.get("trade_date"))
            close = _as_decimal(row.get("close"))
            ref_id = str(row.get("ref_id") or "")
            available_at = row.get("available_at")
            row_version = str(row.get("price_data_version") or "")
            if (
                row_date is None
                or close is None
                or close <= 0
                or not ref_id
                or available_at is None
                or not row_version
            ):
                continue
            normalized.append(
                {
                    "source_record_id": str(
                        row.get("source_record_id") or ref_id
                    ),
                    "ref_id": ref_id,
                    "trade_date": row_date,
                    "close": close,
                    "available_at": available_at,
                    "provider": str(row.get("provider") or ""),
                    "provider_version": str(row.get("provider_version") or ""),
                    "data_version": row_version,
                    "content_hash": str(row.get("content_hash") or ""),
                }
            )
        missing = []
        if len(normalized) != required:
            missing.append(f"benchmark close[{required}]")
        elif normalized[-1]["trade_date"] != trade_date:
            missing.append("benchmark target-date close")
        return normalized, missing

    @staticmethod
    def _benchmark_metrics(
        records: list[dict[str, Any]],
    ) -> dict[str, Decimal | None]:
        closes = [Decimal(str(item["close"])) for item in records]
        if len(closes) < 61:
            return {
                "benchmark_close": None,
                "benchmark_ma20": None,
                "benchmark_ma60": None,
                "benchmark_ma20_slope_5d": None,
                "benchmark_volatility20": None,
            }
        ma20 = sum(closes[-20:], Decimal("0")) / Decimal("20")
        ma60 = sum(closes[-60:], Decimal("0")) / Decimal("60")
        prior_ma20 = sum(closes[-25:-5], Decimal("0")) / Decimal("20")
        returns = [
            float(closes[index] / closes[index - 1] - Decimal("1"))
            for index in range(len(closes) - 20, len(closes))
        ]
        return {
            "benchmark_close": closes[-1],
            "benchmark_ma20": ma20,
            "benchmark_ma60": ma60,
            "benchmark_ma20_slope_5d": ma20 / prior_ma20 - Decimal("1"),
            "benchmark_volatility20": Decimal(
                str(statistics.stdev(returns) * math.sqrt(250))
            ),
        }

    async def sync(
        self,
        *,
        trade_date: date,
        execute: bool,
        provider: HistoricalMarketProvider | None = None,
        timeout_seconds: float = 3600,
        progress: Callable[[dict[str, Any]], None] | None = None,
        now: datetime | None = None,
    ) -> dict[str, Any]:
        now = now or datetime.now(CN_MARKET_TIMEZONE).replace(tzinfo=None)
        now = now.replace(microsecond=(now.microsecond // 1000) * 1000)
        if not _after_close(trade_date, now):
            raise ProductionMarketContextError(
                "production MarketContext requires a completed trading day"
            )
        calendar = await self.db["trading_calendar"].find_one(
            {
                "market": "CN",
                "session_date": _business_timestamp(trade_date),
                "is_open": True,
            }
        )
        if calendar is None:
            raise ProductionMarketContextError(
                "persisted CN calendar does not confirm an open session"
            )
        provider = provider or BaoStockHistoricalMarketProvider()
        capability = provider.capability_check()
        if capability.get("available") is not True:
            raise ProductionMarketContextError(
                f"provider unavailable: {capability.get('error_type', 'UNKNOWN')}"
            )
        provider_policy = {
            "market_context": {
                key: self.policy[key]
                for key in (
                    "normalization_version",
                    "history_buffer_calendar_days",
                    "rolling_high_low_sessions",
                    "amount_ratio_sessions",
                    "minimum_universe_coverage",
                    "minimum_high_low_coverage",
                    "minimum_sector_coverage",
                    "query_retry_attempts",
                    "socket_timeout_seconds",
                    "query_delay_seconds",
                    "fallback_parallelism",
                    "sector_index_codes",
                )
            }
        }
        fetched = await asyncio.wait_for(
            asyncio.to_thread(
                provider.fetch,
                selected_dates=[trade_date],
                policy=provider_policy,
                progress=progress,
            ),
            timeout=timeout_seconds,
        )
        benchmark_records, benchmark_missing = await self._benchmark_records(
            trade_date,
            now,
        )
        benchmark_metrics = self._benchmark_metrics(benchmark_records)
        collected_at = now
        raw_source = dict(fetched.source_payloads[trade_date])
        source_identity = {
            "market": "CN",
            "trade_date": _business_timestamp(trade_date),
            "provider": fetched.provider,
            "provider_version": fetched.provider_version,
            "normalization_version": fetched.normalization_version,
        }
        existing_source = clean_document(
            await self.db[self.SOURCE_COLLECTION].find_one(source_identity)
        )
        if existing_source is not None:
            source_available_at = existing_source.get("available_at")
            source_collected_at = existing_source.get("collected_at")
            if not isinstance(source_available_at, datetime) or not isinstance(
                source_collected_at, datetime
            ):
                raise ProductionMarketContextConflict(
                    "existing production MarketContext source lacks "
                    "first-observation timestamps"
                )
        else:
            source_available_at = collected_at
            source_collected_at = collected_at
        source_business = {
            **raw_source,
            "benchmark_records": benchmark_records,
            "available_at": source_available_at,
        }
        source_business["content_hash"] = production_data_hash(source_business)
        source = ProductionMarketContextSource(
            source_id=str(
                uuid5(
                    NAMESPACE_URL,
                    "alphaguard:production-market-source:"
                    f"CN:{trade_date}:{fetched.provider}:"
                    f"{fetched.provider_version}:{fetched.normalization_version}",
                )
            ),
            collected_at=source_collected_at,
            **source_business,
        )
        source_size = len(BSON.encode(model_document(source)))
        if source_size >= 15_000_000:
            raise ProductionMarketContextError(
                f"production MarketContext source approaches BSON limit: {source_size}"
            )

        raw_context = dict(fetched.context_payloads[trade_date])
        missing = sorted(
            set(list(raw_context.get("missing_fields") or []) + benchmark_missing)
        )
        advances = raw_context.get("advance_count")
        declines = raw_context.get("decline_count")
        breadth = (
            Decimal(int(advances) - int(declines))
            / Decimal(int(advances) + int(declines))
            if advances is not None
            and declines is not None
            and int(advances) + int(declines) > 0
            else None
        )
        highs = raw_context.get("new_high_count")
        lows = raw_context.get("new_low_count")
        high_low_ratio = (
            Decimal(int(highs) - int(lows)) / Decimal(int(highs) + int(lows))
            if highs is not None and lows is not None and int(highs) + int(lows) > 0
            else None
        )
        volatility20 = benchmark_metrics.get("benchmark_volatility20")
        thresholds = regime_config()["thresholds"]
        extreme_risk_flag = (
            bool(
                Decimal(str(volatility20))
                >= Decimal(str(thresholds["extreme_volatility"]))
                and breadth
                <= Decimal(str(thresholds["breadth_collapse"]))
            )
            if volatility20 is not None and breadth is not None
            else None
        )
        data_version = (
            f"{fetched.provider}:{fetched.provider_version}:MARKET_CONTEXT:"
            f"{self.policy['normalization_version']}:"
            f"{self.policy['calculation_version']}"
        )
        context_identity = {
            "market": "CN",
            "trade_date": _business_timestamp(trade_date),
            "data_version": data_version,
        }
        existing_context = clean_document(
            await self.db[self.CONTEXT_COLLECTION].find_one(context_identity)
        )
        if existing_context is not None:
            context_available_at = existing_context.get("available_at")
            context_collected_at = existing_context.get("collected_at")
            if not isinstance(context_available_at, datetime) or not isinstance(
                context_collected_at, datetime
            ):
                raise ProductionMarketContextConflict(
                    "existing production MarketContext lacks "
                    "first-observation timestamps"
                )
        else:
            context_available_at = max(
                _business_timestamp(trade_date, hour=15),
                source_available_at,
            )
            context_collected_at = source_collected_at
        context_ref = (
            f"market-context-CN-{trade_date.isoformat()}-"
            f"{production_data_hash(data_version)[:16]}"
        )
        context_business = {
            "ref_id": context_ref,
            "source_record_id": source.source_id,
            "source_refs": [
                f"ag_market_context_sources:{source.source_id}",
                *[
                    f"stock_daily_quotes:{item['ref_id']}"
                    for item in benchmark_records
                ],
            ],
            "market": "CN",
            "trade_date": trade_date,
            "business_date": _business_timestamp(trade_date),
            "available_at": context_available_at,
            "provider": fetched.provider,
            "provider_version": fetched.provider_version,
            "data_version": data_version,
            "calculation_version": str(self.policy["calculation_version"]),
            **benchmark_metrics,
            "total_amount": raw_context.get("total_amount"),
            "amount_ratio20": raw_context.get("amount_ratio20"),
            "advance_count": advances,
            "decline_count": declines,
            "unchanged_count": raw_context.get("unchanged_count"),
            "market_breadth": breadth,
            "new_high_count": highs,
            "new_low_count": lows,
            "new_high_low_ratio": high_low_ratio,
            "industry_diffusion": raw_context.get("industry_diffusion"),
            "extreme_risk_flag": extreme_risk_flag,
            "universe_coverage": raw_context.get("universe_coverage"),
            "high_low_coverage": raw_context.get("high_low_coverage"),
            "sector_coverage": raw_context.get("sector_coverage"),
            "calculation_status": "READY" if not missing else "INSUFFICIENT_DATA",
            "missing_fields": missing,
            "methodology": {
                **dict(raw_context.get("methodology") or {}),
                "benchmark": (
                    "persisted version-locked CSI300 closes; MA20/MA60/"
                    "MA20 5-session slope/20-session annualized volatility"
                ),
                "production_isolation": (
                    "fresh provider fetch; no ag_research_* reads or copies"
                ),
            },
        }
        context_business["content_hash"] = production_data_hash(context_business)
        context = ProductionMarketContext(
            context_id=str(
                uuid5(
                    NAMESPACE_URL,
                    f"alphaguard:production-market-context:"
                    f"CN:{trade_date}:{data_version}",
                )
            ),
            collected_at=context_collected_at,
            **context_business,
        )

        if (
            existing_source is not None
            and str(existing_source.get("content_hash")) != source.content_hash
        ):
            raise ProductionMarketContextConflict(
                "same production MarketContext source identity has different content"
            )
        if (
            existing_context is not None
            and str(existing_context.get("content_hash")) != context.content_hash
        ):
            raise ProductionMarketContextConflict(
                "same production trade_date + data_version has different content"
            )
        result = {
            "trade_date": trade_date,
            "provider": fetched.provider,
            "provider_version": fetched.provider_version,
            "data_version": data_version,
            "calculation_version": self.policy["calculation_version"],
            "calculation_status": context.calculation_status,
            "missing_fields": context.missing_fields,
            "source_record_count": source.source_record_count,
            "expected_universe_count": source.expected_universe_count,
            "source_bson_bytes": source_size,
            "source_action": "REUSED" if existing_source else "WOULD_CREATE",
            "context_action": "REUSED" if existing_context else "WOULD_CREATE",
            "write": execute,
        }
        if not execute:
            return result
        if existing_source is None:
            await self.db[self.SOURCE_COLLECTION].insert_one(model_document(source))
            result["source_action"] = "CREATED"
        if existing_context is None:
            await self.db[self.CONTEXT_COLLECTION].insert_one(model_document(context))
            result["context_action"] = "CREATED"
        await self.db["ag_production_data_events"].update_one(
            {
                "event_id": str(
                    uuid5(
                        NAMESPACE_URL,
                        f"production-market-context:{trade_date}:{data_version}",
                    )
                )
            },
            {
                "$setOnInsert": {
                    "event_id": str(
                        uuid5(
                            NAMESPACE_URL,
                            f"production-market-context:{trade_date}:{data_version}",
                        )
                    ),
                    "event_type": "PRODUCTION_MARKET_CONTEXT_SYNCED",
                    "market": "CN",
                    "trade_date": _business_timestamp(trade_date),
                    "context_id": context.context_id,
                    "source_id": source.source_id,
                    "data_version": data_version,
                    "input_hash": source.content_hash,
                    "result_hash": context.content_hash,
                    "created_at": collected_at,
                    "schema_version": "alphaguard-production-data-event-v1",
                }
            },
            upsert=True,
        )
        return result
