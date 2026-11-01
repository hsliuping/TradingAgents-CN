"""Real LangGraph compilation/scheduling with offline application boundaries.

Load intact product method bodies to avoid provider registration and app startup.
StateGraph, channels/reducers, parallel barriers, streaming and HTTP are real.
Only model/tool/config/storage boundaries and prompt templates are local fakes.
"""

import asyncio
from copy import deepcopy
from datetime import datetime
import sys
from types import ModuleType, SimpleNamespace
from typing import Any, Callable, Set
from unittest.mock import Mock

import pytest
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph

from test_c1_degraded_nodes import (
    load_definitions, no_external_connections, service, web, task, request_result,
)
from test_c2_market_quality import (
    GOOD, WARNING, FALLBACK, load_methods, package, pure_module,
    market as unit_market,
)


@pytest.fixture
def graph_runtime(monkeypatch):
    for key in ("LANGCHAIN_TRACING_V2", "LANGSMITH_TRACING"):
        monkeypatch.setenv(key, "false")
    for key in ("LANGCHAIN_API_KEY", "LANGSMITH_API_KEY"):
        monkeypatch.delenv(key, raising=False)
    # Do not replace langgraph or langchain_core anywhere in this fixture.
    package(monkeypatch, "core.agents", "core/agents")
    package(monkeypatch, "core.state", "core/state")
    quality = pure_module(monkeypatch, "core.agents.quality_gate", "core/agents/quality_gate.py")
    models = pure_module(monkeypatch, "core.state.models", "core/state/models.py")
    reducers = pure_module(monkeypatch, "core.state.reducers", "core/state/reducers.py")
    state_builder = pure_module(monkeypatch, "core.state.builder", "core/state/builder.py")
    workflow = pure_module(monkeypatch, "offline_workflow_models", "core/workflow/models.py")
    package(monkeypatch, "tradingagents.config", "tradingagents/config")
    mongo = ModuleType("tradingagents.config.mongodb_utils")
    mongo.build_mongodb_connection_string = lambda: "offline-unused"
    mongo.get_mongodb_database_name = lambda: "offline"
    monkeypatch.setitem(sys.modules, mongo.__name__, mongo)
    pymongo = ModuleType("pymongo")
    class FakeMongo:
        def __init__(self, *args, **kwargs):
            pass
        def __getitem__(self, key):
            return SimpleNamespace(agent_configs=SimpleNamespace(find=lambda *a, **k: []))
        def close(self):
            pass
    pymongo.MongoClient = FakeMongo
    monkeypatch.setitem(sys.modules, "pymongo", pymongo)
    trace = ModuleType("core.agents.execution_trace_recorder")
    trace.is_trace_enabled = lambda: False
    trace.start_execution_trace = Mock(side_effect=AssertionError("Offline trace storage is disabled"))
    monkeypatch.setitem(sys.modules, trace.__name__, trace)
    return SimpleNamespace(quality=quality, models=models, reducers=reducers,
                           state_builder=state_builder, workflow=workflow)


def make_market(runtime, content, tools):
    agent = unit_market.__wrapped__(runtime)
    cls, _ = load_methods(
        "core/agents/adapters/market_analyst_v2.py", "MarketAnalystV2",
        {"execute", "_sanitize_report", "_checked_report_result"},
        SystemMessage=SystemMessage, HumanMessage=HumanMessage,
    )
    agent.__class__ = cls
    model = SimpleNamespace(invoke=Mock(return_value=AIMessage(content=content or "")))
    tool = SimpleNamespace(name="offline_prices", invoke=Mock(return_value={"prices": []}))
    if content is None:
        model.invoke.side_effect = RuntimeError("offline provider failure: PRIVATE-TEST-ONLY")
    def fake_tool_boundary(messages, **kwargs):
        tool.invoke({"ticker": "000001"})
        return model.invoke(messages).content
    agent._llm = model
    agent._langchain_tools = [tool] if tools else []
    agent.invoke_with_tools = Mock(side_effect=fake_tool_boundary)
    agent._invoke_llm_with_trace = Mock(side_effect=model.invoke)
    return agent, model, tool


