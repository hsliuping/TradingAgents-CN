"""
Utility helpers for EnhancedScreeningService to separate analysis and conversion logic.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from app.models.screening import ScreeningCondition, FieldType, BASIC_FIELDS_INFO


def analyze_conditions(conditions: List[ScreeningCondition]) -> Dict[str, Any]:
    analysis = {
        "total_conditions": len(conditions),
        "database_supported_conditions": 0,
        "technical_conditions": 0,
        "fundamental_conditions": 0,
        "basic_conditions": 0,
        "can_use_database": True,
        "needs_technical_indicators": False,
        "unsupported_fields": [],
        "condition_types": [],
    }

    for condition in conditions:
        field = condition.field

        if field in BASIC_FIELDS_INFO:
            field_info = BASIC_FIELDS_INFO[field]
            field_type = field_info.field_type

            if field_type == FieldType.BASIC:
                analysis["basic_conditions"] += 1
            elif field_type == FieldType.FUNDAMENTAL:
                analysis["fundamental_conditions"] += 1
            elif field_type == FieldType.TECHNICAL:
                analysis["technical_conditions"] += 1

            analysis["condition_types"].append(field_type.value)

            if field in set(BASIC_FIELDS_INFO.keys()):
                analysis["database_supported_conditions"] += 1
            else:
                analysis["can_use_database"] = False
                analysis["unsupported_fields"].append(field)
        else:
            analysis["can_use_database"] = False
            analysis["needs_technical_indicators"] = True
            analysis["unsupported_fields"].append(field)

    if analysis["technical_conditions"] > 0 or analysis["needs_technical_indicators"]:
        analysis["needs_technical_indicators"] = True

    return analysis


def convert_conditions_to_traditional_format(conditions: List[ScreeningCondition]) -> Dict[str, Any]:
    traditional_conditions: Dict[str, Any] = {}

    for condition in conditions:
        field = condition.field
        operator = condition.operator
        value = condition.value

        if operator == "between" and isinstance(value, list) and len(value) == 2:
            traditional_conditions[field] = {"min": value[0], "max": value[1]}
        elif operator in [">", "<", ">=", "<="]:
            traditional_conditions[field] = {operator: value}
        elif operator == "==":
            traditional_conditions[field] = value
        elif operator in ["in", "not_in"]:
            traditional_conditions[field] = {operator: value}
        else:
            traditional_conditions[field] = {operator: value}

    return traditional_conditions

