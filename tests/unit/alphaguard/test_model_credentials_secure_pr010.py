from __future__ import annotations

import ctypes
from datetime import datetime, timezone
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

from app.schemas.alphaguard.model_runtime import CredentialCapabilitySummary
from app.services.alphaguard.model_credential_management_service import (
    CredentialLifecycleConflict,
    ModelCredentialManagementService,
    _classify_provider_error,
)
from app.services.alphaguard.model_credential_service import (
    CredentialNotConfigured,
    ModelCredentialService,
)
from app.services.alphaguard.model_secret_store import (
    KEYCHAIN_ALIAS_SERVICE,
    MacOSKeychainSecretStore,
    SecretNotFound,
    SecretStoreError,
    keychain_ref,
)
from tests.unit.alphaguard._fakes import FakeDB
from tradingagents.alphaguard.mongo_indexes import ALPHAGUARD_INDEX_SPECS


ROOT = Path(__file__).resolve().parents[3]
TEST_SECRET = "test-provider-secret-never-persist"


class FakeSecretStore:
    available = True

    def __init__(self):
        self.values: dict[tuple[str, str], str] = {}
        self.fail_writes = False
        self.fail_deletes: set[tuple[str, str]] = set()

    def read(self, *, service: str, account: str) -> str:
        try:
            return self.values[(service, account)]
        except KeyError as exc:
            raise SecretNotFound("credential is not configured") from exc

    def write(self, *, service: str, account: str, secret: str) -> None:
        if self.fail_writes:
            raise SecretStoreError("Secret Store operation failed")
        self.values[(service, account)] = secret

    def delete(
        self,
        *,
        service: str,
        account: str,
        missing_ok: bool = False,
    ) -> None:
        if (service, account) in self.fail_deletes:
            raise SecretStoreError("Secret Store operation failed")
        if (service, account) not in self.values and not missing_ok:
            raise SecretNotFound("credential is not configured")
        self.values.pop((service, account), None)


def capability(
    *,
    auth: str = "READY",
    normal: str = "READY",
    top: str = "READY",
) -> CredentialCapabilitySummary:
    return CredentialCapabilitySummary(
        provider="openai",
        authentication_status=auth,
        provider_access_status=auth,
        normal_model_status=normal,
        top_model_status=top,
        structured_output_status="PRICE_NOT_VERIFIED",
        price_status="NOT_VERIFIED",
        budget_status="BLOCKED",
        checked_at=datetime.now(timezone.utc),
    )


def configured_service():
    db = FakeDB()
    store = FakeSecretStore()
    service = ModelCredentialManagementService(db, secret_store=store)

    async def ready_probe(**_kwargs):
        return capability()

    async def no_persisted_probe(**_kwargs):
        return None

    service._probe_secret = ready_probe
    service._persist_capability_checks = no_persisted_probe
    return db, store, service


@pytest.mark.asyncio
async def test_admin_create_stores_secret_only_in_keychain_boundary():
    db, store, service = configured_service()
    result = await service.create(
        credential_id="openai-primary",
        provider="openai",
        secret=TEST_SECRET,
        base_url=None,
        operator_user_id="admin",
        trace_id="trace-create",
    )
    assert result.stored is True
    assert result.status == "DEGRADED"
    document = db["ag_model_credentials"].documents[0]
    serialized = repr(document)
    assert TEST_SECRET not in serialized
    for forbidden in (
        "api_key",
        "secret",
        "authorization",
        "prefix",
        "suffix",
        "length",
        "hash",
    ):
        assert forbidden not in serialized.lower()
    alias_ref = store.read(
        service=KEYCHAIN_ALIAS_SERVICE,
        account="openai-primary",
    )
    assert alias_ref == document["credential_ref"]
    assert ModelCredentialService(store).resolve(
        "keychain-alias:openai-primary"
    ) == TEST_SECRET


