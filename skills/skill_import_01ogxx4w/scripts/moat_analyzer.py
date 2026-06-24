#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
护城河(Moat)强度分析器 - 基于《股市真规则》晨星公司标准

作者: 弗兰克小斯基（Frankski）
Copyright (c) 2026 弗兰克小斯基（Frankski）. All rights reserved.

使用许可:
- 允许个人学习、研究、非商业用途使用
- 允许修改后个人使用
- 禁止直接复制核心算法用于商业产品或竞争性服务
- 禁止移除或修改作者署名后重新分发

免责声明: 本脚本提供的分析结果仅供参考，不构成投资建议。

参考: 《股市真规则》第三章 竞争优势
原作: 帕特·多尔西 (Pat Dorsey)
"""

import argparse
import json
import sys
from typing import Dict, List, Tuple


# 护城河四步检验框架
MOAT_FRAMEWORK = {
    "step1_profitability": {
        "name": "Step 1: 评估历史盈利能力",
        "metrics": {
            "fcf_margin": {
                "name": "自由现金流/销售额",
                "excellent": 0.05,
                "good": 0.03,
                "threshold": 0.05,
                "weight": 0.25
            },
            "net_margin": {
                "name": "净利润率",
                "excellent": 0.15,
                "good": 0.10,
                "threshold": 0.15,
                "weight": 0.25
            },
            "roe": {
                "name": "净资产收益率(ROE)",
                "excellent": 0.15,
                "good": 0.12,
                "threshold": 0.15,
                "weight": 0.25
            },
            "roa": {
                "name": "资产收益率(ROA)",
                "excellent": 0.07,
                "good": 0.06,
                "threshold": 0.06,
                "weight": 0.25
            }
        }
    },
    "step2_moat_source": {
        "name": "Step 2: 识别护城河来源",
        "sources": {
            "real_product_diff": {
                "name": "真实产品差异化",
                "durability": "短暂",
                "examples": ["技术创新", "专利"],
                "moat_width": "narrow"
            },
            "perceived_product_diff": {
                "name": "可感知的产品差异化(品牌)",
                "durability": "中等",
                "examples": ["可口可乐", "蒂凡尼", "泡泡玛特"],
                "moat_width": "wide"
            },
            "cost_advantage": {
                "name": "成本优势",
                "durability": "中等",
                "examples": ["戴尔", "西南航空", "拼多多"],
                "moat_width": "narrow_to_wide"
            },
            "switching_costs": {
                "name": "高转换成本",
                "durability": "持久",
                "examples": ["Oracle数据库", "金蝶ERP", "医疗设备"],
                "moat_width": "wide"
            },
            "network_effects": {
                "name": "网络效应",
                "durability": "持久",
                "examples": ["微信", "eBay", "Adobe PDF"],
                "moat_width": "wide"
            },
            "barriers": {
                "name": "进入壁垒/特许经营权",
                "durability": "持久",
                "examples": ["制药专利", "博彩牌照", "公用事业"],
                "moat_width": "wide"
            }
        }
    },
    "step3_moat_width": {
        "name": "Step 3: 评估护城河宽度",
        "widths": {
            "wide": {
                "name": "面宽护城河",
                "duration": "10-20年以上",
                "examples": ["可口可乐", "迪士尼", "强生"]
            },
            "narrow": {
                "name": "面窄护城河",
                "duration": "5-10年",
                "examples": ["多数技术公司", "零售商"]
            },
            "none": {
                "name": "无护城河",
                "duration": "无",
                "examples": ["大宗商品", "航空公司", "一般制造商"]
            }
        }
    },
    "step4_industry": {
        "name": "Step 4: 行业竞争结构分析",
        "factors": [
            "行业集中度(CR5)",
            "平均毛利率",
            "进入壁垒高低",
            "替代品威胁",
            "上下游议价能力"
        ]
    }
}


def evaluate_profitability(
    fcf_margin: float,
    net_margin: float,
    roe: float,
    roa: float,
    consistency_years: int = 5
) -> Dict:
    """
    评估盈利能力 - Step 1
    """
    metrics = MOAT_FRAMEWORK["step1_profitability"]["metrics"]
    
    results = {}
    total_score = 0
    
    # FCF Margin
    if fcf_margin >= metrics["fcf_margin"]["excellent"]:
        fcf_score = 3
        fcf_comment = "优秀 (>5%)"
    elif fcf_margin >= metrics["fcf_margin"]["good"]:
        fcf_score = 2
        fcf_comment = "良好 (3-5%)"
    elif fcf_margin > 0:
        fcf_score = 1
        fcf_comment = "一般 (<3%)"
    else:
        fcf_score = 0
        fcf_comment = "差 (负现金流)"
    
    results["fcf_margin"] = {
        "name": "自由现金流/销售额",
        "value": fcf_margin,
        "score": fcf_score,
        "comment": fcf_comment,
        "weight": metrics["fcf_margin"]["weight"]
    }
    total_score += fcf_score * metrics["fcf_margin"]["weight"]
    
    # Net Margin
    if net_margin >= metrics["net_margin"]["excellent"]:
        nm_score = 3
        nm_comment = "优秀 (>15%)"
    elif net_margin >= metrics["net_margin"]["good"]:
        nm_score = 2
        nm_comment = "良好 (10-15%)"
    elif net_margin > 0.05:
        nm_score = 1
        nm_comment = "一般 (5-10%)"
    else:
        nm_score = 0
        nm_comment = "差 (<5%)"
    
    results["net_margin"] = {
        "name": "净利润率",
        "value": net_margin,
        "score": nm_score,
        "comment": nm_comment,
        "weight": metrics["net_margin"]["weight"]
    }
    total_score += nm_score * metrics["net_margin"]["weight"]
    
    # ROE
    if roe >= metrics["roe"]["excellent"]:
        roe_score = 3
        roe_comment = "优秀 (>15%)"
    elif roe >= metrics["roe"]["good"]:
        roe_score = 2
        roe_comment = "良好 (12-15%)"
    elif roe >= 0.10:
        roe_score = 1
        roe_comment = "一般 (10-12%)"
    else:
        roe_score = 0
        roe_comment = "差 (<10%)"
    
    results["roe"] = {
        "name": "净资产收益率(ROE)",
        "value": roe,
        "score": roe_score,
        "comment": roe_comment,
        "weight": metrics["roe"]["weight"]
    }
    total_score += roe_score * metrics["roe"]["weight"]
    
    # ROA
    if roa >= metrics["roa"]["excellent"]:
        roa_score = 3
        roa_comment = "优秀 (>7%)"
    elif roa >= metrics["roa"]["good"]:
        roa_score = 2
        roa_comment = "良好 (6-7%)"
    elif roa >= 0.04:
        roa_score = 1
        roa_comment = "一般 (4-6%)"
    else:
        roa_score = 0
        roa_comment = "差 (<4%)"
    
    results["roa"] = {
        "name": "资产收益率(ROA)",
        "value": roa,
        "score": roa_score,
        "comment": roa_comment,
        "weight": metrics["roa"]["weight"]
    }
    total_score += roa_score * metrics["roa"]["weight"]
    
    # 一致性调整
    consistency_bonus = 0
    if consistency_years >= 10:
        consistency_bonus = 0.5
    elif consistency_years >= 5:
        consistency_bonus = 0.25
    
    final_score = min(3, total_score + consistency_bonus)
    
    if final_score >= 2.5:
        overall = "优秀"
    elif final_score >= 1.8:
        overall = "良好"
    elif final_score >= 1.0:
        overall = "一般"
    else:
        overall = "差"
    
    return {
        "metrics": results,
        "total_score": total_score,
        "consistency_bonus": consistency_bonus,
        "final_score": final_score,
        "overall_rating": overall,
        "consistency_years": consistency_years
    }


def evaluate_moat_sources(sources: List[str]) -> Dict:
    """
    评估护城河来源 - Step 2
    """
    source_defs = MOAT_FRAMEWORK["step2_moat_source"]["sources"]
    
    identified = []
    durability_scores = []
    width_scores = {
        "wide": 3,
        "narrow_to_wide": 2.5,
        "narrow": 1.5,
        "none": 0
    }
    
    for source in sources:
        if source in source_defs:
            s = source_defs[source]
            identified.append({
                "name": s["name"],
                "durability": s["durability"],
                "examples": s["examples"],
                "width": s["moat_width"]
            })
            
            # 计算宽度分数
            w_score = width_scores.get(s["moat_width"], 1)
            
            # 根据持久性调整
            if s["durability"] == "持久":
                w_score *= 1.2
            elif s["durability"] == "短暂":
                w_score *= 0.6
            
            durability_scores.append(w_score)
    
    avg_score = sum(durability_scores) / len(durability_scores) if durability_scores else 0
    
    if avg_score >= 2.5:
        width = "wide"
    elif avg_score >= 1.5:
        width = "narrow"
    else:
        width = "none"
    
    return {
        "identified_sources": identified,
        "width_assessment": width,
        "avg_durability_score": avg_score,
        "count": len(identified)
    }


def evaluate_moat_width(duration_estimate: str) -> Dict:
    """
    评估护城河宽度 - Step 3
    """
    widths = MOAT_FRAMEWORK["step3_moat_width"]["widths"]
    
    duration_map = {
        "wide": 20,
        "narrow": 7,
        "none": 0
    }
    
    if duration_estimate in widths:
        w = widths[duration_estimate]
        return {
            "width": duration_estimate,
            "name": w["name"],
            "expected_duration": w["duration"],
            "examples": w["examples"],
            "moat_premium_years": duration_map.get(duration_estimate, 0)
        }
    
    return {"width": "unknown", "name": "未知"}


def calculate_moat_strength(
    profitability_score: float,
    moat_width: str,
    source_count: int
) -> Dict:
    """
    综合评估护城河强度
    """
    width_multiplier = {
        "wide": 1.2,
        "narrow": 0.8,
        "none": 0
    }
    
    source_bonus = min(source_count * 0.1, 0.3)
    
    base_score = profitability_score * width_multiplier.get(moat_width, 0.5)
    final_score = base_score + source_bonus
    
    # 确定护城河等级
    if final_score >= 2.5:
        moat_rating = "强护城河"
        dcf_discount = 0.09  # 9%折现率
        safety_margin = 0.20  # 20%安全边际
    elif final_score >= 1.8:
        moat_rating = "中等护城河"
        dcf_discount = 0.105  # 10.5%折现率
        safety_margin = 0.35  # 35%安全边际
    elif final_score >= 1.0:
        moat_rating = "弱护城河"
        dcf_discount = 0.12  # 12%折现率
        safety_margin = 0.50  # 50%安全边际
    else:
        moat_rating = "无护城河"
        dcf_discount = 0.14  # 14%折现率
        safety_margin = 0.60  # 60%安全边际
    
    return {
        "profitability_score": profitability_score,
        "moat_width": moat_width,
        "source_count": source_count,
        "final_score": final_score,
        "moat_rating": moat_rating,
        "recommended_discount_rate": dcf_discount,
        "recommended_safety_margin": safety_margin
    }


def format_moat_report(
    company_name: str,
    profitability: Dict,
    moat_sources: Dict,
    moat_width: Dict,
    final_assessment: Dict,
    industry_notes: str = ""
) -> str:
    """
    格式化护城河分析报告
    """
    report = f"""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🏰 护城河(Moat)强度分析报告
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
公司名称: {company_name}
分析框架: 《股市真规则》晨星公司四步检验法

