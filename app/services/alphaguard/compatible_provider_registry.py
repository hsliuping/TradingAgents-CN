"""Create-only registry for administrator-approved model provider bindings."""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from typing import Any
from uuid import NAMESPACE_URL, uuid4, uuid5

from app.schemas.alphaguard.decision import canonical_hash
from app.schemas.alphaguard.model_runtime import (
    EndpointModelDefinition,
    EndpointPriceVersion,
    EndpointValidationEvent,
    ModelProfile,
    ModelProfileAssignment,
    ProviderEndpointProfile,
)

from .model_endpoint_security import (
    EndpointSafetyValidator,
    EndpointSecurityError,
    build_pinned_client,
    parse_registered_endpoint,
)
from .model_credential_service import ModelCredentialService
from .model_budget_service import ModelBudgetService
from .model_profile_registry import ModelProfileRegistry
from .model_runtime_repository import (
    ModelRuntimeIntegrityConflict,
    ModelRuntimeRepository,
)
from .model_runtime_status_service import project_capability_check
from .model_secret_store import (
    KEYCHAIN_ALIAS_SERVICE,
    SecretNotFound,
    SecretStoreError,
)
from .prompt_profile_registry import PromptProfileRegistry
from .paper_storage import clean_document


OFFICIAL_OPENAI_ENDPOINT = {
    "endpoint_profile_id": "openai-official",
    "profile_version": "v1",
    "provider_type": "OPENAI_OFFICIAL",
    "display_name": "OpenAI Official",
    "base_url": "https://api.openai.com/v1",
    "normalized_origin": "https://api.openai.com",
    "api_mode": "OPENAI_RESPONSES",
    "auth_scheme": "BEARER",
    "models_endpoint_enabled": True,
    "structured_output_mode": "NATIVE_JSON_SCHEMA",
    "state": "READY",
    "enabled": True,
    "validation_allowed": True,
    "production_allowed": True,
    "url_validation_status": "PASS",
    "data_transmission_confirmed": True,
    "system_managed": True,
}


class ProviderRegistryConflict(RuntimeError):
    pass


class ProviderRegistryNotReady(RuntimeError):
    pass


def _hashable(value: Any) -> Any:
    if isinstance(value, Decimal):
        return format(value.normalize(), "f")
    if isinstance(value, dict):
        return {key: _hashable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_hashable(item) for item in value]
    return value


def _content_hash(value: dict[str, Any], hash_field: str) -> str:
    return canonical_hash(
        _hashable(value), exclude={hash_field, "created_at", "assigned_at"}
    )


def _next_version(rows: list[dict[str, Any]], field: str) -> str:
    values = []
    for row in rows:
        raw = str(row.get(field) or "")
        if raw.startswith("v") and raw[1:].isdigit():
            values.append(int(raw[1:]))
    return f"v{max(values, default=0) + 1}"


def _as_utc(value: datetime) -> datetime:
    """Treat MongoDB's UTC-naive datetimes as UTC for safe comparisons."""

    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _endpoint_config_signature(value: dict[str, Any]) -> tuple[Any, ...]:
    return tuple(
        value.get(field)
        for field in (
            "endpoint_profile_id",
            "provider_type",
            "display_name",
            "base_url",
            "normalized_origin",
            "api_mode",
            "auth_scheme",
            "models_endpoint_enabled",
            "structured_output_mode",
            "notes",
        )
    )


