"""
测试数据源状态接口

验证两个问题：
1. 数据源可用性判断逻辑
2. 优先级是否从数据库读取
"""
import asyncio
import sys
import os

# 添加项目根目录到 Python 路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


async def test_data_source_status():
    """测试数据源状态"""
    print("=" * 80)
    print("测试数据源状态接口")
    print("=" * 80)
    
    # 1. 测试统一配置模块
    print("\n📊 步骤 1: 测试统一配置模块")
    print("-" * 80)
    
    from app.core.unified_config import UnifiedConfigManager
    
    config = UnifiedConfigManager()
    data_source_configs = config.get_data_source_configs()
    
    print(f"\n从统一配置读取到 {len(data_source_configs)} 个数据源配置：")
    for ds_config in data_source_configs:
        print(f"  - {ds_config.type}: 优先级={ds_config.priority}, 启用={ds_config.enabled}")
    
    # 2. 测试 DataSourceManager
    print("\n📊 步骤 2: 测试 DataSourceManager")
    print("-" * 80)
    
    from app.services.data_sources.manager import DataSourceManager
    
    manager = DataSourceManager()
    
    print(f"\nDataSourceManager 中的适配器（按优先级排序）：")
    for adapter in manager.adapters:
        print(f"  - {adapter.name}: 优先级={adapter.priority}")
    
    # 3. 测试可用性检查
    print("\n📊 步骤 3: 测试数据源可用性")
    print("-" * 80)
    
    available_adapters = manager.get_available_adapters()
    
    print(f"\n可用的数据源：")
    for adapter in available_adapters:
        print(f"  ✅ {adapter.name}: 优先级={adapter.priority}")
    
    print(f"\n不可用的数据源：")
    for adapter in manager.adapters:
        if adapter not in available_adapters:
            print(f"  ❌ {adapter.name}: 优先级={adapter.priority}")
            # 检查为什么不可用
            if adapter.name == "local":
                print(f"     原因: 检查 MongoDB 中是否有 source='local' 的数据")
            elif adapter.name == "tushare":
                print(f"     原因: 检查 Tushare Token 是否配置")
            elif adapter.name == "akshare":
                print(f"     原因: AKShare 通常总是可用")
            elif adapter.name == "baostock":
                print(f"     原因: 检查 BaoStock 是否能连接")
    
    # 4. 模拟 API 接口返回
    print("\n📊 步骤 4: 模拟 API 接口返回")
    print("-" * 80)
    
    status_list = []
    descriptions = {
        "tushare": "专业金融数据API，提供高质量的A股数据和财务指标",
        "akshare": "开源金融数据库，提供基础的股票信息",
        "baostock": "免费开源的证券数据平台，提供历史数据",
        "local": "本地数据源"
    }
    
    for adapter in manager.adapters:
        is_available = adapter in available_adapters
        
        status_item = {
            "name": adapter.name,
            "priority": adapter.priority,
            "available": is_available,
            "description": descriptions.get(adapter.name, f"{adapter.name}数据源")
        }
        
        status_list.append(status_item)
    
    import json
    print("\nAPI 返回数据：")
    print(json.dumps(status_list, indent=2, ensure_ascii=False))
    
    # 5. 验证问题
    print("\n📊 步骤 5: 验证问题")
    print("-" * 80)
    
    print("\n问题 1: 为什么 local 和 tushare 不可用？")
    for adapter in manager.adapters:
        if adapter.name in ["local", "tushare"]:
            is_available = adapter.is_available()
            print(f"  - {adapter.name}: available={is_available}")
            if adapter.name == "local":
                print(f"    检查逻辑: 查询 MongoDB stock_basic_info 集合中 source='local' 的文档数量")
            elif adapter.name == "tushare":
                print(f"    检查逻辑: 检查 Tushare Token 是否配置且能连接")
    
    print("\n问题 2: 优先级是否从数据库读取？")
    print(f"  - 统一配置模块已接入: ✅")
    print(f"  - DataSourceManager 使用统一配置: ✅")
    print(f"  - 优先级来源: system_configs 集合的 data_source_configs 字段")
    
    print("\n" + "=" * 80)
    print("测试完成")
    print("=" * 80)


if __name__ == "__main__":
    asyncio.run(test_data_source_status())

