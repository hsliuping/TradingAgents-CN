#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
财务危险信号检查器 - 基于《股市真规则》第八章

作者: 弗兰克小斯基（Frankski）
Copyright (c) 2026 弗兰克小斯基（Frankski）. All rights reserved.

使用许可:
- 允许个人学习、研究、非商业用途使用
- 允许修改后个人使用
- 禁止直接复制核心算法用于商业产品或竞争性服务
- 禁止移除或修改作者署名后重新分发

免责声明: 本脚本提供的分析结果仅供参考，不构成投资建议。

参考: 《股市真规则》第八章 揭开财务伪装
原作: 帕特·多尔西 (Pat Dorsey)
"""

import argparse
import json
import sys
from typing import Dict, List, Tuple


# 六个主要危险信号
RED_FLAGS = {
    "cash_flow_decline": {
        "id": 1,
        "name": "现金流衰退",
        "description": "净利润增长但经营现金流下降或停滞",
        "severity": "高危",
        "check": "净利润与经营现金流趋势背离",
        "details": [
            "经营性现金流减少而净利润增长",
            "现金流增长慢于净利润增长",
            "应收账款激增而现金回收缓慢"
        ]
    },
    "recurring_nonrecurring": {
        "id": 2,
        "name": "连续非经常性费用",
        "description": "频繁的'一次性'重组费用",
        "severity": "高危",
        "check": "3年内≥2次非经常性费用",
        "details": [
            "频繁计提重组费用",
            "将正常经营费用隐藏在非经常性项目中",
            "利用重组费用调节利润"
        ]
    },
    "serial_acquisitions": {
        "id": 3,
        "name": "连续收购",
        "description": "频繁的收购活动，财务资料被多次改写",
        "severity": "中危",
        "check": "每年大额收购活动",
        "details": [
            "财务报告难以追踪真实业绩",
            "商誉可能高估",
            "整合风险"
        ]
    },
    "cfo_auditor_departure": {
        "id": 4,
        "name": "CFO或审计师离职",
        "description": "首席财务官或审计师无解释离职",
        "severity": "高危",
        "check": "近期管理层或审计师变更",
        "details": [
            "CFO突然离职且无合理解释",
            "频繁更换审计师",
            "审计师出具保留意见"
        ]
    },
    "receivables_growth": {
        "id": 5,
        "name": "应收账款异常增长",
        "description": "应收账款增速超过收入增速",
        "severity": "高危",
        "check": "应收增速 > 收入增速",
        "details": [
            "放宽信用条件刺激销售",
            "'填充渠道'式销售",
            "坏账准备不足"
        ]
    },
    "credit_policy_change": {
        "id": 6,
        "name": "赊销条件变更",
        "description": "放宽对客户信用条件",
        "severity": "中危",
        "check": "10-K报告中信用政策变化",
        "details": [
            "延长付款期限",
            "降低信用标准",
            "提前确认收入"
        ]
    }
}

# 七个其他需要关注的缺陷
OTHER_DEFICIENCIES = {
    "investment_income": {
        "name": "投资收益支撑利润",
        "check": "投资收益占营业利润比例高",
        "signal": "核心业务盈利能力弱"
    },
    "pension_deficit": {
        "name": "养老金赤字",
        "check": "养老金义务 > 计划资产",
        "signal": "潜在巨额现金流出"
    },
    "pension_boost": {
        "name": "养老金利润虚增",
        "check": "超额养老金收益计入利润",
        "signal": "不可持续的利润来源"
    },
    "phantom_cashflow": {
        "name": "期权税收收益现金流",
        "check": "大量现金流来自期权税收收益",
        "signal": "股价下跌时现金流将消失"
    },
    "bloated_inventory": {
        "name": "存货积压",
        "check": "存货增速 > 销售增速",
        "signal": "可能被迫降价或核销"
    },
    "accounting_changes": {
        "name": "会计政策变更",
        "check": "折旧年限、坏账准备等突然变更",
        "signal": "可能粉饰业绩"
    },
    "expense_capitalization": {
        "name": "费用资本化",
        "check": "将本应费用化的支出资本化",
        "signal": "夸大资产和利润"
    }
}


def check_cash_flow_divergence(
    net_income_growth: float,
    operating_cf_growth: float
) -> Dict:
    """
    检查现金流与净利润背离
    """
    if net_income_growth > 0.1 and operating_cf_growth < 0:
        return {
            "flagged": True,
            "severity": "高危",
            "details": f"净利润增长{net_income_growth*100:.1f}%，但经营现金流增长{operating_cf_growth*100:.1f}%",
            "explanation": "利润可能没有转化为现金，应收账款或存货积压"
        }
    elif net_income_growth - operating_cf_growth > 0.15:
        return {
            "flagged": True,
            "severity": "中危",
            "details": f"净利润增长({net_income_growth*100:.1f}%)远超经营现金流增长({operating_cf_growth*100:.1f}%)",
            "explanation": "盈利质量可能较低"
        }
    return {"flagged": False}


def check_receivables_vs_revenue(
    receivables_growth: float,
    revenue_growth: float,
    bad_debt_provision_growth: float = None
) -> Dict:
    """
    检查应收账款与收入关系
    """
    if receivables_growth > revenue_growth * 1.2:  # 应收增长超过收入增长20%以上
        if bad_debt_provision_growth and bad_debt_provision_growth < receivables_growth:
            provision_warning = "，且坏账准备未同步增长"
        else:
            provision_warning = ""
        
        return {
            "flagged": True,
            "severity": "高危",
            "details": f"应收账款增长{receivables_growth*100:.1f}% > 收入增长{revenue_growth*100:.1f}%{provision_warning}",
            "explanation": "可能放宽信用条件刺激销售，或回收货款困难"
        }
    return {"flagged": False}


def check_inventory_buildup(
    inventory_growth: float,
    revenue_growth: float
) -> Dict:
    """
    检查存货积压
    """
    if inventory_growth > revenue_growth * 1.3:  # 存货增长超过收入增长30%以上
        return {
            "flagged": True,
            "severity": "中危",
            "details": f"存货增长{inventory_growth*100:.1f}% > 收入增长{revenue_growth*100:.1f}%",
            "explanation": "可能需求萎缩或过度生产，未来可能被迫降价或核销"
        }
    return {"flagged": False}


def check_nonrecurring_frequency(
    nonrecurring_count_3y: int,
    total_adjustments: float,
    net_income: float
) -> Dict:
    """
    检查非经常性费用频率
    """
    if nonrecurring_count_3y >= 2:
        ratio = total_adjustments / abs(net_income) if net_income != 0 else 0
        return {
            "flagged": True,
            "severity": "高危",
            "details": f"3年内{nonrecurring_count_3y}次非经常性调整，累计{total_adjustments:.1f}亿元",
            "explanation": "可能将正常经营费用隐藏在非经常性项目中"
        }
    return {"flagged": False}


def check_acquisition_frequency(
    acquisition_count_3y: int,
    total_acquisition_cost: float,
    market_cap: float
) -> Dict:
    """
    检查收购频率
    """
    if acquisition_count_3y >= 2 or total_acquisition_cost > market_cap * 0.3:
        return {
            "flagged": True,
            "severity": "中危",
            "details": f"3年内{acquisition_count_3y}次收购，累计成本{total_acquisition_cost:.1f}亿元",
            "explanation": "财务资料被多次改写，难以评估真实业绩，整合风险高"
        }
    return {"flagged": False}


def analyze_financial_red_flags(
    # 基本财务数据
    revenue_current: float,
    revenue_prior: float,
    net_income_current: float,
    net_income_prior: float,
    operating_cf_current: float,
    operating_cf_prior: float,
    # 资产负债表数据
    receivables_current: float,
    receivables_prior: float,
    inventory_current: float,
    inventory_prior: float,
    # 其他数据
    nonrecurring_count_3y: int = 0,
    total_nonrecurring_amount: float = 0,
    acquisition_count_3y: int = 0,
    total_acquisition_cost: float = 0,
    market_cap: float = 1,
    cfo_departure: bool = False,
    auditor_change: bool = False,
    # 检查选项
    check_pension: bool = False,
    check_options_tax: bool = False,
    check_capitalization: bool = False
) -> Dict:
    """
    全面分析财务危险信号
    """
    flags_triggered = []
    warnings = []
    
    # 计算增长率
    revenue_growth = (revenue_current - revenue_prior) / revenue_prior if revenue_prior > 0 else 0
    net_income_growth = (net_income_current - net_income_prior) / abs(net_income_prior) if net_income_prior != 0 else 0
    operating_cf_growth = (operating_cf_current - operating_cf_prior) / abs(operating_cf_prior) if operating_cf_prior != 0 else 0
    receivables_growth = (receivables_current - receivables_prior) / receivables_prior if receivables_prior > 0 else 0
    inventory_growth = (inventory_current - inventory_prior) / inventory_prior if inventory_prior > 0 else 0
    
    # 检查1: 现金流衰退
    cf_check = check_cash_flow_divergence(net_income_growth, operating_cf_growth)
    if cf_check["flagged"]:
        flags_triggered.append({
            "signal": "现金流衰退",
            **cf_check
        })
    
    # 检查2: 应收账款异常
    ar_check = check_receivables_vs_revenue(receivables_growth, revenue_growth)
    if ar_check["flagged"]:
        flags_triggered.append({
            "signal": "应收账款异常增长",
            **ar_check
        })
    
    # 检查3: 存货积压
    inv_check = check_inventory_buildup(inventory_growth, revenue_growth)
    if inv_check["flagged"]:
        flags_triggered.append({
            "signal": "存货积压",
            **inv_check
        })
    
    # 检查4: 非经常性费用
    nr_check = check_nonrecurring_frequency(nonrecurring_count_3y, total_nonrecurring_amount, net_income_current)
    if nr_check["flagged"]:
        flags_triggered.append({
            "signal": "连续非经常性费用",
            **nr_check
        })
    
    # 检查5: 连续收购
    acq_check = check_acquisition_frequency(acquisition_count_3y, total_acquisition_cost, market_cap)
    if acq_check["flagged"]:
        flags_triggered.append({
            "signal": "连续收购",
            **acq_check
        })
    
    # 检查6: CFO/审计师离职
    if cfo_departure:
        flags_triggered.append({
            "signal": "CFO离职",
            "severity": "高危",
            "details": "首席财务官近期离职",
            "explanation": "可能财务问题信号"
        })
    
    if auditor_change:
        flags_triggered.append({
            "signal": "审计师变更",
            "severity": "高危",
            "details": "近期更换审计师",
            "explanation": "可能存在审计分歧"
        })
    
    # 其他检查
    if check_options_tax:
        warnings.append({
            "signal": "期权税收收益",
            "severity": "注意",
            "explanation": "大量现金流来自期权税收收益，股价下跌时将消失"
        })
    
    if check_pension:
        warnings.append({
            "signal": "养老金问题",
            "severity": "注意",
            "explanation": "检查养老金计划资金状况"
        })
    
    if check_capitalization:
        warnings.append({
            "signal": "费用资本化",
            "severity": "注意",
            "explanation": "检查是否将费用资本化以夸大利润"
        })
    
    # 综合评级
    high_risk_count = sum(1 for f in flags_triggered if f["severity"] == "高危")
    medium_risk_count = sum(1 for f in flags_triggered if f["severity"] == "中危")
    
    if high_risk_count >= 2:
        overall_rating = "高风险"
        recommendation = "强烈建议回避"
    elif high_risk_count == 1 or medium_risk_count >= 2:
        overall_rating = "中风险"
        recommendation = "需要深入调查"
    elif len(flags_triggered) > 0:
        overall_rating = "低风险"
        recommendation = "保持警惕"
    else:
        overall_rating = "健康"
        recommendation = "无明显危险信号"
    
    return {
        "flags_triggered": flags_triggered,
        "warnings": warnings,
        "flag_count": len(flags_triggered),
        "high_risk_count": high_risk_count,
        "medium_risk_count": medium_risk_count,
        "overall_rating": overall_rating,
        "recommendation": recommendation,
        "growth_rates": {
            "revenue": revenue_growth,
            "net_income": net_income_growth,
            "operating_cf": operating_cf_growth,
            "receivables": receivables_growth,
            "inventory": inventory_growth
        }
    }


def format_red_flag_report(company_name: str, analysis: Dict) -> str:
    """
    格式化危险信号报告
    """
    report = f"""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🚨 财务危险信号检查报告
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
公司名称: {company_name}
检查框架: 《股市真规则》第八章 六个危险信号

