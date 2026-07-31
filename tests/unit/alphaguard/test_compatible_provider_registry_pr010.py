from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

from bson import Decimal128
from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

from app.routers.auth_db import get_current_user
from app.schemas.alphaguard.model_runtime import (
    CredentialCapabilitySummary,
    EndpointPriceVersion,
)
from app.services.alphaguard.compatible_provider_registry import (
    CompatibleProviderRegistryService,
    ProviderRegistryConflict,
    ProviderRegistryNotReady,
)
from app.services.alphaguard.model_credential_management_service import (
    ModelCredentialManagementService,
)
from app.services.alphaguard.model_endpoint_security import (
    EndpointSafetyResult,
    EndpointSafetyValidator,
    EndpointSecurityError,
    EndpointAuth,
    PinnedHTTPSNetworkTransport,
    parse_registered_endpoint,
)
from app.services.alphaguard.model_profile_registry import ModelProfileRegistry
from app.services.alphaguard.model_budget_service import ModelBudgetService
from app.services.alphaguard.model_provider_runtime import ModelProviderRuntime
from app.services.alphaguard.model_credential_service import ModelCredentialService
from app.services.alphaguard.model_secret_store import keychain_ref
from app.services.alphaguard.model_secret_store import SecretNotFound
from tests.unit.alphaguard._fakes import FakeDB
from tradingagents.alphaguard.mongo_indexes import ALPHAGUARD_INDEX_SPECS


ROOT = Path(__file__).resolve().parents[3]
TEST_SECRET = "compatible-test-secret-never-persist"


class FakeSecretStore:
    available = True

    def __init__(self):
        self.values: dict[tuple[str, str], str] = {}

    def read(self, *, service: str, account: str) -> str:
        try:
            return self.values[(service, account)]
        except KeyError as exc:
            raise SecretNotFound("credential is not configured") from exc

    def write(self, *, service: str, account: str, secret: str) -> None:
        self.values[(service, account)] = secret

    def delete(
        self, *, service: str, account: str, missing_ok: bool = False
    ) -> None:
        if (service, account) not in self.values and not missing_ok:
            raise SecretNotFound("credential is not configured")
        self.values.pop((service, account), None)


class SafeValidator:
    async def validate(self, base_url: str) -> EndpointSafetyResult:
        parsed = parse_registered_endpoint(base_url)
        return EndpointSafetyResult(
            base_url=parsed.base_url,
            normalized_origin=parsed.normalized_origin,
            resolved_ips=("93.184.216.34",),
            actual_peer_ip="93.184.216.34",
            status_code=401,
            redirect_status="NONE",
        )


async def validated_registry(*, confirm=True):
    db = FakeDB()
    store = FakeSecretStore()
    registry = CompatibleProviderRegistryService(
        db, safety_validator=SafeValidator(), secret_store=store
    )
    draft, _ = await registry.register_endpoint(
        display_name="Compatible Test",
        base_url="https://models.example.com/v1",
        api_mode="OPENAI_CHAT_COMPLETIONS",
        auth_scheme="BEARER",
        models_endpoint_enabled=True,
        structured_output_mode="NATIVE_JSON_SCHEMA",
        notes="test endpoint",
        created_by="admin",
    )
    endpoint = await registry.validate_endpoint(
        endpoint_profile_id=draft.endpoint_profile_id,
        profile_version=draft.profile_version,
        confirm_data_transmission=confirm,
        operator_user_id="admin",
        trace_id="trace-validate",
    )
    return db, store, registry, endpoint


def test_static_endpoint_validation_rejects_ssrf_inputs():
    rejected = {
        "http://example.com/v1": "HTTPS_REQUIRED",
        "https://user:pass@example.com/v1": "URL_CREDENTIALS_FORBIDDEN",
        "https://example.com/v1#fragment": "URL_FRAGMENT_FORBIDDEN",
        "https://localhost/v1": "SSRF_INTERNAL_HOSTNAME",
        "https://127.0.0.1/v1": "SSRF_UNSAFE_ADDRESS",
        "https://10.0.0.2/v1": "SSRF_UNSAFE_ADDRESS",
        "https://169.254.169.254/latest": "SSRF_UNSAFE_ADDRESS",
        "https://[::1]/v1": "SSRF_UNSAFE_ADDRESS",
        "https://example.com/v1/%2e%2e/admin": "UNSAFE_PATH",
        "https://example.com/v1/%252e%252e/admin": "UNSAFE_PATH",
    }
    for value, code in rejected.items():
        with pytest.raises(EndpointSecurityError) as error:
            parse_registered_endpoint(value)
        assert error.value.code == code


@pytest.mark.asyncio
async def test_dns_resolving_to_private_address_is_rejected_before_network():
    validator = EndpointSafetyValidator(
        resolver=lambda _host, _port: ["192.168.1.7"]
    )
    with pytest.raises(EndpointSecurityError) as error:
        await validator.validate("https://provider.example/v1")
    assert error.value.code == "SSRF_UNSAFE_ADDRESS"


@pytest.mark.asyncio
async def test_proxy_fake_ip_uses_pinned_public_dns_fallback():
    fallback_calls = []
    validator = EndpointSafetyValidator(
        resolver=lambda _host, _port: ["198.18.1.73"],
        fake_ip_resolver=lambda host: (
            fallback_calls.append(host) or ["104.21.60.35", "172.67.191.33"]
        ),
    )
    endpoint = parse_registered_endpoint("https://provider.example/v1")
    resolved = await validator.resolve(endpoint)
    assert resolved == ("104.21.60.35", "172.67.191.33")
    assert fallback_calls == ["provider.example"]