class CompatibleProviderRegistryService:
    def __init__(self, db, *, safety_validator=None, secret_store=None):
        self.db = db
        self.repository = ModelRuntimeRepository(db)
        self.safety = safety_validator or EndpointSafetyValidator()
        self.secret_store = secret_store

    async def _event(
        self,
        *,
        endpoint_profile_id: str,
        endpoint_profile_version: str,
        action: str,
        status: str,
        error_code: str | None,
        operator_user_id: str,
        trace_id: str,
    ) -> EndpointValidationEvent:
        payload = {
            "validation_event_id": str(uuid4()),
            "endpoint_profile_id": endpoint_profile_id,
            "endpoint_profile_version": endpoint_profile_version,
            "action": action,
            "status": status,
            "error_code": error_code,
            "operator_user_id": operator_user_id,
            "trace_id": trace_id,
            "created_at": datetime.now(timezone.utc),
        }
        payload["event_hash"] = _content_hash(payload, "event_hash")
        event = EndpointValidationEvent.model_validate(payload)
        await self.repository.save_immutable(
            "endpoint_events",
            event,
            identity={"validation_event_id": event.validation_event_id},
            hash_field="event_hash",
        )
        return event

    async def register_endpoint(
        self,
        *,
        display_name: str,
        base_url: str,
        api_mode: str,
        auth_scheme: str,
        models_endpoint_enabled: bool,
        structured_output_mode: str,
        notes: str | None,
        created_by: str,
        endpoint_profile_id: str | None = None,
        profile_version: str = "v1",
        create_new_version: bool = False,
    ) -> tuple[ProviderEndpointProfile, bool]:
        parsed = parse_registered_endpoint(base_url)
        if parsed.normalized_origin == "https://api.openai.com":
            raise ValueError(
                "official OpenAI uses its system-managed endpoint profile"
            )
        endpoint_id = endpoint_profile_id or (
            f"compatible-{canonical_hash({'origin': parsed.normalized_origin})[:20]}"
        )
        resolved_profile_version = profile_version
        if create_new_version:
            if not endpoint_profile_id:
                raise ValueError(
                    "endpoint_profile_id is required for a new endpoint version"
                )
            rows = await self.repository.list(
                "endpoints", {"endpoint_profile_id": endpoint_profile_id}
            )
            if not rows:
                raise ProviderRegistryNotReady(
                    "endpoint profile is not registered"
                )
            if any(
                row.get("normalized_origin") != parsed.normalized_origin
                for row in rows
            ):
                raise ValueError(
                    "an endpoint version cannot change normalized origin"
                )
            resolved_profile_version = _next_version(
                rows, "profile_version"
            )
        payload = {
            "endpoint_profile_id": endpoint_id,
            "profile_version": resolved_profile_version,
            "provider_type": "OPENAI_COMPATIBLE",
            "display_name": display_name,
            "base_url": parsed.base_url,
            "normalized_origin": parsed.normalized_origin,
            "api_mode": api_mode,
            "auth_scheme": auth_scheme,
            "models_endpoint_enabled": models_endpoint_enabled,
            "structured_output_mode": structured_output_mode,
            "state": "DRAFT",
            "enabled": True,
            "validation_allowed": True,
            "production_allowed": False,
            "resolved_ips": [],
            "url_validation_status": "NOT_CHECKED",
            "last_error_code": None,
            "notes": notes,
            "data_transmission_confirmed": False,
            "created_by": created_by,
            "created_at": datetime.now(timezone.utc),
        }
        payload["config_hash"] = _content_hash(payload, "config_hash")
        endpoint = ProviderEndpointProfile.model_validate(payload)
        try:
            saved, created = await self.repository.save_immutable(
                "endpoints",
                endpoint,
                identity={
                    "endpoint_profile_id": endpoint.endpoint_profile_id,
                    "profile_version": endpoint.profile_version,
                },
                hash_field="config_hash",
            )
        except ModelRuntimeIntegrityConflict as exc:
            raise ProviderRegistryConflict(str(exc)) from exc
        return saved, created

    async def endpoint(
        self, endpoint_profile_id: str, profile_version: str
    ) -> ProviderEndpointProfile:
        raw = await self.repository.get(
            "endpoints",
            {
                "endpoint_profile_id": endpoint_profile_id,
                "profile_version": profile_version,
            },
        )
        if raw is None:
            raise ProviderRegistryNotReady("endpoint profile is not registered")
        return ProviderEndpointProfile.model_validate(raw)

    async def latest_endpoint(
        self, endpoint_profile_id: str
    ) -> ProviderEndpointProfile:
        rows = await self.repository.list(
            "endpoints", {"endpoint_profile_id": endpoint_profile_id}
        )
        if not rows:
            raise ProviderRegistryNotReady("endpoint profile is not registered")
        rows.sort(key=lambda item: int(str(item["profile_version"])[1:]))
        return ProviderEndpointProfile.model_validate(rows[-1])

    @staticmethod
    def _endpoint_version_number(row: dict[str, Any]) -> int:
        return int(str(row["profile_version"])[1:])

    @classmethod
    def _lineage_disabled_in_rows(
        cls, rows: list[dict[str, Any]]
    ) -> bool:
        disabled_versions = [
            cls._endpoint_version_number(row)
            for row in rows
            if row.get("state") == "DISABLED"
        ]
        active_versions = [
            cls._endpoint_version_number(row)
            for row in rows
            if bool(row.get("enabled"))
            and row.get("url_validation_status") == "PASS"
            and bool(row.get("data_transmission_confirmed"))
            and row.get("state")
            in {"URL_VALIDATED", "CAPABILITY_CHECKED", "READY"}
        ]
        return bool(disabled_versions) and max(disabled_versions) > max(
            active_versions, default=0
        )

    async def _endpoint_version_is_disabled(
        self, endpoint: ProviderEndpointProfile
    ) -> bool:
        rows = await self.repository.list(
            "endpoints",
            {"endpoint_profile_id": endpoint.endpoint_profile_id},
        )
        return self._endpoint_version_is_disabled_in_rows(
            rows,
            endpoint.profile_version,
        )

    @classmethod
    def _endpoint_version_is_disabled_in_rows(
        cls,
        rows: list[dict[str, Any]],
        profile_version: str,
    ) -> bool:
        disabled_versions = [
            cls._endpoint_version_number(row)
            for row in rows
            if row.get("state") == "DISABLED"
        ]
        requested_version = int(profile_version.removeprefix("v"))
        return bool(disabled_versions) and requested_version <= max(
            disabled_versions
        )

    async def _require_active_lineage(
        self, endpoint: ProviderEndpointProfile
    ) -> None:
        if await self._endpoint_version_is_disabled(endpoint):
            raise ProviderRegistryNotReady("endpoint lineage is disabled")

    async def list_endpoints(self) -> list[dict[str, Any]]:
        rows = await self.repository.list("endpoints", sort=("created_at", -1))
        versions: dict[str, list[dict[str, Any]]] = {}
        for row in rows:
            versions.setdefault(str(row["endpoint_profile_id"]), []).append(row)
        projections = []
        for endpoint_rows in versions.values():
            endpoint_rows.sort(
                key=self._endpoint_version_number,
                reverse=True,
            )
            latest_row = endpoint_rows[0]
            # A newer immutable draft must not displace the last validated,
            # enabled version used by the guided configuration flow. Drafts
            # remain persisted and directly addressable by their version.
            lineage_disabled = self._lineage_disabled_in_rows(endpoint_rows)
            row = (
                next(
                    item
                    for item in endpoint_rows
                    if item.get("state") == "DISABLED"
                )
                if lineage_disabled
                else next(
                    (
                        item
                        for item in endpoint_rows
                        if bool(item.get("enabled"))
                        and item.get("url_validation_status") == "PASS"
                        and bool(item.get("data_transmission_confirmed"))
                        and item.get("state")
                        in {"URL_VALIDATED", "CAPABILITY_CHECKED", "READY"}
                    ),
                    latest_row,
                )
            )
            projection = dict(row)
            status = await self.configuration_status(
                str(row["endpoint_profile_id"]),
                str(row["profile_version"]),
            )
            # Endpoint documents are immutable facts. Configuration progress
            # is a read-only projection and must never rewrite the persisted
            # URL_VALIDATED state merely because later objects are incomplete.
            projection["configuration_stage"] = status["stage"]
            projection["production_allowed"] = status["production_allowed"]
            projection["latest_profile_version"] = str(
                latest_row["profile_version"]
            )
            projection["has_newer_draft"] = (
                latest_row["profile_version"] != row["profile_version"]
            )
            projections.append(projection)
        return [OFFICIAL_OPENAI_ENDPOINT, *projections]

    async def configuration_status(
        self,
        endpoint_profile_id: str,
        endpoint_profile_version: str,
    ) -> dict[str, Any]:
        """Return a secret-free, read-only configuration completeness view."""

        endpoint = await self.endpoint(
            endpoint_profile_id, endpoint_profile_version
        )
        endpoint_version_disabled = await self._endpoint_version_is_disabled(
            endpoint
        )
        roles = ("NORMAL_TRADER", "TOP_RISK_REVIEWER")
        endpoint_ready = bool(
            not endpoint_version_disabled
            and endpoint.enabled
            and endpoint.url_validation_status == "PASS"
            and endpoint.data_transmission_confirmed
            and endpoint.state
            in {"URL_VALIDATED", "CAPABILITY_CHECKED", "READY"}
        )
        credential_rows = await self.db["ag_model_credentials"].find(
            {
                "provider_type": "OPENAI_COMPATIBLE",
                "endpoint_profile_id": endpoint_profile_id,
                "endpoint_profile_version": endpoint_profile_version,
                "normalized_origin": endpoint.normalized_origin,
                "auth_scheme": endpoint.auth_scheme,
                "status": {"$ne": "REVOKED"},
            }
        ).sort([("updated_at", -1), ("_id", -1)]).limit(2).to_list(length=2)
        # Multiple active bindings for one endpoint identity are an integrity
        # conflict; never select one according to incidental insertion order.
        credential = credential_rows[0] if len(credential_rows) == 1 else None
        credential_ready = self._credential_secret_configured(credential)

        model_rows = await self.repository.list(
            "endpoint_models",
            {
                "endpoint_profile_id": endpoint_profile_id,
                "endpoint_profile_version": endpoint_profile_version,
            },
            sort=("created_at", -1),
        )
        role_models: dict[str, list[dict[str, Any]]] = {
            role: [
                model
                for model in model_rows
                if role in model.get("role_capabilities", [])
                and model.get("status") not in {"DISABLED", "NOT_FOUND", "UNSUPPORTED"}
            ]
            for role in roles
        }

        price_rows = await self.repository.list(
            "endpoint_prices",
            {
                "endpoint_profile_id": endpoint_profile_id,
                "endpoint_profile_version": endpoint_profile_version,
            },
            sort=("created_at", -1),
        )
        now = datetime.now(timezone.utc)
        role_prices: dict[str, list[dict[str, Any]]] = {}
        for role in roles:
            model_ids = {
                (model["endpoint_model_id"], model["model_version"])
                for model in role_models[role]
            }
            role_prices[role] = [
                price
                for price in price_rows
                if (
                    price.get("endpoint_model_id"),
                    price.get("endpoint_model_version"),
                )
                in model_ids
                and bool(price.get("verified"))
                and _as_utc(price["effective_at"]) <= now
            ]

        assignments = await self.repository.list(
            "profile_assignments", {}, sort=("assigned_at", -1)
        )
        selected_assignments: dict[str, dict[str, Any]] = {}
        for assignment in assignments:
            selected_assignments.setdefault(str(assignment["role"]), assignment)
        role_profiles: dict[str, dict[str, Any] | None] = {}
        role_checks: dict[str, dict[str, Any] | None] = {}
        role_check_stale: dict[str, bool] = {}
        for role in roles:
            assignment = selected_assignments.get(role)
            profile = None
            if assignment:
                candidate = await self.db["ag_model_profiles"].find_one(
                    {
                        "profile_id": assignment["profile_id"],
                        "profile_version": assignment["profile_version"],
                        "role": role,
                        "endpoint_profile_id": endpoint_profile_id,
                        "endpoint_profile_version": endpoint_profile_version,
                    },
                    {"_id": 0},
                )
                if candidate:
                    profile = clean_document(candidate)
            role_profiles[role] = profile
            latest_check = (
                await self.db["ag_model_capability_checks"].find_one(
                    {
                        "profile_id": profile["profile_id"],
                        "profile_version": profile["profile_version"],
                    },
                    {"_id": 0, "request_hash": 0, "response_hash": 0},
                    sort=[("checked_at", -1)],
                )
                if profile
                else None
            )
            bound_credential = (
                credential
                if profile
                and credential
                and profile.get("credential_id")
                == credential.get("credential_id")
                else None
            )
            role_checks[role], role_check_stale[role] = (
                project_capability_check(latest_check, bound_credential)
            )

        resolved_role_prices: dict[str, dict[str, Any] | None] = {}
        for role in roles:
            profile = role_profiles[role]
            resolved_role_prices[role] = (
                next(
                    (
                        price
                        for price in role_prices[role]
                        if price.get("price_version_id")
                        == profile.get("price_version_id")
                    ),
                    None,
                )
                if profile
                else role_prices[role][0]
                if role_prices[role]
                else None
            )

        models_ready = all(role_models[role] for role in roles)
        prices_ready = all(resolved_role_prices[role] for role in roles)
        profiles_ready = all(role_profiles[role] for role in roles)
        assignments_ready = all(
            selected_assignments.get(role) and role_profiles[role]
            for role in roles
        )
        capability_checked = all(
            role_checks[role] and not role_check_stale[role]
            for role in roles
        )
        capability_ready = all(
            role_checks[role] and role_checks[role].get("status") == "READY"
            for role in roles
        )
        selected_prices = [
            resolved_role_prices[role]
            for role in roles
            if resolved_role_prices[role]
        ]
        if len(selected_prices) != len(roles):
            budget_status = "BUDGET_BLOCKED"
            budget_reason = "BUDGET_PRICING_UNAVAILABLE"
        elif any(
            price.get("currency") != ModelBudgetService(self.db).policy.currency
            for price in selected_prices
        ):
            budget_status = "BUDGET_BLOCKED"
            budget_reason = "BUDGET_CURRENCY_MISMATCH"
        else:
            budget_status = "READY"
            budget_reason = None

        if not endpoint_ready:
            stage = "DRAFT"
        elif not credential_ready:
            stage = "URL_VALIDATED"
        elif not models_ready:
            stage = "AUTHENTICATED"
        elif not prices_ready:
            stage = "MODELS_REGISTERED"
        elif not profiles_ready or not assignments_ready:
            stage = "PRICES_CONFIGURED"
        elif not capability_checked:
            stage = "PROFILES_CONFIGURED"
        elif not capability_ready or budget_status != "READY":
            stage = "CAPABILITY_CHECKED"
        else:
            stage = "READY"

        component_values = {
            "endpoint": endpoint_ready,
            "credential": credential_ready,
            "normal_model": bool(role_models["NORMAL_TRADER"]),
            "top_model": bool(role_models["TOP_RISK_REVIEWER"]),
            "normal_price": bool(resolved_role_prices["NORMAL_TRADER"]),
            "top_price": bool(resolved_role_prices["TOP_RISK_REVIEWER"]),
            "normal_profile": bool(role_profiles["NORMAL_TRADER"]),
            "top_profile": bool(role_profiles["TOP_RISK_REVIEWER"]),
            "assignments": bool(assignments_ready),
            "capability": bool(capability_ready),
            "budget": budget_status == "READY",
        }
        labels = {
            "endpoint": "Endpoint",
            "credential": "Credential",
            "normal_model": "Normal Model",
            "top_model": "Top Model",
            "normal_price": "Normal Price",
            "top_price": "Top Price",
            "normal_profile": "Normal Profile",
            "top_profile": "Top Profile",
            "assignments": "Assignments",
            "capability": "Capability",
            "budget": "Budget",
        }
        component_statuses = {
            "endpoint": endpoint.state if endpoint_ready else "MISSING",
            "credential": (
                str(credential.get("status")) if credential_ready else "MISSING"
            ),
            "normal_model": (
                "READY"
                if role_checks["NORMAL_TRADER"]
                and role_checks["NORMAL_TRADER"].get("status") == "READY"
                else str(role_models["NORMAL_TRADER"][0].get("status"))
                if role_models["NORMAL_TRADER"]
                else "MISSING"
            ),
            "top_model": (
                "READY"
                if role_checks["TOP_RISK_REVIEWER"]
                and role_checks["TOP_RISK_REVIEWER"].get("status") == "READY"
                else str(role_models["TOP_RISK_REVIEWER"][0].get("status"))
                if role_models["TOP_RISK_REVIEWER"]
                else "MISSING"
            ),
            "normal_price": (
                "SELF_HOSTED_ZERO"
                if resolved_role_prices["NORMAL_TRADER"]
                and resolved_role_prices["NORMAL_TRADER"].get("pricing_source")
                == "SELF_HOSTED"
                else "VERIFIED"
                if resolved_role_prices["NORMAL_TRADER"]
                else "MISSING"
            ),
            "top_price": (
                "SELF_HOSTED_ZERO"
                if resolved_role_prices["TOP_RISK_REVIEWER"]
                and resolved_role_prices["TOP_RISK_REVIEWER"].get("pricing_source")
                == "SELF_HOSTED"
                else "VERIFIED"
                if resolved_role_prices["TOP_RISK_REVIEWER"]
                else "MISSING"
            ),
            "normal_profile": (
                str(role_checks["NORMAL_TRADER"].get("status"))
                if role_checks["NORMAL_TRADER"]
                else "UNVERIFIED"
                if role_profiles["NORMAL_TRADER"]
                else "MISSING"
            ),
            "top_profile": (
                str(role_checks["TOP_RISK_REVIEWER"].get("status"))
                if role_checks["TOP_RISK_REVIEWER"]
                else "UNVERIFIED"
                if role_profiles["TOP_RISK_REVIEWER"]
                else "MISSING"
            ),
            "assignments": "ACTIVE" if assignments_ready else "MISSING",
            "capability": "READY" if capability_ready else "MISSING",
            "budget": budget_status,
        }
        component_reasons = {
            "normal_profile": (
                "CREDENTIAL_REVERIFIED"
                if role_check_stale["NORMAL_TRADER"]
                else None
            ),
            "top_profile": (
                "CREDENTIAL_REVERIFIED"
                if role_check_stale["TOP_RISK_REVIEWER"]
                else None
            ),
            "capability": (
                "CREDENTIAL_REVERIFIED"
                if any(role_check_stale.values())
                else None
            ),
            "budget": budget_reason,
        }
        components = [
            {
                "key": key,
                "label": labels[key],
                "complete": complete,
                "status": component_statuses[key],
                "reason_code": component_reasons.get(key),
            }
            for key, complete in component_values.items()
        ]
        return {
            "endpoint_profile_id": endpoint_profile_id,
            "endpoint_profile_version": endpoint_profile_version,
            "persisted_endpoint_state": endpoint.state,
            "stage": stage,
            "production_allowed": stage == "READY",
            "components": components,
            "blocking_items": [
                item["key"] for item in components if not item["complete"]
            ],
            "budget_policy_id": ModelBudgetService(self.db).policy.policy_id,
            "budget_policy_version": ModelBudgetService(self.db).policy.policy_version,
            "budget_currency": ModelBudgetService(self.db).policy.currency,
        }

    async def validate_endpoint(
        self,
        *,
        endpoint_profile_id: str,
        profile_version: str,
        confirm_data_transmission: bool,
        operator_user_id: str,
        trace_id: str,
    ) -> ProviderEndpointProfile:
        endpoint = await self.endpoint(endpoint_profile_id, profile_version)
        await self._require_active_lineage(endpoint)
        rows = await self.repository.list(
            "endpoints", {"endpoint_profile_id": endpoint_profile_id}
        )
        reusable = next(
            (
                ProviderEndpointProfile.model_validate(row)
                for row in rows
                if row.get("url_validation_status") == "PASS"
                and not self._endpoint_version_is_disabled_in_rows(
                    rows, str(row["profile_version"])
                )
                and _endpoint_config_signature(row)
                == _endpoint_config_signature(endpoint.model_dump(mode="python"))
                and bool(row.get("data_transmission_confirmed"))
                == confirm_data_transmission
                and row.get("state")
                in {"URL_VALIDATED", "CAPABILITY_CHECKED", "READY"}
            ),
            None,
        )
        if reusable is not None:
            return reusable
        next_version = _next_version(rows, "profile_version")
        now = datetime.now(timezone.utc)
        try:
            result = await self.safety.validate(endpoint.base_url)
            patch = {
                "profile_version": next_version,
                "state": "URL_VALIDATED",
                "resolved_ips": list(result.resolved_ips),
                "url_validation_status": "PASS",
                "last_error_code": None,
                "data_transmission_confirmed": confirm_data_transmission,
                "data_transmission_confirmed_by": (
                    operator_user_id if confirm_data_transmission else None
                ),
                "data_transmission_confirmed_at": (
                    now if confirm_data_transmission else None
                ),
                "created_by": operator_user_id,
                "created_at": now,
                "config_hash": "0" * 64,
            }
            payload = endpoint.model_copy(update=patch).model_dump(mode="python")
            payload["config_hash"] = _content_hash(payload, "config_hash")
            validated = ProviderEndpointProfile.model_validate(payload)
            saved, _ = await self.repository.save_immutable(
                "endpoints",
                validated,
                identity={
                    "endpoint_profile_id": endpoint_profile_id,
                    "profile_version": next_version,
                },
                hash_field="config_hash",
            )
            await self._event(
                endpoint_profile_id=endpoint_profile_id,
                endpoint_profile_version=next_version,
                action="URL_VALIDATION",
                status="PASS",
                error_code=None,
                operator_user_id=operator_user_id,
                trace_id=trace_id,
            )
            return saved
        except EndpointSecurityError as exc:
            patch = {
                "profile_version": next_version,
                "state": "REJECTED",
                "enabled": False,
                "validation_allowed": False,
                "resolved_ips": [],
                "url_validation_status": "REJECTED",
                "last_error_code": exc.code,
                "created_by": operator_user_id,
                "created_at": now,
                "config_hash": "0" * 64,
            }
            payload = endpoint.model_copy(update=patch).model_dump(mode="python")
            payload["config_hash"] = _content_hash(payload, "config_hash")
            rejected = ProviderEndpointProfile.model_validate(payload)
            saved, _ = await self.repository.save_immutable(
                "endpoints",
                rejected,
                identity={
                    "endpoint_profile_id": endpoint_profile_id,
                    "profile_version": next_version,
                },
                hash_field="config_hash",
            )
            await self._event(
                endpoint_profile_id=endpoint_profile_id,
                endpoint_profile_version=next_version,
                action="URL_VALIDATION",
                status="REJECTED",
                error_code=exc.code,
                operator_user_id=operator_user_id,
                trace_id=trace_id,
            )
            return saved

    async def disable_endpoint(
        self,
        *,
        endpoint_profile_id: str,
        profile_version: str,
        operator_user_id: str,
        trace_id: str,
    ) -> ProviderEndpointProfile:
        endpoint = await self.endpoint(endpoint_profile_id, profile_version)
        rows = await self.repository.list(
            "endpoints", {"endpoint_profile_id": endpoint_profile_id}
        )
        if await self._endpoint_version_is_disabled(endpoint):
            disabled_rows = [
                row for row in rows if row.get("state") == "DISABLED"
            ]
            disabled_rows.sort(key=self._endpoint_version_number)
            return ProviderEndpointProfile.model_validate(disabled_rows[-1])
        next_version = _next_version(rows, "profile_version")
        payload = endpoint.model_copy(
            update={
                "profile_version": next_version,
                "state": "DISABLED",
                "enabled": False,
                "validation_allowed": False,
                "production_allowed": False,
                "created_by": operator_user_id,
                "created_at": datetime.now(timezone.utc),
                "config_hash": "0" * 64,
            }
        ).model_dump(mode="python")
        payload["config_hash"] = _content_hash(payload, "config_hash")
        disabled = ProviderEndpointProfile.model_validate(payload)
        saved, _ = await self.repository.save_immutable(
            "endpoints",
            disabled,
            identity={
                "endpoint_profile_id": endpoint_profile_id,
                "profile_version": next_version,
            },
            hash_field="config_hash",
        )
        await self._event(
            endpoint_profile_id=endpoint_profile_id,
            endpoint_profile_version=next_version,
            action="ENDPOINT_DISABLED",
            status="SUCCESS",
            error_code=None,
            operator_user_id=operator_user_id,
            trace_id=trace_id,
        )
        return saved

    async def register_model(
        self,
        *,
        endpoint_profile_id: str,
        endpoint_profile_version: str,
        remote_model_name: str,
        display_name: str,
        role_capabilities: list[str],
        supports_json_schema: bool,
        supports_tool_call: bool,
        supports_reasoning: bool | None,
        max_context_tokens: int | None,
        max_output_tokens: int | None,
        created_by: str,
        model_version: str = "v1",
        endpoint_model_id: str | None = None,
        discovery_mode: str = "MANUAL",
        status: str = "READY",
    ) -> tuple[EndpointModelDefinition, bool]:
        endpoint = await self.endpoint(
            endpoint_profile_id, endpoint_profile_version
        )
        await self._require_active_lineage(endpoint)
        if endpoint.state not in {"URL_VALIDATED", "CAPABILITY_CHECKED", "READY"}:
            raise ProviderRegistryNotReady("endpoint URL is not validated")
        identity_seed = canonical_hash(
            {
                "endpoint_profile_id": endpoint_profile_id,
                "endpoint_profile_version": endpoint_profile_version,
                "remote_model_name": remote_model_name,
            }
        )[:20]
        payload = {
            "endpoint_model_id": endpoint_model_id or f"endpoint-model-{identity_seed}",
            "model_version": model_version,
            "endpoint_profile_id": endpoint_profile_id,
            "endpoint_profile_version": endpoint_profile_version,
            "remote_model_name": remote_model_name,
            "display_name": display_name,
            "role_capabilities": role_capabilities,
            "supports_json_schema": supports_json_schema,
            "supports_tool_call": supports_tool_call,
            "supports_reasoning": supports_reasoning,
            "max_context_tokens": max_context_tokens,
            "max_output_tokens": max_output_tokens,
            "discovery_mode": discovery_mode,
            "status": status,
            "created_by": created_by,
            "created_at": datetime.now(timezone.utc),
        }
        payload["content_hash"] = _content_hash(payload, "content_hash")
        model = EndpointModelDefinition.model_validate(payload)
        try:
            return await self.repository.save_immutable(
                "endpoint_models",
                model,
                identity={
                    "endpoint_model_id": model.endpoint_model_id,
                    "model_version": model.model_version,
                },
                hash_field="content_hash",
            )
        except ModelRuntimeIntegrityConflict as exc:
            raise ProviderRegistryConflict(str(exc)) from exc

    async def list_models(
        self, endpoint_profile_id: str, endpoint_profile_version: str | None = None
    ) -> list[dict[str, Any]]:
        query: dict[str, Any] = {"endpoint_profile_id": endpoint_profile_id}
        if endpoint_profile_version:
            query["endpoint_profile_version"] = endpoint_profile_version
        return await self.repository.list(
            "endpoint_models", query, sort=("created_at", -1)
        )

    async def discover_models(
        self,
        *,
        endpoint_profile_id: str,
        endpoint_profile_version: str,
        credential_id: str | None,
        operator_user_id: str,
        trace_id: str,
    ) -> list[EndpointModelDefinition]:
        names = await self.model_options(
            endpoint_profile_id=endpoint_profile_id,
            endpoint_profile_version=endpoint_profile_version,
            credential_id=credential_id,
        )
        results = []
        for name in names:
            model, _ = await self.register_model(
                endpoint_profile_id=endpoint_profile_id,
                endpoint_profile_version=endpoint_profile_version,
                remote_model_name=name,
                display_name=name,
                role_capabilities=[],
                supports_json_schema=False,
                supports_tool_call=False,
                supports_reasoning=None,
                max_context_tokens=None,
                max_output_tokens=None,
                created_by=operator_user_id,
                discovery_mode="MODELS_ENDPOINT",
                status="UNVERIFIED",
            )
            results.append(model)
        await self._event(
            endpoint_profile_id=endpoint_profile_id,
            endpoint_profile_version=endpoint_profile_version,
            action="MODEL_DISCOVERY",
            status="SUCCESS" if names else "EMPTY",
            error_code=None if names else "MODELS_EMPTY",
            operator_user_id=operator_user_id,
            trace_id=trace_id,
        )
        return results

    async def model_options(
        self,
        *,
        endpoint_profile_id: str,
        endpoint_profile_version: str,
        credential_id: str | None,
    ) -> list[str]:
        """Read the provider model catalog without creating registry objects."""
        endpoint = await self.endpoint(
            endpoint_profile_id, endpoint_profile_version
        )
        await self._require_active_lineage(endpoint)
        if not endpoint.models_endpoint_enabled:
            raise ProviderRegistryNotReady("endpoint requires manual model registration")
        credential = None
        secret = None
        if credential_id:
            credential = await self.db["ag_model_credentials"].find_one(
                {"credential_id": credential_id, "status": {"$ne": "REVOKED"}}
            )
            self._verify_credential_binding(endpoint, credential)
            secret = ModelCredentialService(self.secret_store).resolve(
                f"keychain-alias:{credential['credential_id']}"
            )
        parsed = parse_registered_endpoint(endpoint.base_url)

        def fetch() -> list[str]:
            with build_pinned_client(
                endpoint=parsed,
                resolved_ips=endpoint.resolved_ips,
                timeout_seconds=30,
                secret=secret,
                auth_scheme=endpoint.auth_scheme,
            ) as client:
                response = client.get(f"{endpoint.base_url.rstrip('/')}/models")
                if 300 <= response.status_code < 400:
                    raise EndpointSecurityError(
                        "REDIRECT_FORBIDDEN",
                        "credential-bearing model discovery cannot redirect",
                    )
                response.raise_for_status()
                payload = response.json()
                if not isinstance(payload, dict) or not isinstance(
                    payload.get("data"), list
                ):
                    raise ValueError("provider /models response is invalid")
                names = {
                    str(item["id"]).strip()
                    for item in payload["data"]
                    if isinstance(item, dict)
                    and isinstance(item.get("id"), str)
                    and 0 < len(str(item["id"]).strip()) <= 200
                }
                return sorted(names)[:1000]

        import asyncio

        try:
            return await asyncio.to_thread(fetch)
        finally:
            secret = ""

    async def register_price(
        self,
        *,
        endpoint_profile_id: str,
        endpoint_profile_version: str,
        endpoint_model_id: str,
        endpoint_model_version: str,
        input_price_per_million: Decimal,
        cached_input_price_per_million: Decimal | None,
        output_price_per_million: Decimal,
        currency: str,
        effective_at: datetime,
        source_description: str,
        verified: bool,
        created_by: str,
        pricing_source: str = "PROVIDER_PUBLISHED",
        price_version_id: str | None = None,
        price_version: str = "v1",
    ) -> tuple[EndpointPriceVersion, bool]:
        endpoint = await self.endpoint(
            endpoint_profile_id, endpoint_profile_version
        )
        await self._require_active_lineage(endpoint)
        model = await self.repository.get(
            "endpoint_models",
            {
                "endpoint_model_id": endpoint_model_id,
                "model_version": endpoint_model_version,
            },
        )
        if model is None or (
            model.get("endpoint_profile_id") != endpoint_profile_id
            or model.get("endpoint_profile_version") != endpoint_profile_version
        ):
            raise ProviderRegistryNotReady("endpoint model binding is invalid")
        price_identity = {
            "endpoint_profile_id": endpoint_profile_id,
            "endpoint_profile_version": endpoint_profile_version,
            "endpoint_model_id": endpoint_model_id,
            "endpoint_model_version": endpoint_model_version,
            "effective_at": effective_at,
            "price_version": price_version,
        }
        payload = {
            "price_version_id": price_version_id
            or f"endpoint-price-{canonical_hash(price_identity)[:20]}",
            "price_version": price_version,
            "endpoint_profile_id": endpoint_profile_id,
            "endpoint_profile_version": endpoint_profile_version,
            "endpoint_model_id": endpoint_model_id,
            "endpoint_model_version": endpoint_model_version,
            "pricing_mode": "FIXED_PER_1M",
            "pricing_source": pricing_source,
            "input_price_per_million": input_price_per_million,
            "cached_input_price_per_million": cached_input_price_per_million,
            "output_price_per_million": output_price_per_million,
            "currency": currency.upper(),
            "effective_at": effective_at,
            "source_description": source_description,
            "verified": verified,
            "created_by": created_by,
            "created_at": datetime.now(timezone.utc),
        }
        payload["content_hash"] = _content_hash(payload, "content_hash")
        price = EndpointPriceVersion.model_validate(payload)
        try:
            return await self.repository.save_immutable(
                "endpoint_prices",
                price,
                identity={"price_version_id": price.price_version_id},
                hash_field="content_hash",
            )
        except ModelRuntimeIntegrityConflict as exc:
            raise ProviderRegistryConflict(str(exc)) from exc

    async def list_prices(
        self, endpoint_profile_id: str | None = None
    ) -> list[dict[str, Any]]:
        query = (
            {"endpoint_profile_id": endpoint_profile_id}
            if endpoint_profile_id
            else {}
        )
        return await self.repository.list(
            "endpoint_prices", query, sort=("created_at", -1)
        )

    def _credential_secret_configured(
        self, credential: dict[str, Any] | None
    ) -> bool:
        if not credential or credential.get("status") not in {
            "CONFIGURED",
            "DEGRADED",
        }:
            return False
        if credential.get("lifecycle_operation_id"):
            return False
        credential_id = str(credential.get("credential_id") or "").strip()
        direct_ref = str(credential.get("credential_ref") or "").strip()
        if not credential_id or not direct_ref:
            return False
        credential_service = ModelCredentialService(self.secret_store)
        try:
            alias_target = credential_service.secret_store.read(
                service=KEYCHAIN_ALIAS_SERVICE,
                account=credential_id,
            )
        except (SecretNotFound, SecretStoreError):
            return False
        if alias_target != direct_ref:
            return False
        return credential_service.configured(
            f"keychain-alias:{credential_id}"
        )

    def _verify_credential_binding(
        self,
        endpoint: ProviderEndpointProfile,
        credential: dict[str, Any] | None,
    ) -> None:
        if not credential:
            raise ProviderRegistryNotReady("endpoint credential is not configured")
        expected = {
            "provider_type": endpoint.provider_type,
            "endpoint_profile_id": endpoint.endpoint_profile_id,
            "endpoint_profile_version": endpoint.profile_version,
            "normalized_origin": endpoint.normalized_origin,
            "auth_scheme": endpoint.auth_scheme,
        }
        if any(credential.get(key) != value for key, value in expected.items()):
            raise ProviderRegistryNotReady(
                "credential is not bound to this exact endpoint version"
            )
        if not self._credential_secret_configured(credential):
            raise ProviderRegistryNotReady(
                "endpoint credential Secret Store alias is not configured"
            )

    async def register_profile_assignment(
        self,
        *,
        role: str,
        profile_id: str,
        profile_version: str,
        endpoint_profile_id: str,
        endpoint_profile_version: str,
        endpoint_model_id: str,
        endpoint_model_version: str,
        credential_id: str,
        price_version_id: str,
        price_version: str,
        prompt_profile_id: str,
        explicit_same_model_confirmation: bool,
        assigned_by: str,
    ) -> tuple[ModelProfile, ModelProfileAssignment]:
        endpoint = await self.endpoint(
            endpoint_profile_id, endpoint_profile_version
        )
        await self._require_active_lineage(endpoint)
        if (
            endpoint.state not in {"URL_VALIDATED", "CAPABILITY_CHECKED", "READY"}
            or endpoint.url_validation_status != "PASS"
            or not endpoint.data_transmission_confirmed
        ):
            raise ProviderRegistryNotReady(
                "endpoint URL and third-party data transmission are not approved"
            )
        if endpoint.api_mode == "AUTO_DETECT":
            raise ProviderRegistryNotReady(
                "AUTO_DETECT is not production-resolved; register an explicit API mode version"
            )
        model_raw = await self.repository.get(
            "endpoint_models",
            {
                "endpoint_model_id": endpoint_model_id,
                "model_version": endpoint_model_version,
            },
        )
        if not model_raw:
            raise ProviderRegistryNotReady("endpoint model is not registered")
        model = EndpointModelDefinition.model_validate(model_raw)
        if (
            model.endpoint_profile_id != endpoint_profile_id
            or model.endpoint_profile_version != endpoint_profile_version
        ):
            raise ProviderRegistryNotReady(
                "endpoint model is not bound to this exact endpoint version"
            )
        if role not in model.role_capabilities:
            raise ProviderRegistryNotReady("model role capability is not registered")
        price_raw = await self.repository.get(
            "endpoint_prices",
            {
                "price_version_id": price_version_id,
                "price_version": price_version,
            },
        )
        if not price_raw:
            raise ProviderRegistryNotReady("model price version is not registered")
        price = EndpointPriceVersion.model_validate(price_raw)
        if (
            price.endpoint_profile_id != endpoint_profile_id
            or price.endpoint_profile_version != endpoint_profile_version
            or price.endpoint_model_id != endpoint_model_id
            or price.endpoint_model_version != endpoint_model_version
        ):
            raise ProviderRegistryNotReady(
                "model price is not bound to this exact endpoint model version"
            )
        if not price.verified:
            raise ProviderRegistryNotReady("model price version is not verified")
        if _as_utc(price.effective_at) > datetime.now(timezone.utc):
            raise ProviderRegistryNotReady("model price version is not yet effective")
        credential = await self.db["ag_model_credentials"].find_one(
            {"credential_id": credential_id, "status": {"$ne": "REVOKED"}}
        )
        self._verify_credential_binding(endpoint, credential)
        prompt = PromptProfileRegistry(self.db).definition(prompt_profile_id)
        mode_map = {
            "NATIVE_JSON_SCHEMA": "NATIVE_SCHEMA",
            "TOOL_CALL": "TOOL_CALL",
            "JSON_ONLY": "JSON_SCHEMA",
        }
        structured_mode = mode_map.get(endpoint.structured_output_mode)
        if not structured_mode:
            raise ProviderRegistryNotReady(
                "endpoint structured output mode is not configured"
            )
        other_role = (
            "TOP_RISK_REVIEWER"
            if role == "NORMAL_TRADER"
            else "NORMAL_TRADER"
        )
        other_assignment = await self.db["ag_model_profile_assignments"].find_one(
            {"role": other_role}, sort=[("assigned_at", -1)]
        )
        if other_assignment:
            other_profile = await self.db["ag_model_profiles"].find_one(
                {
                    "profile_id": other_assignment["profile_id"],
                    "profile_version": other_assignment["profile_version"],
                }
            )
            same = bool(
                other_profile
                and other_profile.get("endpoint_profile_id") == endpoint_profile_id
                and other_profile.get("endpoint_profile_version")
                == endpoint_profile_version
                and other_profile.get("endpoint_model_id") == endpoint_model_id
                and other_profile.get("endpoint_model_version")
                == endpoint_model_version
            )
            if same and not explicit_same_model_confirmation:
                raise ProviderRegistryNotReady(
                    "using one endpoint model for Normal and Top requires explicit confirmation"
                )
        now = datetime.now(timezone.utc)
        production_allowed = (
            model.status == "READY"
            and price.currency == ModelBudgetService(self.db).policy.currency
        )
        profile_payload = {
            "profile_id": profile_id,
            "profile_version": profile_version,
            "role": role,
            "provider": "openai_compatible",
            "provider_type": "OPENAI_COMPATIBLE",
            "model_name": model.remote_model_name,
            "model_version": model.model_version,
            "base_url": endpoint.base_url,
            "structured_output_mode": structured_mode,
            "temperature": 0,
            "max_input_tokens": model.max_context_tokens or 32000,
            "max_output_tokens": model.max_output_tokens or 4000,
            "timeout_seconds": 120,
            "max_retries": 0,
            "retry_backoff_seconds": 0,
            "credential_ref": f"keychain-alias:{credential_id}",
            "credential_id": credential_id,
            "prompt_profile_id": prompt.prompt_id,
            "input_cost_per_million": float(price.input_price_per_million),
            "output_cost_per_million": float(price.output_price_per_million),
            "cost_currency": price.currency,
            "enabled": True,
            "production_allowed": production_allowed,
            "research_allowed": True,
            "capability_status": "UNVERIFIED",
            "endpoint_profile_id": endpoint_profile_id,
            "endpoint_profile_version": endpoint_profile_version,
            "endpoint_model_id": endpoint_model_id,
            "endpoint_model_version": endpoint_model_version,
            "price_version_id": price_version_id,
            "normalized_origin": endpoint.normalized_origin,
            "auth_scheme": endpoint.auth_scheme,
            "created_at": now,
            "schema_version": "model_profile_v2",
        }
        profile_payload["config_hash"] = _content_hash(
            profile_payload, "config_hash"
        )
        profile = ModelProfile.model_validate(profile_payload)
        try:
            saved, _ = await self.repository.save_immutable(
                "profiles",
                profile,
                identity={
                    "profile_id": profile.profile_id,
                    "profile_version": profile.profile_version,
                },
                hash_field="config_hash",
            )
        except ModelRuntimeIntegrityConflict as exc:
            raise ProviderRegistryConflict(str(exc)) from exc
        current = await self.db["ag_model_profile_assignments"].find_one(
            {"role": role}, sort=[("assigned_at", -1)]
        )
        if (
            current
            and current.get("profile_id") == profile_id
            and current.get("profile_version") == profile_version
        ):
            if bool(current.get("explicit_same_model_confirmation")) != bool(
                explicit_same_model_confirmation
            ):
                raise ProviderRegistryConflict(
                    "immutable profile assignment confirmation conflicts"
                )
            return saved, ModelProfileAssignment.model_validate(
                clean_document(current)
            )
        identity = {
            "role": role,
            "profile_id": profile_id,
            "profile_version": profile_version,
            "supersedes_assignment_id": (
                current.get("assignment_id") if current else None
            ),
        }
        assignment_payload = {
            "assignment_id": str(
                uuid5(
                    NAMESPACE_URL,
                    f"alphaguard:model-profile-assignment:{canonical_hash(identity)}",
                )
            ),
            **identity,
            "status": "ACTIVE",
            "explicit_same_model_confirmation": explicit_same_model_confirmation,
            "assigned_by": assigned_by,
            "assigned_at": now,
        }
        assignment_payload["assignment_hash"] = _content_hash(
            assignment_payload, "assignment_hash"
        )
        assignment = ModelProfileAssignment.model_validate(assignment_payload)
        saved_assignment, _ = await self.repository.save_immutable(
            "profile_assignments",
            assignment,
            identity={"assignment_id": assignment.assignment_id},
            hash_field="assignment_hash",
        )
        return saved, saved_assignment

    async def configure_decision_models(
        self,
        *,
        endpoint_profile_id: str,
        endpoint_profile_version: str,
        credential_id: str,
        normal_endpoint_model_id: str,
        normal_endpoint_model_version: str,
        top_endpoint_model_id: str,
        top_endpoint_model_version: str,
        explicit_same_model_confirmation: bool,
        assigned_by: str,
    ) -> dict[str, Any]:
        """Apply the two decision roles without exposing registry internals.

        The simple settings UI selects one registered model per role.  This
        method resolves the active verified price, reuses an identical active
        binding, and creates the next immutable profile version only when the
        selected model actually changes.
        """

        endpoint = await self.endpoint(
            endpoint_profile_id, endpoint_profile_version
        )
        await self._require_active_lineage(endpoint)
        credential = await self.db["ag_model_credentials"].find_one(
            {"credential_id": credential_id, "status": {"$ne": "REVOKED"}}
        )
        self._verify_credential_binding(endpoint, credential)
        selections = {
            "NORMAL_TRADER": (
                normal_endpoint_model_id,
                normal_endpoint_model_version,
                "alphaguard_normal_compatible",
                "normal_trade_plan_prompt",
            ),
            "TOP_RISK_REVIEWER": (
                top_endpoint_model_id,
                top_endpoint_model_version,
                "alphaguard_top_compatible",
                "top_risk_review_prompt",
            ),
        }
        same_model = (
            normal_endpoint_model_id == top_endpoint_model_id
            and normal_endpoint_model_version == top_endpoint_model_version
        )
        if same_model and not explicit_same_model_confirmation:
            raise ProviderRegistryNotReady(
                "using one endpoint model for Normal and Top requires explicit confirmation"
            )

        resolved: dict[str, dict[str, Any]] = {}
        now = datetime.now(timezone.utc)
        for role, (model_id, model_version, profile_id, prompt_id) in selections.items():
            model_raw = await self.repository.get(
                "endpoint_models",
                {"endpoint_model_id": model_id, "model_version": model_version},
            )
            if not model_raw:
                raise ProviderRegistryNotReady(
                    f"{role} endpoint model is not registered"
                )
            model = EndpointModelDefinition.model_validate(model_raw)
            if (
                model.endpoint_profile_id != endpoint_profile_id
                or model.endpoint_profile_version != endpoint_profile_version
                or role not in model.role_capabilities
            ):
                raise ProviderRegistryNotReady(
                    f"{role} model is not available for this service version"
                )
            price_rows = await self.repository.list(
                "endpoint_prices",
                {
                    "endpoint_profile_id": endpoint_profile_id,
                    "endpoint_profile_version": endpoint_profile_version,
                    "endpoint_model_id": model_id,
                    "endpoint_model_version": model_version,
                },
                sort=("effective_at", -1),
                limit=500,
            )
            price_raw = next(
                (
                    row
                    for row in price_rows
                    if row.get("verified") is True
                    and row.get("currency")
                    == ModelBudgetService(self.db).policy.currency
                    and isinstance(row.get("effective_at"), datetime)
                    and _as_utc(row["effective_at"]) <= now
                ),
                None,
            )
            if not price_raw:
                raise ProviderRegistryNotReady(
                    f"{role} model has no active verified price"
                )
            price = EndpointPriceVersion.model_validate(clean_document(price_raw))
            resolved[role] = {
                "model": model,
                "price": price,
                "profile_id": profile_id,
                "prompt_id": prompt_id,
            }

        results: dict[str, Any] = {}
        for role, item in resolved.items():
            model = item["model"]
            price = item["price"]
            profile_id = str(item["profile_id"])
            current_assignment = await self.db[
                "ag_model_profile_assignments"
            ].find_one({"role": role}, sort=[("assigned_at", -1)])
            current_profile = None
            if current_assignment:
                current_profile = await self.db["ag_model_profiles"].find_one(
                    {
                        "profile_id": current_assignment.get("profile_id"),
                        "profile_version": current_assignment.get("profile_version"),
                    }
                )
            if current_profile and all(
                (
                    current_profile.get("endpoint_profile_id")
                    == endpoint_profile_id,
                    current_profile.get("endpoint_profile_version")
                    == endpoint_profile_version,
                    current_profile.get("endpoint_model_id")
                    == model.endpoint_model_id,
                    current_profile.get("endpoint_model_version")
                    == model.model_version,
                    current_profile.get("credential_id") == credential_id,
                    current_profile.get("price_version_id")
                    == price.price_version_id,
                )
            ):
                results[role] = {
                    "result": "REUSED",
                    "profile_id": current_profile["profile_id"],
                    "profile_version": current_profile["profile_version"],
                    "model_name": current_profile["model_name"],
                }
                continue
            profile_rows = await self.repository.list(
                "profiles", {"profile_id": profile_id}, limit=500
            )
            profile_version = _next_version(profile_rows, "profile_version")
            profile, assignment = await self.register_profile_assignment(
                role=role,
                profile_id=profile_id,
                profile_version=profile_version,
                endpoint_profile_id=endpoint_profile_id,
                endpoint_profile_version=endpoint_profile_version,
                endpoint_model_id=model.endpoint_model_id,
                endpoint_model_version=model.model_version,
                credential_id=credential_id,
                price_version_id=price.price_version_id,
                price_version=price.price_version,
                prompt_profile_id=str(item["prompt_id"]),
                explicit_same_model_confirmation=(
                    explicit_same_model_confirmation if same_model else False
                ),
                assigned_by=assigned_by,
            )
            results[role] = {
                "result": "CREATED",
                "profile_id": profile.profile_id,
                "profile_version": profile.profile_version,
                "model_name": profile.model_name,
                "assignment_id": assignment.assignment_id,
            }
        return {"roles": results}

    async def resolve_profile_binding(
        self, profile: ModelProfile
    ) -> tuple[ProviderEndpointProfile, EndpointModelDefinition, EndpointPriceVersion, dict[str, Any]]:
        if profile.provider_type != "OPENAI_COMPATIBLE":
            raise ProviderRegistryNotReady("profile is not OpenAI-compatible")
        endpoint = await self.endpoint(
            str(profile.endpoint_profile_id),
            str(profile.endpoint_profile_version),
        )
        await self._require_active_lineage(endpoint)
        model_raw = await self.repository.get(
            "endpoint_models",
            {
                "endpoint_model_id": profile.endpoint_model_id,
                "model_version": profile.endpoint_model_version,
            },
        )
        price_raw = await self.repository.get(
            "endpoint_prices",
            {"price_version_id": profile.price_version_id},
        )
        credential = await self.db["ag_model_credentials"].find_one(
            {"credential_id": profile.credential_id, "status": {"$ne": "REVOKED"}}
        )
        if not model_raw or not price_raw:
            raise ProviderRegistryNotReady("registered profile dependency is missing")
        model = EndpointModelDefinition.model_validate(model_raw)
        price = EndpointPriceVersion.model_validate(price_raw)
        self._verify_credential_binding(endpoint, credential)
        if (
            model.endpoint_profile_id != endpoint.endpoint_profile_id
            or model.endpoint_profile_version != endpoint.profile_version
            or price.endpoint_profile_id != endpoint.endpoint_profile_id
            or price.endpoint_profile_version != endpoint.profile_version
            or price.endpoint_model_id != model.endpoint_model_id
            or price.endpoint_model_version != model.model_version
            or not price.verified
            or endpoint.state in {"DISABLED", "REJECTED"}
        ):
            raise ProviderRegistryNotReady("registered profile binding is inconsistent")
        return endpoint, model, price, credential
