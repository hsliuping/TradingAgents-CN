"""Offline task entry -> WorkflowAPI -> compile -> wrapped nodes -> storage -> HTTP.

Business method bodies, task/runtime models, validator and LangGraph are real.
Constructors that register providers, configuration stores, models/tools, BSON,
memory and post-processing services are local substitutes; no app startup runs.
"""

import ast
import asyncio
from copy import deepcopy
from datetime import datetime, timezone
import os
from pathlib import Path
import sys
from threading import get_ident
from types import ModuleType, SimpleNamespace
from typing import Any, Callable, Dict, List, Optional, Set, Union
from unittest.mock import AsyncMock, Mock
import uuid

import pytest
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph

from test_c1_degraded_nodes import load_definitions, no_external_connections, web
from test_c2_market_quality import GOOD, WARNING, FALLBACK, load_methods, package, pure_module
from test_c2_langgraph_integration import graph_runtime, make_market, make_researcher


ROOT = Path(os.environ.get("PR1_SOURCE_ROOT", Path(__file__).resolve().parents[3])).resolve()
USER_ID = "0123456789abcdef01234567"


class FakeObjectId:
    def __init__(self, value=None):
        self.value = str(value) if value is not None else uuid.uuid4().hex[:24]
    def __str__(self):
        return self.value
    def __eq__(self, value):
        return isinstance(value, FakeObjectId) and self.value == value.value
    @classmethod
    def is_valid(cls, value):
        return isinstance(value, str) and len(value) == 24 and all(c in "0123456789abcdef" for c in value.lower())


class FakeCollection:
    def __init__(self, name, events):
        self.name, self.events, self.documents = name, events, []
    def _find(self, query):
        return next((doc for doc in self.documents if all(
            doc.get(key) != value["$ne"] if isinstance(value, dict) and "$ne" in value else doc.get(key) == value
            for key, value in query.items())), None)
    async def find_one(self, query, *args, **kwargs):
        return deepcopy(self._find(query))
    async def insert_one(self, document):
        self.documents.append(deepcopy(document))
        self.events.append((self.name, "insert", deepcopy(document)))
        return SimpleNamespace(inserted_id="offline-document")
    async def update_one(self, query, update, **kwargs):
        doc = self._find(query)
        if doc is None:
            return SimpleNamespace(modified_count=0, matched_count=0)
        doc.update(deepcopy(update["$set"]))
        self.events.append((self.name, "update", deepcopy(doc)))
        return SimpleNamespace(modified_count=1, matched_count=1)


class FakeInvocationCollection:
    def __init__(self):
        self.records = []
    def update_one(self, query, update, **kwargs):
        self.records.append(deepcopy(update["$set"]))


class FakeMemory:
    def __init__(self, events):
        self.events, self.tasks, self.online = events, {}, True
    async def get_task(self, task_id):
        return deepcopy(self.tasks.get(task_id))
    async def create_task(self, task_id, **kwargs):
        self.tasks[task_id] = {**deepcopy(kwargs), "status": "pending"}
    async def update_task_status(self, task_id, **kwargs):
        self.tasks[task_id].update(deepcopy(kwargs))
        self.events.append(("memory", "update", deepcopy(self.tasks[task_id])))
    async def get_task_status(self, task_id):
        return await self.get_task(task_id) if self.online else None


def fake_module(monkeypatch, name, **values):
    module = ModuleType(name)
    module.__dict__.update(values)
    monkeypatch.setitem(sys.modules, name, module)
    return module


def literal_constants(relative, names):
    tree = ast.parse((ROOT / relative).read_text(encoding="utf-8-sig"))
    return {target.id: ast.literal_eval(node.value) for node in tree.body if isinstance(node, ast.Assign)
            for target in node.targets if isinstance(target, ast.Name) and target.id in names}


