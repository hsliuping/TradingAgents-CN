#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
DCF (现金流折现) 估值计算器 - 基于《股市真规则》晨星公司标准

作者: 弗兰克小斯基（Frankski）
Copyright (c) 2026 弗兰克小斯基（Frankski）. All rights reserved.

使用许可:
- 允许个人学习、研究、非商业用途使用
- 允许修改后个人使用
- 禁止直接复制核心算法用于商业产品或竞争性服务
- 禁止移除或修改作者署名后重新分发

免责声明: 本脚本提供的分析结果仅供参考，不构成投资建议。

参考: 《股市真规则》帕特·多尔西 (Pat Dorsey)
"""

import argparse
import json
import sys
from datetime import datetime
from typing import List, Dict, Tuple


# 晨星公司标准参数
MORNINGSTAR_BENCHMARKS = {
    "strong_moat": {
        "name": "强竞争优势公司",
        "discount_rate": 0.09,
        "safety_margin_required": 0.20,
        "examples": ["强生", "高露洁", "沃尔玛", "腾讯"]
    },
    "average": {
        "name": "一般公司",
        "discount_rate": 0.105,
        "safety_margin_required": 0.30,
        "examples": ["标普500平均公司"]
    },
    "high_risk": {
        "name": "高风险公司",
        "discount_rate": 0.14,
        "safety_margin_required": 0.60,
        "examples": ["AMD", "捷兰航空", "E*Trade", "周期股"]
    }
}

# 折现率调整因素（6个风险因素）
RISK_ADJUSTMENTS = {
    "small_size": {"desc": "小市值", "adjustment": 0.015},
    "high_leverage": {"desc": "高负债", "adjustment": 0.015},
    "cyclical": {"desc": "周期性行业", "adjustment": 0.015},
    "poor_management": {"desc": "管理层可信度低", "adjustment": 0.01},
    "weak_moat": {"desc": "弱竞争优势", "adjustment": 0.015},
    "complexity": {"desc": "业务复杂", "adjustment": 0.01}
}


def calculate_discount_rate(
    base_rate: float = 0.105,
    risk_factors: List[str] = None
) -> Tuple[float, str]:
    """
    计算折现率 - 基于晨星6因素风险调整法
    
    Args:
        base_rate: 基准折现率（默认10.5%晨星标准）
        risk_factors: 风险因素列表
        
    Returns:
        (调整后的折现率, 调整说明)
    """
    if risk_factors is None:
        return base_rate, f"基准折现率: {base_rate*100:.1f}%"
    
    adjustments = []
    total_adjustment = 0.0
    
    for factor in risk_factors:
        if factor in RISK_ADJUSTMENTS:
            adj = RISK_ADJUSTMENTS[factor]["adjustment"]
            total_adjustment += adj
            adjustments.append(f"{RISK_ADJUSTMENTS[factor]['desc']}: +{adj*100:.1f}%")
    
    final_rate = base_rate + total_adjustment
    explanation = f"基准: {base_rate*100:.1f}%\n调整:\n" + "\n".join(adjustments)
    
    return final_rate, explanation


def get_morningstar_preset(preset_name: str) -> Dict:
    """
    获取晨星预设参数
    
    Args:
        preset_name: 'strong_moat', 'average', 'high_risk'
        
    Returns:
        预设参数字典
    """
    if preset_name in MORNINGSTAR_BENCHMARKS:
        return MORNINGSTAR_BENCHMARKS[preset_name]
    return MORNINGSTAR_BENCHMARKS["average"]


def calculate_dcf(
    current_fcf: float,
    growth_rates: List[float],
    terminal_growth: float,
    discount_rate: float,
    net_debt: float = 0,
    shares_outstanding: float = 1
) -> Dict:
    """
    计算 DCF 估值 - 晨星标准5步法
    
    Args:
        current_fcf: 当前年度自由现金流（亿元）
        growth_rates: 预测期增速列表（10年）
        terminal_growth: 永续增速（通常3%，衰退行业2%）
        discount_rate: 折现率
        net_debt: 净负债（亿元，负数为净现金）
        shares_outstanding: 总股本（亿股）
    
    Returns:
        dict: 包含每股内在价值、安全边际等
    """
    
    # 预测期现金流折现
    pv_fcf = 0
    fcf = current_fcf
    fcf_projections = []
    
    for i, growth in enumerate(growth_rates):
        year = i + 1
        fcf = fcf * (1 + growth)
        pv = fcf / ((1 + discount_rate) ** year)
        pv_fcf += pv
        fcf_projections.append({
            "year": year,
            "fcf": fcf,
            "growth": growth,
            "pv": pv
        })
    
    # 终值计算（永续年金价值）
    # 公式: TV = FCF_10 × (1 + g) / (R - g)
    terminal_fcf = fcf * (1 + terminal_growth)
    terminal_value = terminal_fcf / (discount_rate - terminal_growth)
    pv_terminal = terminal_value / ((1 + discount_rate) ** len(growth_rates))
    
    # 企业价值
    enterprise_value = pv_fcf + pv_terminal
    
    # 股权价值
    equity_value = enterprise_value - net_debt
    
    # 每股内在价值
    intrinsic_value_per_share = equity_value / shares_outstanding
    
    return {
        "projections": fcf_projections,
        "pv_forecast_period": pv_fcf,
        "terminal_value": terminal_value,
        "pv_terminal": pv_terminal,
        "enterprise_value": enterprise_value,
        "net_debt": net_debt,
        "equity_value": equity_value,
        "shares_outstanding": shares_outstanding,
        "intrinsic_value_per_share": intrinsic_value_per_share,
        "parameters": {
            "current_fcf": current_fcf,
            "growth_rates": growth_rates,
            "terminal_growth": terminal_growth,
            "discount_rate": discount_rate
        }
    }


def calculate_safety_margin(
    intrinsic_value: float,
    current_price: float
) -> float:
    """
    计算安全边际
    公式: (内在价值 - 当前价格) / 内在价值
    """
    if intrinsic_value <= 0:
        return 0
    return (intrinsic_value - current_price) / intrinsic_value


def evaluate_investment_opportunity(
    intrinsic_value: float,
    current_price: float,
    moat_strength: str
) -> Dict:
    """
    评估投资机会 - 基于晨星安全边际标准
    
    Args:
        intrinsic_value: 每股内在价值
        current_price: 当前股价
        moat_strength: 'strong', 'average', 'weak'
    """
    margin = calculate_safety_margin(intrinsic_value, current_price)
    
    # 根据护城河强度确定要求的安全边际
    requirements = {
        "strong": (0.20, "强竞争优势公司"),
        "average": (0.35, "一般公司"),
        "weak": (0.60, "高风险公司")
    }
    
    required_margin, category = requirements.get(moat_strength, (0.35, "一般公司"))
    
    # 评估结果
    if margin >= required_margin:
        action = "买入"
        recommendation = f"安全边际{margin*100:.1f}% > 要求{required_margin*100:.0f}%，符合买入标准"
    elif margin >= 0:
        action = "观望"
        recommendation = f"安全边际{margin*100:.1f}% < 要求{required_margin*100:.0f}%，等待更好价格"
    else:
        action = "卖出/回避"
        recommendation = f"高估{-margin*100:.1f}%，建议卖出或回避"
    
    return {
        "safety_margin": margin,
        "required_margin": required_margin,
        "company_category": category,
        "action": action,
        "recommendation": recommendation
    }


def generate_growth_rates(
    base_growth: float,
    decay_rate: float = 0.2,
    years: int = 10
) -> List[float]:
    """
    生成递减的增长率序列
    
    Args:
        base_growth: 前5年平均增速
        decay_rate: 衰减率（默认20%每年）
        years: 预测年数
    """
    rates = []
    growth = base_growth
    
    for i in range(years):
        if i >= 5:  # 第6年开始衰减
            growth = growth * (1 - decay_rate)
        rates.append(growth)
    
    return rates


def scenario_analysis(
    current_fcf: float,
    base_growth: float,
    terminal_growth: float,
    discount_rate: float,
    net_debt: float,
    shares_outstanding: float,
    current_price: float
) -> Dict:
    """
    情景分析 - 乐观/中性/悲观
    """
    scenarios = {
        "optimistic": {
            "growth_factor": 1.2,
            "discount_adj": -0.005,
            "name": "乐观情景"
        },
        "neutral": {
            "growth_factor": 1.0,
            "discount_adj": 0,
            "name": "中性情景"
        },
        "pessimistic": {
            "growth_factor": 0.8,
            "discount_adj": 0.01,
            "name": "悲观情景"
        }
    }
    
    results = {}
    
    for key, config in scenarios.items():
        growth_rates = generate_growth_rates(base_growth * config["growth_factor"])
        rate = discount_rate + config["discount_adj"]
        
        result = calculate_dcf(
            current_fcf=current_fcf,
            growth_rates=growth_rates,
            terminal_growth=terminal_growth,
            discount_rate=rate,
            net_debt=net_debt,
            shares_outstanding=shares_outstanding
        )
        
        margin = calculate_safety_margin(
            result["intrinsic_value_per_share"],
            current_price
        )
        
        results[key] = {
            "intrinsic_value": result["intrinsic_value_per_share"],
            "safety_margin": margin,
            "discount_rate": rate,
            "avg_growth": base_growth * config["growth_factor"]
        }
    
    return results


def format_dcf_report(result, current_price=None, moat_strength="average", 
                      risk_factors=None, scenario_results=None):
    """
    格式化 DCF 报告 - 晨星标准格式
    """
    params = result["parameters"]
    
    report = f"""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
