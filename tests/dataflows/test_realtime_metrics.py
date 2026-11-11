"""
测试实时PE/PB计算功能
"""
import pytest
from tradingagents.dataflows.realtime_metrics import (
    calculate_realtime_pe_pb,
    validate_pe_pb,
    get_pe_pb_with_fallback
)


def test_validate_pe_pb():
    """测试PE/PB验证"""
    # 正常范围
    assert validate_pe_pb(20.5, 3.2) == True
    assert validate_pe_pb(50, 2.5) == True
    assert validate_pe_pb(-10, 1.5) == True  # 允许负PE（亏损企业）
    
    # PE异常
    assert validate_pe_pb(1500, 3.2) == False  # PE过大
    assert validate_pe_pb(-150, 3.2) == False  # PE过小
    
    # PB异常
    assert validate_pe_pb(20.5, 150) == False  # PB过大
    assert validate_pe_pb(20.5, 0.05) == False  # PB过小
    
    # None值
    assert validate_pe_pb(None, 3.2) == True
    assert validate_pe_pb(20.5, None) == True
    assert validate_pe_pb(None, None) == True


def test_calculate_realtime_pe_pb_with_mock_data(monkeypatch):
    """测试实时PE/PB计算（使用mock数据）"""
    # Mock MongoDB数据（对齐现役实现：market_quotes / stock_basic_info / stock_financial_data 三集合）
    class MockCollection:
        def __init__(self, name):
            self.name = name

        def find(self, query, *args, **kwargs):
            # 现役实现从 stock_basic_info 多源合并读取（find 返回记录列表）
            return [
                {
                    "code": "000001",
                    "pe_ttm": 20.0,        # 基于昨日收盘价的 TTM 市盈率
                    "pe": 20.0,
                    "pb": 5.0,
                    "total_share": 100000,  # 10万万股 = 10亿股
                }
            ]

        def find_one(self, query, *args, **kwargs):
            code = query.get("code")
            if code != "000001":
                return None
            if self.name == "market_quotes":
                # 返回实时行情
                return {
                    "code": "000001",
                    "close": 10.5,
                    "pre_close": 10.0,
                    "updated_at": "2025-10-14T10:30:00"
                }
            if self.name == "stock_financial_data":
                # 返回财务数据（净资产，单位：元）
                return {"code": "000001", "total_equity": 2_000_000_000}
            return None

    class MockDB:
        def __getattr__(self, name):
            return MockCollection(name)

    class MockClient:
        def __getitem__(self, name):
            return MockDB()

    # 执行测试
    result = calculate_realtime_pe_pb("000001", MockClient())

    # 验证结果
    assert result is not None
    assert result["price"] == 10.5
    assert result["is_realtime"] == True
    assert result["source"] == "realtime_calculated_from_market_quotes"

    # 验证PE计算（现役算法：昨日市值反推 TTM 净利润，再按实时股价重算）
    # 昨日市值 = 100000万股 × 10.0元 / 10000 = 100亿元；TTM净利润 = 100 / 20 = 5亿元
    # 实时市值 = 10.5元 × 100000万股 / 10000 = 105亿元；PE = 105 / 5 = 21
    assert result["pe"] == 21.0

    # 验证PB计算：PB = 105亿元 / 20亿元净资产 = 5.25
    assert result["pb"] == 5.25


def test_calculate_realtime_pe_pb_missing_data(monkeypatch):
    """测试缺少数据时的处理"""
    class MockCollection:
        def find_one(self, query):
            return None
    
    class MockDB:
        def __getitem__(self, name):
            return MockCollection()
    
    class MockClient:
        def __getitem__(self, name):
            return MockDB()
    
    # 执行测试
    result = calculate_realtime_pe_pb("999999", MockClient())
    
    # 验证结果
    assert result is None


def test_get_pe_pb_with_fallback_success(monkeypatch):
    """测试带降级的获取函数（成功场景）"""
    # Mock实时计算成功
    def mock_calculate(symbol, db_client):
        return {
            "pe": 22.5,
            "pb": 3.2,
            "pe_ttm": 23.1,
            "pb_mrq": 3.3,
            "source": "realtime_calculated",
            "is_realtime": True,
            "updated_at": "2025-10-14T10:30:00"
        }
    
    import tradingagents.dataflows.realtime_metrics as metrics_module
    monkeypatch.setattr(metrics_module, "calculate_realtime_pe_pb", mock_calculate)
    
    # 执行测试
    result = get_pe_pb_with_fallback("000001", None)
    
    # 验证结果
    assert result["pe"] == 22.5
    assert result["pb"] == 3.2
    assert result["is_realtime"] == True


def test_get_pe_pb_with_fallback_to_static(monkeypatch):
    """测试降级到静态数据"""
    # Mock实时计算失败
    def mock_calculate(symbol, db_client):
        return None
    
    # Mock静态数据获取（现役实现从 stock_basic_info 多源合并读取，find 返回记录列表）
    class MockCollection:
        def find(self, query, *args, **kwargs):
            return [
                {
                    "code": "000001",
                    "pe": 20.0,
                    "pb": 3.0,
                    "pe_ttm": 21.0,
                    "pb_mrq": 3.1,
                    "updated_at": "2025-10-13T16:00:00"
                }
            ]

    class MockDB:
        def __getattr__(self, name):
            return MockCollection()

    class MockClient:
        def __getitem__(self, name):
            return MockDB()
    
    import tradingagents.dataflows.realtime_metrics as metrics_module
    monkeypatch.setattr(metrics_module, "calculate_realtime_pe_pb", mock_calculate)
    
    # 执行测试
    result = get_pe_pb_with_fallback("000001", MockClient())
    
    # 验证结果
    assert result["pe"] == 20.0
    assert result["pb"] == 3.0
    assert result["is_realtime"] == False
    assert result["source"] == "daily_basic"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

