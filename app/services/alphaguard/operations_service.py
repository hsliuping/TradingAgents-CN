"""AlphaGuard operational truth assembled from existing versioned subsystems."""

from __future__ import annotations

import asyncio
from datetime import date, datetime, timezone
from pathlib import Path
import subprocess
import time
from typing import Any
from uuid import NAMESPACE_URL, uuid5
from zoneinfo import ZoneInfo

import yaml

from app.core.alphaguard_config import (
    load_alphaguard_safety_settings,
    validate_alphaguard_startup_safety,
)
from app.services.alphaguard.champion_resolver import assignment_hash
from app.services.alphaguard.operations_alert_service import OperationsAlertService
from app.services.alphaguard.paper_storage import clean_document, safe_error_message
from app.services.alphaguard.production_data_config import (
    production_market_context_policy,
)
from tradingagents.alphaguard.mongo_indexes import ALPHAGUARD_INDEX_SPECS
from tradingagents.alphaguard.experiment_schemas import ChampionAssignment
from tradingagents.alphaguard.operations_schemas import (
    DataReadinessStatus,
    JobHealth,
    ServiceHealth,
    SystemReadinessReport,
    operations_hash,
)
from app.services.alphaguard.candidate_recommendation_service import (
    CandidateRecommendationService,
)


ROOT = Path(__file__).resolve().parents[3]
CN_MARKET_TIMEZONE = ZoneInfo("Asia/Shanghai")
REQUIRED_CHAMPION_TYPES = {
    "FACTOR_WEIGHT",
    "FACTOR_SET",
    "REGIME_CONFIG",
    "STRATEGY_CONFIG",
}


def _cn_market_now() -> datetime:
    """Return the persisted CN-market wall clock without timezone metadata."""
    return datetime.now(CN_MARKET_TIMEZONE).replace(tzinfo=None)

JOB_REGISTRY: tuple[dict[str, Any], ...] = (
    {"job_name": "trading_calendar_sync", "worker": "scheduler", "scheduler_id": None},
    {"job_name": "price_sync", "worker": "scheduler", "scheduler_id": "akshare_historical_sync"},
    {"job_name": "financial_sync", "worker": "scheduler", "scheduler_id": "akshare_financial_sync"},
    {"job_name": "news_announcement_sync", "worker": "scheduler", "scheduler_id": "news_sync"},
    {"job_name": "candidate_reconciliation", "worker": "operations-worker", "scheduler_id": None},
    {"job_name": "snapshot_generation", "worker": "analysis-worker", "scheduler_id": None},
    {"job_name": "factor_strategy_calculation", "worker": "analysis-worker", "scheduler_id": None},
    {"job_name": "analysis_tasks", "worker": "analysis-worker", "scheduler_id": None},
    {"job_name": "process_execution_outbox", "worker": "api-scheduler", "scheduler_id": "alphaguard_paper_outbox", "collection": "ag_paper_job_runs", "job_type": "process_execution_outbox"},
    {"job_name": "matching", "worker": "api-scheduler", "scheduler_id": "alphaguard_paper_matching", "collection": "ag_paper_job_runs", "job_type": "match_orders_for_trade_date"},
    {"job_name": "settlement_recovery", "worker": "api-scheduler", "scheduler_id": "alphaguard_paper_settlement", "collection": "ag_paper_job_runs", "job_type": "settle_pending_fills"},
    {"job_name": "order_expiry", "worker": "api-scheduler", "scheduler_id": "alphaguard_paper_expiry", "collection": "ag_paper_job_runs", "job_type": "expire_orders"},
    {"job_name": "t1_unlock", "worker": "api-scheduler", "scheduler_id": "alphaguard_paper_lot_roll", "collection": "ag_paper_job_runs", "job_type": "roll_position_lot_availability"},
    {"job_name": "account_snapshot", "worker": "api-scheduler", "scheduler_id": "alphaguard_paper_account_snapshot", "collection": "ag_paper_job_runs", "job_type": "create_daily_account_snapshots"},
    {"job_name": "evaluation_pipeline", "worker": "api-scheduler", "scheduler_id": "alphaguard_evaluation_worker", "collection": "ag_eval_runs"},
    {"job_name": "experiment_worker", "worker": "api-scheduler", "scheduler_id": "alphaguard_experiment_consumer", "collection": "ag_exp_task_runs"},
    {"job_name": "challenger_scheduler", "worker": "api-scheduler", "scheduler_id": "alphaguard_challenger_scheduler", "collection": "ag_exp_task_runs", "job_type": "PAPER_CHALLENGER"},
    {"job_name": "challenger_runtime", "worker": "api-scheduler", "scheduler_id": "alphaguard_challenger_runtime", "collection": "ag_exp_challenger_runs"},
    {"job_name": "promotion_saga_recovery", "worker": "api-scheduler", "scheduler_id": "alphaguard_promotion_saga_recovery", "collection": "ag_exp_task_runs", "job_type": "PROMOTION_SAGA_RECOVERY"},
    {"job_name": "candidate_recommendations", "worker": "api-scheduler", "scheduler_id": "alphaguard_candidate_recommendations", "collection": "ag_candidate_recommendation_runs"},
)


async def _count(collection, query: dict | None = None) -> int:
    if hasattr(collection, "count_documents"):
        return int(await collection.count_documents(query or {}))
    if query:
        return len(await collection.find(query).to_list(length=None))
    if hasattr(collection, "count"):
        return int(collection.count())
    return len(await collection.find({}).to_list(length=None))


