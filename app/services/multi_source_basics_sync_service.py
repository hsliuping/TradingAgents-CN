"""
Multi-source stock basics synchronization service
- Supports multiple data sources with fallback mechanism
- Priority: Tushare > AKShare > BaoStock 
- Fetches A-share stock basic info with extended financial metrics
- Upserts into MongoDB collection `stock_basic_info`
- Provides unified interface for different data sources
"""
from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple
from enum import Enum

from motor.motor_asyncio import AsyncIOMotorDatabase
from pymongo import UpdateOne

from app.core.database import get_mongo_db
from app.services.basics_sync import add_financial_metrics as _add_financial_metrics_util


logger = logging.getLogger(__name__)

# Collection names
COLLECTION_NAME = "stock_basic_info"
STATUS_COLLECTION = "sync_status"
JOB_KEY = "stock_basics_multi_source"
STOCK_LIST_FETCH_TIMEOUT_SECONDS = 45


class DataSourcePriority(Enum):
    """数据源优先级枚举"""
    TUSHARE = 1
    AKSHARE = 2
    BAOSTOCK = 3


@dataclass
class SyncStats:
    """同步统计信息"""
    job: str = JOB_KEY
    data_type: str = "stock_basics"  # 添加data_type字段以符合数据库索引要求
    status: str = "idle"
    started_at: Optional[str] = None
    finished_at: Optional[str] = None
    total: int = 0
    inserted: int = 0
    updated: int = 0
    errors: int = 0
    last_trade_date: Optional[str] = None
    data_sources_used: List[str] = field(default_factory=list)
    source_stats: Dict[str, Dict[str, int]] = field(default_factory=dict)
    message: Optional[str] = None


