"""Nanobot 友好的可复用 Skill 生成工具。"""

from __future__ import annotations

import json
import logging
from typing import Annotated, Any

from langchain_core.tools import tool

from app.core.database import get_mongo_db
from app.services.skill_generation_service import SkillGenerationService
from core.tools.base import register_tool
from core.tools.context import get_current_user_id

logger = logging.getLogger(__name__)


def _json_response(payload: dict[str, Any]) -> str:
    return json.dumps(payload, ensure_ascii=False, indent=2, default=str)


def _parse_optional_json_dict(raw: str, field_name: str) -> dict[str, Any] | None:
    text = str(raw or "").strip()
    if not text:
        return None
    data = json.loads(text)
    if not isinstance(data, dict):
        raise ValueError(f"{field_name} 必须是 JSON 对象")
    return data


def _get_skill_generation_service() -> SkillGenerationService:
    return SkillGenerationService(db=get_mongo_db())


def _recommend_start_next_step(start_result: dict[str, Any]) -> str:
    clarity = str(start_result.get("clarity_level") or "").strip().lower()
    return "preview_external_skill_spec" if clarity == "high" else "respond_to_external_skill_generation_session"


def _recommend_follow_up_next_step(result: dict[str, Any]) -> str:
    if result.get("is_final_round"):
        return "preview_external_skill_spec"
    return "respond_to_external_skill_generation_session"


def _summarize_session_doc(session_doc: dict[str, Any]) -> dict[str, Any]:
    pipeline_result = session_doc.get("pipeline_result") or {}
    summary: dict[str, Any] = {
        "session_id": session_doc.get("session_id"),
        "user_id": session_doc.get("user_id"),
        "status": session_doc.get("status"),
        "current_round": session_doc.get("current_round"),
        "spec_confirmed": session_doc.get("spec_confirmed"),
        "updated_at": session_doc.get("updated_at"),
        "pipeline_stage": session_doc.get("pipeline_stage"),
        "pipeline_message": session_doc.get("pipeline_message"),
        "pipeline_iteration": session_doc.get("pipeline_iteration"),
        "pipeline_progress": session_doc.get("pipeline_progress"),
        "recommendations": session_doc.get("recommendations"),
        "spec": session_doc.get("spec"),
        "fact_report": session_doc.get("fact_report"),
    }
    if pipeline_result:
        summary["pipeline_result"] = {
            "success": pipeline_result.get("success"),
            "error": pipeline_result.get("error"),
            "total_rounds": pipeline_result.get("total_rounds"),
            "total_time": pipeline_result.get("total_time"),
            "final_score": pipeline_result.get("final_score"),
            "final_code_present": bool(pipeline_result.get("final_code")),
        }
    return summary


@tool
@register_tool(
    tool_id="start_external_skill_generation_session",
    name="启动 External Skill 生成会话",
    description="当 Nanobot 判断当前缺口是可复用能力时，启动真实的 SkillGenerationService 会话，而不是停在 temp 脚本。",
    category="external",
    is_online=True,
    auto_register=True,
    timeout_tier="medium",
    when_to_use="当现有能力缺失，但目标明显是可复用、可参数化的能力时使用，例如杜邦分析、估值子模块、财务比率分析。",
    when_not_to_use="当任务只是一次性调试、临时探测、短期数据核验时不要使用；那种情况应优先用 temp 脚本。",
    returns="返回 JSON 字符串，包含 session_id、AI 首轮需求沟通消息、清晰度判断，以及建议下一步。",
    example='start_external_skill_generation_session(description="创建一个可复用的 A 股杜邦分析 skill，输入 symbol，输出结构化三因素分解和趋势摘要")',
    related_tools=["respond_to_external_skill_generation_session", "preview_external_skill_spec", "generate_confirmed_external_skill", "inspect_external_skill_generation_session"],
    data_source_handling="local_only",
)
async def start_external_skill_generation_session(
    description: Annotated[str, "Skill 的自然语言需求描述，需明确这是一个可复用能力而不是一次性脚本"],
    handoff_context_json: Annotated[str, "可选 JSON 对象，补充上游交接上下文，例如原目标、保持的能力边界、禁止缩窄的约束"] = "",
) -> str:
    """启动 external skill 生成会话。"""
    try:
        clean_description = str(description or "").strip()
        if not clean_description:
            return _json_response({"status": "error", "message": "description 不能为空"})

        handoff_context = _parse_optional_json_dict(handoff_context_json, "handoff_context_json")
        service = _get_skill_generation_service()
        user_id = (get_current_user_id() or "").strip()
        start_result = await service.start_session(
            description=clean_description,
            user_id=user_id,
            handoff_context=handoff_context,
        )
        return _json_response({
            "status": "ok",
            "session_id": start_result.get("session_id"),
            "user_id": user_id or None,
            "description": clean_description,
            "handoff_context": handoff_context,
            "start_result": start_result,
            "recommended_next_step": _recommend_start_next_step(start_result),
            "available_next_steps": [
                "respond_to_external_skill_generation_session",
                "preview_external_skill_spec",
            ],
        })
    except Exception as exc:
        logger.error("启动 external skill 生成会话失败: %s", exc, exc_info=True)
        return _json_response({"status": "error", "message": f"启动 external skill 生成会话失败: {exc}"})


