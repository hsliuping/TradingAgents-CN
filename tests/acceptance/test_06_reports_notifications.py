"""
报告与通知 API 验收测试

覆盖:
- GET  /api/reports/list           报告列表
- GET  /api/notifications          通知列表
- GET  /api/usage/statistics       使用统计
"""
import pytest


class TestReports:
    """报告测试。"""

    def test_get_reports_list(self, api_client):
        """获取报告列表。"""
        resp = api_client.get("/api/reports/list")
        assert resp.status_code == 200, f"获取报告列表失败: {resp.text}"

    def test_get_reports_list_with_pagination(self, api_client):
        """分页获取报告列表。"""
        resp = api_client.get("/api/reports/list", params={
            "page": 1,
            "page_size": 10,
        })
        assert resp.status_code == 200


class TestNotifications:
    """通知测试。"""

    def test_get_notifications(self, api_client):
        """获取通知列表。"""
        resp = api_client.get("/api/notifications")
        assert resp.status_code == 200, f"获取通知列表失败: {resp.text}"

    def test_get_unread_count(self, api_client):
        """获取未读通知数量。"""
        resp = api_client.get("/api/notifications/unread-count")
        assert resp.status_code in (200, 404), f"获取未读数量异常: {resp.status_code}"


class TestUsageStatistics:
    """使用统计测试。"""

    def test_get_usage_statistics(self, api_client):
        """获取使用统计。"""
        resp = api_client.get("/api/usage/statistics")
        assert resp.status_code == 200, f"获取使用统计失败: {resp.text}"

    def test_get_token_statistics(self, api_client):
        """获取 Token 使用统计。"""
        resp = api_client.get("/api/usage/token-statistics")
        assert resp.status_code in (200, 404), f"获取Token统计异常: {resp.status_code}"
