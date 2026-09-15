"""
需求分析器 — 多轮对话式需求沟通

核心能力：
1. 清晰度评估 — 判断用户需求的明确程度 (HIGH/MEDIUM/LOW)
2. 边界检测 — 检查需求是否超出单个 Skill 的范围
3. 多轮对话 — 1-3 轮渐进式需求确认
4. 规格生成 — 将确认的需求转化为结构化 SkillSpec
"""

import json
import logging
import re
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from core.llm import UnifiedLLMClient, Message

from .external_data_source_catalog import (
    render_external_data_source_doc,
    select_relevant_external_data_sources,
)
from .stock_data_catalog import (
    render_stock_data_collection_doc,
    select_relevant_stock_collections,
)
from .financial_schema_context import (
    build_schema_constraint_hints,
    build_schema_generated_checks,
    get_contract_required_fields,
    resolve_financial_schema_context,
)
from core.skill_runtime import build_factor_catalog_prompt_context, infer_recommended_factor_packs
from .upgrade_patch import apply_upgrade_patch, build_upgrade_patch_prompt, parent_contract_to_json

# standard_financial_apis 标准函数摘要 — 注入需求分析提示词，让 LLM 知道项目已内置哪些能力
STANDARD_FINANCIAL_APIS_SUMMARY = (
    "## 项目内置标准金融数据能力（standard_financial_apis）\n"
    "项目通过 core.skill_runtime.standard_financial_apis 提供 32 个标准函数，"
    "覆盖行情、财务、估值、风险、同行、质押等场景。这些函数**自动从项目配置的数据源获取数据**"
    "（Tushare/akshare/local 等，优先级由数据库 datasource_groupings 集合统一配置），"
    "**用户不需要、也不应该选择数据源**。\n"
    "如果用户需求能被以下函数覆盖，应直接告知用户「项目已内置该能力」，不要引导用户选择数据源：\n"
    "- get_pledge_risk_profile：股权质押风险画像（质押比例、未解押规模、前几大质押股东、风险等级）\n"
    "- get_pledge_historical_series：股权质押历史趋势（支持自定义起止日期，按年/季/月统计质押比例、未解押股数，自动评估趋势方向）\n"
    "- get_historical_financial_annual_series：历史年报财务序列（营收/净利/ROE/毛利率/现金流等）\n"
    "- get_profitability_stability_metrics：盈利稳定性指标（均值/波动率/变异系数）\n"
    "- get_cashflow_quality_trend：现金流质量趋势（OCF/净利、FCF/净利、margin 趋势）\n"
    "- get_historical_valuation_percentile：历史估值分位（PE/PB/PS/PCF 分位）\n"
    "- get_current_valuation_snapshot：当前估值快照\n"
    "- get_debt_solvency_trend：偿债能力趋势\n"
    "- get_margin_stability_metrics：利润稳定性指标\n"
    "- get_capital_efficiency_trend：资本效率趋势\n"
    "- get_growth_quality_metrics：成长质量指标\n"
    "- get_single_stock_risk_profile：个股风险画像\n"
    "- get_shareholder_return_metrics：股东回报指标（分红/股息率）\n"
    "- get_risk_event_flags：风险事件标记\n"
    "- get_company_event_timeline：公司公告监管事件时间线\n"
    "- get_company_announcements：公司公告\n"
    "- get_business_segment_trend：主营结构趋势\n"
    "- get_peer_group：同行样本\n"
    "- get_peer_relative_growth / get_peer_relative_valuation / get_peer_relative_quality：同行相对分析\n"
    "- get_industry_market_performance：行业市场表现\n"
    "- get_industry_fundamental_summary：行业基本面汇总\n"
    "- get_capital_flow_series：资金流序列\n"
    "- get_chip_distribution_context：筹码分布上下文\n"
    "- get_security_master：证券主数据\n"
    "- get_adjusted_price_series：复权价格序列\n"
    "- get_return_series：收益序列\n"
    "- get_technical_indicator_series：技术指标历史序列\n"
    "- get_volatility_metrics：波动率指标\n"
    "- get_drawdown_metrics：回撤指标\n"
    "- get_portfolio_risk_profile：组合风险画像\n"
    "只有当用户需求**不被以上函数覆盖**时，才考虑引导用户使用外部数据源（如 AKShare/Tushare），"
    "但仍应优先通过 skill_runtime 公开接口访问，不要让用户直接选择数据源。"
)

from .skill_spec import (
    BoundaryCheck,
    ClarityLevel,
    ConversationRound,
    ImplementationFactReport,
    SessionStatus,
    SkillCreationSession,
    SkillHandoffContext,
    SkillParameter,
    SkillSpec,
    ValidationCheck,
)

logger = logging.getLogger(__name__)

ANALYZER_LLM_TIMEOUT_SECONDS = 180


SKILL_SEMANTICS_GUIDANCE = (
    "Skill 的语义：Skill 是一个可复用、可验证、边界清晰的功能实现单元，"
    "不等于只能做数据获取。Skill 可以做数据获取、字段整理、格式转换、指标计算、规则判断、"
    "轻量聚合、模板化说明生成等确定性能力。\n"
    "Agent/Workflow 的语义：负责需求理解、任务规划、多 Skill 编排、开放式追问、主观综合判断、"
    "研究结论整合、研究观察生成等高层决策与推理。\n"
    "判断边界的核心标准不是“是否有计算”或“是否有解释”，而是该能力是否确定、可验证、可复用，"
    "且是否仍然围绕单一明确目标。若解释文本完全基于固定规则和输入数据生成，也可以属于 Skill 输出的一部分。"
)

SKILL_BOUNDARY_EXAMPLES = (
    "可视为单个 Skill 的例子：\n"
    "- 根据历史 PB 分位数计算估值通道，并输出当前 PB、分位点、对应价格区间\n"
    "- 获取财报后计算同比/环比增速并返回结构化结果\n"
    "- 聚合同一目标所需的紧密相关数据并输出标准化摘要\n\n"
    "应交给 Agent/Workflow 的例子：\n"
    "- 结合宏观、行业、财报、新闻给出主观投资结论\n"
    "- 调用多个彼此独立的 Skill 后生成完整研究报告\n"
    "- 在多个候选方法之间做开放式策略选择并解释取舍\n"
)

# 外部 HTTP API 集成的显式信号词（出现在描述/约束中）
EXTERNAL_API_SIGNAL_KEYWORDS = (
    "http://", "https://", "endpoint", "rest api", "open api",
    "公开接口", "公开http接口", "网页接口", "外部接口", "第三方接口", "爬取", "抓取",
)


def classify_requirement_mode(spec: Any) -> str:
    """需求类型分流：external_api（外部 API 集成） / local_data（本地数据复用，默认）。

    判定信号（任一命中即 external_api）：
    1. spec.data_source 明确指定了目录外数据源（如 dongchedi / 懂车帝）；
    2. 描述或约束中出现外部接口集成信号词（URL、公开接口、爬取等）。

    external_api 模式下：不推荐本地股票集合、不把向量召回的本地工具当作
    "数据源已覆盖"，策略改为直接集成外部接口，前端不展示本地/目录资产。
    """
    from .external_data_source_catalog import is_known_external_source

    data_source = (getattr(spec, "data_source", "") or "").strip()
    if data_source and not is_known_external_source(data_source):
        return "external_api"

    text = " ".join(
        [
            getattr(spec, "description", "") or "",
            " ".join(getattr(spec, "constraints", []) or []),
        ]
    ).lower()
    if any(k in text for k in EXTERNAL_API_SIGNAL_KEYWORDS):
        return "external_api"
    return "local_data"


