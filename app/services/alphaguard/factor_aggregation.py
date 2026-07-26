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


def aggregate_factors(results) -> FactorEvidenceBundle:
    factor_set_version, definitions, coverage_threshold = builtin_factor_definitions()
    definition_groups = {
        group: [item.factor_id for item in definitions if item.group == group]
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
        weights = {
            result.factor_id: (1.0 / len(valid) if valid else 0.0)
            for result in valid
        }
        score = (
            sum(float(result.normalized_score) * weights[result.factor_id] for result in valid)
            if valid and coverage >= coverage_threshold
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
            "factor_set_version": factor_set_version,
            "results": [
                {
                    "result_id": result.result_id,
                    "input_hash": result.input_hash,
                    "score": result.normalized_score,
                }
                for result in results
            ],
            "group_coverage_threshold": coverage_threshold,
        }
    )
    return FactorEvidenceBundle(
        snapshot_id=results[0].snapshot_id if results else "missing-snapshot",
        factor_set_version=factor_set_version,
        results=results,
        group_scores=group_scores,
        group_coverage=group_coverage,
        group_details=details,
        missing_factor_ids=sorted(set(missing)),
        risk_flags=risks,
        input_hash=input_hash,
        calculated_at=datetime.utcnow(),
    )
