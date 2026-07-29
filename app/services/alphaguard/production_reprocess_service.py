"""Create-only production-data reprocessing under an execution prohibition."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any
from uuid import NAMESPACE_URL, uuid5

from app.services.alphaguard.benchmark_price_window_service import (
    BenchmarkPriceWindowService,
)
from app.services.alphaguard.champion_resolver import ChampionResolver
from app.services.alphaguard.consensus_engine import ConsensusEngine
from app.services.alphaguard.decision_context_builder import (
    DecisionContextBuilder,
)
from app.services.alphaguard.decision_model_runner import (
    ExistingProviderDecisionModelRunner,
)
from app.services.alphaguard.evidence_snapshot_service import (
    EvidenceSnapshotService,
)
from app.services.alphaguard.execution_mode_safety_gate import (
    ExecutionModeBlockedError,
)
from app.services.alphaguard.execution_outbox_service import (
    ExecutionOutboxService,
)
from app.services.alphaguard.factor_registry import FactorRegistry
from app.services.alphaguard.hard_risk_engine import HardRiskEngine
from app.services.alphaguard.market_context_window_service import (
    MarketContextWindowService,
)
from app.services.alphaguard.paper_storage import (
    clean_document,
    mongo_date,
    safe_error_message,
    to_mongo_value,
)
from app.services.alphaguard.production_data_config import (
    cn_price_limit_policy,
    production_market_context_policy,
)
from app.services.alphaguard.quant_config import sha256_value
from app.services.alphaguard.quant_research_pipeline import (
    QuantResearchPipeline,
)
from app.services.alphaguard.real_data_candidate_service import (
    CandidateRealDataService,
)
from app.services.alphaguard.risk_policy_registry import RiskPolicyRegistry
from app.services.alphaguard.strategy_registry import STRATEGY_SET_VERSION
from tradingagents.alphaguard.evidence_schemas import (
    EVIDENCE_SNAPSHOT_SCHEMA_VERSION_V2,
    EvidenceSnapshot,
)
from tradingagents.alphaguard.production_data_schemas import (
    BenchmarkPriceWindowManifest,
    MarketContextWindowManifest,
)


RUN_MODE = "PRODUCTION_REPROCESS"
REPROCESS_REASON = "EVIDENCE_CONTRACT_UPGRADE"
EVIDENCE_CONTRACT_VERSION = "evidence-contract-v2"
REPROCESS_SCHEMA_VERSION = "production-evidence-reprocess-v1"


class ProductionReprocessError(RuntimeError):
    pass


class ProductionReprocessConflict(ProductionReprocessError):
    pass


class ProductionReprocessService:
    """Re-evaluate frozen production evidence without becoming realtime."""

    SYMBOLS = ("600519", "601318", "000333", "002594", "300750")
    RUN_COLLECTION = "ag_production_reprocess_runs"
    EVALUATION_COLLECTION = "ag_production_reprocess_evaluation_subjects"

    def __init__(self, db):
        self.db = db
        self.data = CandidateRealDataService(db)
        self.snapshots = EvidenceSnapshotService(
            db=db,
            enable_shadow_hook=False,
        )
        self.quant = QuantResearchPipeline(db)
        self.contexts = DecisionContextBuilder(db)

    @staticmethod
    def _stable_id(namespace: str, payload_hash: str) -> str:
        return str(
            uuid5(
                NAMESPACE_URL,
                f"alphaguard:{namespace}:{payload_hash}",
            )
        )

    async def _top_confirmed_account(
        self, *, user_id: str
    ) -> dict[str, Any]:
        rows = await self.db["ag_paper_accounts"].find(
            {
                "user_id": str(user_id),
                "market": "CN",
                "account_type": "PAPER_TOP_CONFIRMED",
                "status": "ACTIVE",
            }
        ).limit(2).to_list(length=2)
        if len(rows) != 1:
            raise ProductionReprocessError(
                "exact active PAPER_TOP_CONFIRMED account is not available"
            )
        account = clean_document(rows[0])
        assert account is not None
        return account

    async def _source_inputs(
        self,
        *,
        user_id: str,
        source_trade_date: date,
        cutoff_at: datetime,
        symbols: list[str],
        execute: bool,
    ) -> dict[str, Any]:
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
            raise ProductionReprocessError(
                "exact READY production MarketContext is not unique"
            )
        context = clean_document(contexts[0])
        assert context is not None

        benchmark_result = await BenchmarkPriceWindowService(self.db).build(
            as_of_trade_date=source_trade_date,
            cutoff_at=cutoff_at,
            execute=execute,
        )
        context_result = await MarketContextWindowService(self.db).build(
            as_of_trade_date=source_trade_date,
            cutoff_at=cutoff_at,
            execute=execute,
        )
        benchmark = BenchmarkPriceWindowManifest.model_validate(
            benchmark_result["manifest"]
        )
        context_window = MarketContextWindowManifest.model_validate(
            context_result["manifest"]
        )
        if benchmark.required_count != 61 or benchmark.actual_count != 61:
            raise ProductionReprocessError(
                "production Benchmark manifest is not COMPLETE 61/61"
            )

        trading_policy = cn_price_limit_policy()
        status_rows = await self.db["ag_security_trading_statuses"].find(
            {
                "symbol": {"$in": symbols},
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
        if any(symbol not in statuses for symbol in symbols):
            raise ProductionReprocessError(
                "versioned trading status is incomplete"
            )
        account = await self._top_confirmed_account(user_id=user_id)
        factor_versions = await FactorRegistry(self.db).get_version_set(
            require_registered=True
        )
        champion_refs = await ChampionResolver(
            self.db
        ).resolve_required_components(
            market="CN",
            as_of_trade_date=source_trade_date,
        )

        prepared: dict[str, dict[str, Any]] = {}
        for symbol in symbols:
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
                for quote_id in benchmark.ordered_quote_ids
            ]
            raw_refs["market_context_window"] = [
                f"market_context_window:{context_window.manifest_id}"
            ]
            raw_refs["benchmark_price_window"] = [
                f"benchmark_price_window:{benchmark.manifest_id}"
            ]
            status = statuses[symbol]
            assert status is not None
            raw_refs["trading_status"] = [
                f"trading_status:{status['trading_status_id']}"
            ]
            raw_refs["accounts"] = [
                f"ag_paper_account:{account['account_id']}"
            ]
            raw_refs = {
                key: sorted(set(values))
                for key, values in sorted(raw_refs.items())
            }
            reprocess_input_hash = sha256_value(
                {
                    "user_id": str(user_id),
                    "market": "CN",
                    "symbol": symbol,
                    "trade_date": source_trade_date,
                    "schema_version": EVIDENCE_SNAPSHOT_SCHEMA_VERSION_V2,
                    "evidence_contract_version": (
                        EVIDENCE_CONTRACT_VERSION
                    ),
                    "run_mode": RUN_MODE,
                    "champion_version_refs": champion_refs,
                    "versions": precheck["versions"],
                    "raw_refs": raw_refs,
                    "market_context_id": context["context_id"],
                    "market_context_hash": context["content_hash"],
                    "market_context_window_manifest_id": (
                        context_window.manifest_id
                    ),
                    "market_context_window_manifest_hash": (
                        context_window.manifest_hash
                    ),
                    "benchmark_price_window_manifest_id": (
                        benchmark.manifest_id
                    ),
                    "benchmark_price_window_manifest_hash": (
                        benchmark.manifest_hash
                    ),
                    "cutoff_at": cutoff_at,
                }
            )
            prepared[symbol] = {
                "precheck": precheck,
                "raw_refs": raw_refs,
                "reprocess_input_hash": reprocess_input_hash,
                "snapshot_id": self._stable_id(
                    "production-reprocess-snapshot",
                    reprocess_input_hash,
                ),
            }
        return {
            "context": context,
            "benchmark": benchmark,
            "benchmark_action": benchmark_result["action"],
            "context_window": context_window,
            "context_window_action": context_result["action"],
            "statuses": statuses,
            "account": account,
            "factor_versions": factor_versions,
            "champion_refs": champion_refs,
            "prepared": prepared,
        }

    async def _save_reprocess_evaluation(
        self,
        *,
        user_id: str,
        snapshot: EvidenceSnapshot,
        proposal,
    ) -> tuple[str, str]:
        identity_hash = sha256_value(
            {
                "evaluation_mode": RUN_MODE,
                "source_object_id": proposal.proposal_id,
                "snapshot_id": snapshot.snapshot_id,
                "evaluation_version": "production-reprocess-evaluation-v1",
            }
        )
        subject_id = self._stable_id(
            "production-reprocess-evaluation",
            identity_hash,
        )
        payload = {
            "reprocess_evaluation_subject_id": subject_id,
            "evaluation_mode": RUN_MODE,
            "actual_production_decision": False,
            "actual_execution": False,
            "user_id": str(user_id),
            "symbol": proposal.symbol,
            "market": proposal.market,
            "source_trade_date": snapshot.trade_date,
            "snapshot_id": snapshot.snapshot_id,
            "source_object_id": proposal.proposal_id,
            "source_object_type": "QUANT_PROPOSAL",
            "decision_status": proposal.status,
            "action": proposal.action_candidate,
            "horizon_statuses": {
                horizon: "PENDING"
                for horizon in ("1D", "5D", "10D", "20D")
            },
            "input_hash": identity_hash,
            "created_at": datetime.utcnow(),
            "schema_version": "production-reprocess-evaluation-v1",
        }
        payload["result_hash"] = sha256_value(
            {
                key: value
                for key, value in payload.items()
                if key not in {"created_at", "result_hash"}
            }
        )
        existing = clean_document(
            await self.db[self.EVALUATION_COLLECTION].find_one(
                {"reprocess_evaluation_subject_id": subject_id}
            )
        )
        if existing is not None:
            if existing.get("result_hash") != payload["result_hash"]:
                raise ProductionReprocessConflict(
                    "INTEGRITY_CONFLICT: reprocess evaluation changed"
                )
            return subject_id, "REUSED"
        document = to_mongo_value(payload)
        document["_id"] = subject_id
        await self.db[self.EVALUATION_COLLECTION].insert_one(document)
        return subject_id, "CREATED"

    async def _model_validation(
        self,
        *,
        user_id: str,
        proposals: list,
        account: dict[str, Any],
        call_real_model: bool,
        trace_id: str,
    ) -> dict[str, Any]:
        chosen = sorted(
            proposals,
            key=lambda item: (
                item.status != "TRIGGERED",
                item.symbol,
                item.strategy_id,
            ),
        )[0]
        context, resolved = await self.contexts.build(
            chosen.proposal_id,
            user_id=str(user_id),
            allow_reprocess_model_validation=True,
            persist=False,
        )
        configuration = (
            await ExistingProviderDecisionModelRunner.configuration_status(
                context
            )
        )
        base = {
            "validation_mode": "REAL_MODEL_CONFIGURATION_VALIDATION",
            "research_safe_input": True,
            "actual_production_decision": False,
            "automated_execution_allowed": False,
            "snapshot_id": context.snapshot_id,
            "proposal_id": context.quant_proposal_id,
            "proposal_status": context.quant_proposal.status,
            "context_id": context.decision_context_id,
            "context_hash": context.context_hash,
            "configuration": configuration,
            "normal": None,
            "top": None,
            "consensus": None,
            "hard_risk": None,
        }
        if not all(
            item["credential_configured"] and item["backend_configured"]
            for item in configuration.values()
        ):
            return {**base, "status": "MODEL_NOT_CONFIGURED"}
        if not call_real_model:
            return {**base, "status": "REAL_MODEL_CALL_NOT_REQUESTED"}
        try:
            runner = await ExistingProviderDecisionModelRunner.create(context)
        except Exception as exc:
            return {
                **base,
                "status": "MODEL_FAILED",
                "error": safe_error_message(exc),
            }

        normal = await runner.run_normal(
            context=context,
            attempt_number=1,
            trace_id=trace_id,
        )
        base["normal"] = normal.model_dump(mode="json")
        if normal.status in {"MODEL_FAILED", "INVALID_OUTPUT"}:
            return {**base, "status": normal.status}

        policy = await RiskPolicyRegistry(self.db).get_active()
        top = await runner.run_top(
            context=context,
            plan=normal,
            risk_policy_summary=policy.model_dump(
                mode="json",
                exclude={"created_at", "config_hash"},
            ),
            attempt_number=1,
            trace_id=trace_id,
        )
        base["top"] = top.model_dump(mode="json")
        if top.status in {"MODEL_FAILED", "INVALID_OUTPUT"}:
            return {**base, "status": top.status}
        consensus = ConsensusEngine().evaluate(
            context=context,
            plan=normal,
            review=top,
        )
        base["consensus"] = consensus.model_dump(mode="json")
        if consensus.status == "CONSENSUS_PASS":
            risk = HardRiskEngine().evaluate(
                data=resolved,
                context=context,
                consensus=consensus,
                policy=policy,
                account_id=str(account["account_id"]),
            )
            base["hard_risk"] = risk.model_dump(mode="json")
        return {**base, "status": "COMPLETED"}

    async def run(
        self,
        *,
        user_id: str,
        source_trade_date: date,
        cutoff_at: datetime,
        execute: bool,
        call_real_model: bool = False,
        symbols: list[str] | None = None,
    ) -> dict[str, Any]:
        selected = sorted(set(symbols or self.SYMBOLS))
        if set(selected) != set(self.SYMBOLS):
            raise ProductionReprocessError(
                "reprocess is limited to the five existing candidates"
            )
        if cutoff_at.date() != source_trade_date or cutoff_at.hour < 15:
            raise ProductionReprocessError(
                "reprocess cutoff must be post-close on source trade date"
            )
        if call_real_model and not execute:
            raise ProductionReprocessError(
                "real model validation requires explicit execute mode"
            )
        sources = await self._source_inputs(
            user_id=str(user_id),
            source_trade_date=source_trade_date,
            cutoff_at=cutoff_at,
            symbols=selected,
            execute=execute,
        )
        run_input_hash = sha256_value(
            {
                "user_id": str(user_id),
                "source_trade_date": source_trade_date,
                "cutoff_at": cutoff_at,
                "run_mode": RUN_MODE,
                "reprocess_reason": REPROCESS_REASON,
                "original_realtime_run": False,
                "automated_execution_allowed": False,
                "benchmark_manifest_hash": (
                    sources["benchmark"].manifest_hash
                ),
                "context_manifest_hash": (
                    sources["context_window"].manifest_hash
                ),
                "snapshot_inputs": {
                    symbol: sources["prepared"][symbol][
                        "reprocess_input_hash"
                    ]
                    for symbol in selected
                },
            }
        )
        run_id = self._stable_id(
            "production-evidence-reprocess-run",
            run_input_hash,
        )
        existing = clean_document(
            await self.db[self.RUN_COLLECTION].find_one(
                {"reprocess_run_id": run_id}
            )
        )
        if existing is not None:
            if existing.get("input_hash") != run_input_hash:
                raise ProductionReprocessConflict(
                    "INTEGRITY_CONFLICT: reprocess run identity changed"
                )
            return {
                **existing,
                "action": "REUSED",
                "write": execute,
            }
        if not execute:
            return {
                "reprocess_run_id": run_id,
                "run_mode": RUN_MODE,
                "original_realtime_run": False,
                "automated_execution_allowed": False,
                "source_trade_date": source_trade_date.isoformat(),
                "input_hash": run_input_hash,
                "action": "WOULD_CREATE",
                "write": False,
                "benchmark_manifest_id": (
                    sources["benchmark"].manifest_id
                ),
                "benchmark_count": sources["benchmark"].actual_count,
                "market_context_manifest_id": (
                    sources["context_window"].manifest_id
                ),
                "market_context_count": (
                    sources["context_window"].actual_count
                ),
            }

        snapshots: list[EvidenceSnapshot] = []
        result_rows: list[dict[str, Any]] = []
        proposals = []
        evaluation_rows = []
        for symbol in selected:
            item = sources["prepared"][symbol]
            precheck = item["precheck"]
            snapshot = await self.snapshots.create(
                user_id=str(user_id),
                payload={
                    "_internal_snapshot_id": item["snapshot_id"],
                    "analysis_id": (
                        f"alphaguard-production-reprocess:{symbol}:"
                        f"{source_trade_date.isoformat()}:v2"
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
                    "market_context_id": sources["context"]["context_id"],
                    "market_context_hash": sources["context"]["content_hash"],
                    "market_context_window_manifest_id": (
                        sources["context_window"].manifest_id
                    ),
                    "market_context_window_manifest_hash": (
                        sources["context_window"].manifest_hash
                    ),
                    "benchmark_price_window_manifest_id": (
                        sources["benchmark"].manifest_id
                    ),
                    "benchmark_price_window_manifest_hash": (
                        sources["benchmark"].manifest_hash
                    ),
                    "required_benchmark_count": 61,
                    "actual_benchmark_count": 61,
                    "evidence_contract_status": "COMPLETE",
                    "run_mode": RUN_MODE,
                    "source_trade_date": source_trade_date,
                    "evidence_contract_version": (
                        EVIDENCE_CONTRACT_VERSION
                    ),
                    "reprocess_reason": REPROCESS_REASON,
                    "reprocess_input_hash": item[
                        "reprocess_input_hash"
                    ],
                    "original_realtime_run": False,
                    "automated_execution_allowed": False,
                    "raw_refs": item["raw_refs"],
                    "factor_version_set": sources["factor_versions"],
                    "strategy_version": STRATEGY_SET_VERSION,
                    "normal_model_version": "gpt-4o-mini",
                    "top_model_version": "o4-mini",
                    "prompt_versions": {
                        "normal_trade_plan": (
                            "normal_trade_plan_quant_v1"
                        ),
                        "top_review_decision": (
                            "top_review_decision_quant_v1"
                        ),
                    },
                    "required_sources": [
                        "prices",
                        "benchmark_prices",
                        "market_context",
                        "market_context_window",
                        "benchmark_price_window",
                        "trading_status",
                        "trading_calendar",
                        "accounts",
                    ],
                    "schema_version": (
                        EVIDENCE_SNAPSHOT_SCHEMA_VERSION_V2
                    ),
                },
            )
            snapshots.append(snapshot)
            symbol_proposals = await self.quant.evaluate(
                snapshot.snapshot_id,
                user_id=str(user_id),
                candidate_id=None,
                trace_id=f"production-reprocess:{run_id}:{symbol}",
            )
            proposals.extend(symbol_proposals)
            regime = clean_document(
                await self.db["ag_regime_results"].find_one(
                    {"snapshot_id": snapshot.snapshot_id}
                )
            )
            for proposal in symbol_proposals:
                subject_id, evaluation_action = (
                    await self._save_reprocess_evaluation(
                        user_id=str(user_id),
                        snapshot=snapshot,
                        proposal=proposal,
                    )
                )
                evaluation_rows.append(
                    {
                        "subject_id": subject_id,
                        "proposal_id": proposal.proposal_id,
                        "action": evaluation_action,
                    }
                )
            result_rows.append(
                {
                    "symbol": symbol,
                    "snapshot_id": snapshot.snapshot_id,
                    "snapshot_schema_version": snapshot.schema_version,
                    "snapshot_hash": snapshot.immutable_hash,
                    "benchmark_manifest_id": (
                        snapshot.benchmark_price_window_manifest_id
                    ),
                    "benchmark_count": snapshot.actual_benchmark_count,
                    "market_context_manifest_id": (
                        snapshot.market_context_window_manifest_id
                    ),
                    "market_context_count": (
                        sources["context_window"].actual_count
                    ),
                    "data_quality": snapshot.data_quality.status,
                    "regime_result": regime,
                    "proposal_results": [
                        proposal.model_dump(mode="json")
                        for proposal in symbol_proposals
                    ],
                }
            )

        model_validation = await self._model_validation(
            user_id=str(user_id),
            proposals=proposals,
            account=sources["account"],
            call_real_model=call_real_model,
            trace_id=f"production-reprocess-model:{run_id}",
        )
        execution_gate_status = "NOT_TESTED"
        try:
            await ExecutionOutboxService(self.db).enqueue(
                event_type="CREATE_QUANT_BENCHMARK_INTENT",
                source_object_id=model_validation["proposal_id"],
                user_id=str(user_id),
                analysis_id=(
                    f"alphaguard-production-reprocess:{run_id}"
                ),
            )
        except ExecutionModeBlockedError:
            execution_gate_status = "BLOCKED"
        if execution_gate_status != "BLOCKED":
            raise ProductionReprocessError(
                "reprocess execution safety gate did not block Outbox"
            )

        stored_payload = {
            "reprocess_run_id": run_id,
            "run_mode": RUN_MODE,
            "reprocess_reason": REPROCESS_REASON,
            "original_realtime_run": False,
            "automated_execution_allowed": False,
            "research_only_model_validation": True,
            "source_trade_date": source_trade_date,
            "cutoff_at": cutoff_at,
            "user_id": str(user_id),
            "benchmark_manifest_id": sources["benchmark"].manifest_id,
            "benchmark_manifest_hash": sources["benchmark"].manifest_hash,
            "benchmark_count": sources["benchmark"].actual_count,
            "market_context_manifest_id": (
                sources["context_window"].manifest_id
            ),
            "market_context_manifest_hash": (
                sources["context_window"].manifest_hash
            ),
            "market_context_count": (
                sources["context_window"].actual_count
            ),
            "snapshot_ids": [
                snapshot.snapshot_id for snapshot in snapshots
            ],
            "results": result_rows,
            "model_validation": model_validation,
            "evaluation_subjects": evaluation_rows,
            "execution_gate_status": execution_gate_status,
            "input_hash": run_input_hash,
            "created_at": datetime.utcnow(),
            "schema_version": REPROCESS_SCHEMA_VERSION,
        }
        stored_payload["result_hash"] = sha256_value(
            {
                key: value
                for key, value in stored_payload.items()
                if key not in {"created_at", "result_hash"}
            }
        )
        document = to_mongo_value(stored_payload)
        document["_id"] = run_id
        await self.db[self.RUN_COLLECTION].insert_one(document)
        return {
            **stored_payload,
            "source_trade_date": source_trade_date.isoformat(),
            "cutoff_at": cutoff_at.isoformat(),
            "action": "CREATED",
            "write": True,
        }
