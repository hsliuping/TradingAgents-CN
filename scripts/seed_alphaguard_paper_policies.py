#!/usr/bin/env python3
"""Dry-run by default; seed immutable PR-006 policies with --execute."""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.core.database import close_database, get_mongo_db, init_database
from app.services.alphaguard.paper_policy_registry import (
    PaperPolicyRegistry,
    builtin_account_policy,
    builtin_execution_policy,
    builtin_fee_policy,
)


async def main(execute: bool) -> None:
    policies = (
        builtin_account_policy(),
        builtin_execution_policy(),
        builtin_fee_policy(),
    )
    for policy in policies:
        print(
            f"policy={policy.version} "
            f"config_hash={policy.config_hash}"
        )
    if not execute:
        print("dry-run: no policies written; pass --execute to seed")
        return
    await init_database()
    try:
        results = await PaperPolicyRegistry(get_mongo_db()).register_builtins()
        print(
            " ".join(
                [
                    f"created={sum(value == 'created' for value in results.values())}",
                    f"reused={sum(value == 'reused' for value in results.values())}",
                    "conflicts=0",
                    "failed=0",
                ]
            )
        )
    finally:
        await close_database()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--execute", action="store_true")
    asyncio.run(main(parser.parse_args().execute))
