"""
股票详情相关API
- 统一响应包: {success, data, message, timestamp}
- 所有端点均需鉴权 (Bearer Token)
- 路径前缀在 main.py 中挂载为 /api，当前路由自身前缀为 /stocks
"""
from typing import Optional, Dict, Any, List, Tuple
from fastapi import APIRouter, Depends, HTTPException, status, Query
from datetime import datetime, timedelta
import asyncio
import time
import logging
import re

from app.routers.auth_db import get_current_user
from app.core.database import get_mongo_db
from app.core.response import ok
from app.services.favorites_service import FavoritesService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/stocks", tags=["stocks"])

_MARKET_OVERVIEW_CACHE: Dict[str, Any] = {"ts": 0.0, "data": None}
_MARKET_OVERVIEW_TTL = 60


def _zfill_code(code: str) -> str:
    try:
        s = str(code).strip()
        if len(s) == 6 and s.isdigit():
            return s
        return s.zfill(6)
    except Exception:
        return str(code)


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


def _safe_float(value: Any) -> Optional[float]:
    try:
        if value is None:
            return None
        if isinstance(value, str):
            s = value.strip().replace(",", "")
            if s.endswith("%"):
                s = s[:-1]
            if s == "" or s == "-":
                return None
            return float(s)
        return float(value)
    except Exception:
        return None


def _pick_col(columns: List[str], candidates: List[str]) -> Optional[str]:
    for c in candidates:
        if c in columns:
            return c
    return None


def _pick_col_contains(columns: List[str], candidates: List[str]) -> Optional[str]:
    for col in columns:
        col_str = str(col)
        for c in candidates:
            if c in col_str:
                return col
    return None


def _format_amount(value: Optional[float]) -> str:
    if value is None:
        return "-"
    try:
        v = float(value)
    except Exception:
        return "-"
    if abs(v) >= 1e8:
        return f"{v / 1e8:.2f}亿"
    if abs(v) >= 1e4:
        return f"{v / 1e4:.2f}万"
    return f"{v:.2f}"


def _normalize_date_str(value: Any) -> Optional[str]:
    if value is None:
        return None
    s = str(value).strip()
    if not s:
        return None
    if "-" in s:
        s = s.replace("-", "")
    if len(s) >= 8:
        return s[:8]
    return s.zfill(8)


async def _fetch_cn_index_cards() -> List[Dict[str, Any]]:
    def _task() -> List[Dict[str, Any]]:
        try:
            import akshare as ak
            df = ak.stock_zh_index_spot_em()
            if df is None or getattr(df, "empty", True):
                return []
            cols = list(df.columns)
            name_col = _pick_col(cols, ["指数名称", "名称", "指数"])
            value_col = _pick_col(cols, ["最新价", "最新", "最新价(元)"])
            chg_col = _pick_col(cols, ["涨跌幅", "涨跌幅(%)", "涨幅"])
            open_col = _pick_col(cols, ["开盘", "今开"])
            high_col = _pick_col(cols, ["最高", "最高价"])
            low_col = _pick_col(cols, ["最低", "最低价"])
            vol_col = _pick_col(cols, ["成交额", "成交额(元)", "成交额(万元)", "成交量"])
            if not name_col or not value_col:
                return []
            target_names = ["上证指数", "深证成指", "创业板指"]
            rows = df[df[name_col].isin(target_names)]
            if rows is None or getattr(rows, "empty", True):
                rows = df.head(6)
            items: List[Dict[str, Any]] = []
            for _, row in rows.iterrows():
                name = str(row.get(name_col)).strip()
                items.append({
                    "name": name,
                    "market": "A股",
                    "value": _safe_float(row.get(value_col)),
                    "chg": _safe_float(row.get(chg_col)),
                    "open": _safe_float(row.get(open_col)),
                    "high": _safe_float(row.get(high_col)),
                    "low": _safe_float(row.get(low_col)),
                    "volume": _safe_float(row.get(vol_col)),
                    "source": "akshare"
                })
            return items
        except Exception as e:
            logger.error(f"获取A股指数失败: {e}")
            return []
    return await asyncio.to_thread(_task)


async def _fetch_trade_dates() -> List[str]:
    def _task() -> List[str]:
        try:
            import akshare as ak
            df = _akshare_call(getattr(ak, "tool_trade_date_hist_sina", None), name="交易日历")
            if df is None or getattr(df, "empty", True):
                return []
            col = _pick_col(list(df.columns), ["trade_date", "交易日期", "日期"])
            if not col:
                return []
            dates = []
            for v in df[col].tolist():
                d = _normalize_date_str(v)
                if d:
                    dates.append(d)
            dates = sorted(set(dates))
            today = datetime.now().strftime("%Y%m%d")
            dates = [d for d in dates if d <= today]
            return dates[-10:] if len(dates) >= 10 else dates
        except Exception as e:
            logger.error(f"获取交易日失败: {e}")
            return []
    return await asyncio.to_thread(_task)


async def _fetch_sector_cards(limit: int = 12) -> List[Dict[str, Any]]:
    def _task() -> List[Dict[str, Any]]:
        try:
            import akshare as ak
            df = _akshare_call(getattr(ak, "stock_board_industry_spot_em", None), name="行业板块")
            if df is None or getattr(df, "empty", True):
                return []
            cols = list(df.columns)
            name_col = _pick_col(cols, ["板块名称", "行业名称", "名称"])
            chg_col = _pick_col(cols, ["涨跌幅", "涨跌幅(%)", "涨幅"])
            vol_col = _pick_col(cols, ["成交额", "成交额(元)", "成交额(万元)", "成交量"])
            if not name_col:
                return []
            items: List[Dict[str, Any]] = []
            for _, row in df.head(limit).iterrows():
                items.append({
                    "name": str(row.get(name_col)).strip(),
                    "chg": _safe_float(row.get(chg_col)),
                    "volume": _safe_float(row.get(vol_col)),
                    "source": "akshare"
                })
            return items
        except Exception as e:
            logger.error(f"获取行业板块失败: {e}")
            return []
    return await asyncio.to_thread(_task)


async def _fetch_market_metrics() -> List[Dict[str, Any]]:
    def _task() -> List[Dict[str, Any]]:
        try:
            import akshare as ak
            df = _akshare_call(getattr(ak, "stock_zh_a_spot_em", None), name="市场指标")
            if df is None or getattr(df, "empty", True):
                return []
            cols = list(df.columns)
            amt_col = _pick_col(cols, ["成交额", "成交额(元)", "成交额(万元)"])
            pe_col = _pick_col(cols, ["市盈率-动态", "市盈率(动)", "市盈率", "pe"])
            turn_col = _pick_col(cols, ["换手率", "换手率(%)"])
            pct_col = _pick_col(cols, ["涨跌幅", "涨跌幅(%)", "涨幅"])
            total_amount = None
            if amt_col:
                total_amount = df[amt_col].apply(_safe_float).dropna().sum()
            avg_pe = None
            if pe_col:
                pe_series = df[pe_col].apply(_safe_float).dropna()
                avg_pe = pe_series.mean() if not pe_series.empty else None
            avg_turn = None
            if turn_col:
                turn_series = df[turn_col].apply(_safe_float).dropna()
                avg_turn = turn_series.mean() if not turn_series.empty else None
            up = None
            down = None
            if pct_col:
                pct_series = df[pct_col].apply(_safe_float).dropna()
                up = int((pct_series > 0).sum())
                down = int((pct_series < 0).sum())
            metrics = [
                {"name": "市场成交额", "value": _format_amount(total_amount), "desc": "全市场成交额"},
                {"name": "平均市盈率", "value": f"{avg_pe:.2f}" if avg_pe is not None else "-", "desc": "动态市盈率均值"},
                {"name": "平均换手率", "value": f"{avg_turn:.2f}%" if avg_turn is not None else "-", "desc": "全市场换手率均值"},
                {"name": "涨跌家数", "value": f"{up}/{down}" if up is not None and down is not None else "-", "desc": "上涨/下跌家数"}
            ]
            return metrics
        except Exception as e:
            logger.error(f"获取市场指标失败: {e}")
            return []
    return await asyncio.to_thread(_task)


