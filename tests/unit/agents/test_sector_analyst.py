"""
板块分析师单元测试

数据访问统一经 DataFacade 能力查询（_query_capability），测试按 capability_id 打桩，
不感知具体数据源。
"""

import pytest
from unittest.mock import patch
import pandas as pd

import core.tools.sector_tools as sector_tools


def _single_row_industry(ts_code: str, industry: str) -> pd.DataFrame:
    """构造 stock_industry 能力的单行返回（工具侧按 DataFrame.iloc[0] 取值）"""
    return pd.DataFrame({"ts_code": [ts_code], "industry": [industry]})


class TestSectorTools:
    """测试板块分析工具函数（按能力 ID 打桩）"""

    @pytest.fixture
    def no_sector_cache(self, monkeypatch):
        """屏蔽 MongoDB 板块缓存，保证用例封闭（缓存未命中 → 走能力查询）"""
        monkeypatch.setattr(sector_tools, "_get_sector_cache_db", lambda: None)

    @pytest.mark.asyncio
    async def test_get_stock_sector_info(self, monkeypatch, no_sector_cache):
        """测试获取股票板块信息"""
        async def fake_query(capability_id: str, **params):
            if capability_id == "stock_industry":
                assert params.get("ts_code") == "000001"
                return _single_row_industry("000001.SZ", "银行")
            if capability_id == "ths_member":
                # 反向查询：个股 → 所属板块
                assert params.get("con_code") == "000001.SZ"
                return pd.DataFrame({
                    'ts_code': ['881155.TI', '885611.TI'],
                    'con_name': ['平安银行', '平安银行'],
                })
            raise AssertionError(f"unexpected capability: {capability_id}")

        monkeypatch.setattr(sector_tools, "_query_capability", fake_query)

        result = await sector_tools.get_stock_sector_info("000001")

        assert result['ticker'] == "000001"
        assert result['industry'] == "银行"
        assert len(result['sectors']) == 2
        assert result['sectors'][0]['ts_code'] == '881155.TI'
        assert result['error'] is None

    @pytest.mark.asyncio
    async def test_get_sector_performance(self, monkeypatch, no_sector_cache):
        """测试板块表现分析（行业类指数排名 + 当日涨跌）"""
        ths_daily_calls: list = []

        async def fake_query(capability_id: str, **params):
            if capability_id == "stock_industry":
                return _single_row_industry("000001.SZ", "银行")
            if capability_id == "ths_member":
                return pd.DataFrame({
                    'ts_code': ['881155.TI', '700402.TI'],
                    'con_name': ['平安银行', '平安银行'],
                })
            if capability_id == "ths_index":
                return pd.DataFrame({
                    'ts_code': ['881155.TI', '700402.TI'],
                    'name': ['银行', '商业银行(A股)'],
                    'count': [42, 60],
                })
            if capability_id == "ths_daily":
                ths_daily_calls.append(params)
                assert params['start_date'] == '20241102'
                assert params['end_date'] == '20241202'
                if params['ts_code'] == '881155.TI':
                    return pd.DataFrame({
                        'trade_date': ['20241201', '20241202'],
                        'close': [100, 105],
                        'pct_change': [0, 5.0],
                    })
                if params['ts_code'] == '700402.TI':
                    return pd.DataFrame({
                        'trade_date': ['20241201', '20241202'],
                        'close': [200, 198],
                        'pct_change': [0, -1.0],
                    })
                raise AssertionError(f"unexpected ts_code: {params['ts_code']}")
            raise AssertionError(f"unexpected capability: {capability_id}")

        monkeypatch.setattr(sector_tools, "_query_capability", fake_query)

        result = await sector_tools.get_sector_performance("000001", "2024-12-02")

        assert "📊 板块表现分析报告" in result
        assert "🏭 一级行业（tushare 宽口径）: 银行" in result
        assert "⭐ 主分析板块（最细行业指数）: 银行（42 只成分股）" in result
        assert "【行业归属分层（由细到宽）】" in result
        assert "📌 所属板块数: 2 个（按细化优先选取 2 个分析）" in result
        assert "【板块涨跌幅排行（★ 为最细行业主分析板块）】" in result
        assert "★ 1. 银行: 📈 +5.00% (今日: +5.00%)" in result
        assert "2. 商业银行(A股): 📉 -1.00% (今日: -1.00%)" in result
        assert len(ths_daily_calls) == 2

    @pytest.mark.asyncio
    async def test_get_peer_comparison(self, monkeypatch, no_sector_cache):
        """测试同业对比（无从指数命中时回退 tushare 一级行业口径）"""
        async def fake_query(capability_id: str, **params):
            if capability_id == "stock_industry":
                return _single_row_industry("000001.SZ", "银行")
            if capability_id == "ths_member":
                return pd.DataFrame()
            if capability_id == "index_daily":
                # _get_latest_trade_date 一次性取近8天上证指数
                return pd.DataFrame({
                    'trade_date': ['20241126', '20241127', '20241128', '20241202'],
                    'close': [3270, 3280, 3290, 3300],
                })
            if capability_id == "sector_stocks_daily_basic":
                assert params.get('industry') == '银行'
                return pd.DataFrame({
                    'ts_code': ['000001.SZ', '600036.SH', '601398.SH'],
                    'name': ['平安银行', '招商银行', '工商银行'],
                    'total_mv': [21521200.0, 98890000.0, 260530000.0],
                    'pe_ttm': [5.05, 6.4, 7.2],
                    'pb': [0.48, 0.92, 0.71],
                    'turnover_rate': [0.25, 0.31, 0.12],
                })
            raise AssertionError(f"unexpected capability: {capability_id}")

        monkeypatch.setattr(sector_tools, "_query_capability", fake_query)

        result = await sector_tools.get_peer_comparison("000001", "2024-12-02")

        assert "📊 同业对比分析报告" in result
        assert "🏭 行业口径: 银行（tushare 行业分类，宽口径）" in result
        assert "行业内上市公司: 3 家" in result
        assert "市值排名: 3/3" in result
        assert "PE(TTM): 5.05" in result

    @pytest.mark.asyncio
    async def test_get_peer_comparison_never_looks_forward_after_cutoff(
        self, monkeypatch, no_sector_cache
    ):
        """测试分析日未完结时估值只向历史回看，不查询未来日期"""
        basic_calls: list = []

        async def fake_query(capability_id: str, **params):
            if capability_id == "stock_industry":
                return _single_row_industry("000001.SZ", "银行")
            if capability_id == "ths_member":
                return pd.DataFrame()
            if capability_id == "index_daily":
                # 指数数据最新只到 20260420（20260421 未完结）
                return pd.DataFrame({
                    'trade_date': ['20260418', '20260420'],
                    'close': [3280, 3290],
                })
            if capability_id == "sector_stocks_daily_basic":
                basic_calls.append(params['trade_date'])
                if params['trade_date'] == '20260420':
                    return pd.DataFrame({
                        'ts_code': ['000001.SZ', '600036.SH'],
                        'name': ['平安银行', '招商银行'],
                        'total_mv': [21521200.0, 98890000.0],
                        'pe_ttm': [5.03, 6.40],
                        'pb': [0.48, 0.92],
                        'turnover_rate': [0.25, 0.31],
                    })
                return pd.DataFrame()
            raise AssertionError(f"unexpected capability: {capability_id}")

        monkeypatch.setattr(sector_tools, "_query_capability", fake_query)

        result = await sector_tools.get_peer_comparison("000001", "2026-04-21")

        assert basic_calls == ['20260420']
        assert "📅 分析日期: 2026-04-20" in result
        assert "PE(TTM): 5.03" in result

    @pytest.mark.asyncio
    async def test_get_peer_comparison_prefers_finest_industry(self, monkeypatch, no_sector_cache):
        """测试有细化行业时按最细行业指数取同业样本，而非 tushare 一级行业"""
        member_codes = ["002714.SZ", "300498.SZ", "002157.SZ", "002124.SZ", "605296.SH"]
        name_map = {
            "002714.SZ": "牧原股份",
            "300498.SZ": "温氏股份",
            "002157.SZ": "正邦科技",
            "002124.SZ": "天邦食品",
            "605296.SH": "神农集团",
        }

        async def fake_query(capability_id: str, **params):
            if capability_id == "stock_industry":
                return _single_row_industry("002714.SZ", "农业综合")
            if capability_id == "ths_member":
                if params.get("con_code") == "002714.SZ":
                    # 个股 → 板块：最细生猪养殖 + 畜牧业 + 农林牧渔业
                    return pd.DataFrame({'ts_code': ['884275.TI', '700651.TI', '700750.TI']})
                if params.get("ts_code") == "884275.TI":
                    return pd.DataFrame({'con_code': member_codes})
                raise AssertionError(f"unexpected ts_code: {params.get('ts_code')}")
            if capability_id == "ths_index":
                return pd.DataFrame({
                    'ts_code': ['884275.TI', '700651.TI', '700750.TI'],
                    'name': ['生猪养殖', '畜牧业指数', '农林牧渔业指数'],
                    'count': [11, 19, 47],
                })
            if capability_id == "index_daily":
                return pd.DataFrame({
                    'trade_date': ['20261030', '20261103'],
                    'close': [3300, 3310],
                })
            if capability_id == "daily_basic":
                assert params['trade_date'] == '20261103'
                return pd.DataFrame({
                    'ts_code': member_codes,
                    'total_mv': [26000000.0, 18000000.0, 9000000.0, 7000000.0, 5000000.0],
                    'pe_ttm': [16.03, 14.2, None, 9.8, 21.5],
                    'pb': [2.1, 1.8, 0.9, 1.1, 2.5],
                    'turnover_rate': [0.8, 0.6, 0.4, 0.5, 1.2],
                })
            raise AssertionError(f"unexpected capability: {capability_id}")

        monkeypatch.setattr(sector_tools, "_query_capability", fake_query)
        monkeypatch.setattr(
            sector_tools, "_stock_name_by_ts_code", lambda code: name_map.get(code, code)
        )

        result = await sector_tools.get_peer_comparison("002714", "2026-11-03")

        assert "🏭 行业口径: 生猪养殖（同花顺细分行业指数，成分 5 家）" in result
        assert "🏷️ tushare 一级行业（宽口径）: 农业综合" in result
        assert "行业内上市公司: 5 家" in result
        assert "股票名称: 牧原股份" in result
        assert "市值排名: 1/5" in result
        assert "PE(TTM): 16.03" in result
        assert "农林牧渔业指数" not in result

    @pytest.mark.asyncio
    async def test_get_sector_rotation(self, monkeypatch, no_sector_cache):
        """测试板块轮动分析（单日快照）"""
        calls: list = []

        async def fake_query(capability_id: str, **params):
            calls.append((capability_id, params))
            if capability_id == "index_daily":
                return pd.DataFrame({
                    'trade_date': ['20241126', '20241202'],
                    'close': [3270, 3300],
                })
            if capability_id == "moneyflow_ind_ths":
                assert params.get('trade_date') == '20241202'
                return pd.DataFrame({
                    'ts_code': ['877035.TI', '881157.TI'],
                    'industry': ['银行', '证券'],
                    'pct_change': [-0.12, 1.35],
                    'company_num': [84, 50],
                    'net_amount': [-40.0, 49.0],
                })
            if capability_id == "moneyflow_cnt_ths":
                return pd.DataFrame()
            raise AssertionError(f"unexpected capability: {capability_id}")

        monkeypatch.setattr(sector_tools, "_query_capability", fake_query)

        result = await sector_tools.get_sector_rotation("2024-12-02")

        assert "🔄 板块资金流向与轮动分析" in result
        assert "📊 模式: 单日快照" in result
        assert "【🏭 行业板块 — 资金净流入TOP】" in result
        assert "证券: 🔴 +49.00亿" in result
        assert "银行: 🟢 -40.00亿" in result
        assert "⚠️ 暂无概念板块资金流向数据" in result
        assert "【🎯 轮动判断】" in result
        assert "当日行业资金进出分化，板块轮动明显" in result
        assert "合计净额: +9.00亿" in result
        assert sum(1 for cid, _ in calls if cid == "moneyflow_ind_ths") == 1

    @pytest.mark.asyncio
    async def test_get_sector_rotation_multi_day_aggregates(self, monkeypatch, no_sector_cache):
        """测试板块轮动分析（多日累计聚合）"""
        async def fake_query(capability_id: str, **params):
            if capability_id == "index_daily":
                return pd.DataFrame({
                    'trade_date': ['20241126', '20241205'],
                    'close': [3270, 3310],
                })
            if capability_id == "moneyflow_ind_ths":
                assert params.get('start_date') == '20241130'
                assert params.get('end_date') == '20241205'
                return pd.DataFrame([
                    {'trade_date': '20241204', 'industry': '银行', 'pct_change': -0.5,
                     'net_amount': -10.0},
                    {'trade_date': '20241204', 'industry': '证券', 'pct_change': 1.2,
                     'net_amount': 20.0},
                    {'trade_date': '20241205', 'industry': '银行', 'pct_change': -1.0,
                     'net_amount': -30.0},
                    {'trade_date': '20241205', 'industry': '证券', 'pct_change': 1.5,
                     'net_amount': 29.0},
                ])
            if capability_id == "moneyflow_cnt_ths":
                return pd.DataFrame()
            raise AssertionError(f"unexpected capability: {capability_id}")

        monkeypatch.setattr(sector_tools, "_query_capability", fake_query)

        result = await sector_tools.get_sector_rotation("2024-12-05", lookback_days=5)

        assert "📊 模式: 累计聚合" in result
        assert "行业板块数据覆盖 2 个交易日" in result
        assert "证券: 🔴 累计+49.00亿" in result
        assert "银行: 🟢 累计-40.00亿" in result
        assert "累计行业资金进出分化，板块轮动明显" in result
        assert "合计净额: +9.00亿" in result


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
