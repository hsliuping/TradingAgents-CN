from __future__ import annotations

import os
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

from app.services.alphaguard.credential_host_broker import (
    build_credential_host_router,
)
from app.services.alphaguard.credential_host_runtime import (
    CREDENTIAL_HOST_TOKEN_HEADER,
    ensure_credential_host_runtime,
    read_credential_host_token,
)
from app.services.alphaguard.daily_run_service import DailyRunBlocked
from app.services.alphaguard.daily_stage_executor import (
    DAILY_MARKET_CONTEXT_TIMEOUT_SECONDS,
    ProductionDailyStageExecutor,
)
from app.services.alphaguard.model_profile_registry import ModelProfileRegistry
from app.services.alphaguard.model_secret_store import (
    KEYCHAIN_ALIAS_SERVICE,
    SecretNotFound,
    SecretStoreError,
    keychain_ref,
)
from scripts.manage_alphaguard_credential_host import (
    _launch_agent_payload,
)
from tests.unit.alphaguard._fakes import FakeDB


class MemorySecretStore:
    def __init__(self, values):
        self.values = dict(values)

    @property
    def available(self):
        return True

    def read(self, *, service, account):
        try:
            value = self.values[(service, account)]
        except KeyError as exc:
            raise SecretNotFound("credential is not configured") from exc
        if isinstance(value, Exception):
            raise value
        return value

    def write(self, *, service, account, secret):
        self.values[(service, account)] = secret

    def delete(self, *, service, account, missing_ok=False):
        self.values.pop((service, account), None)


async def _research_profile_db() -> tuple[FakeDB, object]:
    db = FakeDB()
    profile = ModelProfileRegistry().definition(
        "alphaguard_research_openai",
        "v2",
    )
    await db["ag_model_profiles"].insert_one(
        profile.model_dump(mode="python")
    )
    return db, profile


def _context(profile) -> dict:
    return {
        "role": profile.role,
        "profile_id": profile.profile_id,
        "profile_version": profile.profile_version,
        "config_hash": profile.config_hash,
        "credential_ref": profile.credential_ref,
        "endpoint_profile_id": profile.endpoint_profile_id,
        "endpoint_profile_version": profile.endpoint_profile_version,
        "endpoint_model_id": profile.endpoint_model_id,
        "endpoint_model_version": profile.endpoint_model_version,
    }


@pytest.mark.asyncio
async def test_credential_host_requires_token_and_exact_active_profile(tmp_path):
    db, profile = await _research_profile_db()
    target_service = "AlphaGuard OpenAI API"
    target_account = "runtime-test-account"
    target_ref = keychain_ref(
        service=target_service,
        account=target_account,
    )
    store = MemorySecretStore(
        {
            (KEYCHAIN_ALIAS_SERVICE, "openai-primary"): target_ref,
            (target_service, target_account): "unit-test-provider-secret",
        }
    )
    token_path = ensure_credential_host_runtime(tmp_path / "runtime")
    app = FastAPI()
    app.include_router(
        build_credential_host_router(
            token_path=token_path,
            secret_store=store,
            db_provider=lambda: db,
        )
    )
    client = TestClient(app)
    payload = {
        "service": KEYCHAIN_ALIAS_SERVICE,
        "account": "openai-primary",
        "profile": _context(profile),
    }

    unauthorized = client.post(
        "/internal/alphaguard/credentials/read",
        json=payload,
    )
    assert unauthorized.status_code == 403
    assert "unit-test-provider-secret" not in unauthorized.text

    token = read_credential_host_token(token_path)
    mismatched = dict(payload)
    mismatched["profile"] = {
        **payload["profile"],
        "profile_version": "not-active",
    }
    denied = client.post(
        "/internal/alphaguard/credentials/read",
        json=mismatched,
        headers={CREDENTIAL_HOST_TOKEN_HEADER: token},
    )
    assert denied.status_code == 403
    assert "unit-test-provider-secret" not in denied.text

    allowed = client.post(
        "/internal/alphaguard/credentials/read",
        json=payload,
        headers={CREDENTIAL_HOST_TOKEN_HEADER: token},
    )
    assert allowed.status_code == 200
    assert allowed.json()["value"] == target_ref


@pytest.mark.asyncio
async def test_credential_host_errors_are_secret_free(tmp_path):
    db, profile = await _research_profile_db()
    store = MemorySecretStore(
        {
            (KEYCHAIN_ALIAS_SERVICE, "openai-primary"): SecretStoreError(
                "unit-test-provider-secret"
            )
        }
    )
    token_path = ensure_credential_host_runtime(tmp_path / "runtime")
    app = FastAPI()
    app.include_router(
        build_credential_host_router(
            token_path=token_path,
            secret_store=store,
            db_provider=lambda: db,
        )
    )
    response = TestClient(app).post(
        "/internal/alphaguard/credentials/read",
        json={
            "service": KEYCHAIN_ALIAS_SERVICE,
            "account": "openai-primary",
            "profile": _context(profile),
        },
        headers={
            CREDENTIAL_HOST_TOKEN_HEADER: read_credential_host_token(
                token_path
            )
        },
    )
    assert response.status_code == 403
    assert "unit-test-provider-secret" not in response.text


def test_credential_host_runtime_permissions_and_launch_lifecycle(tmp_path):
    token_path = ensure_credential_host_runtime(tmp_path / "runtime")
    assert token_path.is_file()
    assert os.stat(token_path).st_mode & 0o777 == 0o600
    assert os.stat(token_path.parent).st_mode & 0o777 == 0o700
    payload = _launch_agent_payload()
    assert payload["RunAtLoad"] is True
    assert payload["KeepAlive"] is True
    assert "--execute" in payload["ProgramArguments"]
    assert "0.0.0.0" in payload["ProgramArguments"]
    assert all(
        "API_KEY" not in str(value) and "provider-secret" not in str(value)
        for value in payload.values()
    )


def test_daily_market_context_runtime_allows_full_universe_provider_window():
    assert DAILY_MARKET_CONTEXT_TIMEOUT_SECONDS == 7200


@pytest.mark.asyncio
async def test_model_provider_is_checked_only_after_natural_trigger(monkeypatch):
    executor = ProductionDailyStageExecutor(FakeDB())

    class MustNotRun:
        def __init__(self, _db):
            raise AssertionError("provider status must not run without trigger")

    monkeypatch.setattr(
        "app.services.alphaguard.daily_stage_executor."
        "ModelRuntimeStatusService",
        MustNotRun,
    )
    no_signal = await executor.stage_model_chain(daily_run_id="no-signal")
    assert no_signal.result["provider_check"] == "NOT_REQUIRED"

    class NotReady:
        def __init__(self, _db):
            pass

        async def status(self, *, admin):
            assert admin is True
            return {
                "status": "NOT_CONFIGURED",
                "profiles": [],
                "budget": {"remaining_calls": 1, "remaining_cost": 1},
            }

    monkeypatch.setattr(
        "app.services.alphaguard.daily_stage_executor."
        "ModelRuntimeStatusService",
        NotReady,
    )
    executor.cache["observations"] = [
        {
            "user_id": "user-1",
            "triggered_proposal_ids": ["proposal-1"],
        }
    ]
    with pytest.raises(DailyRunBlocked) as blocked:
        await executor.stage_model_chain(daily_run_id="triggered")
    assert blocked.value.code == "MODEL_PROVIDER_UNAVAILABLE"
    assert "DEGRADED_PAPER" in str(blocked.value)
