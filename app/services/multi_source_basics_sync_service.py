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

    async def get_status(self) -> Dict[str, Any]:
        """获取同步状态"""
        if self._last_status:
            return self._last_status

        db = get_mongo_db()
        doc = await db[STATUS_COLLECTION].find_one({"job": JOB_KEY})
        if doc:
            # 移除MongoDB的_id字段以避免序列化问题
            doc.pop("_id", None)
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
        执行批量写入，带重试机制

        Args:
            db: MongoDB数据库实例
            operations: 批量操作列表
            max_retries: 最大重试次数

        Returns:
            (新增数量, 更新数量)
        """
        inserted = 0
        updated = 0
        retry_count = 0

        while retry_count < max_retries:
            try:
                result = await db[COLLECTION_NAME].bulk_write(operations, ordered=False)
                inserted = result.upserted_count
                updated = result.modified_count
                logger.debug(f"✅ 批量写入成功: 新增 {inserted}, 更新 {updated}")
                return inserted, updated

            except asyncio.TimeoutError as e:
                retry_count += 1
                if retry_count < max_retries:
                    wait_time = 2 ** retry_count  # 指数退避：2秒、4秒、8秒
                    logger.warning(f"⚠️ 批量写入超时 (第{retry_count}次重试)，等待{wait_time}秒后重试...")
                    await asyncio.sleep(wait_time)
                else:
                    logger.error(f"❌ 批量写入失败，已重试{max_retries}次: {e}")
                    return 0, 0

            except Exception as e:
                logger.error(f"❌ 批量写入失败: {e}")
                return 0, 0

        return inserted, updated

    async def run_full_sync(self, force: bool = False, preferred_sources: List[str] = None) -> Dict[str, Any]:
        """
        运行完整同步

        Args:
            force: 是否强制运行（即使已在运行中）
            preferred_sources: 优先使用的数据源列表
        """
        async with self._lock:
            if self._running and not force:
                logger.info("Multi-source stock basics sync already running; skip start")
                return await self.get_status()
            self._running = True

        db = get_mongo_db()
        stats = SyncStats()
        stats.started_at = datetime.now().isoformat()
        stats.status = "running"
        await self._persist_status(db, stats.__dict__.copy())

        try:
            # Step 1: 获取数据源管理器
            from app.services.data_sources.manager import DataSourceManager
            manager = DataSourceManager()
            available_adapters = manager.get_available_adapters()

            if not available_adapters:
                raise RuntimeError("No available data sources found")

            logger.info(f"Available data sources: {[adapter.name for adapter in available_adapters]}")

            # 如果指定了优先数据源，记录日志
            if preferred_sources:
                logger.info(f"Using preferred data sources: {preferred_sources}")

            # Step 2: 尝试从数据源获取股票列表（排除本地数据源）
            stock_df, source_used = await asyncio.to_thread(
                manager.get_stock_list_with_fallback, preferred_sources, True  # exclude_local=True
            )
            if stock_df is None or getattr(stock_df, "empty", True):
                raise RuntimeError("All data sources failed to provide stock list")

            stats.data_sources_used.append(f"stock_list:{source_used}")
            logger.info(f"Successfully fetched {len(stock_df)} stocks from {source_used}")

            # Step 3: 获取最新交易日期和财务数据
            latest_trade_date = await asyncio.to_thread(
                manager.find_latest_trade_date_with_fallback, preferred_sources
            )
            stats.last_trade_date = latest_trade_date

            daily_data_map = {}
            daily_source = ""
            if latest_trade_date:
                daily_df, daily_source = await asyncio.to_thread(
                    manager.get_daily_basic_with_fallback, latest_trade_date, preferred_sources
                )
                if daily_df is not None and not daily_df.empty:
                    for _, row in daily_df.iterrows():
                        ts_code = row.get("ts_code")
                        if ts_code:
                            daily_data_map[ts_code] = row.to_dict()
                    stats.data_sources_used.append(f"daily_data:{daily_source}")

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
                        "industry": industry,
                        "market": market,
                        "list_date": list_date,
                        "sse": sse,
                        "full_symbol": full_symbol,  # 添加 full_symbol 字段
                        "category": category,
                        "source": data_source,  # 🔥 使用实际数据源
                        "updated_at": datetime.now(),
                    }

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

            await self._persist_status(db, stats.__dict__.copy())
            logger.info(
                f"✅ Multi-source sync finished: total={stats.total} inserted={inserted} "
                f"updated={updated} errors={errors} sources={stats.data_sources_used}"
            )
            return stats.__dict__

        except Exception as e:
            stats.status = "failed"
            stats.message = str(e)
            stats.finished_at = datetime.now().isoformat()
            await self._persist_status(db, stats.__dict__.copy())
            logger.exception(f"Multi-source sync failed: {e}")
            return stats.__dict__
        finally:
            async with self._lock:
                self._running = False



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
        elif code.startswith(('8', '4')):  # 北京证券交易所
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
