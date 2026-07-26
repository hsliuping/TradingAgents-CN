from __future__ import annotations

import ast
from datetime import date
from pathlib import Path

import pytest
from bson import BSON
from fastapi import HTTPException

import app.routers.alphaguard_experiments as experiment_router
from app.models.alphaguard.experiment_collections import EXPERIMENT_COLLECTIONS
from app.services.alphaguard.champion_resolver import ChampionResolver
from app.services.alphaguard.evidence_snapshot_service import (
    calculate_immutable_hash,
)
from app.services.alphaguard.experiment_component_adapters import (
    build_current_component_record,
    current_component_payloads,
)
from app.services.alphaguard.experiment_registry import ExperimentRegistry
from app.services.alphaguard.experiment_repository import experiment_document
from app.services.alphaguard.experiment_task_service import ExperimentTaskService
from app.services.alphaguard.factor_registry import FactorRegistry
from app.services.alphaguard.quant_research_pipeline import QuantResearchPipeline
from app.services.alphaguard.strategy_registry import StrategyRegistry
from tests.unit.alphaguard._fakes import FakeDB
from tests.unit.alphaguard.pr008_helpers import (
    seed_champion_assignment,
    seed_single_variable_experiment,
)
from tests.unit.alphaguard.test_quant_pipeline_pr004 import (
    build_pipeline_snapshot,
)
from tradingagents.alphaguard.mongo_indexes import ALPHAGUARD_INDEX_SPECS


PROJECT_ROOT = Path(__file__).resolve().parents[3]


def test_experiment_documents_encode_trade_dates_for_real_mongodb():
    document = experiment_document(
        {
            "activation_trade_date": date(2026, 7, 27),
            "nested": {"effective_date": date(2026, 7, 28)},
        }
    )
    BSON.encode(document)
    assert document["activation_trade_date"].date() == date(2026, 7, 27)
    assert document["nested"]["effective_date"].date() == date(2026, 7, 28)


def test_all_pr008_collections_have_create_only_index_specs():
    assert set(EXPERIMENT_COLLECTIONS.values()) <= set(ALPHAGUARD_INDEX_SPECS)
    for collection in EXPERIMENT_COLLECTIONS.values():
        assert ALPHAGUARD_INDEX_SPECS[collection], collection


def test_experiment_api_exposes_no_delete_or_client_result_creation():
    routes = {
        (method, route.path)
        for route in experiment_router.router.routes
        for method in route.methods
    }
    assert not {item for item in routes if item[0] == "DELETE"}
    forbidden_posts = {
        "/alphaguard/experiment-results",
        "/alphaguard/champion-assignments",
        "/alphaguard/shadow-outputs",
        "/alphaguard/promotion-approvals",
    }
    assert not {path for method, path in routes if method == "POST"} & forbidden_posts


def test_every_experiment_api_write_handler_has_explicit_admin_gate():
    source = (
        PROJECT_ROOT / "app/routers/alphaguard_experiments.py"
    ).read_text(encoding="utf-8")
    tree = ast.parse(source)
    write_handlers = []
    for node in tree.body:
        if not isinstance(node, (ast.AsyncFunctionDef, ast.FunctionDef)):
            continue
        is_write = any(
            isinstance(decorator, ast.Call)
            and isinstance(decorator.func, ast.Attribute)
            and decorator.func.attr in {"post", "put", "patch", "delete"}
            for decorator in node.decorator_list
        )
        if is_write:
            write_handlers.append(node)
    assert write_handlers
    for handler in write_handlers:
        calls = [
            child
            for child in ast.walk(handler)
            if isinstance(child, ast.Call)
            and isinstance(child.func, ast.Name)
            and child.func.id == "_require_admin"
        ]
        assert calls, f"{handler.name} lacks explicit _require_admin gate"


def test_non_admin_is_rejected_before_any_write():
    with pytest.raises(HTTPException) as exc:
        experiment_router._require_admin({"id": "user-1", "is_admin": False})
    assert exc.value.status_code == 403


@pytest.mark.asyncio
async def test_non_admin_list_is_scoped_to_own_experiments(monkeypatch):
    db = FakeDB()
    _, own, _, _ = await seed_single_variable_experiment(
        db, user_id="user-1"
    )
    await seed_single_variable_experiment(db, user_id="user-2")
    monkeypatch.setattr(experiment_router, "get_mongo_db", lambda: db)
    response = await experiment_router.list_experiments(
        current_user={"id": "user-1", "is_admin": False},
        status=None,
        limit=100,
    )
    items = response["data"]["items"]
    assert [item["experiment_id"] for item in items] == [own.experiment_id]


