import json

import pytest

from app.models.capability_index import CapabilityDocument, CapabilitySearchHit
from core.agents.config import AgentCategory, AgentInput, AgentMetadata, AgentOutput, LicenseTier
from core.tools.implementations.agent_builder.nanobot_agent_builder_tools import (
    bind_agent_tools_and_validate_candidate,
    create_or_update_agent_workshop_draft,
    create_or_update_runtime_agent_config,
    create_or_update_universal_agent_prompt_template,
    generate_confirmed_candidate_agent,
    get_agent_blueprint_details,
    inspect_agent_blueprints,
    inspect_agent_workshop_assets,
    inspect_runtime_agent_configs,
    prepare_agent_requirement_intake,
    prepare_agent_generation_confirmation,
    search_project_capabilities,
)


class _FakeCapabilityService:
    def __init__(self, db):
        self.db = db

    async def search_capabilities(self, query, top_k, bindable_only, source_types):
        assert query == "A股估值"
        assert top_k == 5
        assert bindable_only is True
        assert source_types == ["builtin_tool", "skill"]
        return [
            CapabilitySearchHit(
                capability=CapabilityDocument(
                    capability_id="get_value_factor_bundle_tool",
                    registry_tool_id="get_value_factor_bundle_tool",
                    source_type="builtin_tool",
                    category="fundamentals",
                    name="价值因子包",
                    description="估值因子集合",
                    when_to_use="估值分析",
                    returns="JSON",
                    related_tools=["get_fundamental_factor_snapshot_tool"],
                    coverage_terms=["估值", "PE", "PB"],
                    data_source="local",
                    metadata={"parameters": [{"name": "symbol"}]},
                    bindable=True,
                ),
                score=0.91,
            )
        ]


class _FakeRegistry:
    def __init__(self, items):
        self._items = {item.id: item for item in items}

    def list_all(self):
        return list(self._items.values())

    def get_metadata(self, agent_id):
        return self._items.get(agent_id)


class _FakeCursor:
    def __init__(self, items):
        self._items = list(items)

    def sort(self, key, direction):
        reverse = direction == -1
        self._items.sort(key=lambda item: item.get(key) or "", reverse=reverse)
        return self

    async def to_list(self, length=None):
        if length is None:
            return list(self._items)
        return list(self._items[:length])


class _FakeCollection:
    def __init__(self, items):
        self._items = list(items)
        self._next_id = len(self._items) + 1

    def _match(self, item, query):
        query = query or {}
        for key, expected in query.items():
            value = item.get(key)
            if isinstance(expected, dict):
                if "$ne" in expected:
                    if value == expected["$ne"]:
                        return False
                    continue
            if value != expected:
                return False
        return True

    def find(self, query=None, projection=None):
        filtered = []
        for item in self._items:
            if self._match(item, query):
                filtered.append(item)
        return _FakeCursor(filtered)

    async def find_one(self, query=None, projection=None, sort=None):
        results = self.find(query, projection)
        if sort:
            for key, direction in reversed(sort):
                results.sort(key, direction)
        items = await results.to_list(length=1)
        return items[0] if items else None

    async def update_one(self, query, update, upsert=False):
        target = None
        for item in self._items:
            if self._match(item, query):
                target = item
                break
        if target is None and upsert:
            target = dict(query)
            if "_id" not in target:
                target["_id"] = f"fake_{self._next_id}"
                self._next_id += 1
            self._items.append(target)
        if target is None:
            return None
        if "$set" in update:
            for key, value in update["$set"].items():
                current = target
                parts = key.split(".")
                for part in parts[:-1]:
                    current = current.setdefault(part, {})
                current[parts[-1]] = value
        if "$inc" in update:
            for key, value in update["$inc"].items():
                target[key] = int(target.get(key) or 0) + value
        return None

    async def insert_one(self, doc):
        inserted = dict(doc)
        inserted.setdefault("_id", f"fake_{self._next_id}")
        self._next_id += 1
        self._items.append(inserted)
        return type("InsertOneResult", (), {"inserted_id": inserted["_id"]})()

    async def insert_many(self, docs):
        ids = []
        for doc in docs:
            inserted = dict(doc)
            inserted.setdefault("_id", f"fake_{self._next_id}")
            self._next_id += 1
            self._items.append(inserted)
            ids.append(inserted["_id"])
        return type("InsertManyResult", (), {"inserted_ids": ids})()

    async def delete_many(self, query):
        self._items = [item for item in self._items if not self._match(item, query)]
        return None


