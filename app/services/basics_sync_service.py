"""
Stock basics synchronization service
- Fetches A-share stock basic info from Tushare
- Enriches with latest market cap (total_mv)
- Upserts into MongoDB collection `stock_basic_info`
- Persists status in collection `sync_status` with key `stock_basics`
- Provides a singleton accessor for reuse across routers/scheduler

This module is async-friendly and offloads blocking IO (Tushare/pandas) to a thread.
"""
from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from motor.motor_asyncio import AsyncIOMotorDatabase
from pymongo import UpdateOne

from app.core.database import get_mongo_db
from app.core.config import settings

from app.services.basics_sync import (
    fetch_stock_basic_df as _fetch_stock_basic_df_util,
    find_latest_trade_date as _find_latest_trade_date_util,
    fetch_daily_basic_mv_map as _fetch_daily_basic_mv_map_util,
    fetch_latest_roe_map as _fetch_latest_roe_map_util,
)

logger = logging.getLogger(__name__)

STATUS_COLLECTION = "sync_status"
DATA_COLLECTION = "stock_basic_info"
JOB_KEY = "stock_basics"


@dataclass
class SyncStats:
    started_at: Optional[str] = None
    finished_at: Optional[str] = None
    status: str = "idle"  # idle|running|success|failed
    total: int = 0
    inserted: int = 0
    updated: int = 0
    errors: int = 0
    message: str = ""
    last_trade_date: Optional[str] = None  # YYYYMMDD