async def _fetch_market_metrics_from_db() -> List[Dict[str, Any]]:
    try:
        db = get_mongo_db()
        coll = db["market_quotes"]
        pipeline = [
            {"$project": {"amount": 1, "pct_chg": 1}},
            {"$group": {
                "_id": None,
                "total_amount": {"$sum": {"$ifNull": ["$amount", 0]}},
                "up": {"$sum": {"$cond": [{"$gt": ["$pct_chg", 0]}, 1, 0]}},
                "down": {"$sum": {"$cond": [{"$lt": ["$pct_chg", 0]}, 1, 0]}}
            }}
        ]
        docs = await coll.aggregate(pipeline).to_list(length=1)
        if not docs:
            return []
        doc = docs[0]
        total_amount = doc.get("total_amount")
        up = doc.get("up")
        down = doc.get("down")
        metrics = [
            {"name": "市场成交额", "value": _format_amount(total_amount), "desc": "全市场成交额"},
            {"name": "平均市盈率", "value": "-", "desc": "动态市盈率均值"},
            {"name": "平均换手率", "value": "-", "desc": "全市场换手率均值"},
            {"name": "涨跌家数", "value": f"{up}/{down}" if up is not None and down is not None else "-", "desc": "上涨/下跌家数"}
        ]
        return metrics
    except Exception as e:
        logger.error(f"从数据库获取市场指标失败: {e}")
        return []


async def _with_timeout(coro, timeout: float, default: Any, name: str):
    try:
        return await asyncio.wait_for(coro, timeout=timeout)
    except Exception as e:
        detail = str(e).strip() or type(e).__name__
        logger.warning(f"{name}请求超时或失败: {detail}")
        return default


async def _fetch_sector_cards_from_db(limit: int = 12) -> List[Dict[str, Any]]:
    try:
        db = get_mongo_db()
        quotes = await db["market_quotes"].find(
            {"code": {"$regex": r"^\d{6}$"}},
            {"code": 1, "pct_chg": 1, "amount": 1, "_id": 0}
        ).sort("amount", -1).limit(300).to_list(length=300)
        if not quotes:
            return []
        codes = [q.get("code") for q in quotes if q.get("code")]
        basics = await db["stock_basic_info"].find(
            {"code": {"$in": codes}},
            {"code": 1, "industry": 1, "_id": 0}
        ).to_list(length=len(codes))
        industry_map = {str(b.get("code")).zfill(6): b.get("industry") for b in basics if b.get("industry")}
        agg: Dict[str, Dict[str, Any]] = {}
        for q in quotes:
            code = str(q.get("code")).zfill(6)
            industry = industry_map.get(code)
            if not industry:
                continue
            item = agg.setdefault(industry, {"sum_amount": 0.0, "sum_chg": 0.0, "count": 0})
            item["sum_amount"] += float(q.get("amount") or 0)
            pct = _safe_float(q.get("pct_chg")) or 0.0
            item["sum_chg"] += pct
            item["count"] += 1
        items: List[Dict[str, Any]] = []
        for name, val in agg.items():
            count = val.get("count", 0) or 1
            items.append({
                "name": name,
                "chg": val["sum_chg"] / count,
                "volume": val["sum_amount"],
                "source": "database"
            })
        items.sort(key=lambda x: x.get("volume") or 0, reverse=True)
        return items[:limit]
    except Exception as e:
        logger.error(f"从数据库获取行业板块失败: {e}")
        return []


def _akshare_call(func, date_value: Optional[str] = None, name: str = ""):
    if func is None:
        return None
    def _do_call():
        if date_value:
            try:
                return func(date=date_value)
            except TypeError:
                return func(date_value)
        return func()
    try:
        return _do_call()
    except Exception as e:
        msg = str(e)
        prefix = f"{name} " if name else ""
        if "最近 30 个交易日" in msg:
            logger.warning(f"AKShare调用受限: {prefix}{msg}")
            return None
        if "RemoteDisconnected" in msg or "Connection aborted" in msg:
            try:
                time.sleep(0.6)
                return _do_call()
            except Exception as e2:
                logger.warning(f"AKShare调用失败: {prefix}{e2}")
                return None
        logger.error(f"AKShare调用失败: {prefix}{e}")
        return None


async def _fetch_limit_data() -> Dict[str, Any]:
    def _task() -> Dict[str, Any]:
        import akshare as ak
        return {
            "today_up": _akshare_call(getattr(ak, "stock_zt_pool_em", None), name="涨停池"),
            "today_down": _akshare_call(getattr(ak, "stock_zt_pool_dtgc_em", None), name="跌停池"),
            "today_break": _akshare_call(getattr(ak, "stock_zt_pool_zbgc_em", None), name="炸板池"),
            "today_lianban": _akshare_call(getattr(ak, "stock_zt_pool_lgb_em", None), name="连板池"),
        }
    return await asyncio.to_thread(_task)


async def _fetch_limit_data_with_date(trade_date: str) -> Dict[str, Any]:
    def _task() -> Dict[str, Any]:
        import akshare as ak
        return {
            "up": _akshare_call(getattr(ak, "stock_zt_pool_em", None), trade_date, "涨停池"),
            "down": _akshare_call(getattr(ak, "stock_zt_pool_dtgc_em", None), trade_date, "跌停池"),
            "break": _akshare_call(getattr(ak, "stock_zt_pool_zbgc_em", None), trade_date, "炸板池"),
            "lianban": _akshare_call(getattr(ak, "stock_zt_pool_lgb_em", None), trade_date, "连板池")
        }
    return await asyncio.to_thread(_task)


