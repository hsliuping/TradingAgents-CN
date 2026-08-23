"""
ETF 基本面数据工具

获取 ETF 的净值、规模、费率、折溢价、申赎状态等指标（ETF 无 PE/PB/ROE）。
支持本地数据优先：若 etf_basic_info、etf_daily_quotes 有数据则使用，否则回退到 AKShare / Tushare 在线接口。
"""

import logging
from datetime import datetime, timedelta
from typing import Annotated, Optional, Tuple

from langchain_core.tools import tool

from core.tools.base import register_tool

logger = logging.getLogger(__name__)

ETF_BASIC_COLLECTION = "etf_basic_info"
ETF_DAILY_COLLECTION = "etf_daily_quotes"
ETF_DEFAULT_SOURCE_PRIORITY = ["local", "tushare", "akshare"]
ETF_SUPPORTED_ONLINE_SOURCES = {"tushare", "akshare"}


def _is_missing(value) -> bool:
    if value is None:
        return True
    if isinstance(value, str):
        return value.strip() in {"", "-", "--", "None", "nan", "NaN"}
    return False


def _coalesce(*values):
    for value in values:
        if not _is_missing(value):
            return value
    return None


def _normalize_date(value) -> Optional[str]:
    if _is_missing(value):
        return None
    text = str(value).strip()
    if len(text) >= 10 and len(text) > 4 and text[4] in {"-", "/"}:
        return text[:10].replace("/", "-")
    digits = "".join(ch for ch in text if ch.isdigit())
    if len(digits) == 8:
        return f"{digits[:4]}-{digits[4:6]}-{digits[6:8]}"
    return text or None


def _format_value(value, suffix: str = "") -> str:
    if _is_missing(value):
        return "-"
    return f"{value}{suffix}"


def _normalize_source_name(name: str) -> str:
    return str(name or "").strip().lower()


def _get_etf_source_priority() -> list:
    """获取 ETF 可用数据源优先级，遵循统一配置。"""
    try:
        from app.core.data_source_priority import get_enabled_data_sources_sync

        enabled_sources = get_enabled_data_sources_sync("a_shares")
        priority = []
        for source in enabled_sources:
            normalized = _normalize_source_name(source)
            if normalized == "local" or normalized in ETF_SUPPORTED_ONLINE_SOURCES:
                if normalized not in priority:
                    priority.append(normalized)

        if priority:
            logger.info(f"📊 [ETF 基本面] 数据源优先级: {priority}")
            return priority
    except Exception as e:
        logger.warning(f"⚠️ [ETF 基本面] 获取统一数据源优先级失败: {e}")

    logger.info(f"📊 [ETF 基本面] 使用默认数据源优先级: {ETF_DEFAULT_SOURCE_PRIORITY}")
    return ETF_DEFAULT_SOURCE_PRIORITY.copy()


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
    """从本地 MongoDB 获取 ETF 基础信息和日线数据。"""
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
            {"_id": 0, "trade_date": 1, "close": 1, "pct_chg": 1, "volume": 1, "amount": 1, "unit_nav": 1, "accum_nav": 1},
        ).sort("trade_date", -1).limit(30)
        daily = list(cursor)
        return basic, daily
    except Exception as e:
        logger.debug(f"本地 ETF 数据查询失败: {e}")
        return None, []


def _fetch_etf_data_akshare(symbol: str) -> Optional[dict]:
    """从 AKShare 获取 ETF 实时行情数据。"""
    try:
        import akshare as ak

        code = _normalize_etf_symbol(symbol)
        full = _get_etf_full_symbol(symbol)
        if not full:
            return None

        df = ak.fund_etf_spot_em()
        if df is None or df.empty:
            return None

        code_col = "代码" if "代码" in df.columns else "基金代码"
        name_col = "名称" if "名称" in df.columns else "基金名称"
        df["code_clean"] = df[code_col].astype(str).str.extract(r"(\d{6})", expand=False).fillna("")
        row = df[df["code_clean"] == code]
        if row.empty:
            return None

        record = row.iloc[0]
        return {
            "name": record.get(name_col, record.get("名称", "")),
            "code": code,
            "full_symbol": full,
            "latest_price": record.get("最新价", record.get("当前-单位净值", record.get("最新-单位净值"))),
            "change_pct": record.get("涨跌幅", record.get("增长率")),
            "volume": record.get("成交量"),
            "amount": record.get("成交额"),
            "fund_scale": record.get("规模"),
            "track_index": record.get("跟踪指数", ""),
            "fund_type": record.get("基金类型", ""),
        }
    except Exception as e:
        logger.warning(f"AKShare ETF 数据获取失败: {e}")
        return None


