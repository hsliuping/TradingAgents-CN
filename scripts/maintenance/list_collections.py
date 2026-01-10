"""
列出数据库中的所有集合及其文档数量

用法：
    python scripts/maintenance/list_collections.py
"""

import sys
from pathlib import Path

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from pymongo import MongoClient
import os
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()


def list_collections():
    """列出所有集合及其文档数量"""
    
    # 连接数据库
    mongo_host = os.getenv("MONGODB_HOST", "127.0.0.1")
    mongo_port = int(os.getenv("MONGODB_PORT", "27017"))
    mongo_username = os.getenv("MONGODB_USERNAME", "admin")
    mongo_password = os.getenv("MONGODB_PASSWORD", "tradingagents123")
    mongo_auth_source = os.getenv("MONGODB_AUTH_SOURCE", "admin")
    db_name = os.getenv("MONGODB_DATABASE", "tradingagents")
    
    # 构建 MongoDB URI
    mongo_uri = f"mongodb://{mongo_username}:{mongo_password}@{mongo_host}:{mongo_port}/{db_name}?authSource={mongo_auth_source}"
    
    client = MongoClient(mongo_uri)
    db = client[db_name]
    
    print("=" * 80)
    print("📊 数据库集合统计")
    print("=" * 80)
    print(f"数据库: {db_name}")
    print("=" * 80)
    
    try:
        # 获取所有集合名称
        collection_names = db.list_collection_names()
        
        # 过滤掉系统集合
        collection_names = [c for c in collection_names if not c.startswith("system.")]
        
        # 按名称排序
        collection_names.sort()
        
        print(f"\n总集合数: {len(collection_names)}\n")
        
        # 统计每个集合的文档数量
        collection_stats = []
        max_name_len = max(len(name) for name in collection_names) if collection_names else 0
        
        for collection_name in collection_names:
            collection = db[collection_name]
            count = collection.count_documents({})
            collection_stats.append((collection_name, count))
        
        # 按文档数量降序排序
        collection_stats.sort(key=lambda x: x[1], reverse=True)
        
        # 打印统计信息
        print(f"{'集合名称':<{max_name_len + 2}} {'文档数量':>12}")
        print("-" * (max_name_len + 16))
        
        total_docs = 0
        for name, count in collection_stats:
            print(f"{name:<{max_name_len + 2}} {count:>12,}")
            total_docs += count
        
        print("-" * (max_name_len + 16))
        print(f"{'总计':<{max_name_len + 2}} {total_docs:>12,}")
        print()
        
        # 分类显示
        print("=" * 80)
        print("📋 集合分类")
        print("=" * 80)
        
        # v2.0 核心配置
        v2_core = [
            'workflow_definitions', 'agent_configs', 'tool_configs',
            'tool_agent_bindings', 'agent_workflow_bindings', 'agent_io_definitions'
        ]
        
        # 系统配置
        system_config = [
            'system_configs', 'llm_providers', 'model_catalog',
            'platform_configs', 'datasource_groupings', 'market_categories'
        ]
        
        # 用户相关
        user_related = [
            'users', 'user_configs', 'user_tags', 'user_favorites',
            'user_sessions', 'user_activities'
        ]
        
        # 交易系统
        trading_system = [
            'trading_systems', 'trading_system_versions'
        ]
        
        # 提示词
        prompt_related = [
            'prompt_templates', 'user_template_configs'
        ]
        
        # 分析任务和报告
        analysis_related = [
            'unified_analysis_tasks', 'analysis_tasks', 'analysis_reports',
            'analysis_progress'
        ]
        
        # 股票数据
        stock_data = [
            'stock_basic_info', 'market_quotes', 'stock_financial_data',
            'stock_news'
        ]
        
        # 其他
        other = []
        
        categories = {
            "v2.0 核心配置": v2_core,
            "系统配置": system_config,
            "用户相关": user_related,
            "交易系统": trading_system,
            "提示词": prompt_related,
            "分析任务和报告": analysis_related,
            "股票数据": stock_data,
        }
        
        # 找出未分类的集合
        all_categorized = set()
        for cat_collections in categories.values():
            all_categorized.update(cat_collections)
        
        for name in collection_names:
            if name not in all_categorized:
                other.append(name)
        
        if other:
            categories["其他"] = other
        
        # 打印分类
        for category, cat_collections in categories.items():
            existing = [c for c in cat_collections if c in collection_names]
            if existing:
                print(f"\n{category} ({len(existing)} 个):")
                for name in existing:
                    count = next((c for n, c in collection_stats if n == name), 0)
                    print(f"  ✓ {name:<40} {count:>10,} 条")
        
        print()
    
    finally:
        client.close()


if __name__ == "__main__":
    list_collections()

