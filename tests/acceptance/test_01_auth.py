"""
认证模块 API 验收测试

覆盖:
- POST /api/auth/login  登录
- GET  /api/auth/me     获取当前用户信息
- POST /api/auth/logout 登出
- POST /api/auth/login  错误凭据拒绝

API 统一响应结构: {success: bool, data: ..., message: str}
"""
import httpx
import pytest


def _unwrap(resp_json):
    """解包统一响应结构，返回 data 字段。"""
    if isinstance(resp_json, dict) and "data" in resp_json:
        return resp_json["data"]
    return resp_json


class TestLogin:
    """登录接口测试。"""

    def test_login_success(self, backend_url, backend_available):
        """正确凭据登录成功，返回 access_token 和 user 信息。"""
        resp = httpx.post(
            f"{backend_url}/api/auth/login",
            json={"username": "admin", "password": "admin123"},
            timeout=10,
        )
        assert resp.status_code == 200
        data = _unwrap(resp.json())
        assert "access_token" in data, f"响应缺少 access_token: {data}"
        assert "refresh_token" in data, f"响应缺少 refresh_token: {data}"
        assert "user" in data, f"响应缺少 user: {data}"
        assert data["user"]["username"] == "admin"

    def test_login_wrong_password(self, backend_url, backend_available):
        """错误密码登录失败。"""
        resp = httpx.post(
            f"{backend_url}/api/auth/login",
            json={"username": "admin", "password": "wrong_password"},
            timeout=10,
        )
        assert resp.status_code in (401, 403, 400), f"错误密码应被拒绝: {resp.status_code}"

    def test_login_nonexistent_user(self, backend_url, backend_available):
        """不存在的用户登录失败。"""
        resp = httpx.post(
            f"{backend_url}/api/auth/login",
            json={"username": "nonexistent_user_xyz", "password": "any"},
            timeout=10,
        )
        assert resp.status_code in (401, 403, 400)

    def test_login_missing_fields(self, backend_url, backend_available):
        """缺少必填字段返回 422。"""
        resp = httpx.post(
            f"{backend_url}/api/auth/login",
            json={"username": "admin"},
            timeout=10,
        )
        assert resp.status_code == 422


class TestAuthMe:
    """获取当前用户信息测试。"""

    def test_get_me_with_token(self, api_client):
        """带有效 token 获取用户信息成功。"""
        resp = api_client.get("/api/auth/me")
        assert resp.status_code == 200
        data = _unwrap(resp.json())
        assert "username" in data, f"响应缺少 username: {data}"

    def test_get_me_without_token(self, backend_url, backend_available):
        """无 token 访问 /me 返回 401。"""
        resp = httpx.get(f"{backend_url}/api/auth/me", timeout=10)
        assert resp.status_code == 401

    def test_get_me_with_invalid_token(self, backend_url, backend_available):
        """无效 token 访问 /me 返回 401。"""
        resp = httpx.get(
            f"{backend_url}/api/auth/me",
            headers={"Authorization": "Bearer invalid_token_xyz"},
            timeout=10,
        )
        assert resp.status_code == 401


class TestLogout:
    """登出接口测试。"""

    def test_logout_success(self, backend_url, backend_available):
        """登录后登出成功。"""
        # 先登录
        login_resp = httpx.post(
            f"{backend_url}/api/auth/login",
            json={"username": "admin", "password": "admin123"},
            timeout=10,
        )
        token = _unwrap(login_resp.json())["access_token"]
        # 登出
        resp = httpx.post(
            f"{backend_url}/api/auth/logout",
            headers={"Authorization": f"Bearer {token}"},
            timeout=10,
        )
        assert resp.status_code == 200
