"""情景效果试算师 v2.0（v4.0 第二波：流程五段闭环 ③）

对交易计划做机械的情景效果试算：拿辩论结论给出的乐观/审慎情景区间
与市场报告基准价，计算各情景的空间、情景盈亏比、压力参考位与区间
重叠情况，并把计划中的验证信号/失效条件绑定进来，供风险审查环节
（风险三角 / 风险经理）与用户版计划整合（trader）参考。

设计要点：
- 完全确定性：不调用 LLM、不花 token；纯算术计算 + 正则解析；
- 宁缺勿造：区间/基准价解析不到就如实标注「未计算」，绝不臆造；
- 输出 state 字段 scenario_simulation（dict，含 text 摘要），下游经
  flow_context 注入风险审查与 trader 提示词。
"""

import json
import logging
from typing import Any, Dict, Optional, Tuple

from ..researcher import ResearcherAgent
from ..registry import register_agent
from ..config import AgentMetadata, AgentCategory, LicenseTier, AgentInput, AgentOutput
from .flow_context import _report_text, parse_price_range, parse_reference_price, is_degraded_placeholder

logger = logging.getLogger(__name__)


@register_agent
class ScenarioSimulatorV2(ResearcherAgent):
    """情景效果试算师 v2.0（确定性节点，无 LLM 调用）"""

    metadata = AgentMetadata(
        id="scenario_simulator_v2",
        name="情景效果试算师 v2.0",
        description="对交易计划做机械情景试算（空间/盈亏比/压力位/区间重叠），供风险审查参考",
        category=AgentCategory.RISK,
        version="2.0.0",
        license_tier=LicenseTier.FREE,
        default_tools=[],
        inputs=[
            AgentInput(name="ticker", type="string", description="股票代码"),
            AgentInput(name="analysis_date", type="string", description="分析日期"),
            AgentInput(name="investment_plan", type="string", description="综合研究结论（交易计划）", source="state", state_field="investment_plan", source_state_fields=["trader_investment_plan"]),
            AgentInput(name="bull_report", type="string", description="乐观情景研究结论", required=False, source="state", state_field="bull_report"),
            AgentInput(name="bear_report", type="string", description="审慎情景研究结论", required=False, source="state", state_field="bear_report"),
            AgentInput(name="market_report", type="string", description="市场分析报告", required=False, source="state", state_field="market_report"),
        ],
        outputs=[
            AgentOutput(name="scenario_simulation", type="dict", description="情景效果试算结果（含 text 摘要）"),
        ],
        requires_tools=False,
        output_field="scenario_simulation",
        report_label="【情景效果试算】",
        workflow_stage="risk",
        growth_role="reviewer",
        growth_outputs=["scenario_simulation"],
        review_level="manual_required",
        maturity_level="experimental",
        input_mode="upstream-dependent",
        debug_replay_mode="requires_chain_prefill",
        callable_surfaces=["workflow"],
    )

    output_field = "scenario_simulation"

    stance = "neutral"

    # ==================== 抽象方法占位（本节点不调 LLM，提示词不会被使用） ====================

    def _build_system_prompt(self, state=None) -> str:
        return "你是情景效果试算师，对交易计划做机械情景试算（本节点不调用 LLM）。"

    def _build_user_prompt(self, ticker: str, analysis_date: str, state=None) -> str:
        return f"试算 {ticker} @ {analysis_date} 的情景效果。"

    def _get_required_reports(self) -> list:
        return ["investment_plan", "bull_report", "bear_report", "market_report"]

    # ==================== 执行 ====================

    def execute(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """确定性执行情景效果试算（不调用 LLM）"""
        ticker = state.get("ticker", "") or state.get("company_of_interest", "")
        analysis_date = state.get("analysis_date", "") or state.get("trade_date", "")

        logger.info(f"🧮 [ScenarioSimulator] 情景效果试算: {ticker} @ {analysis_date}")

        bull_text = _report_text(state.get("bull_report"))
        bear_text = _report_text(state.get("bear_report"))
        market_text = _report_text(state.get("market_report"))

        # R5：上游关键输入降级 → 显式标注，不臆造试算结果
        degraded_inputs = []
        if is_degraded_placeholder(state.get("investment_plan")) or is_degraded_placeholder(state.get("trader_investment_plan")):
            degraded_inputs.append("投资计划")
        if is_degraded_placeholder(state.get("bull_report")):
            degraded_inputs.append("乐观情景报告")
        if is_degraded_placeholder(state.get("bear_report")):
            degraded_inputs.append("审慎情景报告")

        bull_range = parse_price_range(bull_text)
        bear_range = parse_price_range(bear_text)
        ref_price = parse_reference_price(market_text)
        plan_text = self._plan_text(state)

        sim: Dict[str, Any] = {
            "ticker": ticker,
            "analysis_date": analysis_date,
            "reference_price": ref_price,
            "bull_range": list(bull_range) if bull_range else None,
            "bear_range": list(bear_range) if bear_range else None,
            "upside_pct": None,
            "downside_pct": None,
            "scenario_rr": None,
            "pressure_floor": bear_range[0] if bear_range else None,
            "range_overlap": None,
            "plan_signals": self._plan_signals(plan_text),
        }

        notes = []
        if degraded_inputs:
            notes.append(f"上游降级：{', '.join(degraded_inputs)}，试算结果仅供参考")

        # 区间重叠（乐观下限 <= 审慎上限 即重叠）
        if bull_range and bear_range:
            sim["range_overlap"] = bool(bull_range[0] <= bear_range[1])

        # 情景空间（中值口径，相对基准价）
        if ref_price and bull_range:
            bull_mid = (bull_range[0] + bull_range[1]) / 2
            sim["upside_pct"] = (bull_mid - ref_price) / ref_price
        elif not bull_range:
            notes.append("乐观情景区间未能解析，上行空间未计算")
        if ref_price and bear_range:
            bear_mid = (bear_range[0] + bear_range[1]) / 2
            sim["downside_pct"] = (bear_mid - ref_price) / ref_price
        elif not bear_range:
            notes.append("审慎情景区间未能解析，下行空间未计算")
        if not ref_price:
            notes.append("市场报告未解析出基准价，情景空间均未计算")
        if sim["upside_pct"] is not None and sim["downside_pct"] not in (None, 0):
            sim["scenario_rr"] = abs(sim["upside_pct"] / sim["downside_pct"])

        sim["available"] = bool(bull_range or bear_range)
        if not notes and not sim["available"]:
            notes.append("情景区间全部缺失，试算未执行")

        sim["text"] = self._build_text(ticker, analysis_date, sim, notes)
        logger.info(
            f"✅ [ScenarioSimulator] 试算完成: available={sim['available']}, "
            f"upside={sim['upside_pct']}, downside={sim['downside_pct']}, "
            f"rr={sim['scenario_rr']}"
        )
        return {"scenario_simulation": sim}

    # ==================== 内部方法 ====================

    @staticmethod
    def _plan_text(state: Dict[str, Any]) -> str:
        """提取交易计划纯文本（investment_plan 优先，兼容 JSON 字符串）"""
        raw = state.get("investment_plan") or state.get("trader_investment_plan") or ""
        text = _report_text(raw) if isinstance(raw, dict) else str(raw or "")
        try:
            parsed = json.loads(text)
            if isinstance(parsed, dict):
                # 结构化计划：拼关键假设/验证信号/失效条件
                parts = []
                for key in ("关键假设", "验证信号", "失效条件", "analysis_view"):
                    if parsed.get(key):
                        parts.append(f"{key}: {parsed[key]}")
                if parts:
                    return "\n".join(str(p) for p in parts)
        except (json.JSONDecodeError, TypeError):
            pass
        return text

    @staticmethod
    def _plan_signals(plan_text: str) -> Optional[str]:
        """从计划文本中绑定验证信号/失效条件（原文截取，供审查对照）"""
        if not plan_text:
            return None
        lines = [
            line.strip()
            for line in plan_text.splitlines()
            if ("验证信号" in line or "失效条件" in line or "证伪" in line)
        ]
        if not lines:
            return None
        return "\n".join(lines[:6])

    @staticmethod
    def _fmt_pct(value: Optional[float]) -> str:
        if value is None:
            return "未计算"
        return f"{value * 100:+.1f}%"

    @staticmethod
    def _fmt_range(rng) -> str:
        if not rng:
            return "未能解析"
        return f"[{rng[0]:g}, {rng[1]:g}] 元"

    def _build_text(
        self,
        ticker: str,
        analysis_date: str,
        sim: Dict[str, Any],
        notes: list,
    ) -> str:
        """构建试算文本摘要（供提示词注入）"""
        lines = [
            f"标的：{ticker or '未指定'} @ {analysis_date or '未指定'}（情景中值口径，机械计算）",
            f"基准价：{('%g 元' % sim['reference_price']) if sim['reference_price'] else '未能解析'}",
            f"乐观情景区间：{self._fmt_range(sim['bull_range'])}"
            + (
                f"，中值对应上行空间 {self._fmt_pct(sim['upside_pct'])}"
                if sim['upside_pct'] is not None
                else ""
            ),
            f"审慎情景区间：{self._fmt_range(sim['bear_range'])}"
            + (
                f"，中值对应下行空间 {self._fmt_pct(sim['downside_pct'])}"
                if sim['downside_pct'] is not None
                else ""
            ),
            f"情景盈亏比（|上行/下行|中值口径）："
            + (f"{sim['scenario_rr']:.2f}" if sim['scenario_rr'] is not None else "未计算"),
            f"压力参考位（审慎区间下限）："
            + (f"{sim['pressure_floor']:g} 元" if sim['pressure_floor'] else "未能解析"),
            f"区间重叠："
            + ("是（乐观下限不高于审慎上限，分歧属幅度之争）" if sim['range_overlap']
               else "否（两情景对方向本身存在分歧）" if sim['range_overlap'] is False
               else "未能解析"),
        ]
        if sim.get("plan_signals"):
            lines.append("计划绑定的验证信号/失效条件（原文，供对照审查）：")
            lines.append(str(sim["plan_signals"]))
        if notes:
            lines.append("数据缺口：" + "；".join(notes))
        return "\n".join(lines)
