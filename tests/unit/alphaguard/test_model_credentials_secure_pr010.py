from __future__ import annotations

import ctypes
from datetime import datetime, timezone
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

from app.schemas.alphaguard.model_runtime import CredentialCapabilitySummary
from app.services.alphaguard.model_credential_management_service import (
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
    operations = (
        ROOT / "frontend/src/views/AlphaGuard/Operations.vue"
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
    assert 'type="password"' in operations
    assert 'autocomplete="new-password"' in operations
    assert "credentialApiKey.value = ''" in operations
    assert "••••••••" in operations
    assert "show-password" not in operations
    assert "localStorage.setItem" not in operations
    assert "sessionStorage.setItem" not in operations
    assert "document.cookie" not in operations
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
    assert "实际传入的连接字符串" not in bridge
    assert "mongodb_conn[:30]" not in bridge


def test_credential_host_loads_only_model_apis_and_opens_models_tab():
    operations = (
        ROOT / "frontend/src/views/AlphaGuard/Operations.vue"
    ).read_text(encoding="utf-8")
    config_management = (
        ROOT / "frontend/src/views/Settings/ConfigManagement.vue"
    ).read_text(encoding="utf-8")

    credential_branch = operations.index("if (modelsOnly.value) {")
    operations_request = operations.index("alphaguardOperationsApi.readiness()")

    assert credential_branch < operations_request
    assert "const modelsOnly = computed(() => isCredentialHost || props.modelsOnly)" in operations
    assert "const activeOperationTab = ref(modelsOnly.value ? 'models' : 'services')" in operations
    assert 'v-model="activeOperationTab"' in operations
    assert 'v-model="activeModelTab"' in operations
    assert '<el-tab-pane label="模型与 API" name="models">' in operations
    assert '<section v-if="!modelsOnly" class="safety-strip">' in operations
    assert "'operations-tabs--embedded': props.embedded" in operations

    assert "import AlphaGuardOperations from '@/views/AlphaGuard/Operations.vue'" in config_management
    assert '<span>1. 服务商配置</span>' in config_management
    assert '<span>2. API 密钥</span>' in config_management
    assert '<AlphaGuardOperations' in config_management
    assert "models-only" in config_management
    assert "embedded" in config_management
    assert ':initial-model-tab="activeSecureModelTab"' in config_management
    assert '@model-tab-change="handleSecureModelTabChange"' in config_management
    assert '<div v-if="activeTab === \'validation\'">' in config_management
    assert '<div v-if="activeTab === \'legacy-model-catalog\'">' in config_management
    assert 'activeTab === \'legacy-providers\'' in config_management
    assert 'activeTab === \'legacy-api-keys\'' in config_management


def test_provider_setup_uses_explicit_guided_create_validate_credential_flow():
    operations = (
        ROOT / "frontend/src/views/AlphaGuard/Operations.vue"
    ).read_text(encoding="utf-8")

    assert "endpointEditorMode !== 'closed'" in operations
    assert '>添加服务商</el-button>' in operations
    assert "'继续配置'" in operations
    assert ">创建新版本</el-button>" in operations
    assert "create_new_version: true" in operations
    assert "该服务地址已经登记，请继续配置已有服务商或显式创建新版本" in operations
    assert "validatedCompatibleEndpoints" in operations
    assert ":model-value=\"selectedCredentialEndpoint?.display_name" in operations
    assert "接口版本：当前版本（由系统自动选择）" in operations
    assert "synchronizeEndpointSelections" in operations
    assert "credentialSubmissionBlocked" in operations
    assert "compatibleCredentialDefaultName" in operations
    assert "`${endpoint.endpoint_profile_id}-${endpoint.profile_version}-primary`" in operations
    assert "configurationErrorMessage" in operations
    assert "CREDENTIAL_BINDING_EXISTS" in operations
    assert "该密钥绑定到了旧接口版本" in operations
    assert "系统会自动绑定当前服务商" in operations
    assert "配置完整性" in operations
    assert "endpointConfigurationStatus" in operations
    assert "lastConfigurationError" in operations
    assert "if (!response.data.stored)" in operations
    assert "ElMessage.error(lastConfigurationError.value)" in operations
    assert "当前没有地址验证通过的服务商" in operations
    assert "先到“服务商配置”添加并验证接口地址" in operations
    assert "if (response.data.url_validation_status === 'PASS') {" in operations
    assert "credentialProviderType.value = 'OPENAI_COMPATIBLE'" in operations
    assert "credentialEndpointIdentity.value = validatedIdentity" in operations


def test_model_configuration_experience_is_chinese_and_guided():
    operations = (
        ROOT / "frontend/src/views/AlphaGuard/Operations.vue"
    ).read_text(encoding="utf-8")
    config_management = (
        ROOT / "frontend/src/views/Settings/ConfigManagement.vue"
    ).read_text(encoding="utf-8")

    for label in (
        "服务商配置",
        "模型管理",
        "API 密钥",
        "模型角色",
        "能力检测",
        "调用限制",
    ):
        assert label in operations
        assert label in config_management

    for step in (
        "① 添加服务商",
        "② 添加 API 密钥",
        "③ 登记普通模型和终审模型",
        "④ 创建模型角色",
        "⑤ 执行能力检测",
        "⑥ 完成配置",
    ):
        assert step in operations

    for action in (
        "添加 API 密钥",
        "添加模型",
        "创建普通模型角色",
        "创建终审模型角色",
        "开始能力检测",
    ):
        assert action in operations

    assert "当前缺少：" in operations
    assert "下一步：点击" in operations
    assert "接口版本：当前版本（由系统自动选择）" in operations
    assert "高级信息（技术状态与版本）" in operations
    assert "URL_VALIDATED: '地址验证通过'" in operations
    assert "UNVERIFIED: '未验证'" in operations
    assert "MISSING: '未配置'" in operations
    assert "DEGRADED: '异常'" in operations
    assert "BLOCKED: '已阻止'" in operations
    assert "ACTIVE: '已启用'" in operations
    assert "REUSED: '已复用'" in operations
    assert "CREATED: '已创建'" in operations


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
