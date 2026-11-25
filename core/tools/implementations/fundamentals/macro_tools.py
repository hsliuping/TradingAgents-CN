"""宏观仪表盘与收益率曲线分析工具。"""

import datetime
import json
import logging
from statistics import median
from typing import Any, Dict, List, Optional

import pandas as pd
from langchain_core.tools import tool

from core.tools.base import register_tool

logger = logging.getLogger(__name__)


def _get_db():
    """获取同步 MongoDB 连接。"""
    from app.core.database import get_mongo_db_sync

    return get_mongo_db_sync()


def _safe_float(value: Any) -> Optional[float]:
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        try:
            numeric = float(value)
            if numeric != numeric:
                return None
            return numeric
        except (TypeError, ValueError):
            return None
    try:
        text = str(value).strip()
        if not text:
            return None
        numeric = float(text)
        if numeric != numeric:
            return None
        return numeric
    except (TypeError, ValueError):
        return None


def _get_market_pe_pb_distribution() -> Dict[str, Any]:
    """从 stock_basic_info 统计全市场 PE/PB 分布。"""
    db = _get_db()
    col = db["stock_basic_info"]

    all_stocks = list(col.find({}, {
        "_id": 0,
        "symbol": 1,
        "name": 1,
        "industry": 1,
        "pe_ttm": 1,
        "pb": 1,
        "pb_mrq": 1,
        "total_mv": 1,
    }))

    pe_values: List[float] = []
    pb_values: List[float] = []
    industry_stats: Dict[str, List[float]] = {}
    total_tracked = 0

    for stock in all_stocks:
        if not stock.get("symbol"):
            continue
        total_tracked += 1

        pe = _safe_float(stock.get("pe_ttm"))
        if pe is not None and 0 < pe < 1000:
            pe_values.append(pe)

        pb_raw = _safe_float(stock.get("pb") or stock.get("pb_mrq"))
        if pb_raw is not None and 0 < pb_raw < 100:
            pb_values.append(pb_raw)

        industry = (stock.get("industry") or "未知").strip()
        if industry not in industry_stats:
            industry_stats[industry] = []
        if pe is not None and 0 < pe < 1000:
            industry_stats[industry].append(pe)

    return {
        "total_tracked": total_tracked,
        "pe": {
            "count": len(pe_values),
            "avg": round(sum(pe_values) / len(pe_values), 2) if pe_values else None,
            "median": round(median(pe_values), 2) if pe_values else None,
            "min": round(min(pe_values), 2) if pe_values else None,
            "max": round(max(pe_values), 2) if pe_values else None,
        },
        "pb": {
            "count": len(pb_values),
            "avg": round(sum(pb_values) / len(pb_values), 2) if pb_values else None,
            "median": round(median(pb_values), 2) if pb_values else None,
            "min": round(min(pb_values), 2) if pb_values else None,
            "max": round(max(pb_values), 2) if pb_values else None,
        },
        "industry_count": len(industry_stats),
    }


