import sys
import types

from core.api.workflow_api import WorkflowAPI


class _DummyCollection:
    def __init__(self, docs):
        self.docs = docs
        self.queries = []

    def find_one(self, query, projection=None, sort=None):
        self.queries.append(query)

        code_conditions = query.get("$or", [])
        valid_codes = {
            item.get("code") or item.get("symbol")
            for item in code_conditions
            if isinstance(item, dict)
        }

        lte_value = None
        trade_date_filter = query.get("trade_date")
        if isinstance(trade_date_filter, dict):
            lte_value = trade_date_filter.get("$lte")

        matches = []
        for doc in self.docs:
            doc_code = doc.get("code") or doc.get("symbol")
            if valid_codes and doc_code not in valid_codes:
                continue
            if lte_value is not None and str(doc.get("trade_date", "")) > str(lte_value):
                continue
            matches.append(doc)

        if not matches:
            return None

        return sorted(matches, key=lambda item: str(item.get("trade_date", "")), reverse=True)[0]


class _DummyDb:
    def __init__(self):
        self.stock_basic_info = _DummyCollection(
            [{"code": "000001", "name": "平安银行", "industry": "银行"}]
        )
        self.market_quotes = _DummyCollection(
            [
                {"code": "000001", "close": 11.08, "trade_date": "2026-04-21"},
                {"code": "000001", "close": 10.95, "trade_date": "2026-04-20"},
            ]
        )


def test_prepare_system_variables_uses_effective_data_date_for_price_context(monkeypatch):
    dummy_db = _DummyDb()

    stock_utils_module = types.SimpleNamespace(
        StockUtils=types.SimpleNamespace(get_market_info=lambda stock_code: {"is_china": True})
    )
    database_module = types.SimpleNamespace(get_mongo_db_sync=lambda: dummy_db)

    monkeypatch.setitem(sys.modules, "tradingagents.utils.stock_utils", stock_utils_module)
    monkeypatch.setitem(sys.modules, "app.core.database", database_module)

    import core.tools.trade_date_policy as trade_date_policy

    monkeypatch.setattr(trade_date_policy, "apply_stable_data_cutoff", lambda date_str, cutoff_hour=19: "2026-04-20")
    monkeypatch.setattr(
        trade_date_policy,
        "build_stable_data_cutoff_note",
        lambda requested_date, effective_date, subject="": f"note:{requested_date}->{effective_date}",
    )

    api = WorkflowAPI.__new__(WorkflowAPI)
    system_vars = api._prepare_system_variables("000001", "2026-04-21")

    assert system_vars["effective_data_date"] == "2026-04-20"
    assert system_vars["stable_data_note"] == "note:2026-04-21->2026-04-20"
    assert system_vars["current_price"] == "10.95"
    assert system_vars["current_price_context_date"] == "2026-04-20"
    assert any(query.get("trade_date", {}).get("$lte") == "2026-04-20" for query in dummy_db.market_quotes.queries)