@pytest.mark.asyncio
async def test_failed_replacement_keeps_old_credential():
    db, store, service = configured_service()
    await service.create(
        credential_id="openai-primary",
        provider="openai",
        secret=TEST_SECRET,
        base_url=None,
        operator_user_id="admin",
        trace_id="trace-create",
    )
    old_ref = db["ag_model_credentials"].documents[0]["credential_ref"]

    async def unauthorized(**_kwargs):
        return capability(auth="UNAUTHORIZED")

    service._probe_secret = unauthorized
    result = await service.replace(
        credential_id="openai-primary",
        secret="invalid-new-secret",
        base_url=None,
        operator_user_id="admin",
        trace_id="trace-replace-failed",
    )
    assert result.replaced is False
    assert db["ag_model_credentials"].documents[0]["credential_ref"] == old_ref
    assert ModelCredentialService(store).resolve(
        "keychain-alias:openai-primary"
    ) == TEST_SECRET
    assert "invalid-new-secret" not in repr(db.collections)


@pytest.mark.asyncio
async def test_successful_replacement_switches_alias_and_removes_old_secret():
    db, store, service = configured_service()
    await service.create(
        credential_id="openai-primary",
        provider="openai",
        secret=TEST_SECRET,
        base_url=None,
        operator_user_id="admin",
        trace_id="trace-create",
    )
    old_ref = db["ag_model_credentials"].documents[0]["credential_ref"]
    result = await service.replace(
        credential_id="openai-primary",
        secret="replacement-test-secret",
        base_url=None,
        operator_user_id="admin",
        trace_id="trace-replace",
    )
    new_ref = db["ag_model_credentials"].documents[0]["credential_ref"]
    assert result.replaced is True
    assert new_ref != old_ref
    assert store.read(
        service=KEYCHAIN_ALIAS_SERVICE, account="openai-primary"
    ) == new_ref
    assert ModelCredentialService(store).resolve(
        "keychain-alias:openai-primary"
    ) == "replacement-test-secret"
    old_service, old_account = service._parse_direct_ref(old_ref)
    with pytest.raises(SecretNotFound):
        store.read(service=old_service, account=old_account)


@pytest.mark.asyncio
async def test_revoke_blocks_runtime_and_keeps_capability_history():
    db, store, service = configured_service()
    await service.create(
        credential_id="openai-primary",
        provider="openai",
        secret=TEST_SECRET,
        base_url=None,
        operator_user_id="admin",
        trace_id="trace-create",
    )
    await db["ag_model_capability_checks"].insert_one(
        {"capability_check_id": "history-kept"}
    )
    result = await service.revoke(
        credential_id="openai-primary",
        operator_user_id="admin",
        trace_id="trace-revoke",
    )
    assert result["status"] == "REVOKED"
    with pytest.raises(CredentialNotConfigured):
        ModelCredentialService(store).resolve(
            "keychain-alias:openai-primary"
        )
    assert db["ag_model_capability_checks"].count() == 1


@pytest.mark.asyncio
async def test_revoke_secret_store_failure_is_sanitized_and_retryable(
    monkeypatch,
):
    import app.routers.alphaguard_models as models_router
    from app.routers.auth_db import get_current_user

    db, store, service = configured_service()
    await service.create(
        credential_id="openai-primary",
        provider="openai",
        secret=TEST_SECRET,
        base_url=None,
        operator_user_id="admin",
        trace_id="trace-create",
    )
    store.fail_deletes.add(
        (KEYCHAIN_ALIAS_SERVICE, "openai-primary")
    )
    monkeypatch.setattr(models_router, "get_mongo_db", lambda: db)
    monkeypatch.setattr(
        models_router,
        "ModelCredentialManagementService",
        lambda _db: service,
    )
    app = FastAPI()
    app.include_router(models_router.router, prefix="/api")
    app.dependency_overrides[get_current_user] = lambda: {
        "id": "admin",
        "is_admin": True,
    }
    client = TestClient(app)

    failed = client.delete(
        "/api/alphaguard/models/credentials/openai-primary"
    )

    assert failed.status_code == 503
    assert failed.json()["detail"] == {
        "error_code": "SECRET_STORE_UNAVAILABLE",
        "sanitized_message": "安全 Secret Store 操作失败；请稍后重试",
    }
    assert TEST_SECRET not in failed.text
    assert db["ag_model_credentials"].documents[0]["status"] != "REVOKED"
    assert ModelCredentialService(store).resolve(
        "keychain-alias:openai-primary"
    ) == TEST_SECRET

    store.fail_deletes.clear()
    retried = client.delete(
        "/api/alphaguard/models/credentials/openai-primary"
    )
    assert retried.status_code == 200
    assert retried.json()["data"]["status"] == "REVOKED"