@pytest.fixture
def task_runtime(graph_runtime, monkeypatch, web):
    rt, wf = graph_runtime, graph_runtime.workflow
    events, engines, builders, node_inputs, client_progress = [], [], [], [], []
    tasks = FakeCollection("tasks", events)
    reports = FakeCollection("reports", events)
    db = web.db
    db.unified_analysis_tasks, db.analysis_reports = tasks, reports
    db.workflows, db.system_configs = FakeCollection("workflows", events), FakeCollection("system", events)
    db.agent_configs = SimpleNamespace(find_one=lambda *args, **kwargs: None)
    memory = FakeMemory(events)
    web.state.get_task_status.side_effect = memory.get_task_status
    clock = lambda: datetime.now(timezone.utc)
    fake_module(monkeypatch, "bson", ObjectId=FakeObjectId)
    fake_module(monkeypatch, "app.utils.timezone", now_tz=clock)
    fake_module(monkeypatch, "app.core.config", settings=SimpleNamespace(AGENT_EXECUTION_TRACE_ENABLED=False))
    fake_module(monkeypatch, "app.services.memory_state_manager", get_memory_state_manager=lambda: memory,
                TaskStatus=SimpleNamespace(RUNNING="running", COMPLETED="completed", FAILED="failed", CANCELLED="cancelled"))
    package(monkeypatch, "app.models", "app/models")
    user = pure_module(monkeypatch, "app.models.user", "app/models/user.py")
    pure_module(monkeypatch, "app.models.agent_growth", "app/models/agent_growth.py")
    analysis = pure_module(monkeypatch, "app.models.analysis", "app/models/analysis.py")
    registry = pure_module(monkeypatch, "app.services.workflow_registry", "app/services/workflow_registry.py")
    registry.AnalysisWorkflowRegistry.register(registry.AnalysisWorkflowConfig(
        task_type=analysis.AnalysisTaskType.STOCK_ANALYSIS, workflow_id="offline_entry",
        name="offline", required_params=["symbol"], default_engine="workflow"))
    config = pure_module(monkeypatch, "core.agents.config", "core/agents/config.py")
    collaboration = pure_module(monkeypatch, "core.collaboration_runtime", "core/collaboration_runtime.py")
    package(monkeypatch, "core.workflow", "core/workflow")
    monkeypatch.setitem(sys.modules, "core.workflow.models", wf)
    validator = pure_module(monkeypatch, "core.workflow.validator", "core/workflow/validator.py")
    state_registry = pure_module(monkeypatch, "core.state.registry", "core/state/registry.py")
    # This singleton must be private to the test case.
    state_registry.StateRegistry._instance = None
    package(monkeypatch, "tradingagents.agents", "tradingagents/agents")
    package(monkeypatch, "tradingagents.agents.utils", "tradingagents/agents/utils")
    pure_module(monkeypatch, "tradingagents.agents.utils.agent_context", "tradingagents/agents/utils/agent_context.py")
    fake_module(monkeypatch, "app.services.simple_analysis_service",
        RESEARCH_DEPTH_REASONING_EFFORT={"标准": "medium"}, _get_cached_security_name=lambda code: "离线示例")
    fake_module(monkeypatch, "app.models.notification", NotificationCreate=lambda **kwargs: SimpleNamespace(**kwargs))
    notification = AsyncMock()
    fake_module(monkeypatch, "app.services.notifications_service",
                get_notifications_service=lambda: SimpleNamespace(create_and_publish=notification))
    fake_module(monkeypatch, "app.services.intelligent_assistant_service",
                update_user_profile_with_analysis=AsyncMock(), write_report_back_to_assistant_thread=AsyncMock())
    invocation_store = FakeInvocationCollection()
    constants = literal_constants("core/workflow/builder.py", {
        "ANALYST_TOOL_MAPPING", "_DEFAULT_CALLABLE_SURFACES", "_DEEP_AGENTS", "_MANAGER_AGENT_PREFIXES"})
    functions = load_definitions("core/workflow/builder.py", {"_select_llm_type_for_agent", "_is_manager_agent"}, **constants)
    runtime_types = {name: getattr(collaboration, name) for name in (
        "InvocationRequest", "InvocationResult", "InvocationPolicy", "InvocationProvenance",
        "InvocationArtifactRef", "InvocationSourceType", "InvocationTargetType", "InvocationStatus", "utc_now")}
    builder_cls, _ = load_methods("core/workflow/builder.py", "WorkflowBuilder", {
        "build", "_filter_analyst_nodes", "_is_analyst_selected", "_identify_debate_configs", "_add_edges",
        "_create_node_function", "_create_parallel_node", "_create_merge_node", "_create_agent_node",
        "_create_tool_node_wrapper", "_create_msg_clear_node", "_create_analyst_condition_func",
        "_normalize_callable_surfaces", "_ensure_workflow_surface_access", "_resolve_agent_output_field",
        "_get_default_state_schema", "_sanitize_runtime_value", "_build_workflow_payload", "_extract_report_text",
        "_sanitize_structured_output", "_build_workflow_invocation_request", "_persist_workflow_invocation_record",
        "_execute_agent_node_with_runtime"},
        Callable=Callable, Set=Set, StateGraph=StateGraph, START=START, END=END, ToolNode=Any,
        WorkflowDefinition=wf.WorkflowDefinition, NodeDefinition=wf.NodeDefinition, NodeType=wf.NodeType,
        EdgeType=wf.EdgeType, AgentConfig=config.AgentConfig, datetime=datetime, uuid=uuid,
        **constants, **runtime_types, **{name: functions[name] for name in ("_select_llm_type_for_agent", "_is_manager_agent")})
    scenario = SimpleNamespace(content=GOOD, peer_failure=False, schema="dynamic", invalid=False,
                               callback_failure=False, async_callback=True)
    tool_graph = SimpleNamespace(invoke=Mock(side_effect=AssertionError("No external tool-node calls")))
    base_cls, _ = load_methods("core/agents/base.py", "BaseAgent", {"__call__"})
    def make_builder(legacy_config=None, llm_override=None):
        builder = builder_cls()
        builder._agents, builder._workflow_id, builder._selected_analysts = {}, None, None
        builder.memory_manager = None
        builder.default_config = config.AgentConfig()
        builder.agent_config_manager = SimpleNamespace(get_agent_config=lambda agent_id: None)
        builder.binding_manager = SimpleNamespace(_db=SimpleNamespace(workflow_agent_invocations=invocation_store),
            get_tools_for_node=Mock(return_value=["offline_prices"]))
        market, model, tool = make_market(rt, scenario.content, True)
        market.__class__.__call__ = base_cls.__call__
        researcher = make_researcher()
        researcher.__class__.__call__ = base_cls.__call__
        original_research = researcher.execute
        def observe_research(state):
            node_inputs.append(("research", deepcopy(state), get_ident()))
            return original_research(state)
        researcher.execute = observe_research
        class Peer:
            def __call__(self, state):
                node_inputs.append(("peer", deepcopy(state), get_ident()))
                if scenario.peer_failure:
                    raise RuntimeError("PRIVATE-ENTRY-ERROR offline peer failure")
                return {"news_report": GOOD}
        agents = {"market_analyst_v2": market, "news_analyst_v2": Peer(), "bull_researcher_v2": researcher}
        outputs = {"market_analyst_v2": "market_report", "news_analyst_v2": "news_report", "bull_researcher_v2": "bull_report"}
        metadata = {name: SimpleNamespace(id=name, version="2.0.0", maintenance_status="maintained", output_field=field, node_name=name,
                      callable_surfaces=["workflow"], outputs=[]) for name, field in outputs.items()}
        builder.registry = SimpleNamespace(is_registered=lambda aid: aid in agents, get_metadata=metadata.get,
                                           list_all=lambda: list(metadata.values()))
        builder.factory = SimpleNamespace(create=Mock(side_effect=lambda aid, *a, **kw: agents[aid]))
        builder.llm_override = model
        builder._legacy_provider = SimpleNamespace(get_tool_nodes=lambda: {"market": tool_graph, "news": tool_graph})
        builder.offline = SimpleNamespace(market=market, model=model, tool=tool, researcher=researcher)
        builders.append(builder)
        return builder
    fake_module(monkeypatch, "core.agents.registry", get_registry=lambda: builders[-1].registry)
    engine_methods = {"__init__", "load", "validate", "compile", "execute", "_extract_agent_ids",
        "_build_internal_state_fields", "set_progress_callback", "_report_progress", "_build_execution_config",
        "_init_progress_tracking", "_get_node_progress_info", "_create_execution", "last_execution",
        "_build_output_results", "_build_builtin_output", "_extract_text_value", "_generate_final_trade_decision",
        "_extract_text_from_state", "_is_builtin_workflow", "_lookup_agent_metadata"}
    prepare = load_definitions("core/workflow/engine.py", {"_prepare_workflow_runtime_inputs"})
    dynamic_fields = load_definitions("core/workflow/engine.py", {"_get_dynamic_report_fields"},
        **literal_constants("core/workflow/engine.py", {"_BUILTIN_REPORT_FIELDS"}))
    engine_cls, _ = load_methods("core/workflow/engine.py", "WorkflowEngine", engine_methods,
        __package__="core.workflow", WorkflowBuilder=make_builder, WorkflowValidator=validator.WorkflowValidator,
        ValidationResult=validator.ValidationResult, WorkflowDefinition=wf.WorkflowDefinition,
        WorkflowExecution=wf.WorkflowExecution, WorkflowExecutionState=wf.WorkflowExecutionState,
        FieldType=rt.models.FieldType, Callable=Callable, datetime=datetime, uuid=uuid,
        ANALYST_TOOL_MAPPING=constants["ANALYST_TOOL_MAPPING"],
        _prepare_workflow_runtime_inputs=prepare["_prepare_workflow_runtime_inputs"],
        _get_dynamic_report_fields=dynamic_fields["_get_dynamic_report_fields"])
    engine_cls.last_execution = property(engine_cls.last_execution)
    def make_engine(**kwargs):
        engine = engine_cls(**kwargs, use_dynamic_state=scenario.schema == "dynamic")
        engines.append(engine)
        # IO lookup is fake registry metadata; schema building and caching are real.
        if engine._use_dynamic_state:
            for aid, field in {"market_analyst_v2": "market_report", "news_analyst_v2": "news_report",
                               "bull_researcher_v2": "bull_report"}.items():
                engine._state_registry._builder._io_cache[aid] = rt.models.AgentIODefinition(agent_id=aid,
                    inputs=[rt.models.StateFieldDefinition(name="ticker"), rt.models.StateFieldDefinition(name="analysis_date")],
                    outputs=[rt.models.StateFieldDefinition(name=field)])
        return engine
    nodes = [wf.NodeDefinition(id="start", type="start"), wf.NodeDefinition(id="parallel", type="parallel"),
        wf.NodeDefinition(id="entry_market", type="analyst", agent_id="market_analyst_v2", label="市场节点"),
        wf.NodeDefinition(id="entry_news", type="analyst", agent_id="news_analyst_v2", label="新闻节点"),
        wf.NodeDefinition(id="merge", type="merge"),
        wf.NodeDefinition(id="entry_research", type="researcher", agent_id="bull_researcher_v2"),
        wf.NodeDefinition(id="end", type="end")]
    pairs = [("start", "parallel"), ("parallel", "entry_market"), ("parallel", "entry_news"),
        ("entry_market", "merge"), ("entry_news", "merge"), ("merge", "entry_research"), ("entry_research", "end")]
    definition = wf.WorkflowDefinition(id="offline_entry", name="Offline entry", nodes=nodes,
        edges=[wf.EdgeDefinition(id=str(i), source=a, target=b) for i, (a, b) in enumerate(pairs)])
    def definition_data(workflow_id):
        data = definition.to_dict()
        if scenario.invalid:
            data["edges"].append({"id": "invalid", "source": "entry_research", "target": "missing_node"})
        return data
    api_cls, _ = load_methods("core/api/workflow_api.py", "WorkflowAPI", {"execute", "_prepare_inputs"},
        WorkflowEngine=make_engine, WorkflowDefinition=wf.WorkflowDefinition, Callable=Callable,
        uuid=uuid, os=os, datetime=datetime)
    api = api_cls()
    api.get = definition_data
    api._prepare_system_variables = Mock(return_value={"company_name": "离线示例", "market_type": "A股"})
    fake_module(monkeypatch, "core.api.workflow_api", WorkflowAPI=lambda: api)
    provider = SimpleNamespace(get_system_workflow=lambda workflow_id: definition)
    unified_cls, _ = load_methods("app/services/unified_analysis_engine.py", "UnifiedAnalysisEngine",
        {"__init__", "execute_task", "_resolve_workflow_id", "_workflow_exists", "_workflow_type_for_task",
         "_select_engine", "_call_progress_callback", "_execute_via_workflow"},
        UnifiedAnalysisTask=analysis.UnifiedAnalysisTask, AnalysisTaskType=analysis.AnalysisTaskType,
        AnalysisStatus=analysis.AnalysisStatus, AnalysisWorkflowRegistry=registry.AnalysisWorkflowRegistry,
        Callable=Callable, now_tz=clock, get_default_workflow_provider=lambda: provider)
    unified_cls._inject_memory_facts = AsyncMock()
    class TaskCancelledException(Exception):
        pass
    namespace = load_definitions("app/services/task_analysis_service.py", {
        "__init__", "create_task", "execute_task", "create_and_execute_task", "get_task", "_save_task",
        "_is_task_cancelled", "_format_analysis_result", "_format_decision_dict", "_extract_decision_from_text",
        "_update_task", "_save_to_analysis_reports"}, class_name="TaskAnalysisService",
        UnifiedAnalysisEngine=unified_cls, UnifiedAnalysisTask=analysis.UnifiedAnalysisTask,
        AnalysisTaskType=analysis.AnalysisTaskType, AnalysisStatus=analysis.AnalysisStatus,
        PyObjectId=user.PyObjectId, TaskCancelledException=TaskCancelledException,
        get_mongo_db=lambda: db, now_tz=clock, asyncio=asyncio)
    fake_module(monkeypatch, "app.services.task_analysis_service", TaskCancelledException=TaskCancelledException)
    service = namespace["TaskAnalysisService"]()
    service._resolve_stock_name = AsyncMock(return_value="离线示例")
    service._store_stock_object_memory = AsyncMock()
    service._send_analysis_email_notification = AsyncMock()
    service._schedule_growth_extraction = Mock()
    return SimpleNamespace(scenario=scenario, service=service, analysis=analysis, engines=engines, builders=builders,
        definition=definition, events=events, tasks=tasks, reports=reports, memory=memory, invocation_store=invocation_store,
        node_inputs=node_inputs, client_progress=client_progress, main_thread=get_ident(), web=web, tool_graph=tool_graph)