async def _count_negative(collection, field: str) -> int:
    """Count negative numeric values without relying on a test-double query dialect."""
    rows = await collection.find({}).to_list(length=None)
    count = 0
    for row in rows:
        value = row.get(field)
        try:
            if value is not None and value < 0:
                count += 1
        except TypeError:
            # A malformed value is handled by schema/integrity checks elsewhere.
            continue
    return count


async def _date_bounds(
    collection,
    date_fields: tuple[str, ...],
    *,
    query: dict[str, Any] | None = None,
) -> tuple[date | None, date | None]:
    """Read bounded date samples so readiness never materializes market history."""
    starts: list[date] = []
    ends: list[date] = []
    for field in date_fields:
        field_query = dict(query or {})
        field_query[field] = {"$nin": [None, ""]}
        ascending = (
            await collection.find(field_query, {field: 1, "_id": 0})
            .sort(field, 1)
            .limit(16)
            .to_list(length=16)
        )
        descending = (
            await collection.find(field_query, {field: 1, "_id": 0})
            .sort(field, -1)
            .limit(16)
            .to_list(length=16)
        )
        parsed_starts = [
            parsed
            for row in ascending
            if (parsed := _as_date(row.get(field))) is not None
        ]
        parsed_ends = [
            parsed
            for row in descending
            if (parsed := _as_date(row.get(field))) is not None
        ]
        if parsed_starts:
            starts.append(min(parsed_starts))
        if parsed_ends:
            ends.append(max(parsed_ends))
    return (min(starts) if starts else None, max(ends) if ends else None)


def _as_datetime(value: Any) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.replace(tzinfo=None)
    if isinstance(value, date):
        return datetime.combine(value, datetime.min.time())
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        return parsed.replace(tzinfo=None)
    except (TypeError, ValueError):
        return None


def _as_date(value: Any) -> date | None:
    parsed = _as_datetime(value)
    return parsed.date() if parsed else None


def _git_value(*args: str, fallback: str = "unknown") -> str:
    try:
        return subprocess.run(
            ["git", *args],
            cwd=ROOT,
            capture_output=True,
            check=True,
            text=True,
            timeout=3,
        ).stdout.strip() or fallback
    except Exception:
        return fallback


