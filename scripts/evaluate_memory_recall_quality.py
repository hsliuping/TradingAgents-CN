"""Evaluate L5/L6 recall quality with controlled synthetic scenarios."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Dict, List


ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from core.memory.models import MemoryItem
from core.memory.service import (
    _dedupe_recalled_items,
    _format_recalled_items,
    _sort_recalled_items,
)


def _assistant_scenario() -> Dict[str, Any]:
    return {
        "name": "assistant_profile_prefers_preferences_and_dedupes_conversation",
        "ranking_profile": "assistant",
        "metadata_filters": None,
        "group_by_scope": True,
        "per_scope_limit": 2,
        "items": [
            MemoryItem(id="a1", memory="你偏好先看基本面，再看估值。", scope="user_preference", score=0.58),
            MemoryItem(id="a2", memory="今天先看看白酒板块。", scope="conversation", score=0.96),
            MemoryItem(id="a3", memory="今天先看看白酒板块", scope="conversation", score=0.94),
            MemoryItem(id="a4", memory="历史分析显示白酒估值切换需要业绩验证。", scope="analysis_insight", score=0.88),
        ],
        "expect": {
            "first_scope": "user_preference",
            "deduped_count": 3,
            "contains_headers": ["【历史偏好】", "【历史分析】", "【历史对话】"],
        },
    }


def _analysis_scenario() -> Dict[str, Any]:
    return {
        "name": "analysis_profile_prefers_symbol_matched_insight_over_generic_preference",
        "ranking_profile": "analysis",
        "metadata_filters": {"symbol": "600519"},
        "group_by_scope": True,
        "per_scope_limit": 2,
        "items": [
            MemoryItem(
                id="b1",
                memory="贵州茅台历史分析：估值消化后再跟踪。",
                scope="analysis_insight",
                score=0.82,
                metadata={"symbol": "600519"},
            ),
            MemoryItem(
                id="b2",
                memory="研究经理历史经验：先确认提价持续性。",
                scope="agent_experience",
                score=0.81,
                metadata={"symbol": "600519"},
            ),
            MemoryItem(
                id="b3",
                memory="你偏好低回撤策略。",
                scope="user_preference",
                score=0.95,
            ),
        ],
        "expect": {
            "first_scope": "analysis_insight",
            "deduped_count": 3,
            "contains_headers": ["【历史分析】", "【历史经验】", "【历史偏好】"],
        },
    }


def _skill_generation_scenario() -> Dict[str, Any]:
    return {
        "name": "skill_generation_profile_prefers_exact_lesson_matches",
        "ranking_profile": "skill_generation",
        "metadata_filters": {"category": "news", "data_source": "eastmoney"},
        "group_by_scope": True,
        "per_scope_limit": 3,
        "items": [
            MemoryItem(
                id="c1",
                memory="Skill lesson: 东方财富新闻工具要统一输出 publish_time/source 字段。",
                scope="skill_lesson",
                score=0.76,
                metadata={"category": "news", "data_source": "eastmoney"},
            ),
            MemoryItem(
                id="c2",
                memory="Skill lesson: 东方财富新闻工具要统一输出 publish_time/source 字段",
                scope="skill_lesson",
                score=0.75,
                metadata={"category": "news", "data_source": "eastmoney"},
            ),
            MemoryItem(
                id="c3",
                memory="Skill lesson: 财联社快讯更适合实时提醒。",
                scope="skill_lesson",
                score=0.89,
                metadata={"category": "news", "data_source": "cls"},
            ),
        ],
        "expect": {
            "first_scope": "skill_lesson",
            "deduped_count": 2,
            "contains_headers": ["【历史教训】"],
        },
    }


def _build_scenarios() -> List[Dict[str, Any]]:
    return [
        _assistant_scenario(),
        _analysis_scenario(),
        _skill_generation_scenario(),
    ]


def _evaluate_scenario(scenario: Dict[str, Any]) -> Dict[str, Any]:
    ranking_profile = scenario["ranking_profile"]
    metadata_filters = scenario.get("metadata_filters")
    items = list(scenario["items"])
    sorted_items = _sort_recalled_items(items, metadata_filters, ranking_profile=ranking_profile)
    deduped_items = _dedupe_recalled_items(sorted_items)
    formatted_lines = _format_recalled_items(
        deduped_items,
        max_chars=1200,
        group_by_scope=bool(scenario.get("group_by_scope")),
        per_scope_limit=scenario.get("per_scope_limit"),
        ranking_profile=ranking_profile,
    )
    formatted_text = "\n".join(formatted_lines)

    expect = scenario["expect"]
    issues: List[str] = []
    if not deduped_items:
        issues.append("no recalled items after sorting/deduping")
    elif deduped_items[0].scope != expect["first_scope"]:
        issues.append(
            f"first scope mismatch: expected {expect['first_scope']} got {deduped_items[0].scope}"
        )

    if len(deduped_items) != expect["deduped_count"]:
        issues.append(
            f"deduped count mismatch: expected {expect['deduped_count']} got {len(deduped_items)}"
        )

    for header in expect.get("contains_headers", []):
        if header not in formatted_text:
            issues.append(f"missing formatted header: {header}")

    return {
        "name": scenario["name"],
        "ok": not issues,
        "issues": issues,
        "ranking_profile": ranking_profile,
        "metadata_filters": metadata_filters or {},
        "first_scope": deduped_items[0].scope if deduped_items else "",
        "deduped_count": len(deduped_items),
        "formatted_preview": formatted_lines[:8],
    }


def evaluate_all_scenarios() -> Dict[str, Any]:
    scenario_results = [_evaluate_scenario(scenario) for scenario in _build_scenarios()]
    passed = sum(1 for result in scenario_results if result["ok"])
    total = len(scenario_results)
    return {
        "ok": passed == total,
        "passed": passed,
        "total": total,
        "results": scenario_results,
    }


def _print_report(summary: Dict[str, Any]) -> None:
    status = "PASS" if summary["ok"] else "FAIL"
    print(f"[{status}] recall quality scenarios: {summary['passed']}/{summary['total']}")
    for result in summary["results"]:
        scenario_status = "PASS" if result["ok"] else "FAIL"
        print(f"- [{scenario_status}] {result['name']}")
        print(f"  first_scope={result['first_scope']} deduped_count={result['deduped_count']}")
        if result["issues"]:
            for issue in result["issues"]:
                print(f"  issue: {issue}")


def main() -> int:
    summary = evaluate_all_scenarios()
    _print_report(summary)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0 if summary["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())