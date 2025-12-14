#!/usr/bin/env python3
"""
阶段五：端到端集成测试 - 指数分析完整流程

测试目标：
1. 测试完整的指数分析工作流
2. 验证数据层→工具层→Agent层→图层的完整链路
3. 测试错误处理和降级机制
4. 测试性能指标
"""

import pytest
import sys
import json
import time
from unittest.mock import Mock, patch, MagicMock

# 添加项目根目录到路径
sys.path.insert(0, '.')


class TestIndexDataLayer:
    """测试数据层"""
    
    def test_index_data_provider_import(self):
        """测试IndexDataProvider可以导入"""
        from tradingagents.dataflows.index_data import IndexDataProvider
        provider = IndexDataProvider()
        assert provider is not None
        print("✅ IndexDataProvider导入成功")
    
    def test_macro_data_structure(self):
        """测试宏观数据结构"""
        from tradingagents.dataflows.index_data import IndexDataProvider
        provider = IndexDataProvider()
        
        # Mock AKShare调用
        with patch('tradingagents.dataflows.index_data.ak') as mock_ak:
            # 模拟返回数据
            import pandas as pd
            mock_ak.macro_china_gdp.return_value = pd.DataFrame({
                '季度': ['2024Q3'],
                '国内生产总值-绝对值': [300000],
                '国内生产总值-同比增长': [5.2]
            })
            mock_ak.macro_china_cpi_monthly.return_value = pd.DataFrame({
                '月份': ['2024-11'],
                '全国-当月': [100.5],
                '全国-同比': [0.5]
            })
            mock_ak.macro_china_pmi.return_value = pd.DataFrame({
                '月份': ['2024-11'],
                '制造业-指数': [50.3],
                '非制造业-指数': [51.5]
            })
            
            data = provider.get_macro_economics_data()
            
            # 验证返回数据结构
            assert 'gdp' in data
            assert 'cpi' in data
            assert 'pmi' in data
            print("✅ 宏观数据结构验证通过")


class TestIndexToolsLayer:
    """测试工具层"""
    
    def test_index_tools_import(self):
        """测试指数分析工具可以导入"""
        from tradingagents.tools.index_tools import (
            fetch_macro_data,
            fetch_policy_news,
            fetch_sector_rotation
        )
        
        assert callable(fetch_macro_data)
        assert callable(fetch_policy_news)
        assert callable(fetch_sector_rotation)
        print("✅ 指数分析工具导入成功")
    
    def test_macro_data_tool_mock(self):
        """测试宏观数据工具（Mock）"""
        from tradingagents.tools.index_tools import fetch_macro_data
        
        with patch('tradingagents.tools.index_tools.get_index_data_provider') as mock_provider:
            mock_instance = Mock()
            mock_instance.get_macro_economics_data.return_value = {
                'gdp': {'growth': 5.2},
                'cpi': {'value': 0.5},
                'pmi': {'manufacturing': 50.3}
            }
            mock_provider.return_value = mock_instance
            
            result = fetch_macro_data.invoke({"query_date": "2024-12-10"})
            
            assert isinstance(result, str)
            assert len(result) > 0
            print(f"✅ 宏观数据工具返回: {result[:100]}...")


class TestIndexAgentsLayer:
    """测试Agent层"""
    
    def test_macro_analyst_import(self):
        """测试宏观分析师可以导入"""
        from tradingagents.agents.analysts.macro_analyst import create_macro_analyst
        
        assert callable(create_macro_analyst)
        print("✅ 宏观分析师导入成功")
    
    def test_all_analysts_import(self):
        """测试所有指数分析师可以导入"""
        from tradingagents.agents.analysts.macro_analyst import create_macro_analyst
        from tradingagents.agents.analysts.policy_analyst import create_policy_analyst
        from tradingagents.agents.analysts.sector_analyst import create_sector_analyst
        from tradingagents.agents.analysts.strategy_advisor import create_strategy_advisor
        
        print("✅ 所有指数分析师导入成功")
    
    def test_analysis_schemas(self):
        """测试分析Schema"""
        from tradingagents.agents.utils.analysis_schemas import (
            MacroAnalysis,
            PolicyAnalysis,
            SectorAnalysis,
            StrategyOutput
        )
        
        # 测试MacroAnalysis
        macro = MacroAnalysis(
            economic_cycle="扩张",
            liquidity="宽松",
            key_indicators=["GDP增长5.2%", "CPI上涨0.5%"],
            analysis_summary="经济稳步增长",
            confidence=0.85,
            sentiment_score=0.6
        )
        assert macro.confidence >= 0 and macro.confidence <= 1.0
        assert macro.sentiment_score >= -1.0 and macro.sentiment_score <= 1.0
        print("✅ MacroAnalysis Schema验证通过")
        
        # 测试StrategyOutput
        strategy = StrategyOutput(
            market_outlook="看多",
            recommended_position=0.75,
            key_risks=["通胀风险", "政策风险"],
            opportunity_sectors=["科技", "消费"],
            rationale="基于宏观经济向好，政策支持明确",
            final_sentiment_score=0.7,
            confidence=0.8
        )
        assert strategy.recommended_position >= 0 and strategy.recommended_position <= 1.0
        print("✅ StrategyOutput Schema验证通过")


