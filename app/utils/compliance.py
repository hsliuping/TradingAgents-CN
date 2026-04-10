"""合规输出工具。

统一收口分析结果中的交易建议型字段，保留研究辅助所需的摘要、风险因素和公开信息观察。
"""

from __future__ import annotations

import re
from typing import Any, Dict, Iterable, List


SAFE_REPORT_KEYS = (
    "index_report",
    "sector_report",
    "market_report",
    "fundamentals_report",
    "sentiment_report",
    "news_report",
)

GENERIC_RESEARCH_RECOMMENDATION = "请参考详细研究报告，重点关注基本面变化、市场环境与风险因素。"
GENERIC_POSITION_RECOMMENDATION = "该持仓研究仅提供研究观察与风险提示，请结合自身策略独立判断。"
GENERIC_REVIEW_SUMMARY = "本次复盘仅保留复盘结论、纪律问题与研究改进方向，不提供未来交易动作建议。"
GENERIC_REVIEW_IMPROVEMENTS = (
    "完善交易前证据核验与记录，避免临盘依据不足。",
    "将交易计划触发条件整理为可验证清单，提升执行一致性。",
    "复盘时重点检查纪律执行、风险暴露与研究盲区。",
)

_ACTIONABLE_PATTERNS = [
    re.compile(pattern, re.IGNORECASE)
    for pattern in (
        r"买入|卖出|持有|加仓|减仓|清仓|建仓|平仓|调仓",
        r"止损|止盈|仓位|目标价|目标价格|目标区间|价格分析区间|参考价格",
        r"目标位|目标点位|支撑位|阻力位|压力位|配置建议|防御性配置|进攻性配置|安全边际|板块机会",
        r"投资建议|交易建议|操作建议|一键模拟下单|下单|模拟交易",
        r"BUY|SELL|HOLD|STRONG_BUY|STRONG_SELL",
        r"target_price|stop_loss|take_profit|position_ratio|suggested_quantity|suggested_amount",
    )
]
_REVIEW_EXECUTION_PATTERNS = [
    re.compile(pattern, re.IGNORECASE)
    for pattern in (
        r"(建议|可以|可考虑|应当|应该|需要|宜|不宜).{0,12}(买入|卖出|继续持有|持有|加仓|减仓|补仓|清仓|建仓|平仓|调仓)",
        r"(下次|后续|未来).{0,16}(买入|卖出|继续持有|持有|加仓|减仓|补仓|清仓|建仓|平仓|调仓|止损|止盈)",
        r"继续持有|逢低买入|逢高卖出|分批买入|分批卖出",
        r"止损价|止盈价|目标价|目标价格|目标区间|参考价|参考价格",
        r"(跌破|突破|回调到|反弹到|跌到|涨到|回到).{0,12}(买入|卖出|加仓|减仓|止损|止盈)",
        r"仓位.{0,8}(\d+%|百分之|\d+成|控制在|提升到|降到|上调到|下调到)",
        r"\b(BUY|SELL|HOLD|STRONG_BUY|STRONG_SELL)\b",
        r"一键模拟下单|下单|模拟交易",
    )
]
_JSON_FIELD_PATTERN = re.compile(r'^[\[\]{}":,0-9._%\-\s]+$')
_SENTENCE_SPLIT_PATTERN = re.compile(r"[\n。！？；]+")
_LOW_SIGNAL_PATTERNS = [
    re.compile(pattern, re.IGNORECASE)
    for pattern in (
        r"^股票基本信息$",
        r"^公司名称[:：]",
        r"^股票代码[:：]",
        r"^所属市场[:：]",
        r"^当前价格[:：]",
        r"^涨跌幅[:：]",
        r"^分析日期[:：]",
        r"^数据来源[:：]",
        r"^基本信息[:：]",
        r"^财务数据[:：]$",
        r"^一、公司概况$",
        r"^二、财务数据分析$",
        r"^三、",
        r"^四、",
        r"分析报告",
    )
]
_DISPLAY_REPORT_RISK_PATTERNS = [
    re.compile(pattern, re.IGNORECASE)
    for pattern in (
        r"目标价|目标价格|价格区间|关键价位|关键价格|关键验证位|观察区间|参考价|参考价格|风险控制参考",
        r"支撑位|阻力位|突破|跌破|站稳|失守|止损|止盈|仓位|风险敞口|持仓周期",
        r"上涨空间|下跌空间|上行空间|下行空间|收益空间|收益预期|最大收益|潜在收益|回撤|最大可能损失",
        r"风险收益比|期望收益|安全边际|配置价值|逆向投资机会|买入信号|卖出信号|入场|退出条件|操作策略",
        r"增持观点|减持观点|建仓|平仓|调仓|重仓|轻仓|分批买入|分批卖出|看涨价位|看跌价位",
        r"(?:¥|￥|\$)\s*\d|\d+(?:\.\d+)?\s*(?:元|美元|港元)",
    )
]