@tool
@register_tool(
    tool_id="respond_to_external_skill_generation_session",
    name="回复 External Skill 生成会话",
    description="继续回答 Skill 需求澄清问题，让 SkillGenerationService 把自然语言需求收敛成稳定的 SkillSpec。",
    category="external",
    is_online=True,
    auto_register=True,
    timeout_tier="medium",
    when_to_use="当已存在 skill 生成会话，且 AI 还在追问职责边界、输入输出、数据来源、非目标时使用。",
    when_not_to_use="当会话已经足够清晰并准备预览 spec 或确认生成时，不必重复调用。",
    returns="返回 JSON 字符串，包含 AI 新一轮回复、当前轮次和建议下一步。",
    example="respond_to_external_skill_generation_session(session_id='abc123', user_message='输入只要 symbol，输出结构化 JSON，不给交易建议')",
    related_tools=["start_external_skill_generation_session", "preview_external_skill_spec"],
    data_source_handling="local_only",
)
async def respond_to_external_skill_generation_session(
    session_id: Annotated[str, "已有 Skill 创建会话 ID"],
    user_message: Annotated[str, "对 Skill 需求澄清问题的回复"] = "确认按可复用能力来设计",
) -> str:
    """继续 external skill 需求沟通。"""
    try:
        clean_session_id = str(session_id or "").strip()
        clean_user_message = str(user_message or "").strip()
        if not clean_session_id:
            return _json_response({"status": "error", "message": "session_id 不能为空"})
        if not clean_user_message:
            return _json_response({"status": "error", "message": "user_message 不能为空"})

        service = _get_skill_generation_service()
        result = await service.respond_to_session(clean_session_id, clean_user_message)
        return _json_response({
            "status": "ok",
            "session_id": clean_session_id,
            "response": result,
            "recommended_next_step": _recommend_follow_up_next_step(result),
            "available_next_steps": [
                "respond_to_external_skill_generation_session",
                "preview_external_skill_spec",
            ],
        })
    except Exception as exc:
        logger.error("回复 external skill 生成会话失败: %s", exc, exc_info=True)
        return _json_response({"status": "error", "message": f"回复 external skill 生成会话失败: {exc}"})


@tool
@register_tool(
    tool_id="preview_external_skill_spec",
    name="预览 External Skill 规格",
    description="基于当前 skill 会话生成 SkillSpec 预览和侦察报告，用于确认这是不是正确的可复用能力形状。",
    category="external",
    is_online=True,
    auto_register=True,
    timeout_tier="heavy",
    when_to_use="当需求已基本明确，需要先看结构化 SkillSpec、参数、输出契约和侦察结论，再决定是否真正生成 skill 时使用。",
    when_not_to_use="当需求仍然明显模糊时，优先继续 respond_to_external_skill_generation_session。",
    returns="返回 JSON 字符串，包含 spec 预览、侦察 fact_report、推荐生成上下文，以及建议下一步。",
    example="preview_external_skill_spec(session_id='abc123')",
    related_tools=["respond_to_external_skill_generation_session", "generate_confirmed_external_skill"],
    data_source_handling="local_only",
)
async def preview_external_skill_spec(
    session_id: Annotated[str, "已有 Skill 创建会话 ID"],
    user_message: Annotated[str, "可选确认语，默认使用 确认"] = "确认",
) -> str:
    """预览 external skill 的 SkillSpec。"""
    try:
        clean_session_id = str(session_id or "").strip()
        if not clean_session_id:
            return _json_response({"status": "error", "message": "session_id 不能为空"})

        service = _get_skill_generation_service()
        preview = await service.preview_spec(clean_session_id, str(user_message or "确认").strip() or "确认")
        if not preview:
            return _json_response({"status": "error", "message": "未生成可用的 SkillSpec 预览"})
        return _json_response({
            "status": "ok",
            "session_id": clean_session_id,
            "preview": preview,
            "recommended_next_step": "generate_confirmed_external_skill",
            "available_next_steps": [
                "respond_to_external_skill_generation_session",
                "generate_confirmed_external_skill",
            ],
        })
    except Exception as exc:
        logger.error("预览 external skill 规格失败: %s", exc, exc_info=True)
        return _json_response({"status": "error", "message": f"预览 external skill 规格失败: {exc}"})


