"""经济周期定位、货币环境分析与行业轮动信号工具。"""

import datetime
import json
import logging
from statistics import median
from typing import Any, Dict, List, Optional

import numpy as np
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


def _fetch_zh_us_rate() -> dict:
    """通过 AKShare 获取中美收益率对比最新数据。"""
    try:
        import akshare as ak

        df = ak.bond_zh_us_rate()
        df["日期"] = pd.to_datetime(df["日期"])
        latest = df.sort_values("日期").iloc[-1]
        result: dict = {
            "date": str(latest["日期"].date()),
            "china": {},
            "us": {},
            "spread_cn": {},
            "history": [],
        }
        cn_cols = {
            "中国国债收益率2年": "2年",
            "中国国债收益率5年": "5年",
            "中国国债收益率10年": "10年",
            "中国国债收益率30年": "30年",
        }
        us_cols = {
            "美国国债收益率2年": "2年",
            "美国国债收益率5年": "5年",
            "美国国债收益率10年": "10年",
            "美国国债收益率30年": "30年",
        }
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

        # 取近 3 个月的历史记录用于趋势计算
        three_months_ago = latest["日期"] - pd.DateOffset(months=3)
        hist = df[df["日期"] >= three_months_ago].sort_values("日期")
        hist_records = []
        for _, row in hist.iterrows():
            rec = {"date": str(row["日期"].date())}
            for raw, name in cn_cols.items():
                v = row.get(raw)
                if v is not None and v == v:
                    rec[f"china_{name}"] = round(float(v), 4)
            for raw, name in us_cols.items():
                v = row.get(raw)
                if v is not None and v == v:
                    rec[f"us_{name}"] = round(float(v), 4)
            hist_records.append(rec)
        result["history"] = hist_records

        return result
    except Exception as e:
        logger.warning("AKShare 中美收益率获取失败: %s", e)
        return {"status": "error", "message": str(e)}


def _fetch_csi300_daily(days: int = 90) -> dict:
    """通过 AKShare 获取沪深 300 日线数据。"""
    try:
        import akshare as ak

        df = ak.stock_zh_index_daily("sh000300")
        df["date"] = pd.to_datetime(df["date"])
        df = df.sort_values("date")
        # 取最近 N 天
        cutoff = df["date"].max() - pd.Timedelta(days=days)
        df = df[df["date"] >= cutoff].copy()
        if df.empty:
            return {"status": "no_data", "message": "沪深300数据为空"}
        records = []
        for _, row in df.iterrows():
            records.append({
                "date": str(row["date"].date()),
                "close": round(float(row["close"]), 2),
            })
        return {
            "status": "ok",
            "latest_date": str(df["date"].max().date()),
            "latest_close": round(float(df["close"].iloc[-1]), 2),
            "records": records,
        }
    except Exception as e:
        logger.warning("AKShare 沪深300获取失败: %s", e)
        return {"status": "error", "message": str(e)}


def _compute_merrill_lynch_clock(
    market_return_3m: float,
    yield_change_3m: float,
) -> dict:
    """根据市场回报率和收益率变化映射美林时钟四象限。

    Args:
        market_return_3m: 沪深300近3个月收益率（%）
        yield_change_3m: 中国10Y收益率近3个月变化（百分点）

    Returns:
        包含象限、推荐资产、信号描述的字典
    """
    growth_direction = (
        "high"
        if market_return_3m > 5.0
        else ("low" if market_return_3m < -5.0 else "neutral")
    )
    inflation_direction = (
        "rising"
        if yield_change_3m > 0.2
        else ("falling" if yield_change_3m < -0.2 else "stable")
    )

    # 美林时钟映射
    if growth_direction == "high" and inflation_direction == "rising":
        quadrant = "过热"
        recommended_asset = "商品"
        signal_desc = "经济增长强劲，通胀上行，适合配置大宗商品和周期性资产"
    elif growth_direction == "low" and inflation_direction == "rising":
        quadrant = "滞涨"
        recommended_asset = "现金"
        signal_desc = "经济增长放缓但通胀高企，现金为王，防御为主"
    elif growth_direction == "low" and inflation_direction == "falling":
        quadrant = "衰退"
        recommended_asset = "债券"
        signal_desc = "经济收缩，通胀回落，利率下行期债券表现最佳"
    elif growth_direction == "high" and inflation_direction == "falling":
        quadrant = "复苏"
        recommended_asset = "股票"
        signal_desc = "经济恢复增长，通胀温和，权益资产受益于企业盈利改善"
    else:
        # 中性区域
        quadrant = "过渡/模糊"
        recommended_asset = "均衡配置"
        signal_desc = "信号不明确，建议股债均衡配置"

    return {
        "quadrant": quadrant,
        "recommended_asset_class": recommended_asset,
        "signal_description": signal_desc,
    }


