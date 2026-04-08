"""Validate L4 project-memory injection into the Agent Builder chain."""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from typing import Any, Dict
from unittest.mock import patch


ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from core.embedded_nanobot.agent.runner import AgentRunResult
from core.embedded_nanobot.agent.tools.tradingagents_bridge import TradingAgentsRegistryTool
from core.embedded_nanobot.providers.base import LLMProvider
from core.embedded_nanobot.runtime import EmbeddedNanobotRuntime
from core.tools.config import ToolMetadata


class _FakeProvider(LLMProvider):
    async def chat(self, messages, tools=None, model=None, max_tokens=4096, temperature=0.7, reasoning_effort=None, tool_choice=None):
        del messages, tools, model, max_tokens, temperature, reasoning_effort, tool_choice
        raise AssertionError("This validation should not need a real provider call")

    def get_default_model(self) -> str:
        return "fake-model"


async def validate_all() -> Dict[str, Any]:
    runtime = EmbeddedNanobotRuntime(provider=_FakeProvider(), workspace=ROOT_DIR, memory_db=object())
    runtime.tools.register(
        TradingAgentsRegistryTool(
            metadata=ToolMetadata(
                id="inspect_agent_workshop_assets",
                name="Inspect Agent Workshop Assets",
                description="查看 Agent 工坊中的 spec 和 version 资产摘要。",
                category="assistant_ops",
                parameters=[],
                when_to_use="当用户要查看、修改、继续迭代现有 Agent 工坊资产时先确认状态。",
            ),
            func=lambda: {"ok": True},
        )
    )

    captured: Dict[str, Any] = {}

    class _FakeProjectMemoryService:
        async def build_prompt_block(self, **kwargs):
            captured["project_memory_kwargs"] = dict(kwargs)
            return "【项目长期记忆】\n- 项目规则\n  - 禁止直接投资建议：所有分析只提供研究与学习参考。"

    async def _fake_build_capped_initial_messages(*args, **kwargs):
        captured["extra_system_guidance"] = kwargs.get("extra_system_guidance")
        return ([{"role": "system", "content": "sys"}, {"role": "user", "content": "msg"}], [], 10)

    async def _fake_run(self, spec):
        del self, spec
        return AgentRunResult(final_content="ok", messages=[{"role": "assistant", "content": "ok"}], stop_reason="completed", usage={}, tools_used=[], tool_events=[])

    with patch("app.services.project_memory_service.get_project_memory_service", lambda db: _FakeProjectMemoryService()):
        runtime._build_capped_initial_messages = _fake_build_capped_initial_messages
        runtime._dump_prompt_context = lambda **kwargs: ROOT_DIR / "tmp" / "ctx.json"
        runtime.runner.run = _fake_run.__get__(runtime.runner, type(runtime.runner))

        result = await runtime.handle_message(
            user_message="继续修改这个 agent 工坊版本，先确认当前状态再决定下一步",
            session_key="embedded:agent-builder:l4",
            thread_context={
                "spec_id": "spec_agent_builder_demo",
                "version_id": "spec_agent_builder_demo_v2",
                "version_status": "testing",
            },
        )

    checks = {
        "agent_builder_detected": "# Agent Workshop governance rule" in captured.get("extra_system_guidance", ""),
        "project_memory_injected": "# Agent Workshop project memory" in captured.get("extra_system_guidance", ""),
        "l4_rule_present": "禁止直接投资建议" in captured.get("extra_system_guidance", ""),
        "category_filter_applied": captured.get("project_memory_kwargs", {}).get("categories") == ["project_rule", "governance_constraint", "research_template"],
        "runtime_completed": result["content"] == "ok",
    }
    return {
        "ok": all(checks.values()),
        "checks": checks,
        "extra_system_guidance": captured.get("extra_system_guidance", ""),
    }


def main() -> int:
    summary = asyncio.run(validate_all())
    status = "PASS" if summary["ok"] else "FAIL"
    print(f"[{status}] agent builder project memory loop")
    for check, ok in summary["checks"].items():
        check_status = "PASS" if ok else "FAIL"
        print(f"- [{check_status}] {check}")
    print(summary)
    return 0 if summary["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())