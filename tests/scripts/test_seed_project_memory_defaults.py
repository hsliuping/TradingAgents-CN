import asyncio
import importlib.util
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[2]
SCRIPT_PATH = ROOT_DIR / "scripts" / "seed_project_memory_defaults.py"

spec = importlib.util.spec_from_file_location("seed_project_memory_defaults", SCRIPT_PATH)
module = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(module)


class _FakeUpdateResult:
    def __init__(self, matched_count: int = 1):
        self.matched_count = matched_count


class _FakeCursor:
    def __init__(self, docs):
        self._docs = [dict(doc) for doc in docs]

    def sort(self, sort_spec):
        for field, direction in reversed(sort_spec):
            reverse = direction < 0
            self._docs.sort(key=lambda doc: doc.get(field), reverse=reverse)
        return self

    def limit(self, size):
        self._docs = self._docs[:size]
        return self

    async def to_list(self, length):
        return [dict(doc) for doc in self._docs[:length]]


class _FakeCollection:
    def __init__(self):
        self.docs = []

    async def update_one(self, query, update, upsert=False):
        for doc in self.docs:
            if all(doc.get(key) == value for key, value in query.items()):
                doc.update(update.get("$set", {}))
                return _FakeUpdateResult()
        if upsert:
            new_doc = dict(query)
            new_doc.update(update.get("$setOnInsert", {}))
            new_doc.update(update.get("$set", {}))
            self.docs.append(new_doc)
        return _FakeUpdateResult()

    async def find_one(self, query):
        for doc in self.docs:
            if all(doc.get(key) == value for key, value in query.items()):
                return dict(doc)
        return None

    def find(self, query):
        matched = []
        for doc in self.docs:
            ok = True
            for key, value in query.items():
                if isinstance(value, dict) and "$in" in value:
                    if doc.get(key) not in value["$in"]:
                        ok = False
                        break
                elif doc.get(key) != value:
                    ok = False
                    break
            if ok:
                matched.append(doc)
        return _FakeCursor(matched)


class _FakeDB:
    def __init__(self):
        self._collection = _FakeCollection()

    def __getitem__(self, name):
        assert name == "project_memory_items"
        return self._collection


def test_seed_project_memory_defaults_script_passes(monkeypatch):
    monkeypatch.setattr(module, "get_mongo_db", lambda: _FakeDB())

    summary = asyncio.run(module.seed_defaults())

    assert summary["ok"] is True
    assert summary["count"] >= 6
    assert "global-no-trading-advice" in summary["memory_keys"]
    assert "stock-analysis-template" in summary["memory_keys"]