@tool
@register_tool(
    tool_id="get_economic_cycle_position",
    name="经济周期定位",
    description=(
        "基于美林时钟框架，通过沪深300近3个月收益率（作为增长代理指标）和"
        "中国10年期国债收益率近3个月变化（作为通胀代理指标），"
        "自动定位当前经济周期所处的象限（复苏/过热/滞涨/衰退），"
        "并给出对应的推荐资产配置方向。"
    ),
    category="fundamentals",
    is_online=True,
    auto_register=True,
    timeout_tier="light",
    capability_tags=["macro", "economic_cycle", "asset_allocation"],
    tool_role_hint="specialized",
    output_shape="structured_json",
    preferred_for=["经济周期位置判断", "美林时钟分析", "宏观资产配置参考"],
    when_to_use=(
        "当用户询问当前经济处于什么周期阶段、美林时钟指向哪个象限、"
        "应该配置股票/债券/商品/现金时使用。需要实时宏观数据支持。"
    ),
    when_not_to_use=(
        "不适合查询具体行业或个股的投资建议；"
        "不适合替代详细的宏观研究报告；"
        "当仅需要国债收益率数据时请使用 get_yield_curve_analysis。"
    ),
    returns=(
        "返回 JSON 字符串，包含 cycle_position（周期阶段定位）、"
        "gdp_proxy（沪深300近3个月收益率）、inflation_proxy（国债收益率变化）、"
        "quadrant（美林时钟象限）、recommended_asset_class（推荐资产类别）、"
        "data_quality（数据质量说明）等字段。"
    ),
    example="get_economic_cycle_position()",
    related_tools=["get_yield_curve_analysis", "get_monetary_environment", "get_macro_dashboard"],
)
def get_economic_cycle_position() -> str:
    """获取经济周期定位（美林时钟）分析。

    通过 AKShare 实时获取沪深300指数收益率和国债收益率数据，
    运用简化美林时钟框架判断当前周期所处位置及推荐资产配置。

    Returns:
        str: JSON 字符串，字段说明——
            status: 状态: "ok" | "error"
            analysis_date: 分析日期（YYYY-MM-DD）
            data_source: 数据来源说明
            cycle_position: dict 周期定位——
                — quadrant: 美林时钟象限
                — recommended_asset_class: 推荐资产类别
                — signal_description: 信号描述
            gdp_proxy: dict 增长代理指标（沪深300近3个月收益率）——
                — label: 指标标签
                — value_pct: 收益率（%）
                — direction: 方向: "高增长" | "低增长" | "中性"
                — threshold_note: 阈值说明
            inflation_proxy: dict 通胀代理指标（10Y国债收益率近3个月变化）——
                — label: 指标标签
                — value_change: 收益率变化
                — direction: 方向: "上升" | "下降" | "平稳"
                — threshold_note: 阈值说明
            current_data: dict 当前数据——
                — csi300_latest_close: 沪深300最新收盘价
                — csi300_latest_date: 沪深300最新日期
                — china_10y_yield: 中国10年期收益率
                — china_10y_3m_ago: 3个月前的中国10年期收益率
                — us_10y_yield: 美国10年期收益率
                — cn_us_spread_10y: 中美10年期利差
            data_quality: dict 数据质量——
                — has_csi300_data: 是否有沪深300数据
                — has_yield_history: 是否有收益率历史
                — yield_history_days: 历史数据天数
                — note: 说明文本
            message: 错误信息（仅 status="error" 时存在）
    """
    try:
        # 1. 获取中美收益率数据（含近3个月历史）
        rate_data = _fetch_zh_us_rate()
        if "status" in rate_data and rate_data["status"] == "error":
            return json.dumps({
                "status": "error",
                "message": f"收益率数据获取失败: {rate_data.get('message')}",
            }, ensure_ascii=False, indent=2, default=str)

        # 2. 获取沪深300日线数据
        csi300 = _fetch_csi300_daily(days=120)  # 多取一些确保有3个月数据
        if csi300.get("status") != "ok":
            return json.dumps({
                "status": "error",
                "message": f"沪深300数据获取失败: {csi300.get('message')}",
            }, ensure_ascii=False, indent=2, default=str)

        # 3. 计算沪深300近3个月收益率
        records = csi300.get("records", [])
        if len(records) < 2:
            return json.dumps({
                "status": "error",
                "message": "沪深300数据不足，无法计算收益率",
            }, ensure_ascii=False, indent=2, default=str)

        latest_close = records[-1]["close"]
        # 找到大约90天前的收盘价
        target_date = datetime.datetime.strptime(records[-1]["date"], "%Y-%m-%d") - datetime.timedelta(days=90)
        three_month_ago = None
        for rec in records:
            rec_date = datetime.datetime.strptime(rec["date"], "%Y-%m-%d")
            if rec_date >= target_date:
                three_month_ago = rec["close"]
                break
        if three_month_ago is None:
            three_month_ago = records[0]["close"]

        market_return_3m = round((latest_close - three_month_ago) / three_month_ago * 100, 2)

        # 4. 计算中国10Y收益率近3个月变化
        history = rate_data.get("history", [])
        china_10y_now = rate_data.get("china", {}).get("10年")
        if china_10y_now is None:
            return json.dumps({
                "status": "error",
                "message": "缺少中国10年期国债收益率数据",
            }, ensure_ascii=False, indent=2, default=str)

        # 找大约90天前的10Y收益率
        china_10y_3m_ago = None
        if history:
            target_dt = datetime.datetime.strptime(rate_data["date"], "%Y-%m-%d") - datetime.timedelta(days=90)
            for hrec in history:
                hrec_date = datetime.datetime.strptime(hrec["date"], "%Y-%m-%d")
                if hrec_date >= target_dt:
                    china_10y_3m_ago = hrec.get("china_10年")
                    break
            if china_10y_3m_ago is None and len(history) > 0:
                china_10y_3m_ago = history[0].get("china_10年")

        if china_10y_3m_ago is not None:
            yield_change_3m = round(china_10y_now - china_10y_3m_ago, 4)
        else:
            yield_change_3m = 0.0

        # 5. 美林时钟定位
        clock = _compute_merrill_lynch_clock(market_return_3m, yield_change_3m)

        # 6. 构建结果
        today = datetime.date.today()
        payload = {
            "status": "ok",
            "analysis_date": today.isoformat(),
            "data_source": (
                "沪深300收益率来自 akshare.stock_zh_index_daily('sh000300')，"
                "国债收益率来自 akshare.bond_zh_us_rate()"
            ),
            "cycle_position": {
                "quadrant": clock["quadrant"],
                "recommended_asset_class": clock["recommended_asset_class"],
                "signal_description": clock["signal_description"],
            },
            "gdp_proxy": {
                "label": "增长代理指标 - 沪深300近3个月收益率",
                "value_pct": market_return_3m,
                "direction": "高增长" if market_return_3m > 5 else ("低增长" if market_return_3m < -5 else "中性"),
                "threshold_note": ">5%为高增长，<-5%为低增长",
            },
            "inflation_proxy": {
                "label": "通胀代理指标 - 中国10Y国债收益率近3个月变化",
                "value_change": yield_change_3m,
                "direction": "上升" if yield_change_3m > 0.2 else ("下降" if yield_change_3m < -0.2 else "平稳"),
                "threshold_note": ">0.2%为通胀上升，<-0.2%为通胀下降",
            },
            "current_data": {
                "csi300_latest_close": csi300["latest_close"],
                "csi300_latest_date": csi300["latest_date"],
                "china_10y_yield": china_10y_now,
                "china_10y_3m_ago": china_10y_3m_ago,
                "us_10y_yield": rate_data.get("us", {}).get("10年"),
                "cn_us_spread_10y": (
                    round(china_10y_now - rate_data["us"]["10年"], 4)
                    if rate_data.get("us", {}).get("10年") is not None
                    else None
                ),
            },
            "data_quality": {
                "has_csi300_data": len(records) > 1,
                "has_yield_history": len(history) > 1,
                "yield_history_days": len(history),
                "note": (
                    "本工具采用简化美林时钟模型，以沪深300收益率代理经济增长方向、"
                    "10Y国债收益率变化代理通胀方向。实际周期判断需结合CPI、GDP、PMI等正式宏观指标。"
                ),
            },
        }

        return json.dumps(payload, ensure_ascii=False, indent=2, default=str)

    except Exception as exc:
        logger.error("经济周期定位失败: %s", exc, exc_info=True)
        return json.dumps({"status": "error", "message": str(exc)}, ensure_ascii=False, indent=2, default=str)


