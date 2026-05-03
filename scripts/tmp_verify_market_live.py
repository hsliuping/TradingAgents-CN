#!/usr/bin/env python

import json
import os
import sys
import traceback
from datetime import datetime


ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)


REQUIRED_SECTIONS = [
    "股票基本信息",
    "技术指标分析",
    "移动平均线",
    "MACD",
    "RSI",
    "布林带",
    "价格趋势分析",
    "短期趋势",
    "中期趋势",
    "成交量分析",
    "综合评估",
    "对整体研究结论的影响",
    "后续观察点",
]

BANNED_TERMS = [
    "目标价",
    "价格区间",
    "支撑位",
    "阻力位",
    "关键价位",
    "风险控制位",
    "仓位",
    "执行计划",
]


def build_state() -> dict:
    ticker = os.environ.get("MARKET_VERIFY_TICKER", "600519")
    analysis_date = os.environ.get("MARKET_VERIFY_DATE", "2026-04-10")
    company_name = os.environ.get("MARKET_VERIFY_NAME", "贵州茅台")
    return {
        "ticker": ticker,
        "company_of_interest": ticker,
        "analysis_date": analysis_date,
        "trade_date": analysis_date,
        "current_date": analysis_date,
        "company_name": company_name,
        "market_type": "A股",
        "market_name": "中国A股",
        "currency_name": "人民币",
        "currency_symbol": "¥",
    }


def build_provider_config() -> dict:
    quick_model = os.environ.get("MARKET_TEST_LLM_MODEL") or os.environ.get("TEST_LLM_MODEL") or "qwen-plus"
    deep_model = os.environ.get("MARKET_TEST_DEEP_LLM_MODEL") or quick_model
    return {
        "quick_think_llm": quick_model,
        "deep_think_llm": deep_model,
    }


def ensure_output_dir() -> str:
    output_dir = os.path.join(ROOT, "logs", "tmp_live_checks")
    os.makedirs(output_dir, exist_ok=True)
    return output_dir


def write_text(path: str, content: str) -> None:
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(content)


def main() -> int:
    try:
        from core.agents import create_agent_with_dynamic_tools
        from core.workflow.builder import LegacyDependencyProvider

        state = build_state()
        output_dir = ensure_output_dir()
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        basename = f"market_live_{state['ticker']}_{state['analysis_date']}_{ts}"

        print("=" * 80)
        print("market_analyst_v2 真实链路验证")
        print("=" * 80)
        print(f"ticker={state['ticker']}")
        print(f"company_name={state['company_name']}")
        print(f"analysis_date={state['analysis_date']}")
        provider_config = build_provider_config()
        print(f"provider_config={provider_config}")

        provider = LegacyDependencyProvider(provider_config or None)
        llm = provider.get_llm("quick")
        agent = create_agent_with_dynamic_tools("market_analyst_v2", llm)

        print(f"llm={type(llm).__name__}")
        print(f"loaded_tools={agent.tool_names}")

        system_prompt = agent._build_system_prompt(state.get("market_type"), state=state)
        user_prompt = agent._build_user_prompt(state["ticker"], state["analysis_date"], state)
        analysis_prompt = agent._build_analysis_prompt(state["ticker"])

        prompt_payload = {
            "state": state,
            "system_prompt": system_prompt,
            "user_prompt": user_prompt,
            "analysis_prompt": analysis_prompt,
            "tool_names": agent.tool_names,
        }
        prompt_path = os.path.join(output_dir, f"{basename}_prompts.json")
        write_text(prompt_path, json.dumps(prompt_payload, ensure_ascii=False, indent=2))
        print(f"prompt_dump={prompt_path}")

        result = agent.execute(state)
        report = result.get("market_report", "")
        report_path = os.path.join(output_dir, f"{basename}_report.txt")
        write_text(report_path, report)
        print(f"report_dump={report_path}")
        print(f"report_length={len(report)}")

        missing_sections = [section for section in REQUIRED_SECTIONS if section not in report]
        banned_hits = [term for term in BANNED_TERMS if term in report]

        print("required_sections_missing=" + json.dumps(missing_sections, ensure_ascii=False))
        print("banned_term_hits=" + json.dumps(banned_hits, ensure_ascii=False))
        print("report_preview_start")
        print(report[:4000])
        print("report_preview_end")

        if report.startswith("执行失败:"):
            print("status=FAILED_AGENT_EXECUTION")
            return 1

        if not report.strip():
            print("status=EMPTY_REPORT")
            return 1

        print("status=OK")
        return 0
    except Exception as exc:
        print(f"status=EXCEPTION: {exc}")
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    raise SystemExit(main())