💎 DCF 估值分析报告 (基于《股市真规则》晨星标准)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

📊 基础参数
  当前自由现金流: {params['current_fcf']:.2f} 亿元
  净负债: {result['net_debt']:.2f} 亿元 (负数为净现金)
  总股本: {result['shares_outstanding']:.2f} 亿股
"""
    
    # 折现率说明
    report += f"\n📈 折现率设定: {params['discount_rate']*100:.2f}%\n"
    if risk_factors:
        report += "  风险调整因素:\n"
        for factor in risk_factors:
            if factor in RISK_ADJUSTMENTS:
                report += f"    • {RISK_ADJUSTMENTS[factor]['desc']}: +{RISK_ADJUSTMENTS[factor]['adjustment']*100:.1f}%\n"
    
    # 增长假设
    report += f"\n📊 增长假设\n"
    report += f"  永续增长率: {params['terminal_growth']*100:.1f}% (GDP平均)\n"
    report += f"  预测期: {len(params['growth_rates'])}年\n"
    report += f"  前5年平均增速: {sum(params['growth_rates'][:5])/5*100:.1f}%\n"
    
    # 10年预测详情（简化显示前5年和最后一年）
    report += f"\n📈 现金流预测（10年）\n"
    for proj in result["projections"][:5]:
        report += f"  第{proj['year']:2d}年: FCF={proj['fcf']:8.2f}亿, 增速={proj['growth']*100:5.1f}%, 现值={proj['pv']:7.2f}亿\n"
    report += f"  ...\n"
    final_proj = result["projections"][-1]
    report += f"  第{final_proj['year']:2d}年: FCF={final_proj['fcf']:8.2f}亿, 增速={final_proj['growth']*100:5.1f}%, 现值={final_proj['pv']:7.2f}亿\n"
    
    # 估值结果
    report += f"""