@pytest.mark.asyncio
async def test_proxy_fake_ip_fallback_still_rejects_non_public_answers():
    validator = EndpointSafetyValidator(
        resolver=lambda _host, _port: ["198.18.1.73"],
        fake_ip_resolver=lambda _host: ["10.0.0.7"],
    )
    endpoint = parse_registered_endpoint("https://provider.example/v1")
    with pytest.raises(EndpointSecurityError) as error:
        await validator.resolve(endpoint)
    assert error.value.code == "SSRF_UNSAFE_ADDRESS"


@pytest.mark.asyncio
async def test_proxy_fake_ip_mixed_with_other_dns_answer_is_rejected():
    validator = EndpointSafetyValidator(
        resolver=lambda _host, _port: ["198.18.1.73", "104.21.60.35"],
        fake_ip_resolver=lambda _host: ["104.21.60.35"],
    )
    endpoint = parse_registered_endpoint("https://provider.example/v1")
    with pytest.raises(EndpointSecurityError) as error:
        await validator.resolve(endpoint)
    assert error.value.code == "SSRF_UNSAFE_ADDRESS"


@pytest.mark.asyncio
async def test_cross_origin_redirect_is_rejected(monkeypatch):
    class Response:
        status_code = 302
        headers = {"location": "https://other.example/v1"}

    class Client:
        _transport = object()

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return None

        def get(self, _url):
            return Response()

    monkeypatch.setattr(
        "app.services.alphaguard.model_endpoint_security.build_pinned_client",
        lambda **_kwargs: Client(),
    )
    validator = EndpointSafetyValidator(
        resolver=lambda _host, _port: ["93.184.216.34"]
    )
    with pytest.raises(EndpointSecurityError) as error:
        await validator.validate("https://provider.example/v1")
    assert error.value.code == "CROSS_ORIGIN_REDIRECT"


def test_pinned_transport_blocks_cross_origin_before_connection():
    endpoint = parse_registered_endpoint("https://provider.example/v1")
    transport = PinnedHTTPSNetworkTransport(
        endpoint=endpoint, pinned_ip="93.184.216.34"
    )
    import httpx

    with pytest.raises(EndpointSecurityError) as error:
        transport.handle_request(httpx.Request("GET", "https://evil.example/v1/models"))
    assert error.value.code == "SSRF_ORIGIN_ESCAPE"
    transport.close()


def test_x_api_key_auth_replaces_bearer_without_secret_in_repr():
    import httpx

    request = httpx.Request(
        "GET",
        "https://provider.example/v1/models",
        headers={"Authorization": "Bearer must-be-removed"},
    )
    auth = EndpointAuth(scheme="X_API_KEY", secret=TEST_SECRET)
    authorized = next(auth.auth_flow(request))
    assert "authorization" not in authorized.headers
    assert authorized.headers["x-api-key"] == TEST_SECRET
    assert TEST_SECRET not in repr(auth)


@pytest.mark.asyncio
async def test_endpoint_versions_are_create_only_reused_and_conflicting():
    db = FakeDB()
    registry = CompatibleProviderRegistryService(
        db, safety_validator=SafeValidator()
    )
    kwargs = dict(
        display_name="Compatible Test",
        base_url="https://models.example.com/v1",
        api_mode="OPENAI_CHAT_COMPLETIONS",
        auth_scheme="BEARER",
        models_endpoint_enabled=True,
        structured_output_mode="JSON_ONLY",
        notes=None,
        created_by="admin",
    )
    first, created = await registry.register_endpoint(**kwargs)
    second, reused = await registry.register_endpoint(**kwargs)
    assert created is True
    assert reused is False
    assert second.config_hash == first.config_hash
    with pytest.raises(ProviderRegistryConflict):
        await registry.register_endpoint(**{**kwargs, "display_name": "Changed"})


@pytest.mark.asyncio
async def test_endpoint_configuration_change_requires_explicit_new_version():
    db = FakeDB()
    registry = CompatibleProviderRegistryService(db)
    kwargs = dict(
        display_name="Compatible Test",
        base_url="https://models.example.com/v1",
        api_mode="OPENAI_CHAT_COMPLETIONS",
        auth_scheme="BEARER",
        models_endpoint_enabled=True,
        structured_output_mode="JSON_ONLY",
        notes=None,
        created_by="admin",
    )
    first, _ = await registry.register_endpoint(**kwargs)
    second, created = await registry.register_endpoint(
        **{
            **kwargs,
            "display_name": "Compatible Test v2",
            "auth_scheme": "X_API_KEY",
            "endpoint_profile_id": first.endpoint_profile_id,
            "create_new_version": True,
        }
    )

    assert created is True
    assert second.endpoint_profile_id == first.endpoint_profile_id
    assert second.profile_version == "v2"
    assert second.auth_scheme == "X_API_KEY"
    assert (
        await registry.endpoint(first.endpoint_profile_id, "v1")
    ).auth_scheme == "BEARER"

    with pytest.raises(ValueError, match="cannot change normalized origin"):
        await registry.register_endpoint(
            **{
                **kwargs,
                "base_url": "https://other.example.com/v1",
                "endpoint_profile_id": first.endpoint_profile_id,
                "create_new_version": True,
            }
        )


