"""Validate L4 project-memory checks inside Agent Workshop production-review."""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from typing import Any, Dict


ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.models.agent_workshop import AgentSpec, AgentSpecStatus, AgentVersion, AgentVersionStatus
from app.services.agent_workshop_service import AgentWorkshopService


class _FakeDb:
    def __getitem__(self, name):
        raise KeyError(name)

    def __getattr__(self, name):
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


def _build_version():
    return AgentVersion(
        version_id="spec_valuation_candidate_v1_v1",
        spec_id="spec_valuation_candidate_v1",
        version=1,
        status=AgentVersionStatus.TESTING,
        agent_metadata={
            "id": "spec_valuation_candidate_v1_v1",
            "name": "A股估值分析师 v1",
            "description": "输出A股估值结论",
            "version": "0.1.0",
            "output_field": "valuation_report",
        },
        prompt_template_ref={"template_id": "tpl_spec_valuation_candidate_v1_v1"},
        required_tools=["get_value_factor_bundle_tool"],
        required_capabilities=["valuation"],
        output_schema={"properties": {"valuation_report": {"type": "string"}}},
        evaluation_policy={"minimum_score": 0.75},
        published_from_session_id="session_valuation_001",
    )


async def validate_all() -> Dict[str, Any]:
    svc = AgentWorkshopService(_FakeDb())

    async def _fake_llm_review(_version, _spec, _runtime_result, user_feedback="", rule_details=None):
        del _version, _spec, _runtime_result, user_feedback, rule_details
        return {"summary": "advisory", "scores": {}, "issues": [], "recommendations": []}

    async def _fake_build_project_memory_block():
        return "【项目长期记忆】\n- 项目规则\n  - 禁止直接投资建议：所有分析只提供研究与学习参考。"

    svc._judge_runtime_result_with_llm = _fake_llm_review
    svc._build_project_memory_block_for_workshop = _fake_build_project_memory_block

    spec = _build_spec()
    version = _build_version()

    valid_scores, valid_issues, _valid_recommendations, valid_details = await svc._evaluate_runtime_result(
        version,
        spec,
        {
            "output_text": "已输出 valuation_report，并附带依据、假设与风险。",
            "output_payload": {"valuation_report": "ok"},
            "debug_prompt": {
                "system_prompt": "你是估值分析师。\n【项目长期记忆】\n- 项目规则\n  - 禁止直接投资建议：所有分析只提供研究与学习参考。",
                "user_prompt": "user",
                "tool_trace": [{"tool_name": "get_value_factor_bundle_tool", "success": True}],
            },
        },
    )

    missing_binding_scores, missing_binding_issues, _missing_binding_recommendations, missing_binding_details = await svc._evaluate_runtime_result(
        version,
        spec,
        {
            "output_text": "已输出 valuation_report，并附带依据、假设与风险。",
            "output_payload": {"valuation_report": "ok"},
            "debug_prompt": {
                "system_prompt": "你是估值分析师。请输出研究结论。",
                "user_prompt": "user",
                "tool_trace": [{"tool_name": "get_value_factor_bundle_tool", "success": True}],
            },
        },
    )

    missing_prompt_scores, missing_prompt_issues, _missing_prompt_recommendations, missing_prompt_details = await svc._evaluate_runtime_result(
        version,
        spec,
        {
            "output_text": "已输出 valuation_report，并附带依据、假设与风险。",
            "output_payload": {"valuation_report": "ok"},
            "debug_prompt": {
                "user_prompt": "user",
                "tool_trace": [{"tool_name": "get_value_factor_bundle_tool", "success": True}],
            },
        },
    )

    del valid_scores, missing_binding_scores, missing_prompt_scores, valid_issues, missing_prompt_issues

    checks = {
        "runtime_prompt_accepts_current_l4": valid_details["project_memory_binding"]["valid"] is True,
        "runtime_prompt_missing_l4_revises_review": missing_binding_details["layered_review"]["publish_readiness"]["decision"] == "revise",
        "runtime_prompt_missing_l4_records_issue": any(
            "system_prompt 没有完整包含当前 L4 项目长期记忆" in item
            for item in missing_binding_issues
        ),
        "missing_system_prompt_marks_evidence_incomplete": missing_prompt_details["evaluation_valid"] is False,
        "missing_system_prompt_records_invalid_reason": "缺少 runtime system_prompt 证据，无法确认当前 L4 项目长期记忆是否真实注入。" in missing_prompt_details["evidence_bundle"]["invalid_reasons"],
    }
    return {
        "ok": all(checks.values()),
        "checks": checks,
        "valid_details": valid_details,
        "missing_binding_details": missing_binding_details,
        "missing_prompt_details": missing_prompt_details,
    }


def main() -> int:
    summary = asyncio.run(validate_all())
    status = "PASS" if summary["ok"] else "FAIL"
    print(f"[{status}] agent workshop production review project memory loop")
    for check, ok in summary["checks"].items():
        check_status = "PASS" if ok else "FAIL"
        print(f"- [{check_status}] {check}")
    print(summary)
    return 0 if summary["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())