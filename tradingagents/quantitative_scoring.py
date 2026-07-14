"""
量化评分模块 - 在LLM辩论之前提供一致的数值基准
确保不同股票之间可以横向比较，减少LLM随机性
"""
import math
from typing import Dict, Any, Optional


class FactorWeightConfig:
    """因子权重配置 - 可根据策略偏好调整"""

    # ==============================
    # 估值因子 (权重: 30%)
    # ==============================
    PE_SCORE_WEIGHT = 0.30       # PE估值得分权重
    PB_SCORE_WEIGHT = 0.30       # PB估值得分权重
    DIVIDEND_SCORE_WEIGHT = 0.20  # 股息率得分权重
    PEG_SCORE_WEIGHT = 0.20      # PEG得分权重

    # ==============================
    # 质量因子 (权重: 30%)
    # ==============================
    ROE_SCORE_WEIGHT = 0.35      # ROE得分权重
    GROSS_MARGIN_SCORE_WEIGHT = 0.25  # 毛利率得分权重
    DEBT_SCORE_WEIGHT = 0.25     # 负债率得分权重
    CURRENT_RATIO_SCORE_WEIGHT = 0.15  # 流动比率得分权重

    # ==============================
    # 趋势/技术因子 (权重: 20%)
    # ==============================
    RSI_SCORE_WEIGHT = 0.30      # RSI超卖得分权重
    TREND_SCORE_WEIGHT = 0.40    # 趋势得分权重
    VOLUME_SCORE_WEIGHT = 0.30   # 成交量得分权重

    # ==============================
    # 行业/宏观因子 (权重: 20%)
    # ==============================
    INDUSTRY_CYCLE_SCORE_WEIGHT = 0.40   # 行业周期位置
    DEBT_CYCLE_RISK_SCORE_WEIGHT = 0.30  # 高负债在周期下行的风险
    BRAND_MOAT_SCORE_WEIGHT = 0.30       # 品牌护城河

    # ==============================
    # 行业分类 - 周期性行业列表
    # ==============================
    CYCLICAL_INDUSTRIES = {"有色金属", "钢铁", "矿业", "煤炭", "化工",
                           "航运", "航空", "证券", "房地产", "建材", "石油"}
    DEFENSIVE_INDUSTRIES = {"白酒", "医药", "消费", "银行", "保险", "公用事业"}

    # ==============================
    # 权重合计配置
    # ==============================
    VALUATION_TOTAL_WEIGHT = 0.30    # 估值总分占总分权重
    QUALITY_TOTAL_WEIGHT = 0.30      # 质量总分占总分权重
    TECHNICAL_TOTAL_WEIGHT = 0.20    # 技术总分占总分权重
    MACRO_TOTAL_WEIGHT = 0.20        # 宏观总分占总分权重


def detect_industry_category(company_name: str, sector: str = "") -> str:
    """检测行业类别：防守型、周期型、成长型"""
    text = f"{company_name} {sector}"
    for ind in FactorWeightConfig.CYCLICAL_INDUSTRIES:
        if ind in text:
            return "cyclical"
    for ind in FactorWeightConfig.DEFENSIVE_INDUSTRIES:
        if ind in text:
            return "defensive"
    return "growth"