"""
    
    # Step 1: 盈利能力
    report += f"""
📊 Step 1: 历史盈利能力评估
────────────────────────────────────────────────────
一致性检验年限: {profitability['consistency_years']}年

各项指标评分:
"""
    for metric, data in profitability["metrics"].items():
        report += f"  • {data['name']}: {data['value']*100:.2f}% - {data['comment']}\n"
    
    report += f"""
综合评分: {profitability['final_score']:.2f}/3.0
评级: {profitability['overall_rating']}
一致性加分: +{profitability['consistency_bonus']:.2f}

结论: {"✓ 通过" if profitability['final_score'] >= 1.5 else "✗ 未通过"} (ROE>10%且FCF为正)
"""
    
    # Step 2: 护城河来源
    report += f"""
📊 Step 2: 护城河来源识别
────────────────────────────────────────────────────
已识别护城河来源 ({moat_sources['count']}个):
"""
    for source in moat_sources["identified_sources"]:
        report += f"  • {source['name']}\n"
        report += f"    持久性: {source['durability']}\n"
        report += f"    宽度: {source['width']}\n"
        report += f"    案例: {', '.join(source['examples'][:3])}\n\n"
    
    # Step 3: 护城河宽度
    report += f"""
📊 Step 3: 护城河宽度评估
────────────────────────────────────────────────────
护城河类型: {moat_width.get('name', '未知')}
预期持续时间: {moat_width.get('expected_duration', '未知')}

