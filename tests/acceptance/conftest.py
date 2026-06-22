"""
验收测试 - 后端 API 自动化测试框架

使用 pytest + httpx 对运行中的后端服务做端到端 API 验收测试。
测试前需启动后端: python -m uvicorn app.main:app --port 8000
"""
import os
import pytest
import httpx


# ==================== 配置 ====================

BACKEND_BASE_URL = os.getenv("TEST_BACKEND_URL", "http://localhost:8000")
TEST_USERNAME = os.getenv("TEST_USERNAME", "admin")
TEST_PASSWORD = os.getenv("TEST_PASSWORD", "admin123")


# ==================== Fixtures ====================

@pytest.fixture(scope="session")
def backend_url() -> str:
    """后端服务基础 URL。"""
    return BACKEND_BASE_URL


@pytest.fixture(scope="session")
def backend_available(backend_url) -> bool:
    """检查后端服务是否可用（会话级，只检查一次）。"""
    try:
        resp = httpx.get(f"{backend_url}/api/health", timeout=5)
        if resp.status_code == 200:
            return True
    except Exception:
        pass
    pytest.skip(f"后端服务不可用: {backend_url}，请先启动后端服务")


@pytest.fixture(scope="session")
def auth_token(backend_url, backend_available) -> str:
    """登录获取 access_token（会话级，所有测试共用一个 token）。"""
    resp = httpx.post(
        f"{backend_url}/api/auth/login",
        json={"username": TEST_USERNAME, "password": TEST_PASSWORD},
        timeout=10,
    )
    assert resp.status_code == 200, f"登录失败: {resp.status_code} {resp.text}"
    body = resp.json()
    # API 统一响应结构: {success, data: {access_token, refresh_token, user}, message}
    data = body.get("data", body)
    token = data.get("access_token")
    assert token, f"登录响应中无 access_token: {body}"
    return token


@pytest.fixture(scope="session")
def auth_headers(auth_token) -> dict:
    """带认证的请求头。"""
    return {"Authorization": f"Bearer {auth_token}"}


@pytest.fixture
def api_client(backend_url, auth_headers) -> httpx.Client:
    """带认证的 HTTP 客户端（函数级，每个测试独立）。"""
    with httpx.Client(base_url=backend_url, headers=auth_headers, timeout=30) as client:
        yield client


@pytest.fixture(scope="session")
def api_client_session(backend_url, auth_headers) -> httpx.Client:
    """带认证的 HTTP 客户端（会话级，跨测试共享状态时使用）。"""
    with httpx.Client(base_url=backend_url, headers=auth_headers, timeout=30) as client:
        yield client