💰 估值结果
  预测期现值:     {result['pv_forecast_period']:10.2f} 亿元
  永续价值:       {result['terminal_value']:10.2f} 亿元
  永续价值现值:   {result['pv_terminal']:10.2f} 亿元
  ─────────────────────────────────────
  企业价值(EV):   {result['enterprise_value']:10.2f} 亿元
  股权价值:       {result['equity_value']:10.2f} 亿元
  ─────────────────────────────────────
  🎯 每股内在价值: {result['intrinsic_value_per_share']:8.2f} 元
"""
    
    # 安全边际分析
    if current_price and current_price > 0:
        evaluation = evaluate_investment_opportunity(
            result['intrinsic_value_per_share'],
            current_price,
            moat_strength
        )
        
        margin = evaluation["safety_margin"]
        
        report += f"""
📏 安全边际分析 ({evaluation['company_category']})
  当前价格:       {current_price:.2f} 元
  内在价值:       {result['intrinsic_value_per_share']:.2f} 元
  要求安全边际:   {evaluation['required_margin']*100:.0f}%
  实际安全边际:   {margin*100:+.1f}%
  ─────────────────────────────────────
  💡 投资建议: {evaluation['action']}
  📝 说明: {evaluation['recommendation']}
"""
        
        # 情景分析结果
        if scenario_results:
            report += f"\n📊 情景分析（不同增长假设）\n"
            report += "─" * 50 + "\n"
            report += f"{'情景':12} {'内在价值':12} {'安全边际':12} {'判断':10}\n"
            report += "─" * 50 + "\n"
            
            for key, data in scenario_results.items():
                name = {"optimistic": "乐观", "neutral": "中性", "pessimistic": "悲观"}[key]
                iv = data["intrinsic_value"]
                sm = data["safety_margin"]
                judge = "买入" if sm >= evaluation["required_margin"] else ("观望" if sm >= 0 else "高估")
                report += f"{name:12} {iv:12.2f} {sm*100:11.1f}% {judge:10}\n"
            
            report += "─" * 50 + "\n"
    
    report += "\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
    report += "📖 参考: 《股市真规则》帕特·多尔西 (晨星公司标准)\n"
    report += "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
    
    return report


def main():
    parser = argparse.ArgumentParser(
        description='DCF 估值计算器 - 基于《股市真规则》晨星标准',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # 使用晨星预设（强护城河公司）
  python dcf_calculator.py --fcf 100 --preset strong_moat --shares 10 --current-price 50
  
  # 使用晨星预设（高风险公司）
  python dcf_calculator.py --fcf 50 --preset high_risk --shares 5 --current-price 20
  
  # 自定义参数+风险调整
  python dcf_calculator.py --fcf 100 --growth 0.12 --terminal 0.03 --base-rate 0.105 \\
                           --risk small_size,high_leverage --shares 10 --current-price 80
  
  # 情景分析
  python dcf_calculator.py --fcf 100 --growth 0.15 --shares 10 --current-price 80 --scenario
        """
    )
    
    # 基本参数
    parser.add_argument('--fcf', type=float, required=True, help='当前年度自由现金流（亿元）')
    parser.add_argument('--shares', type=float, required=True, help='总股本（亿股）')
    parser.add_argument('--current-price', type=float, help='当前股价（用于计算安全边际）')
    parser.add_argument('--net-debt', type=float, default=0, help='净负债（亿元，负数为净现金，默认0）')
    
    # 增长参数
    growth_group = parser.add_mutually_exclusive_group()
    growth_group.add_argument('--growth', type=str, help='前5年增速，逗号分隔 (如 "0.15,0.12,0.10,0.08,0.06")')
    growth_group.add_argument('--base-growth', type=float, help='前5年平均增速（用于自动生成10年递减增速）')
    
    parser.add_argument('--terminal', type=float, default=0.03, help='永续增速 (默认 0.03=3%)')
    parser.add_argument('--decay', type=float, default=0.2, help='增速衰减率，第6年后 (默认 0.2=20%)')
    
    # 折现率参数
    discount_group = parser.add_mutually_exclusive_group()
    discount_group.add_argument('--preset', type=str, choices=['strong_moat', 'average', 'high_risk'],
                               help='晨星预设: strong_moat(9%), average(10.5%), high_risk(14%)')
    discount_group.add_argument('--discount', type=float, help='直接指定折现率 (如 0.09)')
    discount_group.add_argument('--base-rate', type=float, default=0.105,
                               help='基准折现率 (默认 0.105=晨星标准)')
    
    parser.add_argument('--risk', type=str, 
                       help='风险调整因素，逗号分隔 (small_size,high_leverage,cyclical,poor_management,weak_moat,complexity)')
    
    # 其他选项
    parser.add_argument('--moat', type=str, default='average', 
                       choices=['strong', 'average', 'weak'],
                       help='护城河强度 (影响安全边际要求)')
    parser.add_argument('--scenario', action='store_true', 
                       help='进行情景分析（乐观/中性/悲观）')
    parser.add_argument('--json', action='store_true', help='输出JSON格式结果')
    
    args = parser.parse_args()
    
    # 确定折现率
    risk_factors = None
    if args.preset:
        preset = get_morningstar_preset(args.preset)
        discount_rate = preset["discount_rate"]
    elif args.discount:
        discount_rate = args.discount
    else:
        risk_factors = args.risk.split(',') if args.risk else []
        discount_rate, _ = calculate_discount_rate(args.base_rate, risk_factors)
    
    # 确定增长率
    if args.growth:
        growth_list = [float(g.strip()) for g in args.growth.split(',')]
        if len(growth_list) < 10:
            # 如果不足10年，最后一年重复
            growth_rates = growth_list + [growth_list[-1]] * (10 - len(growth_list))
        else:
            growth_rates = growth_list[:10]
    elif args.base_growth:
        growth_rates = generate_growth_rates(args.base_growth, args.decay)
    else:
        # 默认10年，前5年10%，后5年递减
        growth_rates = generate_growth_rates(0.10, args.decay)
    
    # 计算 DCF
    result = calculate_dcf(
        current_fcf=args.fcf,
        growth_rates=growth_rates,
        terminal_growth=args.terminal,
        discount_rate=discount_rate,
        net_debt=args.net_debt,
        shares_outstanding=args.shares
    )
    
    # 情景分析
    scenario_results = None
    if args.scenario and args.current_price:
        base_growth = sum(growth_rates[:5]) / 5 if not args.base_growth else args.base_growth
        scenario_results = scenario_analysis(
            args.fcf, base_growth, args.terminal, discount_rate,
            args.net_debt, args.shares, args.current_price
        )
    
    # 生成报告
    report = format_dcf_report(
        result, 
        args.current_price, 
        args.moat,
        risk_factors,
        scenario_results
    )
    print(report)
    
    # JSON输出
    if args.json:
        output = {
            "dcf_result": result,
            "evaluation": evaluate_investment_opportunity(
                result['intrinsic_value_per_share'],
                args.current_price or 0,
                args.moat
            ) if args.current_price else None,
            "scenario_analysis": scenario_results,
            "timestamp": datetime.now().isoformat()
        }
        print("\n" + "="*50, file=sys.stderr)
        print("JSON_OUTPUT:", file=sys.stderr)
        print(json.dumps(output, ensure_ascii=False, indent=2), file=sys.stderr)


if __name__ == "__main__":
    main()
