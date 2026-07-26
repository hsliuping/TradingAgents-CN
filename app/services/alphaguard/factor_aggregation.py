"""Coverage-aware deterministic factor grouping."""

from __future__ import annotations

from datetime import datetime

from app.schemas.alphaguard import FactorEvidenceBundle
from app.schemas.alphaguard.quant import GroupAggregation

from .factor_registry import builtin_factor_definitions
from .quant_config import sha256_value


ALL_GROUPS = (
    "TREND",
    "MOMENTUM",
    "QUALITY",
    "VALUATION",
    "LIQUIDITY",
    "VOLATILITY_RISK",
    "EVENT_RISK",
    "INDUSTRY_STRENGTH",
)


def aggregate_factors(
    results,
    *,
    factor_set_version: str | None = None,
    factor_weights: dict[str, float] | None = None,
    coverage_threshold: float | None = None,
) -> FactorEvidenceBundle:
    # Preserve PR-004 behavior when no Champion overrides are supplied.
    builtin_version, definitions, builtin_coverage = builtin_factor_definitions()
    resolved_factor_set_version = factor_set_version or builtin_version
    resolved_coverage_threshold = (
        builtin_coverage
        if coverage_threshold is None
        else float(coverage_threshold)
    )
    configured_weights = {
        str(key): max(0.0, float(value))
        for key, value in (factor_weights or {}).items()
    }
    selected_ids = {result.factor_id for result in results}
    definition_groups = {
        group: [
            item.factor_id
            for item in definitions
            if item.group == group and item.factor_id in selected_ids
        ]
        for group in ALL_GROUPS
    }
    by_id = {result.factor_id: result for result in results}
    details = {}
    group_scores = {}
    group_coverage = {}
    missing = []
    for group, factor_ids in definition_groups.items():
        valid = [
            by_id[factor_id]
            for factor_id in factor_ids
            if factor_id in by_id and by_id[factor_id].normalized_score is not None
        ]
        missing_ids = [
            factor_id
            for factor_id in factor_ids
            if factor_id not in by_id or by_id[factor_id].normalized_score is None
        ]
        missing.extend(missing_ids)
        total = len(factor_ids)
        coverage = len(valid) / total if total else 0.0
        raw_weights = {
            result.factor_id: configured_weights.get(result.factor_id, 1.0)
            for result in valid
        }
        weight_total = sum(raw_weights.values())
        weights = {
            factor_id: value / weight_total
            for factor_id, value in raw_weights.items()
        } if weight_total > 0 else {}
        score = (
            sum(float(result.normalized_score) * weights[result.factor_id] for result in valid)
            if valid
            and coverage >= resolved_coverage_threshold
            and weights
            else None
        )
        detail = GroupAggregation(
            valid_factor_count=len(valid),
            total_factor_count=total,
            coverage=coverage,
            factor_weights=weights,
            missing_factor_ids=missing_ids,
            score=score,
        )
        details[group] = detail
        group_scores[group] = score
        group_coverage[group] = coverage

    risks = []
    volatility = group_scores["VOLATILITY_RISK"]
    event = group_scores["EVENT_RISK"]
    if volatility is not None and volatility >= 75:
        risks.append("ELEVATED_VOLATILITY_RISK")
    if event is not None and event >= 70:
        risks.append("BLOCKING_EVENT_RISK")
    input_hash = sha256_value(
        {
            "factor_set_version": resolved_factor_set_version,
            "results": [
                {
                    "result_id": result.result_id,
                    "input_hash": result.input_hash,
                    "score": result.normalized_score,
                }
                for result in results
            ],
            "group_coverage_threshold": resolved_coverage_threshold,
        }
    )
    return FactorEvidenceBundle(
        snapshot_id=results[0].snapshot_id if results else "missing-snapshot",
        factor_set_version=resolved_factor_set_version,
        results=results,
        group_scores=group_scores,
        group_coverage=group_coverage,
        group_details=details,
        missing_factor_ids=sorted(set(missing)),
        risk_flags=risks,
        input_hash=input_hash,
        calculated_at=datetime.utcnow(),
    )
