import json

import pytest

from core.tools.implementations.skill_builder.nanobot_skill_builder_tools import (
    generate_confirmed_external_skill,
    inspect_external_skill_generation_session,
    preview_external_skill_spec,
    respond_to_external_skill_generation_session,
    start_external_skill_generation_session,
)


class _FakeSkillGenerationService:
    def __init__(self):
        self.started = []
        self.responded = []
        self.previewed = []
        self.confirmed = []
        self.inspected = []

    async def start_session(self, description: str, user_id: str = "", handoff_context=None):
        self.started.append({
            "description": description,
            "user_id": user_id,
            "handoff_context": handoff_context,
        })
        return {
            "session_id": "skill-session-1",
            "ai_message": "请确认输入输出边界",
            "clarity_level": "high",
            "expected_rounds": 2,
        }

    async def respond_to_session(self, session_id: str, user_message: str):
        self.responded.append({"session_id": session_id, "user_message": user_message})
        return {
            "session_id": session_id,
            "ai_message": "边界已清晰，可预览 spec",
            "current_round": 2,
            "expected_rounds": 2,
            "is_final_round": True,
        }

    async def preview_spec(self, session_id: str, user_message: str = "确认"):
        self.previewed.append({"session_id": session_id, "user_message": user_message})
        return {
            "spec": {
                "tool_id": "dupont_analysis_skill",
                "description": "A股杜邦分析",
            },
            "recommendations": {"category_hint": "fundamentals"},
            "fact_report": {"confidence": 0.8},
        }

    async def confirm_spec(self, session_id: str, user_message: str = "确认"):
        self.confirmed.append({"session_id": session_id, "user_message": user_message})
        return {
            "status": "generating",
            "session_id": session_id,
            "spec": {"tool_id": "dupont_analysis_skill"},
        }

    async def get_session(self, session_id: str):
        self.inspected.append(session_id)
        return {
            "session_id": session_id,
            "status": "generating",
            "pipeline_stage": "code_generation",
            "pipeline_message": "准备开始生成...",
            "pipeline_progress": 0.2,
            "spec_confirmed": True,
            "spec": {"tool_id": "dupont_analysis_skill"},
            "recommendations": {"category_hint": "fundamentals"},
        }


@pytest.mark.asyncio
async def test_start_external_skill_generation_session_uses_service_and_handoff(monkeypatch):
    fake_service = _FakeSkillGenerationService()
    monkeypatch.setattr(
        "core.tools.implementations.skill_builder.nanobot_skill_builder_tools._get_skill_generation_service",
        lambda: fake_service,
    )
    monkeypatch.setattr(
        "core.tools.implementations.skill_builder.nanobot_skill_builder_tools.get_current_user_id",
        lambda: "user-123",
    )

    raw = await start_external_skill_generation_session.ainvoke({
        "description": "创建一个可复用的杜邦分析 skill，输入 symbol，输出结构化三因素分解",
        "handoff_context_json": json.dumps({"original_goal": "杜邦分析可复用化"}, ensure_ascii=False),
    })
    data = json.loads(raw)

    assert data["status"] == "ok"
    assert data["session_id"] == "skill-session-1"
    assert data["recommended_next_step"] == "preview_external_skill_spec"
    assert fake_service.started[0]["user_id"] == "user-123"
    assert fake_service.started[0]["handoff_context"] == {"original_goal": "杜邦分析可复用化"}


@pytest.mark.asyncio
async def test_generate_confirmed_external_skill_requires_confirmation():
    raw = await generate_confirmed_external_skill.ainvoke({
        "session_id": "skill-session-1",
        "confirmed": False,
    })
    data = json.loads(raw)

    assert data["status"] == "error"
    assert "明确确认" in data["message"]


@pytest.mark.asyncio
async def test_skill_builder_tool_chain_calls_service(monkeypatch):
    fake_service = _FakeSkillGenerationService()
    monkeypatch.setattr(
        "core.tools.implementations.skill_builder.nanobot_skill_builder_tools._get_skill_generation_service",
        lambda: fake_service,
    )

    preview_raw = await preview_external_skill_spec.ainvoke({"session_id": "skill-session-1"})
    preview_data = json.loads(preview_raw)
    assert preview_data["status"] == "ok"
    assert preview_data["recommended_next_step"] == "generate_confirmed_external_skill"

    respond_raw = await respond_to_external_skill_generation_session.ainvoke({
        "session_id": "skill-session-1",
        "user_message": "输入只要 symbol，不输出交易建议",
    })
    respond_data = json.loads(respond_raw)
    assert respond_data["status"] == "ok"
    assert respond_data["recommended_next_step"] == "preview_external_skill_spec"

    confirm_raw = await generate_confirmed_external_skill.ainvoke({
        "session_id": "skill-session-1",
        "confirmed": True,
    })
    confirm_data = json.loads(confirm_raw)
    assert confirm_data["status"] == "ok"
    assert confirm_data["recommended_next_step"] == "inspect_external_skill_generation_session"

    inspect_raw = await inspect_external_skill_generation_session.ainvoke({"session_id": "skill-session-1"})
    inspect_data = json.loads(inspect_raw)
    assert inspect_data["status"] == "ok"
    assert inspect_data["session"]["pipeline_stage"] == "code_generation"