"""
大盘/指数分析工具

提供指数走势分析、市场宽度分析等功能
这些工具用于 IndexAnalystV2 分析师
"""

import logging
from typing import Annotated
from langchain_core.tools import tool

from core.tools.base import register_tool
from core.tools.context import get_current_analysis_data_source

logger = logging.getLogger(__name__)


def _resolve_market_analysis_source() -> str:
    """获取当前大盘分析工具应使用的数据源。"""
    current_source = get_current_analysis_data_source()
    if current_source == "qmt":
        return "qmt"
    return "tushare"


def _is_tushare_available() -> bool:
    """检查 Tushare 数据源是否可用。"""
    try:
        from app.services.data_sources.tushare_adapter import TushareAdapter
        return TushareAdapter().is_available()
    except Exception:
        return False


def _is_qmt_available() -> bool:
    """检查 QMT 数据源是否可用。"""
    try:
        from app.services.data_sources.qmt_adapter import QMTAdapter
        return QMTAdapter().is_available()
    except Exception:
        return False


def _qmt_fallback_index_trend(trade_date: str, lookback_days: int = 60) -> str:
    """QMT 降级：获取主要指数趋势数据。"""
    try:
        from core.tools.qmt_market_tools import get_market_overview_qmt_sync
        report = get_market_overview_qmt_sync(trade_date, lookback_days)
        # 从完整报告中提取指数趋势部分
        lines = report.split("\n")
        result_lines = ["📊 以下数据基于 QMT 行情口径（Tushare 不可用时的降级数据）", ""]
        capture = False
        for line in lines:
            if "主要指数趋势" in line:
                capture = True
            if capture:
                result_lines.append(line)
                if line.strip().startswith("##") and "主要指数趋势" not in line:
                    break
        captured = "\n".join(result_lines)
        return captured if len(captured) > 50 else report
    except Exception as e:
        return f"⚠️ Tushare 不可用，QMT 降级获取指数数据也失败: {e}"


def _qmt_fallback_market_breadth(trade_date: str) -> str:
    """QMT 降级：通过全市场快照代理涨跌家数。"""
    try:
        from core.tools.qmt_market_tools import get_market_overview_qmt_sync
        report = get_market_overview_qmt_sync(trade_date, 5)
        lines = report.split("\n")
        result_lines = ["📊 以下数据基于 QMT 快照代理指标（Tushare 不可用时的降级数据）", ""]
        capture = False
        for line in lines:
            if "市场快照代理" in line:
                capture = True
            if capture:
                result_lines.append(line)
                if line.strip().startswith("##") and "市场快照代理" not in line:
                    break
        captured = "\n".join(result_lines)
        return captured if len(captured) > 50 else report
    except Exception as e:
        return f"⚠️ Tushare 不可用，QMT 降级获取市场宽度也失败: {e}"


