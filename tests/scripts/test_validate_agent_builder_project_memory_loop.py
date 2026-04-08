import asyncio
import importlib.util
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[2]
SCRIPT_PATH = ROOT_DIR / "scripts" / "validate_agent_builder_project_memory_loop.py"

spec = importlib.util.spec_from_file_location("validate_agent_builder_project_memory_loop", SCRIPT_PATH)
module = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(module)


def test_validate_agent_builder_project_memory_loop_passes():
    summary = asyncio.run(module.validate_all())

    assert summary["ok"] is True
    assert summary["checks"] == {
        "agent_builder_detected": True,
        "project_memory_injected": True,
        "l4_rule_present": True,
        "category_filter_applied": True,
        "runtime_completed": True,
    }