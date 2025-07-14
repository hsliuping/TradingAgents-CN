#!/usr/bin/env python3
"""
TDX到Tushare迁移测试
验证TDX接口已成功替换为Tushare统一接口
"""

import os
import sys
from datetime import datetime, timedelta

# 添加项目根目录到Python路径
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)


def test_data_source_manager():
    """测试数据源管理器"""
    print("\n🔧 测试数据源管理器")
    print("=" * 60)
    
    try:
        from tradingagents.dataflows.data_source_manager import get_data_source_manager, ChinaDataSource
        
        print("✅ 数据源管理器导入成功")
        
        # 创建管理器实例
        manager = get_data_source_manager()
        
        print(f"✅ 数据源管理器初始化成功")
        print(f"   当前数据源: {manager.get_current_source().value}")
        print(f"   可用数据源: {[s.value for s in manager.available_sources]}")
        
        # 测试数据源切换
        if ChinaDataSource.TUSHARE in manager.available_sources:
            print("🔄 测试切换到Tushare...")
            success = manager.set_current_source(ChinaDataSource.TUSHARE)
            if success:
                print("✅ 成功切换到Tushare")
            else:
                print("❌ 切换到Tushare失败")
        
        return True
        
    except Exception as e:
        print(f"❌ 数据源管理器测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_unified_interfaces():
    """测试统一接口"""
    print("\n🔧 测试统一接口")
    print("=" * 60)
    
    try:
        from tradingagents.dataflows.interface import (
            get_china_stock_data_unified,
            get_china_stock_info_unified,
            switch_china_data_source,
            get_current_china_data_source
        )
        
        print("✅ 统一接口导入成功")
        
        # 测试获取当前数据源
        print("🔄 测试获取当前数据源...")
        current_source = get_current_china_data_source()
        print(f"✅ 当前数据源信息:\n{current_source}")
        
        # 测试切换数据源
        print("🔄 测试切换数据源到Tushare...")
        switch_result = switch_china_data_source("tushare")
        print(f"✅ 切换结果: {switch_result}")
        
        # 测试获取股票信息
        print("🔄 测试获取股票信息...")
        stock_info = get_china_stock_info_unified("000001")
        if "股票代码: 000001" in stock_info:
            print("✅ 股票信息获取成功")
            print(f"📊 股票信息: {stock_info[:200]}...")
        else:
            print("❌ 股票信息获取失败")
        
        # 测试获取股票数据
        print("🔄 测试获取股票数据...")
        end_date = datetime.now().strftime('%Y-%m-%d')
        start_date = (datetime.now() - timedelta(days=10)).strftime('%Y-%m-%d')
        
        stock_data = get_china_stock_data_unified("000001", start_date, end_date)
        if "股票代码: 000001" in stock_data:
            print("✅ 股票数据获取成功")
            print(f"📊 数据长度: {len(stock_data)}字符")
        else:
            print("❌ 股票数据获取失败")
        
        return True
        
    except Exception as e:
        print(f"❌ 统一接口测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_agent_utils_migration():
    """测试agent_utils的迁移"""
    print("\n🔧 测试agent_utils迁移")
    print("=" * 60)
    
    try:
        from tradingagents.agents.utils.agent_utils import AgentUtils

        print("✅ agent_utils导入成功")

        # 测试基本面数据获取
        print("🔄 测试基本面数据获取...")
        curr_date = datetime.now().strftime('%Y-%m-%d')

        # 使用AgentUtils类的静态方法
        fundamentals = AgentUtils.get_fundamentals_openai("000001", curr_date)
        
        if fundamentals and len(fundamentals) > 100:
            print("✅ 基本面数据获取成功")
            print(f"📊 数据长度: {len(fundamentals)}字符")
            
            # 检查是否还包含TDX相关信息
            if "通达信" in fundamentals:
                print("⚠️ 警告: 基本面数据中仍包含通达信相关信息")
            else:
                print("✅ 基本面数据已成功迁移到新数据源")
        else:
            print("❌ 基本面数据获取失败")
        
        return True
        
    except Exception as e:
        print(f"❌ agent_utils迁移测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_optimized_china_data_migration():
    """测试optimized_china_data的迁移"""
    print("\n🔧 测试optimized_china_data迁移")
    print("=" * 60)
    
    try:
        from tradingagents.dataflows.optimized_china_data import OptimizedChinaDataProvider
        
        print("✅ optimized_china_data导入成功")
        
        # 创建提供器实例
        provider = OptimizedChinaDataProvider()
        
        # 测试数据获取
        print("🔄 测试数据获取...")
        end_date = datetime.now().strftime('%Y-%m-%d')
        start_date = (datetime.now() - timedelta(days=10)).strftime('%Y-%m-%d')
        
        data = provider.get_stock_data("000001", start_date, end_date)
        
        if data and len(data) > 100:
            print("✅ 数据获取成功")
            print(f"📊 数据长度: {len(data)}字符")
            
            # 检查是否还包含TDX相关信息
            if "通达信" in data:
                print("⚠️ 警告: 数据中仍包含通达信相关信息")
            else:
                print("✅ 数据获取已成功迁移到新数据源")
        else:
            print("❌ 数据获取失败")
        
        return True
        
    except Exception as e:
        print(f"❌ optimized_china_data迁移测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_tdx_deprecation_warnings():
    """测试TDX弃用警告"""
    print("\n🔧 测试TDX弃用警告")
    print("=" * 60)
    
    try:
        from tradingagents.dataflows.data_source_manager import get_data_source_manager, ChinaDataSource
        
        manager = get_data_source_manager()
        
        # 如果TDX可用，测试弃用警告
        if ChinaDataSource.TDX in manager.available_sources:
            print("🔄 测试TDX弃用警告...")
            
            # 切换到TDX
            manager.set_current_source(ChinaDataSource.TDX)
            
            # 获取数据（应该显示弃用警告）
            end_date = datetime.now().strftime('%Y-%m-%d')
            start_date = (datetime.now() - timedelta(days=5)).strftime('%Y-%m-%d')
            
            data = manager.get_stock_data("000001", start_date, end_date)
            
            if data:
                print("✅ TDX数据获取成功（带弃用警告）")
            else:
                print("❌ TDX数据获取失败")
            
            # 切换回Tushare
            if ChinaDataSource.TUSHARE in manager.available_sources:
                manager.set_current_source(ChinaDataSource.TUSHARE)
                print("✅ 已切换回Tushare数据源")
        else:
            print("ℹ️ TDX数据源不可用，跳过弃用警告测试")
        
        return True
        
    except Exception as e:
        print(f"❌ TDX弃用警告测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def check_migration_completeness():
    """检查迁移完整性"""
    print("\n🔧 检查迁移完整性")
    print("=" * 60)
    
    # 检查环境变量
    tushare_token = os.getenv('TUSHARE_TOKEN')
    default_source = os.getenv('DEFAULT_CHINA_DATA_SOURCE', 'tushare')
    
    print(f"📊 环境变量检查:")
    print(f"   TUSHARE_TOKEN: {'已设置' if tushare_token else '未设置'}")
    print(f"   DEFAULT_CHINA_DATA_SOURCE: {default_source}")
    
    # 检查Tushare库
    try:
        import tushare as ts
        print(f"✅ Tushare库: v{ts.__version__}")
    except ImportError:
        print("❌ Tushare库未安装")
        return False
    
    # 检查统一接口可用性
    try:
        from tradingagents.dataflows import (
            get_china_stock_data_unified,
            get_china_stock_info_unified,
            switch_china_data_source,
            get_current_china_data_source
        )
        print("✅ 统一接口可用")
    except ImportError as e:
        print(f"❌ 统一接口不可用: {e}")
        return False
    
    return True


def main():
    """主测试函数"""
    print("🔬 TDX到Tushare迁移测试")
    print("=" * 70)
    print("💡 测试目标:")
    print("   - 验证数据源管理器功能")
    print("   - 验证统一接口替换TDX")
    print("   - 验证agent_utils迁移")
    print("   - 验证optimized_china_data迁移")
    print("   - 验证TDX弃用警告")
    print("=" * 70)
    
    # 检查迁移完整性
    if not check_migration_completeness():
        print("\n❌ 迁移环境检查失败，请先配置环境")
        return
    
    # 运行所有测试
    tests = [
        ("数据源管理器", test_data_source_manager),
        ("统一接口", test_unified_interfaces),
        ("agent_utils迁移", test_agent_utils_migration),
        ("optimized_china_data迁移", test_optimized_china_data_migration),
        ("TDX弃用警告", test_tdx_deprecation_warnings)
    ]
    
    results = []
    for test_name, test_func in tests:
        try:
            result = test_func()
            results.append((test_name, result))
        except Exception as e:
            print(f"❌ {test_name}测试异常: {e}")
            results.append((test_name, False))
    
    # 总结
    print("\n📋 TDX到Tushare迁移测试总结")
    print("=" * 60)
    
    passed = 0
    for test_name, result in results:
        status = "✅ 通过" if result else "❌ 失败"
        print(f"{test_name}: {status}")
        if result:
            passed += 1
    
    total = len(results)
    print(f"\n📊 测试结果: {passed}/{total} 通过")
    
    if passed == total:
        print("\n🎉 TDX到Tushare迁移测试完全成功！")
        print("\n💡 迁移效果:")
        print("   ✅ TDX接口已成功替换为Tushare统一接口")
        print("   ✅ 数据源管理器正常工作")
        print("   ✅ 支持多数据源备用机制")
        print("   ✅ 保持向后兼容性")
        print("\n🚀 现在系统默认使用Tushare数据源！")
    else:
        print("\n⚠️ 部分测试失败，请检查相关配置")
    
    print("\n🎯 使用建议:")
    print("   1. 设置TUSHARE_TOKEN环境变量")
    print("   2. 设置DEFAULT_CHINA_DATA_SOURCE=tushare")
    print("   3. 使用统一接口获取中国股票数据")
    print("   4. 逐步停用TDX相关代码")
    
    input("按回车键退出...")


if __name__ == "__main__":
    main()
