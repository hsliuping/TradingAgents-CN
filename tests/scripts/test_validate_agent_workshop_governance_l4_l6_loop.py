import asyncio
import importlib.util
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[2]
SCRIPT_PATH = ROOT_DIR / "scripts" / "validate_agent_workshop_governance_l4_l6_loop.py"

spec = importlib.util.spec_from_file_location("validate_agent_workshop_governance_l4_l6_loop", SCRIPT_PATH)
module = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(module)


def test_validate_agent_workshop_governance_l4_l6_loop_passes():
    summary = asyncio.run(module.validate_all())

    assert summary["ok"] is True
    assert summary["checks"] == {
        "worker_completed": True,
        "project_memory_injected": True,
        "historical_lessons_injected": True,
        "governance_rule_injected": True,
        "guidance_order_preserved": True,
        "lesson_recall_scoped_by_spec": True,
        "lesson_recall_uses_worker_user": True,
        "runtime_observation_logged": True,
        "runtime_observation_hit": True,
        "runtime_observation_stage": True,
        "runtime_observation_scoped_by_spec": True,
        "runtime_observation_uses_worker_user": True,
    }