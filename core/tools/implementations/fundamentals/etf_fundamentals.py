"""
ETF 基本面数据工具

获取 ETF 的净值、规模、费率、跟踪误差等指标（ETF 无 PE/PB/ROE）
支持本地数据优先：若 etf_basic_info、etf_daily_quotes 有数据则使用，否则回退到 AKShare 在线接口
"""

import logging
from typing import Annotated, Optional, Tuple
from langchain_core.tools import tool
from datetime import datetime, timedelta

from core.tools.base import register_tool

logger = logging.getLogger(__name__)

ETF_BASIC_COLLECTION = "etf_basic_info"
ETF_DAILY_COLLECTION = "etf_daily_quotes"


def _normalize_etf_symbol(symbol: str) -> str:
    """将 ETF 代码标准化为 6 位数字"""
    if not symbol:
        return ""
    s = str(symbol).strip().upper()
    for prefix in ("SH", "SZ", "SS"):
        if s.startswith(prefix):
            s = s[len(prefix):]
            break
    for suffix in (".SH", ".SZ", ".SS"):
        if s.endswith(suffix):
            s = s[:-len(suffix)]
            break
    digits = "".join(c for c in s if c.isdigit())
    return digits.zfill(6)[-6:] if digits and len(digits) <= 6 else (digits[-6:] if digits else "")


def _get_etf_full_symbol(symbol: str) -> str:
    """根据代码前缀生成完整代码（510050.SH, 159919.SZ）"""
    code = _normalize_etf_symbol(symbol)
    if not code or len(code) != 6:
        return ""
    if code.startswith(("50", "51", "52")):
        return f"{code}.SH"
    if code.startswith(("15", "16")):
        return f"{code}.SZ"
    return f"{code}.SH"


def _fetch_etf_from_local(code: str) -> Tuple[Optional[dict], list]:
    """
    从本地 MongoDB 获取 ETF 基础信息和日线数据。
    Returns:
        (basic_info_dict, daily_records_list)
    """
    try:
        from app.core.database import get_mongo_db_sync
        db = get_mongo_db_sync()
        if not db:
            return None, []

        basic = db[ETF_BASIC_COLLECTION].find_one({"code": code}, {"_id": 0})
        if not basic:
            return None, []

        cursor = db[ETF_DAILY_COLLECTION].find(
            {"code": code},
            {"_id": 0, "trade_date": 1, "close": 1, "pct_chg": 1, "volume": 1, "amount": 1}
        ).sort("trade_date", -1).limit(30)
        daily = list(cursor)
        return basic, daily
    except Exception as e:
        logger.debug(f"本地 ETF 数据查询失败: {e}")
        return None, []


def _fetch_etf_data_akshare(symbol: str) -> Optional[dict]:
    """从 AKShare 获取 ETF 数据"""
    try:
        import akshare as ak
        code = _normalize_etf_symbol(symbol)
        full = _get_etf_full_symbol(symbol)
        if not full:
            return None

        # 获取 ETF 实时行情（东方财富）
        df = ak.fund_etf_spot_em()
        if df is None or df.empty:
            return None

        # 列名可能是 代码/基金代码、名称/基金名称 等
        code_col = "代码" if "代码" in df.columns else "基金代码"
        name_col = "名称" if "名称" in df.columns else "基金名称"
        df["code_clean"] = df[code_col].astype(str).str.replace(".", "").str.zfill(6)
        row = df[df["code_clean"] == code]
        if row.empty:
            row = df[df[code_col].astype(str).str.contains(code, na=False)]
        if row.empty:
            return None

        r = row.iloc[0]
        # 兼容多种列名
        return {
            "name": r.get(name_col, r.get("名称", "")),
            "code": code,
            "full_symbol": full,
            "latest_price": r.get("最新价", r.get("当前-单位净值", r.get("最新-单位净值"))),
            "change_pct": r.get("涨跌幅", r.get("增长率")),
            "volume": r.get("成交量"),
            "amount": r.get("成交额"),
            "fund_scale": r.get("规模"),
            "track_index": r.get("跟踪指数", ""),
        }
    except Exception as e:
        logger.warning(f"AKShare ETF 数据获取失败: {e}")
        return None


