"""Versioned, non-trading configuration for historical research backfill."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from tradingagents.alphaguard.backfill_schemas import backfill_hash


POLICY_PATH = (
    Path(__file__).resolve().parents[3]
    / "config"
    / "alphaguard"
    / "research"
    / "backfill_policy_v1.yaml"
)


def backfill_policy() -> dict[str, Any]:
    payload = yaml.safe_load(POLICY_PATH.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("historical backfill policy must be a mapping")
    payload["config_hash"] = backfill_hash(payload)
    return payload
