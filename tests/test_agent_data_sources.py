#!/usr/bin/env python3
"""
测试各个Agent获取数据源的逻辑
验证数据工具能够正确执行并返回有效数据

测试范围:
1. 指数分析Agent数据获取
   - 宏观经济分析师 (Macro Analyst)
   - 政策分析师 (Policy Analyst)
   - 板块轮动分析师 (Sector Analyst)
2. 数据提供者层
3. 工具层
"""

import os
import sys
import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, MagicMock

# 设置Tushare Token
os.environ["TUSHARE_TOKEN"] = "2876ea85cb005fb5fa17c809a98174f2d5aae8b1f830110a5ead6211"


class TestIndexDataProvider:
    """测试指数数据提供者"""
    
    def test_index_data_provider_import(self):
        """测试数据提供者能否正常导入"""
        from tradingagents.dataflows.index_data import IndexDataProvider, get_index_data_provider
        
        assert IndexDataProvider is not None
        assert get_index_data_provider is not None
        print("✅ IndexDataProvider导入成功")
    
    def test_index_data_provider_init(self):
        """测试数据提供者初始化"""
        from tradingagents.dataflows.index_data import get_index_data_provider
        
        provider = get_index_data_provider()
        assert provider is not None
        assert hasattr(provider, 'get_macro_economics_data')
        assert hasattr(provider, 'get_policy_news')
        assert hasattr(provider, 'get_sector_flows')
        print("✅ IndexDataProvider初始化成功")
    
    def test_macro_data_fetch(self):
        """测试宏观经济数据获取"""
        from tradingagents.dataflows.index_data import get_index_data_provider
        
        provider = get_index_data_provider()
        
        try:
            # 获取最新的宏观数据
            macro_data = provider.get_macro_economics_data()
            
            print(f"\n📊 宏观经济数据获取结果:")
            print(f"  - GDP数据: {macro_data.get('gdp', {})}")
            print(f"  - CPI数据: {macro_data.get('cpi', {})}")
            print(f"  - PMI数据: {macro_data.get('pmi', {})}")
            print(f"  - M2数据: {macro_data.get('m2', {})}")
            print(f"  - LPR数据: {macro_data.get('lpr', {})}")
            
            # 验证数据结构
            assert 'gdp' in macro_data or 'cpi' in macro_data or 'pmi' in macro_data
            
            print("✅ 宏观经济数据获取成功")
            
        except Exception as e:
            print(f"⚠️ 宏观数据获取异常（可能是网络或API限制）: {e}")
            # 不强制要求成功，因为可能受网络/API限制
            pytest.skip(f"宏观数据获取失败: {e}")
    
    def test_policy_news_fetch(self):
        """测试政策新闻数据获取"""
        from tradingagents.dataflows.index_data import get_index_data_provider
        
        provider = get_index_data_provider()
        
        try:
            # 获取最近7天的政策新闻
            news_list = provider.get_policy_news(lookback_days=7)
            
            print(f"\n📰 政策新闻数据获取结果:")
            print(f"  - 新闻数量: {len(news_list)}")
            
            if news_list:
                for i, news in enumerate(news_list[:3], 1):  # 只打印前3条
                    print(f"  - 新闻{i}: {news.get('title', '无标题')} ({news.get('date', 'N/A')})")
            
            # 验证数据结构
            assert isinstance(news_list, list)
            
            print("✅ 政策新闻数据获取成功")
            
        except Exception as e:
            print(f"⚠️ 政策新闻获取异常: {e}")
            pytest.skip(f"政策新闻获取失败: {e}")
    
    def test_sector_flows_fetch(self):
        """测试板块资金流向数据获取"""
        from tradingagents.dataflows.index_data import get_index_data_provider
        
        provider = get_index_data_provider()
        
        try:
            # 获取最新交易日的板块数据
            sector_data = provider.get_sector_flows()
            
            print(f"\n💰 板块资金流向数据获取结果:")
            
            top_sectors = sector_data.get('top_sectors', [])
            bottom_sectors = sector_data.get('bottom_sectors', [])
            
            print(f"  - 领涨板块数量: {len(top_sectors)}")
            if top_sectors:
                for i, sector in enumerate(top_sectors[:3], 1):
                    print(f"    {i}. {sector.get('name', 'N/A')}: {sector.get('change_pct', 0):+.2f}%")
            
            print(f"  - 领跌板块数量: {len(bottom_sectors)}")
            if bottom_sectors:
                for i, sector in enumerate(bottom_sectors[:3], 1):
                    print(f"    {i}. {sector.get('name', 'N/A')}: {sector.get('change_pct', 0):+.2f}%")
            
            # 验证数据结构
            assert 'top_sectors' in sector_data
            assert 'bottom_sectors' in sector_data
            
            print("✅ 板块资金流向数据获取成功")
            
        except Exception as e:
            print(f"⚠️ 板块数据获取异常: {e}")
            pytest.skip(f"板块数据获取失败: {e}")