@pytest.mark.asyncio
async def test_revoke_direct_secret_cleanup_failure_reports_revoked_pending():
    db, store, service = configured_service()
    await service.create(
        credential_id="openai-primary",
        provider="openai",
        secret=TEST_SECRET,
        base_url=None,
        operator_user_id="admin",
        trace_id="trace-create",
    )
    direct_ref = db["ag_model_credentials"].documents[0]["credential_ref"]
    direct_identity = service._parse_direct_ref(direct_ref)
    store.fail_deletes.add(direct_identity)

    pending = await service.revoke(
        credential_id="openai-primary",
        operator_user_id="admin",
        trace_id="trace-revoke-failed-cleanup",
    )

    assert pending["status"] == "REVOKED"
    assert pending["cleanup_status"] == "PENDING"
    assert db["ag_model_credentials"].documents[0]["status"] == "REVOKED"
    with pytest.raises(CredentialNotConfigured):
        ModelCredentialService(store).resolve(
            "keychain-alias:openai-primary"
        )
    assert direct_identity in store.values

    store.fail_deletes.clear()
    result = await service.revoke(
        credential_id="openai-primary",
        operator_user_id="admin",
        trace_id="trace-revoke-cleanup-retry",
    )
    assert result["status"] == "REVOKED"
    assert result["cleanup_status"] == "COMPLETE"
    assert direct_identity not in store.values
    assert (await service.list_public())[0]["last_error_code"] is None


@pytest.mark.asyncio
async def test_revoke_database_failure_restores_runtime_alias(monkeypatch):
    db, store, service = configured_service()
    await service.create(
        credential_id="openai-primary",
        provider="openai",
        secret=TEST_SECRET,
        base_url=None,
        operator_user_id="admin",
        trace_id="trace-create",
    )
    credentials = db["ag_model_credentials"]
    original_update_one = credentials.update_one
    update_calls = 0

    async def fail_finalize(*args, **kwargs):
        nonlocal update_calls
        update_calls += 1
        if update_calls == 2:
            raise RuntimeError("database unavailable")
        return await original_update_one(*args, **kwargs)

    monkeypatch.setattr(credentials, "update_one", fail_finalize)
    with pytest.raises(RuntimeError, match="database unavailable"):
        await service.revoke(
            credential_id="openai-primary",
            operator_user_id="admin",
            trace_id="trace-revoke-db-failure",
        )

    assert credentials.documents[0]["status"] != "REVOKED"
    assert credentials.documents[0].get("lifecycle_operation_id") is None
    assert ModelCredentialService(store).resolve(
        "keychain-alias:openai-primary"
    ) == TEST_SECRET


@pytest.mark.asyncio
async def test_replace_database_failure_restores_original_secret(monkeypatch):
    db, store, service = configured_service()
    await service.create(
        credential_id="openai-primary",
        provider="openai",
        secret=TEST_SECRET,
        base_url=None,
        operator_user_id="admin",
        trace_id="trace-create",
    )
    credentials = db["ag_model_credentials"]
    original_document = dict(credentials.documents[0])
    original_values = dict(store.values)
    original_update_one = credentials.update_one
    update_calls = 0

    async def fail_finalize(*args, **kwargs):
        nonlocal update_calls
        update_calls += 1
        if update_calls == 2:
            raise RuntimeError("database unavailable")
        return await original_update_one(*args, **kwargs)

    monkeypatch.setattr(credentials, "update_one", fail_finalize)
    with pytest.raises(RuntimeError, match="database unavailable"):
        await service.replace(
            credential_id="openai-primary",
            secret="replacement-secret",
            base_url=None,
            operator_user_id="admin",
            trace_id="trace-replace-db-failure",
        )

    credential = credentials.documents[0]
    assert credential["credential_ref"] == original_document["credential_ref"]
    assert credential.get("lifecycle_operation_id") is None
    assert store.values == original_values
    assert ModelCredentialService(store).resolve(
        "keychain-alias:openai-primary"
    ) == TEST_SECRET


