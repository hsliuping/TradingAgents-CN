"""Orchestrate isolated historical AlphaGuard research and mature evaluation."""

from __future__ import annotations

import hashlib
import subprocess
from collections import Counter, defaultdict
from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any
from uuid import NAMESPACE_URL, uuid5

from app.schemas.alphaguard import FactorEvidenceBundle, QuantTradeProposal
from app.services.alphaguard.attribution_engine import AttributionEngine
from app.services.alphaguard.data_quality_gate import DataQualityGate
from app.services.alphaguard.evaluation_repository import EvaluationRepository
from app.services.alphaguard.experiment_component_adapters import (
    _factor_bundle,
    current_component_payloads,
)
from app.services.alphaguard.factor_registry import FactorRegistry
from app.services.alphaguard.historical_backfill_config import backfill_policy
from app.services.alphaguard.historical_shadow_execution_service import (
    HistoricalShadowExecutionService,
)
from app.services.alphaguard.horizon_label_service import HorizonLabelService
from app.services.alphaguard.market_regime_engine import calculate_regime_result
from app.services.alphaguard.paper_policy_registry import PaperPolicyRegistry
from app.services.alphaguard.paper_storage import (
    clean_document,
    model_document,
    to_mongo_value,
)
from app.services.alphaguard.quant_config import sha256_value
from app.services.alphaguard.risk_policy_registry import RiskPolicyRegistry
from app.services.alphaguard.snapshot_data_resolver import ResolvedSnapshotData
from app.services.alphaguard.strategy_engine import StrategyEngine
from app.services.alphaguard.strategy_registry import (
    STRATEGY_SET_VERSION,
    StrategyRegistry,
)
from tradingagents.agents.managers.risk_manager import (
    TOP_REVIEW_QUANT_PROMPT_VERSION,
)
from tradingagents.agents.trader.trader import (
    NORMAL_TRADE_QUANT_PROMPT_VERSION,
)
from tradingagents.alphaguard.backfill_schemas import (
    HistoricalBackfillReport,
    HistoricalBackfillRun,
    HistoricalBackfillSample,
    HistoricalCoverageRecord,
    HistoricalMarketContext,
    HistoricalResearchSnapshot,
    ResearchShadowExecution,
    backfill_hash,
)
from tradingagents.alphaguard.decision_control_schemas import (
    CONSENSUS_POLICY_VERSION,
)
from tradingagents.alphaguard.evaluation_schemas import (
    COUNTERFACTUAL_VERSION,
    CounterfactualEvaluation,
    EvaluationSubject,
    evaluation_hash,
)
from tradingagents.alphaguard.evidence_schemas import (
    ALPHAGUARD_CODE_VERSION,
    EVIDENCE_SNAPSHOT_SCHEMA_VERSION,
    DataQualityReport,
    EvidenceSnapshot,
)
from app.services.alphaguard.evidence_snapshot_service import (
    calculate_immutable_hash,
)


PRODUCTION_TRADING_COLLECTIONS = (
    "ag_execution_outbox",
    "ag_order_intents",
    "ag_paper_orders",
    "ag_paper_fills",
    "ag_paper_accounts",
    "ag_paper_positions",
    "ag_paper_position_lots",
    "ag_paper_reservations",
    "ag_paper_ledger_entries",
    "ag_settlement_records",
)

BACKFILL_RUNTIME_PATHS = (
    "app/models/alphaguard",
    "app/schemas/alphaguard",
    "app/services/alphaguard",
    "tradingagents/alphaguard",
    "config/alphaguard",
    "scripts/run_alphaguard_historical_backfill.py",
    "scripts/sync_alphaguard_historical_market_context.py",
)


class HistoricalBackfillError(RuntimeError):
    pass


class HistoricalBackfillIntegrityConflict(HistoricalBackfillError):
    pass


def _git_value(*args: str) -> str:
    completed = subprocess.run(
        ["git", *args],
        check=True,
        capture_output=True,
        text=True,
    )
    return completed.stdout.strip()


def _code_tree_hash() -> str:
    """Hash runtime code/config changes without coupling runs to docs/tests."""

    digest = hashlib.sha256()
    digest.update(_git_value("rev-parse", "HEAD^{tree}").encode("utf-8"))
    tracked = subprocess.run(
        ["git", "diff", "--binary", "HEAD", "--", *BACKFILL_RUNTIME_PATHS],
        check=True,
        capture_output=True,
    ).stdout
    digest.update(tracked)
    untracked = subprocess.run(
        [
            "git",
            "ls-files",
            "--others",
            "--exclude-standard",
            "-z",
            "--",
            *BACKFILL_RUNTIME_PATHS,
        ],
        check=True,
        capture_output=True,
    ).stdout
    for raw_path in sorted(item for item in untracked.split(b"\0") if item):
        path = Path(raw_path.decode("utf-8"))
        if not path.is_file():
            continue
        digest.update(raw_path)
        digest.update(hashlib.sha256(path.read_bytes()).digest())
    return digest.hexdigest()


def _at_close(value: date) -> datetime:
    return datetime.combine(value, time(15, 0))


def _document_date(document: dict[str, Any], fields: tuple[str, ...]) -> date | None:
    for field in fields:
        raw = document.get(field)
        if isinstance(raw, datetime):
            return raw.date()
        if isinstance(raw, date):
            return raw
        if raw is not None:
            try:
                return date.fromisoformat(str(raw)[:10])
            except ValueError:
                continue
    return None


def _document_datetime(
    document: dict[str, Any], fields: tuple[str, ...]
) -> datetime | None:
    for field in fields:
        raw = document.get(field)
        if isinstance(raw, datetime):
            return (
                raw.astimezone(timezone.utc).replace(tzinfo=None)
                if raw.tzinfo is not None
                else raw
            )
        if isinstance(raw, date):
            return datetime.combine(raw, time())
        if raw is None:
            continue
        text = str(raw).strip()
        if not text:
            continue
        try:
            if text.isdigit() and len(text) == 8:
                return datetime.strptime(text, "%Y%m%d")
            parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
            return (
                parsed.astimezone(timezone.utc).replace(tzinfo=None)
                if parsed.tzinfo is not None
                else parsed
            )
        except ValueError:
            try:
                return datetime.strptime(text[:10], "%Y-%m-%d")
            except ValueError:
                continue
    return None


def _on_or_before(value: datetime | None, cutoff: datetime) -> bool:
    if value is None:
        return False
    if value.tzinfo is not None:
        value = value.astimezone(timezone.utc).replace(tzinfo=None)
    if cutoff.tzinfo is not None:
        cutoff = cutoff.astimezone(timezone.utc).replace(tzinfo=None)
    return value <= cutoff


def _reference(prefix: str, document: dict[str, Any]) -> str:
    identifier = (
        document.get("ref_id")
        or document.get("data_ref")
        or document.get("context_id")
        or document.get("calendar_id")
        or document.get("source_record_id")
        or document.get("_id")
    )
    return f"{prefix}:{identifier}"


def _with_reference(prefix: str, documents: list[dict[str, Any]]) -> list[dict[str, Any]]:
    result = []
    for raw in documents:
        document = clean_document(raw) or {}
        document["_reference"] = _reference(prefix, document)
        result.append(document)
    return result


def _mean(values: list[Decimal]) -> Decimal | None:
    return sum(values, Decimal("0")) / Decimal(len(values)) if values else None


