import asyncio
import importlib.util
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[2]
SCRIPT_PATH = ROOT_DIR / "scripts" / "validate_agent_workshop_production_review_project_memory_loop.py"

spec = importlib.util.spec_from_file_location("validate_agent_workshop_production_review_project_memory_loop", SCRIPT_PATH)
module = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(module)


def test_validate_agent_workshop_production_review_project_memory_loop_passes():
    summary = asyncio.run(module.validate_all())

    assert summary["ok"] is True
    assert summary["checks"] == {
        "runtime_prompt_accepts_current_l4": True,
        "runtime_prompt_missing_l4_revises_review": True,
        "runtime_prompt_missing_l4_records_issue": True,
        "missing_system_prompt_marks_evidence_incomplete": True,
        "missing_system_prompt_records_invalid_reason": True,
    }