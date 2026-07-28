"""Load immutable production-data policies without inventing defaults."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

from tradingagents.alphaguard.production_data_schemas import production_data_hash


ROOT = Path(__file__).resolve().parents[3]
DATA_CONFIG_ROOT = ROOT / "config" / "alphaguard" / "data"


def _load(name: str) -> dict[str, Any]:
    path = DATA_CONFIG_ROOT / name
    with path.open("r", encoding="utf-8") as handle:
        value = yaml.safe_load(handle)
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain a mapping")
    return value


@lru_cache(maxsize=1)
def production_market_context_policy() -> dict[str, Any]:
    value = _load("market_context_policy_v1.yaml")
    required = {
        "policy_id",
        "policy_version",
        "market",
        "provider",
        "normalization_version",
        "calculation_version",
        "required_benchmark_sessions",
        "sector_index_codes",
    }
    missing = sorted(required - set(value))
    if missing:
        raise ValueError(f"production MarketContext policy lacks {missing}")
    result = dict(value)
    result["immutable_hash"] = production_data_hash(value)
    return result


@lru_cache(maxsize=1)
def cn_price_limit_policy() -> dict[str, Any]:
    value = _load("cn_price_limit_rules_v1.yaml")
    required = {
        "policy_id",
        "policy_version",
        "calculation_version",
        "market",
        "tick_size",
        "lot_size",
        "boards",
    }
    missing = sorted(required - set(value))
    if missing:
        raise ValueError(f"CN price-limit policy lacks {missing}")
    result = dict(value)
    result["immutable_hash"] = production_data_hash(value)
    return result


@lru_cache(maxsize=1)
def daily_price_provider_policy() -> dict[str, Any]:
    value = _load("daily_price_provider_policy_v1.yaml")
    required = {
        "policy_id",
        "policy_version",
        "market",
        "normalization_version",
        "market_close_time",
        "price_quantum",
        "amount_quantum_cny",
        "provider_priority",
        "raw_cross_validation",
        "qfq_cross_validation",
        "volume_normalization",
        "amount_normalization",
    }
    missing = sorted(required - set(value))
    if missing:
        raise ValueError(f"daily-price provider policy lacks {missing}")
    result = dict(value)
    result["immutable_hash"] = production_data_hash(value)
    return result
