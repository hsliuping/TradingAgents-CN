"""Research-only validation of the EvidenceSnapshot v2 window contract."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any
from uuid import NAMESPACE_URL, uuid5

from app.services.alphaguard.benchmark_price_window_service import (
    BenchmarkPriceWindowService,
)
from app.services.alphaguard.evidence_snapshot_service import (
    EvidenceSnapshotService,
)
from app.services.alphaguard.factor_registry import FactorRegistry
from app.services.alphaguard.market_context_window_service import (
    MarketContextWindowService,
)
from app.services.alphaguard.paper_storage import (
    clean_document,
    mongo_date,
    to_mongo_value,
)
from app.services.alphaguard.production_data_config import (
    cn_price_limit_policy,
    production_market_context_policy,
)
from app.services.alphaguard.quant_config import sha256_value
from app.services.alphaguard.quant_research_pipeline import QuantResearchPipeline
from app.services.alphaguard.real_data_candidate_service import (
    CandidateRealDataService,
)
from app.services.alphaguard.strategy_registry import STRATEGY_SET_VERSION
from tradingagents.alphaguard.evidence_schemas import (
    EVIDENCE_SNAPSHOT_SCHEMA_VERSION_V2,
    EvidenceSnapshot,
)
from tradingagents.alphaguard.production_data_schemas import (
    BenchmarkPriceWindowManifest,
)


class EvidenceContractValidationError(RuntimeError):
    pass


class _ResearchEvidenceDB:
    """Redirect every quant write while preserving production source reads."""

    COLLECTION_MAP = {
        "ag_evidence_snapshots": (
            "ag_research_evidence_contract_snapshots"
        ),
        "ag_data_quality_reports": (
            "ag_research_evidence_contract_quality"
        ),
        "ag_factor_results": (
            "ag_research_evidence_contract_factor_results"
        ),
        "ag_regime_results": (
            "ag_research_evidence_contract_regime_results"
        ),
        "ag_quant_proposals": (
            "ag_research_evidence_contract_proposals"
        ),
        "ag_quant_audit_events": (
            "ag_research_evidence_contract_events"
        ),
    }

    def __init__(self, db):
        self.db = db

    def __getitem__(self, name):
        return self.db[self.COLLECTION_MAP.get(name, name)]


class EvidenceContractValidationService:
    """Use frozen formal inputs without creating a production decision identity."""

    SYMBOLS = ("600519", "601318", "000333", "002594", "300750")
    SNAPSHOT_COLLECTION = "ag_research_evidence_contract_snapshots"
    RUN_COLLECTION = "ag_research_evidence_contract_runs"

    def __init__(self, db):
        self.db = db
        self.research_db = _ResearchEvidenceDB(db)
        self.data = CandidateRealDataService(db)
        self.snapshots = EvidenceSnapshotService(
            db=self.research_db,
            enable_shadow_hook=False,
        )
        self.quant = QuantResearchPipeline(self.research_db)

    async def run(
        self,
        *,
        user_id: str,
        source_trade_date: date,
        cutoff_at: datetime,
        execute: bool,
        symbols: list[str] | None = None,
    ) -> dict[str, Any]:
        selected = sorted(set(symbols or self.SYMBOLS))
        if set(selected) != set(self.SYMBOLS):
            raise EvidenceContractValidationError(
                "validation is limited to the five existing selected candidates"
            )
        if cutoff_at.date() != source_trade_date or cutoff_at.hour < 15:
            raise EvidenceContractValidationError(
                "validation cutoff must be after close on source trade date"
            )
        context_policy = production_market_context_policy()
        contexts = await self.db["ag_market_contexts"].find(
            {
                "market": "CN",
                "trade_date": mongo_date(source_trade_date),
                "calculation_status": "READY",
                "calculation_version": context_policy[
                    "calculation_version"
                ],
                "available_at": {"$lte": cutoff_at},
                "collected_at": {"$lte": cutoff_at},
            }
        ).limit(2).to_list(length=2)
        if len(contexts) != 1:
            raise EvidenceContractValidationError(
                "exact READY production MarketContext is not unique"
            )
        context = clean_document(contexts[0])
        assert context is not None
        context_window = await MarketContextWindowService(self.db).get_ready(
            as_of_trade_date=source_trade_date,
            cutoff_at=cutoff_at,
        )
        benchmark_result = await BenchmarkPriceWindowService(self.db).build(
            as_of_trade_date=source_trade_date,
            cutoff_at=cutoff_at,
            execute=execute,
        )
        benchmark_window = BenchmarkPriceWindowManifest.model_validate(
            benchmark_result["manifest"]
        )
        factor_versions = await FactorRegistry(self.db).get_version_set(
            require_registered=True
        )
        trading_policy = cn_price_limit_policy()
        status_rows = await self.db["ag_security_trading_statuses"].find(
            {
                "symbol": {"$in": selected},
                "market": "CN",
                "trade_date": mongo_date(source_trade_date),
                "calculation_status": "READY",
                "calculation_version": trading_policy[
                    "calculation_version"
                ],
                "available_at": {"$lte": cutoff_at},
                "collected_at": {"$lte": cutoff_at},
            }
        ).to_list(length=None)
        statuses = {
            str(item.get("symbol")): clean_document(item)
            for item in status_rows
        }
        if any(symbol not in statuses for symbol in selected):
            raise EvidenceContractValidationError(
                "versioned trading status is incomplete for validation symbols"
            )

        results: list[dict[str, Any]] = []
        for symbol in selected:
            precheck = await self.data.precheck_candidate(
                symbol=symbol,
                trade_date=source_trade_date,
                cutoff_at=cutoff_at,
            )
            raw_refs = {
                key: list(value)
                for key, value in precheck["raw_refs"].items()
            }
            raw_refs["benchmark_prices"] = [
                f"index_daily:{quote_id}"
                for quote_id in benchmark_window.ordered_quote_ids
            ]
            raw_refs["market_context_window"] = [
                f"market_context_window:{context_window.manifest_id}"
            ]
            raw_refs["benchmark_price_window"] = [
                f"benchmark_price_window:{benchmark_window.manifest_id}"
            ]
            status = statuses[symbol]
            assert status is not None
            raw_refs["trading_status"] = [
                f"trading_status:{status['trading_status_id']}"
            ]
            existing_rows = await self.db[self.SNAPSHOT_COLLECTION].find(
                {
                    "user_id": str(user_id),
                    "symbol": symbol,
                    "market": "CN",
                    "trade_date": mongo_date(source_trade_date),
                    "schema_version": EVIDENCE_SNAPSHOT_SCHEMA_VERSION_V2,
                }
            ).limit(2).to_list(length=2)
            if len(existing_rows) > 1:
                raise EvidenceContractValidationError(
                    f"INTEGRITY_CONFLICT: duplicate research Snapshot for {symbol}"
                )
            snapshot: EvidenceSnapshot | None = None
            snapshot_action = "WOULD_CREATE"
            if existing_rows:
                snapshot = EvidenceSnapshot.model_validate(
                    clean_document(existing_rows[0])
                )
                expected_refs = {
                    key: sorted(value)
                    for key, value in sorted(raw_refs.items())
                }
                if snapshot.raw_refs != expected_refs or (
                    snapshot.benchmark_price_window_manifest_hash
                    != benchmark_window.manifest_hash
                ):
                    raise EvidenceContractValidationError(
                        f"INTEGRITY_CONFLICT: research Snapshot changed for {symbol}"
                    )
                snapshot_action = "REUSED"
            elif execute:
                snapshot = await self.snapshots.create(
                    user_id=str(user_id),
                    payload={
                        "analysis_id": (
                            "research:evidence-contract-validation:"
                            f"{symbol}:{source_trade_date.isoformat()}"
                        ),
                        "symbol": symbol,
                        "market": "CN",
                        "trade_date": source_trade_date,
                        "price_cutoff_at": cutoff_at,
                        "news_cutoff_at": cutoff_at,
                        "announcement_cutoff_at": cutoff_at,
                        "price_data_version": precheck["versions"][
                            "price_data_version"
                        ],
                        "financial_data_version": precheck["versions"][
                            "financial_data_version"
                        ],
                        "news_data_version": precheck["versions"][
                            "news_data_version"
                        ],
                        "market_context_id": str(context["context_id"]),
                        "market_context_hash": str(context["content_hash"]),
                        "market_context_window_manifest_id": (
                            context_window.manifest_id
                        ),
                        "market_context_window_manifest_hash": (
                            context_window.manifest_hash
                        ),
                        "benchmark_price_window_manifest_id": (
                            benchmark_window.manifest_id
                        ),
                        "benchmark_price_window_manifest_hash": (
                            benchmark_window.manifest_hash
                        ),
                        "required_benchmark_count": (
                            benchmark_window.required_count
                        ),
                        "actual_benchmark_count": (
                            benchmark_window.actual_count
                        ),
                        "evidence_contract_status": "COMPLETE",
                        "raw_refs": raw_refs,
                        "factor_version_set": factor_versions,
                        "strategy_version": STRATEGY_SET_VERSION,
                        "required_sources": [
                            "prices",
                            "benchmark_prices",
                            "market_context",
                            "market_context_window",
                            "benchmark_price_window",
                            "trading_status",
                            "trading_calendar",
                        ],
                        "schema_version": (
                            EVIDENCE_SNAPSHOT_SCHEMA_VERSION_V2
                        ),
                    },
                )
                snapshot_action = "CREATED"

            proposals = []
            regime = None
            factor_count = 0
            if execute and snapshot is not None:
                proposals = await self.quant.evaluate(
                    snapshot.snapshot_id,
                    user_id=str(user_id),
                    candidate_id=None,
                    trace_id=(
                        "evidence-contract-validation:"
                        f"{source_trade_date.isoformat()}:{symbol}"
                    ),
                )
                factor_count = await self.db[
                    "ag_research_evidence_contract_factor_results"
                ].count_documents({"snapshot_id": snapshot.snapshot_id})
                regime = clean_document(
                    await self.db[
                        "ag_research_evidence_contract_regime_results"
                    ].find_one({"snapshot_id": snapshot.snapshot_id})
                )
            results.append(
                {
                    "symbol": symbol,
                    "validation_snapshot_id": (
                        snapshot.snapshot_id if snapshot else None
                    ),
                    "snapshot_action": snapshot_action,
                    "snapshot_schema_version": (
                        snapshot.schema_version
                        if snapshot
                        else EVIDENCE_SNAPSHOT_SCHEMA_VERSION_V2
                    ),
                    "benchmark_manifest_id": benchmark_window.manifest_id,
                    "benchmark_count": benchmark_window.actual_count,
                    "benchmark_window_start": (
                        benchmark_window.start_trade_date.isoformat()
                    ),
                    "benchmark_window_end": (
                        benchmark_window.end_trade_date.isoformat()
                    ),
                    "market_context_manifest_id": context_window.manifest_id,
                    "market_context_count": context_window.actual_count,
                    "factor_result_count": factor_count,
                    "regime_result": (
                        {
                            "regime_result_id": regime.get(
                                "regime_result_id"
                            ),
                            "calculation_status": regime.get(
                                "calculation_status"
                            ),
                            "regime": regime.get("regime"),
                            "input_hash": regime.get("input_hash"),
                            "evidence": regime.get("evidence"),
                        }
                        if regime
                        else None
                    ),
                    "proposal_results": [
                        {
                            "proposal_id": item.proposal_id,
                            "strategy_id": item.strategy_id,
                            "status": item.status,
                            "action": item.action_candidate,
                            "reason_codes": item.reason_codes,
                            "input_hash": item.input_hash,
                        }
                        for item in proposals
                    ],
                }
            )

        run_id = str(
            uuid5(
                NAMESPACE_URL,
                (
                    "alphaguard:evidence-contract-validation:"
                    f"{source_trade_date.isoformat()}:"
                    f"{benchmark_window.manifest_hash}"
                ),
            )
        )
        result_hash = sha256_value(
            {
                "run_id": run_id,
                "source_trade_date": source_trade_date,
                "benchmark_manifest_hash": benchmark_window.manifest_hash,
                "market_context_manifest_hash": context_window.manifest_hash,
                "results": [
                    {
                        key: value
                        for key, value in item.items()
                        if key != "snapshot_action"
                    }
                    for item in results
                ],
            }
        )
        action = "WOULD_CREATE"
        if execute:
            existing_run = clean_document(
                await self.db[self.RUN_COLLECTION].find_one(
                    {"validation_run_id": run_id}
                )
            )
            run_document = {
                "validation_run_id": run_id,
                "run_mode": "EVIDENCE_CONTRACT_VALIDATION",
                "research_only": True,
                "automated_execution_allowed": False,
                "source_trade_date": source_trade_date,
                "benchmark_manifest_id": benchmark_window.manifest_id,
                "market_context_manifest_id": context_window.manifest_id,
                "result_hash": result_hash,
                "results": results,
                "created_at": datetime.utcnow(),
                "schema_version": "evidence-contract-validation-v1",
            }
            if existing_run:
                if existing_run.get("result_hash") != result_hash:
                    raise EvidenceContractValidationError(
                        "INTEGRITY_CONFLICT: validation result changed"
                    )
                action = "REUSED"
            else:
                await self.db[self.RUN_COLLECTION].insert_one(
                    to_mongo_value(run_document)
                )
                action = "CREATED"
        return {
            "validation_run_id": run_id,
            "run_mode": "EVIDENCE_CONTRACT_VALIDATION",
            "research_only": True,
            "automated_execution_allowed": False,
            "write": execute,
            "action": action,
            "source_trade_date": source_trade_date.isoformat(),
            "benchmark_manifest_action": benchmark_result["action"],
            "benchmark_manifest_id": benchmark_window.manifest_id,
            "benchmark_manifest_hash": benchmark_window.manifest_hash,
            "result_hash": result_hash,
            "results": results,
        }