@pytest.mark.asyncio
async def test_manual_models_and_decimal_prices_are_endpoint_scoped():
    db, _store, registry, endpoint = await validated_registry()
    model, created = await registry.register_model(
        endpoint_profile_id=endpoint.endpoint_profile_id,
        endpoint_profile_version=endpoint.profile_version,
        remote_model_name="gpt-5.4-third-party-alias",
        display_name="Third Party Reasoner",
        role_capabilities=["NORMAL_TRADER"],
        supports_json_schema=True,
        supports_tool_call=False,
        supports_reasoning=True,
        max_context_tokens=128000,
        max_output_tokens=8000,
        created_by="admin",
    )
    assert created is True
    assert model.status == "READY"
    assert model.remote_model_name != "gpt-4o-mini"
    price, price_created = await registry.register_price(
        endpoint_profile_id=endpoint.endpoint_profile_id,
        endpoint_profile_version=endpoint.profile_version,
        endpoint_model_id=model.endpoint_model_id,
        endpoint_model_version=model.model_version,
        input_price_per_million=Decimal("1.234567"),
        cached_input_price_per_million=Decimal("0.123456"),
        output_price_per_million=Decimal("9.876543"),
        currency="usd",
        effective_at=datetime(2026, 7, 30, tzinfo=timezone.utc),
        source_description="provider invoice pricing",
        verified=True,
        created_by="admin",
    )
    assert price_created is True
    assert price.currency == "USD"
    stored = db["ag_model_endpoint_prices"].documents[0]
    assert isinstance(stored["input_price_per_million"], Decimal128)
    same, same_created = await registry.register_price(
        endpoint_profile_id=endpoint.endpoint_profile_id,
        endpoint_profile_version=endpoint.profile_version,
        endpoint_model_id=model.endpoint_model_id,
        endpoint_model_version=model.model_version,
        input_price_per_million=Decimal("1.234567"),
        cached_input_price_per_million=Decimal("0.123456"),
        output_price_per_million=Decimal("9.876543"),
        currency="USD",
        effective_at=datetime(2026, 7, 30, tzinfo=timezone.utc),
        source_description="provider invoice pricing",
        verified=True,
        created_by="admin",
    )
    assert same_created is False
    assert same.content_hash == price.content_hash


@pytest.mark.asyncio
async def test_self_hosted_zero_price_is_endpoint_scoped_and_budget_ready():
    db, _store, registry, endpoint = await validated_registry()
    model, _ = await registry.register_model(
        endpoint_profile_id=endpoint.endpoint_profile_id,
        endpoint_profile_version=endpoint.profile_version,
        remote_model_name="self-hosted-model",
        display_name="Self Hosted Model",
        role_capabilities=["NORMAL_TRADER"],
        supports_json_schema=True,
        supports_tool_call=False,
        supports_reasoning=None,
        max_context_tokens=64000,
        max_output_tokens=4000,
        created_by="admin",
    )
    price, created = await registry.register_price(
        endpoint_profile_id=endpoint.endpoint_profile_id,
        endpoint_profile_version=endpoint.profile_version,
        endpoint_model_id=model.endpoint_model_id,
        endpoint_model_version=model.model_version,
        pricing_source="SELF_HOSTED",
        input_price_per_million=Decimal("0"),
        cached_input_price_per_million=Decimal("0"),
        output_price_per_million=Decimal("0"),
        currency="USD",
        effective_at=datetime(2026, 7, 30, tzinfo=timezone.utc),
        source_description="administrator attested self-hosted service",
        verified=True,
        created_by="admin",
    )
    assert created is True
    assert price.pricing_source == "SELF_HOSTED"
    assert price.input_price_per_million == 0
    assert price.cached_input_price_per_million == 0
    assert price.output_price_per_million == 0
    assert price.endpoint_profile_id == endpoint.endpoint_profile_id
    stored = db["ag_model_endpoint_prices"].documents[0]
    assert stored["pricing_source"] == "SELF_HOSTED"
    stored["effective_at"] = stored["effective_at"].replace(tzinfo=None)
    status = await registry.configuration_status(
        endpoint.endpoint_profile_id, endpoint.profile_version
    )
    components = {item["key"]: item for item in status["components"]}
    assert components["normal_price"]["status"] == "SELF_HOSTED_ZERO"
    assert components["normal_price"]["complete"] is True
    assert components["budget"]["reason_code"] == (
        "BUDGET_PRICING_UNAVAILABLE"
    )


def test_external_provider_price_cannot_use_zero():
    payload = {
        "price_version_id": "external-zero",
        "price_version": "v1",
        "endpoint_profile_id": "external-endpoint",
        "endpoint_profile_version": "v1",
        "endpoint_model_id": "external-model",
        "endpoint_model_version": "v1",
        "pricing_source": "PROVIDER_PUBLISHED",
        "input_price_per_million": Decimal("0"),
        "cached_input_price_per_million": Decimal("0"),
        "output_price_per_million": Decimal("0"),
        "currency": "USD",
        "effective_at": datetime(2026, 7, 30, tzinfo=timezone.utc),
        "source_description": "invalid external zero pricing",
        "verified": True,
        "content_hash": "0" * 64,
        "created_by": "admin",
        "created_at": datetime(2026, 7, 30, tzinfo=timezone.utc),
    }
    with pytest.raises(ValueError, match="external provider pricing"):
        EndpointPriceVersion.model_validate(payload)


@pytest.mark.asyncio
async def test_models_endpoint_discovery_and_manual_fallback(monkeypatch):
    db, _store, registry, endpoint = await validated_registry()

    class Response:
        status_code = 200

        @staticmethod
        def raise_for_status():
            return None

        @staticmethod
        def json():
            return {"data": [{"id": "remote-a"}, {"id": "remote-b"}]}

    class Client:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return None

        def get(self, _url):
            return Response()

    monkeypatch.setattr(
        "app.services.alphaguard.compatible_provider_registry.build_pinned_client",
        lambda **_kwargs: Client(),
    )
    discovered = await registry.discover_models(
        endpoint_profile_id=endpoint.endpoint_profile_id,
        endpoint_profile_version=endpoint.profile_version,
        credential_id=None,
        operator_user_id="admin",
        trace_id="trace-discovery",
    )
    assert [item.remote_model_name for item in discovered] == [
        "remote-a",
        "remote-b",
    ]
    assert all(item.status == "UNVERIFIED" for item in discovered)
    manual, created = await registry.register_model(
        endpoint_profile_id=endpoint.endpoint_profile_id,
        endpoint_profile_version=endpoint.profile_version,
        remote_model_name="manual-only",
        display_name="Manual Only",
        role_capabilities=["NORMAL_TRADER"],
        supports_json_schema=False,
        supports_tool_call=False,
        supports_reasoning=None,
        max_context_tokens=None,
        max_output_tokens=None,
        created_by="admin",
    )
    assert created is True
    assert manual.discovery_mode == "MANUAL"


