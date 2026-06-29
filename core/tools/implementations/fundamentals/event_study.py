"""事件研究法工具。

对指定股票在事件日前后的异常收益进行统计分析。
使用均值调整收益模型（Mean-Adjusted Return Model）计算异常收益。
"""

import datetime
import json
import logging
from statistics import mean, stdev
from typing import Annotated, Any, Dict, List, Optional

from langchain_core.tools import tool

from core.skill_runtime.data_access import get_stock_daily_quotes
from core.tools.base import register_tool

logger = logging.getLogger(__name__)


def _to_float(value: Any) -> Optional[float]:
    if value is None:
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
        numeric = float(str(value).strip())
        if numeric != numeric:
            return None
        return numeric
    except (TypeError, ValueError):
        return None


def _parse_date(date_str: str) -> str:
    """标准化日期为 YYYY-MM-DD 格式。"""
    cleaned = "".join(ch for ch in date_str if ch.isdigit())[:8]
    if len(cleaned) == 8:
        return f"{cleaned[:4]}-{cleaned[4:6]}-{cleaned[6:]}"
    return date_str


def _to_dash_date(date_str: str) -> str:
    """将 YYYYMMDD 转为 YYYY-MM-DD，保持已有格式不变。"""
    if "-" in date_str:
        return date_str
    cleaned = "".join(ch for ch in date_str if ch.isdigit())[:8]
    if len(cleaned) == 8:
        return f"{cleaned[:4]}-{cleaned[4:6]}-{cleaned[6:]}"
    return date_str