def _fetch_etf_valuation_akshare(symbol: str) -> Optional[dict]:
    """从 AKShare 获取 ETF 净值、折溢价和场内申赎状态。"""
    try:
        import akshare as ak

        code = _normalize_etf_symbol(symbol)
        if not code:
            return None

        valuation_df = ak.fund_etf_fund_daily_em()
        if valuation_df is None or valuation_df.empty:
            return None

        code_col = "基金代码" if "基金代码" in valuation_df.columns else "代码"
        valuation_df["code_clean"] = valuation_df[code_col].astype(str).str.extract(r"(\d{6})", expand=False).fillna("")
        row = valuation_df[valuation_df["code_clean"] == code]
        if row.empty:
            return None

        record = row.iloc[0]
        unit_nav_col = next((col for col in valuation_df.columns if str(col).endswith("单位净值")), None)
        accum_nav_col = next((col for col in valuation_df.columns if str(col).endswith("累计净值")), None)

        result = {
            "unit_nav": record.get(unit_nav_col) if unit_nav_col else None,
            "accum_nav": record.get(accum_nav_col) if accum_nav_col else None,
            "nav_change_value": record.get("增长值"),
            "nav_growth_rate": record.get("增长率"),
            "market_price": record.get("市价"),
            "premium_discount_rate": record.get("折价率"),
            "fund_type": record.get("类型"),
        }

        try:
            info_df = ak.fund_etf_fund_info_em(
                fund=code,
                start_date=(datetime.now() - timedelta(days=30)).strftime("%Y%m%d"),
                end_date=datetime.now().strftime("%Y%m%d"),
            )
            if info_df is not None and not info_df.empty:
                latest = info_df.iloc[0]
                result.update(
                    {
                        "latest_nav_date": latest.get("净值日期"),
                        "purchase_status": latest.get("申购状态"),
                        "redemption_status": latest.get("赎回状态"),
                        "unit_nav": _coalesce(result.get("unit_nav"), latest.get("单位净值")),
                        "accum_nav": _coalesce(result.get("accum_nav"), latest.get("累计净值")),
                        "nav_growth_rate": _coalesce(result.get("nav_growth_rate"), latest.get("日增长率")),
                    }
                )
        except Exception as exc:
            logger.warning(f"AKShare ETF 申赎状态获取失败: {exc}")

        return result
    except Exception as e:
        logger.warning(f"AKShare ETF 估值数据获取失败: {e}")
        return None


def _fetch_etf_data_tushare(symbol: str) -> Optional[dict]:
    """从 Tushare 获取 ETF 数据（fund_basic + 最新 fund_daily）。"""
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

        record = df_basic.iloc[0]
        end = datetime.now().strftime("%Y%m%d")
        start = (datetime.now() - timedelta(days=1)).strftime("%Y%m%d")
        df_daily = provider.api.fund_daily(ts_code=full, start_date=start, end_date=end)
        latest_price = None
        change_pct = None
        volume = None
        amount = None
        if df_daily is not None and not df_daily.empty:
            latest = df_daily.iloc[0]
            latest_price = latest.get("close")
            change_pct = latest.get("pct_chg")
            volume = latest.get("vol")
            amount = latest.get("amount")
            if amount is not None:
                try:
                    amount = float(amount) * 1000
                except (TypeError, ValueError):
                    pass

        return {
            "name": record.get("name", ""),
            "code": code,
            "full_symbol": full,
            "latest_price": latest_price,
            "change_pct": change_pct,
            "volume": volume,
            "amount": amount,
            "fund_scale": record.get("issue_amount"),
            "track_index": str(record.get("benchmark", "") or ""),
            "management": record.get("management"),
            "custodian": record.get("custodian"),
            "fund_type": record.get("fund_type"),
            "management_fee": record.get("m_fee"),
            "custodian_fee": record.get("c_fee"),
            "found_date": record.get("found_date"),
            "list_date": record.get("list_date"),
            "issue_date": record.get("issue_date"),
            "due_date": record.get("due_date"),
            "invest_type": record.get("invest_type"),
            "status": record.get("status"),
            "min_amount": record.get("min_amount"),
            "purchase_start_date": record.get("purc_startdate"),
            "redemption_start_date": record.get("redm_startdate"),
        }
    except Exception as e:
        logger.warning(f"Tushare ETF 数据获取失败: {e}")
        return None


