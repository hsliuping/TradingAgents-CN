"""风险画像分析师 v2.0（v4.0 第二波：流程五段闭环 ①）

程序化生成「事前风险约束卡」，插在投资辩论之后、研究经理（计划生成）之前，
把风险信息从「事后否决」前移为「事前约束」——交易计划生成时即看到
持仓口径、情景区间边界与硬性约束条目，计划天生合规。

设计要点：
- 完全确定性：不调用 LLM、不花 token、不产生网络请求；
- 宁缺勿造：情景区间/基准价从辩论结论与市场报告中正则解析，解析不到
  如实标注缺失，绝不推算或编造；
- 输出 state 字段 risk_profile_card（dict，含 text 摘要），下游
  research_manager_v2 / trader_v2 经 flow_context 注入提示词。
"""

import logging
from typing import Any, Dict

from ..researcher import ResearcherAgent
from ..registry import register_agent
from ..config import AgentMetadata, AgentCategory, LicenseTier, AgentInput, AgentOutput
from .flow_context import _report_text, parse_price_range, parse_reference_price

logger = logging.getLogger(__name__)


@register_agent
class RiskProfileV2(ResearcherAgent):
    """风险画像分析师 v2.0（确定性节点，无 LLM 调用）"""

    metadata = AgentMetadata(
        id="risk_profile_v2",
        name="风险画像分析师 v2.0",
        description="程序化生成事前风险约束卡（持仓口径/情景区间/约束条目），供计划生成与审查遵守",
        category=AgentCategory.RISK,
        version="2.0.0",
        license_tier=LicenseTier.FREE,
        default_tools=[],
        inputs=[
            AgentInput(name="ticker", type="string", description="股票代码"),
            AgentInput(name="analysis_date", type="string", description="分析日期"),
            AgentInput(name="bull_report", type="string", description="乐观情景研究结论", required=False, source="state", state_field="bull_report"),
            AgentInput(name="bear_report", type="string", description="审慎情景研究结论", required=False, source="state", state_field="bear_report"),
            AgentInput(name="market_report", type="string", description="市场分析报告", required=False, source="state", state_field="market_report"),
            AgentInput(name="position_info", type="dict", description="持仓信息（持仓类工作流）", required=False, source="state", state_field="position_info"),
            AgentInput(name="portfolio_data", type="dict", description="持仓数据（持仓类工作流）", required=False, source="state", state_field="portfolio_data"),
        ],
        outputs=[
            AgentOutput(name="risk_profile_card", type="dict", description="事前风险约束卡（含 text 摘要）"),
        ],
        requires_tools=False,
        output_field="risk_profile_card",
        report_label="【事前风险约束卡】",
        workflow_stage="risk",
        growth_role="reviewer",
        growth_outputs=["risk_profile_card"],
        review_level="manual_required",
        maturity_level="experimental",
        input_mode="upstream-dependent",
        debug_replay_mode="requires_chain_prefill",
        callable_surfaces=["workflow"],
    )

    output_field = "risk_profile_card"

    stance = "neutral"

    # ==================== 抽象方法占位（本节点不调 LLM，提示词不会被使用） ====================

    def _build_system_prompt(self, state=None) -> str:
        return "你是风险画像分析师，程序化生成事前风险约束卡（本节点不调用 LLM）。"

    def _build_user_prompt(self, ticker: str, analysis_date: str, state=None) -> str:
        return f"生成 {ticker} @ {analysis_date} 的事前风险约束卡。"

    def _get_required_reports(self) -> list:
        return ["bull_report", "bear_report", "market_report"]

    # ==================== 执行 ====================

    def execute(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """确定性生成事前风险约束卡（不调用 LLM）"""
        ticker = state.get("ticker", "") or state.get("company_of_interest", "")
        analysis_date = state.get("analysis_date", "") or state.get("trade_date", "")

        logger.info(f"🛡️ [RiskProfile] 生成事前风险约束卡: {ticker} @ {analysis_date}")

        bull_text = _report_text(state.get("bull_report"))
        bear_text = _report_text(state.get("bear_report"))
        market_text = _report_text(state.get("market_report"))

        bull_range = parse_price_range(bull_text)
        bear_range = parse_price_range(bear_text)
        ref_price = parse_reference_price(market_text)

        position = state.get("position_info") or state.get("portfolio_data")
        has_position = bool(position)

        # ---- 约束条目（固定 + 区间派生，全部研究口径，非交易指令） ----
        constraints = [
            "每个情景结论必须附带可公开跟踪的证伪信号（失效条件），不得只给结论",
            "只可引用已提供材料中的数字，材料缺失处如实写明，不得推算或编造",
        ]
        if bear_range:
            constraints.append(
                f"审慎情景区间下限 {bear_range[0]:g} 元为压力参考位，"
                f"更积极的判断必须说明该位跌破时的逻辑应对（研究口径）"
            )
        else:
            constraints.append("审慎情景区间未能解析，结论必须自行给出下行情景的压力位假设")
        if bull_range:
            constraints.append(
                f"乐观情景区间上限 {bull_range[1]:g} 元为情景上界，超出该上界的判断视为脱离材料"
            )
        if has_position:
            constraints.append("已有持仓数据，计划讨论必须区分持仓调整视角与新建仓视角")
        else:
            constraints.append("无持仓数据，按新建仓研究口径讨论，仓位表述必须带上限约束与分批原则，禁止满仓式表述")

        # ---- 文本摘要（供提示词注入） ----
        lines = [
            f"标的：{state.get('company_name') or ticker or '未指定'}（{ticker or '未指定'}）@ {analysis_date or '未指定'}",
            f"情景区间（源自辩论结论）："
            f"乐观 {self._fmt_range(bull_range)}；审慎 {self._fmt_range(bear_range)}",
            f"基准价：{('%g 元（源自市场报告）' % ref_price) if ref_price else '未能解析（市场报告无现价表述）'}",
            f"持仓口径：{'有持仓数据（持仓调整+新建仓双视角）' if has_position else '无持仓数据（新建仓研究口径）'}",
            "约束条目：",
        ]
        lines.extend(f"{i}. {c}" for i, c in enumerate(constraints, 1))
        text = "\n".join(lines)

        card = {
            "ticker": ticker,
            "analysis_date": analysis_date,
            "bull_range": list(bull_range) if bull_range else None,
            "bear_range": list(bear_range) if bear_range else None,
            "reference_price": ref_price,
            "has_position": has_position,
            "constraints": constraints,
            "text": text,
        }

        logger.info(
            f"✅ [RiskProfile] 约束卡生成完成: "
            f"bull_range={bull_range}, bear_range={bear_range}, "
            f"ref_price={ref_price}, has_position={has_position}"
        )
        return {"risk_profile_card": card}

    @staticmethod
    def _fmt_range(rng) -> str:
        if not rng:
            return "未能解析（辩论结论未含价格区间）"
        return f"[{rng[0]:g}, {rng[1]:g}] 元"
