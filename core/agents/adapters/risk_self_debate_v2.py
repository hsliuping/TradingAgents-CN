"""
风险自我辩论分析师 v2.0（A9-P1）

单节点内完成高弹性/防御/基准三个风险审阅视角的立场陈述与交叉质证，
替代风险三角（risky/safe/neutral_analyst_v2）多轮辩论，
将风险辩论环节的 LLM 调用从 轮数×3 次降为 1 次。

设计要点：
- 仅当 state["_risk_self_debate"]=True（标准/深度/全面档且开关开启）时被路由到，
  快速/基础档继续走原风险三角多 agent 路径，互不影响。
- 输出与原风险三角完全兼容：
  * risky_opinion / safe_opinion / neutral_opinion 三个 state 字段
  * risk_debate_state 结构（histories / current_*_response / count）
  渲染层与 risk_manager_v2 零改动。
- 机械护栏（防跑题/防伪辩论）：
  1) 议题卡：程序化生成必答争点与材料边界，限定交锋范围；
  2) 轮次台账：固定两轮，逐轮记录争点/三视角观点/是否收敛；
  3) 五字段校验：三个观点必须含 核心判断/支撑证据/对另外两方质疑的回应/
     触发或失效条件/跟踪信号；
  4) 数字锚点校验：每个观点至少引用 2 个上游材料中的具体数字；
  5) 失败兜底：校验不过先带问题清单修复重试一次，仍不通过则置
     state["_risk_self_debate_failed"]=True，由 builder 条件边回退原风险三角路径。
- 取消历史「全文降级填充」：解析缺失侧不再用全文填充，避免三个视角静默变成同一段文本。
"""

import logging
import re
from typing import Any, Dict, List, Tuple

from langchain_core.messages import SystemMessage, HumanMessage

from ..researcher import ResearcherAgent
from ..registry import register_agent
from ..config import AgentMetadata, AgentCategory, LicenseTier, AgentInput, AgentOutput
from .flow_context import append_flow_context, safe_extract

logger = logging.getLogger(__name__)

# 四段标记（顺序即期望的输出顺序）：交锋台账 + 三视角定稿
_LEDGER_LABEL = "交锋台账"
_RISKY_LABEL = "高弹性情景观点"
_SAFE_LABEL = "防御情景观点"
_NEUTRAL_LABEL = "基准情景观点"
_SECTION_LABELS: Tuple[str, str, str, str] = (
    _LEDGER_LABEL,
    _RISKY_LABEL,
    _SAFE_LABEL,
    _NEUTRAL_LABEL,
)

# 每个观点必须包含的五字段（缺失即校验失败，用于机械拦截跑题/空话）
_REQUIRED_FIELDS = (
    "核心判断",
    "支撑证据",
    "对另外两方质疑的回应",
    "触发或失效条件",
    "跟踪信号",
)

# 交锋台账要求的最少轮次（固定两轮，禁止无限追加）
_REQUIRED_ROUNDS = 2

# 口径校验：从上游材料中抽取数字型锚点，要求每份观点至少命中 2 个
_NUMBER_RE = re.compile(r"\d+(?:\.\d+)?%?")

# 严格模式：标记独占一行（【X】/ ## X / **X** 等变体）
_MARKER_STRICT_RE = re.compile(
    r"(?m)^[ \t]*(?:#{1,6}[ \t]*)?(?:\*\*)?[【\[]?\s*"
    r"(交锋台账|高弹性情景观点|防御情景观点|基准情景观点)"
    r"\s*[】\]]?(?:\*\*)?[ \t]*[:：]?\s*$"
)

