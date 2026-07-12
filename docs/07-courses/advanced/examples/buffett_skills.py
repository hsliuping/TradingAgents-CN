"""
巴菲特价值投资工作流 —— 自定义 Skill 接口定义和实现参考

本文件定义了巴菲特工作流需要的两个自定义 Skill。
这些 Skill 通过平台的"分析流 → Skill 中心"创建，以下是接口定义和实现参考。

使用方式：
在 Skill 中心创建新 Skill 时，可以参考本文件的接口定义和实现逻辑。
系统会自动生成大部分代码，这里提供的是核心逻辑参考，供人工审查时对照。
"""

from typing import Annotated, Optional
from langchain_core.tools import tool

# ============================================================================
# Skill 1: ROE 趋势分析
# ============================================================================

# ── 接口定义 ──
ROE_TREND_SKILL_SPEC = {
    "tool_id": "get_roe_trend_analysis",
    "name": "ROE 趋势分析",
    "description": (
        "获取指定股票过去 5-10 年的 ROE 数据，计算趋势和稳定性，"
        "并基于巴菲特标准（ROE 持续 >15%）进行判断"
    ),
    "category": "fundamentals",
    "is_online": False,
    "capability_tags": ["roe", "return_on_equity", "trend", "buffett", "value_investing"],
    "when_to_use": "当需要评估公司长期 ROE 趋势、稳定性，或应用巴菲特 ROE 标准时使用。",
    "when_not_to_use": "不用于短期 ROE 波动分析；不适用于金融行业（ROE 计算方式不同）。",
    "returns": "返回 JSON 字符串，包含各年度 ROE、趋势分析、杜邦分解和巴菲特标准判断。",
    "example": "get_roe_trend_analysis(symbol='600519', years=10)",
    "related_tools": [
        "get_stock_fundamentals_unified",
        "get_piotroski_fscore",
        "get_dcf_valuation",
    ],

    # ── 参数定义 ──
    "parameters": [
        {
            "name": "symbol",
            "type": "string",
            "description": "A 股股票代码，如 600519",
            "required": True,
        },
        {
            "name": "years",
            "type": "integer",
            "description": "分析年数，默认 10，范围 5-15",
            "required": False,
            "default": 10,
        },
    ],

    # ── 输出结构 ──
    "output_structure": {
        "symbol": "股票代码",
        "years_analyzed": "实际分析的年数",
        "roe_series": {
            "2020": 0.28,
            "2021": 0.30,
            # ...
        },
        "statistics": {
            "mean": "ROE 均值",
            "std": "标准差",
            "cv": "变异系数（std/mean）",
            "min": "最小值",
            "max": "最大值",
        },
        "trend": {
            "direction": "上升/稳定/下降/波动",
            "slope": "线性回归斜率",
            "description": "趋势描述",
        },
        "dupont_decomposition": {
            "net_profit_margin": "净利率趋势",
            "asset_turnover": "资产周转率趋势",
            "equity_multiplier": "权益乘数趋势",
            "driver": "ROE 变化的主要驱动因素",
        },
        "buffett_criteria": {
            "all_years_above_15": True,
            "years_above_15": 8,
            "years_below_15": 2,
            "verdict": "通过/不通过",
            "note": "巴菲特要求过去 5 年 ROE 均高于 15%",
        },
    },

    # ── 需求描述（粘贴到 Skill 中心）──
    "requirement_description": """创建一个 ROE 趋势分析工具。
功能：获取指定股票过去 5-10 年的 ROE 数据，计算趋势和稳定性。

输出内容：
1. 各年度 ROE 数值
2. ROE 均值、标准差、变异系数
3. ROE 趋势判断（上升/稳定/下降/波动）
4. 杜邦分析分解：ROE = 净利率 × 资产周转率 × 权益乘数
5. 巴菲特标准判断：过去 5 年 ROE 是否均 >15%""",
}


# ── 实现参考（核心逻辑）──
# 注意：以下代码是参考实现，实际由 Skill 工坊自动生成并经过沙箱测试。
# 人工审查时请对照此逻辑验证生成的代码。

