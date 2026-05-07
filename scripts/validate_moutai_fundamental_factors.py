from __future__ import annotations

import asyncio
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.core.database import init_database
from app.models.screening import BASIC_FIELDS_INFO
from app.services.database_screening_service import get_database_screening_service
from core.skill_runtime.factor_schema import (
    P0_GROWTH_CASHFLOW_FIELDS,
    P0_FACTOR_FIELD_SCHEMA,
    P0_PUBLIC_SCREENING_FIELDS,
    P0_QUALITY_FIELDS,
    P0_SNAPSHOT_ONLY_FIELDS,
    P0_VALUE_FIELDS,
)
from core.skill_runtime.factor_catalog import (
    P0_BUNDLE_FACTOR_PACKS,
    validate_factor_catalog_schema_alignment,
    validate_factor_catalog_runtime_semantic_alignment,
    validate_factor_schema_semantic_alignment,
    validate_factor_catalog_source_alignment,
    validate_factor_pack_schema_alignment,
)
from core.skill_runtime.fundamental_factors import (
    get_fundamental_factor_snapshot,
    get_growth_cashflow_factor_bundle,
    get_quality_factor_bundle,
    get_value_factor_bundle,
)


SYMBOL = "600519"

VALUE_FIELDS = list(P0_VALUE_FIELDS)
SNAPSHOT_ONLY_FIELDS = list(P0_SNAPSHOT_ONLY_FIELDS)
QUALITY_FIELDS = list(P0_QUALITY_FIELDS)
GROWTH_FIELDS = list(P0_GROWTH_CASHFLOW_FIELDS)
PUBLIC_SCREENING_FIELDS = list(P0_PUBLIC_SCREENING_FIELDS)
CAUTIOUS_FIELDS = sorted(
    field_name
    for field_name, schema in P0_FACTOR_FIELD_SCHEMA.items()
    if schema.data_quality_tier == "cautious"
)


def _metadata_alignment_check() -> List[Dict[str, object]]:
    mismatches: List[Dict[str, object]] = []
    for field in PUBLIC_SCREENING_FIELDS:
        schema = P0_FACTOR_FIELD_SCHEMA.get(field)
        metadata = BASIC_FIELDS_INFO.get(field)
        if schema is None or metadata is None:
            continue

        field_mismatches: Dict[str, object] = {}
        if metadata.display_name != schema.display_name:
            field_mismatches["display_name"] = {
                "expected": schema.display_name,
                "actual": metadata.display_name,
            }
        if metadata.data_type != schema.data_type:
            field_mismatches["data_type"] = {
                "expected": schema.data_type,
                "actual": metadata.data_type,
            }
        expected_unit = schema.screening_unit or schema.unit
        if (metadata.unit or "") != expected_unit:
            field_mismatches["unit"] = {
                "expected": expected_unit,
                "actual": metadata.unit or "",
            }
        if metadata.field_type.value != "fundamental":
            field_mismatches["field_type"] = {
                "expected": "fundamental",
                "actual": metadata.field_type.value,
            }

        if field_mismatches:
            mismatches.append({"field": field, "mismatches": field_mismatches})

    return mismatches


def _bundle_check(bundle_name: str, bundle: Dict[str, object], expected_fields: List[str]) -> Dict[str, object]:
    factors = bundle.get("factors", {}) or {}
    present_fields = [field for field in expected_fields if field in factors]
    missing_fields = [field for field in expected_fields if field not in factors]
    non_null_fields = [field for field in expected_fields if factors.get(field) is not None]
    return {
        "bundle": bundle_name,
        "expected_count": len(expected_fields),
        "present_count": len(present_fields),
        "non_null_count": len(non_null_fields),
        "missing_fields": missing_fields,
        "null_fields": [field for field in expected_fields if field in factors and factors.get(field) is None],
        "factors": {field: factors.get(field) for field in expected_fields},
    }


async def _screening_check(symbol: str) -> Dict[str, object]:
    await init_database()
    service = get_database_screening_service()
    items, total = await service.screen_stocks(
        conditions=[{"field": "code", "operator": "==", "value": symbol}],
        limit=1,
        offset=0,
        order_by=None,
    )
    item = items[0] if items else {}
    factor_diagnostics = item.get("factor_diagnostics", {}) or {}
    factor_warnings = item.get("factor_warnings", {}) or {}
    present_fields = [field for field in PUBLIC_SCREENING_FIELDS if field in item]
    missing_cautious_diagnostics = [
        field_name
        for field_name in CAUTIOUS_FIELDS
        if item.get(field_name) is None and not factor_diagnostics.get(field_name)
    ]
    return {
        "total": total,
        "item_found": bool(item),
        "present_count": len(present_fields),
        "non_null_count": len([field for field in PUBLIC_SCREENING_FIELDS if item.get(field) is not None]),
        "missing_fields": [field for field in PUBLIC_SCREENING_FIELDS if field not in item],
        "null_fields": [field for field in PUBLIC_SCREENING_FIELDS if field in item and item.get(field) is None],
        "missing_cautious_diagnostics": missing_cautious_diagnostics,
        "factor_diagnostics": factor_diagnostics,
        "factor_warnings": factor_warnings,
        "sample_values": {field: item.get(field) for field in PUBLIC_SCREENING_FIELDS},
    }