def _score_bucket(value: Any) -> str | None:
    if value is None:
        return None
    score = Decimal(str(value))
    if not Decimal("0") <= score <= Decimal("100"):
        return None
    lower = min(int(score // Decimal("20")) * 20, 80)
    return f"{lower:03d}_{lower + 20:03d}"


class HistoricalBackfillService:
    def __init__(self, db):
        self.db = db
        self.policy = backfill_policy()
        self.gate = DataQualityGate()
        self.evaluation_repository = EvaluationRepository(db)
        self.labels = HorizonLabelService(db)
        self.attributions = AttributionEngine(db)
        self.shadow = HistoricalShadowExecutionService(db)

    async def select_trade_dates(
        self,
        *,
        start_trade_date: date,
        end_trade_date: date,
        sampling_method: str = "WEEKLY_LAST_SESSION",
    ) -> list[date]:
        documents = await self.db["trading_calendar"].find(
            {"market": "CN", "is_open": True}
        ).sort("session_date", 1).to_list(length=None)
        sessions = sorted(
            {
                item
                for document in documents
                if (item := _document_date(document, ("session_date",)))
                is not None
                and start_trade_date <= item <= end_trade_date
            }
        )
        if not sessions:
            raise HistoricalBackfillError("persisted CN calendar has no open sessions")
        if sampling_method == "DAILY":
            return sessions
        if sampling_method != "WEEKLY_LAST_SESSION":
            raise ValueError("only WEEKLY_LAST_SESSION and DAILY are supported")
        weekly: dict[tuple[int, int], date] = {}
        for session in sessions:
            iso = session.isocalendar()
            weekly[(iso.year, iso.week)] = session
        return sorted(weekly.values())

    async def _locked_versions(self) -> tuple[dict[str, str], dict[str, Any]]:
        descriptors = current_component_payloads()
        by_type = {
            (item["component_type"], item["component_key"]): item
            for item in descriptors
        }
        factor_set = by_type[("FACTOR_SET", "factor-set-v1")]
        factor_weight = by_type[("FACTOR_WEIGHT", "factor-set-v1")]
        regime = by_type[("REGIME_CONFIG", "cn-market-regime")]
        factor_payload = dict(factor_set["payload"])
        factor_payload["factor_weights"] = dict(
            factor_weight["payload"]["factor_weights"]
        )
        strategies = await StrategyRegistry(self.db).require_strategy_set()
        factor_versions = await FactorRegistry(self.db).get_version_set(
            require_registered=True
        )
        paper = PaperPolicyRegistry(self.db)
        execution_policy = await paper.execution_policy()
        fee_policy = await paper.fee_policy()
        risk_policy = await RiskPolicyRegistry(self.db).get_active()
        assignments = await self.db["ag_exp_champion_assignments"].find(
            {"status": "ACTIVE"}
        ).to_list(length=None)
        champion_refs = {
            str(item["champion_slot_id"]): str(item["current_version_ref"])
            for item in assignments
        }
        version_refs = {
            "factor_set": factor_set["version_ref"],
            "factor_weight": factor_weight["version_ref"],
            "regime": regime["version_ref"],
            "strategy_set": STRATEGY_SET_VERSION,
            "normal_prompt": NORMAL_TRADE_QUANT_PROMPT_VERSION,
            "top_prompt": TOP_REVIEW_QUANT_PROMPT_VERSION,
            "consensus": CONSENSUS_POLICY_VERSION,
            "hard_risk": f"{risk_policy.risk_policy_id}@{risk_policy.version}",
            "matching": execution_policy.matching_engine_version,
            "execution_policy": execution_policy.version,
            "fee": fee_policy.version,
            "backfill_policy": (
                f"{self.policy['policy_id']}@{self.policy['version']}"
            ),
        }
        version_refs.update(
            {
                f"strategy:{item.strategy_id}": item.strategy_version
                for item in strategies
            }
        )
        version_refs.update(
            {f"champion:{key}": value for key, value in champion_refs.items()}
        )
        payloads = {
            "factor_payload": factor_payload,
            "factor_component_ref": (
                f"{factor_set['version_ref']}+{factor_weight['version_ref']}"
            ),
            "factor_versions": factor_versions,
            "regime_payload": dict(regime["payload"]),
            "strategies": strategies,
            "champion_refs": champion_refs,
        }
        return dict(sorted(version_refs.items())), payloads

    async def create_run(
        self,
        *,
        user_id: str,
        symbols: list[str],
        start_trade_date: date,
        end_trade_date: date,
        sampling_method: str = "WEEKLY_LAST_SESSION",
        now: datetime | None = None,
    ) -> tuple[HistoricalBackfillRun, bool]:
        now = now or datetime.utcnow()
        normalized_symbols = sorted(set(str(item).zfill(6) for item in symbols))
        if not normalized_symbols or any(len(item) != 6 for item in normalized_symbols):
            raise ValueError("backfill requires explicit six-digit symbols")
        selected = await self.select_trade_dates(
            start_trade_date=start_trade_date,
            end_trade_date=end_trade_date,
            sampling_method=sampling_method,
        )
        version_refs, _ = await self._locked_versions()
        commit = _git_value("rev-parse", "HEAD")
        tree_hash = _code_tree_hash()
        config_hash = backfill_hash(
            {"policy": self.policy, "version_refs": version_refs}
        )
        input_payload = {
            "user_id": str(user_id),
            "market": "CN",
            "symbols": normalized_symbols,
            "start_trade_date": start_trade_date,
            "end_trade_date": end_trade_date,
            "sampling_method": sampling_method,
            "selected_trade_dates": selected,
            "code_commit": commit,
            "code_tree_hash": tree_hash,
            "config_hash": config_hash,
            "version_refs": version_refs,
        }
        input_hash = backfill_hash(input_payload)
        run_id = str(
            uuid5(NAMESPACE_URL, f"alphaguard:historical-backfill:{input_hash}")
        )
        existing = clean_document(
            await self.db["ag_research_backfill_runs"].find_one(
                {"backfill_run_id": run_id}
            )
        )
        if existing:
            run = HistoricalBackfillRun.model_validate(existing)
            if run.input_hash != input_hash:
                raise HistoricalBackfillIntegrityConflict(
                    "same backfill run identity has different input"
                )
            return run, False
        run = HistoricalBackfillRun(
            backfill_run_id=run_id,
            status="CREATED",
            user_id=str(user_id),
            market="CN",
            symbols=normalized_symbols,
            start_trade_date=start_trade_date,
            end_trade_date=end_trade_date,
            sampling_method=sampling_method,
            selected_trade_dates=selected,
            code_commit=commit,
            code_tree_hash=tree_hash,
            config_hash=config_hash,
            input_hash=input_hash,
            version_refs=version_refs,
            total_samples=len(normalized_symbols) * len(selected),
            created_at=now,
            updated_at=now,
        )
        await self.db["ag_research_backfill_runs"].insert_one(model_document(run))
        await self._record_event(
            "HISTORICAL_BACKFILL_RUN_CREATED",
            backfill_run_id=run.backfill_run_id,
            user_id=run.user_id,
            input_hash=run.input_hash,
            created_at=now,
        )
        return run, True

    async def coverage_audit(
        self,
        *,
        run: HistoricalBackfillRun,
        symbol: str,
        trade_date: date,
        now: datetime | None = None,
    ) -> tuple[HistoricalCoverageRecord, dict[str, list[dict[str, Any]]]]:
        now = now or datetime.utcnow()
        sample_id = self.sample_id(run.backfill_run_id, symbol, trade_date)
        cutoff = _at_close(trade_date)
        price_documents = [
            clean_document(item)
            for item in await self.db["stock_daily_quotes"].find(
                {"symbol": symbol, "market": "CN", "period": "daily"}
            ).to_list(length=None)
        ]
        exact_prices = [
            item
            for item in price_documents
            if _document_date(item, ("trade_date",)) == trade_date
            and str(item.get("price_adjustment_mode") or "").upper() == "QFQ"
        ]
        exact_price = exact_prices[0] if len(exact_prices) == 1 else None
        price_identity_conflict = len(exact_prices) > 1
        price_version = str((exact_price or {}).get("price_data_version") or "")
        prices = sorted(
            [
                item
                for item in price_documents
                if price_version
                and str(item.get("price_data_version") or "") == price_version
                and str(item.get("price_adjustment_mode") or "").upper() == "QFQ"
                and (item_date := _document_date(item, ("trade_date",))) is not None
                and item_date <= trade_date
            ],
            key=lambda item: _document_date(item, ("trade_date",)) or date.min,
        )[-800:]
        benchmark_documents = [
            clean_document(item)
            for item in await self.db["stock_daily_quotes"].find(
                {"symbol": "000300", "market": "CN", "period": "daily"}
            ).to_list(length=None)
        ]
        exact_benchmarks = [
            item
            for item in benchmark_documents
            if _document_date(item, ("trade_date",)) == trade_date
            and str(item.get("price_adjustment_mode") or "").upper()
            in {"QFQ", "INDEX_UNADJUSTED_EQUIVALENT"}
        ]
        exact_benchmark = exact_benchmarks[0] if len(exact_benchmarks) == 1 else None
        benchmark_identity_conflict = len(exact_benchmarks) > 1
        benchmark_version = str(
            (exact_benchmark or {}).get("price_data_version") or ""
        )
        benchmark_mode = str(
            (exact_benchmark or {}).get("price_adjustment_mode") or ""
        ).upper()
        benchmark = sorted(
            [
                item
                for item in benchmark_documents
                if benchmark_version
                and str(item.get("price_data_version") or "")
                == benchmark_version
                and str(item.get("price_adjustment_mode") or "").upper()
                == benchmark_mode
                and (item_date := _document_date(item, ("trade_date",))) is not None
                and item_date <= trade_date
            ],
            key=lambda item: _document_date(item, ("trade_date",)) or date.min,
        )[-800:]

        financial_documents = [
            clean_document(item)
            for item in await self.db["stock_financial_data"].find(
                {"symbol": symbol, "market": "CN"}
            ).to_list(length=None)
        ]
        financials = sorted(
            [
                item
                for item in financial_documents
                if (report := _document_date(item, ("report_period", "end_date")))
                is not None
                and report <= trade_date
                and _on_or_before(
                    _document_datetime(
                        item,
                        ("f_ann_date", "ann_date", "publish_date", "published_at"),
                    ),
                    cutoff,
                )
            ],
            key=lambda item: (
                _document_date(item, ("report_period", "end_date")) or date.min,
                _document_datetime(
                    item,
                    ("f_ann_date", "ann_date", "publish_date", "published_at"),
                )
                or datetime.min,
            ),
        )
        news_documents = [
            clean_document(item)
            for item in await self.db["stock_news"].find(
                {"symbol": symbol, "market": "CN"}
            ).to_list(length=None)
        ]
        news = sorted(
            [
                item
                for item in news_documents
                if _on_or_before(
                    _document_datetime(
                        item, ("publish_time", "published_at", "timestamp")
                    ),
                    cutoff,
                )
            ],
            key=lambda item: _document_datetime(
                item, ("publish_time", "published_at", "timestamp")
            )
            or datetime.min,
        )[-100:]
        announcement_documents = [
            clean_document(item)
            for item in await self.db["stock_announcements"].find(
                {"symbol": symbol, "market": "CN"}
            ).to_list(length=None)
        ]
        announcements = sorted(
            [
                item
                for item in announcement_documents
                if _on_or_before(
                    _document_datetime(
                        item,
                        (
                            "announcement_time",
                            "published_at",
                            "publish_time",
                            "timestamp",
                        ),
                    ),
                    cutoff,
                )
            ],
            key=lambda item: _document_datetime(
                item,
                ("announcement_time", "published_at", "publish_time", "timestamp"),
            )
            or datetime.min,
        )[-200:]
        context_candidates = [
            clean_document(item)
            for item in await self.db["ag_research_market_contexts"].find(
                {
                    "market": "CN",
                    "provider": self.policy["market_context"]["provider"],
                }
            ).to_list(length=None)
            if _document_date(item, ("trade_date",)) == trade_date
        ]
        context_raw = context_candidates[0] if len(context_candidates) == 1 else None
        context_identity_conflict = len(context_candidates) > 1
        context = (
            HistoricalMarketContext.model_validate(context_raw)
            if context_raw
            else None
        )
        calendar = sorted(
            [
                clean_document(item)
                for item in await self.db["trading_calendar"].find(
                    {"market": "CN"}
                ).to_list(length=None)
                if (
                    session := _document_date(item, ("session_date",))
                )
                is not None
                and trade_date - timedelta(days=120)
                <= session
                <= trade_date + timedelta(days=120)
            ],
            key=lambda item: _document_date(item, ("session_date",)) or date.min,
        )
        historical_industry = [
            clean_document(item)
            for item in await self.db["stock_industry_history"].find(
                {"symbol": symbol, "market": "CN"}
            ).to_list(length=None)
            if str(item.get("history_coverage_status") or "") != "CURRENT_ONLY"
            and (effective_from := _document_date(item, ("effective_from",)))
            is not None
            and effective_from <= trade_date
            and (
                (effective_to := _document_date(item, ("effective_to",))) is None
                or effective_to >= trade_date
            )
        ]
        resolved = {
            "prices": _with_reference("stock_daily_quotes", prices),
            "benchmark_prices": _with_reference("index_daily", benchmark),
            "financials": _with_reference("stock_financial_data", financials),
            "news": _with_reference("stock_news", news),
            "announcements": _with_reference(
                "stock_announcements", announcements
            ),
            "market_context": (
                _with_reference("research_market_context", [context_raw])
                if context_raw
                else []
            ),
            "trading_calendar": _with_reference("trading_calendar", calendar),
            "industry_history": _with_reference(
                "stock_industry_history", historical_industry
            ),
        }
        critical: list[str] = []
        warnings: list[str] = []
        if price_identity_conflict:
            critical.append("QFQ_PRICE_IDENTITY_CONFLICT")
        if benchmark_identity_conflict:
            critical.append("BENCHMARK_PRICE_IDENTITY_CONFLICT")
        if context_identity_conflict:
            critical.append("MARKET_CONTEXT_IDENTITY_CONFLICT")
        if exact_price is None:
            critical.append("RAW_DAILY_PRICE/QFQ_DAILY_PRICE")
        if len(prices) < 61:
            critical.append("QFQ_HISTORY_61_SESSIONS")
        if exact_benchmark is None or len(benchmark) < 61:
            critical.append("BENCHMARK_PRICE_61_SESSIONS")
        if context is None or context.calculation_status != "READY":
            critical.append("MARKET_CONTEXT")
        if not any(
            _document_date(item, ("session_date",)) == trade_date
            and item.get("is_open") is True
            for item in calendar
        ):
            critical.append("TRADING_CALENDAR")
        future_open = [
            item
            for item in calendar
            if item.get("is_open") is True
            and (_document_date(item, ("session_date",)) or trade_date)
            > trade_date
        ]
        if len(future_open) < 20:
            warnings.append("CALENDAR_HAS_FEWER_THAN_20_FUTURE_SESSIONS")
        if not financials:
            warnings.append("FINANCIAL_DATA_UNAVAILABLE_AS_OF_CUTOFF")
        if not news:
            warnings.append("NEWS_UNAVAILABLE_AS_OF_CUTOFF")
        if not announcements:
            warnings.append("ANNOUNCEMENTS_UNAVAILABLE_AS_OF_CUTOFF")
        if not historical_industry:
            warnings.append("HISTORICAL_INDUSTRY_MAPPING_UNAVAILABLE")
        quality = self.gate.evaluate_documents(
            symbol=symbol,
            market="CN",
            trade_date=trade_date,
            price_cutoff_at=cutoff,
            news_cutoff_at=cutoff,
            announcement_cutoff_at=cutoff,
            resolved=resolved,
            invalid_refs=[],
            required_sources=["prices", "benchmark_prices", "market_context"],
        )
        quality = quality.model_copy(
            update={
                "quality_report_id": str(
                    uuid5(
                        NAMESPACE_URL,
                        f"research-quality:{run.backfill_run_id}:{symbol}:{trade_date}",
                    )
                ),
                "checked_at": run.created_at,
            }
        )
        if quality.status == "FAIL":
            critical.extend(quality.blocking_reasons)

        def domain(
            name: str,
            collection: str,
            documents: list[dict[str, Any]],
            *,
            time_fields: tuple[str, ...],
            version_fields: tuple[str, ...],
            cutoff_resolvable: bool,
        ) -> tuple[str, dict[str, Any]]:
            dates = sorted(
                item
                for document in documents
                if (item := _document_date(document, time_fields)) is not None
            )
            versions = sorted(
                {
                    str(document.get(field))
                    for document in documents
                    for field in version_fields
                    if document.get(field)
                }
            )
            return name, {
                "collection": collection,
                "time_fields": list(time_fields),
                "version_fields": list(version_fields),
                "coverage_start": dates[0] if dates else None,
                "coverage_end": dates[-1] if dates else None,
                "record_count": len(documents),
                "missing_rate": 0 if documents else 1,
                "data_versions": versions,
                "historical_cutoff_resolvable": cutoff_resolvable,
                "allowed_for_replay": bool(documents),
            }

        domains = dict(
            [
                domain(
                    "RAW_DAILY_PRICE",
                    "stock_daily_quotes",
                    prices,
                    time_fields=("trade_date",),
                    version_fields=("raw_data_version",),
                    cutoff_resolvable=True,
                ),
                domain(
                    "QFQ_DAILY_PRICE",
                    "stock_daily_quotes",
                    prices,
                    time_fields=("trade_date",),
                    version_fields=("price_data_version", "adjusted_data_version"),
                    cutoff_resolvable=True,
                ),
                domain(
                    "BENCHMARK_PRICE",
                    "stock_daily_quotes",
                    benchmark,
                    time_fields=("trade_date",),
                    version_fields=("price_data_version",),
                    cutoff_resolvable=True,
                ),
                domain(
                    "TRADING_CALENDAR",
                    "trading_calendar",
                    calendar,
                    time_fields=("session_date",),
                    version_fields=("data_version",),
                    cutoff_resolvable=True,
                ),
                domain(
                    "FINANCIAL_DATA",
                    "stock_financial_data",
                    financials,
                    time_fields=("published_at", "f_ann_date", "ann_date"),
                    version_fields=("data_version",),
                    cutoff_resolvable=True,
                ),
                domain(
                    "NEWS",
                    "stock_news",
                    news,
                    time_fields=("publish_time", "published_at"),
                    version_fields=("data_version",),
                    cutoff_resolvable=True,
                ),
                domain(
                    "ANNOUNCEMENTS",
                    "stock_announcements",
                    announcements,
                    time_fields=("announcement_time", "published_at"),
                    version_fields=("data_version",),
                    cutoff_resolvable=True,
                ),
                domain(
                    "MARKET_CONTEXT",
                    "ag_research_market_contexts",
                    [context_raw] if context_raw else [],
                    time_fields=("trade_date",),
                    version_fields=("data_version",),
                    cutoff_resolvable=True,
                ),
                domain(
                    "INDUSTRY_HISTORY",
                    "stock_industry_history",
                    historical_industry,
                    time_fields=("effective_from",),
                    version_fields=("data_version",),
                    cutoff_resolvable=bool(historical_industry),
                ),
            ]
        )
        coverage_payload = {
            "backfill_run_id": run.backfill_run_id,
            "sample_id": sample_id,
            "symbol": symbol,
            "market": "CN",
            "trade_date": trade_date,
            "status": "READY" if not critical else "INSUFFICIENT_DATA",
            "replay_allowed": not critical,
            "domains": domains,
            "critical_missing": sorted(set(critical)),
            "warnings": sorted(set(warnings)),
        }
        coverage_payload["input_hash"] = backfill_hash(coverage_payload)
        coverage = HistoricalCoverageRecord(
            coverage_id=str(
                uuid5(
                    NAMESPACE_URL,
                    f"research-coverage:{run.backfill_run_id}:{symbol}:{trade_date}",
                )
            ),
            created_at=now,
            **coverage_payload,
        )
        stored = await self._save_immutable(
            "ag_research_coverage",
            coverage,
            identity={"coverage_id": coverage.coverage_id},
            hash_field="input_hash",
        )
        resolved["data_quality"] = [
            quality.model_dump(mode="python")
        ]
        return stored, resolved

    async def run(
        self,
        *,
        backfill_run_id: str,
        as_of_trade_date: date,
        model_replay: bool = False,
        now: datetime | None = None,
    ) -> tuple[HistoricalBackfillRun, HistoricalBackfillReport]:
        now = now or datetime.utcnow()
        raw = clean_document(
            await self.db["ag_research_backfill_runs"].find_one(
                {"backfill_run_id": backfill_run_id}
            )
        )
        if raw is None:
            raise LookupError("HistoricalBackfillRun does not exist")
        run = HistoricalBackfillRun.model_validate(raw)
        existing_report = clean_document(
            await self.db["ag_research_backfill_reports"].find_one(
                {"backfill_run_id": backfill_run_id}
            )
        )
        if run.status in {"COMPLETED", "PARTIAL"} and existing_report:
            stored_report = HistoricalBackfillReport.model_validate(existing_report)
            if (
                stored_report.completed_sample_count == run.completed_samples
                and stored_report.skipped_sample_count == run.skipped_samples
                and stored_report.failed_sample_count == run.failed_samples
            ):
                return run, stored_report
            return run, await self.build_report(backfill_run_id, now=now)
        production_before = await self.production_state()
        await self.db["ag_research_backfill_runs"].update_one(
            {"backfill_run_id": backfill_run_id},
            {
                "$set": {
                    "status": "RUNNING",
                    "started_at": run.started_at or now,
                    "updated_at": now,
                },
                "$inc": {"attempt_count": 1},
            },
        )
        await self._record_event(
            "HISTORICAL_BACKFILL_RUN_STARTED",
            backfill_run_id=run.backfill_run_id,
            user_id=run.user_id,
            input_hash=run.input_hash,
            created_at=now,
        )
        _, locked = await self._locked_versions()
        for trade_date in run.selected_trade_dates:
            for symbol in run.symbols:
                await self._run_sample(
                    run=run,
                    symbol=symbol,
                    trade_date=trade_date,
                    as_of_trade_date=as_of_trade_date,
                    locked=locked,
                    model_replay=model_replay,
                )
        production_after = await self.production_state()
        if production_after != production_before:
            failed_at = datetime.utcnow()
            await self.db["ag_research_backfill_runs"].update_one(
                {"backfill_run_id": backfill_run_id},
                {
                    "$set": {
                        "status": "FAILED",
                        "updated_at": failed_at,
                        "completed_at": failed_at,
                        "error_summary": [
                            "production trading state changed during research backfill"
                        ],
                    }
                },
            )
            raise HistoricalBackfillIntegrityConflict(
                "production trading state changed during research backfill"
            )
        samples = await self.db["ag_research_backfill_samples"].find(
            {"backfill_run_id": backfill_run_id}
        ).to_list(length=None)
        counts = Counter(str(item.get("status")) for item in samples)
        completed = counts["COMPLETED"]
        skipped = counts["BACKFILL_SKIPPED_INSUFFICIENT_DATA"]
        failed = counts["FAILED"] + counts["INTEGRITY_CONFLICT"]
        terminal_status = (
            "COMPLETED"
            if completed == run.total_samples
            else "PARTIAL"
            if completed or skipped
            else "FAILED"
        )
        finished = datetime.utcnow()
        await self.db["ag_research_backfill_runs"].update_one(
            {"backfill_run_id": backfill_run_id},
            {
                "$set": {
                    "status": terminal_status,
                    "completed_samples": completed,
                    "skipped_samples": skipped,
                    "failed_samples": failed,
                    "completed_at": finished,
                    "updated_at": finished,
                }
            },
        )
        await self._record_event(
            "HISTORICAL_BACKFILL_RUN_FINISHED",
            backfill_run_id=run.backfill_run_id,
            user_id=run.user_id,
            status=terminal_status,
            completed_samples=completed,
            skipped_samples=skipped,
            failed_samples=failed,
            created_at=finished,
        )
        report = await self.build_report(backfill_run_id, now=finished)
        refreshed = clean_document(
            await self.db["ag_research_backfill_runs"].find_one(
                {"backfill_run_id": backfill_run_id}
            )
        )
        return HistoricalBackfillRun.model_validate(refreshed), report

    async def _run_sample(
        self,
        *,
        run: HistoricalBackfillRun,
        symbol: str,
        trade_date: date,
        as_of_trade_date: date,
        locked: dict[str, Any],
        model_replay: bool,
    ) -> HistoricalBackfillSample:
        sample_id = self.sample_id(run.backfill_run_id, symbol, trade_date)
        existing_raw = clean_document(
            await self.db["ag_research_backfill_samples"].find_one(
                {"sample_id": sample_id}
            )
        )
        input_hash = backfill_hash(
            {
                "backfill_run_id": run.backfill_run_id,
                "symbol": symbol,
                "trade_date": trade_date,
                "version_refs": run.version_refs,
                "run_input_hash": run.input_hash,
            }
        )
        if existing_raw and str(existing_raw.get("input_hash") or "") != input_hash:
            raise HistoricalBackfillIntegrityConflict(
                "same historical sample identity has different input"
            )
        if existing_raw and existing_raw.get("status") in {
            "COMPLETED",
            "BACKFILL_SKIPPED_INSUFFICIENT_DATA",
        }:
            return HistoricalBackfillSample.model_validate(existing_raw)
        now = datetime.utcnow()
        attempt = int((existing_raw or {}).get("attempt_count", 0)) + 1
        initial = HistoricalBackfillSample(
            sample_id=sample_id,
            backfill_run_id=run.backfill_run_id,
            symbol=symbol,
            market="CN",
            trade_date=trade_date,
            status="RUNNING",
            reason="historical research sample is running",
            version_refs=run.version_refs,
            input_hash=input_hash,
            attempt_count=attempt,
            error_history=list((existing_raw or {}).get("error_history") or []),
            created_at=(existing_raw or {}).get("created_at", now),
            updated_at=now,
        )
        await self.db["ag_research_backfill_samples"].replace_one(
            {"sample_id": sample_id}, model_document(initial), upsert=True
        )
        try:
            coverage, resolved = await self.coverage_audit(
                run=run, symbol=symbol, trade_date=trade_date
            )
            if not coverage.replay_allowed:
                skipped = initial.model_copy(
                    update={
                        "status": "BACKFILL_SKIPPED_INSUFFICIENT_DATA",
                        "reason": "; ".join(coverage.critical_missing),
                        "coverage_id": coverage.coverage_id,
                        "result_hash": backfill_hash(
                            {
                                "coverage_id": coverage.coverage_id,
                                "status": coverage.status,
                                "critical_missing": coverage.critical_missing,
                            }
                        ),
                        "updated_at": datetime.utcnow(),
                    }
                )
                await self.db["ag_research_backfill_samples"].replace_one(
                    {"sample_id": sample_id}, model_document(skipped)
                )
                await self._record_event(
                    "HISTORICAL_BACKFILL_SAMPLE_SKIPPED",
                    backfill_run_id=run.backfill_run_id,
                    sample_id=sample_id,
                    symbol=symbol,
                    trade_date=trade_date,
                    status=skipped.status,
                    result_hash=skipped.result_hash,
                )
                return skipped
            snapshot, data = await self._build_snapshot(
                run=run,
                sample_id=sample_id,
                symbol=symbol,
                trade_date=trade_date,
                coverage=coverage,
                resolved=resolved,
                locked=locked,
            )
            bundle: FactorEvidenceBundle = _factor_bundle(
                data,
                locked["factor_payload"],
                component_version_ref=locked["factor_component_ref"],
                calculated_at=run.created_at,
            )
            await self._save_quant_wrappers(
                run=run,
                sample_id=sample_id,
                kind="factor_result",
                models=bundle.results,
            )
            bundle_hash = backfill_hash(bundle)
            await self._save_wrapper(
                "ag_research_factor_bundles",
                identity={"sample_id": sample_id},
                payload_name="factor_bundle",
                payload=bundle,
                metadata={
                    "backfill_run_id": run.backfill_run_id,
                    "sample_id": sample_id,
                    "snapshot_id": snapshot.evidence_snapshot.snapshot_id,
                },
                immutable_hash=bundle_hash,
            )
            regime = calculate_regime_result(
                data,
                config=locked["regime_payload"],
                calculated_at=run.created_at,
            )
            await self._save_wrapper(
                "ag_research_regime_results",
                identity={"regime_result_id": regime.regime_result_id},
                payload_name="regime_result",
                payload=regime,
                metadata={
                    "backfill_run_id": run.backfill_run_id,
                    "sample_id": sample_id,
                    "regime_result_id": regime.regime_result_id,
                    "snapshot_id": snapshot.evidence_snapshot.snapshot_id,
                },
                immutable_hash=regime.input_hash,
            )
            proposals: list[QuantTradeProposal] = []
            for definition in locked["strategies"]:
                proposal = StrategyEngine().evaluate(
                    definition, data, bundle, regime, candidate_id=None
                )
                proposal = proposal.model_copy(
                    update={"created_at": run.created_at}
                )
                await self._save_wrapper(
                    "ag_research_quant_proposals",
                    identity={"proposal_id": proposal.proposal_id},
                    payload_name="quant_proposal",
                    payload=proposal,
                    metadata={
                        "backfill_run_id": run.backfill_run_id,
                        "sample_id": sample_id,
                        "proposal_id": proposal.proposal_id,
                        "snapshot_id": snapshot.evidence_snapshot.snapshot_id,
                    },
                    immutable_hash=proposal.input_hash,
                )
                proposals.append(proposal)
            evaluation_ids = await self._evaluate_proposals(
                run=run,
                sample_id=sample_id,
                snapshot=snapshot,
                proposals=proposals,
                as_of_trade_date=as_of_trade_date,
            )
            result_payload = {
                "coverage_id": coverage.coverage_id,
                "research_snapshot_id": snapshot.research_snapshot_id,
                "factor_result_ids": [item.result_id for item in bundle.results],
                "factor_bundle_hash": bundle_hash,
                "regime_result_id": regime.regime_result_id,
                "proposal_ids": [item.proposal_id for item in proposals],
                **evaluation_ids,
            }
            completed = initial.model_copy(
                update={
                    "status": "COMPLETED",
                    "reason": "deterministic research backfill completed",
                    "coverage_id": coverage.coverage_id,
                    "research_snapshot_id": snapshot.research_snapshot_id,
                    "factor_result_ids": result_payload["factor_result_ids"],
                    "factor_bundle_hash": bundle_hash,
                    "regime_result_id": regime.regime_result_id,
                    "proposal_ids": result_payload["proposal_ids"],
                    "evaluation_subject_ids": evaluation_ids[
                        "evaluation_subject_ids"
                    ],
                    "horizon_label_ids": evaluation_ids["horizon_label_ids"],
                    "counterfactual_ids": evaluation_ids["counterfactual_ids"],
                    "attribution_ids": evaluation_ids["attribution_ids"],
                    "shadow_execution_ids": evaluation_ids[
                        "shadow_execution_ids"
                    ],
                    "model_replay_status": (
                        "NOT_CONFIGURED" if model_replay else "NOT_REQUESTED"
                    ),
                    "result_hash": backfill_hash(result_payload),
                    "updated_at": datetime.utcnow(),
                }
            )
            await self.db["ag_research_backfill_samples"].replace_one(
                {"sample_id": sample_id}, model_document(completed)
            )
            await self._record_event(
                "HISTORICAL_BACKFILL_SAMPLE_COMPLETED",
                backfill_run_id=run.backfill_run_id,
                sample_id=sample_id,
                symbol=symbol,
                trade_date=trade_date,
                status=completed.status,
                result_hash=completed.result_hash,
            )
            return completed
        except HistoricalBackfillIntegrityConflict as exc:
            return await self._fail_sample(
                initial, exc, status="INTEGRITY_CONFLICT"
            )
        except Exception as exc:
            return await self._fail_sample(initial, exc, status="FAILED")

    async def _build_snapshot(
        self,
        *,
        run: HistoricalBackfillRun,
        sample_id: str,
        symbol: str,
        trade_date: date,
        coverage: HistoricalCoverageRecord,
        resolved: dict[str, list[dict[str, Any]]],
        locked: dict[str, Any],
    ) -> tuple[HistoricalResearchSnapshot, ResolvedSnapshotData]:
        quality = DataQualityReport.model_validate(resolved["data_quality"][0])
        raw_refs = {
            key: sorted(str(item["_reference"]) for item in documents)
            for key, documents in resolved.items()
            if key not in {"data_quality", "industry_history"}
        }
        context_document = resolved["market_context"][0]
        financial_version = next(
            (
                str(item.get("data_version"))
                for item in reversed(resolved["financials"])
                if item.get("data_version")
            ),
            "historical:none-before-cutoff",
        )
        news_version = next(
            (
                str(item.get("data_version"))
                for item in reversed(resolved["news"])
                if item.get("data_version")
            ),
            "historical:none-before-cutoff",
        )
        snapshot_payload = {
            "snapshot_id": str(
                uuid5(
                    NAMESPACE_URL,
                    f"research-snapshot:{run.backfill_run_id}:{symbol}:{trade_date}",
                )
            ),
            "user_id": run.user_id,
            "analysis_id": None,
            "symbol": symbol,
            "market": "CN",
            "trade_date": trade_date,
            "price_cutoff_at": _at_close(trade_date),
            "news_cutoff_at": _at_close(trade_date),
            "announcement_cutoff_at": _at_close(trade_date),
            "price_data_version": str(
                resolved["prices"][-1].get("price_data_version")
            ),
            "financial_data_version": financial_version,
            "news_data_version": news_version,
            "account_snapshot_id": None,
            "market_context_id": str(context_document["context_id"]),
            "data_quality": quality,
            "raw_refs": raw_refs,
            "factor_version_set": locked["factor_versions"],
            "strategy_version": STRATEGY_SET_VERSION,
            "champion_version_refs": locked["champion_refs"],
            "normal_model_version": None,
            "top_model_version": None,
            "prompt_versions": {
                "normal": NORMAL_TRADE_QUANT_PROMPT_VERSION,
                "top": TOP_REVIEW_QUANT_PROMPT_VERSION,
            },
            "immutable_hash": "0" * 64,
            "created_at": run.created_at,
            "schema_version": EVIDENCE_SNAPSHOT_SCHEMA_VERSION,
            "code_version": ALPHAGUARD_CODE_VERSION,
        }
        normalized = EvidenceSnapshot.model_validate(snapshot_payload)
        snapshot_payload["immutable_hash"] = calculate_immutable_hash(normalized)
        evidence = EvidenceSnapshot.model_validate(snapshot_payload)
        wrapper_payload = {
            "research_snapshot_id": f"research:{evidence.snapshot_id}",
            "backfill_run_id": run.backfill_run_id,
            "sample_id": sample_id,
            "source_trade_date": trade_date,
            "evidence_snapshot": evidence,
            "calendar_reference_mode": "PERSISTED_RESEARCH_CONTROL",
            "version_selection_mode": "LOCKED_AT_BACKFILL_RUN",
            "created_at": run.created_at,
        }
        wrapper_payload["immutable_hash"] = backfill_hash(wrapper_payload)
        wrapper = HistoricalResearchSnapshot.model_validate(wrapper_payload)
        wrapper = await self._save_immutable(
            "ag_research_snapshots",
            wrapper,
            identity={"research_snapshot_id": wrapper.research_snapshot_id},
            hash_field="immutable_hash",
        )
        accepted = {
            key: documents
            for key, documents in resolved.items()
            if key
            in {
                "prices",
                "benchmark_prices",
                "financials",
                "news",
                "announcements",
                "market_context",
                "trading_calendar",
            }
        }
        refs = sorted(
            str(item["_reference"])
            for documents in accepted.values()
            for item in documents
        )
        data = ResolvedSnapshotData(
            snapshot=evidence,
            prices=accepted["prices"],
            benchmark_prices=accepted["benchmark_prices"],
            financials=accepted["financials"],
            news=accepted["news"],
            announcements=accepted["announcements"],
            market_context=accepted["market_context"],
            trading_calendar=accepted["trading_calendar"],
            input_refs=refs,
            excluded_refs=[],
            input_hash=backfill_hash(
                {
                    "research_snapshot_hash": wrapper.immutable_hash,
                    "documents": accepted,
                }
            ),
        )
        return wrapper, data

    async def _evaluate_proposals(
        self,
        *,
        run: HistoricalBackfillRun,
        sample_id: str,
        snapshot: HistoricalResearchSnapshot,
        proposals: list[QuantTradeProposal],
        as_of_trade_date: date,
    ) -> dict[str, list[str]]:
        subject_ids: list[str] = []
        label_ids: list[str] = []
        counterfactual_ids: list[str] = []
        attribution_ids: list[str] = []
        shadow_ids: list[str] = []
        for proposal in proposals:
            subject_payload = {
                "subject_type": "QUANT_PROPOSAL",
                "source_object_id": proposal.proposal_id,
                "source_object_version": proposal.strategy_version,
                "user_id": run.user_id,
                "candidate_id": None,
                "symbol": proposal.symbol,
                "market": proposal.market,
                "snapshot_id": snapshot.evidence_snapshot.snapshot_id,
                "analysis_id": None,
                "decision_trade_date": proposal.trade_date,
                "decision_cutoff_at": snapshot.evidence_snapshot.price_cutoff_at,
                "action": proposal.action_candidate,
                "decision_stage": "QUANT",
                "decision_status": proposal.status,
                "selected_for_execution": False,
                "actual_execution_exists": False,
                "entry_zone": proposal.entry_zone,
                "initial_position_pct": Decimal(str(proposal.initial_position_pct)),
                "max_position_pct": Decimal(str(proposal.max_position_pct)),
                "evidence_refs": proposal.evidence_refs,
                "lineage_ids": {
                    "backfill_run_id": run.backfill_run_id,
                    "sample_id": sample_id,
                    "run_mode": "RESEARCH_BACKFILL",
                    "research_only": "true",
                    "automated_execution_allowed": "false",
                    "proposal_id": proposal.proposal_id,
                    "strategy_id": proposal.strategy_id,
                    "strategy_version": proposal.strategy_version,
                },
                "evaluation_version": "evaluation-v1",
                "created_at": run.created_at,
            }
            subject_payload["immutable_hash"] = evaluation_hash(
                subject_payload,
                exclude={"subject_id", "immutable_hash", "created_at"},
            )
            subject = EvaluationSubject(
                subject_id=str(
                    uuid5(
                        NAMESPACE_URL,
                        f"research-evaluation-subject:{proposal.proposal_id}",
                    )
                ),
                **subject_payload,
            )
            stored_subject, _ = await self.evaluation_repository.save_immutable(
                "subjects",
                subject,
                identity={
                    "subject_type": subject.subject_type,
                    "source_object_id": subject.source_object_id,
                    "evaluation_version": subject.evaluation_version,
                },
                hash_field="immutable_hash",
            )
            labels = await self.labels.calculate_all(
                stored_subject, as_of_trade_date=as_of_trade_date
            )
            primary = next(
                (
                    item
                    for item in labels
                    if item.horizon == "10D"
                    and item.anchor_type == "DECISION_CLOSE"
                ),
                None,
            )
            signal = self._signal_counterfactual(stored_subject, primary)
            stored_signal, _ = await self.evaluation_repository.save_counterfactual(
                signal
            )
            shadow = await self.shadow.evaluate(
                backfill_run_id=run.backfill_run_id,
                sample_id=sample_id,
                proposal=proposal,
                primary_label=primary,
                now=run.created_at,
            )
            stored_shadow = await self._save_immutable(
                "ag_research_shadow_executions",
                shadow,
                identity={"shadow_execution_id": shadow.shadow_execution_id},
                hash_field="input_hash",
            )
            executable_counterfactual = self._shadow_counterfactual(
                stored_subject, stored_shadow
            )
            stored_executable, _ = (
                await self.evaluation_repository.save_counterfactual(
                    executable_counterfactual
                )
            )
            attribution = self.attributions.evaluate(
                stored_subject,
                labels,
                [stored_signal, stored_executable],
                [],
            )
            stored_attribution, _ = (
                await self.evaluation_repository.save_attribution(attribution)
            )
            subject_ids.append(stored_subject.subject_id)
            label_ids.extend(item.label_id for item in labels)
            counterfactual_ids.extend(
                [stored_signal.counterfactual_id, stored_executable.counterfactual_id]
            )
            attribution_ids.append(stored_attribution.attribution_id)
            shadow_ids.append(stored_shadow.shadow_execution_id)
        return {
            "evaluation_subject_ids": subject_ids,
            "horizon_label_ids": label_ids,
            "counterfactual_ids": counterfactual_ids,
            "attribution_ids": attribution_ids,
            "shadow_execution_ids": shadow_ids,
        }

    @staticmethod
    def _signal_counterfactual(subject, primary) -> CounterfactualEvaluation:
        status = (
            "CALCULATED"
            if primary is not None and primary.status == "CALCULATED"
            else "PENDING"
            if primary is not None and primary.status == "PENDING"
            else "INSUFFICIENT_DATA"
        )
        return_pct = (
            primary.raw_forward_return
            if status == "CALCULATED" and subject.action in {"HOLD", "WAIT"}
            else primary.action_aligned_return
            if status == "CALCULATED"
            else None
        )
        payload = {
            "subject_id": subject.subject_id,
            "mode": "SIGNAL_ONLY",
            "source_stage": subject.decision_stage,
            "comparison_stage": "RESEARCH_BACKFILL_SIGNAL",
            "status": status,
            "shadow_account_basis_id": None,
            "normalized_notional": None,
            "hypothetical_intent": {
                "run_mode": "RESEARCH_BACKFILL",
                "research_only": True,
                "automated_execution_allowed": False,
            },
            "hypothetical_order": None,
            "hypothetical_fills": [],
            "gross_pnl": None,
            "fees": None,
            "net_pnl": None,
            "return_pct": return_pct,
            "max_adverse_excursion": (
                primary.mae if status == "CALCULATED" else None
            ),
            "max_favorable_excursion": (
                primary.mfe if status == "CALCULATED" else None
            ),
            "execution_rule_version": COUNTERFACTUAL_VERSION,
            "fee_version": "not-applicable:signal-only",
            "matching_version": "not-applicable:signal-only",
            "input_refs": primary.data_refs if primary else [],
        }
        payload["input_hash"] = evaluation_hash(payload)
        return CounterfactualEvaluation(
            counterfactual_id=str(
                uuid5(
                    NAMESPACE_URL,
                    f"research-signal-counterfactual:{subject.subject_id}",
                )
            ),
            created_at=datetime.utcnow(),
            **payload,
        )

    @staticmethod
    def _shadow_counterfactual(
        subject, shadow: ResearchShadowExecution
    ) -> CounterfactualEvaluation:
        status_map = {
            "NOT_ELIGIBLE": "NOT_ELIGIBLE",
            "INSUFFICIENT_DATA": "INSUFFICIENT_DATA",
            "NO_FILL": "NO_FILL",
            "PARTIALLY_FILLED": "PARTIALLY_FILLED",
            "FILLED": "FILLED",
            "BLOCKED": "FAILED",
        }
        payload = {
            "subject_id": subject.subject_id,
            "mode": "EXECUTABLE_SHADOW",
            "source_stage": subject.decision_stage,
            "comparison_stage": "RESEARCH_BACKFILL_SHADOW",
            "status": status_map[shadow.status],
            "shadow_account_basis_id": (
                "historical-normalized-account-v1"
                if shadow.normalized_notional is not None
                else None
            ),
            "normalized_notional": shadow.normalized_notional,
            "hypothetical_intent": {
                "run_mode": "RESEARCH_BACKFILL",
                "research_only": True,
                "automated_execution_allowed": False,
                "proposal_id": shadow.proposal_id,
            },
            "hypothetical_order": shadow.order_payload,
            "hypothetical_fills": (
                [shadow.match_payload]
                if shadow.match_payload and shadow.status in {"FILLED", "PARTIALLY_FILLED"}
                else []
            ),
            "gross_pnl": None,
            "fees": (
                Decimal(str(shadow.fee_payload["total_fee"]))
                if shadow.fee_payload
                else None
            ),
            "net_pnl": None,
            "return_pct": shadow.net_return,
            "max_adverse_excursion": None,
            "max_favorable_excursion": None,
            "execution_rule_version": COUNTERFACTUAL_VERSION,
            "fee_version": shadow.fee_version,
            "matching_version": shadow.matching_version,
            "input_refs": [shadow.shadow_execution_id],
        }
        payload["input_hash"] = evaluation_hash(payload)
        return CounterfactualEvaluation(
            counterfactual_id=str(
                uuid5(
                    NAMESPACE_URL,
                    f"research-shadow-counterfactual:{subject.subject_id}",
                )
            ),
            created_at=datetime.utcnow(),
            **payload,
        )

    async def build_report(
        self, backfill_run_id: str, *, now: datetime | None = None
    ) -> HistoricalBackfillReport:
        now = now or datetime.utcnow()
        run_raw = clean_document(
            await self.db["ag_research_backfill_runs"].find_one(
                {"backfill_run_id": backfill_run_id}
            )
        )
        if run_raw is None:
            raise LookupError("HistoricalBackfillRun does not exist")
        run = HistoricalBackfillRun.model_validate(run_raw)
        samples = [
            clean_document(item)
            for item in await self.db["ag_research_backfill_samples"].find(
                {"backfill_run_id": backfill_run_id}
            ).to_list(length=None)
        ]
        coverage = [
            clean_document(item)
            for item in await self.db["ag_research_coverage"].find(
                {"backfill_run_id": backfill_run_id}
            ).to_list(length=None)
        ]
        factors = [
            clean_document(item)
            for item in await self.db["ag_research_factor_results"].find(
                {"backfill_run_id": backfill_run_id}
            ).to_list(length=None)
        ]
        regimes = [
            clean_document(item)
            for item in await self.db["ag_research_regime_results"].find(
                {"backfill_run_id": backfill_run_id}
            ).to_list(length=None)
        ]
        proposals = [
            clean_document(item)
            for item in await self.db["ag_research_quant_proposals"].find(
                {"backfill_run_id": backfill_run_id}
            ).to_list(length=None)
        ]
        shadows = [
            clean_document(item)
            for item in await self.db["ag_research_shadow_executions"].find(
                {"backfill_run_id": backfill_run_id}
            ).to_list(length=None)
        ]
        subjects = [
            clean_document(item)
            for item in await self.db["ag_eval_subjects"].find({}).to_list(length=None)
            if str((item.get("lineage_ids") or {}).get("backfill_run_id") or "")
            == backfill_run_id
        ]
        subject_ids = [str(item["subject_id"]) for item in subjects]
        labels = [
            clean_document(item)
            for item in await self.db["ag_eval_horizon_labels"].find(
                {"subject_id": {"$in": subject_ids}}
            ).to_list(length=None)
        ] if subject_ids else []
        attributions = [
            clean_document(item)
            for item in await self.db["ag_eval_attributions"].find(
                {"subject_id": {"$in": subject_ids}}
            ).to_list(length=None)
        ] if subject_ids else []
        sample_status = Counter(str(item.get("status")) for item in samples)
        quality_status = Counter(
            (
                "FAIL"
                if item.get("status") != "READY"
                else "WARN"
                if item.get("warnings")
                else "PASS"
            )
            for item in coverage
        )
        context_status = Counter(
            "READY"
            if (item.get("domains") or {})
            .get("MARKET_CONTEXT", {})
            .get("allowed_for_replay")
            is True
            else "BLOCKED"
            for item in coverage
        )
        labels_by_subject: dict[str, dict[str, dict[str, Any]]] = defaultdict(dict)
        for item in labels:
            if item.get("anchor_type") != "DECISION_CLOSE":
                continue
            labels_by_subject[str(item["subject_id"])][str(item["horizon"])] = item
        subject_by_source = {
            str(item["source_object_id"]): str(item["subject_id"])
            for item in subjects
        }
        subject_by_sample: dict[str, str] = {}
        for item in subjects:
            sample_id = str((item.get("lineage_ids") or {}).get("sample_id") or "")
            if sample_id:
                subject_by_sample.setdefault(sample_id, str(item["subject_id"]))

        factor_missing: dict[str, list[int]] = defaultdict(list)
        factor_horizon_returns: dict[str, dict[str, list[Decimal]]] = defaultdict(
            lambda: defaultdict(list)
        )
        factor_direction_hits: dict[str, dict[str, list[Decimal]]] = defaultdict(
            lambda: defaultdict(list)
        )
        factor_bucket_returns: dict[
            str, dict[str, dict[str, list[Decimal]]]
        ] = defaultdict(lambda: defaultdict(lambda: defaultdict(list)))
        for wrapper in factors:
            result = wrapper.get("factor_result") or {}
            factor_id = str(result.get("factor_id") or "UNKNOWN")
            factor_missing[factor_id].append(int(result.get("raw_value") is None))
            subject_id = subject_by_sample.get(str(wrapper.get("sample_id") or ""))
            if not subject_id:
                continue
            direction = str(result.get("direction"))
            bucket = _score_bucket(result.get("normalized_score"))
            for horizon, label in labels_by_subject.get(subject_id, {}).items():
                if (
                    label.get("status") != "CALCULATED"
                    or label.get("raw_forward_return") is None
                ):
                    continue
                raw_return = Decimal(str(label["raw_forward_return"]))
                factor_horizon_returns[factor_id][horizon].append(raw_return)
                if direction in {"POSITIVE", "NEGATIVE"}:
                    factor_direction_hits[factor_id][horizon].append(
                        raw_return if direction == "POSITIVE" else -raw_return
                    )
                if bucket:
                    factor_bucket_returns[factor_id][bucket][horizon].append(
                        raw_return
                    )
        regime_counter = Counter(
            str((item.get("regime_result") or {}).get("regime") or "INSUFFICIENT_DATA")
            for item in regimes
        )
        regime_metrics: dict[str, dict[str, list[Decimal]]] = defaultdict(
            lambda: defaultdict(list)
        )
        for wrapper in regimes:
            result = wrapper.get("regime_result") or {}
            regime_name = str(result.get("regime") or "INSUFFICIENT_DATA")
            subject_id = subject_by_sample.get(str(wrapper.get("sample_id") or ""))
            if not subject_id:
                continue
            for horizon, label in labels_by_subject.get(subject_id, {}).items():
                if label.get("status") != "CALCULATED":
                    continue
                if label.get("benchmark_return") is not None:
                    regime_metrics[regime_name][f"benchmark_return_{horizon}"].append(
                        Decimal(str(label["benchmark_return"]))
                    )
                if label.get("mae") is not None:
                    regime_metrics[regime_name][f"stock_mae_{horizon}"].append(
                        Decimal(str(label["mae"]))
                    )
        proposal_counter = Counter(
            str((item.get("quant_proposal") or {}).get("status"))
            for item in proposals
        )
        shadow_counter = Counter(str(item.get("status")) for item in shadows)
        triggered = [
            item.get("quant_proposal") or {}
            for item in proposals
            if (item.get("quant_proposal") or {}).get("status") == "TRIGGERED"
        ]
        entry_touch_count = 0
        entry_touch_evaluated = 0
        for proposal in triggered:
            subject_id = subject_by_source.get(str(proposal.get("proposal_id")))
            label = labels_by_subject.get(subject_id or "", {}).get("10D")
            if label and label.get("entry_zone_touched") is not None:
                entry_touch_evaluated += 1
                entry_touch_count += int(label["entry_zone_touched"] is True)
        fee_drag: list[Decimal] = []
        slippage_impact: list[Decimal] = []
        for item in shadows:
            if item.get("fee_payload") and item.get("normalized_notional"):
                fee_drag.append(
                    Decimal(str(item["fee_payload"]["total_fee"]))
                    / Decimal(str(item["normalized_notional"]))
                )
            match = item.get("match_payload") or {}
            if match.get("price") is not None and match.get("pricing_reference"):
                slippage_impact.append(
                    Decimal(str(match["price"]))
                    / Decimal(str(match["pricing_reference"]))
                    - Decimal("1")
                )
        horizon_counter = Counter(
            (str(item.get("horizon")), str(item.get("status")))
            for item in labels
            if item.get("anchor_type") == "DECISION_CLOSE"
        )
        attribution_counter = Counter(
            str(item.get("primary_category") or "UNKNOWN")
            for item in attributions
        )
        outcome_counter = Counter(
            str(item.get("outcome_class") or "UNRESOLVED")
            for item in attributions
        )
        report_payload = {
            "backfill_run_id": backfill_run_id,
            "status": (
                "READY"
                if sample_status["COMPLETED"] == run.total_samples
                else "PARTIAL"
                if sample_status["COMPLETED"] or sample_status[
                    "BACKFILL_SKIPPED_INSUFFICIENT_DATA"
                ]
                else "INSUFFICIENT_DATA"
            ),
            "planned_sample_count": run.total_samples,
            "completed_sample_count": sample_status["COMPLETED"],
            "skipped_sample_count": sample_status[
                "BACKFILL_SKIPPED_INSUFFICIENT_DATA"
            ],
            "failed_sample_count": sample_status["FAILED"]
            + sample_status["INTEGRITY_CONFLICT"],
            "data_summary": {
                "coverage_records": len(coverage),
                "data_quality_distribution": dict(sorted(quality_status.items())),
                "market_context_ready_samples": context_status["READY"],
                "market_context_blocked_samples": context_status["BLOCKED"],
                "coverage_warning_count": sum(
                    len(item.get("warnings") or []) for item in coverage
                ),
            },
            "factor_summary": {
                factor_id: {
                    "sample_count": len(values),
                    "missing_count": sum(values),
                    "missing_rate": (
                        Decimal(sum(values)) / Decimal(len(values))
                        if values
                        else None
                    ),
                    "horizon_returns": {
                        horizon: {
                            "sample_count": len(values_by_horizon),
                            "average_raw_return": _mean(values_by_horizon),
                            "direction_evaluated_count": len(
                                factor_direction_hits[factor_id].get(horizon, [])
                            ),
                            "direction_hit_rate": (
                                Decimal(
                                    sum(
                                        value > 0
                                        for value in factor_direction_hits[factor_id].get(
                                            horizon, []
                                        )
                                    )
                                )
                                / Decimal(
                                    len(factor_direction_hits[factor_id][horizon])
                                )
                                if factor_direction_hits[factor_id].get(horizon)
                                else None
                            ),
                        }
                        for horizon, values_by_horizon in sorted(
                            factor_horizon_returns.get(factor_id, {}).items()
                        )
                    },
                    "normalized_score_bucket_returns": {
                        bucket: {
                            horizon: {
                                "sample_count": len(bucket_values),
                                "average_raw_return": _mean(bucket_values),
                            }
                            for horizon, bucket_values in sorted(horizons.items())
                        }
                        for bucket, horizons in sorted(
                            factor_bucket_returns.get(factor_id, {}).items()
                        )
                    },
                }
                for factor_id, values in sorted(factor_missing.items())
            },
            "regime_summary": {
                "sample_count": len(regimes),
                "distribution": dict(sorted(regime_counter.items())),
                "forward_metrics": {
                    regime_name: {
                        metric: {
                            "sample_count": len(metric_values),
                            "average": _mean(metric_values),
                            "worst": min(metric_values) if metric_values else None,
                        }
                        for metric, metric_values in sorted(metrics.items())
                    }
                    for regime_name, metrics in sorted(regime_metrics.items())
                },
            },
            "strategy_summary": {
                "proposal_count": len(proposals),
                "status_distribution": dict(sorted(proposal_counter.items())),
                "triggered_count": len(triggered),
                "entry_touch_evaluated_count": entry_touch_evaluated,
                "entry_touch_count": entry_touch_count,
                "entry_touch_rate": (
                    Decimal(entry_touch_count) / Decimal(entry_touch_evaluated)
                    if entry_touch_evaluated
                    else None
                ),
                "shadow_fill_count": shadow_counter["FILLED"]
                + shadow_counter["PARTIALLY_FILLED"],
                "shadow_fill_rate": (
                    Decimal(
                        shadow_counter["FILLED"]
                        + shadow_counter["PARTIALLY_FILLED"]
                    )
                    / Decimal(len(shadows))
                    if shadows
                    else None
                ),
            },
            "model_summary": {
                "model_replay_requested": False,
                "normal_runs": 0,
                "top_runs": 0,
                "note": "deterministic first round completed without model replay",
            },
            "risk_execution_summary": {
                "consensus_runs": 0,
                "hard_risk_runs": 0,
                "shadow_status_distribution": dict(sorted(shadow_counter.items())),
                "average_fee_drag_pct": _mean(fee_drag),
                "average_slippage_impact_pct": _mean(slippage_impact),
                "production_order_count": 0,
            },
            "evaluation_summary": {
                "subject_count": len(subjects),
                "decision_close_horizon_status": {
                    f"{key[0]}:{key[1]}": value
                    for key, value in sorted(horizon_counter.items())
                },
                "attribution_distribution": dict(
                    sorted(attribution_counter.items())
                ),
                "outcome_distribution": dict(sorted(outcome_counter.items())),
                "avoided_loss_count": outcome_counter["AVOIDED_LOSS"],
                "missed_opportunity_count": outcome_counter[
                    "MISSED_OPPORTUNITY"
                ],
                "unknown_count": attribution_counter["UNKNOWN"],
                "unknown_rate": (
                    Decimal(attribution_counter["UNKNOWN"])
                    / Decimal(len(attributions))
                    if attributions
                    else None
                ),
            },
            "caveats": [
                "Historical research replay, not live production performance.",
                "Research shadow results are not actual account returns.",
                "This report is not investment advice and does not prove future validity.",
                "Historical industry-relative return is null where point-in-time mapping is unavailable.",
                "Daily sources without explicit limit prices block executable shadow matching rather than inferring limits.",
            ],
            "input_hash": backfill_hash(
                {
                    "run_input_hash": run.input_hash,
                    "sample_result_hashes": sorted(
                        str(item.get("result_hash")) for item in samples
                    ),
                }
            ),
        }
        report_payload["report_hash"] = backfill_hash(report_payload)
        report = HistoricalBackfillReport(
            report_id=str(
                uuid5(
                    NAMESPACE_URL,
                    f"research-backfill-report:{backfill_run_id}",
                )
            ),
            created_at=now,
            **report_payload,
        )
        collection = self.db["ag_research_backfill_reports"]
        existing_raw = clean_document(
            await collection.find_one({"backfill_run_id": backfill_run_id})
        )
        if existing_raw is None:
            await collection.insert_one(model_document(report))
            return report
        existing = HistoricalBackfillReport.model_validate(existing_raw)
        if existing.report_hash == report.report_hash:
            return existing
        if (
            existing.planned_sample_count != report.planned_sample_count
            or existing.completed_sample_count > report.completed_sample_count
            or existing.skipped_sample_count > report.skipped_sample_count
        ):
            raise HistoricalBackfillIntegrityConflict(
                "historical backfill report state cannot regress"
            )
        result = await collection.replace_one(
            {
                "backfill_run_id": backfill_run_id,
                "report_hash": existing.report_hash,
            },
            model_document(report),
        )
        if result.matched_count != 1:
            raise HistoricalBackfillIntegrityConflict(
                "historical backfill report changed concurrently"
            )
        return report

    async def production_state(self) -> dict[str, Any]:
        result = {}
        for collection in PRODUCTION_TRADING_COLLECTIONS:
            documents = await self.db[collection].find({}).to_list(length=None)
            result[collection] = {
                "count": len(documents),
                "content_hash": backfill_hash(
                    sorted(
                        (clean_document(item) for item in documents),
                        key=lambda item: backfill_hash(item),
                    )
                ),
            }
        return result

    async def _save_quant_wrappers(
        self,
        *,
        run: HistoricalBackfillRun,
        sample_id: str,
        kind: str,
        models: list,
    ) -> None:
        for model in models:
            await self._save_wrapper(
                "ag_research_factor_results",
                identity={"result_id": model.result_id},
                payload_name=kind,
                payload=model,
                metadata={
                    "backfill_run_id": run.backfill_run_id,
                    "sample_id": sample_id,
                    "result_id": model.result_id,
                    "snapshot_id": model.snapshot_id,
                },
                immutable_hash=model.input_hash,
            )

    async def _save_wrapper(
        self,
        collection: str,
        *,
        identity: dict[str, Any],
        payload_name: str,
        payload,
        metadata: dict[str, Any],
        immutable_hash: str,
    ) -> dict[str, Any]:
        document = {
            **metadata,
            "run_mode": "RESEARCH_BACKFILL",
            "research_only": True,
            "automated_execution_allowed": False,
            payload_name: payload.model_dump(mode="python"),
            "immutable_hash": immutable_hash,
            "created_at": datetime.utcnow(),
            "schema_version": "alphaguard-historical-backfill-v1",
        }
        existing = clean_document(await self.db[collection].find_one(identity))
        if existing:
            if existing.get("immutable_hash") != immutable_hash:
                raise HistoricalBackfillIntegrityConflict(
                    f"immutable {collection} identity conflict"
                )
            return existing
        await self.db[collection].insert_one(to_mongo_value(document))
        return document

    async def _save_immutable(
        self,
        collection: str,
        model,
        *,
        identity: dict[str, Any],
        hash_field: str,
    ):
        existing = clean_document(await self.db[collection].find_one(identity))
        if existing:
            stored = type(model).model_validate(existing)
            if getattr(stored, hash_field) != getattr(model, hash_field):
                raise HistoricalBackfillIntegrityConflict(
                    f"immutable {collection} identity conflict"
                )
            return stored
        await self.db[collection].insert_one(model_document(model))
        return model

    async def _fail_sample(
        self,
        initial: HistoricalBackfillSample,
        exc: Exception,
        *,
        status: str,
    ) -> HistoricalBackfillSample:
        error = {
            "attempt_number": initial.attempt_count,
            "error_type": type(exc).__name__,
            "error_message": str(exc)[:500],
            "at": datetime.utcnow(),
        }
        failed = initial.model_copy(
            update={
                "status": status,
                "reason": f"{type(exc).__name__}: {str(exc)[:300]}",
                "error_history": [*initial.error_history, error],
                "updated_at": datetime.utcnow(),
            }
        )
        await self.db["ag_research_backfill_samples"].replace_one(
            {"sample_id": initial.sample_id}, model_document(failed)
        )
        await self._record_event(
            "HISTORICAL_BACKFILL_SAMPLE_FAILED",
            backfill_run_id=initial.backfill_run_id,
            sample_id=initial.sample_id,
            symbol=initial.symbol,
            trade_date=initial.trade_date,
            status=failed.status,
            error_type=type(exc).__name__,
        )
        return failed

    async def _record_event(
        self,
        event_type: str,
        *,
        backfill_run_id: str,
        created_at: datetime | None = None,
        **details: Any,
    ) -> None:
        identity = {
            "event_type": event_type,
            "backfill_run_id": backfill_run_id,
            "sample_id": details.get("sample_id"),
            "status": details.get("status"),
            "input_hash": details.get("input_hash"),
            "result_hash": details.get("result_hash"),
        }
        event = {
            "event_id": str(
                uuid5(
                    NAMESPACE_URL,
                    f"alphaguard:historical-backfill-event:{backfill_hash(identity)}",
                )
            ),
            "event_type": event_type,
            "backfill_run_id": backfill_run_id,
            **details,
            "run_mode": "RESEARCH_BACKFILL",
            "research_only": True,
            "automated_execution_allowed": False,
            "created_at": created_at or datetime.utcnow(),
            "schema_version": "alphaguard-historical-backfill-v1",
        }
        await self.db["ag_research_backfill_events"].update_one(
            {"event_id": event["event_id"]},
            {"$setOnInsert": to_mongo_value(event)},
            upsert=True,
        )

    @staticmethod
    def sample_id(backfill_run_id: str, symbol: str, trade_date: date) -> str:
        return str(
            uuid5(
                NAMESPACE_URL,
                f"alphaguard:historical-sample:{backfill_run_id}:{symbol}:{trade_date}",
            )
        )
