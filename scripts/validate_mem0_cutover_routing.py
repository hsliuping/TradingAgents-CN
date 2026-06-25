"""Validate mem0 cutover routing for workflow builder and trading graph entrypoints."""

from __future__ import annotations

import argparse
import os
import sys
from contextlib import ExitStack
from pathlib import Path
from typing import Any, Dict, List
from unittest.mock import patch


ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from core.workflow import builder as builder_module
from core.workflow.models import NodeDefinition, NodeType
from tradingagents.default_config import DEFAULT_CONFIG
from tradingagents.graph import trading_graph as trading_graph_module


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Validate mem0-only routing for workflow builder and trading graph entrypoints."
    )
    parser.add_argument(
        "--mode",
        choices=["mem0-only"],
        default="mem0-only",
        help="Legacy fallback has been retired; validation always runs in mem0-only mode.",
    )
    return parser.parse_args()


def _configure_runtime_mode(mode: str, validation_user: str) -> Dict[str, str]:
    normalized_mode = str(mode or "mem0-only").strip().lower()
    if normalized_mode != "mem0-only":
        raise ValueError(f"unsupported validation mode: {mode}")

    updates = {
        "MEM0_COMPAT_USER_ID": validation_user,
        "MEMORY_USE_MEM0_COMPAT": "true",
        "MEM0_FORCE_PRIMARY": "true",
    }

    os.environ.update(updates)
    return updates


class _FakeBindingManager:
    def set_database(self, db: Any) -> None:
        self.db = db

    def get_tools_for_node(self, agent_id: str, workflow_id: str | None, node_id: str) -> List[str]:
        del agent_id, workflow_id, node_id
        return []


class _FakeAgentConfigManager:
    def set_database(self, db: Any) -> None:
        self.db = db

    def get_agent_config(self, agent_id: str) -> None:
        del agent_id
        return None


class _FakeEmbeddingManager:
    def __init__(self, db: Any = None):
        self.db = db


class _FakeMemoryManager:
    instances: List["_FakeMemoryManager"] = []

    def __init__(self, embedding_manager: Any):
        self.embedding_manager = embedding_manager
        self.requested_agent_ids: List[str] = []
        type(self).instances.append(self)

    def get_agent_memory(self, agent_id: str) -> Dict[str, Any]:
        self.requested_agent_ids.append(agent_id)
        return {
            "agent_id": agent_id,
            "force_primary_env": os.getenv("MEM0_FORCE_PRIMARY"),
        }


class _FakeRegistry:
    def is_registered(self, agent_id: str) -> bool:
        del agent_id
        return True


class _FakeAgent:
    def __init__(self, memory: Any = None):
        self.memory = memory


class _FakeFactory:
    def __init__(self):
        self.calls: List[Dict[str, Any]] = []

    def create(self, agent_id: str, config: Any, llm: Any = None, tool_ids: List[str] | None = None, memory: Any = None):
        self.calls.append(
            {
                "agent_id": agent_id,
                "config": config,
                "llm": llm,
                "tool_ids": tool_ids,
                "memory": memory,
            }
        )
        return _FakeAgent(memory=memory)


class _FakeLegacyProvider:
    def __init__(self, config: Dict[str, Any] | None = None):
        self.config = config or {}

    def get_llm(self, llm_type: str = "quick", temperature: float | None = None) -> Dict[str, Any]:
        return {"llm_type": llm_type, "temperature": temperature}

    def get_toolkit(self) -> Dict[str, bool]:
        return {"fake_toolkit": True}


class _FakeGraphMemoryProvider:
    instances: List["_FakeGraphMemoryProvider"] = []

    def __init__(self, config: Dict[str, Any] | None = None, memory_enabled: bool = True):
        self.config = config or {}
        self.memory_enabled = memory_enabled
        self.requested: List[str] = []
        self.force_primary_env = os.getenv("MEM0_FORCE_PRIMARY")
        type(self).instances.append(self)

    def get_memory(self, memory_name: str) -> Dict[str, Any]:
        self.requested.append(memory_name)
        return {"memory_name": memory_name}


class _DummyLLM:
    pass


class _FakeGraphSetup:
    last_init_args: tuple[Any, ...] | None = None

    def __init__(self, *args: Any):
        type(self).last_init_args = args

    def setup_graph(self, selected_analysts: List[str]) -> Dict[str, Any]:
        return {"selected_analysts": selected_analysts}


class _FakeConditionalLogic:
    def __init__(self, max_debate_rounds: int = 1, max_risk_discuss_rounds: int = 1):
        self.max_debate_rounds = max_debate_rounds
        self.max_risk_discuss_rounds = max_risk_discuss_rounds


