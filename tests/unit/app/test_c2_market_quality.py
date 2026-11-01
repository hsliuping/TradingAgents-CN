"""Offline C2 checks over intact adapter/state/consumer function bodies.

Provider, SDK registration and storage startup are replaced by local fakes.
The original lexical validator and list reducer annotations are exercised;
this does not run a LangGraph instance or a real model/tool.
"""

import ast
from copy import deepcopy
import importlib.util
import logging
import os
import operator
from pathlib import Path
import re
import sys
from types import ModuleType, SimpleNamespace
from typing import Annotated, Any, Dict, List, Optional, Type, TypedDict, get_args, get_type_hints
from unittest.mock import Mock

import pytest

from test_c1_degraded_nodes import (
    no_external_connections, service, web, task, raw_result, request_result,
)


ROOT = Path(os.environ.get("PR1_SOURCE_ROOT", Path(__file__).resolve().parents[3])).resolve()
FALLBACK = "工具执行或模型生成未完成，当前结论仍待验证。"
GOOD = "研究观察：公开资料尚不足以支持单一情景，当前判断仍需结合成交与财务证据，重点关注风险与信息缺口。" * 2
WARNING = "公司共有三个部门，分别生产甲类产品、乙类产品和丙类产品，各部门员工数量分别为十二名、十五名和二十一名。" * 2
BLACKLIST = "研究结论：以下内容仅为本地测试资料。" * 4 + FALLBACK


def pure_module(monkeypatch, name, relative):
    spec = importlib.util.spec_from_file_location(name, ROOT / relative)
    module = importlib.util.module_from_spec(spec)
    monkeypatch.setitem(sys.modules, name, module)
    spec.loader.exec_module(module)
    return module


def package(monkeypatch, name, relative):
    module = ModuleType(name)
    module.__path__ = [str(ROOT / relative)]
    monkeypatch.setitem(sys.modules, name, module)
    return module


def load_methods(relative, name, methods, **namespace):
    path = ROOT / relative
    tree = ast.parse(path.read_text(encoding="utf-8-sig"), filename=str(path))
    owner = next(node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == name)
    owner.bases, owner.decorator_list = [], []
    owner.body = [node for node in owner.body
                  if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name in methods]
    for node in owner.body:
        node.decorator_list = [item for item in node.decorator_list
                               if isinstance(item, ast.Name) and item.id == "staticmethod"]
    # Keep the product's actual quality-gate import rather than injecting its symbol.
    imports = [node for node in tree.body if isinstance(node, ast.ImportFrom)
               and node.module == "core.agents.quality_gate"]
    constants = [node for node in tree.body if isinstance(node, ast.Assign)
                 and any(isinstance(target, ast.Name) and target.id in {
                     "_MARKET_REPORT_SANITIZE_RULES", "_BUILTIN_REPORT_FIELDS"}
                         for target in node.targets)]
    # These product modules evaluate annotations eagerly. Preserve that for
    # nested TypedDicts so reducer bindings use the original function locals.
    module = ast.Module(body=[*imports, *constants, owner], type_ignores=[])
    scope = {"__name__": __name__, "logger": logging.getLogger(__name__), "re": re,
             "Any": Any, "Dict": Dict, "List": List, "Optional": Optional, "Type": Type,
             "GENERIC_REPORT_FALLBACK": FALLBACK, "StockUtils": None, **namespace}
    exec(compile(ast.fix_missing_locations(module), str(path), "exec"), scope)
    return scope[name], scope


