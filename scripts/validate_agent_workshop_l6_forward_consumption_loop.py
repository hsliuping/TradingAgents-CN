"""Validate Agent Workshop L6 lesson forward consumption across requirement clarification, gap analysis, and build_version."""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Dict
from unittest.mock import patch


ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.models.agent_workshop import AgentSpec, AgentSpecStatus, AgentWorkshopSession, AgentWorkshopStage
from app.services.agent_workshop_service import AgentWorkshopService


class _FakeCollection:
    async def create_index(self, *_args, **_kwargs):
        return None


class _FakeDb:
    def __init__(self) -> None:
        self.prompt_templates = _FakeCollection()
        self.template_history = _FakeCollection()

    def __getitem__(self, name: str) -> Any:
        try:
            return getattr(self, name)
        except AttributeError as exc:
            raise KeyError(name) from exc

    def __getattr__(self, name: str) -> Any:
        raise AttributeError(name)


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


def _build_capability_snapshot() -> Dict[str, Any]:
    return {
        "totals": {"builtin_tools": 0, "external_skills": 0},
        "builtin_data_tools": [],
        "builtin_analysis_tools": [],
        "external_data_skills": [],
        "external_analysis_skills": [],
        "valuation_tools": [],
        "valuation_skills": [],
        "valuation_tool_details": [],
        "valuation_skill_details": [],
        "registered_capabilities": [],
    }


