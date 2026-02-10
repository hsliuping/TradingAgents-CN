#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
测试 QMT 适配器的财务数据功能
"""
import sys
import os

# 添加项目根目录到 Python 路径
project_root = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, project_root)

from app.services.data_sources.qmt_adapter import QMTAdapter

def on_progress(data):
    """下载进度回调函数"""
    total = data.get('total', 0)
    finished = data.get('finished', 0)
    stockcode = data.get('stockcode', '')
    
    if total > 0:
        percent = (finished / total) * 100
        print(f"  📥 进度: {finished}/{total} ({percent:.1f}%) - {stockcode}")

def test_qmt_adapter_financial():
    """测试 QMT 适配器的财务数据功能"""
    print("=" * 60)
    print("🔍 测试 QMT 适配器 - 财务数据功能")
    print("=" * 60)
    
    # 创建 QMT 适配器实例
    adapter = QMTAdapter()
    
    # 检查可用性
    print("\n1️⃣ 检查 QMT 适配器可用性...")
    if not adapter.is_available():
        print("❌ QMT 适配器不可用")
        return
    print("✅ QMT 适配器可用")
    
    # 测试股票列表
    test_stocks = ["000001", "600000"]
    
    # 测试下载财务数据
    print(f"\n2️⃣ 测试下载财务数据 - {', '.join(test_stocks)}...")
    success = adapter.download_financial_data(
        stock_list=test_stocks,
        table_list=['Pershareindex', 'Income'],
        start_time='20230101',
        end_time='20241231',
        callback=on_progress
    )
    
    if success:
        print("✅ 财务数据下载成功")
    else:
        print("❌ 财务数据下载失败")
        return
    
    # 测试获取财务数据
    print(f"\n3️⃣ 测试获取财务数据...")
    for code in test_stocks:
        print(f"\n  📊 {code}:")
        
        financial_data = adapter.get_financial_data(
            code=code,
            table_list=['Pershareindex', 'Income'],
            start_time='20230101',
            end_time='20241231',
            report_type='announce_time'
        )
        
        if financial_data:
            for table_name, df in financial_data.items():
                print(f"    ✅ {table_name}: {len(df)} 条记录")
                
                # 显示最新一期数据
                if len(df) > 0:
                    latest = df.iloc[0]
                    
                    if table_name == 'Pershareindex':
                        print(f"       最新: {latest.get('m_timetag', 'N/A')} "
                              f"EPS={latest.get('s_fa_eps_basic', 'N/A')} "
                              f"BPS={latest.get('s_fa_bps', 'N/A')}")
                    elif table_name == 'Income':
                        print(f"       最新: {latest.get('m_timetag', 'N/A')} "
                              f"营收={latest.get('revenue_inc', 'N/A')} "
                              f"净利={latest.get('net_profit_incl_min_int_inc', 'N/A')}")
        else:
            print(f"    ❌ 未获取到财务数据")
    
    print("\n" + "=" * 60)
    print("✅ QMT 适配器财务数据功能测试完成")
    print("=" * 60)

if __name__ == "__main__":
    test_qmt_adapter_financial()

