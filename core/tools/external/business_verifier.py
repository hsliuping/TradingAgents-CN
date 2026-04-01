"""业务验收层接口骨架。"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from .skill_spec import (
    BusinessRuleFailure,
    BusinessVerificationResult,
    ImplementationFactReport,
    SandboxResult,
    SkillSpec,
    ValidationCheck,
)
from .financial_schema_context import (
    build_schema_generated_checks,
    infer_financial_schema_profile,
    resolve_financial_schema_context,
)


class BusinessVerifier:
    """业务验收器接口。"""

    def verify(
        self,
        sandbox_result: SandboxResult,
        spec: SkillSpec,
        fact_report: Optional[ImplementationFactReport] = None,
    ) -> BusinessVerificationResult:
        raise NotImplementedError


class DefaultBusinessVerifier(BusinessVerifier):
    """默认业务验收器。

    当前仅提供统一返回结构，后续可按分类扩展细粒度规则。
    """

    def verify(
        self,
        sandbox_result: SandboxResult,
        spec: SkillSpec,
        fact_report: Optional[ImplementationFactReport] = None,
    ) -> BusinessVerificationResult:
        result = BusinessVerificationResult(
            passed=bool(sandbox_result.success),
            business_score=10.0 if sandbox_result.success else 0.0,
            details={
                "verifier": self.__class__.__name__,
                "spec_category": spec.category,
            },
        )
        if not sandbox_result.success:
            result.failures.append(
                BusinessRuleFailure(
                    rule_id="sandbox_success",
                    message=sandbox_result.error or "沙箱执行失败，无法进入业务验收",
                )
            )
            return result

        output = sandbox_result.output
        generated_checks = self._resolve_generated_checks(spec, fact_report)
        schema_context = self._resolve_schema_verification_context(spec)
        schema_checks = self._build_schema_generated_checks(schema_context)
        generated_checks.extend(schema_checks)
        generated_checks = self._dedupe_checks(generated_checks)
        result.details["generated_check_count"] = len(generated_checks)
        result.details["schema_generated_check_count"] = len(schema_checks)
        if schema_context:
            result.details["schema_verification"] = schema_context
        result.details["output_type"] = type(output).__name__ if output is not None else None
        result.details["executed_checks"] = []

        for check in generated_checks:
            self._apply_check(result, output, check)

        if result.failures:
            result.passed = False
            result.business_score = min(result.business_score or 10.0, 3.0)
            result.details["blocking_failure_count"] = len(result.failures)
        elif result.warnings:
            result.passed = True
            result.business_score = min(result.business_score or 10.0, 8.0)
            result.details["warning_check_count"] = len(result.warnings)
        return result

    @staticmethod
    def _resolve_schema_verification_context(spec: SkillSpec) -> Optional[Dict[str, Any]]:
        return resolve_financial_schema_context(spec)

    @staticmethod
    def _infer_schema_profile(spec: SkillSpec) -> Optional[Dict[str, str]]:
        return infer_financial_schema_profile(spec)

    @staticmethod
    def _build_schema_generated_checks(schema_context: Optional[Dict[str, Any]]) -> List[ValidationCheck]:
        return build_schema_generated_checks(schema_context)

    @staticmethod
    def _dedupe_checks(checks: List[ValidationCheck]) -> List[ValidationCheck]:
        deduped: List[ValidationCheck] = []
        seen = set()
        for check in checks:
            key = (
                check.name or "",
                check.check_type or "",
                check.field or "",
                check.value_path or "",
            )
            if key in seen:
                continue
            seen.add(key)
            deduped.append(check)
        return deduped

    @staticmethod
    def _resolve_generated_checks(
        spec: SkillSpec,
        fact_report: Optional[ImplementationFactReport],
    ) -> List[ValidationCheck]:
        checks: List[ValidationCheck] = []
        raw_checks = list(spec.validation_checks or [])
        if fact_report and fact_report.validation_checks:
            existing_names = {check.name for check in raw_checks if check.name}
            for check in fact_report.validation_checks:
                if check.name and check.name in existing_names:
                    continue
                raw_checks.append(check)

        for raw in raw_checks:
            normalized_type = DefaultBusinessVerifier._normalize_check_type(raw.check_type, raw.rule_level)
            rule_level = DefaultBusinessVerifier._default_rule_level(normalized_type, raw.rule_level)

            if normalized_type in ("business", "custom"):
                checks.append(
                    ValidationCheck(
                        name=raw.name,
                        description=raw.description,
                        required=False,
                        check_type="custom",
                        rule_level=rule_level,
                        blocking=False,
                        field=raw.field,
                        value_path=raw.value_path,
                        forbid_null=raw.forbid_null,
                        params=raw.params,
                    )
                )
                continue

            if normalized_type == "input_validation":
                checks.append(
                    ValidationCheck(
                        name=raw.name or "status_success",
                        description=raw.description or "输入与执行状态必须有效",
                        required=raw.required,
                        check_type="status_success",
                        rule_level=rule_level,
                        blocking=raw.blocking,
                        value_path="output",
                        forbid_null=False,
                        params=raw.params,
                    )
                )
                continue

            if normalized_type == "data_validation":
                if raw.field:
                    checks.append(
                        ValidationCheck(
                            name=raw.name or f"required_field:{raw.field}",
                            description=raw.description or f"关键数据字段 {raw.field} 不可缺失",
                            required=raw.required,
                            check_type="required_field",
                            rule_level=rule_level,
                            blocking=raw.blocking,
                            field=raw.field,
                            value_path=raw.value_path or "data",
                            forbid_null=True,
                            params=raw.params,
                        )
                    )
                elif spec.expected_output.fields:
                    for field_name in spec.expected_output.fields:
                        checks.append(
                            ValidationCheck(
                                name=f"{raw.name or 'data_validation'}:{field_name}",
                                description=raw.description or f"关键输出字段 {field_name} 不可缺失",
                                required=raw.required,
                                check_type="required_field",
                                rule_level=rule_level,
                                blocking=raw.blocking,
                                field=field_name,
                                value_path=raw.value_path or "data",
                                forbid_null=True,
                                params=raw.params,
                            )
                        )
                else:
                    checks.append(
                        ValidationCheck(
                            name=raw.name or "required_non_empty_payload",
                            description=raw.description or "成功输出时必须返回非空 data 负载",
                            required=raw.required,
                            check_type="required_non_empty_payload",
                            rule_level=rule_level,
                            blocking=raw.blocking,
                            value_path=raw.value_path or "data",
                            forbid_null=True,
                            params=raw.params,
                        )
                    )
                continue

            checks.append(
                ValidationCheck(
                    name=raw.name,
                    description=raw.description,
                    required=raw.required,
                    check_type=normalized_type,
                    rule_level=rule_level,
                    blocking=raw.blocking,
                    field=raw.field,
                    value_path=raw.value_path,
                    forbid_null=raw.forbid_null,
                    params=raw.params,
                )
            )

        if not any(check.check_type == "status_success" for check in checks):
            checks.insert(
                0,
                ValidationCheck(
                    name="status_success",
                    description="输出状态必须为 success/ok",
                    check_type="status_success",
                    rule_level="output",
                    blocking=True,
                    value_path="output",
                    forbid_null=False,
                )
            )

        if not any(check.check_type in ("required_field", "required_non_empty_payload") for check in checks):
            if spec.expected_output.fields:
                for field_name in spec.expected_output.fields:
                    checks.append(
                        ValidationCheck(
                            name=f"required_field:{field_name}",
                            description=f"成功输出时必须包含字段 {field_name}",
                            check_type="required_field",
                            rule_level="data",
                            blocking=True,
                            field=field_name,
                            value_path="data",
                            forbid_null=True,
                        )
                    )
            else:
                checks.append(
                    ValidationCheck(
                        name="required_non_empty_payload",
                        description="成功输出时必须返回非空 data 负载",
                        check_type="required_non_empty_payload",
                        rule_level="data",
                        blocking=True,
                        value_path="data",
                        forbid_null=True,
                    )
                )
        return checks

    def _apply_check(
        self,
        result: BusinessVerificationResult,
        output: Any,
        check: ValidationCheck,
    ) -> None:
        result.details.setdefault("executed_checks", []).append(
            {
                "name": check.name,
                "check_type": check.check_type,
                "rule_level": check.rule_level,
                "blocking": check.blocking,
            }
        )

        if check.check_type == "status_success":
            status = None
            if isinstance(output, dict):
                status = output.get("status", "success")
            if not isinstance(status, str) or status.lower() not in ("success", "ok"):
                self._record_issue(
                    result,
                    check,
                    check.description or "输出状态必须为 success/ok",
                )
            return

        if check.check_type == "required_non_empty_payload":
            target = self._resolve_target(output, check.value_path)
            if target in (None, "", [], {}):
                self._record_issue(
                    result,
                    check,
                    check.description or "成功输出时必须返回非空负载",
                )
            return

        if check.check_type == "required_field":
            sample = self._resolve_sample(self._resolve_target(output, check.value_path))
            field_name = check.field or check.name.split(":", 1)[-1]
            if not isinstance(sample, dict):
                self._record_issue(
                    result,
                    check,
                    check.description or f"输出中缺少可检查字段 {field_name} 的结构化对象",
                )
                return
            exists, value = self._resolve_field_value(sample, field_name)
            if not exists:
                self._record_issue(
                    result,
                    check,
                    check.description or f"成功输出时必须包含字段 {field_name}",
                )
                return
            if check.forbid_null and value is None:
                self._record_issue(
                    result,
                    check,
                    check.description or f"成功输出时字段 {field_name} 不可为空",
                )
            return

        if check.check_type == "schema_condition":
            sample = self._resolve_sample(self._resolve_target(output, check.value_path))
            evaluation = self._evaluate_schema_condition(
                check.params.get("condition_expr") or {},
                sample,
            )
            if evaluation["passed"]:
                return

            if evaluation["missing_data"] and check.params.get("fallback_to_applicability_check"):
                applicability_check = sample.get("applicability_check") if isinstance(sample, dict) else None
                if isinstance(applicability_check, dict):
                    passed = applicability_check.get("passed")
                    if isinstance(passed, bool):
                        if passed:
                            return
                        self._record_issue(
                            result,
                            check,
                            check.description or "适用性规则校验未通过",
                        )
                        return

            message = check.description or "Schema applicability rule validation failed"
            if evaluation["message"]:
                message = f"{message} ({evaluation['message']})"
            if check.params.get("warning_only"):
                message = f"建议性规则未满足: {message}"
            self._record_issue(result, check, message)
            return

        if check.required:
            result.details.setdefault("unsupported_rule_types", []).append(check.check_type)
            self._record_issue(
                result,
                check,
                f"未支持的业务验收规则类型: {check.check_type}",
            )

    @staticmethod
    def _default_rule_level(check_type: str, current_level: str = "") -> str:
        if check_type == "input_validation" and current_level in ("", "data"):
            return "input"
        if check_type == "status_success" and current_level in ("", "data"):
            return "output"
        if current_level:
            return current_level
        mapping = {
            "input_validation": "input",
            "status_success": "output",
            "required_field": "data",
            "required_non_empty_payload": "data",
            "data_validation": "data",
            "schema_condition": "method",
            "custom": "business",
        }
        return mapping.get(check_type, "business")

    @staticmethod
    def _normalize_check_type(check_type: str, rule_level: str = "") -> str:
        normalized = (check_type or "").strip().lower()
        level = (rule_level or "").strip().lower()

        if normalized in (
            "required_field",
            "required_non_empty_payload",
            "status_success",
            "input_validation",
            "data_validation",
            "schema_condition",
        ):
            return normalized
        if normalized in ("input", "input_check"):
            return "input_validation"
        if normalized in ("output", "output_check", "status"):
            return "status_success"
        if normalized in ("data", "data_check"):
            return "data_validation"
        if normalized in ("business", "business_check"):
            return "custom"
        if level == "input":
            return "input_validation"
        if level == "output":
            return "status_success"
        if level == "data":
            return "data_validation"
        if level == "business":
            return "custom"
        return normalized or "custom"

    @staticmethod
    def _record_issue(
        result: BusinessVerificationResult,
        check: ValidationCheck,
        message: str,
    ) -> None:
        if check.blocking and check.required:
            result.failures.append(
                BusinessRuleFailure(
                    rule_id=check.name or check.check_type,
                    message=message,
                    severity="error",
                )
            )
            return
        result.warnings.append(message)

    @classmethod
    def _evaluate_schema_condition(cls, condition_expr: Dict[str, Any], sample: Any) -> Dict[str, Any]:
        if not isinstance(condition_expr, dict):
            return {"passed": False, "missing_data": True, "message": "invalid condition expression"}

        op = str(condition_expr.get("op") or "").strip().lower()
        if not op:
            return {"passed": False, "missing_data": True, "message": "missing op"}

        if op == "field_exists":
            exists, _ = cls._resolve_field_value(sample, str(condition_expr.get("field") or ""))
            return {"passed": exists, "missing_data": not exists, "message": "field missing" if not exists else ""}

        if op in ("field_gt", "field_gte", "field_lt", "field_lte"):
            exists, value = cls._resolve_field_value(sample, str(condition_expr.get("field") or ""))
            if not exists:
                return {"passed": False, "missing_data": True, "message": "field missing"}
            try:
                numeric_value = float(value)
                threshold = float(condition_expr.get("value"))
            except (TypeError, ValueError):
                return {"passed": False, "missing_data": True, "message": "numeric comparison unavailable"}
            passed = {
                "field_gt": numeric_value > threshold,
                "field_gte": numeric_value >= threshold,
                "field_lt": numeric_value < threshold,
                "field_lte": numeric_value <= threshold,
            }[op]
            return {
                "passed": passed,
                "missing_data": False,
                "message": f"value={numeric_value}, expected {op} {threshold}" if not passed else "",
            }

        if op in ("industry_in", "industry_not_in"):
            exists, value = cls._resolve_field_value(sample, str(condition_expr.get("field") or ""))
            if not exists:
                return {"passed": False, "missing_data": True, "message": "industry field missing"}
            choices = condition_expr.get("value") or []
            if not isinstance(choices, list):
                choices = [choices]
            normalized_choices = {str(item).strip() for item in choices}
            current = str(value).strip()
            passed = current in normalized_choices
            if op == "industry_not_in":
                passed = not passed
            return {
                "passed": passed,
                "missing_data": False,
                "message": f"industry={current}" if not passed else "",
            }

        if op in ("all_of", "any_of"):
            conditions = condition_expr.get("conditions") or []
            if not isinstance(conditions, list) or not conditions:
                return {"passed": False, "missing_data": True, "message": "conditions missing"}
            results = [cls._evaluate_schema_condition(item, sample) for item in conditions]
            passed = all(item["passed"] for item in results) if op == "all_of" else any(item["passed"] for item in results)
            missing_data = any(item["missing_data"] for item in results)
            messages = [item["message"] for item in results if item.get("message")]
            return {"passed": passed, "missing_data": missing_data and not passed, "message": "; ".join(messages)}

        if op == "not":
            nested = cls._evaluate_schema_condition(condition_expr.get("condition") or {}, sample)
            return {
                "passed": not nested["passed"],
                "missing_data": nested["missing_data"],
                "message": nested.get("message", ""),
            }

        return {"passed": False, "missing_data": True, "message": f"unsupported op: {op}"}

    @staticmethod
    def _resolve_field_value(sample: dict, field_name: str) -> tuple[bool, Any]:
        if isinstance(sample, dict) and field_name in sample:
            return True, sample.get(field_name)
        current: Any = sample
        for part in (field_name or "").split("."):
            key = part.strip()
            if not key:
                continue
            if not isinstance(current, dict) or key not in current:
                return False, None
            current = current.get(key)
        return True, current

    @staticmethod
    def _resolve_target(output: Any, value_path: str) -> Any:
        if value_path == "output":
            return output
        if isinstance(output, dict):
            nested = output.get(value_path)
            if nested is not None:
                return nested
            # 回退：若 output 中没有名为 value_path 的嵌套 key，
            # 则将 output 本身视为目标（兼容扁平输出结构）。
            return output
        return None

    @staticmethod
    def _resolve_sample(target: Any) -> Any:
        if isinstance(target, list):
            return target[0] if target else None
        return target


class ValuationBusinessVerifier(DefaultBusinessVerifier):
    """保留估值类验收器类型名，当前不再内置硬编码规则。"""

    def verify(
        self,
        sandbox_result: SandboxResult,
        spec: SkillSpec,
        fact_report: Optional[ImplementationFactReport] = None,
    ) -> BusinessVerificationResult:
        result = super().verify(sandbox_result, spec, fact_report)
        result.details["verifier"] = self.__class__.__name__
        result.details["rule_family"] = "valuation"
        return result


class BusinessVerifierRegistry:
    """按 Skill 类型选择业务验收器。"""

    def resolve(self, spec: SkillSpec) -> BusinessVerifier:
        return DefaultBusinessVerifier()

    def list_rule_families(self) -> List[str]:
        return ["default"]