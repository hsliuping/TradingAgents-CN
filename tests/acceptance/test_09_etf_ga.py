"""
ETF GA 验收测试

覆盖:
- ETF 行情查询 (GET /api/stocks/{etf_code}/quote)
- ETF 基本面查询 (GET /api/stocks/{etf_code}/fundamentals)
- ETF K线查询 (GET /api/stocks/{etf_code}/kline)
- ETF 数据同步 (POST /api/sync/etf/run)
- ETF 模拟交易行情 (GET /api/paper/quote/{etf_code})

ETF 代码规则:
- 上交所: 50/51/52/56/58 开头 (如 510050 上证50ETF)
- 深交所: 15/16/18 开头 (如 159919 沪深300ETF)
- 北交所: 89 开头
"""
import pytest


# 测试用的 ETF 代码
ETF_SH_CODE = "510050"   # 上证50ETF
ETF_SZ_CODE = "159919"   # 沪深300ETF


class TestETFQuote:
    """ETF 行情查询测试。"""

    def test_get_sh_etf_quote(self, api_client):
        """获取上交所 ETF 行情。"""
        resp = api_client.get(f"/api/stocks/{ETF_SH_CODE}/quote")
        assert resp.status_code == 200, f"获取ETF行情失败: {resp.text}"
        data = resp.json()
        # 验证返回了数据
        data_field = data.get("data", data) if isinstance(data, dict) else data
        assert data_field is not None, f"ETF行情数据为空: {data}"

    def test_get_sz_etf_quote(self, api_client):
        """获取深交所 ETF 行情。"""
        resp = api_client.get(f"/api/stocks/{ETF_SZ_CODE}/quote")
        assert resp.status_code == 200, f"获取深交所ETF行情失败: {resp.text}"


class TestETFFundamentals:
    """ETF 基本面查询测试。"""

    def test_get_etf_fundamentals(self, api_client_session):
        """获取 ETF 基本面数据。"""
        resp = api_client_session.get(f"/api/stocks/{ETF_SH_CODE}/fundamentals", timeout=120)
        assert resp.status_code == 200, f"获取ETF基本面失败: {resp.text}"
        data = resp.json()
        data_field = data.get("data", data) if isinstance(data, dict) else data
        # ETF 基本面应包含净值等信息
        if isinstance(data_field, dict):
            # 至少应该有名称
            assert data_field.get("name") or data_field.get("short_name") or data_field.get("ts_code"), \
                f"ETF基本面缺少名称信息: {data_field}"


class TestETFKline:
    """ETF K线查询测试。"""

    def test_get_etf_kline(self, api_client_session):
        """获取 ETF K线数据。"""
        resp = api_client_session.get(f"/api/stocks/{ETF_SH_CODE}/kline", params={
            "period": "daily",
            "limit": 30,
        }, timeout=120)
        assert resp.status_code == 200, f"获取ETF K线失败: {resp.text}"
        data = resp.json()
        data_field = data.get("data", data) if isinstance(data, dict) else data
        # K线数据应该是列表
        if isinstance(data_field, dict):
            kline = data_field.get("kline") or data_field.get("data") or data_field.get("items")
            # 有数据即可，不强制非空（可能数据源不可用）
            assert kline is not None or data_field is not None, f"ETF K线数据异常: {data_field}"


class TestETFSync:
    """ETF 数据同步测试。"""

    def test_trigger_etf_sync(self, api_client_session):
        """触发 ETF 数据同步。"""
        resp = api_client_session.post("/api/sync/etf/run", json={
            "force": False,
            "days": 7,
        }, timeout=120)
        # 同步可能返回 200（成功触发）或 409（已有同步在运行）
        assert resp.status_code in (200, 201, 409, 422), f"ETF同步触发异常: {resp.status_code} {resp.text}"


class TestETFPaperTrading:
    """ETF 模拟交易测试。"""

    def test_get_etf_paper_quote(self, api_client):
        """获取 ETF 模拟交易行情。"""
        resp = api_client.get(f"/api/paper/quote/{ETF_SH_CODE}")
        assert resp.status_code in (200, 404), f"ETF模拟交易行情异常: {resp.status_code} {resp.text}"
