#!/usr/bin/env python3
"""Explicit research-only dual-model validation; never creates trade objects."""

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
from app.services.alphaguard.real_model_validation_service import (  # noqa: E402
    RealModelValidationService,
)


CONFIRMATION = "RUN NON-EXECUTABLE MODEL VALIDATION"


async def run(args) -> int:
    if args.confirm != CONFIRMATION:
        print(f"blocked: --confirm must be exactly {CONFIRMATION!r}")
        return 2
    client = AsyncIOMotorClient(settings.MONGO_URI, serverSelectionTimeoutMS=5000)
    try:
        await client.admin.command("ping")
        result = await RealModelValidationService(
            client[settings.MONGO_DB]
        ).run(
            requested_by=args.requested_by,
            idempotency_key=args.idempotency_key,
            proposal_id=args.proposal_id,
            user_id=args.user_id,
        )
        print(
            json.dumps(
                result.model_dump(mode="json"),
                ensure_ascii=False,
                sort_keys=True,
            )
        )
        return 0 if result.status == "COMPLETED" else 2
    finally:
        client.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--requested-by", required=True)
    parser.add_argument("--idempotency-key", required=True)
    parser.add_argument("--proposal-id")
    parser.add_argument("--user-id")
    parser.add_argument("--confirm", required=True)
    raise SystemExit(asyncio.run(run(parser.parse_args())))
