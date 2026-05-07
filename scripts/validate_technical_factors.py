from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path
from typing import Any, Dict, List


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.core.data_source_priority import get_preferred_data_source_async
from app.core.database import get_mongo_db, init_database
from app.models.screening import BASIC_FIELDS_INFO, FieldType, OperatorType, ScreeningCondition
from app.services.database_screening_service import get_database_screening_service
from app.services.enhanced_screening_service import get_enhanced_screening_service
from core.skill_runtime.factor_catalog import (
    validate_technical_factor_catalog_runtime_semantic_alignment,
    validate_technical_factor_catalog_schema_alignment,
    validate_technical_factor_schema_semantic_alignment,
)
from core.skill_runtime.factor_schema import TECHNICAL_FACTOR_FIELD_SCHEMA, TECHNICAL_PUBLIC_SCREENING_FIELDS


SYMBOL = "600519"
TECHNICAL_FIELDS = list(TECHNICAL_PUBLIC_SCREENING_FIELDS)


def _metadata_alignment_check() -> Dict[str, Any]:
    missing_fields: List[str] = []
    mismatches: List[Dict[str, Any]] = []

    for field_name in TECHNICAL_FIELDS:
        metadata = BASIC_FIELDS_INFO.get(field_name)
        if metadata is None:
            missing_fields.append(field_name)
            continue

        field_mismatches: Dict[str, Any] = {}
        if metadata.field_type != FieldType.TECHNICAL:
            field_mismatches["field_type"] = {
                "expected": FieldType.TECHNICAL.value,
                "actual": metadata.field_type.value,
            }
        if metadata.data_type != "number":
            field_mismatches["data_type"] = {
                "expected": "number",
                "actual": metadata.data_type,
            }

        supported_operators = {operator.value for operator in metadata.supported_operators}
        expected_operators = {
            OperatorType.GT.value,
            OperatorType.LT.value,
            OperatorType.GTE.value,
            OperatorType.LTE.value,
            OperatorType.BETWEEN.value,
        }
        if supported_operators != expected_operators:
            field_mismatches["supported_operators"] = {
                "expected": sorted(expected_operators),
                "actual": sorted(supported_operators),
            }

        if field_mismatches:
            mismatches.append({"field": field_name, "mismatches": field_mismatches})

    return {
        "missing_fields": missing_fields,
        "mismatches": mismatches,
    }


def _technical_schema_alignment_check() -> Dict[str, Any]:
    missing_screening_registration = [
        field_name for field_name in TECHNICAL_PUBLIC_SCREENING_FIELDS if field_name not in BASIC_FIELDS_INFO
    ]
    screening_registration_mismatches: List[Dict[str, Any]] = []

    for field_name in TECHNICAL_PUBLIC_SCREENING_FIELDS:
        schema = TECHNICAL_FACTOR_FIELD_SCHEMA.get(field_name)
        metadata = BASIC_FIELDS_INFO.get(field_name)
        if schema is None or metadata is None:
            continue

        field_mismatches: Dict[str, Any] = {}
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
        if (metadata.unit or "") != schema.unit:
            field_mismatches["unit"] = {
                "expected": schema.unit,
                "actual": metadata.unit or "",
            }
        if field_mismatches:
            screening_registration_mismatches.append({"field": field_name, "mismatches": field_mismatches})

    return {
        "missing_screening_registration": missing_screening_registration,
        "screening_registration_mismatches": screening_registration_mismatches,
        "catalog_alignment": validate_technical_factor_catalog_schema_alignment(),
        "catalog_runtime_semantic_alignment": validate_technical_factor_catalog_runtime_semantic_alignment(),
        "schema_semantic_alignment": validate_technical_factor_schema_semantic_alignment(),
    }


async def _collection_coverage_check() -> Dict[str, Any]:
    db = get_mongo_db()
    collection = db["stock_technical_indicators"]

    coverage: Dict[str, int] = {}
    for field_name in TECHNICAL_FIELDS:
        coverage[field_name] = await collection.count_documents({field_name: {"$ne": None}})

    total_count = await collection.count_documents({})
    sample = await collection.find_one(
        {"code": SYMBOL},
        projection={"_id": 0, "code": 1, "source": 1, "trade_date": 1, **{field: 1 for field in TECHNICAL_FIELDS}},
        sort=[("trade_date", -1), ("updated_at", -1)],
    )

    return {
        "total_count": total_count,
        "non_null_counts": coverage,
        "sample": sample or {},
    }


