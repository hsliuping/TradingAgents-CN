import asyncio
import importlib.util
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[2]
SCRIPT_PATH = ROOT_DIR / "scripts" / "validate_agent_workshop_l6_forward_consumption_loop.py"

spec = importlib.util.spec_from_file_location("validate_agent_workshop_l6_forward_consumption_loop", SCRIPT_PATH)
module = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(module)


def test_validate_agent_workshop_l6_forward_consumption_loop_passes():
    summary = asyncio.run(module.validate_all())

    assert summary["ok"] is True
    assert summary["checks"] == {
        "requirement_lessons_injected": True,
        "gap_analysis_lessons_injected": True,
        "build_version_lessons_injected": True,
        "build_version_constraints_include_lesson_fix": True,
        "three_stage_recall_calls": True,
        "all_recall_scoped_by_spec": True,
        "all_recall_use_same_user": True,
        "three_stage_observation_logs": True,
        "all_observation_stages_present": True,
        "all_observations_hit": True,
        "all_observations_scoped_by_spec": True,
        "all_observations_use_same_user": True,
        "build_version_completed": True,
    }