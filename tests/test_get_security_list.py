#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试Tushare数据接口的get_security_list函数
查看返回的字段结构，特别是是否包含股票名称字段
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from tradingagents.dataflows.tdx_utils import TongDaXinDataProvider
import json

def test_get_security_list():
    """测试get_security_list函数"""
    print("=== 测试Tushare数据接口 get_security_list函数 ===")
    
    try:
        # 创建通达信数据提供者
        provider = TongDaXinDataProvider()
        
        print("正在连接Tushare数据接口...")
        if not provider.connect():
            print("❌ Tushare数据接口连接失败")
            return
            
        print("✅ Tushare数据接口连接成功")
        
        # 测试获取深圳市场股票列表
        print("\n📊 获取深圳市场股票列表 (market=0)")
        try:
            sz_list = provider.api.get_security_list(0, 0)  # 深圳市场，起始位置0
            print(f"获取到 {len(sz_list)} 条深圳市场数据")
            
            if sz_list and len(sz_list) > 0:
                print("\n第一条数据的完整字段结构:")
                first_stock = sz_list[0]
                print(json.dumps(first_stock, ensure_ascii=False, indent=2))
                
                print("\n所有可用字段:")
                for key in first_stock.keys():
                    print(f"  - {key}: {first_stock[key]}")
                
                print("\n前3条数据示例:")
                for i, stock in enumerate(sz_list[:3]):
                    print(f"  {i+1}. 代码: {stock.get('code', 'N/A')}, 名称: {stock.get('name', 'N/A')}")
                    print(f"     完整数据: {stock}")
            else:
                print("❌ 未获取到深圳市场数据")
                
        except Exception as e:
            print(f"❌ 获取深圳市场数据失败: {e}")
        
        # 测试获取上海市场股票列表
        print("\n📊 获取上海市场股票列表 (market=1)")
        try:
            sh_list = provider.api.get_security_list(1, 0)  # 上海市场，起始位置0
            print(f"获取到 {len(sh_list)} 条上海市场数据")
            
            if sh_list and len(sh_list) > 0:
                print("\n第一条数据的完整字段结构:")
                first_stock = sh_list[0]
                print(json.dumps(first_stock, ensure_ascii=False, indent=2))
                
                print("\n前3条数据示例:")
                for i, stock in enumerate(sh_list[:3]):
                    print(f"  {i+1}. 代码: {stock.get('code', 'N/A')}, 名称: {stock.get('name', 'N/A')}")
                    print(f"     完整数据: {stock}")
            else:
                print("❌ 未获取到上海市场数据")
                
        except Exception as e:
            print(f"❌ 获取上海市场数据失败: {e}")
        
        # 断开连接
        provider.disconnect()
        print("\n✅ 测试完成，已断开连接")
        
    except Exception as e:
        print(f"❌ 测试过程中出错: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_get_security_list()