@pytest.mark.asyncio
async def test_lifecycle_cas_conflict_never_overwrites_concurrent_alias():
    db, store, service = configured_service()
    await service.create(
        credential_id="openai-primary",
        provider="openai",
        secret=TEST_SECRET,
        base_url=None,
        operator_user_id="admin",
        trace_id="trace-create",
    )
    credential = db["ag_model_credentials"].documents[0]
    concurrent_ref = keychain_ref(
        service="AlphaGuard OpenAI API",
        account="concurrent-replacement",
    )
    store.write(
        service="AlphaGuard OpenAI API",
        account="concurrent-replacement",
        secret="concurrent-secret",
    )
    store.write(
        service=KEYCHAIN_ALIAS_SERVICE,
        account="openai-primary",
        secret=concurrent_ref,
    )
    credential["lifecycle_operation_id"] = "concurrent-owner"
    credential["lifecycle_operation"] = "REPLACE"
    values_before = dict(store.values)
    assert (await service.list_public())[0]["configured"] is False

    with pytest.raises(CredentialLifecycleConflict):
        await service.replace(
            credential_id="openai-primary",
            secret="losing-replacement",
            base_url=None,
            operator_user_id="admin",
            trace_id="trace-losing-replace",
        )
    with pytest.raises(CredentialLifecycleConflict):
        await service.revoke(
            credential_id="openai-primary",
            operator_user_id="admin",
            trace_id="trace-losing-revoke",
        )

    assert store.values == values_before
    assert store.read(
        service=KEYCHAIN_ALIAS_SERVICE,
        account="openai-primary",
    ) == concurrent_ref
    assert credential["lifecycle_operation_id"] == "concurrent-owner"


@pytest.mark.asyncio
async def test_audit_failure_does_not_mask_secret_store_error(monkeypatch):
    db, store, service = configured_service()
    await service.create(
        credential_id="openai-primary",
        provider="openai",
        secret=TEST_SECRET,
        base_url=None,
        operator_user_id="admin",
        trace_id="trace-create",
    )
    store.fail_deletes.add(
        (KEYCHAIN_ALIAS_SERVICE, "openai-primary")
    )

    async def fail_audit(**_kwargs):
        raise RuntimeError("audit database unavailable")

    monkeypatch.setattr(service, "audit", fail_audit)
    with pytest.raises(SecretStoreError, match="Secret Store operation failed"):
        await service.revoke(
            credential_id="openai-primary",
            operator_user_id="admin",
            trace_id="trace-secret-store-failure",
        )

    credential = db["ag_model_credentials"].documents[0]
    assert credential["status"] != "REVOKED"
    assert credential.get("lifecycle_operation_id") is None
    assert ModelCredentialService(store).resolve(
        "keychain-alias:openai-primary"
    ) == TEST_SECRET


@pytest.mark.asyncio
async def test_revoke_conflict_and_missing_have_distinct_http_statuses(
    monkeypatch,
):
    import app.routers.alphaguard_models as models_router
    from app.routers.auth_db import get_current_user

    db, store, service = configured_service()
    await service.create(
        credential_id="openai-primary",
        provider="openai",
        secret=TEST_SECRET,
        base_url=None,
        operator_user_id="admin",
        trace_id="trace-create",
    )
    store.write(
        service=KEYCHAIN_ALIAS_SERVICE,
        account="openai-primary",
        secret=keychain_ref(service="Concurrent", account="replacement"),
    )
    monkeypatch.setattr(models_router, "get_mongo_db", lambda: db)
    monkeypatch.setattr(
        models_router,
        "ModelCredentialManagementService",
        lambda _db: service,
    )
    app = FastAPI()
    app.include_router(models_router.router, prefix="/api")
    app.dependency_overrides[get_current_user] = lambda: {
        "id": "admin",
        "is_admin": True,
    }
    client = TestClient(app)

    conflict = client.delete(
        "/api/alphaguard/models/credentials/openai-primary"
    )
    missing = client.delete(
        "/api/alphaguard/models/credentials/not-configured"
    )

    assert conflict.status_code == 409
    assert conflict.json()["detail"]["error_code"] == (
        "CREDENTIAL_LIFECYCLE_CONFLICT"
    )
    assert missing.status_code == 404
    assert missing.json()["detail"]["error_code"] == "CREDENTIAL_NOT_FOUND"
    assert TEST_SECRET not in conflict.text + missing.text


