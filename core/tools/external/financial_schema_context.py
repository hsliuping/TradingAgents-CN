"""金融 schema bundle 在 Skill 生成链路中的公共解析能力。"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

from app.services.schema_bundle_service import get_default_schema_bundle_service

from .skill_spec import SkillSpec, ValidationCheck


def _derive_profile_name(verifier_rule_id: str, contract_id: str) -> str:
    for raw in (verifier_rule_id, contract_id):
        token = str(raw or "").rsplit(".", 1)[-1].strip().lower()
        if token.endswith("_basic"):
            token = token[: -len("_basic")]
        if token:
            return token
    return ""


def _build_profile_keywords(profile: str, method_name: str, contract_name: str) -> List[str]:
    return sorted(
        (item for item in {
            profile,
            profile.replace("_", "/"),
            profile.replace("_", " "),
            profile.replace("_", ""),
            str(method_name or "").strip().lower(),
            str(method_name or "").strip().lower().replace(" 相对估值法", ""),
            str(method_name or "").strip().lower().replace(" 成长估值法", ""),
            str(contract_name or "").strip().lower(),
            str(contract_name or "").strip().lower().replace(" 估值基础输出契约", ""),
        } if item),
        key=len,
        reverse=True,
    )


def _collect_object_match_keywords(*objects: Any) -> List[str]:
    keywords = set()
    for schema_object in objects:
        data = getattr(schema_object, "data", None) or {}
        raw_keywords = list(data.get("match_keywords") or [])
        for item in raw_keywords:
            normalized = str(item or "").strip().lower()
            if normalized:
                keywords.add(normalized)
    return sorted(keywords, key=len, reverse=True)


def _discover_schema_profiles() -> List[Dict[str, Any]]:
    service = get_default_schema_bundle_service()
    method_objects = service.get_schema_objects_by_type("method")
    verifier_objects = service.get_schema_objects_by_type("verifier_rule")

    method_by_verifier: Dict[str, Any] = {}
    for method_object in method_objects:
        for verifier_rule_id in list(method_object.data.get("verifier_rule_ids") or []):
            if verifier_rule_id:
                method_by_verifier[str(verifier_rule_id)] = method_object

    profiles: List[Dict[str, Any]] = []
    for verifier_object in verifier_objects:
        verifier_rule_id = str(verifier_object.id or "").strip()
        contract_id = str(verifier_object.data.get("target_contract_id") or "").strip()
        if not verifier_rule_id or not contract_id:
            continue

        profile = _derive_profile_name(verifier_rule_id, contract_id)
        if not profile:
            continue

        method_object = method_by_verifier.get(verifier_rule_id)
        method_id = str(method_object.id if method_object else "").strip()
        method_name = str(method_object.name if method_object else "").strip()
        contract_object = service.get_schema_object(contract_id)
        contract_name = str(contract_object.name if contract_object else "").strip()
        keywords = _build_profile_keywords(profile, method_name, contract_name)
        keywords.extend(_collect_object_match_keywords(method_object, verifier_object, contract_object))
        keywords = sorted({item for item in keywords if item}, key=len, reverse=True)

        profiles.append(
            {
                "profile": profile,
                "method_id": method_id,
                "verifier_rule_id": verifier_rule_id,
                "contract_id": contract_id,
                "keywords": keywords,
            }
        )

    return sorted(profiles, key=lambda item: max((len(keyword) for keyword in item["keywords"]), default=0), reverse=True)


def _keyword_matches_text(text: str, keyword: str) -> bool:
    normalized_text = str(text or "").lower()
    normalized_keyword = str(keyword or "").strip().lower()
    if not normalized_keyword:
        return False

    if re.search(r"[\u4e00-\u9fff]", normalized_keyword):
        return normalized_keyword in normalized_text

    if re.fullmatch(r"[a-z0-9_]+", normalized_keyword) and len(normalized_keyword) <= 3:
        pattern = rf"(?<![a-z0-9]){re.escape(normalized_keyword)}(?![a-z0-9])"
        return re.search(pattern, normalized_text) is not None

    return normalized_keyword in normalized_text


def infer_financial_schema_profile(spec: SkillSpec) -> Optional[Dict[str, str]]:
    text = " ".join(
        [
            spec.tool_id or "",
            spec.display_name or "",
            spec.description or "",
            spec.category or "",
            spec.data_source or "",
            " ".join(spec.constraints or []),
        ]
    ).lower()

    profiles = _discover_schema_profiles()
    if not profiles:
        return None

    if (spec.category or "").lower() != "valuation" and "估值" not in text:
        if not any(any(_keyword_matches_text(text, keyword) for keyword in item["keywords"]) for item in profiles):
            return None

    best_match: Optional[Dict[str, Any]] = None
    for item in profiles:
        matched_keywords = [keyword for keyword in item["keywords"] if _keyword_matches_text(text, keyword)]
        if not matched_keywords:
            continue
        candidate = {
            "profile": item["profile"],
            "method_id": item["method_id"],
            "verifier_rule_id": item["verifier_rule_id"],
            "contract_id": item["contract_id"],
            "matched_keyword_len": max(len(keyword) for keyword in matched_keywords),
            "matched_keyword_count": len(matched_keywords),
        }
        if best_match is None or (
            candidate["matched_keyword_len"],
            candidate["matched_keyword_count"],
        ) > (
            best_match["matched_keyword_len"],
            best_match["matched_keyword_count"],
        ):
            best_match = candidate

    if best_match is not None:
        return {
            "profile": best_match["profile"],
            "method_id": best_match["method_id"],
            "verifier_rule_id": best_match["verifier_rule_id"],
            "contract_id": best_match["contract_id"],
        }

    return None


def resolve_financial_schema_context(spec: SkillSpec) -> Optional[Dict[str, Any]]:
    profile = infer_financial_schema_profile(spec)
    if not profile:
        return None

    service = get_default_schema_bundle_service()
    method_object = service.get_schema_object(profile["method_id"])
    verifier_object = service.get_schema_object(profile["verifier_rule_id"])
    contract_object = service.get_schema_object(profile["contract_id"])

    applicability_rule_ids: List[str] = []
    preferred_rule_ids: List[str] = []
    if verifier_object is not None:
        params = verifier_object.data.get("params") or {}
        applicability_rule_ids = list(params.get("applicability_rules") or [])
        preferred_rule_ids = list(params.get("preferred_rules") or [])

    applicability_rules: Dict[str, Any] = {}
    for rule_id in applicability_rule_ids:
        rule_object = service.get_schema_object(rule_id)
        if rule_object is not None:
            applicability_rules[rule_id] = rule_object.data

    preferred_rules: Dict[str, Any] = {}
    for rule_id in preferred_rule_ids:
        rule_object = service.get_schema_object(rule_id)
        if rule_object is not None:
            preferred_rules[rule_id] = rule_object.data

    if method_object is None and verifier_object is None and contract_object is None and not applicability_rules and not preferred_rules:
        return None

    return {
        "profile": profile["profile"],
        "method_id": profile["method_id"],
        "verifier_rule_id": profile["verifier_rule_id"],
        "contract_id": profile["contract_id"],
        "method": method_object.data if method_object else None,
        "verifier_rule": verifier_object.data if verifier_object else None,
        "contract": contract_object.data if contract_object else None,
        "applicability_rules": applicability_rules,
        "preferred_rules": preferred_rules,
    }


def get_contract_required_fields(schema_context: Optional[Dict[str, Any]]) -> List[str]:
    if not schema_context:
        return []

    contract = schema_context.get("contract") or {}
    verifier_rule = schema_context.get("verifier_rule") or {}
    verifier_rule_id = schema_context.get("verifier_rule_id", "?")
    contract_id = schema_context.get("contract_id", "?")
    required_fields = list((verifier_rule.get("params") or {}).get("required_fields") or [])
    if required_fields:
        result = [field_name for field_name in required_fields if str(field_name).strip()]
        logger = logging.getLogger(__name__)
        logger.info(
            "🔬 [get_contract_required_fields] 来源=verifier_rule(%s) required_fields=%s",
            verifier_rule_id,
            result,
        )
        return result

    fields: List[str] = []
    for field_def in contract.get("required_fields") or []:
        field_name = str((field_def or {}).get("field_name") or "").strip()
        if field_name:
            fields.append(field_name)
    logger = logging.getLogger(__name__)
    logger.info(
        "🔬 [get_contract_required_fields] 来源=contract(%s) required_fields=%s (verifier_rule %s 无 required_fields)",
        contract_id,
        fields,
        verifier_rule_id,
    )
    return fields


def build_schema_constraint_hints(schema_context: Optional[Dict[str, Any]]) -> List[str]:
    if not schema_context:
        return []

    constraints: List[str] = []
    method = schema_context.get("method") or {}
    contract = schema_context.get("contract") or {}
    verifier_rule = schema_context.get("verifier_rule") or {}
    applicability_rules = schema_context.get("applicability_rules") or {}
    preferred_rules = schema_context.get("preferred_rules") or {}

    method_name = str(method.get("name") or schema_context.get("method_id") or "该方法").strip()
    objective = str(method.get("objective") or "").strip()
    if objective:
        constraints.append(f"按 {method_name} 组织输出，目标是：{objective}")

    required_fields = list(method.get("required_fields") or [])
    if required_fields:
        constraints.append(f"方法前置数据至少要覆盖：{', '.join(required_fields[:6])}")

    assumptions = [str(item).strip() for item in method.get("assumptions") or [] if str(item).strip()]
    if assumptions:
        constraints.append(f"方法成立前提：{'；'.join(assumptions[:3])}")

    limitations = [str(item).strip() for item in method.get("limitations") or [] if str(item).strip()]
    if limitations:
        constraints.append(f"方法局限：{'；'.join(limitations[:3])}")

    narrative_requirements = [str(item).strip() for item in contract.get("narrative_requirements") or [] if str(item).strip()]
    if narrative_requirements:
        constraints.append(f"输出叙述必须满足：{'；'.join(narrative_requirements[:4])}")

    prohibited_patterns = [str(item).strip() for item in contract.get("prohibited_patterns") or [] if str(item).strip()]
    if prohibited_patterns:
        constraints.extend(f"禁止：{item}" for item in prohibited_patterns[:4])

    failure_message = str(verifier_rule.get("failure_message") or "").strip()
    if failure_message:
        constraints.append(f"验收失败条件：{failure_message}")

    remediation_hint = str(verifier_rule.get("remediation_hint") or "").strip()
    if remediation_hint:
        constraints.append(f"生成时应主动满足：{remediation_hint}")

    for rule_collection in (applicability_rules, preferred_rules):
        for rule_id, rule in rule_collection.items():
            human_description = str((rule or {}).get("human_description") or rule_id).strip()
            rationale = str((rule or {}).get("rationale") or "").strip()
            severity = str((rule or {}).get("severity") or "").strip()
            line = human_description
            if rationale:
                line += f"；原因：{rationale}"
            if severity:
                line += f"（{severity}）"
            constraints.append(f"适用性规则：{line}")

    deduped: List[str] = []
    seen = set()
    for item in constraints:
        normalized = item.strip()
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        deduped.append(normalized)
    return deduped


def build_schema_generated_checks(schema_context: Optional[Dict[str, Any]]) -> List[ValidationCheck]:
    if not schema_context:
        return []

    checks: List[ValidationCheck] = []
    contract = schema_context.get("contract") or {}
    verifier_rule = schema_context.get("verifier_rule") or {}
    required_fields = list((verifier_rule.get("params") or {}).get("required_fields") or [])
    applicability_rule_ids = list((verifier_rule.get("params") or {}).get("applicability_rules") or [])
    preferred_rule_ids = list((verifier_rule.get("params") or {}).get("preferred_rules") or [])

    if not required_fields:
        for field_def in contract.get("required_fields") or []:
            field_name = str((field_def or {}).get("field_name") or "").strip()
            if field_name:
                required_fields.append(field_name)

    logger = logging.getLogger(__name__)
    logger.info(
        "🔬 [build_schema_generated_checks] required_fields=%s verifier_rule_id=%s contract_id=%s",
        required_fields,
        schema_context.get("verifier_rule_id", "?"),
        schema_context.get("contract_id", "?"),
    )

    blocking = bool(verifier_rule.get("blocking", True))
    contract_name = str(contract.get("name") or schema_context.get("contract_id") or "schema_contract")
    for field_name in required_fields:
        checks.append(
            ValidationCheck(
                name=f"schema_required_field:{field_name}",
                description=f"{contract_name} 要求输出必须包含字段 {field_name}",
                required=True,
                check_type="required_field",
                rule_level="data",
                blocking=blocking,
                field=field_name,
                value_path="data",
                forbid_null=True,
            )
        )

    for rule_id in applicability_rule_ids:
        rule_object = ((schema_context.get("applicability_rules") or {}).get(rule_id) or {})
        severity = str(rule_object.get("severity") or "error").lower()
        rule_kind = str(rule_object.get("rule_kind") or "required").lower()
        checks.append(
            ValidationCheck(
                name=f"schema_condition:{rule_id}",
                description=str(
                    rule_object.get("human_description")
                    or f"Schema applicability rule {rule_id} must pass"
                ),
                required=severity == "error" or rule_kind == "required",
                check_type="schema_condition",
                rule_level="method",
                blocking=severity == "error" or rule_kind == "required",
                value_path="data",
                forbid_null=False,
                params={
                    "rule_id": rule_id,
                    "condition_expr": rule_object.get("condition_expr") or {},
                    "severity": severity,
                    "rule_kind": rule_kind,
                    "fallback_to_applicability_check": True,
                },
            )
        )

    for rule_id in preferred_rule_ids:
        rule_object = ((schema_context.get("preferred_rules") or {}).get(rule_id) or {})
        checks.append(
            ValidationCheck(
                name=f"schema_condition:{rule_id}",
                description=str(
                    rule_object.get("human_description")
                    or f"Schema preferred rule {rule_id} should pass"
                ),
                required=False,
                check_type="schema_condition",
                rule_level="method",
                blocking=False,
                value_path="data",
                forbid_null=False,
                params={
                    "rule_id": rule_id,
                    "condition_expr": rule_object.get("condition_expr") or {},
                    "severity": str(rule_object.get("severity") or "warning").lower(),
                    "rule_kind": str(rule_object.get("rule_kind") or "preferred").lower(),
                    "fallback_to_applicability_check": False,
                    "warning_only": True,
                },
            )
        )

    return checks