class _FakeDb:
    def __init__(self, collections):
        self._collections = collections

    def __getattr__(self, name):
        try:
            return self._collections[name]
        except KeyError as exc:
            raise AttributeError(name) from exc

    def __getitem__(self, name):
        return self._collections[name]


def _build_agent(agent_id: str, name: str, description: str, tags: list[str], tools: list[str]) -> AgentMetadata:
    return AgentMetadata(
        id=agent_id,
        name=name,
        description=description,
        category=AgentCategory.ANALYST,
        license_tier=LicenseTier.FREE,
        tags=tags,
        tools=tools,
        default_tools=tools[:1],
        inputs=[AgentInput(name="ticker", type="string", description="股票代码")],
        outputs=[AgentOutput(name="report", type="string", description="分析结果")],
    )


@pytest.mark.asyncio
async def test_search_project_capabilities_returns_formatted_hits(monkeypatch):
    monkeypatch.setattr(
        "core.tools.implementations.agent_builder.nanobot_agent_builder_tools.get_mongo_db",
        lambda: object(),
    )
    monkeypatch.setattr(
        "core.tools.implementations.agent_builder.nanobot_agent_builder_tools.CapabilityIndexService",
        _FakeCapabilityService,
    )

    raw = await search_project_capabilities.ainvoke({
        "query": "A股估值",
        "top_k": 5,
        "bindable_only": True,
        "source_types": "builtin_tool,skill",
    })
    payload = json.loads(raw)

    assert payload["count"] == 1
    assert payload["results"][0]["capability_id"] == "get_value_factor_bundle_tool"
    assert payload["results"][0]["metadata"]["parameters"][0]["name"] == "symbol"


def test_inspect_agent_blueprints_filters_keyword(monkeypatch):
    registry = _FakeRegistry([
        _build_agent("valuation_analyst_v2", "估值分析师", "分析估值水平", ["估值分析"], ["get_value_factor_bundle_tool"]),
        _build_agent("news_analyst_v2", "新闻分析师", "分析新闻事件", ["新闻"], ["get_stock_news_unified"]),
    ])
    monkeypatch.setattr(
        "core.tools.implementations.agent_builder.nanobot_agent_builder_tools.get_registry",
        lambda: registry,
    )

    raw = inspect_agent_blueprints.invoke({"keyword": "估值", "limit": 10, "maintained_only": False})
    payload = json.loads(raw)

    assert payload["count"] == 1
    assert payload["results"][0]["id"] == "valuation_analyst_v2"


def test_get_agent_blueprint_details_returns_single_blueprint(monkeypatch):
    registry = _FakeRegistry([
        _build_agent("valuation_analyst_v2", "估值分析师", "分析估值水平", ["估值分析"], ["get_value_factor_bundle_tool"]),
    ])
    monkeypatch.setattr(
        "core.tools.implementations.agent_builder.nanobot_agent_builder_tools.get_registry",
        lambda: registry,
    )

    raw = get_agent_blueprint_details.invoke({"agent_id": "valuation_analyst_v2"})
    payload = json.loads(raw)

    assert payload["status"] == "ok"
    assert payload["agent"]["id"] == "valuation_analyst_v2"


