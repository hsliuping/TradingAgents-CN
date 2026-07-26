"""End-to-end snapshot -> factors -> regime -> strategy proposal pipeline."""

from __future__ import annotations

from app.schemas.alphaguard import QuantTradeProposal
from tradingagents.alphaguard.candidate_schemas import CandidateStatus

from .candidate_pool_service import CandidatePoolService
from .factor_aggregation import aggregate_factors
from .factor_engine import FactorEngine
from .factor_registry import DefinitionConflictError, FactorRegistry
from .market_regime_engine import MarketRegimeEngine
from .quant_audit_service import QuantAuditService
from .snapshot_data_resolver import SnapshotDataResolver
from .strategy_engine import StrategyEngine
from .strategy_registry import STRATEGY_SET_VERSION, StrategyRegistry


class QuantResearchPipeline:
    def __init__(self, db):
        self.db = db
        self.resolver = SnapshotDataResolver(db)
        self.factor_registry = FactorRegistry(db)
        self.strategy_registry = StrategyRegistry(db)
        self.factor_engine = FactorEngine(db)
        self.regime_engine = MarketRegimeEngine(db)
        self.strategy_engine = StrategyEngine()
        self.audit = QuantAuditService(db)

    async def evaluate(
        self,
        snapshot_id: str,
        *,
        user_id: str,
        candidate_id: str | None = None,
        trace_id: str | None = None,
    ) -> list[QuantTradeProposal]:
        await self.factor_registry.get_version_set(require_registered=True)
        strategies = await self.strategy_registry.require_strategy_set()
        data = await self.resolver.resolve(snapshot_id, user_id=user_id)
        if data.snapshot.strategy_version != STRATEGY_SET_VERSION:
            raise ValueError(
                f"snapshot strategy_version must be {STRATEGY_SET_VERSION}"
            )
        factor_results = await self.factor_engine.calculate_all(data, trace_id=trace_id)
        bundle = aggregate_factors(factor_results)
        regime = await self.regime_engine.calculate(data, trace_id=trace_id)
        proposals = []
        for definition in strategies:
            try:
                proposal = self.strategy_engine.evaluate(
                    definition,
                    data,
                    bundle,
                    regime,
                    candidate_id=candidate_id,
                )
                proposal = await self._persist(proposal, trace_id=trace_id)
                proposals.append(proposal)
                await self.audit.record(
                    "STRATEGY_EVALUATED",
                    snapshot_id=snapshot_id,
                    entity_id=f"{definition.strategy_id}:{definition.strategy_version}",
                    trace_id=trace_id,
                    details={
                        "proposal_id": proposal.proposal_id,
                        "status": proposal.status,
                    },
                )
            except Exception as exc:
                await self.audit.record(
                    "STRATEGY_EVALUATION_FAILED",
                    snapshot_id=snapshot_id,
                    entity_id=definition.strategy_id,
                    trace_id=trace_id,
                    details={"error_type": type(exc).__name__},
                )
                raise
        if candidate_id and any(item.status == "TRIGGERED" for item in proposals):
            candidate_service = CandidatePoolService(db=self.db)
            candidate = await candidate_service.get_candidate(candidate_id, user_id)
            if candidate and candidate.status == CandidateStatus.WATCHING:
                await candidate_service.transition_status(
                    candidate_id,
                    user_id,
                    CandidateStatus.SIGNAL_DETECTED,
                    reason="deterministic PR-004 strategy trigger",
                    trace_id=trace_id,
                )
        return proposals

    async def _persist(
        self, proposal: QuantTradeProposal, *, trace_id: str | None
    ) -> QuantTradeProposal:
        identity = {
            "snapshot_id": proposal.snapshot_id,
            "strategy_id": proposal.strategy_id,
            "strategy_version": proposal.strategy_version,
        }
        existing = await self.db["ag_quant_proposals"].find_one(identity)
        if existing:
            existing.pop("_id", None)
            stored = QuantTradeProposal.model_validate(existing)
            if stored.input_hash != proposal.input_hash:
                await self.audit.record(
                    "QUANT_INTEGRITY_CONFLICT",
                    snapshot_id=proposal.snapshot_id,
                    entity_id=stored.proposal_id,
                    trace_id=trace_id,
                    details={"entity": "QuantTradeProposal"},
                )
                raise DefinitionConflictError("immutable QuantTradeProposal conflict")
            return stored
        await self.db["ag_quant_proposals"].insert_one(
            proposal.model_dump(mode="python")
        )
        await self.audit.record(
            "QUANT_PROPOSAL_CREATED",
            snapshot_id=proposal.snapshot_id,
            entity_id=proposal.proposal_id,
            trace_id=trace_id,
            details={
                "strategy_id": proposal.strategy_id,
                "status": proposal.status,
                "automated_execution_allowed": False,
            },
        )
        return proposal
