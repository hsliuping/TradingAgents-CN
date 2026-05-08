import asyncio


def test_screening_tool_returns_hard_no_match_message(monkeypatch):
    from core.tools.implementations.market import stock_screening_tool as tool_module

    class DummyScreeningService:
        async def screen_stocks(self, **kwargs):
            return [], 0

    async def fake_init_database():
        return None

    monkeypatch.setattr(tool_module, "asyncio", tool_module.asyncio)
    monkeypatch.setattr("app.services.database_screening_service.get_database_screening_service", lambda: DummyScreeningService())
    monkeypatch.setattr("app.core.database.init_database", fake_init_database)

    result = asyncio.run(tool_module._run_screening([], 20, "total_mv", "desc"))

    assert result == "未找到符合条件的股票。当前没有适合该筛选要求的标的，不要推荐其它不符合条件的股票。"


def test_system_prompt_forbids_recommending_other_stocks_on_empty_screening():
    from app.services.intelligent_assistant_service import _get_system_prompt

    prompt = _get_system_prompt()

    assert "未找到符合条件的股票" in prompt
    assert "严禁为了“给点参考”而推荐其它不符合筛选条件的股票" in prompt