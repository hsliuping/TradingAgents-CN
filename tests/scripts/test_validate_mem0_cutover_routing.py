import importlib.util
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[2]
SCRIPT_PATH = ROOT_DIR / "scripts" / "validate_mem0_cutover_routing.py"

spec = importlib.util.spec_from_file_location("validate_mem0_cutover_routing", SCRIPT_PATH)
module = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(module)


def test_workflow_builder_smoke_respects_mem0_only(monkeypatch):
    monkeypatch.delenv("MEM0_FORCE_PRIMARY", raising=False)
    monkeypatch.delenv("MEMORY_USE_MEM0_COMPAT", raising=False)

    updates = module._configure_runtime_mode("mem0-only", "cutover_test_user")
    result = module._run_workflow_builder_smoke()

    assert updates["MEM0_FORCE_PRIMARY"] == "true"
    assert result["requested_agent_ids"] == ["research_manager_v2"]
    assert result["memory_payload"]["agent_id"] == "research_manager_v2"
    assert result["memory_payload"]["force_primary_env"] == "true"


def test_trading_graph_smoke_respects_mem0_only(monkeypatch):
    monkeypatch.delenv("MEM0_FORCE_PRIMARY", raising=False)
    monkeypatch.delenv("MEMORY_USE_MEM0_COMPAT", raising=False)

    updates = module._configure_runtime_mode("mem0-only", "cutover_test_user_graph")
    result = module._run_trading_graph_smoke()

    assert updates["MEM0_FORCE_PRIMARY"] == "true"
    assert result["requested_memory_names"] == [
        "bull_memory",
        "bear_memory",
        "trader_memory",
        "invest_judge_memory",
        "risk_manager_memory",
    ]
    assert result["provider_memory_use_mem0_compat"] is True
    assert result["force_primary_env"] == "true"