@tool
@register_tool(
    tool_id="generate_confirmed_external_skill",
    name="确认后生成 External Skill",
    description="在用户确认这确实是可复用能力后，调用真实的 SkillGenerationService 进入 external skill 生成管线。",
    category="external",
    is_online=True,
    auto_register=True,
    timeout_tier="heavy",
    when_to_use="当 spec 预览已经确认无误，且目标不是一次性 temp 脚本而是可复用 skill 时使用。",
    when_not_to_use="未确认前不要调用；也不适用于临时探测脚本。",
    returns="返回 JSON 字符串，包含生成任务的启动状态、spec 摘要和后续状态查询建议。",
    example="generate_confirmed_external_skill(session_id='abc123', confirmed=true)",
    related_tools=["preview_external_skill_spec", "inspect_external_skill_generation_session"],
    data_source_handling="local_only",
)
async def generate_confirmed_external_skill(
    session_id: Annotated[str, "已有 Skill 创建会话 ID"],
    confirmed: Annotated[bool, "是否已拿到用户对 SkillSpec 的明确确认"] = False,
    user_message: Annotated[str, "确认消息，默认使用 确认"] = "确认",
) -> str:
    """确认后触发 external skill 生成。"""
    try:
        clean_session_id = str(session_id or "").strip()
        if not clean_session_id:
            return _json_response({"status": "error", "message": "session_id 不能为空"})
        if not confirmed:
            return _json_response({
                "status": "error",
                "message": "未拿到用户明确确认，拒绝触发 external skill 生成。请先预览 spec 并确认。",
            })

        service = _get_skill_generation_service()
        result = await service.confirm_spec(clean_session_id, str(user_message or "确认").strip() or "确认")
        return _json_response({
            "status": "ok",
            "session_id": clean_session_id,
            "generation": result,
            "recommended_next_step": "inspect_external_skill_generation_session",
            "available_next_steps": ["inspect_external_skill_generation_session"],
        })
    except Exception as exc:
        logger.error("确认后生成 external skill 失败: %s", exc, exc_info=True)
        return _json_response({"status": "error", "message": f"确认后生成 external skill 失败: {exc}"})


@tool
@register_tool(
    tool_id="inspect_external_skill_generation_session",
    name="查看 External Skill 生成会话",
    description="查看 external skill 生成会话的当前状态、spec、侦察摘要和生成进度，便于跟踪异步生成结果。",
    category="external",
    is_online=True,
    auto_register=True,
    timeout_tier="light",
    when_to_use="当已触发 external skill 生成，或者需要查看当前会话处于 gathering、confirmed、generating、completed、failed 哪个阶段时使用。",
    when_not_to_use="如果只是继续补充需求，应使用 respond_to_external_skill_generation_session。",
    returns="返回 JSON 字符串，包含会话摘要、pipeline 阶段、spec 和推荐生成上下文。",
    example="inspect_external_skill_generation_session(session_id='abc123')",
    related_tools=["generate_confirmed_external_skill", "respond_to_external_skill_generation_session"],
    data_source_handling="local_only",
)
async def inspect_external_skill_generation_session(
    session_id: Annotated[str, "Skill 创建会话 ID"],
) -> str:
    """查看 external skill 生成会话状态。"""
    try:
        clean_session_id = str(session_id or "").strip()
        if not clean_session_id:
            return _json_response({"status": "error", "message": "session_id 不能为空"})

        service = _get_skill_generation_service()
        session_doc = await service.get_session(clean_session_id)
        if not session_doc:
            return _json_response({"status": "error", "message": f"会话 {clean_session_id} 不存在"})
        return _json_response({
            "status": "ok",
            "session": _summarize_session_doc(session_doc),
        })
    except Exception as exc:
        logger.error("查看 external skill 生成会话失败: %s", exc, exc_info=True)
        return _json_response({"status": "error", "message": f"查看 external skill 生成会话失败: {exc}"})