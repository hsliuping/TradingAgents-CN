"""
QMT (迅投 MiniQMT) 数据同步服务

将 QMT 数据同步到 MongoDB，需 MiniQMT 客户端已启动并登录。
前置条件：xtquant 可用，MiniQMT 运行（仅 Windows）。
新闻不支持，统一使用 AKShare。
"""
import asyncio
import logging
from datetime import datetime
from typing import Dict, Any, List, Optional

from app.core.database import get_mongo_db
from app.services.data_sources.qmt_adapter import QMTAdapter

logger = logging.getLogger(__name__)

_qmt_sync_service = None


class QMTSyncService:
    """
    QMT 数据同步服务

    提供：
    - 股票基础信息同步
    - 实时行情同步（可选）
    """

    def __init__(self):
        self.adapter = QMTAdapter()
        self.db = None
        self.batch_size = 200
        self._current_job_id = None

    async def initialize(self):
        """初始化同步服务"""
        try:
            self.db = get_mongo_db()
            if not self.adapter.is_available():
                raise RuntimeError("❌ QMT 不可用，请确保 MiniQMT 已启动并登录")
            logger.info("✅ QMT 同步服务初始化完成")
        except Exception as e:
            logger.error(f"❌ QMT 同步服务初始化失败: {e}")
            raise

    async def sync_stock_basic_info(
        self,
        force_update: bool = False,
        job_id: str = None,
        symbols: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """
        同步股票基础信息到 MongoDB

        Args:
            force_update: 是否强制更新
            job_id: 任务 ID（用于进度跟踪）
            symbols: 可选，仅同步指定股票列表；为空则同步全市场

        Returns:
            同步结果统计
        """
        self._current_job_id = job_id or "qmt_basic_info_sync"
        logger.info("🔄 开始 QMT 股票基础信息同步...")

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
            df = self.adapter.get_stock_list()
            if df is None or df.empty:
                logger.warning("⚠️ QMT 未获取到股票列表")
                return stats

            if symbols:
                symbol_set = {str(s).zfill(6) for s in symbols}
                df = df[df["symbol"].astype(str).str.zfill(6).isin(symbol_set)]
                if df.empty:
                    logger.warning(f"⚠️ QMT 未找到指定股票: {symbols}")
                    return stats

            stats["total_processed"] = len(df)

            for i in range(0, len(df), self.batch_size):
                batch = df.iloc[i : i + self.batch_size]
                for _, row in batch.iterrows():
                    try:
                        code = str(row.get("symbol", "")).zfill(6)
                        if not code or len(code) != 6:
                            continue

                        if not force_update:
                            existing = await self.db.stock_basic_info.find_one({"code": code, "source": "qmt"})
                            if existing:
                                stats["skipped_count"] += 1
                                continue

                        doc = {
                            "code": code,
                            "symbol": code,
                            "name": row.get("name") or code,
                            "ts_code": row.get("ts_code", ""),
                            "source": "qmt",
                            "market": row.get("market", ""),
                            "area": row.get("area", ""),
                            "industry": row.get("industry", ""),
                            "list_date": row.get("list_date", ""),
                            "updated_at": datetime.utcnow(),
                        }

                        await self.db.stock_basic_info.update_one(
                            {"code": code, "source": "qmt"},
                            {"$set": doc},
                            upsert=True,
                        )
                        stats["success_count"] += 1
                    except Exception as e:
                        stats["error_count"] += 1
                        stats["errors"].append({"code": code, "error": str(e)})

                if i + self.batch_size < len(df):
                    await asyncio.sleep(0.1)

            stats["end_time"] = datetime.utcnow()
            stats["duration"] = (stats["end_time"] - stats["start_time"]).total_seconds()

            logger.info(f"✅ QMT 股票基础信息同步完成: 成功 {stats['success_count']}, 跳过 {stats['skipped_count']}, 错误 {stats['error_count']}")

            return stats
        except Exception as e:
            logger.error(f"❌ QMT 股票基础信息同步失败: {e}")
            stats["errors"].append({"error": str(e), "context": "sync_stock_basic_info"})
            return stats

    async def sync_realtime_quotes(self, symbols: Optional[List[str]] = None, force: bool = False) -> Dict[str, Any]:
        """
        同步实时行情到 market_quotes（可选，需 MiniQMT 运行）

        Args:
            symbols: 指定股票列表，空则全市场
            force: 是否强制执行

        Returns:
            同步结果
        """
        if not self.adapter.is_available():
            logger.warning("⚠️ QMT 不可用，跳过实时行情同步")
            return {"success_count": 0, "message": "QMT 不可用"}

        try:
            quotes = self.adapter.get_realtime_quotes()
            if not quotes:
                return {"success_count": 0, "message": "未获取到行情"}

            if symbols:
                quotes = {k: v for k, v in quotes.items() if k in symbols}

            if not quotes:
                return {"success_count": 0, "message": "无匹配数据"}

            count = 0
            now = datetime.utcnow()
            for code, q in quotes.items():
                try:
                    doc = {
                        "code": code,
                        "symbol": code,
                        "close": q.get("close"),
                        "pct_chg": q.get("pct_chg"),
                        "amount": q.get("amount"),
                        "source": "qmt",
                        "updated_at": now,
                    }
                    await self.db.market_quotes.update_one(
                        {"code": code},
                        {"$set": doc},
                        upsert=True,
                    )
                    count += 1
                except Exception as e:
                    logger.debug(f"QMT 行情更新失败 {code}: {e}")

            return {"success_count": count, "total": len(quotes), "message": f"同步 {count} 只"}
        except Exception as e:
            logger.error(f"QMT 实时行情同步失败: {e}")
            return {"success_count": 0, "error": str(e)}


async def get_qmt_sync_service() -> QMTSyncService:
    """获取 QMT 同步服务单例"""
    global _qmt_sync_service
    if _qmt_sync_service is None:
        _qmt_sync_service = QMTSyncService()
        await _qmt_sync_service.initialize()
    return _qmt_sync_service


async def run_qmt_basic_info_sync(force_update: bool = False, job_id: str = None) -> Dict[str, Any]:
    """运行 QMT 股票基础信息同步"""
    service = await get_qmt_sync_service()
    return await service.sync_stock_basic_info(force_update=force_update, job_id=job_id)