def _as_text(value: Any) -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        for key in ("content", "markdown", "text", "message", "report"):
            item = value.get(key)
            if isinstance(item, str) and item.strip():
                return item
        return ""
    return "" if value is None else str(value)


def contains_actionable_content(text: str) -> bool:
    if not text:
        return False
    return any(pattern.search(text) for pattern in _ACTIONABLE_PATTERNS)


def contains_review_execution_guidance(text: str) -> bool:
    if not text:
        return False
    normalized = _plain_text(text)
    if not normalized:
        return False
    return any(pattern.search(normalized) for pattern in _REVIEW_EXECUTION_PATTERNS)


def _plain_text(text: str) -> str:
    normalized = re.sub(r"```.*?```", " ", text, flags=re.DOTALL)
    normalized = re.sub(r"`+", "", normalized)
    normalized = normalized.replace("#", " ").replace("*", " ")
    return re.sub(r"\s+", " ", normalized).strip()


def is_low_signal_text(text: str) -> bool:
    normalized = _plain_text(text)
    if not normalized:
        return True
    if any(pattern.search(normalized) for pattern in _LOW_SIGNAL_PATTERNS):
        return True
    if normalized.startswith("-") and len(normalized) <= 14:
        return True
    return False


def _fragment_score(text: str) -> int:
    normalized = _plain_text(text)
    if not normalized:
        return -1

    score = min(len(normalized), 160)
    if is_low_signal_text(normalized):
        score -= 120
    if any(keyword in normalized for keyword in ("风险", "盈利", "增长", "压力", "竞争", "估值", "资产", "负债", "催化", "行业", "宏观", "需求", "收入", "利润")):
        score += 60
    if normalized.startswith("-"):
        score -= 10
    return score


def sanitize_text_block(text: Any, fallback: str = "") -> str:
    raw_text = _as_text(text)
    if not raw_text:
        return fallback

    lines: List[str] = []
    for chunk in re.split(r"\r?\n", raw_text):
        line = _plain_text(chunk)
        if not line or len(line) < 6:
            continue
        if _JSON_FIELD_PATTERN.match(line):
            continue
        if contains_actionable_content(line):
            continue
        if is_low_signal_text(line):
            continue
        lines.append(line)

    deduped: List[str] = []
    for line in lines:
        if line not in deduped:
            deduped.append(line)

    if not deduped:
        return fallback
    return "\n".join(deduped[:12])[:2500]


def _iter_review_fragments(text: Any) -> Iterable[str]:
    raw_text = _as_text(text)
    if not raw_text:
        return

    for chunk in re.split(r"\r?\n", raw_text):
        normalized = _plain_text(chunk)
        if not normalized:
            continue

        fragments = [
            fragment.strip()
            for fragment in _SENTENCE_SPLIT_PATTERN.split(normalized)
            if fragment.strip()
        ]
        if not fragments:
            fragments = [normalized]

        for fragment in fragments:
            if len(fragment) < 4:
                continue
            if _JSON_FIELD_PATTERN.match(fragment):
                continue
            if contains_review_execution_guidance(fragment):
                continue
            if is_low_signal_text(fragment):
                continue
            yield fragment


def sanitize_review_text_block(text: Any, fallback: str = "") -> str:
    deduped: List[str] = []
    for fragment in _iter_review_fragments(text):
        if fragment not in deduped:
            deduped.append(fragment)

    if not deduped:
        return fallback
    return "；".join(deduped[:6])[:1200]


