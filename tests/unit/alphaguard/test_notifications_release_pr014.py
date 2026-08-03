from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

import app.routers.websocket_notifications as websocket_module
from app.services.auth_service import AuthService


ROOT = Path(__file__).resolve().parents[3]


def _client(monkeypatch, user):
    async def authorized(_token_data):
        if isinstance(user, Exception):
            raise user
        return user

    monkeypatch.setattr(websocket_module, "_authorized_user", authorized)
    monkeypatch.setattr(
        websocket_module, "manager", websocket_module.ConnectionManager()
    )
    app = FastAPI()
    app.include_router(websocket_module.router)
    return TestClient(app)


def test_notification_websocket_uses_subprotocol_subject_and_database_id_alias(monkeypatch):
    client = _client(
        monkeypatch,
        SimpleNamespace(id="database-user-id", is_active=True),
    )
    token = AuthService.create_access_token("alice")
    with client.websocket_connect(
        "/ws/notifications",
        subprotocols=[websocket_module.WS_PROTOCOL, f"auth.{token}"],
    ) as websocket:
        assert websocket.accepted_subprotocol == websocket_module.WS_PROTOCOL
        message = websocket.receive_json()
        assert message["type"] == "connected"
        assert message["data"]["user_id"] == "alice"
        assert "alice" in websocket_module.manager.active_connections
        assert "database-user-id" in websocket_module.manager.active_connections


@pytest.mark.parametrize(
    ("subprotocols", "user", "expected_code"),
    [
        (None, SimpleNamespace(id="unused", is_active=True), 4401),
        ([websocket_module.WS_PROTOCOL, "auth.invalid"], SimpleNamespace(id="unused", is_active=True), 4401),
        ("valid", None, 4403),
        ("valid", RuntimeError("database down"), 1013),
    ],
)
def test_notification_websocket_classifies_auth_permission_and_service_failures(
    monkeypatch, subprotocols, user, expected_code
):
    client = _client(monkeypatch, user)
    if subprotocols == "valid":
        token = AuthService.create_access_token("alice")
        subprotocols = [websocket_module.WS_PROTOCOL, f"auth.{token}"]
    with pytest.raises(WebSocketDisconnect) as exc:
        with client.websocket_connect(
            "/ws/notifications", subprotocols=subprotocols
        ):
            pass
    assert exc.value.code == expected_code


def test_websocket_stats_expose_only_aggregate_health():
    stats = websocket_module.ConnectionManager().get_stats()
    assert {
        "connection_status",
        "total_users",
        "total_connections",
        "last_success_at",
        "last_disconnect_at",
        "connection_count",
        "auth_failure_count",
        "last_error_code",
        "degraded",
    } == set(stats)
    assert not any("token" in key.lower() or "url" in key.lower() for key in stats)
    assert "users" not in stats


def test_frontend_notification_contract_has_no_url_token_and_has_bounded_retry():
    store = (
        ROOT / "frontend/src/stores/notifications.ts"
    ).read_text(encoding="utf-8")
    header = (
        ROOT / "frontend/src/components/Layout/HeaderActions.vue"
    ).read_text(encoding="utf-8")
    backend = (
        ROOT / "app/routers/websocket_notifications.py"
    ).read_text(encoding="utf-8")
    assert "?token=" not in store
    assert "new WebSocket(wsUrl, [WS_PROTOCOL, `auth.${token}`])" in store
    assert "maxReconnectAttempts = 6" in store
    assert "connectionGeneration" in store
    assert "manuallyDisconnected" in store
    assert "核心功能不受影响" in store
    assert "通知服务已降级" in header
    assert "Query(" not in backend
    assert 'user_id = "admin"' not in backend
    assert "data={data}" not in backend
