"""Build the immutable, snapshot-only input for both PR-005 model calls."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import NAMESPACE_URL, uuid5

from app.schemas.alphaguard.decision import DecisionContext, canonical_hash
from app.schemas.alphaguard.quant import (
    FactorResult,
    MarketRegimeResult,
    QuantTradeProposal,
)
from tradingagents.alphaguard.candidate_schemas import CandidateEntry
from tradingagents.alphaguard.decision_schemas import EvidenceRef

from .factor_aggregation import aggregate_factors
from .quant_config import sha256_value
from .snapshot_data_resolver import ResolvedSnapshotData, SnapshotDataResolver


NORMAL_QUANT_PROMPT_VERSION = "normal_trade_plan_quant_v1"
TOP_QUANT_PROMPT_VERSION = "top_review_decision_quant_v1"
MAX_EVIDENCE_REFS_PER_CATEGORY = 200


class DecisionContextError(ValueError):
    pass


class ProposalNotEligibleError(DecisionContextError):
    pass


def _clean(document: dict[str, Any]) -> dict[str, Any]:
    value = dict(document)
    value.pop("_id", None)
    return value


def _summary(document: dict[str, Any], category: str) -> str:
    preferred = (
        "summary",
        "title",
        "name",
        "account_id",
        "market",
        "currency",
        "close",
        "report_period",
        "trade_date",
        "quantity",
        "available_qty",
        "cash",
        "equity",
        "total_exposure_pct",
        "industry_exposure_pct",
        "new_positions_today",
        "active_orders_complete",
        "industry",
        "suspended",
        "is_st",
        "at_limit_up",
        "at_limit_down",
        "average_amount_20d",
        "status",
    )
    values = [
        f"{key}={document[key]}"
        for key in preferred
        if document.get(key) is not None
    ]
    if not values:
        values = [
            f"{key}={value}"
            for key, value in sorted(document.items())
            if key not in {"_id", "content", "body", "raw_data"}
        ][:6]
    text = f"{category}: " + ", ".join(values)
    return text[:400] or f"{category} snapshot evidence"


def _refs(documents: list[dict[str, Any]], category: str) -> list[EvidenceRef]:
    result = []
    for document in documents:
        reference = str(document.get("_reference") or "")
        if not reference:
            raise DecisionContextError(f"{category} evidence lacks snapshot reference")
        as_of = None
        for field in (
            "as_of",
            "timestamp",
            "updated_at",
            "created_at",
            "publish_time",
            "published_at",
        ):
            if document.get(field) is not None:
                try:
                    as_of = datetime.fromisoformat(
                        str(document[field]).replace("Z", "+00:00")
                    )
                except (TypeError, ValueError):
                    pass
                break
        result.append(
            EvidenceRef(
                evidence_id=reference,
                summary=_summary(document, category),
                source=category,
                as_of=as_of,
            )
        )
    return sorted(
        result, key=lambda item: item.evidence_id
    )[:MAX_EVIDENCE_REFS_PER_CATEGORY]


class DecisionContextBuilder:
    """No latest-data queries: every evidence document comes from raw_refs."""

    def __init__(self, db):
        self.db = db
        self.resolver = SnapshotDataResolver(db)

    @staticmethod
    def _validate_critical_evidence(
        proposal: QuantTradeProposal,
        data: ResolvedSnapshotData,
    ) -> None:
        missing: list[str] = []
        if data.snapshot.data_quality.status == "FAIL":
            missing.append("data_quality")
        if not data.prices:
            missing.append("price_evidence")
        if not data.accounts:
            missing.append("account_snapshot")
        if not data.trading_calendar:
            missing.append("trading_calendar")
        trading_state = (
            data.trading_status[-1]
            if data.trading_status
            else data.instruments[-1]
            if data.instruments
            else None
        )
        if trading_state is None:
            missing.append("instrument_trading_state")
        else:
            versioned_status = bool(data.trading_status)
            required = ["is_suspended" if versioned_status else "suspended"]
            required.append(
                "upper_limit_price"
                if versioned_status and proposal.action_candidate == "BUY"
                else "lower_limit_price"
                if versioned_status
                else "at_limit_up"
                if proposal.action_candidate == "BUY"
                else "at_limit_down"
            )
            if proposal.action_candidate == "BUY":
                required.append("is_st")
            missing.extend(
                f"instrument.{field}"
                for field in required
                if field not in trading_state
                or trading_state.get(field) is None
            )
        if proposal.action_candidate in {"SELL", "REDUCE"} and not data.positions:
            missing.append("target_position_snapshot")
        if proposal.action_candidate == "BUY" and (
            not data.portfolio_positions
            and not any(
                bool(item.get("portfolio_empty_verified"))
                for item in data.accounts
            )
        ):
            missing.append("portfolio_snapshot")
        if missing:
            raise DecisionContextError(
                "critical snapshot evidence missing: "
                + ", ".join(sorted(set(missing)))
            )

    async def build(
        self,
        quant_proposal_id: str,
        *,
        user_id: str,
        allow_reprocess_model_validation: bool = False,
        persist: bool = True,
    ) -> tuple[DecisionContext, ResolvedSnapshotData]:
        document = await self.db["ag_quant_proposals"].find_one(
            {"proposal_id": quant_proposal_id, "user_id": str(user_id)}
        )
        if document is None:
            raise DecisionContextError("QuantTradeProposal not found")
        proposal = QuantTradeProposal.model_validate(_clean(document))
        normally_eligible = (
            proposal.status != "TRIGGERED"
            or proposal.action_candidate not in {"BUY", "SELL", "REDUCE"}
            or proposal.automated_execution_allowed is not False
        )
        if normally_eligible and not allow_reprocess_model_validation:
            raise ProposalNotEligibleError(
                "only TRIGGERED BUY/SELL/REDUCE proposals enter model review"
            )

        data = await self.resolver.resolve(
            proposal.snapshot_id,
            user_id=str(user_id),
        )
        if allow_reprocess_model_validation and (
            data.snapshot.run_mode != "PRODUCTION_REPROCESS"
            or data.snapshot.automated_execution_allowed is not False
            or data.snapshot.original_realtime_run is not False
        ):
            raise DecisionContextError(
                "model-validation bypass is restricted to non-executable "
                "PRODUCTION_REPROCESS snapshots"
            )
        self._validate_critical_evidence(proposal, data)
        snapshot = data.snapshot
        if (
            snapshot.user_id != proposal.user_id
            or snapshot.symbol != proposal.symbol
            or snapshot.market != proposal.market
            or snapshot.trade_date != proposal.trade_date
        ):
            raise DecisionContextError("proposal and snapshot identity mismatch")

        candidate = None
        if proposal.candidate_id:
            candidate_document = await self.db["ag_candidates"].find_one(
                {
                    "candidate_id": proposal.candidate_id,
                    "user_id": str(user_id),
                }
            )
            if candidate_document is None:
                raise DecisionContextError("proposal candidate does not exist")
            candidate = CandidateEntry.model_validate(_clean(candidate_document))
            if (
                candidate.symbol != proposal.symbol
                or candidate.market != proposal.market
            ):
                raise DecisionContextError("candidate and proposal identity mismatch")

        factor_documents = await self.db["ag_factor_results"].find(
            {"result_id": {"$in": proposal.factor_result_ids}}
        ).to_list(length=None)
        factors = [
            FactorResult.model_validate(_clean(item)) for item in factor_documents
        ]
        if {item.result_id for item in factors} != set(proposal.factor_result_ids):
            raise DecisionContextError("one or more FactorResult records are missing")
        if any(
            item.snapshot_id != proposal.snapshot_id
            or item.symbol != proposal.symbol
            or item.market != proposal.market
            or item.trade_date != proposal.trade_date
            for item in factors
        ):
            raise DecisionContextError("FactorResult identity mismatch")

        regime_document = await self.db["ag_regime_results"].find_one(
            {"regime_result_id": proposal.regime_result_id}
        )
        if regime_document is None:
            raise DecisionContextError("MarketRegimeResult not found")
        regime = MarketRegimeResult.model_validate(_clean(regime_document))
        if (
            regime.snapshot_id != proposal.snapshot_id
            or regime.trade_date != proposal.trade_date
        ):
            raise DecisionContextError("MarketRegimeResult identity mismatch")

        strategy_document = await self.db["ag_strategy_definitions"].find_one(
            {
                "strategy_id": proposal.strategy_id,
                "strategy_version": proposal.strategy_version,
            }
        )
        if snapshot.champion_version_refs:
            from .quant_research_pipeline import QuantResearchPipeline

            (
                factor_payload,
                locked_factor_set_version,
                _,
                locked_strategies,
            ) = await QuantResearchPipeline(self.db)._locked_champion_inputs(
                snapshot.champion_version_refs
            )
            locked_strategy = next(
                (
                    item
                    for item in locked_strategies
                    if item.strategy_id == proposal.strategy_id
                    and item.strategy_version == proposal.strategy_version
                ),
                None,
            )
            if locked_strategy is None:
                raise DecisionContextError(
                    "Champion-locked StrategyDefinition not found"
                )
            if proposal.factor_set_version != locked_factor_set_version:
                raise DecisionContextError(
                    "Champion-locked factor-set version mismatch"
                )
            bundle = aggregate_factors(
                factors,
                factor_set_version=locked_factor_set_version,
                factor_weights=factor_payload.get("factor_weights"),
                coverage_threshold=factor_payload.get(
                    "group_coverage_threshold"
                ),
            )
            strategy_code_hash = locked_strategy.code_hash
            strategy_parameter_hash = locked_strategy.parameter_hash
        else:
            if strategy_document is None:
                raise DecisionContextError("StrategyDefinition not found")
            bundle = aggregate_factors(factors)
            strategy_code_hash = strategy_document.get("code_hash")
            strategy_parameter_hash = strategy_document.get("parameter_hash")
        expected_input_hash = sha256_value(
            {
                "snapshot_input_hash": data.input_hash,
                "factor_bundle_hash": bundle.input_hash,
                "regime_input_hash": regime.input_hash,
                "strategy_id": proposal.strategy_id,
                "strategy_version": proposal.strategy_version,
                "code_hash": strategy_code_hash,
                "parameter_hash": strategy_parameter_hash,
            }
        )
        if proposal.input_hash != expected_input_hash:
            raise DecisionContextError("QuantTradeProposal input_hash mismatch")

        allowed_refs = set(data.input_refs)
        proposal_refs = {item.evidence_id for item in proposal.evidence_refs}
        factor_refs = {ref for item in factors for ref in item.input_refs}
        derived_refs = {item.result_id for item in factors}
        if not proposal_refs.issubset(allowed_refs | derived_refs):
            raise DecisionContextError("proposal evidence escapes EvidenceSnapshot")
        if not factor_refs.issubset(allowed_refs):
            raise DecisionContextError("factor evidence escapes EvidenceSnapshot")

        missing = list(snapshot.data_quality.missing_fields)
        if proposal.action_candidate == "BUY":
            if not data.accounts:
                missing.append("account_snapshot")
            if not data.portfolio_positions and not any(
                bool(item.get("portfolio_empty_verified")) for item in data.accounts
            ):
                missing.append("portfolio_snapshot")

        analysis_id = snapshot.analysis_id or f"ag-analysis:{proposal.proposal_id}"
        payload: dict[str, Any] = {
            "analysis_id": analysis_id,
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
            "factor_result_ids": sorted(proposal.factor_result_ids),
            "market_regime": regime,
            "price_evidence": sorted(
                _refs(data.prices, "price")
                + _refs(data.instruments, "instrument")
                + _refs(data.trading_status, "trading_status")
                + _refs(data.trading_calendar, "trading_calendar"),
                key=lambda item: item.evidence_id,
            )[:MAX_EVIDENCE_REFS_PER_CATEGORY],
            "financial_evidence": _refs(data.financials, "financial"),
            "news_evidence": _refs(data.news, "news"),
            "announcement_evidence": _refs(
                data.announcements, "announcement"
            ),
            "account_evidence": _refs(data.accounts, "account"),
            "portfolio_evidence": _refs(
                data.positions + data.portfolio_positions + data.orders,
                "portfolio",
            ),
            "data_quality_status": snapshot.data_quality.status,
            "risk_flags": sorted(set(proposal.risk_flags)),
            "missing_evidence": sorted(set(missing)),
            "normal_prompt_version": NORMAL_QUANT_PROMPT_VERSION,
            "top_prompt_version": TOP_QUANT_PROMPT_VERSION,
            "created_at": datetime.utcnow(),
            "schema_version": "decision-context-v1",
        }
        draft = DecisionContext.model_construct(
            decision_context_id="pending",
            context_hash="0" * 64,
            **payload,
        )
        context_hash = canonical_hash(
            draft,
            exclude={"decision_context_id", "context_hash", "created_at"},
        )
        payload["context_hash"] = context_hash
        payload["decision_context_id"] = str(
            uuid5(NAMESPACE_URL, f"alphaguard-context:{context_hash}")
        )
        context = DecisionContext.model_validate(payload)

        if not persist:
            return context, data
        existing = await self.db["ag_decision_contexts"].find_one(
            {"analysis_id": analysis_id}
        )
        if existing is not None:
            existing.pop("_id", None)
            stored = DecisionContext.model_validate(existing)
            if stored.context_hash != context.context_hash:
                raise DecisionContextError(
                    "immutable DecisionContext identity conflict"
                )
            return stored, data
        await self.db["ag_decision_contexts"].insert_one(
            context.model_dump(mode="python")
        )
        return context, data
