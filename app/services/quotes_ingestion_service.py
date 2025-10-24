import logging
from datetime import datetime, time as dtime, timedelta
from typing import Dict, Optional, Tuple, List
from zoneinfo import ZoneInfo
from collections import deque

from pymongo import UpdateOne

from app.core.config import settings
from app.core.database import get_mongo_db
from app.services.data_sources.manager import DataSourceManager

logger = logging.getLogger(__name__)


class QuotesIngestionService:
    """
    定时从数据源适配层获取全市场近实时行情，入库到 MongoDB 集合 `market_quotes`。

    核心特性：
    - 调度频率：由 settings.QUOTES_INGEST_INTERVAL_SECONDS 控制（默认360秒=6分钟）
    - 接口轮换：Tushare → AKShare东方财富 → AKShare新浪财经（避免单一接口被限流）
    - 智能限流：Tushare免费用户每小时最多2次，付费用户自动切换到高频模式（5秒）
    - 休市时间：跳过任务，保持上次收盘数据；必要时执行一次性兜底补数
    - 字段：code(6位)、close、pct_chg、amount、open、high、low、pre_close、trade_date、updated_at
    """

    def __init__(self, collection_name: str = "market_quotes") -> None:
        self.collection_name = collection_name
        self.tz = ZoneInfo(settings.TIMEZONE)

        # 接口轮换状态
        self._rotation_index = 0  # 当前轮换索引：0=Tushare, 1=AKShare东方财富, 2=AKShare新浪财经
        self._rotation_sources = ["tushare", "akshare_eastmoney", "akshare_sina"]

        # Tushare 调用次数限制（每小时）
        self._tushare_call_times: deque = deque(maxlen=100)  # 记录最近的调用时间
        self._tushare_hourly_limit = settings.QUOTES_TUSHARE_HOURLY_LIMIT

        # Tushare 权限检测
        self._tushare_has_premium = None  # None=未检测, True=付费, False=免费
        self._tushare_permission_checked = False

    async def ensure_indexes(self) -> None:
        db = get_mongo_db()
        coll = db[self.collection_name]
        try:
            await coll.create_index("code", unique=True)
            await coll.create_index("updated_at")
        except Exception as e:
            logger.warning(f"创建行情表索引失败（忽略）: {e}")

    def _check_tushare_permission(self) -> bool:
        """
        检测 Tushare rt_k 接口权限

        Returns:
            True: 有付费权限（可高频调用）
            False: 免费用户（每小时最多2次）
        """
        if self._tushare_permission_checked:
            return self._tushare_has_premium or False

        try:
            from app.services.data_sources.tushare_adapter import TushareAdapter
            adapter = TushareAdapter()

            if not adapter.is_available():
                logger.info("Tushare 不可用，跳过权限检测")
                self._tushare_has_premium = False
                self._tushare_permission_checked = True
                return False

            # 尝试调用 rt_k 接口测试权限
            try:
                df = adapter._provider.api.rt_k(ts_code='000001.SZ')
                if df is not None and not getattr(df, 'empty', True):
                    logger.info("✅ 检测到 Tushare rt_k 接口权限（付费用户）")
                    self._tushare_has_premium = True
                else:
                    logger.info("⚠️ Tushare rt_k 接口返回空数据（可能是免费用户或接口限制）")
                    self._tushare_has_premium = False
            except Exception as e:
                error_msg = str(e).lower()
                if "权限" in error_msg or "permission" in error_msg or "没有访问" in error_msg:
                    logger.info("⚠️ Tushare rt_k 接口无权限（免费用户）")
                    self._tushare_has_premium = False
                else:
                    logger.warning(f"⚠️ Tushare rt_k 接口测试失败: {e}")
                    self._tushare_has_premium = False

            self._tushare_permission_checked = True
            return self._tushare_has_premium or False

        except Exception as e:
            logger.warning(f"Tushare 权限检测失败: {e}")
            self._tushare_has_premium = False
            self._tushare_permission_checked = True
            return False

    def _can_call_tushare(self) -> bool:
        """
        判断是否可以调用 Tushare rt_k 接口

        Returns:
            True: 可以调用
            False: 超过限制，不能调用
        """
        # 如果是付费用户，不限制调用次数
        if self._tushare_has_premium:
            return True

        # 免费用户：检查每小时调用次数
        now = datetime.now(self.tz)
        one_hour_ago = now - timedelta(hours=1)

        # 清理1小时前的记录
        while self._tushare_call_times and self._tushare_call_times[0] < one_hour_ago:
            self._tushare_call_times.popleft()

        # 检查是否超过限制
        if len(self._tushare_call_times) >= self._tushare_hourly_limit:
            logger.warning(
                f"⚠️ Tushare rt_k 接口已达到每小时调用限制 ({self._tushare_hourly_limit}次)，"
                f"跳过本次调用，使用 AKShare 备用接口"
            )
            return False

        return True

    def _record_tushare_call(self) -> None:
        """记录 Tushare 调用时间"""
        self._tushare_call_times.append(datetime.now(self.tz))

    def _get_next_source(self) -> Tuple[str, Optional[str]]:
        """
        获取下一个数据源（轮换机制）

        Returns:
            (source_type, akshare_api):
                - source_type: "tushare" | "akshare"
                - akshare_api: "eastmoney" | "sina" (仅当 source_type="akshare" 时有效)
        """
        if not settings.QUOTES_ROTATION_ENABLED:
            # 未启用轮换，使用默认优先级
            return "tushare", None

        # 轮换逻辑：0=Tushare, 1=AKShare东方财富, 2=AKShare新浪财经
        current_source = self._rotation_sources[self._rotation_index]

        # 更新轮换索引（下次使用下一个接口）
        self._rotation_index = (self._rotation_index + 1) % len(self._rotation_sources)

        if current_source == "tushare":
            return "tushare", None
        elif current_source == "akshare_eastmoney":
            return "akshare", "eastmoney"
        else:  # akshare_sina
            return "akshare", "sina"

    def _is_trading_time(self, now: Optional[datetime] = None) -> bool:
        now = now or datetime.now(self.tz)
        # 工作日 Mon-Fri
        if now.weekday() > 4:
            return False
        t = now.time()
        # 上交所/深交所常规交易时段
        morning = dtime(9, 30)
        noon = dtime(11, 30)
        afternoon_start = dtime(13, 0)
        afternoon_end = dtime(15, 0)
        return (morning <= t <= noon) or (afternoon_start <= t <= afternoon_end)

    async def _collection_empty(self) -> bool:
        db = get_mongo_db()
        coll = db[self.collection_name]
        try:
            count = await coll.estimated_document_count()
            return count == 0
        except Exception:
            return True

    async def _collection_stale(self, latest_trade_date: Optional[str]) -> bool:
        if not latest_trade_date:
            return False
        db = get_mongo_db()
        coll = db[self.collection_name]
        try:
            cursor = coll.find({}, {"trade_date": 1}).sort("trade_date", -1).limit(1)
            docs = await cursor.to_list(length=1)
            if not docs:
                return True
            doc_td = str(docs[0].get("trade_date") or "")
            return doc_td < str(latest_trade_date)
        except Exception:
            return True

    async def _bulk_upsert(self, quotes_map: Dict[str, Dict], trade_date: str, source: Optional[str] = None) -> None:
        db = get_mongo_db()
        coll = db[self.collection_name]
        ops = []
        updated_at = datetime.now(self.tz)
        for code, q in quotes_map.items():
            if not code:
                continue
            code6 = str(code).zfill(6)
            ops.append(
                UpdateOne(
                    {"code": code6},
                    {"$set": {
                        "code": code6,
                        "symbol": code6,  # 添加 symbol 字段，与 code 保持一致
                        "close": q.get("close"),
                        "pct_chg": q.get("pct_chg"),
                        "amount": q.get("amount"),
                        "volume": q.get("volume"),
                        "open": q.get("open"),
                        "high": q.get("high"),
                        "low": q.get("low"),
                        "pre_close": q.get("pre_close"),
                        "trade_date": trade_date,
                        "updated_at": updated_at,
                    }},
                    upsert=True,
                )
            )
        if not ops:
            logger.info("无可写入的数据，跳过")
            return
        result = await coll.bulk_write(ops, ordered=False)
        logger.info(
            f"✅ 行情入库完成 source={source}, matched={result.matched_count}, upserted={len(result.upserted_ids) if result.upserted_ids else 0}, modified={result.modified_count}"
        )

    async def backfill_last_close_snapshot(self) -> None:
        """一次性补齐上一笔收盘快照（用于冷启动或数据陈旧）。允许在休市期调用。"""
        try:
            manager = DataSourceManager()
            # 使用近实时快照作为兜底，休市期返回的即为最后收盘数据
            quotes_map, source = manager.get_realtime_quotes_with_fallback()
            if not quotes_map:
                logger.warning("backfill: 未获取到行情数据，跳过")
                return
            try:
                trade_date = manager.find_latest_trade_date_with_fallback() or datetime.now(self.tz).strftime("%Y%m%d")
            except Exception:
                trade_date = datetime.now(self.tz).strftime("%Y%m%d")
            await self._bulk_upsert(quotes_map, trade_date, source)
        except Exception as e:
            logger.error(f"❌ backfill 行情补数失败: {e}")

    async def backfill_last_close_snapshot_if_needed(self) -> None:
        """若集合为空或 trade_date 落后于最新交易日，则执行一次 backfill"""
        try:
            manager = DataSourceManager()
            latest_td = manager.find_latest_trade_date_with_fallback()
            if await self._collection_empty() or await self._collection_stale(latest_td):
                logger.info("🔁 触发休市期/启动期 backfill 以填充最新收盘数据")
                await self.backfill_last_close_snapshot()
        except Exception as e:
            logger.warning(f"backfill 触发检查失败（忽略）: {e}")

    def _fetch_quotes_from_source(self, source_type: str, akshare_api: Optional[str] = None) -> Tuple[Optional[Dict], Optional[str]]:
        """
        从指定数据源获取行情

        Args:
            source_type: "tushare" | "akshare"
            akshare_api: "eastmoney" | "sina" (仅当 source_type="akshare" 时有效)

        Returns:
            (quotes_map, source_name)
        """
        try:
            if source_type == "tushare":
                # 检查是否可以调用 Tushare
                if not self._can_call_tushare():
                    return None, None

                from app.services.data_sources.tushare_adapter import TushareAdapter
                adapter = TushareAdapter()

                if not adapter.is_available():
                    logger.warning("Tushare 不可用")
                    return None, None

                logger.info("📊 使用 Tushare rt_k 接口获取实时行情")
                quotes_map = adapter.get_realtime_quotes()

                if quotes_map:
                    self._record_tushare_call()
                    return quotes_map, "tushare"
                else:
                    logger.warning("Tushare rt_k 返回空数据")
                    return None, None

            elif source_type == "akshare":
                from app.services.data_sources.akshare_adapter import AKShareAdapter
                adapter = AKShareAdapter()

                if not adapter.is_available():
                    logger.warning("AKShare 不可用")
                    return None, None

                api_name = akshare_api or "eastmoney"
                logger.info(f"📊 使用 AKShare {api_name} 接口获取实时行情")
                quotes_map = adapter.get_realtime_quotes(source=api_name)

                if quotes_map:
                    return quotes_map, f"akshare_{api_name}"
                else:
                    logger.warning(f"AKShare {api_name} 返回空数据")
                    return None, None

            else:
                logger.error(f"未知数据源类型: {source_type}")
                return None, None

        except Exception as e:
            logger.error(f"从 {source_type} 获取行情失败: {e}")
            return None, None

    async def run_once(self) -> None:
        """
        执行一次采集与入库

        核心逻辑：
        1. 检测 Tushare 权限（首次运行）
        2. 按轮换顺序尝试获取行情：Tushare → AKShare东方财富 → AKShare新浪财经
        3. 任意一个接口成功即入库，失败则跳过本次采集
        """
        # 非交易时段处理
        if not self._is_trading_time():
            if settings.QUOTES_BACKFILL_ON_OFFHOURS:
                await self.backfill_last_close_snapshot_if_needed()
            else:
                logger.info("⏭️ 非交易时段，跳过行情采集")
            return

        try:
            # 首次运行：检测 Tushare 权限
            if settings.QUOTES_AUTO_DETECT_TUSHARE_PERMISSION and not self._tushare_permission_checked:
                logger.info("🔍 首次运行，检测 Tushare rt_k 接口权限...")
                has_premium = self._check_tushare_permission()

                if has_premium:
                    logger.info(
                        "✅ 检测到 Tushare 付费权限！建议将 QUOTES_INGEST_INTERVAL_SECONDS 设置为 5-60 秒以充分利用权限"
                    )
                else:
                    logger.info(
                        f"ℹ️ Tushare 免费用户，每小时最多调用 {self._tushare_hourly_limit} 次 rt_k 接口。"
                        f"当前采集间隔: {settings.QUOTES_INGEST_INTERVAL_SECONDS} 秒"
                    )

            # 获取下一个数据源
            source_type, akshare_api = self._get_next_source()

            # 尝试获取行情
            quotes_map, source_name = self._fetch_quotes_from_source(source_type, akshare_api)

            if not quotes_map:
                logger.warning(f"⚠️ {source_name or source_type} 未获取到行情数据，跳过本次入库")
                return

            # 获取交易日
            try:
                manager = DataSourceManager()
                trade_date = manager.find_latest_trade_date_with_fallback() or datetime.now(self.tz).strftime("%Y%m%d")
            except Exception:
                trade_date = datetime.now(self.tz).strftime("%Y%m%d")

            # 入库
            await self._bulk_upsert(quotes_map, trade_date, source_name)

        except Exception as e:
            logger.error(f"❌ 行情入库失败: {e}")