async def _view_alignment_check(symbol: str, preferred_source: str) -> Dict[str, Any]:
    db = get_mongo_db()
    projection = {
        "_id": 0,
        "code": 1,
        "source": 1,
        "trade_date": 1,
        "technical_trade_date": 1,
        **{field: 1 for field in TECHNICAL_FIELDS},
    }
    view_doc = await db["stock_screening_view"].find_one(
        {"code": symbol, "source": preferred_source},
        projection=projection,
    )
    technical_doc = await db["stock_technical_indicators"].find_one(
        {"code": symbol, "source": preferred_source},
        projection={"_id": 0, "code": 1, "source": 1, "trade_date": 1, **{field: 1 for field in TECHNICAL_FIELDS}},
        sort=[("trade_date", -1), ("updated_at", -1)],
    )

    mismatches: List[Dict[str, Any]] = []
    if view_doc and technical_doc:
        if view_doc.get("technical_trade_date") != technical_doc.get("trade_date"):
            mismatches.append(
                {
                    "field": "technical_trade_date",
                    "view": view_doc.get("technical_trade_date"),
                    "snapshot": technical_doc.get("trade_date"),
                }
            )

        for field_name in TECHNICAL_FIELDS:
            if view_doc.get(field_name) != technical_doc.get(field_name):
                mismatches.append(
                    {
                        "field": field_name,
                        "view": view_doc.get(field_name),
                        "snapshot": technical_doc.get(field_name),
                    }
                )

    return {
        "view_found": bool(view_doc),
        "snapshot_found": bool(technical_doc),
        "view_doc": view_doc or {},
        "snapshot_doc": technical_doc or {},
        "mismatches": mismatches,
    }


async def _database_screening_check(symbol: str) -> Dict[str, Any]:
    service = get_database_screening_service()
    items, total = await service.screen_stocks(
        conditions=[{"field": "code", "operator": "==", "value": symbol}],
        limit=1,
        offset=0,
        order_by=None,
    )
    item = items[0] if items else {}
    return {
        "total": total,
        "item_found": bool(item),
        "non_null_fields": [field for field in TECHNICAL_FIELDS if item.get(field) is not None],
        "sample_values": {field: item.get(field) for field in TECHNICAL_FIELDS},
        "source": item.get("source"),
    }


async def _enhanced_screening_check(symbol: str) -> Dict[str, Any]:
    service = get_enhanced_screening_service()
    result = await service.screen_stocks(
        conditions=[
            ScreeningCondition(field="code", operator=OperatorType.EQ, value=symbol),
            ScreeningCondition(field="ma20", operator=OperatorType.GT, value=0),
            ScreeningCondition(field="rsi14", operator=OperatorType.GT, value=0),
        ],
        limit=1,
        offset=0,
        order_by=None,
        use_database_optimization=True,
    )
    item = result.get("items", [])[0] if result.get("items") else {}
    analysis = result.get("analysis", {}) or {}
    return {
        "total": result.get("total", 0),
        "item_found": bool(item),
        "optimization_used": result.get("optimization_used"),
        "database_can_handle": analysis.get("database_can_handle"),
        "technical_conditions": analysis.get("technical_conditions"),
        "sample_values": {field: item.get(field) for field in TECHNICAL_FIELDS},
    }