def make_researcher():
    cls, _ = load_methods(
        "core/agents/researcher.py", "ResearcherAgent", {"execute", "_build_quality_hint"},
        SystemMessage=SystemMessage, HumanMessage=HumanMessage,
    )
    agent = cls()
    agent.agent_id, agent.output_field, agent.stance = "bull_researcher_v2", "bull_report", "bullish"
    agent.memory = None
    agent._extract_common_params = lambda state: (state["ticker"], state["analysis_date"])
    agent._collect_reports = lambda state: {"market_report": state["market_report"]}
    agent._is_debate_mode = lambda state: False
    agent._build_system_prompt = lambda *args: "offline system"
    agent._build_user_prompt = lambda ticker, date, reports, history, state: history or "offline user"
    agent._apply_global_trading_advice_guard = lambda value: value
    agent._parse_response = lambda value: value
    agent._llm = SimpleNamespace(invoke=Mock(return_value=AIMessage(content=GOOD)))
    return agent


def make_run(runtime, schema_kind, content, peer_severity, *, builtin=False, tools=True):
    wf = runtime.workflow
    engine_cls, _ = load_methods(
        "core/workflow/engine.py", "WorkflowEngine",
        {"execute", "execute_async", "_build_execution_config", "_build_internal_state_fields",
         "_build_output_results", "_build_builtin_output", "_extract_text_value",
         "_generate_final_trade_decision", "_extract_text_from_state"},
        FieldType=runtime.models.FieldType, ANALYST_TOOL_MAPPING={}, WorkflowDefinition=Any,
        Callable=Callable, datetime=datetime, WorkflowExecutionState=wf.WorkflowExecutionState,
        _prepare_workflow_runtime_inputs=load_definitions(
            "core/workflow/engine.py", {"_prepare_workflow_runtime_inputs"}
        )["_prepare_workflow_runtime_inputs"],
    )
    engine = engine_cls()
    nodes = [
        wf.NodeDefinition(id="start", type="start"),
        wf.NodeDefinition(id="parallel", type="parallel"),
        wf.NodeDefinition(id="market_node", type="analyst", agent_id="market_analyst_v2"),
        wf.NodeDefinition(id="news_node", type="analyst", agent_id="news_analyst_v2"),
        wf.NodeDefinition(id="merge", type="merge"),
        wf.NodeDefinition(id="empty_update", type="post_processor", agent_id="offline_empty"),
        wf.NodeDefinition(id="research", type="researcher", agent_id="bull_researcher_v2"),
        wf.NodeDefinition(id="end", type="end"),
    ]
    pairs = [("start", "parallel"), ("parallel", "market_node"), ("parallel", "news_node"),
             ("market_node", "merge"), ("news_node", "merge"), ("merge", "empty_update"),
             ("empty_update", "research"), ("research", "end")]
    definition = wf.WorkflowDefinition(id="offline_quality", name="Offline quality", nodes=nodes,
        edges=[wf.EdgeDefinition(id=str(i), source=a, target=b) for i, (a, b) in enumerate(pairs)])
    builder_cls, _ = load_methods(
        "core/workflow/builder.py", "WorkflowBuilder",
        {"build", "_add_edges", "_get_default_state_schema", "_identify_debate_configs",
         "_create_node_function", "_create_parallel_node", "_create_merge_node"},
        StateGraph=StateGraph, START=START, END=END, NodeType=wf.NodeType,
        EdgeType=wf.EdgeType, NodeDefinition=wf.NodeDefinition, WorkflowDefinition=Any,
        Callable=Callable, Set=Set, ANALYST_TOOL_MAPPING={}, _is_manager_agent=lambda aid: False,
    )
    builder = builder_cls()
    builder._filter_analyst_nodes = lambda value: value  # configuration boundary
    if schema_kind == "dynamic":
        fields = [runtime.models.StateFieldDefinition(name=name) for name in
                  ("ticker", "analysis_date", "market_report", "news_report", "bull_report")]
        schema_builder = runtime.state_builder.StateSchemaBuilder()
        # IO registry metadata is fake; schema generation and reducers are product code.
        schema = schema_builder.build_from_agents("offline_quality", [], input_fields=fields,
                    internal_state_fields=engine._build_internal_state_fields(definition))
        schema_type = schema_builder.generate_typed_dict(schema)
    else:
        schema_type = None  # exercise the actual default schema branch in build()
    market, model, tool = make_market(runtime, content, tools)
    researcher = make_researcher()
    seen = []
    def peer(state):
        update = {"news_report": GOOD}
        if peer_severity:
            update["quality_flags"] = [{"agent_id": "news_analyst_v2", "severity": peer_severity,
                "reason": "offline peer quality finding", "retried": False}]
            if peer_severity == "critical":
                update["_node_errors"] = {"news_node": {"agent_id": "news_analyst_v2",
                    "label": "新闻分析师", "error": "PRIVATE-TEST-ONLY peer failure"}}
        return update
    def consume(state):
        seen.append(deepcopy(state))
        return researcher.execute(state)
    handlers = {"market_node": lambda state: market.execute({**state, "node_id": "market_node"}),
                "news_node": peer, "empty_update": lambda state: {"quality_flags": [], "_node_errors": {}},
                "research": consume}
    # Replace live agent factory only; build/add_edges/parallel/merge run intact.
    builder._create_agent_node = lambda node: handlers[node.id]
    graph = builder.build(definition, schema_type)
    assert isinstance(graph, CompiledStateGraph)
    engine._compiled_graph, engine._definition = graph, definition
    engine._task_id, engine._legacy_config = "offline-graph-task", {}
    engine._progress_max = 10
    engine._is_builtin_workflow = lambda value: builtin
    engine._extract_agent_ids = lambda value: []
    engine._collect_output_manifest = lambda state, value: (
        {field: {"content": state[field], "success": bool(state[field])}
         for field in ("market_report", "news_report", "bull_report")}, [])
    engine._create_execution = lambda inputs: wf.WorkflowExecution(id="offline-execution",
        workflow_id=definition.id, inputs=inputs)
    engine._init_progress_tracking = lambda: None
    engine._get_node_progress_info = lambda node: (50, node, node)
    engine._report_progress = Mock()
    return SimpleNamespace(engine=engine, graph=graph, market=market, model=model, tool=tool,
                           researcher=researcher, seen=seen, inputs={"ticker": "000001", "analysis_date": "2026-10-30"})


