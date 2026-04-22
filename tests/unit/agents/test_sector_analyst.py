"""
板块分析师单元测试
"""

import pytest
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
            'ts_code': ['881155.TI', '885611.TI'],
            'con_name': ['平安银行', '平安银行']
        }))
        mock_tushare_provider.get_ths_index_list = AsyncMock(return_value=pd.DataFrame({
            'ts_code': ['881155.TI'],
            'name': ['银行']
        }))
        
        with patch('core.tools.sector_tools._get_tushare_provider', return_value=mock_tushare_provider):
            from core.tools.sector_tools import get_stock_sector_info
            
            result = await get_stock_sector_info("000001")
            
            assert result['ticker'] == "000001"
            assert result['industry'] == "银行"
            assert len(result['sectors']) == 1
            assert result['sectors'][0]['name'] == '银行'
            assert result['error'] is None
    
    @pytest.mark.asyncio
    async def test_get_sector_performance(self, mock_tushare_provider):
        """测试板块表现分析"""
        mock_tushare_provider.get_stock_industry = AsyncMock(return_value="银行")
        mock_tushare_provider.get_index_daily = AsyncMock(return_value=pd.DataFrame({
            'trade_date': ['20241202', '20241201'],
            'close': [3300, 3290],
        }))
        mock_tushare_provider.get_ths_member = AsyncMock(return_value=pd.DataFrame({
            'ts_code': ['881155.TI', '885611.TI', '700402.TI'],
            'con_name': ['平安银行', '平安银行', '平安银行']
        }))
        mock_tushare_provider.get_ths_index_list = AsyncMock(return_value=pd.DataFrame({
            'ts_code': ['881155.TI', '700402.TI'],
            'name': ['银行', '商业银行(A股)']
        }))

        async def mock_get_ths_daily(ts_code, start_date=None, end_date=None):
            if ts_code == '881155.TI':
                return pd.DataFrame({
                    'trade_date': ['20241201', '20241202'],
                    'close': [100, 105],
                    'pct_change': [0, 5.0]
                })
            if ts_code == '700402.TI':
                return pd.DataFrame({
                    'trade_date': ['20241201', '20241202'],
                    'close': [200, 198],
                    'pct_change': [0, -1.0]
                })
            raise AssertionError(f"unexpected ts_code: {ts_code}")

        mock_tushare_provider.get_ths_daily = AsyncMock(side_effect=mock_get_ths_daily)
        
        with patch('core.tools.sector_tools._get_tushare_provider', return_value=mock_tushare_provider):
            from core.tools.sector_tools import get_sector_performance
            
            result = await get_sector_performance("000001", "2024-12-02")
            
            assert "板块表现分析报告" in result
            assert "银行" in result
            assert "主行业锚点: 银行" in result
            assert "请求分析日期: 2024-12-02" in result
            assert "实际板块数据日期: 2024-12-02" in result
            assert "所属行业类指数数: 2 个" in result
            assert "金融科技" not in result
            assert "仅统计同花顺行业类指数" in result
            assert "不改变主行业归属" in result
            assert mock_tushare_provider.get_ths_daily.await_count == 2

    @pytest.mark.asyncio
    async def test_get_sector_performance_discloses_fallback_date(self, mock_tushare_provider):
        """测试板块表现在请求日无稳定数据时披露实际数据日期。"""
        mock_tushare_provider.get_stock_industry = AsyncMock(return_value="银行")
        mock_tushare_provider.get_index_daily = AsyncMock(return_value=pd.DataFrame({
            'trade_date': ['20260420', '20260418'],
            'close': [3290, 3280],
        }))
        mock_tushare_provider.get_ths_member = AsyncMock(return_value=pd.DataFrame({
            'ts_code': ['881155.TI'],
            'con_name': ['平安银行'],
        }))
        mock_tushare_provider.get_ths_index_list = AsyncMock(return_value=pd.DataFrame({
            'ts_code': ['881155.TI'],
            'name': ['银行']
        }))
        mock_tushare_provider.get_ths_daily = AsyncMock(return_value=pd.DataFrame({
            'trade_date': ['20260418', '20260420'],
            'close': [100, 105],
            'pct_change': [0, 5.0],
        }))

        with patch('core.tools.sector_tools._get_tushare_provider', return_value=mock_tushare_provider):
            from core.tools.sector_tools import get_sector_performance

            result = await get_sector_performance("000001", "2026-04-21")

            assert "请求分析日期: 2026-04-21" in result
            assert "实际板块数据日期: 2026-04-20" in result
            assert "当前尚无 2026-04-21 的板块表现分析所需的当日行业类指数日频数据" in result

    @pytest.mark.asyncio
    async def test_get_sector_performance_unifies_sector_dates(self, mock_tushare_provider):
        """测试不同行业类指数更新时间不一致时统一截到同一实际数据日。"""
        mock_tushare_provider.get_stock_industry = AsyncMock(return_value="银行")
        mock_tushare_provider.get_index_daily = AsyncMock(return_value=pd.DataFrame({
            'trade_date': ['20260421', '20260420', '20260418'],
            'close': [3300, 3290, 3280],
        }))
        mock_tushare_provider.get_ths_member = AsyncMock(return_value=pd.DataFrame({
            'ts_code': ['881155.TI', '700402.TI'],
            'con_name': ['平安银行', '平安银行'],
        }))
        mock_tushare_provider.get_ths_index_list = AsyncMock(return_value=pd.DataFrame({
            'ts_code': ['881155.TI', '700402.TI'],
            'name': ['银行', '商业银行(A股)']
        }))

        async def mock_get_ths_daily(ts_code, start_date=None, end_date=None):
            if ts_code == '881155.TI':
                return pd.DataFrame({
                    'trade_date': ['20260418', '20260420', '20260421'],
                    'close': [100, 104, 110],
                    'pct_change': [0, 4.0, 5.77],
                })
            if ts_code == '700402.TI':
                return pd.DataFrame({
                    'trade_date': ['20260418', '20260420'],
                    'close': [200, 190],
                    'pct_change': [0, -5.0],
                })
            raise AssertionError(f"unexpected ts_code: {ts_code}")

        mock_tushare_provider.get_ths_daily = AsyncMock(side_effect=mock_get_ths_daily)

        with patch('core.tools.sector_tools._get_tushare_provider', return_value=mock_tushare_provider):
            from core.tools.sector_tools import get_sector_performance

            result = await get_sector_performance("000001", "2026-04-21")

            assert "实际板块数据日期: 2026-04-20" in result
            assert "以下排名已统一截取到 2026-04-20" in result
            assert "银行: 📈 +4.00% (今日: +4.00%)" in result
            assert "商业银行(A股): 📉 -5.00% (今日: -5.00%)" in result


    @pytest.mark.asyncio
    async def test_get_peer_comparison_uses_single_primary_industry_anchor(self, mock_tushare_provider):
        """测试同业对比固定使用唯一主行业锚点"""
        mock_tushare_provider.get_stock_industry = AsyncMock(return_value="银行")
        mock_tushare_provider.get_sector_stocks_daily_basic = AsyncMock(return_value=pd.DataFrame({
            'ts_code': ['000001.SZ', '600036.SH', '601398.SH'],
            'name': ['平安银行', '招商银行', '工商银行'],
            'total_mv': [21521200.0, 98890000.0, 260530000.0],
            'pe_ttm': [5.05, 6.4, 7.2],
            'pb': [0.48, 0.92, 0.71],
            'turnover_rate': [0.25, 0.31, 0.12],
        }))

        with patch('core.tools.sector_tools._get_tushare_provider', return_value=mock_tushare_provider):
            from core.tools.sector_tools import get_peer_comparison

            result = await get_peer_comparison("000001", "2024-12-02")

            assert "同业对比分析报告" in result
            assert "主行业锚点: 银行" in result
            assert "同行样本按此精确匹配" in result
            assert "行业内上市公司: 3 家" in result
            assert "市值排名: 3/3" in result

    @pytest.mark.asyncio
    async def test_get_peer_comparison_falls_back_to_latest_available_valuation_date(self, mock_tushare_provider):
        """测试同行估值数据缺失时回退到最近可用估值日期。"""
        mock_tushare_provider.get_stock_industry = AsyncMock(return_value="银行")
        mock_tushare_provider.get_index_daily = AsyncMock(return_value=pd.DataFrame({
            'trade_date': ['20260421', '20260420', '20260418'],
            'close': [3300, 3290, 3280],
        }))

        async def mock_get_sector_stocks_daily_basic(industry, trade_date):
            if trade_date == '20260421':
                return pd.DataFrame()
            if trade_date == '20260420':
                return pd.DataFrame({
                    'ts_code': ['000001.SZ', '600036.SH', '601398.SH'],
                    'name': ['平安银行', '招商银行', '工商银行'],
                    'total_mv': [21521200.0, 98890000.0, 260530000.0],
                    'pe_ttm': [5.05, 6.4, 7.2],
                    'pb': [0.48, 0.92, 0.71],
                    'turnover_rate': [0.25, 0.31, 0.12],
                })
            return pd.DataFrame()

        mock_tushare_provider.get_sector_stocks_daily_basic = AsyncMock(side_effect=mock_get_sector_stocks_daily_basic)

        with patch('core.tools.sector_tools._get_tushare_provider', return_value=mock_tushare_provider):
            from core.tools.sector_tools import get_peer_comparison

            result = await get_peer_comparison("000001", "2026-04-21")

            assert "请求分析日期: 2026-04-21" in result
            assert "估值快照日期: 2026-04-20" in result
            assert "当前尚无 2026-04-21 的同行估值所需的当日收盘后日频数据" in result

    @pytest.mark.asyncio
    async def test_get_peer_comparison_never_looks_forward_after_cutoff(self, mock_tushare_provider):
        """测试稳定数据回退后，同业估值只允许向历史回看，不能再跳回当天。"""
        mock_tushare_provider.get_stock_industry = AsyncMock(return_value="银行")
        mock_tushare_provider.get_index_daily = AsyncMock(return_value=pd.DataFrame({
            'trade_date': ['20260420', '20260418', '20260417'],
            'close': [3290, 3280, 3270],
        }))

        async def mock_get_sector_stocks_daily_basic(industry, trade_date):
            if trade_date == '20260420':
                return pd.DataFrame({
                    'ts_code': ['000001.SZ', '600036.SH'],
                    'name': ['平安银行', '招商银行'],
                    'total_mv': [21521200.0, 98890000.0],
                    'pe_ttm': [5.03, 6.40],
                    'pb': [0.48, 0.92],
                    'turnover_rate': [0.25, 0.31],
                })
            if trade_date == '20260421':
                return pd.DataFrame({
                    'ts_code': ['000001.SZ', '600036.SH'],
                    'name': ['平安银行', '招商银行'],
                    'total_mv': [21550000.0, 98950000.0],
                    'pe_ttm': [5.04, 6.41],
                    'pb': [0.49, 0.93],
                    'turnover_rate': [0.26, 0.32],
                })
            return pd.DataFrame()

        mock_tushare_provider.get_sector_stocks_daily_basic = AsyncMock(side_effect=mock_get_sector_stocks_daily_basic)

        with patch('core.tools.sector_tools._get_tushare_provider', return_value=mock_tushare_provider):
            from core.tools.sector_tools import get_peer_comparison

            result = await get_peer_comparison("000001", "2026-04-21")

            queried_dates = [call.kwargs['trade_date'] for call in mock_tushare_provider.get_sector_stocks_daily_basic.await_args_list]
            assert queried_dates[0] == '20260420'
            assert '20260421' not in queried_dates
            assert "估值快照日期: 2026-04-20" in result
            assert "5.03" in result
    
    @pytest.mark.asyncio
    async def test_get_sector_rotation(self, mock_tushare_provider):
        """测试板块轮动分析"""
        mock_tushare_provider.get_moneyflow_ind_ths = AsyncMock(return_value=pd.DataFrame({
            'ts_code': ['877035.TI', '881157.TI'],
            'industry': ['银行', '证券'],
            'pct_change': [-0.12, 1.35],
            'company_num': [84, 50],
            'net_amount': [-40.0, 49.0]
        }))
        
        with patch('core.tools.sector_tools._get_tushare_provider', return_value=mock_tushare_provider):
            from core.tools.sector_tools import get_sector_rotation
            
            result = await get_sector_rotation("2024-12-02")
            
            assert "行业轮动趋势分析" in result
            assert "数据口径: 同花顺行业资金流向（THS）" in result
            assert "银行" in result
            assert "证券" in result
            assert "+49.00亿" in result
            assert "-40.00亿" in result
            assert "成分股" not in result
            assert "资金净流入" in result or "资金净流出" in result
            mock_tushare_provider.get_moneyflow_ind_ths.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_get_sector_rotation_falls_back_to_stock_moneyflow(self, mock_tushare_provider):
        """测试行业资金流不可用时回退到个股资金流"""
        mock_tushare_provider.get_moneyflow_ind_ths = AsyncMock(return_value=pd.DataFrame())
        mock_tushare_provider.get_moneyflow_ths = AsyncMock(return_value=pd.DataFrame({
            'ts_code': ['300750.SZ', '600519.SH', '000001.SZ'],
            'name': ['宁德时代', '贵州茅台', '平安银行'],
            'pct_change': [2.1, -1.3, -0.4],
            'latest': [210.55, 1568.0, 10.25],
            'net_amount': [25600.0, -13200.0, 1800.0]
        }))

        with patch('core.tools.sector_tools._get_tushare_provider', return_value=mock_tushare_provider):
            from core.tools.sector_tools import get_sector_rotation

            result = await get_sector_rotation("2024-12-02")

            assert "数据口径: 同花顺个股资金流向（THS）回退" in result
            assert "个股资金流前列名单作为替代参考" in result
            assert "资金净流入TOP个股" in result
            assert "资金净流出TOP个股" in result
            assert "宁德时代" in result
            assert "平安银行" in result
            assert "贵州茅台" in result
            assert "+2.56亿" in result
            assert "-1.32亿" in result
            mock_tushare_provider.get_moneyflow_ind_ths.assert_awaited_once()
            mock_tushare_provider.get_moneyflow_ths.assert_awaited_once()


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