@pytest.fixture
def runtime(monkeypatch):
    # Avoid core.agents/core.state package initializers that register live tools.
    package(monkeypatch, "core.agents", "core/agents")
    package(monkeypatch, "core.state", "core/state")
    quality = pure_module(monkeypatch, "core.agents.quality_gate", "core/agents/quality_gate.py")
    models = pure_module(monkeypatch, "core.state.models", "core/state/models.py")
    reducers = pure_module(monkeypatch, "core.state.reducers", "core/state/reducers.py")
    package(monkeypatch, "langgraph", "unused")
    graph = package(monkeypatch, "langgraph.graph", "unused")
    messages = ModuleType("langgraph.graph.message")
    messages.add_messages = lambda left, right: (left or []) + (right or [])
    monkeypatch.setitem(sys.modules, "langgraph.graph.message", messages)

    class MessagesState(TypedDict):
        messages: list
    graph.MessagesState = MessagesState

    # The default state builder has an optional workshop metadata lookup.
    package(monkeypatch, "tradingagents.config", "tradingagents/config")
    mongo_utils = ModuleType("tradingagents.config.mongodb_utils")
    mongo_utils.build_mongodb_connection_string = lambda: "offline-unused"
    mongo_utils.get_mongodb_database_name = lambda: "offline"
    monkeypatch.setitem(sys.modules, mongo_utils.__name__, mongo_utils)
    pymongo = ModuleType("pymongo")
    class FakeMongoClient:
        def __init__(self, *args, **kwargs):
            pass
        def __getitem__(self, key):
            return SimpleNamespace(agent_configs=SimpleNamespace(find=lambda *args, **kwargs: []))
        def close(self):
            pass
    pymongo.MongoClient = FakeMongoClient
    monkeypatch.setitem(sys.modules, "pymongo", pymongo)
    trace = ModuleType("core.agents.execution_trace_recorder")
    trace.is_trace_enabled = lambda: False
    trace.start_execution_trace = Mock(side_effect=AssertionError("No trace storage in offline tests"))
    monkeypatch.setitem(sys.modules, trace.__name__, trace)
    return SimpleNamespace(quality=quality, models=models, reducers=reducers)


@pytest.fixture
def market(runtime):
    message = lambda content: SimpleNamespace(content=content)
    cls, _ = load_methods(
        "core/agents/adapters/market_analyst_v2.py", "MarketAnalystV2",
        {"execute", "_sanitize_report", "_checked_report_result"},
        SystemMessage=message, HumanMessage=message,
    )
    agent = cls()
    agent.agent_id, agent.agent_name = "market_analyst_v2", "市场分析师 v2.0"
    agent.analyst_type, agent.output_field = "market", "market_report"
    agent._extract_common_params = lambda state: (state.get("ticker"), "2026-10-30")
    agent._get_prompt_from_template = lambda **kwargs: None
    agent._build_system_prompt = lambda *args, **kwargs: "OFFLINE SYSTEM"
    agent._build_user_prompt = lambda *args, **kwargs: "OFFLINE USER"
    agent._build_analysis_prompt = lambda ticker: "OFFLINE ANALYSIS"
    agent._format_tool_call_summary = lambda: "offline tool summary"
    agent._llm = SimpleNamespace(invoke=Mock(side_effect=AssertionError("Use the existing invocation boundary")))
    agent._check_and_retry_quality = Mock(side_effect=AssertionError("C2 must not use automatic quality retries"))
    agent.invoke_with_tools = Mock(return_value=GOOD)
    agent._invoke_llm_with_trace = Mock(return_value=SimpleNamespace(content=GOOD))
    agent._langchain_tools = [SimpleNamespace(name="offline_tool")]
    return agent


def execute(market, content, tools=True):
    market._langchain_tools = [SimpleNamespace(name="offline_tool")] if tools else []
    market.invoke_with_tools.return_value = content
    market._invoke_llm_with_trace.return_value = SimpleNamespace(content=content)
    return market.execute({"ticker": "000001", "node_id": "custom_market_node"})


@pytest.mark.parametrize("tools", [True, False])
@pytest.mark.parametrize("content,severity", [(GOOD, None), (WARNING, "warning"),
                                               ("", "critical"), ("短报告", "critical"),
                                               (BLACKLIST, "critical"), (None, "critical")])
