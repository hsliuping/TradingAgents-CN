"""Offline regression for the real result formatter, persistence and HTTP route.

Load complete function/method AST definitions from product files, leaving their
bodies intact, to avoid importing application startup, database clients or LLM
providers. Storage/auth are fakes; FastAPI serialization runs through TestClient.
No source fragments are replaced with test implementations.
"""

import ast
from copy import deepcopy
from datetime import datetime
from enum import Enum
import logging
import os
from pathlib import Path
import socket
import sys
from threading import local
from types import ModuleType, SimpleNamespace
from typing import Any, Dict, List, Optional
from unittest.mock import AsyncMock

from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.testclient import TestClient
import pytest



ROOT = Path(os.environ.get("PR1_SOURCE_ROOT", Path(__file__).resolve().parents[3])).resolve()
TASK_ID = "offline-c1-task"
RAW_NODES = {
    "news_node": {
        "agent_id": "news_analyst_v2",
        "label": "新闻分析师",
        "error": "private provider exception: token=do-not-publish",
        "internal_context": {"private": "do-not-publish"},
    },
    "market_node": {
        "agent_id": "market_analyst_v2",
        "label": "市场分析师",
        "error": "private database location",
    },
}
PUBLIC_NODES = {
    key: {"agent_id": value["agent_id"], "label": value["label"],
          "error": "该分析节点执行失败，详细原因请查看执行日志。"}
    for key, value in RAW_NODES.items()
}


async def current_user():
    return {"id": "offline-user"}


class TaskType(str, Enum):
    STOCK_ANALYSIS = "stock_analysis"
    ETF_ANALYSIS = "etf_analysis"


def load_definitions(relative, names, class_name=None, **extra):
    path = ROOT / relative
    tree = ast.parse(path.read_text(encoding="utf-8-sig"), filename=str(path))
    if class_name:
        owner = next(node for node in tree.body
                     if isinstance(node, ast.ClassDef) and node.name == class_name)
        owner.body = [node for node in owner.body
                      if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
                      and node.name in names]
        nodes = [owner]
    else:
        nodes = [node for node in tree.body
                 if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
                 and node.name in names]
    for node in ast.walk(ast.Module(body=nodes, type_ignores=[])):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            node.decorator_list = []
    imports = [node for node in tree.body if isinstance(node, ast.ImportFrom)
               and node.module == "app.utils.result_metadata"]
    module = ast.Module(body=[ast.ImportFrom(module="__future__", names=[
        ast.alias(name="annotations")], level=0), *imports, *nodes], type_ignores=[])
    namespace = {
        "__name__": __name__, "Dict": Dict, "Any": Any, "Optional": Optional,
        "List": List, "datetime": datetime, "logger": logging.getLogger(__name__),
        "HTTPException": HTTPException, "Query": Query, "Depends": Depends,
        "get_current_user": current_user, "AnalysisTaskType": TaskType, **extra,
    }
    exec(compile(ast.fix_missing_locations(module), str(path), "exec"), namespace)
    return namespace


@pytest.fixture(autouse=True)
def no_external_connections(monkeypatch):
    def blocked(*args, **kwargs):
        raise AssertionError("Offline test attempted an external connection")
    # Windows implements asyncio's internal wake-up socketpair over loopback.
    # Permit only connections made inside that stdlib constructor, not services.
    scope = local()
    original_pair, original_connect = socket.socketpair, socket.socket.connect

    def internal_pair(*args, **kwargs):
        scope.creating_pair = True
        try:
            return original_pair(*args, **kwargs)
        finally:
            scope.creating_pair = False

    def connect(sock, address):
        if getattr(scope, "creating_pair", False):
            return original_connect(sock, address)
        return blocked()

    monkeypatch.setattr(socket, "create_connection", blocked)
    monkeypatch.setattr(socket, "getaddrinfo", blocked)
    monkeypatch.setattr(socket, "socketpair", internal_pair)
    monkeypatch.setattr(socket.socket, "connect", connect)
    monkeypatch.setattr(socket.socket, "connect_ex", blocked)


@pytest.fixture
def service():
    namespace = load_definitions(
        "app/services/task_analysis_service.py",
        {"_format_analysis_result", "_format_decision_dict", "_extract_decision_from_text",
         "_update_task", "_save_to_analysis_reports"},
        class_name="TaskAnalysisService",
    )
    instance = namespace["TaskAnalysisService"]()
    instance.logger = logging.getLogger(__name__)
    instance.collection = SimpleNamespace(update_one=AsyncMock())
    instance.db = SimpleNamespace(analysis_reports=SimpleNamespace(
        insert_one=AsyncMock(return_value=SimpleNamespace(inserted_id="offline-report"))))
    return instance


