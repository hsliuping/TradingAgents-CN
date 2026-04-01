from __future__ import annotations

from typing import Any, Dict, List, Optional

from app.models.screening import BASIC_FIELDS_INFO
from core.skill_runtime.factor_catalog import (
    FACTOR_RUNTIME_SEMANTIC_CONTRACTS,
    RECOMMENDED_FACTOR_PACKS,
    get_factor_definition,
    list_factor_definitions,
)
from core.skill_runtime.factor_schema import (
    P0_FACTOR_FIELD_SCHEMA,
    P0_PUBLIC_SCREENING_FIELDS,
    TECHNICAL_FACTOR_FIELD_SCHEMA,
    TECHNICAL_PUBLIC_SCREENING_FIELDS,
    get_factor_field_schema,
)


class FactorRegistryService:
    def __init__(self) -> None:
        self._p0_fields = set(P0_FACTOR_FIELD_SCHEMA.keys())
        self._technical_fields = set(TECHNICAL_FACTOR_FIELD_SCHEMA.keys())
        self._screening_fields = set(BASIC_FIELDS_INFO.keys())
        self._public_screening_fields = set(P0_PUBLIC_SCREENING_FIELDS) | set(TECHNICAL_PUBLIC_SCREENING_FIELDS)
        self._legacy_static_categories = {
            "basic": ["keyword", "symbol", "code", "name", "industry", "area", "market"],
            "market_value": ["total_mv", "circ_mv"],
            "financial": [],
            "trading": ["turnover_rate", "volume_ratio"],
            "price": ["close", "pct_chg", "amount"],
            "technical": [],
        }
        self._category_labels = {
            "basic": "基础条件",
            "market_value": "市值规模",
            "financial": "财务因子",
            "trading": "交易活跃度",
            "price": "价格表现",
            "technical": "技术因子",
        }
        self._category_order = ["basic", "market_value", "financial", "trading", "price", "technical"]
        self._hidden_field_names = {"code", "market"}

    def _infer_category_key(self, field_name: str, field_type: str) -> str:
        if field_type == "technical":
            return "technical"
        if field_name in {"keyword", "symbol", "code", "name", "industry", "area", "market", "is_st"}:
            return "basic"
        if field_name in {"total_mv", "circ_mv"}:
            return "market_value"
        if field_name in {"turnover_rate", "volume_ratio"}:
            return "trading"
        if field_name in {"close", "pct_chg", "amount"}:
            return "price"
        return "financial"

    @staticmethod
    def _dedupe_fields(fields: List[str]) -> List[str]:
        return list(dict.fromkeys(fields))

    @staticmethod
    def _serialize_basic_field_info(field_name: str) -> Optional[Dict[str, Any]]:
        field_info = BASIC_FIELDS_INFO.get(field_name)
        if field_info is None:
            return None

        return {
            "name": field_info.name,
            "display_name": field_info.display_name,
            "field_type": field_info.field_type.value,
            "data_type": field_info.data_type,
            "description": field_info.description,
            "unit": field_info.unit,
            "supported_operators": [operator.value for operator in field_info.supported_operators],
        }

    def _resolve_governance_scope(self, factor_id: str) -> str:
        if factor_id in self._p0_fields:
            return "p0"
        if factor_id in self._technical_fields:
            return "technical"
        return "catalog_only"

    def _build_screening_metadata(self, factor_id: str) -> Optional[Dict[str, Any]]:
        field_info = BASIC_FIELDS_INFO.get(factor_id)
        if field_info is None:
            return None

        return {
            "registered": True,
            "field_type": field_info.field_type.value,
            "data_type": field_info.data_type,
            "unit": field_info.unit or "",
            "supported_operators": [operator.value for operator in field_info.supported_operators],
            "is_public_screening_field": factor_id in self._public_screening_fields,
        }

    def _build_registry_item(self, factor_id: str) -> Optional[Dict[str, Any]]:
        schema = get_factor_field_schema(factor_id)
        catalog = get_factor_definition(factor_id)
        contract = FACTOR_RUNTIME_SEMANTIC_CONTRACTS.get(factor_id)

        if schema is None and catalog is None and contract is None:
            return None

        recommended_packs = [pack_id for pack_id, fields in RECOMMENDED_FACTOR_PACKS.items() if factor_id in fields]
        return {
            "factor_id": factor_id,
            "display_name": schema.display_name if schema else (catalog.display_name if catalog else factor_id),
            "governance_scope": self._resolve_governance_scope(factor_id),
            "schema": schema.to_dict() if schema else None,
            "catalog": catalog.to_dict() if catalog else None,
            "runtime_semantic_contract": contract.to_dict() if contract else None,
            "screening": self._build_screening_metadata(factor_id),
            "recommended_packs": recommended_packs,
            "is_registered_in_screening": factor_id in self._screening_fields,
            "is_public_screening_field": factor_id in self._public_screening_fields,
        }

    def list_registry(
        self,
        category: Optional[str] = None,
        governance_scope: str = "all",
        screening_only: bool = False,
    ) -> Dict[str, Any]:
        catalog_entries = list_factor_definitions(category=category)
        factor_ids = [entry["factor_id"] for entry in catalog_entries]

        if governance_scope == "p0":
            factor_ids = [factor_id for factor_id in factor_ids if factor_id in self._p0_fields]
        elif governance_scope == "technical":
            factor_ids = [factor_id for factor_id in factor_ids if factor_id in self._technical_fields]

        if screening_only:
            factor_ids = [factor_id for factor_id in factor_ids if factor_id in self._screening_fields]

        items = [self._build_registry_item(factor_id) for factor_id in factor_ids]
        items = [item for item in items if item is not None]

        return {
            "total": len(items),
            "filters": {
                "category": category,
                "governance_scope": governance_scope,
                "screening_only": screening_only,
            },
            "items": items,
        }

    def get_registry_item(self, factor_id: str) -> Optional[Dict[str, Any]]:
        return self._build_registry_item(factor_id)

    def list_screening_registry_items(self, public_only: bool = False) -> List[Dict[str, Any]]:
        items = self.list_registry(screening_only=True).get("items", [])
        if public_only:
            items = [item for item in items if item.get("is_public_screening_field")]
        return items

    def get_screening_field_info(self, field_name: str) -> Optional[Dict[str, Any]]:
        registry_item = self.get_registry_item(field_name)
        basic_field_info = self._serialize_basic_field_info(field_name)

        if registry_item is None and basic_field_info is None:
            return None

        screening = (registry_item or {}).get("screening") or {}
        schema = (registry_item or {}).get("schema") or {}
        catalog = (registry_item or {}).get("catalog") or {}

        if basic_field_info is None:
            basic_field_info = {
                "name": field_name,
                "display_name": registry_item.get("display_name") or field_name,
                "field_type": screening.get("field_type") or "catalog_only",
                "data_type": screening.get("data_type") or schema.get("data_type") or "string",
                "description": schema.get("description") or catalog.get("description") or "",
                "unit": screening.get("unit") or schema.get("unit") or None,
                "supported_operators": screening.get("supported_operators") or [],
            }

        return {
            **basic_field_info,
            "governance_scope": (registry_item or {}).get("governance_scope"),
            "is_registered_in_screening": bool((registry_item or {}).get("is_registered_in_screening", field_name in self._screening_fields)),
            "is_public_screening_field": bool((registry_item or {}).get("is_public_screening_field", False)),
            "recommended_packs": (registry_item or {}).get("recommended_packs", []),
            "ui_category": self._infer_category_key(field_name, str(basic_field_info.get("field_type") or "")),
            "ui_order": self._category_order.index(self._infer_category_key(field_name, str(basic_field_info.get("field_type") or ""))) if self._infer_category_key(field_name, str(basic_field_info.get("field_type") or "")) in self._category_order else len(self._category_order),
            "ui_visible": field_name not in self._hidden_field_names,
        }

    def list_supported_screening_fields(self) -> List[Dict[str, Any]]:
        fields: List[Dict[str, Any]] = []
        for field_name in BASIC_FIELDS_INFO.keys():
            field_info = self.get_screening_field_info(field_name)
            if field_info is not None:
                fields.append(field_info)
        return fields

    def get_legacy_screening_field_config(self) -> Dict[str, Any]:
        fields: Dict[str, Dict[str, Any]] = {}
        categories = {key: list(values) for key, values in self._legacy_static_categories.items()}
        visible_fields_by_category = {key: [] for key in self._category_order}

        for field_name in BASIC_FIELDS_INFO.keys():
            field_info = self._serialize_basic_field_info(field_name)
            if field_info is not None:
                fields[field_name] = field_info

        for item in self.list_screening_registry_items(public_only=True):
            factor_id = str(item.get("factor_id") or "").strip()
            if not factor_id:
                continue

            field_info = self.get_screening_field_info(factor_id)
            if field_info is None:
                continue
            fields[factor_id] = {key: value for key, value in field_info.items() if key in {
                "name", "display_name", "field_type", "data_type", "description", "unit", "supported_operators"
            }}

            field_type = ((item.get("screening") or {}).get("field_type") or "").strip()
            if field_type == "technical":
                categories["technical"].append(factor_id)
            elif factor_id in {"total_mv", "circ_mv"}:
                categories["market_value"].append(factor_id)
            elif factor_id not in categories["basic"] and factor_id not in categories["trading"] and factor_id not in categories["price"]:
                categories["financial"].append(factor_id)

        for field_name in fields.keys():
            full_info = self.get_screening_field_info(field_name)
            if not full_info or not full_info.get("ui_visible", True):
                continue
            category_key = str(full_info.get("ui_category") or self._infer_category_key(field_name, str(full_info.get("field_type") or "")))
            visible_fields_by_category.setdefault(category_key, []).append(field_name)

        return {
            "fields": fields,
            "categories": {key: self._dedupe_fields(values) for key, values in categories.items()},
            "ui_metadata": {
                "category_order": list(self._category_order),
                "category_labels": dict(self._category_labels),
                "hidden_fields": sorted(self._hidden_field_names),
                "visible_fields_by_category": {
                    key: self._dedupe_fields(values) for key, values in visible_fields_by_category.items()
                },
            },
        }

    def build_screening_fields_markdown(self, public_only: bool = False) -> str:
        items = self.list_screening_registry_items(public_only=public_only)
        if not items:
            return "- 当前没有可用的筛选字段"

        sorted_items = sorted(
            items,
            key=lambda item: (
                item.get("screening", {}).get("field_type") or "",
                item.get("factor_id") or "",
            ),
        )

        lines: List[str] = []
        for item in sorted_items:
            screening = item.get("screening") or {}
            factor_id = str(item.get("factor_id") or "").strip()
            if not factor_id:
                continue

            display_name = str(item.get("display_name") or factor_id)
            description = str(
                (item.get("schema") or {}).get("description")
                or (item.get("catalog") or {}).get("description")
                or ""
            ).strip()
            data_type = str(screening.get("data_type") or (item.get("schema") or {}).get("data_type") or "")
            operators = screening.get("supported_operators") or []

            detail_parts: List[str] = [display_name]
            if description and description != display_name:
                detail_parts.append(description)
            if data_type:
                detail_parts.append(f"类型: {data_type}")
            if operators:
                detail_parts.append("操作符: " + "/".join(str(operator) for operator in operators))

            lines.append(f"- {factor_id}    " + "；".join(detail_parts))

        return "\n".join(lines)

    def build_screening_tool_description(self, max_fields: int = 20) -> str:
        items = self.list_screening_registry_items(public_only=True)
        field_names = [str(item.get("factor_id") or "").strip() for item in items]
        field_names = [field_name for field_name in field_names if field_name]

        preview = "/".join(field_names[:max_fields])
        remaining = max(len(field_names) - max_fields, 0)
        remaining_text = f" 等 {len(field_names)} 个字段" if remaining > 0 else " 等字段"

        return (
            "按多个财务、交易和技术指标批量筛选 A 股股票。"
            "条件以 JSON 数组形式传入，每个条件包含 field、operator、value 三个字段。"
            f"支持的筛选字段基于 factor registry 动态生成，当前包含 {preview}{remaining_text if preview else ''}。"
            "支持的操作符：> < >= <= == != between in not_in contains。"
            "返回符合条件的股票列表，包含代码、名称、行业、估值、盈利质量、现金流、偿债能力、股息率和技术指标等信息。"
        )


_factor_registry_service: Optional[FactorRegistryService] = None


def get_factor_registry_service() -> FactorRegistryService:
    global _factor_registry_service
    if _factor_registry_service is None:
        _factor_registry_service = FactorRegistryService()
    return _factor_registry_service


def build_screening_fields_markdown(public_only: bool = False) -> str:
    return get_factor_registry_service().build_screening_fields_markdown(public_only=public_only)


def build_screening_tool_description(max_fields: int = 20) -> str:
    return get_factor_registry_service().build_screening_tool_description(max_fields=max_fields)