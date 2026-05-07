"""抽查 research_manager_v2 / trader_v2 / risk_manager_v2 的 live 提示词是否按新口径生效。"""

from __future__ import annotations

import re
import sys
from pathlib import Path

from dotenv import load_dotenv
from pymongo import MongoClient


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))
load_dotenv(PROJECT_ROOT / ".env", override=False)

_builder_path = PROJECT_ROOT / "scripts" / "template_upgrades"
sys.path.insert(0, str(_builder_path))

from tradingagents.config.mongodb_utils import build_mongodb_connection_string, get_mongodb_database_name
from update_research_brief_v2_prompts import PREFERENCE_CONFIG, get_template_name


SAMPLE_COMMON = {
    "ticker": "AAPL",
    "company_name": "苹果公司",
    "analysis_date": "2026-04-13",
    "current_date": "2026-04-13",
    "current_price": "123.45",
    "currency_name": "美元",
    "currency_symbol": "$",
    "market_name": "美股",
    "industry": "消费电子",
}

SAMPLE_RESEARCH_PLAN = (
    "当前研究结论偏中性偏积极：核心支撑来自现金流韧性与产品周期，"
    "但需求修复节奏和估值消化仍待继续验证。"
)


def query_live_docs() -> dict[tuple[str, str], dict]:
    client = MongoClient(build_mongodb_connection_string())
    db = client[get_mongodb_database_name()]
    collection = db.prompt_templates
    docs: dict[tuple[str, str], dict] = {}

    for agent_name in ("research_manager_v2", "trader_v2", "risk_manager_v2"):
        found_docs = list(collection.find({"agent_name": agent_name, "status": "active"}))
        for doc in found_docs:
            key = (agent_name, doc.get("preference_type", ""))
            docs[key] = doc

    client.close()
    return docs


def get_nested_value(data: dict, path: str):
    value = data
    for key in path.split("."):
        if isinstance(value, dict):
            value = value.get(key, "")
        else:
            return ""
    return value


def render_text(template: str, variables: dict) -> str:
    double_brace_pattern = re.compile(r"\{\{([^}]+)\}\}")
    single_brace_pattern = re.compile(r"\{([a-zA-Z_][a-zA-Z0-9_]*)\}")

    def replace_double(match):
        var_path = match.group(1).strip()
        val = get_nested_value(variables, var_path)
        return str(val) if val is not None else ""

    def replace_single(match):
        var_name = match.group(1).strip()
        val = variables.get(var_name)
        return str(val) if val is not None else ""

    rendered = double_brace_pattern.sub(replace_double, template)
    rendered = single_brace_pattern.sub(replace_single, rendered)
    return rendered


def render_user_prompt(doc: dict, variables: dict) -> str:
    content = doc.get("content") or {}
    return render_text(content.get("user_prompt", ""), variables)


def render_system_prompt(doc: dict, variables: dict) -> str:
    content = doc.get("content") or {}
    parts = []
    for key in ("system_prompt", "tool_guidance", "analysis_requirements", "output_format", "constraints"):
        value = content.get(key)
        if isinstance(value, str) and value:
            parts.append(render_text(value, variables))
    return "\n\n".join(parts)


def assert_no_unrendered_placeholders(text: str, label: str) -> None:
    if "{{" in text or "}}" in text:
        raise AssertionError(f"{label} 仍存在双大括号占位符")


def verify_research_manager(doc: dict, preference: str) -> list[str]:
    variables = {
        **SAMPLE_COMMON,
        "bull_report": "看涨观点：盈利质量稳定，回购与服务收入构成支撑。",
        "bear_report": "看跌观点：需求修复节奏不确定，估值对增长延续有较高要求。",
        "debate_summary": "共识在于基本面质量较强，分歧在于增长弹性与估值匹配度。",
    }
    user_prompt = render_user_prompt(doc, variables)
    system_prompt = render_system_prompt(doc, variables)

    assert_no_unrendered_placeholders(user_prompt, f"research_manager_v2/{preference} user_prompt")
    assert_no_unrendered_placeholders(system_prompt, f"research_manager_v2/{preference} system_prompt")

    checks = []
    if "可用资源：" not in user_prompt:
        raise AssertionError(f"research_manager_v2/{preference} user_prompt 未出现可用资源结构")
    checks.append("user_prompt 含可用资源")

    if "材料未提供" not in user_prompt or "材料未提供" not in system_prompt:
        raise AssertionError(f"research_manager_v2/{preference} 未包含缺失材料处理约束")
    checks.append("含缺失材料约束")

    if "¥123.45" in user_prompt or "¥" in user_prompt:
        raise AssertionError(f"research_manager_v2/{preference} user_prompt 仍存在人民币硬编码")
    checks.append("无人民币硬编码")

    if "投资机会" in user_prompt:
        raise AssertionError(f"research_manager_v2/{preference} user_prompt 仍保留旧投资机会措辞")
    checks.append("已移除旧投资机会措辞")

    return checks


