#!/usr/bin/env python3
"""
AData数据源快速测试
快速验证AData集成是否正常
"""

import sys
import os
from datetime import datetime, timedelta

# 添加项目根目录到Python路径
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

def quick_test():
    """快速测试AData集成"""
    print("🚀 AData数据源快速测试")
    print("=" * 40)
    
    try:
        # 检查AData是否可用
        import adata
        print("✅ AData库已安装")
    except ImportError:
        print("❌ AData库未安装")
        print("安装命令: pip install adata")
        return False
    
    try:
        # 测试数据源管理器
        from tradingagents.dataflows.data_source_manager import (
            DataSourceManager,
            ChinaDataSource,
            get_data_source_manager
        )
        
        # 创建数据源管理器实例
        manager = get_data_source_manager()
        
        print(f"📊 当前数据源: {manager.current_source.value}")
        print(f"可用数据源: {[s.value for s in manager.available_sources]}")
        
        # 检查AData是否可用
        if ChinaDataSource.ADATA in manager.available_sources:
            print("✅ AData数据源可用")
            
            # 切换到AData数据源
            success = manager.set_current_source(ChinaDataSource.ADATA)
            if success:
                print("✅ 已切换到AData数据源")
                
                # 测试获取股票数据
                symbol = "000001"  # 平安银行
                start_date = (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d')
                end_date = datetime.now().strftime('%Y-%m-%d')
                
                print(f"📈 测试获取 {symbol} 数据...")
                
                # 获取股票信息
                info = manager.get_stock_info(symbol)
                print(f"✅ 股票信息: {info['name']} ({info['symbol']})")
                
                # 获取股票数据
                data = manager.get_stock_data(symbol, start_date, end_date)
                print(f"✅ 数据获取成功")
                print(f"数据预览: {data[:200]}...")
                
                return True
            else:
                print("❌ 无法切换到AData数据源")
        else:
            print("⚠️ AData数据源不可用")
            
    except Exception as e:
        print(f"❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    return False

if __name__ == "__main__":
    success = quick_test()
    if success:
        print("\n🎉 AData集成测试通过!")
    else:
        print("\n❌ AData集成测试失败")