def test_actual_market_path_checks_once_without_reinvoking(market, runtime, monkeypatch, content, severity, tools):
    checked = Mock(wraps=runtime.quality.validate_analyst_report)
    monkeypatch.setattr(runtime.quality, "validate_analyst_report", checked)
    # The product imports the validator once at load, so reload after the spy.
    market_cls, _ = load_methods(
        "core/agents/adapters/market_analyst_v2.py", "MarketAnalystV2",
        {"execute", "_sanitize_report", "_checked_report_result"},
        SystemMessage=lambda content: SimpleNamespace(content=content),
        HumanMessage=lambda content: SimpleNamespace(content=content),
    )
    market.__class__ = market_cls
    output = execute(market, content, tools)
    assert output["market_report"] == content
    assert output["tool_call_summaries"] == {"market": "offline tool summary"}
    assert market.invoke_with_tools.call_count == int(tools)
    assert market._invoke_llm_with_trace.call_count == int(not tools)
    market._check_and_retry_quality.assert_not_called()
    market._llm.invoke.assert_not_called()
    checked.assert_called_once()
    if severity:
        flag, = output["quality_flags"]
        assert flag["severity"] == severity
        assert flag["agent_id"] == "market_analyst_v2"
        assert flag["ticker"] == "000001" and flag["retried"] is False
        if severity == "critical":
            assert output["_node_errors"]["custom_market_node"]["agent_id"] == "market_analyst_v2"
        else:
            assert "_node_errors" not in output
    else:
        assert "quality_flags" not in output and "_node_errors" not in output


@pytest.mark.parametrize("tools", [True, False])
def test_generation_exception_is_checked_and_marked_without_retry(market, tools):
    boundary = market.invoke_with_tools if tools else market._invoke_llm_with_trace
    boundary.side_effect = RuntimeError("private-do-not-publish")
    output = execute(market, GOOD, tools)
    assert output["market_report"] == FALLBACK
    assert output["quality_flags"][0]["severity"] == "critical"
    assert "custom_market_node" in output["_node_errors"]
    assert "private-do-not-publish" not in str(output)
    assert boundary.call_count == 1
    market._check_and_retry_quality.assert_not_called()


def test_new_invocation_does_not_reuse_instance_quality_flags(market):
    assert execute(market, "")["quality_flags"]
    output = execute(market, GOOD)
    assert "quality_flags" not in output and "_node_errors" not in output
    assert market.invoke_with_tools.call_count == 2


def test_lexically_valid_but_false_numbers_are_outside_this_gate(market):
    text = "研究结论：本虚构样本声称每股收益为99999元。该数字故意错误，用于说明长度和关键词检查不验证事实依据。" * 2
    output = execute(market, text)
    assert output["market_report"] == text
    assert "quality_flags" not in output


def schemas(runtime):
    engine_cls, _ = load_methods(
        "core/workflow/engine.py", "WorkflowEngine",
        {"_build_internal_state_fields", "_build_output_results", "_build_builtin_output", "_extract_text_value"},
        FieldType=runtime.models.FieldType, ANALYST_TOOL_MAPPING={}, WorkflowDefinition=Any,
    )
    definition = SimpleNamespace(id="offline", nodes=[
        SimpleNamespace(type="analyst", agent_id="market_analyst_v2", config={})])
    engine = engine_cls()
    internal = engine._build_internal_state_fields(definition)
    schema = runtime.models.WorkflowStateSchema(workflow_id="offline")
    for name, kind in internal.items():
        schema.add_field(runtime.models.StateFieldDefinition(name=name, type=kind))
    schema.add_field(runtime.models.StateFieldDefinition(name="market_report"))
    schema.add_field(runtime.models.StateFieldDefinition(name="unrelated_list", type="array"))
    dynamic_cls, _ = load_methods(
        "core/state/builder.py", "StateSchemaBuilder", {"generate_typed_dict"},
        __package__="core.state", FieldType=runtime.models.FieldType,
        WorkflowStateSchema=runtime.models.WorkflowStateSchema,
    )
    dynamic = dynamic_cls().generate_typed_dict(schema)
    builder_cls, _ = load_methods(
        "core/workflow/builder.py", "WorkflowBuilder", {"_get_default_state_schema"})
    fallback = builder_cls()._get_default_state_schema()
    bindings = {"Annotated": Annotated, "Any": Any, "List": List, "operator": operator,
                "keep_non_empty": runtime.reducers.keep_non_empty,
                "keep_latest_list": runtime.reducers.keep_latest_list,
                "merge_dict": runtime.reducers.merge_dict}
    return engine, [get_type_hints(item, globalns=bindings, include_extras=True)
                    for item in (dynamic, fallback)]


