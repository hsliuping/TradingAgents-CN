from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone

import pytest

from app.services.alphaguard.analysis_model_resolver import (
    AnalysisModelConfigurationError,
    AnalysisModelResolver,
    model_profile_selector,
)
from app.services.alphaguard.model_profile_registry import ModelProfileRegistry
from tradingagents.graph.trading_graph import _custom_openai_runtime_settings


class _Collection:
    def __init__(self, rows):
        self.rows = rows

    def find_one(self, query, sort=None):
        matches = [
            row
            for row in self.rows
            if all(row.get(key) == value for key, value in query.items())
        ]
        if sort:
            for key, direction in reversed(sort):
                matches.sort(
                    key=lambda row: row.get(key),
                    reverse=direction < 0,
                )
        return deepcopy(matches[0]) if matches else None


class _Database:
    def __init__(self, collections):
        self.collections = collections

    def __getitem__(self, name):
        return _Collection(self.collections.setdefault(name, []))


class _Client:
    def __init__(self, db):
        self.db = db
        self.closed = False

    def __getitem__(self, _name):
        return self.db

    def close(self):
        self.closed = True


class _Credentials:
    def resolve_for_profile(self, profile):
        return f"unit-secret-{profile.role}"


def _runtime():
    registry = ModelProfileRegistry()
    research = registry.definition("alphaguard_research_openai", "v2")
    top = registry.definition("alphaguard_top_openai", "v2")
    now = datetime.now(timezone.utc)
    db = _Database(
        {
            "ag_model_profile_assignments": [
                {
                    "role": research.role,
                    "status": "ACTIVE",
                    "profile_id": research.profile_id,
                    "profile_version": research.profile_version,
                    "assigned_at": now,
                },
                {
                    "role": top.role,
                    "status": "ACTIVE",
                    "profile_id": top.profile_id,
                    "profile_version": top.profile_version,
                    "assigned_at": now,
                },
            ],
            "ag_model_profiles": [
                research.model_dump(mode="python"),
                top.model_dump(mode="python"),
            ],
            "ag_model_capability_checks": [
                {
                    "profile_id": research.profile_id,
                    "profile_version": research.profile_version,
                    "status": "READY",
                    "checked_at": now,
                },
                {
                    "profile_id": top.profile_id,
                    "profile_version": top.profile_version,
                    "status": "READY",
                    "checked_at": now,
                },
            ],
        }
    )
    client = _Client(db)
    resolver = AnalysisModelResolver(
        client_factory=lambda _uri: client,
        credential_service=_Credentials(),
        mongo_uri="mongodb://unit.invalid",
        mongo_db="unit",
    )
    return resolver, client, db, research, top


def test_resolver_uses_exact_active_profiles_and_keeps_secrets_out_of_repr():
    resolver, client, _db, research, top = _runtime()

    pair = resolver.resolve_pair(
        quick_selector=model_profile_selector(research),
        deep_selector=model_profile_selector(top),
    )

    assert pair.quick.profile == research
    assert pair.deep.profile == top
    assert pair.quick.provider == "openai"
    assert pair.quick.model_config["max_tokens"] == research.max_output_tokens
    assert "unit-secret" not in repr(pair)
    assert client.closed is True


def test_resolver_maps_legacy_model_names_to_active_secure_profiles():
    resolver, _client, _db, research, top = _runtime()

    pair = resolver.resolve_pair(
        quick_selector="qwen-turbo",
        deep_selector="qwen-max",
    )

    assert pair.quick.selector == model_profile_selector(research)
    assert pair.deep.selector == model_profile_selector(top)


def test_resolver_maps_compatible_profile_to_custom_openai_runtime():
    resolver, _client, db, research, top = _runtime()
    compatible = research.model_copy(
        update={
            "provider": "openai_compatible",
            "provider_type": "OPENAI_COMPATIBLE",
            "model_name": "registered-compatible-model",
            "base_url": "https://registered.example/v1",
            "endpoint_profile_id": "endpoint-1",
            "endpoint_profile_version": "v1",
            "endpoint_model_id": "model-1",
            "endpoint_model_version": "v1",
            "credential_id": "credential-1",
            "price_version_id": "price-1",
            "normalized_origin": "https://registered.example",
            "auth_scheme": "BEARER",
        }
    )
    db.collections["ag_model_profiles"][0] = compatible.model_dump(mode="python")

    pair = resolver.resolve_pair(
        quick_selector=model_profile_selector(compatible),
        deep_selector=model_profile_selector(top),
    )

    assert pair.quick.provider == "custom_openai"
    assert pair.quick.backend_url == "https://registered.example/v1"


def test_resolver_rejects_stale_secure_selector():
    resolver, client, _db, _research, top = _runtime()

    with pytest.raises(AnalysisModelConfigurationError, match="配置已更新"):
        resolver.resolve_pair(
            quick_selector="alphaguard-profile:old-profile@v1",
            deep_selector=model_profile_selector(top),
        )

    assert client.closed is True


def test_resolver_requires_ready_capability_check():
    resolver, _client, db, research, top = _runtime()
    db.collections["ag_model_capability_checks"] = [
        row
        for row in db.collections["ag_model_capability_checks"]
        if row["profile_id"] != research.profile_id
    ]

    with pytest.raises(AnalysisModelConfigurationError, match="能力检测"):
        resolver.resolve_pair(
            quick_selector=model_profile_selector(research),
            deep_selector=model_profile_selector(top),
        )


def test_custom_openai_uses_resolved_runtime_credentials(monkeypatch):
    monkeypatch.setenv("CUSTOM_OPENAI_API_KEY", "stale-environment-secret")

    api_key, backend_url = _custom_openai_runtime_settings(
        {
            "quick_api_key": "resolved-profile-secret",
            "backend_url": "https://registered.example/v1",
        }
    )

    assert api_key == "resolved-profile-secret"
    assert backend_url == "https://registered.example/v1"
