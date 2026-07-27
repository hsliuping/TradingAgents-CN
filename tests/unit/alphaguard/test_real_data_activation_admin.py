from __future__ import annotations

from datetime import datetime

import pytest

from scripts.bootstrap_admin_user import (
    AdminBootstrapConflict,
    bootstrap_admin,
)
from tests.unit.alphaguard._fakes import FakeDB


@pytest.mark.asyncio
async def test_admin_bootstrap_is_dry_run_by_default():
    db = FakeDB()
    result = await bootstrap_admin(
        db,
        username="operator",
        email="operator@example.com",
        password=None,
        execute=False,
    )
    assert result["status"] == "WOULD_CREATE"
    assert db["users"].documents == []
    assert db["operation_logs"].documents == []


@pytest.mark.asyncio
async def test_admin_bootstrap_uses_bcrypt_and_writes_sanitized_audit():
    db = FakeDB()
    result = await bootstrap_admin(
        db,
        username="operator",
        email="operator@example.com",
        password="correct-horse-battery-staple",
        execute=True,
        now=datetime(2026, 7, 27, 12, 0),
    )
    assert result["status"] == "CREATED"
    stored = db["users"].documents[0]
    assert stored["is_admin"] is True
    assert stored["is_active"] is True
    assert stored["hashed_password"].startswith("$2")
    assert "correct-horse" not in repr(db["operation_logs"].documents)
    assert db["operation_logs"].documents[0]["details"]["outcome"] == "CREATED"


@pytest.mark.asyncio
async def test_admin_bootstrap_reuses_only_same_active_admin():
    db = FakeDB()
    first = await bootstrap_admin(
        db,
        username="operator",
        email="operator@example.com",
        password="correct-horse-battery-staple",
        execute=True,
    )
    second = await bootstrap_admin(
        db,
        username="operator",
        email="operator@example.com",
        password="different-password-is-not-used",
        execute=True,
    )
    assert second["status"] == "REUSED"
    assert second["user_id"] == first["user_id"]
    assert len(db["users"].documents) == 1

    db["users"].documents[0]["is_admin"] = False
    with pytest.raises(AdminBootstrapConflict):
        await bootstrap_admin(
            db,
            username="operator",
            email="operator@example.com",
            password=None,
            execute=False,
        )
