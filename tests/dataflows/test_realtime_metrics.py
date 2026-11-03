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


class _EmptyCollection:
    def find_one(self, *args, **kwargs):
        return None

    def find(self, *args, **kwargs):
        return []


class _NamedCollection:
    def __init__(self, docs):
        self.docs = docs

    def find_one(self, query, *args, **kwargs):
        for doc in self.docs:
            if all(doc.get(k) == v for k, v in query.items()):
                return doc
        for doc in self.docs:
            if "source" not in query and doc.get("code") == query.get("code"):
                return doc
        return None

    def find(self, query, projection=None):
        return [
            doc for doc in self.docs
            if all(doc.get(k) == v for k, v in query.items())
        ]


class _MockDB:
    def __init__(self, quotes=None, basics=None, financials=None):
        self.market_quotes = _NamedCollection(quotes or [])
        self.stock_basic_info = _NamedCollection(basics or [])
        self.stock_financial_data = _NamedCollection(financials or [])


class _MockClient:
    def __init__(self, databases):
        self.databases = databases
        self.accessed = []

    def __getitem__(self, name):
        self.accessed.append(name)
        return self.databases.get(name, _MockDB())


def test_calculate_realtime_pe_pb_with_mock_data(monkeypatch):
    """测试实时PE/PB计算（使用mock数据）"""
    monkeypatch.setattr(
        "app.core.config.settings",
        type("FakeSettings", (), {"MONGODB_DATABASE": "tradingagentscn"})(),
    )

    client = _MockClient({
        "tradingagentscn": _MockDB(
            quotes=[{
                "code": "000001",
                "close": 11.0,
                "pre_close": 10.0,
                "updated_at": "2025-10-14T10:30:00",
            }],
            basics=[{
                "code": "000001",
                "source": "tushare",
                "pe": 10.0,
                "pb": 2.0,
                "pe_ttm": 10.0,
                "total_mv": 10.0,
                "total_share": 10000.0,
            }],
        )
    })

    result = calculate_realtime_pe_pb("000001", client)

    assert result is not None
    assert result["price"] == 11.0
    assert result["is_realtime"] is True
    # 昨日市值=10000万股*10元/10000=10亿，TTM利润=10/10=1亿
    # 实时市值=11元*10000万股/10000=11亿，动态PE=11
    assert result["pe"] == 11.0
    assert client.accessed == ["tradingagentscn"]


def test_resolve_mongodb_name_prefers_settings(monkeypatch):
    """PE 计算必须使用配置库名，不能写死 tradingagents。"""
    from tradingagents.dataflows.realtime_metrics import _resolve_mongodb_name

    class FakeSettings:
        MONGODB_DATABASE = "tradingagentscn"

    import app.core.config as config_module
    monkeypatch.setattr(config_module, "settings", FakeSettings())

    assert _resolve_mongodb_name(None) == "tradingagentscn"


def test_calculate_realtime_pe_pb_uses_configured_database(monkeypatch):
    """查行情时必须落到配置库，而不是空的 tradingagents。"""
    monkeypatch.setattr(
        "app.core.config.settings",
        type("FakeSettings", (), {"MONGODB_DATABASE": "tradingagentscn"})(),
    )

    client = _MockClient({
        "tradingagents": _MockDB(),
        "tradingagentscn": _MockDB(
            quotes=[{
                "code": "002415",
                "close": 32.34,
                "pre_close": 32.82,
                "updated_at": "2026-10-21T07:20:30",
            }],
            basics=[{
                "code": "002415",
                "source": "tushare",
                "pe": 17.1,
                "pb": 3.6,
                "pe_ttm": 17.1,
                "total_mv": 3000.0,
                "total_share": 92800.0,
            }],
        ),
    })

    result = calculate_realtime_pe_pb("002415", client)

    assert client.accessed == ["tradingagentscn"]
    assert result is not None
    assert result["price"] == 32.34


def test_calculate_realtime_pe_pb_missing_data(monkeypatch):
    """测试缺少数据时的处理"""
    monkeypatch.setattr(
        "app.core.config.settings",
        type("FakeSettings", (), {"MONGODB_DATABASE": "tradingagentscn"})(),
    )
    result = calculate_realtime_pe_pb("999999", _MockClient({"tradingagentscn": _MockDB()}))
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
    monkeypatch.setattr(
        "app.core.config.settings",
        type("FakeSettings", (), {"MONGODB_DATABASE": "tradingagentscn"})(),
    )

    def mock_calculate(symbol, db_client):
        return None

    import tradingagents.dataflows.realtime_metrics as metrics_module
    monkeypatch.setattr(metrics_module, "calculate_realtime_pe_pb", mock_calculate)

    client = _MockClient({
        "tradingagentscn": _MockDB(
            basics=[{
                "code": "000001",
                "source": "tushare",
                "pe": 20.0,
                "pb": 3.0,
                "pe_ttm": 21.0,
                "pb_mrq": 3.1,
                "updated_at": "2025-10-13T16:00:00",
            }]
        )
    })

    result = get_pe_pb_with_fallback("000001", client)

    assert result["pe"] == 20.0
    assert result["pb"] == 3.0
    assert result["is_realtime"] is False
    assert result["source"] == "daily_basic"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

