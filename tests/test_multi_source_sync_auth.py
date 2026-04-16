"""
PoC test: Verify that multi_source_sync endpoints require authentication.
Before fix: all requests return 200 (no auth required).
After fix: requests without auth token return 401.
"""
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.routers.multi_source_sync import router


@pytest.fixture
def client():
    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


UNAUTH_ENDPOINTS = [
    ("GET", "/api/sync/multi-source/sources/status"),
    ("GET", "/api/sync/multi-source/sources/current"),
    ("GET", "/api/sync/multi-source/status"),
    ("POST", "/api/sync/multi-source/stock_basics/run"),
    ("POST", "/api/sync/multi-source/test-sources"),
    ("GET", "/api/sync/multi-source/recommendations"),
    ("GET", "/api/sync/multi-source/history"),
    ("DELETE", "/api/sync/multi-source/cache"),
]


@pytest.mark.parametrize("method,path", UNAUTH_ENDPOINTS)
def test_endpoints_require_auth(client, method, path):
    """All multi-source sync endpoints must return 401 without a valid token."""
    if method == "GET":
        resp = client.get(path)
    elif method == "POST":
        resp = client.post(path, json={})
    elif method == "DELETE":
        resp = client.delete(path)

    assert resp.status_code == 401, (
        f"{method} {path} returned {resp.status_code} instead of 401 — "
        "endpoint is accessible without authentication"
    )