@pytest.mark.asyncio
async def test_inspect_runtime_agent_configs_reads_db_defined_agents(monkeypatch):
    registry = _FakeRegistry([
        _build_agent("valuation_analyst_v2", "估值分析师", "分析估值水平", ["估值分析"], ["get_value_factor_bundle_tool"]),
    ])
    fake_db = _FakeDb({
        "agent_configs": _FakeCollection([
            {
                "agent_id": "custom_valuation_agent",
                "name": "自定义估值 Agent",
                "description": "数据库配置的估值 Agent",
                "output_field": "valuation_report",
                "tools": ["get_value_factor_bundle_tool"],
                "default_tools": ["get_stock_valuation_context"],
                "metadata": {"status": "active", "source": "agent_workshop"},
                "updated_at": "2026-04-02T10:00:00",
            },
            {
                "agent_id": "valuation_analyst_v2",
                "name": "估值分析师覆盖",
                "description": "对内置 Agent 的数据库覆盖",
                "tools": ["get_value_factor_bundle_tool"],
                "updated_at": "2026-04-01T10:00:00",
            },
        ]),
        "tool_agent_bindings": _FakeCollection([
            {"agent_id": "custom_valuation_agent", "tool_id": "get_value_factor_bundle_tool", "priority": 1, "is_active": True},
            {"agent_id": "custom_valuation_agent", "tool_id": "summarize_industry_valuation", "priority": 2, "is_active": True},
        ]),
    })
    monkeypatch.setattr(
        "core.tools.implementations.agent_builder.nanobot_agent_builder_tools.get_mongo_db",
        lambda: fake_db,
    )
    monkeypatch.setattr(
        "core.tools.implementations.agent_builder.nanobot_agent_builder_tools.get_registry",
        lambda: registry,
    )

    raw = await inspect_runtime_agent_configs.ainvoke({"keyword": "自定义估值", "limit": 5})
    payload = json.loads(raw)

    assert payload["count"] == 1
    assert payload["results"][0]["agent_id"] == "custom_valuation_agent"
    assert payload["results"][0]["runtime_mode"] == "universal_agent"
    assert payload["results"][0]["effective_tools"] == [
        "get_value_factor_bundle_tool",
        "summarize_industry_valuation",
    ]


@pytest.mark.asyncio
async def test_inspect_agent_workshop_assets_returns_specs_and_versions(monkeypatch):
    fake_db = _FakeDb({
        "agent_specs": _FakeCollection([
            {
                "spec_id": "spec_valuation_001",
                "name": "估值 Agent 规格",
                "domain": "a_share",
                "primary_goal": "输出估值结论",
                "responsibilities": ["估值比较", "行业对比"],
                "status": "active",
                "version_count": 2,
                "current_version_id": "ver_valuation_002",
                "updated_at": "2026-04-02T09:00:00",
            }
        ]),
        "agent_versions": _FakeCollection([
            {
                "version_id": "ver_valuation_002",
                "spec_id": "spec_valuation_001",
                "version": 2,
                "status": "testing",
                "agent_metadata": {"id": "custom_valuation_agent", "name": "自定义估值 Agent"},
                "required_tools": ["get_value_factor_bundle_tool"],
                "required_capabilities": ["industry_valuation_compare"],
                "prompt_template_ref": {"template_id": "tpl_001", "status": "active"},
                "updated_at": "2026-04-02T09:30:00",
            }
        ]),
    })
    monkeypatch.setattr(
        "core.tools.implementations.agent_builder.nanobot_agent_builder_tools.get_mongo_db",
        lambda: fake_db,
    )

    raw = await inspect_agent_workshop_assets.ainvoke({"keyword": "估值", "limit": 5})
    payload = json.loads(raw)

    assert payload["spec_count"] == 1
    assert payload["version_count"] == 1
    assert payload["specs"][0]["spec_id"] == "spec_valuation_001"
    assert payload["versions"][0]["version_id"] == "ver_valuation_002"
    assert payload["versions"][0]["required_tools"] == ["get_value_factor_bundle_tool"]


@pytest.mark.asyncio
async def test_create_or_update_runtime_agent_config_upserts_candidate(monkeypatch):
    fake_db = _FakeDb({"agent_configs": _FakeCollection([])})
    monkeypatch.setattr(
        "core.tools.implementations.agent_builder.nanobot_agent_builder_tools.get_mongo_db",
        lambda: fake_db,
    )

    raw = await create_or_update_runtime_agent_config.ainvoke({
        "agent_id": "valuation_candidate_v1",
        "agent_name": "估值候选Agent",
        "description": "输出A股估值结论",
    })
    payload = json.loads(raw)

    assert payload["status"] == "ok"
    assert payload["action"] == "created"
    assert payload["agent"]["agent_id"] == "valuation_candidate_v1"
    assert payload["agent"]["metadata"]["generation_status"] == "candidate"


