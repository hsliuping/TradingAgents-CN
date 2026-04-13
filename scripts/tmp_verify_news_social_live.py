#!/usr/bin/env python

import json
import os
import sys
import traceback
from datetime import datetime


ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)


COMMON_BANNED_TERMS = [
    "目标价",
    "价格区间",
    "支撑位",
    "阻力位",
    "关键价位",
    "仓位",
    "执行计划",
    "买入建议",
    "卖出建议",
]

AGENT_SPECS = [
    {
        "agent_id": "news_analyst_v2",
        "output_field": "news_report",
        "required_sections": [
            "最新新闻汇总",
            "新闻影响分析",
            "市场情绪评估",
            "分析观点",
        ],
    },
    {
        "agent_id": "social_analyst_v2",
        "output_field": "sentiment_report",
        "required_sections": [
            "情绪方向与热度",
            "观点结构与渠道差异",
            "情绪变化与分化",
            "噪音与风险",
            "对整体研究结论的影响",
            "后续观察事项",
        ],
    },
]


def build_state() -> dict:
    ticker = os.environ.get("NEWS_SOCIAL_VERIFY_TICKER", "600519")
    analysis_date = os.environ.get("NEWS_SOCIAL_VERIFY_DATE", "2026-04-13")
    company_name = os.environ.get("NEWS_SOCIAL_VERIFY_NAME", "贵州茅台")
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
    quick_model = os.environ.get("NEWS_SOCIAL_TEST_LLM_MODEL") or os.environ.get("TEST_LLM_MODEL") or "qwen-plus"
    deep_model = os.environ.get("NEWS_SOCIAL_TEST_DEEP_LLM_MODEL") or quick_model
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


def write_json(path: str, payload: dict) -> None:
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)


def run_agent_check(agent_spec: dict, provider, state: dict, output_dir: str, ts: str) -> dict:
    from core.agents import create_agent_with_dynamic_tools

    llm = provider.get_llm("quick")
    agent = create_agent_with_dynamic_tools(agent_spec["agent_id"], llm)

    basename = f"{agent_spec['agent_id']}_{state['ticker']}_{state['analysis_date']}_{ts}"
    prompt_payload = {
        "state": state,
        "agent_id": agent_spec["agent_id"],
        "tool_names": agent.tool_names,
        "system_prompt": agent._build_system_prompt(state.get("market_type"), state=state),
        "user_prompt": agent._build_user_prompt(state["ticker"], state["analysis_date"], {}, state),
        "analysis_prompt": agent._build_analysis_prompt(state["ticker"]),
    }

    prompt_path = os.path.join(output_dir, f"{basename}_prompts.json")
    write_json(prompt_path, prompt_payload)

    result = agent.execute(state)
    report = str(result.get(agent_spec["output_field"], "") or "")
    report_path = os.path.join(output_dir, f"{basename}_report.txt")
    write_text(report_path, report)

    missing_sections = [section for section in agent_spec["required_sections"] if section not in report]
    banned_hits = [term for term in COMMON_BANNED_TERMS if term in report]

    status = "OK"
    if report.startswith("执行失败:"):
        status = "FAILED_AGENT_EXECUTION"
    elif not report.strip():
        status = "EMPTY_REPORT"
    elif missing_sections or banned_hits:
        status = "CONTENT_VALIDATION_FAILED"

    return {
        "agent_id": agent_spec["agent_id"],
        "tool_names": agent.tool_names,
        "prompt_path": prompt_path,
        "report_path": report_path,
        "report_length": len(report),
        "missing_sections": missing_sections,
        "banned_hits": banned_hits,
        "status": status,
        "report_preview": report[:4000],
    }


def main() -> int:
    try:
        from core.workflow.builder import LegacyDependencyProvider

        state = build_state()
        output_dir = ensure_output_dir()
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        provider_config = build_provider_config()

        print("=" * 80)
        print("news/social analyst v2 真实链路验证")
        print("=" * 80)
        print(f"ticker={state['ticker']}")
        print(f"company_name={state['company_name']}")
        print(f"analysis_date={state['analysis_date']}")
        print(f"provider_config={provider_config}")

        provider = LegacyDependencyProvider(provider_config or None)
        results = []
        exit_code = 0

        for agent_spec in AGENT_SPECS:
            print("-" * 80)
            print(f"running={agent_spec['agent_id']}")
            check_result = run_agent_check(agent_spec, provider, state, output_dir, ts)
            results.append(check_result)

            print(f"tool_names={check_result['tool_names']}")
            print(f"prompt_dump={check_result['prompt_path']}")
            print(f"report_dump={check_result['report_path']}")
            print(f"report_length={check_result['report_length']}")
            print("missing_sections=" + json.dumps(check_result["missing_sections"], ensure_ascii=False))
            print("banned_term_hits=" + json.dumps(check_result["banned_hits"], ensure_ascii=False))
            print(f"status={check_result['status']}")
            print("report_preview_start")
            print(check_result["report_preview"])
            print("report_preview_end")

            if check_result["status"] != "OK":
                exit_code = 1

        summary_path = os.path.join(
            output_dir,
            f"news_social_live_summary_{state['ticker']}_{state['analysis_date']}_{ts}.json",
        )
        write_json(summary_path, {"state": state, "results": results})
        print(f"summary_dump={summary_path}")
        print(f"final_status={'OK' if exit_code == 0 else 'FAILED'}")
        return exit_code
    except Exception as exc:
        print(f"final_status=EXCEPTION: {exc}")
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    raise SystemExit(main())