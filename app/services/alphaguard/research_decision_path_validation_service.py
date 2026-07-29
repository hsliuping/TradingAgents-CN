"""Research-only structural validation of the dual-model decision path."""

from __future__ import annotations

from datetime import date, datetime, time
from typing import Any
from uuid import NAMESPACE_URL, uuid5

from app.schemas.alphaguard.decision import DecisionContext, canonical_hash
from app.schemas.alphaguard.quant import MarketRegimeResult, QuantTradeProposal
from app.services.alphaguard.consensus_engine import ConsensusEngine
from app.services.alphaguard.decision_model_runner import (
    ExistingProviderDecisionModelRunner,
)
from app.services.alphaguard.evidence_snapshot_service import (
    EvidenceSnapshotService,
)
from app.services.alphaguard.hard_risk_engine import HardRiskEngine
from app.services.alphaguard.paper_storage import (
    clean_document,
    mongo_date,
    to_mongo_value,
)
from app.services.alphaguard.quant_config import sha256_value
from app.services.alphaguard.risk_policy_registry import builtin_risk_policy
from app.services.alphaguard.snapshot_data_resolver import ResolvedSnapshotData
from tradingagents.alphaguard.backfill_schemas import (
    HistoricalResearchSnapshot,
)
from tradingagents.alphaguard.decision_schemas import (
    EvidenceRef,
    ModelExecutionMeta,
    NormalTradePlan,
    TopReviewDecision,
)


CANONICAL_BACKFILL_RUN_ID = "9b921ffa-71a5-578b-85e8-252b2f9cfca9"
STRUCTURAL_STUB_VERSION = "research-decision-structural-stub-v1"


class ResearchDecisionPathValidationError(RuntimeError):
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


def _meta(
    *,
    context: DecisionContext,
    prompt_name: str,
    prompt_version: str,
    now: datetime,
) -> ModelExecutionMeta:
    input_hash = sha256_value(
        {
            "structural_stub_version": STRUCTURAL_STUB_VERSION,
            "context_hash": context.context_hash,
            "prompt_version": prompt_version,
        }
    )
    return ModelExecutionMeta(
        provider="deterministic-structural-stub",
        model_name="alphaguard-structure-validator",
        model_version=STRUCTURAL_STUB_VERSION,
        prompt_name=prompt_name,
        prompt_version=prompt_version,
        started_at=now,
        finished_at=now,
        latency_ms=0,
        execution_status="SUCCESS",
        request_id=str(
            uuid5(
                NAMESPACE_URL,
                f"alphaguard:structural-model-request:{input_hash}",
            )
        ),
        trace_id=f"research-structural:{context.quant_proposal_id}",
        raw_output_hash=sha256_value(
            {"status": "STRUCTURAL_STUB_VALIDATION", "input_hash": input_hash}
        ),
        template_hash=sha256_value(
            {
                "prompt_name": prompt_name,
                "prompt_version": prompt_version,
            }
        ),
        context_hash=context.context_hash,
        input_hash=input_hash,
    )