@pytest.mark.parametrize("schema_kind", ["dynamic", "fallback"])
@pytest.mark.parametrize("content,peer_severity", [(GOOD, None), (WARNING, "warning"),
                                                   ("", "critical"), (None, "warning")],
                         ids=["normal", "warnings", "two-critical", "provider-fallback"])
def test_real_graph_merges_flags_and_researcher_consumes_them(graph_runtime, schema_kind, content, peer_severity):
    run = make_run(graph_runtime, schema_kind, content, peer_severity)
    result = run.graph.invoke(run.inputs)
    assert len(run.seen) == 1  # real parallel join must run the consumer exactly once
    assert result["quality_flags"] == run.seen[0]["quality_flags"]
    assert result["_node_errors"] == run.seen[0]["_node_errors"]
    expected = 0 if content == GOOD else 2
    assert len(result["quality_flags"]) == expected
    if expected:
        assert {flag["agent_id"] for flag in result["quality_flags"]} == {"market_analyst_v2", "news_analyst_v2"}
        prompt = run.researcher._llm.invoke.call_args.args[0][1].content
        assert "market_analyst_v2" in prompt and "news_analyst_v2" in prompt
        assert ("质量不合格" if content in ("", None) else "质量存疑") in prompt
        assert all(not flag["retried"] for flag in result["quality_flags"])
    else:
        assert not result["_node_errors"]
        assert "质量提示" not in run.researcher._llm.invoke.call_args.args[0][1].content
    run.model.invoke.assert_called_once()
    run.tool.invoke.assert_called_once()
    run.market._check_and_retry_quality.assert_not_called()


