"""Offline contract regressions added during the cumulative C1/C2 review."""

import asyncio
from copy import deepcopy

import pytest
from langchain_core.messages import AIMessage, HumanMessage
from langgraph.graph import END, START, StateGraph

from test_c1_degraded_nodes import (
    TASK_ID, no_external_connections, payload, request_result, task, web,
)
from test_c2_market_quality import FALLBACK, GOOD, market, runtime
from test_c2_langgraph_integration import graph_runtime, make_run


@pytest.mark.parametrize("schema_kind", ["dynamic", "fallback"])
@pytest.mark.parametrize("async_mode", [False, True], ids=["sync", "async"])
def test_engine_returns_all_reduced_channels_and_isolates_runs(graph_runtime, schema_kind, async_mode):
    run = make_run(graph_runtime, schema_kind, GOOD, None)
    graph = StateGraph(run.graph.builder.schema)
    flags = [{"agent_id": name, "severity": "critical", "reason": "offline finding", "retried": False}
             for name in ("market_analyst_v2", "news_analyst_v2")]
    seen = []
    graph.add_node("first", lambda state: {
        "market_report": GOOD,
        "messages": [AIMessage(id="reply", content="offline reply")],
        "_market_messages": [AIMessage(content="temporary tool history")],
        "tool_call_summaries": {"market": "offline market"},
    })
    def branch(index):
        update = {"quality_flags": [flags[index]],
            "_node_errors": {f"node_{index}": {"agent_id": flags[index]["agent_id"], "error": "offline"}},
            "tool_call_summaries": {f"peer_{index}": "offline peer"}}
        if index == 0:
            update["messages"] = [HumanMessage(id="seed", content="revised offline input")]
        return lambda state: deepcopy(update)
    graph.add_node("left", branch(0))
    graph.add_node("right", branch(1))
    graph.add_node("clear", lambda state: {"market_report": "", "quality_flags": [],
        "_node_errors": {}, "_market_messages": [], "tool_call_summaries": {}})
    def observe(state):
        seen.append(deepcopy(state))
        return {}
    graph.add_node("observe", observe)
    graph.add_edge(START, "first")
    graph.add_edge("first", "left")
    graph.add_edge("first", "right")
    graph.add_edge(["left", "right"], "clear")
    graph.add_edge("clear", "observe")
    graph.add_edge("observe", END)
    run.engine._compiled_graph = graph.compile()
    inputs = {**run.inputs, "messages": [HumanMessage(id="seed", content="original offline input")]}
    before = deepcopy(inputs)
    outputs = []
    for iteration in range(2):
        result = asyncio.run(run.engine.execute_async(inputs)) if async_mode else run.engine.execute(inputs)
        outputs.append(deepcopy(result))
        assert inputs == before
        assert len(seen) == iteration + 1
        for field in ("quality_flags", "_node_errors", "messages", "market_report",
                      "_market_messages", "tool_call_summaries"):
            assert result[field] == seen[-1][field]
        assert result["market_report"] == GOOD  # keep_non_empty rejects later empty text
        assert result["_market_messages"] == []  # keep_latest_list permits explicit clearing
        assert len(result["quality_flags"]) == 2
        assert {flag["agent_id"] for flag in result["quality_flags"]} == {flag["agent_id"] for flag in flags}
        assert set(result["degraded_nodes"]) == {"node_0", "node_1"}
        assert set(result["tool_call_summaries"]) == {"market", "peer_0", "peer_1"}
        assert [(message.id, message.content) for message in result["messages"]] == [
            ("seed", "revised offline input"), ("reply", "offline reply")]
        assert "_workflow_runtime" not in result
    assert outputs[0]["quality_flags"] == outputs[1]["quality_flags"]
    assert outputs[0]["_node_errors"] == outputs[1]["_node_errors"]
    run.model.invoke.assert_not_called()
    run.tool.invoke.assert_not_called()


@pytest.mark.parametrize("source", ["memory", "unified_tasks", "mongodb", "analysis_tasks"])
def test_malformed_historical_metadata_does_not_break_http(web, source):
    result = payload({"old_node": "invalid legacy shape"})
    if source == "memory":
        web.state.get_task_status.return_value = {"status": "completed", "result_data": result}
    elif source == "unified_tasks":
        web.db.unified_analysis_tasks.find_one.return_value = {
            "task_id": TASK_ID, "task_params": task().task_params, "result": result}
    elif source == "mongodb":
        web.db.analysis_reports.find_one.return_value = result
    else:
        web.db.analysis_tasks.find_one.return_value = {"symbol": "000001", "result": result}
    response = request_result(web)
    assert "degraded_nodes" not in response  # invalid metadata must not claim an empty successful run
    assert response["reports"] == result["reports"]
    assert response["decision"] == result["decision"]


@pytest.mark.parametrize("failure", ["missing_ticker", "missing_model"])
def test_market_pre_generation_failure_is_marked_without_invocation(market, failure):
    state = {"ticker": "000001", "node_id": "pre_generation_node"}
    if failure == "missing_ticker":
        state["ticker"] = ""
    else:
        market._llm = None
    result = market.execute(state)
    assert result["market_report"] == FALLBACK
    assert result["quality_flags"][0]["severity"] == "critical"
    assert result["quality_flags"][0]["retried"] is False
    assert set(result["_node_errors"]) == {"pre_generation_node"}
    market.invoke_with_tools.assert_not_called()
    market._invoke_llm_with_trace.assert_not_called()
    market._check_and_retry_quality.assert_not_called()