async def _fetch_wencai_limitup(trade_date: str):
    def _task():
        try:
            import pywencai
        except Exception as e:
            logger.warning(f"⚠️ wencai 未安装或导入失败: {e}")
            return None
        try:
            base_query = f"非ST,{trade_date}涨停"
            query_reason = f"{base_query},涨停原因类别,涨停概念,概念板块"
            logger.info(f"📡 wencai 查询涨停(带概念字段): {query_reason}")
            df_reason = pywencai.get(
                query=query_reason,
                sort_key="成交金额",
                sort_order="desc",
                loop=True
            )
            if df_reason is not None and not getattr(df_reason, "empty", True):
                cols_reason = list(df_reason.columns)
                logger.info(f"✅ wencai 返回 {len(df_reason)} 行, 列数 {len(cols_reason)}")
                logger.info(f"🔍 wencai 列预览: {cols_reason[:12]}")
                if _find_reason_col(cols_reason):
                    return df_reason
                logger.warning("⚠️ wencai 返回未包含概念列，尝试基础查询")
            else:
                logger.warning("⚠️ wencai 带概念字段查询返回空数据，尝试基础查询")
            logger.info(f"📡 wencai 查询涨停(基础): {base_query}")
            df_base = pywencai.get(
                query=base_query,
                sort_key="成交金额",
                sort_order="desc",
                loop=True
            )
            if df_base is None or getattr(df_base, "empty", True):
                logger.warning("⚠️ wencai 基础查询返回空数据")
                return None
            cols_base = list(df_base.columns)
            logger.info(f"✅ wencai 基础返回 {len(df_base)} 行, 列数 {len(cols_base)}")
            logger.info(f"🔍 wencai 基础列预览: {cols_base[:12]}")
            return df_base
        except Exception:
            logger.exception("❌ wencai 查询涨停失败")
            return None
    return await asyncio.to_thread(_task)


def _df_count(df) -> int:
    if df is None:
        return 0
    try:
        return 0 if getattr(df, "empty", True) else int(len(df))
    except Exception:
        return 0


def _extract_codes(df) -> List[str]:
    if df is None or getattr(df, "empty", True):
        return []
    col = _pick_col(list(df.columns), ["代码", "股票代码", "code", "symbol"])
    if not col:
        return []
    codes = []
    for v in df[col].tolist():
        s = str(v).strip()
        if s:
            codes.append(s.zfill(6))
    return codes


def _extract_names(df) -> Dict[str, str]:
    if df is None or getattr(df, "empty", True):
        return {}
    cols = list(df.columns)
    code_col = _pick_col(cols, ["代码", "股票代码", "code", "symbol"])
    name_col = _pick_col(cols, ["名称", "股票简称", "股票名称", "简称", "名字", "name"])
    if not code_col or not name_col:
        return {}
    mapping: Dict[str, str] = {}
    for _, row in df.iterrows():
        code = str(row.get(code_col, "")).strip().zfill(6)
        name = str(row.get(name_col, "")).strip()
        if code and name:
            mapping[code] = name
    return mapping


def _build_stock_list(df, limit: Optional[int] = None) -> List[Dict[str, Any]]:
    if df is None or getattr(df, "empty", True):
        return []
    codes = _extract_codes(df)
    if not codes:
        return []
    name_map = _extract_names(df)
    items = []
    for code in codes:
        name = name_map.get(code) or code
        items.append({"code": code, "name": name})
        if limit and len(items) >= limit:
            break
    return items


def _build_stock_list_by_codes(df, codes: List[str], limit: Optional[int] = None, include_reason: bool = False) -> List[Dict[str, Any]]:
    if df is None or getattr(df, "empty", True):
        return []
    if not codes:
        return []
    code_col = _pick_col(list(df.columns), ["代码", "股票代码", "code", "symbol"])
    if not code_col:
        return []
    code_set = {str(c).zfill(6) for c in codes if c}
    if not code_set:
        return []
    name_map = _extract_names(df)
    reason_col = _find_reason_col(list(df.columns)) if include_reason else None
    items: List[Dict[str, Any]] = []
    for _, row in df.iterrows():
        code = str(row.get(code_col, "")).strip().zfill(6)
        if code not in code_set:
            continue
        item: Dict[str, Any] = {"code": code, "name": name_map.get(code) or code}
        if reason_col:
            item["reason"] = str(row.get(reason_col, "")).strip()
        items.append(item)
        if limit and len(items) >= limit:
            break
    return items


async def _count_sector_limitup(limit_up_df) -> List[Dict[str, Any]]:
    if limit_up_df is None or getattr(limit_up_df, "empty", True):
        return []
    cols = list(limit_up_df.columns)
    industry_col = _pick_col(cols, ["所属行业", "行业", "板块"])
    code_col = _pick_col(cols, ["代码", "股票代码", "code", "symbol"])
    if industry_col:
        code_names = _extract_names(limit_up_df)
        sector_map: Dict[str, Dict[str, Any]] = {}
        for _, row in limit_up_df.iterrows():
            sector = str(row.get(industry_col, "")).strip()
            if not sector:
                continue
            code = str(row.get(code_col or "", "")).strip().zfill(6)
            name = code_names.get(code, "")
            if sector not in sector_map:
                sector_map[sector] = {"name": sector, "count": 0, "stocks": []}
            sector_map[sector]["count"] += 1
            if code and name:
                sector_map[sector]["stocks"].append({"code": code, "name": name})
        items = list(sector_map.values())
        items.sort(key=lambda x: x["count"], reverse=True)
        return items[:20]
    codes = _extract_codes(limit_up_df)
    if not codes:
        return []
    try:
        db = get_mongo_db()
        basics = await db["stock_basic_info"].find(
            {"code": {"$in": codes}},
            {"code": 1, "industry": 1, "name": 1, "_id": 0}
        ).to_list(length=len(codes))
        industry_map = {str(b.get("code")).zfill(6): b.get("industry") for b in basics if b.get("industry")}
        name_map = {str(b.get("code")).zfill(6): b.get("name") for b in basics if b.get("name")}
        sector_map: Dict[str, Dict[str, Any]] = {}
        for code in codes:
            industry = industry_map.get(code)
            if not industry:
                continue
            if industry not in sector_map:
                sector_map[industry] = {"name": industry, "count": 0, "stocks": []}
            sector_map[industry]["count"] += 1
            name = name_map.get(code)
            if name:
                sector_map[industry]["stocks"].append({"code": code, "name": name})
        items = list(sector_map.values())
        items.sort(key=lambda x: x["count"], reverse=True)
        return items[:20]
    except Exception as e:
        logger.error(f"统计板块涨停失败: {e}")
        return []


async def _fetch_limit_snapshot(trade_dates: List[str], index: int, strict: bool = False) -> Dict[str, Any]:
    date_value = trade_dates[index] if trade_dates and len(trade_dates) > abs(index) else None
    if not date_value:
        if strict:
            return {}
        current = await _fetch_limit_data()
        return {
            "up": current.get("today_up"),
            "down": current.get("today_down"),
            "break": current.get("today_break"),
            "lianban": current.get("today_lianban")
        }
    snapshot = await _fetch_limit_data_with_date(date_value)
    if snapshot and any(_df_count(snapshot.get(k)) > 0 for k in ["up", "down", "break", "lianban"]):
        return snapshot
    if len(trade_dates) >= 3 and index == -2:
        prev_snapshot = await _fetch_limit_data_with_date(trade_dates[-3])
        if prev_snapshot and any(_df_count(prev_snapshot.get(k)) > 0 for k in ["up", "down", "break", "lianban"]):
            return prev_snapshot
    if strict:
        return {}
    current = await _fetch_limit_data()
    if current:
        return {
            "up": current.get("today_up"),
            "down": current.get("today_down"),
            "break": current.get("today_break"),
            "lianban": current.get("today_lianban")
        }
    return snapshot


