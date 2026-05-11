from __future__ import annotations

from collections.abc import Mapping
from typing import Any


METRIC_DISPLAY_VARIANTS = {
    "pe": {
        "default": ("pe", "PE"),
        "variants": (("pe_ttm", "PE(TTM)"), ("pe", "PE")),
    },
    "pb": {
        "default": ("pb", "PB"),
        "variants": (("pb_mrq", "PB(MRQ)"), ("pb", "PB")),
    },
}


def select_metric_display_spec(
    raw_conditions: list[dict[str, Any]] | None,
    order_by_field: str | None,
    metric_key: str,
) -> tuple[str, str]:
    config = METRIC_DISPLAY_VARIANTS[metric_key]
    variant_labels = {field: label for field, label in config["variants"]}

    for condition in raw_conditions or []:
        if not isinstance(condition, Mapping):
            continue
        field = condition.get("field")
        if field in variant_labels:
            return field, variant_labels[field]

    if order_by_field in variant_labels:
        return order_by_field, variant_labels[order_by_field]

    return config["default"]


def resolve_metric_value(item: Mapping[str, Any], selected_field: str, metric_key: str) -> Any:
    config = METRIC_DISPLAY_VARIANTS[metric_key]
    fields = [selected_field]
    fields.extend(field for field, _label in config["variants"] if field != selected_field)

    for field in fields:
        value = item.get(field)
        if value is not None:
            return value

    return None