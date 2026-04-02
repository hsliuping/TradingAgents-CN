from __future__ import annotations

from typing import Any, Dict, Iterable, List, Optional, Sequence

from core.skill_runtime import catalog, project_access


def _matches(document: Dict[str, Any], filters: Dict[str, Any]) -> bool:
    if not filters:
        return True

    for key, value in filters.items():
        if key == "$or":
            return any(_matches(document, item) for item in value)
        if document.get(key) != value:
            return False
    return True


class FakeCursor:
    def __init__(self, docs: Iterable[Dict[str, Any]]):
        self._docs = [dict(item) for item in docs]

    def sort(self, spec: Any, direction: Optional[int] = None) -> "FakeCursor":
        if isinstance(spec, str):
            sort_fields: Sequence[tuple[str, int]] = [(spec, int(direction or 1))]
        else:
            sort_fields = [(str(field_name), int(sort_direction)) for field_name, sort_direction in spec]

        docs = list(self._docs)
        for field_name, sort_direction in reversed(sort_fields):
            docs.sort(key=lambda item: str(item.get(field_name) or ""), reverse=sort_direction < 0)
        self._docs = docs
        return self

    def limit(self, count: int) -> "FakeCursor":
        self._docs = self._docs[:count]
        return self

    def __iter__(self):
        return iter(self._docs)


class FakeCollection:
    def __init__(self, docs: Iterable[Dict[str, Any]]):
        self._docs = [dict(item) for item in docs]

    def find(self, filters: Optional[Dict[str, Any]] = None, projection: Optional[Dict[str, int]] = None) -> FakeCursor:
        matched = [dict(item) for item in self._docs if _matches(item, filters or {})]
        if projection and projection.get("_id") == 0:
            for item in matched:
                item.pop("_id", None)
        return FakeCursor(matched)

    def count_documents(self, filters: Optional[Dict[str, Any]] = None) -> int:
        return sum(1 for item in self._docs if _matches(item, filters or {}))

    def estimated_document_count(self) -> int:
        return len(self._docs)


class FakeDb:
    def __init__(self, mapping: Dict[str, List[Dict[str, Any]]]):
        self._mapping = {name: FakeCollection(items) for name, items in mapping.items()}

    def __getitem__(self, name: str) -> FakeCollection:
        return self._mapping[name]


def test_catalog_exposes_a_share_financial_periods_collection() -> None:
    assert "stock_financial_periods" in catalog.SUPPORTED_COLLECTIONS

    metadata = next(
        item for item in catalog.list_supported_stock_collections()
        if item["collection"] == "stock_financial_periods"
    )
    assert metadata["preferred_access"] == ["get_stock_financial_periods"]
    assert metadata["query_keys"] == ["symbol", "report_period", "ann_date", "source"]


def test_project_access_supports_financial_period_schema_inspection(monkeypatch) -> None:
    fake_db = FakeDb({
        "stock_financial_periods": [
            {
                "symbol": "600519",
                "name": "贵州茅台",
                "report_period": "20241231",
                "ann_date": "20250328",
                "source": "tushare",
                "roe": 0.32,
            },
            {
                "symbol": "600519",
                "name": "贵州茅台",
                "report_period": "20240930",
                "ann_date": "20241025",
                "source": "tushare",
                "roe": 0.29,
            },
        ],
    })
    monkeypatch.setattr(project_access, "_get_db", lambda: fake_db, raising=True)

    rows = project_access.query_stock_collection(
        "stock_financial_periods",
        filters={"symbol": "600519"},
        sort=[("report_period", -1)],
        limit=10,
    )
    assert [item["report_period"] for item in rows] == ["20241231", "20240930"]

    schema = project_access.inspect_stock_collection_schema("stock_financial_periods")
    assert schema["collection"] == "stock_financial_periods"
    assert schema["preferred_access"] == ["get_stock_financial_periods"]
    assert "report_period" in schema["top_level_fields"]


def test_inspect_symbol_documents_orders_a_share_financial_periods_by_latest_period(monkeypatch) -> None:
    fake_db = FakeDb({
        "stock_financial_periods": [
            {
                "symbol": "600519",
                "name": "贵州茅台",
                "report_period": "20240930",
                "ann_date": "20241025",
                "source": "tushare",
            },
            {
                "symbol": "600519",
                "name": "贵州茅台",
                "report_period": "20241231",
                "ann_date": "20250328",
                "source": "tushare",
            },
            {
                "symbol": "600519",
                "name": "贵州茅台",
                "report_period": "20241231",
                "ann_date": "20250320",
                "source": "tushare",
            },
        ],
    })
    monkeypatch.setattr(project_access, "_get_db", lambda: fake_db, raising=True)

    result = project_access.inspect_symbol_documents("stock_financial_periods", "600519", limit=3)

    scalar_preview_rows = [item.get("scalar_preview", {}) for item in result["documents"]]
    assert [item.get("report_period") for item in scalar_preview_rows] == ["20241231", "20241231", "20240930"]
    assert [item.get("ann_date") for item in scalar_preview_rows] == ["20250328", "20250320", "20241025"]