类似公司: {', '.join(moat_width.get('examples', [])[:3])}
"""
    
    # 行业分析
    if industry_notes:
        report += f"""
📊 Step 4: 行业竞争结构
────────────────────────────────────────────────────
{industry_notes}
"""
    
    # 最终评估
    report += f"""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
💎 最终评估结果
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

护城河评级: {final_assessment['moat_rating']}
综合得分: {final_assessment['final_score']:.2f}/3.0

📈 DCF估值参数建议:
  推荐折现率: {final_assessment['recommended_discount_rate']*100:.1f}%
  要求安全边际: {final_assessment['recommended_safety_margin']*100:.0f}%

💡 投资建议:
"""
    
    rating = final_assessment['moat_rating']
    if rating == "强护城河":
        report += """  • 公司有持久的竞争优势
  • 可以给予较高估值（较低折现率9%）
  • 20%安全边际即可考虑买入
  • 适合长期持有
"""
    elif rating == "中等护城河":
        report += """  • 公司有一定竞争优势
  • 使用标准折现率10.5%
  • 需要30-40%安全边际
  • 需持续监控竞争格局变化
"""
    elif rating == "弱护城河":
        report += """  • 竞争优势较弱或短暂
  • 使用较高折现率12%
  • 需要50%以上安全边际
  • 短期持有或观望