@pytest.mark.asyncio
async def test_latest_success_clears_stale_public_error_code():
    db, _store, service = configured_service()
    await service.create(
        credential_id="openai-primary",
        provider="openai",
        secret=TEST_SECRET,
        base_url=None,
        operator_user_id="admin",
        trace_id="trace-create",
    )
    assert (await service.list_public())[0]["last_error_code"] == (
        "PRICE_NOT_VERIFIED"
    )

    events = db["ag_model_credential_events"]
    events.documents.clear()
    same_timestamp = datetime.now(timezone.utc)
    await events.insert_one(
        {
            "credential_id": "openai-primary",
            "status": "FAILED",
            "error_code": "UNAUTHORIZED",
            "created_at": same_timestamp,
        }
    )
    await events.insert_one(
        {
            "credential_id": "openai-primary",
            "status": "SUCCESS",
            "error_code": None,
            "created_at": same_timestamp,
        }
    )

    assert (await service.list_public())[0]["last_error_code"] is None


@pytest.mark.asyncio
async def test_public_projection_never_returns_secret_or_reference():
    _db, _store, service = configured_service()
    await service.create(
        credential_id="openai-primary",
        provider="openai",
        secret=TEST_SECRET,
        base_url=None,
        operator_user_id="admin",
        trace_id="trace-create",
    )
    payload = repr(await service.list_public())
    assert TEST_SECRET not in payload
    assert "credential_ref" not in payload
    assert "api_key" not in payload
    assert "••••••••" not in payload


def test_keychain_write_uses_native_framework_not_process_arguments(
    monkeypatch,
):
    captured = {}

    class FakeSecurity:
        def __getitem__(self, name):
            return getattr(self, name)

        @staticmethod
        def SecKeychainFindGenericPassword(*_args):
            return -25300

        @staticmethod
        def SecKeychainAddGenericPassword(
            _keychain,
            _service_length,
            _service,
            _account_length,
            _account,
            secret_length,
            secret_pointer,
            _item_ref,
        ):
            captured["native_secret"] = ctypes.string_at(
                secret_pointer,
                secret_length,
            )
            return 0

    class FakeCoreFoundation:
        @staticmethod
        def CFRelease(_item_ref):
            return None

    class FakeBindings:
        security = FakeSecurity()
        core_foundation = FakeCoreFoundation()

    monkeypatch.setattr(
        "app.services.alphaguard.model_secret_store.platform.system",
        lambda: "Darwin",
    )
    monkeypatch.setattr(
        "app.services.alphaguard.model_secret_store._load_keychain_bindings",
        lambda: FakeBindings(),
    )
    store = MacOSKeychainSecretStore()
    store.write(
        service="AlphaGuard OpenAI API",
        account="test-account",
        secret=TEST_SECRET,
    )
    assert captured["native_secret"] == TEST_SECRET.encode("utf-8")
    assert "subprocess" not in (
        ROOT
        / "app/services/alphaguard/model_secret_store.py"
    ).read_text(encoding="utf-8")


def test_provider_errors_are_stably_classified():
    class Error(RuntimeError):
        def __init__(self, code):
            self.status_code = code
            super().__init__("provider failure with no credential content")

    assert _classify_provider_error(Error(401)) == "UNAUTHORIZED"
    assert _classify_provider_error(Error(403)) == "PROJECT_ACCESS_DENIED"
    assert _classify_provider_error(Error(404)) == "MODEL_NOT_FOUND"
    assert _classify_provider_error(Error(429)) == "RATE_LIMITED"