@tool
def get_roe_trend_analysis(
    symbol: Annotated[str, "A 股股票代码，如 600519"],
    years: Annotated[int, "分析年数，默认 10"] = 10,
) -> str:
    """ROE 趋势分析工具

    获取过去 N 年的 ROE 数据，计算趋势和稳定性，
    并基于巴菲特标准（ROE 持续 >15%）进行判断。

    Returns:
        JSON 字符串，包含 ROE 序列、统计量、趋势、杜邦分解和巴菲特标准判断。
    """
    import json
    import logging
    import numpy as np

    logger = logging.getLogger(__name__)

    try:
        # 1. 获取历史财务数据（使用平台内置的财务数据接口）
        from core.skill_runtime.standard_financial_apis import (
            get_historical_financial_annual_series,
        )

        # 获取关键财务指标序列
        series = get_historical_financial_annual_series(
            symbol=symbol,
            fields=[
                "roe",              # 净资产收益率
                "net_profit_margin",  # 净利率
                "asset_turnover",   # 资产周转率
                "equity_multiplier",  # 权益乘数
                "net_profit",       # 净利润
                "total_equity",     # 净资产
            ],
            years=years,
        )

        if not series or "roe" not in series or len(series["roe"]) == 0:
            return json.dumps({
                "status": "error",
                "message": f"无法获取 {symbol} 的历史 ROE 数据",
                "symbol": symbol,
            }, ensure_ascii=False)

        # 2. 提取 ROE 序列
        roe_values = [float(v) if v is not None else None for v in series["roe"]]
        years_list = series.get("years", list(range(len(roe_values))))

        # 过滤掉 None 值
        valid_pairs = [(y, v) for y, v in zip(years_list, roe_values) if v is not None]
        if len(valid_pairs) < 3:
            return json.dumps({
                "status": "error",
                "message": f"有效 ROE 数据不足（仅 {len(valid_pairs)} 年）",
                "symbol": symbol,
            }, ensure_ascii=False)

        valid_years = [p[0] for p in valid_pairs]
        valid_roes = [p[1] for p in valid_pairs]

        # 3. 计算统计量
        roe_array = np.array(valid_roes)
        mean_roe = float(np.mean(roe_array))
        std_roe = float(np.std(roe_array))
        cv_roe = float(std_roe / mean_roe) if mean_roe != 0 else None
        min_roe = float(np.min(roe_array))
        max_roe = float(np.max(roe_array))

        # 4. 趋势分析（线性回归斜率）
        x = np.arange(len(valid_roes))
        slope = float(np.polyfit(x, valid_roes, 1)[0])

        if slope > 0.01:
            direction = "上升"
        elif slope < -0.01:
            direction = "下降"
        elif cv_roe and cv_roe > 0.2:
            direction = "波动"
        else:
            direction = "稳定"

        # 5. 杜邦分解
        dupont = {}
        for field in ["net_profit_margin", "asset_turnover", "equity_multiplier"]:
            if field in series:
                vals = [float(v) if v is not None else None for v in series[field]]
                valid_vals = [v for v in vals if v is not None]
                if valid_vals:
                    dupont[field] = {
                        "start": valid_vals[0],
                        "end": valid_vals[-1],
                        "change": valid_vals[-1] - valid_vals[0],
                    }

        # 判断 ROE 变化的主要驱动因素
        driver = "无法确定"
        if dupont:
            changes = {k: abs(v["change"]) for k, v in dupont.items()}
            driver = max(changes, key=changes.get)

        # 6. 巴菲特标准判断
        buffett_threshold = 0.15
        years_above = sum(1 for r in valid_roes if r > buffett_threshold)
        years_below = len(valid_roes) - years_above
        all_above = years_below == 0
        last_5_above = all(r > buffett_threshold for r in valid_roes[-5:]) if len(valid_roes) >= 5 else False

        if last_5_above:
            verdict = "通过"
            note = "巴菲特标准：过去 5 年 ROE 均高于 15%"
        elif years_above >= len(valid_roes) * 0.8:
            verdict = "基本通过"
            note = f"过去 {len(valid_roes)} 年中有 {years_above} 年 ROE > 15%"
        else:
            verdict = "不通过"
            note = f"仅 {years_above}/{len(valid_roes)} 年 ROE > 15%"

        # 7. 构建输出
        result = {
            "symbol": symbol,
            "years_analyzed": len(valid_pairs),
            "roe_series": {str(y): round(v, 4) for y, v in valid_pairs},
            "statistics": {
                "mean": round(mean_roe, 4),
                "std": round(std_roe, 4),
                "cv": round(cv_roe, 4) if cv_roe else None,
                "min": round(min_roe, 4),
                "max": round(max_roe, 4),
            },
            "trend": {
                "direction": direction,
                "slope": round(slope, 6),
                "description": f"ROE 趋势{direction}，斜率 {slope:.4f}/年",
            },
            "dupont_decomposition": {
                **dupont,
                "driver": f"ROE 变化的主要驱动因素：{driver}",
            },
            "buffett_criteria": {
                "all_years_above_15": all_above,
                "years_above_15": years_above,
                "years_below_15": years_below,
                "last_5_years_above_15": last_5_above,
                "verdict": verdict,
                "note": note,
            },
        }

        return json.dumps(result, ensure_ascii=False, indent=2)

    except Exception as e:
        logger.error(f"ROE 趋势分析失败: {e}", exc_info=True)
        return json.dumps({
            "status": "error",
            "message": str(e),
            "symbol": symbol,
        }, ensure_ascii=False)


