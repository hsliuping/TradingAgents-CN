"""
股票详情相关API
- 统一响应包: {success, data, message, timestamp}
- 所有端点均需鉴权 (Bearer Token)
- 路径前缀在 main.py 中挂载为 /api，当前路由自身前缀为 /stocks
"""
from datetime import date, datetime
from typing import Optional, Dict, Any, List, Tuple
from fastapi import APIRouter, Depends, HTTPException, status, Query
import asyncio
import logging
import re

from app.routers.auth_db import get_current_user
from app.core.database import get_mongo_db
from app.core.response import ok
from core.skill_runtime.fundamental_factors import get_fundamental_factor_snapshot

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/stocks", tags=["stocks"])


FINANCIAL_RAW_GROUPS = [
    "income_statement",
    "balance_sheet",
    "cashflow_statement",
    "financial_indicators",
    "main_business",
]


def _pick_first_value(*values):
    for value in values:
        if value is not None:
            return value
    return None


def _build_financial_summary(financial_data: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    if not financial_data:
        return {}

    indicators = financial_data.get("financial_indicators") or {}

    summary = {
        "report_period": financial_data.get("report_period"),
        "report_type": financial_data.get("report_type"),
        "ann_date": financial_data.get("ann_date"),
        "data_source": financial_data.get("data_source"),
        "revenue": financial_data.get("revenue"),
        "revenue_ttm": financial_data.get("revenue_ttm"),
        "oper_rev": financial_data.get("oper_rev"),
        "net_income": financial_data.get("net_income"),
        "net_profit": financial_data.get("net_profit"),
        "net_profit_ttm": financial_data.get("net_profit_ttm"),
        "oper_profit": financial_data.get("oper_profit"),
        "total_profit": financial_data.get("total_profit"),
        "gross_margin": _pick_first_value(financial_data.get("gross_margin"), indicators.get("gross_margin")),
        "netprofit_margin": _pick_first_value(financial_data.get("netprofit_margin"), indicators.get("netprofit_margin")),
        "roe": _pick_first_value(financial_data.get("roe"), indicators.get("roe"), indicators.get("roe_avg")),
        "roa": _pick_first_value(financial_data.get("roa"), indicators.get("roa")),
        "roe_waa": financial_data.get("roe_waa"),
        "roe_dt": financial_data.get("roe_dt"),
        "debt_to_assets": _pick_first_value(financial_data.get("debt_to_assets"), indicators.get("debt_to_assets")),
        "assets_to_eqt": _pick_first_value(financial_data.get("assets_to_eqt"), indicators.get("assets_to_eqt")),
        "current_ratio": _pick_first_value(financial_data.get("current_ratio"), indicators.get("current_ratio")),
        "quick_ratio": _pick_first_value(financial_data.get("quick_ratio"), indicators.get("quick_ratio")),
        "cash_ratio": _pick_first_value(financial_data.get("cash_ratio"), indicators.get("cash_ratio")),
        "total_assets": financial_data.get("total_assets"),
        "total_liab": financial_data.get("total_liab"),
        "total_equity": financial_data.get("total_equity"),
        "total_cur_assets": financial_data.get("total_cur_assets"),
        "total_cur_liab": financial_data.get("total_cur_liab"),
        "money_cap": financial_data.get("money_cap"),
        "accounts_receiv": financial_data.get("accounts_receiv"),
        "inventories": financial_data.get("inventories"),
        "fix_assets": financial_data.get("fix_assets"),
        "n_cashflow_act": financial_data.get("n_cashflow_act"),
        "n_cashflow_inv_act": financial_data.get("n_cashflow_inv_act"),
        "n_cashflow_fin_act": financial_data.get("n_cashflow_fin_act"),
        "c_cash_equ_end_period": financial_data.get("c_cash_equ_end_period"),
        "c_cash_equ_beg_period": financial_data.get("c_cash_equ_beg_period"),
        "updated_at": financial_data.get("updated_at"),
    }

    return {k: v for k, v in summary.items() if v is not None}


def _build_financial_raw_data(financial_data: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    if not financial_data:
        return {}

    raw_data = financial_data.get("raw_data") or {}
    result: Dict[str, Any] = {}
    for group in FINANCIAL_RAW_GROUPS:
        if raw_data.get(group):
            result[group] = raw_data.get(group)
    return result


def _get_p0_fundamental_snapshot(symbol: str) -> Dict[str, Any]:
    try:
        # allow_remote_fetch=False：本函数仅服务交互式接口（因子预览/财务明细页），
        # 本地缺分红明细时禁止现场拉取 Tushare（约 20 秒），降级用已同步的股息率快照；
        # 数据应通过数据同步功能主动获取，符合"检验只读、同步才拉"的语义
        return get_fundamental_factor_snapshot(symbol, allow_remote_fetch=False) or {}
    except Exception as e:
        logger.warning("获取 P0 基本面 snapshot 失败 %s: %s", symbol, e)
        return {}


def _merge_snapshot_fields_into_fundamentals(data: Dict[str, Any], snapshot: Dict[str, Any]) -> Dict[str, Any]:
    if not snapshot:
        return data

    factors = snapshot.get("factors") or {}
    if factors.get("pe") is not None:
        data["pe"] = factors.get("pe")
    if factors.get("pe_ttm") is not None:
        data["pe_ttm"] = factors.get("pe_ttm")
    if factors.get("pb") is not None:
        data["pb"] = factors.get("pb")
    if factors.get("pb_mrq") is not None:
        data["pb_mrq"] = factors.get("pb_mrq")
    if factors.get("ps_ttm") is not None:
        data["ps_ttm"] = factors.get("ps_ttm")
        if data.get("ps") is None:
            data["ps"] = factors.get("ps_ttm")

    fundamentals_field_map = {
        "dividend_yield": "dividend_yield",
        "roe": "roe",
        "roa": "roa",
        "gross_margin": "gross_margin",
        "netprofit_margin": "netprofit_margin",
        "debt_to_assets": "debt_ratio",
        "assets_to_eqt": "assets_to_eqt",
        "current_ratio": "current_ratio",
        "quick_ratio": "quick_ratio",
        "cash_ratio": "cash_ratio",
        "revenue_ttm": "revenue_ttm",
        "net_profit_ttm": "net_profit_ttm",
        "n_cashflow_act": "n_cashflow_act",
    }
    for snapshot_field, response_field in fundamentals_field_map.items():
        if factors.get(snapshot_field) is not None:
            data[response_field] = factors.get(snapshot_field)

    if factors.get("debt_to_assets") is not None:
        data["debt_to_assets"] = factors.get("debt_to_assets")

    if snapshot.get("report_period"):
        data["report_period"] = snapshot.get("report_period")
    if snapshot.get("data_source"):
        data["financial_data_source"] = snapshot.get("data_source")

    if snapshot.get("factor_diagnostics"):
        data["factor_diagnostics"] = snapshot.get("factor_diagnostics")
    if snapshot.get("factor_warnings"):
        data["factor_warnings"] = snapshot.get("factor_warnings")

    return data


def _merge_snapshot_fields_into_financial_summary(summary: Dict[str, Any], snapshot: Dict[str, Any]) -> Dict[str, Any]:
    if not snapshot:
        return summary

    factors = snapshot.get("factors") or {}
    summary_field_map = {
        "roe": "roe",
        "roa": "roa",
        "gross_margin": "gross_margin",
        "netprofit_margin": "netprofit_margin",
        "debt_to_assets": "debt_to_assets",
        "assets_to_eqt": "assets_to_eqt",
        "current_ratio": "current_ratio",
        "quick_ratio": "quick_ratio",
        "cash_ratio": "cash_ratio",
        "revenue_ttm": "revenue_ttm",
        "net_profit_ttm": "net_profit_ttm",
        "n_cashflow_act": "n_cashflow_act",
    }
    for snapshot_field, summary_field in summary_field_map.items():
        if factors.get(snapshot_field) is not None:
            summary[summary_field] = factors.get(snapshot_field)

    if snapshot.get("report_period"):
        summary["report_period"] = snapshot.get("report_period")

    return summary


async def _get_cn_source_priority() -> List[str]:
    """按系统配置返回启用的 A 股数据源优先级，数字越大优先级越高。"""
    try:
        from app.core.unified_config import UnifiedConfigManager

        config = UnifiedConfigManager()
        data_source_configs = await config.get_data_source_configs_async()
        enabled_sources = [
            ds.type.lower()
            for ds in data_source_configs
            if ds.enabled and ds.type.lower() in ["tushare", "multi_source", "akshare", "baostock"]
        ]
        if enabled_sources:
            return enabled_sources
    except Exception as e:
        logger.warning("获取数据源优先级失败，使用默认顺序: %s", e)

    return ["tushare", "multi_source", "akshare", "baostock"]


def _zfill_code(code: str) -> str:
    try:
        s = str(code).strip()
        if len(s) == 6 and s.isdigit():
            return s
        return s.zfill(6)
    except Exception:
        return str(code)


ETF_CODE_PREFIXES = ("50", "51", "52", "56", "58", "15", "16", "18")


def _is_cn_etf_code(code: str) -> bool:
    code_str = str(code or "").strip()
    return len(code_str) == 6 and code_str.isdigit() and code_str.startswith(ETF_CODE_PREFIXES)


def _get_etf_market_label(code: str) -> str:
    return "ETF"


def _parse_trade_date(value: Any) -> Optional[date]:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    for fmt in ("%Y%m%d", "%Y-%m-%d", "%Y/%m/%d"):
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    return None


def _build_etf_fundamentals_data(etf_doc: Dict[str, Any], latest_quote: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    latest_quote = latest_quote or {}
    return {
        "code": etf_doc.get("code"),
        "name": etf_doc.get("name"),
        "industry": etf_doc.get("fund_type") or "ETF",
        "market": _get_etf_market_label(etf_doc.get("code")),
        "sector": etf_doc.get("track_index") or "ETF",
        "security_type": "ETF",
        "fund_type": etf_doc.get("fund_type") or "ETF",
        "track_index": etf_doc.get("track_index"),
        "fund_scale": etf_doc.get("fund_scale"),
        "fund_share": etf_doc.get("fund_share"),
        "fund_share_date": etf_doc.get("fund_share_date"),
        "management": etf_doc.get("management"),
        "custodian": etf_doc.get("custodian"),
        "management_fee": etf_doc.get("management_fee"),
        "custodian_fee": etf_doc.get("custodian_fee"),
        "unit_nav": _pick_first_value(etf_doc.get("unit_nav"), latest_quote.get("unit_nav")),
        "accum_nav": _pick_first_value(etf_doc.get("accum_nav"), latest_quote.get("accum_nav")),
        "nav_change_value": etf_doc.get("nav_change_value"),
        "nav_growth_rate": etf_doc.get("nav_growth_rate"),
        "market_price": _pick_first_value(latest_quote.get("close"), etf_doc.get("market_price")),
        "premium_discount_rate": etf_doc.get("premium_discount_rate"),
        "latest_nav_date": etf_doc.get("latest_nav_date"),
        "purchase_status": etf_doc.get("purchase_status"),
        "redemption_status": etf_doc.get("redemption_status"),
        "updated_at": _pick_first_value(latest_quote.get("updated_at"), etf_doc.get("updated_at")),
    }


async def _get_etf_basic_info_by_sources(db, code6: str, preferred_sources: List[str]) -> Optional[Dict[str, Any]]:
    for source in preferred_sources:
        doc = await db["etf_basic_info"].find_one(
            {"code": code6, "source": source},
            {"_id": 0},
            sort=[("updated_at", -1)]
        )
        if doc:
            return doc

    return await db["etf_basic_info"].find_one(
        {"code": code6},
        {"_id": 0},
        sort=[("updated_at", -1)]
    )


def _aggregate_etf_kline_rows(rows: List[Dict[str, Any]], period: str, limit: int) -> List[Dict[str, Any]]:
    parsed_rows = []
    for row in rows:
        trade_date = _parse_trade_date(row.get("trade_date"))
        if not trade_date:
            continue
        parsed_rows.append((trade_date, row))

    parsed_rows.sort(key=lambda item: item[0])
    if not parsed_rows:
        return []

    def build_bar(bar_rows: List[Dict[str, Any]], label: str) -> Dict[str, Any]:
        opens = [float(r["open"]) for r in bar_rows if r.get("open") is not None]
        highs = [float(r["high"]) for r in bar_rows if r.get("high") is not None]
        lows = [float(r["low"]) for r in bar_rows if r.get("low") is not None]
        closes = [float(r["close"]) for r in bar_rows if r.get("close") is not None]
        volumes = [float(r["volume"]) for r in bar_rows if r.get("volume") is not None]
        amounts = [float(r["amount"]) for r in bar_rows if r.get("amount") is not None]

        return {
            "time": label,
            "open": opens[0] if opens else None,
            "high": max(highs) if highs else None,
            "low": min(lows) if lows else None,
            "close": closes[-1] if closes else None,
            "volume": sum(volumes) if volumes else None,
            "amount": sum(amounts) if amounts else None,
        }

    if period == "day":
        items = []
        for trade_date, row in parsed_rows[-limit:]:
            items.append({
                "time": trade_date.strftime("%Y-%m-%d"),
                "open": row.get("open"),
                "high": row.get("high"),
                "low": row.get("low"),
                "close": row.get("close"),
                "volume": row.get("volume"),
                "amount": row.get("amount"),
            })
        return items

    grouped: Dict[str, List[Dict[str, Any]]] = {}
    for trade_date, row in parsed_rows:
        if period == "week":
            iso_year, iso_week, _ = trade_date.isocalendar()
            key = f"{iso_year}-W{iso_week:02d}"
        else:
            key = trade_date.strftime("%Y-%m")
        grouped.setdefault(key, []).append(row)

    items = [build_bar(bar_rows, key) for key, bar_rows in grouped.items()]
    return items[-limit:]


def _detect_market_and_code(code: str) -> Tuple[str, str]:
    """
    检测股票代码的市场类型并标准化代码

    Args:
        code: 股票代码

    Returns:
        (market, normalized_code): 市场类型和标准化后的代码
            - CN: A股（6位数字）
            - HK: 港股（4-5位数字或带.HK后缀）
            - US: 美股（字母代码）
    """
    code = code.strip().upper()

    # 港股：带.HK后缀
    if code.endswith('.HK'):
        return ('HK', code[:-3].zfill(5))  # 移除.HK，补齐到5位

    # 美股：纯字母
    if re.match(r'^[A-Z]+$', code):
        return ('US', code)

    # 港股：4-5位数字
    if re.match(r'^\d{4,5}$', code):
        return ('HK', code.zfill(5))  # 补齐到5位

    # A股：6位数字
    if re.match(r'^\d{6}$', code):
        return ('CN', code)

    # 默认当作A股处理
    return ('CN', _zfill_code(code))


@router.get("/{code}/quote", response_model=dict)
async def get_quote(
    code: str,
    force_refresh: bool = Query(False, description="是否强制刷新（跳过缓存）"),
    current_user: dict = Depends(get_current_user)
):
    """
    获取股票实时行情（支持A股/港股/美股）

    自动识别市场类型：
    - 6位数字 → A股
    - 4位数字或.HK → 港股
    - 纯字母 → 美股

    参数：
    - code: 股票代码
    - force_refresh: 是否强制刷新（跳过缓存）

    返回字段（data内，蛇形命名）:
      - code, name, market
      - price(close), change_percent(pct_chg), amount, prev_close(估算)
      - turnover_rate, amplitude（振幅，替代量比）
      - trade_date, updated_at
    """
    # 检测市场类型
    market, normalized_code = _detect_market_and_code(code)

    # 港股和美股：使用新服务
    if market in ['HK', 'US']:
        from app.services.foreign_stock_service import ForeignStockService

        db = get_mongo_db()  # 不需要 await，直接返回数据库对象
        service = ForeignStockService(db=db)

        try:
            quote = await service.get_quote(market, normalized_code, force_refresh)
            return ok(data=quote)
        except Exception as e:
            logger.error(f"获取{market}股票{code}行情失败: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"获取行情失败: {str(e)}"
            )

    # A股：使用现有逻辑
    db = get_mongo_db()
    code6 = normalized_code
    is_etf = _is_cn_etf_code(code6)

    q = None
    b = None

    if is_etf:
        # ETF：直接查 etf_daily_quotes + etf_basic_info（ETF 不存在于 market_quotes）
        etf_q = await db["etf_daily_quotes"].find_one(
            {"code": code6}, sort=[("trade_date", -1)], projection={"_id": 0}
        )
        if etf_q:
            q = etf_q
        b = await db["etf_basic_info"].find_one({"code": code6}, {"_id": 0})
        logger.debug(f"🔍 ETF 查询: code={code6}, quote={'✅' if q else '❌'}, basic={'✅' if b else '❌'}")
    else:
        # 股票：查 market_quotes
        q = await db["market_quotes"].find_one({"code": code6}, {"_id": 0})
        if q:
            logger.debug(f"🔍 market_quotes: code={code6} ✅ volume={q.get('volume')}, amount={q.get('amount')}")
        else:
            logger.debug(f"🔍 market_quotes: code={code6} ❌ 未找到，将尝试回退")

        # 基础信息 - 按数据源优先级查询
        from app.core.unified_config import UnifiedConfigManager
        config = UnifiedConfigManager()
        data_source_configs = await config.get_data_source_configs_async()

        enabled_sources = [
            ds.type.lower() for ds in data_source_configs
            if ds.enabled and ds.type.lower() in ['tushare', 'akshare', 'baostock']
        ]
        if not enabled_sources:
            enabled_sources = ['tushare', 'akshare', 'baostock']

        for src in enabled_sources:
            b = await db["stock_basic_info"].find_one({"code": code6, "source": src}, {"_id": 0})
            if b:
                break

        # 兼容旧数据（不带 source 条件）
        if not b:
            b = await db["stock_basic_info"].find_one({"code": code6}, {"_id": 0})

        # 回退：stock_basic_info 未命中时查 etf_basic_info + etf_daily_quotes
        if not b:
            b = await db["etf_basic_info"].find_one({"code": code6}, {"_id": 0})
        if not q:
            etf_q = await db["etf_daily_quotes"].find_one(
                {"code": code6}, sort=[("trade_date", -1)], projection={"_id": 0}
            )
            if etf_q:
                q = etf_q

    if not q and not b:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="未找到该股票的任何信息")

    close = (q or {}).get("close")
    pct = (q or {}).get("pct_chg")
    pre_close_saved = (q or {}).get("pre_close")
    prev_close = pre_close_saved
    if prev_close is None:
        try:
            if close is not None and pct is not None:
                prev_close = round(float(close) / (1.0 + float(pct) / 100.0), 4)
        except Exception:
            prev_close = None

    # 🔥 优先从 market_quotes 获取 turnover_rate（实时数据）
    # 如果 market_quotes 中没有，再从 stock_basic_info 获取（日度数据）
    turnover_rate = (q or {}).get("turnover_rate")
    turnover_rate_date = None
    if turnover_rate is None:
        turnover_rate = (b or {}).get("turnover_rate")
        turnover_rate_date = (b or {}).get("trade_date")  # 来自日度数据
    else:
        turnover_rate_date = (q or {}).get("trade_date")  # 来自实时数据

    # 🔥 计算振幅（amplitude）替代量比（volume_ratio）
    # 振幅 = (最高价 - 最低价) / 昨收价 × 100%
    amplitude = None
    amplitude_date = None
    try:
        high = (q or {}).get("high")
        low = (q or {}).get("low")
        logger.debug(f"🔍 计算振幅: high={high}, low={low}, prev_close={prev_close}")
        if high is not None and low is not None and prev_close is not None and prev_close > 0:
            amplitude = round((float(high) - float(low)) / float(prev_close) * 100, 2)
            amplitude_date = (q or {}).get("trade_date")  # 来自实时数据
            logger.debug(f"  ✅ 振幅计算成功: {amplitude}%")
        else:
            logger.debug(f"  ⚠️ 数据不完整，无法计算振幅")
    except Exception as e:
        logger.warning(f"  ❌ 计算振幅失败: {e}")
        amplitude = None

    data = {
        "code": code6,
        "name": (b or {}).get("name"),
        "market": _get_etf_market_label(code6) if _is_cn_etf_code(code6) else (b or {}).get("market"),
        "price": close,
        "change_percent": pct,
        "amount": (q or {}).get("amount"),
        "volume": (q or {}).get("volume"),
        "open": (q or {}).get("open"),
        "high": (q or {}).get("high"),
        "low": (q or {}).get("low"),
        "prev_close": prev_close,
        # 🔥 优先使用实时数据，降级到日度数据
        "turnover_rate": turnover_rate,
        "amplitude": amplitude,  # 🔥 新增：振幅（替代量比）
        "turnover_rate_date": turnover_rate_date,  # 🔥 新增：换手率数据日期
        "amplitude_date": amplitude_date,  # 🔥 新增：振幅数据日期
        "trade_date": (q or {}).get("trade_date"),
        "updated_at": (q or {}).get("updated_at"),
    }

    return ok(data)


@router.get("/{code}/fundamentals", response_model=dict)
async def get_fundamentals(
    code: str,
    source: Optional[str] = Query(None, description="数据源 (tushare/akshare/baostock/multi_source)"),
    force_refresh: bool = Query(False, description="是否强制刷新（跳过缓存）"),
    current_user: dict = Depends(get_current_user)
):
    """
    获取基础面快照（支持A股/港股/美股）

    数据来源优先级：
    1. stock_basic_info 集合（基础信息、估值指标）
    2. stock_financial_data 集合（财务指标：ROE、负债率等）

    参数：
    - code: 股票代码
    - source: 数据源（可选），默认按优先级：tushare > multi_source > akshare > baostock
    - force_refresh: 是否强制刷新（跳过缓存）
    """
    # 检测市场类型
    market, normalized_code = _detect_market_and_code(code)

    # 港股和美股：使用新服务
    if market in ['HK', 'US']:
        from app.services.foreign_stock_service import ForeignStockService

        db = get_mongo_db()  # 不需要 await，直接返回数据库对象
        service = ForeignStockService(db=db)

        try:
            info = await service.get_basic_info(market, normalized_code, force_refresh)
            return ok(data=info)
        except Exception as e:
            logger.error(f"获取{market}股票{code}基础信息失败: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"获取基础信息失败: {str(e)}"
            )

    # A股：使用现有逻辑
    db = get_mongo_db()
    code6 = normalized_code
    # P0 因子快照含同步 Mongo 查询与 Tushare 分红数据拉取，实测可达 20s+，
    # 必须放线程池执行，否则会阻塞事件循环导致整个后端接口无响应
    p0_snapshot = await asyncio.to_thread(_get_p0_fundamental_snapshot, code6)

    if _is_cn_etf_code(code6):
        if source:
            etf_doc = await db["etf_basic_info"].find_one(
                {"code": code6, "source": source},
                {"_id": 0},
                sort=[("updated_at", -1)]
            )
        else:
            etf_source_priority = [src for src in await _get_cn_source_priority() if src in ["tushare", "akshare", "baostock", "qmt"]]
            if not etf_source_priority:
                etf_source_priority = ["tushare", "akshare", "qmt"]
            etf_doc = await _get_etf_basic_info_by_sources(db, code6, etf_source_priority)

        latest_quote = await db["etf_daily_quotes"].find_one(
            {"code": code6},
            {"_id": 0},
            sort=[("trade_date", -1)]
        )

        if not etf_doc:
            if source:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"未找到该 ETF 在数据源 {source} 中的基础信息")
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="未找到该 ETF 的基础信息")

        return ok(data=_build_etf_fundamentals_data(etf_doc, latest_quote))

    # 1. 获取基础信息（支持数据源筛选）
    query = {"code": code6}

    if source:
        # 指定数据源
        query["source"] = source
        b = await db["stock_basic_info"].find_one(query, {"_id": 0})
        if not b:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"未找到该股票在数据源 {source} 中的基础信息"
            )
    else:
        # 🔥 未指定数据源，按优先级查询
        source_priority = await _get_cn_source_priority()
        b = None

        for src in source_priority:
            query_with_source = {"code": code6, "source": src}
            b = await db["stock_basic_info"].find_one(query_with_source, {"_id": 0})
            if b:
                logger.info(f"✅ 使用数据源: {src} 查询股票 {code6}")
                break

        # 如果所有数据源都没有，尝试不带 source 条件查询（兼容旧数据）
        if not b:
            b = await db["stock_basic_info"].find_one({"code": code6}, {"_id": 0})
            if b:
                logger.warning(f"⚠️ 使用旧数据（无 source 字段）: {code6}")

        if not b:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="未找到该股票的基础信息")

    # 2. 尝试从 stock_financial_data 获取最新财务指标
    # 🔥 按数据源优先级查询，而不是按时间戳，避免混用不同数据源的数据
    financial_data = None
    try:
        enabled_sources = [src for src in await _get_cn_source_priority() if src in ['tushare', 'akshare', 'baostock']]
        if not enabled_sources:
            enabled_sources = ['tushare', 'akshare', 'baostock']

        # 按数据源优先级查询财务数据
        for data_source in enabled_sources:
            financial_data = await db["stock_financial_data"].find_one(
                {"$or": [{"symbol": code6}, {"code": code6}], "data_source": data_source},
                {"_id": 0},
                sort=[("report_period", -1)]  # 按报告期降序，获取该数据源的最新数据
            )
            if financial_data:
                logger.info(f"✅ 使用数据源 {data_source} 的财务数据 (报告期: {financial_data.get('report_period')})")
                break

        if not financial_data:
            logger.warning(f"⚠️ 未找到 {code6} 的财务数据")
    except Exception as e:
        logger.error(f"获取财务数据失败: {e}")

    # 3. 获取实时PE/PB（优先使用实时计算）
    from tradingagents.dataflows.realtime_metrics import get_pe_pb_with_fallback

    # 在线程池中执行同步的实时计算
    realtime_metrics = await asyncio.to_thread(
        get_pe_pb_with_fallback,
        code6,
        db.client
    )

    # 4. 构建返回数据
    # 🔥 优先使用实时市值，降级到 stock_basic_info 的静态市值
    realtime_market_cap = realtime_metrics.get("market_cap")  # 实时市值（亿元）
    total_mv = realtime_market_cap if realtime_market_cap else b.get("total_mv")

    data = {
        "code": code6,
        "name": b.get("name"),
        "industry": b.get("industry"),  # 行业（如：银行、软件服务）
        "market": b.get("market"),      # 交易所（如：主板、创业板）

        # 板块信息：使用 market 字段（主板/创业板/科创板/北交所等）
        "sector": b.get("market"),

        # 估值指标（优先使用实时计算，降级到 stock_basic_info）
        "pe": realtime_metrics.get("pe") or b.get("pe"),
        "pb": realtime_metrics.get("pb") or b.get("pb"),
        "pe_ttm": realtime_metrics.get("pe_ttm") or b.get("pe_ttm"),
        "pb_mrq": realtime_metrics.get("pb_mrq") or b.get("pb_mrq"),

        # 🔥 市销率（PS）- 动态计算（使用实时市值）
        "ps": None,
        "ps_ttm": None,

        # PE/PB 数据来源标识
        "pe_source": realtime_metrics.get("source", "unknown"),
        "pe_is_realtime": realtime_metrics.get("is_realtime", False),
        "pe_updated_at": realtime_metrics.get("updated_at"),

        # ROE（优先从 stock_financial_data 获取，其次从 stock_basic_info）
        "roe": None,

        # 负债率（从 stock_financial_data 获取）
        "debt_ratio": None,

        # 扩展财务字段
        "dividend_yield": b.get("dividend_yield"),
        "dividend_yield_ttm": b.get("dividend_yield_ttm"),
        "current_ratio": None,
        "quick_ratio": None,
        "cash_ratio": None,
        "gross_margin": None,
        "netprofit_margin": None,
        "revenue": None,
        "revenue_ttm": None,
        "net_income": None,
        "net_profit": None,
        "net_profit_ttm": None,
        "oper_profit": None,
        "total_profit": None,
        "total_assets": None,
        "total_liab": None,
        "total_equity": None,
        "n_cashflow_act": None,
        "report_period": None,
        "report_type": None,
        "ann_date": None,
        "financial_data_source": None,

        # 市值：优先使用实时市值，降级到静态市值
        "total_mv": total_mv,
        "circ_mv": b.get("circ_mv"),

        # 🔥 市值来源标识
        "mv_is_realtime": bool(realtime_market_cap),

        # 交易指标（可能为空）
        "turnover_rate": b.get("turnover_rate"),
        "volume_ratio": b.get("volume_ratio"),

        "updated_at": b.get("updated_at"),
    }

    # 5. 从财务数据中提取 ROE、负债率和计算 PS
    if financial_data:
        data["report_period"] = financial_data.get("report_period")
        data["report_type"] = financial_data.get("report_type")
        data["ann_date"] = financial_data.get("ann_date")
        data["financial_data_source"] = financial_data.get("data_source")

        # ROE（净资产收益率）
        if financial_data.get("financial_indicators"):
            indicators = financial_data["financial_indicators"]
            data["roe"] = indicators.get("roe")
            data["debt_ratio"] = indicators.get("debt_to_assets")
            data["current_ratio"] = indicators.get("current_ratio")
            data["quick_ratio"] = indicators.get("quick_ratio")
            data["cash_ratio"] = indicators.get("cash_ratio")
            data["gross_margin"] = indicators.get("gross_margin")
            data["netprofit_margin"] = indicators.get("netprofit_margin")
            data["dividend_yield"] = data["dividend_yield"] or indicators.get("dividend_yield")

        # 如果 financial_indicators 中没有，尝试从顶层字段获取
        if data["roe"] is None:
            data["roe"] = financial_data.get("roe")
        if data["debt_ratio"] is None:
            data["debt_ratio"] = financial_data.get("debt_to_assets")
        if data["current_ratio"] is None:
            data["current_ratio"] = financial_data.get("current_ratio")
        if data["quick_ratio"] is None:
            data["quick_ratio"] = financial_data.get("quick_ratio")
        if data["cash_ratio"] is None:
            data["cash_ratio"] = financial_data.get("cash_ratio")
        if data["gross_margin"] is None:
            data["gross_margin"] = financial_data.get("gross_margin")
        if data["netprofit_margin"] is None:
            data["netprofit_margin"] = financial_data.get("netprofit_margin")
        if data["dividend_yield"] is None:
            data["dividend_yield"] = financial_data.get("dividend_yield")

        for field in [
            "revenue",
            "revenue_ttm",
            "net_income",
            "net_profit",
            "net_profit_ttm",
            "oper_profit",
            "total_profit",
            "total_assets",
            "total_liab",
            "total_equity",
            "n_cashflow_act",
        ]:
            data[field] = financial_data.get(field)

        # 🔥 动态计算 PS（市销率）- 使用实时市值
        # 优先使用 TTM 营业收入，如果没有则使用单期营业收入
        revenue_ttm = financial_data.get("revenue_ttm")
        revenue = financial_data.get("revenue")
        revenue_for_ps = revenue_ttm if revenue_ttm and revenue_ttm > 0 else revenue

        if revenue_for_ps and revenue_for_ps > 0:
            # 🔥 使用实时市值（如果有），否则使用静态市值
            if total_mv and total_mv > 0:
                # 营业收入单位：元，需要转换为亿元
                revenue_yi = revenue_for_ps / 100000000
                ps_calculated = total_mv / revenue_yi
                data["ps"] = round(ps_calculated, 2)
                data["ps_ttm"] = round(ps_calculated, 2) if revenue_ttm else None

    # 6. 如果财务数据中没有 ROE，使用 stock_basic_info 中的
    if data["roe"] is None:
        data["roe"] = b.get("roe")

    if data["dividend_yield"] is None:
        data["dividend_yield"] = b.get("dividend_yield")

    data = _merge_snapshot_fields_into_fundamentals(data, p0_snapshot)

    return ok(data)


