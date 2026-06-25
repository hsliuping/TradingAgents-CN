import asyncio
import importlib.util
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[2]
SCRIPT_PATH = ROOT_DIR / "scripts" / "validate_project_memory_l4_loop.py"

spec = importlib.util.spec_from_file_location("validate_project_memory_l4_loop", SCRIPT_PATH)
module = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(module)


def test_validate_project_memory_l4_loop_passes():
    summary = asyncio.run(module.validate_all())

    assert summary["ok"] is True
    assert summary["checks"] == {
        "l4_write_success": True,
        "l4_read_success": True,
        "l4_prompt_block_built": True,
        "assistant_injection_contains_l4": True,
        "assistant_injection_keeps_l5_l6": True,
    }