class MultiSourceBasicsSyncService:
    """多数据源股票基础信息同步服务"""

    def __init__(self):
        self._lock = asyncio.Lock()
        self._running = False
        self._last_status: Optional[Dict[str, Any]] = None
        self._current_task: Optional[asyncio.Task] = None

    async def start_background_sync(self, force: bool = False, preferred_sources: List[str] = None) -> Dict[str, Any]:
        """后台启动同步任务，立即返回当前状态，避免阻塞前端请求。"""
        async with self._lock:
            if self._running:
                status = await self.get_status()
                status["launch_mode"] = "already_running"
                return status

            loop = asyncio.get_running_loop()
            self._current_task = loop.create_task(
                self.run_full_sync(force=force, preferred_sources=preferred_sources)
            )

        status = {
            "job": JOB_KEY,
            "status": "queued",
            "message": "同步任务已提交到后台执行",
            "started_at": datetime.now().isoformat(),
            "launch_mode": "background",
            "preferred_sources": preferred_sources or [],
        }
        self._last_status = status
        return status

    async def _try_mark_running(self, force: bool = False) -> bool:
        async with self._lock:
            if self._running and not force:
                return False
            self._running = True
            return True

    async def start_full_sync(
        self,
        force: bool = False,
        preferred_sources: List[str] = None,
    ) -> Dict[str, Any]:
        """启动后台同步任务并立即返回运行状态。"""
        if not await self._try_mark_running(force=force):
            logger.info("Multi-source stock basics sync already running; skip start")
            return await self.get_status()

        db = get_mongo_db()
        stats = SyncStats()
        stats.started_at = datetime.now().isoformat()
        stats.status = "running"
        stats.message = "Synchronization task started"
        await self._persist_status(db, stats.__dict__.copy())

        asyncio.create_task(self._run_full_sync_impl(db, stats, preferred_sources))
        return stats.__dict__.copy()

    async def get_status(self) -> Dict[str, Any]:
        """获取同步状态"""
        if self._last_status and self._last_status.get("status") == "queued":
            return self._last_status

        db = get_mongo_db()
        doc = await db[STATUS_COLLECTION].find_one({"job": JOB_KEY})
        
        if doc:
            # 移除MongoDB的_id字段以避免序列化问题
            doc.pop("_id", None)
            
            # 🔥 检测僵尸任务：如果状态是running但已经超过30分钟，自动标记为超时
            if doc.get("status") == "running":
                started_at_str = doc.get("started_at")
                if started_at_str:
                    try:
                        started_at = datetime.fromisoformat(started_at_str.replace('Z', '+00:00'))
                        # 如果started_at有时区信息，转换为本地时间
                        if started_at.tzinfo:
                            started_at = started_at.astimezone().replace(tzinfo=None)
                        
                        # 检查是否超过30分钟
                        elapsed = datetime.now() - started_at
                        if elapsed > timedelta(minutes=30):
                            logger.warning(
                                f"⚠️ 检测到僵尸任务: {JOB_KEY} 已运行 {elapsed.total_seconds() / 60:.1f} 分钟，"
                                f"自动标记为超时失败"
                            )
                            # 更新状态为失败
                            doc["status"] = "failed"
                            doc["message"] = f"任务超时（运行时间超过30分钟，实际运行 {elapsed.total_seconds() / 60:.1f} 分钟）"
                            doc["finished_at"] = datetime.now().isoformat()
                            
                            # 保存更新后的状态
                            await self._persist_status(db, doc)
                    except Exception as e:
                        logger.error(f"❌ 检测僵尸任务时出错: {e}")
            
            # 更新内存缓存
            self._last_status = doc
            return doc
        
        return {"job": JOB_KEY, "status": "never_run"}

    async def _persist_status(self, db: AsyncIOMotorDatabase, stats: Dict[str, Any]) -> None:
        """持久化同步状态"""
        stats["job"] = JOB_KEY

        # 使用 upsert 来避免重复键错误
        # 基于 data_type 和 job 进行更新或插入
        filter_query = {
            "data_type": stats.get("data_type", "stock_basics"),
            "job": JOB_KEY
        }

        await db[STATUS_COLLECTION].update_one(
            filter_query,
            {"$set": stats},
            upsert=True
        )

        self._last_status = {k: v for k, v in stats.items() if k != "_id"}

    async def _execute_bulk_write_with_retry(
        self,
        db: AsyncIOMotorDatabase,
        operations: List,
        max_retries: int = 3
    ) -> Tuple[int, int]:
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
                collection_name=COLLECTION_NAME,
                operations=operations,
                ordered=False,
                async_db=db,
                max_retries=max_retries
            )

            inserted = result.upserted_count
            updated = result.modified_count
            logger.debug(f"✅ 批量写入成功: 新增 {inserted}, 更新 {updated}")
            return inserted, updated

        except Exception as e:
            logger.error(f"❌ 批量写入失败: {e}")
            return 0, 0

    async def run_full_sync(self, force: bool = False, preferred_sources: List[str] = None) -> Dict[str, Any]:
        """
        运行完整同步

        Args:
            force: 是否强制运行（即使已在运行中）
            preferred_sources: 优先使用的数据源列表
        """
        if not await self._try_mark_running(force=force):
            logger.info("Multi-source stock basics sync already running; skip start")
            return await self.get_status()

        db = get_mongo_db()
        stats = SyncStats()
        stats.started_at = datetime.now().isoformat()
        stats.status = "running"
        await self._persist_status(db, stats.__dict__.copy())

        return await self._run_full_sync_impl(db, stats, preferred_sources)

    @staticmethod
    def _normalize_preferred_sources(preferred_sources: Optional[List[str]]) -> Optional[List[str]]:
        if not preferred_sources:
            return preferred_sources

        normalized: List[str] = []
        removed_sources: List[str] = []
        for source in preferred_sources:
            source_name = str(source or "").strip().lower()
            if not source_name:
                continue
            if source_name == "qmt":
                removed_sources.append(source_name)
                continue
            if source_name not in normalized:
                normalized.append(source_name)

        if removed_sources:
            logger.info(
                "🧹 [多数据源基础信息同步] 已从优先数据源中排除不适合基础信息启动同步的来源: %s",
                removed_sources,
            )
        return normalized or None

    async def _fetch_stock_list_with_retry(
        self,
        manager,
        preferred_sources: Optional[List[str]],
    ) -> Tuple[Any, Optional[str]]:
        async def _fetch_once(sources: Optional[List[str]], attempt_label: str) -> Tuple[Any, Optional[str]]:
            start = time.perf_counter()
            logger.info(
                "📥 [多数据源基础信息同步] 开始获取股票列表: attempt=%s, preferred_sources=%s, timeout=%ss",
                attempt_label,
                sources or [],
                STOCK_LIST_FETCH_TIMEOUT_SECONDS,
            )
            stock_df, source_used = await asyncio.wait_for(
                asyncio.to_thread(manager.get_stock_list_with_fallback, sources, True),
                timeout=STOCK_LIST_FETCH_TIMEOUT_SECONDS,
            )
            elapsed = time.perf_counter() - start
            logger.info(
                "📥 [多数据源基础信息同步] 股票列表获取完成: attempt=%s, source=%s, records=%s, elapsed=%.2fs",
                attempt_label,
                source_used,
                0 if stock_df is None else len(stock_df),
                elapsed,
            )
            return stock_df, source_used

        try:
            return await _fetch_once(preferred_sources, "primary")
        except asyncio.TimeoutError:
            logger.warning(
                "⏱ [多数据源基础信息同步] 股票列表获取超时: preferred_sources=%s, timeout=%ss",
                preferred_sources or [],
                STOCK_LIST_FETCH_TIMEOUT_SECONDS,
            )
            retry_sources = [source for source in (preferred_sources or []) if source != "qmt"]
            if retry_sources:
                logger.warning(
                    "↩️ [多数据源基础信息同步] 重试股票列表获取，并将 QMT 延后: retry_sources=%s",
                    retry_sources,
                )
                return await _fetch_once(retry_sources, "retry_without_qmt")
            raise

    async def _run_full_sync_impl(
        self,
        db: AsyncIOMotorDatabase,
        stats: SyncStats,
        preferred_sources: List[str] = None,
    ) -> Dict[str, Any]:
        """执行真实同步逻辑；由同步入口或后台任务入口复用。"""

        try:
            preferred_sources = self._normalize_preferred_sources(preferred_sources)
            sync_start = time.perf_counter()
            logger.info(
                "🚀 [多数据源基础信息同步] 开始执行: preferred_sources=%s",
                preferred_sources or [],
            )

            # Step 1: 获取数据源管理器
            from app.services.data_sources.manager import DataSourceManager
            step_start = time.perf_counter()
            manager = DataSourceManager()
            available_adapters = manager.get_available_adapters()

            if not available_adapters:
                raise RuntimeError("No available data sources found")

            logger.info(
                "✅ [多数据源基础信息同步] 可用数据源=%s，耗时=%.2fs",
                [adapter.name for adapter in available_adapters],
                time.perf_counter() - step_start,
            )

            # 如果指定了优先数据源，记录日志
            if preferred_sources:
                logger.info(f"Using preferred data sources: {preferred_sources}")

            # Step 2: 尝试从数据源获取股票列表（排除本地数据源）
            stock_df, source_used = await self._fetch_stock_list_with_retry(manager, preferred_sources)
            if stock_df is None or getattr(stock_df, "empty", True):
                raise RuntimeError("All data sources failed to provide stock list")

            stats.data_sources_used.append(f"stock_list:{source_used}")
            logger.info(f"Successfully fetched {len(stock_df)} stocks from {source_used}")

            # Step 3: 获取最新交易日期和财务数据
            step_start = time.perf_counter()
            latest_trade_date = await asyncio.to_thread(
                manager.find_latest_trade_date_with_fallback, preferred_sources
            )
            stats.last_trade_date = latest_trade_date
            logger.info(
                "🗓️ [多数据源基础信息同步] 最新交易日=%s，耗时=%.2fs",
                latest_trade_date,
                time.perf_counter() - step_start,
            )

            daily_data_map = {}
            daily_source = ""
            if latest_trade_date:
                step_start = time.perf_counter()
                daily_df, daily_source = await asyncio.to_thread(
                    manager.get_daily_basic_with_fallback, latest_trade_date, preferred_sources
                )
                if daily_df is not None and not daily_df.empty:
                    for _, row in daily_df.iterrows():
                        ts_code = row.get("ts_code")
                        if ts_code:
                            daily_data_map[ts_code] = row.to_dict()
                    stats.data_sources_used.append(f"daily_data:{daily_source}")
                logger.info(
                    "📈 [多数据源基础信息同步] daily_basic source=%s, records=%s, elapsed=%.2fs",
                    daily_source or "-",
                    0 if daily_df is None else len(daily_df),
                    time.perf_counter() - step_start,
                )

            from app.services.official_industry_service import (
                INDUSTRY_SOURCE_SYSTEM,
                fetch_industry_mapping,
            )

            step_start = time.perf_counter()
            industry_mapping = await fetch_industry_mapping(refresh_if_empty=True)
            use_system_industry_mapping = bool(industry_mapping)
            if use_system_industry_mapping:
                stats.data_sources_used.append(f"industry_mapping:{INDUSTRY_SOURCE_SYSTEM}")
                logger.info(f"📊 使用系统行业映射集合: {len(industry_mapping)} 只股票")
            logger.info(
                "🏷️ [多数据源基础信息同步] 行业映射加载完成: enabled=%s, elapsed=%.2fs",
                use_system_industry_mapping,
                time.perf_counter() - step_start,
            )

            # Step 5: 处理和更新数据（分批处理）
            ops = []
            inserted = updated = errors = 0
            batch_size = 500  # 🔥 每批处理 500 只股票，避免超时
            total_stocks = len(stock_df)

            logger.info(f"🚀 开始处理 {total_stocks} 只股票，数据源: {source_used}")

            for idx, (_, row) in enumerate(stock_df.iterrows(), 1):
                try:
                    # 提取基础信息
                    name = row.get("name") or ""
                    area = row.get("area") or ""
                    industry = row.get("industry") or ""
                    market = row.get("market") or ""
                    list_date = row.get("list_date") or ""
                    ts_code = row.get("ts_code") or ""

                    # 提取6位股票代码
                    if isinstance(ts_code, str) and "." in ts_code:
                        code = ts_code.split(".")[0]
                    else:
                        symbol = row.get("symbol") or ""
                        code = str(symbol).zfill(6) if symbol else ""

                    mapped_industry = industry_mapping.get(code, "") if use_system_industry_mapping else ""
                    resolved_industry = mapped_industry or industry or "未知"

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

                    # 获取财务数据
                    daily_metrics = {}
                    if isinstance(ts_code, str) and ts_code in daily_data_map:
                        daily_metrics = daily_data_map[ts_code]

                    # 生成 full_symbol（确保不为空）
                    full_symbol = ts_code if ts_code else self._generate_full_symbol(code)

                    # 🔥 确定数据源标识
                    # 根据实际使用的数据源设置 source 字段
                    # 注意：不再使用 "multi_source" 作为默认值，必须有明确的数据源
                    if not source_used:
                        logger.warning(f"⚠️ 股票 {code} 没有明确的数据源，跳过")
                        errors += 1
                        continue
                    data_source = source_used

                    # 构建文档
                    doc = {
                        "code": code,
                        "symbol": code,  # 添加 symbol 字段（标准化字段）
                        "name": name,
                        "area": area,
                        "industry": resolved_industry,
                        "market": market,
                        "list_date": list_date,
                        "sse": sse,
                        "full_symbol": full_symbol,  # 添加 full_symbol 字段
                        "category": category,
                        "source": data_source,  # 🔥 使用实际数据源
                        "updated_at": datetime.now(),
                    }

                    if mapped_industry:
                        doc["industry_source"] = INDUSTRY_SOURCE_SYSTEM

                    # 添加财务指标
                    self._add_financial_metrics(doc, daily_metrics)

                    # 🔥 使用 (code, source) 联合查询条件
                    ops.append(UpdateOne({"code": code, "source": data_source}, {"$set": doc}, upsert=True))

                except Exception as e:
                    logger.error(f"Error processing stock {row.get('ts_code', 'unknown')}: {e}")
                    errors += 1

                # 🔥 分批执行数据库操作
                if len(ops) >= batch_size or idx == total_stocks:
                    if ops:
                        progress_pct = (idx / total_stocks) * 100
                        logger.info(f"📝 执行批量写入: {len(ops)} 条记录 ({idx}/{total_stocks}, {progress_pct:.1f}%)")

                        batch_inserted, batch_updated = await self._execute_bulk_write_with_retry(db, ops)

                        if batch_inserted > 0 or batch_updated > 0:
                            inserted += batch_inserted
                            updated += batch_updated
                            logger.info(f"✅ 批量写入完成: 新增 {batch_inserted}, 更新 {batch_updated} | 累计: 新增 {inserted}, 更新 {updated}, 错误 {errors}")
                        else:
                            errors += len(ops)
                            logger.warning(f"⚠️ 批量写入失败，标记 {len(ops)} 条记录为错误")

                        ops = []  # 清空操作列表

            # Step 7: 更新统计信息
            stats.total = total_stocks  # 🔥 使用总股票数
            stats.inserted = inserted
            stats.updated = updated
            stats.errors = errors
            stats.status = "success" if errors == 0 else "success_with_errors"
            stats.finished_at = datetime.now().isoformat()

            try:
                await self._persist_status(db, stats.__dict__.copy())
                logger.info(
                    f"✅ Multi-source sync finished: total={stats.total} inserted={inserted} "
                    f"updated={updated} errors={errors} sources={stats.data_sources_used}"
                )
                logger.info(
                    "✅ [多数据源基础信息同步] 总耗时 %.2fs",
                    time.perf_counter() - sync_start,
                )
            except Exception as persist_error:
                logger.error(f"❌ 保存成功状态时出错: {persist_error}")
                # 即使保存失败，也返回结果
            finally:
                # 🔥 清除内存缓存，确保下次查询时从数据库读取最新状态
                self._last_status = None
            
            return stats.__dict__

        except Exception as e:
            stats.status = "failed"
            stats.message = str(e)
            stats.finished_at = datetime.now().isoformat()
            try:
                await self._persist_status(db, stats.__dict__.copy())
            except Exception as persist_error:
                logger.error(f"❌ 保存失败状态时出错: {persist_error}")
            logger.exception(f"Multi-source sync failed: {e}")
            return stats.__dict__
        finally:
            # 🔥 确保无论成功还是失败，都更新运行状态和最后状态
            async with self._lock:
                self._running = False
                # 清除内存缓存，强制下次从数据库读取最新状态
                self._last_status = None



    def _add_financial_metrics(self, doc: Dict, daily_metrics: Dict) -> None:
        """委托到 basics_sync.processing.add_financial_metrics"""
        return _add_financial_metrics_util(doc, daily_metrics)

    def _generate_full_symbol(self, code: str) -> str:
        """
        根据股票代码生成完整标准化代码

        Args:
            code: 6位股票代码

        Returns:
            完整标准化代码，如果无法识别则返回原始代码（确保不为空）
        """
        # 确保 code 不为空
        if not code:
            return ""

        # 标准化为字符串并去除空格
        code = str(code).strip()

        # 如果长度不是 6，返回原始代码
        if len(code) != 6:
            return code

        # 根据代码前缀判断交易所
        if code.startswith(('60', '68', '90')):  # 上海证券交易所
            return f"{code}.SS"
        elif code.startswith(('00', '30', '20')):  # 深圳证券交易所
            return f"{code}.SZ"
        elif code.startswith(('8', '4', '92')):  # 北京证券交易所（92 为 2025-10 起统一号段）
            return f"{code}.BJ"
        else:
            # 无法识别的代码，返回原始代码（确保不为空）
            return code if code else ""


# 全局服务实例
_multi_source_sync_service = None

def get_multi_source_sync_service() -> MultiSourceBasicsSyncService:
    """获取多数据源同步服务实例"""
    global _multi_source_sync_service
    if _multi_source_sync_service is None:
        _multi_source_sync_service = MultiSourceBasicsSyncService()
    return _multi_source_sync_service