@pytest.mark.asyncio
async def test_create_or_update_agent_workshop_draft_creates_visible_spec_and_session(monkeypatch):
    fake_db = _FakeDb({
        "agent_specs": _FakeCollection([]),
        "agent_workshop_sessions": _FakeCollection([]),
    })
    monkeypatch.setattr(
        "core.tools.implementations.agent_builder.nanobot_agent_builder_tools.get_mongo_db",
        lambda: fake_db,
    )
    monkeypatch.setattr(
        "core.tools.implementations.agent_builder.nanobot_agent_builder_tools.require_current_user_id",
        lambda: "user_001",
    )
    monkeypatch.setattr(
        "core.tools.implementations.agent_builder.nanobot_agent_builder_tools.get_current_assistant_thread_id",
        lambda: "thread_valuation",
    )

    raw = await create_or_update_agent_workshop_draft.ainvoke({
        "agent_id": "valuation_candidate_v1",
        "agent_name": "估值候选Agent",
        "target_responsibility": "输出A股估值结论",
        "output_field": "valuation_report",
        "tool_ids": "get_value_factor_bundle_tool",
        "preferred_methods": "PE,PB,PEG",
        "constraints": "不要输出交易建议",
    })
    payload = json.loads(raw)

    assert payload["status"] == "ok"
    assert payload["spec_id"] == "spec_nanobot_valuation_candidate_v1"
    assert payload["source"] == "nanobot"
    spec_doc = fake_db["agent_specs"]._items[0]
    assert spec_doc["owner_user_id"] == "user_001"
    assert spec_doc["source"] == "nanobot"
    assert spec_doc["outputs"] == ["valuation_report"]
    session_doc = fake_db["agent_workshop_sessions"]._items[0]
    assert session_doc["spec_id"] == "spec_nanobot_valuation_candidate_v1"
    assert session_doc["user_id"] == "user_001"


@pytest.mark.asyncio
async def test_create_or_update_universal_agent_prompt_template_writes_template(monkeypatch):
    fake_db = _FakeDb({
        "prompt_templates": _FakeCollection([]),
        "agent_configs": _FakeCollection([{"agent_id": "valuation_candidate_v1", "metadata": {}}]),
    })
    monkeypatch.setattr(
        "core.tools.implementations.agent_builder.nanobot_agent_builder_tools.get_mongo_db",
        lambda: fake_db,
    )

    raw = await create_or_update_universal_agent_prompt_template.ainvoke({
        "agent_id": "valuation_candidate_v1",
        "template_name": "估值候选模板",
        "system_prompt": "你是一名A股估值分析师。",
    })
    payload = json.loads(raw)

    assert payload["status"] == "ok"
    assert payload["template"]["agent_type"] == "universal"
    assert payload["template"]["agent_name"] == "valuation_candidate_v1"
    template_doc = fake_db["prompt_templates"]._items[0]
    assert "全局铁律：所有 Agent 一律禁止输出任何交易建议" in template_doc["content"]["system_prompt"]
    assert "全局铁律：所有 Agent 一律禁止输出任何交易建议" in template_doc["content"]["constraints"]
    agent_config = fake_db["agent_configs"]._items[0]
    assert agent_config["metadata"]["default_prompt_template_id"]


@pytest.mark.asyncio
async def test_bind_agent_tools_and_validate_candidate_updates_bindings_and_runs_dry_run(monkeypatch):
    fake_db = _FakeDb({
        "tool_agent_bindings": _FakeCollection([]),
        "agent_configs": _FakeCollection([
            {"agent_id": "valuation_candidate_v1", "name": "估值候选Agent", "description": "输出A股估值结论"}
        ]),
        "prompt_templates": _FakeCollection([
            {
                "_id": "tpl_001",
                "agent_type": "universal",
                "agent_name": "valuation_candidate_v1",
                "template_name": "估值候选模板",
                "workflow_id": None,
                "node_id": None,
                "status": "active",
                "content": {"system_prompt": "x"},
                "updated_at": "2026-04-02T10:00:00",
                "version": 1,
            }
        ]),
    })

    class _FakeFactory:
        def create_with_dynamic_tools(self, agent_id, llm=None):
            return type(
                "FakeAgent",
                (),
                {
                    "agent_id": agent_id,
                    "_langchain_tools": [type("Tool", (), {"name": "get_value_factor_bundle_tool"})()],
                    "_output_field": "analysis_report",
                },
            )()

    class _FakeBindingManager:
        def set_database(self, db):
            self.db = db

    class _FakeToolRegistry:
        def get(self, tool_id):
            if tool_id == "get_value_factor_bundle_tool":
                return object()
            return None

    monkeypatch.setattr(
        "core.tools.implementations.agent_builder.nanobot_agent_builder_tools.get_mongo_db",
        lambda: fake_db,
    )
    monkeypatch.setattr(
        "core.tools.implementations.agent_builder.nanobot_agent_builder_tools.get_mongo_db_sync",
        lambda: fake_db,
    )
    monkeypatch.setattr(
        "core.tools.implementations.agent_builder.nanobot_agent_builder_tools.AgentFactory",
        _FakeFactory,
    )
    monkeypatch.setattr(
        "core.tools.implementations.agent_builder.nanobot_agent_builder_tools.BindingManager",
        _FakeBindingManager,
    )
    monkeypatch.setattr(
        "core.tools.implementations.agent_builder.nanobot_agent_builder_tools.get_tool_registry",
        lambda: _FakeToolRegistry(),
    )

    raw = await bind_agent_tools_and_validate_candidate.ainvoke({
        "agent_id": "valuation_candidate_v1",
        "tool_ids": "get_value_factor_bundle_tool",
    })
    payload = json.loads(raw)

    assert payload["status"] == "ok"
    assert payload["bound_tools"] == ["get_value_factor_bundle_tool"]
    assert payload["validation"]["prompt_template_found"] is True
    assert payload["validation"]["dry_run"]["instantiated"] is True