@pytest.mark.asyncio
async def test_credential_api_is_admin_only_and_never_echoes_secret(
    monkeypatch,
):
    import app.routers.alphaguard_models as models_router
    from app.routers.auth_db import get_current_user

    db, _store, service = configured_service()
    monkeypatch.setattr(models_router, "get_mongo_db", lambda: db)
    monkeypatch.setattr(
        models_router,
        "ModelCredentialManagementService",
        lambda _db: service,
    )
    app = FastAPI()
    app.include_router(models_router.router, prefix="/api")
    app.dependency_overrides[get_current_user] = lambda: {
        "id": "ordinary",
        "is_admin": False,
    }
    client = TestClient(app)
    blocked = client.post(
        "/api/alphaguard/models/credentials",
        headers={"X-Request-ID": TEST_SECRET},
        json={
            "provider": "openai",
            "credential_name": "openai-primary",
            "api_key": TEST_SECRET,
        },
    )
    assert blocked.status_code == 403
    assert TEST_SECRET not in blocked.text
    assert db["ag_model_credential_events"].documents[-1][
        "action"
    ] == "PERMISSION_DENIED"
    assert TEST_SECRET not in repr(
        db["ag_model_credential_events"].documents
    )

    app.dependency_overrides[get_current_user] = lambda: {
        "id": "admin",
        "is_admin": True,
    }
    created = client.post(
        "/api/alphaguard/models/credentials",
        json={
            "provider": "openai",
            "credential_name": "openai-primary",
            "api_key": TEST_SECRET,
        },
    )
    assert created.status_code == 200
    assert TEST_SECRET not in created.text
    listing = client.get("/api/alphaguard/models/credentials")
    assert listing.status_code == 200
    assert TEST_SECRET not in listing.text
    assert "credential_ref" not in listing.text
    assert "api_key" not in listing.text.lower()
    malformed = client.put(
        "/api/alphaguard/models/credentials/openai-primary",
        json={"api_key": {"unexpected": TEST_SECRET}},
    )
    assert malformed.status_code == 400
    assert TEST_SECRET not in malformed.text


def test_frontend_secret_is_password_only_cleared_and_never_persisted():
    model_panel = (
        ROOT
        / "frontend/src/components/alphaguard/ModelConfigurationPanel.vue"
    ).read_text(encoding="utf-8")
    app_shell = (ROOT / "frontend/src/App.vue").read_text(
        encoding="utf-8"
    )
    header_actions = (
        ROOT / "frontend/src/components/Layout/HeaderActions.vue"
    ).read_text(encoding="utf-8")
    api = (
        ROOT / "frontend/src/api/alphaguardModels.ts"
    ).read_text(encoding="utf-8")
    assert 'type="password"' in model_panel
    assert 'autocomplete="new-password"' in model_panel
    assert "credentialApiKey.value = ''" in model_panel
    assert "••••••••" in model_panel
    assert "show-password" not in model_panel
    assert "localStorage.setItem" not in model_panel
    assert "sessionStorage.setItem" not in model_panel
    assert "document.cookie" not in model_panel
    assert "api.openai.com" not in api
    assert "/api/alphaguard/models/credentials" in api
    assert "VITE_ALPHAGUARD_CREDENTIAL_HOST" in app_shell
    assert "isDemo || isCredentialHost" in header_actions


def test_credential_host_is_narrow_and_connection_logs_are_redacted():
    host = (
        ROOT / "scripts/run_alphaguard_credential_host.py"
    ).read_text(encoding="utf-8")
    bridge = (ROOT / "app/core/config_bridge.py").read_text(
        encoding="utf-8"
    )
    assert "scheduler=false workers=false" in host
    assert 'path == "/api/system/config/validate"' in host
    assert '"/api/auth/login"' in host
    assert '"/api/alphaguard/models/"' in host
    assert "access_log=False" in host
    assert "await connect_database()" in host
    assert "await init_db()" not in host
    assert "实际传入的连接字符串" not in bridge
    assert "mongodb_conn[:30]" not in bridge


