"""
ETF 数据同步服务

使用项目统一的数据源配置（get_enabled_data_sources_async），按优先级依次尝试同步。
优先级最高的先调用，同步成功则结束；失败则尝试下一优先级。
- etf_basic_info：ETF 基础信息（代码、名称、规模、跟踪指数等）
- etf_daily_quotes：ETF 日线行情
"""

import asyncio
import logging
from datetime import datetime, timedelta
from functools import partial
from typing import Dict, Any, List, Optional, Callable

from app.core.config import settings
from app.core.database import get_mongo_db
from app.core.data_source_priority import get_enabled_data_sources_async
from app.services.data_sources.qmt_adapter import QMTAdapter

logger = logging.getLogger(__name__)

# 集合名（与设计文档一致）
ETF_BASIC_INFO_COLLECTION = "etf_basic_info"
ETF_DAILY_QUOTES_COLLECTION = "etf_daily_quotes"
DEFAULT_SOURCE_PRIORITY = ["akshare"]  # 统一配置获取失败时的默认值
ETF_FULL_SYNC_FALLBACK_START = "19900101"

ETF_SH_PREFIXES = ("50", "51", "52", "56", "58")
ETF_SZ_PREFIXES = ("15", "16", "18")
ETF_BJ_PREFIXES = ("89",)  # 北交所 ETF 前缀


def _is_missing(value: Any) -> bool:
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


def _safe_float(value: Any) -> Optional[float]:
    if _is_missing(value):
        return None
    try:
        if isinstance(value, str):
            cleaned = value.strip().replace(",", "").replace("%", "")
            if cleaned == "":
                return None
            return float(cleaned)
        return float(value)
    except (TypeError, ValueError):
        return None


def _normalize_date_text(value: Any) -> Optional[str]:
    if _is_missing(value):
        return None
    if hasattr(value, "strftime"):
        return value.strftime("%Y-%m-%d")

    text = str(value).strip()
    if len(text) == 8 and text.isdigit():
        return f"{text[:4]}-{text[4:6]}-{text[6:8]}"
    if len(text) >= 10:
        return text[:10].replace("/", "-")
    return text or None


def _calculate_nav_change(latest_unit_nav: Optional[float], previous_unit_nav: Optional[float]) -> tuple[Optional[float], Optional[float]]:
    if latest_unit_nav is None or previous_unit_nav in (None, 0):
        return None, None
    try:
        change_value = round(float(latest_unit_nav) - float(previous_unit_nav), 4)
        growth_rate = round(change_value / float(previous_unit_nav) * 100, 4)
        return change_value, growth_rate
    except (TypeError, ValueError, ZeroDivisionError):
        return None, None


def _needs_tushare_backfill(existing: Optional[Dict[str, Any]]) -> bool:
    if not existing:
        return False
    required_fields = ("unit_nav", "accum_nav", "latest_nav_date", "fund_share", "fund_share_date")
    return any(_is_missing(existing.get(field)) for field in required_fields)


def _normalize_etf_code(s: str) -> str:
    """标准化 ETF 代码为 6 位"""
    if not s:
        return ""
    digits = "".join(c for c in str(s) if c.isdigit())
    return digits.zfill(6)[-6:] if digits and len(digits) <= 6 else (digits[-6:] if digits else "")


def _get_full_symbol(code: str) -> str:
    """根据代码前缀生成完整代码"""
    if not code or len(code) != 6:
        return ""
    if code.startswith(ETF_SH_PREFIXES):
        return f"{code}.SH"
    if code.startswith(ETF_SZ_PREFIXES):
        return f"{code}.SZ"
    if code.startswith(ETF_BJ_PREFIXES):
        return f"{code}.BJ"
    return f"{code}.SH"


def _is_etf_code(code: str) -> bool:
    return bool(code) and len(code) == 6 and code.startswith(ETF_SH_PREFIXES + ETF_SZ_PREFIXES + ETF_BJ_PREFIXES)


def _normalize_source_name(name: str) -> str:
    """将数据源名称规范化为小写（如 AKShare -> akshare）"""
    return str(name or "").strip().lower()


def _fetch_etf_spot_list_akshare() -> List[Dict[str, Any]]:
    """从 AKShare 获取 ETF 实时行情列表（阻塞调用）"""
    try:
        import akshare as ak
        df = ak.fund_etf_spot_em()
        if df is None or df.empty:
            return []

        code_col = "代码" if "代码" in df.columns else "基金代码"
        name_col = "名称" if "名称" in df.columns else "基金名称"

        rows = []
        for _, r in df.iterrows():
            raw_code = str(r.get(code_col, "")).strip()
            code = _normalize_etf_code(raw_code)
            if not code or len(code) != 6:
                continue
            if not _is_etf_code(code):
                continue

            full_symbol = _get_full_symbol(code)
            rows.append({
                "code": code,
                "name": str(r.get(name_col, r.get("基金名称", ""))),
                "full_symbol": full_symbol,
                "latest_price": r.get("最新价", r.get("最新-单位净值", r.get("当前-单位净值"))),
                "change_pct": r.get("涨跌幅", r.get("增长率")),
                "volume": r.get("成交量"),
                "amount": r.get("成交额"),
                "fund_scale": r.get("规模"),
                "track_index": r.get("跟踪指数", ""),
                "fund_type": r.get("基金类型", ""),
            })
        return rows
    except Exception as e:
        logger.warning(f"AKShare fund_etf_spot_em 获取失败: {e}")
        return []


def _fetch_etf_valuation_map_akshare() -> Dict[str, Dict[str, Any]]:
    """从 AKShare 获取 ETF 净值、折溢价和申赎状态映射。"""
    try:
        import akshare as ak

        valuation_df = ak.fund_etf_fund_daily_em()
        if valuation_df is None or valuation_df.empty:
            return {}

        code_col = "基金代码" if "基金代码" in valuation_df.columns else "代码"
        valuation_df["code_clean"] = valuation_df[code_col].astype(str).str.extract(r"(\d{6})", expand=False).fillna("")
        unit_nav_col = next((col for col in valuation_df.columns if str(col).endswith("单位净值")), None)
        accum_nav_col = next((col for col in valuation_df.columns if str(col).endswith("累计净值")), None)

        result: Dict[str, Dict[str, Any]] = {}
        for _, row in valuation_df.iterrows():
            code = _normalize_etf_code(row.get("code_clean"))
            if not _is_etf_code(code):
                continue
            result[code] = {
                "unit_nav": row.get(unit_nav_col) if unit_nav_col else None,
                "accum_nav": row.get(accum_nav_col) if accum_nav_col else None,
                "nav_change_value": row.get("增长值"),
                "nav_growth_rate": row.get("增长率"),
                "market_price": row.get("市价"),
                "premium_discount_rate": row.get("折价率"),
                "fund_type": row.get("类型"),
            }

        return result
    except Exception as e:
        logger.warning(f"AKShare ETF 估值映射获取失败: {e}")
        return {}