def score_pe(pe: Optional[float], industry_category: str) -> tuple:
    """
    对PE进行评分 (0-100)
    返回 (分数, 说明)
    """
    if pe is None or pe <= 0:
        return 50, "PE数据缺失，取默认分"

    if industry_category == "defensive":
        # 防守型：PE越低越好，极度低估加分
        if pe < 5:   return 95, f"PE={pe:.1f}，极端低估"
        if pe < 8:   return 85, f"PE={pe:.1f}，严重低估"
        if pe < 12:  return 75, f"PE={pe:.1f}，明显低估"
        if pe < 20:  return 60, f"PE={pe:.1f}，合理偏低"
        if pe < 30:  return 45, f"PE={pe:.1f}，合理偏高"
        if pe < 50:  return 30, f"PE={pe:.1f}，偏高"
        return 15, f"PE={pe:.1f}，严重高估"

    elif industry_category == "cyclical":
        # 周期型：低PE可能是陷阱(盈利高峰)，高PE可能是机会(盈利低谷)
        if pe < 5:   return 20, f"PE={pe:.1f}，周期股低PE通常是顶部信号"
        if pe < 10:  return 30, f"PE={pe:.1f}，周期股PE偏低，需警惕盈利见顶"
        if pe < 15:  return 50, f"PE={pe:.1f}，周期股中性估值区"
        if pe < 25:  return 60, f"PE={pe:.1f}，周期股偏高，可能盈利触底"
        if pe < 50:  return 75, f"PE={pe:.1f}，周期股高PE，可能是底部信号"
        return 80, f"PE={pe:.1f}，极端高PE，盈利可能已触底"

    else:
        # 成长型：适度PE可接受
        if pe < 10:  return 90, f"PE={pe:.1f}，很低估"
        if pe < 20:  return 70, f"PE={pe:.1f}，合理偏低"
        if pe < 35:  return 50, f"PE={pe:.1f}，合理"
        if pe < 50:  return 35, f"PE={pe:.1f}，偏高"
        if pe < 80:  return 20, f"PE={pe:.1f}，高估"
        return 10, f"PE={pe:.1f}，严重高估"


def score_pb(pb: Optional[float], industry_category: str) -> tuple:
    """对PB进行评分 (0-100)"""
    if pb is None or pb <= 0:
        return 50, "PB数据缺失"
    if pb < 0.3:   return 95, f"PB={pb:.2f}，极端破净"
    if pb < 0.5:   return 85, f"PB={pb:.2f}，严重破净"
    if pb < 0.8:   return 75, f"PB={pb:.2f}，明显破净"
    if pb < 1.2:   return 65, f"PB={pb:.2f}，略低于净资产"
    if pb < 2:     return 50, f"PB={pb:.2f}，合理偏低估"
    if pb < 3:     return 40, f"PB={pb:.2f}，合理偏高"
    if pb < 5:     return 25, f"PB={pb:.2f}，偏高"
    return 10, f"PB={pb:.2f}，严重偏高"


def score_roe(roe: Optional[float], industry_category: str) -> tuple:
    """对ROE进行评分 (0-100)"""
    if roe is None:
        return 50, "ROE数据缺失"
    if roe < 0:   return 20, f"ROE={roe:.1f}%，亏损"
    if roe < 3:   return 30, f"ROE={roe:.1f}%，很差"
    if roe < 6:   return 45, f"ROE={roe:.1f}%，偏低"
    if roe < 10:  return 60, f"ROE={roe:.1f}%，一般"
    if roe < 15:  return 75, f"ROE={roe:.1f}%，良好"
    if roe < 20:  return 85, f"ROE={roe:.1f}%，优秀"
    return 95, f"ROE={roe:.1f}%，极优秀"


def score_gross_margin(margin: Optional[float], industry_category: str) -> tuple:
    """对毛利率进行评分"""
    if margin is None:
        return 50, "毛利率数据缺失"
    if margin < 10:  return 20, f"毛利率={margin:.1f}%，很低"
    if margin < 20:  return 35, f"毛利率={margin:.1f}%，偏低"
    if margin < 30:  return 50, f"毛利率={margin:.1f}%，一般"
    if margin < 50:  return 70, f"毛利率={margin:.1f}%，较高"
    if margin < 70:  return 85, f"毛利率={margin:.1f}%，很高(品牌溢价)"
    return 95, f"毛利率={margin:.1f}%，极高(强护城河)"


