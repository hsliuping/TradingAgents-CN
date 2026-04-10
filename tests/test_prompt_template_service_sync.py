from datetime import datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from bson import ObjectId

from app.models.prompt_template import PromptTemplateCreate, TemplateContent
from app.services.prompt_template_service import PromptTemplateService


def _build_template_data(template_name: str = "市场分析师 v2.0 - 中性型") -> PromptTemplateCreate:
    return PromptTemplateCreate(
        agent_type="analysts_v2",
        agent_name="market_analyst_v2",
        template_name=template_name,
        preference_type="neutral",
        content=TemplateContent(
            system_prompt="system prompt",
            user_prompt="user prompt",
            tool_guidance="tool guidance",
            analysis_requirements="analysis requirements",
            output_format="markdown",
            constraints="no execution",
        ),
        remark="系统模板",
        status="active",
    )


def _build_service(existing_docs):
    db = MagicMock()
    templates_collection = MagicMock()
    history_collection = MagicMock()
    cursor = MagicMock()
    cursor.to_list = AsyncMock(return_value=existing_docs)
    templates_collection.find.return_value = cursor
    templates_collection.update_one = AsyncMock(return_value=SimpleNamespace(upserted_id=ObjectId()))
    templates_collection.find_one = AsyncMock(return_value=None)
    history_collection.insert_one = AsyncMock(return_value=None)
    db.prompt_templates = templates_collection
    db.template_history = history_collection

    service = PromptTemplateService(db=db)
    service._record_history = AsyncMock(return_value=None)
    return service, templates_collection


@pytest.mark.asyncio
async def test_upsert_system_template_creates_new_document() -> None:
    service, templates_collection = _build_service(existing_docs=[])
    created_id = ObjectId()
    templates_collection.update_one.return_value = SimpleNamespace(upserted_id=created_id)
    service.get_template = AsyncMock(return_value=SimpleNamespace(id=str(created_id)))

    result, operation = await service.upsert_system_template(
        _build_template_data(),
        remark_suffix="[2026-04-11] 幂等同步 v2.0 系统模板",
    )

    assert result is not None
    assert operation == "created"
    templates_collection.update_one.assert_awaited_once()
    update_query, update_doc = templates_collection.update_one.await_args.args[:2]
    assert update_query == {
        "agent_type": "analysts_v2",
        "agent_name": "market_analyst_v2",
        "preference_type": "neutral",
        "is_system": True,
    }
    assert "created_at" not in update_doc["$set"]
    assert update_doc["$set"]["is_system"] is True
    assert update_doc["$set"]["created_by"] is None
    assert update_doc["$set"]["version"] == 1
    assert "幂等同步 v2.0 系统模板" in update_doc["$set"]["remark"]
    assert "created_at" in update_doc["$setOnInsert"]
    service._record_history.assert_awaited_once()


@pytest.mark.asyncio
async def test_upsert_system_template_updates_existing_document_without_touching_created_at() -> None:
    existing_id = ObjectId()
    existing_created_at = datetime(2026, 4, 10, 8, 0, 0)
    existing_doc = {
        "_id": existing_id,
        "agent_type": "analysts_v2",
        "agent_name": "market_analyst_v2",
        "preference_type": "neutral",
        "template_name": "旧模板",
        "content": {"system_prompt": "old"},
        "remark": "旧备注",
        "status": "active",
        "is_system": True,
        "created_by": None,
        "version": 3,
        "created_at": existing_created_at,
    }
    service, templates_collection = _build_service(existing_docs=[existing_doc])
    service.get_template = AsyncMock(return_value=SimpleNamespace(id=str(existing_id)))

    result, operation = await service.upsert_system_template(
        _build_template_data(template_name="新模板"),
        remark_suffix="[2026-04-11] 幂等同步 v2.0 系统模板",
    )

    assert result is not None
    assert operation == "updated"
    update_query, update_doc = templates_collection.update_one.await_args.args[:2]
    assert update_query == {"_id": existing_id}
    assert "created_at" not in update_doc["$set"]
    assert update_doc["$setOnInsert"]["created_at"] == existing_created_at
    assert update_doc["$set"]["version"] == 4
    service._record_history.assert_awaited_once()


@pytest.mark.asyncio
async def test_upsert_system_template_returns_unchanged_for_identical_document() -> None:
    template_data = _build_template_data()
    existing_id = ObjectId()
    existing_doc = {
        "_id": existing_id,
        "agent_type": template_data.agent_type,
        "agent_name": template_data.agent_name,
        "preference_type": template_data.preference_type,
        "template_name": template_data.template_name,
        "content": template_data.content.model_dump(),
        "remark": template_data.remark,
        "status": template_data.status,
        "is_system": True,
        "created_by": None,
        "version": 2,
    }
    service, templates_collection = _build_service(existing_docs=[existing_doc])
    service.get_template = AsyncMock(return_value=SimpleNamespace(id=str(existing_id)))

    result, operation = await service.upsert_system_template(template_data)

    assert result is not None
    assert operation == "unchanged"
    templates_collection.update_one.assert_not_called()
    service._record_history.assert_not_called()


@pytest.mark.asyncio
async def test_upsert_system_template_refuses_duplicate_active_system_templates() -> None:
    duplicate_docs = [
        {"_id": ObjectId(), "agent_type": "analysts_v2", "agent_name": "market_analyst_v2", "preference_type": "neutral", "is_system": True},
        {"_id": ObjectId(), "agent_type": "analysts_v2", "agent_name": "market_analyst_v2", "preference_type": "neutral", "is_system": True},
    ]
    service, templates_collection = _build_service(existing_docs=duplicate_docs)
    service.get_template = AsyncMock(return_value=None)

    result, operation = await service.upsert_system_template(_build_template_data())

    assert result is None
    assert operation == "conflict"
    templates_collection.update_one.assert_not_called()
    service._record_history.assert_not_called()