@router.get("/{code}/financials", response_model=dict)
async def get_financials(
    code: str,
    source: Optional[str] = Query(None, description="数据源 (tushare/akshare/baostock)"),
    include_raw: bool = Query(True, description="是否返回 raw_data 分组明细"),
    current_user: dict = Depends(get_current_user)
):
    """
    获取股票最新财务明细。

    主链路接口，返回：
    1. summary：常用财务字段快照
    2. raw_data：按利润表/资产负债表/现金流/财务指标/主营业务分组的原始明细
    3. available_fields：当前文档实际已落库的顶层字段列表
    """
    market, normalized_code = _detect_market_and_code(code)
    if market != 'CN':
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="当前接口仅支持 A 股财务明细")

    db = get_mongo_db()
    base_query: Dict[str, Any] = {"$or": [{"symbol": normalized_code}, {"code": normalized_code}]}

    financial_data = None
    if source:
        query = {**base_query, "data_source": source}
        financial_data = await db["stock_financial_data"].find_one(
            query,
            {"_id": 0},
            sort=[("report_period", -1), ("updated_at", -1)]
        )
    else:
        source_priority = [src for src in await _get_cn_source_priority() if src in ["tushare", "akshare", "baostock"]]
        for preferred_source in source_priority:
            query = {**base_query, "data_source": preferred_source}
            financial_data = await db["stock_financial_data"].find_one(
                query,
                {"_id": 0},
                sort=[("report_period", -1), ("updated_at", -1)]
            )
            if financial_data:
                logger.info("✅ financials 接口使用数据源 %s 查询股票 %s", preferred_source, normalized_code)
                break

        if not financial_data:
            financial_data = await db["stock_financial_data"].find_one(
                base_query,
                {"_id": 0},
                sort=[("report_period", -1), ("updated_at", -1)]
            )
    if not financial_data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "message": "暂无财务数据",
                "suggestion": "请先在「数据同步」页面同步该股票的财务数据",
                "sync_url": "/sync",
            }
        )

    summary = _build_financial_summary(financial_data)
    # P0 因子快照为同步重计算（含外部数据源拉取），放线程池避免阻塞事件循环
    p0_snapshot = await asyncio.to_thread(_get_p0_fundamental_snapshot, normalized_code)
    summary = _merge_snapshot_fields_into_financial_summary(summary, p0_snapshot)
    raw_data = _build_financial_raw_data(financial_data) if include_raw else {}
    available_fields = sorted(
        key for key in financial_data.keys()
        if key not in {"_id", "raw_data"} and financial_data.get(key) is not None
    )

    return ok(data={
        "code": normalized_code,
        "name": financial_data.get("name"),
        "data_source": financial_data.get("data_source"),
        "report_period": p0_snapshot.get("report_period") or financial_data.get("report_period"),
        "report_type": financial_data.get("report_type"),
        "ann_date": financial_data.get("ann_date"),
        "summary": summary,
        "factor_snapshot": p0_snapshot.get("factors") or {},
        "factor_diagnostics": p0_snapshot.get("factor_diagnostics") or {},
        "factor_warnings": p0_snapshot.get("factor_warnings") or {},
        "raw_data": raw_data,
        "available_fields": available_fields,
    })


