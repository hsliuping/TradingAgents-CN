import asyncio

import app.services.financial_data_service as financial_data_service_module
from app.services.financial_data_service import FinancialDataService


def test_extract_latest_period_and_indicators_from_akshare_matrix_records():
    service = FinancialDataService()

    financial_data = {
        "main_indicators": [
            {"指标": "营业总收入", "20260331": 129131041000.0, "20251231": 423701834000.0},
            {"指标": "归母净利润", "20260331": 20737710000.0, "20251231": 72201280000.0},
            {"指标": "股东权益合计(净资产)", "20260331": 394232291000.0, "20251231": 371026300000.0},
            {"指标": "净资产收益率_平均", "20260331": 5.973097, "20251231": 24.72487},
            {"指标": "资产负债率", "20260331": 62.32234, "20251231": 61.93928},
        ],
        "balance_sheet": [],
        "income_statement": [],
    }

    period = service._extract_latest_period(financial_data)
    indicators = service._extract_akshare_indicators(financial_data)

    assert period == "20260331"
    assert indicators["revenue"] == 129131041000.0
    assert indicators["net_income"] == 20737710000.0
    assert indicators["total_equity"] == 394232291000.0
    assert indicators["roe"] == 5.973097
    assert indicators["debt_to_assets"] == 62.32234


def test_save_financial_data_also_syncs_financial_periods(monkeypatch):
    class _BulkWriteResult:
        upserted_count = 1
        modified_count = 0

    class _FakeCollection:
        def __init__(self):
            self.operations = []

        async def create_index(self, *_args, **_kwargs):
            return None

        async def bulk_write(self, operations, ordered=True):
            self.operations.extend(operations)
            return _BulkWriteResult()

    class _FakeDB:
        def __init__(self):
            self.collections = {
                "stock_financial_data": _FakeCollection(),
                "stock_financial_periods": _FakeCollection(),
            }

        def __getitem__(self, name):
            return self.collections[name]

    service = FinancialDataService()
    service.db = _FakeDB()

    standardized_record = {
        "code": "600519",
        "symbol": "600519",
        "report_period": "20260331",
        "report_type": "quarterly",
        "data_source": "tushare",
        "ann_date": "20260425",
        "updated_at": "2026-05-04T02:47:10Z",
        "roe": 10.5687,
        "revenue_ttm": 172146396849.52,
        "net_profit_ttm": 82715105749.37,
    }

    monkeypatch.setattr(
        service,
        "_standardize_financial_data",
        lambda *_args, **_kwargs: standardized_record,
        raising=True,
    )

    async def _run():
        saved = await service.save_financial_data(
            symbol="600519",
            financial_data={},
            data_source="tushare",
            market="CN",
            report_period="20260331",
            report_type="quarterly",
        )
        assert saved == 1

    asyncio.run(_run())

    raw_ops = service.db["stock_financial_data"].operations
    period_ops = service.db["stock_financial_periods"].operations
    assert len(raw_ops) == 1
    assert len(period_ops) == 1
    assert period_ops[0]._filter["symbol"] == "600519"
    assert period_ops[0]._filter["source"] == "tushare"
    assert period_ops[0]._filter["report_period"] == "20260331"


def test_initialize_also_ensures_financial_period_indexes(monkeypatch):
    class _FakeCollection:
        def __init__(self):
            self.index_names = []

        async def create_index(self, _keys, **kwargs):
            self.index_names.append(kwargs.get("name"))
            return kwargs.get("name")

    class _FakeDB:
        def __init__(self):
            self.collections = {
                "stock_financial_data": _FakeCollection(),
                "stock_financial_periods": _FakeCollection(),
            }

        def __getitem__(self, name):
            return self.collections[name]

    fake_db = _FakeDB()
    monkeypatch.setattr(financial_data_service_module, "get_mongo_db", lambda: fake_db)

    service = FinancialDataService()
    asyncio.run(service.initialize())

    snapshot_indexes = fake_db["stock_financial_data"].index_names
    period_indexes = fake_db["stock_financial_periods"].index_names

    assert "symbol_period_source_unique" in snapshot_indexes
    assert "symbol_1_source_1_report_period_-1_ann_date_-1" in period_indexes
    assert "code_1_source_1_report_period_-1" in period_indexes
    assert "symbol_1_report_period_-1" in period_indexes