async def run_entry(rt, *, by_id=False):
    def on_progress(progress, message, **kwargs):
        rt.client_progress.append((progress, deepcopy(rt.tasks.documents[0]), deepcopy(rt.memory.tasks["entry-offline-task"])))
        if progress == 100 and rt.scenario.callback_failure:
            raise RuntimeError("offline completion listener failure")
    async def on_async_progress(progress, message, **kwargs):
        on_progress(progress, message, **kwargs)
    callback = on_async_progress if rt.scenario.async_callback else on_progress
    kwargs = dict(user_id=FakeObjectId(USER_ID), task_type=rt.analysis.AnalysisTaskType.STOCK_ANALYSIS,
        task_params={"symbol": "000001", "analysis_date": "2026-10-30", "research_depth": "标准"},
        workflow_id="offline_entry", engine_type="workflow", task_id="entry-offline-task")
    if by_id:
        created = await rt.service.create_task(**kwargs)
        return await rt.service.execute_task(created.task_id, callback)
    return await rt.service.create_and_execute_task(**kwargs, progress_callback=callback)


@pytest.mark.parametrize("schema", ["dynamic", "fallback"])
@pytest.mark.parametrize("content,peer_failure", [(GOOD, False), (WARNING, False), ("", False),
    (None, False), (GOOD, True), ("", True)],
    ids=["normal", "warning", "critical", "existing-report-fallback", "wrapped-error", "two-errors"])
