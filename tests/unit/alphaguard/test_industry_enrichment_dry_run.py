from __future__ import annotations

import importlib.util
import logging
from pathlib import Path
import sys
from unittest.mock import AsyncMock

import pytest


ROOT = Path(__file__).resolve().parents[3]
SCRIPT_PATH = ROOT / "scripts" / "补充行业信息_akshare.py"


def _load_script(module_name: str = "industry_enrichment_under_test"):
    spec = importlib.util.spec_from_file_location(module_name, SCRIPT_PATH)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_module_import_does_not_connect_to_mongodb_or_load_akshare(monkeypatch):
    import motor.motor_asyncio

    mongo_calls: list[tuple[tuple[object, ...], dict[str, object]]] = []

    def forbidden_client(*args, **kwargs):
        mongo_calls.append((args, kwargs))
        raise AssertionError("module import must not construct a MongoDB client")

    monkeypatch.setattr(
        motor.motor_asyncio,
        "AsyncIOMotorClient",
        forbidden_client,
    )
    monkeypatch.delitem(sys.modules, "akshare", raising=False)

    module = _load_script("industry_enrichment_import_test")

    assert mongo_calls == []
    assert "akshare" not in sys.modules
    assert callable(module.补充行业信息)


def test_default_cli_run_is_dry_run_without_network_or_database(
    monkeypatch, caplog
):
    module = _load_script()
    network_call = AsyncMock(
        side_effect=AssertionError("dry-run must not call AKShare")
    )

    def forbidden_client(*args, **kwargs):
        del args, kwargs
        raise AssertionError("dry-run must not connect to MongoDB")

    monkeypatch.setattr(module, "AsyncIOMotorClient", forbidden_client)
    monkeypatch.setattr(module, "get_stock_industry_from_akshare", network_call)
    monkeypatch.setattr(
        sys,
        "argv",
        [str(SCRIPT_PATH), "--limit", "12", "--batch-size", "4", "--delay", "0"],
    )

    with caplog.at_level(logging.INFO, logger=module.__name__):
        module.main()

    network_call.assert_not_awaited()
    assert "DRY-RUN" in caplog.text
    assert "limit=12" in caplog.text
    assert "batch_size=4" in caplog.text
    assert "MongoDB连接=0" in caplog.text
    assert "网络请求=0" in caplog.text
    assert "数据库写入=0" in caplog.text


@pytest.mark.asyncio
async def test_default_function_returns_explicit_zero_side_effect_summary(
    monkeypatch,
):
    module = _load_script("industry_enrichment_default_function_test")
    network_call = AsyncMock(
        side_effect=AssertionError("dry-run must not call AKShare")
    )

    def forbidden_client(*args, **kwargs):
        del args, kwargs
        raise AssertionError("dry-run must not connect to MongoDB")

    monkeypatch.setattr(module, "AsyncIOMotorClient", forbidden_client)
    monkeypatch.setattr(module, "get_stock_industry_from_akshare", network_call)

    result = await module.补充行业信息()

    assert result == {
        "mode": "DRY_RUN",
        "planned_limit": None,
        "batch_size": 50,
        "delay": 0.5,
        "database_connections": 0,
        "writes": 0,
        "network_requests": 0,
    }
    network_call.assert_not_awaited()


def test_execute_cli_flag_is_forwarded_without_real_side_effects(monkeypatch):
    module = _load_script("industry_enrichment_execute_cli_test")
    run = AsyncMock(return_value={"mode": "EXECUTE"})
    monkeypatch.setattr(module, "补充行业信息", run)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            str(SCRIPT_PATH),
            "--execute",
            "--limit",
            "3",
            "--batch-size",
            "2",
            "--delay",
            "0",
        ],
    )

    module.main()

    run.assert_awaited_once_with(
        limit=3,
        batch_size=2,
        delay=0.0,
        execute=True,
    )


@pytest.mark.asyncio
async def test_execute_enters_mocked_network_and_database_write_path(
    monkeypatch,
):
    module = _load_script("industry_enrichment_execute_path_test")
    client_instances = []
    network_call = AsyncMock(return_value={"industry": "银行", "area": "深圳"})

    class FakeCursor:
        def __init__(self) -> None:
            self.limit_value = None

        def limit(self, value: int):
            self.limit_value = value
            return self

        async def to_list(self, *, length):
            assert length is None
            assert self.limit_value == 1
            return [{"code": "000001", "name": "平安银行"}]

    class FakeUpdateResult:
        modified_count = 1

    class FakeCollection:
        def __init__(self) -> None:
            self.count_calls = 0
            self.cursor = FakeCursor()
            self.update_calls = []

        async def count_documents(self, query):
            assert "$or" in query
            self.count_calls += 1
            return 1 if self.count_calls == 1 else 0

        def find(self, query, projection):
            assert "$or" in query
            assert projection == {"code": 1, "symbol": 1, "name": 1, "_id": 0}
            return self.cursor

        async def update_one(self, query, update):
            self.update_calls.append((query, update))
            return FakeUpdateResult()

    class FakeDatabase:
        def __init__(self) -> None:
            self.collection = FakeCollection()

        def __getitem__(self, name):
            assert name == "stock_basic_info"
            return self.collection

    class FakeClient:
        def __init__(self, uri: str) -> None:
            assert uri == module.settings.MONGO_URI
            self.database = FakeDatabase()
            self.closed = False
            client_instances.append(self)

        def __getitem__(self, name):
            assert name == module.settings.MONGO_DB
            return self.database

        def close(self) -> None:
            self.closed = True

    monkeypatch.setattr(module, "AsyncIOMotorClient", FakeClient)
    monkeypatch.setattr(module, "get_stock_industry_from_akshare", network_call)

    await module.补充行业信息(execute=True, limit=1, batch_size=1, delay=0)

    assert len(client_instances) == 1
    collection = client_instances[0].database.collection
    assert collection.count_calls == 2
    assert collection.update_calls[0][0] == {
        "$or": [{"code": "000001"}, {"symbol": "000001"}]
    }
    assert collection.update_calls[0][1]["$set"]["industry"] == "银行"
    assert collection.update_calls[0][1]["$set"]["area"] == "深圳"
    assert client_instances[0].closed is True
    network_call.assert_awaited_once_with("000001")


def test_help_returns_success_and_documents_safety_gate(monkeypatch, capsys):
    module = _load_script("industry_enrichment_help_test")
    monkeypatch.setattr(sys, "argv", [str(SCRIPT_PATH), "--help"])

    with pytest.raises(SystemExit) as exc_info:
        module.main()

    assert exc_info.value.code == 0
    output = capsys.readouterr().out
    assert "--execute" in output
    assert "默认仅dry-run" in output
    assert "不联网、不连接MongoDB、不写入数据" in output


@pytest.mark.parametrize(
    "arguments",
    (
        ["--limit", "0"],
        ["--limit", "invalid"],
        ["--batch-size", "0"],
        ["--delay", "-0.1"],
    ),
)
def test_invalid_arguments_exit_before_execution(monkeypatch, capsys, arguments):
    module = _load_script(
        "industry_enrichment_invalid_" + "_".join(arguments).replace("-", "x")
    )
    run = AsyncMock()
    monkeypatch.setattr(module, "补充行业信息", run)
    monkeypatch.setattr(sys, "argv", [str(SCRIPT_PATH), *arguments])

    with pytest.raises(SystemExit) as exc_info:
        module.main()

    assert exc_info.value.code == 2
    assert "error:" in capsys.readouterr().err
    run.assert_not_awaited()
