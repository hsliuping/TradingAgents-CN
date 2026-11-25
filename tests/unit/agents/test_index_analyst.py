"""
大盘/指数分析师单元测试
"""

import pytest
import asyncio
from unittest.mock import Mock, patch, AsyncMock
import pandas as pd


class TestIndexTools:
    """测试指数分析工具函数"""
    
    @pytest.fixture
    def mock_tushare_provider(self):
        """模拟 Tushare 提供器"""
        mock_provider = Mock()
        mock_provider.is_available.return_value = True
        return mock_provider
    
    @pytest.mark.asyncio
    async def test_get_index_trend(self, mock_tushare_provider):
        """测试指数走势分析"""
        # 模拟指数日线数据
        mock_tushare_provider.get_index_daily = AsyncMock(return_value=pd.DataFrame({
            'trade_date': [f'202412{i:02d}' for i in range(1, 22)],
            'close': [3000 + i * 10 for i in range(21)],
            'high': [3010 + i * 10 for i in range(21)],
            'low': [2990 + i * 10 for i in range(21)],
            'pct_chg': [0.5] * 21
        }))
        
        with patch('core.tools.index_tools._get_tushare_provider', return_value=mock_tushare_provider):
            from core.tools.index_tools import get_index_trend
            
            result = await get_index_trend("2024-12-21")
            
            assert "主要指数走势分析" in result
            assert "上证指数" in result or "暂无数据" in result
    
    @pytest.mark.asyncio
    async def test_get_market_breadth(self, mock_tushare_provider):
        """测试市场宽度分析"""
        mock_tushare_provider.get_daily_info = AsyncMock(return_value=pd.DataFrame({
            'trade_date': ['20241221'],
            'up_count': [2500],
            'down_count': [1500],
            'amount': [500000000000]  # 5000亿
        }))
        
        with patch('core.tools.index_tools._get_tushare_provider', return_value=mock_tushare_provider):
            from core.tools.index_tools import get_market_breadth
            
            result = await get_market_breadth("2024-12-21")
            
            assert "市场宽度分析" in result
            assert "涨跌统计" in result or "暂无" in result
    
    @pytest.mark.asyncio
    async def test_get_market_environment(self, mock_tushare_provider):
        """测试市场环境评估"""
        mock_tushare_provider.get_index_dailybasic = AsyncMock(return_value=pd.DataFrame({
            'ts_code': ['000001.SH'],
            'pe': [12.5],
            'pb': [1.2],
            'turnover_rate': [0.8],
            'total_mv': [50000000000000]  # 50万亿
        }))
        mock_tushare_provider.get_index_daily = AsyncMock(return_value=pd.DataFrame({
            'trade_date': [f'202412{i:02d}' for i in range(1, 22)],
            'close': [3000 + i for i in range(21)],
            'pct_chg': [0.5, -0.3, 0.2, -0.1, 0.4] * 4 + [0.3]
        }))
        
        with patch('core.tools.index_tools._get_tushare_provider', return_value=mock_tushare_provider):
            from core.tools.index_tools import get_market_environment
            
            result = await get_market_environment("2024-12-21")
            
            assert "市场环境评估" in result
    
    @pytest.mark.asyncio
    async def test_identify_market_cycle(self, mock_tushare_provider):
        """测试市场周期识别"""
        # 创建模拟的上涨趋势数据
        mock_tushare_provider.get_index_daily = AsyncMock(return_value=pd.DataFrame({
            'trade_date': [f'2024{(i//30+1):02d}{(i%30+1):02d}' for i in range(120)],
            'close': [3000 + i * 5 for i in range(120)],
            'high': [3010 + i * 5 for i in range(120)],
            'low': [2990 + i * 5 for i in range(120)],
        }))
        
        with patch('core.tools.index_tools._get_tushare_provider', return_value=mock_tushare_provider):
            from core.tools.index_tools import identify_market_cycle
            
            result = await identify_market_cycle("2024-12-21")
            
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

