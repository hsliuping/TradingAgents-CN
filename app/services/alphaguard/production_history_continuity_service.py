"""Create-only production MarketContext history and QFQ continuity audit.

This module does not change Factor, Regime, Strategy, execution, or evaluation
rules.  Historical market inputs are fetched once, then persisted through the
existing production MarketContext boundary under per-date immutable identities.
"""

from __future__ import annotations

import asyncio
from datetime import date, datetime, time
from typing import Any, Callable

from app.services.alphaguard.akshare_market_context_provider import (
    AKShareTencentMarketContextProvider,
)
from app.services.alphaguard.historical_market_context_service import (
    HistoricalMarketFetchResult,
    HistoricalMarketProvider,
)
from app.services.alphaguard.paper_storage import clean_document
from app.services.alphaguard.production_data_config import (
    production_market_context_history_policy,
    production_market_context_policy,
)
from app.services.alphaguard.production_market_context_service import (
    ProductionMarketContextError,
    ProductionMarketContextService,
)
from app.services.alphaguard.market_regime_engine import (
    calculate_regime_result,
)
from app.services.alphaguard.quant_research_pipeline import (
    QuantResearchPipeline,
)
from app.services.alphaguard.snapshot_data_resolver import (
    SnapshotDataResolver,
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


class ProductionHistoryContinuityError(RuntimeError):
    pass


class _PrefetchedDateProvider:
    """Expose one date from an already completed provider batch."""

    def __init__(self, fetched: HistoricalMarketFetchResult):
        self.fetched = fetched
        self.name = fetched.provider

    def capability_check(self) -> dict[str, Any]:
        return {
            "provider": self.fetched.provider,
            "provider_version": self.fetched.provider_version,
            "available": True,
            "prefetched": True,
        }

    def fetch(
        self,
        *,
        selected_dates: list[date],
        policy: dict[str, Any],
        progress: Callable[[dict[str, Any]], None] | None = None,
    ) -> HistoricalMarketFetchResult:
        if len(selected_dates) != 1:
            raise ProductionHistoryContinuityError(
                "prefetched production source requires exactly one trade date"
            )
        trade_date = selected_dates[0]
        if (
            trade_date not in self.fetched.source_payloads
            or trade_date not in self.fetched.context_payloads
        ):
            raise ProductionHistoryContinuityError(
                f"prefetched provider lacks {trade_date.isoformat()}"
            )
        return HistoricalMarketFetchResult(
            provider=self.fetched.provider,
            provider_version=self.fetched.provider_version,
            normalization_version=self.fetched.normalization_version,
            source_payloads={
                trade_date: self.fetched.source_payloads[trade_date]
            },
            context_payloads={
                trade_date: self.fetched.context_payloads[trade_date]
            },
            failures=self.fetched.failures,
        )


class ProductionHistoryContinuityService:
    """Backfill a fixed open-session window without touching research data."""

    def __init__(self, db):
        self.db = db
        self.policy = production_market_context_policy()
        self.history_policy = production_market_context_history_policy()
        if (
            self.history_policy["calculation_version"]
            != self.policy["calculation_version"]
        ):
            raise ProductionHistoryContinuityError(
                "history and current MarketContext calculation versions differ"
            )
        self.contexts = ProductionMarketContextService(db)

    async def select_trade_dates(
        self,
        *,
        through_trade_date: date,
        prior_session_count: int,
    ) -> list[date]:
        if prior_session_count <= 0:
            raise ValueError("prior_session_count must be positive")
        rows = (
            await self.db["trading_calendar"]
            .find(
                {
                    "market": "CN",
                    "is_open": True,
                    "session_date": {
                        "$lt": _business_timestamp(through_trade_date)
                    },
                }
            )
            .sort("session_date", -1)
            .limit(prior_session_count)
            .to_list(length=prior_session_count)
        )
        dates = sorted(
            {
                parsed
                for row in rows
                if (parsed := _as_date(row.get("session_date"))) is not None
            }
        )
        if len(dates) != prior_session_count:
            raise ProductionHistoryContinuityError(
                "persisted CN calendar lacks the required continuous history"
            )
        target = await self.db["trading_calendar"].find_one(
            {
                "market": "CN",
                "is_open": True,
                "session_date": _business_timestamp(through_trade_date),
            }
        )
        if target is None:
            raise ProductionHistoryContinuityError(
                "through_trade_date is not a persisted CN open session"
            )
        return dates

    def _provider_policy(self) -> dict[str, Any]:
        context = {
            key: self.policy[key]
            for key in (
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
        context["normalization_version"] = self.history_policy[
            "normalization_version"
        ]
        context["response_hash_scope"] = self.history_policy[
            "response_hash_scope"
        ]
        return {"market_context": context}

    async def sync(
        self,
        *,
        through_trade_date: date,
        prior_session_count: int = 120,
        execute: bool,
        provider: HistoricalMarketProvider | None = None,
        timeout_seconds: float = 7200,
        progress: Callable[[dict[str, Any]], None] | None = None,
        now: datetime | None = None,
    ) -> dict[str, Any]:
        dates = await self.select_trade_dates(
            through_trade_date=through_trade_date,
            prior_session_count=prior_session_count,
        )
        provider = provider or AKShareTencentMarketContextProvider()
        capability = provider.capability_check()
        if capability.get("available") is not True:
            raise ProductionHistoryContinuityError(
                f"provider unavailable: {capability.get('error_type', 'UNKNOWN')}"
            )
        fetched = await asyncio.wait_for(
            asyncio.to_thread(
                provider.fetch,
                selected_dates=dates,
                policy=self._provider_policy(),
                progress=progress,
            ),
            timeout=timeout_seconds,
        )
        expected = set(dates)
        if set(fetched.source_payloads) != expected or set(
            fetched.context_payloads
        ) != expected:
            raise ProductionHistoryContinuityError(
                "provider batch does not exactly cover the selected trade dates"
            )
        if fetched.failures:
            raise ProductionHistoryContinuityError(
                f"provider batch contains {len(fetched.failures)} failures"
            )
        collected_at = now or datetime.now()
        results = []
        prefetched = _PrefetchedDateProvider(fetched)
        for index, trade_date in enumerate(dates, start=1):
            result = await self.contexts.sync(
                trade_date=trade_date,
                execute=execute,
                provider=prefetched,
                timeout_seconds=timeout_seconds,
                now=collected_at,
            )
            results.append(result)
            if progress:
                progress(
                    {
                        "stage": "PRODUCTION_HISTORY_PERSISTENCE",
                        "completed": index,
                        "total": len(dates),
                        "trade_date": trade_date.isoformat(),
                        "source_action": result["source_action"],
                        "context_action": result["context_action"],
                    }
                )
        return {
            "status": (
                "READY"
                if all(
                    item["calculation_status"] == "READY"
                    for item in results
                )
                else "INSUFFICIENT_DATA"
            ),
            "write": execute,
            "through_trade_date": through_trade_date,
            "selected_trade_date_count": len(dates),
            "first_trade_date": dates[0],
            "last_trade_date": dates[-1],
            "normalization_version": fetched.normalization_version,
            "calculation_version": self.policy["calculation_version"],
            "ready_count": sum(
                item["calculation_status"] == "READY" for item in results
            ),
            "insufficient_count": sum(
                item["calculation_status"] != "READY" for item in results
            ),
            "source_created": sum(
                item["source_action"] == "CREATED" for item in results
            ),
            "source_reused": sum(
                item["source_action"] == "REUSED" for item in results
            ),
            "context_created": sum(
                item["context_action"] == "CREATED" for item in results
            ),
            "context_reused": sum(
                item["context_action"] == "REUSED" for item in results
            ),
            "results": results,
        }

    async def audit_pending_20d(
        self,
        *,
        backfill_run_id: str,
    ) -> dict[str, Any]:
        subjects_raw = await self.db["ag_eval_subjects"].find(
            {"lineage_ids.backfill_run_id": backfill_run_id}
        ).to_list(length=None)
        subjects = {
            str(row["subject_id"]): clean_document(row)
            for row in subjects_raw
        }
        labels = await self.db["ag_eval_horizon_labels"].find(
            {
                "subject_id": {"$in": sorted(subjects)},
                "horizon": "20D",
                "anchor_type": "DECISION_CLOSE",
                "status": "PENDING",
            }
        ).to_list(length=None)
        rows = []
        for label_raw in sorted(labels, key=lambda row: str(row["label_id"])):
            label = clean_document(label_raw)
            subject = subjects[str(label["subject_id"])]
            start = _as_date(subject.get("decision_trade_date"))
            end = _as_date(label.get("horizon_end_date"))
            if start is None or end is None:
                raise ProductionHistoryContinuityError(
                    "pending label lacks a valid evaluation window"
                )
            prices = (
                await self.db["stock_daily_quotes"]
                .find(
                    {
                        "symbol": subject["symbol"],
                        "market": subject["market"],
                        "period": "daily",
                        "price_adjustment_mode": "QFQ",
                        "trade_date": {
                            "$gte": _business_timestamp(start),
                            "$lte": _business_timestamp(end),
                        },
                    }
                )
                .sort("trade_date", 1)
                .to_list(length=None)
            )
            versions: dict[str, list[date]] = {}
            discontinuities = []
            previous = None
            for price in prices:
                trade_date = _as_date(price.get("trade_date"))
                version = str(price.get("price_data_version") or "")
                if trade_date is None:
                    continue
                versions.setdefault(version, []).append(trade_date)
                if previous is not None and previous != version:
                    discontinuities.append(
                        {
                            "trade_date": trade_date,
                            "from_version": previous,
                            "to_version": version,
                        }
                    )
                previous = version
            expected_dates = {
                parsed
                for row in await self.db["trading_calendar"]
                .find(
                    {
                        "market": subject["market"],
                        "is_open": True,
                        "session_date": {
                            "$gte": _business_timestamp(start),
                            "$lte": _business_timestamp(end),
                        },
                    }
                )
                .to_list(length=None)
                if (parsed := _as_date(row.get("session_date"))) is not None
            }
            observed_dates = {
                parsed
                for row in prices
                if (parsed := _as_date(row.get("trade_date"))) is not None
            }
            rows.append(
                {
                    "label_id": label["label_id"],
                    "evaluation_subject_id": label["subject_id"],
                    "symbol": subject["symbol"],
                    "decision_trade_date": start,
                    "target_trade_date": end,
                    "label_price_data_version": label.get(
                        "price_data_version"
                    ),
                    "versions": {
                        key: {
                            "count": len(value),
                            "first_trade_date": min(value),
                            "last_trade_date": max(value),
                        }
                        for key, value in sorted(versions.items())
                    },
                    "discontinuities": discontinuities,
                    "missing_dates": sorted(expected_dates - observed_dates),
                    "status": label["status"],
                    "safe_resolution": (
                        "UNIFIED_VERSION_AVAILABLE"
                        if len(versions) == 1
                        and not discontinuities
                        and expected_dates == observed_dates
                        else "PENDING_VERSION_DISCONTINUITY"
                    ),
                }
            )
        return {
            "backfill_run_id": backfill_run_id,
            "pending_label_count": len(rows),
            "labels": rows,
        }

    async def verify_locked_regimes(
        self,
        *,
        trade_date: date,
    ) -> dict[str, Any]:
        """Recalculate in memory with Snapshot-locked Champion inputs.

        This intentionally does not call ``MarketRegimeEngine.calculate``:
        verification must not create a result under a default, non-Champion
        version identity.
        """

        snapshots = (
            await self.db["ag_evidence_snapshots"]
            .find(
                {
                    "market": "CN",
                    "trade_date": _business_timestamp(trade_date),
                }
            )
            .sort("symbol", 1)
            .to_list(length=None)
        )
        resolver = SnapshotDataResolver(self.db)
        pipeline = QuantResearchPipeline(self.db)
        results = []
        for raw in snapshots:
            snapshot = clean_document(raw)
            data = await resolver.resolve(
                snapshot["snapshot_id"],
                user_id=snapshot["user_id"],
            )
            if not data.snapshot.champion_version_refs:
                raise ProductionHistoryContinuityError(
                    "production Snapshot lacks locked Champion refs"
                )
            _, _, regime_config, _ = await pipeline._locked_champion_inputs(
                data.snapshot.champion_version_refs
            )
            recalculated = calculate_regime_result(data, config=regime_config)
            stored = clean_document(
                await self.db["ag_regime_results"].find_one(
                    {
                        "snapshot_id": data.snapshot.snapshot_id,
                        "regime_version": regime_config["regime_version"],
                    }
                )
            )
            if stored is None:
                status = "MISSING_CREATE_ONLY_RESULT"
            elif (
                stored.get("input_hash") != recalculated.input_hash
                or stored.get("regime_result_id")
                != recalculated.regime_result_id
            ):
                status = "INTEGRITY_CONFLICT"
            else:
                status = "VERIFIED_UNCHANGED"
            results.append(
                {
                    "symbol": data.snapshot.symbol,
                    "snapshot_id": data.snapshot.snapshot_id,
                    "market_context_id": data.snapshot.market_context_id,
                    "benchmark_ref_count": len(data.benchmark_prices),
                    "locked_regime_version": regime_config[
                        "regime_version"
                    ],
                    "stored_regime_result_id": (
                        stored.get("regime_result_id") if stored else None
                    ),
                    "stored_status": (
                        stored.get("calculation_status") if stored else None
                    ),
                    "recalculated_status": (
                        recalculated.calculation_status
                    ),
                    "stored_input_hash": (
                        stored.get("input_hash") if stored else None
                    ),
                    "recalculated_input_hash": recalculated.input_hash,
                    "verification_status": status,
                }
            )
        return {
            "trade_date": trade_date,
            "snapshot_count": len(snapshots),
            "verified_unchanged_count": sum(
                item["verification_status"] == "VERIFIED_UNCHANGED"
                for item in results
            ),
            "integrity_conflict_count": sum(
                item["verification_status"] == "INTEGRITY_CONFLICT"
                for item in results
            ),
            "missing_result_count": sum(
                item["verification_status"]
                == "MISSING_CREATE_ONLY_RESULT"
                for item in results
            ),
            "results": results,
        }