def task():
    params = {"symbol": "000001", "stock_code": "000001", "analysis_date": "2026-10-30",
              "selected_analysts": ["market", "news"], "research_depth": "标准"}
    item = SimpleNamespace(task_id=TASK_ID, task_params=params, execution_time=1.0,
                           task_type=TaskType.STOCK_ANALYSIS, engine_type="auto", user_id=None)
    item.model_dump = lambda **kwargs: {"task_id": TASK_ID, "result": deepcopy(item.result)}
    return item


def raw_result():
    return {
        "final_decision": {"action": "中性", "confidence": 0.6, "risk_score": 0.5,
                           "reasoning": "离线固定研究结论，保留不确定性及缺失数据。"},
        "investment_plan": {"summary": "这是离线固定摘要，仅用于验证结果字段的传递。"},
        "structured_reports": {"market_report": {"success": True,
                                                  "content": "完整市场报告：离线资料未显示明确变化。"}},
        "report_manifest": [{"field": "market_report", "has_content": True}],
        "degraded_nodes": deepcopy(RAW_NODES),
    }


def payload(nodes=RAW_NODES):
    result = {
        "summary": "这是可以展示的固定研究摘要。", "recommendation": "请结合研究资料判断不确定性。",
        "reports": {"market_report": "完整市场报告：离线资料未显示明确变化。"},
        "decision": {"action": "中性", "confidence": 0.6, "risk_score": 0.5,
                     "reasoning": "研究依据来自离线固定资料，不涉及模型调用。"},
        "stock_symbol": "000001", "stock_code": "000001", "analysis_date": "2026-10-30",
    }
    if nodes is not None:
        result["degraded_nodes"] = deepcopy(nodes)
    return result


def assert_public(result, expected=PUBLIC_NODES):
    assert result["degraded_nodes"] == expected
    assert "do-not-publish" not in str(result)
    assert "internal_context" not in str(result)


def test_formatter_preserves_degradation_and_normal_business_fields(service):
    raw = raw_result()
    before = deepcopy(raw)
    result = service._format_analysis_result(raw, task())
    assert_public(result)
    assert raw == before
    normal = deepcopy(raw)
    del normal["degraded_nodes"]
    expected = service._format_analysis_result(normal, task())
    for output in (result, expected):
        output.pop("analysis_id")  # independently generated identifier
    assert {key: value for key, value in result.items() if key != "degraded_nodes"} == expected
    assert "degraded_nodes" not in expected


@pytest.mark.parametrize("nodes", [RAW_NODES, {}, None])
def test_formatted_result_survives_task_and_report_persistence(service, nodes):
    import asyncio
    raw = raw_result()
    if nodes is None:
        raw.pop("degraded_nodes")
    else:
        raw["degraded_nodes"] = deepcopy(nodes)
    item = task()
    item.result = service._format_analysis_result(raw, item)
    item.result["stock_name"] = "离线示例"
    asyncio.run(service._update_task(item))
    saved_task = service.collection.update_one.call_args.args[1]["$set"]
    assert saved_task["result"] == item.result
    assert asyncio.run(service._save_to_analysis_reports(item, item.result))
    saved_report = service.db.analysis_reports.insert_one.call_args.args[0]
    for result in (saved_task["result"], saved_report):
        if nodes is None:
            assert "degraded_nodes" not in result
        else:
            assert_public(result, PUBLIC_NODES if nodes else {})
    assert saved_report["status"] == "completed"


@pytest.fixture
def web(monkeypatch):
    collections = {name: SimpleNamespace(find_one=AsyncMock(return_value=None))
                   for name in ("unified_analysis_tasks", "analysis_reports", "analysis_tasks")}
    db = SimpleNamespace(**collections)
    database = ModuleType("app.core.database")
    database.get_mongo_db = lambda: db
    monkeypatch.setitem(sys.modules, "app.core.database", database)
    state = SimpleNamespace(get_task_status=AsyncMock(return_value=None))
    namespace = load_definitions(
        "app/routers/analysis.py",
        {"normalize_result_data", "_has_meaningful_text", "_summarize_result_completeness",
         "_log_result_completeness", "get_task_result"},
        get_simple_analysis_service=lambda: state,
        format_http_error_detail=lambda exc: str(exc),
    )
    app = FastAPI()
    app.add_api_route("/api/analysis/tasks/{task_id}/result", namespace["get_task_result"],
                      methods=["GET"], response_model=Dict[str, Any])
    with TestClient(app) as client:
        yield SimpleNamespace(client=client, state=state, db=db, namespace=namespace)


def request_result(web):
    response = web.client.get(f"/api/analysis/tasks/{TASK_ID}/result")
    assert response.status_code == 200, response.text
    envelope = response.json()
    assert envelope["success"] is True
    return envelope["data"]


