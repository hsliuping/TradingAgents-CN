"""Validate Agent Workshop governance injection with combined L4 project memory and L6 lessons."""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path
from typing import Any, Dict
from unittest.mock import patch


ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.models.agent_workshop import (
    AgentEvaluationCandidateFinding,
    AgentEvaluationEvidenceTask,
    AgentSpec,
    AgentSpecStatus,
    AgentVersion,
    AgentVersionStatus,
    AgentWorkshopSession,
    AgentWorkshopStage,
)
from app.services.agent_workshop_service import AgentWorkshopService, SESSION_COLLECTION
from core.embedded_nanobot.agent.runner import AgentRunResult
from core.embedded_nanobot.agent.tools.tradingagents_bridge import TradingAgentsRegistryTool
from core.embedded_nanobot.providers.base import LLMProvider
from core.embedded_nanobot.runtime import EmbeddedNanobotRuntime
from core.tools.config import ToolMetadata


class _FakeCollection:
    def __init__(self, items):
        self._items = [dict(item) for item in items]

    async def find_one(self, query, sort=None):
        del sort
        for item in self._items:
            if all(item.get(key) == value for key, value in query.items()):
                return dict(item)
        return None


class _FakeDb:
    def __init__(self, collections):
        self._collections = collections

    def __getitem__(self, name):
        return self._collections[name]

    def __getattr__(self, name):
        try:
            return self._collections[name]
        except KeyError as exc:
            raise AttributeError(name) from exc


class _FakeProvider(LLMProvider):
    async def chat(self, messages, tools=None, model=None, max_tokens=4096, temperature=0.7, reasoning_effort=None, tool_choice=None):
        del messages, tools, model, max_tokens, temperature, reasoning_effort, tool_choice
        raise AssertionError("This validation should not need a real provider call")

    def get_default_model(self) -> str:
        return "fake-model"


def _build_spec() -> AgentSpec:
    return AgentSpec(
        spec_id="spec_valuation_candidate_v1",
        name="A股估值分析师",
        domain="stock_analysis",
        primary_goal="输出A股估值结论",
        outputs=["valuation_report"],
        status=AgentSpecStatus.DRAFT,
        latest_session_id="session_valuation_001",
    )


def _build_version() -> AgentVersion:
    return AgentVersion(
        version_id="spec_valuation_candidate_v1_v2",
        spec_id="spec_valuation_candidate_v1",
        version=2,
        status=AgentVersionStatus.TESTING,
        agent_metadata={
            "id": "spec_valuation_candidate_v1_v2",
            "name": "A股估值分析师 v2",
            "description": "输出A股估值结论",
            "version": "0.2.0",
            "output_field": "valuation_report",
        },
        prompt_template_ref={"template_id": "tpl_spec_valuation_candidate_v1_v2"},
        required_tools=["get_value_factor_bundle_tool", "get_peer_comparison"],
        required_capabilities=["valuation"],
        output_schema={"properties": {"valuation_report": {"type": "string"}}},
        evaluation_policy={"minimum_score": 0.75},
        published_from_session_id="session_valuation_001",
    )


