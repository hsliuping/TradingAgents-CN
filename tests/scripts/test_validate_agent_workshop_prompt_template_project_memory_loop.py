import asyncio
import importlib.util
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[2]
SCRIPT_PATH = ROOT_DIR / "scripts" / "validate_agent_workshop_prompt_template_project_memory_loop.py"

spec = importlib.util.spec_from_file_location("validate_agent_workshop_prompt_template_project_memory_loop", SCRIPT_PATH)
module = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(module)


def test_validate_agent_workshop_prompt_template_project_memory_loop_passes():
    summary = asyncio.run(module.validate_all())

    assert summary["ok"] is True
    assert summary["checks"] == {
        "template_created": True,
        "system_prompt_contains_l4": True,
        "system_prompt_contains_rule": True,
        "constraints_contains_l4_guard": True,
        "constraints_contains_output_constraint": True,
    }