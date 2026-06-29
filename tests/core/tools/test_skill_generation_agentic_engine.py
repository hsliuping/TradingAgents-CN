import json

import pytest

from app.services.skill_generation_service import SkillGenerationService, _store_skill_lessons
from core.tools.external import ExpectedOutput, GeneratedCode, PipelineResult, SkillCreationSession, SkillHandoffContext, SkillParameter, SkillSpec
from core.tools.external.recon_tools import probe_interface, run_readonly_query
from core.tools.external.sandbox_runner import SandboxRunner
from core.tools.external.static_validator import StaticValidator


def test_probe_interface_describes_runtime_helper_shape():
    raw = probe_interface(
        "external_sources.get_external_historical_data",
        {
            "symbol": "__invalid__",
            "start_date": "2024-01-01",
            "end_date": "2024-01-02",
            "source": "unknown_source",
        },
    )
    payload = json.loads(raw)

    assert payload["success"] is True
    assert payload["function"] == "get_external_historical_data"
    assert payload["shape"]["type"] == "dict"
    assert "data" in payload["shape"].get("keys", [])


def test_run_readonly_query_rejects_mongo_operators():
    raw = run_readonly_query(
        "stock_basic_info",
        {"symbol": {"$ne": "600519"}},
        {"_id": 0},
        1,
    )
    payload = json.loads(raw)

    assert payload["success"] is False
    assert "Mongo operators" in payload["error"]
    assert payload["metrics"]["call_count"] >= 1


def test_probe_interface_returns_rate_limit_metrics():
    raw = probe_interface(
        "external_sources.get_external_historical_data",
        {
            "symbol": "__invalid__",
            "start_date": "2024-01-01",
            "end_date": "2024-01-02",
            "source": "unknown_source",
        },
    )
    payload = json.loads(raw)

    assert payload["success"] is True
    assert "metrics" in payload
    assert payload["metrics"]["call_count"] >= 1
    assert "rate_limit_wait_ms" in payload["metrics"]


def test_static_validator_blocks_build_time_rpc_imports():
    spec = SkillSpec(
        tool_id="demo_skill",
        display_name="Demo Skill",
        description="demo",
        parameters=[SkillParameter(name="symbol")],
        expected_output=ExpectedOutput(type="dict", fields=[]),
    )
    code = GeneratedCode(
        code="""
from hermes_tools import run_readonly_query

def demo_skill(symbol: str):
    return {"ok": True}
""".strip()
    )

    result = StaticValidator().validate(code, spec)

    assert result.passed is False
    assert any("hermes_tools" in error for error in result.errors)


def test_diagnostic_sandbox_allows_hermes_tools_stub():
    runner = SandboxRunner(timeout=20)
    script = """
from hermes_tools import probe_interface
result = probe_interface(
    "external_sources.get_external_historical_data",
    {
        "symbol": "__invalid__",
        "start_date": "2024-01-01",
        "end_date": "2024-01-02",
        "source": "unknown_source",
    },
)
""".strip()

    result = runner.run_diagnostic_script(script)

    assert result.success is True
    assert result.output["tool_call_count"] == 1
    assert result.output["result"]["success"] is True
    assert result.output["result"]["function"] == "get_external_historical_data"


def test_apply_handoff_context_to_spec_preserves_full_summary():
    spec = SkillSpec(tool_id="demo_skill", display_name="Demo", description="demo")
    context = SkillHandoffContext(
        source="agent_studio_gap",
        source_spec_id="spec_001",
        source_name="估值 Agent",
        target_capability="行业对比",
        agent_goal="输出基本面分析",
        gap_context="缺少行业横向比较",
        searched_capabilities=["查过估值 Skill"],
        confirmed_data_sources=["external_sources.get_external_historical_data"],
        user_clarifications=["只需要客观数据，不输出建议"],
        related_gaps=["估值分位"],
        known_failure_summaries=["pe_ttm 字段不存在"],
        known_verified_facts=["helper 返回 OHLCV"],
    )

    SkillGenerationService._apply_handoff_context_to_spec(spec, context)

    summary = spec.metadata["handoff_context_summary"]
    assert summary["target_capability"] == "行业对比"
    assert summary["searched_capabilities"] == ["查过估值 Skill"]
    assert summary["confirmed_data_sources"] == ["external_sources.get_external_historical_data"]
    assert spec.metadata["known_failure_summaries"] == ["pe_ttm 字段不存在"]
    assert spec.metadata["known_verified_facts"] == ["helper 返回 OHLCV"]


@pytest.mark.asyncio
async def test_store_skill_lessons_persists_agentic_failure_and_facts(monkeypatch):
    stored = {}

    class _FakeMemoryService:
        async def store(self, messages, agent_id, scope, metadata):
            stored["messages"] = messages
            stored["agent_id"] = agent_id
            stored["scope"] = scope
            stored["metadata"] = metadata

    monkeypatch.setattr(
        "core.memory.service.get_memory_service",
        lambda db: _FakeMemoryService(),
    )
    spec = SkillSpec(
        tool_id="demo_skill",
        display_name="Demo Skill",
        description="demo",
        category="fundamentals",
        data_source="local",
    )
    result = PipelineResult(
        success=False,
        tool_id="demo_skill",
        error="字段 pe_ttm 不存在",
        final_metadata={
            "generation_engine": "agentic_loop",
            "verified_facts": ["valuation helper 返回 pb_mrq"],
        },
        total_rounds=1,
    )

    await _store_skill_lessons(object(), spec, result)

    assert stored["agent_id"] == "skill_generator"
    assert stored["scope"] == "skill_lesson"
    assert stored["metadata"]["generation_engine"] == "agentic_loop"
    assert stored["metadata"]["verified_fact_count"] == 1
    assert "字段 pe_ttm 不存在" in stored["messages"][0]["content"]
    assert "valuation helper 返回 pb_mrq" in stored["messages"][0]["content"]


def test_skill_generation_infers_role_metadata_for_gap_skill():
    spec = SkillSpec(
        tool_id="get_financial_cashflow_quality_trend",
        display_name="现金流质量趋势",
        description="计算经营现金流/净利润、自由现金流率等现金流质量指标趋势",
        category="fundamentals",
        data_source="tushare",
        expected_output=ExpectedOutput(
            type="dict",
            fields=["ocf_to_net_profit", "fcf_margin", "quality_score"],
            description="返回结构化现金流质量指标",
        ),
    )
    session = SkillCreationSession(
        session_id="skill_session_001",
        user_id="u1",
        handoff_context=SkillHandoffContext(
            source="agent_studio_gap",
            target_capability="缺少现金流质量指标自动计算能力",
        ),
    )

    metadata = SkillGenerationService._infer_skill_role_metadata(spec, session)

    assert metadata["tool_role_hint"] == "specialized"
    assert metadata["output_shape"] == "structured_metrics"
    assert "cashflow_quality" in metadata["capability_tags"]
    assert "cashflow_quality_analysis" in metadata["preferred_for"]


def test_skill_generation_infers_supporting_role_for_report_skill():
    spec = SkillSpec(
        tool_id="generate_financial_summary_report",
        display_name="财务摘要报告",
        description="生成 Markdown 财务摘要报告",
        category="fundamentals",
        expected_output=ExpectedOutput(type="string", fields=[], description="Markdown 报告"),
    )
    session = SkillCreationSession(session_id="skill_session_002", user_id="u1")

    metadata = SkillGenerationService._infer_skill_role_metadata(spec, session)

    assert metadata["tool_role_hint"] == "supporting"
    assert metadata["output_shape"] == "report"
    assert "primary_capability" in metadata["not_replacement_for"]