async def validate_all() -> Dict[str, Any]:
    svc = AgentWorkshopService(_FakeDb())
    captured: Dict[str, Any] = {
        "llm_prompts": [],
        "template_payload": None,
        "observation_logs": [],
    }

    class _FakeMemoryService:
        def __init__(self) -> None:
            self.calls: list[dict[str, Any]] = []

        async def recall_formatted(self, **kwargs):
            self.calls.append(dict(kwargs))
            return "【历史工坊教训】\n- 上一轮误把已有能力判成新缺口\n- 修正动作：先核对合法工具清单和能力覆盖映射\n"

    class _FakeClient:
        def __init__(self) -> None:
            self.call_count = 0

        async def achat(self, messages):
            self.call_count += 1
            captured["llm_prompts"].append({
                "system": str(messages[0].content),
                "user": str(messages[1].content),
            })
            if self.call_count == 1:
                return SimpleNamespace(content=json.dumps({
                    "feasibility_status": "feasible",
                    "response_message": "我先按现有需求整理成一版可执行草案。",
                    "refusal_reason": "",
                    "pending_questions": [],
                    "completeness_score": 0.96,
                    "name": "A股估值分析师",
                    "domain": "stock_analysis",
                    "target_users": ["投研人员"],
                    "primary_goal": "输出A股估值结论",
                    "responsibilities": ["输出估值结论并解释关键依据"],
                    "non_goals": ["不直接给买卖建议"],
                    "inputs": [{"name": "symbol", "type": "string", "required": True, "description": "股票代码"}],
                    "outputs": [{"name": "valuation_report", "type": "string", "required": True, "description": "估值报告"}],
                    "success_criteria": ["结论可解释且有依据"],
                    "constraints": ["不直接给买卖建议"],
                    "preferred_methods": ["PE", "PB"],
                    "capability_requirements": [{
                        "capability_key": "peer_comparison",
                        "capability_name": "同业比较",
                        "capability_type": "data",
                        "description": "获取同业估值与财务比较依据",
                        "delivery_requirement": "tool-or-prompt",
                        "acceptance_criteria": ["能给出至少一组可解释的同行比较依据"],
                    }],
                    "sample_symbols": ["600519.SH"],
                }, ensure_ascii=False))
            if self.call_count == 2:
                return SimpleNamespace(content=json.dumps({
                    "existing_tools": [],
                    "suggested_tools": [],
                    "suggested_capabilities": [],
                    "manual_dependencies": [],
                    "blocking_gaps": ["需要补充更稳定的同行比较能力封装"],
                    "fallback_strategy": ["先基于现有工具做保守降级"],
                    "build_recommendations": ["优先补同行比较证据链"],
                    "notes": ["已结合历史 lesson 做去重判断"],
                }, ensure_ascii=False))
            raise AssertionError("Unexpected LLM call count")

    fake_memory_service = _FakeMemoryService()
    fake_client = _FakeClient()
    base_spec = _build_spec()

    async def _fake_ensure_llm_client():
        return fake_client

    async def _fake_collect_capability_snapshot(_text, top_k=12):
        del _text, top_k
        return _build_capability_snapshot()

    async def _fake_resolve_session_draft_version(_session, _spec):
        return None

    async def _fake_get_next_version_number(_spec_id):
        return 1

    async def _fake_save_version(version):
        captured["saved_version"] = version

    async def _fake_save_session(session):
        captured["saved_session"] = session

    async def _fake_save_spec(spec, session_id=""):
        captured["saved_spec"] = {"spec": spec, "session_id": session_id}

    async def _fake_build_project_memory_block():
        return ""

    async def _fake_create_template(_self, payload):
        captured["template_payload"] = payload
        return SimpleNamespace(id="tpl_l6_forward_001", template_name=payload.template_name, status=payload.status)

    def _fake_log_generated_result(stage: str, result: Dict[str, Any], context: Dict[str, Any] | None = None):
        if stage == "agent_builder_lesson_recall_observation":
            captured["observation_logs"].append({
                "stage": stage,
                "result": dict(result),
                "context": dict(context or {}),
            })

    monkeypatch_targets = [
        patch("core.memory.service.get_memory_service", lambda _db=None: fake_memory_service),
        patch("app.services.agent_workshop_service.PromptTemplateService.create_template", _fake_create_template),
    ]

    for target in monkeypatch_targets:
        target.start()

    try:
        svc._llm_client_meta = {"provider": "fake", "model": "fake-model", "timeout": 60}
        svc._ensure_llm_client = _fake_ensure_llm_client
        svc._collect_capability_snapshot = _fake_collect_capability_snapshot
        svc._resolve_session_draft_version = _fake_resolve_session_draft_version
        svc._get_next_version_number = _fake_get_next_version_number
        svc._save_version = _fake_save_version
        svc._save_session = _fake_save_session
        svc._save_spec = _fake_save_spec
        svc._build_project_memory_block_for_workshop = _fake_build_project_memory_block
        svc._log_generated_result = _fake_log_generated_result

        clarification = await svc._analyze_requirement_turn(
            ["请帮我做一个A股估值 Agent，不能直接给买卖建议。"],
            user_id="user_001",
            existing_spec=base_spec,
        )
        clarified_spec = clarification["spec"]

        session = AgentWorkshopSession(
            session_id="session_valuation_001",
            spec_id=clarified_spec.spec_id,
            user_id="user_001",
            stage=AgentWorkshopStage.BUILDING,
            current_round=1,
            current_spec_snapshot=clarified_spec,
            completeness_score=1.0,
            feasibility_status="feasible",
        )

        async def _fake_load_session(session_id: str):
            assert session_id == session.session_id
            return session

        svc._load_session = _fake_load_session

        build_result = await svc.build_version(session.session_id)
    finally:
        for target in reversed(monkeypatch_targets):
            target.stop()

    requirement_prompt = str(captured["llm_prompts"][0]["user"])
    gap_prompt = str(captured["llm_prompts"][1]["user"])
    template_payload = captured["template_payload"]
    recall_calls = fake_memory_service.calls
    observation_logs = captured["observation_logs"]
    expected_stages = {"requirement_clarification", "gap_analysis", "build_version"}

    checks = {
        "requirement_lessons_injected": "【Agent 工坊历史教训】" in requirement_prompt,
        "gap_analysis_lessons_injected": "【Agent 工坊历史教训】" in gap_prompt,
        "build_version_lessons_injected": bool(template_payload) and "【Agent 工坊历史教训】" in template_payload.content.system_prompt,
        "build_version_constraints_include_lesson_fix": bool(template_payload) and "必须结合 Agent 工坊历史教训修正上一轮或同类版本已确认的问题。" in template_payload.content.constraints,
        "three_stage_recall_calls": len(recall_calls) == 3,
        "all_recall_scoped_by_spec": len(recall_calls) == 3 and all(call.get("metadata_filters") == {"spec_id": clarified_spec.spec_id} for call in recall_calls),
        "all_recall_use_same_user": len(recall_calls) == 3 and all(call.get("user_id") == "user_001" for call in recall_calls),
        "three_stage_observation_logs": len(observation_logs) == 3,
        "all_observation_stages_present": {item["result"].get("source_stage") for item in observation_logs} == expected_stages,
        "all_observations_hit": len(observation_logs) == 3 and all(item["result"].get("status") == "hit" for item in observation_logs),
        "all_observations_scoped_by_spec": len(observation_logs) == 3 and all(item["result"].get("metadata_filters") == {"spec_id": clarified_spec.spec_id} for item in observation_logs),
        "all_observations_use_same_user": len(observation_logs) == 3 and all(item["context"].get("user_id") == "user_001" for item in observation_logs),
        "build_version_completed": build_result["version"].version_id == "spec_valuation_candidate_v1_v1",
    }

    return {
        "ok": all(checks.values()),
        "checks": checks,
        "requirement_prompt": requirement_prompt,
        "gap_prompt": gap_prompt,
        "template_system_prompt": template_payload.content.system_prompt if template_payload else "",
        "lesson_recall_calls": recall_calls,
        "observation_logs": observation_logs,
    }


def main() -> int:
    summary = asyncio.run(validate_all())
    status = "PASS" if summary["ok"] else "FAIL"
    print(f"[{status}] agent workshop l6 forward consumption loop")
    for check, ok in summary["checks"].items():
        check_status = "PASS" if ok else "FAIL"
        print(f"- [{check_status}] {check}")
    print(summary)
    return 0 if summary["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())