async def main() -> int:
    symbol = sys.argv[1] if len(sys.argv) > 1 else SYMBOL

    await init_database()
    preferred_source = await get_preferred_data_source_async(market_category="a_shares")

    report = {
        "symbol": symbol,
        "preferred_source": preferred_source,
        "metadata_alignment": _metadata_alignment_check(),
        "technical_schema_alignment": _technical_schema_alignment_check(),
        "collection_coverage": await _collection_coverage_check(),
        "view_alignment": await _view_alignment_check(symbol, preferred_source),
        "database_screening": await _database_screening_check(symbol),
        "enhanced_screening": await _enhanced_screening_check(symbol),
    }

    failures: List[str] = []

    if report["metadata_alignment"]["missing_fields"]:
        failures.append(
            "BASIC_FIELDS_INFO 缺少技术字段: "
            + ", ".join(report["metadata_alignment"]["missing_fields"])
        )
    if report["metadata_alignment"]["mismatches"]:
        failures.append(
            "技术字段元数据不一致: "
            + ", ".join(item["field"] for item in report["metadata_alignment"]["mismatches"])
        )

    technical_schema_alignment = report["technical_schema_alignment"]
    if technical_schema_alignment["missing_screening_registration"]:
        failures.append(
            "技术字段缺少 screening 注册: "
            + ", ".join(technical_schema_alignment["missing_screening_registration"])
        )
    if technical_schema_alignment["screening_registration_mismatches"]:
        failures.append(
            "技术字段 screening 元数据与 schema 不一致: "
            + ", ".join(item["field"] for item in technical_schema_alignment["screening_registration_mismatches"])
        )
    if technical_schema_alignment["catalog_alignment"].get("missing_catalog_entries"):
        failures.append(
            "technical factor_catalog 缺少字段登记: "
            + ", ".join(item["field"] for item in technical_schema_alignment["catalog_alignment"]["missing_catalog_entries"])
        )
    if technical_schema_alignment["catalog_alignment"].get("mismatches"):
        failures.append(
            "technical factor_catalog 字段类别不一致: "
            + ", ".join(item["field"] for item in technical_schema_alignment["catalog_alignment"]["mismatches"])
        )
    if technical_schema_alignment["catalog_runtime_semantic_alignment"].get("missing_contract_entries"):
        failures.append(
            "technical runtime semantic contract 缺失: "
            + ", ".join(item["field"] for item in technical_schema_alignment["catalog_runtime_semantic_alignment"]["missing_contract_entries"])
        )
    if technical_schema_alignment["catalog_runtime_semantic_alignment"].get("mismatches"):
        failures.append(
            "technical factor_catalog 与 runtime semantic contract 不一致: "
            + ", ".join(item["field"] for item in technical_schema_alignment["catalog_runtime_semantic_alignment"]["mismatches"])
        )
    if technical_schema_alignment["schema_semantic_alignment"].get("missing_schema_fields"):
        failures.append(
            "technical schema/runtime semantic contract 缺失字段: "
            + ", ".join(item["field"] for item in technical_schema_alignment["schema_semantic_alignment"]["missing_schema_fields"])
        )
    if technical_schema_alignment["schema_semantic_alignment"].get("missing_source_priority_entries"):
        failures.append(
            "technical schema/source_priority 缺失: "
            + ", ".join(item["field"] for item in technical_schema_alignment["schema_semantic_alignment"]["missing_source_priority_entries"])
        )
    if technical_schema_alignment["schema_semantic_alignment"].get("missing_minimum_input_group_entries"):
        failures.append(
            "technical schema/minimum_input_groups 缺失: "
            + ", ".join(item["field"] for item in technical_schema_alignment["schema_semantic_alignment"]["missing_minimum_input_group_entries"])
        )
    if technical_schema_alignment["schema_semantic_alignment"].get("missing_minimum_computable_condition_entries"):
        failures.append(
            "technical schema/minimum_computable_conditions 缺失: "
            + ", ".join(item["field"] for item in technical_schema_alignment["schema_semantic_alignment"]["missing_minimum_computable_condition_entries"])
        )
    if technical_schema_alignment["schema_semantic_alignment"].get("mismatches"):
        failures.append(
            "technical schema 与 runtime semantic contract 不一致: "
            + ", ".join(item["field"] for item in technical_schema_alignment["schema_semantic_alignment"]["mismatches"])
        )

    collection_coverage = report["collection_coverage"]
    if collection_coverage["total_count"] <= 0:
        failures.append("stock_technical_indicators 为空")
    empty_fields = [
        field_name
        for field_name, count in collection_coverage["non_null_counts"].items()
        if count <= 0
    ]
    if empty_fields:
        failures.append("以下技术字段在物化集合中没有非空数据: " + ", ".join(empty_fields))

    view_alignment = report["view_alignment"]
    if not view_alignment["view_found"]:
        failures.append(f"stock_screening_view 缺少 {symbol}/{preferred_source} 记录")
    if not view_alignment["snapshot_found"]:
        failures.append(f"stock_technical_indicators 缺少 {symbol}/{preferred_source} 记录")
    if view_alignment["mismatches"]:
        failures.append(
            "视图技术字段与技术快照不一致: "
            + ", ".join(item["field"] for item in view_alignment["mismatches"])
        )

    database_screening = report["database_screening"]
    if database_screening["total"] <= 0 or not database_screening["item_found"]:
        failures.append(f"数据库筛选未返回 {symbol}")
    db_missing_fields = [
        field_name for field_name in TECHNICAL_FIELDS if field_name not in database_screening["non_null_fields"]
    ]
    if db_missing_fields:
        failures.append("数据库筛选缺少非空技术字段: " + ", ".join(db_missing_fields))

    enhanced_screening = report["enhanced_screening"]
    if enhanced_screening["optimization_used"] != "database":
        failures.append(
            f"增强筛选未走数据库路径: {enhanced_screening['optimization_used']}"
        )
    if not enhanced_screening["database_can_handle"]:
        failures.append("增强筛选分析认为数据库无法处理技术条件")
    if enhanced_screening["technical_conditions"] != 2:
        failures.append(
            f"增强筛选技术条件统计异常: {enhanced_screening['technical_conditions']}"
        )
    if enhanced_screening["total"] <= 0 or not enhanced_screening["item_found"]:
        failures.append(f"增强筛选未返回 {symbol}")

    report["failures"] = failures

    print(json.dumps(report, ensure_ascii=False, indent=2, default=str))
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))