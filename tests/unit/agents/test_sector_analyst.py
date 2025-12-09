"""
板块分析师单元测试
"""

import pytest
import asyncio
from unittest.mock import Mock, patch, AsyncMock
import pandas as pd


class TestSectorTools:
    """测试板块分析工具函数"""
    
    @pytest.fixture
    def mock_tushare_provider(self):
        """模拟 Tushare 提供器"""
        mock_provider = Mock()
        mock_provider.is_available.return_value = True
        mock_provider._normalize_ts_code.side_effect = lambda x: f"{x}.SZ" if not '.' in x else x
        return mock_provider
    
    @pytest.mark.asyncio
    async def test_get_stock_sector_info(self, mock_tushare_provider):
        """测试获取股票板块信息"""
        # 设置模拟返回值
        mock_tushare_provider.get_stock_industry = AsyncMock(return_value="银行")
        mock_tushare_provider.get_ths_member = AsyncMock(return_value=pd.DataFrame({
            'ts_code': ['885691.TI', '885611.TI'],
            'name': ['银行', '金融科技']
        }))
        
        with patch('core.tools.sector_tools._get_tushare_provider', return_value=mock_tushare_provider):
            from core.tools.sector_tools import get_stock_sector_info
            
            result = await get_stock_sector_info("000001")
            
            assert result['ticker'] == "000001"
            assert result['industry'] == "银行"
            assert len(result['sectors']) == 2
            assert result['error'] is None
    
    @pytest.mark.asyncio
    async def test_get_sector_performance(self, mock_tushare_provider):
        """测试板块表现分析"""
        mock_tushare_provider.get_stock_industry = AsyncMock(return_value="银行")
        mock_tushare_provider.get_ths_member = AsyncMock(return_value=pd.DataFrame({
            'ts_code': ['885691.TI'],
            'name': ['银行']
        }))
        mock_tushare_provider.get_ths_daily = AsyncMock(return_value=pd.DataFrame({
            'trade_date': ['20241201', '20241202'],
            'close': [100, 105],
            'pct_change': [0, 5.0]
        }))
        
        with patch('core.tools.sector_tools._get_tushare_provider', return_value=mock_tushare_provider):
            from core.tools.sector_tools import get_sector_performance
            
            result = await get_sector_performance("000001", "2024-12-02")
            
            assert "板块表现分析报告" in result
            assert "银行" in result
    
    @pytest.mark.asyncio
    async def test_get_sector_rotation(self, mock_tushare_provider):
        """测试板块轮动分析"""
        mock_tushare_provider.get_moneyflow_ths = AsyncMock(return_value=pd.DataFrame({
            'ts_code': ['885691.TI', '885611.TI'],
            'name': ['银行', '科技'],
            'net_amount': [50000, -30000],
            'net_amount_rate': [2.5, -1.5]
        }))
        
        with patch('core.tools.sector_tools._get_tushare_provider', return_value=mock_tushare_provider):
            from core.tools.sector_tools import get_sector_rotation
            
            result = await get_sector_rotation("2024-12-02")
            
            assert "板块轮动趋势分析" in result
            assert "资金净流入" in result or "资金净流出" in result


class TestSectorAnalystAgent:
    """测试板块分析师 Agent"""
    
    def test_agent_metadata(self):
        """测试 Agent 元数据"""
        from core.agents.adapters.sector_analyst import SectorAnalystAgent
        
        metadata = SectorAnalystAgent.get_metadata()
        
        assert metadata.id == "sector_analyst"
        assert metadata.name == "行业/板块分析师"
        assert "行业分析" in metadata.tags
    
    def test_agent_execute(self):
        """测试 Agent 执行"""
        from core.agents.adapters.sector_analyst import SectorAnalystAgent
        
        agent = SectorAnalystAgent()
        
        # 模拟分析工具
        mock_report = "测试板块分析报告"
        with patch('core.tools.sector_tools.analyze_sector_sync', return_value=mock_report):
            state = {
                "company_of_interest": "000001",
                "trade_date": "2024-12-02",
                "messages": []
            }
            
            result = agent.execute(state)
            
            assert "sector_report" in result
            assert result["sector_report"] == mock_report


class TestAgentStateExtension:
    """测试 AgentState 扩展"""
    
    def test_sector_report_field(self):
        """测试 sector_report 字段存在"""
        from tradingagents.agents.utils.agent_states import AgentState
        
        # 检查字段注解
        annotations = AgentState.__annotations__
        
        assert 'sector_report' in annotations
        assert 'index_report' in annotations


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