@tool
@register_tool(
    tool_id="get_macro_dashboard",
    name="宏观仪表盘",
    description=(
        "返回市场宏观概览仪表盘，包含全市场估值分布（PE/PB）、宏观指标占位槽（CPI/GDP/PMI/利率）"
        "和市场宽度统计。宏观指标需从外部来源补充。"
    ),
    category="fundamentals",
    is_online=False,
    auto_register=True,
    timeout_tier="light",
    capability_tags=["macro", "market_overview"],
    tool_role_hint="specialized",
    output_shape="structured_json",
    preferred_for=["市场整体估值概览", "宏观数据框架查询"],
    when_to_use=(
        "当需要快速了解全市场估值水平、PE/PB 分布、市场整体宽度时使用。"
        "此工具可提供从本地数据库能拿到的市场统计，以及需要外部填充的宏观指标清单。"
    ),
    when_not_to_use=(
        "不适合查询具体股票的基本面或财务数据；"
        "不适合获取实时 CPI/GDP/PMI 实际数值（这些需要外部数据源补充）。"
    ),
    returns=(
        "返回 JSON 字符串，包含 market_overview（全市场估值统计）、"
        "indicator_slots（宏观指标占位，状态为 pending_external_data）、"
        "market_breadth（市场宽度，含数据来源说明）。"
    ),
    example="get_macro_dashboard()",
    related_tools=["get_yield_curve_analysis", "get_sector_performance"],
)
def get_macro_dashboard() -> str:
    """获取市场宏观概览仪表盘。

    返回全市场 PE/PB 统计数据，以及需要外部数据源补充的宏观指标框架。

    Returns:
        str: JSON 字符串，字段说明——
            dashboard_date: 仪表盘日期（YYYY-MM-DD）
            data_source_note: 数据来源说明
            market_overview: dict 市场总览——
                — total_stocks_tracked: 跟踪的股票总数
                — pe_ttm_distribution: dict PE_TTM分布（avg/median/min/max/valid_samples）
                — pb_distribution: dict PB分布（avg/median/min/max/valid_samples）
                — industry_coverage: dict 行业覆盖（total_industries）
            indicator_slots: dict 宏观指标占位，每个指标结构——
                — label: 指标名称
                — status: 状态（固定为 "pending_external_data"）
                — suggested_source: 建议数据源
                — note: 说明
                包含 key: cpi / gdp / pmi / interest_rates
            market_breadth: dict 市场宽度——
                — status: 状态（固定为 "partial_data"）
                — note: 说明
                — available_from_system: list[str] 系统可用数据源
            suggested_external_sources: dict 建议的外部数据源（akshare/tushare/eastmoney）
            status: 状态（仅异常时为 "error"）
            message: 错误信息（仅 status="error" 时存在）
    """
    try:
        today = datetime.date.today()
        market_stats = _get_market_pe_pb_distribution()

        dashboard = {
            "dashboard_date": today.isoformat(),
            "data_source_note": (
                "以下 market_overview 来自本地数据库 stock_basic_info 集合的统计快照，"
                "反映系统已同步的 A 股全市场 PE/PB 分布。"
                "indicator_slots 中的宏观指标需要从外部数据源（如东方财富、国家统计局 API）获取。"
            ),
            "market_overview": {
                "total_stocks_tracked": market_stats["total_tracked"],
                "pe_ttm_distribution": {
                    "avg": market_stats["pe"]["avg"],
                    "median": market_stats["pe"]["median"],
                    "min": market_stats["pe"]["min"],
                    "max": market_stats["pe"]["max"],
                    "valid_samples": market_stats["pe"]["count"],
                },
                "pb_distribution": {
                    "avg": market_stats["pb"]["avg"],
                    "median": market_stats["pb"]["median"],
                    "min": market_stats["pb"]["min"],
                    "max": market_stats["pb"]["max"],
                    "valid_samples": market_stats["pb"]["count"],
                },
                "industry_coverage": {
                    "total_industries": market_stats["industry_count"],
                },
            },
            "indicator_slots": {
                "cpi": {
                    "label": "居民消费价格指数 (CPI)",
                    "status": "pending_external_data",
                    "suggested_source": "国家统计局 / 东方财富宏观经济数据",
                    "note": "需外部 API 补充月度 CPI 同比/环比数据",
                },
                "gdp": {
                    "label": "国内生产总值 (GDP)",
                    "status": "pending_external_data",
                    "suggested_source": "国家统计局 / 东方财富宏观经济数据",
                    "note": "需外部 API 补充季度 GDP 同比/累计增速",
                },
                "pmi": {
                    "label": "采购经理人指数 (PMI)",
                    "status": "pending_external_data",
                    "suggested_source": "国家统计局 / 东方财富宏观经济数据",
                    "note": "需外部 API 补充制造业/非制造业 PMI",
                },
                "interest_rates": {
                    "label": "利率 (LPR/MLF/国债收益率)",
                    "status": "pending_external_data",
                    "suggested_source": "中国人民银行 / 中国货币网 / 东方财富",
                    "note": "需外部 API 补充 LPR、MLF 利率及国债收益率曲线",
                },
            },
            "market_breadth": {
                "status": "partial_data",
                "note": (
                    "市场宽度统计（涨跌家数、MA50 以上占比等）需要日线数据全量计算，"
                    "当前系统暂未预聚合该统计。可通过外部数据源或下游查询补充。"
                ),
                "available_from_system": [
                    "单只股票的日线行情（get_stock_daily_quotes）",
                    "行业估值汇总（summarize_industry_valuation）",
                    "全市场 PE/PB 分布（本工具已提供）",
                ],
            },
            "suggested_external_sources": {
                "akshare": "可通过 akshare 获取宏观经济指标和债券收益率数据",
                "tushare": "可通过 tushare 获取宏观经济指标（需积分）",
                "eastmoney": "东方财富宏观经济数据接口",
            },
        }

        return json.dumps(dashboard, ensure_ascii=False, indent=2, default=str)

    except Exception as exc:
        logger.error("宏观仪表盘获取失败: %s", exc, exc_info=True)
        return json.dumps({"status": "error", "message": str(exc)}, ensure_ascii=False, indent=2, default=str)


