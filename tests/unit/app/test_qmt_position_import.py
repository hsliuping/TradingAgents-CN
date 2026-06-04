import asyncio
from types import ModuleType, SimpleNamespace
import sys

import pandas as pd
import pytest

import app.services.data_sources.qmt_adapter as qmt_module
from app.models.portfolio import PositionCreate, PositionSource
from app.services.portfolio_service import PortfolioService


class _FakeTrader:
    def __init__(self, path: str, session: int):
        self.path = path
        self.session = session
        self.started = False
        self.stopped = False

    def start(self):
        self.started = True

    def connect(self):
        return 0

    def query_stock_positions(self, account):
        assert account.account_id == "123456"
        return [
            SimpleNamespace(
                stock_code="600000.SH",
                volume=100,
                can_use_volume=80,
                open_price=10.25,
                market_value=1025.0,
                frozen_volume=10,
                on_road_volume=0,
                yesterday_volume=90,
            )
        ]

    def query_stock_asset(self, account):
        assert account.account_id == "123456"
        return SimpleNamespace(cash=1000.0, total_asset=2025.0)

    def stop(self):
        self.stopped = True


def test_qmt_query_account_positions_builds_import_rows(monkeypatch):
    fake_trader = _FakeTrader(r"D:\gjzq\userdata", 20260604)

    fake_xttrader = ModuleType("xtquant.xttrader")
    fake_xttrader.XtQuantTrader = lambda path, session: fake_trader

    fake_xttype = ModuleType("xtquant.xttype")

    class _FakeStockAccount:
        def __init__(self, account_id, account_type="STOCK"):
            self.account_id = account_id
            self.account_type = account_type

    fake_xttype.StockAccount = _FakeStockAccount

    fake_xtquant = ModuleType("xtquant")
    fake_xtquant.__path__ = []
    fake_xtquant.xttype = fake_xttype

    monkeypatch.setitem(sys.modules, "xtquant", fake_xtquant)
    monkeypatch.setitem(sys.modules, "xtquant.xttype", fake_xttype)
    monkeypatch.setattr(qmt_module, "_get_xttrader", lambda: fake_xttrader, raising=True)
    monkeypatch.setattr(qmt_module, "_get_xtdata", lambda: SimpleNamespace(get_instrument_detail=lambda _xt_code: {"InstrumentName": "浦发银行"}), raising=True)
    monkeypatch.setattr(qmt_module.QMTAdapter, "_resolve_qmt_userdata_dir", lambda self: r"D:\gjzq\userdata", raising=True)

    adapter = qmt_module.QMTAdapter()
    df = adapter.query_account_positions("123456")

    assert df is not None
    assert len(df) == 1
    row = df.iloc[0]
    assert row["code"] == "600000"
    assert row["name"] == "浦发银行"
    assert row["market"] == "CN"
    assert row["currency"] == "CNY"
    assert row["quantity"] == 100
    assert row["cost_price"] == 10.25
    assert "QMT 持仓导入" in row["notes"]
    assert fake_trader.started is True
    assert fake_trader.stopped is True


def test_import_positions_marks_source_as_import(monkeypatch):
    monkeypatch.setattr("app.services.portfolio_service.get_mongo_db", lambda: object(), raising=True)
    service = PortfolioService()

    calls = []

    async def fake_add_position(user_id, data, source=PositionSource.MANUAL, validate_input=True):
        calls.append((user_id, data.code, source, validate_input))
        return None

    monkeypatch.setattr(service, "add_position", fake_add_position, raising=True)

    positions = [
        PositionCreate(
            code="600000",
            name="浦发银行",
            market="CN",
            quantity=100,
            cost_price=10.25,
        )
    ]

    result = asyncio.run(service.import_positions("user-1", positions))

    assert result["success_count"] == 1
    assert calls == [("user-1", "600000", PositionSource.IMPORT, True)]


