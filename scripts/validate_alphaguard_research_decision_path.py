#!/usr/bin/env python3
"""Dry-run-first research decision-path structural validation."""

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

from app.core.config import settings
from app.services.alphaguard.research_decision_path_validation_service import (
    ResearchDecisionPathValidationService,
)


async def main(*, execute: bool) -> None:
    client = AsyncIOMotorClient(
        settings.MONGO_URI,
        serverSelectionTimeoutMS=5000,
        connectTimeoutMS=5000,
    )
    try:
        db = client[settings.MONGO_DB]
        await db.command("ping")
        result = await ResearchDecisionPathValidationService(db).run(
            execute=execute
        )
        print(json.dumps(result, ensure_ascii=False, indent=2, default=str))
    finally:
        client.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--execute", action="store_true")
    asyncio.run(main(execute=parser.parse_args().execute))