def _build_session() -> AgentWorkshopSession:
    return AgentWorkshopSession(
        session_id="session_valuation_001",
        spec_id="spec_valuation_candidate_v1",
        user_id="user_001",
        stage=AgentWorkshopStage.BUILDING,
        current_round=1,
        current_spec_snapshot=_build_spec(),
    )


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

    captured: Dict[str, Any] = {
        "observation_logs": [],
    }

    class _FakeProjectMemoryService:
        async def build_prompt_block(self, **kwargs):
            captured["project_memory_kwargs"] = dict(kwargs)
            return "【项目长期记忆】\n- 项目规则\n  - 禁止直接投资建议：所有分析只提供研究与学习参考。"

    class _FakeMemoryService:
        async def recall_formatted(self, **kwargs):
            captured["lesson_recall_kwargs"] = dict(kwargs)
            return "【工坊历史教训】\n- 上一轮缺少行业对比证据\n- 修正动作：补充行业横向比较和估值解释\n"

    async def _fake_build_capped_initial_messages(*args, **kwargs):
        captured["extra_system_guidance"] = kwargs.get("extra_system_guidance")
        return ([{"role": "system", "content": "sys"}, {"role": "user", "content": "msg"}], [], 10)

    async def _fake_run(self, spec):
        del self, spec
        return AgentRunResult(
            final_content=json.dumps({
                "status": "confirmed",
                "summary": "已完成治理核查",
                "evidence": ["已检查 L4/L6 guidance 注入链路"],
                "artifacts": [],
            }, ensure_ascii=False),
            messages=[{"role": "assistant", "content": "ok"}],
            stop_reason="completed",
            usage={},
            tools_used=[],
            tool_events=[],
        )

    async def _fake_sync_tradingagents_capabilities(_db):
        del _db
        return None

    async def _fake_get_runtime(self):
        del self
        return runtime

    async def _fake_persist_chat_turn(self, **kwargs):
        captured["persist_chat_turn_kwargs"] = dict(kwargs)
        return None

    def _fake_log_agent_builder_lesson_recall_observation(**kwargs):
        captured["observation_logs"].append(dict(kwargs))

    fake_db = _FakeDb({
        SESSION_COLLECTION: _FakeCollection([
            _build_session().model_dump(mode="json", by_alias=True),
        ]),
    })
    svc = AgentWorkshopService(fake_db)
    spec = _build_spec()
    version = _build_version()
    task = AgentEvaluationEvidenceTask(
        task_id="task_nanobot_001",
        finding_id="finding_nanobot_001",
        worker_name="PromptEvidenceWorker",
        objective="核查运行时 Prompt 的治理约束注入情况",
    )
    finding = AgentEvaluationCandidateFinding(
        finding_id="finding_nanobot_001",
        category="project_memory_binding",
        title="运行时 Prompt 缺少治理上下文",
    )

    runtime._build_capped_initial_messages = _fake_build_capped_initial_messages
    runtime._dump_prompt_context = lambda **kwargs: ROOT_DIR / "tmp" / "ctx.json"
    runtime.runner.run = _fake_run.__get__(runtime.runner, type(runtime.runner))
    runtime.sync_tradingagents_capabilities = _fake_sync_tradingagents_capabilities
    runtime._log_agent_builder_lesson_recall_observation = _fake_log_agent_builder_lesson_recall_observation

    with patch("app.services.project_memory_service.get_project_memory_service", lambda db: _FakeProjectMemoryService()), patch("core.memory.service.get_memory_service", lambda db: _FakeMemoryService()), patch("app.services.embedded_nanobot_service.EmbeddedNanobotService.get_runtime", _fake_get_runtime), patch("app.services.embedded_nanobot_service.EmbeddedNanobotService.persist_chat_turn", _fake_persist_chat_turn):
        original_build_prompt = svc._build_nanobot_evidence_worker_prompt
        svc._build_nanobot_evidence_worker_prompt = lambda *args, **kwargs: (
            "继续修改这个 agent 工坊版本，先结合历史评估结论确认下一步，并核对当前 spec/version 状态。\n\n"
            + original_build_prompt(*args, **kwargs)
        )
        try:
            result = await svc._run_nanobot_evidence_worker_task(
                task,
                finding,
                version,
                spec,
                {"output_text": "ok", "output_payload": {}, "debug_prompt": {}},
                {"project_memory_binding": {"enabled": True}},
            )
        finally:
            svc._build_nanobot_evidence_worker_prompt = original_build_prompt

    extra_guidance = str(captured.get("extra_system_guidance") or "")
    observation_logs = captured.get("observation_logs", [])
    checks = {
        "worker_completed": result.status == "confirmed",
        "project_memory_injected": "# Agent Workshop project memory" in extra_guidance,
        "historical_lessons_injected": "# Agent Workshop historical lessons" in extra_guidance,
        "governance_rule_injected": "# Agent Workshop governance rule" in extra_guidance,
        "guidance_order_preserved": extra_guidance.index("# Agent Workshop project memory") < extra_guidance.index("# Agent Workshop historical lessons") < extra_guidance.index("# Agent Workshop governance rule"),
        "lesson_recall_scoped_by_spec": captured.get("lesson_recall_kwargs", {}).get("metadata_filters") == {"spec_id": spec.spec_id},
        "lesson_recall_uses_worker_user": captured.get("lesson_recall_kwargs", {}).get("user_id") == "user_001",
        "runtime_observation_logged": len(observation_logs) == 1,
        "runtime_observation_hit": len(observation_logs) == 1 and observation_logs[0].get("status") == "hit",
        "runtime_observation_stage": len(observation_logs) == 1 and observation_logs[0].get("source_stage") == "runtime_governance",
        "runtime_observation_scoped_by_spec": len(observation_logs) == 1 and observation_logs[0].get("metadata_filters") == {"spec_id": spec.spec_id},
        "runtime_observation_uses_worker_user": len(observation_logs) == 1 and observation_logs[0].get("user_id") == "user_001",
    }
    return {
        "ok": all(checks.values()),
        "checks": checks,
        "extra_system_guidance": extra_guidance,
        "lesson_recall_kwargs": captured.get("lesson_recall_kwargs", {}),
        "observation_logs": observation_logs,
        "project_memory_kwargs": captured.get("project_memory_kwargs", {}),
        "persist_chat_turn_kwargs": captured.get("persist_chat_turn_kwargs", {}),
    }


def main() -> int:
    summary = asyncio.run(validate_all())
    status = "PASS" if summary["ok"] else "FAIL"
    print(f"[{status}] agent workshop governance l4+l6 loop")
    for check, ok in summary["checks"].items():
        check_status = "PASS" if ok else "FAIL"
        print(f"- [{check_status}] {check}")
    print(summary)
    return 0 if summary["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())