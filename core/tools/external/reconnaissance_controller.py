"""Skill 生成前置侦察层 — LLM 驱动 + 工具调用模式。

侦察层在代码生成前运行，通过 LLM function-calling 自主探索：
- 数据库集合的字段和覆盖率
- skill_runtime 公开 helper 的签名和用途
- 指定股票的样本数据

产出结构化 ImplementationFactReport，供 CodeGenerator 消费。
"""

from __future__ import annotations

import json
import logging
import time
from typing import Any, Dict, List, Optional

from .recon_tools import RECON_TOOLS
from .requirement_analyzer import RequirementAnalyzer
from .skill_spec import (
    ImplementationFact,
    ImplementationFactReport,
    ImplementationHelper,
    ImplementationIssue,
    SkillSpec,
    ValidationCheck,
)

logger = logging.getLogger(__name__)

# LLM 侦察最大工具调用轮数
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
                    reason="估值类 Skill 的标准输入入口，可一次获得现价、估值指标和财务数据",
                )
            )
        if any(k in normalized for k in ("行业", "peer", "relative", "同行", "pb", "pe", "ps")):
            helpers.append(
                ImplementationHelper(
                    module="core.skill_runtime.data_access",
                    name="summarize_industry_valuation",
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
        checks: list[ValidationCheck] = []
        if spec.expected_output.fields:
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
        else:
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

    @staticmethod
    def _infer_notes(spec: SkillSpec, recommendations: dict) -> list[str]:
        notes: list[str] = []
        if recommendations.get("external_sources"):
            notes.append("外部数据源在侦察阶段可用于确认实现路径，但不代表最终 Skill 可以直接依赖其内部 provider。")
        if spec.expected_output.fields:
            notes.append(f"期望输出字段: {', '.join(spec.expected_output.fields)}")
        return notes

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
            self._enrich_collection_facts(report, collection, symbol,
                                          inspect_stock_collection_schema,
                                          inspect_field_coverage,
                                          inspect_symbol_documents)

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
            report.sample_fields[collection] = top_fields[:60]
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
        if symbol_docs:
            symbol_fields = list(symbol_docs[0].keys())[:30]
            report.notes.append(f"{collection} 中存在 {symbol} 的样本记录，首条字段: {', '.join(symbol_fields)}")
            # 将符号样本中的特有字段合并到 sample_fields
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

        # 注册侦察工具
        tool_defs = []
        for func in RECON_TOOLS:
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
            f"📝 User Prompt ({len(user_prompt)} 字符):\n{user_prompt[:2000]}\n"
            f"{'...(截断)' if len(user_prompt) > 2000 else ''}\n"
            f"🔧 可用工具: {[td['function']['name'] for td in tool_defs]}\n"
            f"{'─'*50}"
        )

        # 执行工具调用循环
        response = client.chat(
            messages,
            tools=tool_defs,
            auto_execute_tools=True,
            max_tool_rounds=MAX_RECON_TOOL_ROUNDS,
        )

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
        report.confidence = max(report.confidence, 0.75)
        report.notes.append(f"侦察耗时: {elapsed:.1f}s（LLM 驱动）")
        return report

    # ================================================================
    # Prompt 构建 & 输出解析
    # ================================================================

    @staticmethod
    def _build_recon_system_prompt() -> str:
        return (
            "你是一个 Skill 代码生成前置侦察 Agent。\n"
            "你的任务是通过调用工具，收集足够的实现事实，帮助后续的代码生成器写出正确、可运行的 Python 函数。\n\n"
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
            "探索完成后，请输出一份 JSON 对象（用 ```json 包裹），包含以下字段：\n"
            "```\n"
            "{\n"
            '  "task_summary": "一句话总结任务需求",\n'
            '  "recommended_strategy": "推荐的实现策略（数据来源、计算路径）",\n'
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
            '    {"name": "检查名", "description": "描述", "check_type": "类型"}\n'
            "  ],\n"
            '  "confidence": 0.0到1.0之间的置信度,\n'
            '  "notes": ["额外备注"]\n'
            "}\n"
            "```\n\n"
            "## 重要约束\n"
            "- 只做只读探测，不修改任何数据。\n"
            "- 探测时优先关注与任务直接相关的集合和函数。\n"
            "- 如果发现某个关键字段覆盖率很低或不存在，务必在 runtime_gaps 中标注。\n"
            "- 如果发现 MCP 工具或外部数据源能满足需求，在 schema_facts 和 recommended_strategy 中明确说明。\n"
            "- 生成的 Skill 不应直接导入内部 provider，应通过 skill_runtime 公开接口访问数据。\n"
        )

    @staticmethod
    def _build_recon_user_prompt(spec: SkillSpec, rule_report: ImplementationFactReport) -> str:
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

        parts.append(
            "\n## 请求\n"
            "请通过工具调用，系统性地探索上述 Skill 的实现路径，然后输出结构化的侦察报告 JSON。"
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
                report.validation_checks.append(
                    ValidationCheck(
                        name=vc.get("name", ""),
                        description=vc.get("description", ""),
                        check_type=vc.get("check_type", "custom"),
                        field=vc.get("field", ""),
                        value_path=vc.get("value_path", "data"),
                        forbid_null=vc.get("forbid_null", False),
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

        return report