class RequirementAnalyzer:
    """
    需求分析器

    通过多轮对话将用户的自然语言需求转化为结构化 SkillSpec。
    """

    def __init__(
        self,
        llm_client: Optional[UnifiedLLMClient] = None,
        provider: str = "deepseek",
        model: Optional[str] = None,
        quick_llm_client: Optional[UnifiedLLMClient] = None,
    ):
        self._client = llm_client
        self._provider = provider
        self._model = model
        # 快速模型客户端：清晰度评估/边界检测/对话回复/规格生成等轻推理
        # 环节优先使用；未配置时全部回退主模型，行为与旧版一致
        self._quick_client = quick_llm_client

    def _get_client(self) -> UnifiedLLMClient:
        """懒加载 LLM 客户端"""
        if self._client is None:
            kwargs = {"timeout": ANALYZER_LLM_TIMEOUT_SECONDS}
            if self._model:
                kwargs["model"] = self._model
            self._client = UnifiedLLMClient.from_provider(self._provider, **kwargs)
        else:
            adapter = getattr(self._client, "_adapter", None)
            config = getattr(adapter, "config", None)
            if config and getattr(config, "timeout", 0) < ANALYZER_LLM_TIMEOUT_SECONDS:
                config.timeout = ANALYZER_LLM_TIMEOUT_SECONDS
                try:
                    adapter.initialize()
                except Exception as e:
                    logger.warning(f"更新需求分析 LLM 超时时间失败: {e}")
        return self._client

    def _get_quick_client(self) -> Optional[UnifiedLLMClient]:
        """轻量判断专用快速模型客户端；未配置时返回 None（调用方回退主模型）。"""
        if self._quick_client is None:
            return None
        adapter = getattr(self._quick_client, "_adapter", None)
        config = getattr(adapter, "config", None)
        if config and getattr(config, "timeout", 0) < ANALYZER_LLM_TIMEOUT_SECONDS:
            config.timeout = ANALYZER_LLM_TIMEOUT_SECONDS
            try:
                adapter.initialize()
            except Exception as e:
                logger.warning(f"更新快速模型超时时间失败: {e}")
        return self._quick_client

    def _chat_with_quick_fallback(
        self, messages: List[Message], *, stage: str
    ) -> str:
        """轻推理调用（对话回复/规格生成）：优先快速模型，失败时回退主模型。

        需求对话（复述/澄清/确认引导）与规格生成（结构化转录）不需要深度
        推理，快速非思考模型可将响应从分钟级降到秒级；快速模型不可用
        （欠费/超时/空回复）时回退主模型，保障功能可用性。
        """
        quick = self._get_quick_client()
        if quick is not None:
            try:
                response = quick.chat(messages)
                content = (response.content or "").strip()
                if content:
                    return content
                logger.warning(f"{stage}: 快速模型返回空内容，回退主模型")
            except Exception as exc:
                logger.warning(f"{stage}: 快速模型调用失败，回退主模型: {exc}")
        response = self._get_client().chat(messages)
        return (response.content or "").strip()

    @staticmethod
    def _raise_analysis_error(stage: str, error: Optional[Exception] = None) -> None:
        detail = str(error) if error else "LLM 未返回有效内容"
        raise RuntimeError(f"{stage}失败：{detail}")

    # ==================== 健壮 JSON 解析 ====================

    @staticmethod
    def _parse_llm_json(raw: str) -> Optional[Dict[str, Any]]:
        """从 LLM 输出中提取 JSON 对象，多策略容错。

        策略顺序：
        1. 提取 ```json ... ``` Markdown 代码块
        2. 用大括号深度匹配找到最外层 { ... }
        3. 修复常见 LLM JSON 错误后重试（尾随逗号、单引号等）

        Returns:
            解析成功返回 dict，全部策略失败返回 None。
        """
        if not raw or not raw.strip():
            return None

        text = raw.strip()

        # 策略 1: 提取 ```json ... ``` 代码块
        json_blocks = re.findall(r"```(?:json)?\s*\n?(.*?)```", text, re.DOTALL)
        for block in json_blocks:
            result = RequirementAnalyzer._try_parse_json(block.strip())
            if result is not None:
                return result

        # 策略 2: 大括号深度匹配（比贪婪正则 `\{.*\}` 精准得多）
        brace_start = text.find("{")
        if brace_start >= 0:
            depth = 0
            for i in range(brace_start, len(text)):
                if text[i] == "{":
                    depth += 1
                elif text[i] == "}":
                    depth -= 1
                    if depth == 0:
                        result = RequirementAnalyzer._try_parse_json(text[brace_start:i + 1])
                        if result is not None:
                            return result
                        break  # 匹配到最外层但解析失败，进入修复策略

        # 策略 3: 修复常见 LLM JSON 错误后重试
        if brace_start >= 0:
            # 重新提取最外层
            depth = 0
            end_idx = -1
            for i in range(brace_start, len(text)):
                if text[i] == "{":
                    depth += 1
                elif text[i] == "}":
                    depth -= 1
                    if depth == 0:
                        end_idx = i
                        break
            if end_idx > brace_start:
                candidate = text[brace_start:end_idx + 1]
                candidate = RequirementAnalyzer._fix_common_json_errors(candidate)
                result = RequirementAnalyzer._try_parse_json(candidate)
                if result is not None:
                    return result

        return None

    @staticmethod
    def _try_parse_json(text: str) -> Optional[Dict[str, Any]]:
        """尝试解析 JSON，失败返回 None。"""
        try:
            data = json.loads(text)
            if isinstance(data, dict):
                return data
        except (json.JSONDecodeError, ValueError):
            pass
        return None

    @staticmethod
    def _fix_common_json_errors(text: str) -> str:
        """修复 LLM 常见的 JSON 格式错误。"""
        # 移除尾随逗号: ,} 和 ,]
        text = re.sub(r",\s*}", "}", text)
        text = re.sub(r",\s*]", "]", text)
        # 替换单引号为双引号（简单场景）
        # 仅在值不含单引号的情况下安全替换
        # text = text.replace("'", '"')  # 不安全，先注释
        # 修复 true/false 大小写问题
        text = re.sub(r"\bTrue\b", "true", text)
        text = re.sub(r"\bFalse\b", "false", text)
        text = re.sub(r"\bNone\b", "null", text)
        return text

    @staticmethod
    def _extract_tool_id_hint(text: str) -> str:
        match = re.search(r"(?:skill|工具)[:：]\s*([a-zA-Z][a-zA-Z0-9_]*)", text or "", re.IGNORECASE)
        if match:
            return match.group(1)
        if "pb" in (text or "").lower() or "市净率" in (text or ""):
            return "calculate_pb_valuation_band"
        return "new_skill"

    def _build_fallback_blueprint(self, text: str) -> Dict[str, Any]:
        normalized = (text or "").lower()
        recommendations = self.build_recommendations(conversation=text)
        tool_id = self._extract_tool_id_hint(text)
        category = recommendations.get("category_hint") or self._infer_category_hint(text)
        data_source_hint = recommendations.get("data_source_hint") or ""
        external_sources = recommendations.get("external_sources") or []
        primary_source = data_source_hint or (external_sources[0] if external_sources else "待确认")

        if "peg" in normalized:
            return {
                "tool_id": tool_id if tool_id != "new_skill" else "calculate_peg_valuation",
                "display_name": "PEG估值计算",
                "description": "根据股票代码获取PE(TTM)和盈利增长率，计算PEG指标并输出结构化估值结论。",
                "category": "fundamentals",
                "data_source": primary_source,
                "parameters": [
                    {"name": "symbol", "type": "string", "description": "股票代码", "required": True},
                    {"name": "growth_years", "type": "integer", "description": "增长口径参数，当前仅支持1，表示同口径同比，不代表连续年报年数", "required": False, "default": 1},
                ],
                "fields": [
                    "symbol", "name", "industry", "current_price", "pe_ttm",
                    "earnings_growth_rate", "peg_ratio", "valuation_level",
                    "assumptions", "failure_reason",
                ],
                "constraints": [
                    "仅输出结构化、可验证的 PEG 结果，不生成开放式投资建议。",
                    "输出字段名必须稳定，使用 earnings_growth_rate 和 peg_ratio，不要改写成 growth_rate 或 peg。",
                    "growth_years 当前仅支持1，表示同口径同比；不得把 financial_indicators 的季度 end_date 序列误当作连续年报序列。",
                    "若增长率缺失、非正或接近0，应返回失效原因，不允许伪造默认值继续估值。",
                ],
                "test_input": {
                    "symbol": "600519.SH",
                    "growth_years": 1,
                },
                "recommendations": recommendations,
            }

        if "pb" in normalized or "市净率" in text or "估值" in text:
            return {
                "tool_id": tool_id,
                "display_name": "PB估值区间计算",
                "description": "基于历史PB分位数及可选行业PB统计，输出股票估值区间与结构化依据。",
                "category": "fundamentals",
                "data_source": primary_source,
                "parameters": [
                    {"name": "symbol", "type": "string", "description": "股票代码", "required": True},
                    {"name": "market", "type": "string", "description": "市场标识，如 CN/HK/US", "required": False, "default": "CN"},
                    {"name": "lookback_years", "type": "integer", "description": "历史回溯年数", "required": False, "default": 5},
                    {"name": "valuation_method", "type": "string", "description": "估值方法：historical_percentile 或 historical_plus_industry", "required": False, "default": "historical_percentile"},
                    {"name": "include_industry_comparison", "type": "boolean", "description": "是否输出行业PB统计", "required": False, "default": True},
                ],
                "fields": [
                    "symbol", "current_pb", "pb_p20", "pb_p50", "pb_p80",
                    "valuation_lower", "valuation_mid", "valuation_upper",
                    "industry_pb_median", "industry_pb_mean", "peer_sample_size",
                    "assumptions", "invalidation_conditions", "data_as_of",
                ],
                "constraints": [
                    "仅输出结构化、可验证的估值结果，不生成开放式投资建议。",
                    "估值区间必须基于固定算法，不允许临时主观设定。",
                    "若存在行业对比，仅返回统计结果和样本规模，不展开长篇行业分析。",
                ],
                "test_input": {
                    "symbol": "600519.SH",
                    "market": "CN",
                    "lookback_years": 5,
                    "valuation_method": "historical_percentile",
                    "include_industry_comparison": True,
                },
                "recommendations": recommendations,
            }

        return {
            "tool_id": tool_id,
            "display_name": "新建功能 Skill",
            "description": "围绕单一明确目标提供可复用、可验证的结构化能力。",
            "category": category or "utility",
            "data_source": primary_source,
            "parameters": [
                {"name": "symbol", "type": "string", "description": "查询对象标识", "required": True},
            ],
            "fields": ["result", "data_as_of"],
            "constraints": [
                "保持单一明确目标，避免扩展为开放式分析工作流。",
                "输出需结构化且可验证。",
            ],
            "test_input": {"symbol": "600519.SH"},
            "recommendations": recommendations,
        }

    def _build_fallback_round1_response(self, user_message: str) -> str:
        blueprint = self._build_fallback_blueprint(user_message)
        recommendations = blueprint.get("recommendations") or {}
        stock_collections = recommendations.get("stock_collections") or []
        external_sources = recommendations.get("external_sources") or []
        return (
            "当前需求分析模型响应超时，我先按系统规则给你一个可继续执行的收敛草案，避免会话直接失败。\n\n"
            "## 初步理解\n"
            f"- 候选 tool_id: {blueprint['tool_id']}\n"
            f"- 功能定位: {blueprint['description']}\n"
            f"- 分类: {blueprint['category']}\n"
            f"- 主数据源: {blueprint['data_source']}\n"
            f"- 推荐复用的本地集合: {'、'.join(stock_collections) if stock_collections else '待确认'}\n"
            f"- 推荐外部来源: {'、'.join(external_sources) if external_sources else '待确认'}\n\n"
            "## 我帮你先收敛的职责边界\n"
            "- 这个 Skill 聚焦单一、确定性的估值/计算能力。\n"
            "- 可以包含必要的数据获取、字段整理和固定算法计算。\n"
            "- 不承担开放式研究报告、主观投资结论和多阶段编排。\n\n"
            "## 请优先确认这 4 项\n"
            "1. 估值方法是否固定为 historical_percentile，还是使用 historical_plus_industry？\n"
            f"2. 主数据源是否使用 {blueprint['data_source']}？如果不是，请直接指定。\n"
            "3. assumptions 和 invalidation_conditions 是否接受以结构化字段列表返回，而不是长文解释？\n"
            "4. 行业背景是否仅限返回同行 PB 统计结果，而不展开长篇行业分析？"
        )

    def _build_fallback_round2_response(self, session: SkillCreationSession, user_message: str) -> str:
        history = self._collect_conversation(session, user_message)
        blueprint = self._build_fallback_blueprint(history)
        parameter_names = "、".join(item["name"] for item in blueprint["parameters"])
        output_fields = "、".join(blueprint["fields"])
        return (
            "需求分析模型再次超时，我先基于当前对话把技术规格收敛到可确认状态。\n\n"
            "## 当前收敛结果\n"
            f"- tool_id: {blueprint['tool_id']}\n"
            f"- description: {blueprint['description']}\n"
            f"- data_source: {blueprint['data_source']}\n"
            f"- 参数建议: {parameter_names}\n"
            f"- 输出字段建议: {output_fields}\n\n"
            "## 待你拍板\n"
            "1. valuation_method 用哪个固定枚举值作为默认值？\n"
            "2. 是否保留 include_industry_comparison 参数？\n"
            "3. 输出里是否需要 industry_pb_median、industry_pb_mean、peer_sample_size 这三项？\n"
            "4. 如果数据不足，是返回部分结果并附错误字段，还是直接失败？"
        )

    def _build_fallback_spec_confirmation(self, history: str) -> str:
        blueprint = self._build_fallback_blueprint(history)
        parameters = "、".join(f"{item['name']}({item['type']})" for item in blueprint["parameters"])
        fields = "、".join(blueprint["fields"])
        constraints = "；".join(blueprint["constraints"])
        recommendations = blueprint.get("recommendations") or {}
        return (
            "## Skill 规格确认\n"
            f"- **tool_id**: {blueprint['tool_id']}\n"
            f"- **名称**: {blueprint['display_name']}\n"
            f"- **描述**: {blueprint['description']}\n"
            f"- **分类**: {blueprint['category']}\n"
            f"- **数据源**: {blueprint['data_source']}\n"
            f"- **推荐复用的本地集合**: {'、'.join(recommendations.get('stock_collections') or []) or '无'}\n"
            f"- **推荐外部来源**: {'、'.join(recommendations.get('external_sources') or []) or '无'}\n"
            f"- **参数**: {parameters}\n"
            f"- **返回字段**: {fields}\n"
            f"- **约束**: {constraints}\n\n"
            "以上规格由超时降级策略生成，用于保证流程可继续。以上规格是否正确？确认后将开始生成代码。"
        )

    def _generate_fallback_spec(self, conversation: str) -> Optional[SkillSpec]:
        blueprint = self._build_fallback_blueprint(conversation)
        try:
            validation_checks = self._build_default_validation_checks(
                expected_fields=blueprint["fields"],
                category=blueprint["category"],
            )
            return SkillSpec(
                tool_id=blueprint["tool_id"],
                display_name=blueprint["display_name"],
                description=blueprint["description"],
                category=blueprint["category"],
                data_source=blueprint["data_source"] if blueprint["data_source"] != "待确认" else "",
                parameters=[
                    {
                        "name": item["name"],
                        "type": item["type"],
                        "description": item["description"],
                        "required": item.get("required", True),
                        "default": item.get("default"),
                    }
                    for item in blueprint["parameters"]
                ],
                expected_output={
                    "type": "dict",
                    "fields": blueprint["fields"],
                    "description": blueprint["description"],
                },
                validation_checks=validation_checks,
                constraints=blueprint["constraints"],
                test_input=blueprint["test_input"],
            )
        except Exception as e:
            logger.error(f"启发式 SkillSpec 生成失败: {e}")
            return None

    @staticmethod
    def _build_default_validation_checks(
        expected_fields: list[str],
        category: str = "",
    ) -> list[dict[str, Any]]:
        checks: list[dict[str, Any]] = [
            {
                "name": "status_success",
                "description": "输出状态必须为 success/ok，不能返回 error 或伪成功结果",
                "required": True,
                "check_type": "status_success",
                "rule_level": "output",
                "blocking": True,
                "value_path": "output",
                "forbid_null": False,
            }
        ]

        if expected_fields:
            for field_name in expected_fields:
                checks.append(
                    {
                        "name": f"required_field:{field_name}",
                        "description": f"成功输出时必须包含字段 {field_name}",
                        "required": True,
                        "check_type": "required_field",
                        "rule_level": "data",
                        "blocking": True,
                        "field": field_name,
                        "value_path": "data",
                        "forbid_null": True,
                    }
                )
        else:
            checks.append(
                {
                    "name": "required_non_empty_payload",
                    "description": "成功输出时必须返回非空 data 负载",
                    "required": True,
                    "check_type": "required_non_empty_payload",
                    "rule_level": "data",
                    "blocking": True,
                    "value_path": "data",
                    "forbid_null": True,
                }
            )

        normalized = (category or "").lower()
        if normalized in ("fundamentals", "market", "technical", "utility", "news", "social"):
            checks.append(
                {
                    "name": "data_payload_object",
                    "description": "成功输出时 data 应为结构化对象或对象列表，不能只返回空文本说明",
                    "required": False,
                    "check_type": "required_non_empty_payload",
                    "rule_level": "data",
                    "blocking": False,
                    "value_path": "data",
                    "forbid_null": True,
                }
            )

        return checks

    @staticmethod
    def _normalize_validation_check_type(check_type: str, rule_level: str = "") -> str:
        normalized = (check_type or "").strip().lower()
        level = (rule_level or "").strip().lower()

        if normalized in ("status_success", "required_field", "required_non_empty_payload", "schema_condition"):
            return normalized
        if normalized in ("input", "input_check", "input_validation", "output", "output_check", "status"):
            return "status_success"
        if normalized in ("data", "data_check", "data_validation"):
            return "required_field"
        if normalized in ("business", "business_check", "custom"):
            return "custom"
        if level == "output":
            return "status_success"
        if level == "data":
            return "required_field"
        if level in ("business", "warning"):
            return "custom"
        return normalized or "custom"

    def _sanitize_validation_checks(
        self,
        checks: list[ValidationCheck],
        expected_fields: list[str],
    ) -> list[ValidationCheck]:
        sanitized: list[ValidationCheck] = []
        seen_names: set[str] = set()

        for check in checks:
            normalized_type = self._normalize_validation_check_type(check.check_type, check.rule_level)

            if normalized_type == "custom":
                continue

            if normalized_type == "status_success":
                normalized_check = ValidationCheck(
                    name=check.name or "status_success",
                    description=check.description or "输出状态必须为 success/ok",
                    required=True,
                    check_type="status_success",
                    rule_level="output",
                    blocking=True,
                    value_path="output",
                    forbid_null=False,
                )
            elif normalized_type == "required_non_empty_payload":
                normalized_check = ValidationCheck(
                    name=check.name or "required_non_empty_payload",
                    description=check.description or "成功输出时必须返回非空 data 负载",
                    required=check.required,
                    check_type="required_non_empty_payload",
                    rule_level="data",
                    blocking=check.blocking,
                    value_path=check.value_path or "data",
                    forbid_null=True,
                )
            elif normalized_type == "schema_condition":
                normalized_check = ValidationCheck(
                    name=check.name or "schema_condition",
                    description=check.description or "必须满足 schema 适用性规则",
                    required=check.required,
                    check_type="schema_condition",
                    rule_level=check.rule_level or "method",
                    blocking=check.blocking,
                    field=check.field,
                    value_path=check.value_path or "data",
                    forbid_null=check.forbid_null,
                    params=dict(check.params or {}),
                )
            else:
                field_name = (check.field or "").strip()
                if not field_name:
                    continue
                if expected_fields and field_name not in expected_fields:
                    continue
                normalized_check = ValidationCheck(
                    name=check.name or f"required_field:{field_name}",
                    description=check.description or f"成功输出时必须包含字段 {field_name}",
                    required=check.required,
                    check_type="required_field",
                    rule_level="data",
                    blocking=check.blocking,
                    field=field_name,
                    value_path=check.value_path or "data",
                    forbid_null=True,
                )

            dedupe_name = normalized_check.name or f"{normalized_check.check_type}:{normalized_check.field}"
            if dedupe_name in seen_names:
                continue
            seen_names.add(dedupe_name)
            sanitized.append(normalized_check)

        return sanitized

    @staticmethod
    def _enforce_known_skill_contracts(spec: SkillSpec) -> SkillSpec:
        tool_id = (spec.tool_id or "").strip().lower()
        description = (spec.description or "").lower()
        schema_context = resolve_financial_schema_context(spec)

        if tool_id == "calculate_peg_valuation" or "peg" in tool_id or "peg" in description:
            if (schema_context or {}).get("profile") == "peg":
                spec.category = "valuation"
                if not spec.expected_output.description:
                    spec.expected_output.description = "返回 PEG 估值结果及关键依据"
            else:
                spec.category = "fundamentals"
                canonical_fields = [
                    "symbol",
                    "name",
                    "industry",
                    "current_price",
                    "pe_ttm",
                    "earnings_growth_rate",
                    "peg_ratio",
                    "valuation_level",
                    "assumptions",
                    "failure_reason",
                ]
                alias_map = {
                    "growth_rate": "earnings_growth_rate",
                    "earnings_growth": "earnings_growth_rate",
                    "peg": "peg_ratio",
                    "failure_reasons": "failure_reason",
                    "invalidation_conditions": "failure_reason",
                }
                normalized_fields: list[str] = []
                seen_fields: set[str] = set()
                for field in list(spec.expected_output.fields or []) + canonical_fields:
                    normalized_field = alias_map.get(field, field)
                    if normalized_field in seen_fields:
                        continue
                    seen_fields.add(normalized_field)
                    normalized_fields.append(normalized_field)
                spec.expected_output.type = "dict"
                spec.expected_output.fields = normalized_fields
                if not spec.expected_output.description:
                    spec.expected_output.description = "返回 PEG 估值结果及关键依据"

            has_growth_years = any(param.name == "growth_years" for param in spec.parameters)
            if not has_growth_years:
                spec.parameters.append(
                    SkillParameter(
                        name="growth_years",
                        type="integer",
                        description="增长口径参数，当前仅支持1，表示同口径同比，不代表连续年报年数",
                        required=False,
                        default=1,
                    )
                )
            if "growth_years" not in spec.test_input:
                spec.test_input["growth_years"] = 1

        return spec

    def _ensure_spec_validation_checks(self, spec: SkillSpec) -> SkillSpec:
        spec = self._enforce_known_skill_contracts(spec)
        spec = self._align_spec_with_schema_contract(spec)
        existing_checks = list(spec.validation_checks or [])
        if not existing_checks:
            spec.validation_checks = [
                ValidationCheck(**item)
                for item in self._build_default_validation_checks(
                    expected_fields=list(spec.expected_output.fields or []),
                    category=spec.category,
                )
            ]
            spec.validation_checks = self._sanitize_validation_checks(
                list(spec.validation_checks or []),
                list(spec.expected_output.fields or []),
            )
            return spec

        existing_checks = self._sanitize_validation_checks(
            existing_checks,
            list(spec.expected_output.fields or []),
        )

        normalized_names = {check.name for check in existing_checks if check.name}
        if "status_success" not in normalized_names:
            existing_checks.insert(
                0,
                ValidationCheck(**self._build_default_validation_checks([], spec.category)[0]),
            )

        has_data_check = any(
            check.check_type in ("required_field", "required_non_empty_payload")
            for check in existing_checks
        )
        if not has_data_check:
            fallback_checks = self._build_default_validation_checks(
                expected_fields=list(spec.expected_output.fields or []),
                category=spec.category,
            )[1:]
            existing_checks.extend(ValidationCheck(**item) for item in fallback_checks)

        spec.validation_checks = self._sanitize_validation_checks(
            existing_checks,
            list(spec.expected_output.fields or []),
        )
        return spec

    @staticmethod
    def _align_spec_with_schema_contract(spec: SkillSpec) -> SkillSpec:
        schema_context = resolve_financial_schema_context(spec)
        if not schema_context:
            return spec

        contract_required_fields = get_contract_required_fields(schema_context)
        if contract_required_fields:
            existing_fields = [str(field).strip() for field in list(spec.expected_output.fields or []) if str(field).strip()]
            merged_fields = []
            seen_fields = set()
            for field_name in contract_required_fields + existing_fields:
                if not field_name or field_name in seen_fields:
                    continue
                seen_fields.add(field_name)
                merged_fields.append(field_name)
            spec.expected_output.type = "dict"
            spec.expected_output.fields = merged_fields

        contract = schema_context.get("contract") or {}
        if not (spec.expected_output.description or "").strip():
            contract_name = str(contract.get("name") or schema_context.get("contract_id") or "").strip()
            method_name = str((schema_context.get("method") or {}).get("name") or "").strip()
            description_parts = [item for item in [contract_name, method_name] if item]
            if description_parts:
                spec.expected_output.description = "；".join(description_parts) + " 的结构化输出"

        schema_constraints = build_schema_constraint_hints(schema_context)
        if schema_constraints:
            existing_constraints = [str(item).strip() for item in list(spec.constraints or []) if str(item).strip()]
            merged_constraints = []
            seen_constraints = set()
            for item in existing_constraints + schema_constraints:
                if not item or item in seen_constraints:
                    continue
                seen_constraints.add(item)
                merged_constraints.append(item)
            spec.constraints = merged_constraints

        schema_checks = build_schema_generated_checks(schema_context)
        if schema_checks:
            existing_checks = list(spec.validation_checks or [])
            existing_names = {check.name for check in existing_checks if check.name}
            for check in schema_checks:
                if check.name and check.name in existing_names:
                    continue
                existing_checks.append(check)
                if check.name:
                    existing_names.add(check.name)
            spec.validation_checks = existing_checks

        return spec

    @staticmethod
    def _infer_category_hint(text: str) -> str:
        normalized = (text or "").lower()
        keyword_map = {
            "news": ["新闻", "快讯", "公告", "headline", "news", "舆情", "事件"],
            "fundamentals": ["财务", "报表", "营收", "净利润", "分红", "估值", "基本面", "roe"],
            "technical": ["技术指标", "均线", "macd", "rsi", "k线", "日线", "走势", "波动率"],
            "market": ["行情", "盘口", "资金流", "成交额", "实时", "quote", "snapshot"],
            "social": ["情绪", "社交", "讨论", "论坛"],
        }
        for category, keywords in keyword_map.items():
            if any(keyword in normalized for keyword in keywords):
                return category
        return "utility"

    @staticmethod
    def _infer_data_source_hint(text: str) -> str:
        normalized = (text or "").lower()
        for source in ("tushare", "akshare", "finnhub", "google news", "google", "eastmoney", "东方财富"):
            if source.lower() in normalized:
                return source
        return ""

    def _build_catalog_context(self, text: str) -> str:
        category = self._infer_category_hint(text)
        data_source = self._infer_data_source_hint(text)
        local_collections = select_relevant_stock_collections(
            category=category,
            description=text,
            data_source=data_source,
            max_items=3,
        )
        external_sources = select_relevant_external_data_sources(
            category=category,
            description=text,
            data_source=data_source,
            max_items=3,
        )
        local_doc = render_stock_data_collection_doc(
            collections=local_collections,
            focus_summary="、".join(item["collection"] for item in local_collections),
        )
        external_doc = render_external_data_source_doc(
            sources=external_sources,
            focus_summary="、".join(item["display_name"] for item in external_sources),
        )
        factor_doc = build_factor_catalog_prompt_context(
            text,
            category=category,
        )
        sections = [local_doc, external_doc]
        if factor_doc:
            sections.append(factor_doc)
        return "\n\n".join(section for section in sections if section.strip())

    def build_recommendations(
        self,
        *,
        spec: Optional[SkillSpec] = None,
        conversation: str = "",
        fact_report: Optional["ImplementationFactReport"] = None,
    ) -> Dict[str, Any]:
        if spec is not None:
            category = getattr(spec, "category", "") or self._infer_category_hint(getattr(spec, "description", ""))
            data_source = getattr(spec, "data_source", "") or self._infer_data_source_hint(getattr(spec, "description", ""))
            description = getattr(spec, "description", "")
            constraints = getattr(spec, "constraints", []) or []
            expected_output = getattr(spec, "expected_output", None)
            expected_fields = getattr(expected_output, "fields", []) if expected_output else []
            parameter_names = [getattr(param, "name", "") for param in getattr(spec, "parameters", []) or []]
        else:
            category = self._infer_category_hint(conversation)
            data_source = self._infer_data_source_hint(conversation)
            description = conversation
            constraints = []
            expected_fields = []
            parameter_names = []

        # 当侦察层已找到推荐 helper 时，不再推荐本地集合和外部来源——
        # helper 函数内部已封装数据访问，直接推荐集合/来源会让用户困惑该以哪个为准。
        # category_hint / data_source_hint / recommended_factor_packs 等元信息仍然返回。
        has_recon_helpers = bool(fact_report and getattr(fact_report, "available_helpers", None))

        # ── 目录外数据源检测（改进点 2）：用户明确指定的来源不在已知目录时，
        # 显式返回 unknown_data_source 且不 fallback 凑推荐外部源，避免误导 ──
        from .external_data_source_catalog import is_known_external_source
        unknown_data_source = ""
        if spec is not None:
            spec_source = (getattr(spec, "data_source", "") or "").strip()
            if spec_source and not is_known_external_source(spec_source):
                unknown_data_source = spec_source

        if unknown_data_source:
            stock_collections: List[str] = []
            external_sources: List[str] = []
        elif has_recon_helpers:
            stock_collections: List[str] = []
            external_sources: List[str] = []
        else:
            local_collections = select_relevant_stock_collections(
                category=category,
                description=description,
                data_source=data_source,
                constraints=constraints,
                expected_fields=expected_fields,
                parameter_names=parameter_names,
                max_items=3,
            )
            external_sources_list = select_relevant_external_data_sources(
                category=category,
                description=description,
                data_source=data_source,
                constraints=constraints,
                expected_fields=expected_fields,
                parameter_names=parameter_names,
                max_items=3,
            )
            stock_collections = [item["collection"] for item in local_collections]
            external_sources = [item["source_id"] for item in external_sources_list]

        return {
            "category_hint": category,
            "data_source_hint": data_source,
            "stock_collections": stock_collections,
            "external_sources": external_sources,
            "unknown_data_source": unknown_data_source,
            "requirement_mode": classify_requirement_mode(spec) if spec is not None else "local_data",
            "recommended_factor_packs": infer_recommended_factor_packs(
                description,
                category=category,
                expected_fields=list(expected_fields or []),
            ),
        }

    # ==================== 会话管理 ====================

    def create_session(
        self,
        user_id: str = "",
        handoff_context: Optional[SkillHandoffContext] = None,
        iterate_skill_id: Optional[str] = None,
    ) -> SkillCreationSession:
        """创建新的 Skill 创建会话"""
        return SkillCreationSession(
            session_id=str(uuid.uuid4()),
            user_id=user_id,
            status=SessionStatus.GATHERING,
            handoff_context=handoff_context,
            iterate_skill_id=iterate_skill_id,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )

    @staticmethod
    def _build_handoff_context_text(session: SkillCreationSession) -> str:
        context = session.handoff_context
        if not context:
            return ""

        lines = [
            "当前这次会话来自上游流程交接，不是凭空新建需求。",
            f"- 来源: {context.source or 'unknown'}",
        ]
        if context.source_name:
            lines.append(f"- 上游对象: {context.source_name}")
        if context.source_spec_id:
            lines.append(f"- 上游规格 ID: {context.source_spec_id}")
        if context.target_capability:
            lines.append(f"- 待补目标能力: {context.target_capability}")
        if context.handoff_intent:
            lines.append(f"- 上游交接意图: {context.handoff_intent}")
        if context.agent_goal:
            lines.append(f"- 上游 Agent 目标: {context.agent_goal}")
        if context.gap_context:
            lines.append(f"- 当前缺口上下文: {context.gap_context[:800]}")
        if context.searched_capabilities:
            lines.append("- 上游已检索/评估过的能力:")
            for item in context.searched_capabilities[:8]:
                lines.append(f"  - {str(item)[:500]}")
        if context.confirmed_data_sources:
            lines.append("- 上游已确认的数据源/helper:")
            for item in context.confirmed_data_sources[:8]:
                lines.append(f"  - {str(item)[:500]}")
        if context.user_clarifications:
            lines.append("- 用户已澄清的关键结论:")
            for item in context.user_clarifications[:8]:
                lines.append(f"  - {str(item)[:500]}")
        if context.related_gaps:
            lines.append("- 同一次任务中的相关能力缺口:")
            for item in context.related_gaps[:8]:
                lines.append(f"  - {str(item)[:500]}")
        if context.known_failure_summaries:
            lines.append("- 同一次补齐任务中已知失败摘要（避免重复踩坑）:")
            for item in context.known_failure_summaries[:5]:
                lines.append(f"  - {str(item)[:500]}")
        if context.known_verified_facts:
            lines.append("- 同一次补齐任务中已验证环境事实:")
            for item in context.known_verified_facts[:8]:
                lines.append(f"  - {str(item)[:500]}")
        lines.extend([
            "- 你要先判断现有工具或已有 Skill 是否可复用。",
            "- 只有确实缺实现时，才把需求收敛成一个新增的最小能力单元。",
        ])
        return "\n".join(lines)

    @staticmethod
    def _build_handoff_guardrails(session: SkillCreationSession) -> str:
        context = session.handoff_context
        if not context:
            return ""

        target_capability = context.target_capability or "上游指定能力"
        source_name = context.source_name or context.source or "上游 Agent 创建流程"
        return (
            "## 上游交接约束（必须遵守）\n"
            f"- 这次需求来自 {source_name} 的能力缺口交接，不是普通的从零自由脑暴。\n"
            f"- 你必须围绕上游指定的目标能力“{target_capability}”继续收敛，除非用户明确改题。\n"
            "- 不要把上游已经确认的目标能力偷偷改写成另一个你更熟悉的实现，比如把“估值分析”擅自收缩成“PB估值区间计算”。\n"
            "- 若同一次补齐任务已经记录了失败摘要或已验证事实，必须显式避开这些已知错误路径，不要重新采用已被证伪的数据源/字段假设。\n"
            "- 若你判断完整目标更像 Agent/Workflow 而不是单个 Skill，要明确指出这是 Agent 级目标，并把当前 Skill 只定位为其中一个确定性的子能力；不要假装整个目标已经被一个 Skill 完整覆盖。\n"
            "- 若存在可复用的现有 Skill，应优先指出复用方案；若不存在，再定义新增 Skill 的最小职责边界。\n"
        )

    def process_user_input(
        self,
        session: SkillCreationSession,
        user_message: str,
        skill_context: Optional[str] = None,
    ) -> Tuple[SkillCreationSession, str]:
        """
        处理用户输入，推进对话

        Args:
            session: 当前会话
            user_message: 用户消息
            skill_context: 迭代模式下已有 Skill 的上下文（JSON 字符串）

        Returns:
            (更新后的会话, AI 回复消息)
        """
        session.updated_at = datetime.utcnow()

        # 判断是否为迭代模式
        is_iteration = bool(session.iterate_skill_id)

        # 如果是第一轮，先做清晰度评估和边界检测
        if session.current_round == 0:
            try:
                clarity = self._assess_clarity(user_message)
            except Exception as exc:
                logger.error("清晰度评估失败，降级为 MEDIUM: %s", exc)
                clarity = ClarityLevel.MEDIUM
            session.clarity_level = clarity

            try:
                boundary_context = self._build_handoff_context_text(session)
                boundary = self._check_boundary(
                    user_message,
                    conversation_context=boundary_context or None,
                )
            except Exception as exc:
                logger.error("边界检测失败，降级为通过: %s", exc)
                boundary = BoundaryCheck(within_boundary=True, reason="边界检测失败，默认通过")
            session.boundary_check = boundary

            # 如果超出边界，返回拆分建议
            if not boundary.within_boundary:
                ai_msg = self._build_boundary_warning(boundary)
                round_obj = ConversationRound(
                    round_number=1,
                    ai_message=ai_msg,
                    user_message=user_message,
                )
                session.rounds.append(round_obj)
                session.current_round = 1
                return session, ai_msg

        # 推进对话
        session.current_round += 1
        max_rounds = self._get_max_rounds(session.clarity_level)

        # 第 2 轮及以后：根据用户最新反馈重新评估边界，复杂度提醒会随之更新
        if session.current_round >= 2:
            try:
                conversation = self._collect_conversation(session, user_message)
                boundary = self._check_boundary(user_message, conversation_context=conversation)
                session.boundary_check = boundary
            except Exception as exc:
                logger.error("第%d轮边界检测失败，跳过: %s", session.current_round, exc)

        if session.current_round >= max_rounds:
            # 迭代模式：第 1 轮绝不能直接跳到最后轮，至少需要一次迭代引导
            if is_iteration and session.current_round == 1:
                if skill_context:
                    try:
                        ai_msg = self._build_iteration_round1_response(
                            session, user_message, skill_context
                        )
                    except Exception as exc:
                        logger.error("迭代模式第1轮需求分析 LLM 调用失败，使用降级回复: %s", exc)
                        ai_msg = self._build_fallback_round1_response(user_message)
                else:
                    ai_msg = self._build_round1_response(session, user_message)
            else:
                # 最后一轮：生成规格确认
                try:
                    ai_msg = self._build_spec_confirmation(session, user_message)
                except Exception as exc:
                    logger.error("最后一轮规格确认 LLM 调用失败，使用降级回复: %s", exc)
                    ai_msg = self._build_fallback_spec_confirmation(
                        self._collect_conversation(session, user_message)
                    )
        elif session.current_round == 1:
            # 第 1 轮
            if is_iteration and skill_context:
                # 迭代模式：使用迭代专用提示词
                try:
                    ai_msg = self._build_iteration_round1_response(
                        session, user_message, skill_context
                    )
                except Exception as exc:
                    logger.error("迭代模式第1轮需求分析 LLM 调用失败，使用降级回复: %s", exc)
                    ai_msg = self._build_fallback_round1_response(user_message)
            else:
                # 普通模式：初步理解 + 功能点拆解
                try:
                    ai_msg = self._build_round1_response(session, user_message)
                except Exception as exc:
                    logger.error("第1轮需求分析 LLM 调用失败，使用降级回复: %s", exc)
                    ai_msg = self._build_fallback_round1_response(user_message)
        else:
            # 第 2 轮：技术细化
            try:
                ai_msg = self._build_round2_response(session, user_message)
            except Exception as exc:
                logger.error("第2轮需求分析 LLM 调用失败，使用降级回复: %s", exc)
                ai_msg = self._build_fallback_round2_response(session, user_message)

        round_obj = ConversationRound(
            round_number=session.current_round,
            ai_message=ai_msg,
            user_message=user_message,
        )
        session.rounds.append(round_obj)

        return session, ai_msg

    def confirm_spec(
        self,
        session: SkillCreationSession,
        user_message: str,
        fact_report: Optional[ImplementationFactReport] = None,
        parent_contract: Optional[Dict[str, Any]] = None,
    ) -> Tuple[SkillCreationSession, Optional[SkillSpec]]:
        """
        用户确认规格后，生成 SkillSpec

        Args:
            session: 当前会话
            user_message: 用户的确认消息（"确认" / 补充修改）
            fact_report: 侦察报告（侦察前置模式），用于增强 spec 生成
            parent_contract: 迭代模式的父版本契约（含完整参数/约束/代码），
                传入时走升级补丁模式：LLM 只输出 delta，父契约原样继承

        Returns:
            (更新后的会话, 生成的 SkillSpec 或 None)
        """
        # 收集所有对话内容
        conversation = self._collect_conversation(session, user_message)

        # LLM 生成结构化 SkillSpec
        spec = self._generate_spec(
            conversation, fact_report=fact_report, session=session,
            parent_contract=parent_contract,
        )

        if spec:
            session.spec = spec
            session.spec_confirmed = True
            session.status = SessionStatus.CONFIRMED
            session.updated_at = datetime.utcnow()

        return session, spec

    def preview_spec(
        self,
        session: SkillCreationSession,
        user_message: str = "确认",
        fact_report: Optional[ImplementationFactReport] = None,
        parent_contract: Optional[Dict[str, Any]] = None,
    ) -> Optional[SkillSpec]:
        """
        仅生成 SkillSpec 预览，不修改会话状态。
        用于规格确认步骤展示，用户确认后再调用 confirm_spec 执行管线。

        parent_contract: 迭代模式的父版本契约，传入时走升级补丁模式
        """
        conversation = self._collect_conversation(session, user_message)
        return self._generate_spec(
            conversation, fact_report=fact_report, session=session,
            parent_contract=parent_contract,
        )

    # ==================== 清晰度评估 ====================

    def _assess_clarity(self, user_message: str) -> ClarityLevel:
        """评估需求清晰度"""
        client = self._get_quick_client() or self._get_client()
        prompt = (
            "请评估以下用户需求的清晰度（1-5分）。\n"
            "5分=非常清晰（明确了数据源、参数、输出），"
            "3分=一般（有主题但缺细节），"
            "1分=模糊（只有大方向）。\n\n"
            f"用户需求: {user_message}\n\n"
            "只回复一个数字（1-5），不要其他内容。"
        )
        try:
            response = client.chat([Message(role="user", content=prompt)])
            score_text = (response.content or "3").strip()
            score = int(re.search(r"[1-5]", score_text).group())
        except Exception:
            score = 3

        if score >= 4:
            return ClarityLevel.HIGH
        elif score >= 3:
            return ClarityLevel.MEDIUM
        else:
            return ClarityLevel.LOW

    # ==================== 边界检测 ====================

    def _check_boundary(
        self, user_message: str, conversation_context: Optional[str] = None
    ) -> BoundaryCheck:
        """检测需求是否超出单个 Skill 范围。若有对话历史，基于最新共识重新评估。"""
        client = self._get_quick_client() or self._get_client()
        if conversation_context:
            prompt = (
                "你是 Skill 边界检测专家。一个 Skill 应该聚焦一个明确、可复用的功能单元。"
                "它可以包含必要的数据获取、清洗转换、格式整理、确定性计算、规则判断或轻量聚合；"
                "但不应承载开放式研究、主观投资结论、跨多个独立目标的长链路编排。\n\n"
                f"{SKILL_SEMANTICS_GUIDANCE}\n\n"
                f"{SKILL_BOUNDARY_EXAMPLES}\n"
                "**重要**：用户经过多轮对话后，需求可能已显著调整，例如：\n"
                "- 选择了某个子方案（如「方案A/B/C」）\n"
                "- 改为通过 API 获取（而非 PDF 解析）\n"
                "- 缩小了范围或简化了实现方式\n\n"
                "你必须基于**用户最新一轮的明确选择**重新评估，而非沿用首轮的判断。"
                "若用户已将需求收敛为单一明确能力，即使内部需要组合紧密相关的数据来源或做确定性计算，也不应机械判为越界。"
                "只有当需求同时包含多个彼此独立的功能目标、开放式分析结论或多阶段工作流时，才建议拆分。"
                "不要因为出现“计算”“估值区间”“解释假设”“行业背景”这些词就自动判定为 Agent 职责，必须结合其是否确定、可验证来判断。\n\n"
                f"对话历史:\n{conversation_context}\n\n"
                "若判定超出边界：concerns 必须聚焦真正的越界点，decomposition_suggestions 必须按功能边界拆分，"
                "不要输出“Skill 只能取数”或“凡是解释都归 Agent”这类错误前提。\n\n"
                "请用 JSON 回复（不要其他内容）：\n"
                '{"within_boundary": true/false, "complexity_score": 1-5, '
                '"concerns": ["问题1", ...], "decomposition_suggestions": ["建议1", ...]}'
            )
        else:
            prompt = (
                "你是 Skill 边界检测专家。一个 Skill 应该聚焦一个明确、可复用的功能单元。"
                "它可以包含必要的数据获取、清洗转换、格式整理、确定性计算、规则判断或轻量聚合；"
                "但不应承载开放式研究、主观投资结论、跨多个独立目标的长链路编排。\n"
                f"{SKILL_SEMANTICS_GUIDANCE}\n\n"
                f"{SKILL_BOUNDARY_EXAMPLES}\n"
                "以下需求是否超出了单个 Skill 的范围？\n\n"
                f"需求: {user_message}\n\n"
                "若判定超出边界：concerns 必须聚焦真正的越界点，decomposition_suggestions 必须按功能边界拆分，"
                "不要输出“Skill 只能取数”或“凡是解释都归 Agent”这类错误前提。\n\n"
                "请用 JSON 回复（不要其他内容）：\n"
                '{"within_boundary": true/false, "complexity_score": 1-5, '
                '"concerns": ["问题1", ...], "decomposition_suggestions": ["建议1", ...]}'
            )
        try:
            response = client.chat([Message(role="user", content=prompt)])
            raw = response.content or "{}"
            logger.info(f"边界检测 LLM 原始返回 ({len(raw)} 字符):\n{raw}")
            data = self._parse_llm_json(raw)
            if data:
                return BoundaryCheck(**data)
        except Exception as e:
            logger.warning(f"边界检测失败: {e}")

        return BoundaryCheck()

    # ==================== 对话构建 ====================

    @staticmethod
    def _get_max_rounds(clarity: Optional[ClarityLevel]) -> int:
        """根据清晰度决定对话轮数"""
        if clarity == ClarityLevel.HIGH:
            return 1
        elif clarity == ClarityLevel.MEDIUM:
            return 2
        return 3

    def _build_round1_response(self, session: SkillCreationSession, user_message: str) -> str:
        """第 1 轮：初步理解 + 功能点拆解 + 数据源引导"""
        catalog_context = self._build_catalog_context(user_message)
        handoff_context = self._build_handoff_context_text(session)
        handoff_guardrails = self._build_handoff_guardrails(session)
        prompt = (
            "你是 Skill 需求分析专家，不仅理解用户需求，更要主动给出专业建议。\n\n"
            "## 项目背景\n"
            "你所在的是 **TradingAgents-CN**：面向中文用户的多智能体股票分析学习平台。"
            "平台专注 A股/港股/美股 的合规研究与策略实验，使用 AI Agent 调用各类可复用 Skill 完成分析。"
            "用户正在创建的 Skill 将作为 Agent 可调用的可复用功能工具，可用于数据获取、清洗转换、指标计算、规则判断、结构化汇总等明确且可验证的能力。"
            "Skill 不等于只能取数，但应避免把开放式研究、主观投资结论或完整多阶段工作流塞进单个 Skill。\n\n"
            f"{SKILL_SEMANTICS_GUIDANCE}\n\n"
            f"{STANDARD_FINANCIAL_APIS_SUMMARY}\n\n"
            "## 你的任务\n"
            "1. 复述你的理解\n"
            "2. 用表格列出功能点（目标市场、输入参数、返回字段、调用方式）\n"
            "3. **主动建议**：根据用户需求给出专业建议（如更合适的实现方式、常见坑、最佳实践）\n"
            "4. **实现路径引导（重要）**：\n"
            "   - **首先检查**：用户需求是否已被上方「项目内置标准金融数据能力」中的函数覆盖？\n"
            "   - 如果已覆盖：直接告知用户「项目已内置该能力（XXX 函数），无需选择数据源，数据源由项目统一配置」，"
            "并说明该函数的返回内容和适用场景，不需要再问数据源。\n"
            "   - 如果未覆盖：简要说明项目暂无直接覆盖的标准函数，可建议通过 skill_runtime 公开接口组合实现，"
            "或提及可能相关的外部数据源方向，但**不要让用户选择数据源**——数据源由项目统一配置和管理。\n"
            "   - **绝对不要**问用户「您偏好 AKShare 还是 Tushare」之类的问题，这不是用户应该关心的事。\n\n"
            "5. 提出其他需要确认的问题（如返回格式、风险判断规则、批量需求等）\n\n"
            f"{handoff_guardrails}\n"
            f"上游交接上下文:\n{handoff_context or '无'}\n\n"
            f"当前按需求命中的数据上下文:\n{catalog_context}\n\n"
            f"用户描述: {user_message}"
        )
        try:
            content = self._chat_with_quick_fallback(
                [Message(role="user", content=prompt)], stage="第1轮需求分析"
            )
            if content:
                return content
            self._raise_analysis_error("第1轮需求分析")
        except Exception as e:
            logger.error(f"第1轮需求分析失败: {e}")
            self._raise_analysis_error("第1轮需求分析", e)

    def _build_iteration_round1_response(
        self,
        session: SkillCreationSession,
        user_message: str,
        skill_context: str,
    ) -> str:
        """迭代模式第 1 轮：展示现有 Skill 现状，引导用户描述需要调整的内容"""
        prompt = (
            "你是 Skill 迭代优化专家。用户正在优化一个已有的 Skill，以下是当前 Skill 的信息：\n\n"
            f"```json\n{skill_context}\n```\n\n"
            "## 你的任务\n"
            "请用**极简**的方式回复，不要生成规格书、不要列功能表格、不要分析数据源：\n\n"
            "**第一步：一句话介绍当前 Skill**\n"
            "用大白话告诉用户：这个 Skill 做了什么、输入什么、输出什么。最多 3 行。\n\n"
            "**第二步：理解用户的改进意图并引导**\n"
            "用户说：" + user_message + "\n"
            "请基于用户的描述，判断他的意图属于哪一类（Bug 修复 / 功能增强 / 结果优化 / 其他），"
            "然后**只问 1-2 个最关键的确认问题**，引导用户说出更具体的改进方向。\n\n"
            "**约束：**\n"
            "- 不要生成工具规格确认（tool_id/参数/返回字段/数据源等），那些留给后面的流程处理\n"
            "- 不要问数据源选择、不要列本地集合、不要提 AKShare/Tushare\n"
            "- 本次回复的核心目的：让用户确认你的理解，然后说出更多改进细节\n"
            "- 如果用户的想法跟当前 Skill 实现完全冲突，温和建议重新创建"
        )
        try:
            content = self._chat_with_quick_fallback(
                [Message(role="user", content=prompt)], stage="迭代模式第1轮需求分析"
            )
            if content:
                return content
            self._raise_analysis_error("迭代模式第1轮需求分析")
        except Exception as e:
            logger.error(f"迭代模式第1轮需求分析失败: {e}")
            self._raise_analysis_error("迭代模式第1轮需求分析", e)

    def _build_round2_response(
        self, session: SkillCreationSession, user_message: str
    ) -> str:
        """第 2 轮：技术细化"""
        history = self._collect_conversation(session, user_message)
        catalog_context = self._build_catalog_context(history)
        handoff_context = self._build_handoff_context_text(session)
        handoff_guardrails = self._build_handoff_guardrails(session)
        prompt = (
            "你是 Skill 需求分析专家，所在项目是 **TradingAgents-CN**（A股/港股/美股多智能体股票分析平台）。"
            "正在进行第 2 轮技术细化。\n\n"
            f"{STANDARD_FINANCIAL_APIS_SUMMARY}\n\n"
            "请根据之前的对话和用户新的反馈：\n"
            "1. 确认技术方案（返回格式、风险判断规则等）\n"
            "2. **主动建议**：根据用户需求给出技术方案建议（如推荐实现方式、边界情况处理）\n"
            "3. **实现路径确认**：确认用户需求是否已被项目内置标准函数覆盖。"
            "如果已覆盖，说明将复用哪个函数；如果未覆盖，说明将通过 skill_runtime 公开接口组合实现。"
            "**不要问用户选择数据源**——数据源由项目统一配置。\n"
            "4. 给出推荐方案让用户选择（而不是问开放性问题）\n"
            "5. 列出最终的参数和返回字段清单\n\n"
            f"{handoff_guardrails}\n"
            f"上游交接上下文:\n{handoff_context or '无'}\n\n"
            f"当前按需求命中的数据上下文:\n{catalog_context}\n\n"
            f"对话历史:\n{history}"
        )
        try:
            content = self._chat_with_quick_fallback(
                [Message(role="user", content=prompt)], stage="第2轮需求分析"
            )
            if content:
                return content
            self._raise_analysis_error("第2轮需求分析")
        except Exception as e:
            logger.error(f"第2轮需求分析失败: {e}")
            self._raise_analysis_error("第2轮需求分析", e)

    def _build_spec_confirmation(
        self, session: SkillCreationSession, user_message: str
    ) -> str:
        """最后一轮：生成规格确认摘要"""
        history = self._collect_conversation(session, user_message)
        catalog_context = self._build_catalog_context(history)
        handoff_context = self._build_handoff_context_text(session)
        handoff_guardrails = self._build_handoff_guardrails(session)
        prompt = (
            "你是 Skill 需求分析专家，请根据所有对话内容生成最终的规格确认摘要。\n"
            "用以下格式输出：\n"
            "## Skill 规格确认\n"
            "- **tool_id**: xxx\n"
            "- **名称**: xxx\n"
            "- **描述**: xxx\n"
            "- **分类**: xxx\n"
            "- **数据源**: xxx\n"
            "- **推荐复用的本地集合**: 列表\n"
            "- **推荐外部来源**: 列表（若本地即可满足，可写无或仅作为降级来源）\n"
            "- **参数**: 列表\n"
            "- **返回字段**: 列表\n"
            "- **约束**: 列表\n\n"
            "要求：推荐复用项必须优先引用当前系统已命中的集合与外部来源，不要编造系统里没有整理过的数据源。\n\n"
            "最后问用户: '以上规格是否正确？确认后将开始生成代码。'\n\n"
            f"{handoff_guardrails}\n"
            f"上游交接上下文:\n{handoff_context or '无'}\n\n"
            f"当前按需求命中的数据上下文:\n{catalog_context}\n\n"
            f"对话历史:\n{history}"
        )
        try:
            content = self._chat_with_quick_fallback(
                [Message(role="user", content=prompt)], stage="规格确认摘要生成"
            )
            if content:
                return content
            self._raise_analysis_error("规格确认摘要生成")
        except Exception as e:
            logger.error(f"规格确认摘要生成失败: {e}")
            self._raise_analysis_error("规格确认摘要生成", e)

    @staticmethod
    def _build_boundary_warning(check: BoundaryCheck) -> str:
        """构建边界警告消息"""
        concerns = "\n".join(f"  - {c}" for c in check.concerns)
        suggestions = "\n".join(
            f"  {i+1}. {s}" for i, s in enumerate(check.decomposition_suggestions)
        )
        return (
            "⚠️ 你的需求包含了多个功能层级，建议拆分：\n\n"
            f"**关注点：**\n{concerns}\n\n"
            f"**建议拆分为：**\n{suggestions}\n\n"
            "每个 Skill 应聚焦一个明确功能，可以包含必要的数据获取与确定性处理；"
            "开放式分析、投资结论和多阶段编排由 Agent/Workflow 完成。\n"
            "若你的目标本身是一个可验证的确定性功能，也可以继续收敛为单个 Skill，而不是被迫拆成“纯取数层”。\n"
            "请选择一个明确的能力单元开始创建，或者告诉我你想先落哪一段功能。"
        )

    # ==================== 对话收集 & 规格生成 ====================

    @staticmethod
    def _collect_conversation(
        session: SkillCreationSession, current_message: str = ""
    ) -> str:
        """收集所有对话历史为格式化字符串"""
        parts = []
        handoff_context = RequirementAnalyzer._build_handoff_context_text(session)
        if handoff_context:
            parts.append(f"[系统交接上下文]:\n{handoff_context}")
        for r in session.rounds:
            parts.append(f"[用户 - 第{r.round_number}轮]: {r.user_message}")
            parts.append(f"[AI - 第{r.round_number}轮]: {r.ai_message}")
        if current_message:
            parts.append(f"[用户 - 最新]: {current_message}")
        return "\n\n".join(parts)

    def _generate_spec(
        self,
        conversation: str,
        fact_report: Optional[ImplementationFactReport] = None,
        session: Optional[SkillCreationSession] = None,
        parent_contract: Optional[Dict[str, Any]] = None,
    ) -> Optional[SkillSpec]:
        """通过 LLM 将对话转化为结构化 SkillSpec

        Args:
            conversation: 收集的对话内容
            fact_report: 侦察报告（侦察前置模式），包含真实字段可用性
            session: 当前会话（用于迭代模式识别，传入时会保留原 tool_id 等版本关系）
            parent_contract: 父版本契约（服务层加载，含完整参数/约束/代码）。
                传入时优先走升级补丁模式（LLM 只输出 delta，父契约确定性继承），
                补丁生成失败时降级为旧版全量生成（prompt 中注入父契约约束）。
        """
        # 升级补丁模式：父契约 + delta，未提及的字段没有输出通道，
        # 结构上杜绝「重新发明参数定义/接口约束」（曾把 int=11 重写成
        # 字符串「月度销量榜」导致接口静默回退热度榜，死循环 4 次尝试）
        if parent_contract:
            spec = self._generate_upgrade_spec(conversation, parent_contract)
            if spec:
                return spec
            logger.warning(
                "[UpgradePatch] 补丁生成失败，降级为全量规格生成（注入父契约上下文）"
            )

        # 规格生成本质是结构化转录（对话已把参数/字段确认清楚），
        # 优先走快速模型，失败回退主模型
        catalog_context = self._build_catalog_context(conversation)
        handoff_guardrails = ""
        if "[系统交接上下文]:" in conversation:
            handoff_guardrails = (
                "6. 这次会话带有上游交接上下文，必须保留上游指定能力，不要把它改写成另一个更窄、更偷懒的实现。\n"
                "7. 若原目标显然是 Agent/Workflow 级目标，当前 SkillSpec 只能定义为其中一个确定性的子能力，并在 description/constraints 中明确这一点。\n"
                "8. 禁止把“估值分析”“研究分析”“多维判断”这类目标直接偷换成单一 PB/PE 指标计算器，除非用户明确只要这个子功能。\n\n"
            )

        # 🔧 迭代模式约束：新版本用 _v{N} 后缀，体现版本关系
        iteration_guardrails = ""
        is_iteration = bool(session and session.iterate_skill_id)
        if is_iteration:
            original_tool_id = session.iterate_skill_id or ""
            iteration_guardrails = (
                f"9. **迭代模式约束（必须遵守）**：本次是迭代优化已有 Skill，原 Skill 的 tool_id 是 `{original_tool_id}`。\n"
                f"   - 生成的 spec.tool_id **必须以 `_v2`、`_v3` 等版本后缀结尾**（首次迭代用 `_v2`，二次迭代用 `_v3`，以此类推）。\n"
                f"   - **禁止沿用原 tool_id**（会覆盖原 Skill，影响已绑定到 Agent 的旧版本）。\n"
                f"   - 命名格式：`{{原tool_id}}_v{{新版本号}}`，如 `{original_tool_id}_v2`。\n"
                f"   - display_name 必须以 ` v{{新版本号}}` 结尾，可附加简短说明，如 `xxx v2`。\n"
                f"   - 这是对原 Skill 的升级，不是创建全新 Skill；功能要在原 Skill 基础上改进，不要完全推翻重写。\n"
                f"   - 在 constraints 中追加一条：`本 Skill 是 {original_tool_id} 的迭代优化版本`。\n\n"
            )
            # 降级路径的父契约注入：即使全量生成，参数定义/接口约束也必须以
            # 父版本多轮验证的事实为准，不得重新发明
            if parent_contract:
                iteration_guardrails += (
                    "10. **父版本契约（多轮实测验证的事实，必须原样继承）**：\n"
                    f"```json\n{parent_contract_to_json(parent_contract)}\n```\n"
                    "    - 同名参数的名称/类型/默认值/取值语义、接口约束（URL/请求头/取值要求）"
                    "必须与父版本完全一致，除非升级需求明确要求修改\n"
                    "    - 父版本已有的参数和输出字段不得丢失\n\n"
                )

        # 侦察事实注入：将真实的字段可用性、Helper 函数信息注入 prompt
        recon_context = ""
        if fact_report:
            recon_context = self._build_recon_context_for_spec(fact_report)

        prompt = (
            "你是 Skill 规格生成器。请根据以下对话内容，"
            "提取出一个结构化的 Skill 规格（JSON 格式）。\n\n"
            "**重要**：\n"
            "1. 若对话中有「[用户 - 最新]」或用户明确选择方案（如选 A/B/C），必须严格按用户选择生成，不可忽略。\n"
            "2. Skill 可以是明确的功能实现，不局限于纯数据查询；允许必要的确定性计算、格式整理和轻量聚合。\n"
            "3. data_source 填写对话中确定的主数据源标识；若实现会组合紧密相关的数据来源，则填写主数据源，并在 constraints 中说明附加来源或降级策略。\n"
            "4. 不要写「需通过参数传入」等模糊描述。\n\n"
            "5. 优先让 spec 与当前系统可复用的本地集合、外部来源保持一致；若本地可满足，不要强行指定外部源。\n\n"
            "5.1 如果这是估值类或方法型 Skill，expected_output.fields 必须优先贴近系统已有 schema 契约，不要自造一套字段名。\n"
            "5.2 constraints 应明确写出方法适用边界、禁止模式和必要叙述要求，而不是泛泛地写'返回估值结果'。\n\n"
            "6. **命名规则（关键）**：tool_id 必须使用 snake_case，且 **禁止与引用的底层 Python 函数名相同**。\n"
            "   例如：如果实现要调用 get_stock_news 函数，tool_id 应命名为 get_unified_news 或 fetch_news_by_ticker，\n"
            "   而不能也叫 get_stock_news。命名冲突会导致 Skill 执行时进入无限递归。\n"
            "   建议命名格式：get_<数据源>_<功能>（如 get_eastmoney_news、fetch_tushare_financials）。\n\n"
            f"{handoff_guardrails}"
            f"{iteration_guardrails}"
            f"{SKILL_SEMANTICS_GUIDANCE}\n\n"
            f"当前按需求命中的数据上下文:\n{catalog_context}\n\n"
        )

        # 插入侦察事实上下文
        if recon_context:
            prompt += (
                f"### 侦察层发现的实现事实（真实数据源探测结果）\n"
                f"{recon_context}\n\n"
                "**基于侦察事实的约束**：\n"
                "- expected_output.fields 只能包含侦察证实可获取的字段，不要凭想象添加数据源中不存在的字段。\n"
                "- 如果侦察上下文已经提供金融 schema 方法/契约/规则，expected_output.fields 与 constraints 必须优先对齐这些 schema 对象。\n"
                "- 若某字段覆盖率低或不可用，应在 constraints 中注明降级策略，而非标记为必填。\n"
                "- 优先使用侦察发现的 Helper 函数，而非猜测 API 调用方式。\n\n"
            )

        prompt += f"对话内容:\n{conversation}\n\n"
        prompt += (
            "请严格用以下 JSON 格式输出（不要其他内容）：\n"
            "参数命名规则（必须遵守）：\n"
            "- parameters 中的 name 必须是合法 Python 标识符（snake_case，如 month、rank_data_type）\n"
            "- HTTP 请求头（User-Agent/Referer/Token 等）、认证密钥、接口 URL 是实现细节，"
            "写入 constraints（如\"请求需携带 User-Agent 和 Referer 请求头\"），严禁列为函数参数\n"
            "- parameters 只收录调用方需要传入的业务参数（如月份、代码、类型），"
            "函数内部写死的常量不收录\n\n"
            "{\n"
            '  "tool_id": "snake_case_id",\n'
            '  "display_name": "中文显示名称",\n'
            '  "description": "功能描述",\n'
            '  "category": "news|market|fundamentals|social|technical|utility|valuation",\n'
            '  "data_source": "对话中确定的数据源标识",\n'
            '  "parameters": [\n'
            '    {"name": "param1", "type": "string", "description": "说明", '
            '"required": true}\n'
            "  ],\n"
            '  "expected_output": {\n'
            '    "type": "list[dict]",\n'
            '    "fields": ["field1", "field2"],\n'
            '    "description": "输出描述"\n'
            "  },\n"
            '  "validation_checks": [\n'
            '    {"name": "status_success", "description": "输出状态必须成功", "required": true, "check_type": "status_success", "rule_level": "output", "blocking": true, "value_path": "output", "forbid_null": false},\n'
            '    {"name": "required_field:field1", "description": "成功输出时 field1 不可缺失", "required": true, "check_type": "required_field", "rule_level": "data", "blocking": true, "field": "field1", "value_path": "data", "forbid_null": true}\n'
            "  ],\n"
            '  "constraints": ["约束1"],\n'
            '  "test_input": {"param1": "测试值"}\n'
            "}"
        )
        # 带 1 次重试的 JSON 解析
        max_attempts = 2
        last_raw = ""
        last_error: Optional[Exception] = None

        for attempt in range(max_attempts):
            try:
                if attempt == 0:
                    last_raw = self._chat_with_quick_fallback(
                        [Message(role="user", content=prompt)], stage="规格生成"
                    )
                else:
                    # 第 2 次：将上次失败的输出反馈给 LLM，要求修正
                    retry_prompt = (
                        f"你上次的输出无法被解析为合法 JSON，请修正后重新输出。\n"
                        f"上次输出:\n{last_raw[:8000]}\n\n"
                        f"错误: {last_error}\n\n"
                        "请只输出纯 JSON，不要包含任何 Markdown 标记或解释文字。"
                    )
                    last_raw = self._chat_with_quick_fallback(
                        [
                            Message(role="user", content=prompt),
                            Message(role="assistant", content=last_raw[:8000]),
                            Message(role="user", content=retry_prompt),
                        ],
                        stage="规格生成",
                    )

                logger.info(f"SkillSpec LLM 原始返回 (attempt {attempt + 1}/{max_attempts}, {len(last_raw)} 字符):\n{last_raw}")
                data = self._parse_llm_json(last_raw)
                if data:
                    self._sanitize_spec_params(data)
                    self._ensure_interface_spec_constraints(data, conversation)
                    return self._ensure_spec_validation_checks(SkillSpec(**data))

                last_error = ValueError("LLM 未返回合法 JSON")
                logger.warning(f"SkillSpec JSON 解析失败 (attempt {attempt + 1}/{max_attempts}): {last_error}")

            except Exception as e:
                last_error = e
                logger.warning(f"SkillSpec 生成异常 (attempt {attempt + 1}/{max_attempts}): {e}")

        logger.error(f"SkillSpec 生成最终失败: {last_error}")
        self._raise_analysis_error("SkillSpec 生成", last_error)
        return None

    def _generate_upgrade_spec(
        self, conversation: str, parent_contract: Dict[str, Any]
    ) -> Optional[SkillSpec]:
        """升级补丁模式：LLM 读父契约 + 父代码后只输出 delta，确定性套用成新 spec。

        与全量规格生成的本质区别（对齐编程 agent 的 edit-apply）：
        - LLM 的输出通道只有「变更清单」，未提及的参数/约束/字段
          由 apply_upgrade_patch 从父版本原样继承——想重写都没有通道
        - 父代码完整注入（不截断），满足「先读懂原代码再读新需求」

        Returns:
            套用补丁后的 SkillSpec；补丁生成/套用失败返回 None（调用方降级）
        """
        prompt = build_upgrade_patch_prompt(parent_contract, conversation)
        last_raw = ""
        last_error: Optional[Exception] = None

        for attempt in range(2):
            try:
                if attempt == 0:
                    last_raw = self._chat_with_quick_fallback(
                        [Message(role="user", content=prompt)], stage="升级补丁生成"
                    )
                else:
                    retry_prompt = (
                        f"你上次的输出无法解析为补丁 JSON，请修正后重新输出。\n"
                        f"上次输出:\n{last_raw[:6000]}\n\n"
                        f"错误: {last_error}\n\n"
                        "请只输出纯 JSON，不要包含任何 Markdown 标记或解释文字。"
                    )
                    last_raw = self._chat_with_quick_fallback(
                        [
                            Message(role="user", content=prompt),
                            Message(role="assistant", content=last_raw[:6000]),
                            Message(role="user", content=retry_prompt),
                        ],
                        stage="升级补丁生成",
                    )

                logger.info(
                    f"[UpgradePatch] 补丁 LLM 原始返回 (attempt {attempt + 1}/2, "
                    f"{len(last_raw)} 字符):\n{last_raw}"
                )
                patch = self._parse_llm_json(last_raw)
                if not isinstance(patch, dict):
                    raise ValueError("补丁必须是 JSON 对象")
                spec = apply_upgrade_patch(parent_contract, patch)
                logger.info(
                    "[UpgradePatch] 补丁套用成功: tool_id=%s 变更点=%s",
                    spec.tool_id,
                    spec.metadata.get("upgrade_change_points"),
                )
                return spec
            except Exception as e:
                last_error = e
                logger.warning(f"[UpgradePatch] 第 {attempt + 1}/2 次失败: {e}")

        logger.error(f"[UpgradePatch] 补丁生成最终失败: {last_error}")
        return None

    @staticmethod
    def _sanitize_spec_params(data: Dict[str, Any]) -> None:
        """清洗 spec 参数：剔除非法 Python 标识符参数（如 headers.User-Agent）。

        LLM 可能把 HTTP 请求头误收录为函数参数；这类名字不可能出现在函数
        签名中，会直接导致静态校验死循环。剔除后把头部要求补进 constraints，
        保证实现信息不丢失。
        """
        import keyword as _keyword
        import re as _re

        def _usable(name: str) -> bool:
            return bool(_re.match(r"^[a-zA-Z_][a-zA-Z0-9_]*$", name)) and not _keyword.iskeyword(name)

        params = data.get("parameters")
        if not isinstance(params, list):
            return
        valid = []
        dropped: list[str] = []
        for p in params:
            if isinstance(p, dict) and _usable(str(p.get("name") or "")):
                valid.append(p)
            elif isinstance(p, dict):
                dropped.append(str(p.get("name") or "未命名"))
        if dropped:
            data["parameters"] = valid
            constraints = data.get("constraints")
            if not isinstance(constraints, list):
                constraints = []
            constraints.append(
                f"请求所需的 HTTP 头/认证等实现细节（原参数: {', '.join(dropped)}）"
                "应在函数内部写死，不作为函数参数暴露"
            )
            data["constraints"] = constraints
            logger.warning(f"[RequirementAnalyzer] 已剔除非法标识符参数: {dropped}")

    @staticmethod
    def _ensure_interface_spec_constraints(data: Dict[str, Any], conversation: str) -> None:
        """从对话原文提取接口规格（URL/方法/请求头），兜底写回 constraints。

        背景：用户在外部接口需求中给出的 URL、请求头、参数说明是接口契约的
        唯一事实源，但规格生成 LLM 可能将其摘要丢失（constraints 为空），
        导致代码生成阶段臆造 URL（如把 rank_data 写成 rank/data → 404）。
        """
        import re as _re

        if not conversation:
            return
        # 提取对话中出现的 http(s) URL；查询串是示例参数（应以函数参数实现），
        # 只保留基础 URL 作为逐字契约，避免诱导 LLM 硬编码示例参数。
        # 查询串单独作为「文档化查询参数」约束保留——它是接口预检差分测试
        # 区分「接口真实参数」与「业务过滤参数」（如 brand_name）的依据。
        # URL 匹配仅限 ASCII URL 字符：中文紧贴 URL 时（如「rank_data发起」）必须截断
        urls: list[str] = []
        url_queries: dict[str, str] = {}
        for m in _re.finditer(r"https?://[A-Za-z0-9\-._~:/?#\[\]@!$&'()*+,;=%]+", conversation):
            raw = m.group(0)
            base_url = raw.split("?")[0].rstrip(".,;:")
            if base_url not in urls:
                urls.append(base_url)
            query = raw.split("?", 1)[1].rstrip(".,;:") if "?" in raw else ""
            if query and base_url not in url_queries:
                url_queries[base_url] = query
        if not urls:
            return

        constraints = data.get("constraints")
        if not isinstance(constraints, list):
            constraints = []
        existing = "\n".join(str(c) for c in constraints)

        added: list[str] = []
        for base_url in urls:
            if base_url in existing:
                continue
            constraints.insert(
                0,
                f"【接口规格 — 必须原样使用】接口 URL: {base_url}（来自用户需求，路径/参数名严禁改写，"
                "如 rank_data 不得写成 rank/data；URL 中的查询参数仅是示例，实现时以函数参数传参）",
            )
            added.append(base_url)

        # 文档化查询参数：用户 URL 原文查询串（幂等：已存在则不重复写）
        query_added = 0
        for base_url, query in url_queries.items():
            if query in existing:
                continue
            constraints.insert(
                1,
                f"【接口规格】接口查询参数（用户 URL 原文查询串）: {query}"
                "——仅这些参数名为接口真实查询参数，可拼装进 URL 请求；"
                "其余业务过滤条件（如品牌/厂商）接口不支持，必须拉取数据后按返回字段本地过滤",
            )
            query_added += 1

        # 请求头要求
        header_kws = ["User-Agent", "Referer", "Authorization", "Content-Type", "Token", "请求头"]
        mentioned_headers = [kw for kw in header_kws if kw in conversation]
        if mentioned_headers and "请求头" not in existing and "User-Agent" not in existing:
            constraints.insert(
                1,
                f"【接口规格】请求需携带请求头: {'、'.join(dict.fromkeys(mentioned_headers))}（以用户需求描述为准）",
            )

        if added or query_added or mentioned_headers:
            data["constraints"] = constraints
            logger.warning(
                f"[RequirementAnalyzer] 对话中检测到接口规格，已兜底写入 constraints: urls={added}, "
                f"queries={query_added}, headers={mentioned_headers[:4]}"
            )

    @staticmethod
    def _build_recon_context_for_spec(report: ImplementationFactReport) -> str:
        """将侦察报告转化为 spec 生成 prompt 可消费的文本上下文。"""
        parts = []

        if report.recommended_strategy:
            parts.append(f"- 推荐实现策略: {report.recommended_strategy}")

        if report.confidence:
            parts.append(f"- 侦察置信度: {report.confidence:.0%}")

        # 可用 Helper 函数
        if report.available_helpers:
            helper_lines = []
            helper_field_names: set[str] = set()
            for h in report.available_helpers:
                sig = f"  • {h.name}({h.signature})" if h.signature else f"  • {h.name}"
                ds = h.data_source_handling or "self_contained"
                sig += f" [数据源:{ds}]"
                if h.description:
                    sig += f" — {h.description}"
                helper_lines.append(sig)
                # 🔧 从 helper 的 Returns 文档中提取字段名，用于约束 LLM 输出字段命名
                if h.description:
                    field_names = RequirementAnalyzer._extract_return_field_names(h.description)
                    helper_field_names.update(field_names)
            parts.append(
                "- 可用 Helper 函数 (数据源: self_contained=自包含; local_only=仅本地MongoDB; partial=部分覆盖):\n"
                + "\n".join(helper_lines)
            )
            # 🔧 注入 helper 实际返回的字段名，防止 LLM 自创字段名
            if helper_field_names:
                sorted_fields = sorted(helper_field_names)
                parts.append(
                    f"- 🚨 Helper 实际返回的字段名（expected_output.fields 必须优先使用这些字段名，禁止自创）: "
                    f"{', '.join(sorted_fields[:30])}"
                )

        # 数据库字段实况
        if report.schema_facts:
            fact_lines = []
            for f in report.schema_facts:
                # field/description 为新增可选字段，回退到 fact
                label = f.field if f.field else f.fact
                desc = f.description if f.description else ""
                line = f"  • [{f.source}] {label}"
                if desc:
                    line += f": {desc}"
                if f.coverage is not None:
                    line += f" (覆盖率 {f.coverage:.0%})"
                fact_lines.append(line)
            parts.append("- 数据库字段实况:\n" + "\n".join(fact_lines))

        # 样本字段
        if report.sample_fields:
            for collection, fields in report.sample_fields.items():
                parts.append(f"- {collection} 的实际字段: {', '.join(fields[:20])}")

        schema_bundle_context = report.schema_bundle_context or {}
        method = schema_bundle_context.get("method") or {}
        contract = schema_bundle_context.get("contract") or {}
        verifier_rule = schema_bundle_context.get("verifier_rule") or {}
        applicability_rules = schema_bundle_context.get("applicability_rules") or {}
        schema_lines = []
        if method:
            schema_lines.append(
                f"  • 方法: {method.get('name') or schema_bundle_context.get('method_id')}"
            )
            if method.get("required_fields"):
                schema_lines.append(
                    f"  • 方法前置字段: {', '.join(list(method.get('required_fields') or [])[:6])}"
                )
        if contract:
            contract_fields = [
                str((item or {}).get("field_name") or "").strip()
                for item in contract.get("required_fields") or []
                if str((item or {}).get("field_name") or "").strip()
            ]
            if contract_fields:
                schema_lines.append(f"  • 输出契约字段: {', '.join(contract_fields[:8])}")
        if applicability_rules:
            schema_lines.append(
                "  • 适用性规则: "
                + "；".join(
                    str((rule or {}).get("human_description") or rule_id)
                    for rule_id, rule in list(applicability_rules.items())[:4]
                )
            )
        if verifier_rule and verifier_rule.get("failure_message"):
            schema_lines.append(f"  • 验收失败语义: {verifier_rule.get('failure_message')}")
        if schema_lines:
            parts.append("- 金融 schema 指南:\n" + "\n".join(schema_lines))

        # 受阻路径
        if report.blocked_paths:
            block_lines = [f"  ⚠️ [{b.severity}] {b.path}: {b.reason}" for b in report.blocked_paths]
            parts.append("- 受阻路径（不可用）:\n" + "\n".join(block_lines))

        # 运行时缺口
        if report.runtime_gaps:
            gap_lines = [f"  ⚠️ [{g.severity}] {g.path}: {g.reason}" for g in report.runtime_gaps]
            parts.append("- 运行时缺口:\n" + "\n".join(gap_lines))

        if report.notes:
            parts.append("- 备注: " + "; ".join(report.notes))

        return "\n".join(parts) if parts else ""

    @staticmethod
    def _extract_return_field_names(description: str) -> list[str]:
        """从 helper 的 docstring 描述中提取 Returns 区块列出的字段名。

        Helper 的 docstring 通常包含这样的 Returns 段落:
            Returns:
                dict: 字段说明（代码中使用 .get() 或 [] 访问这些 key）——
                    status: 状态: "success" | "no_pledge" | ...
                    symbol: 标准化后的 6 位股票代码
                    metrics: 聚合指标 — ...
                    top_pledgers: 前几大未解押股东列表
                    ...

        本方法解析出 status / symbol / metrics / top_pledgers 等字段名,
        用于约束 spec 生成阶段不要自创字段名。
        """
        if not description:
            return []
        text = str(description)

        # 定位 Returns 区块
        returns_idx = text.find("Returns:")
        if returns_idx < 0:
            return []
        returns_block = text[returns_idx:]

        # 截到下一个段落标记（Args/Examples/Note 等）或文档末尾
        for marker in ("\nArgs:", "\nExamples:", "\nNote:", "\nRaises:"):
            marker_idx = returns_block.find(marker)
            if marker_idx > 0:
                returns_block = returns_block[:marker_idx]
                break

        field_names: list[str] = []
        seen: set[str] = set()
        # 匹配 "            field_name: 描述" 这种行
        # 字段名通常由字母/数字/下划线组成，冒号前
        import re
        for match in re.finditer(r"^\s+([a-zA-Z_][a-zA-Z0-9_]*)\s*:", returns_block, re.MULTILINE):
            name = match.group(1)
            # 过滤掉明显的非字段名（如 "dict"、"list"、"str"、"Returns" 等）
            if name.lower() in {"dict", "list", "str", "int", "float", "bool", "returns", "args", "examples", "note"}:
                continue
            if name in seen:
                continue
            seen.add(name)
            field_names.append(name)
        return field_names
