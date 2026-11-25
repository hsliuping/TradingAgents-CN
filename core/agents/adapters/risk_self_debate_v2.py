"""
风险自我辩论分析师 v2.0（A9-P1）

单节点内完成高弹性/防御/基准三个风险审阅视角的立场陈述与交叉质证，
替代风险三角（risky/safe/neutral_analyst_v2）多轮辩论，
将深度/全面档风险辩论环节的 LLM 调用从 轮数×3 次降为 1 次。

设计要点：
- 仅当 state["_risk_self_debate"]=True（深度/全面档且开关开启）时被路由到，
  快速/基础/标准档继续走原风险三角多 agent 路径，互不影响。
- 输出与原风险三角完全兼容：
  * risky_opinion / safe_opinion / neutral_opinion 三个 state 字段
  * risk_debate_state 结构（histories / current_*_response / count）
  渲染层与 risk_manager_v2 零改动。
- 通过三段式标记解析 LLM 输出；解析失败时全文降级填充，保证字段非空。
"""

import logging
import re
from typing import Any, Dict, List, Tuple

from langchain_core.messages import SystemMessage, HumanMessage

from ..researcher import ResearcherAgent
from ..registry import register_agent
from ..config import AgentMetadata, AgentCategory, LicenseTier, AgentInput, AgentOutput

logger = logging.getLogger(__name__)

# 三视角小节标记（输出解析用，顺序即期望的输出顺序）
_SECTION_LABELS: Tuple[str, str, str] = ("高弹性情景观点", "防御情景观点", "基准情景观点")

# 严格模式：标记独占一行（【X】/ ## X / **X** 等变体）
_MARKER_STRICT_RE = re.compile(
    r"(?m)^[ \t]*(?:#{1,6}[ \t]*)?(?:\*\*)?[【\[]?\s*"
    r"(高弹性情景观点|防御情景观点|基准情景观点)"
    r"\s*[】\]]?(?:\*\*)?[ \t]*[:：]?\s*$"
)

# 宽松模式：标记在行首、允许同行跟内容（严格模式解析失败时启用）
_MARKER_LOOSE_RE = re.compile(
    r"(?m)^[ \t]*(?:#{1,6}[ \t]*)?(?:\*\*)?[【\[]?\s*"
    r"(高弹性情景观点|防御情景观点|基准情景观点)"
    r"\s*[】\]]?(?:\*\*)?[ \t]*[:：]?"
)


def _extract_sections(text: str, marker_re: re.Pattern) -> Dict[str, str]:
    """按标记切分文本，返回 {标签: 小节内容}（每个标签只取首次出现）"""
    matches = list(marker_re.finditer(text))
    sections: Dict[str, str] = {}
    for i, m in enumerate(matches):
        label = m.group(1)
        if label in sections:
            continue
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        sections[label] = text[start:end].strip()
    return sections


def parse_self_debate_response(response: str) -> Tuple[str, str, str]:
    """
    解析自我辩论输出为 (risky, safe, neutral) 三段观点。

    解析策略：严格（标记独占一行）→ 宽松（同行内容）→ 全文降级。
    全文降级时三个字段填充完整输出，保证下游 risk_manager 与报告渲染
    拿到非空内容（极端情况下的保底行为，正常不会触发）。
    """
    if not response or not response.strip():
        return "", "", ""

    sections = _extract_sections(response, _MARKER_STRICT_RE)
    if len(sections) < 3:
        sections = _extract_sections(response, _MARKER_LOOSE_RE)

    risky = sections.get(_SECTION_LABELS[0], "")
    safe = sections.get(_SECTION_LABELS[1], "")
    neutral = sections.get(_SECTION_LABELS[2], "")

    if risky and safe and neutral:
        return risky, safe, neutral

    logger.warning(
        f"[RiskSelfDebateV2] 输出未按三段标记完整分段 "
        f"(risky={bool(risky)}, safe={bool(safe)}, neutral={bool(neutral)})，降级为全文填充"
    )
    full = response.strip()
    return full, full, full