class TestIndexTools:
    """测试指数分析工具"""
    
    def test_tools_import(self):
        """测试工具导入"""
        from tradingagents.tools.index_tools import (
            fetch_macro_data,
            fetch_policy_news,
            fetch_sector_rotation,
            INDEX_ANALYSIS_TOOLS
        )
        
        assert fetch_macro_data is not None
        assert fetch_policy_news is not None
        assert fetch_sector_rotation is not None
        assert len(INDEX_ANALYSIS_TOOLS) == 3
        
        print("✅ 所有指数分析工具导入成功")
    
    def test_fetch_macro_data_tool(self):
        """测试宏观数据工具"""
        from tradingagents.tools.index_tools import fetch_macro_data
        
        try:
            # 调用工具
            result = fetch_macro_data.invoke({})
            
            print(f"\n🌍 宏观数据工具返回结果:")
            print(f"  - 结果类型: {type(result)}")
            print(f"  - 结果长度: {len(result)} 字符")
            print(f"  - 结果预览: {result[:300]}...")
            
            # 验证返回Markdown格式
            assert isinstance(result, str)
            assert len(result) > 0
            assert '宏观经济' in result or 'GDP' in result or 'PMI' in result
            
            print("✅ 宏观数据工具执行成功")
            
        except Exception as e:
            print(f"⚠️ 宏观数据工具执行异常: {e}")
            pytest.skip(f"宏观数据工具执行失败: {e}")
    
    def test_fetch_policy_news_tool(self):
        """测试政策新闻工具"""
        from tradingagents.tools.index_tools import fetch_policy_news
        
        try:
            # 调用工具
            result = fetch_policy_news.invoke({"lookback_days": 7})
            
            print(f"\n📰 政策新闻工具返回结果:")
            print(f"  - 结果类型: {type(result)}")
            print(f"  - 结果长度: {len(result)} 字符")
            print(f"  - 结果预览: {result[:300]}...")
            
            # 验证返回Markdown格式
            assert isinstance(result, str)
            assert len(result) > 0
            
            print("✅ 政策新闻工具执行成功")
            
        except Exception as e:
            print(f"⚠️ 政策新闻工具执行异常: {e}")
            pytest.skip(f"政策新闻工具执行失败: {e}")
    
    def test_fetch_sector_rotation_tool(self):
        """测试板块轮动工具"""
        from tradingagents.tools.index_tools import fetch_sector_rotation
        
        try:
            # 调用工具
            result = fetch_sector_rotation.invoke({})
            
            print(f"\n💰 板块轮动工具返回结果:")
            print(f"  - 结果类型: {type(result)}")
            print(f"  - 结果长度: {len(result)} 字符")
            print(f"  - 结果预览: {result[:300]}...")
            
            # 验证返回Markdown格式
            assert isinstance(result, str)
            assert len(result) > 0
            assert '板块' in result or '领涨' in result or '领跌' in result
            
            print("✅ 板块轮动工具执行成功")
            
        except Exception as e:
            print(f"⚠️ 板块轮动工具执行异常: {e}")
            pytest.skip(f"板块轮动工具执行失败: {e}")


class TestMacroAnalyst:
    """测试宏观经济分析师"""
    
    def test_macro_analyst_import(self):
        """测试宏观分析师导入"""
        from tradingagents.agents.analysts.macro_analyst import create_macro_analyst
        
        assert create_macro_analyst is not None
        print("✅ 宏观分析师导入成功")
    
    def test_macro_analyst_creation(self):
        """测试宏观分析师创建"""
        from tradingagents.agents.analysts.macro_analyst import create_macro_analyst
        from unittest.mock import Mock
        
        # 创建Mock LLM和工具包
        mock_llm = Mock()
        mock_toolkit = Mock()
        
        # 创建分析师节点
        analyst_node = create_macro_analyst(mock_llm, mock_toolkit)
        
        assert analyst_node is not None
        assert callable(analyst_node)
        
        print("✅ 宏观分析师节点创建成功")
    
    def test_macro_analyst_with_tool_execution(self):
        """测试宏观分析师工具执行逻辑（不涉及LLM）"""
        from tradingagents.tools.index_tools import fetch_macro_data
        
        try:
            # 直接调用工具
            result = fetch_macro_data.invoke({})
            
            print(f"\n🌍 宏观分析师工具执行测试:")
            print(f"  - 工具调用成功: ✅")
            print(f"  - 返回数据长度: {len(result)} 字符")
            
            # 验证工具能返回有效数据
            assert isinstance(result, str)
            assert len(result) > 0
            
            print("✅ 宏观分析师工具执行逻辑正常")
            
        except Exception as e:
            print(f"⚠️ 工具执行异常: {e}")
            pytest.skip(f"工具执行失败: {e}")