def _fetch_etf_data_tushare(symbol: str) -> Optional[dict]:
    """从 Tushare 获取 ETF 数据（fund_basic + 最新 fund_daily）"""
    try:
        from tradingagents.dataflows.providers.china.tushare import get_tushare_provider
        provider = get_tushare_provider()
        if not provider or not provider.api:
            return None

        code = _normalize_etf_symbol(symbol)
        full = _get_etf_full_symbol(symbol)
        if not full:
            return None

        df_basic = provider.api.fund_basic(market="E", status="L", ts_code=full)
        if df_basic is None or df_basic.empty:
            return None

        r = df_basic.iloc[0]
        end = datetime.now().strftime("%Y%m%d")
        start = (datetime.now() - timedelta(days=1)).strftime("%Y%m%d")
        df_daily = provider.api.fund_daily(ts_code=full, start_date=start, end_date=end)
        latest_price = None
        change_pct = None
        volume = None
        amount = None
        if df_daily is not None and not df_daily.empty:
            d = df_daily.iloc[0]
            latest_price = d.get("close")
            change_pct = d.get("pct_chg")
            vol = d.get("vol")
            amt = d.get("amount")
            volume = vol
            if amt is not None:
                try:
                    amount = float(amt) * 1000
                except (TypeError, ValueError):
                    amount = amt

        return {
            "name": r.get("name", ""),
            "code": code,
            "full_symbol": full,
            "latest_price": latest_price,
            "change_pct": change_pct,
            "volume": volume,
            "amount": amount,
            "fund_scale": r.get("issue_amount"),
            "track_index": str(r.get("benchmark", "") or ""),
        }
    except Exception as e:
        logger.warning(f"Tushare ETF 数据获取失败: {e}")
        return None


def _fetch_etf_hist_tushare(symbol: str, days: int = 30) -> list:
    """从 Tushare 获取 ETF 历史数据"""
    try:
        from tradingagents.dataflows.providers.china.tushare import get_tushare_provider
        provider = get_tushare_provider()
        if not provider or not provider.api:
            return []

        code = _normalize_etf_symbol(symbol)
        full = _get_etf_full_symbol(symbol)
        if not full:
            return []

        end = datetime.now().strftime("%Y%m%d")
        start = (datetime.now() - timedelta(days=days)).strftime("%Y%m%d")
        df = provider.api.fund_daily(ts_code=full, start_date=start, end_date=end)
        if df is None or df.empty:
            return []

        records = []
        for _, r in df.iterrows():
            td = r.get("trade_date")
            if td:
                td = str(td)
                if len(td) == 8:
                    td = f"{td[:4]}-{td[4:6]}-{td[6:8]}"
            records.append({
                "日期": td,
                "date": td,
                "trade_date": td,
                "收盘": r.get("close"),
                "close": r.get("close"),
                "涨跌幅": r.get("pct_chg"),
                "pct_chg": r.get("pct_chg"),
                "增长率": r.get("pct_chg"),
            })
        return records
    except Exception as e:
        logger.warning(f"Tushare ETF 历史数据获取失败: {e}")
        return []


def _fetch_etf_hist_akshare(symbol: str, days: int = 30) -> list:
    """从 AKShare 获取 ETF 历史数据"""
    try:
        import akshare as ak
        code = _normalize_etf_symbol(symbol)
        if not code:
            return []
        end = datetime.now().strftime("%Y%m%d")
        start = (datetime.now() - timedelta(days=days)).strftime("%Y%m%d")
        # fund_etf_hist_em 参数: symbol 为 6 位代码
        df = ak.fund_etf_hist_em(symbol=code, period="daily", start_date=start, end_date=end)
        if df is None or df.empty:
            return []
        return df.to_dict("records")
    except Exception as e:
        logger.warning(f"AKShare ETF 历史数据获取失败: {e}")
        return []


