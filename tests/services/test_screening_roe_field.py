import asyncio


def test_database_screening_builds_roe_query():
    from app.services.database_screening_service import DatabaseScreeningService

    svc = DatabaseScreeningService()

    async def _run():
        query = await svc._build_query([
            {"field": "roe", "operator": "between", "value": [10, 20]},
        ])
        # Should map to direct 'roe' field with $gte/$lte
        assert "roe" in query
        assert query["roe"]["$gte"] == 10
        assert query["roe"]["$lte"] == 20

    asyncio.run(_run())


def test_database_screening_formats_roe_in_result(monkeypatch):
    from app.services.database_screening_service import DatabaseScreeningService
    import app.services.database_screening_service as mod

    # Fake collection returning docs that contain 'roe'
    class _FakeCursor:
        def __init__(self, docs):
            self._docs = docs
        def sort(self, *_args, **_kwargs):
            return self
        def skip(self, *_args, **_kwargs):
            return self
        def limit(self, *_args, **_kwargs):
            return self
        async def __aiter__(self):
            for d in self._docs:
                yield d

    class _FakeColl:
        def __init__(self, docs):
            self._docs = docs
        async def count_documents(self, _query):
            return len(self._docs)
        def find(self, _query):
            return _FakeCursor(self._docs)

    class _FakeDB:
        def __init__(self, docs):
            self._coll = _FakeColl(docs)
        def __getitem__(self, name: str):
            return self._coll

    docs = [
        {"code": "000001", "name": "平安银行", "roe": 12.3},
        {"code": "600000", "name": "浦发银行", "roe": 8.9},
    ]

    def _fake_get_db():
        return _FakeDB(docs)

    monkeypatch.setattr(mod, "get_mongo_db", _fake_get_db, raising=True)

    async def _run():
        svc = DatabaseScreeningService()
        items, total = await svc.screen_stocks(
            conditions=[{"field": "roe", "operator": ">=", "value": 5}],
            limit=50,
            offset=0,
            order_by=None,
        )
        assert total == 2
        # Ensure roe is present in formatted result
        by_code = {it["code"]: it for it in items}
        assert by_code["000001"]["roe"] == 12.3
        assert by_code["600000"]["roe"] == 8.9

    asyncio.run(_run())