📊 综合评估
────────────────────────────────────────────────────
危险信号数量: {analysis['flag_count']}
  - 高危: {analysis['high_risk_count']}
  - 中危: {analysis['medium_risk_count']}

整体评级: {analysis['overall_rating']}
建议: {analysis['recommendation']}
"""
    
    if analysis['flags_triggered']:
        report += f"""
🚨 触发的危险信号
────────────────────────────────────────────────────
"""
        for i, flag in enumerate(analysis['flags_triggered'], 1):
            emoji = "🔴" if flag['severity'] == "高危" else "🟡"
            report += f"""
{i}. {emoji} {flag['signal']} [{flag['severity']}]
   详情: {flag['details']}
   解释: {flag['explanation']}
"""
    
    if analysis['warnings']:
        report += f"""
⚠️  其他需关注事项
────────────────────────────────────────────────────
"""
        for warning in analysis['warnings']:
            report += f"""
• {warning['signal']} [{warning['severity']}]
  {warning['explanation']}
"""
    
    # 增长数据
    report += f"""
📈 关键增长率对比
────────────────────────────────────────────────────
  收入增长:      {analysis['growth_rates']['revenue']*100:+.1f}%
  净利润增长:    {analysis['growth_rates']['net_income']*100:+.1f}%
  经营现金流增长: {analysis['growth_rates']['operating_cf']*100:+.1f}%
  应收账款增长:  {analysis['growth_rates']['receivables']*100:+.1f}%
  存货增长:      {analysis['growth_rates']['inventory']*100:+.1f}%