def test_task_entry_quality_and_degradation_reach_web(task_runtime, schema, content, peer_failure):
    rt = task_runtime
    rt.scenario.schema, rt.scenario.content, rt.scenario.peer_failure = schema, content, peer_failure
    result = asyncio.run(run_entry(rt))
    assert result.status == "completed"
    assert len(rt.engines) == 1 and isinstance(rt.engines[0]._compiled_graph, CompiledStateGraph)
    expected_nodes = ({"entry_market"} if content in ("", None) else set()) | (
        {"entry_news"} if peer_failure else set())
    output = rt.engines[0]._current_execution.outputs
    consumed = [state for name, state, _ in rt.node_inputs if name == "research"]
    assert len(consumed) == 1
    assert output.get("quality_flags", []) == consumed[0].get("quality_flags", [])
    flags = output.get("quality_flags", [])
    severity = None if content == GOOD else "warning" if content == WARNING else "critical"
    assert len(flags) == int(severity is not None)
    if severity:
        assert flags[0]["severity"] == severity and flags[0]["retried"] is False
    prompt = rt.builders[0].offline.researcher._llm.invoke.call_args.args[0][1].content
    if severity:
        assert "market_analyst_v2" in prompt
        assert ("质量存疑" if severity == "warning" else "质量不合格") in prompt
    else:
        assert "质量提示" not in prompt
    assert {record["step_id"] for record in rt.invocation_store.records} == {
        "entry_market", "entry_news", "entry_research"}
    assert set(output.get("degraded_nodes", {})) == expected_nodes
    assert rt.tasks.documents[0]["result"] == result.result
    assert set(rt.reports.documents[0].get("degraded_nodes", {})) == expected_nodes
    for source in ("memory", "task", "report"):
        rt.memory.online = source == "memory"
        rt.web.db.unified_analysis_tasks = rt.tasks if source != "report" else FakeCollection("empty", [])
        response = rt.web.client.get(f"/api/analysis/tasks/{result.task_id}/result")
        assert response.status_code == 200, response.text
        data = response.json()["data"]
        assert data["reports"] and set(data.get("degraded_nodes", {})) == expected_nodes
        assert "PRIVATE-" not in response.text
    rt.builders[0].offline.model.invoke.assert_called_once()
    rt.builders[0].offline.tool.invoke.assert_called_once()
    rt.builders[0].offline.market._check_and_retry_quality.assert_not_called()