def sanitize_review_points(points: Any, fallback: Iterable[str] = ()) -> List[str]:
    cleaned_points: List[str] = []

    if isinstance(points, list):
        source_items = points
    elif points in (None, ""):
        source_items = []
    else:
        source_items = [points]

    for item in source_items:
        for fragment in _iter_review_fragments(item):
            if fragment not in cleaned_points:
                cleaned_points.append(fragment)
            if len(cleaned_points) >= 5:
                return cleaned_points

    for item in fallback:
        normalized = _plain_text(item)
        if normalized and normalized not in cleaned_points:
            cleaned_points.append(normalized)
        if len(cleaned_points) >= 5:
            break

    return cleaned_points[:5]


def sanitize_brief_points(points: Any) -> List[str]:
    cleaned_points: List[str] = []

    if not isinstance(points, list):
        return cleaned_points

    for item in points:
        normalized = _plain_text(_as_text(item))
        if len(normalized) < 2:
            continue
        if _JSON_FIELD_PATTERN.match(normalized):
            continue
        if contains_actionable_content(normalized):
            continue
        if is_low_signal_text(normalized):
            continue
        if normalized not in cleaned_points:
            cleaned_points.append(normalized[:120])
        if len(cleaned_points) >= 5:
            break

    return cleaned_points


def sanitize_display_report_text(text: Any, fallback: str = "") -> str:
    raw_text = _as_text(text)
    if not raw_text:
        return fallback

    cleaned_lines: List[str] = []

    for raw_line in raw_text.splitlines():
        line = raw_line.rstrip()
        normalized = _plain_text(line)

        if not normalized:
            if cleaned_lines and cleaned_lines[-1] != "":
                cleaned_lines.append("")
            continue

        if contains_actionable_content(normalized):
            continue
        if any(pattern.search(normalized) for pattern in _DISPLAY_REPORT_RISK_PATTERNS):
            continue

        cleaned_lines.append(line)

    while cleaned_lines and cleaned_lines[0] == "":
        cleaned_lines.pop(0)
    while cleaned_lines and cleaned_lines[-1] == "":
        cleaned_lines.pop()

    cleaned_text = "\n".join(cleaned_lines)
    cleaned_text = re.sub(r"\n{3,}", "\n\n", cleaned_text).strip()

    if cleaned_text:
        return cleaned_text[:4000]

    return sanitize_text_block(raw_text, fallback=fallback)


def filter_analysis_reports(reports: Any) -> Dict[str, str]:
    if not isinstance(reports, dict):
        return {}

    filtered: Dict[str, str] = {}
    for key in SAFE_REPORT_KEYS:
        cleaned = sanitize_text_block(reports.get(key))
        if cleaned:
            filtered[key] = cleaned
    return filtered


def _iter_safe_fragments(reports: Dict[str, str], fallback_summary: str = "") -> Iterable[str]:
    if fallback_summary:
        cleaned_summary = sanitize_text_block(fallback_summary)
        if cleaned_summary:
            for fragment in _SENTENCE_SPLIT_PATTERN.split(cleaned_summary):
                sentence = fragment.strip()
                if sentence and not contains_actionable_content(sentence) and not is_low_signal_text(sentence):
                    yield sentence

    summary_priority = (
        "fundamentals_report",
        "market_report",
        "sector_report",
        "news_report",
        "sentiment_report",
        "index_report",
    )

    for key in summary_priority:
        content = sanitize_text_block(reports.get(key, ""))
        if not content:
            continue
        for fragment in _SENTENCE_SPLIT_PATTERN.split(content):
            sentence = fragment.strip()
            if sentence and not contains_actionable_content(sentence) and not is_low_signal_text(sentence):
                yield sentence


def build_research_summary(reports: Dict[str, str], fallback_summary: str = "") -> str:
    candidate_fragments: List[str] = []
    for fragment in _iter_safe_fragments(reports, fallback_summary):
        normalized = _plain_text(fragment)
        if normalized and normalized not in candidate_fragments:
            candidate_fragments.append(normalized)

    summary_parts = sorted(candidate_fragments, key=_fragment_score, reverse=True)[:3]

    if summary_parts:
        return "；".join(summary_parts)[:800]

    return "本次结果已按研究辅助模式输出，请重点关注基础数据、风险因素与后续披露信息。"