def _qmt_fallback_technical(trade_date: str, lookback_days: int = 60) -> str:
    """QMT 降级：通过指数K线计算技术指标。"""
    try:
        from app.services.data_sources.qmt_adapter import QMTAdapter
        from statistics import median as _median

        adapter = QMTAdapter()
        if not adapter.is_available():
            return "⚠️ Tushare 不可用，QMT 也不可用，无法获取技术指标数据。"

        index_codes = {
            "000001.SH": "上证指数",
            "399006.SZ": "创业板指",
            "000300.SH": "沪深300",
        }

        result_lines = [
            "📊 指数技术指标（基于 QMT K线计算，Tushare 不可用时的降级数据）",
            "",
        ]

        for code, name in index_codes.items():
            items = adapter.get_kline(code, period="day", limit=max(lookback_days, 60) + 5)
            if not items:
                result_lines.append(f"- {name}: 暂无数据")
                continue

            closes = []
            for item in items:
                c = item.get("close")
                if c is not None:
                    try:
                        closes.append(float(c))
                    except (TypeError, ValueError):
                        pass

            if len(closes) < 20:
                result_lines.append(f"- {name}: 数据不足")
                continue

            # 计算 MA
            ma5 = sum(closes[-5:]) / 5 if len(closes) >= 5 else None
            ma10 = sum(closes[-10:]) / 10 if len(closes) >= 10 else None
            ma20 = sum(closes[-20:]) / 20 if len(closes) >= 20 else None
            ma60 = sum(closes[-60:]) / 60 if len(closes) >= 60 else None

            # 计算 RSI(14)
            rsi = None
            if len(closes) >= 15:
                gains, losses = [], []
                for i in range(-14, 0):
                    diff = closes[i] - closes[i - 1]
                    gains.append(max(diff, 0))
                    losses.append(max(-diff, 0))
                avg_gain = sum(gains) / 14
                avg_loss = sum(losses) / 14
                if avg_loss > 0:
                    rs = avg_gain / avg_loss
                    rsi = 100 - (100 / (1 + rs))
                else:
                    rsi = 100

            # 趋势判断
            latest = closes[-1]
            trend = "数据不足"
            if ma5 and ma10 and ma20 and ma60:
                if latest > ma5 > ma20 > ma60:
                    trend = "多头排列"
                elif latest < ma5 < ma20 < ma60:
                    trend = "空头排列"
                else:
                    trend = "震荡整理"

            ma60_str = f"{ma60:.2f}" if ma60 else "-"
            rsi_str = f"{rsi:.1f}" if rsi else "-"
            result_lines.append(
                f"- {name}: 最新 {latest:.2f} | MA5={ma5:.2f} MA20={ma20:.2f} MA60={ma60_str} | "
                f"RSI(14)={rsi_str} | {trend}"
            )

        return "\n".join(result_lines)
    except Exception as e:
        return f"⚠️ Tushare 不可用，QMT 降级获取技术指标也失败: {e}"


def _tushare_unavailable_msg(dimensions: str) -> str:
    """Tushare 不可用且 QMT 无法替代时的统一提示。"""
    return (
        f"⚠️ 当前 Tushare 数据源不可用，{dimensions}数据仅 Tushare 提供，QMT 不支持此维度。"
        f"请优先参考 get_market_analysis 工具返回的 QMT 大盘分析数据。"
    )


@tool
@register_tool(
    tool_id="get_index_data",
    name="指数数据",
    description="获取主要指数数据（上证、深证、创业板等），分析大盘走势和趋势",
    category="market",
    is_online=True,
    auto_register=True
)
def get_index_data(
    trade_date: Annotated[str, "交易日期，格式：YYYY-MM-DD"],
    lookback_days: Annotated[int, "回看天数，默认60天"] = 60
) -> str:
    """
    获取主要指数数据和走势分析

    分析上证指数、深证成指、创业板指、沪深300、中证500等主要指数的走势，
    包括今日涨跌、5日/20日涨跌幅、均线位置和趋势判断。

    Args:
        trade_date: 交易日期（格式：YYYY-MM-DD）
        lookback_days: 回看天数，用于计算均线和趋势（默认60天）

    Returns:
        str: 指数走势分析报告
    """
    try:
        from core.tools.index_tools import get_index_trend_sync
        return get_index_trend_sync(trade_date, lookback_days)
    except Exception as e:
        logger.error(f"获取指数数据失败: {e}")
        # Tushare 失败时尝试 QMT 降级
        if _is_qmt_available():
            logger.info("Tushare 获取指数数据失败，尝试 QMT 降级")
            return _qmt_fallback_index_trend(trade_date, lookback_days)
        return f"❌ 获取指数数据失败: {e}"


@tool
@register_tool(
    tool_id="get_market_breadth",
    name="市场宽度",
    description="分析市场宽度（涨跌家数、涨停跌停等），评估市场整体情绪",
    category="market",
    is_online=True,
    auto_register=True
)
def get_market_breadth(
    trade_date: Annotated[str, "交易日期，格式：YYYY-MM-DD"]
) -> str:
    """
    分析市场宽度

    统计涨跌家数、涨停跌停数量、成交量分布等，评估市场整体参与度和情绪。

    Args:
        trade_date: 交易日期（格式：YYYY-MM-DD）

    Returns:
        str: 市场宽度分析报告
    """
    try:
        from core.tools.index_tools import get_market_breadth_sync
        return get_market_breadth_sync(trade_date)
    except Exception as e:
        logger.error(f"获取市场宽度失败: {e}")
        # Tushare 失败时尝试 QMT 降级
        if _is_qmt_available():
            logger.info("Tushare 获取市场宽度失败，尝试 QMT 降级")
            return _qmt_fallback_market_breadth(trade_date)
        return f"❌ 获取市场宽度失败: {e}"


