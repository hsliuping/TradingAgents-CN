import asyncio
from types import SimpleNamespace


class DummyTimeoutClient:
    async def achat(self, *args, **kwargs):
        await asyncio.sleep(0.05)


class DummyNoMatchClient:
    async def achat(self, *args, **kwargs):
        return SimpleNamespace(
            content=(
                "### 工具调用\n"
                "**步骤 1**：调用 `screen_stocks_by_criteria`\n"
                "- `conditions`: `[{\"field\": \"dividend_yield\", \"operator\": \">=\", \"value\": 5}]`\n"
                "- `limit`: 10\n"
                '- `order_by_field`: "dividend_yield"\n'
                '- `order_direction`: "desc"\n'
            )
        )


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

    async def fake_run_locked_result_execution(self, message, locked_plan, progress_callback=None):
        return "本轮筛选未返回结构化股票结果。", ["screen_stocks_by_criteria"], []

    service = service_module.IntelligentScreeningService(db=object())
    service._ensure_client = _ok
    service._llm_client = DummyNoMatchClient()
    service._result_openai_tools = []
    monkeypatch.setattr(service_module.IntelligentScreeningService, "_run_locked_result_execution", fake_run_locked_result_execution)

    result = asyncio.run(service.run_direct_screening("user-1", "高分红低估值", max_stocks=5))

    assert result["stocks"] == []
    assert "未找到符合“高分红”条件的股票" in result["reply"]
    assert "不推荐其它不符合条件的股票" in result["reply"]
    assert result.get("is_fallback") is not True


def test_run_direct_screening_builds_structured_stocks_via_locked_execution(monkeypatch):
    from app.services import intelligent_screening_service as service_module

    async def _ok():
        return True

    class DummyPlanningClient:
        async def achat(self, messages, tools=None, **kwargs):
            assert tools is None
            return SimpleNamespace(
                content=(
                    "### 工具调用\n"
                    "**步骤 1**：调用 `screen_stocks_by_criteria`\n"
                    "- `conditions`: `[{\"field\": \"dividend_yield\", \"operator\": \">=\", \"value\": 5}, {\"field\": \"pe_ttm\", \"operator\": \"<=\", \"value\": 15}]`\n"
                    "- `limit`: 10\n"
                    '- `order_by_field`: "dividend_yield"\n'
                    '- `order_direction`: "desc"\n'
                )
            )

    monkeypatch.setattr(service_module, "set_current_user_id", lambda user_id: None)

    async def fake_run_locked_result_execution(self, message, locked_plan, progress_callback=None):
        assert message == "高分红低估值"
        assert locked_plan["screen"]["limit"] == 5
        return (
            "已按批准的筛选方案执行完成。\n\n```json\n"
            '{"stocks": [{"code": "002818", "name": "富森美", "pe": 11.36, "pe_display_label": "PE(TTM)", "pb": 1.51, "pb_display_label": "PB", "reason": "符合已批准条件"}]}'
            "\n```",
            ["screen_stocks_by_criteria"],
            [{
                "code": "002818",
                "name": "富森美",
                "industry": "商业贸易",
                "pe": 11.36,
                "pe_display_label": "PE(TTM)",
                "pb": 1.51,
                "pb_display_label": "PB",
                "reason": "符合已批准条件",
            }],
        )

    service = service_module.IntelligentScreeningService(db=object())
    service._ensure_client = _ok
    service._llm_client = DummyPlanningClient()
    service._result_openai_tools = []
    monkeypatch.setattr(service_module.IntelligentScreeningService, "_run_locked_result_execution", fake_run_locked_result_execution)

    result = asyncio.run(service.run_direct_screening("user-1", "高分红低估值", max_stocks=5))

    assert result["phase"] == "result"
    assert result["stocks"][0]["code"] == "002818"
    assert result["stocks"][0]["pe"] == 11.36
    assert result["stocks"][0]["pe_display_label"] == "PE(TTM)"
    assert result.get("is_fallback") is False