"""Research-only real-model validation with immutable historical evidence."""

from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal, InvalidOperation
from typing import Any
from uuid import NAMESPACE_URL, uuid5

from app.schemas.alphaguard.decision import DecisionContext, canonical_hash
from app.schemas.alphaguard.model_runtime import (
    RealModelValidationRun,
    ResearchAgentResult,
)
from app.schemas.alphaguard.quant import MarketRegimeResult, QuantTradeProposal
from tradingagents.alphaguard.backfill_schemas import HistoricalResearchSnapshot
from tradingagents.alphaguard.evidence_schemas import (
    EVIDENCE_SNAPSHOT_SCHEMA_VERSION_V3,
)
from tradingagents.alphaguard.production_data_schemas import (
    BenchmarkPriceWindowManifest,
    MarketContextWindowManifest,
)
from tradingagents.alphaguard.decision_schemas import (
    NormalTradePlan,
    TopModelDecisionOutput,
)
from tradingagents.alphaguard.structured_output import model_output_schema
from tradingagents.agents.managers.risk_manager import TOP_REQUEST_BUILDER_VERSION

from .benchmark_price_window_service import BenchmarkPriceWindowService
from .cn_trading_status_service import CNTradingStatusService
from .consensus_engine import ConsensusEngine
from .decision_context_builder import (
    DecisionContextBuilder,
    _refs,
)
from .decision_evidence_pack_service import DecisionEvidencePackService
from .evidence_snapshot_service import EvidenceSnapshotService
from .execution_mode_safety_gate import (
    ExecutionModeBlockedError,
    ExecutionModeSafetyGate,
)
from .hard_risk_engine import HardRiskEngine
from .market_context_window_service import MarketContextWindowService
from .model_profile_registry import ModelProfileRegistry
from .model_budget_service import ModelBudgetService
from .model_runtime_context import build_model_runtime_context
from .model_runtime_repository import ModelRuntimeRepository
from .model_runtime_status_service import ModelRuntimeStatusService
from .paper_storage import clean_document, model_document, mongo_date
from .profiled_decision_model_runner import ProfiledDecisionModelRunner
from .prompt_profile_registry import PromptProfileRegistry
from .quant_config import sha256_value
from .research_decision_path_validation_service import CANONICAL_BACKFILL_RUN_ID
from .risk_policy_registry import RiskPolicyRegistry
from .snapshot_data_resolver import ResolvedSnapshotData, SnapshotDataResolver
from .snapshot_research_runtime import SnapshotResearchRuntime
from .snapshot_research_runtime import (
    RESEARCH_MANAGER_CONTRACT_ID,
    RESEARCH_MANAGER_CONTRACT_VERSION,
    RESEARCH_MANAGER_SCHEMA_HASH,
)


VALIDATION_SNAPSHOT_COLLECTION = "ag_model_validation_evidence_snapshots"
VALIDATION_QUALITY_COLLECTION = "ag_model_validation_quality_reports"
VALIDATION_ACCOUNT_COLLECTION = "ag_model_validation_account_evidence"
VALIDATION_CONTRACT_VERSION = "real-model-historical-decision-evidence-v13"
REUSABLE_VALIDATION_CONTRACT_VERSION = (
    "real-model-historical-decision-evidence-v11"
)
TOKEN_ADMISSION_POLICY_VERSION = "model-context-window-only-v1"
SAMPLE_SELECTION_VERSION = (
    "evidence-completeness-factor-mean-date-symbol-proposal-v1"
)
EXPECTED_NORMAL_MODEL = "gpt-5.6-luna"
EXPECTED_TOP_MODEL = "gpt-5.6-sol"
VALIDATION_EVIDENCE_REFS_PER_CATEGORY = 5


class RealModelValidationError(RuntimeError):
    pass


def _date_value(value: Any) -> date | None:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    try:
        return date.fromisoformat(str(value)[:10])
    except (TypeError, ValueError):
        return None


def _reference_date(reference: str) -> date | None:
    return _date_value(str(reference).rsplit(":", 1)[-1])


def _stable_id(namespace: str, payload: Any) -> str:
    return str(
        uuid5(
            NAMESPACE_URL,
            f"alphaguard:{namespace}:{canonical_hash(payload)}",
        )
    )


def _proposal_selection_score(proposal: QuantTradeProposal) -> float:
    scores = [
        float(value)
        for value in proposal.factor_summary.values()
        if value is not None
    ]
    return round(sum(scores) / len(scores), 8) if scores else 0.0


def _sample_order_key(
    proposal: QuantTradeProposal,
    completeness_score: float = 0.0,
) -> tuple[float, float, int, str, str]:
    return (
        -float(completeness_score),
        -_proposal_selection_score(proposal),
        proposal.trade_date.toordinal(),
        proposal.symbol,
        proposal.proposal_id,
    )


def _rank_deduplicate_samples(
    samples: list[dict[str, Any]],
    *,
    limit: int,
) -> list[dict[str, Any]]:
    ranked = sorted(
        samples,
        key=lambda item: _sample_order_key(
            item["proposal"],
            item["evidence_completeness_score"],
        ),
    )
    selected: list[dict[str, Any]] = []
    seen_symbol_dates: set[tuple[str, date]] = set()
    for item in ranked:
        proposal = item["proposal"]
        identity = (proposal.symbol, proposal.trade_date)
        if identity in seen_symbol_dates:
            continue
        seen_symbol_dates.add(identity)
        selected.append(item)
        if len(selected) >= limit:
            break
    return selected


def _recent_documents(
    documents: list[dict[str, Any]],
    *,
    limit: int,
) -> list[dict[str, Any]]:
    def key(document: dict[str, Any]):
        document_date = next(
            (
                parsed
                for field in (
                    "trade_date",
                    "date",
                    "published_at",
                    "publish_time",
                    "announcement_time",
                    "report_period",
                    "updated_at",
                )
                if (parsed := _date_value(document.get(field))) is not None
            ),
            date.min,
        )
        return document_date, str(document.get("_reference") or "")

    return sorted(documents, key=key, reverse=True)[:limit]


def _frozen_snapshot_prompt_version(
    snapshot,
    key: str,
    fallback: str,
) -> str:
    value = str((snapshot.prompt_versions or {}).get(key) or "")
    return value.rsplit("@", 1)[-1] if "@" in value else fallback


def _decision_research_projection(result) -> dict[str, Any]:
    structured = dict(result.structured_summary or {})
    return {
        "research_result_id": result.research_result_id,
        "agent_name": result.agent_name,
        "agent_role": result.agent_role,
        "status": result.status,
        "snapshot_id": result.snapshot_id,
        "context_hash": result.context_hash,
        "summary": structured.get("summary") or structured.get("reason"),
        "evidence_refs": list(result.evidence_refs)[:8],
        "result_hash": result.result_hash,
    }