def test_database_screening_refreshes_stale_financial_snapshot(monkeypatch):
    from app.services.database_screening_service import DatabaseScreeningService
    import app.services.database_screening_service as mod
    import app.core.data_source_priority as priority_mod

    class _AsyncCursor:
        def __init__(self, docs):
            self._docs = docs

        async def __aiter__(self):
            for doc in self._docs:
                yield doc

    class _FakeCollection:
        def __init__(self, find_docs=None, aggregate_docs=None):
            self._find_docs = find_docs or []
            self._aggregate_docs = aggregate_docs or []

        def find(self, *_args, **_kwargs):
            return _AsyncCursor(self._find_docs)

        def aggregate(self, *_args, **_kwargs):
            return _AsyncCursor(self._aggregate_docs)

    class _FakeDB:
        def __init__(self, aggregate_docs):
            self._collections = {
                "stock_financial_periods": _FakeCollection(aggregate_docs=aggregate_docs),
                "stock_basic_info": _FakeCollection(find_docs=[]),
            }

        def __getitem__(self, name: str):
            return self._collections[name]

    latest_snapshot = {
        "report_period": "20260331",
        "revenue_ttm": 172146396849.52,
        "net_profit_ttm": 82715105749.37,
        "n_cashflow_act": 26909891269.13,
        "roe": 10.5687,
        "roa": 11.9998,
        "gross_margin": 89.7592,
        "netprofit_margin": 52.2245,
        "debt_to_assets": 12.1227,
        "assets_to_eqt": 1.138,
        "current_ratio": 7.0607,
        "quick_ratio": 5.4825,
        "cash_ratio": 1.3629,
        "total_cur_assets": 120000000000.0,
        "total_cur_liab": 30000000000.0,
        "total_assets": 900000000000.0,
        "total_liab": 110000000000.0,
        "total_ncl": 50000000000.0,
        "total_equity": 400000000000.0,
        "money_cap": 240000000000.0,
        "accounts_receiv": 1500000000.0,
        "inventories": 2200000000.0,
        "oper_cost": 17000000000.0,
    }
    previous_snapshot = {
        "report_period": "20251231",
        "total_cur_assets": 110000000000.0,
        "total_cur_liab": 28000000000.0,
    }
    aggregate_docs = [{
        "_id": "600519",
        **latest_snapshot,
        "dividend_yield": 3.2,
        "period_snapshots": [latest_snapshot, previous_snapshot],
        "report_period": "20260331",
    }]

    def _fake_get_db():
        return _FakeDB(aggregate_docs)

    async def _fake_preferred_source(*_args, **_kwargs):
        return "tushare"

    monkeypatch.setattr(mod, "get_mongo_db", _fake_get_db, raising=True)
    monkeypatch.setattr(priority_mod, "get_preferred_data_source_async", _fake_preferred_source, raising=True)
    monkeypatch.setattr(mod, "_compute_yoy_growth", lambda *_args, **_kwargs: None, raising=True)
    monkeypatch.setattr(mod, "_compute_cagr", lambda *_args, **_kwargs: None, raising=True)
    monkeypatch.setattr(mod, "_estimate_roic", lambda *_args, **_kwargs: None, raising=True)
    monkeypatch.setattr(mod, "_estimate_interest_coverage", lambda *_args, **_kwargs: None, raising=True)
    monkeypatch.setattr(mod, "_estimate_piotroski_f_score", lambda *_args, **_kwargs: None, raising=True)
    monkeypatch.setattr(mod, "_estimate_beneish_m_score", lambda *_args, **_kwargs: None, raising=True)
    monkeypatch.setattr(mod, "_estimate_altman_z_score", lambda *_args, **_kwargs: None, raising=True)

    async def _run():
        svc = DatabaseScreeningService()
        results = [{
            "code": "600519",
            "report_period": "20250930",
            "roe": 26.3688,
            "roa": 29.4079,
            "gross_margin": 91.2934,
            "netprofit_margin": 52.0801,
            "debt_to_assets": 12.8088,
            "assets_to_eqt": 1.1469,
            "current_ratio": 6.6193,
            "quick_ratio": 5.1783,
            "cash_ratio": 1.472,
            "revenue_ttm": 178576728057.51,
            "net_profit_ttm": 90027341015.29,
            "n_cashflow_act": 38196802155.27,
            "dividend_yield": 3.76,
            "total_mv": 17000.0,
            "pb_mrq": 6.69,
            "pe_ttm": 20.8,
        }]

        await svc._enrich_with_financial_data(results, ["600519"])

        refreshed = results[0]
        assert refreshed["report_period"] == "20260331"
        assert refreshed["roe"] == latest_snapshot["roe"]
        assert refreshed["roa"] == latest_snapshot["roa"]
        assert refreshed["gross_margin"] == latest_snapshot["gross_margin"]
        assert refreshed["netprofit_margin"] == latest_snapshot["netprofit_margin"]
        assert refreshed["current_ratio"] == latest_snapshot["current_ratio"]
        assert refreshed["revenue_ttm"] == latest_snapshot["revenue_ttm"]
        assert refreshed["net_profit_ttm"] == latest_snapshot["net_profit_ttm"]
        assert refreshed["n_cashflow_act"] == latest_snapshot["n_cashflow_act"]
        assert round(refreshed["pb_mrq"], 4) == round((17000.0 * 100000000) / latest_snapshot["total_equity"], 4)
        assert round(refreshed["pe_ttm"], 4) == round((17000.0 * 100000000) / latest_snapshot["net_profit_ttm"], 4)

    asyncio.run(_run())

