"""Secret-free runtime status for Operations and the frontend."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from .model_budget_service import ModelBudgetService
from .model_credential_service import ModelCredentialService
from .model_profile_registry import ModelProfileRegistry
from .model_runtime_repository import ModelRuntimeRepository
from .prompt_profile_registry import PromptProfileRegistry


def capability_failure_summary(
    status: str,
    error_code: str | None,
    validation_error_count: int | None = None,
) -> str | None:
    if status == "READY":
        return None
    if error_code == "ValidationError":
        return "模型已返回内容，但结构化结果未通过校验。"
    if (error_code or status) == "INVALID_OUTPUT" and validation_error_count:
        return (
            f"模型返回了 JSON，但有 {validation_error_count} 个决策字段缺失或不符合要求；"
            "请改用结构化输出能力更稳定的模型。"
        )
    summaries = {
        "UNVERIFIED": "尚未执行能力检测。",
        "CREDENTIAL_REVERIFIED": (
            "API 密钥已在上次检测后重新验证，请重新检测模型连接。"
        ),
        "UNAUTHORIZED": (
            "模型调用认证失败，请重新检测；若仍失败，请检查该模型的访问权限。"
        ),
        "PROJECT_ACCESS_DENIED": "当前密钥没有访问该服务项目的权限。",
        "MODEL_NOT_FOUND": "服务商没有找到登记的模型名称。",
        "RATE_LIMITED": "服务商限制了请求频率，请稍后重试。",
        "TIMEOUT": "服务商未在限定时间内响应。",
        "MODEL_TIMEOUT": "模型未在限定时间内完成响应。",
        "STRUCTURED_OUTPUT_UNSUPPORTED": "当前模型或接口不支持所需结构化输出。",
        "INVALID_OUTPUT": (
            "模型返回了 JSON，但决策字段不完整或不符合要求；"
            "请改用结构化输出能力更稳定的模型。"
        ),
        "MALFORMED_JSON": "模型返回内容不是合法 JSON。",
        "INVALID_RESPONSE_TYPE": "服务商返回了不支持的响应格式。",
        "USAGE_UNAVAILABLE": "服务商未返回完整 Token 用量。",
        "PROVIDER_ERROR": "服务商返回异常，或兼容响应未通过解析。",
        "PROVIDER_QUOTA_EXHAUSTED": (
            "服务商额度不足，请充值或选择额度要求更低的模型。"
        ),
        "BUDGET_BLOCKED": "调用限制已阻止本次检测。",
        "NOT_CONFIGURED": "模型角色或 API 密钥尚未完成配置。",
    }
    return summaries.get(error_code or status) or "能力检测未通过。"


def _utc_datetime(value: Any) -> datetime | None:
    if not isinstance(value, datetime):
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def project_capability_check(
    latest_check: dict[str, Any] | None,
    credential: dict[str, Any] | None,
) -> tuple[dict[str, Any] | None, bool]:
    """Project an immutable check against the currently verified credential."""

    if latest_check is None:
        return None, False
    projected = dict(latest_check)
    # Legacy rows used the exception class for a final output-contract failure.
    # Keep the immutable row and correct only its current read projection.
    if latest_check.get("error_code") == "ValidationError":
        projected.update(
            {
                "status": "INVALID_OUTPUT",
                "error_category": "INVALID_OUTPUT",
                "error_code": "INVALID_OUTPUT",
            }
        )
    legacy_message = str(latest_check.get("sanitized_message") or "").lower()
    if (
        latest_check.get("status") == "UNAUTHORIZED"
        and any(
            marker in legacy_message
            for marker in (
                "insufficient_user_quota",
                "insufficient_quota",
                "quota exhausted",
                "quota_exhausted",
                "余额不足",
                "额度不足",
            )
        )
    ):
        projected.update(
            {
                "status": "BUDGET_BLOCKED",
                "error_category": "PROVIDER_QUOTA_EXHAUSTED",
                "error_code": "PROVIDER_QUOTA_EXHAUSTED",
                "sanitized_message": "provider quota is exhausted",
            }
        )
    checked_at = _utc_datetime(latest_check.get("checked_at"))
    verified_at = _utc_datetime(
        credential.get("last_verified_at") if credential else None
    )
    stale = bool(
        credential
        and credential.get("status") == "CONFIGURED"
        and checked_at
        and verified_at
        and verified_at > checked_at
    )
    if stale:
        projected.update(
            {
                "status": "UNVERIFIED",
                "error_category": "CREDENTIAL_REVERIFIED",
                "error_code": "CREDENTIAL_REVERIFIED",
            }
        )
    return projected, stale


def _profile_readiness(items: list[dict], *, expected_count: int) -> str:
    return (
        "READY"
        if len(items) == expected_count
        and all(
            item["configured"] and item["capability"] == "READY"
            for item in items
        )
        else "NOT_CONFIGURED"
        if any(not item["configured"] for item in items)
        else "DEGRADED"
    )


class ModelRuntimeStatusService:
    def __init__(self, db):
        self.db = db
        self.profiles = ModelProfileRegistry(db)
        self.prompts = PromptProfileRegistry(db)
        self.repository = ModelRuntimeRepository(db)
        self.credentials = ModelCredentialService()
        self.budget = ModelBudgetService(db)

    async def status(self, *, admin: bool) -> dict:
        items = []
        selected = []
        for role in ("RESEARCH_AGENT", "NORMAL_TRADER", "TOP_RISK_REVIEWER"):
            try:
                selected.append(await self.profiles.persisted_for_role(role))
            except Exception:
                selected.append(self.profiles.for_role(role))
        for defined in selected:
            persisted = await self.repository.get(
                "profiles",
                {
                    "profile_id": defined.profile_id,
                    "profile_version": defined.profile_version,
                },
            )
            prompt = self.prompts.definition(defined.prompt_profile_id)
            prompt_persisted = await self.repository.get(
                "prompts",
                {
                    "prompt_id": prompt.prompt_id,
                    "prompt_version": prompt.prompt_version,
                },
            )
            latest_check = await self.db[
                "ag_model_capability_checks"
            ].find_one(
                {
                    "profile_id": defined.profile_id,
                    "profile_version": defined.profile_version,
                },
                sort=[("checked_at", -1)],
            )
            credential = (
                await self.db["ag_model_credentials"].find_one(
                    {
                        "credential_id": defined.credential_id,
                        "status": {"$ne": "REVOKED"},
                    },
                    {
                        "_id": 0,
                        "credential_id": 1,
                        "status": 1,
                        "last_verified_at": 1,
                    },
                )
                if defined.credential_id
                else None
            )
            latest_check, capability_stale = project_capability_check(
                latest_check, credential
            )
            latest_success = await self.db["ag_model_runs"].find_one(
                {
                    "model_profile_id": defined.profile_id,
                    "structured_output_status": "SUCCESS",
                },
                sort=[("created_at", -1)],
            )
            latest_failure = await self.db["ag_model_runs"].find_one(
                {
                    "model_profile_id": defined.profile_id,
                    "structured_output_status": {"$ne": "SUCCESS"},
                },
                sort=[("created_at", -1)],
            )
            configured_for_profile = getattr(
                self.credentials,
                "configured_for_profile",
                None,
            )
            credential_configured = (
                configured_for_profile(defined)
                if configured_for_profile is not None
                else self.credentials.configured(defined.credential_ref)
            )
            configured = bool(
                persisted
                and persisted.get("config_hash") == defined.config_hash
                and prompt_persisted
                and prompt_persisted.get("template_hash")
                == prompt.template_hash
                and credential_configured
            )
            capability = (
                str(latest_check.get("status"))
                if latest_check
                else "UNVERIFIED"
            )
            last_error_code = (
                str(
                    latest_check.get("error_category")
                    or latest_check.get("error_code")
                )
                if latest_check
                and (
                    latest_check.get("error_category")
                    or latest_check.get("error_code")
                )
                else None
            )
            item = {
                "role": defined.role,
                "profile_id": defined.profile_id,
                "profile_version": defined.profile_version,
                "provider": defined.provider,
                "provider_type": defined.provider_type,
                "endpoint_profile_id": defined.endpoint_profile_id,
                "endpoint_profile_version": defined.endpoint_profile_version,
                "endpoint_model_id": defined.endpoint_model_id,
                "price_version_id": defined.price_version_id,
                "model_name": defined.model_name,
                "model_version": defined.model_version,
                "prompt_id": prompt.prompt_id,
                "prompt_version": prompt.prompt_version,
                "configured": configured,
                "credential_status": (
                    "CONFIGURED" if configured else "NOT_CONFIGURED"
                ),
                "capability": capability,
                "capability_stale": capability_stale,
                "capability_stale_reason": (
                    "CREDENTIAL_REVERIFIED" if capability_stale else None
                ),
                "last_error_code": last_error_code,
                "failure_summary": capability_failure_summary(
                    capability,
                    str(latest_check.get("error_code"))
                    if latest_check and latest_check.get("error_code")
                    else last_error_code,
                    int(latest_check.get("validation_error_count"))
                    if latest_check
                    and latest_check.get("validation_error_count") is not None
                    else None,
                ),
                "last_check": (
                    latest_check.get("checked_at") if latest_check else None
                ),
                "last_success": (
                    latest_success.get("created_at")
                    if latest_success
                    else None
                ),
                "last_failure": (
                    latest_failure.get("created_at")
                    if latest_failure
                    else None
                ),
                "latency_ms": (
                    latest_check.get("latency_ms") if latest_check else None
                ),
            }
            if not admin:
                item = {
                    key: item[key]
                    for key in (
                        "role",
                        "profile_id",
                        "profile_version",
                        "provider",
                        "model_name",
                        "configured",
                        "capability",
                        "capability_stale",
                        "last_check",
                    )
                }
            items.append(item)
        decision_profiles = [
            item
            for item in items
            if item["role"] in {"NORMAL_TRADER", "TOP_RISK_REVIEWER"}
        ]
        research_profiles = [
            item for item in items if item["role"] == "RESEARCH_AGENT"
        ]
        overall = _profile_readiness(items, expected_count=3)
        result = {
            "status": overall,
            "decision_status": _profile_readiness(
                decision_profiles, expected_count=2
            ),
            "research_status": _profile_readiness(
                research_profiles, expected_count=1
            ),
            "profiles": items,
        }
        if admin:
            result["budget"] = await self.budget.summary()
        return result
