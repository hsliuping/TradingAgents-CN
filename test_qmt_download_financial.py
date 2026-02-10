#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
测试 QMT download_financial_data2 方法（带回调的批量下载）
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

def on_progress(data):
    """下载进度回调函数"""
    total = data.get('total', 0)
    finished = data.get('finished', 0)
    stockcode = data.get('stockcode', '')
    message = data.get('message', '')
    
    # 计算进度百分比
    if total > 0:
        percent = (finished / total) * 100
        print(f"  📥 进度: {finished}/{total} ({percent:.1f}%) - {stockcode} {message}")
    else:
        print(f"  📥 {stockcode} {message}")

def test_download_financial_data2():
    """测试 download_financial_data2 方法"""
    print("=" * 60)
    print("🔍 测试 QMT download_financial_data2 方法")
    print("=" * 60)
    
    # 测试股票列表（少量股票以加快测试）
    stock_list = [
        "000001.SZ",  # 平安银行
        "600000.SH",  # 浦发银行
        "000002.SZ",  # 万科A
    ]
    
    # 只下载主要指标（减少下载时间）
    table_list = [
        'Pershareindex',  # 每股指标（主要指标）
        'Income',         # 利润表
    ]
    
    print(f"\n📊 测试股票: {', '.join(stock_list)}")
    print(f"📋 报表类型: {', '.join(table_list)}")
    print(f"⏰ 时间范围: 2023-01-01 至 2024-12-31")
    
    # 使用 download_financial_data2 下载
    print(f"\n⏬ 开始下载财务数据...")
    print(f"💡 提示: 这可能需要一些时间，请耐心等待...\n")
    
    try:
        xtdata.download_financial_data2(
            stock_list=stock_list,
            table_list=table_list,
            start_time='20230101',  # 起始时间（按披露日期）
            end_time='20241231',    # 结束时间（按披露日期）
            callback=on_progress    # 进度回调
        )
        
        print(f"\n✅ 下载完成！")
        
        # 验证下载的数据
        print(f"\n📥 验证下载的数据...")
        for stock_code in stock_list:
            print(f"\n  📊 {stock_code}:")
            
            financial_data = xtdata.get_financial_data(
                stock_list=[stock_code],
                table_list=table_list,
                start_time='20230101',
                end_time='20241231',
                report_type='announce_time'  # 按披露日期筛选
            )
            
            if financial_data and stock_code in financial_data:
                stock_data = financial_data[stock_code]
                
                for table_name, table_data in stock_data.items():
                    if table_data is not None and not table_data.empty:
                        print(f"    ✅ {table_name}: {len(table_data)} 条记录")
                        
                        # 显示最新一期
                        if len(table_data) > 0:
                            latest = table_data.iloc[0]
                            
                            if table_name == 'Pershareindex':
                                print(f"       最新: {latest.get('m_timetag', 'N/A')} "
                                      f"EPS={latest.get('s_fa_eps_basic', 'N/A')} "
                                      f"BPS={latest.get('s_fa_bps', 'N/A')}")
                            elif table_name == 'Income':
                                print(f"       最新: {latest.get('m_timetag', 'N/A')} "
                                      f"营收={latest.get('revenue_inc', 'N/A')} "
                                      f"净利={latest.get('net_profit_incl_min_int_inc', 'N/A')}")
                    else:
                        print(f"    ❌ {table_name}: 无数据")
            else:
                print(f"    ❌ 未获取到数据")
        
    except Exception as e:
        print(f"\n❌ 下载失败: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_download_financial_data2()