@pytest.mark.asyncio
async def test_compatible_credential_is_exactly_bound_and_secret_free():
    db, store, registry, endpoint = await validated_registry()
    service = ModelCredentialManagementService(db, secret_store=store)

    async def ready_probe(**_kwargs):
        return CredentialCapabilitySummary(
            provider="openai_compatible",
            authentication_status="READY",
            provider_access_status="READY",
            normal_model_status="READY",
            top_model_status="READY",
            structured_output_status="READY",
            price_status="VERIFIED",
            budget_status="READY",
            checked_at=datetime.now(timezone.utc),
        )

    service._probe_compatible_secret = ready_probe
    result = await service.create(
        credential_id="compatible-primary",
        provider="openai_compatible",
        provider_type="OPENAI_COMPATIBLE",
        endpoint_profile_id=endpoint.endpoint_profile_id,
        endpoint_profile_version=endpoint.profile_version,
        secret=TEST_SECRET,
        base_url=None,
        operator_user_id="admin",
        trace_id="trace-credential",
    )
    assert result.stored is True
    document = db["ag_model_credentials"].documents[0]
    assert document["normalized_origin"] == endpoint.normalized_origin
    assert document["auth_scheme"] == endpoint.auth_scheme
    assert TEST_SECRET not in repr(db.collections)
    for forbidden in ("api_key", "prefix", "suffix", "length"):
        assert forbidden not in repr(document).lower()
    changed_draft, _ = await registry.register_endpoint(
        display_name="Compatible Test Responses",
        base_url=endpoint.base_url,
        api_mode="OPENAI_RESPONSES",
        auth_scheme=endpoint.auth_scheme,
        models_endpoint_enabled=True,
        structured_output_mode="NATIVE_JSON_SCHEMA",
        notes="new immutable endpoint config",
        created_by="admin",
        endpoint_profile_id=endpoint.endpoint_profile_id,
        profile_version="v3",
    )
    later = await registry.validate_endpoint(
        endpoint_profile_id=changed_draft.endpoint_profile_id,
        profile_version=changed_draft.profile_version,
        confirm_data_transmission=True,
        operator_user_id="admin",
        trace_id="trace-new-version",
    )
    with pytest.raises(ProviderRegistryNotReady):
        registry._verify_credential_binding(later, document)


@pytest.mark.asyncio
async def test_compatible_credential_bootstrap_uses_bound_endpoint_and_stores_degraded(
    monkeypatch,
):
    db, store, _registry, endpoint = await validated_registry()
    service = ModelCredentialManagementService(db, secret_store=store)
    requested_urls: list[str] = []

    class Response:
        status_code = 200

        @staticmethod
        def json():
            return {"data": [{"id": "remote-normal"}, {"id": "remote-top"}]}

    class Client:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return None

        def get(self, url):
            requested_urls.append(url)
            return Response()

    monkeypatch.setattr(
        "app.services.alphaguard.model_credential_management_service."
        "build_pinned_client",
        lambda **_kwargs: Client(),
    )
    result = await service.create(
        credential_id="compatible-bootstrap",
        provider="openai_compatible",
        provider_type="OPENAI_COMPATIBLE",
        endpoint_profile_id=endpoint.endpoint_profile_id,
        endpoint_profile_version=endpoint.profile_version,
        secret=TEST_SECRET,
        base_url=None,
        operator_user_id="admin",
        trace_id="trace-bootstrap",
    )

    assert result.stored is True
    assert result.status == "DEGRADED"
    assert result.capability.authentication_status == "READY"
    assert result.capability.provider_access_status == "READY"
    assert result.capability.normal_model_status == "MODEL_NOT_FOUND"
    assert result.capability.top_model_status == "MODEL_NOT_FOUND"
    assert requested_urls == [f"{endpoint.base_url}/models"]
    assert all("api.openai.com" not in url for url in requested_urls)
    assert TEST_SECRET not in repr(db.collections)


@pytest.mark.asyncio
async def test_official_credential_rejects_compatible_endpoint_binding():
    db = FakeDB()
    store = FakeSecretStore()
    service = ModelCredentialManagementService(db, secret_store=store)

    with pytest.raises(
        ValueError,
        match="official credential cannot bind a compatible Endpoint Profile",
    ):
        await service.create(
            credential_id="invalid-official-binding",
            provider="openai",
            provider_type="OPENAI_OFFICIAL",
            endpoint_profile_id="compatible-endpoint",
            endpoint_profile_version="v2",
            secret=TEST_SECRET,
            base_url=None,
            operator_user_id="admin",
            trace_id="trace-invalid-binding",
        )

    assert db["ag_model_credentials"].count() == 0
    assert not store.values