def _fetch_etf_hist_tushare(symbol: str, days: int = 30) -> list:
    """从 Tushare 获取 ETF 历史数据。"""
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
        for _, record in df.iterrows():
            trade_date = record.get("trade_date")
            if trade_date:
                trade_date = str(trade_date)
                if len(trade_date) == 8:
                    trade_date = f"{trade_date[:4]}-{trade_date[4:6]}-{trade_date[6:8]}"
            records.append(
                {
                    "日期": trade_date,
                    "date": trade_date,
                    "trade_date": trade_date,
                    "收盘": record.get("close"),
                    "close": record.get("close"),
                    "涨跌幅": record.get("pct_chg"),
                    "pct_chg": record.get("pct_chg"),
                    "增长率": record.get("pct_chg"),
                }
            )
        return records
    except Exception as e:
        logger.warning(f"Tushare ETF 历史数据获取失败: {e}")
        return []


def _fetch_etf_hist_akshare(symbol: str, days: int = 30) -> list:
    """从 AKShare 获取 ETF 历史数据。"""
    try:
        import akshare as ak

        code = _normalize_etf_symbol(symbol)
        if not code:
            return []
        end = datetime.now().strftime("%Y%m%d")
        start = (datetime.now() - timedelta(days=days)).strftime("%Y%m%d")
        df = ak.fund_etf_hist_em(symbol=code, period="daily", start_date=start, end_date=end)
        if df is None or df.empty:
            return []
        return df.to_dict("records")
    except Exception as e:
        logger.warning(f"AKShare ETF 历史数据获取失败: {e}")
        return []


def _merge_missing_fields(target: dict, extra: Optional[dict]) -> dict:
    if not extra:
        return target
    for key, value in extra.items():
        target[key] = _coalesce(target.get(key), value)
    return target


def _fetch_etf_online_bundle(symbol: str, source: str, include_hist: bool = True) -> Tuple[Optional[dict], list]:
    """按指定在线数据源获取 ETF 数据，避免跨源无序回退。"""
    normalized = _normalize_source_name(source)
    hist = []

    if normalized == "tushare":
        spot = _fetch_etf_data_tushare(symbol)
        if spot and include_hist:
            hist = _fetch_etf_hist_tushare(symbol, days=30)
        return spot, hist

    if normalized == "akshare":
        spot = _fetch_etf_data_akshare(symbol)
        spot = _merge_missing_fields(spot or {}, _fetch_etf_valuation_akshare(symbol))
        if not spot:
            return None, []
        if include_hist:
            hist = _fetch_etf_hist_akshare(symbol, days=30)
        return spot, hist

    return None, []