class AlphaGuardOperationsService:
    def __init__(self, db, *, redis_client=None, scheduler=None):
        self.db = db
        self.redis = redis_client
        self.scheduler = scheduler
        self.alerts = OperationsAlertService(db)

    async def service_health(self, *, now: datetime | None = None) -> list[ServiceHealth]:
        now = now or _cn_market_now()
        services = [
            ServiceHealth(
                service_name="FASTAPI",
                status="HEALTHY",
                required=True,
                reachable=True,
                latency_ms=0,
                last_checked_at=now,
                last_success_at=now,
                details={"process": "alive"},
            )
        ]
        start = time.perf_counter()
        try:
            if hasattr(self.db, "command"):
                await self.db.command("ping")
            latency = (time.perf_counter() - start) * 1000
            services.append(
                ServiceHealth(
                    service_name="MONGODB",
                    status="HEALTHY",
                    required=True,
                    reachable=True,
                    latency_ms=latency,
                    last_checked_at=now,
                    last_success_at=now,
                    details={"database": getattr(self.db, "name", "test-double")},
                )
            )
        except Exception as exc:
            services.append(
                ServiceHealth(
                    service_name="MONGODB",
                    status="UNHEALTHY",
                    required=True,
                    reachable=False,
                    last_checked_at=now,
                    error_code="MONGODB_UNAVAILABLE",
                    sanitized_message=safe_error_message(exc),
                    details={},
                )
            )

        services.append(await self._index_health(now))

        if self.redis is None:
            services.append(
                ServiceHealth(
                    service_name="REDIS",
                    status="UNKNOWN",
                    required=True,
                    reachable=None,
                    last_checked_at=now,
                    error_code="REDIS_CHECK_UNAVAILABLE",
                    sanitized_message="Redis client was not supplied to this check",
                    details={},
                )
            )
        else:
            start = time.perf_counter()
            try:
                reachable = bool(await self.redis.ping())
                services.append(
                    ServiceHealth(
                        service_name="REDIS",
                        status="HEALTHY" if reachable else "UNHEALTHY",
                        required=True,
                        reachable=reachable,
                        latency_ms=(time.perf_counter() - start) * 1000,
                        last_checked_at=now,
                        last_success_at=now if reachable else None,
                        error_code=None if reachable else "REDIS_UNAVAILABLE",
                        details={},
                    )
                )
            except Exception as exc:
                services.append(
                    ServiceHealth(
                        service_name="REDIS",
                        status="UNHEALTHY",
                        required=True,
                        reachable=False,
                        last_checked_at=now,
                        error_code="REDIS_UNAVAILABLE",
                        sanitized_message=safe_error_message(exc),
                        details={},
                    )
                )

        scheduler_running = bool(
            self.scheduler is not None
            and getattr(self.scheduler, "running", False)
        )
        services.append(
            ServiceHealth(
                service_name="SCHEDULER",
                status="HEALTHY" if scheduler_running else "DEGRADED",
                required=True,
                reachable=scheduler_running,
                last_checked_at=now,
                last_success_at=now if scheduler_running else None,
                error_code=None if scheduler_running else "SCHEDULER_NOT_VISIBLE",
                sanitized_message=(
                    None
                    if scheduler_running
                    else "Scheduler is not visible in the current process"
                ),
                details={},
            )
        )

        worker_details = await self._worker_visibility()
        for service_name, visible in worker_details.items():
            services.append(
                ServiceHealth(
                    service_name=service_name,
                    status="HEALTHY" if visible else "DEGRADED",
                    required=True,
                    reachable=visible,
                    last_checked_at=now,
                    last_success_at=now if visible else None,
                    error_code=None if visible else "WORKER_STALE",
                    sanitized_message=None if visible else "No fresh worker heartbeat",
                    details={},
                )
            )
        return services

    async def _index_health(self, now: datetime) -> ServiceHealth:
        missing: list[str] = []
        try:
            for collection_name, specs in ALPHAGUARD_INDEX_SPECS.items():
                existing = {
                    item["name"]
                    for item in await self.db[collection_name]
                    .list_indexes()
                    .to_list(length=None)
                }
                missing.extend(
                    f"{collection_name}.{spec['name']}"
                    for spec in specs
                    if spec["name"] not in existing
                )
            healthy = not missing
            return ServiceHealth(
                service_name="ALPHAGUARD_INDEXES",
                status="HEALTHY" if healthy else "UNHEALTHY",
                required=True,
                reachable=True,
                last_checked_at=now,
                last_success_at=now if healthy else None,
                error_code=None if healthy else "REQUIRED_INDEXES_MISSING",
                sanitized_message=(
                    None
                    if healthy
                    else f"{len(missing)} required create-only indexes are missing"
                ),
                details={
                    "missing_count": len(missing),
                    "missing_indexes": missing[:20],
                },
            )
        except Exception as exc:
            return ServiceHealth(
                service_name="ALPHAGUARD_INDEXES",
                status="UNKNOWN",
                required=True,
                reachable=None,
                last_checked_at=now,
                error_code="INDEX_CHECK_FAILED",
                sanitized_message=safe_error_message(exc),
                details={},
            )

    async def _worker_visibility(self) -> dict[str, bool]:
        result = {"QUEUE_WORKER": False, "ANALYSIS_WORKER": False}
        if self.redis is None:
            return result
        try:
            result["QUEUE_WORKER"] = bool(await self.redis.exists("alphaguard:worker:queue"))
            keys = []
            if hasattr(self.redis, "scan_iter"):
                async for key in self.redis.scan_iter(match="worker:*:heartbeat"):
                    keys.append(key)
                    if len(keys) >= 1:
                        break
            result["ANALYSIS_WORKER"] = bool(keys)
        except Exception:
            pass
        return result

    async def data_readiness(self, *, now: datetime | None = None) -> list[DataReadinessStatus]:
        now = now or _cn_market_now()
        statuses: list[DataReadinessStatus] = []
        statuses.append(
            await self._collection_readiness(
                "TRADING_CALENDAR",
                ("trading_calendar",),
                now=now,
                market="CN",
                required_for=["PAPER_EXECUTION", "EVALUATION", "CHAMPION_EFFECTIVE_DATE"],
                date_fields=("session_date", "trade_date", "date"),
                empty_reason="TRADING_CALENDAR_MISSING",
            )
        )
        statuses.append(await self._qfq_readiness(now))
        statuses.append(
            await self._collection_readiness(
                "RAW_PRICE_DATA",
                ("stock_daily_quotes", "market_quotes"),
                now=now,
                market="CN",
                required_for=["SNAPSHOT", "EXECUTION_SNAPSHOT"],
                date_fields=("trade_date", "date", "timestamp"),
                empty_reason="RAW_PRICE_DATA_MISSING",
            )
        )
        for component, collections, required_for, reason in (
            ("FINANCIAL_DATA", ("financial_data", "stock_financial_data"), ["SNAPSHOT"], "FINANCIAL_DATA_MISSING"),
            ("NEWS_DATA", ("stock_news", "news_data"), ["SNAPSHOT"], "NEWS_DATA_MISSING"),
            ("ANNOUNCEMENT_DATA", ("stock_announcements", "announcements"), ["SNAPSHOT"], "ANNOUNCEMENT_DATA_MISSING"),
        ):
            statuses.append(
                await self._collection_readiness(
                    component,
                    collections,
                    now=now,
                    market="CN",
                    required_for=required_for,
                    date_fields=("trade_date", "date", "published_at", "created_at"),
                    empty_reason=reason,
                )
            )
        statuses.append(await self._market_context_readiness(now))
        statuses.append(await self._industry_readiness(now))
        statuses.append(await self._model_readiness(now))
        statuses.append(await self._champion_readiness(now))
        evaluation_count = await _count(self.db["ag_eval_subjects"])
        mature_count = await _count(
            self.db["ag_eval_horizon_labels"], {"status": "CALCULATED"}
        )
        statuses.append(
            DataReadinessStatus(
                component="EVALUATION_SAMPLES",
                status="READY" if evaluation_count and mature_count else "NOT_READY",
                market="CN",
                record_count=evaluation_count,
                required_for=["EVALUATION", "EXPERIMENT_COMPARISON"],
                blocking_reasons=(
                    [] if evaluation_count and mature_count else ["EVALUATION_SAMPLES_EMPTY"]
                ),
                warnings=[f"mature_horizon_labels={mature_count}"],
                last_checked_at=now,
            )
        )
        experiment_count = await _count(
            self.db["ag_exp_runs"], {"status": "COMPLETED"}
        )
        statuses.append(
            DataReadinessStatus(
                component="EXPERIMENT_SAMPLES",
                status="READY" if experiment_count else "NOT_READY",
                market="CN",
                record_count=experiment_count,
                required_for=["EXPERIMENT_COMPARISON", "PROMOTION"],
                blocking_reasons=[] if experiment_count else ["EXPERIMENT_SAMPLES_EMPTY"],
                last_checked_at=now,
            )
        )
        challenger_accounts = await _count(
            self.db["ag_paper_accounts"],
            {
                "account_type": "PAPER_CHALLENGER",
                "market": "CN",
                "status": "ACTIVE",
            },
        )
        challenger_framework = bool(
            challenger_accounts
            and await _count(self.db["ag_exp_promotion_policies"])
            and await _count(self.db["ag_exp_component_versions"])
        )
        pending_jobs = await _count(
            self.db["ag_exp_task_runs"],
            {"job_type": "PAPER_CHALLENGER", "status": "PENDING"},
        )
        run_count = await _count(self.db["ag_exp_challenger_runs"])
        failure_count = await _count(
            self.db["ag_exp_challenger_runs"], {"status": "FAILED"}
        )
        statuses.append(
            DataReadinessStatus(
                component="CHALLENGER_PIPELINE",
                status="READY" if challenger_framework else "NOT_READY",
                market="CN",
                record_count=challenger_accounts,
                required_for=["PAPER_CHALLENGER", "PROMOTION"],
                blocking_reasons=(
                    []
                    if challenger_framework
                    else [
                        "PAPER_CHALLENGER_ACCOUNT_OR_RUNTIME_DEPENDENCY_MISSING"
                    ]
                ),
                warnings=[
                    f"run_count={run_count}",
                    f"failed_run_count={failure_count}",
                    f"pending_job_count={pending_jobs}",
                    "model Profile and budget readiness are enforced when a Challenger runs",
                    "no active Challenger is required for runtime readiness",
                ],
                last_checked_at=now,
            )
        )
        return statuses

    async def _industry_readiness(self, now: datetime) -> DataReadinessStatus:
        chosen = None
        count = 0
        for name in ("industry_history", "stock_industry_history"):
            current = await _count(self.db[name])
            if current:
                chosen, count = name, current
                break
        if not chosen:
            return DataReadinessStatus(
                component="INDUSTRY_HISTORY",
                status="NOT_READY",
                market="CN",
                record_count=0,
                required_for=["ATTRIBUTION", "INDUSTRY_EXPOSURE"],
                blocking_reasons=["INDUSTRY_HISTORY_MISSING"],
                last_checked_at=now,
            )
        coverage_start, coverage_end = await _date_bounds(
            self.db[chosen],
            ("effective_from", "trade_date", "date"),
        )
        current_only = await _count(
            self.db[chosen], {"history_coverage_status": "CURRENT_ONLY"}
        )
        complete = coverage_start is not None and current_only == 0
        return DataReadinessStatus(
            component="INDUSTRY_HISTORY",
            status="READY" if complete else "PARTIAL",
            market="CN",
            coverage_start=coverage_start,
            coverage_end=coverage_end,
            record_count=count,
            required_for=["ATTRIBUTION", "INDUSTRY_EXPOSURE"],
            blocking_reasons=(
                [] if complete else ["INDUSTRY_HISTORY_CURRENT_ONLY"]
            ),
            warnings=[
                f"source_collection={chosen}",
                f"current_only_records={current_only}",
            ],
            last_checked_at=now,
        )

    async def _collection_readiness(
        self,
        component: str,
        collections: tuple[str, ...],
        *,
        now: datetime,
        market: str,
        required_for: list[str],
        date_fields: tuple[str, ...],
        empty_reason: str,
    ) -> DataReadinessStatus:
        chosen = None
        count = 0
        for name in collections:
            current = await _count(self.db[name])
            if current:
                chosen, count = name, current
                break
        if not chosen:
            return DataReadinessStatus(
                component=component,
                status="NOT_READY",
                market=market,
                record_count=0,
                required_for=required_for,
                blocking_reasons=[empty_reason],
                last_checked_at=now,
            )
        coverage_start, coverage_end = await _date_bounds(
            self.db[chosen], date_fields
        )
        return DataReadinessStatus(
            component=component,
            status="READY" if coverage_start is not None else "PARTIAL",
            market=market,
            coverage_start=coverage_start,
            coverage_end=coverage_end,
            record_count=count,
            required_for=required_for,
            blocking_reasons=(
                []
                if coverage_start is not None
                else [f"{component}_DATE_COVERAGE_UNKNOWN"]
            ),
            warnings=[f"source_collection={chosen}"],
            last_checked_at=now,
        )

    async def _qfq_readiness(self, now: datetime) -> DataReadinessStatus:
        query = {
            "$or": [
                {"price_adjustment_mode": {"$in": ["QFQ", "qfq"]}},
                {"adjustment_mode": {"$in": ["QFQ", "qfq"]}},
            ],
            "price_data_version": {"$nin": [None, ""]},
        }
        count = await _count(self.db["stock_daily_quotes"], query)
        coverage_start, coverage_end = await _date_bounds(
            self.db["stock_daily_quotes"], ("trade_date",), query=query
        )
        ready = bool(count and coverage_start is not None)
        return DataReadinessStatus(
            component="QFQ_PRICE_DATA",
            status="READY" if ready else "NOT_READY",
            market="CN",
            coverage_start=coverage_start,
            coverage_end=coverage_end,
            record_count=count,
            required_for=["EVALUATION", "HISTORICAL_REPLAY"],
            blocking_reasons=[] if ready else ["QFQ_DATA_MISSING"],
            last_checked_at=now,
        )

    async def _market_context_readiness(
        self,
        now: datetime,
    ) -> DataReadinessStatus:
        policy = production_market_context_policy()
        query = {
            "market": "CN",
            "calculation_version": policy["calculation_version"],
            "calculation_status": "READY",
            "available_at": {"$lte": now},
            "collected_at": {"$lte": now},
        }
        count = await _count(self.db["ag_market_contexts"], query)
        coverage_start, coverage_end = await _date_bounds(
            self.db["ag_market_contexts"], ("trade_date",), query=query
        )
        ready = bool(count and coverage_start is not None)
        return DataReadinessStatus(
            component="MARKET_CONTEXT",
            status="READY" if ready else "NOT_READY",
            market="CN",
            coverage_start=coverage_start,
            coverage_end=coverage_end,
            record_count=count,
            required_for=["REGIME"],
            blocking_reasons=(
                []
                if ready
                else ["MARKET_CONTEXT_CURRENT_VERSION_MISSING"]
            ),
            warnings=[
                "source_collection=ag_market_contexts",
                f"calculation_version={policy['calculation_version']}",
            ],
            last_checked_at=now,
        )

    async def _model_readiness(self, now: datetime) -> DataReadinessStatus:
        from .model_runtime_status_service import ModelRuntimeStatusService

        runtime = await ModelRuntimeStatusService(self.db).status(admin=True)
        profiles = runtime["profiles"]
        required = [
            item
            for item in profiles
            if item["role"]
            in {"RESEARCH_AGENT", "NORMAL_TRADER", "TOP_RISK_REVIEWER"}
        ]
        status = (
            "READY"
            if runtime["status"] == "READY"
            else "NOT_CONFIGURED"
            if runtime["status"] == "NOT_CONFIGURED"
            else "PARTIAL"
        )
        reasons = []
        for item in required:
            if not item["configured"]:
                reasons.append(f"{item['role']}_MODEL_NOT_CONFIGURED")
            elif item["capability"] != "READY":
                reasons.append(
                    f"{item['role']}_CAPABILITY_{item['capability']}"
                )
        return DataReadinessStatus(
            component="MODEL_PROVIDER",
            status=status,
            record_count=len(profiles),
            required_for=["NORMAL_MODEL", "TOP_REVIEW"],
            blocking_reasons=sorted(set(reasons)),
            warnings=[
                f"registered_profile_count={len(profiles)}",
                "readiness requires exact persisted profile, prompt, credential, and network capability",
            ],
            last_checked_at=now,
        )

    async def _champion_readiness(self, now: datetime) -> DataReadinessStatus:
        assignments = [
            clean_document(row)
            for row in await self.db["ag_exp_champion_assignments"].find(
                {"status": "ACTIVE"}
            ).to_list(length=None)
        ]
        versions = {
            row.get("version_ref"): clean_document(row)
            for row in await self.db["ag_exp_component_versions"].find({}).to_list(
                length=None
            )
        }
        reasons: list[str] = []
        identities: set[tuple[str, str, str]] = set()
        types: set[str] = set()
        for item in assignments:
            identity = (
                str(item.get("component_type")),
                str(item.get("component_key")),
                str(item.get("market")),
            )
            if identity in identities:
                reasons.append("MULTIPLE_ACTIVE_CHAMPIONS")
            identities.add(identity)
            types.add(identity[0])
            if item.get("current_version_ref") not in versions:
                reasons.append("CHAMPION_VERSION_MISSING")
            try:
                expected = assignment_hash(ChampionAssignment.model_validate(item))
                if item.get("assignment_hash") != expected:
                    reasons.append("CHAMPION_HASH_MISMATCH")
            except Exception:
                reasons.append("CHAMPION_HASH_INVALID")
        if not REQUIRED_CHAMPION_TYPES.issubset(types):
            reasons.append("CHAMPION_SLOTS_INCOMPLETE")
        incomplete_sagas = await _count(
            self.db["ag_exp_promotion_sagas"],
            {"status": {"$nin": ["COMMITTED", "ROLLED_BACK", "FAILED"]}},
        )
        if incomplete_sagas:
            reasons.append("PROMOTION_SAGA_INCOMPLETE")
        return DataReadinessStatus(
            component="CHAMPION_ASSIGNMENTS",
            status="READY" if not reasons else "NOT_READY",
            market="CN",
            record_count=len(assignments),
            required_for=["QUANT_RESEARCH", "EXPERIMENT"],
            blocking_reasons=sorted(set(reasons)),
            warnings=(
                ["effective dates require persisted trading-calendar verification"]
                if not await _count(self.db["trading_calendar"])
                else []
            ),
            last_checked_at=now,
        )

    async def job_health(self, *, now: datetime | None = None) -> list[JobHealth]:
        now = now or _cn_market_now()
        result: list[JobHealth] = []
        for descriptor in JOB_REGISTRY:
            scheduler_job = (
                self.scheduler.get_job(descriptor["scheduler_id"])
                if self.scheduler is not None and descriptor.get("scheduler_id")
                else None
            )
            query = {}
            if descriptor.get("job_type"):
                query["job_type"] = descriptor["job_type"]
            raw = None
            if descriptor.get("collection"):
                raw = clean_document(
                    await self.db[descriptor["collection"]].find_one(
                        query, sort=[("created_at", -1)]
                    )
                )
            status = str((raw or {}).get("status") or "")
            mapped = {
                "RUNNING": "RUNNING",
                "COMPLETED": "SUCCESS",
                "SUCCESS": "SUCCESS",
                "FAILED": "FAILED",
                "PENDING": "IDLE",
                "RETRYING": "RETRYING",
                "DEAD_LETTER": "FAILED",
            }.get(status, "IDLE" if scheduler_job else "DISABLED")
            next_run = _as_datetime(
                getattr(scheduler_job, "next_run_time", None)
            )
            backlog = (
                await _count(
                    self.db[descriptor["collection"]],
                    {"status": {"$in": ["PENDING", "FAILED"]}},
                )
                if descriptor.get("collection")
                else None
            )
            result.append(
                JobHealth(
                    job_name=descriptor["job_name"],
                    worker_name=descriptor["worker"],
                    status=mapped,
                    last_run_id=(
                        str(
                            (raw or {}).get("job_id")
                            or (raw or {}).get("evaluation_job_id")
                            or (raw or {}).get("task_run_id")
                        )
                        if raw
                        else None
                    ),
                    last_started_at=_as_datetime((raw or {}).get("started_at")),
                    last_finished_at=_as_datetime(
                        (raw or {}).get("finished_at")
                        or (raw or {}).get("completed_at")
                    ),
                    last_success_at=(
                        _as_datetime(
                            (raw or {}).get("finished_at")
                            or (raw or {}).get("completed_at")
                        )
                        if mapped == "SUCCESS"
                        else None
                    ),
                    next_scheduled_at=next_run,
                    retry_count=int((raw or {}).get("attempt_count") or 0),
                    backlog_count=backlog,
                    error_code=(
                        str((raw or {}).get("error_type") or "JOB_FAILED")
                        if mapped == "FAILED"
                        else None
                    ),
                    sanitized_message=(
                        str(
                            (raw or {}).get("error")
                            or (raw or {}).get("last_error")
                        )
                        if mapped == "FAILED"
                        else None
                    ),
                )
            )
        return result

    async def integrity(self) -> dict[str, Any]:
        checks: list[dict[str, Any]] = []
        checks.append(
            {
                "check": "negative_cash",
                "count": await _count_negative(
                    self.db["ag_paper_accounts"], "cash_available"
                ),
            }
        )
        checks.append(
            {
                "check": "negative_position",
                "count": await _count_negative(
                    self.db["ag_paper_positions"], "quantity"
                ),
            }
        )
        checks.append(
            {
                "check": "outbox_dead_letter",
                "count": await _count(
                    self.db["ag_execution_outbox"], {"status": "DEAD_LETTER"}
                ),
            }
        )
        checks.append(
            {
                "check": "settlement_saga_stuck",
                "count": await _count(
                    self.db["ag_settlement_records"],
                    {
                        "status": {
                            "$in": [
                                "PREPARED",
                                "ACCOUNT_APPLIED",
                                "POSITION_APPLIED",
                                "LEDGER_APPLIED",
                                "COMPENSATION_REQUIRED",
                            ]
                        }
                    },
                ),
            }
        )
        checks.append(
            {
                "check": "promotion_saga_stuck",
                "count": await _count(
                    self.db["ag_exp_promotion_sagas"],
                    {
                        "status": {
                            "$nin": ["COMMITTED", "ROLLED_BACK", "FAILED"]
                        }
                    },
                ),
            }
        )
        missing_indexes: list[str] = []
        for collection_name, specs in ALPHAGUARD_INDEX_SPECS.items():
            existing = {
                item["name"]
                for item in await self.db[collection_name].list_indexes().to_list(
                    length=None
                )
            }
            missing_indexes.extend(
                f"{collection_name}.{spec['name']}"
                for spec in specs
                if spec["name"] not in existing
            )
        checks.append(
            {"check": "required_indexes_missing", "count": len(missing_indexes)}
        )
        return {
            "status": (
                "PASS"
                if all(item["count"] == 0 for item in checks)
                else "FAIL"
            ),
            "checks": checks,
            "missing_indexes": missing_indexes,
            "checked_at": datetime.utcnow(),
        }

    async def versions(self) -> dict[str, Any]:
        config_versions = {}
        for path in (
            "config/alphaguard/risk/risk_policy_v1.yaml",
            "config/alphaguard/paper/account_policy_v1.yaml",
            "config/alphaguard/paper/execution_policy_v1.yaml",
            "config/alphaguard/paper/fee_policy_v1.yaml",
            "config/alphaguard/evaluation/evaluation_policy_v1.yaml",
            "config/alphaguard/experiments/promotion_policy_v1.yaml",
        ):
            try:
                payload = yaml.safe_load((ROOT / path).read_text(encoding="utf-8"))
                config_versions[path] = {
                    key: value
                    for key, value in payload.items()
                    if key
                    in {
                        "risk_policy_id",
                        "account_policy_id",
                        "execution_policy_id",
                        "fee_policy_id",
                        "evaluation_policy_id",
                        "policy_id",
                        "version",
                        "policy_version",
                        "matching_engine_version",
                    }
                }
            except Exception as exc:
                config_versions[path] = {"error": safe_error_message(exc)}
        champions = [
            {
                key: row.get(key)
                for key in (
                    "champion_slot_id",
                    "component_type",
                    "component_key",
                    "market",
                    "current_version_ref",
                    "effective_from_trade_date",
                    "status",
                )
            }
            for row in await self.db["ag_exp_champion_assignments"].find({}).to_list(
                length=None
            )
        ]
        return {
            "code_commit": _git_value("rev-parse", "HEAD"),
            "code_tree_hash": _git_value("rev-parse", "HEAD^{tree}"),
            "build_version": (
                (ROOT / "VERSION").read_text(encoding="utf-8").strip()
                if (ROOT / "VERSION").exists()
                else "unknown"
            ),
            "configs": config_versions,
            "champions": champions,
            "consensus_version": "consensus-policy-v1",
            "schema_version": "alphaguard-operations-v1",
        }

    async def readiness(
        self,
        *,
        now: datetime | None = None,
        persist_alerts: bool = True,
    ) -> SystemReadinessReport:
        now = now or _cn_market_now()
        safety = load_alphaguard_safety_settings()
        services, data, jobs = await asyncio.gather(
            self.service_health(now=now),
            self.data_readiness(now=now),
            self.job_health(now=now),
        )
        unsafe_reasons: list[str] = []
        try:
            validate_alphaguard_startup_safety(safety)
        except Exception as exc:
            unsafe_reasons.append(safe_error_message(exc))
        if safety.live_trading_enabled:
            unsafe_reasons.append("LIVE_MODE_ENABLED")
        required_services_bad = [
            item.service_name
            for item in services
            if item.required and item.status != "HEALTHY"
        ]
        blocking_data = [
            reason
            for item in data
            if item.status in {"NOT_READY", "NOT_CONFIGURED", "ERROR"}
            for reason in item.blocking_reasons
        ]
        blocking_items = sorted(
            set(unsafe_reasons + required_services_bad + blocking_data)
        )
        calendar_ready = self._data_ready(data, "TRADING_CALENDAR")
        qfq_ready = self._data_ready(data, "QFQ_PRICE_DATA")
        champion_ready = self._data_ready(data, "CHAMPION_ASSIGNMENTS")
        active_account_rows = await self.db["ag_paper_accounts"].find(
            {"status": "ACTIVE", "market": "CN"}
        ).to_list(length=None)
        active_account_types = {
            str(row.get("account_type")) for row in active_account_rows
        }
        required_paper_account_types = {
            "PAPER_QUANT",
            "PAPER_NORMAL",
            "PAPER_TOP_CONFIRMED",
        }
        paper_policy_count = await _count(self.db["ag_paper_policies"])
        paper_ready = bool(
            calendar_ready
            and champion_ready
            and required_paper_account_types <= active_account_types
            and paper_policy_count >= 1
            and not required_services_bad
        )
        evaluation_ready = self._data_ready(data, "EVALUATION_SAMPLES") and qfq_ready
        experiment_framework = bool(
            champion_ready
            and await _count(self.db["ag_exp_promotion_policies"])
            and await _count(self.db["ag_exp_component_versions"])
        )
        challenger_ready = bool(
            experiment_framework
            and self._data_ready(data, "CHALLENGER_PIPELINE")
            and paper_ready
            and evaluation_ready
            and not required_services_bad
        )
        active_challenger = bool(
            await _count(
                self.db["ag_exp_challenger_assignments"],
                {"status": "ACTIVE"},
            )
        )
        recommendation_status = await CandidateRecommendationService(self.db).metrics()
        overall = (
            "UNSAFE"
            if unsafe_reasons
            else (
                "READY_FOR_PAPER"
                if paper_ready and not blocking_items
                else ("DEGRADED_PAPER" if paper_ready else "NOT_READY")
            )
        )
        versions = await self.versions()
        config_payload = {
            "system_mode": safety.system_mode.value,
            "live_trading_enabled": safety.live_trading_enabled,
            "versions": versions["configs"],
        }
        base = {
            "report_id": str(
                uuid5(
                    NAMESPACE_URL,
                    f"alphaguard:readiness:{now.replace(microsecond=0).isoformat()}",
                )
            ),
            "generated_at": now,
            "overall_status": overall,
            "system_mode": safety.system_mode.value,
            "live_trading_enabled": safety.live_trading_enabled,
            "live_execution_allowed": False,
            "service_health": services,
            "data_readiness": data,
            "job_health": jobs,
            "blocking_items": blocking_items,
            "warnings": [
                "MongoDB standalone: settlement and promotion use recoverable Saga",
                "Real trading is intentionally unavailable",
            ],
            "paper_execution_ready": paper_ready,
            "evaluation_ready": evaluation_ready,
            "experiment_ready": experiment_framework,
            "challenger_ready": challenger_ready,
            "active_challenger": active_challenger,
            "recommendation_ready": recommendation_status["recommendation_ready"],
            "auto_candidate_accept": False,
            "live_ready": False,
            "code_commit": versions["code_commit"],
            "build_version": versions["build_version"],
            "config_hash": operations_hash(config_payload),
            "schema_version": "alphaguard-operations-v1",
        }
        base["report_hash"] = operations_hash(
            base, exclude={"report_id", "report_hash", "generated_at"}
        )
        report = SystemReadinessReport.model_validate(base)
        if persist_alerts:
            await self._emit_readiness_alerts(report)
        return report

    @staticmethod
    def _data_ready(items: list[DataReadinessStatus], component: str) -> bool:
        return any(
            item.component == component and item.status == "READY" for item in items
        )

    async def _emit_readiness_alerts(self, report: SystemReadinessReport) -> None:
        for item in report.service_health:
            if item.status == "UNHEALTHY":
                await self.alerts.observe(
                    severity="CRITICAL" if item.required else "ERROR",
                    category="INFRASTRUCTURE",
                    code=item.error_code or f"{item.service_name}_UNHEALTHY",
                    title=f"{item.service_name} unavailable",
                    message=item.sanitized_message or "required service is unavailable",
                    source_module="operations.readiness",
                    source_object_id=item.service_name,
                    now=report.generated_at,
                )
        alert_map = {
            "TRADING_CALENDAR": ("TRADING_CALENDAR_MISSING", "DATA"),
            "QFQ_PRICE_DATA": ("QFQ_DATA_MISSING", "DATA"),
            "CHAMPION_ASSIGNMENTS": ("CHAMPION_INTEGRITY_FAILURE", "INTEGRITY"),
            "CHALLENGER_PIPELINE": ("CHALLENGER_PIPELINE_NOT_READY", "EXPERIMENT"),
        }
        for item in report.data_readiness:
            if item.status == "READY" or item.component not in alert_map:
                continue
            code, category = alert_map[item.component]
            await self.alerts.observe(
                severity="WARNING" if item.component != "CHAMPION_ASSIGNMENTS" else "ERROR",
                category=category,
                code=code,
                title=f"{item.component} is not ready",
                message="; ".join(item.blocking_reasons) or item.status,
                source_module="operations.data_readiness",
                source_object_id=item.component,
                now=report.generated_at,
            )

    async def overview(self) -> dict[str, Any]:
        report = await self.readiness()
        alerts = await self.alerts.list(status="OPEN", limit=20)
        counts = {}
        for name in (
            "ag_candidates",
            "ag_evidence_snapshots",
            "ag_quant_proposals",
            "ag_decision_contexts",
            "ag_risk_decisions",
            "ag_paper_fills",
            "ag_eval_subjects",
            "ag_exp_runs",
            "ag_exp_challenger_runs",
            "ag_exp_challenger_objects",
            "ag_candidate_recommendation_runs",
            "ag_candidate_recommendations",
        ):
            counts[name] = await _count(self.db[name])
        return {
            "readiness": report,
            "sample_counts": counts,
            "challenger_status": await self.challenger_operations_status(),
            "recommendation_status": await CandidateRecommendationService(self.db).metrics(),
            "open_alerts": alerts,
            "safety_notice": "PAPER ONLY — live execution is unavailable",
        }

    async def challenger_operations_status(self) -> dict[str, Any]:
        """Return a secret-free, read-only summary for the Operations page."""

        accounts = await self.db["ag_paper_accounts"].find(
            {"account_type": "PAPER_CHALLENGER", "market": "CN"}
        ).to_list(length=None)
        account_ids = [
            str(item["account_id"])
            for item in accounts
            if item.get("account_id") is not None
        ]
        active_accounts = [item for item in accounts if item.get("status") == "ACTIVE"]
        latest_run = clean_document(
            await self.db["ag_exp_challenger_runs"].find_one(
                {}, sort=[("updated_at", -1)]
            )
        )
        latest_success = clean_document(
            await self.db["ag_exp_challenger_runs"].find_one(
                {"status": {"$in": ["COMPLETED", "BLOCKED"]}},
                sort=[("completed_at", -1)],
            )
        )
        latest_failure = clean_document(
            await self.db["ag_exp_challenger_runs"].find_one(
                {"status": "FAILED"}, sort=[("completed_at", -1)]
            )
        )
        subject_query = (
            {"account_id": {"$in": account_ids}}
            if account_ids
            else {"account_id": {"$in": []}}
        )
        subjects = await self.db["ag_eval_subjects"].find(subject_query).to_list(
            length=None
        )
        subject_ids = [
            str(item["evaluation_subject_id"])
            for item in subjects
            if item.get("evaluation_subject_id") is not None
        ]
        mature_labels = await _count(
            self.db["ag_eval_horizon_labels"],
            {
                "evaluation_subject_id": {"$in": subject_ids},
                "status": "CALCULATED",
            },
        )
        from .model_budget_service import ModelBudgetService

        budget = await ModelBudgetService(self.db).summary()
        return {
            "account_status": "ACTIVE" if active_accounts else "NOT_CONFIGURED",
            "active_challenger_count": await _count(
                self.db["ag_exp_challenger_assignments"], {"status": "ACTIVE"}
            ),
            "last_run_at": (
                latest_run.get("updated_at") or latest_run.get("created_at")
                if latest_run
                else None
            ),
            "last_success_at": (
                latest_success.get("completed_at") if latest_success else None
            ),
            "last_failure_at": (
                latest_failure.get("completed_at") if latest_failure else None
            ),
            "pending_task_count": await _count(
                self.db["ag_exp_task_runs"],
                {"job_type": "PAPER_CHALLENGER", "status": "PENDING"},
            ),
            "model_call_count": await _count(
                self.db["ag_model_runs"], {"run_mode": "PAPER_CHALLENGER"}
            ),
            "budget_status": (
                "READY" if int(budget["remaining_calls"]) > 0 else "BLOCKED"
            ),
            "budget_remaining_calls": int(budget["remaining_calls"]),
            "order_count": await _count(
                self.db["ag_paper_orders"],
                {"account_id": {"$in": account_ids}},
            ),
            "fill_count": await _count(
                self.db["ag_paper_fills"],
                {"account_id": {"$in": account_ids}},
            ),
            "evaluation_subject_count": len(subjects),
            "mature_evaluation_count": mature_labels,
        }
