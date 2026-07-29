#!/usr/bin/env python3
"""Dry-run-first 2026-07-29 research evidence-contract validation."""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from datetime import date, datetime
from pathlib import Path

from motor.motor_asyncio import AsyncIOMotorClient

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

FROZEN_SOURCE_TRADE_DATE = date(2026, 7, 29)
FROZEN_CUTOFF_AT = datetime(2026, 7, 29, 23, 59, 59)

from app.core.config import settings
from app.services.alphaguard.evidence_contract_validation_service import (
    EvidenceContractValidationService,
)


async def main(*, execute: bool, user_id: str | None) -> None:
    client = AsyncIOMotorClient(
        settings.MONGO_URI,
        serverSelectionTimeoutMS=5000,
        connectTimeoutMS=5000,
    )
    try:
        db = client[settings.MONGO_DB]
        await db.command("ping")
        resolved_user = user_id
        if not resolved_user:
            rows = await db["ag_candidates"].distinct(
                "user_id",
                {"symbol": {"$in": list(EvidenceContractValidationService.SYMBOLS)}},
            )
            if len(rows) != 1:
                raise RuntimeError(
                    "exactly one existing candidate owner is required"
                )
            resolved_user = str(rows[0])
        result = await EvidenceContractValidationService(db).run(
            user_id=resolved_user,
            source_trade_date=FROZEN_SOURCE_TRADE_DATE,
            cutoff_at=FROZEN_CUTOFF_AT,
            execute=execute,
        )
        print(json.dumps(result, ensure_ascii=False, indent=2, default=str))
    finally:
        client.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--user-id")
    options = parser.parse_args()
    asyncio.run(main(execute=options.execute, user_id=options.user_id))
