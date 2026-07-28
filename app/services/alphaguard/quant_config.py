"""Versioned configuration loading and canonical hashing for PR-004."""

from __future__ import annotations

import hashlib
import json
from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from pathlib import Path
from typing import Any

import yaml
from bson import Decimal128
from pydantic import BaseModel


PROJECT_ROOT = Path(__file__).resolve().parents[3]
CONFIG_ROOT = PROJECT_ROOT / "config" / "alphaguard"
FACTOR_CONFIG = CONFIG_ROOT / "factors" / "factor_set_v1.yaml"
REGIME_CONFIG = CONFIG_ROOT / "regimes" / "market_regime_v1.yaml"
STRATEGY_CONFIGS = (
    CONFIG_ROOT / "strategies" / "swing_trend_pullback_v1.yaml",
    CONFIG_ROOT / "strategies" / "position_exit_v1.yaml",
)
FACTOR_ENGINE_CODE_VERSION = "factor-engine-v1"
REGIME_ENGINE_CODE_VERSION = "market-regime-engine-v1"
STRATEGY_ENGINE_CODE_VERSION = "strategy-engine-v1"


def canonical_value(value: Any) -> Any:
    if isinstance(value, BaseModel):
        return canonical_value(value.model_dump(mode="python"))
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, Decimal128):
        return format(value.to_decimal(), "f")
    if isinstance(value, Decimal):
        return format(value, "f")
    if isinstance(value, dict):
        return {
            str(key): canonical_value(item)
            for key, item in sorted(value.items(), key=lambda pair: str(pair[0]))
            if key != "_id"
        }
    if isinstance(value, (list, tuple)):
        return [canonical_value(item) for item in value]
    return value


def canonical_json(value: Any) -> str:
    return json.dumps(
        canonical_value(value),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )


def sha256_value(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def load_yaml(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as stream:
        value = yaml.safe_load(stream)
    if not isinstance(value, dict):
        raise ValueError(f"invalid AlphaGuard config: {path}")
    return value


def factor_config() -> dict[str, Any]:
    return load_yaml(FACTOR_CONFIG)


def regime_config() -> dict[str, Any]:
    return load_yaml(REGIME_CONFIG)


def strategy_configs() -> list[dict[str, Any]]:
    return [load_yaml(path) for path in STRATEGY_CONFIGS]