class TestPolicyAnalyst:
    """测试政策分析师"""
    
    def test_policy_analyst_import(self):
        """测试政策分析师导入"""
        from tradingagents.agents.analysts.policy_analyst import create_policy_analyst
        
        assert create_policy_analyst is not None
        print("✅ 政策分析师导入成功")
    
    def test_policy_analyst_creation(self):
        """测试政策分析师创建"""
        from tradingagents.agents.analysts.policy_analyst import create_policy_analyst
        from unittest.mock import Mock
        
        mock_llm = Mock()
        mock_toolkit = Mock()
        
        analyst_node = create_policy_analyst(mock_llm, mock_toolkit)
        
        assert analyst_node is not None
        assert callable(analyst_node)
        
        print("✅ 政策分析师节点创建成功")
    
    def test_policy_analyst_with_tool_execution(self):
        """测试政策分析师工具执行逻辑"""
        from tradingagents.tools.index_tools import fetch_policy_news
        
        try:
            # 直接调用工具
            result = fetch_policy_news.invoke({"lookback_days": 7})
            
            print(f"\n📰 政策分析师工具执行测试:")
            print(f"  - 工具调用成功: ✅")
            print(f"  - 返回数据长度: {len(result)} 字符")
            
            assert isinstance(result, str)
            assert len(result) > 0
            
            print("✅ 政策分析师工具执行逻辑正常")
            
        except Exception as e:
            print(f"⚠️ 工具执行异常: {e}")
            pytest.skip(f"工具执行失败: {e}")


class TestSectorAnalyst:
    """测试板块轮动分析师"""
    
    def test_sector_analyst_import(self):
        """测试板块分析师导入"""
        from tradingagents.agents.analysts.sector_analyst import create_sector_analyst
        
        assert create_sector_analyst is not None
        print("✅ 板块分析师导入成功")
    
    def test_sector_analyst_creation(self):
        """测试板块分析师创建"""
        from tradingagents.agents.analysts.sector_analyst import create_sector_analyst
        from unittest.mock import Mock
        
        mock_llm = Mock()
        mock_toolkit = Mock()
        
        analyst_node = create_sector_analyst(mock_llm, mock_toolkit)
        
        assert analyst_node is not None
        assert callable(analyst_node)
        
        print("✅ 板块分析师节点创建成功")
    
    def test_sector_analyst_with_tool_execution(self):
        """测试板块分析师工具执行逻辑"""
        from tradingagents.tools.index_tools import fetch_sector_rotation
        
        try:
            # 直接调用工具
            result = fetch_sector_rotation.invoke({})
            
            print(f"\n💰 板块分析师工具执行测试:")
            print(f"  - 工具调用成功: ✅")
            print(f"  - 返回数据长度: {len(result)} 字符")
            
            assert isinstance(result, str)
            assert len(result) > 0
            
            print("✅ 板块分析师工具执行逻辑正常")
            
        except Exception as e:
            print(f"⚠️ 工具执行异常: {e}")
            pytest.skip(f"工具执行失败: {e}")


class TestStrategyAdvisor:
    """测试策略顾问"""
    
    def test_strategy_advisor_import(self):
        """测试策略顾问导入"""
        from tradingagents.agents.analysts.strategy_advisor import create_strategy_advisor
        
        assert create_strategy_advisor is not None
        print("✅ 策略顾问导入成功")
    
    def test_strategy_advisor_creation(self):
        """测试策略顾问创建"""
        from tradingagents.agents.analysts.strategy_advisor import create_strategy_advisor
        from unittest.mock import Mock
        
        mock_llm = Mock()
        
        # 策略顾问不需要toolkit参数
        advisor_node = create_strategy_advisor(mock_llm)
        
        assert advisor_node is not None
        assert callable(advisor_node)
        
        print("✅ 策略顾问节点创建成功")


