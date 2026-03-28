"""
报告语言规范化工具

用于在中文偏好下，将报告正文中的原始英文 key、英文小标题和不自然的阶段标题
统一转换为更适合中文阅读的标题。
"""

from __future__ import annotations

import re
from typing import Dict, Optional


REPORT_SECTION_TITLES: Dict[str, Dict[str, str]] = {
    "zh-CN": {
        "market_report": "市场技术分析",
        "sentiment_report": "市场情绪分析",
        "news_report": "新闻事件分析",
        "fundamentals_report": "基本面分析",
        "bull_researcher": "多头研究观点",
        "bear_researcher": "空头研究观点",
        "research_team_decision": "研究经理综合决策",
        "trader_investment_plan": "交易员执行计划",
        "risky_analyst": "激进风险评估",
        "safe_analyst": "保守风险评估",
        "neutral_analyst": "中性风险评估",
        "risk_management_decision": "风险管理决策",
        "final_trade_decision": "最终交易决策",
        "investment_plan": "投资建议",
        "investment_debate_state": "研究团队讨论",
        "risk_debate_state": "风险管理团队讨论",
    },
    "en-US": {
        "market_report": "Market Analysis",
        "sentiment_report": "Sentiment Analysis",
        "news_report": "News Analysis",
        "fundamentals_report": "Fundamentals Analysis",
        "bull_researcher": "Bull Case",
        "bear_researcher": "Bear Case",
        "research_team_decision": "Research Manager Decision",
        "trader_investment_plan": "Trader Plan",
        "risky_analyst": "Aggressive Risk Review",
        "safe_analyst": "Conservative Risk Review",
        "neutral_analyst": "Neutral Risk Review",
        "risk_management_decision": "Risk Management Decision",
        "final_trade_decision": "Final Trade Decision",
        "investment_plan": "Investment Plan",
        "investment_debate_state": "Research Debate",
        "risk_debate_state": "Risk Debate",
    },
}


SECTION_ALIASES: Dict[str, tuple[str, ...]] = {
    "market_report": ("market_report", "market report"),
    "sentiment_report": ("sentiment_report", "sentiment report"),
    "news_report": ("news_report", "news report"),
    "fundamentals_report": ("fundamentals_report", "fundamentals report"),
    "bull_researcher": ("bull_researcher", "bull researcher", "bull case"),
    "bear_researcher": ("bear_researcher", "bear researcher", "bear case"),
    "research_team_decision": ("research_team_decision", "research manager", "research manager decision"),
    "trader_investment_plan": ("trader_investment_plan", "trader investment plan", "trader plan"),
    "risky_analyst": ("risky_analyst", "aggressive analyst", "risky analyst", "aggressive risk assessment"),
    "safe_analyst": ("safe_analyst", "conservative analyst", "safe analyst", "conservative risk assessment"),
    "neutral_analyst": ("neutral_analyst", "neutral analyst", "neutral risk assessment"),
    "risk_management_decision": ("risk_management_decision", "risk judge", "risk management decision"),
    "final_trade_decision": ("final_trade_decision", "final trade decision"),
}


RISK_ENUMERATION_REPLACEMENTS = {
    r"^\s*[0-9一二三]+[\)\.、：:\-）]\s*(aggressive(?:\s+analyst|\s+risk\s+assessment)?|risky(?:\s+analyst)?)\s*$": "### 激进风险评估",
    r"^\s*[0-9一二三]+[\)\.、：:\-）]\s*(conservative(?:\s+analyst|\s+risk\s+assessment)?|safe(?:\s+analyst)?)\s*$": "### 保守风险评估",
    r"^\s*[0-9一二三]+[\)\.、：:\-）]\s*(neutral(?:\s+analyst|\s+risk\s+assessment)?)\s*$": "### 中性风险评估",
}


def get_report_section_title(report_key: str, language: Optional[str] = "zh-CN") -> str:
    lang = "zh-CN" if (language or "zh-CN").startswith("zh") else "en-US"
    return REPORT_SECTION_TITLES.get(lang, {}).get(report_key, report_key.replace("_", " "))


def _replace_heading_aliases(content: str, language: str) -> str:
    normalized = content
    for report_key, aliases in SECTION_ALIASES.items():
        title = get_report_section_title(report_key, language)
        for alias in aliases:
            pattern = r"^(#{1,6}\s*)?" + re.escape(alias) + r"\s*$"
            normalized = re.sub(pattern, f"## {title}", normalized, flags=re.IGNORECASE | re.MULTILINE)
    return normalized


def normalize_report_markdown(
    content: str,
    report_key: Optional[str] = None,
    language: Optional[str] = "zh-CN",
) -> str:
    if not isinstance(content, str):
        return content

    lang = "zh-CN" if (language or "zh-CN").startswith("zh") else "en-US"
    normalized = content.replace("\r\n", "\n").strip()
    if not normalized:
        return normalized

    normalized = _replace_heading_aliases(normalized, lang)

    if lang == "zh-CN":
        for pattern, replacement in RISK_ENUMERATION_REPLACEMENTS.items():
            normalized = re.sub(pattern, replacement, normalized, flags=re.IGNORECASE | re.MULTILINE)

    if report_key:
        title = get_report_section_title(report_key, lang)
        first_non_empty = next((line.strip() for line in normalized.splitlines() if line.strip()), "")
        if not re.match(r"^#{1,6}\s+", first_non_empty):
            normalized = f"## {title}\n\n{normalized}"
        elif first_non_empty.lower() in {report_key.lower(), title.lower()}:
            normalized = re.sub(
                r"^#{1,6}\s+.*$",
                f"## {title}",
                normalized,
                count=1,
                flags=re.MULTILINE,
            )
        duplicate_heading_pattern = (
            r"^(##\s+" + re.escape(title) + r"\s*\n+)(###\s+" + re.escape(title) + r"\s*\n+)"
        )
        normalized = re.sub(duplicate_heading_pattern, r"\1", normalized, flags=re.MULTILINE)

    return normalized


def normalize_reports_dict(
    reports: Dict[str, str],
    language: Optional[str] = "zh-CN",
) -> Dict[str, str]:
    normalized_reports: Dict[str, str] = {}
    for report_key, content in (reports or {}).items():
        normalized_reports[report_key] = normalize_report_markdown(content, report_key, language)
    return normalized_reports
