"""估值测算 bundle 自动装配（A10-D2）

从本地同步数据库装配 generate_valuation_spec 所需的 bundle，数据全部来自现有 helper：

- 现价：core.tools.external.local_data.get_latest_stock_price（market_quotes → basic_info 回退）
- 股票名称：core.tools.external.local_data.get_stock_basic_info
- 财务历史（年报营收/归母净利润）：
  core.skill_runtime.standard_financial_apis.get_historical_financial_annual_series
  （records 单位为元，此处换算为亿元）
- 总股本（亿股）：
  1) stock_basic_info.total_share / total_shares（字段契约单位：万股）
  2) 兜底：最新年报 balance_sheet.total_share（同步链路实测单位为股，做量级判别）

数据溯源铁律：任一必需数据未同步时抛 ValuationDataError 并明确说明缺失项，
禁止估算补位。
"""

import logging
from typing import Any, Dict, List, Optional, Tuple

from core.skill_runtime.standard_financial_apis import (
    get_historical_financial_annual_series,
    get_stock_financial_periods,
)
from core.tools.external.local_data import get_latest_stock_price, get_stock_basic_info

logger = logging.getLogger(__name__)

# 年报历史期数（渲染增速公式需要至少 2 期）
_MIN_HISTORY = 2
_MAX_HISTORY = 3


class ValuationDataError(Exception):
    """估值测算必需数据未同步（阻断生成，需先数据同步）"""


def _normalize_symbol(symbol: str) -> str:
    s = str(symbol or "").strip()
    digits = "".join(ch for ch in s if ch.isdigit())
    if len(digits) != 6:
        raise ValuationDataError(f"股票代码不合法：{symbol!r}（需 6 位数字代码）")
    return digits.zfill(6)


def _shares_to_yi(raw: float, source: str) -> Tuple[float, Optional[str]]:
    """把原始股本值换算为亿股，返回 (亿股, 量级判别说明或 None)"""
    if raw >= 1e8:
        # 单位为股
        return raw / 1e8, None
    # 单位为万股（字段契约口径）
    return raw / 1e4, f"股本来源 {source} 数值 {raw} 按万股口径换算"


def _resolve_share_count_yi(symbol: str, basic_info: Dict[str, Any]) -> Tuple[float, List[str]]:
    """解析总股本（亿股）：basic_info 万股契约 → 最新年报 balance_sheet 兜底"""
    notes: List[str] = []
    raw = basic_info.get("total_share") or basic_info.get("total_shares")
    if isinstance(raw, (int, float)) and raw > 0:
        yi, note = _shares_to_yi(float(raw), "stock_basic_info.total_share")
        if note:
            notes.append(note)
        return yi, notes

    # 兜底：最新年报 balance_sheet.total_share（同步链路实测单位为股）
    try:
        periods = get_stock_financial_periods(symbol, limit=8)
    except Exception as exc:  # noqa: BLE001
        logger.warning("[ValuationBundle] 查询财务期间失败（股本兜底不可用）: %s", exc)
        periods = []
    annual = [p for p in periods if str(p.get("report_period") or "").endswith("1231")]
    if annual:
        latest = annual[0]
        bs = latest.get("balance_sheet") or {}
        raw_bs = bs.get("total_share") or bs.get("total_shares")
        if isinstance(raw_bs, (int, float)) and raw_bs > 0:
            yi, note = _shares_to_yi(
                float(raw_bs), f"年报{latest.get('report_period')} balance_sheet.total_share"
            )
            if note:
                notes.append(note)
            notes.append(f"总股本取自最新年报 {latest.get('report_period')}，可能晚于当前股本变动")
            return yi, notes

    raise ValuationDataError(
        "总股本数据未同步（stock_basic_info 与年报 balance_sheet 均无 total_share），"
        "请先执行该股票的基础信息数据同步后重试"
    )