def score_debt_ratio(debt: Optional[float], industry_category: str) -> tuple:
    """对负债率进行评分"""
    if debt is None:
        return 50, "负债率数据缺失"
    if industry_category == "cyclical":
        # 周期股对负债更敏感
        if debt < 20:  return 80, f"负债率={debt:.1f}%，极低(周期下行安全)"
        if debt < 40:  return 60, f"负债率={debt:.1f}%，较低(周期安全)"
        if debt < 50:  return 45, f"负债率={debt:.1f}%，适中(周期需谨慎)"
        if debt < 65:  return 30, f"负债率={debt:.1f}%，偏高(周期风险较大)"
        return 15, f"负债率={debt:.1f}%，高负债(周期致命风险)"
    else:
        # 非周期
        if debt < 20:  return 85, f"负债率={debt:.1f}%，极低"
        if debt < 35:  return 75, f"负债率={debt:.1f}%，低"
        if debt < 50:  return 60, f"负债率={debt:.1f}%，适中"
        if debt < 65:  return 40, f"负债率={debt:.1f}%，偏高"
        return 25, f"负债率={debt:.1f}%，过高"


def score_rsi(rsi: Optional[float]) -> tuple:
    """对RSI进行评分 - 超卖/超买信号"""
    if rsi is None:
        return 50, "RSI数据缺失"
    if rsi < 10:   return 90, f"RSI={rsi:.1f}，极端超卖(历史大底信号)"
    if rsi < 20:   return 80, f"RSI={rsi:.1f}，严重超卖(极度恐慌)"
    if rsi < 30:   return 70, f"RSI={rsi:.1f}，超卖区域(短期反弹概率大)"
    if rsi < 40:   return 55, f"RSI={rsi:.1f}，偏弱但未超卖"
    if rsi < 60:   return 45, f"RSI={rsi:.1f}，中性区域"
    if rsi < 70:   return 35, f"RSI={rsi:.1f}，偏强"
    if rsi < 80:   return 20, f"RSI={rsi:.1f}，超买"
    return 10, f"RSI={rsi:.1f}，严重超买"


def score_trend(macd_dif: Optional[float], macd_hist: Optional[float]) -> tuple:
    """对技术趋势评分"""
    if macd_dif is None or macd_hist is None:
        return 50, "MACD数据缺失"

    # 综合DIF和柱状体判断趋势强度
    dif_bullish = macd_dif > 0
    hist_bullish = macd_hist > 0
    hist_turning = abs(macd_hist) < 0.1 and macd_hist > -0.1

    if dif_bullish and hist_bullish:   return 80, "双多(趋势向上+动能增强)"
    if dif_bullish and not hist_bullish: return 65, "趋势向上但动能减弱"
    if not dif_bullish and hist_bullish: return 40, "趋势向下但短期反弹"
    if not dif_bullish and not hist_bullish:
        if abs(macd_hist) > 0.3:
            return 15, "双空且动能强劲(空头趋势延续)"
        return 30, "双空但动能减弱(可能底部区域)"
    return 45, "MACD中性"


