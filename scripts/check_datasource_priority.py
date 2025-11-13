"""
检查数据库中的数据源优先级配置
"""
import sys
import os
from pymongo import MongoClient
from dotenv import load_dotenv

# 添加项目根目录到 Python 路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def check_datasource_priority():
    """检查数据源优先级配置"""
    try:
        # 从环境变量读取 MongoDB 连接信息
        load_dotenv()
        
        mongo_uri = os.getenv("MONGO_URI", "mongodb://localhost:27017")
        mongo_db_name = os.getenv("MONGO_DB", "tradingagents")
        
        print(f"连接 MongoDB: {mongo_uri}")
        print(f"数据库: {mongo_db_name}")
        print()
        
        # 创建同步 MongoDB 客户端
        client = MongoClient(mongo_uri)
        db = client[mongo_db_name]
        
        # 1. 检查 system_configs 集合
        print("=" * 80)
        print("📋 检查 system_configs 集合")
        print("=" * 80)
        
        config_data = db.system_configs.find_one(
            {"is_active": True},
            sort=[("version", -1)]
        )
        
        if config_data:
            print(f"✅ 找到激活的配置，版本: {config_data.get('version')}")
            print()
            
            data_source_configs = config_data.get('data_source_configs', [])
            if data_source_configs:
                print(f"📊 数据源配置（共 {len(data_source_configs)} 个）:")
                print()
                
                # 按 priority 排序显示
                sorted_configs = sorted(data_source_configs, key=lambda x: x.get('priority', 0), reverse=True)
                
                for idx, ds in enumerate(sorted_configs, 1):
                    print(f"{idx}. {ds.get('name', 'Unknown')}")
                    print(f"   类型: {ds.get('type', 'Unknown')}")
                    print(f"   优先级: {ds.get('priority', 0)}")
                    print(f"   启用状态: {'✅ 启用' if ds.get('enabled', False) else '❌ 禁用'}")
                    print()
            else:
                print("⚠️ 没有找到 data_source_configs 字段")
        else:
            print("❌ 没有找到激活的配置")
        
        print()
        
        # 2. 检查 datasource_groupings 集合
        print("=" * 80)
        print("📋 检查 datasource_groupings 集合（A股市场）")
        print("=" * 80)
        
        # 查找 A股市场的分类
        market_category = db.market_categories.find_one({"name": "A股"})
        
        if market_category:
            category_id = str(market_category.get('_id'))
            print(f"✅ 找到 A股 市场分类，ID: {category_id}")
            print()
            
            # 查询该分类下的数据源
            groupings = list(db.datasource_groupings.find(
                {"market_category_id": category_id}
            ).sort("priority", -1))  # 按优先级降序排序
            
            if groupings:
                print(f"📊 数据源分组（共 {len(groupings)} 个）:")
                print()
                
                for idx, group in enumerate(groupings, 1):
                    print(f"{idx}. {group.get('data_source_name', 'Unknown')}")
                    print(f"   优先级: {group.get('priority', 0)}")
                    print(f"   启用状态: {'✅ 启用' if group.get('enabled', False) else '❌ 禁用'}")
                    print()
            else:
                print("⚠️ 没有找到数据源分组")
        else:
            print("❌ 没有找到 A股 市场分类")
        
        print()
        
        # 3. 对比两个集合的配置
        print("=" * 80)
        print("🔍 对比分析")
        print("=" * 80)
        
        if config_data and data_source_configs and market_category and groupings:
            print("✅ 两个集合都有配置")
            print()
            
            # 提取 system_configs 中的优先级
            system_priorities = {}
            for ds in data_source_configs:
                name = ds.get('name', '')
                priority = ds.get('priority', 0)
                enabled = ds.get('enabled', False)
                system_priorities[name] = {'priority': priority, 'enabled': enabled}
            
            # 提取 datasource_groupings 中的优先级
            grouping_priorities = {}
            for group in groupings:
                name = group.get('data_source_name', '')
                priority = group.get('priority', 0)
                enabled = group.get('enabled', False)
                grouping_priorities[name] = {'priority': priority, 'enabled': enabled}
            
            # 对比
            all_names = set(system_priorities.keys()) | set(grouping_priorities.keys())
            
            print("数据源优先级对比:")
            print()
            print(f"{'数据源':<15} {'system_configs':<20} {'datasource_groupings':<20} {'状态':<10}")
            print("-" * 80)
            
            for name in sorted(all_names):
                sys_info = system_priorities.get(name, {})
                grp_info = grouping_priorities.get(name, {})
                
                sys_priority = sys_info.get('priority', '-')
                grp_priority = grp_info.get('priority', '-')
                
                sys_enabled = '✅' if sys_info.get('enabled', False) else '❌'
                grp_enabled = '✅' if grp_info.get('enabled', False) else '❌'
                
                status = '✅ 一致' if sys_priority == grp_priority else '❌ 不一致'
                
                print(f"{name:<15} {str(sys_priority) + ' ' + sys_enabled:<20} {str(grp_priority) + ' ' + grp_enabled:<20} {status:<10}")
            
            print()
            
            # 显示最终的优先级顺序
            print("=" * 80)
            print("🎯 最终使用的数据源优先级顺序（从 system_configs 读取）:")
            print("=" * 80)
            
            enabled_sources = [
                ds for ds in sorted_configs
                if ds.get('enabled', False) and ds.get('type', '').lower() in ['tushare', 'akshare', 'baostock']
            ]
            
            if enabled_sources:
                for idx, ds in enumerate(enabled_sources, 1):
                    print(f"{idx}. {ds.get('name', 'Unknown')} (优先级: {ds.get('priority', 0)})")
            else:
                print("⚠️ 没有启用的数据源")
        
        print()
        print("=" * 80)
        print("✅ 检查完成")
        print("=" * 80)
        
    except Exception as e:
        print(f"❌ 错误: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    check_datasource_priority()

