from __future__ import annotations

import logging

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

import app.routers.notifications as notifications_router
from app.models.notification import NotificationList
from app.routers.auth_db import get_current_user


class _NotificationService:
    def __init__(
        self,
        *,
        list_result: NotificationList | None = None,
        unread_result: int = 0,
        list_error: Exception | None = None,
        unread_error: Exception | None = None,
    ) -> None:
        self.list_result = list_result
        self.unread_result = unread_result
        self.list_error = list_error
        self.unread_error = unread_error
        self.list_calls: list[dict[str, object]] = []
        self.unread_calls: list[str] = []

    async def list(self, **kwargs):
        self.list_calls.append(kwargs)
        if self.list_error is not None:
            raise self.list_error
        assert self.list_result is not None
        return self.list_result

    async def unread_count(self, user_id: str) -> int:
        self.unread_calls.append(user_id)
        if self.unread_error is not None:
            raise self.unread_error
        return self.unread_result


@pytest.fixture
def client_for(monkeypatch):
    clients: list[TestClient] = []

    def build(service: _NotificationService) -> TestClient:
        monkeypatch.setattr(
            notifications_router,
            "get_notifications_service",
            lambda: service,
        )
        app = FastAPI()
        app.include_router(notifications_router.router, prefix="/api")
        app.dependency_overrides[get_current_user] = lambda: {"id": "user-1"}
        client = TestClient(app)
        clients.append(client)
        return client

    yield build

    for client in clients:
        client.close()


def test_notification_list_normal_response_preserves_contract(client_for):
    service = _NotificationService(
        list_result=NotificationList(items=[], total=3, page=2, page_size=10)
    )
    client = client_for(service)

    response = client.get(
        "/api/notifications",
        params={
            "status": "unread",
            "type": "alert",
            "page": 2,
            "page_size": 10,
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["message"] == "ok"
    assert body["data"] == {
        "items": [],
        "total": 3,
        "page": 2,
        "page_size": 10,
        "service_status": "READY",
        "error_code": None,
    }
    assert service.list_calls == [
        {
            "user_id": "user-1",
            "status": "unread",
            "ntype": "alert",
            "page": 2,
            "page_size": 10,
        }
    ]


def test_notification_unread_count_normal_response_preserves_contract(client_for):
    service = _NotificationService(unread_result=7)
    client = client_for(service)

    response = client.get("/api/notifications/unread_count")

    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["message"] == "ok"
    assert body["data"] == {
        "count": 7,
        "service_status": "READY",
        "error_code": None,
    }
    assert service.unread_calls == ["user-1"]


def test_notification_list_failure_returns_stable_degraded_response(
    client_for, caplog
):
    internal_detail = "mongodb://admin:secret@db.internal token=private-token"
    service = _NotificationService(list_error=RuntimeError(internal_detail))
    client = client_for(service)

    with caplog.at_level(logging.WARNING, logger="webapi.notifications"):
        response = client.get(
            "/api/notifications",
            params={"page": 3, "page_size": 5},
        )

    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["data"] == {
        "items": [],
        "total": 0,
        "page": 3,
        "page_size": 5,
        "service_status": "DEGRADED",
        "error_code": "NOTIFICATION_SERVICE_UNAVAILABLE",
    }
    assert body["message"] == "通知服务暂不可用，不影响AlphaGuard核心功能"
    assert internal_detail not in response.text
    assert "secret" not in caplog.text
    assert "private-token" not in caplog.text
    assert "db.internal" not in caplog.text
    assert "error_type=RuntimeError" in caplog.text


def test_notification_unread_count_failure_returns_stable_degraded_response(
    client_for, caplog
):
    internal_detail = "database query failed password=hidden-value"
    service = _NotificationService(unread_error=ValueError(internal_detail))
    client = client_for(service)

    with caplog.at_level(logging.WARNING, logger="webapi.notifications"):
        response = client.get("/api/notifications/unread_count")

    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["data"] == {
        "count": 0,
        "service_status": "DEGRADED",
        "error_code": "NOTIFICATION_SERVICE_UNAVAILABLE",
    }
    assert body["message"] == "通知服务暂不可用，不影响AlphaGuard核心功能"
    assert internal_detail not in response.text
    assert "hidden-value" not in caplog.text
    assert "database query failed" not in caplog.text
    assert "error_type=ValueError" in caplog.text
