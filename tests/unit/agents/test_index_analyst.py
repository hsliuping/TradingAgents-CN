"""
大盘/指数分析师单元测试
"""

import pytest
import pandas as pd
from unittest.mock import patch


def _make_index_daily_frame(rows: int, base_close: float = 3000.0, step: float = 10.0,
                            pct_chg: float = 0.5) -> pd.DataFrame:
    """构造指数日线测试数据（升序，工具内部自行排序）"""
    dates = [f"2024{(i // 28) + 1:02d}{(i % 28) + 1:02d}" for i in range(rows)]
    close = [base_close + i * step for i in range(rows)]
    return pd.DataFrame({
        "trade_date": dates,
        "close": close,
        "high": [c + step for c in close],
        "low": [c - step for c in close],
        "pct_chg": [pct_chg] * rows,
    })


def _capability_stub(frames: dict):
    """构造 _query_capability 替身：按 capability_id 分发返回，未登记的能力返回空表"""
    async def fake_query(capability_id: str, **params) -> pd.DataFrame:
        return frames.get(capability_id, pd.DataFrame())
    return fake_query


class TestIndexTools:
    """测试指数分析工具函数（能力取数范式：monkeypatch _query_capability）"""

    @pytest.mark.asyncio
    async def test_get_index_trend(self, monkeypatch):
        """测试指数走势分析"""
        import core.tools.index_tools as index_tools

        monkeypatch.setattr(
            index_tools, "_query_capability",
            _capability_stub({"index_daily": _make_index_daily_frame(21)}),
        )

        result = await index_tools.get_index_trend("2024-12-21")

        assert "主要指数走势分析" in result
        assert "上证指数" in result

    @pytest.mark.asyncio
    async def test_get_market_breadth(self, monkeypatch):
        """测试市场宽度分析（daily_info 能力路径）"""
        import core.tools.index_tools as index_tools

        daily_info = pd.DataFrame([
            {"ts_code": "SH_MARKET", "amount": 3000.0, "vol": 250.0, "com_count": 2300},
            {"ts_code": "SZ_MARKET", "amount": 2000.0, "vol": 296.68, "com_count": 3100},
        ])
        monkeypatch.setattr(
            index_tools, "_query_capability",
            _capability_stub({"daily_info": daily_info}),
        )

        result = await index_tools.get_market_breadth("2024-12-21")

        assert "市场宽度分析" in result
        assert "总成交额" in result
        assert "暂无" not in result

    @pytest.mark.asyncio
    async def test_get_market_environment(self, monkeypatch):
        """测试市场环境评估（index_daily + index_dailybasic 能力路径）"""
        import core.tools.index_tools as index_tools

        frames = {
            "index_daily": _make_index_daily_frame(21, base_close=3000.0, step=1.0, pct_chg=0.3),
            "index_dailybasic": pd.DataFrame([
                {"turnover_rate": 0.8, "total_mv": 5.0e13},  # 万元 -> /1e8 = 50 万亿
            ]),
        }
        monkeypatch.setattr(index_tools, "_query_capability", _capability_stub(frames))

        result = await index_tools.get_market_environment("2024-12-21")

        assert "市场环境评估" in result

    @pytest.mark.asyncio
    async def test_identify_market_cycle(self, monkeypatch):
        """测试市场周期识别"""
        import core.tools.index_tools as index_tools

        monkeypatch.setattr(
            index_tools, "_query_capability",
            _capability_stub({"index_daily": _make_index_daily_frame(120, base_close=3000.0, step=5.0)}),
        )

        result = await index_tools.identify_market_cycle("2024-12-21")

        assert "市场周期判断" in result


class TestIndexAnalystAgent:
    """测试大盘分析师 Agent"""

    def test_agent_metadata(self):
        """测试 Agent 元数据"""
        from core.agents.adapters.index_analyst import IndexAnalystAgent

        metadata = IndexAnalystAgent.get_metadata()

        assert metadata.id == "index_analyst"
        assert metadata.name == "大盘/指数分析师"
        assert "大盘" in metadata.tags or "指数" in metadata.tags

    def test_agent_execute(self):
        """测试 Agent 执行"""
        from core.agents.adapters.index_analyst import IndexAnalystAgent

        agent = IndexAnalystAgent()

        # 模拟分析工具
        mock_report = "测试大盘分析报告"
        with patch('core.tools.index_tools.analyze_index_sync', return_value=mock_report):
            state = {
                "trade_date": "2024-12-21",
                "messages": []
            }

            result = agent.execute(state)

            assert "index_report" in result
            assert result["index_report"] == mock_report


class TestAgentStateIndexField:
    """测试 AgentState 中的 index_report 字段"""

    def test_index_report_field_exists(self):
        """测试 index_report 字段存在"""
        from tradingagents.agents.utils.agent_states import AgentState

        annotations = AgentState.__annotations__

        assert 'index_report' in annotations


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