def test_credential_host_loads_only_model_apis_and_opens_models_tab():
    operations = (
        ROOT / "frontend/src/views/AlphaGuard/Operations.vue"
    ).read_text(encoding="utf-8")
    config_management = (
        ROOT / "frontend/src/views/Settings/ConfigManagement.vue"
    ).read_text(encoding="utf-8")

    credential_branch = operations.index("if (modelsOnly.value) return")
    operations_request = operations.index("alphaguardOperationsApi.overview()")

    assert credential_branch < operations_request
    assert "alphaguardOperationsApi.readiness()" not in operations
    assert "overviewResponse.data.readiness" in operations
    assert "const modelsOnly = computed(() => props.modelsOnly || isCredentialHost)" in operations
    assert "const activeOperationTab = ref(modelsOnly.value ? 'models' : 'services')" in operations
    assert 'v-model="activeOperationTab"' in operations
    assert '<el-tab-pane label="模型与 API" name="models">' in operations
    assert '<ModelConfigurationPanel />' in operations
    assert '<section class="safety-strip">' in operations
    assert "'operations-tabs--embedded': props.embedded" in operations

    assert "import AlphaGuardOperations from '@/views/AlphaGuard/Operations.vue'" in config_management
    assert '<span>大模型配置</span>' in config_management
    assert "const activeTab = ref('models')" in config_management
    assert '<span>1. 服务商配置</span>' not in config_management
    assert '<span>2. API 密钥</span>' not in config_management
    assert '<AlphaGuardOperations' in config_management
    assert "models-only" in config_management
    assert "embedded" in config_management
    assert "initial-model-tab" not in config_management
    assert "model-tab-change" not in config_management
    assert '<div v-if="activeTab === \'validation\'">' in config_management
    assert "legacy-model-catalog" not in config_management
    assert "legacy-providers" not in config_management
    assert "legacy-api-keys" not in config_management


def test_provider_setup_uses_explicit_guided_create_validate_credential_flow():
    model_panel = (
        ROOT
        / "frontend/src/components/alphaguard/ModelConfigurationPanel.vue"
    ).read_text(encoding="utf-8")

    assert "providerDialogVisible" in model_panel
    assert "保存并验证地址" in model_panel
    assert "create_new_version: true" in model_panel
    assert "validateEndpoint" in model_panel
    assert "selectPreferredEndpoint" in model_panel
    assert "credentialBlockedReason" in model_panel
    assert "`${endpoint.endpoint_profile_id}-${endpoint.profile_version}-primary`" in model_panel
    assert "parseActionError" in model_panel
    assert "CREDENTIAL_ENDPOINT_VERSION_MISMATCH" in model_panel
    assert "该密钥属于旧接口版本" in model_panel
    assert "endpointConfigurationStatus" in model_panel
    assert "actionError" in model_panel
    assert "if (!response.data.stored)" in model_panel
    assert "API 密钥未保存" in model_panel
    assert "selectedEndpoint.value.url_validation_status !== 'PASS'" in model_panel
    assert "credentialDialogVisible.value = true" in model_panel


def test_model_configuration_experience_is_chinese_and_guided():
    model_panel = (
        ROOT
        / "frontend/src/components/alphaguard/ModelConfigurationPanel.vue"
    ).read_text(encoding="utf-8")
    config_management = (
        ROOT / "frontend/src/views/Settings/ConfigManagement.vue"
    ).read_text(encoding="utf-8")

    for label in (
        "模型服务",
        "API 密钥",
        "决策模型",
        "连接检测",
        "调用限制",
    ):
        assert label in model_panel

    assert '<span>大模型配置</span>' in config_management
    for label in (
        "模型服务",
        "接口地址",
        "API 密钥",
        "普通决策模型",
        "风险终审模型",
    ):
        assert label in model_panel
    assert "保存模型设置" in model_panel
    assert "开始检测" in model_panel
    assert "高级信息与审计记录" in model_panel
    assert "configureDecisionModels" in model_panel
    simple_view = model_panel[
        model_panel.index('<header class="page-heading">'):
        model_panel.index('<el-collapse v-model="advancedSections"')
    ]
    assert "角色配置标识" not in simple_view
    assert "技术版本" not in simple_view
    assert "价格版本" not in simple_view
    assert "像 TradingAgents-CN 一样" not in simple_view
    assert "credentialBlockedReason" in simple_view
    assert "modelSaveBlockedReason" in simple_view
    assert "capabilityBlockedReason" in simple_view
    assert "URL_VALIDATED: '地址验证通过'" in model_panel
    assert "UNVERIFIED: '未验证'" in model_panel
    assert "MISSING: '未配置'" in model_panel
    assert "DEGRADED: '异常'" in model_panel
    assert "BLOCKED: '已阻止'" in model_panel
    assert "ACTIVE: '已启用'" in model_panel
    assert "REUSED: '已复用'" in model_panel
    assert "CREATED: '已创建'" in model_panel