@tool
@register_tool(
    tool_id="get_monetary_environment",
    name="货币环境分析",
    description=(
        "实时分析当前货币/利率环境，基于中国和美国10年期国债收益率数据，"
        "包括收益率水平评估（低/中/高）、近1个月和3个月趋势方向、"
        "中美利差对比、以及货币政策立场判断（宽松/中性/紧缩）。"
    ),
    category="fundamentals",
    is_online=True,
    auto_register=True,
    timeout_tier="light",
    capability_tags=["macro", "monetary_policy", "interest_rate"],
    tool_role_hint="specialized",
    output_shape="structured_json",
    preferred_for=["货币环境评估", "利率走势分析", "中美利差查询"],
    when_to_use=(
        "当用户询问当前货币政策是松是紧、利率处于什么水平、"
        "中美利差走势、国债收益率趋势时使用。"
    ),
    when_not_to_use=(
        "不适合查询具体LPR/MLF操作利率（需要央行官方数据）；"
        "不适合查询存款准备金率等货币政策工具；"
        "不适合查询历史长时间序列的收益率数据。"
    ),
    returns=(
        "返回 JSON 字符串，包含 interest_rate_environment（利率水平/趋势评估）、"
        "china_10y_yield（中国10Y收益率及变化）、us_10y_yield（美国10Y收益率及变化）、"
        "spread_trend（中美利差趋势）、monetary_stance（货币政策立场判断）、"
        "available_data_sources（数据来源说明）等字段。"
    ),
    example="get_monetary_environment()",
    related_tools=["get_yield_curve_analysis", "get_economic_cycle_position", "get_macro_dashboard"],
)
def get_monetary_environment() -> str:
    """获取货币环境分析。

    通过 AKShare 获取中美国债收益率数据，分析利率水平、趋势、
    利差和政策立场。

    Returns:
        str: JSON 字符串，字段说明——
            status: 状态: "ok" | "error"
            analysis_date: 分析日期（YYYY-MM-DD）
            data_source: 数据来源说明
            interest_rate_environment: dict 利率环境——
                — china_10y_level: 利率水平: "低位" | "中性" | "高位" | "未知"
                — china_10y_level_detail: 水平详细说明
                — trend_1m: dict 近1个月趋势——
                    — change_bps: 变化（基点）
                    — direction: 方向: "上升" | "下降" | "平稳" | "未知"
                — trend_3m: dict 近3个月趋势（结构同 trend_1m）
            china_10y_yield: dict 中国10年期收益率——
                — current: 当前值
                — 1m_ago: 1个月前
                — 3m_ago: 3个月前
            us_10y_yield: dict 美国10年期收益率——
                — current: 当前值
            spread_trend: dict 中美利差趋势——
                — cn_us_10y_spread: 中美10年期利差
                — note: 说明文本
            monetary_stance: dict 货币政策立场——
                — stance: 立场: "宽松" | "中性" | "紧缩" | "未知"
                — description: 立场描述
                — basis: 判断依据
            available_data_sources: dict 可用数据源——
                — current_data: 当前数据源
                — not_included: list[str] 未包含的数据源列表
            data_quality: dict 数据质量——
                — has_full_history: 是否有完整历史
                — has_china_10y: 是否有中国10Y数据
                — has_us_10y: 是否有美国10Y数据
                — history_points: 历史数据点数
            message: 错误信息（仅 status="error" 时存在）
    """
    try:
        rate_data = _fetch_zh_us_rate()
        if "status" in rate_data and rate_data["status"] == "error":
            return json.dumps({
                "status": "error",
                "message": f"收益率数据获取失败: {rate_data.get('message')}",
            }, ensure_ascii=False, indent=2, default=str)

        today = datetime.date.today()
        china_10y = rate_data.get("china", {}).get("10年")
        us_10y = rate_data.get("us", {}).get("10年")
        history = rate_data.get("history", [])

        # 利率水平判断（中国10Y历史参考：<2.5%较低，2.5%-3.5%中性，>3.5%较高）
        if china_10y is not None:
            if china_10y < 2.5:
                rate_level = "低位"
                rate_level_note = "中国10Y国债收益率低于2.5%，处于历史低位区间"
            elif china_10y > 3.5:
                rate_level = "高位"
                rate_level_note = "中国10Y国债收益率高于3.5%，处于历史高位区间"
            else:
                rate_level = "中性"
                rate_level_note = "中国10Y国债收益率在2.5%-3.5%之间，处于中性区间"
        else:
            rate_level = "未知"
            rate_level_note = "缺少中国10Y国债收益率数据"

        # 趋势计算（近1个月和近3个月）
        trend_1m = None
        trend_3m = None
        china_10y_1m_ago = None
        china_10y_3m_ago = None

        if history and china_10y is not None:
            current_date = datetime.datetime.strptime(rate_data["date"], "%Y-%m-%d")
            target_1m = current_date - datetime.timedelta(days=30)
            target_3m = current_date - datetime.timedelta(days=90)

            for hrec in history:
                hrec_date = datetime.datetime.strptime(hrec["date"], "%Y-%m-%d")
                if china_10y_1m_ago is None and hrec_date >= target_1m:
                    china_10y_1m_ago = hrec.get("china_10年")
                if china_10y_3m_ago is None and hrec_date >= target_3m:
                    china_10y_3m_ago = hrec.get("china_10年")

            if china_10y_1m_ago is None and len(history) > 0:
                china_10y_1m_ago = history[0].get("china_10年")
            if china_10y_3m_ago is None and len(history) > 0:
                china_10y_3m_ago = history[0].get("china_10年")

        if china_10y is not None and china_10y_1m_ago is not None:
            trend_1m = round(china_10y - china_10y_1m_ago, 4)
        if china_10y is not None and china_10y_3m_ago is not None:
            trend_3m = round(china_10y - china_10y_3m_ago, 4)

        def trend_label(chg):
            if chg is None:
                return "未知"
            if chg > 0.1:
                return "上升"
            if chg < -0.1:
                return "下降"
            return "平稳"

        # 中美利差
        cn_us_spread = None
        if china_10y is not None and us_10y is not None:
            cn_us_spread = round(china_10y - us_10y, 4)

        # 货币政策立场综合判断
        if china_10y is not None:
            if china_10y < 2.0 or (trend_3m is not None and trend_3m < -0.3):
                monetary_stance = "宽松"
                stance_desc = "利率处于低位且持续下行，货币政策偏宽松"
            elif china_10y > 3.5 or (trend_3m is not None and trend_3m > 0.3):
                monetary_stance = "紧缩"
                stance_desc = "利率处于高位且持续上行，货币政策偏紧缩"
            else:
                monetary_stance = "中性"
                stance_desc = "利率处于中等水平，波动幅度不大，货币政策中性"
        else:
            monetary_stance = "未知"
            stance_desc = "数据不足无法判断"

        payload = {
            "status": "ok",
            "analysis_date": today.isoformat(),
            "data_source": "akshare.bond_zh_us_rate()",
            "interest_rate_environment": {
                "china_10y_level": rate_level,
                "china_10y_level_detail": rate_level_note,
                "trend_1m": {
                    "change_bps": round(trend_1m * 100, 2) if trend_1m is not None else None,
                    "direction": trend_label(trend_1m),
                },
                "trend_3m": {
                    "change_bps": round(trend_3m * 100, 2) if trend_3m is not None else None,
                    "direction": trend_label(trend_3m),
                },
            },
            "china_10y_yield": {
                "current": china_10y,
                "1m_ago": china_10y_1m_ago,
                "3m_ago": china_10y_3m_ago,
            },
            "us_10y_yield": {
                "current": us_10y,
            },
            "spread_trend": {
                "cn_us_10y_spread": cn_us_spread,
                "note": (
                    "正值表示中国收益率高于美国，负值表示中国收益率低于美国"
                    if cn_us_spread is not None else "数据不足"
                ),
            },
            "monetary_stance": {
                "stance": monetary_stance,
                "description": stance_desc,
                "basis": (
                    "基于10Y国债收益率的绝对水平和近3个月趋势进行判断，"
                    "实际货币政策立场需结合央行公开市场操作、LPR、MLF利率等综合评估"
                ),
            },
            "available_data_sources": {
                "current_data": "akshare.bond_zh_us_rate()",
                "not_included": [
                    "LPR（贷款市场报价利率）- 需从央行官网或东方财富获取",
                    "MLF（中期借贷便利）利率 - 需从央行官网获取",
                    "存款准备金率 - 需从央行官网获取",
                    "SHIBOR - 可通过 akshare 获取",
                ],
            },
            "data_quality": {
                "has_full_history": len(history) > 1,
                "has_china_10y": china_10y is not None,
                "has_us_10y": us_10y is not None,
                "history_points": len(history),
            },
        }

        return json.dumps(payload, ensure_ascii=False, indent=2, default=str)

    except Exception as exc:
        logger.error("货币环境分析失败: %s", exc, exc_info=True)
        return json.dumps({"status": "error", "message": str(exc)}, ensure_ascii=False, indent=2, default=str)