def _get_tushare_pro_api():
    """获取 Tushare pro_api（复用单例，避免重复连接）"""
    try:
        from tradingagents.dataflows.providers.china.tushare import get_tushare_provider
        provider = get_tushare_provider()
        if provider and provider.api:
            return provider.api
    except Exception as e:
        logger.warning(f"Tushare 连接失败: {e}")
    return None


def _fetch_etf_spot_list_tushare() -> List[Dict[str, Any]]:
    """从 Tushare fund_basic(market='E') 获取 ETF 基础信息列表（阻塞调用）"""
    pro = _get_tushare_pro_api()
    if pro is None:
        return []
    try:
        df = pro.fund_basic(market="E", status="L")
        if df is None or df.empty:
            return []

        rows = []
        for _, r in df.iterrows():
            ts_code = str(r.get("ts_code", "")).strip()
            code = _normalize_etf_code(ts_code)
            if not code or len(code) != 6:
                continue
            if not _is_etf_code(code):
                continue

            full_symbol = ts_code if "." in ts_code else _get_full_symbol(code)
            rows.append({
                "code": code,
                "name": str(r.get("name", "")),
                "full_symbol": full_symbol,
                "latest_price": None,
                "change_pct": None,
                "volume": None,
                "amount": None,
                "fund_scale": r.get("issue_amount"),
                "track_index": str(r.get("benchmark", "") or ""),
                "fund_type": str(r.get("fund_type", "ETF") or "ETF"),
                "management": r.get("management"),
                "custodian": r.get("custodian"),
                "management_fee": r.get("m_fee"),
                "custodian_fee": r.get("c_fee"),
                "found_date": r.get("found_date"),
                "list_date": r.get("list_date"),
                "issue_date": r.get("issue_date"),
                "due_date": r.get("due_date"),
                "invest_type": r.get("invest_type"),
                "status": r.get("status"),
                "min_amount": r.get("min_amount"),
                "purchase_start_date": r.get("purc_startdate"),
                "redemption_start_date": r.get("redm_startdate"),
            })
        return rows
    except Exception as e:
        logger.warning(f"Tushare fund_basic 获取失败: {e}")
        return []


def _fetch_etf_nav_map_tushare(target_codes: Optional[set[str]] = None, recent_days: int = 15) -> Dict[str, Dict[str, Any]]:
    """从 Tushare fund_nav 批量获取 ETF 最新净值映射。"""
    pro = _get_tushare_pro_api()
    if pro is None:
        return {}

    try:
        records_by_code: Dict[str, List[Dict[str, Any]]] = {}
        pending_codes = set(target_codes or [])
        end_dt = datetime.now()

        for offset in range(recent_days):
            nav_date = (end_dt - timedelta(days=offset)).strftime("%Y%m%d")
            df = pro.fund_nav(nav_date=nav_date, market="E")
            if df is None or df.empty:
                continue

            for _, row in df.iterrows():
                ts_code = str(row.get("ts_code", "")).strip()
                code = _normalize_etf_code(ts_code)
                if not _is_etf_code(code):
                    continue
                if pending_codes and code not in pending_codes:
                    continue

                bucket = records_by_code.setdefault(code, [])
                if len(bucket) < 2:
                    bucket.append(row.to_dict())

            if pending_codes and all(len(records_by_code.get(code, [])) >= 2 for code in pending_codes):
                break

        result: Dict[str, Dict[str, Any]] = {}
        for code, rows in records_by_code.items():
            rows.sort(
                key=lambda item: (
                    str(item.get("nav_date") or ""),
                    str(item.get("ann_date") or "")
                ),
                reverse=True
            )
            latest = rows[0]
            previous = rows[1] if len(rows) > 1 else None

            latest_unit_nav = _safe_float(latest.get("unit_nav"))
            previous_unit_nav = _safe_float(previous.get("unit_nav")) if previous else None
            nav_change_value, nav_growth_rate = _calculate_nav_change(latest_unit_nav, previous_unit_nav)

            result[code] = {
                "unit_nav": latest_unit_nav,
                "accum_nav": _safe_float(latest.get("accum_nav")),
                "latest_nav_date": _normalize_date_text(latest.get("nav_date")),
                "latest_nav_ann_date": _normalize_date_text(latest.get("ann_date")),
                "accum_div": _safe_float(latest.get("accum_div")),
                "net_asset": _safe_float(latest.get("net_asset")),
                "total_netasset": _safe_float(latest.get("total_netasset")),
                "adj_nav": _safe_float(latest.get("adj_nav")),
                "nav_change_value": nav_change_value,
                "nav_growth_rate": nav_growth_rate,
            }

        return result
    except Exception as e:
        logger.warning(f"Tushare fund_nav 获取失败: {e}")
        return {}


def _fetch_etf_share_map_tushare(target_codes: Optional[set[str]] = None, recent_days: int = 30) -> Dict[str, Dict[str, Any]]:
    """从 Tushare fund_share 批量获取 ETF 最新份额映射。"""
    pro = _get_tushare_pro_api()
    if pro is None:
        return {}

    try:
        target_codes = set(target_codes or [])
        end_dt = datetime.now()
        start_dt = end_dt - timedelta(days=recent_days)
        rows: List[Dict[str, Any]] = []

        for market in ("SH", "SZ", "BJ"):
            df = pro.fund_share(
                market=market,
                start_date=start_dt.strftime("%Y%m%d"),
                end_date=end_dt.strftime("%Y%m%d")
            )
            if df is None or df.empty:
                continue
            rows.extend(df.to_dict("records"))

        if not rows:
            return {}

        latest_by_code: Dict[str, Dict[str, Any]] = {}
        for row in rows:
            ts_code = str(row.get("ts_code", "")).strip()
            code = _normalize_etf_code(ts_code)
            if not _is_etf_code(code):
                continue
            if target_codes and code not in target_codes:
                continue

            existing = latest_by_code.get(code)
            trade_date = str(row.get("trade_date") or "")
            if not existing or trade_date > str(existing.get("trade_date") or ""):
                latest_by_code[code] = row

        return {
            code: {
                "fund_share": _safe_float(row.get("fd_share")),
                "fund_share_date": _normalize_date_text(row.get("trade_date")),
            }
            for code, row in latest_by_code.items()
        }
    except Exception as e:
        logger.warning(f"Tushare fund_share 获取失败: {e}")
        return {}