@router.get("/{code}/kline", response_model=dict)
async def get_kline(
    code: str,
    period: str = "day",
    limit: int = 120,
    adj: str = "none",
    force_refresh: bool = Query(False, description="是否强制刷新（跳过缓存）"),
    current_user: dict = Depends(get_current_user)
):
    """
    获取K线数据（支持A股/港股/美股）

    period: day/week/month/5m/15m/30m/60m
    adj: none/qfq/hfq
    force_refresh: 是否强制刷新（跳过缓存）

    🔥 新增功能：当天实时K线数据
    - 交易时间内（09:30-15:00）：从 market_quotes 获取实时数据
    - 收盘后：检查历史数据是否有当天数据，没有则从 market_quotes 获取
    """
    import logging
    from datetime import datetime, timedelta, time as dtime
    from zoneinfo import ZoneInfo
    logger = logging.getLogger(__name__)

    valid_periods = {"day","week","month","5m","15m","30m","60m"}
    if period not in valid_periods:
        raise HTTPException(status_code=400, detail=f"不支持的period: {period}")

    # 检测市场类型
    market, normalized_code = _detect_market_and_code(code)

    # 港股和美股：使用新服务
    if market in ['HK', 'US']:
        from app.services.foreign_stock_service import ForeignStockService

        db = get_mongo_db()  # 不需要 await，直接返回数据库对象
        service = ForeignStockService(db=db)

        try:
            kline_data = await service.get_kline(market, normalized_code, period, limit, force_refresh)
            return ok(data={
                'code': normalized_code,
                'period': period,
                'items': kline_data,
                'source': 'cache_or_api'
            })
        except Exception as e:
            logger.error(f"获取{market}股票{code}K线数据失败: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"获取K线数据失败: {str(e)}"
            )

    # A股：使用现有逻辑
    code_padded = normalized_code

    if _is_cn_etf_code(code_padded):
        db = get_mongo_db()
        rows = await db["etf_daily_quotes"].find(
            {"code": code_padded},
            {"_id": 0}
        ).sort("trade_date", 1).to_list(length=2000)

        if not rows:
            etf_exists = await db["etf_basic_info"].find_one({"code": code_padded}, {"_id": 1})
            if not etf_exists:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="未找到该 ETF 的K线数据")
            return ok(data={
                "code": code_padded,
                "period": period,
                "items": [],
                "source": "etf_daily_quotes"
            })

        if period not in {"day", "week", "month"}:
            period = "day"

        items = _aggregate_etf_kline_rows(rows, period, limit)
        return ok(data={
            "code": code_padded,
            "period": period,
            "items": items,
            "source": "etf_daily_quotes"
        })

    adj_norm = None if adj in (None, "none", "", "null") else adj
    items = None
    source = None

    # 周期映射：前端 -> MongoDB
    period_map = {
        "day": "daily",
        "week": "weekly",
        "month": "monthly",
        "5m": "5min",
        "15m": "15min",
        "30m": "30min",
        "60m": "60min"
    }
    mongodb_period = period_map.get(period, "daily")

    # 获取当前时间（北京时间）
    from app.core.config import settings
    tz = ZoneInfo(settings.TIMEZONE)
    now = datetime.now(tz)
    today_str_yyyymmdd = now.strftime("%Y%m%d")  # 格式：20251028（用于查询）
    today_str_formatted = now.strftime("%Y-%m-%d")  # 格式：2025-10-28（用于返回）

    # 1. 优先检查本地数据源（stock_historical_data 集合）
    try:
        from app.core.data_source_priority import get_preferred_data_source_async
        preferred_source = await get_preferred_data_source_async(market_category="a_shares")

        if preferred_source == 'local':
            logger.info(f"🔍 优先数据源为 local，尝试从 stock_daily_quotes 获取 K 线数据")
            db = get_mongo_db()
            collection = db.stock_daily_quotes

            # 查询本地历史数据（异步迭代）
            cursor = collection.find(
                {"symbol": code_padded, "data_source": "local", "period": period}
            ).sort("trade_date", 1).limit(limit)

            # 使用异步迭代获取数据
            local_klines = []
            async for kline in cursor:
                local_klines.append(kline)

            if local_klines:
                items = []
                for kline in local_klines:
                    items.append({
                        "time": kline.get("trade_date"),
                        "open": float(kline.get("open", 0)),
                        "high": float(kline.get("high", 0)),
                        "low": float(kline.get("low", 0)),
                        "close": float(kline.get("close", 0)),
                        "volume": float(kline.get("volume", 0)),
                        "amount": float(kline.get("amount", 0)) if "amount" in kline else None,
                    })
                source = "local"
                logger.info(f"✅ 从本地数据源获取到 {len(items)} 条 K 线数据")
    except Exception as e:
        logger.warning(f"⚠️ 本地数据源获取 K 线失败: {e}")

    # 2. 如果本地数据源没有数据，尝试从 MongoDB 缓存获取
    if not items:
        try:
            from tradingagents.dataflows.cache.mongodb_cache_adapter import get_mongodb_cache_adapter
            adapter = get_mongodb_cache_adapter()

            # 计算日期范围
            end_date = now.strftime("%Y-%m-%d")
            start_date = (now - timedelta(days=limit * 2)).strftime("%Y-%m-%d")

            logger.info(f"🔍 尝试从 MongoDB 缓存获取 K 线数据: {code_padded}, period={period} (MongoDB: {mongodb_period}), limit={limit}")
            df = adapter.get_historical_data(code_padded, start_date, end_date, period=mongodb_period)

            if df is not None and not df.empty:
                # 转换 DataFrame 为列表格式
                items = []
                for _, row in df.tail(limit).iterrows():
                    items.append({
                        "time": row.get("trade_date", row.get("date", "")),  # 前端期望 time 字段
                        "open": float(row.get("open", 0)),
                        "high": float(row.get("high", 0)),
                        "low": float(row.get("low", 0)),
                        "close": float(row.get("close", 0)),
                        "volume": float(row.get("volume", row.get("vol", 0))),
                        "amount": float(row.get("amount", 0)) if "amount" in row else None,
                    })
                source = "mongodb"
                logger.info(f"✅ 从 MongoDB 缓存获取到 {len(items)} 条 K 线数据")
        except Exception as e:
            logger.warning(f"⚠️ MongoDB 缓存获取 K 线失败: {e}")

    # 3. 如果本地和缓存都没有数据，降级到外部 API（带超时保护）
    if not items:
        logger.info(f"📡 本地和缓存都无数据，降级到外部 API")
        try:
            import asyncio
            from app.services.data_sources.manager import DataSourceManager

            mgr = DataSourceManager()
            # 添加 10 秒超时保护
            items, source = await asyncio.wait_for(
                asyncio.to_thread(mgr.get_kline_with_fallback, code_padded, period, limit, adj_norm),
                timeout=10.0
            )
        except asyncio.TimeoutError:
            logger.error(f"❌ 外部 API 获取 K 线超时（10秒）")
            raise HTTPException(status_code=504, detail="获取K线数据超时，请稍后重试")
        except Exception as e:
            logger.error(f"❌ 外部 API 获取 K 线失败: {e}")
            raise HTTPException(status_code=500, detail=f"获取K线数据失败: {str(e)}")

    # 🔥 4. 检查是否需要添加当天实时数据（仅针对日线）
    if period == "day" and items:
        try:
            # 检查历史数据中是否已有当天的数据（支持两种日期格式）
            has_today_data = any(
                item.get("time") in [today_str_yyyymmdd, today_str_formatted]
                for item in items
            )

            # 判断是否在交易时间内或收盘后缓冲期
            current_time = now.time()
            is_weekday = now.weekday() < 5  # 周一到周五

            # 交易时间：9:30-11:30, 13:00-15:00
            # 收盘后缓冲期：15:00-15:30（确保获取到收盘价）
            is_trading_time = (
                is_weekday and (
                    (dtime(9, 30) <= current_time <= dtime(11, 30)) or
                    (dtime(13, 0) <= current_time <= dtime(15, 30))
                )
            )

            # 🔥 只在交易时间或收盘后缓冲期内才添加实时数据
            # 非交易日（周末、节假日）不添加实时数据
            should_fetch_realtime = is_trading_time

            if should_fetch_realtime:
                logger.info(f"🔥 尝试从 market_quotes 获取当天实时数据: {code_padded} (交易时间: {is_trading_time}, 已有当天数据: {has_today_data})")

                db = get_mongo_db()
                market_quotes_coll = db["market_quotes"]

                # 查询当天的实时行情
                realtime_quote = await market_quotes_coll.find_one({"code": code_padded})

                if realtime_quote:
                    # 🔥 构造当天的K线数据（使用统一的日期格式 YYYY-MM-DD）
                    today_kline = {
                        "time": today_str_formatted,  # 🔥 使用 YYYY-MM-DD 格式，与历史数据保持一致
                        "open": float(realtime_quote.get("open", 0)),
                        "high": float(realtime_quote.get("high", 0)),
                        "low": float(realtime_quote.get("low", 0)),
                        "close": float(realtime_quote.get("close", 0)),
                        "volume": float(realtime_quote.get("volume", 0)),
                        "amount": float(realtime_quote.get("amount", 0)),
                    }

                    # 如果历史数据中已有当天数据，替换；否则追加
                    if has_today_data:
                        # 替换最后一条数据（假设最后一条是当天的）
                        items[-1] = today_kline
                        logger.info(f"✅ 替换当天K线数据: {code_padded}")
                    else:
                        # 追加到末尾
                        items.append(today_kline)
                        logger.info(f"✅ 追加当天K线数据: {code_padded}")

                    source = f"{source}+market_quotes"
                else:
                    logger.warning(f"⚠️ market_quotes 中未找到当天数据: {code_padded}")
        except Exception as e:
            logger.warning(f"⚠️ 获取当天实时数据失败（忽略）: {e}")

    data = {
        "code": code_padded,
        "period": period,
        "limit": limit,
        "adj": adj if adj else "none",
        "source": source,
        "items": items or []
    }
    return ok(data)