def _limit_progression(lianban_df) -> List[Dict[str, Any]]:
    if lianban_df is None or getattr(lianban_df, "empty", True):
        return []
    col = _pick_col(list(lianban_df.columns), ["连板数", "连板", "连板高度", "涨停板数"])
    if not col:
        return []
    counts: Dict[int, int] = {2: 0, 3: 0, 4: 0, 5: 0, 6: 0}
    for v in lianban_df[col].tolist():
        try:
            n = int(float(v))
        except Exception:
            continue
        if n in counts:
            counts[n] += 1
    return [
        {"from": 1, "to": 2, "count": counts[2]},
        {"from": 2, "to": 3, "count": counts[3]},
        {"from": 3, "to": 4, "count": counts[4]},
        {"from": 4, "to": 5, "count": counts[5]},
        {"from": 5, "to": 6, "count": counts[6]},
    ]


def _limit_promotion_rates(prev_df, curr_df) -> List[Dict[str, Any]]:
    if prev_df is None or getattr(prev_df, "empty", True):
        return []
    if curr_df is None or getattr(curr_df, "empty", True):
        return []
    prev_col = _pick_col(list(prev_df.columns), ["连板数", "连板", "连板高度", "连续涨停天数", "涨停板数"])
    curr_col = _pick_col(list(curr_df.columns), ["连板数", "连板", "连板高度", "连续涨停天数", "涨停板数"])
    if not prev_col or not curr_col:
        return []
    prev_series = prev_df[prev_col].apply(_safe_float).fillna(1)
    curr_series = curr_df[curr_col].apply(_safe_float).fillna(1)
    try:
        max_days = int(max(prev_series.max() or 0, curr_series.max() or 0))
    except Exception:
        max_days = 0
    if max_days <= 0:
        return []
    code_col = _pick_col(list(curr_df.columns), ["代码", "股票代码", "code", "symbol"])
    name_map = _extract_names(curr_df)
    items: List[Dict[str, Any]] = []
    for days in range(1, max_days + 1):
        prev_count = int((prev_series == days).sum())
        curr_mask = curr_series == (days + 1)
        curr_count = int(curr_mask.sum())
        rate = (curr_count / prev_count) if prev_count else None
        stocks = []
        if code_col and curr_count:
            for _, row in curr_df.loc[curr_mask].head(30).iterrows():
                code = str(row.get(code_col, "")).strip().zfill(6)
                name = name_map.get(code, "")
                if code:
                    stocks.append({"code": code, "name": name})
        items.append({
            "from": days,
            "to": days + 1,
            "success": curr_count,
            "total": prev_count,
            "rate": rate,
            "stocks": stocks
        })
    return items


def _find_reason_col(cols: List[str]) -> Optional[str]:
    if not cols:
        return None
    priority = ["涨停原因", "涨停概念", "原因类别", "涨停原因类别", "概念板块", "所属概念", "概念", "题材", "热点", "属性"]
    for key in priority:
        for c in cols:
            if key in str(c):
                return c
    return None


def _limitup_concepts(df) -> Dict[str, int]:
    if df is None or getattr(df, "empty", True):
        return {}
    col = _find_reason_col(list(df.columns))
    if not col:
        logger.warning(f"⚠️ 未找到概念列，列名预览: {list(df.columns)[:12]}")
        return {}
    logger.info(f"🎯 概念统计列: {col}")
    counter: Dict[str, int] = {}
    for v in df[col].tolist():
        if v is None:
            continue
        parts = re.split(r"[+|、，,;/；\s]+", str(v))
        for p in parts:
            t = str(p).strip()
            if not t or t.lower() in {"nan", "none"}:
                continue
            counter[t] = counter.get(t, 0) + 1
    logger.info(f"📈 概念统计结果数: {len(counter)}")
    return counter


def _limitup_concepts_with_stocks(df, limit_per_concept: int = 50) -> Dict[str, Dict[str, Any]]:
    if df is None or getattr(df, "empty", True):
        return {}
    cols = list(df.columns)
    reason_col = _find_reason_col(cols)
    if not reason_col:
        logger.warning(f"⚠️ 未找到概念列，列名预览: {list(df.columns)[:12]}")
        return {}
    code_col = _pick_col(cols, ["代码", "股票代码", "code", "symbol"])
    name_col = _pick_col(cols, ["名称", "股票简称", "股票名称", "简称", "名字", "name"])
    result: Dict[str, Dict[str, Any]] = {}
    for _, row in df.iterrows():
        reason_val = row.get(reason_col)
        if reason_val is None:
            continue
        code = str(row.get(code_col, "")).strip().zfill(6) if code_col else ""
        name = str(row.get(name_col, "")).strip() if name_col else ""
        parts = re.split(r"[+|、，,;/；\s]+", str(reason_val))
        for p in parts:
            concept = str(p).strip()
            if not concept or concept.lower() in {"nan", "none"}:
                continue
            bucket = result.get(concept)
            if not bucket:
                bucket = {"count": 0, "stocks": [], "code_set": set()}
                result[concept] = bucket
            bucket["count"] += 1
            if code:
                code_set = bucket["code_set"]
                if code not in code_set and len(bucket["stocks"]) < limit_per_concept:
                    code_set.add(code)
                    bucket["stocks"].append({"code": code, "name": name or code})
    for item in result.values():
        item.pop("code_set", None)
    logger.info(f"📈 概念统计结果数: {len(result)}")
    return result


def _merge_limitup_concepts(
    today_df,
    prev_df,
    limit: int = 12,
    include_stocks: bool = False,
    stock_limit: int = 50
) -> List[Dict[str, Any]]:
    if include_stocks:
        today_map = _limitup_concepts_with_stocks(today_df, stock_limit)
        prev_map = _limitup_concepts_with_stocks(prev_df, stock_limit)
        keys = set(today_map) | set(prev_map)
        items = []
        for k in keys:
            today_item = today_map.get(k) or {}
            prev_item = prev_map.get(k) or {}
            today = today_item.get("count", 0)
            prev = prev_item.get("count", 0)
            items.append({
                "concept": k,
                "today": today,
                "yesterday": prev,
                "change": today - prev,
                "today_stocks": today_item.get("stocks", []),
                "yesterday_stocks": prev_item.get("stocks", [])
            })
        items.sort(key=lambda x: (x["today"], x["change"]), reverse=True)
        return items[:limit]
    today_map = _limitup_concepts(today_df)
    prev_map = _limitup_concepts(prev_df)
    keys = set(today_map) | set(prev_map)
    items = []
    for k in keys:
        today = today_map.get(k, 0)
        prev = prev_map.get(k, 0)
        items.append({
            "concept": k,
            "today": today,
            "yesterday": prev,
            "change": today - prev
        })
    items.sort(key=lambda x: (x["today"], x["change"]), reverse=True)
    return items[:limit]


