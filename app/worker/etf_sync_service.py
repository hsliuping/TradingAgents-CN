"""
ETF 数据同步服务

使用 AKShare 同步 ETF 基础信息和日线数据到 MongoDB：
- etf_basic_info：ETF 基础信息（代码、名称、规模、跟踪指数等）
- etf_daily_quotes：ETF 日线行情
"""

import asyncio
import logging
from datetime import datetime, timedelta
from functools import partial
from typing import Dict, Any, List, Optional

from app.core.database import get_mongo_db

logger = logging.getLogger(__name__)

# 集合名（与设计文档一致）
ETF_BASIC_INFO_COLLECTION = "etf_basic_info"
ETF_DAILY_QUOTES_COLLECTION = "etf_daily_quotes"
DATA_SOURCE = "akshare"


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
    if code.startswith(("50", "51", "52")):
        return f"{code}.SH"
    if code.startswith(("15", "16")):
        return f"{code}.SZ"
    return f"{code}.SH"


def _fetch_etf_spot_list() -> List[Dict[str, Any]]:
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
            if not (code.startswith(("50", "51", "52")) or code.startswith(("15", "16"))):
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


def _fetch_etf_hist(symbol: str, start_date: str, end_date: str) -> List[Dict[str, Any]]:
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
                "data_source": DATA_SOURCE,
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


class EtfSyncService:
    """ETF 数据同步服务"""

    def __init__(self):
        self.db = None
        self.batch_size = 50
        self.rate_limit_delay = 0.3

    async def initialize(self):
        """初始化数据库连接"""
        self.db = get_mongo_db()
        logger.info("✅ ETF 同步服务初始化完成")

    async def sync_etf_basic_info(self, force_update: bool = False) -> Dict[str, Any]:
        """
        同步 ETF 基础信息到 etf_basic_info 集合

        Returns:
            同步结果统计
        """
        if not self.db:
            await self.initialize()

        stats = {
            "total_processed": 0,
            "success_count": 0,
            "error_count": 0,
            "skipped_count": 0,
            "start_time": datetime.utcnow(),
            "end_time": None,
            "duration": 0,
            "errors": [],
        }

        try:
            loop = asyncio.get_running_loop()
            rows = await loop.run_in_executor(None, _fetch_etf_spot_list)
            if not rows:
                logger.warning("⚠️ 未获取到 ETF 列表")
                return stats

            stats["total_processed"] = len(rows)
            logger.info(f"📊 获取到 {len(rows)} 只 ETF 基础信息")

            collection = self.db[ETF_BASIC_INFO_COLLECTION]
            now = datetime.utcnow()

            for r in rows:
                try:
                    code = r["code"]
                    if not force_update:
                        existing = await collection.find_one({"code": code, "source": DATA_SOURCE})
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
                        "source": DATA_SOURCE,
                        "updated_at": now,
                    }
                    await collection.update_one(
                        {"code": code, "source": DATA_SOURCE},
                        {"$set": doc},
                        upsert=True,
                    )
                    stats["success_count"] += 1
                except Exception as e:
                    stats["error_count"] += 1
                    stats["errors"].append({"code": r.get("code", "?"), "error": str(e)})

                await asyncio.sleep(self.rate_limit_delay / 10)

            stats["end_time"] = datetime.utcnow()
            stats["duration"] = (stats["end_time"] - stats["start_time"]).total_seconds()
            logger.info(
                f"🎉 ETF 基础信息同步完成: 成功 {stats['success_count']}, "
                f"跳过 {stats['skipped_count']}, 错误 {stats['error_count']}, 耗时 {stats['duration']:.2f}s"
            )
        except Exception as e:
            logger.error(f"❌ ETF 基础信息同步失败: {e}", exc_info=True)
            stats["errors"].append({"error": str(e), "context": "sync_etf_basic_info"})

        return stats

    async def sync_etf_daily_quotes(
        self,
        symbols: Optional[List[str]] = None,
        days: int = 30,
        force_update: bool = False,
    ) -> Dict[str, Any]:
        """
        同步 ETF 日线数据到 etf_daily_quotes 集合

        Args:
            symbols: 指定 ETF 代码列表，为空则同步所有 etf_basic_info 中的 ETF
            days: 同步最近 N 天
            force_update: 是否强制覆盖已有数据

        Returns:
            同步结果统计
        """
        if not self.db:
            await self.initialize()

        stats = {
            "total_processed": 0,
            "success_count": 0,
            "error_count": 0,
            "records_inserted": 0,
            "start_time": datetime.utcnow(),
            "end_time": None,
            "duration": 0,
            "errors": [],
        }

        try:
            end_dt = datetime.now()
            start_dt = end_dt - timedelta(days=days)
            start_date = start_dt.strftime("%Y%m%d")
            end_date = end_dt.strftime("%Y%m%d")

            if symbols:
                codes = [_normalize_etf_code(s) for s in symbols if _normalize_etf_code(s)]
            else:
                cursor = self.db[ETF_BASIC_INFO_COLLECTION].find(
                    {"source": DATA_SOURCE},
                    {"code": 1, "_id": 0},
                )
                codes = [d["code"] async for d in cursor]

            if not codes:
                logger.warning("⚠️ 没有可同步的 ETF 代码")
                return stats

            stats["total_processed"] = len(codes)
            logger.info(f"📊 开始同步 {len(codes)} 只 ETF 的日线数据（最近 {days} 天）")

            collection = self.db[ETF_DAILY_QUOTES_COLLECTION]
            loop = asyncio.get_running_loop()

            for i, code in enumerate(codes):
                try:
                    records = await loop.run_in_executor(
                        None,
                        partial(_fetch_etf_hist, code, start_date, end_date),
                    )
                    if not records:
                        continue

                    inserted = 0
                    for rec in records:
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
                        logger.info(f"📈 ETF 日线同步进度: {i + 1}/{len(codes)}")

                    await asyncio.sleep(self.rate_limit_delay)
                except Exception as e:
                    stats["error_count"] += 1
                    stats["errors"].append({"code": code, "error": str(e)})

            stats["end_time"] = datetime.utcnow()
            stats["duration"] = (stats["end_time"] - stats["start_time"]).total_seconds()
            logger.info(
                f"🎉 ETF 日线同步完成: {stats['success_count']}/{len(codes)} 只, "
                f"插入 {stats['records_inserted']} 条, 耗时 {stats['duration']:.2f}s"
            )
        except Exception as e:
            logger.error(f"❌ ETF 日线同步失败: {e}", exc_info=True)
            stats["errors"].append({"error": str(e), "context": "sync_etf_daily_quotes"})

        return stats

    async def sync_all(self, force_update: bool = False, days: int = 30) -> Dict[str, Any]:
        """全量同步：先基础信息，再日线"""
        basic_stats = await self.sync_etf_basic_info(force_update=force_update)
        daily_stats = await self.sync_etf_daily_quotes(days=days, force_update=force_update)
        return {
            "basic_info": basic_stats,
            "daily_quotes": daily_stats,
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
