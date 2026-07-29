"""Immutable prompt versions for formal AlphaGuard model calls."""

from __future__ import annotations

from typing import Any

from app.schemas.alphaguard.model_runtime import PromptProfile

from .model_runtime_config import load_model_runtime_config
from .model_runtime_repository import ModelRuntimeRepository


class PromptProfileNotRegistered(LookupError):
    pass


class PromptProfileRegistry:
    def __init__(self, db=None):
        self.db = db
        self._prompts = tuple(load_model_runtime_config()["prompts"])

    def definitions(self) -> tuple[PromptProfile, ...]:
        return self._prompts

    def definition(
        self, prompt_id: str, prompt_version: str | None = None
    ) -> PromptProfile:
        matches = [
            item
            for item in self._prompts
            if item.prompt_id == prompt_id
            and (
                prompt_version is None
                or item.prompt_version == prompt_version
            )
        ]
        if len(matches) != 1:
            raise PromptProfileNotRegistered(
                f"exact PromptProfile is not registered: "
                f"{prompt_id}@{prompt_version or '<required>'}"
            )
        return matches[0]

    async def seed(self) -> dict[str, int]:
        if self.db is None:
            raise RuntimeError("database is required to seed prompts")
        repository = ModelRuntimeRepository(self.db)
        created = 0
        reused = 0
        for prompt in self._prompts:
            _, was_created = await repository.save_immutable(
                "prompts",
                prompt,
                identity={
                    "prompt_id": prompt.prompt_id,
                    "prompt_version": prompt.prompt_version,
                },
                hash_field="template_hash",
            )
            created += int(was_created)
            reused += int(not was_created)
        return {"created": created, "reused": reused}

    async def persisted(
        self, prompt_id: str, prompt_version: str
    ) -> PromptProfile:
        if self.db is None:
            raise RuntimeError("database is required for production resolution")
        defined = self.definition(prompt_id, prompt_version)
        raw = await ModelRuntimeRepository(self.db).get(
            "prompts",
            {"prompt_id": prompt_id, "prompt_version": prompt_version},
        )
        if raw is None:
            raise PromptProfileNotRegistered(
                f"PromptProfile is not persisted: {prompt_id}@{prompt_version}"
            )
        stored = PromptProfile.model_validate(raw)
        if stored.template_hash != defined.template_hash:
            raise PromptProfileNotRegistered(
                f"PromptProfile hash differs from registered definition: "
                f"{prompt_id}@{prompt_version}"
            )
        return stored
