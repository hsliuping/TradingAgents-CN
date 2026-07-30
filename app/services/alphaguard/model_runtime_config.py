"""Immutable file definitions for the PR-010 runtime registries."""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

from app.schemas.alphaguard.decision import canonical_hash
from app.schemas.alphaguard.model_runtime import (
    ModelBudgetPolicy,
    ModelProfile,
    PromptProfile,
)


ROOT = Path(__file__).resolve().parents[3]
DEFAULT_CONFIG_PATH = (
    ROOT / "config" / "alphaguard" / "models" / "model_runtime_v2.yaml"
)


def _timestamp(value: Any) -> datetime:
    if isinstance(value, datetime):
        return value
    return datetime.fromisoformat(str(value).replace("Z", "+00:00"))


@lru_cache(maxsize=4)
def load_model_runtime_config(
    path: str | Path = DEFAULT_CONFIG_PATH,
) -> dict[str, Any]:
    source = Path(path)
    raw = yaml.safe_load(source.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError("model runtime configuration must be a mapping")
    created_at = _timestamp(raw["created_at"])

    prompts: list[PromptProfile] = []
    for item in raw.get("prompts", []):
        payload = deepcopy(item)
        payload["created_at"] = created_at
        payload["template_hash"] = canonical_hash(payload["template"])
        prompts.append(PromptProfile.model_validate(payload))

    profiles: list[ModelProfile] = []
    for item in raw.get("profiles", []):
        payload = deepcopy(item)
        payload["created_at"] = created_at
        payload["capability_status"] = (
            "UNVERIFIED" if payload.get("enabled") else "DISABLED"
        )
        payload["config_hash"] = canonical_hash(
            payload,
            exclude={"config_hash", "created_at"},
        )
        profiles.append(ModelProfile.model_validate(payload))

    budget_payload = deepcopy(raw["budget_policy"])
    budget_payload["created_at"] = created_at
    budget_payload["policy_hash"] = canonical_hash(
        budget_payload,
        exclude={"policy_hash", "created_at"},
    )
    budget = ModelBudgetPolicy.model_validate(budget_payload)

    prompt_ids = {item.prompt_id for item in prompts if item.enabled}
    for profile in profiles:
        if profile.enabled and profile.prompt_profile_id not in prompt_ids:
            raise ValueError(
                f"enabled profile references missing prompt: "
                f"{profile.prompt_profile_id}"
            )
    role_counts = {
        role: sum(1 for item in profiles if item.enabled and item.role == role)
        for role in ("NORMAL_TRADER", "TOP_RISK_REVIEWER")
    }
    if role_counts != {"NORMAL_TRADER": 1, "TOP_RISK_REVIEWER": 1}:
        raise ValueError(
            "runtime must bind exactly one enabled Normal and one enabled Top profile"
        )
    return {
        "runtime_version": str(raw["runtime_version"]),
        "profiles": tuple(profiles),
        "prompts": tuple(prompts),
        "budget_policy": budget,
    }


def clear_model_runtime_config_cache() -> None:
    load_model_runtime_config.cache_clear()