@tool
@register_tool(
    tool_id="get_event_study",
    name="事件研究法",
    description=(
        "对指定股票在事件日前后的异常收益进行统计分析。"
        "使用均值调整收益模型（Mean-Adjusted Return Model）计算异常收益(AR)和累计异常收益(CAR)，"
        "并计算 t 统计量检验显著性。"
    ),
    category="fundamentals",
    is_online=False,
    auto_register=True,
    timeout_tier="medium",
    capability_tags=["event", "event_study", "quantitative"],
    tool_role_hint="specialized",
    output_shape="structured_json",
    preferred_for=["事件驱动分析", "公告效应研究", "市场反应量化评估"],
    when_to_use=(
        "当需要定量分析某个事件（如财报发布、重大公告、监管处罚、高管变更等）"
        "对股票价格的影响时使用。适合事件驱动策略研究。"
    ),
    when_not_to_use=(
        "不适合获取股票历史行情本身（请用 get_stock_daily_quotes）；"
        "不适合基本面因子分析。如果只需事件前后涨跌幅，可直接用行情查询。"
    ),
    returns=(
        "返回 JSON 字符串，包含 symbol、event_date、method、"
        "estimation（估计期统计量）、event_window（每日 AR/CAR 明细）、"
        "summary（总 CAR、t 统计量、显著性判断）、data_quality（数据质量说明）。"
    ),
    example="get_event_study(symbol='600519', event_date='20251201', window_before=30, window_after=30, estimation_window=120)",
    related_tools=[
        "get_stock_daily_quotes",
        "get_income_analysis",
        "get_stock_news",
    ],
)
def get_event_study(
    symbol: Annotated[str, "A 股股票代码，6 位数字，如 600519"],
    event_date: Annotated[str, "事件日期，格式为 YYYYMMDD 或 YYYY-MM-DD"],
    window_before: Annotated[int, "事件窗口向前天数（事件前），默认 30"] = 30,
    window_after: Annotated[int, "事件窗口向后天数（事件后），默认 30"] = 30,
    estimation_window: Annotated[int, "估计期窗口天数，默认 120"] = 120,
) -> str:
    """事件研究法分析工具。

    使用均值调整收益模型（Mean-Adjusted Return Model）计算：
    - 估计期：用于估计正常收益
    - 事件窗口：计算异常收益(AR)和累计异常收益(CAR)
    - 显著性检验：t 统计量

    Args:
        symbol: A 股股票代码
        event_date: 事件日期
        window_before: 事件窗口向前天数
        window_after: 事件窗口向后天数
        estimation_window: 估计期窗口天数

    Returns:
        JSON 字符串格式的事件研究结果
    """
    try:
        symbol = str(symbol).strip().zfill(6)
        event = _parse_date(event_date)

        event_dt = datetime.datetime.strptime(event, "%Y-%m-%d")

        # 计算日期范围
        estimation_start = event_dt - datetime.timedelta(days=estimation_window + window_before + 10)
        event_end = event_dt + datetime.timedelta(days=window_after + 10)

        start_str = estimation_start.strftime("%Y%m%d")
        end_str = event_end.strftime("%Y%m%d")

        # 获取日线数据
        quotes = get_stock_daily_quotes(symbol, start_str, end_str, period="daily", limit=5000)

        if not quotes:
            return json.dumps(
                {"status": "error", "message": f"未获取到 {symbol} 的日线数据"},
                ensure_ascii=False,
                default=str,
            )

        # 计算每日收益率
        daily_returns: List[Dict[str, Any]] = []
        for q in quotes:
            trade_date = q.get("trade_date", "")
            trade_date_str = _to_dash_date(str(trade_date)) if trade_date else ""

            close = _to_float(q.get("close"))
            pre_close = _to_float(q.get("pre_close"))

            if close is not None and pre_close is not None and pre_close > 0:
                daily_return = (close - pre_close) / pre_close
            else:
                continue

            daily_returns.append({
                "date": trade_date_str,
                "return": daily_return,
            })

        if len(daily_returns) < estimation_window // 2:
            return json.dumps(
                {
                    "status": "error",
                    "message": f"日线数据不足，仅获取到 {len(daily_returns)} 条有效交易记录，"
                    f"估计期需要至少 {estimation_window // 2} 条",
                },
                ensure_ascii=False,
                default=str,
            )

        # 按日期排序
        daily_returns.sort(key=lambda x: x["date"])

        # 将日期转换为 datetime 用于比较
        def _date_key(d: str) -> datetime.datetime:
            try:
                return datetime.datetime.strptime(d, "%Y-%m-%d")
            except ValueError:
                return datetime.datetime.min

        event_dt_compare = _date_key(event)

        # 分离估计期和事件窗口
        estimation_returns: List[float] = []
        event_window_returns: List[Dict[str, Any]] = []

        for item in daily_returns:
            item_date = _date_key(item["date"])
            days_diff = (item_date - event_dt_compare).days

            # 估计期：[event_date - estimation_window - window_before, event_date - window_before)
            est_start = -estimation_window - window_before
            est_end = -window_before

            if est_start <= days_diff < est_end:
                estimation_returns.append(item["return"])

            # 事件窗口：[event_date - window_before, event_date + window_after]
            if -window_before <= days_diff <= window_after:
                event_window_returns.append({
                    "date": item["date"],
                    "days_from_event": days_diff,
                    "actual_return": item["return"],
                })

        if len(estimation_returns) < 10:
            return json.dumps(
                {
                    "status": "error",
                    "message": f"估计期内有效收益数据不足，仅 {len(estimation_returns)} 条（需至少 10 条）",
                },
                ensure_ascii=False,
                default=str,
            )

        # 均值调整收益模型
        mean_return = mean(estimation_returns)
        std_return = stdev(estimation_returns) if len(estimation_returns) > 1 else 0.0

        # 计算事件窗口内的 AR 和 CAR
        ar_values: List[float] = []
        car = 0.0
        event_results: List[Dict[str, Any]] = []

        for item in event_window_returns:
            ar = item["actual_return"] - mean_return
            ar_values.append(ar)
            car += ar

            event_results.append({
                "date": item["date"],
                "days_from_event": item["days_from_event"],
                "actual_return": round(item["actual_return"], 6),
                "expected_return": round(mean_return, 6),
                "ar": round(ar, 6),
                "car": round(car, 6),
            })

        # t 统计量检验：H0: CAR = 0
        n = len(ar_values)
        if n > 1 and std_return > 0:
            # 使用估计期的标准差近似
            t_stat = car / (std_return * (n ** 0.5)) if n > 0 else 0.0
        else:
            t_stat = 0.0

        # 临界值近似（双尾检验，5% 显著性水平）
        significant = abs(t_stat) > 1.96

        summary = {
            "car_total": round(car, 6),
            "t_stat": round(t_stat, 4),
            "significant": significant,
            "interpretation": (
                "事件在统计上产生显著异常收益"
                if significant
                else "事件未产生显著异常收益"
            ),
        }

        payload = {
            "symbol": symbol,
            "event_date": event,
            "method": "mean_adjusted_return",
            "estimation": {
                "window_days": len(estimation_returns),
                "mean_return": round(mean_return, 6),
                "std": round(std_return, 6),
            },
            "event_window": event_results,
            "summary": summary,
            "data_quality": {
                "total_quotes_fetched": len(quotes),
                "valid_return_days": len(daily_returns),
                "estimation_days_used": len(estimation_returns),
                "event_window_days_used": len(event_results),
            },
        }

        return json.dumps(payload, ensure_ascii=False, indent=2, default=str)

    except Exception as exc:
        logger.error("事件研究法分析失败: %s", exc, exc_info=True)
        return json.dumps({"status": "error", "message": str(exc)}, ensure_ascii=False, indent=2, default=str)


__all__ = ["get_event_study"]