@router.get("/{code}/news", response_model=dict)
async def get_news(code: str, days: int = 30, limit: int = 50, include_announcements: bool = True, current_user: dict = Depends(get_current_user)):
    """获取新闻与公告（支持A股、港股、美股）"""
    from app.services.foreign_stock_service import ForeignStockService
    from app.services.news_data_service import get_news_data_service, NewsQueryParams

    # 检测股票类型
    market, normalized_code = _detect_market_and_code(code)

    if market == 'US':
        # 美股：使用 ForeignStockService
        service = ForeignStockService()
        result = await service.get_us_news(normalized_code, days=days, limit=limit)
        return ok(result)
    elif market == 'HK':
        # 港股：使用 ForeignStockService（含 yfinance / finnhub / akshare 回退）
        service = ForeignStockService()
        result = await service.get_hk_news(normalized_code, days=days, limit=limit)
        return ok(result)
    else:
        # A股：直接调用同步服务的查询方法（包含智能回退逻辑）
        try:
            logger.info(f"=" * 80)
            logger.info(f"📰 开始获取新闻: code={code}, normalized_code={normalized_code}, days={days}, limit={limit}")

            # 直接使用 news_data 路由的查询逻辑
            from app.services.news_data_service import get_news_data_service, NewsQueryParams
            from datetime import datetime, timedelta
            from app.worker.akshare_sync_service import get_akshare_sync_service

            service = await get_news_data_service()
            sync_service = await get_akshare_sync_service()

            # 计算时间范围
            hours_back = days * 24

            # 🔥 不设置 start_time 限制，直接查询最新的 N 条新闻
            # 因为数据库中的新闻可能不是最近几天的，而是历史数据
            params = NewsQueryParams(
                symbol=normalized_code,
                limit=limit,
                sort_by="publish_time",
                sort_order=-1
            )

            logger.info(f"🔍 查询参数: symbol={params.symbol}, limit={params.limit} (不限制时间范围)")

            # 1. 先从数据库查询
            logger.info(f"📊 步骤1: 从数据库查询新闻...")
            news_list = await service.query_news(params)
            logger.info(f"📊 数据库查询结果: 返回 {len(news_list)} 条新闻")

            data_source = "database"

            # 2. 如果数据库没有数据，调用同步服务
            if not news_list:
                logger.info(f"⚠️ 数据库无新闻数据，调用同步服务获取: {normalized_code}")
                try:
                    # 🔥 调用同步服务，传入单个股票代码列表
                    logger.info(f"📡 步骤2: 调用同步服务...")
                    await sync_service.sync_news_data(
                        symbols=[normalized_code],
                        max_news_per_stock=limit,
                        force_update=False,
                        favorites_only=False
                    )

                    # 重新查询
                    logger.info(f"🔄 步骤3: 重新从数据库查询...")
                    news_list = await service.query_news(params)
                    logger.info(f"📊 重新查询结果: 返回 {len(news_list)} 条新闻")
                    data_source = "realtime"

                except Exception as e:
                    logger.error(f"❌ 同步服务异常: {e}", exc_info=True)

            # 转换为旧格式（兼容前端）
            logger.info(f"🔄 步骤4: 转换数据格式...")
            items = []
            for news in news_list:
                # 🔥 将 datetime 对象转换为 ISO 字符串
                publish_time = news.get("publish_time", "")
                if isinstance(publish_time, datetime):
                    publish_time = publish_time.isoformat()

                items.append({
                    "title": news.get("title", ""),
                    "source": news.get("source", ""),
                    "time": publish_time,
                    "url": news.get("url", ""),
                    "type": "news",
                    "content": news.get("content", ""),
                    "summary": news.get("summary", "")
                })

            logger.info(f"✅ 转换完成: {len(items)} 条新闻")

            data = {
                "code": normalized_code,
                "days": days,
                "limit": limit,
                "include_announcements": include_announcements,
                "source": data_source,
                "items": items
            }

            logger.info(f"📤 最终返回: source={data_source}, items_count={len(items)}")
            logger.info(f"=" * 80)
            return ok(data)

        except Exception as e:
            logger.error(f"❌ 获取新闻失败: {e}", exc_info=True)
            data = {
                "code": normalized_code,
                "days": days,
                "limit": limit,
                "include_announcements": include_announcements,
                "source": None,
                "items": []
            }
            return ok(data)

