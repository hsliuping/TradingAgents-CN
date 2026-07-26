"""Versioned, side-effect-free component adapters for PR-008."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import NAMESPACE_URL, uuid5

from app.schemas.alphaguard import (
    FactorEvidenceBundle,
    FactorResult,
    StrategyDefinition,
)
from app.schemas.alphaguard.quant import GroupAggregation
from app.services.alphaguard.factor_aggregation import ALL_GROUPS
from app.services.alphaguard.factor_engine import _calculate, _direction, _normalize
from app.services.alphaguard.factor_registry import builtin_factor_definitions
from app.services.alphaguard.market_regime_engine import calculate_regime_result
from app.services.alphaguard.quant_config import (
    REGIME_ENGINE_CODE_VERSION,
    STRATEGY_ENGINE_CODE_VERSION,
    factor_config,
    regime_config,
    sha256_value,
    strategy_configs,
)
from app.services.alphaguard.strategy_engine import StrategyEngine
from tradingagents.alphaguard.experiment_schemas import (
    ComponentVersionRecord,
    ExperimentComponentType,
    experiment_hash,
)


EXECUTABLE_COMPONENTS = frozenset(
    {"FACTOR_WEIGHT", "FACTOR_SET", "REGIME_CONFIG", "STRATEGY_CONFIG"}
)
REGISTER_ONLY_COMPONENTS = frozenset(
    {
        "FACTOR_FORMULA",
        "NORMAL_PROMPT",
        "TOP_PROMPT",
        "MODEL_CONFIG",
        "AGENT_CONFIG",
        "DEBATE_CONFIG",
        "HARD_RISK_CONFIG",
        "MATCHING_CONFIG",
    }
)


def component_capability(component_type: str) -> dict[str, Any]:
    if component_type in EXECUTABLE_COMPONENTS:
        return {
            "registration_supported": True,
            "execution_supported": True,
            "promotion_eligible": True,
            "reason": None,
        }
    if component_type in REGISTER_ONLY_COMPONENTS:
        return {
            "registration_supported": True,
            "execution_supported": False,
            "promotion_eligible": False,
            "reason": "UNSUPPORTED_COMPONENT_ADAPTER",
        }
    raise ValueError(f"unsupported experiment component type: {component_type}")


def _weight_payload() -> dict[str, Any]:
    config = factor_config()
    return {
        "factor_set_version": config["factor_set_version"],
        "factor_ids": sorted(item["factor_id"] for item in config["factors"]),
        "factor_weights": {
            item["factor_id"]: 1.0 for item in config["factors"]
        },
        "group_coverage_threshold": config["group_coverage_threshold"],
    }


def _factor_set_payload() -> dict[str, Any]:
    config = factor_config()
    return {
        "factor_set_version": config["factor_set_version"],
        "factor_ids": sorted(item["factor_id"] for item in config["factors"]),
        "factor_weights": {
            item["factor_id"]: 1.0 for item in config["factors"]
        },
        "group_coverage_threshold": config["group_coverage_threshold"],
    }


def current_component_payloads() -> list[dict[str, Any]]:
    """Exact legacy/current versions; no highest-version guessing."""

    payloads: list[dict[str, Any]] = [
        {
            "component_type": "FACTOR_WEIGHT",
            "component_key": "factor-set-v1",
            "version_ref": "factor-weight:factor-set-v1@1.0.0",
            "payload": _weight_payload(),
        },
        {
            "component_type": "FACTOR_SET",
            "component_key": "factor-set-v1",
            "version_ref": "factor-set:factor-set-v1@1.0.0",
            "payload": _factor_set_payload(),
        },
        {
            "component_type": "REGIME_CONFIG",
            "component_key": "cn-market-regime",
            "version_ref": "regime:market-regime-v1",
            "payload": regime_config(),
        },
    ]
    payloads.extend(
        {
            "component_type": "STRATEGY_CONFIG",
            "component_key": item["strategy_id"],
            "version_ref": (
                f"strategy:{item['strategy_id']}@{item['strategy_version']}"
            ),
            "payload": item,
        }
        for item in strategy_configs()
    )
    return payloads


def build_current_component_record(
    descriptor: dict[str, Any],
    *,
    created_by: str,
    created_at: datetime | None = None,
) -> ComponentVersionRecord:
    created_at = created_at or datetime.utcnow()
    capability = component_capability(descriptor["component_type"])
    return ComponentVersionRecord(
        version_ref=descriptor["version_ref"],
        component_type=descriptor["component_type"],
        component_key=descriptor["component_key"],
        market="CN",
        payload=descriptor["payload"],
        payload_hash=experiment_hash(descriptor["payload"]),
        registration_supported=capability["registration_supported"],
        execution_supported=capability["execution_supported"],
        promotion_eligible=capability["promotion_eligible"],
        unsupported_reason=capability["reason"],
        source="CURRENT_CONFIG_IMPORT",
        parent_version_ref=None,
        created_by=created_by,
        created_at=created_at,
    )


_IGNORED_DIFF_KEYS = frozenset(
    {
        "factor_set_version",
        "regime_version",
        "strategy_version",
        "strategy_set_version",
        "schema_version",
        "status",
        "config_hash",
    }
)


def diff_leaf_paths(left: Any, right: Any, prefix: str = "") -> list[str]:
    if isinstance(left, dict) and isinstance(right, dict):
        paths: list[str] = []
        for key in sorted(set(left) | set(right)):
            if key in _IGNORED_DIFF_KEYS:
                continue
            child = f"{prefix}.{key}" if prefix else str(key)
            if key not in left or key not in right:
                paths.append(child)
            else:
                paths.extend(diff_leaf_paths(left[key], right[key], child))
        return paths
    if left != right:
        return [prefix or "$"]
    return []


def value_at_path(payload: dict[str, Any], path: str) -> Any:
    value: Any = payload
    for part in path.split("."):
        if isinstance(value, dict) and part in value:
            value = value[part]
        else:
            raise KeyError(path)
    return value


def _factor_results(
    data,
    payload: dict[str, Any],
    *,
    component_version_ref: str,
    calculated_at: datetime,
) -> tuple[list[FactorResult], float]:
    _, definitions, default_coverage = builtin_factor_definitions()
    selected = set(payload.get("factor_ids") or ())
    coverage = float(payload.get("group_coverage_threshold", default_coverage))
    results: list[FactorResult] = []
    for definition in definitions:
        if definition.factor_id not in selected:
            continue
        raw = _calculate(definition.factor_id, data, definition.parameters)
        score = (
            None
            if raw is None
            else _normalize(
                raw,
                definition.normalization_method,
                definition.parameters,
            )
        )
        input_hash = sha256_value(
            {
                "snapshot_input_hash": data.input_hash,
                "factor_id": definition.factor_id,
                "factor_version": definition.factor_version,
                "component_version_ref": component_version_ref,
            }
        )
        results.append(
            FactorResult(
                result_id=str(
                    uuid5(
                        NAMESPACE_URL,
                        "alphaguard:experiment-factor:"
                        f"{data.snapshot.snapshot_id}:{definition.factor_id}:"
                        f"{component_version_ref}:{input_hash}",
                    )
                ),
                snapshot_id=data.snapshot.snapshot_id,
                factor_id=definition.factor_id,
                factor_version=definition.factor_version,
                group=definition.group,
                symbol=data.snapshot.symbol,
                market=data.snapshot.market,
                trade_date=data.snapshot.trade_date,
                raw_value=raw,
                normalized_score=score,
                direction=(
                    "UNKNOWN"
                    if score is None
                    else _direction(score, definition.group)
                ),
                confidence=0.0 if score is None else 1.0,
                missing_reason=(
                    f"snapshot lacks required inputs: "
                    f"{', '.join(definition.required_inputs)}"
                    if score is None
                    else None
                ),
                input_refs=sorted(data.input_refs),
                input_hash=input_hash,
                code_hash=definition.code_hash,
                parameter_hash=definition.parameter_hash,
                calculated_at=calculated_at,
            )
        )
    return results, coverage


def _factor_bundle(
    data,
    payload: dict[str, Any],
    *,
    component_version_ref: str,
    calculated_at: datetime,
) -> FactorEvidenceBundle:
    results, coverage_threshold = _factor_results(
        data,
        payload,
        component_version_ref=component_version_ref,
        calculated_at=calculated_at,
    )
    weights = {
        str(key): float(value)
        for key, value in (payload.get("factor_weights") or {}).items()
    }
    _, all_definitions, _ = builtin_factor_definitions()
    selected = set(payload.get("factor_ids") or ())
    definition_groups = {
        group: [
            item.factor_id
            for item in all_definitions
            if item.group == group and item.factor_id in selected
        ]
        for group in ALL_GROUPS
    }
    by_id = {result.factor_id: result for result in results}
    details: dict[str, GroupAggregation] = {}
    group_scores: dict[str, float | None] = {}
    group_coverage: dict[str, float] = {}
    missing: list[str] = []
    for group, factor_ids in definition_groups.items():
        valid = [
            by_id[factor_id]
            for factor_id in factor_ids
            if factor_id in by_id and by_id[factor_id].normalized_score is not None
        ]
        missing_ids = [
            factor_id
            for factor_id in factor_ids
            if factor_id not in by_id
            or by_id[factor_id].normalized_score is None
        ]
        missing.extend(missing_ids)
        total = len(factor_ids)
        coverage = len(valid) / total if total else 0.0
        raw_weights = {
            item.factor_id: max(0.0, weights.get(item.factor_id, 1.0))
            for item in valid
        }
        weight_total = sum(raw_weights.values())
        normalized_weights = {
            factor_id: value / weight_total
            for factor_id, value in raw_weights.items()
        } if weight_total > 0 else {}
        score = (
            sum(
                float(item.normalized_score)
                * normalized_weights[item.factor_id]
                for item in valid
            )
            if valid
            and coverage >= coverage_threshold
            and normalized_weights
            else None
        )
        details[group] = GroupAggregation(
            valid_factor_count=len(valid),
            total_factor_count=total,
            coverage=coverage,
            factor_weights=normalized_weights,
            missing_factor_ids=missing_ids,
            score=score,
        )
        group_scores[group] = score
        group_coverage[group] = coverage
    risk_flags = []
    if (
        group_scores["VOLATILITY_RISK"] is not None
        and group_scores["VOLATILITY_RISK"] >= 75
    ):
        risk_flags.append("ELEVATED_VOLATILITY_RISK")
    if (
        group_scores["EVENT_RISK"] is not None
        and group_scores["EVENT_RISK"] >= 70
    ):
        risk_flags.append("BLOCKING_EVENT_RISK")
    input_hash = sha256_value(
        {
            "snapshot_input_hash": data.input_hash,
            "component_version_ref": component_version_ref,
            "payload_hash": experiment_hash(payload),
            "results": [item.input_hash for item in results],
        }
    )
    return FactorEvidenceBundle(
        snapshot_id=data.snapshot.snapshot_id,
        factor_set_version=component_version_ref,
        results=results,
        group_scores=group_scores,
        group_coverage=group_coverage,
        group_details=details,
        missing_factor_ids=sorted(set(missing)),
        risk_flags=risk_flags,
        input_hash=input_hash,
        calculated_at=calculated_at,
    )


def strategy_definition_from_payload(
    payload: dict[str, Any],
    *,
    version_ref: str,
    created_at: datetime,
) -> StrategyDefinition:
    parameters = payload["parameters"]
    return StrategyDefinition(
        strategy_id=payload["strategy_id"],
        strategy_version=version_ref,
        name=payload["name"],
        description=payload["description"],
        status="CHAMPION",
        supported_markets=payload["supported_markets"],
        allowed_regimes=payload["allowed_regimes"],
        factor_dependencies=payload["factor_dependencies"],
        required_group_scores=payload["required_group_scores"],
        parameters=parameters,
        code_hash=sha256_value(
            {
                "engine": STRATEGY_ENGINE_CODE_VERSION,
                "strategy_id": payload["strategy_id"],
            }
        ),
        parameter_hash=sha256_value(parameters),
        parent_version=None,
        created_at=created_at,
        promoted_at=created_at,
    )


def _baseline_factor_payload() -> dict[str, Any]:
    return _factor_set_payload()


class DeterministicExperimentAdapter:
    """Run the four PR-008 deterministic component types without persistence."""

    def run(
        self,
        data,
        component: ComponentVersionRecord,
    ) -> dict[str, Any]:
        if component.component_type not in EXECUTABLE_COMPONENTS:
            raise ValueError("UNSUPPORTED_COMPONENT_ADAPTER")
        calculated_at = data.snapshot.price_cutoff_at
        factor_payload = _baseline_factor_payload()
        factor_version_ref = "factor-set:factor-set-v1@1.0.0"
        regime_payload = regime_config()
        regime_version_ref = "regime:market-regime-v1"
        strategy_payloads = strategy_configs()
        strategy_version_refs = {
            item["strategy_id"]: (
                f"strategy:{item['strategy_id']}@{item['strategy_version']}"
            )
            for item in strategy_payloads
        }
        if component.component_type in {"FACTOR_WEIGHT", "FACTOR_SET"}:
            factor_payload = component.payload
            factor_version_ref = component.version_ref
        elif component.component_type == "REGIME_CONFIG":
            regime_payload = {
                **component.payload,
                "regime_version": component.version_ref,
            }
            regime_version_ref = component.version_ref
        elif component.component_type == "STRATEGY_CONFIG":
            strategy_payloads = [
                component.payload
                if item["strategy_id"] == component.component_key
                else item
                for item in strategy_payloads
            ]
            strategy_version_refs[component.component_key] = component.version_ref

        bundle = _factor_bundle(
            data,
            factor_payload,
            component_version_ref=factor_version_ref,
            calculated_at=calculated_at,
        )
        regime_payload = {**regime_payload, "regime_version": regime_version_ref}
        regime = calculate_regime_result(
            data,
            config=regime_payload,
            calculated_at=calculated_at,
        )
        engine = StrategyEngine()
        proposals = []
        for payload in sorted(strategy_payloads, key=lambda item: item["strategy_id"]):
            definition = strategy_definition_from_payload(
                payload,
                version_ref=strategy_version_refs[payload["strategy_id"]],
                created_at=calculated_at,
            )
            proposals.append(
                engine.evaluate(definition, data, bundle, regime).model_dump(
                    mode="json"
                )
            )
        output = {
            "snapshot_id": data.snapshot.snapshot_id,
            "component_type": component.component_type,
            "component_key": component.component_key,
            "component_version_ref": component.version_ref,
            "factor_bundle": bundle.model_dump(mode="json"),
            "market_regime": regime.model_dump(mode="json"),
            "quant_proposals": proposals,
            "production_writes": False,
        }
        return {**output, "output_hash": experiment_hash(output)}

    def run_pair(
        self,
        data,
        baseline: ComponentVersionRecord,
        challenger: ComponentVersionRecord,
    ) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
        if (
            baseline.component_type != challenger.component_type
            or baseline.component_key != challenger.component_key
            or baseline.market != challenger.market
        ):
            raise ValueError("experiment component identity mismatch")
        champion_output = self.run(data, baseline)
        challenger_output = self.run(data, challenger)
        difference = {
            "component_paths": diff_leaf_paths(
                baseline.payload, challenger.payload
            ),
            "champion_output_hash": champion_output["output_hash"],
            "challenger_output_hash": challenger_output["output_hash"],
            "outputs_equal": (
                champion_output["output_hash"]
                == challenger_output["output_hash"]
            ),
        }
        return champion_output, challenger_output, difference
