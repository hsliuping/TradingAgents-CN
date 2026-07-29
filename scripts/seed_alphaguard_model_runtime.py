#!/usr/bin/env python3
"""Dry-run by default; persist immutable, secret-free PR-010 registries."""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

from motor.motor_asyncio import AsyncIOMotorClient

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.core.config import settings  # noqa: E402
from app.services.alphaguard.model_profile_registry import (  # noqa: E402
    ModelProfileRegistry,
)
from app.services.alphaguard.model_runtime_config import (  # noqa: E402
    load_model_runtime_config,
)
from app.services.alphaguard.prompt_profile_registry import (  # noqa: E402
    PromptProfileRegistry,
)


async def run(*, execute: bool) -> int:
    config = load_model_runtime_config()
    print(
        f"runtime_version={config['runtime_version']} "
        f"profiles={len(config['profiles'])} prompts={len(config['prompts'])}"
    )
    for profile in config["profiles"]:
        print(
            f"profile {profile.profile_id}@{profile.profile_version} "
            f"role={profile.role} provider={profile.provider} "
            f"model={profile.model_name} hash={profile.config_hash}"
        )
    for prompt in config["prompts"]:
        print(
            f"prompt {prompt.prompt_id}@{prompt.prompt_version} "
            f"hash={prompt.template_hash}"
        )
    if not execute:
        print("dry-run: no registry documents written; pass --execute to seed")
        return 0
    client = AsyncIOMotorClient(settings.MONGO_URI, serverSelectionTimeoutMS=5000)
    try:
        await client.admin.command("ping")
        db = client[settings.MONGO_DB]
        profile_result = await ModelProfileRegistry(db).seed()
        prompt_result = await PromptProfileRegistry(db).seed()
        print(f"profiles={profile_result} prompts={prompt_result}")
        return 0
    finally:
        client.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--execute", action="store_true")
    raise SystemExit(asyncio.run(run(execute=parser.parse_args().execute)))