class BasicsSyncService:
    def __init__(self) -> None:
        self._lock = asyncio.Lock()
        self._running = False
        self._last_status: Optional[Dict[str, Any]] = None
        self._indexes_ensured = False

    async def _ensure_indexes(self, db: AsyncIOMotorDatabase) -> None:
        """确保必要的索引存在"""
        if self._indexes_ensured:
            return

        try:
            collection = db[DATA_COLLECTION]
            logger.info("📊 检查并创建股票基础信息索引...")

            # 1. 复合唯一索引：股票代码+数据源（用于 upsert）
            await collection.create_index([
                ("code", 1),
                ("source", 1)
            ], unique=True, name="code_source_unique", background=True)

            # 2. 股票代码索引（查询所有数据源）
            await collection.create_index([("code", 1)], name="code_index", background=True)

            # 3. 数据源索引（按数据源筛选）
            await collection.create_index([("source", 1)], name="source_index", background=True)

            # 4. 股票名称索引（按名称搜索）
            await collection.create_index([("name", 1)], name="name_index", background=True)

            # 5. 行业索引（按行业筛选）
            await collection.create_index([("industry", 1)], name="industry_index", background=True)

            # 6. 市场索引（按市场筛选）
            await collection.create_index([("market", 1)], name="market_index", background=True)

            # 7. 总市值索引（按市值排序）
            await collection.create_index([("total_mv", -1)], name="total_mv_desc", background=True)

            # 8. 流通市值索引（按流通市值排序）
            await collection.create_index([("circ_mv", -1)], name="circ_mv_desc", background=True)

            # 9. 更新时间索引（数据维护）
            await collection.create_index([("updated_at", -1)], name="updated_at_desc", background=True)

            # 10. PE索引（按估值筛选）
            await collection.create_index([("pe", 1)], name="pe_index", background=True)

            # 11. PB索引（按估值筛选）
            await collection.create_index([("pb", 1)], name="pb_index", background=True)

            # 12. 换手率索引（按活跃度筛选）
            await collection.create_index([("turnover_rate", -1)], name="turnover_rate_desc", background=True)

            self._indexes_ensured = True
            logger.info("✅ 股票基础信息索引检查完成")
        except Exception as e:
            # 索引创建失败不应该阻止服务启动
            logger.warning(f"⚠️ 创建索引时出现警告（可能已存在）: {e}")

    async def get_status(self, db: Optional[AsyncIOMotorDatabase] = None) -> Dict[str, Any]:
        """Return last persisted status; falls back to in-memory snapshot."""
        try:
            db = db or get_mongo_db()
            doc = await db[STATUS_COLLECTION].find_one({"job": JOB_KEY})
            if doc:
                doc.pop("_id", None)
                return doc
        except Exception as e:
            logger.warning(f"Failed to load sync status from DB: {e}")
        return self._last_status or {"job": JOB_KEY, "status": "idle"}

    async def _persist_status(self, db: AsyncIOMotorDatabase, stats: Dict[str, Any]) -> None:
        stats["job"] = JOB_KEY
        await db[STATUS_COLLECTION].update_one({"job": JOB_KEY}, {"$set": stats}, upsert=True)
        self._last_status = {k: v for k, v in stats.items() if k != "_id"}

    async def _execute_bulk_write_with_retry(
        self,
        db: AsyncIOMotorDatabase,
        operations: List,
        max_retries: int = 3
    ) -> tuple:
        """
        执行批量写入，带重试机制（线程安全）

        Args:
            db: MongoDB数据库实例
            operations: 批量操作列表
            max_retries: 最大重试次数

        Returns:
            (新增数量, 更新数量)
        """
        try:
            # 🔥 使用线程安全的 bulk_write
            from app.utils.thread_safe_db import safe_bulk_write

            result = await safe_bulk_write(
                collection_name=DATA_COLLECTION,
                operations=operations,
                ordered=False,
                async_db=db,
                max_retries=max_retries
            )

            inserted = len(result.upserted_ids) if result.upserted_ids else 0
            updated = result.modified_count or 0
            logger.debug(f"✅ 批量写入成功: 新增 {inserted}, 更新 {updated}")
            return inserted, updated

        except Exception as e:
            logger.error(f"❌ 批量写入失败: {e}")
            return 0, 0

    async def run_full_sync(self, force: bool = False) -> Dict[str, Any]:
        """Run a full sync. If already running, return current status unless force."""
        async with self._lock:
            if self._running and not force:
                logger.info("Stock basics sync already running; skip start")
                return await self.get_status()
            self._running = True

        db = get_mongo_db()

        # 🔥 确保索引存在（提升查询和 upsert 性能）
        await self._ensure_indexes(db)

        stats = SyncStats()
        stats.started_at = datetime.utcnow().isoformat()
        stats.status = "running"
        await self._persist_status(db, stats.__dict__.copy())

        try:
            # 🔧 移除 TUSHARE_ENABLED 检查，与财务数据、历史数据同步保持一致
            # 只检查 Tushare 连接状态，如果连接失败则报错
            # 注意：如果需要多数据源支持，请使用 MultiSourceBasicsSyncService

            # Step 1: Fetch stock basic list from Tushare (blocking -> thread)
            stock_df = await asyncio.to_thread(self._fetch_stock_basic_df)
            if stock_df is None or getattr(stock_df, "empty", True):
                raise RuntimeError("Tushare returned empty stock_basic list")

            # Step 2: Determine latest trade_date and fetch daily_basic for financial metrics (blocking -> thread)
            latest_trade_date = await asyncio.to_thread(self._find_latest_trade_date)
            stats.last_trade_date = latest_trade_date
            daily_data_map = await asyncio.to_thread(self._fetch_daily_basic_mv_map, latest_trade_date)

            # Step 2b: Fetch latest ROE snapshot from fina_indicator (blocking -> thread)
            roe_map = await asyncio.to_thread(self._fetch_latest_roe_map)

            # Step 3: Upsert into MongoDB (batched bulk writes)
            ops: List[UpdateOne] = []
            now_iso = datetime.utcnow().isoformat()
            for _, row in stock_df.iterrows():  # type: ignore
                name = row.get("name") or ""
                area = row.get("area") or ""
                industry = row.get("industry") or ""
                market = row.get("market") or ""
                list_date = row.get("list_date") or ""
                ts_code = row.get("ts_code") or ""

                # Extract 6-digit stock code from ts_code (e.g., "000001.SZ" -> "000001")
                if isinstance(ts_code, str) and "." in ts_code:
                    code = ts_code.split(".")[0]  # Keep the 6-digit format
                else:
                    # Fallback to symbol with zero-padding if ts_code is invalid
                    symbol = row.get("symbol") or ""
                    code = str(symbol).zfill(6) if symbol else ""

                # 根据 ts_code 判断交易所
                if isinstance(ts_code, str):
                    if ts_code.endswith(".SH"):
                        sse = "上海证券交易所"
                    elif ts_code.endswith(".SZ"):
                        sse = "深圳证券交易所"
                    elif ts_code.endswith(".BJ"):
                        sse = "北京证券交易所"
                    else:
                        sse = "未知"
                else:
                    sse = "未知"

                category = "stock_cn"

                # Extract daily financial metrics - use ts_code directly for matching
                daily_metrics = {}
                if isinstance(ts_code, str) and ts_code in daily_data_map:
                    daily_metrics = daily_data_map[ts_code]

                # Process market cap (convert from 万元 to 亿元)
                total_mv_yi = None
                circ_mv_yi = None
                if "total_mv" in daily_metrics:
                    try:
                        total_mv_yi = float(daily_metrics["total_mv"]) / 10000.0
                    except Exception:
                        pass
                if "circ_mv" in daily_metrics:
                    try:
                        circ_mv_yi = float(daily_metrics["circ_mv"]) / 10000.0
                    except Exception:
                        pass

                # 生成 full_symbol（完整标准化代码）
                full_symbol = self._generate_full_symbol(code)

                doc = {
                    "code": code,
                    "symbol": code,  # 添加 symbol 字段（标准化字段）
                    "name": name,
                    "area": area,
                    "industry": industry,
                    "market": market,
                    "list_date": list_date,
                    "sse": sse,
                    "sec": category,
                    "source": "tushare",  # 🔥 数据源标识
                    "updated_at": now_iso,
                    "full_symbol": full_symbol,  # 添加完整标准化代码
                }

                # Add market cap fields
                if total_mv_yi is not None:
                    doc["total_mv"] = total_mv_yi
                if circ_mv_yi is not None:
                    doc["circ_mv"] = circ_mv_yi

                # Add financial ratios (🔥 新增 ps 和 ps_ttm)
                for field in ["pe", "pb", "ps", "pe_ttm", "pb_mrq", "ps_ttm"]:
                    if field in daily_metrics:
                        doc[field] = daily_metrics[field]
                # ROE from fina_indicator snapshot
                if isinstance(ts_code, str) and ts_code in roe_map:
                    roe_val = roe_map[ts_code].get("roe")
                    if roe_val is not None:
                        doc["roe"] = roe_val

                # Add trading metrics
                for field in ["turnover_rate", "volume_ratio"]:
                    if field in daily_metrics:
                        doc[field] = daily_metrics[field]

                # 🔥 Add share capital fields (total_share, float_share)
                for field in ["total_share", "float_share"]:
                    if field in daily_metrics:
                        doc[field] = daily_metrics[field]

                # 🔥 使用 (code, source) 联合查询条件
                ops.append(
                    UpdateOne({"code": code, "source": "tushare"}, {"$set": doc}, upsert=True)
                )

            inserted = 0
            updated = 0
            errors = 0
            # Execute in chunks to avoid oversized batches
            BATCH = 1000
            for i in range(0, len(ops), BATCH):
                batch = ops[i : i + BATCH]
                batch_inserted, batch_updated = await self._execute_bulk_write_with_retry(db, batch)

                if batch_inserted > 0 or batch_updated > 0:
                    inserted += batch_inserted
                    updated += batch_updated
                else:
                    errors += 1
                    logger.error(f"Bulk write error on batch {i//BATCH}")

            stats.total = len(ops)
            stats.inserted = inserted
            stats.updated = updated
            stats.errors = errors
            stats.status = "success" if errors == 0 else "success_with_errors"
            stats.finished_at = datetime.utcnow().isoformat()
            await self._persist_status(db, stats.__dict__.copy())
            logger.info(
                f"Stock basics sync finished: total={stats.total} inserted={inserted} updated={updated} errors={errors} trade_date={latest_trade_date}"
            )
            return stats.__dict__

        except Exception as e:
            stats.status = "failed"
            stats.message = str(e)
            stats.finished_at = datetime.utcnow().isoformat()
            await self._persist_status(db, stats.__dict__.copy())
            logger.exception(f"Stock basics sync failed: {e}")
            return stats.__dict__
        finally:
            async with self._lock:
                self._running = False

    # ---- Blocking helpers (run in thread) ----
    def _fetch_stock_basic_df(self):
        """委托到 basics_sync.utils 的阻塞式实现"""
        return _fetch_stock_basic_df_util()

    def _find_latest_trade_date(self) -> str:
        """Delegate to basics_sync.utils (blocking)"""
        return _find_latest_trade_date_util()

    def _fetch_daily_basic_mv_map(self, trade_date: str) -> Dict[str, Dict[str, float]]:
        """Delegate to basics_sync.utils (blocking)"""
        return _fetch_daily_basic_mv_map_util(trade_date)

    def _fetch_latest_roe_map(self) -> Dict[str, Dict[str, float]]:
        """Delegate to basics_sync.utils (blocking)"""
        return _fetch_latest_roe_map_util()

    def _generate_full_symbol(self, code: str) -> str:
        """
        根据股票代码生成完整标准化代码

        Args:
            code: 6位股票代码

        Returns:
            完整标准化代码（如 000001.SZ），如果代码无效则返回原始代码（确保不为空）
        """
        # 确保 code 不为空
        if not code:
            return ""

        # 标准化为字符串并去除空格
        code = str(code).strip()

        # 如果长度不是 6，返回原始代码（避免返回 None）
        if len(code) != 6:
            return code

        # 根据代码判断交易所
        if code.startswith(('60', '68', '90')):
            return f"{code}.SS"  # 上海证券交易所
        elif code.startswith(('00', '30', '20')):
            return f"{code}.SZ"  # 深圳证券交易所
        elif code.startswith(('8', '4')):
            return f"{code}.BJ"  # 北京证券交易所
        else:
            # 无法识别的代码，返回原始代码（确保不为空）
            return code if code else ""


# Singleton accessor
_basics_sync_service: Optional[BasicsSyncService] = None


def get_basics_sync_service() -> BasicsSyncService:
    global _basics_sync_service
    if _basics_sync_service is None:
        _basics_sync_service = BasicsSyncService()
    return _basics_sync_service

