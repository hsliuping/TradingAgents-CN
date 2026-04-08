import pytest

from app.services.skill_generation_service import (
    _build_skill_memory_metadata_filters,
    _recall_skill_lessons,
)
from core.tools.external import SkillSpec


class _FakeMemoryService:
    def __init__(self, response: str):
        self.response = response
        self.calls = []

    async def recall_formatted(self, **kwargs):
        self.calls.append(kwargs)
        return self.response


def test_build_skill_memory_metadata_filters_prefers_category_and_data_source() -> None:
    spec = SkillSpec(
        tool_id="get_stock_news",
        display_name="个股新闻",
        description="获取个股新闻列表",
        category="news",
        data_source="eastmoney",
    )

    assert _build_skill_memory_metadata_filters(spec) == {
        "category": "news",
        "data_source": "eastmoney",
    }


def test_build_skill_memory_metadata_filters_falls_back_to_tool_id() -> None:
    spec = SkillSpec(
        tool_id="get_custom_payload",
        display_name="自定义载荷",
        description="生成自定义载荷",
        category="",
        data_source="",
    )

    assert _build_skill_memory_metadata_filters(spec) == {"tool_id": "get_custom_payload"}


@pytest.mark.asyncio
async def test_recall_skill_lessons_passes_metadata_filters(monkeypatch):
    fake_memory_service = _FakeMemoryService("skill lessons")
    spec = SkillSpec(
        tool_id="get_stock_news",
        display_name="个股新闻",
        description="获取个股新闻列表",
        category="news",
        data_source="eastmoney",
    )

    monkeypatch.setattr("core.memory.service.get_memory_service", lambda db: fake_memory_service)

    result = await _recall_skill_lessons(object(), spec)

    assert result == "skill lessons"
    assert len(fake_memory_service.calls) == 1
    call = fake_memory_service.calls[0]
    assert call["agent_id"] == "skill_generator"
    assert call["scopes"] == ["skill_lesson"]
    assert call["metadata_filters"] == {
        "category": "news",
        "data_source": "eastmoney",
    }