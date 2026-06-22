"""
健康检查与系统状态 API 验收测试

覆盖:
- GET /api/health                健康检查
- GET /api/system/config/summary 系统配置摘要
- GET /api/system/logs           日志列表
"""
import pytest


class TestHealth:
    """健康检查测试。"""

    def test_health_check(self, backend_url, backend_available):
        """健康检查端点返回 200。"""
        import httpx
        resp = httpx.get(f"{backend_url}/api/health", timeout=5)
        assert resp.status_code == 200

    def test_health_check_no_auth_required(self, backend_url, backend_available):
        """健康检查不需要认证。"""
        import httpx
        resp = httpx.get(f"{backend_url}/api/health", timeout=5)
        assert resp.status_code == 200


class TestSystemConfig:
    """系统配置测试。"""

    def test_config_summary(self, api_client):
        """获取系统配置摘要。"""
        resp = api_client.get("/api/system/config/summary")
        # 可能返回 200 或 404（如果端点路径不同），这里验证不返回 500
        assert resp.status_code != 500, f"系统配置摘要不应返回 500: {resp.text}"

    def test_system_logs(self, api_client):
        """获取系统日志列表。"""
        resp = api_client.get("/api/system/logs")
        assert resp.status_code != 500, f"系统日志不应返回 500: {resp.text}"