def _fetch_china_yield_curve() -> dict:
    """通过 AKShare 获取中国国债收益率曲线最新数据。"""
    try:
        import akshare as ak
        df = ak.bond_china_yield()
        # 筛选"中债国债收益率曲线"
        treasury = df[df["曲线名称"] == "中债国债收益率曲线"]
        if treasury.empty:
            return {"status": "no_data", "message": "未找到国债收益率曲线数据"}
        # 取最新日期
        treasury["日期"] = pd.to_datetime(treasury["日期"])
        latest = treasury.loc[treasury["日期"].idxmax()]
        yields = {}
        for col in ["3月", "6月", "1年", "3年", "5年", "7年", "10年", "30年"]:
            val = latest.get(col)
            if val is not None and val == val:
                yields[col] = round(float(val), 4)
            else:
                yields[col] = None
        return {
            "status": "ok",
            "date": str(latest["日期"].date()),
            "yields": yields,
        }
    except Exception as e:
        logger.warning("AKShare 国债收益率获取失败: %s", e)
        return {"status": "error", "message": str(e)}


def _fetch_zh_us_rate() -> dict:
    """通过 AKShare 获取中美收益率对比最新数据。"""
    try:
        import akshare as ak
        df = ak.bond_zh_us_rate()
        df["日期"] = pd.to_datetime(df["日期"])
        latest = df.sort_values("日期").iloc[-1]
        result = {
            "date": str(latest["日期"].date()),
            "china": {},
            "us": {},
            "spread_cn": {},
        }
        cn_cols = {"中国国债收益率2年": "2年", "中国国债收益率5年": "5年",
                    "中国国债收益率10年": "10年", "中国国债收益率30年": "30年"}
        us_cols = {"美国国债收益率2年": "2年", "美国国债收益率5年": "5年",
                    "美国国债收益率10年": "10年", "美国国债收益率30年": "30年"}
        for raw, name in cn_cols.items():
            v = latest.get(raw)
            if v is not None and v == v:
                result["china"][name] = round(float(v), 4)
        for raw, name in us_cols.items():
            v = latest.get(raw)
            if v is not None and v == v:
                result["us"][name] = round(float(v), 4)
        spread = latest.get("中国国债收益率10年-2年")
        if spread is not None and spread == spread:
            result["spread_cn"]["10Y-2Y"] = round(float(spread), 4)
        return result
    except Exception as e:
        logger.warning("AKShare 中美收益率获取失败: %s", e)
        return {"status": "error", "message": str(e)}


