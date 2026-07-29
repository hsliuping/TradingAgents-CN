"""Snapshot-v2-only context envelope shared by every formal model role."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.schemas.alphaguard.decision import DecisionContext, canonical_hash
from tradingagents.alphaguard.evidence_schemas import (
    EVIDENCE_SNAPSHOT_SCHEMA_VERSION_V2,
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
) -> ModelRuntimeContext:
    snapshot = resolved.snapshot
    if context.snapshot_id != snapshot.snapshot_id:
        raise ModelRuntimeContextError("decision and evidence snapshots differ")
    if snapshot.schema_version != EVIDENCE_SNAPSHOT_SCHEMA_VERSION_V2:
        raise ModelRuntimeContextError("formal model runtime requires Snapshot v2")
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
        "resolved_input_refs": sorted(resolved.input_refs),
    }
    context_hash = canonical_hash(payload)
    return ModelRuntimeContext(
        snapshot_id=snapshot.snapshot_id,
        context_hash=context_hash,
        payload=payload,
        evidence_refs=tuple(sorted(resolved.input_refs)),
    )
