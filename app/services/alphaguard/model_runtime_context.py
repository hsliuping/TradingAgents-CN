"""Snapshot-v2-only context envelope shared by every formal model role."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.schemas.alphaguard.decision import DecisionContext, canonical_hash
from tradingagents.alphaguard.evidence_schemas import (
    EVIDENCE_SNAPSHOT_SCHEMA_VERSION_V2,
    EVIDENCE_SNAPSHOT_SCHEMA_VERSION_V3,
)

from .snapshot_data_resolver import ResolvedSnapshotData


class ModelRuntimeContextError(ValueError):
    pass


@dataclass(frozen=True)
class ModelRuntimeContext:
    snapshot_id: str
    context_hash: str
    payload: dict[str, Any]
    evidence_refs: tuple[str, ...]


def build_model_runtime_context(
    context: DecisionContext,
    resolved: ResolvedSnapshotData,
    *,
    include_resolved_refs: bool = True,
) -> ModelRuntimeContext:
    snapshot = resolved.snapshot
    if context.snapshot_id != snapshot.snapshot_id:
        raise ModelRuntimeContextError("decision and evidence snapshots differ")
    if snapshot.schema_version not in {
        EVIDENCE_SNAPSHOT_SCHEMA_VERSION_V2,
        EVIDENCE_SNAPSHOT_SCHEMA_VERSION_V3,
    }:
        raise ModelRuntimeContextError("formal model runtime requires Snapshot v2 or v3")
    if snapshot.evidence_contract_status != "COMPLETE":
        raise ModelRuntimeContextError("Snapshot evidence contract is incomplete")
    if (
        not snapshot.benchmark_price_window_manifest_id
        or not snapshot.benchmark_price_window_manifest_hash
        or not snapshot.market_context_window_manifest_id
        or not snapshot.market_context_window_manifest_hash
        or (snapshot.actual_benchmark_count or 0)
        < (snapshot.required_benchmark_count or 61)
    ):
        raise ModelRuntimeContextError("Snapshot evidence windows are incomplete")
    if snapshot.schema_version == EVIDENCE_SNAPSHOT_SCHEMA_VERSION_V3 and (
        not snapshot.decision_evidence_pack_manifest_id
        or not snapshot.decision_evidence_pack_manifest_hash
        or snapshot.evidence_completeness_matrix is None
        or any(
            status not in {"COMPLETE", "NOT_APPLICABLE"}
            for status in snapshot.evidence_completeness_matrix.model_dump(
                mode="python"
            ).values()
        )
    ):
        raise ModelRuntimeContextError("Decision Evidence Pack v3 is incomplete")
    resolved_refs = sorted(resolved.input_refs)
    payload = {
        "decision_context": context.model_dump(mode="json"),
        "evidence_contract": {
            "snapshot_schema_version": snapshot.schema_version,
            "status": snapshot.evidence_contract_status,
            "benchmark_price_window_manifest_id": (
                snapshot.benchmark_price_window_manifest_id
            ),
            "benchmark_price_window_manifest_hash": (
                snapshot.benchmark_price_window_manifest_hash
            ),
            "required_benchmark_count": snapshot.required_benchmark_count,
            "actual_benchmark_count": snapshot.actual_benchmark_count,
            "market_context_window_manifest_id": (
                snapshot.market_context_window_manifest_id
            ),
            "market_context_window_manifest_hash": (
                snapshot.market_context_window_manifest_hash
            ),
            "market_context_id": snapshot.market_context_id,
            "market_context_hash": snapshot.market_context_hash,
            "snapshot_immutable_hash": snapshot.immutable_hash,
        },
        "resolved_input_hash": resolved.input_hash,
        "resolved_input_ref_count": len(resolved_refs),
    }
    if snapshot.schema_version == EVIDENCE_SNAPSHOT_SCHEMA_VERSION_V3:
        payload["evidence_contract"].update(
            {
                "decision_evidence_pack_manifest_id": (
                    snapshot.decision_evidence_pack_manifest_id
                ),
                "decision_evidence_pack_manifest_hash": (
                    snapshot.decision_evidence_pack_manifest_hash
                ),
                "evidence_completeness_matrix": (
                    snapshot.evidence_completeness_matrix.model_dump(
                        mode="json"
                    )
                ),
            }
        )
    if include_resolved_refs:
        payload["resolved_input_refs"] = resolved_refs
    else:
        selected_refs = {
            item.evidence_id
            for group in (
                context.price_evidence,
                context.financial_evidence,
                context.news_evidence,
                context.announcement_evidence,
                context.account_evidence,
                context.portfolio_evidence,
            )
            for item in group
        }
        if not selected_refs or not selected_refs.issubset(set(resolved_refs)):
            raise ModelRuntimeContextError(
                "compact model evidence refs are not locked by Snapshot"
            )
        derived_refs = {
            context.quant_proposal_id,
            context.regime_result_id,
            *context.factor_result_ids,
        }
        if any(not item for item in derived_refs):
            raise ModelRuntimeContextError(
                "compact model derived evidence identities are incomplete"
            )
        payload["allowed_raw_evidence_refs"] = sorted(selected_refs)
        payload["allowed_derived_evidence_refs"] = sorted(derived_refs)
        payload["allowed_evidence_refs"] = sorted(selected_refs | derived_refs)
    context_hash = canonical_hash(payload)
    return ModelRuntimeContext(
        snapshot_id=snapshot.snapshot_id,
        context_hash=context_hash,
        payload=payload,
        evidence_refs=tuple(resolved_refs),
    )