def _fetch_etf_hist_tushare(symbol: str, start_date: str, end_date: str) -> List[Dict[str, Any]]:
    """从 Tushare fund_daily 获取单只 ETF 历史日线（阻塞调用）"""
    pro = _get_tushare_pro_api()
    if pro is None:
        return []
    try:
        code = _normalize_etf_code(symbol)
        if not code:
            return []
        ts_code = _get_full_symbol(code)
        if not ts_code:
            ts_code = f"{code}.SH"

        df = pro.fund_daily(ts_code=ts_code, start_date=start_date, end_date=end_date)
        if df is None or df.empty:
            return []

        full_symbol = _get_full_symbol(code)
        records = []
        for _, r in df.iterrows():
            trade_date = r.get("trade_date")
            if trade_date is None:
                continue
            trade_date = str(trade_date)
            if len(trade_date) == 8:
                trade_date = f"{trade_date[:4]}-{trade_date[4:6]}-{trade_date[6:8]}"

            vol = r.get("vol")
            amt = r.get("amount")
            if amt is not None and amt != "":
                try:
                    amt = float(amt) * 1000
                except (TypeError, ValueError):
                    pass

            records.append({
                "symbol": code,
                "code": code,
                "full_symbol": full_symbol,
                "trade_date": trade_date,
                "open": r.get("open"),
                "high": r.get("high"),
                "low": r.get("low"),
                "close": r.get("close"),
                "volume": vol,
                "amount": amt,
                "pct_chg": r.get("pct_chg"),
                "data_source": "tushare",
            })
        return records
    except Exception as e:
        logger.warning(f"Tushare fund_daily {symbol} 获取失败: {e}")
        return []


def _fetch_etf_hist_akshare(symbol: str, start_date: str, end_date: str) -> List[Dict[str, Any]]:
    """从 AKShare 获取单只 ETF 历史日线（阻塞调用）"""
    try:
        import akshare as ak
        code = _normalize_etf_code(symbol)
        if not code:
            return []
        df = ak.fund_etf_hist_em(symbol=code, period="daily", start_date=start_date, end_date=end_date)
        if df is None or df.empty:
            return []

        # 列名兼容：日期/date、开盘/open、收盘/close、最高/high、最低/low、成交量/volume、成交额/amount、涨跌幅
        date_col = "日期" if "日期" in df.columns else "date"
        open_col = "开盘" if "开盘" in df.columns else "open"
        high_col = "最高" if "最高" in df.columns else "high"
        low_col = "最低" if "最低" in df.columns else "low"
        close_col = "收盘" if "收盘" in df.columns else "close"
        vol_col = "成交量" if "成交量" in df.columns else "volume"
        amt_col = "成交额" if "成交额" in df.columns else "amount"
        pct_col = "涨跌幅" if "涨跌幅" in df.columns else "增长率"
        nav_col = "单位净值" if "单位净值" in df.columns else None
        accum_col = "累计净值" if "累计净值" in df.columns else None

        records = []
        full_symbol = _get_full_symbol(code)
        for _, r in df.iterrows():
            trade_date = r.get(date_col)
            if trade_date is None:
                continue
            if hasattr(trade_date, "strftime"):
                trade_date = trade_date.strftime("%Y-%m-%d")
            else:
                trade_date = str(trade_date)[:10].replace("/", "-")

            rec = {
                "symbol": code,
                "code": code,  # 与 stock_daily_quotes 一致，便于 UnifiedStockService 查询
                "full_symbol": full_symbol,
                "trade_date": trade_date,
                "open": r.get(open_col),
                "high": r.get(high_col),
                "low": r.get(low_col),
                "close": r.get(close_col),
                "volume": r.get(vol_col),
                "amount": r.get(amt_col),
                "pct_chg": r.get(pct_col),
                "data_source": "akshare",  # 由 sync 方法按实际 source 覆盖
            }
            if nav_col and nav_col in r:
                rec["unit_nav"] = r.get(nav_col)
            if accum_col and accum_col in r:
                rec["accum_nav"] = r.get(accum_col)
            records.append(rec)
        return records
    except Exception as e:
        logger.warning(f"AKShare fund_etf_hist_em {symbol} 获取失败: {e}")
        return []


def _fetch_etf_spot_list_qmt() -> List[Dict[str, Any]]:
    """从 QMT 获取 ETF 基础信息与近实时快照"""
    try:
        adapter = QMTAdapter()
        if not adapter.is_available():
            return []

        df = adapter.get_etf_list()
        if df is None or df.empty:
            return []

        quotes = adapter.get_realtime_quotes() or {}
        rows = []
        for _, r in df.iterrows():
            code = _normalize_etf_code(r.get("code") or r.get("symbol") or "")
            if not _is_etf_code(code):
                continue
            quote = quotes.get(code, {})
            rows.append({
                "code": code,
                "name": str(r.get("name", "") or code),
                "full_symbol": str(r.get("ts_code", "") or _get_full_symbol(code)),
                "latest_price": quote.get("close"),
                "change_pct": quote.get("pct_chg"),
                "volume": None,
                "amount": quote.get("amount"),
                "fund_scale": None,
                "track_index": "",
                "fund_type": str(r.get("fund_type", "ETF") or "ETF"),
            })
        return rows
    except Exception as e:
        logger.warning(f"QMT ETF 列表获取失败: {e}")
        return []


def _fetch_etf_hist_qmt(symbol: str, start_date: str, end_date: str) -> List[Dict[str, Any]]:
    """从 QMT 获取单只 ETF 历史日线"""
    try:
        adapter = QMTAdapter()
        if not adapter.is_available():
            return []

        code = _normalize_etf_code(symbol)
        if not _is_etf_code(code):
            return []

        start_dt = datetime.strptime(start_date, "%Y%m%d")
        end_dt = datetime.strptime(end_date, "%Y%m%d")
        limit = max((end_dt - start_dt).days + 5, 30)
        items = adapter.get_kline(code, period="day", limit=limit)
        if not items:
            return []

        records = []
        previous_close = None
        for item in items:
            trade_date = str(item.get("date") or item.get("time") or "")
            if not trade_date:
                continue
            if len(trade_date) >= 10:
                normalized_date = trade_date[:10].replace("/", "-")
            elif len(trade_date) == 8 and trade_date.isdigit():
                normalized_date = f"{trade_date[:4]}-{trade_date[4:6]}-{trade_date[6:8]}"
            else:
                normalized_date = trade_date

            compact_date = normalized_date.replace("-", "")
            if compact_date < start_date or compact_date > end_date:
                continue

            close_value = item.get("close")
            record = {
                "symbol": code,
                "code": code,
                "full_symbol": _get_full_symbol(code),
                "trade_date": normalized_date,
                "open": item.get("open"),
                "high": item.get("high"),
                "low": item.get("low"),
                "close": close_value,
                "volume": item.get("volume"),
                "amount": item.get("amount"),
                "pct_chg": None,
                "data_source": "qmt",
            }

            if previous_close not in (None, 0) and close_value is not None:
                try:
                    record["pct_chg"] = round((float(close_value) - float(previous_close)) / float(previous_close) * 100, 4)
                except (TypeError, ValueError, ZeroDivisionError):
                    record["pct_chg"] = None

            previous_close = close_value if close_value is not None else previous_close
            records.append(record)
        return records
    except Exception as e:
        logger.warning(f"QMT ETF 历史日线获取失败 {symbol}: {e}")
        return []


# 数据源与 fetcher 映射（可扩展 Tushare 等）
_FETCH_BASIC: Dict[str, Callable] = {
    "akshare": _fetch_etf_spot_list_akshare,
    "tushare": _fetch_etf_spot_list_tushare,
    "qmt": _fetch_etf_spot_list_qmt,
}
_FETCH_HIST: Dict[str, Callable[[str, str, str], List[Dict[str, Any]]]] = {
    "akshare": _fetch_etf_hist_akshare,
    "tushare": _fetch_etf_hist_tushare,
    "qmt": _fetch_etf_hist_qmt,
}


