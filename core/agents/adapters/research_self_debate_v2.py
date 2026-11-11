"""研究自我辩论分析师 v2.0（v4.0 第二波 P2）

单节点内完成乐观情景 / 审慎情景两位研究员的多轮对抗辩论，
替代 bull_researcher_v2 + bear_researcher_v2 的多 agent 轮循路径，
把投资辩论环节的 LLM 调用从 轮数×2 次降为 1 次，且双方共享同一份上下文
（不再反复切换上下文），既更快也避免跨 agent 上下文丢失。

设计要点：
- 仅当 state["_research_self_debate"]=True（标准/深度/全面档且开关开启）时被路由到，
  快速/基础档继续走原并行开局 / 轮循对抗路径，互不影响。
- 输出与原双研究员路径完全兼容：
  * bull_report / bear_report 两个 state 字段（研究报告文本）
  * investment_debate_state 结构（history / bull_history / bear_history /
    current_response / latest_speaker / count）
  下游 research_manager_v2 与报告渲染零改动。
- 双方各自输出「最可能推翻自身判断的 1-2 个信号」（证伪点），
  供研究经理重点审视，降低确认偏误。
- 机械护栏（防跑题/防伪辩论）：
  1) 议题卡：程序化生成必答争点与材料边界，限定交锋范围；
  2) 轮次台账：固定两轮，逐轮记录争点/双方观点/是否收敛；
  3) 五字段校验：两份定稿必须含 核心主张/支撑证据/对对方质疑的回应/成立前提/证伪信号；
  4) 数字锚点校验：每份定稿至少引用 2 个分析师报告中的具体数字；
  5) 失败兜底：校验不过先带问题清单修复重试一次，仍不通过则置
     state["_self_debate_failed"]=True，由 builder 条件边回退原双研究员轮循路径。
"""

import logging
import re
from typing import Any, Dict, Tuple

from langchain_core.messages import SystemMessage, HumanMessage

from ..researcher import ResearcherAgent
from ..registry import register_agent
from ..config import AgentMetadata, AgentCategory, LicenseTier, AgentInput, AgentOutput
from .flow_context import safe_extract

logger = logging.getLogger(__name__)

# 输出小节标记（顺序即期望的输出顺序）：交锋台账 + 双方定稿
_LEDGER_LABEL = "交锋台账"
_BULL_LABEL = "乐观情景研究结论"
_BEAR_LABEL = "审慎情景研究结论"
_SECTION_LABELS: Tuple[str, str, str] = (_LEDGER_LABEL, _BULL_LABEL, _BEAR_LABEL)

# 每份定稿必须包含的五字段（缺失即校验失败，用于机械拦截跑题/空话）
_REQUIRED_FIELDS = ("核心主张", "支撑证据", "对对方质疑的回应", "成立前提", "证伪信号")

# 交锋台账要求的最少轮次（固定两轮，禁止无限追加）
_REQUIRED_ROUNDS = 2

# 证据引用校验：从分析师报告中抽取数字型锚点，要求每份定稿至少命中 2 个
_NUMBER_RE = re.compile(r"\d+(?:\.\d+)?%?")

# 严格模式：标记独占一行（【X】/ ## X / **X** 等变体）
_MARKER_STRICT_RE = re.compile(
    r"(?m)^[ \t]*(?:#{1,6}[ \t]*)?(?:\*\*)?[【\[]?\s*"
    r"(交锋台账|乐观情景研究结论|审慎情景研究结论)"
    r"\s*[】\]]?(?:\*\*)?[ \t]*[:：]?\s*$"
)

