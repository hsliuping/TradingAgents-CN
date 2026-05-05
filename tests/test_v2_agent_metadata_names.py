import ast
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[1]

EXPECTED_METADATA = {
    "core/agents/adapters/bull_researcher_v2.py": {
        "id": "bull_researcher_v2",
        "name": "看涨研究员 v2.0",
        "description": "从看涨角度综合分析多个报告，找出支持买入的理由",
        "report_label": "【看涨观点 v2】",
    },
    "core/agents/adapters/bear_researcher_v2.py": {
        "id": "bear_researcher_v2",
        "name": "看跌研究员 v2.0",
        "description": "从看跌角度综合分析多个报告，找出风险因素和看跌理由",
        "report_label": "【看跌观点 v2】",
    },
    "core/agents/adapters/index_analyst_v2.py": {
        "id": "index_analyst_v2",
        "name": "大盘分析师 v2.0",
        "description": "分析大盘指数走势与市场环境，提炼系统性风险和关键观察信号",
        "report_label": "【大盘分析 v2】",
    },
    "core/agents/adapters/sector_analyst_v2.py": {
        "id": "sector_analyst_v2",
        "name": "板块分析师 v2.0",
        "description": "分析行业趋势、板块轮动和同业对比，提炼结构变化与风险来源",
        "report_label": "【板块分析 v2】",
    },
    "core/agents/adapters/risk_manager_v2.py": {
        "id": "risk_manager_v2",
        "name": "风险管理者 v2.0",
    },
    "core/agents/adapters/risky_analyst_v2.py": {
        "id": "risky_analyst_v2",
        "name": "激进风险分析师 v2.0",
    },
    "core/agents/adapters/safe_analyst_v2.py": {
        "id": "safe_analyst_v2",
        "name": "保守风险分析师 v2.0",
    },
    "core/agents/adapters/neutral_analyst_v2.py": {
        "id": "neutral_analyst_v2",
        "name": "中性风险分析师 v2.0",
    },
}


def _extract_metadata(file_path: Path) -> dict[str, str]:
    tree = ast.parse(file_path.read_text(encoding="utf-8"))

    for node in ast.walk(tree):
        if not isinstance(node, ast.Assign):
            continue

        if not any(isinstance(target, ast.Name) and target.id == "metadata" for target in node.targets):
            continue

        if not isinstance(node.value, ast.Call):
            continue

        func = node.value.func
        func_name = func.id if isinstance(func, ast.Name) else getattr(func, "attr", None)
        if func_name != "AgentMetadata":
            continue

        extracted = {}
        for keyword in node.value.keywords:
            if keyword.arg not in {"id", "name", "description", "report_label"}:
                continue
            if isinstance(keyword.value, ast.Constant) and isinstance(keyword.value.value, str):
                extracted[keyword.arg] = keyword.value.value

        return extracted

    raise AssertionError(f"未在 {file_path} 中找到 AgentMetadata")


@pytest.mark.parametrize("relative_path, expected", EXPECTED_METADATA.items())
def test_v2_agent_metadata_matches_release_names(relative_path: str, expected: dict[str, str]) -> None:
    actual = _extract_metadata(REPO_ROOT / relative_path)

    for key, value in expected.items():
        assert actual.get(key) == value