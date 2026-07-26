"""Versioned PR-008 policy loading."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

from tradingagents.alphaguard.experiment_schemas import PromotionPolicy, experiment_hash


EXPERIMENT_CONFIG_ROOT = (
    Path(__file__).resolve().parents[3] / "config" / "alphaguard" / "experiments"
)


def _load(name: str) -> dict[str, Any]:
    path = EXPERIMENT_CONFIG_ROOT / name
    payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"invalid experiment policy: {path}")
    return payload


@lru_cache(maxsize=1)
def promotion_policy() -> PromotionPolicy:
    payload = _load("promotion_policy_v1.yaml")
    immutable_hash = experiment_hash(payload)
    return PromotionPolicy.model_validate(
        {
            **payload,
            "created_at": "2026-07-26T00:00:00",
            "immutable_hash": immutable_hash,
        }
    )


@lru_cache(maxsize=1)
def robustness_policy() -> dict[str, Any]:
    payload = _load("robustness_suite_v1.yaml")
    return {**payload, "immutable_hash": experiment_hash(payload)}


@lru_cache(maxsize=1)
def replay_policy() -> dict[str, Any]:
    payload = _load("replay_policy_v1.yaml")
    return {**payload, "immutable_hash": experiment_hash(payload)}
