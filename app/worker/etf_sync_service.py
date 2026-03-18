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

from app.core.database import get_mongo_db
from app.core.data_source_priority import get_enabled_data_sources_async
from app.services.data_sources.qmt_adapter import QMTAdapter

logger = logging.getLogger(__name__)

# 集合名（与设计文档一致）
ETF_BASIC_INFO_COLLECTION = "etf_basic_info"
ETF_DAILY_QUOTES_COLLECTION = "etf_daily_quotes"
DEFAULT_SOURCE_PRIORITY = ["akshare"]  # 统一配置获取失败时的默认值

ETF_SH_PREFIXES = ("50", "51", "52", "56", "58")
ETF_SZ_PREFIXES = ("15", "16", "18")


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
    return f"{code}.SH"


def _is_etf_code(code: str) -> bool:
    return bool(code) and len(code) == 6 and code.startswith(ETF_SH_PREFIXES + ETF_SZ_PREFIXES)


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
            })
        return rows
    except Exception as e:
        logger.warning(f"Tushare fund_basic 获取失败: {e}")
        return []


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

    async def initialize(self):
        """初始化数据库连接"""
        self.db = get_mongo_db()
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

    async def _sync_basic_by_source(self, source: str, force_update: bool) -> Dict[str, Any]:
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
            if not rows:
                logger.warning(f"⚠️ [{source}] 未获取到 ETF 列表")
                return stats

            stats["total_processed"] = len(rows)
            logger.info(f"📊 [{source}] 获取到 {len(rows)} 只 ETF 基础信息")

            collection = self.db[ETF_BASIC_INFO_COLLECTION]
            now = datetime.utcnow()

            for r in rows:
                try:
                    code = r["code"]
                    if not force_update:
                        existing = await collection.find_one({"code": code, "source": source})
                        if existing and self._is_fresh(existing.get("updated_at"), hours=24):
                            stats["skipped_count"] += 1
                            continue

                    doc = {
                        "code": code,
                        "symbol": code,
                        "name": r.get("name", ""),
                        "full_symbol": r.get("full_symbol", _get_full_symbol(code)),
                        "fund_type": r.get("fund_type", "ETF"),
                        "fund_scale": r.get("fund_scale"),
                        "track_index": r.get("track_index", ""),
                        "source": source,
                        "updated_at": now,
                    }
                    await collection.update_one({"code": code, "source": source}, {"$set": doc}, upsert=True)
                    stats["success_count"] += 1
                except Exception as e:
                    stats["error_count"] += 1
                    stats["errors"].append({"code": r.get("code", "?"), "error": str(e)})
                await asyncio.sleep(self.rate_limit_delay / 10)

            stats["end_time"] = datetime.utcnow()
            stats["duration"] = (stats["end_time"] - stats["start_time"]).total_seconds()
            logger.info(f"🎉 [{source}] ETF 基础信息同步完成: 成功 {stats['success_count']}, 跳过 {stats['skipped_count']}, 错误 {stats['error_count']}")
        except Exception as e:
            logger.error(f"❌ [{source}] ETF 基础信息同步失败: {e}", exc_info=True)
            stats["errors"].append({"error": str(e), "context": "sync_etf_basic_info"})

        return stats

    async def _sync_daily_by_source(self, source: str, symbols: Optional[List[str]], days: int, force_update: bool) -> Dict[str, Any]:
        """按指定数据源同步 ETF 日线"""
        if self.db is None:
            await self.initialize()
        fetch_fn = _FETCH_HIST.get(source)
        if not fetch_fn:
            return {"total_processed": 0, "success_count": 0, "records_inserted": 0, "errors": [{"error": f"未实现的数据源: {source}"}]}

        stats = {"total_processed": 0, "success_count": 0, "error_count": 0, "records_inserted": 0, "start_time": datetime.utcnow(), "end_time": None, "duration": 0, "errors": [], "data_source": source}

        try:
            end_dt = datetime.now()
            start_dt = end_dt - timedelta(days=days)
            start_date = start_dt.strftime("%Y%m%d")
            end_date = end_dt.strftime("%Y%m%d")

            if symbols:
                codes = [_normalize_etf_code(s) for s in symbols if _normalize_etf_code(s)]
            else:
                cursor = self.db[ETF_BASIC_INFO_COLLECTION].find({"source": source}, {"code": 1, "_id": 0})
                codes = [d["code"] async for d in cursor]

            if not codes:
                logger.warning(f"⚠️ [{source}] 没有可同步的 ETF 代码")
                return stats

            stats["total_processed"] = len(codes)
            logger.info(f"📊 [{source}] 开始同步 {len(codes)} 只 ETF 的日线数据（最近 {days} 天）")

            collection = self.db[ETF_DAILY_QUOTES_COLLECTION]
            loop = asyncio.get_running_loop()

            for i, code in enumerate(codes):
                try:
                    records = await loop.run_in_executor(None, partial(fetch_fn, code, start_date, end_date))
                    if not records:
                        continue

                    inserted = 0
                    for rec in records:
                        rec["data_source"] = source
                        key = {"symbol": rec["symbol"], "trade_date": rec["trade_date"]}
                        if not force_update:
                            existing = await collection.find_one(key)
                            if existing:
                                continue
                        await collection.update_one(key, {"$set": {**rec, "updated_at": datetime.utcnow()}}, upsert=True)
                        inserted += 1

                    stats["success_count"] += 1
                    stats["records_inserted"] += inserted

                    if (i + 1) % 20 == 0:
                        logger.info(f"📈 [{source}] ETF 日线同步进度: {i + 1}/{len(codes)}")

                    await asyncio.sleep(self.rate_limit_delay)
                except Exception as e:
                    stats["error_count"] += 1
                    stats["errors"].append({"code": code, "error": str(e)})

            stats["end_time"] = datetime.utcnow()
            stats["duration"] = (stats["end_time"] - stats["start_time"]).total_seconds()
            logger.info(f"🎉 [{source}] ETF 日线同步完成: {stats['success_count']}/{len(codes)} 只, 插入 {stats['records_inserted']} 条")
        except Exception as e:
            logger.error(f"❌ [{source}] ETF 日线同步失败: {e}", exc_info=True)
            stats["errors"].append({"error": str(e), "context": "sync_etf_daily_quotes"})

        return stats

    async def sync_all(self, force_update: bool = False, days: int = 30) -> Dict[str, Any]:
        """
        全量同步：按数据源优先级依次尝试，优先级最高的先调用，同步成功则结束，失败则尝试下一优先级。
        """
        if self.db is None:
            await self.initialize()

        priority = await self._get_source_priority()
        last_error = None

        for source in priority:
            if source not in _FETCH_BASIC:
                logger.debug(f"⏭️ 跳过未实现的数据源: {source}")
                continue

            logger.info(f"🔄 [ETF 同步] 尝试数据源: {source}")

            try:
                basic_stats = await self._sync_basic_by_source(source, force_update)

                # 基础信息同步成功：获取到数据即可（total_processed > 0）
                if basic_stats.get("total_processed", 0) > 0:
                    daily_stats = await self._sync_daily_by_source(source, None, days, force_update)
                    logger.info(f"✅ [ETF 同步] 数据源 {source} 同步完成")
                    return {
                        "basic_info": basic_stats,
                        "daily_quotes": daily_stats,
                        "data_source_used": source,
                    }
                else:
                    last_error = basic_stats.get("errors", [{"error": "未获取到 ETF 列表"}])
                    logger.warning(f"⚠️ [ETF 同步] 数据源 {source} 未获取到数据，尝试下一优先级")
            except Exception as e:
                last_error = str(e)
                logger.warning(f"⚠️ [ETF 同步] 数据源 {source} 失败: {e}，尝试下一优先级")

        logger.error(f"❌ [ETF 同步] 所有数据源均失败，最后错误: {last_error}")
        return {
            "basic_info": {"total_processed": 0, "errors": [{"error": str(last_error)}]},
            "daily_quotes": {"records_inserted": 0},
            "data_source_used": None,
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
        result = await service.sync_all(force_update=force_update, days=days)
        if job_id:
            try:
                from app.services.scheduler_service import mark_job_completed
                await mark_job_completed(job_id, result)
            except Exception:
                pass
        return result
    except Exception as e:
        logger.error(f"❌ ETF 同步失败: {e}", exc_info=True)
        if job_id:
            try:
                from app.services.scheduler_service import mark_job_completed
                await mark_job_completed(job_id, {}, str(e))
            except Exception:
                pass
        raise