@pytest.mark.asyncio
async def test_failed_compatible_verification_persists_no_secret_or_metadata():
    db, store, _registry, endpoint = await validated_registry()
    service = ModelCredentialManagementService(db, secret_store=store)

    async def unauthorized(**_kwargs):
        return CredentialCapabilitySummary(
            provider="openai_compatible",
            authentication_status="UNAUTHORIZED",
            provider_access_status="UNAUTHORIZED",
            normal_model_status="NOT_CHECKED",
            top_model_status="NOT_CHECKED",
            structured_output_status="NOT_CHECKED",
            price_status="NOT_VERIFIED",
            budget_status="BLOCKED",
            checked_at=datetime.now(timezone.utc),
        )

    service._probe_compatible_secret = unauthorized
    result = await service.create(
        credential_id="compatible-failed",
        provider="openai_compatible",
        provider_type="OPENAI_COMPATIBLE",
        endpoint_profile_id=endpoint.endpoint_profile_id,
        endpoint_profile_version=endpoint.profile_version,
        secret=TEST_SECRET,
        base_url=None,
        operator_user_id="admin",
        trace_id="trace-failed",
    )
    assert result.stored is False
    assert db["ag_model_credentials"].count() == 0
    assert TEST_SECRET not in repr(db.collections)
    assert not any(TEST_SECRET in value for value in store.values.values())


@pytest.mark.asyncio
async def test_explicit_role_assignments_resolve_exact_dynamic_profiles():
    db, _store, registry, endpoint = await validated_registry()
    model, _ = await registry.register_model(
        endpoint_profile_id=endpoint.endpoint_profile_id,
        endpoint_profile_version=endpoint.profile_version,
        remote_model_name="compatible-model",
        display_name="Compatible Model",
        role_capabilities=["NORMAL_TRADER", "TOP_RISK_REVIEWER"],
        supports_json_schema=True,
        supports_tool_call=False,
        supports_reasoning=None,
        max_context_tokens=64000,
        max_output_tokens=4000,
        created_by="admin",
    )
    price, _ = await registry.register_price(
        endpoint_profile_id=endpoint.endpoint_profile_id,
        endpoint_profile_version=endpoint.profile_version,
        endpoint_model_id=model.endpoint_model_id,
        endpoint_model_version=model.model_version,
        input_price_per_million=Decimal("1.2"),
        cached_input_price_per_million=None,
        output_price_per_million=Decimal("4.8"),
        currency="USD",
        effective_at=datetime(2026, 7, 30, tzinfo=timezone.utc),
        source_description="verified provider pricing",
        verified=True,
        created_by="admin",
    )
    await db["ag_model_credentials"].insert_one(
        {
            "credential_id": "compatible-primary",
            "provider": "openai_compatible",
            "provider_type": "OPENAI_COMPATIBLE",
            "credential_ref": "keychain:service/account",
            "endpoint_profile_id": endpoint.endpoint_profile_id,
            "endpoint_profile_version": endpoint.profile_version,
            "normalized_origin": endpoint.normalized_origin,
            "auth_scheme": endpoint.auth_scheme,
            "status": "CONFIGURED",
        }
    )
    normal, assignment = await registry.register_profile_assignment(
        role="NORMAL_TRADER",
        profile_id="alphaguard_normal_compatible",
        profile_version="v1",
        endpoint_profile_id=endpoint.endpoint_profile_id,
        endpoint_profile_version=endpoint.profile_version,
        endpoint_model_id=model.endpoint_model_id,
        endpoint_model_version=model.model_version,
        credential_id="compatible-primary",
        price_version_id=price.price_version_id,
        price_version=price.price_version,
        prompt_profile_id="normal_trade_plan_prompt",
        explicit_same_model_confirmation=False,
        assigned_by="admin",
    )
    assert normal.production_allowed is True
    assert assignment.role == "NORMAL_TRADER"
    resolved = await ModelProfileRegistry(db).persisted_for_role(
        "NORMAL_TRADER"
    )
    assert resolved.config_hash == normal.config_hash
    same_profile, same_assignment = await registry.register_profile_assignment(
        role="NORMAL_TRADER",
        profile_id="alphaguard_normal_compatible",
        profile_version="v1",
        endpoint_profile_id=endpoint.endpoint_profile_id,
        endpoint_profile_version=endpoint.profile_version,
        endpoint_model_id=model.endpoint_model_id,
        endpoint_model_version=model.model_version,
        credential_id="compatible-primary",
        price_version_id=price.price_version_id,
        price_version=price.price_version,
        prompt_profile_id="normal_trade_plan_prompt",
        explicit_same_model_confirmation=False,
        assigned_by="admin",
    )
    assert same_profile.config_hash == normal.config_hash
    assert same_assignment.assignment_id == assignment.assignment_id
    assert db["ag_model_profile_assignments"].count() == 1
    with pytest.raises(ProviderRegistryNotReady):
        await registry.register_profile_assignment(
            role="TOP_RISK_REVIEWER",
            profile_id="alphaguard_top_compatible",
            profile_version="v1",
            endpoint_profile_id=endpoint.endpoint_profile_id,
            endpoint_profile_version=endpoint.profile_version,
            endpoint_model_id=model.endpoint_model_id,
            endpoint_model_version=model.model_version,
            credential_id="compatible-primary",
            price_version_id=price.price_version_id,
            price_version=price.price_version,
            prompt_profile_id="top_risk_review_prompt",
            explicit_same_model_confirmation=False,
            assigned_by="admin",
        )