@tool
@register_tool(
    tool_id="get_etf_fundamentals",
    name="ETF 基本面数据",
    description="获取 ETF 的净值、规模、跟踪指数、涨跌幅等。ETF 无 PE/PB/ROE，使用净值、规模、费率、跟踪误差等指标。",
    category="fundamentals",
    is_online=True,
    auto_register=True
)
def get_etf_fundamentals(
    ticker: Annotated[str, "ETF 代码（如 510050、159919）"],
    start_date: Annotated[Optional[str], "开始日期，格式：YYYY-MM-DD"] = None,
    end_date: Annotated[Optional[str], "结束日期，格式：YYYY-MM-DD"] = None,
    curr_date: Annotated[Optional[str], "当前日期，格式：YYYY-MM-DD"] = None
) -> str:
    """
    获取 ETF 基本面分析数据

    ETF 与股票不同，没有 PE/PB/ROE。本工具返回：
    - 最新价、涨跌幅
    - 规模、跟踪指数
    - 近期走势摘要

    Args:
        ticker: ETF 代码（如 510050 上证50ETF、159919 沪深300ETF）
        start_date: 开始日期（可选）
        end_date: 结束日期（可选）
        curr_date: 当前日期（可选）

    Returns:
        str: ETF 基本面分析数据（格式化文本）
    """
    logger.info(f"📊 [ETF 基本面] 分析: {ticker}")

    code = _normalize_etf_symbol(ticker)
    if not code or len(code) != 6:
        return f"❌ 无效的 ETF 代码: {ticker}，请输入 6 位数字（如 510050、159919）"

    # 验证是否为 ETF 代码
    if not (code.startswith(("50", "51", "52")) or code.startswith(("15", "16"))):
        return f"❌ {ticker} 不是 ETF 代码。ETF 代码通常为 50/51/52 开头（沪市）或 15/16 开头（深市）"

    # 优先使用本地数据（需同时有基础信息和日线）
    spot = None
    hist = []
    basic_local, daily_local = _fetch_etf_from_local(code)
    if basic_local and daily_local:
        spot = {
            "name": basic_local.get("name", ""),
            "code": code,
            "full_symbol": basic_local.get("full_symbol", _get_etf_full_symbol(ticker)),
            "latest_price": daily_local[0].get("close") if daily_local else None,
            "change_pct": daily_local[0].get("pct_chg") if daily_local else None,
            "volume": daily_local[0].get("volume") if daily_local else None,
            "amount": daily_local[0].get("amount") if daily_local else None,
            "fund_scale": basic_local.get("fund_scale"),
            "track_index": basic_local.get("track_index", ""),
        }
        hist = [{"日期": d.get("trade_date"), "收盘": d.get("close"), "涨跌幅": d.get("pct_chg")} for d in daily_local]
        logger.info(f"📊 [ETF 基本面] 使用本地数据: {code}")

    if not spot:
        spot = _fetch_etf_data_akshare(ticker)
        if spot:
            hist = _fetch_etf_hist_akshare(ticker, days=30)
        else:
            spot = _fetch_etf_data_tushare(ticker)
            hist = _fetch_etf_hist_tushare(ticker, days=30) if spot else []

    lines = [
        f"# {ticker} ETF 基本面分析数据",
        f"**分析日期**: {curr_date or datetime.now().strftime('%Y-%m-%d')}",
        "",
    ]

    if spot:
        lines.extend([
            "## ETF 基本信息",
            f"- 名称: {spot.get('name', '-')}",
            f"- 代码: {spot.get('code', '-')}",
            f"- 完整代码: {spot.get('full_symbol', '-')}",
            "",
            "## 当前行情",
            f"- 最新价: {spot.get('latest_price', '-')}",
            f"- 涨跌幅: {spot.get('change_pct', '-')}%",
            f"- 成交量: {spot.get('volume', '-')}",
            f"- 成交额: {spot.get('amount', '-')}",
            f"- 规模: {spot.get('fund_scale', '-')}",
            f"- 跟踪指数: {spot.get('track_index', '-')}",
            "",
        ])
    else:
        lines.append("## 当前行情\n⚠️ 未能获取实时数据，请检查网络或数据源。\n")

    if hist:
        lines.append("## 近期走势")
        recent = hist[:5] if len(hist) >= 5 else hist
        for h in reversed(recent):
            date = h.get("日期", h.get("date", h.get("trade_date", "-")))
            close = h.get("收盘", h.get("close", "-"))
            pct = h.get("涨跌幅", h.get("pct_chg", h.get("增长率", "-")))
            lines.append(f"- {date}: 收盘 {close}, 涨跌幅 {pct}%")
        lines.append("")
    else:
        lines.append("## 近期走势\n⚠️ 未能获取历史数据。\n")

    lines.append("---")
    lines.append("*说明: ETF 无 PE/PB/ROE 等个股估值指标，分析时请关注净值、规模、跟踪指数、跟踪误差等。*")

    return "\n".join(lines)