@tool
@register_tool(
    tool_id="get_yield_curve_analysis",
    name="收益率曲线分析",
    description=(
        "通过 akshare 实时获取中国国债收益率曲线数据，"
        "包含各期限（3月/6月/1年/3年/5年/7年/10年/30年）国债到期收益率、"
        "10Y-2Y 期限利差、中美收益率对比。同时提供曲线形态判断。"
    ),
    category="fundamentals",
    is_online=True,
    auto_register=True,
    timeout_tier="light",
    capability_tags=["macro", "yield_curve", "interest_rate"],
    tool_role_hint="specialized",
    output_shape="structured_json",
    preferred_for=["国债收益率查询", "收益率曲线形态判断", "中美利差对比"],
    when_to_use=(
        "当用户问及当前国债收益率水平、收益率曲线形态（正常/倒挂/平坦）、"
        "中美利差对比、期限利差（10Y-2Y）时使用。"
    ),
    when_not_to_use=(
        "不适合查询个券（单只债券）的收益率或估值数据；"
        "不适合查询历史收益率序列（如需长时间序列请直接使用 akshare）。"
    ),
    returns=(
        "返回 JSON 字符串，包含 yield_curve（中国国债各期限收益率）、"
        "date（数据日期）、curve_shape（曲线形态判断）、"
        "key_spreads（关键利差）、zh_us_comparison（中美对比）。"
    ),
    example="get_yield_curve_analysis()",
    related_tools=["get_macro_dashboard", "get_bond_yield_calculation", "get_monetary_environment", "get_credit_spread_analysis"],
)
def get_yield_curve_analysis() -> str:
    """获取中国国债收益率曲线实时分析。

    通过 AKShare 获取中债国债收益率曲线数据，包含各期限收益率、
    曲线形态判断、期限利差和中美对比。

    Returns:
        str: JSON 字符串，字段说明——
            status: 状态: "ok" | "error"
            date: 数据日期（YYYY-MM-DD）
            data_source: 数据来源说明
            yield_curve: dict 各期限收益率（key 为 "3月"/"6月"/"1年"/"3年"/"5年"/"7年"/"10年"/"30年"）
            curve_shape: 曲线形态: "正常向上倾斜" | "倒挂" | "平坦" | "数据不足无法判断"
            key_spreads: dict 关键利差（key 如 "10Y-1Y"/"10Y-3Y"/"10Y-5Y"）
            zh_us_comparison: dict 中美收益率对比（数据不可用时为 {"status": "unavailable", "message": ...}）——
                — date: 日期
                — china: dict 中国各期限收益率
                — us: dict 美国各期限收益率
                — spread_cn: dict 中国期限利差（如 10Y-2Y）
            data_note: 数据注释
            message: 错误信息（仅 status="error" 时存在）
            suggestion: 建议（仅部分错误场景存在）
    """
    try:
        curve = _fetch_china_yield_curve()
        zh_us = _fetch_zh_us_rate()

        if curve.get("status") == "error":
            return json.dumps({
                "status": "error",
                "message": f"国债收益率数据获取失败: {curve.get('message')}",
                "suggestion": "可通过 akshare.bond_china_yield() 直接获取",
            }, ensure_ascii=False, indent=2, default=str)

        yields = curve.get("yields", {})
        date = curve.get("date", "未知")

        # 判断曲线形态
        y1 = yields.get("1年")
        y10 = yields.get("10年")
        y2 = yields.get("3月")
        if y10 is not None and y1 is not None:
            if y10 > y1 + 0.5:
                curve_shape = "正常向上倾斜"
            elif y10 < y1 - 0.1:
                curve_shape = "倒挂"
            else:
                curve_shape = "平坦"
        else:
            curve_shape = "数据不足无法判断"

        # 关键利差
        spreads = {}
        if y10 is not None and yields.get("1年") is not None:
            spreads["10Y-1Y"] = round(y10 - yields["1年"], 4)
        if y10 is not None and yields.get("3年") is not None:
            spreads["10Y-3Y"] = round(y10 - yields["3年"], 4)
        if y10 is not None and yields.get("5年") is not None:
            spreads["10Y-5Y"] = round(y10 - yields["5年"], 4)

        payload = {
            "status": "ok",
            "date": date,
            "data_source": "akshare.bond_china_yield() / bond_zh_us_rate()",
            "yield_curve": yields,
            "curve_shape": curve_shape,
            "key_spreads": spreads,
            "zh_us_comparison": zh_us if "status" not in zh_us else {
                "status": "unavailable",
                "message": zh_us.get("message", ""),
            },
            "data_note": "曲线基于中债国债收益率曲线最新数据，单位为百分比（%）",
        }

        return json.dumps(payload, ensure_ascii=False, indent=2, default=str)

    except Exception as exc:
        logger.error("收益率曲线分析失败: %s", exc, exc_info=True)
        return json.dumps({"status": "error", "message": str(exc)}, ensure_ascii=False, indent=2, default=str)


__all__ = ["get_macro_dashboard", "get_yield_curve_analysis"]
