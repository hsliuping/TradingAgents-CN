#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""分析 test2.json 的结构，找出重复内容"""

import json
from pathlib import Path

def analyze_structure():
    """分析 JSON 结构"""
    json_file = Path(__file__).parent.parent / "logs" / "test2.json"
    
    with open(json_file, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    result = data.get('data', {}).get('result_data', {})
    reports = result.get('reports', {})
    state = result.get('state', {})
    detailed = result.get('detailed_analysis', {})
    
    print("=" * 80)
    print("JSON 结构分析")
    print("=" * 80)
    
    print("\n【顶层字段】")
    print(f"  {list(result.keys())}")
    
    print("\n【reports 字段】")
    print(f"  数量: {len(reports)}")
    print(f"  字段: {list(reports.keys())}")
    
    print("\n【state 字段】")
    print(f"  数量: {len(state)}")
    print(f"  主要字段: {list(state.keys())[:20]}")  # 只显示前20个
    
    print("\n【detailed_analysis 字段】")
    print(f"  数量: {len(detailed)}")
    print(f"  主要字段: {list(detailed.keys())[:20]}")
    
    print("\n" + "=" * 80)
    print("重复内容分析")
    print("=" * 80)
    
    # 1. final_trade_decision
    print("\n1. final_trade_decision:")
    ft_reports = reports.get('final_trade_decision')
    ft_state = state.get('final_trade_decision')
    ft_detailed = detailed.get('structured_reports', {}).get('final_trade_decision')
    
    print(f"  ✓ reports.final_trade_decision: {'存在' if ft_reports else '不存在'}")
    if ft_reports:
        print(f"    类型: {type(ft_reports).__name__}, 长度: {len(str(ft_reports))}")
    
    print(f"  ✓ state.final_trade_decision: {'存在' if ft_state else '不存在'}")
    if ft_state:
        print(f"    类型: {type(ft_state).__name__}, 长度: {len(str(ft_state))}")
    
    print(f"  ✓ detailed_analysis.structured_reports.final_trade_decision: {'存在' if ft_detailed else '不存在'}")
    if ft_detailed:
        print(f"    类型: {type(ft_detailed).__name__}")
        if isinstance(ft_detailed, dict):
            print(f"    字段: {list(ft_detailed.keys())}")
    
    # 2. investment_plan
    print("\n2. investment_plan:")
    ip_reports = reports.get('investment_plan')
    ip_state = state.get('investment_plan')
    print(f"  ✓ reports.investment_plan: {'存在' if ip_reports else '不存在'}")
    if ip_reports:
        print(f"    类型: {type(ip_reports).__name__}, 长度: {len(str(ip_reports))}")
    print(f"  ✓ state.investment_plan: {'存在' if ip_state else '不存在'}")
    
    # 3. 研究员报告
    print("\n3. 研究员报告:")
    bull_reports = reports.get('bull_researcher')
    bull_state = state.get('investment_debate_state', {}).get('bull_history')
    print(f"  ✓ reports.bull_researcher: {'存在' if bull_reports else '不存在'}")
    if bull_reports:
        print(f"    长度: {len(str(bull_reports))}")
    print(f"  ✓ state.investment_debate_state.bull_history: {'存在' if bull_state else '不存在'}")
    if bull_state:
        print(f"    长度: {len(str(bull_state))}")
    
    # 4. 风险分析师报告
    print("\n4. 风险分析师报告:")
    risky_reports = reports.get('risky_analyst')
    risky_state = state.get('risk_debate_state', {}).get('risky_history')
    print(f"  ✓ reports.risky_analyst: {'存在' if risky_reports else '不存在'}")
    if risky_reports:
        print(f"    长度: {len(str(risky_reports))}")
    print(f"  ✓ state.risk_debate_state.risky_history: {'存在' if risky_state else '不存在'}")
    if risky_state:
        print(f"    长度: {len(str(risky_state))}")
    
    # 5. 统计重复字段
    print("\n" + "=" * 80)
    print("字段重复统计")
    print("=" * 80)
    
    # reports 和 state 的重复
    reports_keys = set(reports.keys())
    state_keys = set(state.keys())
    common_keys = reports_keys & state_keys
    
    print(f"\nreports 和 state 的重复字段 ({len(common_keys)} 个):")
    for key in sorted(common_keys):
        print(f"  - {key}")
    
    # 检查内容是否相同
    print("\n内容是否相同:")
    for key in sorted(common_keys)[:5]:  # 只检查前5个
        r_val = str(reports.get(key, ''))
        s_val = str(state.get(key, ''))
        is_same = r_val == s_val
        print(f"  {key}: {'相同' if is_same else '不同'} (reports长度:{len(r_val)}, state长度:{len(s_val)})")
    
    # 6. 数据大小统计
    print("\n" + "=" * 80)
    print("数据大小统计")
    print("=" * 80)
    
    import sys
    reports_size = sys.getsizeof(json.dumps(reports, ensure_ascii=False))
    state_size = sys.getsizeof(json.dumps(state, ensure_ascii=False))
    detailed_size = sys.getsizeof(json.dumps(detailed, ensure_ascii=False))
    
    print(f"\nreports 大小: {reports_size / 1024:.2f} KB")
    print(f"state 大小: {state_size / 1024:.2f} KB")
    print(f"detailed_analysis 大小: {detailed_size / 1024:.2f} KB")
    print(f"总计: {(reports_size + state_size + detailed_size) / 1024:.2f} KB")

if __name__ == '__main__':
    analyze_structure()