@pytest.mark.asyncio
async def test_profile_assignment_rejects_cross_endpoint_model_and_price():
    db, _store, registry, endpoint = await validated_registry()
    other_draft, _ = await registry.register_endpoint(
        display_name="Other Compatible Test",
        base_url="https://other-models.example.com/v1",
        api_mode="OPENAI_CHAT_COMPLETIONS",
        auth_scheme="BEARER",
        models_endpoint_enabled=True,
        structured_output_mode="NATIVE_JSON_SCHEMA",
        notes=None,
        created_by="admin",
    )
    other_endpoint = await registry.validate_endpoint(
        endpoint_profile_id=other_draft.endpoint_profile_id,
        profile_version=other_draft.profile_version,
        confirm_data_transmission=True,
        operator_user_id="admin",
        trace_id="trace-other-endpoint",
    )
    other_model, _ = await registry.register_model(
        endpoint_profile_id=other_endpoint.endpoint_profile_id,
        endpoint_profile_version=other_endpoint.profile_version,
        remote_model_name="other-compatible-model",
        display_name="Other Compatible Model",
        role_capabilities=["NORMAL_TRADER"],
        supports_json_schema=True,
        supports_tool_call=False,
        supports_reasoning=None,
        max_context_tokens=64000,
        max_output_tokens=4000,
        created_by="admin",
    )
    other_price, _ = await registry.register_price(
        endpoint_profile_id=other_endpoint.endpoint_profile_id,
        endpoint_profile_version=other_endpoint.profile_version,
        endpoint_model_id=other_model.endpoint_model_id,
        endpoint_model_version=other_model.model_version,
        input_price_per_million=Decimal("1"),
        cached_input_price_per_million=None,
        output_price_per_million=Decimal("2"),
        currency="USD",
        effective_at=datetime(2026, 7, 30, tzinfo=timezone.utc),
        source_description="other verified price",
        verified=True,
        created_by="admin",
    )
    await db["ag_model_credentials"].insert_one(
        {
            "credential_id": "first-endpoint-credential",
            "provider": "openai_compatible",
            "provider_type": "OPENAI_COMPATIBLE",
            "credential_ref": "keychain:service/account",
            "endpoint_profile_id": endpoint.endpoint_profile_id,
            "endpoint_profile_version": endpoint.profile_version,
            "normalized_origin": endpoint.normalized_origin,
            "auth_scheme": endpoint.auth_scheme,
            "status": "CONFIGURED",
        }
    )

    with pytest.raises(ProviderRegistryNotReady, match="exact endpoint version"):
        await registry.register_profile_assignment(
            role="NORMAL_TRADER",
            profile_id="cross-endpoint-profile",
            profile_version="v1",
            endpoint_profile_id=endpoint.endpoint_profile_id,
            endpoint_profile_version=endpoint.profile_version,
            endpoint_model_id=other_model.endpoint_model_id,
            endpoint_model_version=other_model.model_version,
            credential_id="first-endpoint-credential",
            price_version_id=other_price.price_version_id,
            price_version=other_price.price_version,
            prompt_profile_id="normal_trade_plan_prompt",
            explicit_same_model_confirmation=False,
            assigned_by="admin",
        )


@pytest.mark.asyncio
async def test_unified_model_runtime_uses_registered_pinned_endpoint():
    db, store, registry, endpoint = await validated_registry()
    model, _ = await registry.register_model(
        endpoint_profile_id=endpoint.endpoint_profile_id,
        endpoint_profile_version=endpoint.profile_version,
        remote_model_name="compatible-runtime-model",
        display_name="Runtime Model",
        role_capabilities=["NORMAL_TRADER"],
        supports_json_schema=True,
        supports_tool_call=False,
        supports_reasoning=None,
        max_context_tokens=64000,
        max_output_tokens=4000,
        created_by="admin",
    )
    price, _ = await registry.register_price(
        endpoint_profile_id=endpoint.endpoint_profile_id,
        endpoint_profile_version=endpoint.profile_version,
        endpoint_model_id=model.endpoint_model_id,
        endpoint_model_version=model.model_version,
        input_price_per_million=Decimal("1"),
        cached_input_price_per_million=None,
        output_price_per_million=Decimal("2"),
        currency="USD",
        effective_at=datetime(2026, 7, 30, tzinfo=timezone.utc),
        source_description="verified runtime price",
        verified=True,
        created_by="admin",
    )
    direct_ref = keychain_ref(service="Compatible Test", account="runtime")
    store.write(service="Compatible Test", account="runtime", secret=TEST_SECRET)
    await db["ag_model_credentials"].insert_one(
        {
            "credential_id": "runtime-compatible",
            "provider": "openai_compatible",
            "provider_type": "OPENAI_COMPATIBLE",
            "credential_ref": direct_ref,
            "endpoint_profile_id": endpoint.endpoint_profile_id,
            "endpoint_profile_version": endpoint.profile_version,
            "normalized_origin": endpoint.normalized_origin,
            "auth_scheme": endpoint.auth_scheme,
            "status": "CONFIGURED",
        }
    )
    profile, _assignment = await registry.register_profile_assignment(
        role="NORMAL_TRADER",
        profile_id="runtime-compatible-normal",
        profile_version="v1",
        endpoint_profile_id=endpoint.endpoint_profile_id,
        endpoint_profile_version=endpoint.profile_version,
        endpoint_model_id=model.endpoint_model_id,
        endpoint_model_version=model.model_version,
        credential_id="runtime-compatible",
        price_version_id=price.price_version_id,
        price_version=price.price_version,
        prompt_profile_id="normal_trade_plan_prompt",
        explicit_same_model_confirmation=False,
        assigned_by="admin",
    )
    runtime = ModelProviderRuntime(ModelCredentialService(store))
    llm = await runtime.create_registered(profile, db=db)
    assert llm.model_name == "compatible-runtime-model"
    assert str(llm.openai_api_base).rstrip("/") == endpoint.base_url
    assert TEST_SECRET not in repr(llm)
    assert llm.http_client._transport.endpoint.normalized_origin == (
        endpoint.normalized_origin
    )