# ============================================================================
# Skill 2: 安全边际计算
# ============================================================================

# ── 接口定义 ──
MARGIN_OF_SAFETY_SKILL_SPEC = {
    "tool_id": "get_margin_of_safety",
    "name": "安全边际计算",
    "description": (
        "基于 DCF 估值结果和当前股价，计算保守/基准/乐观三种情景下的安全边际，"
        "并给出巴菲特风格的投资建议"
    ),
    "category": "fundamentals",
    "is_online": False,
    "capability_tags": ["margin_of_safety", "buffett", "value_investing", "valuation"],
    "when_to_use": "当需要计算安全边际、判断买入时机是否符合巴菲特标准时使用。",
    "when_not_to_use": "不适用于没有正自由现金流的企业（DCF 无法计算）。",
    "returns": "返回 JSON 字符串，包含三种情景的内在价值、安全边际和投资建议。",
    "example": "get_margin_of_safety(symbol='600519')",
    "related_tools": [
        "get_dcf_valuation",
        "get_extended_valuation",
        "get_comparable_valuation",
    ],

    # ── 参数定义 ──
    "parameters": [
        {
            "name": "symbol",
            "type": "string",
            "description": "A 股股票代码，如 600519",
            "required": True,
        },
        {
            "name": "current_price",
            "type": "float",
            "description": "当前股价，默认 None 自动获取",
            "required": False,
            "default": None,
        },
    ],

    # ── 输出结构 ──
    "output_structure": {
        "symbol": "股票代码",
        "current_price": "当前股价",
        "scenarios": {
            "conservative": {
                "intrinsic_value": "保守情景内在价值",
                "margin_of_safety": "安全边际百分比",
                "rating": "有吸引力/合理/偏高/高估",
            },
            "base": { ... },
            "optimistic": { ... },
        },
        "overall_rating": "综合评级",
        "buffett_advice": "巴菲特风格投资建议",
    },

    # ── 需求描述 ──
    "requirement_description": """创建一个安全边际计算工具。
功能：基于 DCF 估值结果和当前股价，计算安全边际。

输入：股票代码
输出：
1. 调用 DCF 估值获取保守/基准/乐观三种情景的内在价值
2. 获取当前股价
3. 计算各情景下的安全边际 = (内在价值 - 当前价格) / 内在价值
4. 给出投资建议：
   - 安全边际 > 30%：有吸引力的买入机会
   - 安全边际 15-30%：合理价格
   - 安全边际 0-15%：价格偏高
   - 安全边际 < 0：高估""",
}


# ── 实现参考（核心逻辑）──