@pytest.mark.asyncio
async def test_experiment_task_queue_is_db_backed_and_idempotent():
    db = FakeDB()
    service = ExperimentTaskService(db)
    payload = {"as_of_trade_date": date(2026, 7, 27).isoformat()}
    first = await service.enqueue(
        "EXPERIMENT_RECONCILIATION",
        experiment_id=None,
        payload=payload,
        requested_by="scheduler",
        trade_date=date(2026, 7, 27),
    )
    second = await service.enqueue(
        "EXPERIMENT_RECONCILIATION",
        experiment_id=None,
        payload=payload,
        requested_by="scheduler",
        trade_date=date(2026, 7, 27),
    )
    assert first.task_run_id == second.task_run_id
    assert db["ag_exp_task_runs"].count() == 1
    assert await service.process(
        job_types={"EXPERIMENT_RECONCILIATION"}
    ) == {"completed": 1, "failed": 0}
    assert await service.process(
        job_types={"EXPERIMENT_RECONCILIATION"}
    ) == {"completed": 0, "failed": 0}
    assert db["ag_exp_task_runs"].count() == 1


@pytest.mark.asyncio
async def test_new_quant_task_consumes_snapshot_locked_champions_not_latest():
    db = FakeDB()
    await FactorRegistry(db).seed_builtins()
    await StrategyRegistry(db).seed_builtins()
    registry = ExperimentRegistry(db)
    records = []
    for descriptor in current_component_payloads():
        record = build_current_component_record(
            descriptor, created_by="test"
        )
        await registry.register_component_version(record)
        await seed_champion_assignment(
            db, record, effective_date=date(2026, 1, 1)
        )
        records.append(record)
    refs = await ChampionResolver(db).resolve_required_components(
        market="CN", as_of_trade_date=date(2026, 7, 1)
    )
    assert len(refs) == len(records) == 5
    snapshot = await build_pipeline_snapshot(db)
    payload = snapshot.model_dump(mode="python")
    payload["champion_version_refs"] = refs
    payload["immutable_hash"] = calculate_immutable_hash(payload)
    await db["ag_evidence_snapshots"].replace_one(
        {"snapshot_id": snapshot.snapshot_id}, payload
    )
    proposals = await QuantResearchPipeline(db).evaluate(
        snapshot.snapshot_id, user_id="user"
    )
    assert {item.strategy_version for item in proposals} == {
        item.version_ref
        for item in records
        if item.component_type == "STRATEGY_CONFIG"
    }
    assert all(
        item.factor_set_version.startswith("champion:")
        for item in proposals
    )
    assert {
        item["regime_version"]
        for item in db["ag_regime_results"].documents
    } == {"regime:market-regime-v1"}


def test_experiment_execution_has_no_broker_or_live_order_dependency():
    service_files = [
        "historical_replay_engine.py",
        "shadow_experiment_service.py",
        "robustness_test_service.py",
        "champion_comparison_service.py",
        "experiment_risk_review_service.py",
    ]
    combined = "\n".join(
        (
            PROJECT_ROOT / "app/services/alphaguard" / filename
        ).read_text(encoding="utf-8")
        for filename in service_files
    )
    forbidden = (
        "BrokerAdapter",
        "OrderService(",
        '["paper_accounts"]',
        '["paper_orders"]',
        '["paper_trades"]',
        "live_trading_enabled = true",
    )
    assert not [token for token in forbidden if token in combined]


def test_shadow_and_replay_only_persist_experiment_collections():
    for filename in (
        "historical_replay_engine.py",
        "shadow_experiment_service.py",
    ):
        source = (
            PROJECT_ROOT / "app/services/alphaguard" / filename
        ).read_text(encoding="utf-8")
        write_lines = [
            line.strip()
            for line in source.splitlines()
            if any(
                token in line
                for token in (
                    ".insert_one(",
                    ".replace_one(",
                    ".update_one(",
                    ".delete_one(",
                )
            )
        ]
        assert write_lines
        assert all("ag_exp_" in line for line in write_lines), (
            filename,
            write_lines,
        )