@pytest.mark.asyncio
async def test_prepare_agent_generation_confirmation_reports_overwrite_risk(monkeypatch):
    fake_db = _FakeDb({
        "agent_configs": _FakeCollection([
            {"agent_id": "valuation_candidate_v1", "name": "已存在估值Agent"}
        ]),
        "prompt_templates": _FakeCollection([
            {
                "_id": "tpl_001",
                "agent_type": "universal",
                "agent_name": "valuation_candidate_v1",
                "workflow_id": None,
                "node_id": None,
                "status": "active",
            }
        ]),
        "tool_agent_bindings": _FakeCollection([
            {"agent_id": "valuation_candidate_v1", "tool_id": "get_value_factor_bundle_tool", "is_active": True}
        ]),
    })

    class _FakeToolRegistry:
        def get(self, tool_id):
            return object() if tool_id == "get_value_factor_bundle_tool" else None

    monkeypatch.setattr(
        "core.tools.implementations.agent_builder.nanobot_agent_builder_tools.get_mongo_db",
        lambda: fake_db,
    )
    monkeypatch.setattr(
        "core.tools.implementations.agent_builder.nanobot_agent_builder_tools.get_tool_registry",
        lambda: _FakeToolRegistry(),
    )

    raw = await prepare_agent_generation_confirmation.ainvoke({
        "agent_id": "valuation_candidate_v1",
        "agent_name": "估值候选Agent",
        "target_responsibility": "输出A股估值结论",
        "tool_ids": "get_value_factor_bundle_tool",
        "non_goals": "不做交易建议,不做仓位决策",
        "valuation_method_scope": "仅PE/PB/PEG与相对估值",
        "test_strategy": "只做配置校验，不跑真实股票样例",
    })
    payload = json.loads(raw)

    assert payload["status"] == "ok"
    assert payload["confirmation_required"] is True
    assert payload["confirmation_brief"]["overwrite_risk"]["requires_explicit_overwrite"] is True
    assert "全局铁律：所有 Agent 一律禁止输出任何交易建议" in payload["confirmation_brief"]["recommendation_policy"]


@pytest.mark.asyncio
async def test_generate_confirmed_candidate_agent_rejects_without_confirmation():
    raw = await generate_confirmed_candidate_agent.ainvoke({
        "agent_id": "valuation_candidate_v1",
        "agent_name": "估值候选Agent",
        "target_responsibility": "输出A股估值结论",
        "tool_ids": "get_value_factor_bundle_tool",
        "system_prompt": "你是一名估值分析师。",
        "confirmed": False,
    })
    payload = json.loads(raw)

    assert payload["status"] == "error"
    assert "未拿到用户明确确认" in payload["message"]