def build_key_points(reports: Dict[str, str], key_points: Any, summary: str) -> List[str]:
    cleaned_points: List[str] = []
    if isinstance(key_points, list):
        for item in key_points:
            point = sanitize_text_block(item)
            if point and point not in cleaned_points and not is_low_signal_text(point):
                cleaned_points.append(point)

    if len(cleaned_points) >= 3:
        return cleaned_points[:5]

    for fragment in _iter_safe_fragments(reports, summary):
        if fragment not in cleaned_points and not is_low_signal_text(fragment):
            cleaned_points.append(fragment)
        if len(cleaned_points) >= 5:
            break

    return cleaned_points[:5]


def sanitize_analysis_payload(result_data: Dict[str, Any]) -> Dict[str, Any]:
    if not isinstance(result_data, dict) or not result_data:
        return result_data

    sanitized = dict(result_data)
    reports = filter_analysis_reports(sanitized.get("reports") or {})
    summary = build_research_summary(reports, sanitized.get("summary", ""))

    sanitized["reports"] = reports
    sanitized["summary"] = summary
    sanitized["key_points"] = build_key_points(reports, sanitized.get("key_points"), summary)

    decision = sanitized.get("decision")
    normalized_action = ""
    if isinstance(decision, dict):
        sanitized_decision: Dict[str, Any] = {}
        action = decision.get("analysis_view") or decision.get("action")
        if isinstance(action, str) and action.strip():
            action_mapping = {
                "BUY": "看涨",
                "SELL": "看跌",
                "HOLD": "中性",
                "buy": "看涨",
                "sell": "看跌",
                "hold": "中性",
                "买入": "看涨",
                "卖出": "看跌",
                "持有": "中性",
            }
            normalized_action = action_mapping.get(action.strip(), action.strip())
            sanitized_decision["action"] = normalized_action
            sanitized_decision["analysis_view"] = normalized_action
        confidence = decision.get("confidence")
        if isinstance(confidence, (int, float)):
            sanitized_decision["confidence"] = confidence / 100 if confidence > 1 else confidence
        risk_score = decision.get("risk_score")
        if isinstance(risk_score, (int, float)):
            sanitized_decision["risk_score"] = risk_score / 100 if risk_score > 1 else risk_score
        reasoning = sanitize_text_block(decision.get("reasoning"), fallback=summary)
        if reasoning:
            sanitized_decision["reasoning"] = reasoning[:400]
        decision_summary = sanitize_text_block(decision.get("summary"))
        if decision_summary:
            sanitized_decision["summary"] = decision_summary[:240]
        risk_warning = sanitize_text_block(decision.get("risk_warning"))
        if risk_warning:
            sanitized_decision["risk_warning"] = risk_warning[:200]
        for field_name in ("core_evidence", "uncertainties", "invalidation_conditions", "watch_items"):
            cleaned_items = sanitize_brief_points(decision.get(field_name))
            if cleaned_items:
                sanitized_decision[field_name] = cleaned_items
        sanitized["decision"] = sanitized_decision

    recommendation_parts: List[str] = []
    if normalized_action:
        recommendation_parts.append(f"研究判断：{normalized_action}")
    if summary:
        recommendation_parts.append(summary[:120])
    recommendation_parts.append("请结合详细报告继续关注证据变化、风险因素与后续披露。")
    sanitized["recommendation"] = "；".join(part for part in recommendation_parts if part)[:240] or GENERIC_RESEARCH_RECOMMENDATION

    return sanitized


