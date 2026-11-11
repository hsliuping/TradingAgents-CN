"""
中国市场概览工具
取数经 DataFacade index_daily 能力（tushare/akshare 双源自动降级），
工具不感知具体数据源。
"""
import logging
import threading
from typing import Annotated
from datetime import datetime, timedelta

import pandas as pd

from langchain_core.tools import tool

from core.tools.base import register_tool

logger = logging.getLogger(__name__)


def _query_index_daily(ts_code: str, start_date: str, end_date: str):
    """经 DataFacade 查询指数日线（返回标准字段 + source/quality，trade_date 降序）"""
    from tradingagents.dataflows.capability.facade import get_data_facade

    return get_data_facade().get_capability("index_daily").query(
        ts_code=ts_code, start_date=start_date, end_date=end_date
    )


def _run_async_in_thread(coro, timeout: int = 30):
    """在独立线程中运行异步协程（同步工具函数接入 async facade）"""
    import asyncio

    container = {"result": None, "error": None}

    def _run():
        try:
            container["result"] = asyncio.run(coro)
        except Exception as exc:
            container["error"] = exc

    t = threading.Thread(target=_run)
    t.start()
    t.join(timeout=timeout)
    if container["error"] is not None:
        raise container["error"]
    return container["result"]


def _safe_float(row, col: str):
    """读取标准化行字段并转 float；缺失/NaN 返回 None"""
    val = row.get(col)
    try:
        if val is None or pd.isna(val):
            return None
        return float(val)
    except (TypeError, ValueError):
        return None


@tool
@register_tool(
    tool_id="get_china_market_overview",
    name="中国市场概览",
    description="获取中国股市主要指数行情概览（上证、深证、创业板、科创50）",
    category="market",
    is_online=True,
    auto_register=True,
    capability_tags=["china_market_overview", "market_overview", "index_data", "market_quote", "main_index"],
    tool_role_hint="specialized",
    output_shape="markdown",
    preferred_for=["china_market_overview", "index_performance_review", "main_index_tracking"],
)
def get_china_market_overview(
    curr_date: Annotated[str, "当前日期，格式 yyyy-mm-dd"]
) -> str:
    """
    获取中国股市整体概览，包括主要指数的行情。
    涵盖上证指数、深证成指、创业板指、科创50等主要指数。

    Args:
        curr_date (str): 当前日期，格式 yyyy-mm-dd

    Returns:
        str: 包含主要指数行情的市场概览报告
    """
    logger.info(f"📊 [中国市场概览] 开始获取数据, 日期: {curr_date}")

    try:
        # 主要指数代码
        indices = {
            "000001.SH": "上证指数",
            "399001.SZ": "深证成指",
            "399006.SZ": "创业板指",
            "000688.SH": "科创50"
        }

        # 查询窗口：请求日前推 30 天，覆盖周末/节假日无数据场景
        end_clean = curr_date.replace('-', '')
        start_clean = (
            datetime.strptime(end_clean, '%Y%m%d') - timedelta(days=30)
        ).strftime('%Y%m%d')

        results = []
        actual_dates = []
        actual_sources = set()

        for code, name in indices.items():
            try:
                # 🔑 取请求日前最近的一个交易日（能力返回按 trade_date 降序，iloc[0] 即最新）
                df = _run_async_in_thread(
                    _query_index_daily(code, start_clean, end_clean), timeout=30
                )

                if df is not None and not df.empty:
                    row = df.iloc[0]
                    close = _safe_float(row, 'close')
                    if close is None:
                        results.append(f"### {name} ({code})\n- 暂无有效数据（请求日期：{curr_date}）")
                        continue
                    change = _safe_float(row, 'change')
                    pct_chg = _safe_float(row, 'pct_chg')
                    vol = _safe_float(row, 'vol')
                    amount = _safe_float(row, 'amount')

                    # 实际数据来源（facade 标准化附带的 source 列）
                    source_val = str(row.get('source', '') or '').strip()
                    if source_val:
                        actual_sources.add(source_val)

                    trade_date = str(row['trade_date'])
                    trade_date_str = f"{trade_date[:4]}-{trade_date[4:6]}-{trade_date[6:]}"
                    actual_dates.append(trade_date_str)

                    # 🔑 如果实际日期与请求日期不一致，在报告中说明
                    date_note = ""
                    if trade_date_str != curr_date:
                        date_note = f" (注：{curr_date} 无数据，使用最近交易日 {trade_date_str})"

                    # 格式化涨跌幅符号
                    if change is None or pct_chg is None:
                        change_line = "- **涨跌**: 暂无数据"
                    else:
                        sign = "+" if change > 0 else ""
                        change_line = f"- **涨跌**: {sign}{change:.2f} ({sign}{pct_chg:.2f}%)"

                    # vol 单位手（÷1e4=万手），amount 单位千元（÷1e5=亿元）
                    vol_line = (
                        f"- **成交量**: {vol / 10000:.2f} 万手"
                        if vol is not None else "- **成交量**: 暂无数据"
                    )
                    amount_line = (
                        f"- **成交额**: {amount / 100000:.2f} 亿元"
                        if amount is not None else "- **成交额**: 暂无数据"
                    )

                    item = f"""### {name} ({code})
- **日期**: {trade_date_str}{date_note}
- **收盘**: {close:.2f}
{change_line}
{vol_line}
{amount_line}
"""
                    results.append(item)
                else:
                    results.append(f"### {name} ({code})\n- 暂无数据（请求日期：{curr_date}）")

            except Exception as e:
                logger.error(f"❌ 获取指数 {name} 失败: {e}")
                results.append(f"### {name} ({code})\n- 获取失败: {e}")

        # 🔑 如果所有指数的实际日期都一致，使用实际日期；否则使用请求日期
        if actual_dates and len(set(actual_dates)) == 1:
            actual_date = actual_dates[0]
            date_note = f"（请求日期：{curr_date}，实际使用：{actual_date}）" if actual_date != curr_date else ""
        else:
            date_note = ""

        # 数据来源标注（取本次各指数实际命中的数据源）
        if actual_sources:
            source_note = "、".join(sorted(actual_sources)) + "（DataFacade 自动降级）"
        else:
            source_note = "多数据源（DataFacade 自动降级）"

        # 组合报告
        report = f"""# 中国市场概览
**分析基准日期**: {curr_date}{date_note}

## 📉 主要指数表现
{chr(10).join(results)}

---
*数据来源: {source_note}*
"""
        logger.info(f"✅ [中国市场概览] 获取成功")
        return report

    except Exception as e:
        error_msg = f"中国市场概览获取失败: {str(e)}"
        logger.error(f"❌ {error_msg}")
        return error_msg
