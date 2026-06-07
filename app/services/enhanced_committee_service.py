"""
Enhanced single-stock research committee helpers.

The existing LangGraph remains the source of truth for the standard
TradingAgents workflow. This module adds optional post-analysis committee
reports without changing graph topology.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, Iterable, List, Optional, Tuple


DEFAULT_ENHANCED_COMMITTEE_AGENTS = [
    "data_steward",
    "industry_macro",
    "business_moat",
    "valuation",
    "flow_positioning",
    "scorecard",
]

COMMITTEE_AGENT_LABELS: Dict[str, str] = {
    "data_steward": "数据质量官",
    "industry_macro": "行业与宏观分析师",
    "business_moat": "商业与护城河分析师",
    "valuation": "估值分析师",
    "flow_positioning": "资金流与持仓分析师",
    "scorecard": "研究委员会评分卡",
}

LLM_COMMITTEE_AGENTS = {
    "industry_macro",
    "business_moat",
    "valuation",
    "flow_positioning",
}


@dataclass
class ScorecardEntry:
    agent: str
    label: str
    score: float
    confidence: float
    evidence_grade: str
    kill_switch: str


class EnhancedCommitteeService:
    """Build optional post-analysis reports for the enhanced committee mode."""

    def build_reports(
        self,
        *,
        request: Any,
        reports: Dict[str, Any],
        state: Dict[str, Any],
        decision: Dict[str, Any],
        llm: Optional[Any] = None,
    ) -> Dict[str, str]:
        params = getattr(request, "parameters", None)
        committee_mode = getattr(params, "committee_mode", "standard") if params else "standard"
        if committee_mode != "enhanced":
            return {}

        selected = self.normalize_selected_agents(
            getattr(params, "selected_committee_agents", None) if params else None
        )
        if not selected:
            selected = list(DEFAULT_ENHANCED_COMMITTEE_AGENTS)

        output: Dict[str, str] = {}
        scorecard: Dict[str, ScorecardEntry] = {}

        if "data_steward" in selected:
            memo, entry = self._build_data_steward_report(request, reports, state)
            output["committee_data_steward"] = memo
            scorecard["data_steward"] = entry

        context = self._build_context(request, reports, decision)
        for agent_id in selected:
            if agent_id not in LLM_COMMITTEE_AGENTS:
                continue
            memo = self._build_llm_agent_report(agent_id, context, llm)
            output[f"committee_{agent_id}"] = memo
            scorecard[agent_id] = self._entry_from_memo(agent_id, memo, reports)

        if "scorecard" in selected:
            output["committee_scorecard"] = self._build_scorecard_report(scorecard)
            output["committee_reconciliation"] = self._build_reconciliation_report(scorecard, decision)

        return output

    def normalize_selected_agents(self, selected: Optional[Iterable[str]]) -> List[str]:
        if not selected:
            return []
        normalized: List[str] = []
        for agent_id in selected:
            if agent_id in COMMITTEE_AGENT_LABELS and agent_id not in normalized:
                normalized.append(agent_id)
        return normalized

    def _build_data_steward_report(
        self,
        request: Any,
        reports: Dict[str, Any],
        state: Dict[str, Any],
    ) -> Tuple[str, ScorecardEntry]:
        required_reports = {
            "market_report": "市场技术分析",
            "fundamentals_report": "基本面分析",
            "final_trade_decision": "最终交易决策",
        }
        missing = [
            label
            for key, label in required_reports.items()
            if not isinstance(reports.get(key), str) or len(reports.get(key, "").strip()) < 20
        ]

        if len(missing) >= 2:
            evidence_grade = "D"
            confidence_cap = 0.35
        elif missing:
            evidence_grade = "C"
            confidence_cap = 0.55
        else:
            evidence_grade = "B"
            confidence_cap = 0.72

        params = getattr(request, "parameters", None)
        analysis_date = getattr(params, "analysis_date", None) if params else None
        if isinstance(analysis_date, datetime):
            analysis_date_text = analysis_date.strftime("%Y-%m-%d")
        else:
            analysis_date_text = str(analysis_date or "未提供")

        performance = state.get("performance_metrics", {}) if isinstance(state, dict) else {}
        missing_text = "、".join(missing) if missing else "无核心报告缺失"

        memo = (
            "## 数据质量官\n\n"
            f"- 证据等级：{evidence_grade}\n"
            f"- 置信度上限：{confidence_cap:.0%}\n"
            f"- 分析日期：{analysis_date_text}\n"
            f"- 缺失或不足：{missing_text}\n"
            f"- 性能记录：{performance or '未提供'}\n\n"
            "结论：该模块用于限制增强委员会的过度自信。若核心报告缺失，"
            "后续估值、资金流和交易计划只应作为低置信度参考。"
        )
        entry = ScorecardEntry(
            agent="data_steward",
            label=COMMITTEE_AGENT_LABELS["data_steward"],
            score=0.0,
            confidence=confidence_cap,
            evidence_grade=evidence_grade,
            kill_switch="核心行情/基本面/最终决策报告缺失时，不允许给出强买入评级。",
        )
        return memo, entry

    def _build_context(
        self,
        request: Any,
        reports: Dict[str, Any],
        decision: Dict[str, Any],
    ) -> Dict[str, Any]:
        params = getattr(request, "parameters", None)
        symbol = request.get_symbol() if hasattr(request, "get_symbol") else getattr(request, "symbol", "")
        return {
            "stock_code": symbol,
            "market_type": getattr(params, "market_type", "A股") if params else "A股",
            "research_depth": getattr(params, "research_depth", "标准") if params else "标准",
            "selected_analysts": getattr(params, "selected_analysts", []) if params else [],
            "decision": decision or {},
            "reports": self._compact_reports(reports),
        }

    def _compact_reports(self, reports: Dict[str, Any], limit: int = 1000) -> Dict[str, str]:
        compact: Dict[str, str] = {}
        for key, value in reports.items():
            if isinstance(value, str) and value.strip():
                compact[key] = value.strip()[:limit]
        return compact

    def _build_llm_agent_report(self, agent_id: str, context: Dict[str, Any], llm: Optional[Any]) -> str:
        label = COMMITTEE_AGENT_LABELS[agent_id]
        prompt = self._build_agent_prompt(agent_id, context)

        if llm is not None:
            try:
                response = llm.invoke(prompt)
                content = getattr(response, "content", response)
                if isinstance(content, str) and content.strip():
                    return content.strip()
            except Exception:
                pass

        return self._build_fallback_agent_report(agent_id, context)

    def _build_agent_prompt(self, agent_id: str, context: Dict[str, Any]) -> str:
        label = COMMITTEE_AGENT_LABELS[agent_id]
        return (
            f"你是 TradingAgents-CN 增强研究委员会中的{label}。\n"
            "请基于已有报告做追加分析，不要编造未给出的精确数据。\n"
            "输出 Markdown，包含：立场、核心依据、正面因素、负面因素、"
            "证据等级(A-D)、置信度(0-1)、kill switch。\n\n"
            f"股票代码：{context['stock_code']}\n"
            f"市场类型：{context['market_type']}\n"
            f"研究深度：{context['research_depth']}\n"
            f"已有决策：{context['decision']}\n"
            f"已有报告摘要：{context['reports']}"
        )

    def _build_fallback_agent_report(self, agent_id: str, context: Dict[str, Any]) -> str:
        label = COMMITTEE_AGENT_LABELS[agent_id]
        decision = context.get("decision", {})
        action = decision.get("action", "持有") if isinstance(decision, dict) else "持有"

        focus_map = {
            "industry_macro": "行业政策、宏观周期和同业表现需要进一步验证。",
            "business_moat": "商业模式、竞争壁垒和管理执行需要结合最新公告继续确认。",
            "valuation": "估值吸引力需要与历史区间、同业倍数和盈利质量一起判断。",
            "flow_positioning": "资金流、换手率和拥挤度信息不足时，不宜追高解读。",
        }
        focus = focus_map.get(agent_id, "该维度需要更多数据验证。")
        evidence_grade = "C" if context.get("reports") else "D"

        return (
            f"## {label}\n\n"
            "- 立场：中性\n"
            f"- 当前动作参考：{action}\n"
            f"- 核心判断：{focus}\n"
            f"- 证据等级：{evidence_grade}\n"
            "- 置信度：0.50\n"
            "- Kill Switch：若后续公开数据与当前报告方向冲突，应降低评级或暂停交易计划。"
        )

    def _entry_from_memo(
        self,
        agent_id: str,
        memo: str,
        reports: Dict[str, Any],
    ) -> ScorecardEntry:
        evidence_grade = "B" if len(reports) >= 3 else "C" if reports else "D"
        lowered = memo.lower()
        score = 0.0
        if any(word in memo for word in ("积极", "正面", "上行", "低估", "改善")) or "bullish" in lowered:
            score = 0.5
        if any(word in memo for word in ("负面", "下行", "高估", "恶化", "拥挤")) or "bearish" in lowered:
            score = min(score, -0.5)

        return ScorecardEntry(
            agent=agent_id,
            label=COMMITTEE_AGENT_LABELS[agent_id],
            score=score,
            confidence=0.5 if evidence_grade != "D" else 0.3,
            evidence_grade=evidence_grade,
            kill_switch="公开数据或价格行为与该维度判断明显冲突。",
        )

    def _build_scorecard_report(self, entries: Dict[str, ScorecardEntry]) -> str:
        if not entries:
            return "## 研究委员会评分卡\n\n暂无可聚合的增强委员会维度。"

        rows = [
            "| 维度 | 分数 | 置信度 | 证据等级 | Kill Switch |",
            "| --- | ---: | ---: | --- | --- |",
        ]
        weighted_total = 0.0
        for entry in entries.values():
            weighted_total += entry.score * entry.confidence
            rows.append(
                f"| {entry.label} | {entry.score:.1f} | {entry.confidence:.0%} | "
                f"{entry.evidence_grade} | {entry.kill_switch} |"
            )

        avg = weighted_total / max(len(entries), 1)
        return (
            "## 研究委员会评分卡\n\n"
            + "\n".join(rows)
            + f"\n\n综合加权倾向：{avg:.2f}\n\n"
            "说明：分数范围为 -2 到 +2；增强委员会输出用于补充现有 TradingAgents 结论，"
            "不替代最终交易决策。"
        )

    def _build_reconciliation_report(
        self,
        entries: Dict[str, ScorecardEntry],
        decision: Dict[str, Any],
    ) -> str:
        weak_entries = [entry.label for entry in entries.values() if entry.evidence_grade in {"C", "D"}]
        action = decision.get("action", "持有") if isinstance(decision, dict) else "持有"
        weak_text = "、".join(weak_entries) if weak_entries else "暂无低证据等级维度"

        return (
            "## 研究委员会分歧调和\n\n"
            f"- 原始 TradingAgents 动作参考：{action}\n"
            f"- 需谨慎解读的维度：{weak_text}\n"
            "- 调和结论：当数据质量、估值或资金流证据不足时，增强委员会只降低置信度，"
            "不直接覆盖原始最终交易决策。若任一 kill switch 触发，应重新分析或下调仓位。"
        )


enhanced_committee_service = EnhancedCommitteeService()