def sanitize_position_analysis_payload(result_data: Dict[str, Any]) -> Dict[str, Any]:
    if not isinstance(result_data, dict) or not result_data:
        return result_data

    sanitized = dict(result_data)
    summary = sanitize_text_block(
        sanitized.get("summary") or sanitized.get("action_reason") or sanitized.get("detailed_analysis"),
        fallback="该持仓研究已转换为研究观察，请结合自身策略独立判断。",
    )

    sanitized["action"] = "hold"
    sanitized["action_reason"] = sanitize_text_block(
        sanitized.get("action_reason"),
        fallback="该结果仅保留研究观察与风险提示，不提供执行性交易建议。",
    )
    sanitized["price_targets"] = {}
    sanitized["suggested_quantity"] = None
    sanitized["suggested_amount"] = None
    sanitized["risk_assessment"] = sanitize_text_block(
        sanitized.get("risk_assessment"),
        fallback="请重点关注持仓波动、行业变化和公告风险。",
    )
    sanitized["opportunity_assessment"] = sanitize_text_block(
        sanitized.get("opportunity_assessment"),
        fallback="请持续跟踪经营质量、估值变化和潜在催化事件。",
    )
    sanitized["detailed_analysis"] = sanitize_text_block(
        sanitized.get("detailed_analysis"),
        fallback=summary,
    )
    sanitized["summary"] = summary
    sanitized["recommendation"] = GENERIC_POSITION_RECOMMENDATION

    confidence = sanitized.get("confidence")
    if isinstance(confidence, (int, float)):
        sanitized["confidence"] = max(0.0, min(100.0, float(confidence)))

    return sanitized


def sanitize_trade_review_payload(result_data: Dict[str, Any]) -> Dict[str, Any]:
    if not isinstance(result_data, dict) or not result_data:
        return result_data

    sanitized = dict(result_data)
    sanitized["summary"] = sanitize_review_text_block(
        sanitized.get("summary"),
        fallback=GENERIC_REVIEW_SUMMARY,
    )
    sanitized["strengths"] = sanitize_review_points(sanitized.get("strengths"))
    sanitized["weaknesses"] = sanitize_review_points(sanitized.get("weaknesses"))
    sanitized["suggestions"] = sanitize_review_points(
        sanitized.get("suggestions"),
        fallback=GENERIC_REVIEW_IMPROVEMENTS,
    )
    sanitized["timing_analysis"] = sanitize_review_text_block(
        sanitized.get("timing_analysis"),
        fallback="请重点复盘入场与退出依据是否充分，而非给出新的买卖指令。",
    )
    sanitized["position_analysis"] = sanitize_review_text_block(
        sanitized.get("position_analysis"),
        fallback="请重点复盘仓位管理依据与风险暴露，不提供具体仓位调整方案。",
    )
    sanitized["emotion_analysis"] = sanitize_review_text_block(
        sanitized.get("emotion_analysis"),
        fallback="请重点复盘情绪控制与纪律执行问题。",
    )
    sanitized["attribution_analysis"] = sanitize_review_text_block(
        sanitized.get("attribution_analysis"),
        fallback="请重点复盘收益与亏损来源的证据归因。",
    )
    sanitized["plan_adherence"] = sanitize_review_text_block(sanitized.get("plan_adherence"))
    sanitized["plan_deviation"] = sanitize_review_text_block(sanitized.get("plan_deviation"))

    return sanitized


def sanitize_periodic_review_payload(result_data: Dict[str, Any]) -> Dict[str, Any]:
    if not isinstance(result_data, dict) or not result_data:
        return result_data

    sanitized = dict(result_data)
    sanitized["summary"] = sanitize_review_text_block(
        sanitized.get("summary"),
        fallback=GENERIC_REVIEW_SUMMARY,
    )
    sanitized["trading_style"] = sanitize_review_text_block(
        sanitized.get("trading_style"),
        fallback="请从风格稳定性、纪律执行与研究准备充分性角度进行阶段性复盘。",
    )
    sanitized["common_mistakes"] = sanitize_review_points(sanitized.get("common_mistakes"))
    sanitized["improvement_areas"] = sanitize_review_points(
        sanitized.get("improvement_areas"),
        fallback=GENERIC_REVIEW_IMPROVEMENTS,
    )
    sanitized["action_plan"] = sanitize_review_points(
        sanitized.get("action_plan"),
        fallback=GENERIC_REVIEW_IMPROVEMENTS,
    )
    sanitized["best_trade"] = sanitize_review_text_block(sanitized.get("best_trade"))
    sanitized["worst_trade"] = sanitize_review_text_block(sanitized.get("worst_trade"))

    return sanitized