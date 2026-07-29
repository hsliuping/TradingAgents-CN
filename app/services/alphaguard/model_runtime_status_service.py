"""Secret-free runtime status for Operations and the frontend."""

from __future__ import annotations

from .model_budget_service import ModelBudgetService
from .model_credential_service import ModelCredentialService
from .model_profile_registry import ModelProfileRegistry
from .model_runtime_repository import ModelRuntimeRepository
from .prompt_profile_registry import PromptProfileRegistry


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
        for defined in self.profiles.definitions():
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
            configured = bool(
                persisted
                and persisted.get("config_hash") == defined.config_hash
                and prompt_persisted
                and prompt_persisted.get("template_hash")
                == prompt.template_hash
                and self.credentials.configured(defined.credential_ref)
            )
            capability = (
                str(latest_check.get("status"))
                if latest_check
                else "UNVERIFIED"
            )
            item = {
                "role": defined.role,
                "profile_id": defined.profile_id,
                "profile_version": defined.profile_version,
                "provider": defined.provider,
                "model_name": defined.model_name,
                "model_version": defined.model_version,
                "prompt_id": prompt.prompt_id,
                "prompt_version": prompt.prompt_version,
                "configured": configured,
                "credential_status": (
                    "CONFIGURED" if configured else "NOT_CONFIGURED"
                ),
                "capability": capability,
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
                        "last_check",
                    )
                }
            items.append(item)
        required = list(items)
        overall = (
            "READY"
            if len(required) == 3
            and all(
                item["configured"] and item["capability"] == "READY"
                for item in required
            )
            else "NOT_CONFIGURED"
            if any(not item["configured"] for item in required)
            else "DEGRADED"
        )
        result = {"status": overall, "profiles": items}
        if admin:
            result["budget"] = await self.budget.summary()
        return result
