"""
DashScope endpoint mode helpers.

Keep the legacy compatible endpoint and the Qwen Coding Plan endpoint
under the same provider identity.
"""

from __future__ import annotations

from typing import Any, Dict, Optional


DASHSCOPE_ENDPOINT_MODE_COMPATIBLE = "compatible"
DASHSCOPE_ENDPOINT_MODE_CODING_PLAN = "coding_plan"

DASHSCOPE_COMPATIBLE_BASE_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1"
DASHSCOPE_CODING_BASE_URL = "https://coding.dashscope.aliyuncs.com/v1"

DASHSCOPE_ENDPOINT_MODES = [
    DASHSCOPE_ENDPOINT_MODE_COMPATIBLE,
    DASHSCOPE_ENDPOINT_MODE_CODING_PLAN,
]

DASHSCOPE_BASE_URL_MAP = {
    DASHSCOPE_ENDPOINT_MODE_COMPATIBLE: DASHSCOPE_COMPATIBLE_BASE_URL,
    DASHSCOPE_ENDPOINT_MODE_CODING_PLAN: DASHSCOPE_CODING_BASE_URL,
}

DASHSCOPE_MODELS_BY_MODE = {
    DASHSCOPE_ENDPOINT_MODE_COMPATIBLE: [
        "qwen-turbo",
        "qwen-plus",
        "qwen-plus-latest",
        "qwen-max",
        "qwen-max-latest",
        "qwen-max-longcontext",
    ],
    DASHSCOPE_ENDPOINT_MODE_CODING_PLAN: [
        "qwen3.5-plus",
        "qwen3-max-2026-01-23",
        "qwen3-coder-next",
        "qwen3-coder-plus",
    ],
}

DASHSCOPE_DEFAULT_MODELS = {
    DASHSCOPE_ENDPOINT_MODE_COMPATIBLE: {
        "quick": "qwen-turbo",
        "deep": "qwen-max",
    },
    DASHSCOPE_ENDPOINT_MODE_CODING_PLAN: {
        "quick": "qwen3.5-plus",
        "deep": "qwen3-max-2026-01-23",
    },
}


def normalize_dashscope_base_url(base_url: Optional[str]) -> str:
    """Normalize any DashScope-like base URL to one of the canonical URLs."""
    if not base_url:
        return DASHSCOPE_COMPATIBLE_BASE_URL

    normalized = base_url.rstrip("/")
    if "coding.dashscope.aliyuncs.com" in normalized:
        return DASHSCOPE_CODING_BASE_URL
    if "dashscope.aliyuncs.com" in normalized:
        return DASHSCOPE_COMPATIBLE_BASE_URL
    return normalized


def get_dashscope_mode_from_base_url(base_url: Optional[str]) -> str:
    """Infer endpoint mode from a base URL."""
    normalized = normalize_dashscope_base_url(base_url)
    if "coding.dashscope.aliyuncs.com" in normalized:
        return DASHSCOPE_ENDPOINT_MODE_CODING_PLAN
    return DASHSCOPE_ENDPOINT_MODE_COMPATIBLE


def get_dashscope_base_url_for_mode(mode: Optional[str] = None) -> str:
    """Return the canonical base URL for a mode."""
    normalized_mode = mode or DASHSCOPE_ENDPOINT_MODE_COMPATIBLE
    if normalized_mode not in DASHSCOPE_BASE_URL_MAP:
        normalized_mode = DASHSCOPE_ENDPOINT_MODE_COMPATIBLE
    return DASHSCOPE_BASE_URL_MAP[normalized_mode]


def get_dashscope_mode_from_model(model_name: Optional[str], base_url: Optional[str] = None) -> str:
    """Infer endpoint mode from model name first, then base URL."""
    if model_name:
        for mode, models in DASHSCOPE_MODELS_BY_MODE.items():
            if model_name in models:
                return mode
    return get_dashscope_mode_from_base_url(base_url)


def get_dashscope_default_model(mode: Optional[str] = None) -> str:
    """Return the default quick model for a mode."""
    normalized_mode = mode or DASHSCOPE_ENDPOINT_MODE_COMPATIBLE
    if normalized_mode not in DASHSCOPE_DEFAULT_MODELS:
        normalized_mode = DASHSCOPE_ENDPOINT_MODE_COMPATIBLE
    return DASHSCOPE_DEFAULT_MODELS[normalized_mode]["quick"]


def get_dashscope_default_deep_model(mode: Optional[str] = None) -> str:
    """Return the default deep model for a mode."""
    normalized_mode = mode or DASHSCOPE_ENDPOINT_MODE_COMPATIBLE
    if normalized_mode not in DASHSCOPE_DEFAULT_MODELS:
        normalized_mode = DASHSCOPE_ENDPOINT_MODE_COMPATIBLE
    return DASHSCOPE_DEFAULT_MODELS[normalized_mode]["deep"]


def get_dashscope_base_url_for_model(model_name: Optional[str], base_url: Optional[str] = None) -> str:
    """Return canonical base URL for a model, optionally using existing URL as hint."""
    mode = get_dashscope_mode_from_model(model_name, base_url)
    return get_dashscope_base_url_for_mode(mode)


def build_dashscope_extra_config(
    endpoint_mode: Optional[str] = None,
    existing: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Merge DashScope endpoint metadata into provider extra_config."""
    merged = dict(existing or {})
    mode = endpoint_mode or get_dashscope_mode_from_base_url(merged.get("default_base_url"))
    if mode not in DASHSCOPE_ENDPOINT_MODES:
        mode = DASHSCOPE_ENDPOINT_MODE_COMPATIBLE

    merged["endpoint_mode"] = mode
    merged["endpoint_modes"] = list(DASHSCOPE_ENDPOINT_MODES)
    merged["base_url_map"] = dict(DASHSCOPE_BASE_URL_MAP)
    return merged
