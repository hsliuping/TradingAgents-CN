#!/usr/bin/env python3
"""
AData数据源集成测试
测试AData数据源的完整性和功能
"""

import sys
import os
import unittest
from datetime import datetime, timedelta

# 添加项目根目录到Python路径
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

from tradingagents.dataflows.adata_utils import (
    get_adata_provider,
    get_china_stock_data_adata,
    get_china_stock_info_adata
)
from tradingagents.dataflows.data_source_manager import (
    DataSourceManager,
    ChinaDataSource,
    get_data_source_manager
)


class TestADataIntegration(unittest.TestCase):
    """AData集成测试类"""
    
    def setUp(self):
        """测试前的准备工作"""
        self.test_symbol = "000001"  # 平安银行
        self.start_date = (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d')
        self.end_date = datetime.now().strftime('%Y-%m-%d')
    
    def test_adata_provider_availability(self):
        """测试AData提供者是否可用"""
        provider = get_adata_provider()
        is_available = provider.check_availability()
        
        print(f"AData提供者可用性: {is_available}")
        
        # 如果adata不可用，跳过测试
        if not is_available:
            self.skipTest("AData库未安装，跳过测试")
        
        self.assertTrue(is_available)
    
    def test_adata_stock_data(self):
        """测试获取股票数据"""
        try:
            # 获取AData提供者
            provider = get_adata_provider()
            
            # 检查是否可用
            if not provider.check_availability():
                self.skipTest("AData库未安装，跳过测试")
            
            # 获取股票数据
            data = provider.get_stock_data(
                symbol=self.test_symbol,
                start_date=self.start_date,
                end_date=self.end_date
            )
            
            # 验证数据格式
            self.assertIsNotNone(data)
            self.assertFalse(data.empty)
            self.assertGreater(len(data), 0)
            
            # 验证必要的列存在
            required_columns = ['date', 'open', 'high', 'low', 'close', 'vol']
            for col in required_columns:
                self.assertIn(col, data.columns)
            
            print(f"✅ 成功获取{self.test_symbol}数据，共{len(data)}条记录")
            print(f"数据列: {list(data.columns)}")
            print(f"最新数据: {data.tail(1).iloc[0].to_dict()}")
            
        except Exception as e:
            self.fail(f"获取股票数据失败: {e}")
    
    def test_adata_stock_info(self):
        """测试获取股票信息"""
        try:
            # 获取AData提供者
            provider = get_adata_provider()
            
            # 检查是否可用
            if not provider.check_availability():
                self.skipTest("AData库未安装，跳过测试")
            
            # 获取股票信息
            info = provider.get_stock_info(self.test_symbol)
            
            # 验证信息格式
            self.assertIsNotNone(info)
            self.assertIsInstance(info, dict)
            self.assertEqual(info['symbol'], self.test_symbol)
            self.assertIn('name', info)
            self.assertIn('source', info)
            self.assertEqual(info['source'], 'adata')
            
            print(f"✅ 成功获取{self.test_symbol}信息")
            print(f"股票信息: {info}")
            
        except Exception as e:
            self.fail(f"获取股票信息失败: {e}")
    
    def test_adata_realtime_data(self):
        """测试获取实时数据"""
        try:
            # 获取AData提供者
            provider = get_adata_provider()
            
            # 检查是否可用
            if not provider.check_availability():
                self.skipTest("AData库未安装，跳过测试")
            
            # 获取实时数据
            realtime = provider.get_realtime_data(self.test_symbol)
            
            if realtime is not None:
                # 验证实时数据格式
                self.assertIsInstance(realtime, dict)
                self.assertIn('symbol', realtime)
                self.assertIn('price', realtime)
                
                print(f"✅ 成功获取{self.test_symbol}实时数据")
                print(f"实时数据: {realtime}")
            else:
                print("⚠️ 实时数据获取失败，可能市场未开盘")
                
        except Exception as e:
            print(f"获取实时数据失败: {e}")
    
    def test_data_source_manager_adata(self):
        """测试数据源管理器集成AData"""
        try:
            # 获取数据源管理器
            manager = get_data_source_manager()
            
            # 检查AData是否可用
            if ChinaDataSource.ADATA not in manager.available_sources:
                self.skipTest("AData库未安装，跳过测试")
            
            # 设置数据源为AData
            success = manager.set_current_source(ChinaDataSource.ADATA)
            self.assertTrue(success)
            self.assertEqual(manager.current_source, ChinaDataSource.ADATA)
            
            # 测试获取数据
            data_str = manager.get_stock_data(
                symbol=self.test_symbol,
                start_date=self.start_date,
                end_date=self.end_date
            )
            
            self.assertIsInstance(data_str, str)
            self.assertIn(self.test_symbol, data_str)
            self.assertIn("AData", data_str)
            
            # 测试获取信息
            info = manager.get_stock_info(self.test_symbol)
            self.assertIsInstance(info, dict)
            self.assertEqual(info['symbol'], self.test_symbol)
            
            print(f"✅ 数据源管理器AData集成测试通过")
            
        except Exception as e:
            self.fail(f"数据源管理器测试失败: {e}")
    
    def test_unified_interface(self):
        """测试统一接口"""
        try:
            from tradingagents.dataflows.data_source_manager import get_china_stock_data_unified
            
            # 获取数据源管理器
            manager = get_data_source_manager()
            
            # 检查AData是否可用
            if ChinaDataSource.ADATA not in manager.available_sources:
                self.skipTest("AData库未安装，跳过测试")
            
            # 设置数据源为AData
            manager.set_current_source(ChinaDataSource.ADATA)
            
            # 使用统一接口获取数据
            data_str = get_china_stock_data_unified(
                symbol=self.test_symbol,
                start_date=self.start_date,
                end_date=self.end_date
            )
            
            self.assertIsInstance(data_str, str)
            self.assertIn(self.test_symbol, data_str)
            self.assertIn("AData", data_str)
            
            print(f"✅ 统一接口测试通过")
            
        except Exception as e:
            self.fail(f"统一接口测试失败: {e}")


class TestADataExamples(unittest.TestCase):
    """AData使用示例测试"""
    
    def setUp(self):
        """测试前的准备工作"""
        self.test_symbols = ["000001", "600519", "601127"]  # 平安银行, 贵州茅台, 小康股份
        self.start_date = (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d')
        self.end_date = datetime.now().strftime('%Y-%m-%d')
    
    def test_multiple_symbols(self):
        """测试多个股票代码"""
        try:
            # 获取数据源管理器
            manager = get_data_source_manager()
            
            # 检查AData是否可用
            if ChinaDataSource.ADATA not in manager.available_sources:
                self.skipTest("AData库未安装，跳过测试")
            
            # 设置数据源为AData
            manager.set_current_source(ChinaDataSource.ADATA)
            
            for symbol in self.test_symbols:
                try:
                    # 获取股票信息
                    info = manager.get_stock_info(symbol)
                    print(f"✅ {symbol} - {info.get('name', '未知')}")
                    
                    # 获取股票数据
                    data = manager.get_stock_data(symbol, self.start_date, self.end_date)
                    print(f"   数据: {data[:100]}...")
                    
                except Exception as e:
                    print(f"⚠️ {symbol} 获取失败: {e}")
                    
        except Exception as e:
            self.fail(f"多股票测试失败: {e}")


if __name__ == '__main__':
    print("=" * 60)
    print("AData数据源集成测试")
    print("=" * 60)
    
    # 检查AData是否可用
    try:
        import adata
        print("✅ AData库已安装，开始测试")
    except ImportError:
        print("❌ AData库未安装，请运行: pip install adata")
        sys.exit(1)
    
    # 运行测试
    unittest.main(verbosity=2)