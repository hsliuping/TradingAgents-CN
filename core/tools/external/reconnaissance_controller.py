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
# 由 10 调整为 6：rule_report 已通过向量搜索提供 helpers，LLM 只需补充验证，
# 不需要从头探索所有集合/模块。过多轮数会拖慢生成流程且收益递减。
MAX_RECON_TOOL_ROUNDS = 6


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

    def analyze(self, spec: SkillSpec, capability_hits: list = None) -> ImplementationFactReport:
        # Phase 1: 规则基线（快速、零成本）
        rule_report = self._rule_based_analyze(spec, capability_hits)

        # 【分层策略】根据 helper 数量决定是否启用 Phase 2
        # - 1-2 个 helper（如质押）：直接验证签名，跳过 LLM 探索
        # - 3+ 个 helper（如估值、现金流）：进入 Phase 2，但只做筛选，不允许探索新工具
        helper_count = len(rule_report.available_helpers)
        if helper_count <= 2:
            helper_names = [h.name for h in rule_report.available_helpers]
            logger.info(
                f"\n{'='*80}\n"
                f"✅ [侦察层优化] Phase 1 已找到 {helper_count} 个 helper，直接跳过 Phase 2\n"
                f"   已发现的 helper: {', '.join(helper_names)}\n"
                f"   置信度: {rule_report.confidence:.2f}\n"
                f"   理由: 少量 helper 场景无需 LLM 筛选\n"
                f"{'='*80}"
            )
            return rule_report

        # Phase 2: LLM 驱动筛选（仅当 helper >= 3 时启用）
        client = self._get_client()
        if client is None:
            logger.info("🧭 侦察层降级为纯规则模式（无 LLM 客户端）")
            return rule_report

        logger.info(
            f"\n{'='*80}\n"
            f"🔄 [侦察层] Phase 1 已找到 {helper_count} 个候选 helper，启动 Phase 2 LLM 筛选\n"
            f"   候选列表: {', '.join([h.name for h in rule_report.available_helpers])}\n"
            f"   任务: 从已知候选中筛选最相关的 3-4 个，不探索新工具\n"
            f"{'='*80}"
        )

        try:
            llm_report = self._llm_driven_analyze(
                client, spec, rule_report,
                has_many_helpers=True  # 多 helper 场景：只做筛选
            )
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

    # ==================== 需求类型分流（改进点 1） ====================

    @staticmethod
    def _classify_requirement_mode(spec: SkillSpec) -> str:
        """识别需求类型：external_api（外部 API 集成） / local_data（本地数据复用，默认）。

        判定逻辑统一实现在 requirement_analyzer.classify_requirement_mode，
        此处保留方法壳供侦察层内部与既有测试调用。
        """
        from .requirement_analyzer import classify_requirement_mode

        return classify_requirement_mode(spec)

    @staticmethod
    def _build_external_api_strategy(spec: SkillSpec, unknown_data_source: str = "") -> str:
        """external_api 模式的实现策略话术。"""
        source_name = unknown_data_source or (getattr(spec, "data_source", "") or "用户指定来源")
        return (
            f"本需求为外部 HTTP API 集成（数据源: {source_name}，不属于系统本地股票数据体系）。"
            "实现以直接调用该外部接口为主：requests/httpx + 合法请求头（UA/Referer）+ 超时与失败降级；"
            "不使用本地股票集合、不复用股票类 helper 作为数据来源。"
            "接口规格（URL、请求方式、参数、认证、返回字段）必须以用户确认的信息为准，"
            "未确认前不得臆造接口细节与字段名。"
        )

    # ==================== 验收字段一致性校验（改进点 3） ====================

    @staticmethod
    def _normalize_field_token(name: str) -> str:
        return "".join(ch for ch in str(name or "").lower() if ch.isalnum())

    def _validate_expected_field_coverage(
        self,
        spec: SkillSpec,
        report: ImplementationFactReport,
        requirement_mode: str,
    ) -> None:
        """校验 expected_output.fields 与命中资产的能力一致性。

        - local_data 模式：字段应能由 helper 返回字段 / 本地集合样本字段产出，
          覆盖率过低时降置信度并提示澄清（防止规格臆造字段）。
        - external_api 模式：字段来自外部接口实际响应，不做本地覆盖校验，
          只提示"字段须以接口实际响应为准、不得声明接口不存在的层级"。
        """
        expected_output = getattr(spec, "expected_output", None)
        expected = [str(f).strip() for f in (getattr(expected_output, "fields", None) or []) if str(f or "").strip()]
        if not expected:
            return

        if requirement_mode == "external_api":
            report.notes.append(
                "⚠️ 验收字段须以外部接口实际响应为准：expected_output.fields 不得包含接口未提供的字段"
                "（例如接口按车系 series 级返回时，不应声明 model_id/model_name/manufacturer_id 等"
                "接口不存在的层级字段）；字段清单需在规格确认时与用户核对。"
            )
            return

        # local_data 模式：收集命中资产可产出的字段池
        pool: set = set()
        for fields in (report.sample_fields or {}).values():
            pool.update(self._normalize_field_token(f) for f in fields or [])
        for helper in report.available_helpers:
            for fname in self._analyzer._extract_return_field_names(helper.description or ""):
                pool.add(self._normalize_field_token(fname))
        for fact in report.schema_facts:
            if fact.field:
                pool.add(self._normalize_field_token(fact.field))
        if not pool:
            return  # 无任何资产字段信息时不强判

        missing = [f for f in expected if self._normalize_field_token(f) not in pool]
        coverage = 1 - len(missing) / len(expected)
        if missing and coverage < 0.5:
            report.notes.append(
                f"⚠️ 验收字段覆盖不足（{len(expected) - len(missing)}/{len(expected)}）："
                f"{', '.join(missing[:8])} 无法由当前命中的 helper/本地集合产出。"
                "这些字段需由外部数据源或自行计算提供，规格确认前建议向用户澄清字段来源。"
            )
            report.confidence = min(report.confidence, 0.45)

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
                    data_source_handling="local_only",
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
                    data_source_handling="local_only",
                )
            )
        # 护城河/盈利稳定性/长期趋势类 Skill 优先复用 standard_financial_apis
        if any(k in normalized for k in ("moat", "护城河", "稳定性", "stability", "质量", "quality", "长期", "annual_series", "年报序列")):
            helpers.append(
                ImplementationHelper(
                    module="core.skill_runtime.standard_financial_apis",
                    name="get_historical_financial_annual_series",
                    signature="symbol: str, years: int = 10, source: str = None",
                    description="一键返回最近 N 年年报序列（revenue/net_profit/roe/gross_margin/operating_cashflow 等）",
                    reason="长期财务台账、5-10 年趋势分析的优先入口，避免手动遍历多期数据",
                    data_source_handling="local_only",
                )
            )
            helpers.append(
                ImplementationHelper(
                    module="core.skill_runtime.standard_financial_apis",
                    name="get_profitability_stability_metrics",
                    signature="symbol: str, years: int = 10, source: str = None",
                    description="基于年报序列计算营收/净利/ROE/毛利率的均值、波动率、变异系数",
                    reason="盈利稳定性、护城河财务证据分析的优先函数，避免重复计算统计指标",
                    data_source_handling="local_only",
                )
            )
        if any(k in normalized for k in ("现金流", "cashflow", "自由现金流", "fcf", "ocf", "利润含金量")):
            helpers.append(
                ImplementationHelper(
                    module="core.skill_runtime.standard_financial_apis",
                    name="get_cashflow_quality_trend",
                    signature="symbol: str, years: int = 10, source: str = None",
                    description="返回 OCF/净利、FCF/净利、OCF margin、FCF margin 的年度趋势和统计摘要",
                    reason="现金流质量、利润含金量分析的优先函数",
                    data_source_handling="local_only",
                )
            )
        if any(k in normalized for k in ("分位", "percentile", "估值分位", "历史估值", "pe_ttm", "pb")):
            helpers.append(
                ImplementationHelper(
                    module="core.skill_runtime.standard_financial_apis",
                    name="get_historical_valuation_percentile",
                    signature="symbol: str, metrics: list = None, lookback_years: int = 5, as_of_date: str = None",
                    description="结构化返回 pe_ttm/pb/ps_ttm/pcf_ttm 的历史分位、当前值、中位数",
                    reason="历史估值分位分析的优先函数，替代文本分位输出",
                    data_source_handling="self_contained",
                )
            )
        # 股权质押/大股东质押/质押风险
        if any(k in normalized for k in ("质押", "pledge", "股权质押", "大股东质押", "爆仓", "平仓线")):
            helpers.append(
                ImplementationHelper(
                    module="core.skill_runtime.standard_financial_apis",
                    name="get_pledge_risk_profile",
                    signature="symbol: str, source: str = None",
                    description="返回股权质押风险画像：总质押比例、未解押规模、前几大质押股东、最近质押事件、风险等级(low/medium/medium_high/high/none)",
                    reason="股权质押风险快照分析的优先函数，自动从 Tushare/akshare 获取数据，无需手动调用外部接口",
                    data_source_handling="self_contained",
                )
            )
            if any(k in normalized for k in ("趋势", "历史", "trend", "historical", "年度", "逐年", "变化", "变动", "好转", "恶化")):
                helpers.append(
                    ImplementationHelper(
                        module="core.skill_runtime.standard_financial_apis",
                        name="get_pledge_historical_series",
                        signature="symbol: str, start_date: str = None, end_date: str = None, years: int = None, period: str = 'year', source: str = None",
                        description="返回指定时间段内股权质押趋势，支持按年/季/月统计，包含每周期末质押比例、未解押股数、活跃质押笔数，以及自动评估的趋势方向（improving/worsening/stable）",
                        reason="质押趋势分析的优先函数，支持自定义起止日期和统计粒度，直接判断风险好转/恶化",
                        data_source_handling="self_contained",
                    )
                )
        return helpers

    @staticmethod
    def _convert_capability_hits_to_helpers(capability_hits: list) -> list:
        """把 CapabilityIndexService.search_capabilities 的命中结果转换为 ImplementationHelper。

        capability_hits 中的每项是 CapabilitySearchHit（含 capability + score）。
        通过 registry_tool_id 查 ToolRegistry 获取 module_path 和 function_name。
        只保留 bindable=True 且 source_type in (builtin_tool, mcp_tool) 的工具。
        """
        if not capability_hits:
            return []

        try:
            from core.tools.registry import get_tool_registry
            registry = get_tool_registry()
        except Exception as exc:
            logger.warning("⚠️ 向量搜索结果转换失败（ToolRegistry 不可用）: %s", exc)
            return []

        helpers = []
        seen_tool_ids = set()
        for hit in capability_hits:
            try:
                cap = hit.capability if hasattr(hit, "capability") else hit.get("capability", {})
                score = hit.score if hasattr(hit, "score") else hit.get("score", 0.0)
            except Exception:
                continue

            # 只收录可绑定的工具类能力（跳过 skill/external_skill，那些是独立 skill 不是函数）
            source_type = getattr(cap, "source_type", "") or (cap.get("source_type", "") if isinstance(cap, dict) else "")
            if source_type not in ("builtin_tool", "mcp_tool"):
                continue
            bindable = getattr(cap, "bindable", False) or (cap.get("bindable", False) if isinstance(cap, dict) else False)
            if not bindable:
                continue

            tool_id = getattr(cap, "registry_tool_id", None) or (cap.get("registry_tool_id") if isinstance(cap, dict) else None)
            if not tool_id or tool_id in seen_tool_ids:
                continue

            # 查 ToolRegistry 获取函数的 module_path 和 function_name
            try:
                func = registry.get_function(tool_id)
            except Exception:
                func = None
            if func is None:
                continue

            module_path = getattr(func, "__module__", "") or ""
            function_name = getattr(func, "__name__", tool_id)
            # 只收录 ALLOWED_CORE_PREFIXES 下的模块（与静态验证器白名单一致）
            from core.tools.external.static_validator import ALLOWED_CORE_PREFIXES
            allowed = any(module_path == p or module_path.startswith(p + ".") for p in ALLOWED_CORE_PREFIXES)
            if not allowed:
                continue

            name = getattr(cap, "name", "") or (cap.get("name", "") if isinstance(cap, dict) else "") or function_name
            description = getattr(cap, "description", "") or (cap.get("description", "") if isinstance(cap, dict) else "")
            when_to_use = getattr(cap, "when_to_use", "") or (cap.get("when_to_use", "") if isinstance(cap, dict) else "")

            # 从 ToolMetadata 读取 data_source_handling，传递到 ImplementationHelper
            # 让 LLM 在 skill 工坊设计 skill 时能判断是否需要补充数据源
            try:
                metadata = registry.get(tool_id)
                data_source_handling = getattr(metadata, "data_source_handling", "self_contained") if metadata else "self_contained"
            except Exception:
                data_source_handling = "self_contained"

            helpers.append(
                ImplementationHelper(
                    module=module_path,
                    name=function_name,
                    signature=f"{function_name}(symbol, **kwargs)",  # 签名由 code_generator 通过 describe_runtime_helper 获取
                    description=description or when_to_use or name,
                    reason=f"向量搜索召回（score={score:.2f}），语义匹配 skill 需求",
                    data_source_handling=data_source_handling,
                )
            )
            seen_tool_ids.add(tool_id)

        logger.info("🧭 向量搜索召回转换: %d 个 hit → %d 个 ImplementationHelper", len(capability_hits), len(helpers))
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

    def _rule_based_analyze(self, spec: SkillSpec, capability_hits: list = None) -> ImplementationFactReport:
        """纯规则驱动的侦察，作为 LLM 侦察的基线和降级方案。"""
        from core.skill_runtime.project_access import (
            inspect_field_coverage,
            inspect_stock_collection_schema,
            inspect_symbol_documents,
        )

        recommendations = self._analyzer.build_recommendations(spec=spec)

        # ── 需求类型分流（改进点 1）：外部 API 集成 vs 本地数据复用 ──
        requirement_mode = self._classify_requirement_mode(spec)
        unknown_data_source = ""
        if requirement_mode == "external_api":
            data_source_raw = (getattr(spec, "data_source", "") or "").strip()
            if data_source_raw:
                from .external_data_source_catalog import is_known_external_source
                if not is_known_external_source(data_source_raw):
                    unknown_data_source = data_source_raw
            # 外部 API 集成模式：本地股票集合与目录外部源均与需求无关，清空避免凑数误导
            recommendations["stock_collections"] = []
            recommendations["external_sources"] = []

        report = ImplementationFactReport(
            task_summary=spec.description,
            recommended_strategy=(
                self._build_external_api_strategy(spec, unknown_data_source)
                if requirement_mode == "external_api"
                else self._build_strategy(spec, recommendations)
            ),
            confidence=0.45,
        )

        # ── 目录外数据源显式标注（改进点 2）：不再静默 fallback，登记运行时缺口 ──
        if unknown_data_source:
            from .external_data_source_catalog import EXTERNAL_DATA_SOURCE_CATALOG
            known_names = "、".join(item["display_name"] for item in EXTERNAL_DATA_SOURCE_CATALOG)
            gap_reason = (
                f"数据源 '{unknown_data_source}' 不在系统已知外部数据源目录（{known_names}）。"
                "本 Skill 属目录外数据源集成：需要用户提供或确认接口规格"
                "（URL、请求方式、参数、认证方式、返回字段），"
                "生成代码时不得臆造接口细节与字段；规格不完整时应先向用户澄清。"
            )
            report.runtime_gaps.append(
                ImplementationIssue(
                    path=f"external_data_source:{unknown_data_source}",
                    reason=gap_reason,
                    severity="warning",
                )
            )
            report.notes.append(f"⚠️ {gap_reason}")
        symbol = self._extract_probe_symbol(spec)

        rule_based_helpers = self._infer_helpers(spec)
        logger.info(
            "\n" + "=" * 80 + "\n"
            "🔍 [侦察层 Phase 1] 规则基线分析\n"
            f"   tool_id: {spec.tool_id}\n"
            f"   需求描述: {spec.description[:80]}{'...' if len(spec.description) > 80 else ''}\n"
            f"   规则推荐 helpers: {[h.module + '.' + h.name for h in rule_based_helpers]}\n"
            f"   推荐本地集合: {recommendations.get('stock_collections', [])}\n"
            f"   推荐外部数据源: {recommendations.get('external_sources', [])}\n"
            f"   提取的测试股票代码: {symbol}\n"
            + "=" * 80
        )

        # 检查是否已有足够的 helper，避免分析不相关集合
        has_direct_helpers = len(rule_based_helpers) > 0
        if has_direct_helpers:
            helper_names = [h.name for h in rule_based_helpers]
            # 根据 helper 的 data_source_handling 分类
            self_contained_helpers = [h for h in rule_based_helpers if h.data_source_handling == "self_contained"]
            local_only_helpers = [h for h in rule_based_helpers if h.data_source_handling == "local_only"]
            partial_helpers = [h for h in rule_based_helpers if h.data_source_handling == "partial"]

            logger.info(
                f"✅ [侦察层 Phase 1] 已发现 {len(rule_based_helpers)} 个直接可用的 helper "
                f"({', '.join(helper_names)})，将根据数据源处理能力调整数据层推荐"
            )
            logger.info(
                f"   📊 数据源处理能力: self_contained={len(self_contained_helpers)}, "
                f"local_only={len(local_only_helpers)}, partial={len(partial_helpers)}"
            )

            # 智能决定数据层推荐策略：
            # - 全部 self_contained：helper 完全自包含，清空外部数据源推荐（LLM 不需要自己调数据源）
            # - 有 local_only：helper 只查本地 MongoDB，保留外部数据源作为补充（LLM 可能需要自己调外部 API）
            # - 有 partial：保留相关数据源推荐
            all_self_contained = len(self_contained_helpers) == len(rule_based_helpers)
            has_local_only = len(local_only_helpers) > 0

            if all_self_contained:
                # 全部自包含：清空外部数据源，只保留 stock_basic_info
                filtered_collections = []
                for col in recommendations.get("stock_collections") or []:
                    if col == "stock_basic_info":
                        filtered_collections.append(col)
                    else:
                        logger.info(f"   ⏭️  跳过集合分析: {col}（helper 已自包含数据获取）")
                recommendations["stock_collections"] = filtered_collections
                recommendations["external_sources"] = []

                report.notes.append(
                    f"✅ 已推荐 {len(rule_based_helpers)} 个 helper 函数（{', '.join(helper_names)}），"
                    "全部为 **self_contained** 类型（已封装数据源调用，自动调 Tushare/AKShare 或查本地 MongoDB）。"
                    "LLM 生成代码时**直接调用 helper 即可，不要自己实现数据源调用逻辑**"
                    "（如 import tushare/akshare、直接调 provider 等）。"
                )

                # strategy 明确说明"直接调用 helper"
                helper_list_text = ", ".join(helper_names)
                report.recommended_strategy = (
                    f"直接调用推荐的 helper 函数（{helper_list_text}）获取数据并组织输出。"
                    "这些 helper 已封装数据源调用逻辑，无需自行 import tushare/akshare 或查 MongoDB。"
                )
            elif has_local_only:
                # 有 local_only helper：保留外部数据源作为补充
                report.notes.append(
                    f"✅ 已推荐 {len(rule_based_helpers)} 个 helper 函数。"
                    f"其中 self_contained 类型 {len(self_contained_helpers)} 个（已封装数据源，直接调用即可），"
                    f"local_only 类型 {len(local_only_helpers)} 个（只查本地 MongoDB）。"
                )
                report.notes.append(
                    "⚠️ local_only helper 只查本地 MongoDB，若本地无数据，LLM 可能需要：\n"
                    "  1. 调用 self_contained helper 补充数据（如 get_external_historical_data）\n"
                    "  2. 或自行调用外部数据源（Tushare/AKShare）补充\n"
                    "  3. 在代码中处理本地无数据的情况（返回 no_data 或降级到外部 API）"
                )
                # strategy 保持原样（包含本地集合和外部来源推荐作为补充）
            else:
                # partial 或混合情况：保留数据层推荐
                report.notes.append(
                    f"✅ 已推荐 {len(rule_based_helpers)} 个 helper 函数，部分为 partial 类型。"
                    "LLM 调用 helper 后，可能需要补充其它数据源或计算。"
                )

            if "估值" in spec.description or any(
                k in spec.description.lower() for k in ("valuation", "peg", "pb", "pe", "dcf")
            ):
                if "先确认价格" not in report.recommended_strategy:
                    report.recommended_strategy += "；先确认价格、财务口径和增长率路径，再固化估值公式"

        for collection in recommendations.get("stock_collections") or []:
            logger.info(f"📦 [侦察层 Phase 1] 开始分析本地集合: {collection}")
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
            logger.info(f"🌐 [侦察层 Phase 1] 记录外部数据源推荐: {source}")
            report.schema_facts.append(
                ImplementationFact(
                    source=source,
                    fact=f"若本地数据不足，可优先考虑文档化的数据源 {source}",
                    evidence="RequirementAnalyzer.build_recommendations",
                )
            )

        report.available_helpers.extend(rule_based_helpers)

        # 【关键优化】直接验证 Phase 1 发现的 helper 签名，不需要 LLM 去探索
        # 这样 Phase 2 就可以直接跳过，避免 LLM 去探索不相关的工具
        if rule_based_helpers:
            logger.info(
                f"🔍 [侦察层 Phase 1] 开始验证 {len(rule_based_helpers)} 个 helper 的签名..."
            )
            # 注意：describe_runtime_helper 是从 recon_tools 导入的，它返回 JSON 字符串
            from .recon_tools import describe_runtime_helper, probe_interface

            # 提取测试股票（用于真实调用 helper）
            test_symbol = (
                getattr(spec, "test_input", {}).get("symbol")
                or getattr(spec, "test_input", {}).get("code")
                or ""
            )

            for helper in rule_based_helpers:
                try:
                    # helper.module 是完整路径，比如 "core.skill_runtime.standard_financial_apis"
                    # 需要提取模块短名，比如 "standard_financial_apis"
                    module_short = helper.module.split(".")[-1]
                    result_json = describe_runtime_helper(module_short, helper.name)
                    result = json.loads(result_json)
                    if "error" not in result:
                        helper.signature = result.get("signature", helper.signature)
                        # 把完整 docstring 填入 description，代码生成器会用到
                        helper.description = result.get("docstring") or result.get("description") or ""
                        logger.info(
                            f"   ✅ {helper.name}: 签名验证成功"
                        )
                    else:
                        logger.warning(
                            f"   ⚠️  {helper.name}: 签名验证失败 - {result.get('error')}"
                        )
                except Exception as exc:
                    logger.warning(
                        f"   ⚠️  {helper.name}: 签名验证异常 - {exc}"
                    )

            # 【新增】真实调用 helper 验证可用性 + 财经专家判断 no_data 合理性
            # 避免 LLM 生成代码后才发现 helper 返回 no_data（如测试股票本身无质押）
            if test_symbol:
                self._probe_helpers_and_judge(
                    rule_based_helpers, spec, test_symbol, report
                )

        # 向量搜索召回的分析工具推荐（语义匹配，比关键词规则更精准）
        if capability_hits:
            if requirement_mode == "external_api":
                # 改进点 1：外部 API 集成模式下，向量召回的本地工具与指定外部数据源无关，
                # 不纳入 available_helpers（避免"数据源已覆盖"的误导性结论）
                logger.info(
                    "🧭 [侦察层] 外部API集成模式：跳过 %d 个向量召回工具（与指定外部数据源无关）",
                    len(capability_hits),
                )
                report.schema_facts.append(
                    ImplementationFact(
                        source="capability_index",
                        fact=(
                            f"向量搜索召回 {len(capability_hits)} 个本地工具，"
                            "因需求为外部 API 集成模式未采纳（本地工具与指定外部数据源无关）"
                        ),
                        evidence="RequirementMode=external_api",
                    )
                )
            else:
                vector_helpers = self._convert_capability_hits_to_helpers(capability_hits)
                report.available_helpers.extend(vector_helpers)
                if vector_helpers:
                    report.schema_facts.append(
                        ImplementationFact(
                            source="capability_index",
                            fact=f"向量搜索召回 {len(vector_helpers)} 个语义相关工具（top score={capability_hits[0].score if capability_hits else 0:.2f}）",
                            evidence="CapabilityIndexService.search_capabilities",
                        )
                    )
        report.blocked_paths.extend(self._infer_blocked_paths(spec))
        report.validation_checks.extend(self._infer_validation_checks(spec))
        report.notes.extend(self._infer_notes(spec, recommendations))
        schema_context = resolve_financial_schema_context(spec)
        if schema_context:
            self._enrich_schema_bundle_guidance(report, schema_context)
        if report.sample_fields:
            report.confidence = max(report.confidence, 0.65)
        # ── 验收字段一致性校验（改进点 3）：覆盖率过低时降置信度并提示澄清 ──
        self._validate_expected_field_coverage(spec, report, requirement_mode)
        return report

    def _probe_helpers_and_judge(
        self,
        helpers: List[ImplementationHelper],
        spec,
        test_symbol: str,
        report: ImplementationFactReport,
    ) -> None:
        """真实调用 helper 验证可用性，并在返回 no_data 时调用财经专家判断合理性。

        - 如果 helper 返回 success：把返回值结构样例写入 fact_report.notes，
          帮助 LLM 知道字段名（避免瞎猜 current_pledge_ratio 等不存在的字段）
        - 如果 helper 返回 no_data：调用财经专家判断是否业务合理，
          不合理则推荐更合适的测试股票写入 notes
        - 如果 helper 调用异常：记录具体错误，提示 LLM 该 helper 不可用
        """
        from .recon_tools import probe_interface
        from .financial_expert_advisor import get_financial_expert_advisor

        # 准备财经专家顾问（延迟初始化，仅在 no_data 时调用）
        advisor = None

        for helper in helpers[:3]:  # 最多验证前 3 个 helper
            try:
                # 构建 sample_args
                sample_args = {"symbol": test_symbol}
                # 根据 helper 名推断额外参数
                if "historical" in helper.name.lower() or "series" in helper.name.lower():
                    sample_args["years"] = 3

                probe_result_json = probe_interface(
                    f"{helper.module}.{helper.name}", sample_args
                )
                probe_result = json.loads(probe_result_json)

                if not probe_result.get("success"):
                    # 调用本身失败
                    error_msg = probe_result.get("error", "未知错误")
                    report.notes.append(
                        f"⚠️ helper {helper.name} 真实调用失败: {error_msg}（建议 LLM 谨慎使用或换数据源）"
                    )
                    logger.warning(
                        f"⚠️ [侦察层] helper {helper.name} 真实调用失败: {error_msg}"
                    )
                    continue

                # 提取 helper 返回的 status
                preview = probe_result.get("preview", "")
                preview_dict = json.loads(preview) if isinstance(preview, str) else preview
                if not isinstance(preview_dict, dict):
                    preview_dict = {}

                helper_status = preview_dict.get("status", "unknown")
                helper_warnings = preview_dict.get("warnings", [])

                if helper_status == "success":
                    # ✅ helper 正常返回数据：把返回值结构样例写入 notes + helper.description
                    # 即使 docstring 不完整，代码生成器也能看到实际返回字段（保底机制）
                    field_keys = list(preview_dict.keys())
                    metrics_keys = (
                        list(preview_dict.get("metrics", {}).keys())
                        if isinstance(preview_dict.get("metrics"), dict)
                        else []
                    )
                    # 构建返回结构文本（保底）
                    return_struct = f"📋 实际返回字段: {field_keys}"
                    if metrics_keys:
                        return_struct += f"，metrics 子字段: {metrics_keys}"
                    # 追加到 helper.description（保留原有 docstring）
                    if helper.description:
                        helper.description = f"{helper.description}\n{return_struct}"
                    else:
                        helper.description = return_struct

                    report.notes.append(
                        f"✅ helper {helper.name} 真实调用成功（status=success）。"
                        f"返回字段: {field_keys}。"
                        f"metrics 子字段: {metrics_keys}。"
                        f"LLM 生成代码时应直接读取这些字段名。"
                    )
                    logger.info(
                        f"✅ [侦察层] helper {helper.name} 真实调用成功，返回字段: {field_keys}"
                    )

                elif helper_status in ("no_data", "no_news", "no_pledge"):
                    # ⚠️ helper 返回 no_data：调用财经专家判断是否业务合理
                    # 注意：不在此提取返回字段名，因为空数据会导致代码生成器误判结构（无法看到
                    # 列表元素内部的字段如 holder_name/shares_wan/ratio_pct）
                    # 返回结构应依赖 docstring 的 Returns 文档或后续沙箱反馈
                    logger.info(
                        f"🔍 [侦察层] helper {helper.name} 返回 {helper_status}，调用财经专家判断合理性..."
                    )

                    if advisor is None:
                        advisor = get_financial_expert_advisor(
                            llm_client=self._get_client_safe(),
                            provider=self._provider,
                            model=self._model,
                        )

                    # 获取股票基础信息（行业等）
                    stock_name = ""
                    industry = ""
                    try:
                        from core.skill_runtime.data_access import get_stock_basic_info

                        basic = get_stock_basic_info(test_symbol) or {}
                        stock_name = basic.get("name", "")
                        industry = basic.get("industry", "")
                    except Exception:
                        pass

                    # 推断数据类型描述
                    data_type = self._infer_data_type(helper.name, spec)

                    judgment = advisor.judge_no_data_rationality(
                        stock_symbol=test_symbol,
                        stock_name=stock_name,
                        industry=industry,
                        skill_purpose=getattr(spec, "display_name", "")
                        or getattr(spec, "description", ""),
                        data_type=data_type,
                        helper_name=helper.name,
                        helper_warnings=helper_warnings,
                        skill_category=getattr(spec, "category", ""),
                    )

                    if judgment.is_rational:
                        # no_data 业务合理（如银行股无质押）：告诉 LLM 这是正常情况
                        report.notes.append(
                            f"ℹ️ helper {helper.name} 返回 {helper_status}（业务合理）。"
                            f"专家判断: {judgment.reasoning}。"
                            f"建议: Skill 代码应返回 status=success 并标注'该股票无此类数据'，"
                            f"而不是返回 error。{judgment.advice}"
                        )
                    else:
                        # no_data 业务不合理：推荐换股
                        report.notes.append(
                            f"⚠️ helper {helper.name} 返回 {helper_status}（业务不合理）。"
                            f"专家判断: {judgment.reasoning}。"
                            f"建议换股重试。"
                        )
                        if judgment.recommended_stocks:
                            for stock in judgment.recommended_stocks[:3]:
                                report.notes.append(
                                    f"  推荐测试股票: {stock.get('code')} {stock.get('name')} - {stock.get('reason')}"
                                )
                        if judgment.advice:
                            report.notes.append(f"  专家建议: {judgment.advice}")

                        # 把推荐股票写入 schema_facts，方便后续管道读取
                        if judgment.recommended_stocks:
                            recommended_codes = ", ".join(
                                f"{s.get('code')}({s.get('name')})"
                                for s in judgment.recommended_stocks[:3]
                            )
                            report.schema_facts.append(
                                ImplementationFact(
                                    source="financial_expert_advisor",
                                    fact=f"建议换股测试: {recommended_codes}（原测试股票 {test_symbol} 无{data_type}）",
                                    evidence=f"helper {helper.name} 返回 {helper_status}，专家判断不合理",
                                )
                            )

                    logger.info(
                        f"🧠 [侦察层] 财经专家判断: is_rational={judgment.is_rational}, "
                        f"confidence={judgment.confidence:.2f}"
                    )

                else:
                    # 其他状态（error 等）
                    report.notes.append(
                        f"⚠️ helper {helper.name} 真实调用返回 status={helper_status}，"
                        f"warnings={helper_warnings}。LLM 应处理此情况。"
                    )

            except Exception as exc:
                logger.warning(
                    f"⚠️ [侦察层] helper {helper.name} 真实调用异常: {exc}"
                )
                report.notes.append(
                    f"⚠️ helper {helper.name} 真实调用异常: {exc}（建议 LLM 谨慎使用）"
                )

    def _get_client_safe(self):
        """安全获取 LLM 客户端，失败返回 None"""
        try:
            return self._get_client()
        except Exception:
            return None

    @staticmethod
    def _infer_data_type(helper_name: str, spec) -> str:
        """根据 helper 名和 spec 推断数据类型描述"""
        name_lower = helper_name.lower()
        if "pledge" in name_lower:
            return "质押数据"
        if "financial" in name_lower or "annual" in name_lower:
            return "财务数据"
        if "news" in name_lower or "announcement" in name_lower:
            return "新闻/公告数据"
        if "valuation" in name_lower:
            return "估值数据"
        if "technical" in name_lower or "price" in name_lower:
            return "技术指标/价格数据"
        if "capital" in name_lower or "flow" in name_lower:
            return "资金流向数据"
        return "所需数据"

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
        self, client, spec: SkillSpec, rule_report: ImplementationFactReport,
        has_many_helpers: bool = False
    ) -> ImplementationFactReport:
        """通过 LLM function-calling 自主探索，产出增强版事实报告。
        Args:
            has_many_helpers: True 表示 helper >= 3，只做筛选，限制 2 轮
        """
        from core.llm import Message

        start_time = time.time()
        tool_traces: List[ReconToolTrace] = []
        phase1_helper_names = {h.name for h in rule_report.available_helpers}

        # 注册侦察工具
        tool_defs = []
        for func in self._build_traced_tools(tool_traces):
            td = client.register_tool(func)
            tool_defs.append(td)

        # 构建侦察 prompt：根据场景选择不同的系统提示
        system_prompt = self._build_recon_system_prompt(has_many_helpers=has_many_helpers)
        user_prompt = self._build_recon_user_prompt(spec, rule_report)
        max_rounds = 2 if has_many_helpers else MAX_RECON_TOOL_ROUNDS

        messages = [
            Message(role="system", content=system_prompt),
            Message(role="user", content=user_prompt),
        ]

        logger.info(
            f"\n{'─'*50}\n"
            f"🧭 [侦察层] LLM {'筛选模式' if has_many_helpers else '探索模式'} | tool_id={spec.tool_id} | max_rounds={max_rounds}\n"
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
                max_tool_rounds=max_rounds,
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

        # Phase 2 分析完成后的总结日志
        if tool_traces:
            phase1_helper_names = {h.name for h in rule_report.available_helpers}
            phase2_helpers = set()
            phase2_collections = set()
            for trace in tool_traces:
                if trace.tool_name == "describe_runtime_helper":
                    func_name = trace.arguments.get("function_name", "")
                    if func_name:
                        phase2_helpers.add(func_name)
                elif trace.tool_name == "inspect_collection_schema":
                    col = trace.arguments.get("collection", "")
                    if col:
                        phase2_collections.add(col)

            redundant_collections = phase2_collections - phase1_helper_names
            if redundant_collections:
                helper_list = ", ".join(phase2_helpers)
                col_list = ", ".join(redundant_collections)
                logger.warning(
                    f"\n{'='*80}\n"
                    f"⚠️ [侦察层 Phase 2] 检测到可能冗余的集合探测\n"
                    f"   Phase 1 已发现 helpers: {', '.join(phase1_helper_names) or '无'}\n"
                    f"   Phase 2 探测的集合: {col_list}\n"
                    f"   建议: 如果任务可通过已有 helper 完成，可简化系统提示避免探索无关集合\n"
                    f"{'='*80}"
                )
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
    def _build_recon_system_prompt(has_many_helpers: bool = False) -> str:
        if has_many_helpers:
            # helper 较多的场景：只做筛选，禁止探索
            return (
                "你是一个 Skill 代码生成前置侦察 Agent。\n"
                "## 【重要约束】当前场景：Phase 1 已找到 3+ 个候选 helper\n"
                "你的任务非常单一：只需要从【规则基线推荐 Helper】列表中，筛选出最相关的 3-4 个即可。\n"
                "你不需要探索任何新工具、新集合、新函数！不需要调用 list_* 系列工具！\n\n"
                "## 允许做的唯一事情\n"
                "1. 用 describe_runtime_helper 验证候选 helper 的签名（仅当你需要确认参数细节时）\n"
                "2. 从候选列表中选择最相关的 3-4 个，填入 available_helpers\n\n"
                "## 绝对禁止\n"
                "❌ 禁止调用 list_available_collections\n"
                "❌ 禁止调用 list_runtime_functions\n"
                "❌ 禁止调用 list_analysis_tools\n"
                "❌ 禁止调用 list_external_data_sources\n"
                "❌ 禁止调用 inspect_collection_schema 去看不在推荐列表中的集合\n\n"
                "## 输出格式\n"
                "只输出一个纯 JSON 对象，包含 task_summary、recommended_strategy、available_helpers（筛选后的 3-4 个）、schema_facts、confidence。\n"
                "工具调用轮数：最多 2 轮，不要做多余探索！"
            )
        
        # helper 较少的场景：正常探索（备用分支，通常不会走到这里）
        return (
            "你是一个 Skill 代码生成前置侦察 Agent。\n"
            "你的任务是通过调用工具，收集最少但足够的实现事实，帮助后续代码生成器写出正确、可运行的 Python 函数。\n\n"
            "## 核心原则：按需探索，避免冗余\n"
            "...（原有系统提示保持不变）..."
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
            parts.append(f"\n## 规则基线已知事实（来自向量搜索 + 静态分析，已可信）\n" + "\n".join(baseline_facts))
        if rule_report.available_helpers:
            helper_lines = []
            for h in rule_report.available_helpers[:5]:
                ds = h.data_source_handling or "self_contained"
                helper_lines.append(f"  - {h.module}.{h.name} [数据源:{ds}]: {h.reason}")
            parts.append(
                "\n## 规则基线推荐 Helper（来自向量搜索，已高置信）\n"
                + "数据源标签: self_contained=自包含(直接调用); local_only=仅本地MongoDB(可能需补充外部数据源); partial=部分覆盖\n"
                + "\n".join(helper_lines)
                + "\n\n⚠️ 这些 helper 已通过语义匹配筛选，**只需用 describe_runtime_helper 验证签名即可**，"
                "不要用 list_runtime_functions 重新列举。如果签名匹配需求，直接加入 available_helpers 输出。\n"
                "⚠️ 选用 helper 时注意数据源标签：local_only 的 helper 若本地无数据，需在 skill 中补充外部数据源调用；self_contained 的 helper 直接调用即可。"
            )
        if data_contract_doc:
            parts.append(f"\n## 任务相关数据契约\n{data_contract_doc}")
        if factor_catalog_doc:
            parts.append(
                "\n## 任务相关因子白名单\n"
                f"{factor_catalog_doc}\n"
                "请重点验证这些因子对应的 helper、字段路径和可复用 bundle 是否已经足够，不要把 catalog 里已有因子误判成新缺口。"
            )

        # 附加推荐集合（来自 rule_report 的 schema_facts 中提取）
        recommended_collections = [
            f.source for f in (rule_report.schema_facts or [])
            if "推荐优先复用本地集合" in (f.fact or "")
        ]
        if recommended_collections:
            parts.append(
                "\n## 规则基线推荐集合（已可信，直接验证字段即可）\n"
                + "\n".join(f"  - {c}" for c in recommended_collections[:4])
                + "\n\n⚠️ 这些集合已通过需求分析筛选，**只需用 inspect_collection_schema 验证字段即可**，"
                "不要用 list_available_collections 重新列举所有集合。"
            )

        parts.append(
            "\n## 请求\n"
            "请先依据数据契约理解字段层级，再通过工具调用验证关键路径。输出时只保留会影响代码实现的最小事实集，不要写成长篇方案说明。\n"
            "⚠️ 最多 6 轮工具调用。每轮必须有明确目的。如果基线已推荐 helper 和集合，理想情况下 2-3 轮即可完成验证。"
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
                helper_name = h["name"]
                # 优先使用 LLM 输出的 data_source_handling；否则查 ToolRegistry 获取
                data_source_handling = str(h.get("data_source_handling", "") or "").strip()
                if not data_source_handling:
                    try:
                        from core.tools.registry import get_tool_registry
                        registry = get_tool_registry()
                        metadata = registry.get(helper_name) or registry.get_tool(helper_name)
                        if metadata:
                            data_source_handling = getattr(metadata, "data_source_handling", "self_contained")
                    except Exception:
                        pass
                    if not data_source_handling:
                        data_source_handling = "self_contained"
                report.available_helpers.append(
                    ImplementationHelper(
                        module=h.get("module", ""),
                        name=helper_name,
                        signature=h.get("signature", ""),
                        reason=h.get("reason", ""),
                        data_source_handling=data_source_handling,
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

        # 补充 available_helpers：Phase 1 规则基线推荐的 helpers 在 Phase 2 中可能被 LLM 遗漏，
        # 必须保留以确保代码生成阶段能看到关键 helper（如 get_pledge_risk_profile）
        if rule_report.available_helpers:
            existing_helper_names = {h.name for h in report.available_helpers if h.name}
            for base_helper in rule_report.available_helpers:
                if base_helper.name and base_helper.name not in existing_helper_names:
                    report.available_helpers.append(base_helper)
                    existing_helper_names.add(base_helper.name)

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