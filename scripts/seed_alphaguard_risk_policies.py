#!/usr/bin/env python3
"""Dry-run by default; register risk-policy-v1 only with --execute."""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.core.database import close_database, get_mongo_db, init_database
from app.services.alphaguard.risk_policy_registry import (
    RiskPolicyRegistry,
    builtin_risk_policy,
)


async def main(execute: bool) -> None:
    policy = builtin_risk_policy()
    print(
        f"risk_policy={policy.risk_policy_id}@{policy.version} "
        f"config_hash={policy.config_hash}"
    )
    if not execute:
        print("dry-run: no data written; pass --execute to register")
        return
    await init_database()
    try:
        stored = await RiskPolicyRegistry(get_mongo_db()).register_builtin()
        print(f"seeded_or_verified={stored.risk_policy_id}@{stored.version}")
    finally:
        await close_database()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--execute", action="store_true")
    asyncio.run(main(parser.parse_args().execute))
