from core.llm.embedding_manager import EmbeddingManager


class _BrokenAsyncCollection:
    def find_one(self, *args, **kwargs):
        raise AssertionError("should not use async/proxy collections directly")

    def find(self, *args, **kwargs):
        raise AssertionError("should not use async/proxy collections directly")


class _BrokenProxyDb:
    llm_providers = _BrokenAsyncCollection()
    system_configs = _BrokenAsyncCollection()


class _FakeCursor:
    def __init__(self, docs):
        self._docs = docs

    def sort(self, *args, **kwargs):
        return self

    def __iter__(self):
        return iter(self._docs)


class _FakeCollection:
    def __init__(self, docs=None, one=None):
        self._docs = docs or []
        self._one = one

    def find_one(self, *args, **kwargs):
        return self._one

    def find(self, *args, **kwargs):
        return _FakeCursor(self._docs)


class _FakeSyncDb:
    def __init__(self):
        self.system_configs = _FakeCollection(
            one={
                "is_active": True,
                "system_settings": {
                    "default_embedding_model": "dashscope:text-embedding-v3"
                },
            }
        )
        self.llm_providers = _FakeCollection(
            docs=[
                {
                    "name": "dashscope",
                    "display_name": "阿里云通义千问",
                    "api_key": "test-key",
                    "default_base_url": "https://dashscope.aliyuncs.com/api/v1",
                    "embedding_model": "text-embedding-v3",
                    "supported_features": ["embedding"],
                    "is_active": True,
                }
            ]
        )


def test_embedding_manager_uses_sync_db_for_proxy_objects(monkeypatch):
    fake_sync_db = _FakeSyncDb()

    monkeypatch.setattr(
        "app.core.database.get_mongo_db_sync",
        lambda: fake_sync_db,
    )

    manager = EmbeddingManager(db=_BrokenProxyDb())

    assert len(manager._providers) == 1
    assert manager._primary_provider is not None
    assert manager._primary_provider["name"] == "dashscope"
    assert manager._primary_provider["model"] == "text-embedding-v3"