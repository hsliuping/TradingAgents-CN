import ast
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[1]

EXPECTED_METADATA = {
    "core/agents/adapters/bull_researcher_v2.py": {
        "id": "bull_researcher_v2",
        "name": "乐观情景研究员 v2.0",
        "description": "基于现有材料构建偏乐观但克制的研究论证，提炼成立前提、证据链与观察信号",
        "category": "RESEARCHER",
        "version": "2.0.0",
        "license_tier": "FREE",
        "report_label": "【乐观情景研究 v2】",
    },
    "core/agents/adapters/bear_researcher_v2.py": {
        "id": "bear_researcher_v2",
        "name": "审慎情景研究员 v2.0",
        "description": "基于现有材料构建偏审慎的研究论证，提炼风险、脆弱点与判断边界",
        "category": "RESEARCHER",
        "version": "2.0.0",
        "license_tier": "FREE",
        "report_label": "【审慎情景研究 v2】",
    },
    "core/agents/adapters/index_analyst_v2.py": {
        "id": "index_analyst_v2",
        "name": "大盘分析师 v2.0",
        "description": "分析大盘指数走势与市场环境，提炼系统性风险和关键观察信号",
        "category": "ANALYST",
        "version": "2.0.0",
        "license_tier": "FREE",
        "report_label": "【大盘分析 v2】",
    },
    "core/agents/adapters/sector_analyst_v2.py": {
        "id": "sector_analyst_v2",
        "name": "板块分析师 v2.0",
        "description": "分析行业趋势、板块轮动和同业对比，提炼结构变化与风险来源",
        "category": "ANALYST",
        "version": "2.0.0",
        "license_tier": "FREE",
        "report_label": "【板块分析 v2】",
    },
    "core/agents/adapters/research_manager_v2.py": {
        "id": "research_manager_v2",
        "name": "研究经理 v2.0",
        "description": "综合乐观与审慎情景研究，形成平衡研究结论与观察重点",
        "category": "MANAGER",
        "version": "2.0.0",
        "license_tier": "FREE",
        "report_label": "【平衡研究结论 v2】",
    },
    "core/agents/adapters/risk_manager_v2.py": {
        "id": "risk_manager_v2",
        "name": "风险管理者 v2.0",
        "description": "主持稳健性审阅，综合多方观点，形成风险审阅后的综合研究结论",
        "category": "MANAGER",
        "version": "2.0.0",
        "license_tier": "FREE",
        "report_label": "【风险治理结论 v2】",
    },
    "core/agents/adapters/risky_analyst_v2.py": {
        "id": "risky_analyst_v2",
        "name": "激进风险分析师 v2.0",
        "description": "从激进角度审阅研究结论的上修条件，关注高收益机会，容忍较高风险，支持多轮辩论",
        "category": "RISK",
        "version": "2.0.0",
        "license_tier": "FREE",
        "report_label": "【激进风险评估】",
    },
    "core/agents/adapters/safe_analyst_v2.py": {
        "id": "safe_analyst_v2",
        "name": "保守风险分析师 v2.0",
        "description": "从保守角度审阅研究结论的脆弱点，优先资本保护，规避潜在风险，支持多轮辩论",
        "category": "RISK",
        "version": "2.0.0",
        "license_tier": "FREE",
        "report_label": "【保守风险评估】",
    },
    "core/agents/adapters/neutral_analyst_v2.py": {
        "id": "neutral_analyst_v2",
        "name": "中性风险分析师 v2.0",
        "description": "从中性角度审阅研究结论的基准情景，平衡收益与风险，支持多轮辩论",
        "category": "RISK",
        "version": "2.0.0",
        "license_tier": "FREE",
        "report_label": "【中性风险评估】",
    },
    "core/agents/adapters/trader_v2.py": {
        "id": "trader_v2",
        "name": "研究整合员 v2.0",
        "description": "根据风险审阅后的综合研究结论生成用户版研究简报",
        "category": "TRADER",
        "version": "2.0.0",
        "license_tier": "FREE",
        "report_label": "【用户版研究简报 v2】",
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
            if keyword.arg not in {"id", "name", "description", "category", "version", "license_tier", "report_label"}:
                continue
            if isinstance(keyword.value, ast.Constant) and isinstance(keyword.value.value, str):
                extracted[keyword.arg] = keyword.value.value
            elif isinstance(keyword.value, ast.Attribute):
                extracted[keyword.arg] = keyword.value.attr

        return extracted

    raise AssertionError(f"未在 {file_path} 中找到 AgentMetadata")


@pytest.mark.parametrize("relative_path, expected", EXPECTED_METADATA.items())
def test_v2_agent_metadata_matches_release_names(relative_path: str, expected: dict[str, str]) -> None:
    actual = _extract_metadata(REPO_ROOT / relative_path)

    for key, value in expected.items():
        assert actual.get(key) == value