⚠️  注意: 如果应收/存货增长远超收入增长，需警惕
"""
    
    if analysis['overall_rating'] == "高风险":
        report += """
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🔴 投资建议: 强烈建议回避
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
该公司存在多个高危财务危险信号，可能存在：
• 会计操纵或财务造假
• 经营质量恶化
• 现金流压力

建议：
1. 深入阅读10-K报告脚注
2. 检查审计师意见
3. 对比同行业公司
4. 如无充分解释，应回避投资
"""
    elif analysis['overall_rating'] == "中风险":
        report += """
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🟡 投资建议: 需要深入调查
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
该公司存在部分财务危险信号，需要：
• 仔细阅读年报管理层讨论
• 分析应收账款账龄
• 了解非经常性费用具体构成
• 评估收购整合风险

建议：在获得合理解释前，暂缓投资
"""
    else:
        report += """
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🟢 投资建议: 保持正常关注
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
未发现重大财务危险信号，但仍需：
• 定期监控财务指标
• 关注季度报告变化
• 对比行业趋势
"""
    
    report += """
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📖 参考: 《股市真规则》第八章 揭开财务伪装
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""
    
    return report


def main():
    parser = argparse.ArgumentParser(
        description='财务危险信号检查器 - 基于《股市真规则》',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # 交互式输入
  python red_flag_checker.py --company 某公司
  
  # 直接输入数据
  python red_flag_checker.py --company 某公司 \\
    --revenue-current 100 --revenue-prior 80 \\
    --net-income-current 10 --net-income-prior 5 \\
    --operating-cf-current 5 --operating-cf-prior 8 \\
    --receivables-current 30 --receivables-prior 20 \\
    --inventory-current 25 --inventory-prior 20
        """
    )
    
    parser.add_argument('--company', type=str, required=True, help='公司名称')
    
    # 收入数据
    parser.add_argument('--revenue-current', type=float, help='当期收入（亿元）')
    parser.add_argument('--revenue-prior', type=float, help='上期收入（亿元）')
    
    # 利润数据
    parser.add_argument('--net-income-current', type=float, help='当期净利润（亿元）')
    parser.add_argument('--net-income-prior', type=float, help='上期净利润（亿元）')
    
    # 现金流数据
    parser.add_argument('--operating-cf-current', type=float, help='当期经营现金流（亿元）')
    parser.add_argument('--operating-cf-prior', type=float, help='上期经营现金流（亿元）')
    
    # 应收/存货数据
    parser.add_argument('--receivables-current', type=float, help='当期应收账款（亿元）')
    parser.add_argument('--receivables-prior', type=float, help='上期应收账款（亿元）')
    parser.add_argument('--inventory-current', type=float, help='当期存货（亿元）')
    parser.add_argument('--inventory-prior', type=float, help='上期存货（亿元）')
    
    # 其他信号
    parser.add_argument('--nonrecurring-count', type=int, default=0, help='3年非经常性费用次数')
    parser.add_argument('--nonrecurring-amount', type=float, default=0, help='累计非经常性金额（亿元）')
    parser.add_argument('--acquisition-count', type=int, default=0, help='3年收购次数')
    parser.add_argument('--acquisition-cost', type=float, default=0, help='累计收购成本（亿元）')
    parser.add_argument('--market-cap', type=float, default=100, help='市值（亿元）')
    parser.add_argument('--cfo-departure', action='store_true', help='CFO近期离职')
    parser.add_argument('--auditor-change', action='store_true', help='审计师变更')
    
    parser.add_argument('--json', action='store_true', help='输出JSON格式')
    
    args = parser.parse_args()
    
    # 检查是否提供了完整数据
    required = [args.revenue_current, args.revenue_prior, args.net_income_current,
                args.net_income_prior, args.operating_cf_current, args.operating_cf_prior,
                args.receivables_current, args.receivables_prior]
    
    if None in required:
        print(f"\n🚨 财务危险信号检查: {args.company}")
        print("请提供以下财务数据（亿元）:\n")
        
        revenue_current = float(input("当期收入: ") or "0")
        revenue_prior = float(input("上期收入: ") or "0")
        net_income_current = float(input("当期净利润: ") or "0")
        net_income_prior = float(input("上期净利润: ") or "0")
        operating_cf_current = float(input("当期经营现金流: ") or "0")
        operating_cf_prior = float(input("上期经营现金流: ") or "0")
        receivables_current = float(input("当期应收账款: ") or "0")
        receivables_prior = float(input("上期应收账款: ") or "0")
        inventory_current = float(input("当期存货: ") or "0")
        inventory_prior = float(input("上期存货: ") or "0")
        
        args.revenue_current = revenue_current
        args.revenue_prior = revenue_prior
        args.net_income_current = net_income_current
        args.net_income_prior = net_income_prior
        args.operating_cf_current = operating_cf_current
        args.operating_cf_prior = operating_cf_prior
        args.receivables_current = receivables_current
        args.receivables_prior = receivables_prior
        args.inventory_current = inventory_current
        args.inventory_prior = inventory_prior
    
    # 执行分析
    analysis = analyze_financial_red_flags(
        revenue_current=args.revenue_current,
        revenue_prior=args.revenue_prior,
        net_income_current=args.net_income_current,
        net_income_prior=args.net_income_prior,
        operating_cf_current=args.operating_cf_current,
        operating_cf_prior=args.operating_cf_prior,
        receivables_current=args.receivables_current,
        receivables_prior=args.receivables_prior,
        inventory_current=args.inventory_current,
        inventory_prior=args.inventory_prior,
        nonrecurring_count_3y=args.nonrecurring_count,
        total_nonrecurring_amount=args.nonrecurring_amount,
        acquisition_count_3y=args.acquisition_count,
        total_acquisition_cost=args.acquisition_cost,
        market_cap=args.market_cap,
        cfo_departure=args.cfo_departure,
        auditor_change=args.auditor_change
    )
    
    # 生成报告
    report = format_red_flag_report(args.company, analysis)
    print(report)
    
    # JSON输出
    if args.json:
        print("\nJSON_OUTPUT:")
        print(json.dumps(analysis, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