@pytest.mark.asyncio
async def test_generate_confirmed_candidate_agent_runs_one_shot_after_confirmation(monkeypatch):
    fake_db = _FakeDb({
        "agent_configs": _FakeCollection([]),
        "prompt_templates": _FakeCollection([]),
        "tool_agent_bindings": _FakeCollection([]),
        "agent_specs": _FakeCollection([]),
        "agent_workshop_sessions": _FakeCollection([]),
    })

    class _FakeFactory:
        def create_with_dynamic_tools(self, agent_id, llm=None):
            return type(
                "FakeAgent",
                (),
                {
                    "agent_id": agent_id,
                    "_langchain_tools": [type("Tool", (), {"name": "get_value_factor_bundle_tool"})()],
                    "_output_field": "valuation_report",
                },
            )()

    class _FakeBindingManager:
        def set_database(self, db):
            self.db = db

    class _FakeToolRegistry:
        def get(self, tool_id):
            if tool_id == "get_value_factor_bundle_tool":
                return object()
            return None

    monkeypatch.setattr(
        "core.tools.implementations.agent_builder.nanobot_agent_builder_tools.get_mongo_db",
        lambda: fake_db,
    )
    monkeypatch.setattr(
        "core.tools.implementations.agent_builder.nanobot_agent_builder_tools.get_mongo_db_sync",
        lambda: fake_db,
    )
    monkeypatch.setattr(
        "core.tools.implementations.agent_builder.nanobot_agent_builder_tools.AgentFactory",
        _FakeFactory,
    )
    monkeypatch.setattr(
        "core.tools.implementations.agent_builder.nanobot_agent_builder_tools.BindingManager",
        _FakeBindingManager,
    )
    monkeypatch.setattr(
        "core.tools.implementations.agent_builder.nanobot_agent_builder_tools.get_tool_registry",
        lambda: _FakeToolRegistry(),
    )
    monkeypatch.setattr(
        "core.tools.implementations.agent_builder.nanobot_agent_builder_tools.require_current_user_id",
        lambda: "user_001",
    )
    monkeypatch.setattr(
        "core.tools.implementations.agent_builder.nanobot_agent_builder_tools.get_current_assistant_thread_id",
        lambda: "thread_valuation",
    )

    raw = await generate_confirmed_candidate_agent.ainvoke({
        "agent_id": "valuation_candidate_v1",
        "agent_name": "估值候选Agent",
        "target_responsibility": "输出A股估值结论",
        "tool_ids": "get_value_factor_bundle_tool",
        "system_prompt": "你是一名估值分析师。",
        "output_field": "valuation_report",
        "confirmed": True,
        "allow_overwrite": False,
    })
    payload = json.loads(raw)

    assert payload["status"] == "ok"
    assert payload["steps"]["workshop_draft"]["status"] == "ok"
    assert payload["steps"]["agent_config"]["status"] == "ok"
    assert payload["steps"]["prompt_template"]["status"] == "ok"
    assert payload["steps"]["bindings_and_validation"]["validation"]["dry_run"]["instantiated"] is True


def test_prepare_agent_requirement_intake_returns_follow_up_questions_for_vague_request():
    raw = prepare_agent_requirement_intake.invoke({
        "user_request": "帮我做一个估值分析 agent",
    })
    payload = json.loads(raw)

    assert payload["status"] == "ok"
    assert payload["can_proceed_to_confirmation"] is False
    assert "single_responsibility" in payload["missing_decisions"]
    assert "output_shape" in payload["missing_decisions"]
    assert "valuation_method_scope" in payload["missing_decisions"]
    assert "test_strategy" in payload["missing_decisions"]
    assert "全局铁律：所有 Agent 一律禁止输出任何交易建议" in payload["known_context"]["recommendation_policy"]
    assert payload["follow_up_questions"]
    assert payload["recommended_next_step"] == "ask_requirement_questions"


def test_prepare_agent_requirement_intake_detects_style_preview_scope_questions():
    raw = prepare_agent_requirement_intake.invoke({
        "user_request": "估值分析 agent 的报告样式是什么样？",
        "target_responsibility": "输出A股估值结论",
        "desired_output_shape": "估值报告样式预览",
    })
    payload = json.loads(raw)

    assert payload["status"] == "ok"
    assert payload["request_profile"]["output_preview_request"] is True
    assert "preview_mode" in payload["missing_decisions"]
    assert "report_section_scope" in payload["missing_decisions"]
    assert payload["can_proceed_to_confirmation"] is False