class EtfSyncService:
    """ETF 数据同步服务（按数据源优先级依次尝试）"""

    def __init__(self):
        self.db = None
        self.batch_size = 50
        self.rate_limit_delay = 0.3
        self.item_timeout_seconds = settings.ETF_SYNC_ITEM_TIMEOUT_SECONDS

    @staticmethod
    def _find_index_name(index_info: Dict[str, Any], keys: List[tuple[str, int]]) -> Optional[str]:
        expected_keys = tuple(keys)
        for index_name, spec in index_info.items():
            if tuple(spec.get("key", [])) == expected_keys:
                return index_name
        return None

    async def _find_duplicate_key_sample(self, collection, keys: List[tuple[str, int]]) -> Optional[Dict[str, Any]]:
        group_id = {field: f"${field}" for field, _ in keys}
        duplicates = await collection.aggregate(
            [
                {"$group": {"_id": group_id, "count": {"$sum": 1}}},
                {"$match": {"count": {"$gt": 1}}},
                {"$limit": 1},
            ]
        ).to_list(length=1)
        return duplicates[0] if duplicates else None

    async def _ensure_unique_index(self, collection, collection_name: str, keys: List[tuple[str, int]]) -> None:
        index_info = await collection.index_information()
        index_name = self._find_index_name(index_info, keys)

        if index_name and index_info[index_name].get("unique"):
            return

        duplicate_sample = await self._find_duplicate_key_sample(collection, keys)
        if duplicate_sample:
            logger.warning(
                f"⚠️ {collection_name} 存在重复数据，暂时无法升级唯一索引: "
                f"keys={list(duplicate_sample.get('_id', {}).items())}, count={duplicate_sample.get('count')}"
            )
            return

        if index_name:
            await collection.drop_index(index_name)
            logger.info(
                f"🧹 已移除 {collection_name} 的旧非唯一索引，准备升级为唯一索引: {index_name}"
            )

        await collection.create_index(keys, unique=True, background=True)
        logger.info(f"✅ 已确保 {collection_name} 唯一索引: {keys}")

    async def _ensure_indexes(self):
        """确保 ETF 基础信息和日线集合具备关键索引。"""
        try:
            if self.db is None:
                self.db = get_mongo_db()

            basic_collection = self.db[ETF_BASIC_INFO_COLLECTION]
            daily_collection = self.db[ETF_DAILY_QUOTES_COLLECTION]

            logger.info("📊 检查并创建 ETF 集合索引...")

            await self._ensure_unique_index(
                basic_collection,
                ETF_BASIC_INFO_COLLECTION,
                [("code", 1), ("source", 1)],
            )
            await basic_collection.create_index([("code", 1)], background=True)

            await self._ensure_unique_index(
                daily_collection,
                ETF_DAILY_QUOTES_COLLECTION,
                [("code", 1), ("trade_date", -1)],
            )
            await daily_collection.create_index([("symbol", 1), ("trade_date", -1)], background=True)

            logger.info("✅ ETF 集合索引检查完成")
        except Exception as e:
            logger.warning(f"⚠️ ETF 集合索引检查/创建失败（不阻塞主流程）: {e}")

    @staticmethod
    def _calculate_stage_progress(stage_start: int, stage_end: int, processed_items: int, total_items: int) -> int:
        """按阶段区间计算整体进度，确保进度单调递增。"""
        stage_start = max(0, min(100, stage_start))
        stage_end = max(stage_start, min(100, stage_end))
        if total_items <= 0:
            return stage_start

        ratio = min(max(processed_items / total_items, 0.0), 1.0)
        return int(round(stage_start + (stage_end - stage_start) * ratio))

    async def _report_job_progress(
        self,
        job_id: Optional[str],
        progress: int,
        message: str,
        *,
        current_item: Optional[str] = None,
        total_items: Optional[int] = None,
        processed_items: Optional[int] = None,
    ) -> None:
        """向调度执行历史回写进度，供前端显示进度/当前操作/剩余时间。"""
        if not job_id:
            return

        try:
            from app.services.scheduler_service import TaskCancelledException, update_job_progress

            await update_job_progress(
                job_id=job_id,
                progress=max(0, min(100, progress)),
                message=message,
                current_item=current_item,
                total_items=total_items,
                processed_items=processed_items,
            )
        except TaskCancelledException:
            raise
        except Exception as e:
            logger.debug(f"ETF 同步进度回写失败（不影响主流程）: {e}")

    @staticmethod
    def _build_sync_result(basic_stats: Dict[str, Any], daily_stats: Dict[str, Any], source: str) -> Dict[str, Any]:
        """将 ETF 分阶段结果扁平化，兼容调度器完成态统计。"""
        daily_total = int(daily_stats.get("total_processed") or 0)
        basic_total = int(basic_stats.get("total_processed") or 0)
        total_processed = daily_total or basic_total

        if daily_total > 0:
            error_count = int(daily_stats.get("error_count") or 0)
        else:
            error_count = int(basic_stats.get("error_count") or 0)

        success_count = max(total_processed - error_count, 0)

        errors = list(basic_stats.get("errors") or []) + list(daily_stats.get("errors") or [])

        return {
            "basic_info": basic_stats,
            "daily_quotes": daily_stats,
            "data_source_used": source,
            "total_processed": total_processed,
            "success_count": success_count,
            "error_count": error_count,
            "skipped_count": int(basic_stats.get("skipped_count") or 0),
            "records_inserted": int(daily_stats.get("records_inserted") or 0),
            "errors": errors,
        }

    @staticmethod
    def _to_compact_date(value: Any) -> Optional[str]:
        normalized = _normalize_date_text(value)
        if not normalized:
            return None
        try:
            return datetime.strptime(normalized, "%Y-%m-%d").strftime("%Y%m%d")
        except ValueError:
            return None

    @staticmethod
    def _get_initial_full_sync_date(basic_doc: Optional[Dict[str, Any]]) -> Optional[str]:
        if not basic_doc:
            return None

        for field in ("list_date", "found_date", "issue_date"):
            compact_date = EtfSyncService._to_compact_date(basic_doc.get(field))
            if compact_date:
                return compact_date

        return None

    async def _resolve_daily_sync_window(
        self,
        code: str,
        source: str,
        fallback_days: int,
        force_update: bool,
        *,
        basic_doc: Optional[Dict[str, Any]] = None,
        smart_incremental: bool = False,
    ) -> tuple[str, str, str]:
        """确定 ETF 日线同步窗口：首次全量，后续按库内最新日期增量补齐。"""
        end_dt = datetime.now()
        end_date = end_dt.strftime("%Y%m%d")

        if force_update or not smart_incremental:
            start_dt = end_dt - timedelta(days=fallback_days)
            return start_dt.strftime("%Y%m%d"), end_date, f"按指定窗口同步最近 {fallback_days} 天"

        collection = self.db[ETF_DAILY_QUOTES_COLLECTION]
        latest_doc = await collection.find_one(
            {"symbol": code},
            {"trade_date": 1, "_id": 0},
            sort=[("trade_date", -1)]
        )
        latest_trade_date = _normalize_date_text((latest_doc or {}).get("trade_date"))
        if latest_trade_date:
            try:
                next_dt = datetime.strptime(latest_trade_date, "%Y-%m-%d") + timedelta(days=1)
                return next_dt.strftime("%Y%m%d"), end_date, f"增量补齐（最新入库 {latest_trade_date}）"
            except ValueError:
                logger.debug(f"ETF {code} 最新 trade_date 解析失败，回退到全量起点: {latest_trade_date}")

        initial_start_date = self._get_initial_full_sync_date(basic_doc)

        if not initial_start_date and basic_doc is None:
            basic_doc = await self.db[ETF_BASIC_INFO_COLLECTION].find_one(
                {"code": code, "source": source},
                {"list_date": 1, "found_date": 1, "issue_date": 1, "_id": 0}
            )
            initial_start_date = self._get_initial_full_sync_date(basic_doc)

        if not initial_start_date:
            basic_doc = await self.db[ETF_BASIC_INFO_COLLECTION].find_one(
                {"code": code},
                {"list_date": 1, "found_date": 1, "issue_date": 1, "_id": 0}
            )
            initial_start_date = self._get_initial_full_sync_date(basic_doc)

        if initial_start_date:
            return initial_start_date, end_date, f"首次全量（从 {initial_start_date[:4]}-{initial_start_date[4:6]}-{initial_start_date[6:8]} 开始）"

        return ETF_FULL_SYNC_FALLBACK_START, end_date, "首次全量（缺少上市日，使用全历史兜底起点）"

    async def initialize(self):
        """初始化数据库连接"""
        self.db = get_mongo_db()
        await self._ensure_indexes()
        logger.info("✅ ETF 同步服务初始化完成")

    async def _get_source_priority(self) -> List[str]:
        """使用项目统一的数据源配置（a_shares，ETF 与 A 股同市场），排除 local 后按优先级返回"""
        try:
            enabled = await get_enabled_data_sources_async("a_shares")
            # 排除 local（local 为读库，同步需调用外部 API）
            raw = [s for s in enabled if s and s.lower() != "local"]
            # 只保留已实现 ETF 同步的数据源，并规范化为小写
            priority = [_normalize_source_name(p) for p in raw if _normalize_source_name(p) in _FETCH_BASIC]
            if priority:
                logger.info(f"📊 [ETF 同步] 数据源优先级（统一配置）: {priority}")
                return priority
        except Exception as e:
            logger.warning(f"⚠️ [ETF 同步] 获取统一数据源配置失败: {e}")
        logger.info(f"📊 [ETF 同步] 使用默认数据源: {DEFAULT_SOURCE_PRIORITY}")
        return DEFAULT_SOURCE_PRIORITY

    async def _sync_basic_by_source(
        self,
        source: str,
        force_update: bool,
        symbols: Optional[List[str]] = None,
        job_id: Optional[str] = None,
        stage_start: int = 5,
        stage_end: int = 45,
    ) -> Dict[str, Any]:
        """按指定数据源同步 ETF 基础信息"""
        if self.db is None:
            await self.initialize()
        fetch_fn = _FETCH_BASIC.get(source)
        if not fetch_fn:
            return {"total_processed": 0, "success_count": 0, "error_count": 1, "errors": [{"error": f"未实现的数据源: {source}"}]}

        stats = {"total_processed": 0, "success_count": 0, "error_count": 0, "skipped_count": 0, "start_time": datetime.utcnow(), "end_time": None, "duration": 0, "errors": [], "data_source": source}

        try:
            loop = asyncio.get_running_loop()
            rows = await loop.run_in_executor(None, fetch_fn)
            if symbols:
                normalized_symbols = {_normalize_etf_code(symbol) for symbol in symbols if _normalize_etf_code(symbol)}
                rows = [row for row in rows if row.get("code") in normalized_symbols]
            valuation_map = {}
            share_map = {}
            if source == "akshare":
                valuation_map = await loop.run_in_executor(None, _fetch_etf_valuation_map_akshare)
            elif source == "tushare":
                target_codes = {row["code"] for row in rows if row.get("code")}
                valuation_map = await loop.run_in_executor(None, partial(_fetch_etf_nav_map_tushare, target_codes, 15))
                share_map = await loop.run_in_executor(None, partial(_fetch_etf_share_map_tushare, target_codes, 30))
            if not rows:
                await self._report_job_progress(
                    job_id,
                    stage_start,
                    f"未获取到 ETF 基础信息（{source.upper()}），尝试其他数据源",
                    current_item=source.upper(),
                )
                logger.warning(f"⚠️ [{source}] 未获取到 ETF 列表")
                return stats

            stats["total_processed"] = len(rows)
            logger.info(f"📊 [{source}] 获取到 {len(rows)} 只 ETF 基础信息")
            await self._report_job_progress(
                job_id,
                stage_start,
                f"正在同步 ETF 基础信息（{source.upper()}）",
                total_items=len(rows),
                processed_items=0,
            )

            collection = self.db[ETF_BASIC_INFO_COLLECTION]
            now = datetime.utcnow()

            for index, r in enumerate(rows, start=1):
                try:
                    code = r["code"]
                    existing = None
                    skip_item = False
                    if not force_update:
                        existing = await collection.find_one({"code": code, "source": source})
                        if existing and self._is_fresh(existing.get("updated_at"), hours=24):
                            if source == "tushare" and _needs_tushare_backfill(existing):
                                logger.info(f"🔄 [{source}] ETF {code} 基础信息较新但缺净值/份额字段，执行回填")
                            else:
                                stats["skipped_count"] += 1
                                skip_item = True

                    if not skip_item:
                        valuation = valuation_map.get(code, {})
                        share_info = share_map.get(code, {})
                        existing_doc = existing or {}

                        doc = {
                            "code": code,
                            "symbol": code,
                            "name": r.get("name", ""),
                            "full_symbol": r.get("full_symbol", _get_full_symbol(code)),
                            "fund_type": _coalesce(r.get("fund_type"), valuation.get("fund_type"), "ETF"),
                            "fund_scale": r.get("fund_scale"),
                            "track_index": r.get("track_index", ""),
                            "management": r.get("management"),
                            "custodian": r.get("custodian"),
                            "management_fee": r.get("management_fee"),
                            "custodian_fee": r.get("custodian_fee"),
                            "found_date": r.get("found_date"),
                            "list_date": r.get("list_date"),
                            "issue_date": r.get("issue_date"),
                            "due_date": r.get("due_date"),
                            "invest_type": r.get("invest_type"),
                            "status": r.get("status"),
                            "min_amount": r.get("min_amount"),
                            "purchase_start_date": r.get("purchase_start_date"),
                            "redemption_start_date": r.get("redemption_start_date"),
                            "unit_nav": _coalesce(valuation.get("unit_nav"), existing_doc.get("unit_nav")),
                            "accum_nav": _coalesce(valuation.get("accum_nav"), existing_doc.get("accum_nav")),
                            "nav_change_value": _coalesce(valuation.get("nav_change_value"), existing_doc.get("nav_change_value")),
                            "nav_growth_rate": _coalesce(valuation.get("nav_growth_rate"), existing_doc.get("nav_growth_rate")),
                            "market_price": _coalesce(valuation.get("market_price"), existing_doc.get("market_price")),
                            "premium_discount_rate": _coalesce(valuation.get("premium_discount_rate"), existing_doc.get("premium_discount_rate")),
                            "latest_nav_date": _coalesce(valuation.get("latest_nav_date"), existing_doc.get("latest_nav_date")),
                            "latest_nav_ann_date": _coalesce(valuation.get("latest_nav_ann_date"), existing_doc.get("latest_nav_ann_date")),
                            "accum_div": _coalesce(valuation.get("accum_div"), existing_doc.get("accum_div")),
                            "net_asset": _coalesce(valuation.get("net_asset"), existing_doc.get("net_asset")),
                            "total_netasset": _coalesce(valuation.get("total_netasset"), existing_doc.get("total_netasset")),
                            "adj_nav": _coalesce(valuation.get("adj_nav"), existing_doc.get("adj_nav")),
                            "fund_share": _coalesce(share_info.get("fund_share"), existing_doc.get("fund_share")),
                            "fund_share_date": _coalesce(share_info.get("fund_share_date"), existing_doc.get("fund_share_date")),
                            "purchase_status": _coalesce(valuation.get("purchase_status"), existing_doc.get("purchase_status")),
                            "redemption_status": _coalesce(valuation.get("redemption_status"), existing_doc.get("redemption_status")),
                            "source": source,
                            "updated_at": now,
                        }
                        await collection.update_one({"code": code, "source": source}, {"$set": doc}, upsert=True)
                        stats["success_count"] += 1
                except Exception as e:
                    stats["error_count"] += 1
                    stats["errors"].append({"code": r.get("code", "?"), "error": str(e)})

                if index == 1 or index == len(rows) or index % 10 == 0:
                    current_code = r.get("code", "?")
                    current_name = str(r.get("name") or "").strip()
                    current_item = f"{current_code} {current_name}".strip()
                    await self._report_job_progress(
                        job_id,
                        self._calculate_stage_progress(stage_start, stage_end, index, len(rows)),
                        f"正在同步 ETF 基础信息（{source.upper()}）",
                        current_item=current_item,
                        total_items=len(rows),
                        processed_items=index,
                    )
                await asyncio.sleep(self.rate_limit_delay / 10)

            stats["end_time"] = datetime.utcnow()
            stats["duration"] = (stats["end_time"] - stats["start_time"]).total_seconds()
            logger.info(f"🎉 [{source}] ETF 基础信息同步完成: 成功 {stats['success_count']}, 跳过 {stats['skipped_count']}, 错误 {stats['error_count']}")
        except Exception as e:
            from app.services.scheduler_service import TaskCancelledException

            if isinstance(e, TaskCancelledException):
                raise
            logger.error(f"❌ [{source}] ETF 基础信息同步失败: {e}", exc_info=True)
            stats["errors"].append({"error": str(e), "context": "sync_etf_basic_info"})

        return stats

    async def _sync_daily_by_source(
        self,
        source: str,
        symbols: Optional[List[str]],
        days: int,
        force_update: bool,
        job_id: Optional[str] = None,
        stage_start: int = 50,
        stage_end: int = 95,
        smart_incremental: bool = False,
    ) -> Dict[str, Any]:
        """按指定数据源同步 ETF 日线"""
        if self.db is None:
            await self.initialize()
        fetch_fn = _FETCH_HIST.get(source)
        if not fetch_fn:
            return {"total_processed": 0, "success_count": 0, "records_inserted": 0, "errors": [{"error": f"未实现的数据源: {source}"}]}

        stats = {"total_processed": 0, "success_count": 0, "error_count": 0, "records_inserted": 0, "start_time": datetime.utcnow(), "end_time": None, "duration": 0, "errors": [], "data_source": source}

        try:
            if symbols:
                code_entries = []
                for symbol in symbols:
                    normalized = _normalize_etf_code(symbol)
                    if normalized:
                        code_entries.append({"code": normalized})
            else:
                cursor = self.db[ETF_BASIC_INFO_COLLECTION].find(
                    {"source": source},
                    {"code": 1, "name": 1, "list_date": 1, "found_date": 1, "issue_date": 1, "_id": 0}
                )
                code_entries = [d async for d in cursor if d.get("code")]

            if not code_entries:
                await self._report_job_progress(
                    job_id,
                    stage_start,
                    f"未找到可同步的 ETF 日线代码（{source.upper()}）",
                    current_item=source.upper(),
                )
                logger.warning(f"⚠️ [{source}] 没有可同步的 ETF 代码")
                return stats

            stats["total_processed"] = len(code_entries)
            if smart_incremental and not force_update:
                sync_scope_message = "首次全量，后续按最新入库日期增量补齐"
            else:
                sync_scope_message = f"按指定窗口同步最近 {days} 天"

            logger.info(f"📊 [{source}] 开始同步 {len(code_entries)} 只 ETF 的日线数据（{sync_scope_message}）")
            await self._report_job_progress(
                job_id,
                stage_start,
                f"正在同步 ETF 日线（{source.upper()}）",
                total_items=len(code_entries),
                processed_items=0,
            )

            collection = self.db[ETF_DAILY_QUOTES_COLLECTION]
            loop = asyncio.get_running_loop()

            for i, code_entry in enumerate(code_entries, start=1):
                code = code_entry["code"]
                current_name = str(code_entry.get("name") or "").strip()
                try:
                    start_date, end_date, sync_window_desc = await self._resolve_daily_sync_window(
                        code,
                        source,
                        days,
                        force_update,
                        basic_doc=code_entry,
                        smart_incremental=smart_incremental,
                    )

                    fetch_started_at = loop.time()
                    if start_date > end_date:
                        logger.info(
                            f"🌐 [{source}] 跳过网络抓取: code={code}, name={current_name or '-'}, "
                            f"reason=同步窗口为空, start_date={start_date}, end_date={end_date}"
                        )
                        records = []
                    else:
                        logger.info(
                            f"🌐 [{source}] 开始抓取 ETF 日线: code={code}, name={current_name or '-'}, "
                            f"start_date={start_date}, end_date={end_date}"
                        )
                        records = await asyncio.wait_for(
                            loop.run_in_executor(None, partial(fetch_fn, code, start_date, end_date)),
                            timeout=self.item_timeout_seconds,
                        )
                        fetch_elapsed = loop.time() - fetch_started_at
                        logger.info(
                            f"🌐 [{source}] 抓取完成: code={code}, records={len(records)}, "
                            f"elapsed={fetch_elapsed:.2f}s"
                        )
                    if not records:
                        inserted = 0
                        logger.info(
                            f"💾 [{source}] 跳过数据库写入: code={code}, name={current_name or '-'}, records=0"
                        )
                    else:
                        from pymongo import UpdateOne

                        written_count = 0
                        updated_count = 0
                        skipped_existing = 0
                        write_started_at = loop.time()
                        write_timestamp = datetime.utcnow()
                        logger.info(
                            f"💾 [{source}] 开始写入 ETF 日线: code={code}, name={current_name or '-'}, "
                            f"records={len(records)}, force_update={force_update}"
                        )

                        existing_trade_dates = set()
                        existing_query_code = records[0].get("code") or code
                        record_trade_dates = [rec.get("trade_date") for rec in records if rec.get("trade_date") is not None]
                        if record_trade_dates:
                            existing_cursor = collection.find(
                                {"code": existing_query_code, "trade_date": {"$in": record_trade_dates}},
                                {"trade_date": 1, "_id": 0},
                            )
                            async for existing_doc in existing_cursor:
                                existing_trade_dates.add(existing_doc.get("trade_date"))

                        known_trade_dates = set(existing_trade_dates)
                        bulk_operations = []
                        bulk_batch_size = 200

                        for rec in records:
                            rec["data_source"] = source
                            record_code = rec.get("code") or rec.get("symbol") or code
                            rec["code"] = record_code
                            trade_date = rec.get("trade_date")
                            key = {"code": record_code, "trade_date": trade_date}
                            record_exists = trade_date in known_trade_dates

                            if not force_update and record_exists:
                                skipped_existing += 1
                                logger.info(
                                    f"💾 [{source}] 跳过已存在日线: code={record_code}, "
                                    f"trade_date={trade_date}, action=skip_existing"
                                )
                                continue

                            known_trade_dates.add(trade_date)
                            bulk_operations.append(
                                UpdateOne(
                                    key,
                                    {"$set": {**rec, "updated_at": write_timestamp}},
                                    upsert=True,
                                )
                            )

                            action = "updated" if record_exists else "inserted"
                            if action == "updated":
                                updated_count += 1
                            written_count += 1
                            logger.info(
                                f"💾 [{source}] 写入日线记录: code={record_code}, "
                                f"trade_date={trade_date}, action={action}"
                            )

                            if len(bulk_operations) >= bulk_batch_size:
                                await collection.bulk_write(bulk_operations, ordered=False)
                                bulk_operations = []

                        if bulk_operations:
                            await collection.bulk_write(bulk_operations, ordered=False)

                        write_elapsed = loop.time() - write_started_at
                        logger.info(
                            f"💾 [{source}] 写入完成: code={code}, inserted={written_count}, "
                            f"updated={updated_count}, skipped_existing={skipped_existing}, elapsed={write_elapsed:.2f}s"
                        )

                        stats["records_inserted"] += written_count

                    stats["success_count"] += 1

                    if i % 20 == 0:
                        logger.info(f"📈 [{source}] ETF 日线同步进度: {i}/{len(code_entries)}")
                except asyncio.TimeoutError:
                    stats["error_count"] += 1
                    timeout_message = f"抓取超时（>{self.item_timeout_seconds}s）"
                    stats["errors"].append({"code": code, "error": timeout_message})
                    sync_window_desc = timeout_message
                    logger.warning(
                        f"⏰ [{source}] ETF 日线抓取超时: code={code}, "
                        f"timeout={self.item_timeout_seconds}s, start_date={start_date}, end_date={end_date}"
                    )
                except Exception as e:
                    stats["error_count"] += 1
                    stats["errors"].append({"code": code, "error": str(e)})
                    sync_window_desc = "同步失败"

                if i == 1 or i == len(code_entries) or i % 10 == 0:
                    current_item = f"{code} {current_name}".strip()
                    if sync_window_desc:
                        current_item = f"{current_item} | {sync_window_desc}" if current_item else sync_window_desc
                    await self._report_job_progress(
                        job_id,
                        self._calculate_stage_progress(stage_start, stage_end, i, len(code_entries)),
                        f"正在同步 ETF 日线（{source.upper()}）",
                        current_item=current_item,
                        total_items=len(code_entries),
                        processed_items=i,
                    )

                await asyncio.sleep(self.rate_limit_delay)

            stats["end_time"] = datetime.utcnow()
            stats["duration"] = (stats["end_time"] - stats["start_time"]).total_seconds()
            logger.info(f"🎉 [{source}] ETF 日线同步完成: {stats['success_count']}/{len(code_entries)} 只, 插入 {stats['records_inserted']} 条")
        except Exception as e:
            from app.services.scheduler_service import TaskCancelledException

            if isinstance(e, TaskCancelledException):
                raise
            logger.error(f"❌ [{source}] ETF 日线同步失败: {e}", exc_info=True)
            stats["errors"].append({"error": str(e), "context": "sync_etf_daily_quotes"})

        return stats

    async def sync_all(self, force_update: bool = False, days: int = 30, job_id: Optional[str] = None) -> Dict[str, Any]:
        """
        全量同步：按数据源优先级依次尝试，优先级最高的先调用，同步成功则结束，失败则尝试下一优先级。
        """
        if self.db is None:
            await self.initialize()

        priority = await self._get_source_priority()
        valid_sources = [source for source in priority if source in _FETCH_BASIC]
        last_error = None

        await self._report_job_progress(job_id, 1, "开始同步 ETF 数据...")

        if not valid_sources:
            return {
                "basic_info": {"total_processed": 0, "errors": [{"error": "未找到可用的 ETF 数据源"}]},
                "daily_quotes": {"records_inserted": 0, "total_processed": 0},
                "data_source_used": None,
                "total_processed": 0,
                "success_count": 0,
                "error_count": 1,
                "errors": [{"error": "未找到可用的 ETF 数据源"}],
            }

        total_sources = len(valid_sources)

        for index, source in enumerate(valid_sources):
            slot_start = 5 + int(90 * index / total_sources)
            slot_end = 5 + int(90 * (index + 1) / total_sources)
            slot_end = max(slot_start + 1, min(95, slot_end))
            basic_end = min(slot_end - 1, slot_start + max(1, int((slot_end - slot_start) * 0.45)))
            daily_start = min(slot_end, basic_end + 1)

            logger.info(f"🔄 [ETF 同步] 尝试数据源: {source}")
            await self._report_job_progress(
                job_id,
                slot_start,
                f"准备同步 ETF 数据（{source.upper()}）",
                current_item=source.upper(),
            )

            try:
                from app.services.scheduler_service import TaskCancelledException

                basic_stats = await self._sync_basic_by_source(
                    source,
                    force_update,
                    job_id=job_id,
                    stage_start=slot_start,
                    stage_end=basic_end,
                )

                # 基础信息同步成功：获取到数据即可（total_processed > 0）
                if basic_stats.get("total_processed", 0) > 0:
                    # 一旦当前数据源拿到了 ETF 列表，当前任务就会直接使用该数据源完成日线同步并返回，
                    # 不会再继续尝试后续数据源；因此日线阶段应覆盖到全任务的完成区间，而不是停留在当前槽位上限。
                    daily_stats = await self._sync_daily_by_source(
                        source,
                        None,
                        days,
                        force_update,
                        job_id=job_id,
                        stage_start=daily_start,
                        stage_end=95,
                        smart_incremental=True,
                    )
                    result = self._build_sync_result(basic_stats, daily_stats, source)
                    await self._report_job_progress(
                        job_id,
                        99,
                        f"ETF 数据同步即将完成（{source.upper()}）",
                        current_item=source.upper(),
                        total_items=result.get("total_processed") or None,
                        processed_items=result.get("total_processed") or None,
                    )
                    logger.info(f"✅ [ETF 同步] 数据源 {source} 同步完成")
                    return result
                else:
                    last_error = basic_stats.get("errors", [{"error": "未获取到 ETF 列表"}])
                    await self._report_job_progress(
                        job_id,
                        slot_end,
                        f"数据源 {source.upper()} 未获取到 ETF 数据，尝试下一数据源",
                        current_item=source.upper(),
                    )
                    logger.warning(f"⚠️ [ETF 同步] 数据源 {source} 未获取到数据，尝试下一优先级")
            except TaskCancelledException:
                raise
            except Exception as e:
                last_error = str(e)
                await self._report_job_progress(
                    job_id,
                    slot_end,
                    f"数据源 {source.upper()} 失败，尝试下一数据源",
                    current_item=source.upper(),
                )
                logger.warning(f"⚠️ [ETF 同步] 数据源 {source} 失败: {e}，尝试下一优先级")

        logger.error(f"❌ [ETF 同步] 所有数据源均失败，最后错误: {last_error}")
        return {
            "basic_info": {"total_processed": 0, "errors": [{"error": str(last_error)}]},
            "daily_quotes": {"records_inserted": 0},
            "data_source_used": None,
            "total_processed": 0,
            "success_count": 0,
            "error_count": 1,
            "errors": [{"error": str(last_error)}],
        }

    async def sync_symbols(
        self,
        symbols: List[str],
        force_update: bool = False,
        days: int = 30,
        job_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """按指定 ETF 代码同步基础信息与日线数据。"""
        if self.db is None:
            await self.initialize()

        normalized_symbols = sorted(
            {
                normalized
                for normalized in (_normalize_etf_code(symbol) for symbol in (symbols or []))
                if _is_etf_code(normalized)
            }
        )

        if not normalized_symbols:
            return {
                "basic_info": {"total_processed": 0, "errors": [{"error": "未提供有效的 ETF 代码"}]},
                "daily_quotes": {"records_inserted": 0, "total_processed": 0},
                "data_source_used": None,
                "total_processed": 0,
                "success_count": 0,
                "error_count": 1,
                "errors": [{"error": "未提供有效的 ETF 代码"}],
                "requested_symbols": [],
            }

        priority = await self._get_source_priority()
        valid_sources = [source for source in priority if source in _FETCH_BASIC]
        last_error = None

        await self._report_job_progress(
            job_id,
            1,
            "开始同步指定 ETF 数据...",
            total_items=len(normalized_symbols),
            processed_items=0,
        )

        if not valid_sources:
            return {
                "basic_info": {"total_processed": 0, "errors": [{"error": "未找到可用的 ETF 数据源"}]},
                "daily_quotes": {"records_inserted": 0, "total_processed": 0},
                "data_source_used": None,
                "total_processed": 0,
                "success_count": 0,
                "error_count": 1,
                "errors": [{"error": "未找到可用的 ETF 数据源"}],
                "requested_symbols": normalized_symbols,
            }

        for source in valid_sources:
            logger.info(f"🔄 [ETF 同步] 尝试指定代码同步，数据源: {source}, 数量: {len(normalized_symbols)}")
            await self._report_job_progress(
                job_id,
                5,
                f"准备同步指定 ETF 数据（{source.upper()}）",
                current_item=source.upper(),
                total_items=len(normalized_symbols),
                processed_items=0,
            )

            try:
                basic_stats = await self._sync_basic_by_source(
                    source,
                    force_update,
                    symbols=normalized_symbols,
                    job_id=job_id,
                    stage_start=5,
                    stage_end=45,
                )

                if basic_stats.get("total_processed", 0) > 0:
                    daily_stats = await self._sync_daily_by_source(
                        source,
                        normalized_symbols,
                        days,
                        force_update,
                        job_id=job_id,
                        stage_start=50,
                        stage_end=95,
                        smart_incremental=True,
                    )
                    result = self._build_sync_result(basic_stats, daily_stats, source)
                    result["requested_symbols"] = normalized_symbols
                    return result

                last_error = basic_stats.get("errors", [{"error": "未获取到 ETF 列表"}])
            except Exception as e:
                last_error = str(e)
                logger.warning(f"⚠️ [ETF 同步] 指定 ETF 同步失败: source={source}, error={e}")

        logger.error(f"❌ [ETF 同步] 指定 ETF 同步失败，最后错误: {last_error}")
        return {
            "basic_info": {"total_processed": 0, "errors": [{"error": str(last_error)}]},
            "daily_quotes": {"records_inserted": 0, "total_processed": 0},
            "data_source_used": None,
            "total_processed": 0,
            "success_count": 0,
            "error_count": 1,
            "errors": [{"error": str(last_error)}],
            "requested_symbols": normalized_symbols,
        }

    def _is_fresh(self, updated_at: Any, hours: int = 24) -> bool:
        """检查数据是否在指定小时内更新过"""
        if not updated_at:
            return False
        try:
            if isinstance(updated_at, str):
                updated_at = datetime.fromisoformat(updated_at.replace("Z", "+00:00"))
            if updated_at.tzinfo:
                updated_at = updated_at.replace(tzinfo=None)
            return (datetime.utcnow() - updated_at).total_seconds() < hours * 3600
        except Exception:
            return False


_etf_sync_service: Optional[EtfSyncService] = None


async def get_etf_sync_service() -> EtfSyncService:
    """获取 ETF 同步服务单例"""
    global _etf_sync_service
    if _etf_sync_service is None:
        _etf_sync_service = EtfSyncService()
        await _etf_sync_service.initialize()
    return _etf_sync_service


async def run_etf_sync(force_update: bool = False, days: int = 30, job_id: str = None) -> Dict[str, Any]:
    """运行 ETF 全量同步（供 APScheduler 或 API 调用）"""
    try:
        service = await get_etf_sync_service()
        result = await service.sync_all(force_update=force_update, days=days, job_id=job_id)
        if job_id:
            try:
                from app.services.scheduler_service import mark_job_completed
                await mark_job_completed(job_id, result)
            except Exception:
                pass
        return result
    except Exception as e:
        from app.services.scheduler_service import TaskCancelledException

        if isinstance(e, TaskCancelledException):
            logger.info("ℹ️ ETF 同步任务已被用户取消")
            return {"cancelled": True, "message": "任务已被用户取消"}
        logger.error(f"❌ ETF 同步失败: {e}", exc_info=True)
        if job_id:
            try:
                from app.services.scheduler_service import mark_job_completed
                await mark_job_completed(job_id, {}, str(e))
            except Exception:
                pass
        raise
