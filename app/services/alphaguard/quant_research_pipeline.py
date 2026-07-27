"""End-to-end snapshot -> factors -> regime -> strategy proposal pipeline."""

from __future__ import annotations

from copy import deepcopy

from app.schemas.alphaguard import QuantTradeProposal
from tradingagents.alphaguard.candidate_schemas import CandidateStatus
from tradingagents.alphaguard.experiment_schemas import (
    ComponentVersionRecord,
    experiment_hash,
)

from .candidate_pool_service import CandidatePoolService
from .factor_aggregation import aggregate_factors
from .factor_engine import FactorEngine
from .factor_registry import DefinitionConflictError, FactorRegistry
from .market_regime_engine import MarketRegimeEngine
from .paper_storage import to_mongo_value
from .quant_audit_service import QuantAuditService
from .snapshot_data_resolver import SnapshotDataResolver
from .strategy_engine import StrategyEngine
from .strategy_registry import (
    STRATEGY_SET_VERSION,
    StrategyRegistry,
    builtin_strategy_definitions,
)
from .experiment_component_adapters import strategy_definition_from_payload
from .experiment_registry import ExperimentRegistry


class QuantResearchPipeline:
    def __init__(self, db):
        self.db = db
        self.resolver = SnapshotDataResolver(db)
        self.factor_registry = FactorRegistry(db)
        self.strategy_registry = StrategyRegistry(db)
        self.factor_engine = FactorEngine(db)
        self.regime_engine = MarketRegimeEngine(db)
        self.strategy_engine = StrategyEngine()
        self.experiment_registry = ExperimentRegistry(db)
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
        champion_refs = data.snapshot.champion_version_refs
        if champion_refs:
            (
                factor_payload,
                factor_set_version,
                regime_payload,
                strategies,
            ) = await self._locked_champion_inputs(champion_refs)
            factor_results = await self.factor_engine.calculate_all(
                data,
                trace_id=trace_id,
                factor_ids=factor_payload["factor_ids"],
            )
            bundle = aggregate_factors(
                factor_results,
                factor_set_version=factor_set_version,
                factor_weights=factor_payload.get("factor_weights"),
                coverage_threshold=factor_payload.get(
                    "group_coverage_threshold"
                ),
            )
            regime = await self.regime_engine.calculate(
                data,
                trace_id=trace_id,
                config=regime_payload,
            )
        else:
            factor_results = await self.factor_engine.calculate_all(
                data, trace_id=trace_id
            )
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

    async def _locked_champion_inputs(
        self,
        refs: dict[str, str],
    ) -> tuple[dict, str, dict, list]:
        records: dict[tuple[str, str], ComponentVersionRecord] = {}
        for slot_id, version_ref in sorted(refs.items()):
            component = await self.experiment_registry.component_version(
                version_ref
            )
            expected_slot = (
                f"{component.component_type}:"
                f"{component.component_key}:{component.market}"
            )
            if slot_id != expected_slot:
                raise ValueError("snapshot Champion slot/version mismatch")
            records[(component.component_type, component.component_key)] = (
                component
            )
        factor_set = records.get(("FACTOR_SET", "factor-set-v1"))
        factor_weight = records.get(("FACTOR_WEIGHT", "factor-set-v1"))
        regime = records.get(("REGIME_CONFIG", "cn-market-regime"))
        strategy_records = sorted(
            (
                item
                for (component_type, _), item in records.items()
                if component_type == "STRATEGY_CONFIG"
            ),
            key=lambda item: item.component_key,
        )
        expected_strategy_keys = {
            item.strategy_id for item in builtin_strategy_definitions()
        }
        if (
            factor_set is None
            or factor_weight is None
            or regime is None
            or {item.component_key for item in strategy_records}
            != expected_strategy_keys
        ):
            raise ValueError(
                "snapshot lacks the complete deterministic Champion set"
            )
        factor_payload = deepcopy(factor_set.payload)
        factor_payload["factor_weights"] = deepcopy(
            factor_weight.payload["factor_weights"]
        )
        factor_set_version = (
            "champion:"
            + experiment_hash(
                {
                    "factor_set": factor_set.version_ref,
                    "factor_weight": factor_weight.version_ref,
                }
            )
        )
        regime_payload = deepcopy(regime.payload)
        regime_payload["regime_version"] = regime.version_ref
        definitions = [
            strategy_definition_from_payload(
                item.payload,
                version_ref=item.version_ref,
                created_at=item.created_at,
            )
            for item in strategy_records
        ]
        return (
            factor_payload,
            factor_set_version,
            regime_payload,
            definitions,
        )

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
            to_mongo_value(proposal.model_dump(mode="python"))
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
