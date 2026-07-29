#!/usr/bin/env python3
"""Explicit, non-trading capability check for one registered profile."""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

from motor.motor_asyncio import AsyncIOMotorClient

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.core.config import settings  # noqa: E402
from app.services.alphaguard.model_capability_service import (  # noqa: E402
    ModelCapabilityService,
)


async def run(args) -> int:
    client = AsyncIOMotorClient(settings.MONGO_URI, serverSelectionTimeoutMS=5000)
    try:
        await client.admin.command("ping")
        result = await ModelCapabilityService(
            client[settings.MONGO_DB]
        ).check(
            profile_id=args.profile_id,
            profile_version=args.profile_version,
            checked_by=args.checked_by,
            idempotency_key=args.idempotency_key,
            network=args.network,
        )
        print(
            json.dumps(
                result.model_dump(
                    mode="json",
                    exclude={"request_hash", "response_hash"},
                ),
                ensure_ascii=False,
                sort_keys=True,
            )
        )
        return 0 if result.status in {"READY", "UNVERIFIED"} else 2
    finally:
        client.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--profile-id", required=True)
    parser.add_argument("--profile-version", required=True)
    parser.add_argument("--checked-by", required=True)
    parser.add_argument("--idempotency-key", required=True)
    parser.add_argument(
        "--network",
        action="store_true",
        help="make one paid/provider call; omitted means read-only preflight",
    )
    raise SystemExit(asyncio.run(run(parser.parse_args())))
