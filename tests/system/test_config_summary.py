import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.routers import system_config as system_config_router
from app.routers.auth_db import get_current_user


@pytest.fixture()
def client() -> TestClient:
    app = FastAPI()
    app.include_router(system_config_router.router, prefix="/api/system")
    with TestClient(app) as client:
        yield client


def test_config_summary_requires_auth(client: TestClient):
    resp = client.get("/api/system/config/summary")
    assert resp.status_code == 401


def test_config_summary_masks_sensitive_fields_with_auth(client: TestClient):
    client.app.dependency_overrides[get_current_user] = lambda: {
        "id": "u1",
        "username": "admin",
        "is_admin": True,
    }
    resp = client.get("/api/system/config/summary")
    assert resp.status_code == 200
    data = resp.json()

    assert "settings" in data
    s = data["settings"]

    # Sensitive keys should exist and be masked as '***' (even if original is empty)
    for key in [
        "MONGODB_PASSWORD",
        "REDIS_PASSWORD",
        "JWT_SECRET",
        "CSRF_SECRET",
        "STOCK_DATA_API_KEY",
    ]:
        assert key in s
        assert s[key] == "***"

    # Derived URIs should be present and credentials masked if any
    assert "MONGO_URI" in s
    assert "REDIS_URL" in s
    if any(x in s["MONGO_URI"] for x in ["@", ":***@"]):
        assert ":***@" in s["MONGO_URI"]
    # Redis URL 仅在配置了密码时才会出现认证段
    if "@" in s["REDIS_URL"]:
        assert "redis://:***@" in s["REDIS_URL"]

    # A few non-sensitive keys should be present for sanity
    for key in ["DEBUG", "HOST", "PORT", "MONGODB_HOST", "REDIS_HOST"]:
        assert key in s