@tool
@register_tool(
    tool_id="get_market_environment",
    name="市场环境",
    description="综合评估市场环境，包括波动、换手与市场规模等",
    category="market",
    is_online=True,
    auto_register=True
)
def get_market_environment(
    trade_date: Annotated[str, "交易日期，格式：YYYY-MM-DD"]
) -> str:
    """
    综合评估市场环境

    整合波动、换手和市场规模等多维度数据，给出市场环境综合评估。

    Args:
        trade_date: 交易日期（格式：YYYY-MM-DD）

    Returns:
        str: 市场环境综合评估报告
    """
    try:
        from core.tools.index_tools import get_market_environment_sync
        return get_market_environment_sync(trade_date)
    except Exception as e:
        logger.error(f"获取市场环境失败: {e}")
        # Tushare 失败时尝试 QMT 降级（返回 QMT 大盘概览作为替代）
        if _is_qmt_available():
            logger.info("Tushare 获取市场环境失败，尝试 QMT 降级")
            try:
                from core.tools.qmt_market_tools import get_market_overview_qmt_sync
                report = get_market_overview_qmt_sync(trade_date, 60)
                return f"📊 以下数据基于 QMT 行情口径（Tushare 不可用时的降级数据）\n\n{report}"
            except Exception as qmt_e:
                return f"❌ 获取市场环境失败: Tushare={e}, QMT降级={qmt_e}"
        return f"❌ 获取市场环境失败: {e}"


@tool
@register_tool(
    tool_id="identify_market_cycle",
    name="市场周期识别",
    description="识别当前市场所处的周期阶段（牛市、熊市、震荡等）",
    category="market",
    is_online=True,
    auto_register=True
)
def identify_market_cycle(
    trade_date: Annotated[str, "交易日期，格式：YYYY-MM-DD"]
) -> str:
    """
    识别市场周期

    基于技术指标和市场数据，识别当前市场所处的周期阶段。

    Args:
        trade_date: 交易日期（格式：YYYY-MM-DD）

    Returns:
        str: 市场周期分析报告
    """
    try:
        from core.tools.index_tools import identify_market_cycle_sync
        return identify_market_cycle_sync(trade_date)
    except Exception as e:
        logger.error(f"识别市场周期失败: {e}")
        # Tushare 失败时尝试 QMT 降级（基于指数趋势判断周期）
        if _is_qmt_available():
            logger.info("Tushare 识别市场周期失败，尝试 QMT 降级")
            try:
                from core.tools.qmt_market_tools import get_market_overview_qmt_sync
                report = get_market_overview_qmt_sync(trade_date, 60)
                return (
                    "📊 市场周期识别（基于 QMT 指数趋势代理，Tushare 不可用时的降级分析）\n\n"
                    "⚠️ 注意：此降级分析仅基于指数趋势和均线排列，不如 Tushare 版本全面。\n\n"
                    f"{report}"
                )
            except Exception as qmt_e:
                return f"❌ 识别市场周期失败: Tushare={e}, QMT降级={qmt_e}"
        return f"❌ 识别市场周期失败: {e}"


