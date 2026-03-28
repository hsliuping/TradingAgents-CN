import sys
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

# Ensure project root on path
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.routers import config as config_router  # noqa: E402
from app.routers.auth_db import get_current_user  # noqa: E402
from app.models.config import SystemConfig, DataSourceConfig, DataSourceType  # noqa: E402
from app.models.user import User  # noqa: E402
from app.services.config_service import config_service  # noqa: E402


@pytest.fixture()
def test_app():
    app = FastAPI()
    app.include_router(config_router.router, prefix="/api")

    # Override auth dependency
    def _fake_user():
        return User(username="tester", email="t@example.com", hashed_password="x")

    app.dependency_overrides[get_current_user] = _fake_user

    with TestClient(app) as client:
        yield client


def test_add_llm_provider_keeps_valid_api_key(monkeypatch, test_app: TestClient):
    captured = {}

    async def mock_add_llm_provider(provider):
        captured["api_key"] = provider.api_key
        return "mock-id-123"

    monkeypatch.setattr(config_service, "add_llm_provider", mock_add_llm_provider)

    payload = {
        "name": "openai",
        "display_name": "OpenAI",
        "description": "desc",
        "website": "https://openai.com",
        "api_doc_url": None,
        "logo_url": None,
        "is_active": True,
        "supported_features": [],
        "default_base_url": None,
        "api_key": "sk-test-placeholder-provider-123456",
        "api_secret": None,
        "extra_config": {}
    }

    resp = test_app.post("/api/config/llm/providers", json=payload)
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data.get("success") is True
    assert captured.get("api_key") == "sk-test-placeholder-provider-123456"


def test_add_llm_provider_rejects_invalid_api_key(monkeypatch, test_app: TestClient):
    async def mock_add_llm_provider(provider):
        raise AssertionError("should not be called")

    monkeypatch.setattr(config_service, "add_llm_provider", mock_add_llm_provider)

    payload = {
        "name": "openai",
        "display_name": "OpenAI",
        "description": "desc",
        "website": "https://openai.com",
        "api_doc_url": None,
        "logo_url": None,
        "is_active": True,
        "supported_features": [],
        "default_base_url": None,
        "api_key": "short",
        "api_secret": None,
        "extra_config": {}
    }

    resp = test_app.post("/api/config/llm/providers", json=payload)
    assert resp.status_code == 400, resp.text
    assert "API Key 无效" in resp.text


def test_update_llm_provider_sanitizes_api_key(monkeypatch, test_app: TestClient):
    captured = {}

    async def mock_update_llm_provider(provider_id, update_data):
        captured["provider_id"] = provider_id
        captured["has_api_key_field"] = "api_key" in update_data
        return True

    monkeypatch.setattr(config_service, "update_llm_provider", mock_update_llm_provider)

    payload = {
        "name": "openai",
        "display_name": "OpenAI",
        "description": "desc",
        "website": "https://openai.com",
        "api_doc_url": None,
        "logo_url": None,
        "is_active": True,
        "supported_features": [],
        "default_base_url": None,
        "api_key": "your-openai-api-key",
        "api_secret": None,
        "extra_config": {"k": "v"}
    }

    resp = test_app.put("/api/config/llm/providers/abc123", json=payload)
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data.get("success") is True
    assert captured.get("provider_id") == "abc123"
    # 占位符在更新时应被忽略，避免覆盖已有真实配置
    assert captured.get("has_api_key_field") is False


def test_get_datasource_configs_include_key_source(monkeypatch, test_app: TestClient):
    async def mock_get_system_config():
        return SystemConfig(
            config_name="test",
            config_type="system",
            llm_configs=[],
            data_source_configs=[
                DataSourceConfig(
                    name="Tushare",
                    type=DataSourceType.TUSHARE,
                    api_key="db-valid-token-123456",
                    enabled=True,
                ),
                DataSourceConfig(
                    name="AKShare",
                    type=DataSourceType.AKSHARE,
                    enabled=True,
                ),
            ],
            database_configs=[],
            system_settings={},
            version=1,
            is_active=True,
        )

    monkeypatch.setattr(config_service, "get_system_config", mock_get_system_config)

    resp = test_app.get("/api/config/datasource")
    assert resp.status_code == 200, resp.text
    data = resp.json()

    tushare = next(item for item in data if item["name"] == "Tushare")
    akshare = next(item for item in data if item["name"] == "AKShare")

    assert tushare["api_key"].startswith("db-val")
    assert tushare["extra_config"]["source"] == "database"
    assert tushare["extra_config"]["has_api_key"] is True
    assert akshare["extra_config"]["has_api_key"] is False