# 宽松模式：标记在行首、允许同行跟内容（严格模式解析失败时启用）
_MARKER_LOOSE_RE = re.compile(
    r"(?m)^[ \t]*(?:#{1,6}[ \t]*)?(?:\*\*)?[【\[]?\s*"
    r"(交锋台账|高弹性情景观点|防御情景观点|基准情景观点)"
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


def parse_self_debate_response(response: str) -> Tuple[str, str, str, str]:
    """
    解析自我辩论输出为 (交锋台账, 高弹性观点, 防御观点, 基准观点)。

    解析策略：严格（标记独占一行）→ 宽松（同行内容）。
    缺失侧不用全文兜底——交由 validate_self_debate 判失败并触发修复重试/回退，
    避免三个视角静默变成同一段全文。
    """
    if not response or not response.strip():
        return "", "", "", ""

    sections = _extract_sections(response, _MARKER_STRICT_RE)
    if len(sections) < 4:
        loose = _extract_sections(response, _MARKER_LOOSE_RE)
        if len(loose) > len(sections):
            sections = loose

    ledger = sections.get(_LEDGER_LABEL, "")
    risky = sections.get(_RISKY_LABEL, "")
    safe = sections.get(_SAFE_LABEL, "")
    neutral = sections.get(_NEUTRAL_LABEL, "")

    if not (ledger and risky and safe and neutral):
        logger.warning(
            f"[RiskSelfDebateV2] 输出分段不完整 "
            f"(ledger={bool(ledger)}, risky={bool(risky)}, "
            f"safe={bool(safe)}, neutral={bool(neutral)})"
        )
    return ledger, risky, safe, neutral


def validate_self_debate(
    ledger: str,
    risky: str,
    safe: str,
    neutral: str,
    source_text: str,
) -> list:
    """确定性校验（不花 token）：格式、轮次、五字段、数字锚点。

    返回问题列表；空列表表示通过。用于拦截跑题、空话和伪辩论。
    """
    issues: list = []

    for label, text in (
        (_LEDGER_LABEL, ledger),
        (_RISKY_LABEL, risky),
        (_SAFE_LABEL, safe),
        (_NEUTRAL_LABEL, neutral),
    ):
        if not text:
            issues.append(f"缺少【{label}】小节")

    # 轮次校验：台账必须明确出现第 1、2 轮
    for i in range(1, _REQUIRED_ROUNDS + 1):
        if f"第{i}轮" not in ledger:
            issues.append(f"交锋台账缺少第{i}轮记录")

    # 五字段校验：三视角观点都要有固定字段
    for label, text in (
        ("高弹性", risky),
        ("防御", safe),
        ("基准", neutral),
    ):
        if not text:
            continue
        missing = [field for field in _REQUIRED_FIELDS if field not in text]
        if missing:
            issues.append(f"{label}观点缺少字段: {'、'.join(missing)}")

    # 数字锚点校验：每个观点至少命中 2 个上游材料中的数字
    anchors = set(_NUMBER_RE.findall(source_text or ""))
    if len(anchors) >= 2:
        for label, text in (
            ("高弹性", risky),
            ("防御", safe),
            ("基准", neutral),
        ):
            if not text:
                continue
            hit = sum(1 for a in anchors if a in text)
            if hit < 2:
                issues.append(f"{label}观点引用上游材料的数字不足（{hit}/2）")

    return issues


@register_agent
class RiskSelfDebateV2(ResearcherAgent):
    """
    风险自我辩论分析师 v2.0

    工作流程：
    1. 读取综合研究结论（investment_plan）与全部上游分析报告
    2. 单次 LLM 调用中完成三视角两轮交锋：立论 → 交叉质证 → 定稿
    3. 机械校验（台账轮次 / 五字段 / 数字锚点），失败修复重试一次
    4. 通过后更新 risk_debate_state（histories / current_*_response / count）

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

    # 议题卡争点（程序化生成，机械限定辩论范围，防止跑题）
    _TOPIC_POINTS = (
        ("R1", "综合研究结论最脆弱的假设是什么", "investment_plan", "综合研究结论"),
        ("R2", "结论上修需要哪些高要求前提与催化证据", "bull_report", "乐观研究员报告"),
        ("R3", "下行风险的主要来源与失效条件", "news_report", "新闻分析报告"),
        ("R4", "当前信息缺口在哪里、哪份材料不足以支撑判断", "", ""),
        ("R5", "未来 1-3 个月哪些可跟踪信号会证伪当前结论", "", ""),
    )

    _MATERIAL_LABELS = (
        ("investment_plan", "综合研究结论"),
        ("bull_report", "乐观研究员报告"),
        ("bear_report", "审慎研究员报告"),
        ("market_report", "市场分析报告"),
        ("fundamentals_report", "基本面分析报告"),
        ("news_report", "新闻分析报告"),
        ("sentiment_report", "社交媒体情绪报告"),
        ("index_report", "大盘分析报告"),
        ("sector_report", "板块分析报告"),
    )

    # ==================== 提示词 ====================

    # 内置系统提示词：模板系统未配置该 Agent 时作为兜底传入，
    # 否则模板层会返回「请进行分析。」（长度 6），导致四段标记与交锋台账全部缺失
    _SYSTEM_PROMPT_FALLBACK = """你是一位资深风险研究专家，主持三个风险审阅视角的对抗辩论：高弹性情景、防御情景、基准情景。

辩论纪律（最高优先级，逐条遵守）：
1. 只围绕用户提示词中「风险辩论议题卡」列出的争点交锋。严禁引入议题卡以外的新话题或材料中不存在的数字与事实；某争点在材料中无依据时，直接写"材料不足，本争点不展开"。
2. 交锋固定两轮，不得增减：
   - 第1轮：三个视角就争点各自立论，必须引用综合研究结论或上游报告中的具体数字，并写明出处。
   - 第2轮：三个视角交叉质证——高弹性指出防御过度保守、忽视了哪些已验证的积极信号；防御指出高弹性的结论依赖哪些未验证假设、哪些证据存在瑕疵；基准比较双方证据强度并指出信息缺口。各方正面回应质疑后修正自身论证，第2轮结束必须收敛，严禁出现第3轮。
3. 正文必须且只能包含四节，顺序固定：交锋台账 → 高弹性情景观点 → 防御情景观点 → 基准情景观点；每节标记必须独占一行、原样输出（保留【】）。
4. 交锋台账严格两行、一行一轮，格式固定为：
   第1轮｜争点：<议题卡中的争点编号与名称>｜高弹性：<一句话>｜防御：<一句话>｜基准：<一句话>｜是否收敛：否
   第2轮｜争点：<...>｜高弹性：<...>｜防御：<...>｜基准：<...>｜是否收敛：是（或不收敛时写：否，分歧根因：...）
5. 三个观点都必须按顺序包含且标注以下五个字段：
   核心判断 / 支撑证据 / 对另外两方质疑的回应 / 触发或失效条件 / 跟踪信号
   其中「支撑证据」必须引用至少 2 个上游材料中出现的具体数字。

输出格式（严格照此结构，不得增删小节）：
【交锋台账】
第1轮｜争点：...｜高弹性：...｜防御：...｜基准：...｜是否收敛：否
第2轮｜争点：...｜高弹性：...｜防御：...｜基准：...｜是否收敛：是
【高弹性情景观点】
核心判断：...
支撑证据：...
对另外两方质疑的回应：...
触发或失效条件：...
跟踪信号：...
【防御情景观点】
核心判断：...
支撑证据：...
对另外两方质疑的回应：...
触发或失效条件：...
跟踪信号：...
【基准情景观点】
核心判断：...
支撑证据：...
对另外两方质疑的回应：...
触发或失效条件：...
跟踪信号：...

其他要求：
- 三个视角必须体现交叉质证后的结论差异，不得简单重复同一结论
- 严禁输出买卖指令（买入/卖出/加仓/减仓/持有/清仓）与具体目标价；如需给出价格分析区间，必须注明是情景测算、不构成目标价
- 严禁承诺收益或保证盈利，严禁输出概率数值、风险收益比或任何交易建议
- 严禁输出思考过程、格式说明或台账与定稿之外的讨论
- 使用中文撰写"""

    def _build_system_prompt(self, state: Dict[str, Any] = None) -> str:
        """构建系统提示词（模板系统优先，失败降级内置提示词）"""
        prompt = self._get_prompt_from_template(
            agent_type="debators_v2",
            agent_name="risk_self_debate_v2",
            variables={},
            state=state,
            context=state.get("context") if state else None,
            fallback_prompt=self._SYSTEM_PROMPT_FALLBACK,
            prompt_type="system",
        )
        if prompt:
            logger.debug("✅ 获取风险自我辩论系统提示词")
            return prompt

        return self._SYSTEM_PROMPT_FALLBACK

    @staticmethod
    def _report_text(value: Any) -> str:
        """提取报告纯文本（降级占位返回空串，不混入辩论）"""
        return safe_extract(value)

    def _build_topic_card(self, ticker: str, analysis_date: str, state: Dict[str, Any]) -> str:
        """生成风险辩论议题卡（确定性，不花 token）：限定争点范围与材料边界。"""
        available, missing = [], []
        for field, label in self._MATERIAL_LABELS:
            text = self._report_text(state.get(field))
            if text.strip():
                available.append(f"{label}（{len(text):,} 字）")
            else:
                missing.append(label)

        lines = [
            "风险辩论议题卡（只允许围绕以下争点交锋，不得扩展）：",
            f"标的：{ticker or '未指定'} @ {analysis_date or '未指定'}",
            f"可用材料：{'、'.join(available) if available else '无'}",
            f"缺失材料：{'、'.join(missing) if missing else '无'}",
            "必答争点：",
        ]
        for code, point, field, label in self._TOPIC_POINTS:
            if not field:
                lines.append(f"- {code} {point}（依据：全部可用材料）")
            elif self._report_text(state.get(field)).strip():
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
        investment_plan = state.get("investment_plan", "") or state.get("trader_investment_plan", "")
        # 🔑 上游 bull/bear_researcher_v2 写入 bull_report/bear_report（dict 含 content）；
        # state 中的 bull_opinion/bear_opinion 为历史遗留字段，始终为空
        bull_opinion = self._report_text(state.get("bull_report"))
        bear_opinion = self._report_text(state.get("bear_report"))
        if not topic_card:
            topic_card = self._build_topic_card(ticker, analysis_date, state)

        template_variables = {
            "ticker": ticker,
            "analysis_date": analysis_date,
            "risk_topic_card": topic_card,
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

        fallback_prompt = f"""请在一次深度思考中完成风险三视角的两轮对抗辩论，直接输出交锋台账与三个定稿观点（过程性内容只留在思考中）。

分析对象：{ticker or '未指定'} @ {analysis_date or '未指定'}

{topic_card}

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

请严格按系统提示词规定的四段标记格式输出：正文只包含【交锋台账】【高弹性情景观点】【防御情景观点】【基准情景观点】四个小节（各独占一行），台账固定两行，三个观点各含五个字段，不要输出任何过程内容。"""

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
            return append_flow_context(prompt, state, include_profile=True, include_simulation=True)
        logger.info(f"📝 [RiskSelfDebate] 使用降级提示词 (长度: {len(fallback_prompt)})")
        return append_flow_context(fallback_prompt, state, include_profile=True, include_simulation=True)

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
2. 正文只包含【交锋台账】【高弹性情景观点】【防御情景观点】【基准情景观点】四节，标记独占一行；台账固定两行（第1轮、第2轮）；三个观点各含 核心判断/支撑证据/对另外两方质疑的回应/触发或失效条件/跟踪信号 五个字段。
3. 支撑证据至少引用上游材料中出现的 2 个具体数字。

上一版输出（供参考，可保留其中有效内容）：
{raw}"""

    @staticmethod
    def _normalize_content(content: Any) -> str:
        """把 LLM 返回内容统一成字符串"""
        if isinstance(content, list):
            content = "".join(str(c) for c in content)
        return str(content or "")

    def execute(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        执行风险三视角自我辩论（单次 LLM 调用 + 机械校验 + 一次修复重试）

        Returns:
            更新后的状态，包含:
                - risky_opinion / safe_opinion / neutral_opinion: 三视角观点
                - risk_debate_state: 更新后的辩论状态
                - _risk_self_debate_failed=True: 校验两次未过，交由 builder 回退原风险三角路径
        """
        ticker = state.get("ticker", "") or state.get("company_of_interest", "")
        analysis_date = state.get("analysis_date", "") or state.get("trade_date", "")

        logger.info(f"🧠 风险自我辩论分析师开始评估 {ticker} @ {analysis_date}")

        risk_debate_state = state.get("risk_debate_state", {}) or {}
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
            logger.info("⏱️ [RiskSelfDebate] 开始调用LLM（单次调用替代风险三角多轮辩论）...")

            if not self._llm:
                raise ValueError("LLM not initialized")

            response = self._invoke_llm_with_trace(messages)
            raw = self._normalize_content(response.content)

            llm_elapsed = time.time() - llm_start_time
            logger.info(
                f"⏱️ [RiskSelfDebate] LLM调用完成，耗时: {llm_elapsed:.2f}秒，"
                f"输出长度: {len(raw):,} 字符"
            )

            ledger, risky, safe, neutral = parse_self_debate_response(raw)
            issues = validate_self_debate(ledger, risky, safe, neutral, source_text)

            if issues:
                logger.warning(
                    f"⚠️ [RiskSelfDebate] 机械校验未通过（{len(issues)} 项），"
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
                    r_ledger, r_risky, r_safe, r_neutral = parse_self_debate_response(repaired_raw)
                    r_issues = validate_self_debate(
                        r_ledger, r_risky, r_safe, r_neutral, source_text
                    )
                    logger.info(f"🔁 [RiskSelfDebate] 修复重试后剩余问题: {len(r_issues)} 项")
                    if len(r_issues) < len(issues):
                        ledger, risky, safe, neutral, issues = (
                            r_ledger, r_risky, r_safe, r_neutral, r_issues
                        )
                except Exception as repair_error:
                    logger.warning(f"⚠️ [RiskSelfDebate] 修复重试调用失败: {repair_error}")

            if issues:
                logger.error(
                    f"❌ [RiskSelfDebate] 校验仍不通过（{len(issues)} 项），"
                    f"置 _risk_self_debate_failed=True 回退原风险三角路径: {issues}"
                )
                return {
                    "risky_opinion": "",
                    "safe_opinion": "",
                    "neutral_opinion": "",
                    "risk_debate_state": risk_debate_state,
                    "_risk_self_debate_failed": True,
                }

            logger.info(
                f"✅ 三视角解析完成: ledger={len(ledger):,}, risky={len(risky):,}, "
                f"safe={len(safe):,}, neutral={len(neutral):,} 字符"
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
                "debate_ledger": ledger,
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
            return {
                "risky_opinion": "",
                "safe_opinion": "",
                "neutral_opinion": "",
                "risk_debate_state": risk_debate_state,  # 保持原状态
                "_risk_self_debate_failed": True,
            }