def _limitup_continuous_list(df, limit: int = 200) -> List[Dict[str, Any]]:
    if df is None or getattr(df, "empty", True):
        return []
    cols = list(df.columns)
    days_col = _pick_col(cols, ["连板数", "连板", "连板高度", "连续涨停天数", "涨停板数"]) or _pick_col_contains(
        cols, ["连板数", "连板", "连板高度", "连续涨停天数", "涨停板数"]
    )
    code_col = _pick_col(cols, ["代码", "股票代码", "code", "symbol"])
    name_col = _pick_col(cols, ["名称", "股票简称", "股票名称", "简称", "名字", "name"])
    price_col = _pick_col(cols, ["最新价", "最新", "收盘价", "价格", "现价"])
    reason_col = _find_reason_col(cols)
    first_time_col = _pick_col(cols, ["首次涨停时间", "首次封板时间", "首次涨停"]) or _pick_col_contains(
        cols, ["首次涨停时间", "首次封板时间", "首次涨停"]
    )
    last_time_col = _pick_col(cols, ["最终涨停时间", "最终封板时间", "最后封板时间"]) or _pick_col_contains(
        cols, ["最终涨停时间", "最终封板时间", "最后封板时间"]
    )
    order_vol_col = _pick_col(cols, ["涨停封单量", "封单量"]) or _pick_col_contains(cols, ["涨停封单量", "封单量"])
    order_amt_col = _pick_col(cols, ["涨停封单额", "封单额"]) or _pick_col_contains(cols, ["涨停封单额", "封单额"])
    type_col = _pick_col(cols, ["涨停类型", "类型"]) or _pick_col_contains(cols, ["涨停类型", "类型"])
    if not code_col:
        return []
    df_sorted = df
    if days_col:
        try:
            df_sorted = df_sorted.copy()
            df_sorted[days_col] = df_sorted[days_col].apply(_safe_float).fillna(1)
            df_sorted = df_sorted.sort_values(days_col, ascending=False)
        except Exception:
            df_sorted = df
    items: List[Dict[str, Any]] = []
    for _, row in df_sorted.head(limit).iterrows():
        code = str(row.get(code_col, "")).strip().zfill(6)
        if not code:
            continue
        item: Dict[str, Any] = {"code": code}
        if name_col:
            item["name"] = str(row.get(name_col, "")).strip()
        if days_col:
            item["days"] = int((_safe_float(row.get(days_col)) or 1))
        if price_col:
            item["price"] = _safe_float(row.get(price_col))
        if reason_col:
            item["reason"] = str(row.get(reason_col, "")).strip()
        if first_time_col:
            item["first_time"] = str(row.get(first_time_col, "")).strip()
        if last_time_col:
            item["last_time"] = str(row.get(last_time_col, "")).strip()
        if order_vol_col:
            item["order_volume"] = _safe_float(row.get(order_vol_col))
        if order_amt_col:
            item["order_amount"] = _safe_float(row.get(order_amt_col))
        if type_col:
            item["limit_type"] = str(row.get(type_col, "")).strip()
        items.append(item)
    return items


def _promotion_rates_with_reason(prev_df, curr_df) -> List[Dict[str, Any]]:
    if prev_df is None or getattr(prev_df, "empty", True):
        return []
    if curr_df is None or getattr(curr_df, "empty", True):
        return []
    prev_col = _pick_col(list(prev_df.columns), ["连板数", "连板", "连板高度", "连续涨停天数", "涨停板数"])
    curr_col = _pick_col(list(curr_df.columns), ["连板数", "连板", "连板高度", "连续涨停天数", "涨停板数"])
    if not prev_col or not curr_col:
        return []
    prev_series = prev_df[prev_col].apply(_safe_float).fillna(1)
    curr_series = curr_df[curr_col].apply(_safe_float).fillna(1)
    try:
        max_days = int(max(prev_series.max() or 0, curr_series.max() or 0))
    except Exception:
        max_days = 0
    if max_days <= 0:
        return []
    code_col = _pick_col(list(curr_df.columns), ["代码", "股票代码", "code", "symbol"])
    name_map = _extract_names(curr_df)
    reason_col = _find_reason_col(list(curr_df.columns))
    items: List[Dict[str, Any]] = []
    for days in range(1, max_days + 1):
        prev_count = int((prev_series == days).sum())
        curr_mask = curr_series == (days + 1)
        curr_count = int(curr_mask.sum())
        rate = (curr_count / prev_count) if prev_count else None
        stocks = []
        if code_col and curr_count:
            for _, row in curr_df.loc[curr_mask].head(30).iterrows():
                code = str(row.get(code_col, "")).strip().zfill(6)
                name = name_map.get(code, "")
                if code:
                    stock: Dict[str, Any] = {"code": code, "name": name}
                    if reason_col:
                        stock["reason"] = str(row.get(reason_col, "")).strip()
                    stocks.append(stock)
        items.append({
            "from": days,
            "to": days + 1,
            "success": curr_count,
            "total": prev_count,
            "rate": rate,
            "stocks": stocks
        })
    return items