@tool
@register_tool(
    tool_id="get_market_overview",
    name="市场概览",
    description="获取整体市场环境概览，包括指数走势、涨跌统计、资金流向等综合数据",
    category="market",
    is_online=True,
    auto_register=True
)
def get_market_overview(
    trade_date: Annotated[str, "交易日期，格式：YYYY-MM-DD"]
) -> str:
    """
    获取整体市场概览

    综合多维度数据，提供市场整体环境概览，包括：
    - 主要指数走势
    - 涨跌家数统计
    - 资金流向情况
    - 市场情绪评估

    这是 get_market_environment 的别名，提供相同的综合市场分析。

    Args:
        trade_date: 交易日期（格式：YYYY-MM-DD）

    Returns:
        str: 市场概览分析报告
    """
    try:
        from core.tools.index_tools import get_market_environment_sync
        return get_market_environment_sync(trade_date)
    except Exception as e:
        logger.error(f"获取市场概览失败: {e}")
        # Tushare 失败时尝试 QMT 降级
        if _is_qmt_available():
            logger.info("Tushare 获取市场概览失败，尝试 QMT 降级")
            try:
                from core.tools.qmt_market_tools import get_market_overview_qmt_sync
                report = get_market_overview_qmt_sync(trade_date, 60)
                return f"📊 以下数据基于 QMT 行情口径（Tushare 不可用时的降级数据）\n\n{report}"
            except Exception as qmt_e:
                return f"❌ 获取市场概览失败: Tushare={e}, QMT降级={qmt_e}"
        return f"❌ 获取市场概览失败: {e}"


@tool
@register_tool(
    tool_id="get_market_analysis",
    name="统一大盘分析",
    description="根据当前分析数据源自动选择 QMT 或 Tushare 路径，返回统一的大盘分析结果。",
    category="market",
    is_online=True,
    auto_register=True
)
def get_market_analysis(
    trade_date: Annotated[str, "交易日期，格式：YYYY-MM-DD"],
    lookback_days: Annotated[int, "回看天数，默认60天"] = 60
) -> str:
    """统一的大盘分析工具，自动按当前数据源路由。"""
    source = _resolve_market_analysis_source()

    if source == "qmt":
        try:
            from core.tools.qmt_market_tools import get_market_overview_qmt_sync
            return get_market_overview_qmt_sync(trade_date, lookback_days)
        except Exception as e:
            logger.error(f"QMT 大盘分析失败: {e}")
            # QMT 失败时尝试 Tushare
            if _is_tushare_available():
                logger.info("QMT 大盘分析失败，尝试 Tushare 降级")
                try:
                    from core.tools.index_tools import get_market_environment_sync
                    return get_market_environment_sync(trade_date)
                except Exception as ts_e:
                    return f"❌ 大盘分析失败: QMT={e}, Tushare={ts_e}"
            return f"❌ QMT 大盘分析失败: {e}"

    sections = []
    tool_calls = [
        ("指数趋势", lambda: get_index_data.invoke({"trade_date": trade_date, "lookback_days": lookback_days})),
        ("市场宽度", lambda: get_market_breadth.invoke({"trade_date": trade_date})),
        ("市场环境", lambda: get_market_environment.invoke({"trade_date": trade_date})),
        ("市场周期", lambda: identify_market_cycle.invoke({"trade_date": trade_date})),
        ("北向资金", lambda: get_north_flow.invoke({"trade_date": trade_date, "lookback_days": min(lookback_days, 10)})),
        ("两融余额", lambda: get_margin_trading.invoke({"trade_date": trade_date, "lookback_days": min(lookback_days, 10)})),
        ("涨跌停统计", lambda: get_limit_stats.invoke({"trade_date": trade_date})),
        ("指数技术面", lambda: get_index_technical.invoke({"trade_date": trade_date, "lookback_days": lookback_days})),
    ]

    for title, producer in tool_calls:
        try:
            content = producer()
        except Exception as exc:
            logger.error(f"统一大盘分析组装失败 [{title}]: {exc}")
            content = f"❌ {title} 获取失败: {exc}"
        sections.append(f"## {title}\n{content}")

    return "\n\n".join(sections)


# ==================== 新增大盘分析工具 ====================

@tool
@register_tool(
    tool_id="get_north_flow",
    name="北向资金流向",
    description="获取沪深港通北向资金流向数据，分析外资动向",
    category="market",
    is_online=True,
    auto_register=True
)
def get_north_flow(
    trade_date: Annotated[str, "交易日期，格式：YYYY-MM-DD"],
    lookback_days: Annotated[int, "回看天数，默认10天"] = 10
) -> str:
    """
    获取北向资金流向分析

    分析沪股通、深股通资金流入流出情况，评估外资态度。

    Args:
        trade_date: 交易日期（格式：YYYY-MM-DD）
        lookback_days: 回看天数（默认10天）

    Returns:
        str: 北向资金流向分析报告
    """
    try:
        from core.tools.index_tools import get_north_flow_sync
        return get_north_flow_sync(trade_date, lookback_days)
    except Exception as e:
        logger.error(f"获取北向资金失败: {e}")
        if not _is_tushare_available():
            return _tushare_unavailable_msg("北向资金")
        return f"❌ 获取北向资金失败: {e}"


