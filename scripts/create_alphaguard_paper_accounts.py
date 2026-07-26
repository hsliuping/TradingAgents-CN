#!/usr/bin/env python3
"""Dry-run by default; initialize four isolated accounts with --execute."""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.core.database import close_database, get_mongo_db, init_database
from app.services.alphaguard.paper_account_service import PaperAccountService
from app.services.alphaguard.paper_policy_registry import (
    PaperPolicyRegistry,
    builtin_account_policy,
)


async def main(user_id: str | None, execute: bool) -> None:
    policy = builtin_account_policy()
    print(
        f"user_id={user_id or '<required-for-execute>'} "
        f"account_types={','.join(policy.account_types)} "
        f"initial_cash={policy.initial_cash}"
    )
    if not execute:
        print("dry-run: no accounts written; pass --execute with --user-id")
        return
    if not user_id:
        raise SystemExit("--user-id is required with --execute")
    await init_database()
    try:
        db = get_mongo_db()
        await PaperPolicyRegistry(db).register_builtins()
        before = {
            document["account_type"]
            for document in await db["ag_paper_accounts"].find(
                {"user_id": str(user_id)}
            ).to_list(length=None)
        }
        accounts = await PaperAccountService(db).initialize_user_accounts(user_id)
        created = sum(key not in before for key in accounts)
        reused = len(accounts) - created
        print(
            f"created={created} reused={reused} conflicts=0 failed=0"
        )
    finally:
        await close_database()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--user-id")
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args()
    asyncio.run(main(args.user_id, args.execute))
