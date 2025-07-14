#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
增强版股票列表获取示例
演示如何使用从tdx_servers_config.json配置文件中获取数据服务器参数
"""

from enhanced_stock_list_fetcher import enhanced_fetch_stock_list
import pandas as pd
import json

def demo_stock_list_fetcher():
    """演示增强版股票列表获取功能"""
    print("=== 增强版股票列表获取演示 ===")
    print("\n功能特点:")
    print("1. 从tdx_servers_config.json自动加载服务器配置")
    print("2. 支持服务器故障转移")
    print("3. 获取完整的股票、指数、ETF信息")
    print("4. 自动数据清洗和去重")
    
    # 演示不同类型的数据获取
    data_types = {
        'stock': '股票',
        'index': '指数', 
        'etf': 'ETF基金',
        'all': '全部数据'
    }
    
    for type_key, type_name in data_types.items():
        print(f"\n=== 获取{type_name}数据 ===")
        
        try:
            # 调用增强版股票列表获取函数
            result = enhanced_fetch_stock_list(
                type_=type_key,
                enable_server_failover=True,  # 启用服务器故障转移
                max_retries=2  # 每个服务器最多重试2次
            )
            
            if result is not None and not result.empty:
                print(f"✅ 成功获取 {len(result)} 条{type_name}数据")
                
                # 转换为DataFrame便于查看
                df = pd.DataFrame(result)
                print(f"\n数据列: {list(df.columns)}")
                
                # 显示前5条数据
                print(f"\n前5条{type_name}数据:")
                print(df.head().to_string(index=False))
                
                # 显示统计信息
                if 'sse' in df.columns:
                    market_counts = df['sse'].value_counts()
                    print(f"\n市场分布:")
                    for market, count in market_counts.items():
                        market_name = '上海' if market == 1 else '深圳'
                        print(f"  {market_name}市场: {count} 只")
                        
            else:
                print(f"❌ 未能获取到{type_name}数据")
                
        except Exception as e:
            print(f"❌ 获取{type_name}数据时发生错误: {str(e)}")
            
        # 只演示第一种类型，避免过多网络请求
        print("\n注意: 为避免过多网络请求，此演示只获取股票数据")
        print("实际使用时可以获取所有类型的数据")
        break

def show_usage_examples():
    """显示使用示例"""
    print("\n=== 使用示例 ===")
    
    examples = [
        {
            'title': '获取所有股票数据',
            'code': '''result = enhanced_fetch_stock_list(type_='stock')'''
        },
        {
            'title': '获取所有指数数据',
            'code': '''result = enhanced_fetch_stock_list(type_='index')'''
        },
        {
            'title': '获取ETF数据',
            'code': '''result = enhanced_fetch_stock_list(type_='etf')'''
        },
        {
            'title': '获取全部数据（股票+指数+ETF）',
            'code': '''result = enhanced_fetch_stock_list(type_='all')'''
        },
        {
            'title': '启用服务器故障转移',
            'code': '''result = enhanced_fetch_stock_list(
    type_='stock',
    enable_server_failover=True,
    max_retries=3
)'''
        },
        {
            'title': '指定服务器IP和端口',
            'code': '''result = enhanced_fetch_stock_list(
    type_='stock',
    ip='115.238.56.198',
    port=7709
)'''
        }
    ]
    
    for i, example in enumerate(examples, 1):
        print(f"\n{i}. {example['title']}:")
        print(f"```python\n{example['code']}\n```")

if __name__ == "__main__":
    # 显示使用示例
    show_usage_examples()
    
    # 演示功能（注释掉以避免实际网络请求）
    print("\n" + "="*50)
    print("如需测试实际功能，请取消下面代码的注释:")
    print("# demo_stock_list_fetcher()")
    
    # 取消注释下面这行来运行实际演示
    demo_stock_list_fetcher()