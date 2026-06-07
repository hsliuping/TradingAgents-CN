from datetime import datetime

import pytest

from app.models.analysis import AnalysisParameters, SingleAnalysisRequest
from app.services.simple_analysis_service import SimpleAnalysisService


def _request(agent_engine: str = "codex") -> SingleAnalysisRequest:
    return SingleAnalysisRequest(
        symbol="000001",
        parameters=AnalysisParameters(
            market_type="A股",
            analysis_date=datetime(2026, 6, 6),
            research_depth="标准",
            selected_analysts=["market", "fundamentals"],
            agent_engine=agent_engine,
        ),
    )


def test_codex_agent_engine_is_selected():
    service = SimpleAnalysisService()

    assert service._get_agent_engine(_request("codex")) == "codex"
    assert service._get_agent_engine(_request("codex_agent")) == "codex"
    assert service._get_agent_engine(_request("tradingagents")) == "tradingagents"


def test_codex_bridge_requires_explicit_configuration(monkeypatch):
    service = SimpleAnalysisService()
    monkeypatch.delenv("CODEX_AGENT_ENDPOINT", raising=False)
    monkeypatch.delenv("CODEX_AGENT_COMMAND", raising=False)

    with pytest.raises(RuntimeError, match="CODEX_AGENT_ENDPOINT"):
        service._invoke_codex_agent_bridge("prompt", {"task_id": "task-1"})


def test_codex_agent_capability_reports_unconfigured(monkeypatch):
    service = SimpleAnalysisService()
    monkeypatch.delenv("CODEX_AGENT_ENDPOINT", raising=False)
    monkeypatch.delenv("CODEX_AGENT_COMMAND", raising=False)

    capabilities = service.get_agent_engine_capabilities()
    codex = next(engine for engine in capabilities["engines"] if engine["id"] == "codex")

    assert capabilities["default_engine"] == "tradingagents"
    assert codex["available"] is False
    assert codex["configured"] is False
    assert "CODEX_AGENT_ENDPOINT" in codex["reason"]


def test_codex_agent_request_is_rejected_when_unconfigured(monkeypatch):
    service = SimpleAnalysisService()
    monkeypatch.delenv("CODEX_AGENT_ENDPOINT", raising=False)
    monkeypatch.delenv("CODEX_AGENT_COMMAND", raising=False)

    error = service.validate_agent_engine_request(_request("codex"))

    assert error is not None
    assert "平台多智能体" in error


def test_codex_endpoint_must_be_reachable_to_be_available(monkeypatch):
    service = SimpleAnalysisService()
    monkeypatch.setenv("CODEX_AGENT_ENDPOINT", "http://127.0.0.1:8787/analyze")
    monkeypatch.delenv("CODEX_AGENT_COMMAND", raising=False)
    monkeypatch.setattr(service, "_codex_agent_endpoint_healthy", lambda endpoint, timeout=2: False)

    capabilities = service.get_agent_engine_capabilities()
    codex = next(engine for engine in capabilities["engines"] if engine["id"] == "codex")

    assert codex["configured"] is True
    assert codex["available"] is False
    assert "无法连接" in codex["reason"]
    assert service.validate_agent_engine_request(_request("codex")) is not None


def test_codex_endpoint_health_allows_codex_requests(monkeypatch):
    service = SimpleAnalysisService()
    monkeypatch.setenv("CODEX_AGENT_ENDPOINT", "http://127.0.0.1:8787/analyze")
    monkeypatch.delenv("CODEX_AGENT_COMMAND", raising=False)
    monkeypatch.setattr(service, "_codex_agent_endpoint_healthy", lambda endpoint, timeout=2: True)

    capabilities = service.get_agent_engine_capabilities()
    codex = next(engine for engine in capabilities["engines"] if engine["id"] == "codex")

    assert codex["configured"] is True
    assert codex["available"] is True
    assert service.validate_agent_engine_request(_request("codex")) is None


def test_tradingagents_request_does_not_require_codex_bridge(monkeypatch):
    service = SimpleAnalysisService()
    monkeypatch.delenv("CODEX_AGENT_ENDPOINT", raising=False)
    monkeypatch.delenv("CODEX_AGENT_COMMAND", raising=False)

    assert service.validate_agent_engine_request(_request("tradingagents")) is None


def test_codex_response_is_normalized_to_platform_result():
    service = SimpleAnalysisService()
    result = service._normalize_codex_agent_response(
        task_id="task-1",
        request=_request(),
        response={
            "content": "# 核心结论\n建议持有，当前信息不足以支持激进买入。\n\n## 风险因素\n中等风险。",
            "tokens_used": 42,
        },
        analysis_date="2026-06-06",
        execution_time=1.25,
    )

    assert result["agent_engine"] == "codex"
    assert result["stock_code"] == "000001"
    assert result["decision"]["action"] == "持有"
    assert result["tokens_used"] == 42
    assert "codex_agent_report" in result["reports"]
    assert result["state"]["agent_engine"] == "codex"
