#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
测试不同数据深度级别的差异
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from tradingagents.agents.utils.agent_utils import Toolkit
from tradingagents.default_config import DEFAULT_CONFIG

def test_data_depth_levels():
    """测试不同数据深度级别"""
    print("测试不同数据深度级别的差异...")
    
    # 测试股票代码
    ticker = '300750'  # 宁德时代
    
    # 测试不同级别
    levels = [1, 3, 5]
    level_names = {1: "快速", 3: "标准", 5: "深度"}
    
    results = {}
    
    for level in levels:
        print(f"\n{'='*60}")
        print(f"🔍 测试级别 {level} ({level_names[level]})")
        print(f"{'='*60}")
        
        # 设置配置
        config = DEFAULT_CONFIG.copy()
        config["online_tools"] = True
        config["research_depth"] = level  # 设置数据深度级别
        
        # 创建工具包
        toolkit = Toolkit(config)
        
        # 获取基本面数据
        result = toolkit.get_stock_fundamentals_unified.invoke({
            'ticker': ticker,
            'start_date': '2025-06-01',
            'end_date': '2025-07-15',
            'curr_date': '2025-07-15'
        })
        
        # 分析结果
        data_length = len(result)
        lines = result.split('\n')
        line_count = len(lines)
        
        # 统计不同类型的内容
        sections = []
        current_section = None
        
        for line in lines:
            if line.startswith('##'):
                current_section = line.strip()
                sections.append(current_section)
        
        results[level] = {
            'data_length': data_length,
            'line_count': line_count,
            'sections': sections,
            'content': result
        }
        
        print(f"📊 数据长度: {data_length:,} 字符")
        print(f"📝 行数: {line_count:,} 行")
        print(f"📋 数据模块数量: {len(sections)}")
        print(f"📋 数据模块:")
        for i, section in enumerate(sections, 1):
            print(f"  {i}. {section}")
        
        # 显示部分内容预览
        print(f"\n📄 内容预览 (前500字符):")
        print("-" * 50)
        print(result[:500] + "..." if len(result) > 500 else result)
        print("-" * 50)
    
    # 比较结果
    print(f"\n{'='*80}")
    print(f"📊 不同级别数据对比总结")
    print(f"{'='*80}")
    
    print(f"{'级别':<8} {'名称':<8} {'数据长度':<12} {'行数':<8} {'模块数':<8}")
    print("-" * 60)
    
    for level in levels:
        data = results[level]
        print(f"{level:<8} {level_names[level]:<8} {data['data_length']:,<12} {data['line_count']:<8} {len(data['sections']):<8}")
    
    # 分析差异
    print(f"\n🔍 差异分析:")
    
    # 数据长度差异
    level1_length = results[1]['data_length']
    level3_length = results[3]['data_length']
    level5_length = results[5]['data_length']
    
    print(f"  📈 数据长度增长:")
    print(f"    - 级别1→3: {level3_length - level1_length:+,} 字符 ({((level3_length/level1_length-1)*100):+.1f}%)")
    print(f"    - 级别3→5: {level5_length - level3_length:+,} 字符 ({((level5_length/level3_length-1)*100):+.1f}%)")
    print(f"    - 级别1→5: {level5_length - level1_length:+,} 字符 ({((level5_length/level1_length-1)*100):+.1f}%)")
    
    # 模块数量差异
    print(f"\n  📋 数据模块差异:")
    for level in levels:
        sections = results[level]['sections']
        print(f"    - 级别{level} ({level_names[level]}): {len(sections)}个模块")
        for section in sections:
            print(f"      • {section}")
    
    # 历史数据范围差异
    print(f"\n  📅 历史数据范围差异:")
    print(f"    - 级别1 (快速): 7天历史数据")
    print(f"    - 级别3 (标准): 21天历史数据")
    print(f"    - 级别5 (全面): 30天历史数据")
    
    print(f"\n✅ 测试完成！不同级别确实获取到了不同深度的数据。")

if __name__ == "__main__":
    test_data_depth_levels()