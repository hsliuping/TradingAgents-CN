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
from typing import Any, Dict, Optional, Tuple

from core.llm import UnifiedLLMClient, Message

from .external_data_source_catalog import (
    render_external_data_source_doc,
    select_relevant_external_data_sources,
)
from .stock_data_catalog import (
    render_stock_data_collection_doc,
    select_relevant_stock_collections,
)

from .skill_spec import (
    BoundaryCheck,
    ClarityLevel,
    ConversationRound,
    ImplementationFactReport,
    SessionStatus,
    SkillCreationSession,
    SkillHandoffContext,
    SkillSpec,
)

logger = logging.getLogger(__name__)

ANALYZER_LLM_TIMEOUT_SECONDS = 180


SKILL_SEMANTICS_GUIDANCE = (
    "Skill 的语义：Skill 是一个可复用、可验证、边界清晰的功能实现单元，"
    "不等于只能做数据获取。Skill 可以做数据获取、字段整理、格式转换、指标计算、规则判断、"
    "轻量聚合、模板化说明生成等确定性能力。\n"
    "Agent/Workflow 的语义：负责需求理解、任务规划、多 Skill 编排、开放式追问、主观综合判断、"
    "研究结论整合、投资建议生成等高层决策与推理。\n"
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
    ):
        self._client = llm_client
        self._provider = provider
        self._model = model

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

    @staticmethod
    def _raise_analysis_error(stage: str, error: Optional[Exception] = None) -> None:
        detail = str(error) if error else "LLM 未返回有效内容"
        raise RuntimeError(f"{stage}失败：{detail}")

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
                constraints=blueprint["constraints"],
                test_input=blueprint["test_input"],
            )
        except Exception as e:
            logger.error(f"启发式 SkillSpec 生成失败: {e}")
            return None

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
        return f"{local_doc}\n\n{external_doc}"

    def build_recommendations(
        self,
        *,
        spec: Optional[SkillSpec] = None,
        conversation: str = "",
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

        local_collections = select_relevant_stock_collections(
            category=category,
            description=description,
            data_source=data_source,
            constraints=constraints,
            expected_fields=expected_fields,
            parameter_names=parameter_names,
            max_items=3,
        )
        external_sources = select_relevant_external_data_sources(
            category=category,
            description=description,
            data_source=data_source,
            constraints=constraints,
            expected_fields=expected_fields,
            parameter_names=parameter_names,
            max_items=3,
        )
        return {
            "category_hint": category,
            "data_source_hint": data_source,
            "stock_collections": [item["collection"] for item in local_collections],
            "external_sources": [item["source_id"] for item in external_sources],
        }

    # ==================== 会话管理 ====================

    def create_session(
        self,
        user_id: str = "",
        handoff_context: Optional[SkillHandoffContext] = None,
    ) -> SkillCreationSession:
        """创建新的 Skill 创建会话"""
        return SkillCreationSession(
            session_id=str(uuid.uuid4()),
            user_id=user_id,
            status=SessionStatus.GATHERING,
            handoff_context=handoff_context,
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
            "- 若你判断完整目标更像 Agent/Workflow 而不是单个 Skill，要明确指出这是 Agent 级目标，并把当前 Skill 只定位为其中一个确定性的子能力；不要假装整个目标已经被一个 Skill 完整覆盖。\n"
            "- 若存在可复用的现有 Skill，应优先指出复用方案；若不存在，再定义新增 Skill 的最小职责边界。\n"
        )

    def process_user_input(
        self,
        session: SkillCreationSession,
        user_message: str,
    ) -> Tuple[SkillCreationSession, str]:
        """
        处理用户输入，推进对话

        Args:
            session: 当前会话
            user_message: 用户消息

        Returns:
            (更新后的会话, AI 回复消息)
        """
        session.updated_at = datetime.utcnow()

        # 如果是第一轮，先做清晰度评估和边界检测
        if session.current_round == 0:
            clarity = self._assess_clarity(user_message)
            session.clarity_level = clarity

            boundary_context = self._build_handoff_context_text(session)
            boundary = self._check_boundary(
                user_message,
                conversation_context=boundary_context or None,
            )
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
            conversation = self._collect_conversation(session, user_message)
            boundary = self._check_boundary(user_message, conversation_context=conversation)
            session.boundary_check = boundary

        if session.current_round >= max_rounds:
            # 最后一轮：生成规格确认
            ai_msg = self._build_spec_confirmation(session, user_message)
        elif session.current_round == 1:
            # 第 1 轮：初步理解 + 功能点拆解
            ai_msg = self._build_round1_response(session, user_message)
        else:
            # 第 2 轮：技术细化
            ai_msg = self._build_round2_response(session, user_message)

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
    ) -> Tuple[SkillCreationSession, Optional[SkillSpec]]:
        """
        用户确认规格后，生成 SkillSpec

        Args:
            session: 当前会话
            user_message: 用户的确认消息（"确认" / 补充修改）
            fact_report: 侦察报告（侦察前置模式），用于增强 spec 生成

        Returns:
            (更新后的会话, 生成的 SkillSpec 或 None)
        """
        # 收集所有对话内容
        conversation = self._collect_conversation(session, user_message)

        # LLM 生成结构化 SkillSpec
        spec = self._generate_spec(conversation, fact_report=fact_report)

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
    ) -> Optional[SkillSpec]:
        """
        仅生成 SkillSpec 预览，不修改会话状态。
        用于规格确认步骤展示，用户确认后再调用 confirm_spec 执行管线。
        """
        conversation = self._collect_conversation(session, user_message)
        return self._generate_spec(conversation, fact_report=fact_report)

    # ==================== 清晰度评估 ====================

    def _assess_clarity(self, user_message: str) -> ClarityLevel:
        """评估需求清晰度"""
        client = self._get_client()
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
        client = self._get_client()
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
            json_match = re.search(r"\{.*\}", raw, re.DOTALL)
            if json_match:
                data = json.loads(json_match.group())
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
        client = self._get_client()
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
            "## 你的任务\n"
            "1. 复述你的理解\n"
            "2. 用表格列出功能点（目标市场、数据源、输入参数、返回字段、调用方式）\n"
            "3. **主动建议**：根据用户需求给出专业建议（如更合适的实现方式、常见坑、最佳实践）\n"
            "4. **数据源引导（重要）**：\n"
            "   - 先问用户：您是否有偏好的数据源？\n"
            "   - 若用户说「不确定」「不知道」「没有」「都可以」："
            "结合你对 A股/中国金融数据生态的了解，根据用户需求类型（财报、新闻、行情、资金流等），"
            "推荐 2-3 个合适的数据源，简要说明各自特点和适用场景，让用户选择。\n"
            "   - 优先在系统当前可复用的本地集合/外部来源里做建议，不要泛泛推荐一长串不在系统内的接口。\n"
            "   - 不要只说「需通过参数传入数据源」而不给建议，这样用户会不知道如何操作。\n\n"
            "5. 提出其他需要确认的问题\n\n"
            f"{handoff_guardrails}\n"
            f"上游交接上下文:\n{handoff_context or '无'}\n\n"
            f"当前按需求命中的数据上下文:\n{catalog_context}\n\n"
            f"用户描述: {user_message}"
        )
        try:
            response = client.chat([Message(role="user", content=prompt)])
            content = (response.content or "").strip()
            if content:
                return content
            self._raise_analysis_error("第1轮需求分析")
        except Exception as e:
            logger.error(f"第1轮需求分析失败: {e}")
            self._raise_analysis_error("第1轮需求分析", e)

    def _build_round2_response(
        self, session: SkillCreationSession, user_message: str
    ) -> str:
        """第 2 轮：技术细化"""
        history = self._collect_conversation(session, user_message)
        client = self._get_client()
        catalog_context = self._build_catalog_context(history)
        handoff_context = self._build_handoff_context_text(session)
        handoff_guardrails = self._build_handoff_guardrails(session)
        prompt = (
            "你是 Skill 需求分析专家，所在项目是 **TradingAgents-CN**（A股/港股/美股多智能体股票分析平台）。"
            "正在进行第 2 轮技术细化。\n\n"
            "请根据之前的对话和用户新的反馈：\n"
            "1. 确认技术方案（数据接口、返回格式）\n"
            "2. **主动建议**：根据用户需求给出技术方案建议（如推荐实现方式、边界情况处理）\n"
            "3. **若数据源仍未明确**：结合你对 A股/中国金融数据生态的了解，"
            "根据需求类型给出 2-3 个具体数据源推荐及理由，让用户选择\n"
            "   - 推荐时优先引用当前系统已整理的本地集合和外部来源，不要脱离系统现状给建议。\n"
            "4. 给出推荐方案让用户选择（而不是问开放性问题）\n"
            "5. 列出最终的参数和返回字段清单\n\n"
            f"{handoff_guardrails}\n"
            f"上游交接上下文:\n{handoff_context or '无'}\n\n"
            f"当前按需求命中的数据上下文:\n{catalog_context}\n\n"
            f"对话历史:\n{history}"
        )
        try:
            response = client.chat([Message(role="user", content=prompt)])
            content = (response.content or "").strip()
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
        client = self._get_client()
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
            response = client.chat([Message(role="user", content=prompt)])
            content = (response.content or "").strip()
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
    ) -> Optional[SkillSpec]:
        """通过 LLM 将对话转化为结构化 SkillSpec

        Args:
            conversation: 收集的对话内容
            fact_report: 侦察报告（侦察前置模式），包含真实字段可用性
        """
        client = self._get_client()
        catalog_context = self._build_catalog_context(conversation)
        handoff_guardrails = ""
        if "[系统交接上下文]:" in conversation:
            handoff_guardrails = (
                "6. 这次会话带有上游交接上下文，必须保留上游指定能力，不要把它改写成另一个更窄、更偷懒的实现。\n"
                "7. 若原目标显然是 Agent/Workflow 级目标，当前 SkillSpec 只能定义为其中一个确定性的子能力，并在 description/constraints 中明确这一点。\n"
                "8. 禁止把“估值分析”“研究分析”“多维判断”这类目标直接偷换成单一 PB/PE 指标计算器，除非用户明确只要这个子功能。\n\n"
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
            f"{handoff_guardrails}"
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
                "- 若某字段覆盖率低或不可用，应在 constraints 中注明降级策略，而非标记为必填。\n"
                "- 优先使用侦察发现的 Helper 函数，而非猜测 API 调用方式。\n\n"
            )

        prompt += f"对话内容:\n{conversation}\n\n"
        prompt += (
            "请严格用以下 JSON 格式输出（不要其他内容）：\n"
            "{\n"
            '  "tool_id": "snake_case_id",\n'
            '  "display_name": "中文显示名称",\n'
            '  "description": "功能描述",\n'
            '  "category": "news|market|fundamentals|social|technical|utility",\n'
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
            '  "constraints": ["约束1"],\n'
            '  "test_input": {"param1": "测试值"}\n'
            "}"
        )
        try:
            response = client.chat([Message(role="user", content=prompt)])
            raw = response.content or ""
            json_match = re.search(r"\{.*\}", raw, re.DOTALL)
            if json_match:
                data = json.loads(json_match.group())
                return SkillSpec(**data)
            self._raise_analysis_error("SkillSpec 生成", ValueError("LLM 未返回合法 JSON"))
        except Exception as e:
            logger.error(f"SkillSpec 生成失败: {e}")
            self._raise_analysis_error("SkillSpec 生成", e)
        return None

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
            for h in report.available_helpers:
                sig = f"  • {h.name}({h.signature})" if h.signature else f"  • {h.name}"
                if h.description:
                    sig += f" — {h.description}"
                helper_lines.append(sig)
            parts.append("- 可用 Helper 函数:\n" + "\n".join(helper_lines))

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

        # 受阻路径
        if report.blocked_paths:
            block_lines = [f"  ⚠️ {b.description}" for b in report.blocked_paths]
            parts.append("- 受阻路径（不可用）:\n" + "\n".join(block_lines))

        # 运行时缺口
        if report.runtime_gaps:
            gap_lines = [f"  ⚠️ {g.description}" for g in report.runtime_gaps]
            parts.append("- 运行时缺口:\n" + "\n".join(gap_lines))

        if report.notes:
            parts.append("- 备注: " + "; ".join(report.notes))

        return "\n".join(parts) if parts else ""
