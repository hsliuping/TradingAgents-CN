"""Skill 生成前置侦察层 — LLM 驱动 + 工具调用模式。

侦察层在代码生成前运行，通过 LLM function-calling 自主探索：
- 数据库集合的字段和覆盖率
- skill_runtime 公开 helper 的签名和用途
- 指定股票的样本数据

产出结构化 ImplementationFactReport，供 CodeGenerator 消费。
"""

from __future__ import annotations

import inspect
import json
import logging
import time
from functools import wraps
from typing import Any, Dict, List, Optional

from .recon_tools import RECON_TOOLS
from .requirement_analyzer import RequirementAnalyzer
from .data_contracts import build_data_contract_doc_for_skill
from .financial_schema_context import build_schema_generated_checks, resolve_financial_schema_context
from core.skill_runtime import build_factor_catalog_prompt_context
from .skill_spec import (
    ImplementationFact,
    ImplementationFactReport,
    ImplementationHelper,
    ImplementationIssue,
    ReconToolTrace,
    SkillSpec,
    ValidationCheck,
)

logger = logging.getLogger(__name__)

# LLM 侦察最大工具调用轮数
MAX_RECON_TOOL_ROUNDS = 10


class ReconnaissanceController:
    """前置侦察层接口。"""

    def analyze(self, spec: SkillSpec) -> ImplementationFactReport:
        raise NotImplementedError