@pytest.mark.parametrize("source", ["memory", "unified_tasks", "mongodb", "analysis_tasks"])
@pytest.mark.parametrize("nodes", [RAW_NODES, {}, None])
def test_http_result_preserves_metadata_for_each_source(web, source, nodes):
    result = payload(nodes)
    if source == "memory":
        web.state.get_task_status.return_value = {"status": "completed", "result_data": result}
    elif source == "unified_tasks":
        web.db.unified_analysis_tasks.find_one.return_value = {
            "task_id": TASK_ID, "task_params": task().task_params, "result": result}
    elif source == "mongodb":
        web.db.analysis_reports.find_one.return_value = result
    else:
        web.db.analysis_tasks.find_one.return_value = {"symbol": "000001", "result": result}
    output = request_result(web)
    if nodes is None:
        assert "degraded_nodes" not in output
    else:
        assert_public(output, PUBLIC_NODES if nodes else {})
    assert output["reports"] == result["reports"]
    assert output["summary"] == result["summary"]
    assert output["decision"] == result["decision"]
    if source == "memory":
        web.db.unified_analysis_tasks.find_one.assert_not_called()
    else:
        assert output["source"] == source


@pytest.mark.parametrize("incomplete", ["memory", "unified_tasks"])
def test_incomplete_result_falls_back_to_report_with_its_metadata(web, incomplete):
    # Metadata alone is not a usable report. Do not merge it into another
    # source's result (the sources may describe different result snapshots).
    shell = {"reports": {}, "summary": "", "decision": {},
             "degraded_nodes": {"old_node": {"agent_id": "old_agent"}}}
    if incomplete == "memory":
        web.state.get_task_status.return_value = {"status": "completed", "result_data": shell}
    else:
        web.db.unified_analysis_tasks.find_one.return_value = {"task_id": TASK_ID, "result": shell}
    web.db.analysis_reports.find_one.return_value = payload()
    result = request_result(web)
    assert result["source"] == "mongodb"
    assert_public(result)


def test_valid_unified_result_is_not_overwritten_by_legacy_fallback(web):
    web.db.unified_analysis_tasks.find_one.return_value = {
        "task_id": TASK_ID, "task_params": task().task_params, "result": payload()}
    web.db.analysis_tasks.find_one.return_value = {"result": payload(None)}
    result = request_result(web)
    assert result["source"] == "unified_tasks"
    assert_public(result)
    web.db.analysis_tasks.find_one.assert_not_called()
    web.db.analysis_reports.find_one.assert_not_called()


def test_report_lookup_by_legacy_analysis_id_preserves_metadata(web):
    web.db.analysis_reports.find_one.side_effect = [None, payload()]
    web.db.analysis_tasks.find_one.return_value = {"result": {"analysis_id": "legacy-report"}}
    assert_public(request_result(web))
    assert web.db.analysis_reports.find_one.call_args_list[1].args[0] == {"analysis_id": "legacy-report"}


def test_missing_result_remains_404(web):
    response = web.client.get(f"/api/analysis/tasks/{TASK_ID}/result")
    assert response.status_code == 404


def test_normalization_retains_recorded_metadata(web):
    result = payload()
    assert web.namespace["normalize_result_data"](result)["degraded_nodes"] == RAW_NODES


@pytest.mark.parametrize("value", [None, [], "invalid", {"node": "invalid"}])
def test_malformed_metadata_is_not_reported_as_empty_success(value):
    from app.utils.result_metadata import public_degraded_nodes
    assert public_degraded_nodes(value) is None


def test_projection_does_not_mutate_or_alias_raw_metadata():
    from app.utils.result_metadata import public_degraded_nodes
    original = deepcopy(RAW_NODES)
    public = public_degraded_nodes(original)
    assert_public({"degraded_nodes": public})
    public["news_node"]["label"] = "changed"
    assert original == RAW_NODES


def test_report_saver_filters_raw_metadata_for_direct_callers():
    from app.utils.report_saver import save_analysis_report
    import asyncio
    collection = SimpleNamespace(insert_one=AsyncMock(return_value=SimpleNamespace(inserted_id="report")))
    asyncio.run(save_analysis_report(
        SimpleNamespace(analysis_reports=collection), "000001", "离线示例", "A股", "offline",
        {"market_report": "完整离线报告"}, {"action": "中性"}, "研究参考", 0.5, "中",
        degraded_nodes=deepcopy(RAW_NODES),
    ))
    assert_public(collection.insert_one.call_args.args[0])


def test_pipeline_formatter_task_storage_and_http_fallback(service, web):
    import asyncio
    item = task()
    item.result = service._format_analysis_result(raw_result(), item)
    asyncio.run(service._update_task(item))
    persisted = service.collection.update_one.call_args.args[1]["$set"]
    persisted["task_params"] = item.task_params
    web.db.unified_analysis_tasks.find_one.return_value = persisted
    result = request_result(web)
    assert_public(result)
    assert result["reports"] == item.result["reports"]
