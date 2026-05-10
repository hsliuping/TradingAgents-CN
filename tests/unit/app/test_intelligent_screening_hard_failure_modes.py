import asyncio
from types import SimpleNamespace


class DummyTimeoutClient:
    async def achat(self, *args, **kwargs):
        await asyncio.sleep(0.05)


class DummyNoMatchClient:
    async def achat(self, *args, **kwargs):
        tools_used = kwargs.get("tools_used")
        if isinstance(tools_used, list):
            tools_used.append("screen_stocks_by_criteria")
        return SimpleNamespace(content="本轮筛选未返回结构化股票结果。")


def test_run_direct_screening_returns_hard_timeout_without_fallback(monkeypatch):
    from app.services import intelligent_screening_service as service_module

    async def _ok():
        return True

    monkeypatch.setattr(service_module, "SCREENING_RESULT_TIMEOUT_SECONDS", 0)
    monkeypatch.setattr(service_module, "set_current_user_id", lambda user_id: None)

    service = service_module.IntelligentScreeningService(db=object())
    service._ensure_client = _ok
    service._llm_client = DummyTimeoutClient()
    service._result_openai_tools = []

    result = asyncio.run(service.run_direct_screening("user-1", "高分红低估值", max_stocks=5))

    assert result["stocks"] == []
    assert "超时" in result["reply"]
    assert "不会改为推荐其它不符合原筛选条件的股票" in result["reply"]
    assert result.get("is_fallback") is not True


def test_run_direct_screening_returns_hard_no_match_without_fallback(monkeypatch):
    from app.services import intelligent_screening_service as service_module

    async def _ok():
        return True

    monkeypatch.setattr(service_module, "set_current_user_id", lambda user_id: None)

    service = service_module.IntelligentScreeningService(db=object())
    service._ensure_client = _ok
    service._llm_client = DummyNoMatchClient()
    service._result_openai_tools = []

    result = asyncio.run(service.run_direct_screening("user-1", "高分红低估值", max_stocks=5))

    assert result["stocks"] == []
    assert "未找到符合“高分红”条件的股票" in result["reply"]
    assert "不推荐其它不符合条件的股票" in result["reply"]
    assert result.get("is_fallback") is not True