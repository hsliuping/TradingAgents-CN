#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
测试 QMT 财务数据获取（简化版）
"""
import sys
import os

# 添加项目根目录到 Python 路径
project_root = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, project_root)

try:
    import xtquant.xtdata as xtdata
except ImportError:
    print("❌ xtquant 未安装")
    sys.exit(1)

def test_financial_data_simple():
    """测试财务数据获取（不下载，只查询本地）"""
    print("=" * 60)
    print("🔍 测试 QMT 财务数据获取（查询本地数据）")
    print("=" * 60)
    
    # 测试股票
    stock_code = "000001.SZ"  # 平安银行
    
    # 只测试主要指标
    table_list = ['Pershareindex']  # 每股指标（主要指标）
    
    print(f"\n📊 测试股票: {stock_code}")
    print(f"📋 报表类型: {', '.join(table_list)}")
    
    # 直接获取财务数据（不下载）
    print(f"\n📥 获取本地财务数据...")
    try:
        financial_data = xtdata.get_financial_data(
            stock_list=[stock_code],
            table_list=table_list,
            start_time='',  # 空表示最早
            end_time='',    # 空表示最新
            report_type='report_time'  # 按截止日期筛选
        )
        
        if financial_data and stock_code in financial_data:
            stock_data = financial_data[stock_code]
            print(f"✅ 成功获取财务数据")
            
            for table_name, table_data in stock_data.items():
                if table_data is not None and not table_data.empty:
                    print(f"\n  📋 {table_name}:")
                    print(f"     记录数: {len(table_data)}")
                    print(f"     字段数: {len(table_data.columns)}")
                    
                    # 显示最新一期数据
                    if len(table_data) > 0:
                        latest = table_data.iloc[0]
                        print(f"\n     最新一期数据:")
                        print(f"       披露日期: {latest.get('m_anntime', 'N/A')}")
                        print(f"       截止日期: {latest.get('m_timetag', 'N/A')}")
                        print(f"       每股收益: {latest.get('s_fa_eps_basic', 'N/A')}")
                        print(f"       每股净资产: {latest.get('s_fa_bps', 'N/A')}")
                        print(f"       净资产收益率: {latest.get('du_return_on_equity', 'N/A')}")
                        print(f"       每股经营现金流: {latest.get('s_fa_ocfps', 'N/A')}")
                else:
                    print(f"\n  ❌ {table_name}: 本地无数据")
                    print(f"  💡 提示: 需要先在 MiniQMT 中下载财务数据")
        else:
            print(f"❌ 未获取到财务数据")
            print(f"💡 提示: 本地可能没有该股票的财务数据")
            print(f"   可以在 MiniQMT 中手动下载，或使用 download_financial_data() 下载")
            
    except Exception as e:
        print(f"❌ 获取失败: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_financial_data_simple()