def compute_quantitative_score(
    fundamentals: Dict[str, Any],
    technical: Dict[str, Any],
    company_name: str = "",
    sector: str = ""
) -> Dict[str, Any]:
    """
    计算综合量化评分

    Args:
        fundamentals: 基本面数据，包含 pe, pb, roe, gross_margin, debt_ratio, current_ratio
        technical: 技术数据，包含 rsi6, macd_dif, macd_hist
        company_name: 公司名称
        sector: 行业

    Returns:
        {
            "total_score": 总分(0-100),
            "valuation_score": 估值分,
            "quality_score": 质量分,
            "technical_score": 技术分,
            "macro_score": 宏观分,
            "suggested_action": 基于分数的建议,
            "detail": { ... 各因子得分详情 ... }
        }
    """
    industry_cat = detect_industry_category(company_name, sector)

    detail = {}

    # ---- 估值因子 ----
    pe_score, pe_note = score_pe(fundamentals.get("pe"), industry_cat)
    pb_score, pb_note = score_pb(fundamentals.get("pb"), industry_cat)
    detail.update({
        "pe": {"score": pe_score, "note": pe_note, "weight": FactorWeightConfig.PE_SCORE_WEIGHT},
        "pb": {"score": pb_score, "note": pb_note, "weight": FactorWeightConfig.PB_SCORE_WEIGHT},
    })

    valuation_subtotal = (
        pe_score * FactorWeightConfig.PE_SCORE_WEIGHT +
        pb_score * FactorWeightConfig.PB_SCORE_WEIGHT
    )
    # 对周期股，在估值因子上打8折(周期股估值不可信)
    if industry_cat == "cyclical":
        valuation_subtotal *= 0.8
        detail["valuation_note"] = "周期股估值打8折"

    # ---- 质量因子 ----
    roe_score, roe_note = score_roe(fundamentals.get("roe"), industry_cat)
    gm_score, gm_note = score_gross_margin(fundamentals.get("gross_margin"), industry_cat)
    debt_score, debt_note = score_debt_ratio(fundamentals.get("debt_ratio"), industry_cat)

    detail.update({
        "roe": {"score": roe_score, "note": roe_note, "weight": FactorWeightConfig.ROE_SCORE_WEIGHT},
        "gross_margin": {"score": gm_score, "note": gm_note, "weight": FactorWeightConfig.GROSS_MARGIN_SCORE_WEIGHT},
        "debt_ratio": {"score": debt_score, "note": debt_note, "weight": FactorWeightConfig.DEBT_SCORE_WEIGHT},
    })

    quality_subtotal = (
        roe_score * FactorWeightConfig.ROE_SCORE_WEIGHT +
        gm_score * FactorWeightConfig.GROSS_MARGIN_SCORE_WEIGHT +
        debt_score * FactorWeightConfig.DEBT_SCORE_WEIGHT
    )

    # ---- 技术因子 ----
    rsi_score, rsi_note = score_rsi(technical.get("rsi6"))
    trend_score, trend_note = score_trend(
        technical.get("macd_dif"),
        technical.get("macd_hist")
    )

    detail.update({
        "rsi6": {"score": rsi_score, "note": rsi_note, "weight": FactorWeightConfig.RSI_SCORE_WEIGHT},
        "trend": {"score": trend_score, "note": trend_note, "weight": FactorWeightConfig.TREND_SCORE_WEIGHT},
    })

    technical_subtotal = (
        rsi_score * FactorWeightConfig.RSI_SCORE_WEIGHT +
        trend_score * FactorWeightConfig.TREND_SCORE_WEIGHT
    )

    # ---- 宏观因子 ----
    # 周期股在行业下行时扣分
    if industry_cat == "cyclical":
        macro_score = 45 - max(0, min(20, 50 - debt_score)) * 0.3
        macro_note = "周期行业，需关注商品价格/运价等驱动因素"
        if fundamentals.get("debt_ratio", 0) > 50:
            macro_score = 25
            macro_note = "周期+高负债，行业下行时风险极大"
    elif industry_cat == "defensive":
        macro_score = 65
        macro_note = "防守型行业，下行周期中相对安全"
    else:
        macro_score = 55
        macro_note = "成长型行业，估值需匹配增长"

    detail["macro"] = {
        "score": macro_score,
        "note": macro_note,
        "industry_category": industry_cat
    }

    # ---- 综合评分 ----
    total_score = (
        valuation_subtotal * FactorWeightConfig.VALUATION_TOTAL_WEIGHT +
        quality_subtotal * FactorWeightConfig.QUALITY_TOTAL_WEIGHT +
        technical_subtotal * FactorWeightConfig.TECHNICAL_TOTAL_WEIGHT +
        macro_score * FactorWeightConfig.MACRO_TOTAL_WEIGHT
    )

    # 根据分数给出建议
    if total_score >= 75:
        suggested_action = "买入"
        confidence = min(1.0, total_score / 90)
    elif total_score >= 60:
        suggested_action = "持有(偏多)"
        confidence = 0.6
    elif total_score >= 45:
        suggested_action = "持有(偏空)"
        confidence = 0.5
    elif total_score >= 30:
        suggested_action = "卖出(适当减仓)"
        confidence = 0.65
    else:
        suggested_action = "卖出(清仓)"
        confidence = 0.8

    return {
        "total_score": round(total_score, 1),
        "valuation_score": round(valuation_subtotal, 1),
        "quality_score": round(quality_subtotal, 1),
        "technical_score": round(technical_subtotal, 1),
        "macro_score": round(macro_score, 1),
        "suggested_action": suggested_action,
        "confidence": confidence,
        "industry_category": industry_cat,
        "detail": detail,
    }