def test_model_configuration_explains_invalid_actions_before_request():
    model_panel = (
        ROOT
        / "frontend/src/components/alphaguard/ModelConfigurationPanel.vue"
    ).read_text(encoding="utf-8")
    api = (
        ROOT / "frontend/src/api/alphaguardModels.ts"
    ).read_text(encoding="utf-8")
    request = (
        ROOT / "frontend/src/api/request.ts"
    ).read_text(encoding="utf-8")

    assert ':disabled="Boolean(credentialBlockedReason)"' not in model_panel
    assert ':disabled="Boolean(modelAddBlockedReason)"' not in model_panel
    assert ':disabled="Boolean(modelSaveBlockedReason)"' not in model_panel
    assert ':disabled="Boolean(capabilityBlockedReason)"' not in model_panel
    assert "ElMessage.warning(modelAddBlockedReason.value)" in model_panel
    assert "ElMessage.warning(modelSaveBlockedReason.value)" in model_panel
    assert "ElMessage.warning(capabilityBlockedReason.value)" in model_panel
    assert "if (!credentialReady.value) return '请先添加或修复 API 密钥。'" in model_panel
    assert "CREDENTIAL_ENDPOINT_VERSION_MISMATCH" in model_panel
    assert "PROVIDER_ERROR: '服务异常'" in model_panel
    assert "UNVERIFIED: '未验证'" in model_panel
    assert "capabilityGuidance(profileForRole(role))" in model_panel
    assert "last_error_code?: string | null" in api
    assert "skipErrorHandler: true" in api[api.index("capabilityCheck(payload"):]
    not_found_case = request[request.index("case 404:"):request.index("case 429:")]
    assert "if (!config?.skipErrorHandler)" in not_found_case


def test_legacy_config_validation_uses_authenticated_api_client():
    app = (ROOT / "frontend/src/App.vue").read_text(encoding="utf-8")
    validator = (
        ROOT / "frontend/src/components/ConfigValidator.vue"
    ).read_text(encoding="utf-8")
    config_api = (ROOT / "frontend/src/api/config.ts").read_text(encoding="utf-8")

    assert "validateSystemConfig" in config_api
    assert "ApiClient.get<T>('/api/system/config/validate'" in config_api
    assert "configApi.validateSystemConfig" in app
    assert "configApi.validateSystemConfig" in validator
    assert "axios.get('/api/system/config/validate')" not in app
    assert "axios.get('/api/system/config/validate')" not in validator


def test_configuration_api_is_refresh_driven_and_returns_no_secret_fields():
    api = (
        ROOT / "frontend/src/api/alphaguardModels.ts"
    ).read_text(encoding="utf-8")
    router = (
        ROOT / "app/routers/alphaguard_models.py"
    ).read_text(encoding="utf-8")

    assert "endpointConfigurationStatus" in api
    assert "/configuration-status" in api
    assert "api_key" not in api[api.index("export interface ProviderConfigurationStatus"):api.index("export interface EndpointModelDefinition")]
    assert '"/endpoints/{endpoint_profile_id}/configuration-status"' in router
    assert '"credential_ref"' not in router[router.index("async def endpoint_configuration_status"):router.index("@router.post(\"/endpoints/{endpoint_profile_id}/validate\"")]


def test_credential_collections_have_create_only_indexes():
    assert "ag_model_credentials" in ALPHAGUARD_INDEX_SPECS
    assert "ag_model_credential_events" in ALPHAGUARD_INDEX_SPECS
    assert any(
        item.get("unique")
        for item in ALPHAGUARD_INDEX_SPECS["ag_model_credentials"]
    )


def test_keychain_reference_contains_no_secret_material():
    reference = keychain_ref(
        service="AlphaGuard OpenAI API",
        account="openai-safe-account",
    )
    assert reference.startswith("keychain:")
    assert TEST_SECRET not in reference