def verify_trader(doc: dict, preference: str) -> list[str]:
    variables = {
        **SAMPLE_COMMON,
        "investment_plan": SAMPLE_RESEARCH_PLAN,
        "market_report": "市场报告：短期波动收敛，但趋势确认仍依赖量价配合。",
        "fundamentals_report": "基本面报告：毛利率稳定，资本开支可控。",
        "news_report": "新闻报告：新品发布节奏明确，但供应链扰动仍需观察。",
        "sentiment_report": "情绪报告：讨论热度偏积极，但平台分化明显。",
        "report_sector_report": "板块报告：消费电子景气边际改善。",
        "report_index_report": "大盘报告：指数震荡，风险偏好未形成单边扩张。",
        "report_bull_report": "看涨研究：服务收入与回购构成底层支撑。",
        "report_bear_report": "看跌研究：估值与需求修复节奏存在错配风险。",
        "historical_trades": "2026-03-01 买入观察仓；2026-03-20 继续跟踪财报前指引。",
    }
    user_prompt = render_user_prompt(doc, variables)
    system_prompt = render_system_prompt(doc, variables)

    assert_no_unrendered_placeholders(user_prompt, f"trader_v2/{preference} user_prompt")
    assert_no_unrendered_placeholders(system_prompt, f"trader_v2/{preference} system_prompt")

    checks = []
    if "可用资源：" not in user_prompt:
        raise AssertionError(f"trader_v2/{preference} user_prompt 未出现可用资源结构")
    checks.append("user_prompt 含可用资源")

    if "情绪分析报告：情绪报告：讨论热度偏积极，但平台分化明显。" not in user_prompt:
        raise AssertionError(f"trader_v2/{preference} user_prompt 未消费 sentiment_report")
    checks.append("已消费 sentiment_report")

    if "材料未提供" not in user_prompt or "材料未提供" not in system_prompt:
        raise AssertionError(f"trader_v2/{preference} 未包含缺失材料处理约束")
    checks.append("含缺失材料约束")

    if (
        "价格触发后的执行动作" not in user_prompt
        and "达到某价位后执行什么动作" not in user_prompt
        and "执行策略" not in user_prompt
    ):
        raise AssertionError(f"trader_v2/{preference} 未保留非交易化约束")
    checks.append("保留非交易化约束")

    return checks


def verify_risk_manager(doc: dict, preference: str) -> list[str]:
    variables = {
        **SAMPLE_COMMON,
        "investment_plan": SAMPLE_RESEARCH_PLAN,
        "risky_opinion": "激进风险观点：若新品周期超预期，当前中性判断可能低估弹性。",
        "safe_opinion": "保守风险观点：需求验证不足，估值对增长延续过于敏感。",
        "neutral_opinion": "中性风险观点：经营质量尚可，但短期驱动与估值约束并存。",
        "debate_summary": "共识在于质量较稳，分歧集中在增长弹性、估值压力和验证节奏。",
    }
    user_prompt = render_user_prompt(doc, variables)
    system_prompt = render_system_prompt(doc, variables)

    assert_no_unrendered_placeholders(user_prompt, f"risk_manager_v2/{preference} user_prompt")
    assert_no_unrendered_placeholders(system_prompt, f"risk_manager_v2/{preference} system_prompt")

    checks = []
    if "可用资源：" not in user_prompt:
        raise AssertionError(f"risk_manager_v2/{preference} user_prompt 未出现可用资源结构")
    checks.append("user_prompt 含可用资源")

    if "$123.45" not in user_prompt:
        raise AssertionError(f"risk_manager_v2/{preference} user_prompt 未使用传入货币符号")
    checks.append("使用传入货币符号")

    if "¥123.45" in user_prompt or "¥" in user_prompt:
        raise AssertionError(f"risk_manager_v2/{preference} user_prompt 仍存在人民币硬编码")
    checks.append("无人民币硬编码")

    if "材料未提供" not in user_prompt or "材料未提供" not in system_prompt:
        raise AssertionError(f"risk_manager_v2/{preference} 未包含缺失材料处理约束")
    checks.append("含缺失材料约束")

    return checks


def main() -> int:
    live_docs = query_live_docs()
    print("=== Live Prompt Chain Verification ===")

    failures: list[str] = []
    for preference in PREFERENCE_CONFIG:
        print(f"\n[{preference}]")

        expected_versions = {
            ("research_manager_v2", preference): 9,
            ("trader_v2", preference): 9,
            ("risk_manager_v2", preference): 9,
        }
        for key, expected_version in expected_versions.items():
            doc = live_docs.get(key)
            actual_version = int((doc or {}).get("version") or 0)
            expected_template_name = get_template_name(key[0], preference)
            actual_template_name = (doc or {}).get("template_name")
            if actual_version != expected_version:
                failures.append(f"{key[0]}/{preference} version={actual_version}, expected={expected_version}")
            elif actual_template_name != expected_template_name:
                failures.append(
                    f"{key[0]}/{preference} template_name={actual_template_name}, expected={expected_template_name}"
                )
            else:
                print(f"  - {key[0]} version={actual_version}")

        research_doc = live_docs.get(("research_manager_v2", preference))
        trader_doc = live_docs.get(("trader_v2", preference))
        risk_doc = live_docs.get(("risk_manager_v2", preference))

        try:
            if research_doc is None:
                raise AssertionError(f"research_manager_v2/{preference} 未找到 live 模板")
            research_checks = verify_research_manager(research_doc, preference)
            print(f"  - research_manager_v2: {'; '.join(research_checks)}")
        except Exception as exc:
            failures.append(str(exc))

        try:
            if trader_doc is None:
                raise AssertionError(f"trader_v2/{preference} 未找到 live 模板")
            trader_checks = verify_trader(trader_doc, preference)
            print(f"  - trader_v2: {'; '.join(trader_checks)}")
        except Exception as exc:
            failures.append(str(exc))

        try:
            if risk_doc is None:
                raise AssertionError(f"risk_manager_v2/{preference} 未找到 live 模板")
            risk_checks = verify_risk_manager(risk_doc, preference)
            print(f"  - risk_manager_v2: {'; '.join(risk_checks)}")
        except Exception as exc:
            failures.append(str(exc))

    if failures:
        print("\n=== FAILURES ===")
        for failure in failures:
            print(f"- {failure}")
        return 1

    print("\n全部校验通过：research_manager_v2 -> trader_v2 -> risk_manager_v2 live 提示词链路已按新口径生效。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())