# 宽松模式：标记在行首、允许同行跟内容（严格模式解析失败时启用）
_MARKER_LOOSE_RE = re.compile(
    r"(?m)^[ \t]*(?:#{1,6}[ \t]*)?(?:\*\*)?[【\[]?\s*"
    r"(交锋台账|乐观情景研究结论|审慎情景研究结论)"
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
    """解析自我辩论输出为 (交锋台账, 乐观结论, 审慎结论)。

    解析策略：严格（标记独占一行）→ 宽松（同行内容）。
    缺失侧不用全文兜底——交由 validate_self_debate 判失败并触发修复重试/回退，
    避免两份报告静默变成同一段全文。
    """
    if not response or not response.strip():
        return "", "", ""

    sections = _extract_sections(response, _MARKER_STRICT_RE)
    if len(sections) < 3:
        loose = _extract_sections(response, _MARKER_LOOSE_RE)
        if len(loose) > len(sections):
            sections = loose

    ledger = sections.get(_LEDGER_LABEL, "")
    bull = sections.get(_BULL_LABEL, "")
    bear = sections.get(_BEAR_LABEL, "")

    if not (ledger and bull and bear):
        logger.warning(
            f"[ResearchSelfDebateV2] 输出分段不完整 "
            f"(ledger={bool(ledger)}, bull={bool(bull)}, bear={bool(bear)})"
        )
    return ledger, bull, bear


def validate_self_debate(
    ledger: str,
    bull: str,
    bear: str,
    source_text: str,
) -> list:
    """确定性校验（不花 token）：格式、轮次、五字段、证据引用。

    返回问题列表；空列表表示通过。用于拦截跑题、空话和伪辩论。
    """
    issues: list = []

    if not bull:
        issues.append("缺少【乐观情景研究结论】小节")
    if not bear:
        issues.append("缺少【审慎情景研究结论】小节")
    if not ledger:
        issues.append("缺少【交锋台账】小节")

    # 轮次校验：台账必须明确出现第 1、2 轮
    for i in range(1, _REQUIRED_ROUNDS + 1):
        if f"第{i}轮" not in ledger:
            issues.append(f"交锋台账缺少第{i}轮记录")

    # 五字段校验：双方定稿都要有固定小节
    for label, text in (("乐观", bull), ("审慎", bear)):
        if not text:
            continue
        missing = [field for field in _REQUIRED_FIELDS if field not in text]
        if missing:
            issues.append(f"{label}结论缺少字段: {'、'.join(missing)}")

    # 证据引用校验：每份定稿至少命中 2 个分析师报告中的数字锚点
    anchors = set(_NUMBER_RE.findall(source_text or ""))
    if len(anchors) >= 2:
        for label, text in (("乐观", bull), ("审慎", bear)):
            if not text:
                continue
            hit = sum(1 for a in anchors if a in text)
            if hit < 2:
                issues.append(f"{label}结论引用分析师报告的数字不足（{hit}/2）")

    return issues


@register_agent
class ResearchSelfDebateV2(ResearcherAgent):
    """研究自我辩论分析师 v2.0

    工作流程：
    1. 读取全部上游分析师报告
    2. 单次 LLM 调用中完成乐观/审慎双视角多轮交锋（过程只留在思考里）
    3. 解析为乐观/审慎两份定稿研究结论
    4. 更新 investment_debate_state，count 增量为 2（双方各一次定稿发言）
    """

    metadata = AgentMetadata(
        id="research_self_debate_v2",
        name="研究自我辩论分析师 v2.0",
        description="单节点完成乐观/审慎双视角多轮对抗与定稿（P2 深度档路径）",
        category=AgentCategory.RESEARCHER,
        version="2.0.0",
        license_tier=LicenseTier.FREE,
        default_tools=[],
        inputs=[
            AgentInput(name="ticker", type="string", description="股票代码"),
            AgentInput(name="analysis_date", type="string", description="分析日期"),
            AgentInput(name="market_report", type="string", description="市场分析报告", required=False, source="state", state_field="market_report", producer_hint="market_analyst_v2"),
            AgentInput(name="fundamentals_report", type="string", description="基本面分析报告", required=False, source="state", state_field="fundamentals_report", producer_hint="fundamentals_analyst_v2"),
            AgentInput(name="news_report", type="string", description="新闻分析报告", required=False, source="state", state_field="news_report", producer_hint="news_analyst_v2"),
            AgentInput(name="sentiment_report", type="string", description="情绪分析报告", required=False, source="state", state_field="sentiment_report", producer_hint="social_analyst_v2"),
            AgentInput(name="index_report", type="string", description="大盘分析报告", required=False, source="state", state_field="index_report", producer_hint="index_analyst_v2"),
            AgentInput(name="sector_report", type="string", description="板块分析报告", required=False, source="state", state_field="sector_report", producer_hint="sector_analyst_v2"),
            AgentInput(name="chip_report", type="string", description="筹码分布报告", required=False, source="state", state_field="chip_report", producer_hint="chip_distribution_analyst_v2"),
        ],
        outputs=[
            AgentOutput(name="bull_report", type="string", description="乐观情景研究结论"),
            AgentOutput(name="bear_report", type="string", description="审慎情景研究结论"),
            AgentOutput(name="investment_debate_state", type="dict", description="更新后的投资辩论状态"),
        ],
        requires_tools=False,
        output_field="bull_report",
        report_label="【研究双视角自我辩论】",
        workflow_stage="research",
        growth_role="reviewer",
        growth_outputs=["bull_report", "bear_report"],
        memory_scope_hint="pattern",
        review_level="manual_required",
        growth_source_type="analysis_report",
        maturity_level="experimental",
        input_mode="upstream-dependent",
        debug_replay_mode="requires_chain_prefill",
        callable_surfaces=["workflow"],
    )

    # 自我辩论不站在单一立场
    stance = "self_debate"

    output_field = "bull_report"

    debate_state_field = "investment_debate_state"

    # ==================== 提示词 ====================

    # 内置系统提示词：模板系统未配置该 Agent 时作为兜底传入，
    # 否则模板层会返回「请进行分析。」（长度 6），导致三段标记与交锋台账全部缺失
    _SYSTEM_PROMPT_FALLBACK = """你是一位资深研究总监，主持两位研究员围绕同一份材料的对抗辩论：一位构建乐观情景，一位构建审慎情景。

辩论纪律（最高优先级，逐条遵守）：
1. 只围绕用户提示词中「辩论议题卡」列出的争点交锋。严禁引入议题卡以外的新话题、宏观叙事或材料中不存在的数字与事实；某争点在材料中无依据时，直接写"材料不足，本争点不展开"。
2. 交锋固定两轮，不得增减：
   - 第1轮：双方就争点各自立论，必须引用分析师报告中的具体数字或事实，并写明出处报告名。
   - 第2轮：双方针对对方第1轮论点交叉质证——指出对方证据的薄弱处、未验证假设和逻辑跳跃，并正面回应对方对自己的质疑，修正自身论证。
   - 第2轮结束后必须收敛（维持或修正观点），严禁出现第3轮或任何补充轮次。
3. 正文必须且只能包含三节，顺序固定：交锋台账 → 乐观情景研究结论 → 审慎情景研究结论；每节标记必须独占一行、原样输出（保留【】）。
4. 交锋台账严格两行、一行一轮，格式固定为：
   第1轮｜争点：<议题卡中的争点编号与名称>｜乐观：<一句话>｜审慎：<一句话>｜是否收敛：否
   第2轮｜争点：<...>｜乐观：<...>｜审慎：<...>｜是否收敛：是（或不收敛时写：否，分歧根因：...）
5. 两份定稿都必须按顺序包含且标注以下五个字段：
   核心主张 / 支撑证据 / 对对方质疑的回应 / 成立前提 / 证伪信号
   其中「支撑证据」必须引用至少 2 个分析师报告中出现的具体数字。

输出格式（严格照此结构，不得增删小节）：
【交锋台账】
第1轮｜争点：...｜乐观：...｜审慎：...｜是否收敛：否
第2轮｜争点：...｜乐观：...｜审慎：...｜是否收敛：是
【乐观情景研究结论】
核心主张：...
支撑证据：...
对对方质疑的回应：...
成立前提：...
证伪信号：...
【审慎情景研究结论】
核心主张：...
支撑证据：...
对对方质疑的回应：...
成立前提：...
证伪信号：...

其他要求：
- 两份结论必须体现质证后的真实分歧，不得简单复述同一判断
- 严禁输出买卖指令（买入/卖出/加仓/减仓/持有/清仓）与具体目标价；如需给出价格分析区间，必须注明是情景测算、不构成目标价
- 严禁承诺收益或保证盈利，严禁输出概率数值、风险收益比或任何交易建议
- 严禁输出思考过程、格式说明或台账与定稿之外的讨论
- 使用中文撰写"""

    def _build_system_prompt(self, state: Dict[str, Any] = None) -> str:
        """构建系统提示词（模板系统优先，失败降级内置提示词）"""
        prompt = self._get_prompt_from_template(
            agent_type="researchers_v2",
            agent_name="research_self_debate_v2",
            variables={},
            state=state,
            context=state.get("context") if state else None,
            fallback_prompt=self._SYSTEM_PROMPT_FALLBACK,
            prompt_type="system",
        )
        if prompt:
            logger.debug("✅ 获取研究自我辩论系统提示词")
            return prompt

        return self._SYSTEM_PROMPT_FALLBACK

    @staticmethod
    def _report_text(value: Any) -> str:
        """提取报告纯文本（降级占位返回空串，不混入辩论）"""
        return safe_extract(value)

    # 议题卡争点（程序化生成，机械限定辩论范围，防止跑题）
    _TOPIC_POINTS = (
        ("P1", "估值与业绩是否匹配", "fundamentals_report", "基本面分析报告"),
        ("P2", "盈利增长的驱动是否可持续", "fundamentals_report", "基本面分析报告"),
        ("P3", "当前价格是否得到资金与情绪支撑", "market_report", "市场分析报告"),
        ("P4", "行业与大盘环境是顺风还是逆风", "sector_report", "板块分析报告"),
        ("P5", "哪些已公开事实最可能证伪本次判断", "news_report", "新闻分析报告"),
    )

    _MATERIAL_LABELS = (
        ("market_report", "市场分析报告"),
        ("fundamentals_report", "基本面分析报告"),
        ("news_report", "新闻分析报告"),
        ("sentiment_report", "社交媒体情绪报告"),
        ("index_report", "大盘分析报告"),
        ("sector_report", "板块分析报告"),
        ("chip_report", "筹码分布报告"),
    )

    def _build_topic_card(self, ticker: str, analysis_date: str, state: Dict[str, Any]) -> str:
        """生成辩论议题卡（确定性，不花 token）：限定争点范围与材料边界。"""
        company = state.get("company_name") or ticker or "未指定"
        available, missing = [], []
        for field, label in self._MATERIAL_LABELS:
            text = self._report_text(state.get(field))
            if text.strip():
                available.append(f"{label}（{len(text):,} 字）")
            else:
                missing.append(label)

        lines = [
            "辩论议题卡（只允许围绕以下争点交锋，不得扩展）：",
            f"标的：{company}（{ticker or '未指定'}）@ {analysis_date or '未指定'}",
            f"可用材料：{'、'.join(available) if available else '无'}",
            f"缺失材料：{'、'.join(missing) if missing else '无'}",
            "必答争点：",
        ]
        for code, point, field, label in self._TOPIC_POINTS:
            if self._report_text(state.get(field)).strip():
                lines.append(f"- {code} {point}（依据：{label}）")
            else:
                lines.append(
                    f"- {code} {point}（依据：{label}，材料缺失，"
                    f"本争点写「材料不足，本争点不展开」）"
                )
        lines.append(
            "禁止事项：引入议题卡之外的话题；使用未提供的材料或编造数字；"
            "给出交易建议；输出过程性讨论。"
        )
        return "\n".join(lines)

    def _build_user_prompt(
        self,
        ticker: str,
        analysis_date: str,
        state: Dict[str, Any],
        topic_card: str = "",
    ) -> str:
        """构建用户提示词（模板系统优先，失败降级硬编码）"""
        debate_state = state.get("investment_debate_state") or {}
        previous_debate = str(debate_state.get("history") or "").strip()
        if not topic_card:
            topic_card = self._build_topic_card(ticker, analysis_date, state)

        template_variables = {
            "ticker": ticker,
            "analysis_date": analysis_date,
            "company_name": state.get("company_name", ticker),
            "debate_topic_card": topic_card,
            "market_report": state.get("market_report", ""),
            "fundamentals_report": state.get("fundamentals_report", ""),
            "news_report": state.get("news_report", ""),
            "sentiment_report": state.get("sentiment_report", ""),
            "index_report": state.get("index_report", ""),
            "sector_report": state.get("sector_report", ""),
            "chip_report": state.get("chip_report", ""),
            "historical_context": previous_debate,
        }

        logger.info(
            f"📊 [ResearchSelfDebate] 输入数据长度: "
            f"market={len(template_variables['market_report']):,}, "
            f"fundamentals={len(template_variables['fundamentals_report']):,}, "
            f"news={len(template_variables['news_report']):,}, "
            f"sentiment={len(template_variables['sentiment_report']):,} 字符"
        )

        fallback_prompt = f"""请在一次深度思考中主持乐观/审慎双方的两轮对抗辩论，直接输出交锋台账与两份定稿研究结论（过程性内容只留在思考中）。

分析对象：{state.get('company_name') or ticker or '未指定'}（{ticker or '未指定'}）@ {analysis_date or '未指定'}

{topic_card}

【市场分析报告】
{template_variables['market_report'] or '无市场分析报告'}

【基本面分析报告】
{template_variables['fundamentals_report'] or '无基本面分析报告'}

【新闻分析报告】
{template_variables['news_report'] or '无新闻分析报告'}

【社交媒体情绪报告】
{template_variables['sentiment_report'] or '无情绪分析报告'}

【大盘分析报告】
{template_variables['index_report'] or '无大盘分析报告'}

【板块分析报告】
{template_variables['sector_report'] or '无板块分析报告'}

【筹码分布报告】
{template_variables['chip_report'] or '无筹码分布报告'}

【既有辩论历史】
{previous_debate or '无（本轮为首轮）'}

请严格按系统提示词规定的三段标记格式输出：正文只包含【交锋台账】【乐观情景研究结论】【审慎情景研究结论】三个小节（各独占一行），台账固定两行，两份定稿各含五个字段，不要输出任何过程内容。"""

        prompt = self._get_prompt_from_template(
            agent_type="researchers_v2",
            agent_name="research_self_debate_v2",
            variables=template_variables,
            state=state,
            context=state.get("context") if isinstance(state, dict) else state,
            fallback_prompt=fallback_prompt,
            prompt_type="user",
        )
        if prompt:
            logger.info(f"✅ 从模板系统获取研究自我辩论用户提示词 (长度: {len(prompt)})")
            return prompt
        logger.info(f"📝 [ResearchSelfDebate] 使用降级提示词 (长度: {len(fallback_prompt)})")
        return fallback_prompt

    def _get_required_reports(self) -> list:
        return [
            "market_report",
            "fundamentals_report",
            "news_report",
            "sentiment_report",
            "index_report",
            "sector_report",
            "chip_report",
        ]

    @staticmethod
    def _build_repair_prompt(raw: str, issues: list, topic_card: str) -> str:
        """校验失败后的一次性修复提示词（带问题清单与议题卡）"""
        issue_lines = "\n".join(f"- {issue}" for issue in issues)
        return f"""你上一版输出未通过格式与内容校验，请在不改变辩论结论实质的前提下重写一次完整输出。

必须修复以下问题：
{issue_lines}

重写要求：
1. 仍只围绕以下议题卡争点，不得扩展：
{topic_card}
2. 正文只包含【交锋台账】【乐观情景研究结论】【审慎情景研究结论】三节，标记独占一行；台账固定两行（第1轮、第2轮）；两份定稿各含 核心主张/支撑证据/对对方质疑的回应/成立前提/证伪信号 五个字段。
3. 支撑证据至少引用分析师报告中出现的 2 个具体数字。

上一版输出（供参考，可保留其中有效内容）：
{raw}"""

    # ==================== 执行 ====================

    @staticmethod
    def _normalize_content(content: Any) -> str:
        """把 LLM 返回内容统一成字符串"""
        if isinstance(content, list):
            content = "".join(str(c) for c in content)
        return str(content or "")

    def execute(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """执行研究双视角自我辩论（单次 LLM 调用 + 机械校验 + 一次修复重试）"""
        ticker = state.get("ticker", "") or state.get("company_of_interest", "")
        analysis_date = state.get("analysis_date", "") or state.get("trade_date", "")

        logger.info(f"🧠 研究自我辩论分析师开始评估 {ticker} @ {analysis_date}")

        debate_state = state.get("investment_debate_state", {}) or {}
        topic_card = self._build_topic_card(ticker, analysis_date, state)
        source_text = "\n".join(
            self._report_text(state.get(field)) for field, _ in self._MATERIAL_LABELS
        )

        try:
            system_prompt = self._apply_global_trading_advice_guard(
                self._build_system_prompt(state)
            )
            user_prompt = self._build_user_prompt(ticker, analysis_date, state, topic_card)
            messages = [
                SystemMessage(content=system_prompt),
                HumanMessage(content=user_prompt),
            ]

            import time
            llm_start_time = time.time()
            logger.info("⏱️ [ResearchSelfDebate] 开始调用LLM（单次调用替代双研究员多轮辩论）...")

            if not self._llm:
                raise ValueError("LLM not initialized")

            response = self._invoke_llm_with_trace(messages)
            raw = self._normalize_content(response.content)

            llm_elapsed = time.time() - llm_start_time
            logger.info(
                f"⏱️ [ResearchSelfDebate] LLM调用完成，耗时: {llm_elapsed:.2f}秒，"
                f"输出长度: {len(raw):,} 字符"
            )

            ledger, bull, bear = parse_self_debate_response(raw)
            issues = validate_self_debate(ledger, bull, bear, source_text)

            if issues:
                logger.warning(
                    f"⚠️ [ResearchSelfDebate] 机械校验未通过（{len(issues)} 项），"
                    f"触发一次修复重试: {issues}"
                )
                try:
                    repair_messages = messages + [
                        HumanMessage(
                            content=self._build_repair_prompt(raw, issues, topic_card)
                        )
                    ]
                    repair_response = self._invoke_llm_with_trace(repair_messages)
                    repaired_raw = self._normalize_content(repair_response.content)
                    r_ledger, r_bull, r_bear = parse_self_debate_response(repaired_raw)
                    r_issues = validate_self_debate(r_ledger, r_bull, r_bear, source_text)
                    logger.info(f"🔁 [ResearchSelfDebate] 修复重试后剩余问题: {len(r_issues)} 项")
                    if len(r_issues) < len(issues):
                        ledger, bull, bear, issues = r_ledger, r_bull, r_bear, r_issues
                except Exception as repair_error:
                    logger.warning(
                        f"⚠️ [ResearchSelfDebate] 修复重试调用失败: {repair_error}"
                    )

            if issues:
                logger.error(
                    f"❌ [ResearchSelfDebate] 校验仍不通过（{len(issues)} 项），"
                    f"置 _self_debate_failed=True 回退原双研究员路径: {issues}"
                )
                return {
                    "bull_report": "",
                    "bear_report": "",
                    "investment_debate_state": debate_state,
                    "_self_debate_failed": True,
                }

            logger.info(
                f"✅ 双视角解析完成: ledger={len(ledger):,}, "
                f"bull={len(bull):,}, bear={len(bear):,} 字符"
            )

            bull_arg = f"Bull Analyst: {bull}"
            bear_arg = f"Bear Analyst: {bear}"
            old_history = debate_state.get("history", "")
            old_count = debate_state.get("count", 0)

            new_debate_state = {
                "history": (old_history + "\n" + bull_arg + "\n" + bear_arg).strip("\n"),
                "bull_history": (debate_state.get("bull_history", "") + "\n" + bull_arg).strip("\n"),
                "bear_history": (debate_state.get("bear_history", "") + "\n" + bear_arg).strip("\n"),
                "current_response": bear_arg,
                "latest_speaker": "bear",
                "count": old_count + 2,  # 双方各一次定稿发言
                "debate_ledger": ledger,
            }

            logger.info("✅ 研究自我辩论完成（单节点替代双研究员多轮辩论）")

            return {
                "bull_report": bull,
                "bear_report": bear,
                "investment_debate_state": new_debate_state,
            }

        except Exception as e:
            logger.error(f"❌ 研究自我辩论失败: {e}", exc_info=True)
            return {
                "bull_report": "",
                "bear_report": "",
                "investment_debate_state": debate_state,
                "_self_debate_failed": True,
            }