@tool
@register_tool(
    tool_id="get_etf_fundamentals",
    name="ETF 基本面数据",
    description="获取 ETF 的净值、规模、费率、折溢价、申赎状态、跟踪指数、涨跌幅等。",
    category="fundamentals",
    is_online=True,
    auto_register=True,
    capability_tags=["etf_fundamentals", "etf", "etf_nav", "fundamentals", "etf_valuation", "fund_scale", "premium_discount"],
    tool_role_hint="specialized",
    output_shape="markdown",
    preferred_for=["etf_analysis", "etf_valuation_review", "fund_basics_lookup"],
)
def get_etf_fundamentals(
    ticker: Annotated[str, "ETF 代码（如 510050、159919）"],
    start_date: Annotated[Optional[str], "开始日期，格式：YYYY-MM-DD"] = None,
    end_date: Annotated[Optional[str], "结束日期，格式：YYYY-MM-DD"] = None,
    curr_date: Annotated[Optional[str], "当前日期，格式：YYYY-MM-DD"] = None,
) -> str:
    """获取 ETF 基本面分析数据。

    Args:
        ticker: ETF 代码（如 "510050"、"159919"）
        start_date: 开始日期（YYYY-MM-DD），默认 None（当前未使用）
        end_date: 结束日期（YYYY-MM-DD），默认 None（当前未使用）
        curr_date: 当前日期（YYYY-MM-DD），为 None 时使用 datetime.now()，默认 None

    Returns:
        str: Markdown 格式字符串，包含以下章节——
            标题: "{ticker} ETF 基本面分析数据"
            分析日期: 当前或指定日期
            ETF 基本信息: 名称、代码、完整代码、基金类型、跟踪指数、管理人、托管人、成立日期、上市日期
            当前行情: 最新价、涨跌幅、成交量、成交额、规模
            ETF 深属性: 单位净值、累计净值、净值日期、场内市价、折溢价率、净值增长率、
                管理费、托管费、起购金额、申购开始日、赎回开始日、申购状态、赎回状态、
                投资类型、基金状态、跟踪误差、申赎清单结构
            近期走势: 最近 5 个交易日的日期、收盘价、涨跌幅
            说明: 关于 ETF 不适用个股估值指标的提示

            若代码非法返回 "❌ 无效的 ETF 代码..." 提示字符串；
            若代码非 ETF 代码返回 "❌ {ticker} 不是 ETF 代码..." 提示字符串。
    """
    logger.info(f"📊 [ETF 基本面] 分析: {ticker}")

    code = _normalize_etf_symbol(ticker)
    if not code or len(code) != 6:
        return f"❌ 无效的 ETF 代码: {ticker}，请输入 6 位数字（如 510050、159919）"

    if not (code.startswith(("50", "51", "52")) or code.startswith(("15", "16"))):
        return f"❌ {ticker} 不是 ETF 代码。ETF 代码通常为 50/51/52 开头（沪市）或 15/16 开头（深市）"

    source_priority = _get_etf_source_priority()
    online_sources = [source for source in source_priority if source in ETF_SUPPORTED_ONLINE_SOURCES]

    spot = None
    hist = []
    spot_source = "local"
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
            "management": basic_local.get("management"),
            "custodian": basic_local.get("custodian"),
            "fund_type": basic_local.get("fund_type"),
            "management_fee": basic_local.get("management_fee"),
            "custodian_fee": basic_local.get("custodian_fee"),
            "found_date": basic_local.get("found_date"),
            "list_date": basic_local.get("list_date"),
            "issue_date": basic_local.get("issue_date"),
            "due_date": basic_local.get("due_date"),
            "invest_type": basic_local.get("invest_type"),
            "status": basic_local.get("status"),
            "min_amount": basic_local.get("min_amount"),
            "purchase_start_date": basic_local.get("purchase_start_date"),
            "redemption_start_date": basic_local.get("redemption_start_date"),
            "unit_nav": basic_local.get("unit_nav") or (daily_local[0].get("unit_nav") if daily_local else None),
            "accum_nav": basic_local.get("accum_nav") or (daily_local[0].get("accum_nav") if daily_local else None),
            "market_price": basic_local.get("market_price"),
            "premium_discount_rate": basic_local.get("premium_discount_rate"),
            "nav_growth_rate": basic_local.get("nav_growth_rate"),
            "latest_nav_date": basic_local.get("latest_nav_date"),
            "purchase_status": basic_local.get("purchase_status"),
            "redemption_status": basic_local.get("redemption_status"),
        }
        hist = [{"日期": item.get("trade_date"), "收盘": item.get("close"), "涨跌幅": item.get("pct_chg")} for item in daily_local]
        logger.info(f"📊 [ETF 基本面] 使用本地数据: {code}")

    if not spot:
        spot_source = None
        for source in online_sources:
            source_spot, source_hist = _fetch_etf_online_bundle(ticker, source, include_hist=True)
            if source_spot:
                spot = source_spot
                hist = source_hist
                spot_source = source
                logger.info(f"📊 [ETF 基本面] 使用在线数据源: {source}")
                break

    spot = spot or {}

    if spot_source == "local" and online_sources:
        # 本地命中时，仅使用最高优先级在线数据源做一次补充，避免次优源额外报错。
        enrichment_source = online_sources[0]
        enrichment_spot, _ = _fetch_etf_online_bundle(ticker, enrichment_source, include_hist=False)
        spot = _merge_missing_fields(spot, enrichment_spot)
        logger.info(f"📊 [ETF 基本面] 本地数据补充来源: {enrichment_source}")

    lines = [
        f"# {ticker} ETF 基本面分析数据",
        f"**分析日期**: {curr_date or datetime.now().strftime('%Y-%m-%d')}",
        "",
    ]

    if spot:
        lines.extend(
            [
                "## ETF 基本信息",
                f"- 名称: {_format_value(spot.get('name'))}",
                f"- 代码: {_format_value(spot.get('code'))}",
                f"- 完整代码: {_format_value(spot.get('full_symbol'))}",
                f"- 基金类型: {_format_value(spot.get('fund_type'))}",
                f"- 跟踪指数: {_format_value(spot.get('track_index'))}",
                f"- 管理人: {_format_value(spot.get('management'))}",
                f"- 托管人: {_format_value(spot.get('custodian'))}",
                f"- 成立日期: {_format_value(_normalize_date(spot.get('found_date')))}",
                f"- 上市日期: {_format_value(_normalize_date(spot.get('list_date')))}",
                "",
                "## 当前行情",
                f"- 最新价: {_format_value(spot.get('latest_price'), ' 元')}",
                f"- 涨跌幅: {_format_value(spot.get('change_pct'), '%')}",
                f"- 成交量: {_format_value(spot.get('volume'))} 手",
                f"- 成交额: {_format_value(spot.get('amount'))} 元",
                f"- 规模: {_format_value(spot.get('fund_scale'))} 份",
                "",
                "## ETF 深属性",
                f"- 单位净值: {_format_value(spot.get('unit_nav'))}",
                f"- 累计净值: {_format_value(spot.get('accum_nav'))}",
                f"- 净值日期: {_format_value(_normalize_date(spot.get('latest_nav_date')))}",
                f"- 场内市价: {_format_value(spot.get('market_price'))}",
                f"- 折溢价率: {_format_value(spot.get('premium_discount_rate'), '%')}",
                f"- 净值增长率: {_format_value(spot.get('nav_growth_rate'), '%')}",
                f"- 管理费: {_format_value(spot.get('management_fee'), '%')}",
                f"- 托管费: {_format_value(spot.get('custodian_fee'), '%')}",
                f"- 起购金额: {_format_value(spot.get('min_amount'))}",
                f"- 申购开始日: {_format_value(_normalize_date(spot.get('purchase_start_date')))}",
                f"- 赎回开始日: {_format_value(_normalize_date(spot.get('redemption_start_date')))}",
                f"- 申购状态: {_format_value(spot.get('purchase_status'))}",
                f"- 赎回状态: {_format_value(spot.get('redemption_status'))}",
                f"- 投资类型: {_format_value(spot.get('invest_type'))}",
                f"- 基金状态: {_format_value(spot.get('status'))}",
                "- 跟踪误差: 暂无直接数据源",
                "- 申赎清单结构: 暂无直接数据源",
                "",
            ]
        )
    else:
        lines.append("## 当前行情\n⚠️ 未能获取实时数据，请检查网络或数据源。\n")

    if hist:
        lines.append("## 近期走势")
        recent = hist[:5] if len(hist) >= 5 else hist
        for item in reversed(recent):
            date = item.get("日期", item.get("date", item.get("trade_date", "-")))
            close = item.get("收盘", item.get("close", "-"))
            pct = item.get("涨跌幅", item.get("pct_chg", item.get("增长率", "-")))
            lines.append(f"- {date}: 收盘 {close}, 涨跌幅 {pct}%")
        lines.append("")
    else:
        lines.append("## 近期走势\n⚠️ 未能获取历史数据。\n")

    lines.append("---")
    lines.append("*说明: ETF 无 PE/PB/ROE 等个股估值指标，分析时请关注净值、规模、费率、折溢价、申赎状态、跟踪指数等。跟踪误差与申赎清单结构当前暂无直接数据源。*")

    return "\n".join(lines)
