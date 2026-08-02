#!/usr/bin/env python3
"""Dry-run by default; initialize selected isolated accounts with --execute."""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorClient

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.core.config import settings
from app.services.alphaguard.paper_account_service import PaperAccountService
from app.services.alphaguard.paper_policy_registry import (
    PaperPolicyRegistry,
    builtin_account_policy,
)


DEFAULT_ACCOUNT_TYPES = (
    "PAPER_QUANT",
    "PAPER_NORMAL",
    "PAPER_TOP_CONFIRMED",
    "PAPER_CHALLENGER",
)


async def main(
    user_id: str | None,
    execute: bool,
    account_types: tuple[str, ...],
) -> None:
    policy = builtin_account_policy()
    unsupported = set(account_types) - set(policy.account_types)
    if unsupported:
        raise SystemExit(
            f"unsupported account types: {','.join(sorted(unsupported))}"
        )
    print(
        f"user_id={user_id or '<required-for-execute>'} "
        f"account_types={','.join(account_types)} "
        f"initial_cash={policy.initial_cash} market={policy.market} "
        f"currency={policy.currency}"
    )
    if not execute:
        print(
            "dry-run: no accounts written; "
            "pass --execute with a verified administrator --user-id"
        )
        if not user_id:
            return
    if not user_id:
        raise SystemExit("--user-id is required with --execute")
    client = AsyncIOMotorClient(
        settings.MONGO_URI,
        serverSelectionTimeoutMS=settings.MONGO_SERVER_SELECTION_TIMEOUT_MS,
    )
    try:
        db = client[settings.MONGO_DB]
        clauses: list[dict] = [{"_id": str(user_id)}, {"id": str(user_id)}]
        if ObjectId.is_valid(str(user_id)):
            clauses.append({"_id": ObjectId(str(user_id))})
        user = await db["users"].find_one({"$or": clauses})
        if user is None:
            raise SystemExit("user check failed: user_id does not exist")
        if user.get("is_admin") is not True or user.get("is_active") is False:
            raise SystemExit(
                "user check failed: account initialization requires an active administrator"
            )

        indexes = await db["ag_paper_accounts"].index_information()
        unique_identity = indexes.get("uniq_paper_user_type_market") or {}
        expected_keys = [
            ("user_id", 1),
            ("account_type", 1),
            ("market", 1),
        ]
        if (
            unique_identity.get("unique") is not True
            or unique_identity.get("key") != expected_keys
        ):
            raise SystemExit(
                "index check failed: uniq_paper_user_type_market is missing or invalid"
            )
        before = {
            document["account_type"]
            for document in await db["ag_paper_accounts"].find(
                {"user_id": str(user_id)}
            ).to_list(length=None)
        }
        print(
            f"user_check=active_admin index_check=pass "
            f"existing={','.join(sorted(before)) or '-'}"
        )
        if not execute:
            print("dry-run complete: database checks passed; no writes performed")
            return

        await PaperPolicyRegistry(db).register_builtins()
        accounts = await PaperAccountService(db).initialize_user_accounts(
            user_id,
            account_types=account_types,
        )
        created = sum(key not in before for key in accounts)
        reused = len(accounts) - created
        print(
            f"created={created} reused={reused} conflicts=0 failed=0"
        )
    finally:
        client.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--user-id")
    parser.add_argument("--execute", action="store_true")
    parser.add_argument(
        "--account-type",
        action="append",
        choices=tuple(builtin_account_policy().account_types),
        dest="account_types",
        help=(
            "account type to initialize; repeat as needed. Defaults to all four "
            "isolated automatic paper accounts"
        ),
    )
    args = parser.parse_args()
    asyncio.run(
        main(
            args.user_id,
            args.execute,
            tuple(args.account_types or DEFAULT_ACCOUNT_TYPES),
        )
    )