def test_import_positions_replace_existing_clears_current_positions(monkeypatch):
    monkeypatch.setattr("app.services.portfolio_service.get_mongo_db", lambda: object(), raising=True)
    service = PortfolioService()

    state = {}

    async def fake_clear(user_id):
        state["cleared_user"] = user_id
        return {"deleted_positions": 2, "deleted_changes": 3, "restored_cash": {"CNY": 10000.0, "HKD": 0.0, "USD": 0.0}}

    async def fake_add_position(user_id, data, source=PositionSource.MANUAL, validate_input=True):
        state.setdefault("added", []).append((user_id, data.code, source, validate_input))
        return None

    monkeypatch.setattr(service, "_clear_existing_real_positions_for_sync", fake_clear, raising=True)
    monkeypatch.setattr(service, "add_position", fake_add_position, raising=True)

    positions = [
        PositionCreate(
            code="600000",
            name="浦发银行",
            market="CN",
            quantity=100,
            cost_price=10.25,
        )
    ]

    result = asyncio.run(service.import_positions("user-1", positions, validate_input=False, replace_existing=True))

    assert state["cleared_user"] == "user-1"
    assert state["added"] == [("user-1", "600000", PositionSource.IMPORT, False)]
    assert result["deleted_positions"] == 2
    assert result["deleted_changes"] == 3
    assert result["restored_cash"]["CNY"] == 10000.0
    assert result["replace_existing"] is True


def test_preview_qmt_position_import_builds_summary(monkeypatch):
    class _FakeCollection:
        def __init__(self, count):
            self.count = count

        async def count_documents(self, _query):
            return self.count

    class _FakeDB:
        def __getitem__(self, name):
            mapping = {
                "real_positions": _FakeCollection(2),
                "position_changes": _FakeCollection(3),
            }
            return mapping[name]

    monkeypatch.setattr("app.services.portfolio_service.get_mongo_db", lambda: _FakeDB(), raising=True)
    service = PortfolioService()

    class _FakeQMTAdapter:
        def query_account_snapshot(self, account_id, account_type="STOCK"):
            assert account_id == "123456"
            assert account_type == "STOCK"
            return {
                "positions_df": pd.DataFrame([
                    {
                        "code": "600000",
                        "name": "浦发银行",
                        "market": "CN",
                        "currency": "CNY",
                        "quantity": 100,
                        "cost_price": 10.25,
                        "buy_date": None,
                        "notes": "QMT 持仓导入 | 账户 123456",
                    }
                ]),
                "asset": {"cash": 1000.0, "market_value": 1025.0, "total_asset": 2025.0},
            }

    async def fake_get_account_summary(_user_id):
        return SimpleNamespace(cash={"CNY": 5000.0}, total_assets={"CNY": 8000.0})

    monkeypatch.setattr("app.services.data_sources.qmt_adapter.QMTAdapter", _FakeQMTAdapter, raising=True)
    monkeypatch.setattr(service, "get_account_summary", fake_get_account_summary, raising=True)

    result = asyncio.run(service.preview_qmt_position_import("user-1", "123456"))

    assert result["will_replace_position_count"] == 2
    assert result["will_clear_change_count"] == 3
    assert result["local_cash"] == 5000.0
    assert result["qmt_position_count"] == 1
    assert result["qmt_importable_count"] == 1
    assert result["qmt_cash"] == 1000.0
    assert result["qmt_total_asset"] == 2025.0
    assert result["will_sync_cash"] is True