def _build_financial_history(symbol: str) -> Tuple[List[Dict[str, Any]], List[str]]:
    """构建年报财务历史（升序，亿元），数据不足时抛 ValuationDataError"""
    notes: List[str] = []
    try:
        result = get_historical_financial_annual_series(symbol, years=_MAX_HISTORY)
    except Exception as exc:  # noqa: BLE001
        raise ValuationDataError(f"年报财务数据获取失败：{exc}") from exc

    records = result.get("records") or []
    history: List[Dict[str, Any]] = []
    for rec in records:  # records 按年份倒序，反转为升序（老 → 新）
        revenue, net_profit = rec.get("revenue"), rec.get("net_profit")
        if not isinstance(revenue, (int, float)) or revenue <= 0:
            continue
        if not isinstance(net_profit, (int, float)) or net_profit <= 0:
            continue
        history.append(
            {
                "period": str(rec.get("year") or rec.get("report_period") or ""),
                "revenue": round(float(revenue) / 1e8, 4),  # 元 → 亿元
                "net_profit": round(float(net_profit) / 1e8, 4),
            }
        )
    history.reverse()

    if len(history) < _MIN_HISTORY:
        raise ValuationDataError(
            f"年报数据不足（有效年报 {len(history)} 期，至少 {_MIN_HISTORY} 期），"
            "请先执行该股票的财务数据同步后重试"
        )
    notes.append(
        f"财务历史取最近 {len(history)} 期年报（最新 {history[-1]['period']}），单位换算：元 → 亿元"
    )
    return history, notes


def build_valuation_bundle(
    symbol: str,
    context_notes: str = "",
    forecast_years: int = 2,
) -> Dict[str, Any]:
    """装配估值测算 bundle（数据全部来自本地同步库，缺失即报错）

    Returns:
        bundle dict：ticker / stock_name / analysis_date / current_price /
        share_count（亿股）/ financial_history（升序，亿元）/
        investment_plan（context_notes，作为综合研究结论注入）/
        data_notes（数据口径说明，供结果披露）

    Raises:
        ValuationDataError: 必需数据未同步
    """
    from datetime import datetime

    sym = _normalize_symbol(symbol)
    notes: List[str] = []

    basic_info = get_stock_basic_info(sym) or {}
    stock_name = str(basic_info.get("name") or basic_info.get("stock_name") or "").strip()
    if not stock_name:
        raise ValuationDataError(f"未找到股票 {sym} 的基础信息，请先执行数据同步")

    current_price = get_latest_stock_price(sym)
    if not current_price or current_price <= 0:
        raise ValuationDataError(
            f"股票 {sym}（{stock_name}）最新行情未同步，无法确定现价，请先执行行情数据同步"
        )

    share_count_yi, share_notes = _resolve_share_count_yi(sym, basic_info)
    notes.extend(share_notes)

    history, history_notes = _build_financial_history(sym)
    notes.extend(history_notes)

    forecast_years = max(1, min(int(forecast_years or 2), 3))
    context = ""
    if str(context_notes or "").strip():
        context = (
            f"用户希望基于以下研究结论，对未来 {forecast_years} 年进行盈利推演与估值测算：\n"
            f"{str(context_notes).strip()}"
        )
    else:
        context = f"用户希望对未来 {forecast_years} 年进行盈利推演与估值测算，假设由你基于财务历史数据提出。"

    bundle: Dict[str, Any] = {
        "ticker": sym,
        "stock_name": stock_name,
        "analysis_date": datetime.now().strftime("%Y-%m-%d"),
        "current_price": float(current_price),
        "share_count": round(share_count_yi, 4),
        "financial_history": history,
        "investment_plan": context,
        "data_notes": notes,
    }
    logger.info(
        "[ValuationBundle] %s（%s）装配完成: price=%s, shares=%.2f亿股, history=%s",
        stock_name, sym, current_price, share_count_yi,
        [h["period"] for h in history],
    )
    return bundle