async def main() -> int:
    value_bundle = get_value_factor_bundle(SYMBOL)
    quality_bundle = get_quality_factor_bundle(SYMBOL)
    growth_bundle = get_growth_cashflow_factor_bundle(SYMBOL)
    snapshot = get_fundamental_factor_snapshot(SYMBOL)

    bundle_results = {
        "value_core": _bundle_check("value_core", value_bundle, VALUE_FIELDS),
        "quality_core": _bundle_check("quality_core", quality_bundle, QUALITY_FIELDS),
        "growth_cashflow_core": _bundle_check("growth_cashflow_core", growth_bundle, GROWTH_FIELDS),
    }

    snapshot_factors = snapshot.get("factors", {}) or {}
    factor_diagnostics = snapshot.get("factor_diagnostics", {}) or {}
    factor_warnings = snapshot.get("factor_warnings", {}) or {}
    snapshot_missing = [field for field in PUBLIC_SCREENING_FIELDS if field not in snapshot_factors]
    metadata_missing = [field for field in PUBLIC_SCREENING_FIELDS if field not in BASIC_FIELDS_INFO]
    metadata_mismatches = _metadata_alignment_check()
    catalog_alignment = validate_factor_catalog_schema_alignment()
    catalog_runtime_semantic_alignment = validate_factor_catalog_runtime_semantic_alignment()
    schema_semantic_alignment = validate_factor_schema_semantic_alignment()
    catalog_source_alignment = validate_factor_catalog_source_alignment()
    factor_pack_alignment = validate_factor_pack_schema_alignment()
    screening_result = await _screening_check(SYMBOL)

    structural_failures: List[str] = []
    for bundle_name, bundle_result in bundle_results.items():
        if bundle_result["missing_fields"]:
            structural_failures.append(f"{bundle_name} 缺少字段: {', '.join(bundle_result['missing_fields'])}")
    if snapshot_missing:
        structural_failures.append(f"snapshot 缺少字段: {', '.join(snapshot_missing)}")
    if metadata_missing:
        structural_failures.append(f"BASIC_FIELDS_INFO 缺少字段: {', '.join(metadata_missing)}")
    if metadata_mismatches:
        structural_failures.append(
            "BASIC_FIELDS_INFO 与 factor_schema 不一致: "
            + ", ".join(item["field"] for item in metadata_mismatches)
        )
    if catalog_alignment.get("mismatches"):
        structural_failures.append(
            "factor_catalog 与 factor_schema 不一致: "
            + ", ".join(item["field"] for item in catalog_alignment["mismatches"])
        )
    if catalog_alignment.get("missing_catalog_entries"):
        structural_failures.append(
            "factor_catalog 缺少 P0 字段登记: "
            + ", ".join(item["field"] for item in catalog_alignment["missing_catalog_entries"])
        )
    if catalog_alignment.get("missing_cautious_catalog_entries"):
        structural_failures.append(
            "factor_catalog 缺少 cautious 字段登记: "
            + ", ".join(item["field"] for item in catalog_alignment["missing_cautious_catalog_entries"])
        )
    if catalog_source_alignment.get("legacy_source_refs"):
        structural_failures.append(
            "factor_catalog 仍引用旧财务口径: "
            + ", ".join(item["field"] for item in catalog_source_alignment["legacy_source_refs"])
        )
    if catalog_runtime_semantic_alignment.get("mismatches"):
        structural_failures.append(
            "factor_catalog 的 fallback_rules/warnings 与 runtime 语义约束不一致: "
            + ", ".join(item["field"] for item in catalog_runtime_semantic_alignment["mismatches"])
        )
    if catalog_runtime_semantic_alignment.get("missing_contract_entries"):
        structural_failures.append(
            "factor_catalog 缺少 P0 字段的 runtime semantic contract 登记: "
            + ", ".join(item["field"] for item in catalog_runtime_semantic_alignment["missing_contract_entries"])
        )
    if schema_semantic_alignment.get("missing_schema_fields"):
        structural_failures.append(
            "factor_schema 缺少 runtime semantic contract 对应字段: "
            + ", ".join(item["field"] for item in schema_semantic_alignment["missing_schema_fields"])
        )
    if schema_semantic_alignment.get("missing_source_priority_entries"):
        structural_failures.append(
            "factor_schema 或 runtime semantic contract 缺少 source_priority 覆盖: "
            + ", ".join(item["field"] for item in schema_semantic_alignment["missing_source_priority_entries"])
        )
    if schema_semantic_alignment.get("missing_minimum_input_group_entries"):
        structural_failures.append(
            "factor_schema 或 runtime semantic contract 缺少 minimum_input_groups 覆盖: "
            + ", ".join(item["field"] for item in schema_semantic_alignment["missing_minimum_input_group_entries"])
        )
    if schema_semantic_alignment.get("missing_minimum_computable_condition_entries"):
        structural_failures.append(
            "factor_schema 或 runtime semantic contract 缺少 minimum_computable_conditions 覆盖: "
            + ", ".join(item["field"] for item in schema_semantic_alignment["missing_minimum_computable_condition_entries"])
        )
    if schema_semantic_alignment.get("missing_warning_condition_entries"):
        structural_failures.append(
            "factor_schema 或 runtime semantic contract 缺少 warning_conditions 覆盖: "
            + ", ".join(item["field"] for item in schema_semantic_alignment["missing_warning_condition_entries"])
        )
    if schema_semantic_alignment.get("missing_warning_category_entries"):
        structural_failures.append(
            "factor_schema 或 runtime semantic contract 缺少 warning_categories 覆盖: "
            + ", ".join(item["field"] for item in schema_semantic_alignment["missing_warning_category_entries"])
        )
    if schema_semantic_alignment.get("mismatches"):
        structural_failures.append(
            "factor_schema 的 calculation_mode/semantic_tags/warning_categories 与 runtime semantic contract 不一致: "
            + ", ".join(item["field"] for item in schema_semantic_alignment["mismatches"])
        )
    if factor_pack_alignment.get("mismatches"):
        structural_failures.append(
            "RECOMMENDED_FACTOR_PACKS 与 P0 bundle 不一致: "
            + ", ".join(item["pack_id"] for item in factor_pack_alignment["mismatches"])
        )
    missing_cautious_diagnostics = [
        field_name
        for field_name in CAUTIOUS_FIELDS
        if snapshot_factors.get(field_name) is None and not factor_diagnostics.get(field_name)
    ]
    if missing_cautious_diagnostics:
        structural_failures.append(
            "snapshot 缺少 cautious 字段的结构化诊断信息: " + ", ".join(missing_cautious_diagnostics)
        )
    if not screening_result["item_found"]:
        structural_failures.append("screen_stocks 未返回 600519")
    if screening_result.get("missing_cautious_diagnostics"):
        structural_failures.append(
            "screening 缺少 cautious 字段的结构化诊断信息: "
            + ", ".join(screening_result["missing_cautious_diagnostics"])
        )
    missing_screening_warnings = sorted(
        field_name
        for field_name in factor_warnings
        if field_name not in (screening_result.get("factor_warnings") or {})
    )
    if missing_screening_warnings:
        structural_failures.append(
            "screening 缺少 snapshot 已命中的结构化 warning: " + ", ".join(missing_screening_warnings)
        )

    report = {
        "timestamp": datetime.now().isoformat(),
        "symbol": SYMBOL,
        "name": snapshot.get("name"),
        "industry": snapshot.get("industry"),
        "report_period": snapshot.get("report_period"),
        "bundle_results": bundle_results,
        "snapshot": {
            "factor_count": len(snapshot_factors),
            "missing_fields": snapshot_missing,
            "non_null_count": len([field for field in PUBLIC_SCREENING_FIELDS if snapshot_factors.get(field) is not None]),
            "cautious_fields": CAUTIOUS_FIELDS,
            "sample_values": {field: snapshot_factors.get(field) for field in PUBLIC_SCREENING_FIELDS},
            "missing_factors_reported": snapshot.get("missing_factors", []),
            "factor_diagnostics": factor_diagnostics,
            "factor_warnings": factor_warnings,
        },
        "metadata": {
            "registered_count": len([field for field in PUBLIC_SCREENING_FIELDS if field in BASIC_FIELDS_INFO]),
            "missing_fields": metadata_missing,
            "mismatched_fields": metadata_mismatches,
        },
        "catalog_alignment": catalog_alignment,
        "catalog_runtime_semantic_alignment": catalog_runtime_semantic_alignment,
        "schema_semantic_alignment": schema_semantic_alignment,
        "catalog_source_alignment": catalog_source_alignment,
        "factor_pack_alignment": factor_pack_alignment,
        "p0_bundle_factor_packs": P0_BUNDLE_FACTOR_PACKS,
        "screening": screening_result,
        "structural_failures": structural_failures,
    }

    print(json.dumps(report, ensure_ascii=False, indent=2, default=str))
    if structural_failures:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))