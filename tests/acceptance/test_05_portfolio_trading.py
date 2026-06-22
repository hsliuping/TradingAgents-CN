"""
持仓与交易计划 API 验收测试

覆盖:
- GET  /api/portfolio/positions     持仓列表
- GET  /api/paper/positions         模拟交易持仓
- GET  /api/v1/trading-systems      交易计划列表
- POST /api/v1/trading-systems      创建交易计划
- GET  /api/review/periodic/history 交易复盘历史
- POST /api/review/periodic         触发周期性复盘
"""
import pytest


class TestPortfolio:
    """持仓管理测试。"""

    def test_get_portfolio_positions(self, api_client):
        """获取持仓列表。"""
        resp = api_client.get("/api/portfolio/positions")
        assert resp.status_code == 200, f"获取持仓列表失败: {resp.text}"

    def test_get_portfolio_statistics(self, api_client):
        """获取持仓统计。"""
        resp = api_client.get("/api/portfolio/statistics")
        assert resp.status_code == 200, f"获取持仓统计失败: {resp.text}"

    def test_get_portfolio_account(self, api_client):
        """获取账户信息。"""
        resp = api_client.get("/api/portfolio/account")
        assert resp.status_code == 200, f"获取账户信息失败: {resp.text}"


class TestPaperTrading:
    """模拟交易测试。"""

    def test_get_paper_positions(self, api_client):
        """获取模拟交易持仓。"""
        resp = api_client.get("/api/paper/positions")
        assert resp.status_code == 200, f"获取模拟交易持仓失败: {resp.text}"

    def test_get_paper_account(self, api_client):
        """获取模拟交易账户。"""
        resp = api_client.get("/api/paper/account")
        assert resp.status_code == 200, f"获取模拟交易账户失败: {resp.text}"


class TestTradingSystem:
    """交易计划测试。"""

    def test_get_trading_systems(self, api_client):
        """获取交易计划列表。"""
        resp = api_client.get("/api/v1/trading-systems")
        assert resp.status_code == 200, f"获取交易计划列表失败: {resp.text}"

    def test_get_active_trading_system(self, api_client):
        """获取活跃交易计划。"""
        resp = api_client.get("/api/v1/trading-systems/active")
        assert resp.status_code in (200, 404), f"获取活跃交易计划异常: {resp.status_code}"

    def test_create_trading_system(self, api_client):
        """创建交易计划。"""
        resp = api_client.post("/api/v1/trading-systems", json={
            "name": "验收测试交易计划",
            "description": "自动化测试创建的交易计划",
            "stocks": [],
            "rules": {
                "stop_loss": {"type": "percentage", "value": 5},
                "take_profit": {"type": "percentage", "value": 10},
            },
        })
        assert resp.status_code in (200, 201, 400, 422), f"创建交易计划异常: {resp.status_code} {resp.text}"
        if resp.status_code in (200, 201):
            data = resp.json()
            data_field = data.get("data", data) if isinstance(data, dict) else data
            system_id = data_field.get("id") or data_field.get("_id") or data_field.get("system_id") if isinstance(data_field, dict) else None
            if system_id:
                api_client.delete(f"/api/v1/trading-systems/{system_id}")


class TestTradeReview:
    """交易复盘测试。"""

    def test_get_periodic_reviews(self, api_client):
        """获取周期性复盘历史。"""
        resp = api_client.get("/api/review/periodic/history")
        assert resp.status_code == 200, f"获取周期性复盘历史失败: {resp.text}"

    def test_get_review_statistics(self, api_client):
        """获取复盘统计。"""
        resp = api_client.get("/api/review/statistics")
        assert resp.status_code == 200, f"获取复盘统计失败: {resp.text}"

    def test_trigger_periodic_review(self, api_client):
        """触发周期性复盘。"""
        resp = api_client.post("/api/review/periodic", json={
            "review_type": "weekly",
        })
        assert resp.status_code in (200, 201, 400, 422), f"触发复盘异常: {resp.status_code} {resp.text}"