class ResearchDecisionPathValidationService:
    """Never invokes a provider and never imports execution/outbox writers."""

    COLLECTION = "ag_research_decision_path_validations"

    def __init__(self, db):
        self.db = db

    async def run(
        self,
        *,
        execute: bool,
        backfill_run_id: str = CANONICAL_BACKFILL_RUN_ID,
    ) -> dict[str, Any]:
        proposal_rows = await self.db[
            "ag_research_quant_proposals"
        ].find(
            {
                "backfill_run_id": backfill_run_id,
                "quant_proposal.status": "TRIGGERED",
            }
        ).sort("sample_id", 1).to_list(length=None)
        if len(proposal_rows) != 4:
            raise ResearchDecisionPathValidationError(
                "canonical run must contain exactly four natural TRIGGERED samples"
            )
        sample_audits = []
        for raw in proposal_rows:
            proposal = QuantTradeProposal.model_validate(
                raw["quant_proposal"]
            )
            wrapper_raw = await self.db["ag_research_snapshots"].find_one(
                {
                    "backfill_run_id": backfill_run_id,
                    "sample_id": raw["sample_id"],
                }
            )
            if wrapper_raw is None:
                raise ResearchDecisionPathValidationError(
                    "canonical research Snapshot is missing"
                )
            wrapper = HistoricalResearchSnapshot.model_validate(
                clean_document(wrapper_raw)
            )
            refs = wrapper.evidence_snapshot.raw_refs
            future_refs = []
            for category in ("prices", "benchmark_prices"):
                for reference in refs.get(category, []):
                    reference_date = _date_value(reference.rsplit(":", 1)[-1])
                    if (
                        reference_date is not None
                        and reference_date > proposal.trade_date
                    ):
                        future_refs.append(reference)
            status_count = await self.db[
                "ag_security_trading_statuses"
            ].count_documents(
                {
                    "symbol": proposal.symbol,
                    "trade_date": mongo_date(proposal.trade_date),
                }
            )
            exact_quote = clean_document(
                await self.db["stock_daily_quotes"].find_one(
                    {
                        "symbol": proposal.symbol,
                        "market": "CN",
                        "trade_date": mongo_date(proposal.trade_date),
                        "period": "daily",
                    }
                )
            )
            explicit_limits = bool(
                exact_quote
                and exact_quote.get("limit_up_price") is not None
                and exact_quote.get("limit_down_price") is not None
            )
            reasons = []
            if status_count != 1:
                reasons.append("VERSIONED_TRADING_STATUS_MISSING")
            if not explicit_limits:
                reasons.append("EXPLICIT_PRICE_LIMITS_MISSING")
            if future_refs:
                reasons.append("LEGACY_RAW_REFS_INCLUDE_FUTURE_DATES")
            sample_audits.append(
                {
                    "sample_id": str(raw["sample_id"]),
                    "proposal_id": proposal.proposal_id,
                    "snapshot_id": proposal.snapshot_id,
                    "symbol": proposal.symbol,
                    "trade_date": proposal.trade_date.isoformat(),
                    "strategy_id": proposal.strategy_id,
                    "strategy_version": proposal.strategy_version,
                    "natural_trigger": True,
                    "snapshot_integrity": (
                        EvidenceSnapshotService.verify_integrity(
                            wrapper.evidence_snapshot
                        )
                    ),
                    "benchmark_ref_count": len(
                        refs.get("benchmark_prices", [])
                    ),
                    "trading_status_count": status_count,
                    "explicit_price_limits": explicit_limits,
                    "future_ref_count": len(future_refs),
                    "eligible_for_real_model": not reasons,
                    "blocking_reasons": reasons,
                }
            )

        eligible = [
            item for item in sample_audits if item["eligible_for_real_model"]
        ]
        # The four natural triggers are not eligible for a real model call.
        # A single deterministic structural fixture, anchored to the first
        # natural proposal, exercises the actual Consensus and HardRisk code.
        structural = await self._structural_stub(
            proposal_row=proposal_rows[0],
            backfill_run_id=backfill_run_id,
        )
        validation_id = str(
            uuid5(
                NAMESPACE_URL,
                (
                    "alphaguard:research-decision-path-validation:"
                    f"{backfill_run_id}:{STRUCTURAL_STUB_VERSION}"
                ),
            )
        )
        stable_payload = {
            "validation_id": validation_id,
            "backfill_run_id": backfill_run_id,
            "run_mode": "RESEARCH_DECISION_PATH_VALIDATION",
            "research_only": True,
            "automated_execution_allowed": False,
            "natural_triggered_samples": sample_audits,
            "eligible_real_model_sample_count": len(eligible),
            "real_model_status": (
                "NOT_CALLED_NO_EVIDENCE_COMPLETE_SAMPLE"
                if not eligible
                else "NOT_CALLED_COST_CONTROL"
            ),
            "structural_stub_validation": structural,
        }
        result_hash = sha256_value(stable_payload)
        action = "WOULD_CREATE"
        if execute:
            existing = clean_document(
                await self.db[self.COLLECTION].find_one(
                    {"validation_id": validation_id}
                )
            )
            if existing:
                if existing.get("result_hash") != result_hash:
                    raise ResearchDecisionPathValidationError(
                        "INTEGRITY_CONFLICT: decision validation changed"
                    )
                action = "REUSED"
            else:
                await self.db[self.COLLECTION].insert_one(
                    to_mongo_value(
                        {
                            **stable_payload,
                            "result_hash": result_hash,
                            "created_at": datetime.utcnow(),
                            "schema_version": (
                                "research-decision-path-validation-v1"
                            ),
                        }
                    )
                )
                action = "CREATED"
        return {
            **stable_payload,
            "result_hash": result_hash,
            "write": execute,
            "action": action,
        }

    async def _structural_stub(
        self,
        *,
        proposal_row: dict[str, Any],
        backfill_run_id: str,
    ) -> dict[str, Any]:
        proposal = QuantTradeProposal.model_validate(
            proposal_row["quant_proposal"]
        )
        wrapper = HistoricalResearchSnapshot.model_validate(
            clean_document(
                await self.db["ag_research_snapshots"].find_one(
                    {
                        "backfill_run_id": backfill_run_id,
                        "sample_id": proposal_row["sample_id"],
                    }
                )
            )
        )
        regime_raw = clean_document(
            await self.db["ag_research_regime_results"].find_one(
                {
                    "backfill_run_id": backfill_run_id,
                    "sample_id": proposal_row["sample_id"],
                }
            )
        )
        if regime_raw is None:
            raise ResearchDecisionPathValidationError(
                "research MarketRegimeResult is missing"
            )
        regime = MarketRegimeResult.model_validate(
            regime_raw["regime_result"]
        )
        price_reference = next(
            (
                reference
                for reference in wrapper.evidence_snapshot.raw_refs.get(
                    "prices", []
                )
                if reference.endswith(proposal.trade_date.isoformat())
            ),
            wrapper.evidence_snapshot.raw_refs["prices"][-1],
        )
        evidence = [
            EvidenceRef(
                evidence_id=price_reference,
                summary=(
                    "STRUCTURAL_STUB_VALIDATION anchored to persisted "
                    "historical price identity"
                ),
                source="research-structural-price",
                as_of=datetime.combine(proposal.trade_date, time(15)),
            )
        ]
        evaluation_time = datetime.combine(proposal.trade_date, time(16))
        context_payload = {
            "analysis_id": (
                "research:decision-path-structural:"
                f"{proposal.proposal_id}"
            ),
            "user_id": proposal.user_id,
            "candidate_id": proposal.candidate_id,
            "symbol": proposal.symbol,
            "market": proposal.market,
            "trade_date": proposal.trade_date,
            "snapshot_id": proposal.snapshot_id,
            "quant_proposal_id": proposal.proposal_id,
            "strategy_id": proposal.strategy_id,
            "strategy_version": proposal.strategy_version,
            "factor_set_version": proposal.factor_set_version,
            "regime_result_id": proposal.regime_result_id,
            "quant_proposal": proposal,
            "factor_summary": proposal.factor_summary,
            "factor_result_ids": proposal.factor_result_ids,
            "market_regime": regime,
            "price_evidence": evidence,
            "financial_evidence": [],
            "news_evidence": [],
            "announcement_evidence": [],
            "account_evidence": [
                EvidenceRef(
                    evidence_id="research_stub_account:account-1",
                    summary="deterministic research-only account fixture",
                    source="STRUCTURAL_STUB_VALIDATION",
                )
            ],
            "portfolio_evidence": [],
            "data_quality_status": (
                wrapper.evidence_snapshot.data_quality.status
            ),
            "risk_flags": proposal.risk_flags,
            "missing_evidence": [
                "STRUCTURAL_STUB_ACCOUNT_AND_TRADING_STATE"
            ],
            "normal_prompt_version": "normal_trade_plan_quant_v1",
            "top_prompt_version": "top_review_decision_quant_v1",
            "created_at": evaluation_time,
            "schema_version": "decision-context-v1",
        }
        context_id = str(
            uuid5(
                NAMESPACE_URL,
                f"alphaguard:research-structural-context:{proposal.proposal_id}",
            )
        )
        draft = DecisionContext.model_construct(
            decision_context_id=context_id,
            context_hash="0" * 64,
            **context_payload,
        )
        context_payload["context_hash"] = canonical_hash(
            draft,
            exclude={"decision_context_id", "context_hash", "created_at"},
        )
        context_payload["decision_context_id"] = context_id
        context = DecisionContext.model_validate(context_payload)

        def normal_node(state: dict[str, Any]) -> dict[str, Any]:
            node_context = DecisionContext.model_validate(
                state["decision_context"]
            )
            plan = NormalTradePlan(
                plan_id=str(
                    uuid5(
                        NAMESPACE_URL,
                        (
                            "alphaguard:research-structural-plan:"
                            f"{proposal.proposal_id}"
                        ),
                    )
                ),
                snapshot_id=node_context.snapshot_id,
                quant_proposal_id=node_context.quant_proposal_id,
                analysis_id=node_context.analysis_id,
                decision_context_id=node_context.decision_context_id,
                symbol=node_context.symbol,
                market=node_context.market,
                trade_date=node_context.trade_date,
                strategy_id=node_context.strategy_id,
                strategy_version=node_context.strategy_version,
                status="PROPOSE_TRADE",
                action=proposal.action_candidate,
                confidence=0.8,
                thesis=(
                    "Deterministic structural validation; "
                    "not a model opinion."
                ),
                bullish_evidence=evidence,
                bearish_evidence=[],
                entry_zone=proposal.entry_zone,
                initial_position_pct=proposal.initial_position_pct,
                max_position_pct=proposal.max_position_pct,
                add_conditions=proposal.add_conditions,
                stop_conditions=[],
                reduce_conditions=proposal.reduce_conditions,
                exit_conditions=proposal.exit_conditions,
                invalidation_conditions=proposal.invalidation_conditions,
                target_price=None,
                valid_until=proposal.valid_until,
                main_risks=[],
                unresolved_questions=[],
                model_meta=_meta(
                    context=node_context,
                    prompt_name="normal_trade_plan",
                    prompt_version=node_context.normal_prompt_version,
                    now=evaluation_time,
                ),
            )
            return {"normal_trade_plan": plan.model_dump(mode="json")}

        def top_node(state: dict[str, Any]) -> dict[str, Any]:
            node_context = DecisionContext.model_validate(
                state["decision_context"]
            )
            plan = NormalTradePlan.model_validate(state["normal_trade_plan"])
            review = TopReviewDecision(
                review_id=str(
                    uuid5(
                        NAMESPACE_URL,
                        (
                            "alphaguard:research-structural-review:"
                            f"{proposal.proposal_id}"
                        ),
                    )
                ),
                snapshot_id=node_context.snapshot_id,
                plan_id=plan.plan_id,
                analysis_id=node_context.analysis_id,
                decision_context_id=node_context.decision_context_id,
                quant_proposal_id=node_context.quant_proposal_id,
                symbol=node_context.symbol,
                market=node_context.market,
                trade_date=node_context.trade_date,
                strategy_id=node_context.strategy_id,
                strategy_version=node_context.strategy_version,
                status="CONFIRM",
                completeness_score=1,
                logic_consistency_score=1,
                risk_control_score=1,
                missing_evidence=[],
                logical_conflicts=[],
                risk_findings=[],
                adjusted_plan=None,
                material_change_fields=[],
                review_reason=(
                    "Deterministic structural confirmation; "
                    "not a model opinion."
                ),
                model_meta=_meta(
                    context=node_context,
                    prompt_name="top_review_decision",
                    prompt_version=node_context.top_prompt_version,
                    now=evaluation_time,
                ),
            )
            return {"top_review_decision": review.model_dump(mode="json")}

        model_runner = ExistingProviderDecisionModelRunner(
            normal_node=normal_node,
            top_node=top_node,
        )
        normal = await model_runner.run_normal(
            context=context,
            attempt_number=1,
            trace_id=f"research-structural:{proposal.proposal_id}",
        )
        top = await model_runner.run_top(
            context=context,
            plan=normal,
            risk_policy_summary=builtin_risk_policy().model_dump(mode="json"),
            attempt_number=1,
            trace_id=f"research-structural:{proposal.proposal_id}",
        )
        consensus = ConsensusEngine().evaluate(
            context=context,
            plan=normal,
            review=top,
            now=evaluation_time,
        )
        quote_ref_id = price_reference.split(":", 1)[1].split(":", 1)[0]
        quote = clean_document(
            await self.db["stock_daily_quotes"].find_one(
                {"ref_id": quote_ref_id}
            )
        )
        if quote is None:
            raise ResearchDecisionPathValidationError(
                "structural fixture price reference is missing"
            )
        quote["_reference"] = price_reference
        quote["average_amount_20d"] = 100_000_000
        next_calendar = clean_document(
            await self.db["trading_calendar"].find_one(
                {
                    "market": "CN",
                    "is_open": True,
                    "session_date": {"$gt": mongo_date(proposal.trade_date)},
                },
                sort=[("session_date", 1)],
            )
        )
        if next_calendar is None:
            raise ResearchDecisionPathValidationError(
                "structural fixture calendar evidence is missing"
            )
        next_calendar["_reference"] = (
            "trading_calendar:"
            f"{next_calendar.get('calendar_id')}"
        )
        account_id = "research-structural-account"
        data = ResolvedSnapshotData(
            snapshot=wrapper.evidence_snapshot,
            prices=[quote],
            accounts=[
                {
                    "_reference": f"research_stub_account:{account_id}",
                    "account_id": account_id,
                    "user_id": proposal.user_id,
                    "status": "ACTIVE",
                    "market": "CN",
                    "currency": "CNY",
                    "cash": {"CNY": 800_000},
                    "equity": {"CNY": 1_000_000},
                    "total_exposure_pct": 0.2,
                    "industry_exposure_pct": {
                        "STRUCTURAL_STUB": 0.05
                    },
                    "new_positions_today": 0,
                    "active_orders_complete": True,
                    "portfolio_empty_verified": True,
                    "updated_at": evaluation_time,
                }
            ],
            instruments=[
                {
                    "_reference": (
                        f"research_stub_instrument:{proposal.symbol}"
                    ),
                    "symbol": proposal.symbol,
                    "market": proposal.market,
                    "industry": "STRUCTURAL_STUB",
                    "suspended": False,
                    "is_st": False,
                    "at_limit_up": False,
                    "at_limit_down": False,
                    "average_amount_20d": 100_000_000,
                }
            ],
            positions=[],
            portfolio_positions=[],
            orders=[],
            trading_calendar=[next_calendar],
            input_refs=[
                price_reference,
                f"research_stub_account:{account_id}",
                f"research_stub_instrument:{proposal.symbol}",
                next_calendar["_reference"],
            ],
            excluded_refs=[],
            input_hash=sha256_value(
                {
                    "snapshot_hash": wrapper.evidence_snapshot.immutable_hash,
                    "fixture_version": STRUCTURAL_STUB_VERSION,
                    "proposal_id": proposal.proposal_id,
                }
            ),
        )
        risk = HardRiskEngine().evaluate(
            data=data,
            context=context,
            consensus=consensus,
            policy=builtin_risk_policy(),
            account_id=account_id,
            now=evaluation_time,
        )
        return {
            "validation_type": "STRUCTURAL_STUB_VALIDATION",
            "source_proposal_id": proposal.proposal_id,
            "source_sample_id": str(proposal_row["sample_id"]),
            "normal_status": normal.status,
            "normal_model_provider": normal.model_meta.provider,
            "top_status": top.status,
            "top_model_provider": top.model_meta.provider,
            "top_material_change_fields": top.material_change_fields,
            "consensus_status": consensus.status,
            "hard_risk_status": risk.status,
            "hard_risk_reason": risk.reasons,
            "research_shadow_status": "NOT_RUN_EVIDENCE_INCOMPLETE",
            "research_shadow_reason": (
                "natural sample lacks versioned trading status and explicit "
                "price-limit evidence"
            ),
            "order_intent_created": risk.order_intent_created,
            "formal_write_allowed": False,
            "real_model_effect_validation": False,
            "input_hash": risk.input_hash,
        }
