"""业务验收层接口骨架。"""

from __future__ import annotations

from typing import Any, List, Optional

from .skill_spec import (
    BusinessRuleFailure,
    BusinessVerificationResult,
    ImplementationFactReport,
    SandboxResult,
    SkillSpec,
    ValidationCheck,
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
        result.details["generated_check_count"] = len(generated_checks)
        result.details["output_type"] = type(output).__name__ if output is not None else None

        for check in generated_checks:
            self._apply_check(result, output, check)

        if result.failures:
            result.passed = False
            result.business_score = min(result.business_score or 10.0, 3.0)
        return result

    @staticmethod
    def _resolve_generated_checks(
        spec: SkillSpec,
        fact_report: Optional[ImplementationFactReport],
    ) -> List[ValidationCheck]:
        if fact_report and fact_report.validation_checks:
            return list(fact_report.validation_checks)

        checks: List[ValidationCheck] = []
        for field_name in spec.expected_output.fields:
            checks.append(
                ValidationCheck(
                    name=f"required_field:{field_name}",
                    description=f"成功输出时必须包含字段 {field_name}",
                    check_type="required_field",
                    field=field_name,
                    value_path="data",
                    forbid_null=True,
                )
            )
        if not checks:
            checks.append(
                ValidationCheck(
                    name="required_non_empty_payload",
                    description="成功输出时必须返回非空 data 负载",
                    check_type="required_non_empty_payload",
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
        if check.check_type == "required_non_empty_payload":
            target = self._resolve_target(output, check.value_path)
            if target in (None, "", [], {}):
                result.failures.append(
                    BusinessRuleFailure(
                        rule_id=check.name or "required_non_empty_payload",
                        message=check.description or "成功输出时必须返回非空负载",
                    )
                )
            return

        if check.check_type == "required_field":
            sample = self._resolve_sample(self._resolve_target(output, check.value_path))
            field_name = check.field or check.name.split(":", 1)[-1]
            if not isinstance(sample, dict):
                result.failures.append(
                    BusinessRuleFailure(
                        rule_id=check.name or "required_field",
                        message=check.description or f"输出中缺少可检查字段 {field_name} 的结构化对象",
                    )
                )
                return
            if field_name not in sample:
                result.failures.append(
                    BusinessRuleFailure(
                        rule_id=check.name or f"required_field:{field_name}",
                        message=check.description or f"成功输出时必须包含字段 {field_name}",
                    )
                )
                return
            if check.forbid_null and sample.get(field_name) is None:
                result.failures.append(
                    BusinessRuleFailure(
                        rule_id=check.name or f"required_field:{field_name}",
                        message=check.description or f"成功输出时字段 {field_name} 不可为空",
                    )
                )

    @staticmethod
    def _resolve_target(output: Any, value_path: str) -> Any:
        if value_path == "output":
            return output
        if isinstance(output, dict):
            return output.get(value_path)
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