def test_endpoint_api_is_admin_only_and_official_url_cannot_be_registered(monkeypatch):
    import app.routers.alphaguard_models as models_router

    db = FakeDB()
    monkeypatch.setattr(models_router, "get_mongo_db", lambda: db)
    app = FastAPI()
    app.include_router(models_router.router, prefix="/api")
    app.dependency_overrides[get_current_user] = lambda: {
        "id": "ordinary",
        "is_admin": False,
    }
    client = TestClient(app)
    payload = {
        "display_name": "Compatible",
        "provider_type": "OPENAI_COMPATIBLE",
        "base_url": "https://models.example.com/v1",
        "api_mode": "OPENAI_CHAT_COMPLETIONS",
        "auth_scheme": "BEARER",
        "models_endpoint_enabled": True,
        "structured_output_mode": "JSON_ONLY",
    }
    blocked = client.post("/api/alphaguard/models/endpoints", json=payload)
    assert blocked.status_code == 403
    app.dependency_overrides[get_current_user] = lambda: {
        "id": "admin",
        "is_admin": True,
    }
    official = client.post(
        "/api/alphaguard/models/endpoints",
        json={**payload, "base_url": "https://api.openai.com/v1"},
    )
    assert official.status_code == 400
    assert db["ag_model_provider_endpoints"].count() == 0


def test_staged_v4_configuration_persists_through_api_refresh_without_network(
    monkeypatch,
):
    import app.routers.alphaguard_models as models_router

    db = FakeDB()
    store = FakeSecretStore()
    registry_class = CompatibleProviderRegistryService

    def registry_factory(_db, **_kwargs):
        return registry_class(
            db,
            safety_validator=SafeValidator(),
            secret_store=store,
        )

    credential_service = ModelCredentialManagementService(
        db, secret_store=store
    )

    async def bootstrap_probe(**_kwargs):
        return CredentialCapabilitySummary(
            provider="openai_compatible",
            authentication_status="READY",
            provider_access_status="READY",
            normal_model_status="MODEL_NOT_FOUND",
            top_model_status="MODEL_NOT_FOUND",
            structured_output_status="NOT_CHECKED",
            price_status="NOT_VERIFIED",
            budget_status="BLOCKED",
            checked_at=datetime.now(timezone.utc),
        )

    credential_service._probe_compatible_secret = bootstrap_probe
    monkeypatch.setattr(models_router, "get_mongo_db", lambda: db)
    monkeypatch.setattr(
        models_router, "CompatibleProviderRegistryService", registry_factory
    )
    monkeypatch.setattr(
        models_router,
        "ModelCredentialManagementService",
        lambda _db: credential_service,
    )
    app = FastAPI()
    app.include_router(models_router.router, prefix="/api")
    app.dependency_overrides[get_current_user] = lambda: {
        "id": "admin",
        "is_admin": True,
    }
    client = TestClient(app)
    endpoint_payload = {
        "display_name": "Isolated Compatible",
        "provider_type": "OPENAI_COMPATIBLE",
        "base_url": "https://models.example.com/v1",
        "api_mode": "OPENAI_CHAT_COMPLETIONS",
        "auth_scheme": "BEARER",
        "models_endpoint_enabled": True,
        "structured_output_mode": "JSON_ONLY",
    }

    draft = client.post(
        "/api/alphaguard/models/endpoints", json=endpoint_payload
    )
    assert draft.status_code == 200
    endpoint_id = draft.json()["data"]["item"]["endpoint_profile_id"]
    validated_v2 = client.post(
        f"/api/alphaguard/models/endpoints/{endpoint_id}/validate",
        json={"profile_version": "v1", "confirm_data_transmission": True},
    )
    assert validated_v2.status_code == 200
    assert validated_v2.json()["data"]["profile_version"] == "v2"
    v2_credential_id = f"{endpoint_id}-v2-primary"
    v2_credential = client.post(
        "/api/alphaguard/models/credentials",
        json={
            "provider": "openai_compatible",
            "provider_type": "OPENAI_COMPATIBLE",
            "endpoint_profile_id": endpoint_id,
            "endpoint_profile_version": "v2",
            "credential_name": v2_credential_id,
            "api_key": TEST_SECRET,
        },
    )
    assert v2_credential.status_code == 200
    assert v2_credential.json()["data"]["stored"] is True

    draft_v3 = client.post(
        "/api/alphaguard/models/endpoints",
        json={
            **endpoint_payload,
            "display_name": "Isolated Compatible v4",
            "endpoint_profile_id": endpoint_id,
            "create_new_version": True,
        },
    )
    assert draft_v3.status_code == 200
    assert draft_v3.json()["data"]["item"]["profile_version"] == "v3"
    validated_v4 = client.post(
        f"/api/alphaguard/models/endpoints/{endpoint_id}/validate",
        json={"profile_version": "v3", "confirm_data_transmission": True},
    )
    assert validated_v4.status_code == 200
    assert validated_v4.json()["data"]["profile_version"] == "v4"

    secret_count = len(store.values)
    collision = client.post(
        "/api/alphaguard/models/credentials",
        json={
            "provider": "openai_compatible",
            "provider_type": "OPENAI_COMPATIBLE",
            "endpoint_profile_id": endpoint_id,
            "endpoint_profile_version": "v4",
            "credential_name": v2_credential_id,
            "api_key": TEST_SECRET,
        },
    )
    assert collision.status_code == 409
    assert collision.json()["detail"]["error_code"] == (
        "CREDENTIAL_BINDING_EXISTS"
    )
    assert db["ag_model_credentials"].count() == 1
    assert len(store.values) == secret_count
    assert TEST_SECRET not in collision.text

    v4_credential_id = f"{endpoint_id}-v4-primary"
    v4_credential = client.post(
        "/api/alphaguard/models/credentials",
        json={
            "provider": "openai_compatible",
            "provider_type": "OPENAI_COMPATIBLE",
            "endpoint_profile_id": endpoint_id,
            "endpoint_profile_version": "v4",
            "credential_name": v4_credential_id,
            "api_key": TEST_SECRET,
        },
    )
    assert v4_credential.status_code == 200
    assert v4_credential.json()["data"]["status"] == "DEGRADED"

    model_results = {}
    for role, remote_name in (
        ("NORMAL_TRADER", "isolated-normal"),
        ("TOP_RISK_REVIEWER", "isolated-top"),
    ):
        response = client.post(
            f"/api/alphaguard/models/endpoints/{endpoint_id}/models",
            json={
                "endpoint_profile_version": "v4",
                "remote_model_name": remote_name,
                "display_name": remote_name,
                "role_capabilities": [role],
                "supports_json_schema": False,
                "supports_tool_call": False,
                "max_context_tokens": 64000,
                "max_output_tokens": 4000,
            },
        )
        assert response.status_code == 200
        item = response.json()["data"]["item"]
        assert item["status"] == "UNVERIFIED"
        model_results[role] = item

    price_results = {}
    for role, item in model_results.items():
        response = client.post(
            "/api/alphaguard/models/prices",
            json={
                "endpoint_profile_id": endpoint_id,
                "endpoint_profile_version": "v4",
                "endpoint_model_id": item["endpoint_model_id"],
                "endpoint_model_version": item["model_version"],
                "input_price_per_million": "1.25",
                "output_price_per_million": "5.00",
                "currency": "USD",
                "effective_at": "2026-07-30T00:00:00Z",
                "source_description": "isolated verified pricing",
                "verified": True,
            },
        )
        assert response.status_code == 200
        price_results[role] = response.json()["data"]["item"]

    profile_results = {}
    for role in ("NORMAL_TRADER", "TOP_RISK_REVIEWER"):
        response = client.post(
            "/api/alphaguard/models/profiles/compatible",
            json={
                "role": role,
                "profile_id": f"isolated-{role.lower()}",
                "profile_version": "v4",
                "endpoint_profile_id": endpoint_id,
                "endpoint_profile_version": "v4",
                "endpoint_model_id": model_results[role]["endpoint_model_id"],
                "endpoint_model_version": model_results[role]["model_version"],
                "credential_id": v4_credential_id,
                "price_version_id": price_results[role]["price_version_id"],
                "price_version": price_results[role]["price_version"],
                "prompt_profile_id": (
                    "normal_trade_plan_prompt"
                    if role == "NORMAL_TRADER"
                    else "top_risk_review_prompt"
                ),
                "explicit_same_model_confirmation": False,
            },
        )
        assert response.status_code == 200
        profile = response.json()["data"]["profile"]
        assert profile["capability_status"] == "UNVERIFIED"
        assert profile["production_allowed"] is False
        profile_results[role] = profile

    before_capability = client.get(
        f"/api/alphaguard/models/endpoints/{endpoint_id}/configuration-status",
        params={"profile_version": "v4"},
    )
    assert before_capability.status_code == 200
    assert before_capability.json()["data"]["stage"] == (
        "PROFILES_CONFIGURED"
    )
    assert before_capability.json()["data"]["production_allowed"] is False

    for profile in profile_results.values():
        asyncio.run(
            db["ag_model_capability_checks"].insert_one(
                {
                    "profile_id": profile["profile_id"],
                    "profile_version": profile["profile_version"],
                    "status": "READY",
                    "checked_at": datetime.now(timezone.utc),
                }
            )
        )
    refreshed = client.get(
        f"/api/alphaguard/models/endpoints/{endpoint_id}/configuration-status",
        params={"profile_version": "v4"},
    )
    assert refreshed.status_code == 200
    assert refreshed.json()["data"]["stage"] == "READY"
    assert refreshed.json()["data"]["production_allowed"] is True
    assert not refreshed.json()["data"]["blocking_items"]
    assert db["ag_model_endpoint_prices"].count() == 2
    assert db["ag_model_profiles"].count() == 2
    assert db["ag_model_profile_assignments"].count() == 2
    assert TEST_SECRET not in repr(db.collections)