def test_import_positions_from_qmt_converts_rows(monkeypatch):
    monkeypatch.setattr("app.services.portfolio_service.get_mongo_db", lambda: object(), raising=True)
    service = PortfolioService()

    fake_df = pd.DataFrame([
        {
            "code": "600000",
            "name": "浦发银行",
            "market": "CN",
            "currency": "CNY",
            "quantity": 100,
            "cost_price": 10.25,
            "buy_date": None,
            "notes": "QMT 持仓导入 | 账户 123456",
        }
    ])

    class _FakeQMTAdapter:
        def query_account_snapshot(self, account_id, account_type="STOCK"):
            assert account_id == "123456"
            assert account_type == "STOCK"
            return {
                "positions_df": fake_df,
                "asset": {"cash": 1000.0, "market_value": 1025.0, "total_asset": 2025.0},
            }

    monkeypatch.setattr("app.services.data_sources.qmt_adapter.QMTAdapter", _FakeQMTAdapter, raising=True)

    captured = {}

    async def fake_import_positions(user_id, positions, validate_input=True, replace_existing=False):
        captured["user_id"] = user_id
        captured["positions"] = positions
        captured["validate_input"] = validate_input
        captured["replace_existing"] = replace_existing
        return {"success_count": len(positions), "failed_count": 0, "errors": []}

    async def fake_sync_cash(user_id, asset_summary):
        captured["cash_user_id"] = user_id
        captured["asset_summary"] = asset_summary
        return {"cash_synced": True, "synced_currency": "CNY", "synced_cash": 1000.0}

    monkeypatch.setattr(service, "import_positions", fake_import_positions, raising=True)
    monkeypatch.setattr(service, "_sync_qmt_cash_to_account", fake_sync_cash, raising=True)

    result = asyncio.run(service.import_positions_from_qmt("user-1", "123456"))

    assert result["success_count"] == 1
    assert result["account_id"] == "123456"
    assert result["queried_count"] == 1
    assert result["imported_count"] == 1
    assert captured["user_id"] == "user-1"
    assert len(captured["positions"]) == 1
    assert captured["positions"][0].code == "600000"
    assert captured["validate_input"] is False
    assert captured["replace_existing"] is True
    assert captured["cash_user_id"] == "user-1"
    assert captured["asset_summary"]["cash"] == 1000.0
    assert result["cash_synced"] is True
    assert result["synced_cash"] == 1000.0


def test_import_positions_from_qmt_allows_empty_positions_when_cash_available(monkeypatch):
    monkeypatch.setattr("app.services.portfolio_service.get_mongo_db", lambda: object(), raising=True)
    service = PortfolioService()

    class _FakeQMTAdapter:
        def query_account_snapshot(self, account_id, account_type="STOCK"):
            assert account_id == "123456"
            assert account_type == "STOCK"
            return {
                "positions_df": pd.DataFrame([], columns=["code", "quantity", "cost_price"]),
                "asset": {"cash": 3000.0, "market_value": 0.0, "total_asset": 3000.0},
            }

    captured = {}

    async def fake_import_positions(user_id, positions, validate_input=True, replace_existing=False):
        captured["user_id"] = user_id
        captured["positions"] = positions
        captured["validate_input"] = validate_input
        captured["replace_existing"] = replace_existing
        return {"success_count": 0, "failed_count": 0, "errors": []}

    async def fake_sync_cash(user_id, asset_summary):
        captured["cash_user_id"] = user_id
        captured["asset_summary"] = asset_summary
        return {"cash_synced": True, "synced_currency": "CNY", "synced_cash": 3000.0}

    monkeypatch.setattr("app.services.data_sources.qmt_adapter.QMTAdapter", _FakeQMTAdapter, raising=True)
    monkeypatch.setattr(service, "import_positions", fake_import_positions, raising=True)
    monkeypatch.setattr(service, "_sync_qmt_cash_to_account", fake_sync_cash, raising=True)

    result = asyncio.run(service.import_positions_from_qmt("user-1", "123456"))

    assert captured["user_id"] == "user-1"
    assert captured["positions"] == []
    assert captured["validate_input"] is False
    assert captured["replace_existing"] is True
    assert captured["cash_user_id"] == "user-1"
    assert captured["asset_summary"]["cash"] == 3000.0
    assert result["imported_count"] == 0
    assert result["cash_synced"] is True
    assert result["synced_cash"] == 3000.0