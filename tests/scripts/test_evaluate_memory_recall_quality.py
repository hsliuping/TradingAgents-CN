import importlib.util
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[2]
SCRIPT_PATH = ROOT_DIR / "scripts" / "evaluate_memory_recall_quality.py"

spec = importlib.util.spec_from_file_location("evaluate_memory_recall_quality", SCRIPT_PATH)
module = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(module)


def test_evaluate_all_scenarios_passes() -> None:
    summary = module.evaluate_all_scenarios()

    assert summary["ok"] is True
    assert summary["passed"] == summary["total"]
    assert summary["total"] >= 3


def test_assistant_scenario_prefers_user_preference_scope() -> None:
    scenario = module._assistant_scenario()
    result = module._evaluate_scenario(scenario)

    assert result["ok"] is True
    assert result["first_scope"] == "user_preference"
    assert result["deduped_count"] == 3


def test_skill_generation_scenario_dedupes_duplicate_lessons() -> None:
    scenario = module._skill_generation_scenario()
    result = module._evaluate_scenario(scenario)

    assert result["ok"] is True
    assert result["deduped_count"] == 2
    assert any("【历史教训】" in line for line in result["formatted_preview"])


def test_agent_builder_scenario_prefers_spec_matched_lessons() -> None:
    scenario = module._agent_builder_scenario()
    result = module._evaluate_scenario(scenario)

    assert result["ok"] is True
    assert result["first_scope"] == "agent_builder_lesson"
    assert result["deduped_count"] == 3
    assert any("【历史工坊教训】" in line for line in result["formatted_preview"])