@pytest.mark.parametrize("schema_kind", ["dynamic", "fallback"])
@pytest.mark.parametrize("async_mode", [False, True], ids=["sync", "async"])
@pytest.mark.parametrize("builtin", [False, True], ids=["custom-output", "builtin-output"])
def test_engine_keeps_graph_merged_state_through_c1_and_http(
        graph_runtime, schema_kind, async_mode, builtin, service, web):
    run = make_run(graph_runtime, schema_kind, "", "critical", builtin=builtin)
    before = deepcopy(run.inputs)
    result = asyncio.run(run.engine.execute_async(run.inputs)) if async_mode else run.engine.execute(run.inputs)
    assert run.inputs == before
    assert len(run.seen) == 1
    assert result["quality_flags"] == run.seen[0]["quality_flags"]
    assert len(result["quality_flags"]) == 2
    assert set(result["degraded_nodes"]) == {"market_node", "news_node"}
    assert run.engine._current_execution.state == "completed"
    assert run.engine._current_execution.outputs == result
    assert "_workflow_runtime" not in result
    node_events = [call.args[2] for call in run.engine._report_progress.call_args_list if call.args[0] == 50]
    assert sorted(node_events) == sorted(["parallel", "market_node", "news_node", "merge", "empty_update", "research"])
    item = task()
    item.result = service._format_analysis_result(result, item)
    item.result["stock_name"] = "离线示例"
    asyncio.run(service._update_task(item))
    saved_task = service.collection.update_one.call_args.args[1]["$set"]
    saved_task["task_params"] = item.task_params
    assert asyncio.run(service._save_to_analysis_reports(item, item.result))
    saved_report = service.db.analysis_reports.insert_one.call_args.args[0]
    for source in ("task", "report"):
        web.db.unified_analysis_tasks.find_one.return_value = saved_task if source == "task" else None
        web.db.analysis_reports.find_one.return_value = saved_report if source == "report" else None
        response = request_result(web)
        assert set(response["degraded_nodes"]) == {"market_node", "news_node"}
        assert response["degraded_nodes"]["market_node"]["agent_id"] == "market_analyst_v2"
        assert response["degraded_nodes"]["news_node"]["agent_id"] == "news_analyst_v2"
        assert "PRIVATE-TEST-ONLY" not in str(response)
        assert all(node["error"] == "该分析节点执行失败，详细原因请查看执行日志。"
                   for node in response["degraded_nodes"].values())
    run.model.invoke.assert_called_once()
    run.tool.invoke.assert_called_once()


@pytest.mark.parametrize("async_mode", [False, True], ids=["sync", "async"])
@pytest.mark.parametrize("content,severity", [(GOOD, None), (WARNING, "warning"), (None, "critical")],
                         ids=["normal", "warning", "provider-fallback"])
def test_engine_normal_warning_and_no_tool_fallback(graph_runtime, async_mode, content, severity):
    run = make_run(graph_runtime, "dynamic", content, None, tools=False)
    result = asyncio.run(run.engine.execute_async(run.inputs)) if async_mode else run.engine.execute(run.inputs)
    assert len(result["quality_flags"]) == int(severity is not None)
    if severity:
        assert result["quality_flags"][0]["severity"] == severity
    assert set(result.get("degraded_nodes", {})) == ({"market_node"} if severity == "critical" else set())
    assert result["market_report"] == (FALLBACK if content is None else content)
    run.model.invoke.assert_called_once()
    run.tool.invoke.assert_not_called()
    run.market.invoke_with_tools.assert_not_called()
    run.market._check_and_retry_quality.assert_not_called()