def test_quality_flags_survive_both_state_schemas_and_parallel_merge(runtime, market):
    _, states = schemas(runtime)
    output = execute(market, "")
    other_flag = {"agent_id": "news_analyst_v2", "severity": "warning", "reason": "offline"}
    for state in states:
        assert "quality_flags" in state and "_node_errors" in state
        merge = get_args(state["quality_flags"])[1]
        first = [deepcopy(other_flag)]
        second = output["quality_flags"]
        before = deepcopy((first, second))
        flags = merge(first, second)
        assert {flag["agent_id"] for flag in flags} == {"news_analyst_v2", "market_analyst_v2"}
        assert (first, second) == before
        assert merge(flags, []) == flags
        errors = get_args(state["_node_errors"])[1]({"news_node": {"agent_id": "news"}}, output["_node_errors"])
        assert set(errors) == {"news_node", "custom_market_node"}
    assert get_args(states[0]["unrelated_list"])[1] is runtime.reducers.keep_latest_list


@pytest.mark.parametrize("content,expected", [("", "质量不合格"), (WARNING, "质量存疑"), (GOOD, None)])
def test_researcher_receives_quality_notice_in_actual_model_input(runtime, market, content, expected):
    _, states = schemas(runtime)
    output = execute(market, content)
    state = {"ticker": "000001", "market_report": output["market_report"]}
    if "quality_flags" in output:
        assert "quality_flags" in states[0]
        state["quality_flags"] = get_args(states[0]["quality_flags"])[1]([], output["quality_flags"])
    message = lambda content: SimpleNamespace(content=content)
    cls, _ = load_methods("core/agents/researcher.py", "ResearcherAgent", {"execute", "_build_quality_hint"},
                          SystemMessage=message, HumanMessage=message)
    researcher = cls()
    researcher.agent_id, researcher.output_field, researcher.stance = "bull_researcher_v2", "bull_report", "bullish"
    researcher.memory = None
    researcher._extract_common_params = lambda value: ("000001", "2026-10-30")
    researcher._collect_reports = lambda value: {"market_report": value["market_report"]}
    researcher._is_debate_mode = lambda value: False
    researcher._build_system_prompt = lambda *args: "offline system"
    researcher._build_user_prompt = lambda ticker, date, reports, history, state: history or "offline user"
    researcher._apply_global_trading_advice_guard = lambda value: value
    researcher._parse_response = lambda value: value
    researcher._llm = SimpleNamespace(invoke=Mock(return_value=SimpleNamespace(content="offline research")))
    result = researcher.execute(state)
    assert result["bull_report"] == "offline research"
    messages = researcher._llm.invoke.call_args.args[0]
    if expected:
        assert expected in messages[1].content
        assert "market_analyst_v2" in messages[1].content and "已重试" not in messages[1].content
    else:
        assert "质量提示" not in messages[1].content


@pytest.mark.parametrize("builtin", [False, True], ids=["custom-workflow", "builtin-workflow"])
def test_critical_quality_marker_reaches_c1_web_output(runtime, market, service, web, builtin):
    import asyncio
    output = execute(market, "")
    assert "_node_errors" in output
    engine, _ = schemas(runtime)
    engine._definition = SimpleNamespace()
    engine._is_builtin_workflow = lambda definition: builtin
    engine._extract_agent_ids = lambda definition: []
    engine._collect_output_manifest = lambda value, definition: ({}, [])
    raw = raw_result()
    raw.pop("degraded_nodes")
    raw["final_trade_decision"] = {"action": "中性", "content": "离线固定研究结论，仅验证降级信息的交接。"}
    raw.update(output)
    final = engine._build_output_results(raw)
    assert set(final["degraded_nodes"]) == {"custom_market_node"}
    item = task()
    item.result = service._format_analysis_result(final, item)
    asyncio.run(service._update_task(item))
    persisted = service.collection.update_one.call_args.args[1]["$set"]
    persisted["task_params"] = item.task_params
    web.db.unified_analysis_tasks.find_one.return_value = persisted
    response = request_result(web)
    assert set(response["degraded_nodes"]) == {"custom_market_node"}
    assert response["degraded_nodes"]["custom_market_node"]["agent_id"] == "market_analyst_v2"
    assert market.invoke_with_tools.call_count == 1