def test_registry_indexes_and_frontend_browser_isolation_contract():
    required = {
        "ag_model_provider_endpoints",
        "ag_model_endpoint_models",
        "ag_model_endpoint_prices",
        "ag_model_profile_assignments",
        "ag_model_endpoint_events",
    }
    assert required <= set(ALPHAGUARD_INDEX_SPECS)
    operations = (
        ROOT / "frontend/src/views/AlphaGuard/Operations.vue"
    ).read_text(encoding="utf-8")
    api = (ROOT / "frontend/src/api/alphaguardModels.ts").read_text(
        encoding="utf-8"
    )
    assert "服务商" in operations
    assert "模型目录" in operations
    assert "价格" in operations
    assert "我确认将研究数据发送到该第三方服务" in operations
    assert 'type="password"' in operations
    assert "credentialApiKey.value = ''" in operations
    assert "localStorage.setItem" not in operations
    assert "sessionStorage.setItem" not in operations
    assert "models.example" not in api
    assert "/api/alphaguard/models/endpoints" in api


@pytest.mark.asyncio
async def test_unconvertible_price_currency_blocks_budget():
    db = FakeDB()
    profile = ModelProfileRegistry().for_role("NORMAL_TRADER").model_copy(
        update={
            "input_cost_per_million": 1.0,
            "output_cost_per_million": 2.0,
            "cost_currency": "CNY",
        }
    )
    decision = await ModelBudgetService(db).check(
        profile=profile,
        analysis_id="currency-check",
        snapshot_id=None,
        rendered_input="fixed capability payload",
    )
    assert decision.allowed is False
    assert decision.reason_code == "BUDGET_CURRENCY_MISMATCH"