def _get_industry_sector_snapshot() -> dict:
    """从 stock_basic_info 获取各行业的估值快照。"""
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

    # 按行业分组
    industry_groups: Dict[str, Dict[str, Any]] = {}
    all_pe: List[float] = []
    all_pb: List[float] = []

    for stock in all_stocks:
        if not stock.get("symbol"):
            continue
        industry = (stock.get("industry") or "未知").strip()

        pe = _safe_float(stock.get("pe_ttm"))
        if pe is not None and 0 < pe < 1000:
            all_pe.append(pe)

        pb_raw = _safe_float(stock.get("pb") or stock.get("pb_mrq"))
        if pb_raw is not None and 0 < pb_raw < 100:
            all_pb.append(pb_raw)

        if industry not in industry_groups:
            industry_groups[industry] = {"count": 0, "pe_list": [], "pb_list": [], "total_mv": 0.0}
        industry_groups[industry]["count"] += 1
        if pe is not None and 0 < pe < 1000:
            industry_groups[industry]["pe_list"].append(pe)
        if pb_raw is not None and 0 < pb_raw < 100:
            industry_groups[industry]["pb_list"].append(pb_raw)
        mv = _safe_float(stock.get("total_mv"))
        if mv is not None:
            industry_groups[industry]["total_mv"] += mv

    # 全市场中位数
    market_pe_median = round(median(all_pe), 2) if all_pe else None
    market_pb_median = round(median(all_pb), 2) if all_pb else None

    # 计算每个行业的相对强度
    sector_results = []
    for industry, data in industry_groups.items():
        pe_med = round(median(data["pe_list"]), 2) if data["pe_list"] else None
        pb_med = round(median(data["pb_list"]), 2) if data["pb_list"] else None

        # 相对强度：PE比市场中位数越低越"价值"，越高越"成长"
        relative_strength = 0.0
        if pe_med is not None and market_pe_median is not None and market_pe_median > 0:
            # 负值表示相对低估（价值型），正值表示相对高估（成长型）
            relative_strength = round((market_pe_median - pe_med) / market_pe_median, 4)

        sector_results.append({
            "industry": industry,
            "stock_count": data["count"],
            "pe_median": pe_med,
            "pb_median": pb_med,
            "total_mv_billion": round(data["total_mv"], 2),
            "relative_strength": relative_strength,
            "relative_valuation": (
                "价值" if relative_strength > 0.2
                else ("成长" if relative_strength < -0.2 else "中性")
            ),
        })

    # 按相对强度排序（价值型在前）
    sector_results.sort(key=lambda x: x["relative_strength"], reverse=True)

    return {
        "market_pe_median": market_pe_median,
        "market_pb_median": market_pb_median,
        "total_industries": len(sector_results),
        "total_stocks_tracked": len(all_stocks),
        "sectors": sector_results,
    }


