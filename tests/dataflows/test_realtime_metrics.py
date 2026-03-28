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


def test_calculate_realtime_pe_pb_with_mock_data():
    """测试实时PE/PB计算（使用mock数据）"""
    class MockCollection:
        def __init__(self, document=None):
            self.document = document

        def find_one(self, *args, **kwargs):
            return self.document

        def find(self, *args, **kwargs):
            return []

    class MockDB:
        def __init__(self):
            self.market_quotes = MockCollection(
                {
                    "code": "000001",
                    "close": 10.5,
                    "pre_close": 10.0,
                    "updated_at": "2025-10-14T10:30:00",
                }
            )
            self.stock_basic_info = MockCollection(
                {
                    "code": "000001",
                    "source": "tushare",
                    "pe_ttm": 20.0,
                    "pe": 19.5,
                    "pb": 0.5,
                    "total_mv": 100.0,
                    "total_share": 100000,
                    "updated_at": "2025-10-13T16:00:00",
                }
            )
            self.stock_financial_data = MockCollection(
                {
                    "code": "000001",
                    "report_period": "2025Q3",
                    "total_equity": 20000000000,
                }
            )

        def __getitem__(self, name):
            return getattr(self, name)

    class MockClient:
        def __init__(self):
            self.db = MockDB()

        def __getitem__(self, name):
            assert name == "tradingagents"
            return self.db

    result = calculate_realtime_pe_pb("000001", MockClient())

    assert result is not None
    assert result["price"] == 10.5
    assert result["is_realtime"] is True
    assert result["source"] == "realtime_calculated_from_market_quotes"
    assert result["pe"] == 21.0
    assert result["pb"] == 0.53
    assert result["market_cap"] == 105.0
    assert result["ttm_net_profit"] == 5.0


def test_calculate_realtime_pe_pb_missing_data():
    """测试缺少数据时的处理"""
    class MockCollection:
        def find_one(self, query):
            return None
    
    class MockDB:
        market_quotes = MockCollection()
        stock_basic_info = MockCollection()
        stock_financial_data = MockCollection()

        def __getitem__(self, name):
            return getattr(self, name)

    class MockClient:
        def __init__(self):
            self.db = MockDB()

        def __getitem__(self, name):
            return self.db
    
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
    result = get_pe_pb_with_fallback("000001", object())
    
    # 验证结果
    assert result["pe"] == 22.5
    assert result["pb"] == 3.2
    assert result["is_realtime"] == True


def test_get_pe_pb_with_fallback_to_static(monkeypatch):
    """测试降级到静态数据"""
    # Mock实时计算失败
    def mock_calculate(symbol, db_client):
        return None
    
    # Mock静态数据获取
    class MockCollection:
        def __init__(self, document):
            self.document = document

        def find_one(self, query):
            return self.document

    class MockDB:
        def __init__(self):
            self.stock_basic_info = MockCollection(
                {
                    "code": "000001",
                    "source": "tushare",
                    "pe": 20.0,
                    "pb": 3.0,
                    "pe_ttm": 21.0,
                    "pb_mrq": 3.1,
                    "updated_at": "2025-10-13T16:00:00",
                }
            )

        def __getitem__(self, name):
            return getattr(self, name)

    class MockClient:
        def __init__(self):
            self.db = MockDB()

        def __getitem__(self, name):
            return self.db
    
    import tradingagents.dataflows.realtime_metrics as metrics_module
    monkeypatch.setattr(metrics_module, "calculate_realtime_pe_pb", mock_calculate)
    
    # 执行测试
    result = get_pe_pb_with_fallback("000001", MockClient())
    
    # 验证结果
    assert result["pe"] == 20.0
    assert result["pb"] == 3.0
    assert result["is_realtime"] is False
    assert result["source"] == "daily_basic"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