async def _fetch_watchlist_from_db(limit: int = 6) -> List[Dict[str, Any]]:
    try:
        db = get_mongo_db()
        quotes = await db["market_quotes"].find(
            {"code": {"$regex": r"^\d{6}$"}},
            {"code": 1, "pct_chg": 1, "close": 1, "amount": 1, "_id": 0}
        ).sort("amount", -1).limit(limit).to_list(length=limit)
        if not quotes:
            return []
        codes = [q.get("code") for q in quotes if q.get("code")]
        basics = await db["stock_basic_info"].find(
            {"code": {"$in": codes}},
            {"code": 1, "name": 1, "_id": 0}
        ).to_list(length=len(codes))
        name_map = {str(b.get("code")).zfill(6): b.get("name") for b in basics if b.get("name")}
        items = []
        for q in quotes:
            code = str(q.get("code")).zfill(6)
            items.append({
                "code": code,
                "name": name_map.get(code, code),
                "price": q.get("close"),
                "chg": q.get("pct_chg"),
                "volume": q.get("amount")
            })
        return items
    except Exception as e:
        logger.error(f"从数据库获取热门关注失败: {e}")
        return []

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

    # 行情
    q = await db["market_quotes"].find_one({"code": code6}, {"_id": 0})

    # 🔥 调试日志：查看查询结果
    logger.info(f"🔍 查询 market_quotes: code={code6}")
    if q:
        logger.info(f"  ✅ 找到数据: volume={q.get('volume')}, amount={q.get('amount')}, volume_ratio={q.get('volume_ratio')}")
    else:
        logger.info(f"  ❌ 未找到数据")

    # 🔥 基础信息 - 按数据源优先级查询
    from app.core.unified_config import UnifiedConfigManager
    config = UnifiedConfigManager()
    data_source_configs = await config.get_data_source_configs_async()

    # 提取启用的数据源，按优先级排序
    enabled_sources = [
        ds.type.lower() for ds in data_source_configs
        if ds.enabled and ds.type.lower() in ['tushare', 'akshare', 'baostock']
    ]

    if not enabled_sources:
        enabled_sources = ['tushare', 'akshare', 'baostock']

    # 按优先级查询基础信息
    b = None
    for src in enabled_sources:
        b = await db["stock_basic_info"].find_one({"code": code6, "source": src}, {"_id": 0})
        if b:
            break

    # 如果所有数据源都没有，尝试不带 source 条件查询（兼容旧数据）
    if not b:
        b = await db["stock_basic_info"].find_one({"code": code6}, {"_id": 0})

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
        logger.info(f"🔍 计算振幅: high={high}, low={low}, prev_close={prev_close}")
        if high is not None and low is not None and prev_close is not None and prev_close > 0:
            amplitude = round((float(high) - float(low)) / float(prev_close) * 100, 2)
            amplitude_date = (q or {}).get("trade_date")  # 来自实时数据
            logger.info(f"  ✅ 振幅计算成功: {amplitude}%")
        else:
            logger.warning(f"  ⚠️ 数据不完整，无法计算振幅")
    except Exception as e:
        logger.warning(f"  ❌ 计算振幅失败: {e}")
        amplitude = None

    data = {
        "code": code6,
        "name": (b or {}).get("name"),
        "market": (b or {}).get("market"),
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
        source_priority = ["tushare", "multi_source", "akshare", "baostock"]
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
        # 获取数据源优先级配置
        from app.core.unified_config import UnifiedConfigManager
        config = UnifiedConfigManager()
        data_source_configs = await config.get_data_source_configs_async()

        # 提取启用的数据源，按优先级排序
        enabled_sources = [
            ds.type.lower() for ds in data_source_configs
            if ds.enabled and ds.type.lower() in ['tushare', 'akshare', 'baostock']
        ]

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
    import asyncio

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
        # ROE（净资产收益率）
        if financial_data.get("financial_indicators"):
            indicators = financial_data["financial_indicators"]
            data["roe"] = indicators.get("roe")
            data["debt_ratio"] = indicators.get("debt_to_assets")

        # 如果 financial_indicators 中没有，尝试从顶层字段获取
        if data["roe"] is None:
            data["roe"] = financial_data.get("roe")
        if data["debt_ratio"] is None:
            data["debt_ratio"] = financial_data.get("debt_to_assets")

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

    return ok(data)


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

    # 1. 优先从 MongoDB 缓存获取
    try:
        from tradingagents.dataflows.cache.mongodb_cache_adapter import get_mongodb_cache_adapter
        adapter = get_mongodb_cache_adapter()

        # 计算日期范围
        end_date = now.strftime("%Y-%m-%d")
        start_date = (now - timedelta(days=limit * 2)).strftime("%Y-%m-%d")

        logger.info(f"🔍 尝试从 MongoDB 获取 K 线数据: {code_padded}, period={period} (MongoDB: {mongodb_period}), limit={limit}")
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
            logger.info(f"✅ 从 MongoDB 获取到 {len(items)} 条 K 线数据")
    except Exception as e:
        logger.warning(f"⚠️ MongoDB 获取 K 线失败: {e}")

    # 2. 如果 MongoDB 没有数据，降级到外部 API（带超时保护）
    if not items:
        logger.info(f"📡 MongoDB 无数据，降级到外部 API")
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

    # 🔥 3. 检查是否需要添加当天实时数据（仅针对日线）
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
        # 港股：暂时返回空数据（TODO: 实现港股新闻）
        data = {
            "code": normalized_code,
            "days": days,
            "limit": limit,
            "source": "none",
            "items": []
        }
        return ok(data)
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


@router.get("/market/overview", response_model=dict)
async def get_market_overview(
    sector_limit: int = Query(12, description="行业板块数量"),
    current_user: dict = Depends(get_current_user)
):
    try:
        now_ts = time.time()
        cache_data = _MARKET_OVERVIEW_CACHE.get("data")
        cache_ts = _MARKET_OVERVIEW_CACHE.get("ts", 0.0)
        if cache_data and (now_ts - cache_ts) < _MARKET_OVERVIEW_TTL:
            return ok(cache_data)

        sectors_task = _with_timeout(_fetch_sector_cards(sector_limit), 8.0, [], "板块")
        metrics_task = _with_timeout(_fetch_market_metrics(), 12.0, [], "指标")
        sectors, metrics = await asyncio.gather(sectors_task, metrics_task)
        if not metrics:
            metrics = await _fetch_market_metrics_from_db()
        if not metrics:
            metrics = [
                {"name": "市场成交额", "value": "-", "desc": "全市场成交额"},
                {"name": "平均市盈率", "value": "-", "desc": "动态市盈率均值"},
                {"name": "平均换手率", "value": "-", "desc": "全市场换手率均值"},
                {"name": "涨跌家数", "value": "-", "desc": "上涨/下跌家数"}
            ]
        if not sectors:
            sectors = await _fetch_sector_cards_from_db(sector_limit)

        trade_dates = await _with_timeout(_fetch_trade_dates(), 6.0, [], "交易日")
        current_trade_date = trade_dates[-1] if trade_dates else None
        prev_trade_date = trade_dates[-2] if len(trade_dates) >= 2 else None
        if current_trade_date:
            limit_today_task = _with_timeout(_fetch_limit_data_with_date(current_trade_date), 12.0, {}, "涨跌停池")
        else:
            limit_today_task = _with_timeout(_fetch_limit_data(), 12.0, {}, "涨跌停池")
        if prev_trade_date:
            limit_prev_task = _with_timeout(_fetch_limit_data_with_date(prev_trade_date), 12.0, {}, "昨日涨跌停池")
        else:
            limit_prev_task = _with_timeout(_fetch_limit_data_with_date(current_trade_date), 12.0, {}, "昨日涨跌停池") if current_trade_date else _with_timeout(_fetch_limit_data(), 12.0, {}, "昨日涨跌停池")
        limit_today, limit_prev = await asyncio.gather(limit_today_task, limit_prev_task)
        if limit_today and "today_up" in limit_today:
            limit_today = {
                "up": limit_today.get("today_up"),
                "down": limit_today.get("today_down"),
                "break": limit_today.get("today_break"),
                "lianban": limit_today.get("today_lianban")
            }
        if limit_prev and "today_up" in limit_prev:
            limit_prev = {
                "up": limit_prev.get("today_up"),
                "down": limit_prev.get("today_down"),
                "break": limit_prev.get("today_break"),
                "lianban": limit_prev.get("today_lianban")
            }
        if current_trade_date and _df_count(limit_today.get("up")) == 0:
            logger.warning("⚠️ 按日期涨停池为空，回退实时涨停池")
            limit_today_fallback = await _with_timeout(_fetch_limit_data(), 12.0, {}, "涨跌停池")
            if limit_today_fallback and "today_up" in limit_today_fallback:
                limit_today = {
                    "up": limit_today_fallback.get("today_up"),
                    "down": limit_today_fallback.get("today_down"),
                    "break": limit_today_fallback.get("today_break"),
                    "lianban": limit_today_fallback.get("today_lianban")
                }

        today_up = _df_count(limit_today.get("up"))
        today_down = _df_count(limit_today.get("down"))
        prev_up = _df_count(limit_prev.get("up"))
        prev_down = _df_count(limit_prev.get("down"))
        break_count = _df_count(limit_today.get("break"))
        lianban_today = _df_count(limit_today.get("lianban"))

        yesterday_limitup_codes = _extract_codes(limit_prev.get("up"))
        yesterday_up_total = len(yesterday_limitup_codes)
        yesterday_up_today_up = 0
        if yesterday_limitup_codes:
            db = get_mongo_db()
            docs = await db["market_quotes"].find(
                {"code": {"$in": yesterday_limitup_codes}},
                {"code": 1, "pct_chg": 1, "_id": 0}
            ).to_list(length=len(yesterday_limitup_codes))
            for d in docs:
                if (_safe_float(d.get("pct_chg")) or 0) > 0:
                    yesterday_up_today_up += 1

        lianban_upgraded = 0
        if yesterday_limitup_codes:
            today_up_codes = set(_extract_codes(limit_today.get("up")))
            lianban_upgraded = len([c for c in yesterday_limitup_codes if c in today_up_codes])

        break_total = break_count + today_up
        sentiment_up_list = _build_stock_list(limit_prev.get("up"), 300)
        sentiment_today_up_list = _build_stock_list(limit_today.get("up"), 300)
        sentiment_break_list = _build_stock_list(limit_today.get("break"), 300)
        break_pool = {s["code"]: s for s in sentiment_break_list}
        limit_break_stocks = list(break_pool.values())
        today_up_pool = {s["code"]: s for s in sentiment_today_up_list}
        limit_up_today_stocks = list(today_up_pool.values())
        sentiment = {
            "yesterday_limit_up_up_rate": (yesterday_up_today_up / yesterday_up_total) if yesterday_up_total else None,
            "lianban_upgrade_rate": (lianban_upgraded / yesterday_up_total) if yesterday_up_total else None,
            "limit_break_rate": (break_count / break_total) if break_total else None
        }
        sentiment_detail = {
            "yesterday_limit_up_up_rate": {"success": yesterday_up_today_up, "total": yesterday_up_total, "stocks": limit_up_today_stocks},
            "lianban_upgrade_rate": {"success": lianban_upgraded, "total": yesterday_up_total, "stocks": limit_up_today_stocks},
            "limit_break_rate": {"success": break_count, "total": break_total, "stocks": limit_break_stocks}
        }
        limit_change = {
            "today_up": today_up,
            "today_down": today_down,
            "yesterday_up": prev_up,
            "yesterday_down": prev_down,
            "up_change": today_up - prev_up,
            "down_change": today_down - prev_down
        }
        limit_progression = _limit_progression(limit_today.get("lianban"))
        promotion_rates = _limit_promotion_rates(limit_prev.get("up"), limit_today.get("up"))
        limitup_concepts = _merge_limitup_concepts(limit_today.get("up"), limit_prev.get("up"))
        if not limitup_concepts and current_trade_date:
            logger.warning("⚠️ 涨停概念为空，尝试 wencai 概念兜底")
            wencai_today = await _fetch_wencai_limitup(current_trade_date)
            wencai_prev = await _fetch_wencai_limitup(prev_trade_date) if prev_trade_date else None
            limitup_concepts = _merge_limitup_concepts(wencai_today, wencai_prev)
        logger.info(f"📊 概念条目数: {len(limitup_concepts)}")
        sector_limitup = await _count_sector_limitup(limit_today.get("up"))
        if not sector_limitup and current_trade_date:
            logger.warning("⚠️ 板块涨停分布为空，尝试 wencai 兜底")
            wencai_today = await _fetch_wencai_limitup(current_trade_date)
            if wencai_today is not None:
                sector_limitup = await _count_sector_limitup(wencai_today)
        logger.info(f"🏷️ 板块涨停条目数: {len(sector_limitup)}")

        favorites_service = FavoritesService()
        favorites = await favorites_service.get_user_favorites(current_user.get("id", ""))
        watchlist = []
        watchlist_source = "favorites"
        for item in favorites:
            watchlist.append({
                "code": item.get("stock_code"),
                "name": item.get("stock_name"),
                "price": item.get("current_price"),
                "chg": item.get("change_percent"),
                "volume": item.get("volume")
            })
        if not watchlist:
            watchlist = await _fetch_watchlist_from_db(6)
            watchlist_source = "market"

        industries = [s.get("name") for s in sectors if s.get("name")]
        filters = {
            "industries": industries[:12],
            "markets": ["A股"],
            "risks": ["低风险", "中风险", "高风险"]
        }

        data = {
            "updated_at": datetime.utcnow().isoformat(),
            "indices": [],
            "sectors": sectors,
            "watchlist": watchlist,
            "watchlist_source": watchlist_source,
            "metrics": metrics,
            "filters": filters,
            "sentiment": sentiment,
            "limit_change": limit_change,
            "limit_progression": limit_progression,
            "promotion_rates": promotion_rates,
            "limitup_concepts": limitup_concepts,
            "sentiment_detail": sentiment_detail,
            "sector_limitup": sector_limitup
        }
        if sectors or metrics or watchlist or sentiment or limit_change or limit_progression or sector_limitup:
            _MARKET_OVERVIEW_CACHE["ts"] = time.time()
            _MARKET_OVERVIEW_CACHE["data"] = data
        return ok(data)
    except Exception as e:
        logger.error(f"获取市场概览失败: {e}", exc_info=True)
        cache_data = _MARKET_OVERVIEW_CACHE.get("data")
        if cache_data:
            return ok(cache_data)
        data = {
            "updated_at": datetime.utcnow().isoformat(),
            "indices": [],
            "sectors": [],
            "watchlist": [],
            "watchlist_source": "favorites",
            "metrics": [
                {"name": "市场成交额", "value": "-", "desc": "全市场成交额"},
                {"name": "平均市盈率", "value": "-", "desc": "动态市盈率均值"},
                {"name": "平均换手率", "value": "-", "desc": "全市场换手率均值"},
                {"name": "涨跌家数", "value": "-", "desc": "上涨/下跌家数"}
            ],
            "filters": {"industries": [], "markets": ["A股"], "risks": ["低风险", "中风险", "高风险"]},
            "sentiment": {
                "yesterday_limit_up_up_rate": None,
                "lianban_upgrade_rate": None,
                "limit_break_rate": None
            },
            "sentiment_detail": {
                "yesterday_limit_up_up_rate": {"success": 0, "total": 0},
                "lianban_upgrade_rate": {"success": 0, "total": 0},
                "limit_break_rate": {"success": 0, "total": 0}
            },
            "limit_change": {
                "today_up": 0,
                "today_down": 0,
                "yesterday_up": 0,
                "yesterday_down": 0,
                "up_change": 0,
                "down_change": 0
            },
            "limit_progression": [],
            "promotion_rates": [],
            "limitup_concepts": [],
            "sector_limitup": []
        }
        return ok(data)


@router.get("/market/limitup-analysis", response_model=dict)
async def get_limitup_analysis(
    date: Optional[str] = Query(None, description="交易日YYYY-MM-DD"),
    current_user: dict = Depends(get_current_user)
):
    try:
        trade_dates = await _with_timeout(_fetch_trade_dates(), 6.0, [], "交易日")
        if not trade_dates:
            return ok({
                "selected_date": None,
                "previous_date": None,
                "sentiment": {
                    "yesterday_up": {"success": 0, "total": 0, "rate": None},
                    "lianban": {"success": 0, "total": 0, "rate": None},
                    "break": {"success": 0, "total": 0, "rate": None}
                },
                "sentiment_detail": {
                    "yesterday_up": {"success": 0, "total": 0, "stocks": []},
                    "lianban": {"success": 0, "total": 0, "stocks": []},
                    "break": {"success": 0, "total": 0}
                },
                "limit_change": {
                    "selected_up": 0,
                    "selected_down": 0,
                    "previous_up": 0,
                    "previous_down": 0,
                    "up_change": 0,
                    "down_change": 0
                },
                "concepts": [],
                "continuous": [],
                "promotion_rates": []
            })
        target = _normalize_date_str(date) if date else trade_dates[-1]
        if target not in trade_dates:
            candidates = [d for d in trade_dates if d <= target]
            target = candidates[-1] if candidates else trade_dates[-1]
        idx = trade_dates.index(target) if target in trade_dates else len(trade_dates) - 1
        prev = trade_dates[idx - 1] if idx > 0 else None

        selected_task = _with_timeout(_fetch_limit_data_with_date(target), 12.0, {}, "涨跌停池")
        if prev:
            prev_task = _with_timeout(_fetch_limit_data_with_date(prev), 12.0, {}, "昨日涨跌停池")
        else:
            prev_task = _with_timeout(_fetch_limit_data_with_date(target), 12.0, {}, "昨日涨跌停池")
        selected, previous = await asyncio.gather(selected_task, prev_task)
        if target == trade_dates[-1] and _df_count(selected.get("up")) == 0:
            logger.warning("⚠️ 按日期涨停池为空，回退实时涨停池")
            selected_fallback = await _with_timeout(_fetch_limit_data(), 12.0, {}, "涨跌停池")
            if selected_fallback and "today_up" in selected_fallback:
                selected = {
                    "up": selected_fallback.get("today_up"),
                    "down": selected_fallback.get("today_down"),
                    "break": selected_fallback.get("today_break"),
                    "lianban": selected_fallback.get("today_lianban")
                }

        today_up = _df_count(selected.get("up"))
        today_down = _df_count(selected.get("down"))
        prev_up = _df_count(previous.get("up"))
        prev_down = _df_count(previous.get("down"))
        break_count = _df_count(selected.get("break"))
        break_total = break_count + today_up

        yesterday_limitup_codes = _extract_codes(previous.get("up"))
        yesterday_up_total = len(yesterday_limitup_codes)
        today_up_codes = set(_extract_codes(selected.get("up")))
        lianban_upgraded = len([c for c in yesterday_limitup_codes if c in today_up_codes]) if yesterday_limitup_codes else 0

        yesterday_up_today_up = 0
        yesterday_up_today_total = 0
        yesterday_up_stocks: List[Dict[str, Any]] = []
        if target == trade_dates[-1] and yesterday_limitup_codes:
            db = get_mongo_db()
            docs = await db["market_quotes"].find(
                {"code": {"$in": yesterday_limitup_codes}},
                {"code": 1, "pct_chg": 1, "_id": 0}
            ).to_list(length=len(yesterday_limitup_codes))
            yesterday_up_today_total = len(docs)
            up_codes: List[str] = []
            for d in docs:
                if (_safe_float(d.get("pct_chg")) or 0) > 0:
                    yesterday_up_today_up += 1
                    code = str(d.get("code") or "").zfill(6)
                    if code:
                        up_codes.append(code)
            if up_codes:
                basics = await db["stock_basic_info"].find(
                    {"code": {"$in": up_codes}},
                    {"code": 1, "name": 1, "_id": 0}
                ).to_list(length=len(up_codes))
                name_map = {str(b.get("code")).zfill(6): b.get("name") for b in basics if b.get("name")}
                yesterday_up_stocks = [{"code": code, "name": name_map.get(code) or code} for code in up_codes]

        sentiment = {
            "yesterday_up": {
                "success": yesterday_up_today_up,
                "total": yesterday_up_today_total,
                "rate": (yesterday_up_today_up / yesterday_up_today_total) if yesterday_up_today_total else None
            },
            "lianban": {
                "success": lianban_upgraded,
                "total": yesterday_up_total,
                "rate": (lianban_upgraded / yesterday_up_total) if yesterday_up_total else None
            },
            "break": {
                "success": break_count,
                "total": break_total,
                "rate": (break_count / break_total) if break_total else None
            }
        }

        lianban_codes = [c for c in yesterday_limitup_codes if c in today_up_codes] if yesterday_limitup_codes else []
        lianban_stocks = _build_stock_list_by_codes(selected.get("up"), lianban_codes, 60, True)
        sentiment_detail = {
            "yesterday_up": {"success": yesterday_up_today_up, "total": yesterday_up_today_total, "stocks": yesterday_up_stocks},
            "lianban": {"success": lianban_upgraded, "total": yesterday_up_total, "stocks": lianban_stocks},
            "break": {"success": break_count, "total": break_total}
        }

        concepts = _merge_limitup_concepts(selected.get("up"), previous.get("up"), 10, True)
        if not concepts:
            concepts = _merge_limitup_concepts(selected.get("lianban"), previous.get("lianban"), 10, True)
        if not concepts:
            logger.warning("⚠️ 涨停概念为空，尝试 wencai 概念兜底")
            wencai_today = await _fetch_wencai_limitup(target)
            wencai_prev = await _fetch_wencai_limitup(prev) if prev else None
            concepts = _merge_limitup_concepts(wencai_today, wencai_prev, 10, True)
        logger.info(f"📊 概念条目数: {len(concepts)}")
        continuous = _limitup_continuous_list(selected.get("lianban")) or _limitup_continuous_list(selected.get("up"))
        promotion_rates = _promotion_rates_with_reason(previous.get("up"), selected.get("up"))

        def _format_date(val: Optional[str]) -> Optional[str]:
            if not val:
                return None
            return f"{val[:4]}-{val[4:6]}-{val[6:8]}"

        data = {
            "selected_date": _format_date(target),
            "previous_date": _format_date(prev),
            "sentiment": sentiment,
            "sentiment_detail": sentiment_detail,
            "limit_change": {
                "selected_up": today_up,
                "selected_down": today_down,
                "previous_up": prev_up,
                "previous_down": prev_down,
                "up_change": today_up - prev_up,
                "down_change": today_down - prev_down
            },
            "concepts": concepts,
            "continuous": continuous,
            "promotion_rates": promotion_rates
        }
        return ok(data)
    except Exception as e:
        logger.error(f"获取涨停分析失败: {e}", exc_info=True)
        return ok({
            "selected_date": None,
            "previous_date": None,
            "sentiment": {
                "yesterday_up": {"success": 0, "total": 0, "rate": None},
                "lianban": {"success": 0, "total": 0, "rate": None},
                "break": {"success": 0, "total": 0, "rate": None}
            },
            "sentiment_detail": {
                "yesterday_up": {"success": 0, "total": 0, "stocks": []},
                "lianban": {"success": 0, "total": 0, "stocks": []},
                "break": {"success": 0, "total": 0}
            },
            "limit_change": {
                "selected_up": 0,
                "selected_down": 0,
                "previous_up": 0,
                "previous_down": 0,
                "up_change": 0,
                "down_change": 0
            },
            "concepts": [],
            "continuous": [],
            "promotion_rates": []
        })

