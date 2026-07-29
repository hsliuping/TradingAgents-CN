"""Exact, versioned role-to-model bindings with no model guessing."""

from __future__ import annotations

from typing import Any

from app.schemas.alphaguard.model_runtime import ModelProfile

from .model_runtime_config import load_model_runtime_config
from .model_runtime_repository import ModelRuntimeRepository


class ModelProfileNotRegistered(LookupError):
    pass


class ModelProfileRegistry:
    def __init__(self, db=None):
        self.db = db
        config = load_model_runtime_config()
        self._profiles = tuple(config["profiles"])

    def definitions(self) -> tuple[ModelProfile, ...]:
        return self._profiles

    def definition(
        self, profile_id: str, profile_version: str | None = None
    ) -> ModelProfile:
        matches = [
            item
            for item in self._profiles
            if item.profile_id == profile_id
            and (
                profile_version is None
                or item.profile_version == profile_version
            )
        ]
        if len(matches) != 1:
            raise ModelProfileNotRegistered(
                f"exact ModelProfile is not registered: "
                f"{profile_id}@{profile_version or '<required>'}"
            )
        return matches[0]

    def for_role(self, role: str) -> ModelProfile:
        matches = [
            item for item in self._profiles if item.enabled and item.role == role
        ]
        if len(matches) != 1:
            raise ModelProfileNotRegistered(
                f"role must bind exactly one enabled ModelProfile: {role}"
            )
        return matches[0]

    async def seed(self) -> dict[str, Any]:
        if self.db is None:
            raise RuntimeError("database is required to seed model profiles")
        repository = ModelRuntimeRepository(self.db)
        created = 0
        reused = 0
        for profile in self._profiles:
            _, was_created = await repository.save_immutable(
                "profiles",
                profile,
                identity={
                    "profile_id": profile.profile_id,
                    "profile_version": profile.profile_version,
                },
                hash_field="config_hash",
            )
            created += int(was_created)
            reused += int(not was_created)
        return {"created": created, "reused": reused}

    async def persisted(
        self, profile_id: str, profile_version: str
    ) -> ModelProfile:
        if self.db is None:
            raise RuntimeError("database is required for production resolution")
        defined = self.definition(profile_id, profile_version)
        raw = await ModelRuntimeRepository(self.db).get(
            "profiles",
            {
                "profile_id": profile_id,
                "profile_version": profile_version,
            },
        )
        if raw is None:
            raise ModelProfileNotRegistered(
                f"ModelProfile is not persisted: {profile_id}@{profile_version}"
            )
        stored = ModelProfile.model_validate(raw)
        if stored.config_hash != defined.config_hash:
            raise ModelProfileNotRegistered(
                f"ModelProfile hash differs from registered definition: "
                f"{profile_id}@{profile_version}"
            )
        return stored
