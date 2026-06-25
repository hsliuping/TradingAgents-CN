import sys
import importlib.util
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))


MODULE_PATH = ROOT_DIR / "scripts" / "validate_manager_memory_runtime.py"
SPEC = importlib.util.spec_from_file_location("validate_manager_memory_runtime", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)

_configure_runtime_mode = MODULE._configure_runtime_mode


def test_configure_runtime_mode_uses_mem0_only(monkeypatch):
    monkeypatch.delenv("MEM0_FORCE_PRIMARY", raising=False)
    monkeypatch.delenv("MEMORY_USE_MEM0_COMPAT", raising=False)

    updates = _configure_runtime_mode("mem0-only", "validation_user_1")

    assert updates == {
        "MEM0_COMPAT_USER_ID": "validation_user_1",
        "MEMORY_USE_MEM0_COMPAT": "true",
        "MEM0_FORCE_PRIMARY": "true",
    }