"""Versioned, read-only PR-007 evaluation and attribution policies."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, ConfigDict, Field

from tradingagents.alphaguard.evaluation_schemas import evaluation_hash


POLICY_ROOT = (
    Path(__file__).resolve().parents[3] / "config" / "alphaguard" / "evaluation"
)


class EvaluationPolicy(BaseModel):
    model_config = ConfigDict(extra="forbid")
    evaluation_policy_id: str
    version: str
    horizons: dict[str, int]
    primary_attribution_horizon: str
    benchmark_symbol: str
    required_price_adjustment_mode: str
    normalized_shadow_notional: str
    cross_section_min_samples: int = Field(ge=2)
    paired_min_samples: int = Field(ge=2)
    evaluation_version: str
    label_calculation_version: str
    counterfactual_version: str
    account_metric_version: str
    comparison_version: str
    config_hash: str


class AttributionRuleConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")
    attribution_rule_id: str
    version: str
    primary_horizon: str
    thresholds: dict[str, str]
    rules: list[dict[str, str]]
    config_hash: str


def _load(path: Path) -> dict[str, Any]:
    payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"invalid evaluation policy: {path}")
    payload["config_hash"] = evaluation_hash(payload)
    return payload


@lru_cache(maxsize=1)
def evaluation_policy() -> EvaluationPolicy:
    policy = EvaluationPolicy.model_validate(
        _load(POLICY_ROOT / "evaluation_policy_v1.yaml")
    )
    if policy.horizons != {"1D": 1, "5D": 5, "10D": 10, "20D": 20}:
        raise ValueError("evaluation horizon contract changed unexpectedly")
    return policy


@lru_cache(maxsize=1)
def attribution_policy() -> AttributionRuleConfig:
    return AttributionRuleConfig.model_validate(
        _load(POLICY_ROOT / "attribution_rules_v1.yaml")
    )