def _run_workflow_builder_smoke() -> Dict[str, Any]:
    fake_factory = _FakeFactory()
    fake_binding_manager = _FakeBindingManager()
    fake_legacy_provider = _FakeLegacyProvider(
        {"memory_enabled": True, "memory_use_mem0_compat": True}
    )
    _FakeMemoryManager.instances.clear()

    with ExitStack() as stack:
        stack.enter_context(
            patch("core.config.agent_config_manager.AgentConfigManager", _FakeAgentConfigManager)
        )
        stack.enter_context(patch("app.core.database.get_mongo_db_sync", return_value=object()))
        stack.enter_context(patch("core.llm.EmbeddingManager", _FakeEmbeddingManager))
        stack.enter_context(patch("core.memory.MemoryManager", _FakeMemoryManager))
        stack.enter_context(
            patch.object(
                builder_module.LegacyDependencyProvider,
                "get_instance",
                return_value=fake_legacy_provider,
            )
        )

        builder = builder_module.WorkflowBuilder(
            registry=_FakeRegistry(),
            factory=fake_factory,
            legacy_config={"memory_enabled": True, "memory_use_mem0_compat": True},
            binding_manager=fake_binding_manager,
        )

    builder._ensure_workflow_surface_access = lambda *args, **kwargs: None
    builder._resolve_agent_output_field = lambda *args, **kwargs: "investment_plan"

    node = NodeDefinition(
        id="research_manager_node",
        type=NodeType.MANAGER,
        agent_id="research_manager_v2",
        label="研究经理",
    )
    node_callable = builder._create_agent_node(node)

    if not callable(node_callable):
        raise AssertionError("workflow builder did not produce a callable node")
    if not _FakeMemoryManager.instances:
        raise AssertionError("workflow builder did not initialize MemoryManager")
    if not fake_factory.calls:
        raise AssertionError("workflow builder did not create the target agent")

    memory_manager = _FakeMemoryManager.instances[-1]
    factory_call = fake_factory.calls[-1]

    return {
        "agent_id": factory_call["agent_id"],
        "requested_agent_ids": list(memory_manager.requested_agent_ids),
        "memory_payload": dict(factory_call["memory"] or {}),
        "force_primary_env": os.getenv("MEM0_FORCE_PRIMARY"),
    }


def _run_trading_graph_smoke() -> Dict[str, Any]:
    _FakeGraphMemoryProvider.instances.clear()
    _FakeGraphSetup.last_init_args = None

    config = DEFAULT_CONFIG.copy()
    config.update(
        {
            "llm_provider": "openai",
            "backend_url": "https://example.test/v1",
            "deep_think_llm": "deep-model",
            "quick_think_llm": "quick-model",
            "memory_enabled": True,
            "memory_use_mem0_compat": True,
        }
    )

    with ExitStack() as stack:
        stack.enter_context(patch.object(trading_graph_module, "set_config", lambda config: None))
        stack.enter_context(patch.object(trading_graph_module.os, "makedirs", lambda *args, **kwargs: None))
        stack.enter_context(patch.object(trading_graph_module, "ChatOpenAI", lambda *args, **kwargs: _DummyLLM()))
        stack.enter_context(patch.object(trading_graph_module, "Toolkit", lambda config=None: object()))
        stack.enter_context(
            patch.object(trading_graph_module.TradingAgentsGraph, "_create_tool_nodes", lambda self: {})
        )
        stack.enter_context(
            patch.object(
                trading_graph_module,
                "MemoryProvider",
                lambda config=None, memory_enabled=True: _FakeGraphMemoryProvider(
                    config=config,
                    memory_enabled=memory_enabled,
                ),
            )
        )
        stack.enter_context(patch.object(trading_graph_module, "GraphSetup", _FakeGraphSetup))
        stack.enter_context(
            patch.object(trading_graph_module, "ConditionalLogic", _FakeConditionalLogic)
        )
        stack.enter_context(patch.object(trading_graph_module, "Reflector", lambda llm: object()))
        stack.enter_context(
            patch.object(trading_graph_module, "SignalProcessor", lambda llm: object())
        )

        graph = trading_graph_module.TradingAgentsGraph(
            selected_analysts=["market"],
            config=config,
        )

    if not _FakeGraphMemoryProvider.instances:
        raise AssertionError("trading graph did not initialize MemoryProvider")

    provider = _FakeGraphMemoryProvider.instances[-1]

    return {
        "requested_memory_names": list(provider.requested),
        "provider_memory_use_mem0_compat": provider.config.get("memory_use_mem0_compat"),
        "force_primary_env": provider.force_primary_env,
        "graph_selected_analysts": graph.graph.get("selected_analysts"),
    }


def main() -> int:
    args = _parse_args()
    validation_user = f"cutover_routing_validation_{args.mode}"
    env_updates = _configure_runtime_mode(args.mode, validation_user)

    workflow_builder_result = _run_workflow_builder_smoke()
    trading_graph_result = _run_trading_graph_smoke()

    print("[INFO] mode=", args.mode)
    print("[INFO] env_updates=", env_updates)
    print("[INFO] workflow_builder_result=", workflow_builder_result)
    print("[INFO] trading_graph_result=", trading_graph_result)

    workflow_ok = workflow_builder_result["requested_agent_ids"] == ["research_manager_v2"]
    workflow_ok = workflow_ok and workflow_builder_result["memory_payload"].get("agent_id") == "research_manager_v2"

    graph_ok = trading_graph_result["requested_memory_names"] == [
        "bull_memory",
        "bear_memory",
        "trader_memory",
        "invest_judge_memory",
        "risk_manager_memory",
    ]
    graph_ok = graph_ok and trading_graph_result["provider_memory_use_mem0_compat"] is True

    if not workflow_ok or not graph_ok:
        print("[FAIL] mem0 cutover routing validation failed")
        return 1

    print("[PASS] workflow builder and trading graph route memory dependencies through mem0 cutover settings")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())