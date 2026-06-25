import pytest

from app.services.intelligent_assistant_service import (
    _extract_memory_metadata_filters,
    _recall_memory_block,
)


class _FakeMemoryService:
    def __init__(self, response: str):
        self.response = response
        self.calls = []

    async def recall_formatted(self, **kwargs):
        self.calls.append(kwargs)
        return self.response


class _FakeProjectMemoryService:
    def __init__(self, response: str):
        self.response = response
        self.calls = []

    async def build_prompt_block(self, **kwargs):
        self.calls.append(kwargs)
        return self.response


def test_extract_memory_metadata_filters_reads_symbol_from_topic_title() -> None:
    assert _extract_memory_metadata_filters("贵州茅台(600519) 分析报告") == {"symbol": "600519"}
    assert _extract_memory_metadata_filters("腾讯控股(HK.00700) 分析报告") == {"symbol": "HK.00700"}
    assert _extract_memory_metadata_filters("宏观策略讨论") is None


def test_extract_memory_metadata_filters_falls_back_to_report_refs() -> None:
    assert _extract_memory_metadata_filters(
        "宏观策略讨论",
        report_refs=[{"symbol": "sz.000001"}, {"symbol": "600519"}],
    ) == {"symbol": "SZ.000001"}


@pytest.mark.asyncio
async def test_recall_memory_block_passes_symbol_metadata_filters(monkeypatch):
    fake_memory_service = _FakeMemoryService("memory block")

    monkeypatch.setattr("core.memory.service.get_memory_service", lambda db: fake_memory_service)

    result = await _recall_memory_block(
        db=object(),
        user_id="user-1",
        user_message="帮我回顾一下这个标的之前的分析结论",
        current_topic_title="贵州茅台(600519) 分析报告",
    )

    assert result == "memory block"
    assert len(fake_memory_service.calls) == 1
    call = fake_memory_service.calls[0]
    assert call["metadata_filters"] == {"symbol": "600519"}
    assert call["scopes"] == ["conversation", "user_preference", "analysis_insight", "trade_pattern"]


@pytest.mark.asyncio
async def test_recall_memory_block_skips_metadata_filters_without_symbol(monkeypatch):
    fake_memory_service = _FakeMemoryService("memory block")

    monkeypatch.setattr("core.memory.service.get_memory_service", lambda db: fake_memory_service)

    await _recall_memory_block(
        db=object(),
        user_id="user-1",
        user_message="总结一下我最近的偏好",
        current_topic_title="宏观策略讨论",
    )

    assert len(fake_memory_service.calls) == 1
    assert fake_memory_service.calls[0]["metadata_filters"] is None


@pytest.mark.asyncio
async def test_recall_memory_block_uses_report_ref_symbol_when_title_has_no_symbol(monkeypatch):
    fake_memory_service = _FakeMemoryService("memory block")

    monkeypatch.setattr("core.memory.service.get_memory_service", lambda db: fake_memory_service)

    await _recall_memory_block(
        db=object(),
        user_id="user-1",
        user_message="回顾这个主题的历史分析",
        current_topic_title="宏观策略讨论",
        report_refs=[{"symbol": "hk.00700", "title": "腾讯控股(HK.00700) 分析报告"}],
    )

    assert len(fake_memory_service.calls) == 1
    assert fake_memory_service.calls[0]["metadata_filters"] == {"symbol": "HK.00700"}


@pytest.mark.asyncio
async def test_recall_memory_block_combines_project_memory_with_mem0(monkeypatch):
    fake_memory_service = _FakeMemoryService("【历史偏好】\n- 偏好先看结论")
    fake_project_memory_service = _FakeProjectMemoryService("【项目长期记忆】\n- 输出约束\n  - 回答结构：先给结论")

    monkeypatch.setattr("core.memory.service.get_memory_service", lambda db: fake_memory_service)
    monkeypatch.setattr(
        "app.services.project_memory_service.get_project_memory_service",
        lambda db: fake_project_memory_service,
    )

    result = await _recall_memory_block(
        db=object(),
        user_id="user-1",
        user_message="继续这个主题",
        current_topic_title="宏观策略讨论",
    )

    assert "【项目长期记忆】" in result
    assert "【历史偏好】" in result
    assert len(fake_project_memory_service.calls) == 1
    assert fake_project_memory_service.calls[0]["max_items"] == 4