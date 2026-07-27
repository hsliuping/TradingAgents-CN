#!/usr/bin/env python3
"""Safely bootstrap the first database-backed administrator.

The command is dry-run by default.  It never accepts a password as a command
line argument and never prints password material.
"""

from __future__ import annotations

import argparse
import asyncio
import getpass
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

from motor.motor_asyncio import AsyncIOMotorClient

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.core.config import settings
from app.models.user import UserCreate, UserPreferences
from app.services.user_service import UserService


PASSWORD_ENV = "ALPHAGUARD_BOOTSTRAP_ADMIN_PASSWORD"
USERNAME_ENV = "ALPHAGUARD_BOOTSTRAP_ADMIN_USERNAME"
EMAIL_ENV = "ALPHAGUARD_BOOTSTRAP_ADMIN_EMAIL"


class AdminBootstrapConflict(RuntimeError):
    """Raised when bootstrap would mutate or overwrite an existing identity."""


async def _ensure_identity_indexes(db: Any) -> None:
    indexes = {
        item["name"]: item
        for item in await db["users"].list_indexes().to_list(length=None)
    }
    requirements = (
        ("uniq_users_username", [("username", 1)]),
        ("uniq_users_email", [("email", 1)]),
    )
    for name, keys in requirements:
        existing = indexes.get(name)
        if existing is not None:
            if existing.get("key") != dict(keys) or existing.get("unique") is not True:
                raise AdminBootstrapConflict(f"user index {name} has conflicting definition")
            continue
        await db["users"].create_index(keys, name=name, unique=True)


def _admin_document(username: str, email: str, password: str, now: datetime) -> dict:
    validated = UserCreate(username=username, email=email, password=password)
    if len(validated.password) < 12:
        raise ValueError("bootstrap administrator password must contain at least 12 characters")
    return {
        "username": validated.username,
        "email": validated.email,
        "hashed_password": UserService.hash_password(validated.password),
        "password_hash_algo": "bcrypt",
        "is_active": True,
        "is_verified": True,
        "is_admin": True,
        "created_at": now,
        "updated_at": now,
        "last_login": None,
        "preferences": UserPreferences().model_dump(mode="python"),
        "daily_quota": 10000,
        "concurrent_limit": 10,
        "total_analyses": 0,
        "successful_analyses": 0,
        "failed_analyses": 0,
        "favorite_stocks": [],
        "bootstrap_source": "scripts/bootstrap_admin_user.py",
    }


def _audit_document(
    *,
    user_id: str,
    username: str,
    outcome: str,
    now: datetime,
) -> dict:
    return {
        "user_id": user_id,
        "username": username,
        "action_type": "user_management",
        "action": "AlphaGuard administrator bootstrap",
        "details": {
            "outcome": outcome,
            "source": "scripts/bootstrap_admin_user.py",
            "is_admin": True,
        },
        "success": True,
        "error_message": None,
        "duration_ms": None,
        "ip_address": None,
        "user_agent": "local-cli",
        "session_id": None,
        "timestamp": now,
        "created_at": now,
    }


async def bootstrap_admin(
    db: Any,
    *,
    username: str,
    email: str,
    password: str | None,
    execute: bool,
    now: datetime | None = None,
) -> dict[str, str]:
    """Validate or create one administrator without modifying existing users."""

    now = now or datetime.utcnow()
    existing_username = await db["users"].find_one({"username": username})
    existing_email = await db["users"].find_one({"email": email})

    if existing_username is not None:
        if str(existing_username.get("email")) != email:
            raise AdminBootstrapConflict("username exists with a different email")
        if existing_username.get("is_admin") is not True:
            raise AdminBootstrapConflict("existing user is not an administrator")
        if existing_username.get("is_active") is False:
            raise AdminBootstrapConflict("existing administrator is inactive")
        if existing_email is not None and existing_email.get("_id") != existing_username.get("_id"):
            raise AdminBootstrapConflict("email belongs to a different user")
        if execute:
            await db["operation_logs"].insert_one(
                _audit_document(
                    user_id=str(existing_username["_id"]),
                    username=username,
                    outcome="REUSED",
                    now=now,
                )
            )
        return {
            "status": "REUSED",
            "user_id": str(existing_username["_id"]),
            "username": username,
        }

    if existing_email is not None:
        raise AdminBootstrapConflict("email belongs to an existing user")
    if not execute:
        return {
            "status": "WOULD_CREATE",
            "user_id": "",
            "username": username,
        }
    if password is None:
        raise ValueError("password is required for administrator creation")

    await _ensure_identity_indexes(db)
    document = _admin_document(username, email, password, now)
    inserted = await db["users"].insert_one(document)
    try:
        await db["operation_logs"].insert_one(
            _audit_document(
                user_id=str(inserted.inserted_id),
                username=username,
                outcome="CREATED",
                now=now,
            )
        )
    except Exception:
        await db["users"].delete_one({"_id": inserted.inserted_id})
        raise
    return {
        "status": "CREATED",
        "user_id": str(inserted.inserted_id),
        "username": username,
    }


def _password_for_execute() -> str:
    value = os.getenv(PASSWORD_ENV)
    if value:
        return value
    if sys.stdin.isatty():
        return getpass.getpass("Administrator password: ")
    raise SystemExit(
        f"{PASSWORD_ENV} must be set when --execute is used non-interactively"
    )


async def _main(args: argparse.Namespace) -> None:
    username = args.username or os.getenv(USERNAME_ENV)
    email = args.email or os.getenv(EMAIL_ENV)
    if not username or not email:
        raise SystemExit(
            f"--username/--email or {USERNAME_ENV}/{EMAIL_ENV} are required"
        )
    password = _password_for_execute() if args.execute else None
    client = AsyncIOMotorClient(
        settings.MONGO_URI,
        serverSelectionTimeoutMS=settings.MONGO_SERVER_SELECTION_TIMEOUT_MS,
    )
    try:
        await client.admin.command("ping")
        result = await bootstrap_admin(
            client[settings.MONGO_DB],
            username=username,
            email=email,
            password=password,
            execute=args.execute,
        )
        print(
            f"status={result['status']} username={result['username']} "
            f"user_id={result['user_id'] or '-'} write={'yes' if args.execute else 'no'}"
        )
    finally:
        client.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Dry-run or securely bootstrap the first AlphaGuard administrator"
    )
    parser.add_argument("--username")
    parser.add_argument("--email")
    parser.add_argument("--execute", action="store_true")
    asyncio.run(_main(parser.parse_args()))
