from __future__ import annotations

import socket
from pathlib import Path

import pytest
import yaml

from app.core.redis_client import _tcp_keepalive_options
from app.services.alphaguard.paper_account_service import PaperAccountService
from app.services.alphaguard.paper_policy_registry import PaperPolicyRegistry
from tests.unit.alphaguard._fakes import FakeDB


ROOT = Path(__file__).resolve().parents[3]


def test_redis_keepalive_uses_platform_socket_constants():
    options = _tcp_keepalive_options()
    expected = {
        int(getattr(socket, name))
        for name in ("TCP_KEEPIDLE", "TCP_KEEPINTVL", "TCP_KEEPCNT")
        if hasattr(socket, name)
    }
    assert set(options) == expected
    assert all(value > 0 for value in options.values())


def test_compose_passes_canonical_container_database_and_redis_hosts():
    compose = yaml.safe_load((ROOT / "docker-compose.yml").read_text("utf-8"))
    for service_name in ("backend", "queue-worker", "analysis-worker"):
        environment = compose["services"][service_name]["environment"]
        assert environment["MONGODB_HOST"] == "mongodb"
        assert environment["REDIS_HOST"] == "redis"
        assert "@mongodb:27017/" in environment["MONGODB_CONNECTION_STRING"]


@pytest.mark.asyncio
async def test_account_initialization_can_exclude_challenger_without_resetting():
    db = FakeDB()
    await PaperPolicyRegistry(db).register_builtins()
    service = PaperAccountService(db)
    selected = (
        "PAPER_QUANT",
        "PAPER_NORMAL",
        "PAPER_TOP_CONFIRMED",
    )
    created = await service.initialize_user_accounts(
        "admin-1",
        account_types=selected,
    )
    assert set(created) == set(selected)
    assert "PAPER_CHALLENGER" not in created

    before = {
        key: account.cash_available for key, account in created.items()
    }
    reused = await service.initialize_user_accounts(
        "admin-1",
        account_types=selected,
    )
    assert {
        key: account.cash_available for key, account in reused.items()
    } == before