@tool
@register_tool(
    tool_id="get_sector_rotation_signals",
    name="行业轮动信号",
    description=(
        "基于本地数据库 stock_basic_info 的行业估值数据和实时宏观周期信号，"
        "分析各行业的相对估值强度（PE/PB vs 市场中位数），"
        "识别当前行业轮动阶段（价值领涨/成长领涨/防御轮动/均衡），"
        "并给出防御型、周期型和成长型板块的排名建议。"
    ),
    category="fundamentals",
    is_online=True,
    auto_register=True,
    timeout_tier="light",
    capability_tags=["macro", "sector_rotation", "industry_analysis"],
    tool_role_hint="specialized",
    output_shape="structured_json",
    preferred_for=["行业轮动分析", "板块排名查询", "行业配置建议"],
    when_to_use=(
        "当用户询问当前哪些行业板块表现好、行业轮动处于哪个阶段、"
        "应该配置周期型还是防御型板块、行业估值排名时使用。"
    ),
    when_not_to_use=(
        "不适合查询具体个股的估值或行情（请使用 get_value_factor_bundle_tool 或 get_stock_fundamentals_unified）。"
        "不适合查询板块指数的实时涨跌幅（请使用 get_sector_daily）；"
        "不适合查询板块成分股列表（请使用 get_sector_constituents）。"
    ),
    returns=(
        "返回 JSON 字符串，包含 current_cycle_position_data（当前周期数据）、"
        "sector_ranking（按相对强度排序的行业列表）、rotation_phase（轮动阶段判断）、"
        "top_defensive（推荐防御型板块）、top_cyclical（推荐周期型板块）、"
        "data_quality（数据质量说明）等字段。"
    ),
    example="get_sector_rotation_signals()",
    related_tools=["get_economic_cycle_position", "get_monetary_environment", "get_macro_dashboard"],
)
def get_sector_rotation_signals() -> str:
    """获取行业轮动信号分析。

    结合本地行业估值数据和实时宏观周期信号，判断行业轮动阶段
    并给出各行业的相对强度排名。

    Returns:
        str: JSON 字符串，字段说明——
            status: 状态: "ok" | "error"
            analysis_date: 分析日期（YYYY-MM-DD）
            data_source: 数据来源说明
            current_cycle_position_data: dict 当前周期数据（实时数据不可用时包含 cycle_phase="未知（实时数据不可用）"）——
                — market_return_3m: 沪深300近3个月收益率
                — china_10y_yield: 中国10年期收益率
                — cycle_phase: 周期阶段: "复苏" | "过热" | "滞涨" | "衰退" | "过渡" | "未知" | "未知（实时数据不可用）"
            rotation_phase: dict 轮动阶段——
                — phase: 阶段: "成长领涨" | "周期领涨" | "防御轮动" | "价值领涨" | "均衡轮动"
                — description: 阶段描述
                — methodology: 方法论说明
            sector_ranking: list[dict] 行业排名（前30），元素结构——
                — industry: 行业名
                — stock_count: 股票数量
                — pe_median: PE中位数
                — pb_median: PB中位数
                — total_mv_billion: 总市值（亿元）
                — relative_strength: 相对强度
                — relative_valuation: 相对估值: "价值" | "成长" | "中性"
            market_valuation_context: dict 市场估值上下文——
                — market_pe_median: 市场PE中位数
                — market_pb_median: 市场PB中位数
                — total_industries: 行业总数
                — total_stocks_tracked: 跟踪的股票总数
            top_defensive: list[dict] 推荐防御型板块（结构同 sector_ranking 元素）
            top_cyclical: list[dict] 推荐周期型板块（结构同 sector_ranking 元素）
            data_quality: dict 数据质量——
                — industry_count: 行业数
                — defensive_found: 找到的防御型板块数
                — cyclical_found: 找到的周期型板块数
                — cycle_data_available: 是否有实时周期数据
                — note: 说明文本
            message: 错误信息（仅 status="error" 时存在）
    """
    try:
        today = datetime.date.today()

        # 1. 获取行业估值快照
        snapshot = _get_industry_sector_snapshot()
        sectors = snapshot.get("sectors", [])

        # 2. 尝试获取实时周期信号（非阻塞，失败不影响行业数据）
        cycle_info = None
        try:
            import akshare as ak

            rate_df = ak.bond_zh_us_rate()
            rate_df["日期"] = pd.to_datetime(rate_df["日期"])
            latest_rate = rate_df.sort_values("日期").iloc[-1]
            china_10y = _safe_float(latest_rate.get("中国国债收益率10年"))

            # 沪深300近3个月收益率
            idx_df = ak.stock_zh_index_daily("sh000300")
            idx_df["date"] = pd.to_datetime(idx_df["date"])
            idx_df = idx_df.sort_values("date")
            if len(idx_df) >= 2:
                latest_close = float(idx_df["close"].iloc[-1])
                three_m_ago = float(idx_df["close"].iloc[0])
                mkt_return = round((latest_close - three_m_ago) / three_m_ago * 100, 2)
            else:
                mkt_return = None

            # 简单周期判断
            if mkt_return is not None and china_10y is not None:
                if mkt_return > 5:
                    if china_10y > 3.0:
                        cycle_phase = "过热"
                    else:
                        cycle_phase = "复苏"
                elif mkt_return < -5:
                    if china_10y > 3.0:
                        cycle_phase = "滞涨"
                    else:
                        cycle_phase = "衰退"
                else:
                    cycle_phase = "过渡"
            else:
                cycle_phase = "未知"

            cycle_info = {
                "market_return_3m": mkt_return,
                "china_10y_yield": china_10y,
                "cycle_phase": cycle_phase,
            }
        except Exception as e:
            logger.debug("周期数据获取失败，仅使用行业估值数据: %s", e)
            cycle_info = {"cycle_phase": "未知（实时数据不可用）"}

        # 3. 判断轮动阶段
        # 基于行业估值分布特征识别轮动阶段
        top_value = [s for s in sectors[:10] if s.get("relative_valuation") == "价值"]
        top_growth = [s for s in sectors[-10:] if s.get("relative_valuation") == "成长"]
        defensive_industries = {"银行", "公用事业", "食品饮料", "医药生物", "交通运输", "保险"}
        cyclical_industries = {"有色金属", "钢铁", "煤炭", "基础化工", "建筑材料", "房地产", "机械设备"}

        value_score = len(top_value)  # 价值型板块数量
        growth_score = len(top_growth)  # 成长型板块数量

        if cycle_info and isinstance(cycle_info, dict):
            cycle_phase = cycle_info.get("cycle_phase", "")
            if cycle_phase == "复苏":
                rotation_phase = "成长领涨"
                rotation_desc = "经济复苏期，成长型和高贝塔板块通常表现领先"
            elif cycle_phase == "过热":
                rotation_phase = "周期领涨"
                rotation_desc = "经济过热期，周期性板块（资源、原材料）通常表现领先"
            elif cycle_phase == "滞涨":
                rotation_phase = "防御轮动"
                rotation_desc = "滞涨期，防御型板块（公用事业、医药、必需消费）通常表现领先"
            elif cycle_phase == "衰退":
                rotation_phase = "防御轮动"
                rotation_desc = "衰退期，防御型板块和债券相关资产通常表现领先"
            else:
                # 基于估值数据推断
                if value_score > growth_score + 3:
                    rotation_phase = "价值领涨"
                    rotation_desc = "价值型板块相对强度突出，市场偏向低估值防御"
                elif growth_score > value_score + 3:
                    rotation_phase = "成长领涨"
                    rotation_desc = "成长型板块相对强度突出，市场偏好高增长"
                else:
                    rotation_phase = "均衡轮动"
                    rotation_desc = "价值与成长板块相对强度接近，市场无明显偏好"
        else:
            if value_score > growth_score + 3:
                rotation_phase = "价值领涨"
                rotation_desc = "价值型板块相对强度突出，市场偏向低估值防御"
            elif growth_score > value_score + 3:
                rotation_phase = "成长领涨"
                rotation_desc = "成长型板块相对强度突出，市场偏好高增长"
            else:
                rotation_phase = "均衡轮动"
                rotation_desc = "价值与成长板块相对强度接近，市场无明显偏好"

        # 4. 识别防御型和周期型板块推荐
        def _filter_by_industry_list(sectors_list: List[dict], industry_set: set) -> List[dict]:
            return [
                s for s in sectors_list
                if s["industry"] in industry_set and s["relative_strength"] is not None
            ]

        top_defensive = sorted(
            _filter_by_industry_list(sectors, defensive_industries),
            key=lambda x: x["relative_strength"],
            reverse=True,
        )[:5]

        top_cyclical = sorted(
            _filter_by_industry_list(sectors, cyclical_industries),
            key=lambda x: x["relative_strength"],
            reverse=True,
        )[:5]

        # 5. 构建返回结果（只返回前30个行业以控制输出大小）
        payload = {
            "status": "ok",
            "analysis_date": today.isoformat(),
            "data_source": (
                "行业估值数据来自本地数据库 stock_basic_info 集合，"
                "周期信号来自 akshare.bond_zh_us_rate() / stock_zh_index_daily()"
            ),
            "current_cycle_position_data": cycle_info,
            "rotation_phase": {
                "phase": rotation_phase,
                "description": rotation_desc,
                "methodology": (
                    "基于宏观周期阶段（如有）和行业相对估值分布综合判断。"
                    "防御型板块参考：银行、公用事业、食品饮料、医药生物、交通运输、保险；"
                    "周期型板块参考：有色金属、钢铁、煤炭、基础化工、建筑材料、房地产、机械设备。"
                ),
            },
            "sector_ranking": sectors[:30],  # 前30个行业
            "market_valuation_context": {
                "market_pe_median": snapshot.get("market_pe_median"),
                "market_pb_median": snapshot.get("market_pb_median"),
                "total_industries": snapshot.get("total_industries"),
                "total_stocks_tracked": snapshot.get("total_stocks_tracked"),
            },
            "top_defensive": top_defensive,
            "top_cyclical": top_cyclical,
            "data_quality": {
                "industry_count": len(sectors),
                "defensive_found": len(top_defensive),
                "cyclical_found": len(top_cyclical),
                "cycle_data_available": isinstance(cycle_info, dict) and cycle_info.get("cycle_phase") != "未知（实时数据不可用）",
                "note": (
                    "行业排名基于 PE/PB 相对市场中位数的偏离程度，"
                    "仅反映估值层面的相对强度信号，不构成投资建议。"
                    "实际轮动还需结合资金流向、政策催化、景气度等综合判断。"
                ),
            },
        }

        return json.dumps(payload, ensure_ascii=False, indent=2, default=str)

    except Exception as exc:
        logger.error("行业轮动信号分析失败: %s", exc, exc_info=True)
        return json.dumps({"status": "error", "message": str(exc)}, ensure_ascii=False, indent=2, default=str)


__all__ = [
    "get_economic_cycle_position",
    "get_monetary_environment",
    "get_sector_rotation_signals",
]