@tool
@register_tool(
    tool_id="get_margin_trading",
    name="两融余额",
    description="获取融资融券余额数据，描述余额水平并识别异常字段",
    category="market",
    is_online=True,
    auto_register=True
)
def get_margin_trading(
    trade_date: Annotated[str, "交易日期，格式：YYYY-MM-DD"],
    lookback_days: Annotated[int, "回看天数，默认10天"] = 10
) -> str:
    """
    获取两融余额分析

    描述融资融券余额水平，并识别变化字段中的异常或口径冲突。

    Args:
        trade_date: 交易日期（格式：YYYY-MM-DD）
        lookback_days: 回看天数（默认10天）

    Returns:
        str: 两融余额分析报告
    """
    try:
        from core.tools.index_tools import get_margin_trading_sync
        return get_margin_trading_sync(trade_date, lookback_days)
    except Exception as e:
        logger.error(f"获取两融余额失败: {e}")
        if not _is_tushare_available():
            return _tushare_unavailable_msg("两融余额")
        return f"❌ 获取两融余额失败: {e}"


@tool
@register_tool(
    tool_id="get_limit_stats",
    name="涨跌停统计",
    description="获取涨跌停家数和涨跌家数统计，描述涨跌分布事实",
    category="market",
    is_online=True,
    auto_register=True
)
def get_limit_stats(
    trade_date: Annotated[str, "交易日期，格式：YYYY-MM-DD"]
) -> str:
    """
    获取涨跌停和涨跌家数统计

    统计涨跌停家数、涨跌家数、涨跌幅分布，输出供上层模型归纳的事实数据。

    Args:
        trade_date: 交易日期（格式：YYYY-MM-DD）

    Returns:
        str: 涨跌停和涨跌家数分析报告
    """
    try:
        from core.tools.index_tools import get_limit_stats_sync
        return get_limit_stats_sync(trade_date)
    except Exception as e:
        logger.error(f"获取涨跌停统计失败: {e}")
        # Tushare 失败时尝试 QMT 降级
        if _is_qmt_available():
            logger.info("Tushare 获取涨跌停统计失败，尝试 QMT 降级")
            try:
                from core.tools.qmt_market_tools import get_limit_stats_qmt_sync
                return get_limit_stats_qmt_sync(trade_date)
            except Exception as qmt_e:
                return f"❌ 获取涨跌停统计失败: Tushare={e}, QMT降级={qmt_e}"
        if not _is_tushare_available():
            return _tushare_unavailable_msg("涨跌停统计")
        return f"❌ 获取涨跌停统计失败: {e}"


@tool
@register_tool(
    tool_id="get_index_technical",
    name="指数技术指标",
    description="获取指数技术指标（MACD、RSI、KDJ）及规则标签",
    category="market",
    is_online=True,
    auto_register=True
)
def get_index_technical(
    trade_date: Annotated[str, "交易日期，格式：YYYY-MM-DD"],
    lookback_days: Annotated[int, "回看天数，默认60天"] = 60
) -> str:
    """
    获取指数技术指标分析

    计算上证指数的MACD、RSI、KDJ等技术指标，返回指标数值与轻量规则标签。

    Args:
        trade_date: 交易日期（格式：YYYY-MM-DD）
        lookback_days: 回看天数（默认60天）

    Returns:
        str: 指数技术指标报告
    """
    try:
        from core.tools.index_tools import get_index_technical_sync
        return get_index_technical_sync(trade_date, lookback_days)
    except Exception as e:
        logger.error(f"获取指数技术指标失败: {e}")
        # Tushare 失败时尝试 QMT 降级
        if _is_qmt_available():
            logger.info("Tushare 获取技术指标失败，尝试 QMT 降级")
            return _qmt_fallback_technical(trade_date, lookback_days)
        return f"❌ 获取指数技术指标失败: {e}"
