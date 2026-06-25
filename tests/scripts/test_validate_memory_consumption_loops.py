import asyncio
import importlib.util
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[2]
SCRIPT_PATH = ROOT_DIR / "scripts" / "validate_memory_consumption_loops.py"

spec = importlib.util.spec_from_file_location("validate_memory_consumption_loops", SCRIPT_PATH)
module = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(module)


def test_assistant_memory_block_reaches_prompt():
    result = asyncio.run(module._run_assistant_consumption_smoke())

    assert result["memory_block"].startswith("【历史偏好】")
    assert result["prompt_contains_memory"] is True
    assert result["prompt_contains_topic"] is True


def test_analysis_memory_block_reaches_workflow_inputs():
    result = asyncio.run(module._run_analysis_consumption_smoke())

    assert result["injected_growth_memory"] is True
    assert result["injected_mem0_memory"] is True
    assert "【成长记忆】" in result["combined_block"]
    assert "【历史分析】" in result["combined_block"]


def test_growth_approved_memory_reaches_recall_context():
    result = asyncio.run(module._run_growth_approval_consumption_smoke())

    assert result["approved"] is True
    assert result["bridged_to_mem0"] is True
    assert result["bridge_scope"] == "agent_experience"
    assert result["context_contains_header"] is True
    assert result["context_contains_title"] is True
    assert result["context_contains_summary"] is True


def test_skill_lessons_reach_initial_feedback():
    result = asyncio.run(module._run_skill_consumption_smoke())

    assert result["feedback_contains_mem0_lessons"] is True
    assert result["feedback_contains_original_feedback"] is True
    assert "【历史教训】" in result["final_initial_feedback"]
    assert "【用户反馈】" in result["final_initial_feedback"]


def test_validate_all_passes():
    summary = asyncio.run(module.validate_all())

    assert summary["ok"] is True
    assert summary["checks"] == {
        "assistant_prompt_injection": True,
        "analysis_input_injection": True,
        "growth_approved_memory_consumption": True,
        "skill_feedback_injection": True,
    }