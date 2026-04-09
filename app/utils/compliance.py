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
GENERIC_POSITION_RECOMMENDATION = "该持仓分析仅提供研究观察与风险提示，请结合自身策略独立判断。"

_ACTIONABLE_PATTERNS = [
    re.compile(pattern, re.IGNORECASE)
    for pattern in (
        r"买入|卖出|持有|加仓|减仓|清仓|建仓|平仓|调仓",
        r"止损|止盈|仓位|目标价|目标价格|目标区间|价格分析区间|参考价格",
        r"投资建议|交易建议|操作建议|一键模拟下单|下单|模拟交易",
        r"BUY|SELL|HOLD|STRONG_BUY|STRONG_SELL",
        r"target_price|stop_loss|take_profit|position_ratio|suggested_quantity|suggested_amount",
    )
]
_JSON_FIELD_PATTERN = re.compile(r'^[\[\]{}":,0-9._%\-\s]+$')
_SENTENCE_SPLIT_PATTERN = re.compile(r"[\n。！？；]+")


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


def _plain_text(text: str) -> str:
    normalized = re.sub(r"```.*?```", " ", text, flags=re.DOTALL)
    normalized = re.sub(r"`+", "", normalized)
    normalized = normalized.replace("#", " ").replace("*", " ")
    return re.sub(r"\s+", " ", normalized).strip()


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
        lines.append(line)

    deduped: List[str] = []
    for line in lines:
        if line not in deduped:
            deduped.append(line)

    if not deduped:
        return fallback
    return "\n".join(deduped[:6])[:1500]


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
                if sentence and not contains_actionable_content(sentence):
                    yield sentence

    for key in SAFE_REPORT_KEYS:
        content = sanitize_text_block(reports.get(key, ""))
        if not content:
            continue
        for fragment in _SENTENCE_SPLIT_PATTERN.split(content):
            sentence = fragment.strip()
            if sentence and not contains_actionable_content(sentence):
                yield sentence


def build_research_summary(reports: Dict[str, str], fallback_summary: str = "") -> str:
    summary_parts: List[str] = []
    for fragment in _iter_safe_fragments(reports, fallback_summary):
        if fragment not in summary_parts:
            summary_parts.append(fragment)
        if len(summary_parts) >= 3:
            break

    if summary_parts:
        return "；".join(summary_parts)[:800]

    return "本次结果已按研究辅助模式输出，请重点关注基础数据、风险因素与后续披露信息。"


def build_key_points(reports: Dict[str, str], key_points: Any, summary: str) -> List[str]:
    cleaned_points: List[str] = []
    if isinstance(key_points, list):
        for item in key_points:
            point = sanitize_text_block(item)
            if point and point not in cleaned_points:
                cleaned_points.append(point)

    if len(cleaned_points) >= 3:
        return cleaned_points[:5]

    for fragment in _iter_safe_fragments(reports, summary):
        if fragment not in cleaned_points:
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
    sanitized["recommendation"] = GENERIC_RESEARCH_RECOMMENDATION
    sanitized["key_points"] = build_key_points(reports, sanitized.get("key_points"), summary)

    decision = sanitized.get("decision")
    if isinstance(decision, dict):
        sanitized_decision: Dict[str, Any] = {}
        confidence = decision.get("confidence")
        if isinstance(confidence, (int, float)):
            sanitized_decision["confidence"] = confidence / 100 if confidence > 1 else confidence
        risk_score = decision.get("risk_score")
        if isinstance(risk_score, (int, float)):
            sanitized_decision["risk_score"] = risk_score / 100 if risk_score > 1 else risk_score
        reasoning = sanitize_text_block(decision.get("reasoning"), fallback=summary)
        if reasoning:
            sanitized_decision["reasoning"] = reasoning[:400]
        sanitized["decision"] = sanitized_decision

    return sanitized


def sanitize_position_analysis_payload(result_data: Dict[str, Any]) -> Dict[str, Any]:
    if not isinstance(result_data, dict) or not result_data:
        return result_data

    sanitized = dict(result_data)
    summary = sanitize_text_block(
        sanitized.get("summary") or sanitized.get("action_reason") or sanitized.get("detailed_analysis"),
        fallback="该持仓分析已转换为研究观察，请结合自身策略独立判断。",
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