class RealModelValidationService:
    def __init__(self, db):
        self.db = db
        self.repository = ModelRuntimeRepository(db)
        self.profiles = ModelProfileRegistry(db)
        self.prompts = PromptProfileRegistry(db)

    async def _profiles(self):
        normal = await self.profiles.persisted_for_role("NORMAL_TRADER")
        top = await self.profiles.persisted_for_role("TOP_RISK_REVIEWER")
        return normal, top

    async def _historical_samples(
        self,
        *,
        proposal_id: str | None,
        user_id: str | None,
        limit: int = 3,
    ) -> list[dict[str, Any]]:
        query: dict[str, Any] = {
            "backfill_run_id": CANONICAL_BACKFILL_RUN_ID,
            "quant_proposal.status": "TRIGGERED",
            "quant_proposal.action_candidate": {"$in": ["BUY", "SELL", "REDUCE"]},
            "quant_proposal.automated_execution_allowed": False,
        }
        if proposal_id:
            query["quant_proposal.proposal_id"] = proposal_id
        if user_id:
            query["quant_proposal.user_id"] = str(user_id)
        rows = await self.db["ag_research_quant_proposals"].find(query).to_list(
            length=100
        )
        candidates: list[tuple[QuantTradeProposal, dict[str, Any]]] = []
        for raw in rows:
            try:
                proposal = QuantTradeProposal.model_validate(raw["quant_proposal"])
            except Exception:
                continue
            candidates.append((proposal, raw))
        candidates.sort(key=lambda item: item[0].proposal_id)
        eligible: list[dict[str, Any]] = []
        evidence_service = DecisionEvidencePackService(self.db)
        for proposal, raw in candidates:
            wrapper_raw = await self.db["ag_research_snapshots"].find_one(
                {
                    "backfill_run_id": CANONICAL_BACKFILL_RUN_ID,
                    "sample_id": raw["sample_id"],
                }
            )
            regime_raw = await self.db["ag_research_regime_results"].find_one(
                {
                    "backfill_run_id": CANONICAL_BACKFILL_RUN_ID,
                    "sample_id": raw["sample_id"],
                }
            )
            if wrapper_raw is None or regime_raw is None:
                continue
            wrapper = HistoricalResearchSnapshot.model_validate(
                clean_document(wrapper_raw)
            )
            if not EvidenceSnapshotService.verify_integrity(
                wrapper.evidence_snapshot
            ):
                continue
            if any(
                parsed is not None and parsed > proposal.trade_date
                for category in ("prices", "benchmark_prices")
                for reference in wrapper.evidence_snapshot.raw_refs.get(category, [])
                if (parsed := _reference_date(reference)) is not None
            ):
                continue
            evidence_pack = await evidence_service.get_for_snapshot(
                source_snapshot_id=wrapper.evidence_snapshot.snapshot_id,
                symbol=proposal.symbol,
                source_trade_date=proposal.trade_date,
            )
            eligible.append(
                {
                    "sample_id": str(raw["sample_id"]),
                    "proposal": proposal,
                    "wrapper": wrapper,
                    "regime": MarketRegimeResult.model_validate(
                        regime_raw["regime_result"]
                    ),
                    "decision_evidence_pack": evidence_pack,
                    "evidence_completeness_score": (
                        evidence_pack.completeness_score if evidence_pack else 0.0
                    ),
                    "proposal_selection_score": _proposal_selection_score(proposal),
                }
            )
        return _rank_deduplicate_samples(eligible, limit=limit)

    async def _historical_sample(
        self,
        *,
        proposal_id: str | None,
        user_id: str | None,
    ) -> dict[str, Any] | None:
        samples = await self._historical_samples(
            proposal_id=proposal_id,
            user_id=user_id,
            limit=100,
        )
        return next(
            (
                sample
                for sample in samples
                if sample["decision_evidence_pack"] is not None
                and sample["decision_evidence_pack"].overall_status == "COMPLETE"
            ),
            None,
        )

    def _validation_contract_hash(self) -> str:
        manager_prompt = self.prompts.definition(
            "alphaguard_research_manager_snapshot",
            RESEARCH_MANAGER_CONTRACT_VERSION,
        )
        top_prompt = self.prompts.definition("top_risk_review_prompt")
        return canonical_hash(
            {
                "validation_contract_version": VALIDATION_CONTRACT_VERSION,
                "research_manager_contract_id": RESEARCH_MANAGER_CONTRACT_ID,
                "research_manager_contract_version": (
                    RESEARCH_MANAGER_CONTRACT_VERSION
                ),
                "research_manager_schema_hash": RESEARCH_MANAGER_SCHEMA_HASH,
                "research_manager_prompt_hash": manager_prompt.template_hash,
                "sample_selection_version": SAMPLE_SELECTION_VERSION,
                "decision_evidence_pack_schema_version": (
                    "decision-evidence-pack-v3"
                ),
                "token_admission_policy_version": TOKEN_ADMISSION_POLICY_VERSION,
                "top_model_payload_schema_version": (
                    "top_model_decision_output_v1"
                ),
                "top_model_payload_schema_hash": canonical_hash(
                    model_output_schema(TopModelDecisionOutput)
                ),
                "top_prompt_version": top_prompt.prompt_version,
                "top_prompt_hash": top_prompt.template_hash,
                "top_request_builder_version": TOP_REQUEST_BUILDER_VERSION,
                "reusable_validation_contract_version": (
                    REUSABLE_VALIDATION_CONTRACT_VERSION
                ),
            }
        )

    async def _reusable_validation(
        self,
        *,
        sample: dict[str, Any],
    ) -> RealModelValidationRun:
        proposal: QuantTradeProposal = sample["proposal"]
        rows = await self.repository.list(
            "validation_runs",
            {
                "validation_contract_version": REUSABLE_VALIDATION_CONTRACT_VERSION,
                "source_quant_proposal_id": proposal.proposal_id,
                "source_trade_date": mongo_date(proposal.trade_date),
                "symbol": proposal.symbol,
                "normal_result.status": "PROPOSE_TRADE",
                "top_result.status": "MODEL_FAILED",
                "top_result.model_meta.error_type": (
                    "SNAPSHOT_TOKEN_BUDGET_EXCEEDED"
                ),
                "actual_production_decision": False,
                "actual_execution": False,
            },
            limit=2,
        )
        if len(rows) != 1:
            raise RealModelValidationError(
                "REUSABLE_V11_VALIDATION_NOT_UNIQUE"
            )
        result = RealModelValidationRun.model_validate(rows[0])
        if not result.snapshot_id or not result.context_hash:
            raise RealModelValidationError("REUSABLE_V11_INPUT_IDENTITY_MISSING")
        if not result.decision_context_hash or not result.normal_result:
            raise RealModelValidationError("REUSABLE_V11_DECISION_MISSING")
        if not result.research_result_ids:
            raise RealModelValidationError("REUSABLE_V11_RESEARCH_MISSING")
        return result

    async def _reused_research(
        self,
        *,
        predecessor: RealModelValidationRun,
    ) -> list[ResearchAgentResult]:
        results: list[ResearchAgentResult] = []
        expected_analysis_id = f"real-model-validation:{predecessor.validation_run_id}"
        for result_id in predecessor.research_result_ids:
            raw = await self.repository.get(
                "research_results", {"research_result_id": result_id}
            )
            if raw is None:
                raise RealModelValidationError(
                    "REUSABLE_V11_RESEARCH_RESULT_MISSING"
                )
            result = ResearchAgentResult.model_validate(raw)
            if (
                result.analysis_id != expected_analysis_id
                or result.snapshot_id != predecessor.snapshot_id
                or result.context_hash != predecessor.context_hash
            ):
                raise RealModelValidationError(
                    "REUSABLE_V11_RESEARCH_IDENTITY_MISMATCH"
                )
            results.append(result)
        return results

    async def _reused_top_budget(
        self,
        *,
        sample: dict[str, Any],
        predecessor: RealModelValidationRun,
        normal_profile,
        top_profile,
        model_call_analysis_id: str | None = None,
    ):
        snapshot = await EvidenceSnapshotService(
            db=self.db,
            snapshot_collection=VALIDATION_SNAPSHOT_COLLECTION,
            quality_collection=VALIDATION_QUALITY_COLLECTION,
            enable_shadow_hook=False,
        ).get(predecessor.snapshot_id, user_id=sample["proposal"].user_id)
        if snapshot is None or not EvidenceSnapshotService.verify_integrity(snapshot):
            raise RealModelValidationError(
                "REUSABLE_V11_SNAPSHOT_INTEGRITY_FAILED"
            )
        if snapshot.immutable_hash != predecessor.snapshot_hash:
            raise RealModelValidationError("REUSABLE_V11_SNAPSHOT_HASH_MISMATCH")
        context, resolved, _ = await self._context(
            validation_run_id=predecessor.validation_run_id,
            sample=sample,
            snapshot=snapshot,
            normal_profile=normal_profile,
            top_profile=top_profile,
        )
        verified_model_context = build_model_runtime_context(
            context,
            resolved,
            include_resolved_refs=False,
        )
        if context.context_hash != predecessor.decision_context_hash:
            raise RealModelValidationError("REUSABLE_V11_CONTEXT_HASH_MISMATCH")
        research = await self._reused_research(predecessor=predecessor)
        normal = NormalTradePlan.model_validate(predecessor.normal_result)
        if normal.model_meta.context_hash != predecessor.context_hash:
            raise RealModelValidationError(
                "REUSABLE_V11_NORMAL_IDENTITY_MISMATCH"
            )
        policy = await RiskPolicyRegistry(self.db).get_active()
        top_prompt_definition = self.prompts.definition(
            top_profile.prompt_profile_id
        )
        top_prompt = await self.prompts.persisted(
            top_prompt_definition.prompt_id,
            top_prompt_definition.prompt_version,
        )
        rendered = ProfiledDecisionModelRunner.render_top_input(
            context=context,
            plan=normal,
            risk_policy_summary=policy.model_dump(
                mode="json", exclude={"created_at", "config_hash"}
            ),
            research_results=[
                _decision_research_projection(item) for item in research
            ],
            model_runtime_context_hash=predecessor.context_hash,
            top_prompt_version=top_prompt.prompt_version,
            top_prompt_template=top_prompt.template,
            structured_output_mode=top_profile.structured_output_mode,
            run_mode="REAL_MODEL_VALIDATION",
        )
        if verified_model_context.snapshot_id != predecessor.snapshot_id:
            raise RealModelValidationError("REUSABLE_V11_SNAPSHOT_ID_MISMATCH")
        return await ModelBudgetService(self.db).check(
            profile=top_profile,
            analysis_id=model_call_analysis_id or context.analysis_id,
            snapshot_id=context.snapshot_id,
            rendered_input=rendered,
        )

    async def _source_context_count(self, trade_date: date) -> int:
        count = await self.db["ag_market_contexts"].count_documents(
            {
                "market": "CN",
                "trade_date": {"$lte": mongo_date(trade_date)},
                "calculation_status": "READY",
                "calculation_version": "production-market-context-calculation-v1.1",
            }
        )
        return int(count)

    async def _account(self, user_id: str) -> dict[str, Any] | None:
        rows = await self.db["ag_paper_accounts"].find(
            {
                "user_id": str(user_id),
                "market": "CN",
                "account_type": "PAPER_TOP_CONFIRMED",
                "status": "ACTIVE",
            }
        ).limit(2).to_list(length=2)
        return clean_document(rows[0]) if len(rows) == 1 else None

    async def preflight(
        self,
        *,
        proposal_id: str | None = None,
        user_id: str | None = None,
        model_call_analysis_id: str | None = None,
    ) -> dict[str, Any]:
        status = await ModelRuntimeStatusService(self.db).status(admin=True)
        blockers: list[str] = []
        if status.get("decision_status") != "READY":
            blockers.append("DECISION_MODELS_NOT_READY")
        try:
            normal, top = await self._profiles()
        except Exception:
            normal = top = None
            blockers.append("MODEL_PROFILE_NOT_READY")
        if normal is not None and normal.model_name != EXPECTED_NORMAL_MODEL:
            blockers.append("NORMAL_MODEL_IDENTITY_MISMATCH")
        if top is not None and top.model_name != EXPECTED_TOP_MODEL:
            blockers.append("TOP_MODEL_IDENTITY_MISMATCH")
        budget = status.get("budget") or {}
        if int(budget.get("remaining_calls") or 0) < 1:
            blockers.append("RESOURCE_BUDGET_NOT_READY")
        if top is not None and top.max_input_tokens <= top.max_output_tokens:
            blockers.append("TOP_MODEL_CONTEXT_WINDOW_NOT_READY")
        ranked_samples = await self._historical_samples(
            proposal_id=proposal_id,
            user_id=user_id,
            limit=100,
        )
        sample = next(
            (
                item
                for item in ranked_samples
                if item["decision_evidence_pack"] is not None
                and item["decision_evidence_pack"].overall_status == "COMPLETE"
            ),
            None,
        )
        evidence_gate = [
            {
                "source_proposal_id": item["proposal"].proposal_id,
                "source_snapshot_id": item["proposal"].snapshot_id,
                "symbol": item["proposal"].symbol,
                "trade_date": item["proposal"].trade_date.isoformat(),
                "proposal_selection_score": item["proposal_selection_score"],
                "manifest_id": (
                    item["decision_evidence_pack"].manifest_id
                    if item["decision_evidence_pack"]
                    else None
                ),
                "overall_status": (
                    item["decision_evidence_pack"].overall_status
                    if item["decision_evidence_pack"]
                    else "MISSING"
                ),
                "completeness_score": item["evidence_completeness_score"],
                "matrix": (
                    item[
                        "decision_evidence_pack"
                    ].evidence_completeness_matrix.model_dump(mode="json")
                    if item["decision_evidence_pack"]
                    else None
                ),
            }
            for item in ranked_samples
        ]
        evidence: dict[str, Any] | None = None
        top_budget_decision = None
        if not ranked_samples:
            blockers.append("NO_NATURAL_TRIGGERED_SAMPLE")
        elif sample is None:
            blockers.append("DECISION_EVIDENCE_PACK_NOT_READY")
        else:
            proposal = sample["proposal"]
            predecessor = None
            try:
                predecessor = await self._reusable_validation(sample=sample)
                if normal is not None and top is not None:
                    top_budget_decision = await self._reused_top_budget(
                        sample=sample,
                        predecessor=predecessor,
                        normal_profile=normal,
                        top_profile=top,
                        model_call_analysis_id=model_call_analysis_id,
                    )
                    if not top_budget_decision.allowed:
                        blockers.append(
                            top_budget_decision.reason_code or "BUDGET_BLOCKED"
                        )
            except RealModelValidationError as exc:
                blockers.append(str(exc))
            context_count = await self._source_context_count(proposal.trade_date)
            if context_count < 61:
                blockers.append("MARKET_CONTEXT_WINDOW_NOT_READY")
            cutoff = datetime.now()
            try:
                benchmark = await BenchmarkPriceWindowService(self.db).build(
                    as_of_trade_date=proposal.trade_date,
                    cutoff_at=cutoff,
                    execute=False,
                    required_count=61,
                )
                context = await MarketContextWindowService(self.db).build(
                    as_of_trade_date=proposal.trade_date,
                    cutoff_at=cutoff,
                    execute=False,
                    prior_session_count=max(1, context_count - 1),
                )
                trading = await CNTradingStatusService(self.db).sync(
                    symbols=[proposal.symbol],
                    trade_date=proposal.trade_date,
                    execute=False,
                )
                trading_row = trading["results"][0]
                if trading_row["calculation_status"] != "READY":
                    blockers.append("TRADING_STATUS_NOT_READY")
                account = await self._account(proposal.user_id)
                if account is None:
                    blockers.append("VALIDATION_ACCOUNT_NOT_READY")
                evidence = {
                    "sample_id": sample["sample_id"],
                    "source_proposal_id": proposal.proposal_id,
                    "source_snapshot_id": proposal.snapshot_id,
                    "symbol": proposal.symbol,
                    "trade_date": proposal.trade_date.isoformat(),
                    "natural_trigger": True,
                    "decision_evidence_pack_manifest_id": sample[
                        "decision_evidence_pack"
                    ].manifest_id,
                    "decision_evidence_pack_status": sample[
                        "decision_evidence_pack"
                    ].overall_status,
                    "benchmark_count": benchmark["manifest"]["actual_count"],
                    "market_context_count": context["manifest"]["actual_count"],
                    "trading_status": trading_row["calculation_status"],
                    "reusable_validation_run_id": (
                        predecessor.validation_run_id if predecessor else None
                    ),
                    "reusable_snapshot_id": (
                        predecessor.snapshot_id if predecessor else None
                    ),
                    "top_estimated_input_tokens": (
                        top_budget_decision.estimated_input_tokens
                        if top_budget_decision
                        else None
                    ),
                    "top_configured_max_output_tokens": (
                        top_budget_decision.estimated_output_tokens
                        if top_budget_decision
                        else None
                    ),
                    "top_model_context_window": (
                        top_budget_decision.model_context_window
                        if top_budget_decision
                        else None
                    ),
                    "top_remaining_context_capacity": (
                        top_budget_decision.remaining_context_capacity
                        if top_budget_decision
                        else None
                    ),
                    "top_context_warning_level": (
                        top_budget_decision.context_warning_level
                        if top_budget_decision
                        else None
                    ),
                }
            except Exception as exc:
                blockers.append(type(exc).__name__)
        return {
            "status": "READY" if not blockers else "BLOCKED",
            "run_mode": "REAL_MODEL_VALIDATION",
            "automated_execution_allowed": False,
            "actual_production_decision": False,
            "actual_execution": False,
            "validation_contract_version": VALIDATION_CONTRACT_VERSION,
            "contract_hash": self._validation_contract_hash(),
            "sample_selection_version": SAMPLE_SELECTION_VERSION,
            "decision_status": status.get("decision_status"),
            "normal_model": normal.model_name if normal else None,
            "top_model": top.model_name if top else None,
            "top_model_context_window": (
                top.max_input_tokens if top else None
            ),
            "top_configured_max_output_tokens": (
                top.max_output_tokens if top else None
            ),
            "context_window_source": (
                "MODEL_PROFILE_MAX_INPUT_TOKENS" if top else None
            ),
            "budget": {
                key: budget.get(key)
                for key in (
                    "policy_id",
                    "policy_version",
                    "remaining_calls",
                    "remaining_cost",
                    "currency",
                )
            },
            "evidence": evidence,
            "evidence_gate": evidence_gate,
            "blocking_items": sorted(set(blockers)),
        }

    async def _persist_account_evidence(
        self,
        *,
        account: dict[str, Any],
    ) -> dict[str, Any]:
        account_id = str(account["account_id"])
        position_rows = await self.db["ag_paper_positions"].find(
            {"account_id": account_id}
        ).to_list(length=None)
        positions = 0
        for row in position_rows:
            try:
                quantity = Decimal(str(row.get("quantity")))
            except (InvalidOperation, TypeError, ValueError):
                raise RealModelValidationError(
                    "validation account has an unreadable position quantity"
                ) from None
            if quantity < 0:
                raise RealModelValidationError(
                    "validation account has a negative position quantity"
                )
            positions += int(quantity > 0)
        orders = await self.db["ag_paper_orders"].count_documents(
            {"account_id": account_id, "status": {"$nin": ["FILLED", "CANCELLED", "REJECTED"]}}
        )
        try:
            cash_reserved = Decimal(str(account.get("cash_reserved")))
        except (InvalidOperation, TypeError, ValueError):
            raise RealModelValidationError(
                "validation account has unreadable reserved cash"
            ) from None
        if cash_reserved < 0:
            raise RealModelValidationError(
                "validation account has negative reserved cash"
            )
        if positions or orders or cash_reserved != 0:
            raise RealModelValidationError(
                "validation requires an empty, unfrozen, order-free formal paper account"
            )
        stable = {
            "source_account_id": account_id,
            "source_account_version": account.get("account_version"),
            "user_id": str(account["user_id"]),
            "cash_available": str(account["cash_available"]),
            "cash_reserved": str(account["cash_reserved"]),
            "position_count": positions,
            "active_order_count": orders,
        }
        ref_id = _stable_id("real-model-validation-account", stable)
        payload = {
            "ref_id": ref_id,
            "account_id": account_id,
            "user_id": str(account["user_id"]),
            "status": str(account["status"]),
            "market": str(account["market"]),
            "currency": str(account["currency"]),
            "cash": {"CNY": str(account["cash_available"])},
            "equity": {"CNY": str(account["cash_available"])},
            "total_exposure_pct": 0.0,
            "industry_exposure_pct": {"UNKNOWN": 0.0},
            "new_positions_today": 0,
            "active_orders_complete": True,
            "portfolio_empty_verified": True,
            "source_account_id": account_id,
            "source_account_version": account.get("account_version"),
            "run_mode": "REAL_MODEL_VALIDATION",
            "automated_execution_allowed": False,
            "as_of": account.get("updated_at") or account.get("created_at"),
        }
        payload["content_hash"] = canonical_hash(payload)
        existing = clean_document(
            await self.db[VALIDATION_ACCOUNT_COLLECTION].find_one(
                {"ref_id": ref_id}
            )
        )
        if existing is not None:
            if existing.get("content_hash") != payload["content_hash"]:
                raise RealModelValidationError(
                    "INTEGRITY_CONFLICT: validation account evidence changed"
                )
            return existing
        document = {**payload, "created_at": datetime.utcnow()}
        await self.db[VALIDATION_ACCOUNT_COLLECTION].insert_one(document)
        return clean_document(document)

    async def _prepare_snapshot(
        self,
        *,
        sample: dict[str, Any],
        normal_profile,
        top_profile,
    ):
        proposal: QuantTradeProposal = sample["proposal"]
        source = sample["wrapper"].evidence_snapshot
        decision_evidence = sample.get("decision_evidence_pack")
        if decision_evidence is None or decision_evidence.overall_status != "COMPLETE":
            raise RealModelValidationError(
                "DECISION_EVIDENCE_PACK_NOT_READY: model calls are blocked"
            )
        context_count = await self._source_context_count(proposal.trade_date)
        if context_count < 61:
            raise RealModelValidationError("historical MarketContext window is incomplete")
        cutoff = datetime.now()
        benchmark_result = await BenchmarkPriceWindowService(self.db).build(
            as_of_trade_date=proposal.trade_date,
            cutoff_at=cutoff,
            execute=True,
            required_count=61,
        )
        context_result = await MarketContextWindowService(self.db).build(
            as_of_trade_date=proposal.trade_date,
            cutoff_at=cutoff,
            execute=True,
            prior_session_count=context_count - 1,
        )
        benchmark = BenchmarkPriceWindowManifest.model_validate(
            benchmark_result["manifest"]
        )
        context_window = MarketContextWindowManifest.model_validate(
            context_result["manifest"]
        )
        trading_result = await CNTradingStatusService(self.db).sync(
            symbols=[proposal.symbol],
            trade_date=proposal.trade_date,
            execute=True,
        )
        trading_summary = trading_result["results"][0]
        if trading_summary["calculation_status"] != "READY":
            raise RealModelValidationError("historical trading status is incomplete")
        trading = clean_document(
            await self.db["ag_security_trading_statuses"].find_one(
                {
                    "symbol": proposal.symbol,
                    "trade_date": mongo_date(proposal.trade_date),
                    "content_hash": trading_summary["content_hash"],
                }
            )
        )
        if trading is None:
            raise RealModelValidationError("persisted historical trading status missing")
        contexts = await self.db["ag_market_contexts"].find(
            {
                "market": "CN",
                "trade_date": mongo_date(proposal.trade_date),
                "calculation_status": "READY",
                "calculation_version": context_window.context_version,
            }
        ).limit(2).to_list(length=2)
        if len(contexts) != 1:
            raise RealModelValidationError("exact historical MarketContext is ambiguous")
        market_context = clean_document(contexts[0])
        assert market_context is not None
        account = await self._account(proposal.user_id)
        if account is None:
            raise RealModelValidationError("formal validation account is unavailable")
        account_evidence = await self._persist_account_evidence(account=account)

        basic_rows = await self.db["stock_basic_info"].find(
            {"$or": [{"symbol": proposal.symbol}, {"code": proposal.symbol}]}
        ).to_list(length=None)
        usable_basic = [
            row
            for row in basic_rows
            if _date_value(
                row.get("list_date") or row.get("listing_date") or row.get("ipo_date")
            )
            is not None
        ]
        if len(usable_basic) != 1:
            raise RealModelValidationError("versioned security-master identity is ambiguous")
        instrument_ref = str(usable_basic[0]["_id"])

        quote_refs = sorted(
            source.raw_refs.get("prices", []),
            key=lambda item: _reference_date(item) or date.min,
        )[-121:]
        calendar_rows = await self.db["trading_calendar"].find(
            {
                "market": "CN",
                "is_open": True,
                "session_date": {"$lte": mongo_date(proposal.trade_date)},
            }
        ).sort("session_date", -1).limit(2).to_list(length=2)
        next_session = await self.db["trading_calendar"].find_one(
            {
                "market": "CN",
                "is_open": True,
                "session_date": {"$gt": mongo_date(proposal.trade_date)},
            },
            sort=[("session_date", 1)],
        )
        calendar_rows = list(reversed(calendar_rows)) + ([next_session] if next_session else [])
        calendar_refs = [
            f"trading_calendar:{row['calendar_id']}"
            for row in calendar_rows
            if row and row.get("calendar_id")
        ]
        raw_refs = {
            "prices": quote_refs,
            "benchmark_prices": [
                f"index_daily:{quote_id}" for quote_id in benchmark.ordered_quote_ids
            ],
            "financials": list(decision_evidence.financial_evidence.source_refs),
            "cashflow_evidence": list(
                decision_evidence.cashflow_evidence.source_refs
            ),
            "dividend_evidence": list(
                decision_evidence.dividend_evidence.source_refs
            ),
            "news": list(source.raw_refs.get("news", [])),
            "announcements": list(
                decision_evidence.announcement_evidence.source_refs
            ),
            "decision_evidence_pack": [
                f"decision_evidence_pack:{decision_evidence.manifest_id}"
            ],
            "market_context": [f"market_context:{market_context['context_id']}"],
            "market_context_window": [
                f"market_context_window:{context_window.manifest_id}"
            ],
            "benchmark_price_window": [
                f"benchmark_price_window:{benchmark.manifest_id}"
            ],
            "trading_status": [f"trading_status:{trading['trading_status_id']}"],
            "accounts": [f"model_validation_account:{account_evidence['ref_id']}"],
            "instruments": [f"stock_basic_info:{instrument_ref}"],
            "trading_calendar": calendar_refs,
        }
        normal_prompt = self.prompts.definition(normal_profile.prompt_profile_id)
        top_prompt = self.prompts.definition(top_profile.prompt_profile_id)
        research_prompt = self.prompts.definition("alphaguard_research_snapshot")
        research_manager_prompt = self.prompts.definition(
            "alphaguard_research_manager_snapshot",
            RESEARCH_MANAGER_CONTRACT_VERSION,
        )
        input_hash = sha256_value(
            {
                "contract": VALIDATION_CONTRACT_VERSION,
                "contract_hash": self._validation_contract_hash(),
                "source_snapshot_hash": source.immutable_hash,
                "source_proposal_hash": proposal.input_hash,
                "benchmark_manifest_hash": benchmark.manifest_hash,
                "context_manifest_hash": context_window.manifest_hash,
                "decision_evidence_pack_manifest_hash": (
                    decision_evidence.manifest_hash
                ),
                "trading_status_hash": trading["content_hash"],
                "account_evidence_hash": account_evidence["content_hash"],
                "champion_version_refs": source.champion_version_refs,
                "normal_profile_hash": normal_profile.config_hash,
                "top_profile_hash": top_profile.config_hash,
                "raw_refs": raw_refs,
            }
        )
        snapshot_id = _stable_id("real-model-validation-snapshot", input_hash)
        snapshot_cutoff = datetime.now()
        service = EvidenceSnapshotService(
            db=self.db,
            snapshot_collection=VALIDATION_SNAPSHOT_COLLECTION,
            quality_collection=VALIDATION_QUALITY_COLLECTION,
            enable_shadow_hook=False,
        )
        required_sources = [
            "prices",
            "financials",
            "market_context",
            "market_context_window",
            "benchmark_price_window",
            "decision_evidence_pack",
            "trading_status",
            "accounts",
            "instruments",
            "trading_calendar",
        ]
        snapshot = await service.create(
            user_id=proposal.user_id,
            payload={
                "_internal_snapshot_id": snapshot_id,
                "analysis_id": f"real-model-validation:{proposal.proposal_id}",
                "symbol": proposal.symbol,
                "market": proposal.market,
                "trade_date": proposal.trade_date,
                "price_cutoff_at": snapshot_cutoff,
                "news_cutoff_at": snapshot_cutoff,
                "announcement_cutoff_at": snapshot_cutoff,
                "price_data_version": source.price_data_version,
                "financial_data_version": (
                    f"{decision_evidence.schema_version}:"
                    f"{decision_evidence.source_hash}"
                ),
                "news_data_version": source.news_data_version,
                "market_context_id": str(market_context["context_id"]),
                "market_context_hash": str(market_context["content_hash"]),
                "market_context_window_manifest_id": context_window.manifest_id,
                "market_context_window_manifest_hash": context_window.manifest_hash,
                "benchmark_price_window_manifest_id": benchmark.manifest_id,
                "benchmark_price_window_manifest_hash": benchmark.manifest_hash,
                "decision_evidence_pack_manifest_id": (
                    decision_evidence.manifest_id
                ),
                "decision_evidence_pack_manifest_hash": (
                    decision_evidence.manifest_hash
                ),
                "evidence_completeness_matrix": (
                    decision_evidence.evidence_completeness_matrix.model_dump(
                        mode="python"
                    )
                ),
                "required_benchmark_count": benchmark.required_count,
                "actual_benchmark_count": benchmark.actual_count,
                "evidence_contract_status": "COMPLETE",
                "run_mode": "EVIDENCE_CONTRACT_VALIDATION",
                "source_trade_date": proposal.trade_date,
                "evidence_contract_version": "decision-evidence-pack-v3",
                "reprocess_reason": VALIDATION_CONTRACT_VERSION,
                "reprocess_input_hash": input_hash,
                "original_realtime_run": False,
                "automated_execution_allowed": False,
                "raw_refs": raw_refs,
                "factor_version_set": source.factor_version_set,
                "strategy_version": source.strategy_version,
                "champion_version_refs": source.champion_version_refs,
                "normal_model_version": (
                    f"{normal_profile.profile_id}@{normal_profile.profile_version}"
                ),
                "top_model_version": f"{top_profile.profile_id}@{top_profile.profile_version}",
                "prompt_versions": {
                    "research": f"{research_prompt.prompt_id}@{research_prompt.prompt_version}",
                    "research_manager": (
                        f"{research_manager_prompt.prompt_id}@"
                        f"{research_manager_prompt.prompt_version}"
                    ),
                    "normal": f"{normal_prompt.prompt_id}@{normal_prompt.prompt_version}",
                    "top": f"{top_prompt.prompt_id}@{top_prompt.prompt_version}",
                },
                # News is optional when the immutable source Snapshot only has
                # announcements. The deterministic gate separately requires at
                # least one of those two event-evidence categories.
                "required_sources": required_sources,
                "schema_version": EVIDENCE_SNAPSHOT_SCHEMA_VERSION_V3,
            },
        )
        return snapshot, account

    async def _context(
        self,
        *,
        validation_run_id: str,
        sample: dict[str, Any],
        snapshot,
        normal_profile,
        top_profile,
    ) -> tuple[DecisionContext, ResolvedSnapshotData, str]:
        source_proposal: QuantTradeProposal = sample["proposal"]
        source_regime: MarketRegimeResult = sample["regime"]
        proposal_id = _stable_id(
            "real-model-validation-proposal",
            {"source": source_proposal.proposal_id, "snapshot": snapshot.immutable_hash},
        )
        regime_id = _stable_id(
            "real-model-validation-regime",
            {"source": source_regime.regime_result_id, "snapshot": snapshot.immutable_hash},
        )
        regime = MarketRegimeResult.model_validate(
            {
                **source_regime.model_dump(mode="python"),
                "regime_result_id": regime_id,
                "snapshot_id": snapshot.snapshot_id,
                "input_hash": sha256_value(
                    {"source": source_regime.input_hash, "snapshot": snapshot.immutable_hash}
                ),
            }
        )
        proposal = QuantTradeProposal.model_validate(
            {
                **source_proposal.model_dump(mode="python"),
                "proposal_id": proposal_id,
                "snapshot_id": snapshot.snapshot_id,
                "regime_result_id": regime_id,
                "input_hash": sha256_value(
                    {"source": source_proposal.input_hash, "snapshot": snapshot.immutable_hash}
                ),
            }
        )
        resolved = await SnapshotDataResolver(
            self.db,
            snapshot_collection=VALIDATION_SNAPSHOT_COLLECTION,
        ).resolve(snapshot.snapshot_id, user_id=source_proposal.user_id)
        DecisionContextBuilder._validate_critical_evidence(proposal, resolved)
        missing = list(snapshot.data_quality.missing_fields)
        analysis_id = f"real-model-validation:{validation_run_id}"
        critical_price_refs = (
            _refs(resolved.instruments, "instrument")
            + _refs(resolved.trading_status, "trading_status")
            + _refs(resolved.trading_calendar, "trading_calendar")
        )
        historical_price_limit = max(
            1,
            VALIDATION_EVIDENCE_REFS_PER_CATEGORY - len(critical_price_refs),
        )
        normal_prompt = self.prompts.definition(normal_profile.prompt_profile_id)
        top_prompt = self.prompts.definition(top_profile.prompt_profile_id)
        payload: dict[str, Any] = {
            "analysis_id": analysis_id,
            "user_id": proposal.user_id,
            "candidate_id": proposal.candidate_id,
            "symbol": proposal.symbol,
            "market": proposal.market,
            "trade_date": proposal.trade_date,
            "snapshot_id": snapshot.snapshot_id,
            "quant_proposal_id": proposal.proposal_id,
            "strategy_id": proposal.strategy_id,
            "strategy_version": proposal.strategy_version,
            "factor_set_version": proposal.factor_set_version,
            "regime_result_id": regime.regime_result_id,
            "quant_proposal": proposal,
            "factor_summary": proposal.factor_summary,
            "factor_result_ids": sorted(proposal.factor_result_ids),
            "market_regime": regime,
            "price_evidence": sorted(
                _refs(
                    _recent_documents(
                        resolved.prices,
                        limit=historical_price_limit,
                    ),
                    "price",
                )
                + critical_price_refs,
                key=lambda item: item.evidence_id,
            )[:VALIDATION_EVIDENCE_REFS_PER_CATEGORY],
            "financial_evidence": _refs(
                _recent_documents(
                    resolved.financials + resolved.cashflows,
                    limit=VALIDATION_EVIDENCE_REFS_PER_CATEGORY,
                ),
                "financial",
            ),
            "news_evidence": _refs(
                _recent_documents(
                    resolved.news,
                    limit=VALIDATION_EVIDENCE_REFS_PER_CATEGORY,
                ),
                "news",
            ),
            "announcement_evidence": _refs(
                _recent_documents(
                    resolved.announcements
                    + resolved.dividends
                    + resolved.corporate_actions,
                    limit=VALIDATION_EVIDENCE_REFS_PER_CATEGORY,
                ),
                "announcement",
            ),
            "account_evidence": _refs(resolved.accounts, "account"),
            "portfolio_evidence": [],
            "data_quality_status": snapshot.data_quality.status,
            "risk_flags": sorted(set(proposal.risk_flags)),
            "missing_evidence": sorted(set(missing)),
            "normal_prompt_version": _frozen_snapshot_prompt_version(
                snapshot, "normal", normal_prompt.prompt_version
            ),
            "top_prompt_version": _frozen_snapshot_prompt_version(
                snapshot, "top", top_prompt.prompt_version
            ),
            "created_at": datetime.utcnow(),
            "schema_version": "decision-context-v1",
        }
        draft = DecisionContext.model_construct(
            decision_context_id="pending",
            context_hash="0" * 64,
            **payload,
        )
        payload["context_hash"] = canonical_hash(
            draft,
            exclude={"decision_context_id", "context_hash", "created_at"},
        )
        payload["decision_context_id"] = _stable_id(
            "real-model-validation-context", payload["context_hash"]
        )
        return DecisionContext.model_validate(payload), resolved, proposal_id

    async def _model_call_records(
        self, analysis_id: str | list[str]
    ) -> list[dict[str, Any]]:
        analysis_query = (
            {"$in": list(dict.fromkeys(analysis_id))}
            if isinstance(analysis_id, list)
            else analysis_id
        )
        rows = await self.repository.list(
            "runs",
            {
                "analysis_id": analysis_query,
                "run_mode": "REAL_MODEL_VALIDATION",
            },
            sort=("created_at", 1),
            limit=100,
        )
        keys = (
            "model_run_id",
            "analysis_id",
            "snapshot_id",
            "context_hash",
            "role",
            "agent_name",
            "model_name",
            "model_profile_id",
            "model_profile_version",
            "structured_output_status",
            "estimated_input_tokens",
            "input_tokens",
            "output_tokens",
            "total_tokens",
            "model_context_window",
            "configured_max_output_tokens",
            "remaining_context_capacity",
            "context_usage_ratio",
            "context_warning_level",
            "latency_ms",
            "request_hash",
            "response_hash",
            "error_category",
            "attempt",
        )
        return [{key: row.get(key) for key in keys} for row in rows]

    async def run(
        self,
        *,
        requested_by: str,
        idempotency_key: str,
        proposal_id: str | None = None,
        user_id: str | None = None,
    ) -> RealModelValidationRun:
        identity = {
            "requested_by": requested_by,
            "idempotency_key": idempotency_key,
            "proposal_id": proposal_id,
            "user_id": user_id,
            "run_mode": "REAL_MODEL_VALIDATION",
            "contract_version": VALIDATION_CONTRACT_VERSION,
            "contract_hash": self._validation_contract_hash(),
            "sample_selection_version": SAMPLE_SELECTION_VERSION,
        }
        validation_run_id = _stable_id("real-model-validation", identity)
        existing = await self.repository.get(
            "validation_runs", {"validation_run_id": validation_run_id}
        )
        if existing is not None:
            return RealModelValidationRun.model_validate(existing).model_copy(
                update={"idempotency_status": "REUSED"}
            )

        started = datetime.now(timezone.utc)
        model_call_analysis_id = f"real-model-validation:{validation_run_id}"
        status = "CREATED"
        snapshot = None
        sample = None
        context = None
        model_context = None
        runtime_context_hash = None
        validation_proposal_id = None
        research_ids: list[str] = []
        normal_run_id = top_run_id = None
        normal_result = top_result = None
        consensus_result = hard_risk_result = None
        consensus_status = hard_risk_status = None
        failure_code = None
        gate_invoked = False
        gate_status = "NOT_REACHED"
        predecessor = None
        reused_research_and_normal = False
        try:
            gate = await self.preflight(
                proposal_id=proposal_id,
                user_id=user_id,
                model_call_analysis_id=model_call_analysis_id,
            )
            if gate["status"] != "READY":
                failure_code = ",".join(gate["blocking_items"])
                status = "MODEL_NOT_CONFIGURED" if (
                    "DECISION_MODELS_NOT_READY" in gate["blocking_items"]
                ) else "NO_ELIGIBLE_SAMPLE"
            else:
                sample = await self._historical_sample(
                    proposal_id=proposal_id,
                    user_id=user_id,
                )
                if sample is None:
                    raise RealModelValidationError("natural historical sample disappeared")
                normal_profile, top_profile = await self._profiles()
                predecessor = await self._reusable_validation(sample=sample)
                snapshot_service = EvidenceSnapshotService(
                    db=self.db,
                    snapshot_collection=VALIDATION_SNAPSHOT_COLLECTION,
                    quality_collection=VALIDATION_QUALITY_COLLECTION,
                    enable_shadow_hook=False,
                )
                snapshot = await snapshot_service.get(
                    predecessor.snapshot_id,
                    user_id=sample["proposal"].user_id,
                )
                if snapshot is None or not EvidenceSnapshotService.verify_integrity(
                    snapshot
                ):
                    raise RealModelValidationError(
                        "REUSABLE_V11_SNAPSHOT_INTEGRITY_FAILED"
                    )
                if snapshot.immutable_hash != predecessor.snapshot_hash:
                    raise RealModelValidationError(
                        "REUSABLE_V11_SNAPSHOT_HASH_MISMATCH"
                    )
                account = await self._account(sample["proposal"].user_id)
                if account is None:
                    raise RealModelValidationError(
                        "formal validation account is unavailable"
                    )
                context, resolved, validation_proposal_id = await self._context(
                    validation_run_id=predecessor.validation_run_id,
                    sample=sample,
                    snapshot=snapshot,
                    normal_profile=normal_profile,
                    top_profile=top_profile,
                )
                model_context = build_model_runtime_context(
                    context,
                    resolved,
                    include_resolved_refs=False,
                )
                if (
                    context.context_hash != predecessor.decision_context_hash
                    or model_context.snapshot_id != predecessor.snapshot_id
                ):
                    raise RealModelValidationError(
                        "REUSABLE_V11_CONTEXT_HASH_MISMATCH"
                    )
                runtime_context_hash = predecessor.context_hash
                research = await self._reused_research(
                    predecessor=predecessor
                )
                research_ids = [item.research_result_id for item in research]
                if research_ids != predecessor.research_result_ids:
                    raise RealModelValidationError(
                        "REUSABLE_V11_RESEARCH_ORDER_MISMATCH"
                    )
                if any(
                    item.status
                    not in {"SUCCESS", "INSUFFICIENT_DATA", "DISABLED_NOT_REQUIRED"}
                    for item in research
                ):
                    failure_code = "RESEARCH_MODEL_PATH_FAILED"
                    status = "FAILED"
                else:
                    research_projection = [
                        _decision_research_projection(item) for item in research
                    ]
                    normal = NormalTradePlan.model_validate(
                        predecessor.normal_result
                    )
                    if (
                        normal.status != "PROPOSE_TRADE"
                        or normal.analysis_id != context.analysis_id
                        or normal.snapshot_id != context.snapshot_id
                        or normal.decision_context_id != context.decision_context_id
                        or normal.quant_proposal_id != context.quant_proposal_id
                        or normal.model_meta.context_hash != runtime_context_hash
                    ):
                        raise RealModelValidationError(
                            "REUSABLE_V11_NORMAL_IDENTITY_MISMATCH"
                        )
                    normal_result = normal.model_dump(mode="json")
                    normal_run_id = predecessor.normal_model_run_id
                    reused_research_and_normal = True
                    runner = await ProfiledDecisionModelRunner.create(
                        db=self.db,
                        run_mode="REAL_MODEL_VALIDATION",
                        automated_execution_allowed=False,
                        model_runtime_context_hash=runtime_context_hash,
                        research_results=research_projection,
                        model_call_analysis_id=model_call_analysis_id,
                        top_attempt_limit=1,
                    )
                    policy = await RiskPolicyRegistry(self.db).get_active()
                    top = await runner.run_top(
                        context=context,
                        plan=normal,
                        risk_policy_summary=policy.model_dump(
                            mode="json", exclude={"created_at", "config_hash"}
                        ),
                        attempt_number=2,
                        trace_id=validation_run_id,
                    )
                    top_result = top.model_dump(mode="json")
                    if top.status in {"MODEL_FAILED", "INVALID_OUTPUT"}:
                        failure_code = f"TOP_{top.status}"
                        status = "FAILED"
                    else:
                        validation_now = datetime.combine(
                            context.trade_date,
                            time(hour=15),
                            tzinfo=timezone(timedelta(hours=8)),
                        )
                        consensus = ConsensusEngine().evaluate(
                            context=context,
                            plan=normal,
                            review=top,
                            now=validation_now,
                            additional_top_prompt_versions={
                                runner.top_prompt.prompt_version
                            },
                        )
                        consensus_status = consensus.status
                        consensus_result = consensus.model_dump(mode="json")
                        if consensus.status != "CONSENSUS_PASS":
                            hard_risk_status = "NOT_REACHED_BY_DESIGN"
                            hard_risk_result = {
                                "reason_code": "CONSENSUS_DID_NOT_PASS",
                                "consensus_status": consensus.status,
                                "consensus_id": consensus.consensus_id,
                            }
                        else:
                            hard_risk = HardRiskEngine().evaluate(
                                data=resolved,
                                context=context,
                                consensus=consensus,
                                policy=policy,
                                account_id=str(account["account_id"]),
                                now=validation_now,
                            )
                            hard_risk_status = hard_risk.status
                            hard_risk_result = hard_risk.model_dump(mode="json")
                        try:
                            ExecutionModeSafetyGate.assert_snapshot_allowed(
                                snapshot.model_dump(mode="python")
                            )
                        except ExecutionModeBlockedError:
                            gate_invoked = True
                            gate_status = "BLOCKED_VALIDATION_MODE"
                        else:
                            raise RealModelValidationError(
                                "validation Snapshot escaped execution mode gate"
                            )
                        status = "COMPLETED"
                call_records = await self._model_call_records(
                    [context.analysis_id, model_call_analysis_id]
                )
                normal_matches = [
                    item for item in call_records if item["role"] == "NORMAL_TRADER"
                ]
                top_matches = [
                    item for item in call_records if item["role"] == "TOP_RISK_REVIEWER"
                ]
                normal_run_id = normal_matches[-1]["model_run_id"] if normal_matches else None
                top_run_id = top_matches[-1]["model_run_id"] if top_matches else None
        except Exception as exc:
            status = "FAILED"
            failure_code = (
                str(exc)
                if isinstance(exc, RealModelValidationError)
                else type(exc).__name__
            )

        call_records = (
            await self._model_call_records(
                [context.analysis_id, model_call_analysis_id]
            )
            if context
            else []
        )
        proposal = sample["proposal"] if sample else None
        result_payload = {
            "validation_run_id": validation_run_id,
            "validation_contract_version": VALIDATION_CONTRACT_VERSION,
            "contract_hash": self._validation_contract_hash(),
            "sample_selection_version": SAMPLE_SELECTION_VERSION,
            "actual_production_decision": False,
            "actual_execution": False,
            "requested_by": requested_by,
            "reused_from_validation_run_id": (
                predecessor.validation_run_id if predecessor else None
            ),
            "reused_research_and_normal": reused_research_and_normal,
            "snapshot_id": snapshot.snapshot_id if snapshot else None,
            "snapshot_hash": snapshot.immutable_hash if snapshot else None,
            "source_snapshot_id": proposal.snapshot_id if proposal else None,
            "source_quant_proposal_id": proposal.proposal_id if proposal else None,
            "source_sample_id": sample["sample_id"] if sample else None,
            "source_trade_date": proposal.trade_date if proposal else None,
            "symbol": proposal.symbol if proposal else None,
            "quant_proposal_id": validation_proposal_id,
            "context_hash": runtime_context_hash,
            "decision_context_hash": context.context_hash if context else None,
            "status": status,
            "research_result_ids": research_ids,
            "model_run_ids": [item["model_run_id"] for item in call_records],
            "model_call_records": call_records,
            "normal_model_run_id": normal_run_id,
            "top_model_run_id": top_run_id,
            "normal_result": normal_result,
            "top_result": top_result,
            "consensus_status": consensus_status,
            "consensus_result": consensus_result,
            "hard_risk_status": hard_risk_status,
            "hard_risk_result": hard_risk_result,
            "failure_code": failure_code,
            "execution_gate_invoked": gate_invoked,
            "execution_gate_status": gate_status,
            "input_hash": canonical_hash(identity),
            "created_at": started,
            "completed_at": datetime.now(timezone.utc),
            "schema_version": "real_model_validation_v5",
        }
        result_payload["result_hash"] = canonical_hash(
            result_payload,
            exclude={"result_hash", "created_at", "completed_at"},
        )
        result = RealModelValidationRun.model_validate(result_payload)
        saved, created = await self.repository.save_immutable(
            "validation_runs",
            result,
            identity={"validation_run_id": validation_run_id},
            hash_field="result_hash",
        )
        if created:
            return saved
        return saved.model_copy(update={"idempotency_status": "REUSED"})