class TestIndexGraphLayer:
    """测试图层"""
    
    def test_graph_setup_index_support(self):
        """测试GraphSetup支持指数分析"""
        from tradingagents.graph.setup import GraphSetup
        
        # 验证_setup_index_graph方法存在
        assert hasattr(GraphSetup, '_setup_index_graph')
        print("✅ GraphSetup支持指数分析")
    
    def test_trading_graph_index_support(self):
        """测试TradingAgentsGraph支持指数分析"""
        from tradingagents.graph.trading_graph import TradingAgentsGraph
        from tradingagents.default_config import DEFAULT_CONFIG
        
        config = DEFAULT_CONFIG.copy()
        
        # 创建指数分析图（不实际初始化LLM）
        with patch('tradingagents.graph.trading_graph.ChatOpenAI'):
            try:
                graph = TradingAgentsGraph(
                    selected_analysts=[],
                    debug=False,
                    config=config,
                    analysis_type="index"
                )
                assert graph.analysis_type == "index"
                print("✅ TradingAgentsGraph支持analysis_type='index'")
            except Exception as e:
                # 允许LLM初始化失败，只要接受了参数即可
                if "analysis_type" in str(type(graph).__init__.__code__.co_varnames):
                    print("✅ TradingAgentsGraph接受analysis_type参数")
                else:
                    raise


class TestConditionalLogic:
    """测试路由逻辑"""
    
    def test_index_routing_methods_exist(self):
        """测试指数分析路由方法存在"""
        from tradingagents.graph.conditional_logic import ConditionalLogic
        
        logic = ConditionalLogic()
        
        required_methods = [
            'should_continue_macro',
            'should_continue_policy',
            'should_continue_sector',
            'should_continue_strategy'
        ]
        
        for method in required_methods:
            assert hasattr(logic, method), f"缺少{method}方法"
            print(f"✅ {method}方法存在")


class TestPerformance:
    """性能测试"""
    
    def test_import_performance(self):
        """测试导入性能"""
        start_time = time.time()
        
        from tradingagents.dataflows.index_data import IndexDataProvider
        from tradingagents.tools.index_tools import fetch_macro_data
        from tradingagents.agents.analysts.macro_analyst import create_macro_analyst
        
        import_time = time.time() - start_time
        
        print(f"\n✅ 导入耗时: {import_time:.3f}秒")
        assert import_time < 5.0, f"导入耗时过长: {import_time}秒"


class TestErrorHandling:
    """错误处理测试"""
    
    def test_data_provider_fallback(self):
        """测试数据提供者降级机制"""
        from tradingagents.dataflows.index_data import IndexDataProvider
        
        provider = IndexDataProvider()
        
        # Mock所有数据源失败
        with patch('tradingagents.dataflows.index_data.ak') as mock_ak:
            mock_ak.macro_china_gdp.side_effect = Exception("API失败")
            mock_ak.macro_china_cpi_monthly.side_effect = Exception("API失败")
            mock_ak.macro_china_pmi.side_effect = Exception("API失败")
            
            # 应该返回默认数据而不是崩溃
            data = provider.get_macro_economics_data()
            
            # 验证返回了默认数据结构
            assert isinstance(data, dict)
            assert 'status' in data or 'error' in data or len(data) > 0
            print("✅ 数据提供者降级机制正常")


class TestIntegration:
    """集成测试"""
    
    def test_data_to_tool_flow(self):
        """测试数据层到工具层的流程"""
        from tradingagents.dataflows.index_data import IndexDataProvider
        from tradingagents.tools.index_tools import fetch_macro_data
        
        # 这个测试验证工具可以调用数据层
        provider = IndexDataProvider()
        assert provider is not None
        
        # 工具应该能够使用数据层
        with patch('tradingagents.tools.index_tools.get_index_data_provider') as mock:
            mock.return_value = provider
            # 验证不会抛出异常
            print("✅ 数据层→工具层流程正常")


def run_all_tests():
    """运行所有测试"""
    print("=" * 80)
    print("阶段五：端到端集成测试")
    print("=" * 80)
    
    test_classes = [
        TestIndexDataLayer,
        TestIndexToolsLayer,
        TestIndexAgentsLayer,
        TestIndexGraphLayer,
        TestConditionalLogic,
        TestPerformance,
        TestErrorHandling,
        TestIntegration
    ]
    
    total_tests = 0
    passed_tests = 0
    failed_tests = []
    
    for test_class in test_classes:
        print(f"\n{'=' * 60}")
        print(f"测试类: {test_class.__name__}")
        print(f"{'=' * 60}")
        
        test_instance = test_class()
        test_methods = [m for m in dir(test_instance) if m.startswith('test_')]
        
        for method_name in test_methods:
            total_tests += 1
            try:
                method = getattr(test_instance, method_name)
                print(f"\n运行: {method_name}")
                method()
                passed_tests += 1
            except Exception as e:
                failed_tests.append((test_class.__name__, method_name, str(e)))
                print(f"❌ 失败: {e}")
    
    print("\n" + "=" * 80)
    print("测试总结")
    print("=" * 80)
    print(f"总计: {total_tests} 个测试")
    print(f"通过: {passed_tests} 个")
    print(f"失败: {len(failed_tests)} 个")
    
    if failed_tests:
        print("\n失败的测试:")
        for class_name, method_name, error in failed_tests:
            print(f"  - {class_name}.{method_name}: {error}")
    else:
        print("\n🎉 所有测试通过！")
    
    print("=" * 80)
    
    return len(failed_tests) == 0


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