class DefaultReconnaissanceController(ReconnaissanceController):
    """LLM 驱动的侦察层实现。

    Phase 1（规则基线）：利用 RequirementAnalyzer 做静态推断，生成初始事实。
    Phase 2（LLM 探索）：通过 UnifiedLLMClient + 工具调用，让 LLM 自主决定
    查看哪些集合 schema、调用哪些 helper 描述、检查哪些字段覆盖率。
    最终将 LLM 输出解析为 ImplementationFactReport。

    如果 LLM 客户端不可用或调用失败，自动降级为纯规则模式。
    """

    def __init__(
        self,
        llm_client=None,
        provider: str = "deepseek",
        model: Optional[str] = None,
        analyzer: Optional[RequirementAnalyzer] = None,
    ):
        self._llm_client = llm_client
        self._provider = provider
        self._model = model
        self._analyzer = analyzer or RequirementAnalyzer()

    def _get_client(self):
        """获取或延迟创建 LLM 客户端。"""
        if self._llm_client is None:
            try:
                from core.llm import UnifiedLLMClient
                kwargs = {}
                if self._model:
                    kwargs["model"] = self._model
                self._llm_client = UnifiedLLMClient.from_provider(self._provider, **kwargs)
            except Exception as exc:
                logger.warning("⚠️ 侦察层无法创建 LLM 客户端，将降级为规则模式: %s", exc)
                return None
        return self._llm_client

    def analyze(self, spec: SkillSpec) -> ImplementationFactReport:
        # Phase 1: 规则基线（快速、零成本）
        rule_report = self._rule_based_analyze(spec)

        # Phase 2: LLM 探索（增量增强）
        client = self._get_client()
        if client is None:
            logger.info("🧭 侦察层降级为纯规则模式（无 LLM 客户端）")
            return rule_report

        try:
            llm_report = self._llm_driven_analyze(client, spec, rule_report)
            return llm_report
        except Exception as exc:
            logger.warning("⚠️ LLM 侦察失败，降级为规则模式: %s", exc)
            return rule_report

    @staticmethod
    def _extract_probe_symbol(spec: SkillSpec) -> Optional[str]:
        test_input = spec.test_input or {}
        symbol_candidates = [
            test_input.get("symbol"),
            test_input.get("stock_code"),
            test_input.get("code"),
            test_input.get("ticker"),
        ]
        for item in symbol_candidates:
            normalized = DefaultReconnaissanceController._normalize_symbol(item)
            if normalized:
                return normalized
        for parameter in spec.parameters:
            normalized = DefaultReconnaissanceController._normalize_symbol(parameter.default)
            if normalized:
                return normalized
        return None

    @staticmethod
    def _normalize_symbol(value: Any) -> Optional[str]:
        text = str(value or "").strip()
        digits = "".join(ch for ch in text if ch.isdigit())
        if len(digits) == 6:
            return digits
        return None

    @staticmethod
    def _build_strategy(spec: SkillSpec, recommendations: dict) -> str:
        local_collections = recommendations.get("stock_collections") or []
        external_sources = recommendations.get("external_sources") or []
        strategy = ["优先使用 skill_runtime 公开接口和本地已同步数据"]
        if local_collections:
            strategy.append(f"优先关注本地集合: {', '.join(local_collections[:3])}")
        if external_sources:
            strategy.append(f"外部来源仅作为补充侦察依据: {', '.join(external_sources[:3])}")
        if "估值" in spec.description or any(k in spec.description.lower() for k in ("valuation", "peg", "pb", "pe", "dcf")):
            strategy.append("先确认价格、财务口径和增长率路径，再固化估值公式")
        return "；".join(strategy)

    @staticmethod
    def _infer_helpers(spec: SkillSpec) -> list[ImplementationHelper]:
        normalized = f"{spec.display_name} {spec.description} {spec.category}".lower()
        helpers: list[ImplementationHelper] = []
        if any(k in normalized for k in ("valuation", "估值", "peg", "pb", "pe", "ps", "dcf")):
            helpers.append(
                ImplementationHelper(
                    module="core.skill_runtime.data_access",
                    name="get_stock_valuation_context",
                    signature="symbol: str, *, lookback_days: int = 90",
                    description="估值类 Skill 的标准输入入口，可一次获得现价、估值指标和财务数据",
                    reason="估值类 Skill 的标准输入入口，可一次获得现价、估值指标和财务数据",
                )
            )
        if any(k in normalized for k in ("行业", "peer", "relative", "同行", "pb", "pe", "ps")):
            helpers.append(
                ImplementationHelper(
                    module="core.skill_runtime.data_access",
                    name="summarize_industry_valuation",
                    signature="industry: str, *, top_n: int = 10",
                    description="相对估值和行业统计优先复用现有行业估值汇总 helper",
                    reason="相对估值和行业统计优先复用现有行业估值汇总 helper",
                )
            )
        return helpers

    @staticmethod
    def _infer_blocked_paths(spec: SkillSpec) -> list[ImplementationIssue]:
        normalized = f"{spec.display_name} {spec.description} {spec.category}".lower()
        issues = [
            ImplementationIssue(
                path="direct provider import",
                reason="生成的 Skill 不应直接导入 tradingagents.dataflows.provider/interface，应通过 skill_runtime 公开接口访问",
                severity="error",
            )
        ]
        if any(k in normalized for k in ("valuation", "估值", "peg", "pb", "pe", "dcf")):
            issues.append(
                ImplementationIssue(
                    path="default zero valuation outputs",
                    reason="估值类 Skill 缺少关键输入时不得输出 fair_value=0、peg_value=0 等伪完成结果",
                    severity="error",
                )
            )
        return issues

    @staticmethod
    def _infer_validation_checks(spec: SkillSpec) -> list[ValidationCheck]:
        if spec.validation_checks:
            return list(spec.validation_checks)

        checks: list[ValidationCheck] = [
            ValidationCheck(
                name="status_success",
                description="输出状态必须为 success/ok，不能以 error 或伪成功结束",
                check_type="status_success",
                rule_level="output",
                blocking=True,
                value_path="output",
                forbid_null=False,
            )
        ]
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

    @staticmethod
    def _infer_notes(spec: SkillSpec, recommendations: dict) -> list[str]:
        notes: list[str] = []
        if recommendations.get("external_sources"):
            notes.append("外部数据源在侦察阶段可用于确认实现路径，但不代表最终 Skill 可以直接依赖其内部 provider。")
        if spec.expected_output.fields:
            notes.append(f"期望输出字段: {', '.join(spec.expected_output.fields)}")
        return notes

    @staticmethod
    def _enrich_schema_bundle_guidance(
        report: ImplementationFactReport,
        schema_context: Dict[str, Any],
    ) -> None:
        report.schema_bundle_context = dict(schema_context)
        report.confidence = max(report.confidence, 0.72)

        method = schema_context.get("method") or {}
        contract = schema_context.get("contract") or {}
        verifier_rule = schema_context.get("verifier_rule") or {}
        applicability_rules = schema_context.get("applicability_rules") or {}

        method_id = str(schema_context.get("method_id") or method.get("id") or "")
        method_name = str(method.get("name") or method_id or "schema_method")
        method_objective = str(method.get("objective") or "").strip()
        if method_name:
            if method_objective:
                report.schema_facts.append(
                    ImplementationFact(
                        source=method_id or method_name,
                        fact=f"优先按 {method_name} 组织实现: {method_objective}",
                        evidence="financial_schema_bundle",
                    )
                )
            report.recommended_strategy = (
                f"{report.recommended_strategy}；按 {method_name} 组织输入校验、指标计算和输出结论"
                if report.recommended_strategy
                else f"按 {method_name} 组织输入校验、指标计算和输出结论"
            )

        required_metrics = list(method.get("required_metrics") or [])
        if required_metrics:
            report.schema_facts.append(
                ImplementationFact(
                    source=method_id or method_name,
                    fact=f"方法要求优先获取指标: {', '.join(required_metrics)}",
                    evidence="financial_schema_bundle",
                )
            )

        required_fields = list(method.get("required_fields") or [])
        if required_fields:
            report.schema_facts.append(
                ImplementationFact(
                    source=method_id or method_name,
                    fact=f"方法要求检查输入字段: {', '.join(required_fields)}",
                    evidence="financial_schema_bundle",
                )
            )

        contract_id = str(schema_context.get("contract_id") or contract.get("id") or "")
        contract_required_fields = [
            str((field_def or {}).get("field_name") or "").strip()
            for field_def in contract.get("required_fields") or []
            if str((field_def or {}).get("field_name") or "").strip()
        ]
        if contract_required_fields:
            report.schema_facts.append(
                ImplementationFact(
                    source=contract_id or "output_contract",
                    fact=f"输出必须覆盖契约字段: {', '.join(contract_required_fields)}",
                    evidence="financial_schema_bundle",
                )
            )

        narrative_requirements = [str(item).strip() for item in contract.get("narrative_requirements") or [] if str(item).strip()]
        if narrative_requirements:
            report.notes.append(f"schema 输出叙述要求: {'; '.join(narrative_requirements[:4])}")

        prohibited_patterns = [str(item).strip() for item in contract.get("prohibited_patterns") or [] if str(item).strip()]
        if prohibited_patterns:
            for pattern in prohibited_patterns[:3]:
                report.blocked_paths.append(
                    ImplementationIssue(
                        path=f"schema_contract:{contract_id or 'output_contract'}",
                        reason=pattern,
                        severity="error",
                    )
                )

        verifier_id = str(schema_context.get("verifier_rule_id") or verifier_rule.get("id") or "")
        failure_message = str(verifier_rule.get("failure_message") or "").strip()
        if failure_message:
            report.notes.append(f"schema verifier 失败语义: {failure_message}")
        remediation_hint = str(verifier_rule.get("remediation_hint") or "").strip()
        if remediation_hint:
            report.notes.append(f"schema verifier 修复提示: {remediation_hint}")

        for rule_id, rule_object in applicability_rules.items():
            human_description = str(rule_object.get("human_description") or rule_id).strip()
            report.schema_facts.append(
                ImplementationFact(
                    source=rule_id,
                    fact=f"适用性规则: {human_description}",
                    evidence="financial_schema_bundle",
                )
            )
            rationale = str(rule_object.get("rationale") or "").strip()
            if rationale:
                report.notes.append(f"{rule_id}: {rationale}")

        existing_names = {item.name for item in report.validation_checks if item.name}
        for check in build_schema_generated_checks(schema_context):
            if check.name and check.name in existing_names:
                continue
            report.validation_checks.append(check)
            if check.name:
                existing_names.add(check.name)

        if verifier_id:
            report.notes.append(f"schema profile: {schema_context.get('profile')} / {verifier_id}")

    # ================================================================
    # Phase 1: 规则基线（零 LLM 成本）
    # ================================================================

    def _rule_based_analyze(self, spec: SkillSpec) -> ImplementationFactReport:
        """纯规则驱动的侦察，作为 LLM 侦察的基线和降级方案。"""
        from core.skill_runtime.project_access import (
            inspect_field_coverage,
            inspect_stock_collection_schema,
            inspect_symbol_documents,
        )

        recommendations = self._analyzer.build_recommendations(spec=spec)
        report = ImplementationFactReport(
            task_summary=spec.description,
            recommended_strategy=self._build_strategy(spec, recommendations),
            confidence=0.45,
        )
        symbol = self._extract_probe_symbol(spec)

        for collection in recommendations.get("stock_collections") or []:
            report.schema_facts.append(
                ImplementationFact(
                    source=collection,
                    fact=f"推荐优先复用本地集合 {collection}",
                    evidence="RequirementAnalyzer.build_recommendations",
                )
            )
            self._enrich_collection_facts(
                report,
                collection,
                symbol,
                inspect_stock_collection_schema,
                inspect_field_coverage,
                inspect_symbol_documents,
            )

        for source in recommendations.get("external_sources") or []:
            report.schema_facts.append(
                ImplementationFact(
                    source=source,
                    fact=f"若本地数据不足，可优先考虑文档化的数据源 {source}",
                    evidence="RequirementAnalyzer.build_recommendations",
                )
            )

        report.available_helpers.extend(self._infer_helpers(spec))
        report.blocked_paths.extend(self._infer_blocked_paths(spec))
        report.validation_checks.extend(self._infer_validation_checks(spec))
        report.notes.extend(self._infer_notes(spec, recommendations))
        schema_context = resolve_financial_schema_context(spec)
        if schema_context:
            self._enrich_schema_bundle_guidance(report, schema_context)
        if report.sample_fields:
            report.confidence = max(report.confidence, 0.65)
        return report

    @staticmethod
    def _enrich_collection_facts(
        report: ImplementationFactReport,
        collection: str,
        symbol: Optional[str],
        inspect_schema_fn=None,
        inspect_coverage_fn=None,
        inspect_symbol_fn=None,
    ) -> None:
        """利用 project_access 函数丰富集合事实。"""
        if inspect_schema_fn is None:
            return
        try:
            schema_summary = inspect_schema_fn(collection, sample_size=12)
        except Exception as exc:
            report.runtime_gaps.append(
                ImplementationIssue(path=collection, reason=f"无法读取集合 schema 摘要: {exc}", severity="warning")
            )
            return

        sample_count = int(schema_summary.get("sample_count") or 0)
        top_fields = list(schema_summary.get("top_level_fields") or [])
        if sample_count <= 0:
            report.runtime_gaps.append(
                ImplementationIssue(path=collection, reason="集合暂无可用样本，无法做字段侦察", severity="warning")
            )
            return

        if top_fields:
            report.sample_fields[collection] = top_fields
            preview_fields = ", ".join(top_fields[:6])
            report.schema_facts.append(
                ImplementationFact(source=collection, fact=f"样本字段包括: {preview_fields}", evidence="inspect_stock_collection_schema")
            )
            if inspect_coverage_fn:
                try:
                    coverage_summary = inspect_coverage_fn(collection, top_fields[:min(6, len(top_fields))], sample_size=max(sample_count, 12))
                    coverage_parts = [f"{item.get('field')}={item.get('non_null_coverage', 0.0):.0%}" for item in coverage_summary.get("fields") or []]
                    if coverage_parts:
                        report.notes.append(f"{collection} 字段非空覆盖率: {', '.join(coverage_parts[:6])}")
                except Exception:
                    pass

        if not symbol or not inspect_symbol_fn:
            return
        try:
            symbol_docs = inspect_symbol_fn(collection, symbol, limit=2)
        except Exception as exc:
            report.runtime_gaps.append(
                ImplementationIssue(path=collection, reason=f"无法读取 symbol={symbol} 的样本: {exc}", severity="warning")
            )
            return
        symbol_documents = []
        if isinstance(symbol_docs, dict):
            symbol_documents = list(symbol_docs.get("documents") or [])
        elif isinstance(symbol_docs, list):
            symbol_documents = list(symbol_docs)

        if symbol_documents:
            first_doc = symbol_documents[0] if isinstance(symbol_documents[0], dict) else {}
            symbol_fields = list(first_doc.keys())
            matched_count = None
            if isinstance(symbol_docs, dict):
                matched_count = symbol_docs.get("matching_document_count")

            matched_text = f"，命中 {matched_count} 条" if matched_count is not None else ""
            report.notes.append(
                f"{collection} 中存在 {symbol} 的样本记录{matched_text}，首条摘要字段: {', '.join(symbol_fields)}"
            )
            existing = set(report.sample_fields.get(collection, []))
            new_fields = [f for f in symbol_fields if f not in existing]
            if new_fields and collection in report.sample_fields:
                report.sample_fields[collection].extend(new_fields)
        else:
            report.notes.append(f"{collection} 中未找到 {symbol} 的直接样本记录")

    # ================================================================
    # Phase 2: LLM 驱动侦察
    # ================================================================

    def _llm_driven_analyze(
        self, client, spec: SkillSpec, rule_report: ImplementationFactReport
    ) -> ImplementationFactReport:
        """通过 LLM function-calling 自主探索，产出增强版事实报告。"""
        from core.llm import Message

        start_time = time.time()
        tool_traces: List[ReconToolTrace] = []

        # 注册侦察工具
        tool_defs = []
        for func in self._build_traced_tools(tool_traces):
            td = client.register_tool(func)
            tool_defs.append(td)

        # 构建侦察 prompt
        system_prompt = self._build_recon_system_prompt()
        user_prompt = self._build_recon_user_prompt(spec, rule_report)

        messages = [
            Message(role="system", content=system_prompt),
            Message(role="user", content=user_prompt),
        ]

        logger.info(
            f"\n{'─'*50}\n"
            f"🧭 [侦察层] LLM 侦察开始 | tool_id={spec.tool_id}\n"
            f"{'─'*50}\n"
            f"📋 System Prompt ({len(system_prompt)} 字符):\n{system_prompt[:3000]}\n"
            f"{'...(截断)' if len(system_prompt) > 3000 else ''}\n"
            f"{'─'*50}\n"
            f"📝 User Prompt ({len(user_prompt)} 字符):\n{user_prompt[:2000]}\n"
            f"{'...(截断)' if len(user_prompt) > 2000 else ''}\n"
            f"🔧 可用工具: {[td['function']['name'] for td in tool_defs]}\n"
            f"{'─'*50}"
        )

        # 执行工具调用循环
        try:
            response = client.chat(
                messages,
                tools=tool_defs,
                auto_execute_tools=True,
                max_tool_rounds=MAX_RECON_TOOL_ROUNDS,
            )
        except Exception:
            self._log_tool_trace_summary(spec.tool_id, tool_traces, failed=True)
            raise

        elapsed = time.time() - start_time
        raw_output = response.content or ""

        logger.info(
            f"\n{'─'*50}\n"
            f"📥 [侦察层] LLM 输出 ({len(raw_output)} 字符, {elapsed:.1f}s)\n"
            f"{'─'*50}\n"
            f"{raw_output[:3000]}\n"
            f"{'...(截断)' if len(raw_output) > 3000 else ''}\n"
            f"{'─'*50}"
        )

        # 解析 LLM 输出为 ImplementationFactReport
        report = self._parse_llm_report(raw_output, spec, rule_report)
        report.tool_traces = tool_traces
        report.confidence = max(report.confidence, 0.75)
        report.notes.append(f"工具调用次数: {len(tool_traces)}")
        report.notes.append(f"侦察耗时: {elapsed:.1f}s（LLM 驱动）")
        self._log_tool_trace_summary(spec.tool_id, tool_traces, failed=False)
        return report

    @staticmethod
    def _truncate_log_text(text: str, limit: int = 1600) -> str:
        raw = str(text or "")
        if len(raw) <= limit:
            return raw
        head = raw[:1000]
        tail = raw[-400:]
        return f"{head}\n...(中间省略 {len(raw) - 1400} 字符)...\n{tail}"

    @classmethod
    def _log_tool_trace_summary(
        cls,
        tool_id: str,
        tool_traces: List[ReconToolTrace],
        *,
        failed: bool,
    ) -> None:
        if not tool_traces:
            logger.info("🧭 [侦察层] 无工具调用轨迹 | tool_id=%s | failed=%s", tool_id, failed)
            return

        logger.info(
            "🧭 [侦察层] 工具调用轨迹汇总 | tool_id=%s | count=%s | failed=%s",
            tool_id,
            len(tool_traces),
            failed,
        )
        for index, trace in enumerate(tool_traces, start=1):
            logger.info(
                "🧭 [侦察层] 工具轨迹[%s] | tool=%s | success=%s | duration_ms=%s | result_chars=%s | args=%s\n%s",
                index,
                trace.tool_name,
                trace.success,
                trace.duration_ms,
                trace.result_chars,
                json.dumps(trace.arguments or {}, ensure_ascii=False, default=str),
                cls._truncate_log_text(trace.result_preview or trace.error or ""),
            )

    @staticmethod
    def _build_traced_tools(tool_traces: List[ReconToolTrace]) -> List[callable]:
        traced_tools: List[callable] = []

        for func in RECON_TOOLS:
            @wraps(func)
            def traced_func(*args, __func=func, **kwargs):
                started = time.time()
                arguments: Dict[str, Any] = {}
                try:
                    bound = inspect.signature(__func).bind_partial(*args, **kwargs)
                    arguments = dict(bound.arguments)
                except Exception:
                    arguments = {"args": list(args), **kwargs}

                try:
                    logger.info(
                        "🧭 [侦察层] 调用工具 | tool=%s | args=%s",
                        __func.__name__,
                        json.dumps(arguments, ensure_ascii=False, default=str),
                    )
                    result = __func(*args, **kwargs)
                    preview = str(result)
                    logger.info(
                        "🧭 [侦察层] 工具返回 | tool=%s | chars=%s\n%s",
                        __func.__name__,
                        len(preview),
                        DefaultReconnaissanceController._truncate_log_text(preview),
                    )
                    tool_traces.append(
                        ReconToolTrace(
                            tool_name=__func.__name__,
                            arguments=arguments,
                            success=True,
                            duration_ms=round((time.time() - started) * 1000, 2),
                            result_chars=len(preview),
                            result_preview=preview[:400],
                        )
                    )
                    return result
                except Exception as exc:
                    logger.warning(
                        "🧭 [侦察层] 工具异常 | tool=%s | args=%s | error=%s",
                        __func.__name__,
                        json.dumps(arguments, ensure_ascii=False, default=str),
                        exc,
                    )
                    tool_traces.append(
                        ReconToolTrace(
                            tool_name=__func.__name__,
                            arguments=arguments,
                            success=False,
                            duration_ms=round((time.time() - started) * 1000, 2),
                            result_chars=0,
                            error=str(exc),
                        )
                    )
                    raise

            traced_tools.append(traced_func)

        return traced_tools

    # ================================================================
    # Prompt 构建 & 输出解析
    # ================================================================

    @staticmethod
    def _build_recon_system_prompt() -> str:
        return (
            "你是一个 Skill 代码生成前置侦察 Agent。\n"
            "你的任务是通过调用工具，收集最少但足够的实现事实，帮助后续代码生成器写出正确、可运行的 Python 函数。\n"
            "你不是在写研究报告，也不是在写方案说明书。你的职责只有三个：确认数据路径、确认 helper、确认禁止路径。\n\n"
            "## 工作流程\n"
            "### 第一阶段：本地数据探索\n"
            "1. 先用 list_available_collections 了解有哪些本地集合可用。\n"
            "2. 用 inspect_collection_schema 查看与任务相关的集合字段结构。\n"
            "3. 如果任务涉及具体股票，用 inspect_symbol_sample 查看样本数据，确认字段名和数据格式。\n"
            "4. 用 check_field_coverage 检查关键字段的覆盖率，判断数据可靠性。\n\n"
            "### 第二阶段：外部资源探索\n"
            "5. 用 list_external_data_sources 查看当前已配置的外部数据源（如 akshare、tushare、baostock）。\n"
            "   如果任务需要历史 K 线、实时行情、宏观数据等本地集合缺失的数据，外部数据源可能是关键实现路径。\n"
            "6. 用 list_mcp_tools 查看通过 MCP (Model Context Protocol) 注册的外部工具。\n"
            "   MCP 工具可能提供额外的数据获取或计算能力，如果有匹配任务需求的 MCP 工具，应优先推荐。\n\n"
            "### 第三阶段：Runtime Helper 探索\n"
            "7. 用 list_runtime_functions 和 describe_runtime_helper 查看可复用的 helper 函数。\n"
            "   重点关注 'data_access'（本地数据）、'project_access'（项目数据）、'external_sources'（外部数据源封装）三个模块。\n\n"
            "## 输出格式\n"
            "探索完成后，只输出一个纯 JSON 对象，不要前言、不要总结、不要 Markdown 代码块、不要解释性文字。\n"
            "JSON 只包含以下字段：\n"
            "{\n"
            '  "task_summary": "一句话总结任务需求（不超过50字）",\n'
            '  "recommended_strategy": "推荐实现路径（不超过120字）",\n'
            '  "available_helpers": [\n'
            '    {"module": "模块路径", "name": "函数名", "reason": "推荐理由"}\n'
            "  ],\n"
            '  "schema_facts": [\n'
            '    {"source": "集合/模块名/MCP工具名", "fact": "发现的事实", "evidence": "证据来源"}\n'
            "  ],\n"
            '  "sample_fields": {"集合名": ["字段1", "字段2"]},\n'
            '  "blocked_paths": [\n'
            '    {"path": "不可用路径", "reason": "原因", "severity": "error|warning"}\n'
            "  ],\n"
            '  "runtime_gaps": [\n'
            '    {"path": "缺口描述", "reason": "原因", "severity": "warning"}\n'
            "  ],\n"
            '  "validation_checks": [\n'
            '    {"name": "检查名", "description": "描述", "check_type": "status_success|required_field|required_non_empty_payload|input_validation|data_validation|custom", "rule_level": "input|output|data|business|warning", "blocking": true}\n'
            "  ],\n"
            '  "confidence": 0.0到1.0之间的置信度,\n'
            '  "notes": ["额外备注"]\n'
            "}\n"
            "\n"
            "## 输出收敛要求\n"
            "- task_summary 只写结果，不写背景。\n"
            "- recommended_strategy 只写最终推荐路径，不写推理过程。\n"
            "- available_helpers 最多 4 个。\n"
            "- schema_facts 最多 6 条，只保留对代码实现真正有影响的事实。\n"
            "- sample_fields 每个集合最多 8 个字段。\n"
            "- blocked_paths 最多 4 条。\n"
            "- runtime_gaps 最多 4 条。\n"
            "- validation_checks 只补充规格里没有但确实必须新增的规则；不要把已有规格规则原样重写一遍。\n"
            "- notes 最多 3 条。\n\n"
            "## 重要约束\n"
            "- 只做只读探测，不修改任何数据。\n"
            "- 探测时优先关注与任务直接相关的集合和函数。\n"
            "- 如果发现某个关键字段覆盖率很低或不存在，务必在 runtime_gaps 中标注。\n"
            "- 如果发现 MCP 工具或外部数据源能满足需求，在 schema_facts 和 recommended_strategy 中明确说明。\n"
            "- 生成的 Skill 不应直接导入内部 provider，应通过 skill_runtime 公开接口访问数据。\n"
            "- 不要输出‘完美’、‘我已经完成探索’、‘现在开始生成报告’之类前言。\n"
        )

    @staticmethod
    def _build_recon_user_prompt(spec: SkillSpec, rule_report: ImplementationFactReport) -> str:
        data_contract_doc = build_data_contract_doc_for_skill(spec)
        factor_catalog_doc = build_factor_catalog_prompt_context(
            spec.description,
            category=spec.category,
            expected_fields=list(spec.expected_output.fields or []),
        )
        parts = [
            f"## 待实现的 Skill\n"
            f"- tool_id: {spec.tool_id}\n"
            f"- 名称: {spec.display_name}\n"
            f"- 描述: {spec.description}\n"
            f"- 分类: {spec.category}\n",
        ]
        if spec.parameters:
            param_lines = [f"  - {p.name}: {p.type} (默认: {p.default})" for p in spec.parameters]
            parts.append(f"- 参数:\n" + "\n".join(param_lines))
        if spec.expected_output.fields:
            parts.append(f"- 期望输出字段: {', '.join(spec.expected_output.fields)}")
        if spec.test_input:
            parts.append(f"- 测试输入: {json.dumps(spec.test_input, ensure_ascii=False)}")

        # 附加规则基线已知的事实
        if rule_report.schema_facts:
            baseline_facts = [f"  - [{f.source}] {f.fact}" for f in rule_report.schema_facts[:5]]
            parts.append(f"\n## 规则基线已知事实（仅供参考，请用工具验证和补充）\n" + "\n".join(baseline_facts))
        if rule_report.available_helpers:
            helper_lines = [f"  - {h.module}.{h.name}: {h.reason}" for h in rule_report.available_helpers[:5]]
            parts.append(f"\n## 规则基线推荐 Helper\n" + "\n".join(helper_lines))
        if data_contract_doc:
            parts.append(f"\n## 任务相关数据契约\n{data_contract_doc}")
        if factor_catalog_doc:
            parts.append(
                "\n## 任务相关因子白名单\n"
                f"{factor_catalog_doc}\n"
                "请重点验证这些因子对应的 helper、字段路径和可复用 bundle 是否已经足够，不要把 catalog 里已有因子误判成新缺口。"
            )

        parts.append(
            "\n## 请求\n"
            "请先依据数据契约理解字段层级，再通过工具调用验证关键路径。输出时只保留会影响代码实现的最小事实集，不要写成长篇方案说明。"
        )
        return "\n".join(parts)

    @staticmethod
    def _parse_llm_report(
        raw_output: str,
        spec: SkillSpec,
        rule_report: ImplementationFactReport,
    ) -> ImplementationFactReport:
        """解析 LLM 输出文本，提取 JSON 并构建 ImplementationFactReport。

        解析策略：
        1. 尝试从 ```json ... ``` 代码块中提取。
        2. 尝试直接 json.loads 整段文本。
        3. 如果都失败，使用 rule_report 作为降级，并将 LLM 文本追加到 notes。
        """
        parsed: Optional[Dict[str, Any]] = None

        # 策略 1: 提取 ```json ... ``` 块
        import re
        json_blocks = re.findall(r"```(?:json)?\s*\n?(.*?)```", raw_output, re.DOTALL)
        for block in json_blocks:
            try:
                parsed = json.loads(block.strip())
                break
            except (json.JSONDecodeError, ValueError):
                continue

        # 策略 2: 直接尝试解析整段
        if parsed is None:
            try:
                parsed = json.loads(raw_output.strip())
            except (json.JSONDecodeError, ValueError):
                pass

        # 策略 3: 降级
        if not isinstance(parsed, dict):
            logger.warning("⚠️ 侦察层无法从 LLM 输出中解析 JSON，降级为规则报告")
            rule_report.notes.append(f"LLM 侦察输出未能解析为 JSON，已降级。原始输出前500字: {raw_output[:500]}")
            return rule_report

        # 从 parsed dict 构建 report
        report = ImplementationFactReport(
            task_summary=parsed.get("task_summary", spec.description),
            recommended_strategy=parsed.get("recommended_strategy", rule_report.recommended_strategy),
            confidence=float(parsed.get("confidence", 0.75)),
        )
        expected_fields = set(spec.expected_output.fields or [])

        # available_helpers
        for h in parsed.get("available_helpers") or []:
            if isinstance(h, dict) and h.get("name"):
                report.available_helpers.append(
                    ImplementationHelper(
                        module=h.get("module", ""),
                        name=h["name"],
                        reason=h.get("reason", ""),
                    )
                )

        # schema_facts
        for f in parsed.get("schema_facts") or []:
            if isinstance(f, dict) and f.get("fact"):
                report.schema_facts.append(
                    ImplementationFact(
                        source=f.get("source", ""),
                        fact=f["fact"],
                        evidence=f.get("evidence", ""),
                    )
                )

        # sample_fields
        for coll, fields in (parsed.get("sample_fields") or {}).items():
            if isinstance(fields, list):
                report.sample_fields[coll] = [str(f) for f in fields]

        # blocked_paths
        for issue in parsed.get("blocked_paths") or []:
            if isinstance(issue, dict):
                report.blocked_paths.append(
                    ImplementationIssue(
                        path=issue.get("path", ""),
                        reason=issue.get("reason", ""),
                        severity=issue.get("severity", "error"),
                    )
                )

        # runtime_gaps
        for issue in parsed.get("runtime_gaps") or []:
            if isinstance(issue, dict):
                report.runtime_gaps.append(
                    ImplementationIssue(
                        path=issue.get("path", ""),
                        reason=issue.get("reason", ""),
                        severity=issue.get("severity", "warning"),
                    )
                )

        # validation_checks
        for vc in parsed.get("validation_checks") or []:
            if isinstance(vc, dict):
                raw_type = str(vc.get("check_type", "custom") or "custom").strip().lower()
                field_name = str(vc.get("field", "") or "").strip()

                if raw_type in ("business", "business_check", "custom"):
                    report.notes.append(
                        f"忽略不可执行的业务描述规则: {vc.get('description') or vc.get('name') or raw_type}"
                    )
                    continue

                normalized_type = raw_type
                if raw_type in ("input_validation", "input", "input_check", "output", "output_check", "status"):
                    normalized_type = "status_success"
                elif raw_type in ("data_validation", "data", "data_check"):
                    normalized_type = "required_field" if field_name else "required_non_empty_payload"

                if normalized_type == "required_field" and field_name and expected_fields and field_name not in expected_fields:
                    report.notes.append(f"忽略未纳入规格输出的侦察字段规则: {field_name}")
                    continue

                report.validation_checks.append(
                    ValidationCheck(
                        name=vc.get("name", "") or (f"required_field:{field_name}" if normalized_type == "required_field" and field_name else normalized_type),
                        description=vc.get("description", ""),
                        required=vc.get("required", True),
                        check_type=normalized_type,
                        rule_level="output" if normalized_type == "status_success" else "data",
                        blocking=vc.get("blocking", True),
                        field=field_name,
                        value_path="output" if normalized_type == "status_success" else vc.get("value_path", "data"),
                        forbid_null=False if normalized_type == "status_success" else vc.get("forbid_null", False),
                    )
                )

        # notes
        for note in parsed.get("notes") or []:
            if isinstance(note, str):
                report.notes.append(note)

        # 补充 rule_report 中有但 LLM 报告缺失的关键信息
        if not report.blocked_paths and rule_report.blocked_paths:
            report.blocked_paths.extend(rule_report.blocked_paths)
        if not report.validation_checks and rule_report.validation_checks:
            report.validation_checks.extend(rule_report.validation_checks)

        existing_names = {item.name for item in report.validation_checks if item.name}
        for base_check in spec.validation_checks:
            if base_check.name and base_check.name in existing_names:
                continue
            report.validation_checks.append(base_check)

        deduped_checks: list[ValidationCheck] = []
        seen_names: set[str] = set()
        for check in report.validation_checks:
            dedupe_name = check.name or f"{check.check_type}:{check.field}"
            if dedupe_name in seen_names:
                continue
            seen_names.add(dedupe_name)
            deduped_checks.append(check)
        report.validation_checks = deduped_checks

        return report