@tool
def get_margin_of_safety(
    symbol: Annotated[str, "A 股股票代码，如 600519"],
    current_price: Annotated[Optional[float], "当前股价，默认 None 自动获取"] = None,
) -> str:
    """安全边际计算工具

    基于 DCF 估值结果和当前股价，计算三种情景下的安全边际。

    Returns:
        JSON 字符串，包含三种情景的内在价值、安全边际和投资建议。
    """
    import json
    import logging

    logger = logging.getLogger(__name__)

    try:
        # 1. 调用 DCF 估值工具获取内在价值
        from core.tools.implementations.fundamentals.valuation.dcf_valuation import get_dcf_valuation
        from core.tools.implementations.fundamentals.valuation.extended_valuation import get_extended_valuation

        # 获取基准 DCF 估值
        dcf_result_raw = get_dcf_valuation.invoke({
            "symbol": symbol,
            "growth_rate": None,        # 自动估算
            "wacc": None,               # 自动计算
            "terminal_growth_rate": 2.5,
            "forecast_years": 5,
        })

        dcf_result = json.loads(dcf_result_raw) if isinstance(dcf_result_raw, str) else dcf_result_raw

        if dcf_result.get("status") == "error":
            return json.dumps({
                "status": "error",
                "message": f"DCF 估值失败: {dcf_result.get('message', '未知错误')}",
                "symbol": symbol,
            }, ensure_ascii=False)

        # 2. 获取当前股价
        if current_price is None:
            from core.skill_runtime.standard_financial_apis import get_current_price
            current_price = get_current_price(symbol)

        if current_price is None or current_price <= 0:
            return json.dumps({
                "status": "error",
                "message": "无法获取当前股价",
                "symbol": symbol,
            }, ensure_ascii=False)

        # 3. 从 DCF 结果中提取三种情景
        scenarios_data = dcf_result.get("scenarios", {})
        valuation = dcf_result.get("valuation", {})

        base_value = valuation.get("per_share_value")
        bull_value = scenarios_data.get("bull", {}).get("per_share_value")
        bear_value = scenarios_data.get("base", {}).get("per_share_value")  # base 在 scenarios 中是保守

        # 如果没有情景分析，使用估值结果 ±20% 作为保守/乐观
        if base_value is None:
            return json.dumps({
                "status": "error",
                "message": "DCF 估值结果缺少每股内在价值",
                "symbol": symbol,
            }, ensure_ascii=False)

        conservative_value = bear_value if bear_value else base_value * 0.8
        base_case_value = base_value
        optimistic_value = bull_value if bull_value else base_value * 1.2

        # 4. 计算安全边际
        def calc_margin(intrinsic, price):
            if intrinsic is None or intrinsic <= 0:
                return None
            return (intrinsic - price) / intrinsic

        def margin_rating(margin):
            if margin is None:
                return "无法计算"
            if margin > 0.30:
                return "有吸引力"
            elif margin > 0.15:
                return "合理"
            elif margin > 0:
                return "偏高"
            else:
                return "高估"

        scenarios = {
            "conservative": {
                "intrinsic_value": round(conservative_value, 2),
                "margin_of_safety": round(calc_margin(conservative_value, current_price), 4) if calc_margin(conservative_value, current_price) is not None else None,
                "rating": margin_rating(calc_margin(conservative_value, current_price)),
            },
            "base": {
                "intrinsic_value": round(base_case_value, 2),
                "margin_of_safety": round(calc_margin(base_case_value, current_price), 4) if calc_margin(base_case_value, current_price) is not None else None,
                "rating": margin_rating(calc_margin(base_case_value, current_price)),
            },
            "optimistic": {
                "intrinsic_value": round(optimistic_value, 2),
                "margin_of_safety": round(calc_margin(optimistic_value, current_price), 4) if calc_margin(optimistic_value, current_price) is not None else None,
                "rating": margin_rating(calc_margin(optimistic_value, current_price)),
            },
        }

        # 5. 综合评级
        base_margin = calc_margin(base_case_value, current_price)
        conservative_margin = calc_margin(conservative_value, current_price)

        if conservative_margin and conservative_margin > 0.15:
            overall = "有安全边际"
            advice = "即使在保守情景下仍有安全边际，符合巴菲特投资标准"
        elif base_margin and base_margin > 0.15:
            overall = "基准情景有安全边际"
            advice = "基准情景下有安全边际，但保守情景偏紧，建议谨慎"
        elif base_margin and base_margin > 0:
            overall = "安全边际不足"
            advice = "当前价格偏高，安全边际不足，建议等待更好价格"
        else:
            overall = "高估"
            advice = "当前价格高于内在价值，不符合巴菲特投资标准"

        result = {
            "symbol": symbol,
            "current_price": current_price,
            "scenarios": scenarios,
            "overall_rating": overall,
            "buffett_advice": advice,
            "dcf_parameters": dcf_result.get("parameters", {}),
            "note": "安全边际 = (内在价值 - 当前价格) / 内在价值。巴菲特通常要求 >15-30%。",
        }

        return json.dumps(result, ensure_ascii=False, indent=2)

    except Exception as e:
        logger.error(f"安全边际计算失败: {e}", exc_info=True)
        return json.dumps({
            "status": "error",
            "message": str(e),
            "symbol": symbol,
        }, ensure_ascii=False)


# ============================================================================
# 导出所有 Skill 规格
# ============================================================================

BUFFETT_SKILL_SPECS = [
    ROE_TREND_SKILL_SPEC,
    MARGIN_OF_SAFETY_SKILL_SPEC,
]
