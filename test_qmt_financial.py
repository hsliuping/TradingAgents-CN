#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
测试 QMT 财务数据获取
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

def test_financial_data():
    """测试财务数据获取"""
    print("=" * 60)
    print("🔍 测试 QMT 财务数据获取")
    print("=" * 60)
    
    # 测试股票
    stock_code = "000001.SZ"  # 平安银行
    
    # 支持的财务报表
    table_list = [
        'Balance',          # 资产负债表
        'Income',           # 利润表
        'CashFlow',         # 现金流量表
        'Pershareindex',    # 每股指标（主要指标）
        'Capital',          # 股本表
        'Top10holder',      # 十大股东
        'Top10flowholder',  # 十大流通股东
        'Holdernum',        # 股东数
    ]
    
    print(f"\n📊 测试股票: {stock_code}")
    print(f"📋 报表类型: {', '.join(table_list)}")
    
    # 先下载财务数据
    print(f"\n⏬ 下载财务数据...")
    try:
        xtdata.download_financial_data([stock_code], table_list)
        print("✅ 下载完成")
    except Exception as e:
        print(f"⚠️  下载失败: {e}")
    
    # 获取财务数据
    print(f"\n📥 获取财务数据...")
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
            print(f"\n📊 数据概览:")
            
            for table_name, table_data in stock_data.items():
                if table_data is not None and not table_data.empty:
                    print(f"\n  📋 {table_name}:")
                    print(f"     记录数: {len(table_data)}")
                    print(f"     字段数: {len(table_data.columns)}")
                    print(f"     字段列表: {', '.join(table_data.columns[:10].tolist())}...")
                    
                    # 显示最新一期数据的部分字段
                    if len(table_data) > 0:
                        latest = table_data.iloc[0]
                        print(f"     最新一期:")
                        
                        # 根据不同报表显示关键字段
                        if table_name == 'Income':
                            print(f"       披露日期: {latest.get('m_anntime', 'N/A')}")
                            print(f"       截止日期: {latest.get('m_timetag', 'N/A')}")
                            print(f"       营业收入: {latest.get('revenue_inc', 'N/A')}")
                            print(f"       净利润: {latest.get('net_profit_incl_min_int_inc', 'N/A')}")
                        elif table_name == 'Balance':
                            print(f"       披露日期: {latest.get('m_anntime', 'N/A')}")
                            print(f"       截止日期: {latest.get('m_timetag', 'N/A')}")
                            print(f"       总资产: {latest.get('tot_assets', 'N/A')}")
                            print(f"       总负债: {latest.get('tot_liab', 'N/A')}")
                        elif table_name == 'Pershareindex':
                            print(f"       披露日期: {latest.get('m_anntime', 'N/A')}")
                            print(f"       截止日期: {latest.get('m_timetag', 'N/A')}")
                            print(f"       每股收益: {latest.get('s_fa_eps_basic', 'N/A')}")
                            print(f"       每股净资产: {latest.get('s_fa_bps', 'N/A')}")
                            print(f"       净资产收益率: {latest.get('du_return_on_equity', 'N/A')}")
                        elif table_name == 'Capital':
                            print(f"       报告日期: {latest.get('m_timetag', 'N/A')}")
                            print(f"       总股本: {latest.get('total_capital', 'N/A')}")
                            print(f"       流通股本: {latest.get('circulating_capital', 'N/A')}")
                else:
                    print(f"\n  ❌ {table_name}: 无数据")
        else:
            print(f"❌ 未获取到财务数据")
            
    except Exception as e:
        print(f"❌ 获取失败: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_financial_data()

