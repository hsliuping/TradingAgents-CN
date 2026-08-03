from __future__ import annotations

import json

import pytest
from bson import BSON

from app.core.config import settings
from scripts.alphaguard_backup import (
    BACKUP_COLLECTIONS,
    BACKUP_FORMAT,
    list_backups,
    load_manifest,
    _secret_paths,
    run as backup_run,
    verify_backup,
)
from scripts.alphaguard_restore import _restore_bson_stream, run as restore_run


class SyncCollection:
    def __init__(self):
        self.documents = []
        self.insert_many_calls = 0

    def find(self, _query):
        return list(self.documents)

    def count_documents(self, _query):
        return len(self.documents)

    def insert_many(self, documents, ordered=True):
        assert ordered is True
        self.insert_many_calls += 1
        self.documents.extend(documents)

    def delete_many(self, _query):
        self.documents.clear()


class SyncDB:
    def __init__(self):
        self.collections = {}

    def __getitem__(self, name):
        self.collections.setdefault(name, SyncCollection())
        return self.collections[name]


class SyncAdmin:
    @staticmethod
    def command(name):
        assert name == "ping"
        return {"ok": 1}


class SyncClient:
    def __init__(self):
        self.databases = {}
        self.admin = SyncAdmin()
        self.closed = False

    def __getitem__(self, name):
        self.databases.setdefault(name, SyncDB())
        return self.databases[name]

    def close(self):
        self.closed = True

    def drop_database(self, name):
        self.databases.pop(name, None)


def _factory(client):
    def create(*_args, **_kwargs):
        client.closed = False
        return client

    return create


def test_secret_scan_allows_business_rule_ids_but_rejects_secret_fields():
    assert _secret_paths({"rule_id": "key-risk-threshold-validation"}) == []
    assert _secret_paths({"credential_ref": "keychain-alias:model-primary"}) == []
    assert _secret_paths({"api_key": "unit-test-secret-sentinel"}) == ["$.api_key"]


def test_restore_streams_large_collections_in_bounded_batches(tmp_path):
    path = tmp_path / "batch.bson"
    with path.open("wb") as handle:
        for index in range(205):
            handle.write(BSON.encode({"index": index, "payload": "x" * 64}))
    collection = SyncCollection()
    restored = _restore_bson_stream(
        collection,
        path,
        max_documents=100,
        max_bytes=1024 * 1024,
    )
    assert restored == 205
    assert collection.insert_many_calls == 3


def test_v2_backup_manifest_list_verify_and_isolated_restore(tmp_path):
    client = SyncClient()
    source = client[settings.MONGO_DB]
    source[BACKUP_COLLECTIONS[0]].documents.append(
        {
            "document_id": "safe-document",
            "credential_ref": "keychain-alias:model-primary",
        }
    )
    target = tmp_path / "backups" / "release-backup"
    assert backup_run(
        execute=True,
        output=target,
        client_factory=_factory(client),
    ) == 0
    manifest = load_manifest(target)
    assert manifest["format"] == BACKUP_FORMAT
    assert manifest["backup_id"]
    assert manifest["schema_version"]
    assert manifest["source_commit"]
    assert manifest["source_tag"]
    assert manifest["manifest_hash"]
    assert manifest["verification"]["status"] == "PASS"
    assert manifest["verification"]["verified_at"]
    assert manifest["collection_counts"][BACKUP_COLLECTIONS[0]] == 1
    verification = verify_backup(target)
    assert verification["status"] == "PASS"
    assert verification["secret_scan"] == "PASS"
    listed = list_backups(target.parent)
    assert listed[0]["backup_id"] == manifest["backup_id"]
    assert listed[0]["status"] == "READY"

    isolated_database = f"{settings.MONGO_DB}_pr014_isolated"
    assert restore_run(
        source=target,
        target_database=isolated_database,
        execute=True,
        overwrite_current=False,
        confirmation=None,
        drill=True,
        client_factory=_factory(client),
    ) == 0
    assert (
        client[isolated_database][BACKUP_COLLECTIONS[0]].count_documents({}) == 1
    )

    with pytest.raises(RuntimeError, match="requires --overwrite-current"):
        restore_run(
            source=target,
            target_database=settings.MONGO_DB,
            execute=False,
            overwrite_current=False,
            confirmation=None,
            client_factory=_factory(client),
        )

    manifest_path = target / "manifest.json"
    tampered = json.loads(manifest_path.read_text(encoding="utf-8"))
    tampered["source_commit"] = "tampered"
    manifest_path.write_text(json.dumps(tampered), encoding="utf-8")
    with pytest.raises(RuntimeError, match="manifest hash mismatch"):
        verify_backup(target)


def test_backup_refuses_secrets(tmp_path):
    client = SyncClient()
    client[settings.MONGO_DB][BACKUP_COLLECTIONS[0]].documents.append(
        {"api_key": "unit-test-secret-sentinel"}
    )
    target = tmp_path / "secret-backup"
    with pytest.raises(RuntimeError, match="secret-like content refused"):
        backup_run(
            execute=True,
            output=target,
            client_factory=_factory(client),
        )
    assert not target.exists()