@register_agent
class RiskSelfDebateV2(ResearcherAgent):
    """
    风险自我辩论分析师 v2.0

    工作流程：
    1. 读取综合研究结论（investment_plan）与全部上游分析报告
    2. 单次 LLM 调用中完成三视角自我辩论：
       立场陈述 → 交叉质证 → 定稿输出
    3. 解析为 risky/safe/neutral 三段观点
    4. 更新 risk_debate_state（histories / current_*_response / count）

    输出与原风险三角（risky/safe/neutral_analyst_v2）完全兼容。
    """

    metadata = AgentMetadata(
        id="risk_self_debate_v2",
        name="风险自我辩论分析师 v2.0",
        description="单节点完成高弹性/防御/基准三视角风险审阅与交叉质证（A9-P1 深度档路径）",
        category=AgentCategory.RISK,
        version="2.0.0",
        license_tier=LicenseTier.FREE,
        default_tools=[],
        inputs=[
            AgentInput(name="ticker", type="string", description="股票代码"),
            AgentInput(name="analysis_date", type="string", description="分析日期"),
            AgentInput(name="investment_plan", type="string", description="综合研究结论", source="state", state_field="investment_plan", source_state_fields=["trader_investment_plan"], producer_hint="research_manager_v2"),
            AgentInput(name="bull_opinion", type="string", description="乐观情景观点", required=False, source="state", state_field="bull_report", producer_hint="bull_researcher_v2"),
            AgentInput(name="bear_opinion", type="string", description="审慎情景观点", required=False, source="state", state_field="bear_report", producer_hint="bear_researcher_v2"),
            AgentInput(name="market_report", type="string", description="市场分析报告", required=False, source="state", state_field="market_report", producer_hint="market_analyst_v2"),
            AgentInput(name="fundamentals_report", type="string", description="基本面分析报告", required=False, source="state", state_field="fundamentals_report", producer_hint="fundamentals_analyst_v2"),
            AgentInput(name="news_report", type="string", description="新闻分析报告", required=False, source="state", state_field="news_report", producer_hint="news_analyst_v2"),
            AgentInput(name="sentiment_report", type="string", description="情绪分析报告", required=False, source="state", state_field="sentiment_report", producer_hint="social_analyst_v2"),
            AgentInput(name="index_report", type="string", description="大盘分析报告", required=False, source="state", state_field="index_report", producer_hint="index_analyst_v2"),
            AgentInput(name="sector_report", type="string", description="板块分析报告", required=False, source="state", state_field="sector_report", producer_hint="sector_analyst_v2"),
        ],
        outputs=[
            AgentOutput(name="risky_opinion", type="string", description="高弹性情景观点"),
            AgentOutput(name="safe_opinion", type="string", description="防御情景观点"),
            AgentOutput(name="neutral_opinion", type="string", description="基准情景观点"),
            AgentOutput(name="risk_debate_state", type="dict", description="更新后的风险辩论状态"),
        ],
        requires_tools=False,
        output_field="risky_opinion",
        report_label="【风险三视角自我辩论】",
        workflow_stage="risk",
        growth_role="reviewer",
        growth_outputs=["risky_opinion", "safe_opinion", "neutral_opinion"],
        memory_scope_hint="pattern",
        review_level="manual_required",
        growth_source_type="manager_decision",
        maturity_level="experimental",
        input_mode="upstream-dependent",
        debug_replay_mode="requires_chain_prefill",
        callable_surfaces=["workflow"],
    )

    # 自我辩论不站在单一立场
    stance = "self_debate"

    # 输出字段名（状态展示用，实际输出三个观点字段）
    output_field = "risky_opinion"

    debate_state_field = "risk_debate_state"

    # ==================== 提示词 ====================

    def _build_system_prompt(self, state: Dict[str, Any] = None) -> str:
        """构建系统提示词（模板系统优先，失败降级硬编码）"""
        prompt = self._get_prompt_from_template(
            agent_type="debators_v2",
            agent_name="risk_self_debate_v2",
            variables={},
            state=state,
            context=state.get("context") if state else None,
            fallback_prompt=None,
            prompt_type="system",
        )
        if prompt:
            logger.debug("✅ 从模板系统获取风险自我辩论系统提示词")
            return prompt

        return """你是一位资深风险研究专家。你的任务：在一次深度思考中，从三个风险审阅视角完成自我辩论，并只输出三个定稿观点。

思考方法（在思考过程中完成，严禁写进正文）：
1. 依次以三个视角独立审阅综合研究结论，各自形成判断；
2. 交叉质证：高弹性视角指出防御视角在哪里过度保守、忽视了哪些已验证的积极信号；防御视角指出高弹性视角的结论依赖哪些未验证假设、哪些证据存在瑕疵；基准视角评估双方论点的证据强度，指出哪些分歧源于信息缺口；
3. 吸收对方合理质疑后，形成三个视角的定稿观点。

三个视角（名称固定，不得改用"乐观方/审慎方"等其他叫法）：
1. 高弹性情景：结论上修依赖的强化条件、催化证据与高要求前提
2. 防御情景：结论最脆弱的前提、关键风险来源与失效条件
3. 基准情景：双方论点的证据质量比较、信息缺口与当前最稳妥的基准情景

输出要求（最高优先级，逐字遵守）：
- 正文必须且只能包含以下三个小节，每节以指定的标记行开头
- 严禁输出"立场陈述""交叉质证""定稿输出"等任何过程性标题、编号或内容
- 三个标记必须独占一行、原样输出（保留【】）

输出格式（严格照此结构）：
【高弹性情景观点】
（本视角定稿观点，300-500字：结论上修依赖的强化条件与催化；若要更积极需满足哪些高要求前提；当前材料中最支持上修的证据）
【防御情景观点】
（本视角定稿观点，300-500字：结论最脆弱的前提与关键风险来源；失效条件；哪些证据不足以支撑当前结论）
【基准情景观点】
（本视角定稿观点，300-500字：双方论点的证据质量比较；信息缺口；当前最稳妥的基准情景与需要跟踪的验证信号）

其他要求：
- 三个视角必须体现交叉质证后的结论差异，不得简单重复同一结论
- 不输出仓位、目标价、收益空间或交易建议
- 使用中文撰写"""

    @staticmethod
    def _report_text(value: Any) -> str:
        """提取报告纯文本（研究员输出为 dict{'content': ...}，兼容 str）"""
        if isinstance(value, dict):
            return str(value.get("content") or value.get("markdown") or "")
        return str(value) if value else ""

    def _build_user_prompt(self, ticker: str, analysis_date: str, state: Dict[str, Any]) -> str:
        """构建用户提示词（模板系统优先，失败降级硬编码）"""
        investment_plan = state.get("investment_plan", "") or state.get("trader_investment_plan", "")
        # 🔑 上游 bull/bear_researcher_v2 写入 bull_report/bear_report（dict 含 content）；
        # state 中的 bull_opinion/bear_opinion 为历史遗留字段，始终为空
        bull_opinion = self._report_text(state.get("bull_report"))
        bear_opinion = self._report_text(state.get("bear_report"))
        template_variables = {
            "ticker": ticker,
            "analysis_date": analysis_date,
            "investment_plan": investment_plan,
            "bull_opinion": bull_opinion,
            "bear_opinion": bear_opinion,
            "market_report": state.get("market_report", ""),
            "fundamentals_report": state.get("fundamentals_report", ""),
            "news_report": state.get("news_report", ""),
            "sentiment_report": state.get("sentiment_report", ""),
            "index_report": state.get("index_report", ""),
            "sector_report": state.get("sector_report", ""),
        }

        logger.info(
            f"📊 [RiskSelfDebate] 输入数据长度: "
            f"investment_plan={len(template_variables['investment_plan']):,}, "
            f"bull_opinion={len(template_variables['bull_opinion']):,}, "
            f"bear_opinion={len(template_variables['bear_opinion']):,}, "
            f"market_report={len(template_variables['market_report']):,}, "
            f"news_report={len(template_variables['news_report']):,}, "
            f"fundamentals_report={len(template_variables['fundamentals_report']):,} 字符"
        )

        fallback_prompt = f"""请在一次深度思考中完成风险三视角自我辩论，直接输出三个定稿观点（过程性内容只留在思考中）。

分析对象：{ticker or '未指定'} @ {analysis_date or '未指定'}

【综合研究结论】
{investment_plan or '无综合研究结论'}

【乐观研究员报告】
{template_variables['bull_opinion'] or '无乐观研究员报告'}

【审慎研究员报告】
{template_variables['bear_opinion'] or '无审慎研究员报告'}

【市场分析报告】
{template_variables['market_report'] or '无市场分析报告'}

【新闻分析报告】
{template_variables['news_report'] or '无新闻分析报告'}

【基本面分析报告】
{template_variables['fundamentals_report'] or '无基本面分析报告'}

【社交媒体情绪报告】
{template_variables['sentiment_report'] or '无情绪分析报告'}

【大盘分析报告】
{template_variables['index_report'] or '无大盘分析报告'}

【板块分析报告】
{template_variables['sector_report'] or '无板块分析报告'}

请严格按系统提示词规定的三段标记格式输出：正文只包含三个定稿观点小节（【高弹性情景观点】/【防御情景观点】/【基准情景观点】各独占一行），不要输出立场陈述、交叉质证等任何过程内容。"""

        prompt = self._get_prompt_from_template(
            agent_type="debators_v2",
            agent_name="risk_self_debate_v2",
            variables=template_variables,
            state=state,
            context=state.get("context") if isinstance(state, dict) else state,
            fallback_prompt=fallback_prompt,
            prompt_type="user",
        )
        if prompt:
            logger.info(f"✅ 从模板系统获取风险自我辩论用户提示词 (长度: {len(prompt)})")
            return prompt
        logger.info(f"📝 [RiskSelfDebate] 使用降级提示词 (长度: {len(fallback_prompt)})")
        return fallback_prompt

    def _get_required_reports(self) -> list:
        return [
            "investment_plan",
            "bull_report",
            "bear_report",
            "market_report",
            "fundamentals_report",
            "news_report",
            "sentiment_report",
            "index_report",
            "sector_report",
        ]

    # ==================== 执行 ====================

    def execute(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        执行风险三视角自我辩论（单次 LLM 调用）

        Returns:
            更新后的状态，包含:
                - risky_opinion / safe_opinion / neutral_opinion: 三视角观点
                - risk_debate_state: 更新后的辩论状态
        """
        ticker = state.get("ticker", "") or state.get("company_of_interest", "")
        analysis_date = state.get("analysis_date", "") or state.get("trade_date", "")

        logger.info(f"🧠 风险自我辩论分析师开始评估 {ticker} @ {analysis_date}")

        risk_debate_state = state.get("risk_debate_state", {}) or {}

        try:
            system_prompt = self._apply_global_trading_advice_guard(
                self._build_system_prompt(state)
            )
            user_prompt = self._build_user_prompt(ticker, analysis_date, state)
            messages = [
                SystemMessage(content=system_prompt),
                HumanMessage(content=user_prompt),
            ]

            import time
            llm_start_time = time.time()
            logger.info("⏱️ [RiskSelfDebate] 开始调用LLM（单次调用替代风险三角多轮辩论）...")

            if self._llm:
                response = self._invoke_llm_with_trace(messages)
                raw = response.content
            else:
                raise ValueError("LLM not initialized")

            # 部分模型返回分段 content 列表
            if isinstance(raw, list):
                raw = "".join(str(c) for c in raw)
            raw = str(raw)

            llm_elapsed = time.time() - llm_start_time
            logger.info(
                f"⏱️ [RiskSelfDebate] LLM调用完成，耗时: {llm_elapsed:.2f}秒，"
                f"输出长度: {len(raw):,} 字符"
            )

            risky, safe, neutral = parse_self_debate_response(raw)
            logger.info(
                f"✅ 三视角解析完成: risky={len(risky):,}, safe={len(safe):,}, "
                f"neutral={len(neutral):,} 字符"
            )

            # 更新辩论状态（与原风险三角兼容）
            risky_arg = f"Risky Analyst: {risky}"
            safe_arg = f"Safe Analyst: {safe}"
            neutral_arg = f"Neutral Analyst: {neutral}"
            full_history = "\n".join([risky_arg, safe_arg, neutral_arg])
            old_history = risk_debate_state.get("history", "")
            old_count = risk_debate_state.get("count", 0)

            new_risk_debate_state = {
                "history": (old_history + "\n" + full_history).strip("\n"),
                "risky_history": (risk_debate_state.get("risky_history", "") + "\n" + risky_arg).strip("\n"),
                "safe_history": (risk_debate_state.get("safe_history", "") + "\n" + safe_arg).strip("\n"),
                "neutral_history": (risk_debate_state.get("neutral_history", "") + "\n" + neutral_arg).strip("\n"),
                "latest_speaker": "SelfDebate",
                "current_risky_response": risky_arg,
                "current_safe_response": safe_arg,
                "current_neutral_response": neutral_arg,
                "count": old_count + 3,  # 三视角各计一次发言
            }

            logger.info("✅ 风险自我辩论完成（单节点替代风险三角多轮辩论）")

            return {
                "risky_opinion": risky,
                "safe_opinion": safe,
                "neutral_opinion": neutral,
                "risk_debate_state": new_risk_debate_state,
            }

        except Exception as e:
            logger.error(f"❌ 风险自我辩论失败: {e}", exc_info=True)
            error_text = f"风险自我辩论失败: {str(e)}"
            return {
                "risky_opinion": error_text,
                "safe_opinion": error_text,
                "neutral_opinion": error_text,
                "risk_debate_state": risk_debate_state,  # 保持原状态
            }