@pytest.mark.asyncio
async def test_prepare_agent_generation_confirmation_blocks_stock_agent_when_intake_incomplete(monkeypatch):
    fake_db = _FakeDb({
        "agent_configs": _FakeCollection([]),
        "prompt_templates": _FakeCollection([]),
        "tool_agent_bindings": _FakeCollection([]),
    })

    class _FakeToolRegistry:
        def get(self, tool_id):
            return object() if tool_id == "get_value_factor_bundle_tool" else None

    monkeypatch.setattr(
        "core.tools.implementations.agent_builder.nanobot_agent_builder_tools.get_mongo_db",
        lambda: fake_db,
    )
    monkeypatch.setattr(
        "core.tools.implementations.agent_builder.nanobot_agent_builder_tools.get_tool_registry",
        lambda: _FakeToolRegistry(),
    )

    raw = await prepare_agent_generation_confirmation.ainvoke({
        "agent_id": "valuation_candidate_v1",
        "agent_name": "估值候选Agent",
        "target_responsibility": "输出A股估值结论",
        "tool_ids": "get_value_factor_bundle_tool",
    })
    payload = json.loads(raw)

    assert payload["status"] == "needs_requirement_intake"
    assert "valuation_method_scope" in payload["missing_intake_fields"]
    assert "test_strategy" in payload["missing_intake_fields"]


@pytest.mark.asyncio
async def test_prepare_agent_generation_confirmation_blocks_style_preview_when_scope_unspecified(monkeypatch):
    fake_db = _FakeDb({
        "agent_configs": _FakeCollection([]),
        "prompt_templates": _FakeCollection([]),
        "tool_agent_bindings": _FakeCollection([]),
    })

    class _FakeToolRegistry:
        def get(self, tool_id):
            return object() if tool_id == "get_value_factor_bundle_tool" else None

    monkeypatch.setattr(
        "core.tools.implementations.agent_builder.nanobot_agent_builder_tools.get_mongo_db",
        lambda: fake_db,
    )
    monkeypatch.setattr(
        "core.tools.implementations.agent_builder.nanobot_agent_builder_tools.get_tool_registry",
        lambda: _FakeToolRegistry(),
    )

    raw = await prepare_agent_generation_confirmation.ainvoke({
        "agent_id": "valuation_candidate_v1",
        "agent_name": "估值候选Agent",
        "target_responsibility": "输出A股估值结论",
        "tool_ids": "get_value_factor_bundle_tool",
        "desired_output_shape": "估值报告样式预览",
        "non_goals": "不做交易建议,不做仓位决策",
        "valuation_method_scope": "仅PE/PB/PEG与相对估值",
        "test_strategy": "只做配置校验，不跑真实股票样例",
    })
    payload = json.loads(raw)

    assert payload["status"] == "needs_requirement_intake"
    assert "preview_mode" in payload["missing_intake_fields"]
    assert "report_section_scope" in payload["missing_intake_fields"]


@pytest.mark.asyncio
async def test_prepare_agent_generation_confirmation_does_not_treat_structured_report_as_preview(monkeypatch):
    fake_db = _FakeDb({
        "agent_configs": _FakeCollection([]),
        "prompt_templates": _FakeCollection([]),
        "tool_agent_bindings": _FakeCollection([]),
    })

    class _FakeToolRegistry:
        def get(self, tool_id):
            return object() if tool_id == "get_value_factor_bundle_tool" else None

    monkeypatch.setattr(
        "core.tools.implementations.agent_builder.nanobot_agent_builder_tools.get_mongo_db",
        lambda: fake_db,
    )
    monkeypatch.setattr(
        "core.tools.implementations.agent_builder.nanobot_agent_builder_tools.get_tool_registry",
        lambda: _FakeToolRegistry(),
    )

    raw = await prepare_agent_generation_confirmation.ainvoke({
        "agent_id": "valuation_candidate_v2",
        "agent_name": "估值候选Agent",
        "target_responsibility": "输出A股估值结论",
        "tool_ids": "get_value_factor_bundle_tool",
        "desired_output_shape": "结构化估值报告",
        "non_goals": "不做交易建议,不做仓位决策",
        "valuation_method_scope": "仅PE/PB/PEG与相对估值",
        "test_strategy": "只做配置校验，不跑真实股票样例",
    })
    payload = json.loads(raw)

    assert payload["status"] == "ok"
    assert payload["confirmation_brief"]["report_contract"]["style_preview_mode"] == "structure_skeleton"
    assert "仅限当前已确认职责相关章节" in payload["confirmation_brief"]["report_contract"]["content_scope"]
    assert payload["confirmation_brief"]["report_contract_display"]["style_preview_mode"] == "只看结构骨架"
    assert "请确认下面这份 Agent 生成方案" in payload["confirmation_brief"]["user_confirmation_template"]
    assert "报告契约" in payload["confirmation_brief"]["user_confirmation_template"]