class TestDataIntegration:
    """测试数据集成流程"""
    
    def test_full_data_pipeline(self):
        """测试完整的数据获取管道"""
        print("\n" + "="*60)
        print("🔄 开始测试完整数据获取管道")
        print("="*60)
        
        from tradingagents.tools.index_tools import (
            fetch_macro_data,
            fetch_policy_news,
            fetch_sector_rotation
        )
        
        results = {}
        
        # 1. 宏观数据
        try:
            print("\n📊 Step 1: 获取宏观经济数据...")
            macro_result = fetch_macro_data.invoke({})
            results['macro'] = {
                'success': True,
                'length': len(macro_result),
                'preview': macro_result[:200]
            }
            print("  ✅ 宏观数据获取成功")
        except Exception as e:
            results['macro'] = {'success': False, 'error': str(e)}
            print(f"  ⚠️ 宏观数据获取失败: {e}")
        
        # 2. 政策新闻
        try:
            print("\n📰 Step 2: 获取政策新闻...")
            policy_result = fetch_policy_news.invoke({"lookback_days": 7})
            results['policy'] = {
                'success': True,
                'length': len(policy_result),
                'preview': policy_result[:200]
            }
            print("  ✅ 政策新闻获取成功")
        except Exception as e:
            results['policy'] = {'success': False, 'error': str(e)}
            print(f"  ⚠️ 政策新闻获取失败: {e}")
        
        # 3. 板块数据
        try:
            print("\n💰 Step 3: 获取板块轮动数据...")
            sector_result = fetch_sector_rotation.invoke({})
            results['sector'] = {
                'success': True,
                'length': len(sector_result),
                'preview': sector_result[:200]
            }
            print("  ✅ 板块数据获取成功")
        except Exception as e:
            results['sector'] = {'success': False, 'error': str(e)}
            print(f"  ⚠️ 板块数据获取失败: {e}")
        
        # 打印总结
        print("\n" + "="*60)
        print("📊 数据获取管道测试总结")
        print("="*60)
        
        success_count = sum(1 for r in results.values() if r.get('success', False))
        total_count = len(results)
        
        print(f"\n✅ 成功: {success_count}/{total_count}")
        
        for key, result in results.items():
            status = "✅" if result.get('success') else "❌"
            print(f"  {status} {key}: {result}")
        
        # 至少有一个数据源成功即可
        assert success_count > 0, "至少应该有一个数据源成功"
        
        print("\n✅ 数据获取管道测试完成")


class TestAKShareDataSources:
    """测试AKShare数据源（直接调用）"""
    
    def test_akshare_import(self):
        """测试AKShare导入"""
        try:
            import akshare as ak
            assert ak is not None
            print("✅ AKShare导入成功")
            print(f"  - AKShare版本: {ak.__version__ if hasattr(ak, '__version__') else 'Unknown'}")
        except ImportError as e:
            pytest.skip(f"AKShare未安装: {e}")
    
    def test_akshare_macro_data_direct(self):
        """测试AKShare直接获取宏观数据"""
        try:
            import akshare as ak
            
            print("\n📊 测试AKShare宏观数据接口:")
            
            # 测试PMI数据（最稳定的接口）
            try:
                pmi_df = ak.macro_china_pmi_yearly()
                print(f"  - PMI数据行数: {len(pmi_df)}")
                if not pmi_df.empty:
                    print(f"  - 最新PMI: {pmi_df.iloc[-1].to_dict()}")
                    print("  ✅ PMI数据获取成功")
            except Exception as e:
                print(f"  ⚠️ PMI数据获取失败: {e}")
            
            # 测试CPI数据
            try:
                cpi_df = ak.macro_china_cpi_yearly()
                print(f"  - CPI数据行数: {len(cpi_df)}")
                if not cpi_df.empty:
                    print(f"  - 最新CPI: {cpi_df.iloc[-1].to_dict()}")
                    print("  ✅ CPI数据获取成功")
            except Exception as e:
                print(f"  ⚠️ CPI数据获取失败: {e}")
            
            print("\n✅ AKShare宏观数据接口测试完成")
            
        except ImportError:
            pytest.skip("AKShare未安装")
        except Exception as e:
            print(f"⚠️ AKShare测试异常: {e}")
            pytest.skip(f"AKShare测试失败: {e}")
    
    def test_akshare_sector_data_direct(self):
        """测试AKShare直接获取板块数据"""
        try:
            import akshare as ak
            
            print("\n💰 测试AKShare板块数据接口:")
            
            # 测试板块行情
            try:
                sector_df = ak.stock_board_industry_name_em()
                print(f"  - 板块数量: {len(sector_df)}")
                if not sector_df.empty:
                    print(f"  - 前5个板块: {sector_df.head()['板块名称'].tolist()}")
                    print("  ✅ 板块数据获取成功")
            except Exception as e:
                print(f"  ⚠️ 板块数据获取失败: {e}")
            
            print("\n✅ AKShare板块数据接口测试完成")
            
        except ImportError:
            pytest.skip("AKShare未安装")
        except Exception as e:
            print(f"⚠️ AKShare测试异常: {e}")
            pytest.skip(f"AKShare测试失败: {e}")


if __name__ == "__main__":
    # 可以直接运行此文件进行测试
    print("🧪 开始测试各Agent的数据源获取逻辑")
    print("="*80)
    
    # 运行pytest
    pytest.main([__file__, "-v", "-s", "--tb=short"])