"""
    else:
        report += """  • 无明显竞争优势
  • 使用高风险折现率14%
  • 需要60%安全边际（深度低估）
  • 仅适合投机或回避
"""
    
    report += """
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📖 参考: 《股市真规则》第三章 竞争优势
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""
    
    return report


def main():
    parser = argparse.ArgumentParser(
        description='护城河强度分析器 - 基于《股市真规则》晨星标准',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # 完整分析（交互式输入）
  python moat_analyzer.py --company 腾讯控股
  
  # 直接指定所有参数
  python moat_analyzer.py --company 泡泡玛特 \\
    --fcf-margin 0.33 --net-margin 0.25 --roe 0.20 --roa 0.15 \\
    --sources brand,network_effects \\
    --width wide --years 5
        """
    )
    
    parser.add_argument('--company', type=str, required=True, help='公司名称')
    parser.add_argument('--fcf-margin', type=float, help='自由现金流/销售额 (如 0.05)')
    parser.add_argument('--net-margin', type=float, help='净利润率 (如 0.15)')
    parser.add_argument('--roe', type=float, help='净资产收益率ROE (如 0.15)')
    parser.add_argument('--roa', type=float, help='资产收益率ROA (如 0.07)')
    parser.add_argument('--years', type=int, default=5, help='一致性检验年限 (默认5年)')
    parser.add_argument('--sources', type=str, 
                       help='护城河来源，逗号分隔 (real_product_diff,perceived_product_diff,cost_advantage,switching_costs,network_effects,barriers)')
    parser.add_argument('--width', type=str, choices=['wide', 'narrow', 'none'],
                       help='护城河宽度估计')
    parser.add_argument('--industry', type=str, help='行业分析备注')
    parser.add_argument('--json', action='store_true', help='输出JSON格式')
    
    args = parser.parse_args()
    
    # 如果提供了完整参数，直接计算
    if all([args.fcf_margin, args.net_margin, args.roe, args.roa]):
        profitability = evaluate_profitability(
            args.fcf_margin, args.net_margin, args.roe, args.roa, args.years
        )
    else:
        # 交互式输入
        print(f"\n🏰 护城河分析: {args.company}")
        print("请提供财务指标（小数形式，如0.15表示15%）:\n")
        
        fcf_margin = float(input("自由现金流/销售额 (优秀>5%): ") or "0")
        net_margin = float(input("净利润率 (优秀>15%): ") or "0")
        roe = float(input("ROE (优秀>15%): ") or "0")
        roa = float(input("ROA (优秀>6-7%): ") or "0")
        years = int(input("一致性检验年限 (默认5): ") or "5")
        
        profitability = evaluate_profitability(
            fcf_margin, net_margin, roe, roa, years
        )
        
        print("\n护城河来源选项:")
        print("1. real_product_diff - 真实产品差异化")
        print("2. perceived_product_diff - 品牌差异化")
        print("3. cost_advantage - 成本优势")
        print("4. switching_costs - 高转换成本")
        print("5. network_effects - 网络效应")
        print("6. barriers - 进入壁垒/特许经营权")
        
        sources_input = input("请输入护城河来源编号（逗号分隔，如1,4,5）: ") or ""
        source_map = {
            "1": "real_product_diff",
            "2": "perceived_product_diff",
            "3": "cost_advantage",
            "4": "switching_costs",
            "5": "network_effects",
            "6": "barriers"
        }
        sources = [source_map.get(s.strip()) for s in sources_input.split(",") if s.strip() in source_map]
        args.sources = ",".join(sources)
        
        width_input = input("\n护城河宽度 (wide/narrow/none): ") or "none"
        args.width = width_input
        
        args.industry = input("行业竞争分析备注（可选）: ") or ""
    
    # 分析护城河来源
    if args.sources:
        sources_list = [s.strip() for s in args.sources.split(",")]
        moat_sources = evaluate_moat_sources(sources_list)
    else:
        moat_sources = {"identified_sources": [], "width_assessment": "none", "count": 0}
    
    # 分析护城河宽度
    if args.width:
        moat_width = evaluate_moat_width(args.width)
    else:
        moat_width = evaluate_moat_width(moat_sources.get("width_assessment", "none"))
    
    # 综合评估
    final_assessment = calculate_moat_strength(
        profitability["final_score"],
        moat_width.get("width", "none"),
        moat_sources["count"]
    )
    
    # 生成报告
    report = format_moat_report(
        args.company,
        profitability,
        moat_sources,
        moat_width,
        final_assessment,
        args.industry
    )
    print(report)
    
    # JSON输出
    if args.json:
        output = {
            "company": args.company,
            "profitability": profitability,
            "moat_sources": moat_sources,
            "moat_width": moat_width,
            "final_assessment": final_assessment
        }
        print("\nJSON_OUTPUT:")
        print(json.dumps(output, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
