"""
交易复盘工具集测试

测试 v2.0 工具系统中的交易复盘工具
"""

import pytest
from core.tools.registry import ToolRegistry


class TestTradeReviewTools:
    """交易复盘工具测试"""
    
    def test_tools_registered(self):
        """测试工具是否正确注册"""
        registry = ToolRegistry()
        
        # 检查工具是否存在
        tool_ids = [
            "get_trade_records",
            "build_trade_info",
            "get_account_info",
            "get_market_snapshot_for_review"
        ]
        
        for tool_id in tool_ids:
            assert registry.get_function(tool_id) is not None, f"工具 {tool_id} 未注册"
    
    def test_tool_metadata(self):
        """测试工具元数据"""
        registry = ToolRegistry()
        
        # 检查 get_account_info 工具元数据
        tool_func = registry.get_function("get_account_info")
        assert tool_func is not None
        
        # 检查工具是否有正确的元数据
        assert hasattr(tool_func, '__name__')
        assert tool_func.__name__ == 'get_account_info'
    
    def test_build_trade_info_tool(self):
        """测试 build_trade_info 工具"""
        from core.tools.implementations.trade_review import build_trade_info
        
        # 测试空数据
        result = build_trade_info([], None)
        assert result["success"] is False
        
        # 测试有效数据
        trade_records = [
            {
                "_id": "123",
                "code": "688111",
                "market": "CN",
                "side": "buy",
                "quantity": 100,
                "price": 100.0,
                "amount": 10000.0,
                "pnl": 0.0,
                "timestamp": "2025-01-01T10:00:00"
            },
            {
                "_id": "124",
                "code": "688111",
                "market": "CN",
                "side": "sell",
                "quantity": 100,
                "price": 110.0,
                "amount": 11000.0,
                "pnl": 1000.0,
                "timestamp": "2025-01-10T10:00:00"
            }
        ]
        
        result = build_trade_info(trade_records, "688111")
        assert result["success"] is True
        
        data = result["data"]
        assert data["code"] == "688111"
        assert data["total_buy_quantity"] == 100
        assert data["total_sell_quantity"] == 100
        assert data["realized_pnl"] == 1000.0
        assert data["holding_days"] == 9
    
    def test_agent_tools_binding(self):
        """测试 Agent 工具绑定"""
        from core.agents.config import BUILTIN_AGENTS
        
        # 检查 position_analyst 是否绑定了新工具
        position_analyst = BUILTIN_AGENTS.get("position_analyst")
        assert position_analyst is not None
        
        expected_tools = [
            "get_trade_records",
            "build_trade_info",
            "get_account_info",
            "get_market_snapshot_for_review"
        ]
        
        for tool_id in expected_tools:
            assert tool_id in position_analyst.tools, \
                f"工具 {tool_id} 未绑定到 position_analyst"
        
        # 检查默认工具
        assert "build_trade_info" in position_analyst.default_tools
        assert "get_account_info" in position_analyst.default_tools


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

