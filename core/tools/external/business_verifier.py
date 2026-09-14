"""业务验收层接口骨架。"""

from __future__ import annotations

import json
import logging
from typing import Any, Callable, Dict, List, Optional

from core.llm import Message, UnifiedLLMClient

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

logger = logging.getLogger(__name__)

# 业务验收 LLM 判断超时时间（秒）
BUSINESS_LLM_TIMEOUT_SECONDS = 120


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

    结合规则检查 + LLM 判断：
    - 规则检查：字段存在性、状态码、全零检测（零成本，快速拦截明显错误）
    - LLM 判断：数据矛盾、业务合理性（准确判断，避免误判导致重试成本）
    """

    def __init__(
        self,
        llm_client: Optional[UnifiedLLMClient] = None,
        provider: Optional[str] = None,
        model: Optional[str] = None,
    ):
        self._llm_client = llm_client
        self._provider = provider
        self._model = model

    def _get_client(self) -> Optional[UnifiedLLMClient]:
        if self._llm_client is not None:
            return self._llm_client
        if self._provider:
            try:
                kwargs: Dict[str, Any] = {}
                if self._model:
                    kwargs["model"] = self._model
                self._llm_client = UnifiedLLMClient.from_provider(self._provider, **kwargs)
            except Exception as exc:
                logger.warning(f"业务验收 LLM 客户端初始化失败: {exc}")
        return self._llm_client

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

        # 🔬 日志：输出所有验收规则，便于追踪字段名变化
        check_summary = []
        for c in generated_checks:
            check_summary.append(f"  {c.check_type}:{c.name} field={c.field or '-'} blocking={c.blocking}")
        logger.info(
            "🔬 [BusinessVerifier] 验收规则汇总(%d条) | tool_id=%s:\n%s",
            len(generated_checks),
            spec.tool_id,
            "\n".join(check_summary),
        )

        for check in generated_checks:
            self._apply_check(result, output, check)

        # 数值合理性检查：检测明显错误的输出
        self._apply_plausibility_checks(result, output, spec)

        # LLM 业务验收：用 LLM 判断数据矛盾和业务合理性（准确判断，不靠关键词/正则）
        self._apply_llm_business_check(result, output, sandbox_result, spec, fact_report)

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
            # 🔧 spec 是权威来源，其 required_field 检查优先于 fact_report（侦察结果可能有字段名幻觉）
            spec_has_required_fields = any(
                c.check_type == "required_field" for c in raw_checks
            )
            for check in fact_report.validation_checks:
                if check.name and check.name in existing_names:
                    continue
                # 🔧 如果 spec 已有 required_field 检查，跳过 fact_report 中所有 required_field，
                #    避免 LLM 侦察输出的字段名与 spec 冲突导致验收规则左右互搏
                if spec_has_required_fields and check.check_type == "required_field":
                    logger.info(
                        "🔬 [_resolve_generated_checks] 跳过 fact_report required_field: name=%s field=%s (spec 已有 required_field，以 spec 为准)",
                        check.name,
                        check.field,
                    )
                    continue
                raw_checks.append(check)

        logger.info(
            "🔬 [_resolve_generated_checks] spec_checks=%d fact_report_checks=%d total_raw=%d | tool_id=%s",
            len(spec.validation_checks or []),
            len(fact_report.validation_checks if fact_report else []),
            len(raw_checks),
            spec.tool_id,
        )

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
            elif isinstance(output, list):
                # list[dict] 输出（expected_output.type="list[dict]"）没有 status 字段契约，
                # 沙箱执行成功即视为成功形态；此前误将 list 判为失败导致正确实现被误杀
                status = "success"
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
        if isinstance(output, list):
            # list[dict] 输出：字段检查针对记录本身，返回列表由 _resolve_sample
            # 取首条记录检查；此前 list 直接返回 None 导致全部字段检查误判失败
            return output
        return None

    @staticmethod
    def _resolve_sample(target: Any) -> Any:
        if isinstance(target, list):
            return target[0] if target else None
        return target

    @staticmethod
    def _apply_plausibility_checks(
        result: BusinessVerificationResult,
        output: Any,
        spec: SkillSpec,
    ) -> None:
        """数值合理性检查：检测明显错误的结果（如全零数据）"""
        if not isinstance(output, dict):
            return

        def _collect_numeric_values(obj: Any, path: str = "") -> Dict[str, float]:
            """递归收集所有数值字段及其路径。

            跳过 raw_data / raw 原始回显字段：它们是外部接口的完整原始返回
            （溯源用途），内部存在大量与业务无关的恒零噪声字段（如懂车帝榜单
            的 score/descender_price），不应参与业务数值合理性判断。
            """
            values: Dict[str, float] = {}
            if isinstance(obj, dict):
                for k, v in obj.items():
                    if str(k).lower() in ("raw_data", "raw"):
                        continue
                    full_path = f"{path}.{k}" if path else k
                    if isinstance(v, (int, float)) and not isinstance(v, bool):
                        values[full_path] = float(v)
                    elif isinstance(v, dict):
                        values.update(_collect_numeric_values(v, full_path))
                    elif isinstance(v, list) and v:
                        # 列表中每个元素都检查
                        for i, item in enumerate(v):
                            if isinstance(item, dict):
                                values.update(_collect_numeric_values(item, f"{full_path}[{i}]"))
            return values

        numeric_fields = _collect_numeric_values(output)
        if not numeric_fields:
            return  # 没有数值字段，跳过

        # 检查：超过 3 个关键数值字段全部为 0
        zero_fields = [k for k, v in numeric_fields.items() if v == 0.0]
        total_fields = len(numeric_fields)

        if total_fields >= 3 and len(zero_fields) >= total_fields * 0.7:
            # 超过 70% 的数值字段为 0，很可能是计算逻辑错误
            sample = list(zero_fields)[:5]
            msg = (
                f"数值合理性失败：{len(zero_fields)}/{total_fields} 个数值字段为 0 "
                f"（如 {', '.join(sample)}），可能是计算逻辑错误而非真实数据"
            )
            result.failures.append(
                BusinessRuleFailure(
                    rule_id="all_zero_values",
                    message=msg,
                    severity="error",
                )
            )
            result.details["zero_value_fields"] = len(zero_fields)
            result.details["total_numeric_fields"] = total_fields
            return

        # 检查：嵌套字段全零（如 trend/series 列表中每项数值都为 0）
        list_zero_count = 0
        for k, v in numeric_fields.items():
            if "[0]" in k or "[1]" in k or "[2]" in k:
                if v == 0.0:
                    list_zero_count += 1

        if list_zero_count >= 3 and total_fields >= 5:
            msg = (
                f"数值合理性失败：列表内数据全部为 0（共 {list_zero_count} 个零值），"
                "趋势/序列类数据不可能全为 0，数据获取或计算逻辑有误"
            )
            result.failures.append(
                BusinessRuleFailure(
                    rule_id="trend_list_all_zeros",
                    message=msg,
                    severity="error",
                )
            )
            result.details["trend_zero_count"] = list_zero_count

    def _apply_llm_business_check(
        self,
        result: BusinessVerificationResult,
        output: Any,
        sandbox_result: SandboxResult,
        spec: SkillSpec,
        fact_report: Optional[ImplementationFactReport],
    ) -> None:
        """LLM 业务验收 — 简单内联 prompt 模式，所有证据一次性传入"""
        client = self._get_client()
        if client is None:
            logger.warning("业务验收 LLM 客户端不可用，跳过 LLM 业务验收")
            return

        logger.info(f"🤖 [BusinessVerifier] LLM 业务验收启动 | tool_id={spec.tool_id}")

        test_symbol = spec.test_input.get("symbol", "") or spec.test_input.get("code", "")
        test_name = spec.test_input.get("name", "") or spec.test_input.get("display_name", "")

        # 准备输出摘要
        try:
            output_str = json.dumps(output, ensure_ascii=False, indent=2, default=str)[:4000]
        except Exception:
            output_str = str(output)[:4000]

        # 构建 helper 清单
        helpers_block = "（无 helper）"
        if fact_report and fact_report.available_helpers:
            lines = []
            for h in fact_report.available_helpers:
                ds_tag = getattr(h, 'data_source_handling', 'self_contained') or 'self_contained'
                sig = getattr(h, 'signature', '') or '(无签名)'
                lines.append(f"  {h.name}: {sig} [{ds_tag}]")
            if lines:
                helpers_block = "\n".join(lines)

        # 构建日志摘要（取最后 60 行）
        log_block = "（无日志）"
        if sandbox_result.stdout:
            log_lines = sandbox_result.stdout.strip().split("\n")
            log_block = "\n".join(log_lines[-60:])

        # 构建内联 user message
        # ⚠️ 必须注入当前系统日期：LLM 对"当前时间"的感知来自训练数据（常滞后数月），
        # 曾据此把已完结月份误判为"未来月份"，导致正确实现被反复误杀
        from datetime import datetime as _dt
        current_date = _dt.now().strftime("%Y-%m-%d")
        user_msg = (
            f"当前系统日期: {current_date}（判断任何时间合理性问题时必须以此为准，"
            f"严禁使用你训练记忆中的时间）\n"
            f"测试标的: {test_symbol} {test_name}\n"
            f"Skill 功能: {spec.description}\n\n"
            f"【沙箱执行结果】\n"
            f"  success: {sandbox_result.success}\n"
            f"  error: {sandbox_result.error or '无'}\n"
            f"  输出摘要: {output_str}\n\n"
            f"【沙箱日志（最后 60 行）】\n{log_block}\n\n"
            f"【已确认可用的 helper 函数】\n{helpers_block}\n\n"
            f"判断要点：\n"
            f"1. 日志中的数据是否与输出矛盾？(helper 有数据但输出为空 → has_contradiction=true)\n"
            f"2. 输出是否业务合理？(蓝筹股无质押数据 → is_business_valid=true)\n"
            f"3. success=True 说明代码已成功执行，函数必然存在。\n"
            f"4. 时间合理性以最上方的【当前系统日期】为基准：早于或等于该日期的查询周期"
            f"均为合法的历史/当前周期，不得判为'未来月份'。\n"
            f"5. 🚨 跨 helper 一致性检查：如果 Skill 调用了多个 helper，\n"
            f"   检查它们的返回是否互相矛盾。例如：\n"
            f"   - 一个 helper 说'无质押'（status=no_pledge），另一个返回了质押股东列表 → has_contradiction=true, severity=critical\n"
            f"   - 一个 helper 返回空趋势序列，另一个返回非空数据 → has_contradiction=true\n"
            f"   - 两个 helper 对同一指标给出不同数值 → has_contradiction=true\n\n"
            f"输出格式，只输出以下，不要其他内容：\n"
            f"<verdict>\n"
            f'{{"has_contradiction": true/false, "is_business_valid": true/false, '
            f'"severity": "none/minor/major/critical", "issue": "一句话", "suggestion": "修复建议"}}\n'
            f"</verdict>"
        )

        try:
            import queue
            import threading

            result_queue: "queue.Queue[tuple[str, Any]]" = queue.Queue(maxsize=1)

            def _worker() -> None:
                try:
                    messages = [
                        Message(role="system", content="你是金融数据审计专家。判断 Skill 工具的执行结果是否存在数据矛盾或业务不合理。严格按格式输出 <verdict> JSON。"),
                        Message(role="user", content=user_msg),
                    ]
                    response = client.chat(messages, temperature=0.0, max_tokens=2048)
                    result_queue.put(("ok", response.content or ""))
                except Exception as exc:
                    result_queue.put(("error", exc))

            worker = threading.Thread(
                target=_worker, name=f"biz-verify-{spec.tool_id}", daemon=True
            )
            worker.start()
            worker.join(BUSINESS_LLM_TIMEOUT_SECONDS)

            if worker.is_alive():
                logger.warning(
                    f"业务验收 LLM 判断超时（{BUSINESS_LLM_TIMEOUT_SECONDS}s），跳过 | tool_id={spec.tool_id}"
                )
                return

            status, payload = result_queue.get_nowait()
            if status == "error":
                raise payload
            raw = str(payload)

            if not raw:
                logger.warning("业务验收 LLM 返回空内容，跳过")
                return

            logger.info(f"📥 [BusinessVerifier] LLM 输出: {raw[:500]}")

            # 解析 JSON：优先从 <verdict> 标签中提取
            import re
            verdict_match = re.search(r"<verdict>\s*(.*?)\s*</verdict>", raw, re.DOTALL)
            if verdict_match:
                json_str = verdict_match.group(1).strip()
            else:
                json_match = re.search(r"\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}", raw, re.DOTALL)
                json_str = json_match.group() if json_match else ""

            if not json_str:
                logger.warning(f"业务验收 LLM 输出无法解析为 JSON: {raw[:300]}")
                return

            try:
                verdict = json.loads(json_str)
            except json.JSONDecodeError as je:
                logger.warning(f"业务验收 LLM JSON 解析失败: {je} | json_str={json_str[:200]}")
                return

            has_contradiction = bool(verdict.get("has_contradiction", False))
            is_business_valid = bool(verdict.get("is_business_valid", True))
            severity = str(verdict.get("severity", "none")).lower()
            issue = str(verdict.get("issue", "")).strip()
            suggestion = str(verdict.get("suggestion", "")).strip()

            result.details["llm_business_check"] = {
                "has_contradiction": has_contradiction,
                "is_business_valid": is_business_valid,
                "severity": severity,
                "issue": issue,
                "suggestion": suggestion,
            }

            # 数据矛盾 → 直接判为失败（阻断）
            if has_contradiction:
                msg = f"数据矛盾（LLM 判断）: {issue}"
                if suggestion and suggestion != "无":
                    msg += f" | 修复建议: {suggestion}"
                result.failures.append(
                    BusinessRuleFailure(
                        rule_id="llm_data_contradiction",
                        message=msg,
                        severity="error",
                    )
                )
                logger.warning(f"🚨 [BusinessVerifier] LLM 检测到数据矛盾: {issue}")
            elif not is_business_valid and severity in ("major", "critical"):
                msg = f"业务不合理（LLM 判断）: {issue}"
                if suggestion and suggestion != "无":
                    msg += f" | 修复建议: {suggestion}"
                result.failures.append(
                    BusinessRuleFailure(
                        rule_id="llm_business_invalid",
                        message=msg,
                        severity="error",
                    )
                )
                logger.warning(f"🚨 [BusinessVerifier] LLM 判断业务不合理: {issue}")
            elif severity == "minor":
                result.warnings.append(f"LLM 业务验收建议: {issue}")
                logger.info(f"ℹ️ [BusinessVerifier] LLM 发现小问题: {issue}")
            else:
                logger.info(f"✅ [BusinessVerifier] LLM 业务验收通过: {issue}")

        except Exception as exc:
            logger.warning(f"业务验收 LLM 判断异常: {exc}", exc_info=True)


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

    def __init__(
        self,
        llm_client: Optional[UnifiedLLMClient] = None,
        provider: Optional[str] = None,
        model: Optional[str] = None,
    ):
        self._llm_client = llm_client
        self._provider = provider
        self._model = model

    def resolve(self, spec: SkillSpec) -> BusinessVerifier:
        return DefaultBusinessVerifier(
            llm_client=self._llm_client,
            provider=self._provider,
            model=self._model,
        )

    def list_rule_families(self) -> List[str]:
        return ["default"]