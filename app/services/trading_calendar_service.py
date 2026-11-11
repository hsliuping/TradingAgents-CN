"""
交易日历服务

在系统启动时通过数据能力框架（trade_cal 能力，tushare 主源 + akshare 备源）
查询 A 股最近实际交易日，并将结果缓存到 Redis，
供 JIT 数据同步等模块精确判断数据新鲜度。

Redis Key: trading_calendar:last_trade_date
缓存格式:
  {
    "last_trade_date": "2026-02-27",   # YYYY-MM-DD
    "is_today_trade_day": true,
    "fetched_at": "2026-02-27",        # 本次查询当天
    "source": "tushare"
  }

TTL: 25 小时（每天系统启动时刷新，不会无限期存在）
"""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timedelta
from typing import Optional

logger = logging.getLogger(__name__)

REDIS_KEY = "trading_calendar:last_trade_date"
CACHE_TTL_SECONDS = 25 * 3600  # 25 小时，保证每天启动时刷新


class TradingCalendarService:
    """A 股交易日历服务（单例）"""

    # ------------------------------------------------------------------ #
    # 内部工具                                                             #
    # ------------------------------------------------------------------ #

    @staticmethod
    def _today_str() -> str:
        return datetime.now().strftime("%Y-%m-%d")

    @staticmethod
    def _is_loop_mismatch_error(error: Exception) -> bool:
        error_text = str(error).lower()
        return "attached to a different loop" in error_text or "different loop" in error_text

    @staticmethod
    def _build_cache_payload(last_trade_date: str, is_today: bool, source: str) -> dict:
        return {
            "last_trade_date": last_trade_date,
            "is_today_trade_day": is_today,
            "fetched_at": TradingCalendarService._today_str(),
            "source": source,
        }

    # ------------------------------------------------------------------ #
    # 从交易日历能力获取最后交易日                                          #
    # ------------------------------------------------------------------ #

    async def _fetch_via_capability(self) -> Optional[tuple[str, str]]:
        """通过数据能力框架（trade_cal 能力）查询最近交易日

        Returns: (last_trade_date: YYYY-MM-DD, source: str)，失败返回 None
        """
        try:
            import pandas as pd

            from tradingagents.dataflows.capability.facade import get_data_facade

            today = datetime.now()
            start = (today - timedelta(days=15)).strftime("%Y-%m-%d")
            df = await get_data_facade().get_capability("trade_cal").query(start_date=start)
            if df is None or df.empty:
                return None

            open_df = df[df["is_open"] == 1]
            if open_df.empty:
                return None

            result = pd.to_datetime(open_df["cal_date"]).max().strftime("%Y-%m-%d")
            source = str(df["source"].iloc[0]) if "source" in df.columns else "trade_cal"
            logger.info(f"📅 [TradingCalendar] 交易日历能力确认最新交易日: {result} (source={source})")
            return result, source
        except Exception as e:
            logger.warning(f"⚠️ [TradingCalendar] 交易日历能力查询失败: {e}")
            return None

    async def _fetch_last_trade_date(self) -> tuple[str, str]:
        """
        按优先级（交易日历能力 → 简单回溯）获取最近交易日。
        Returns: (last_trade_date: YYYY-MM-DD, source: str)
        """
        capability_result = await self._fetch_via_capability()
        if capability_result:
            return capability_result

        # 最后兜底：从今天往前找第一个周一~周五（不保证节假日准确）
        today = datetime.now()
        for delta in range(0, 5):
            d = today - timedelta(days=delta)
            if d.weekday() < 5:
                fallback = d.strftime("%Y-%m-%d")
                logger.warning(f"⚠️ [TradingCalendar] 所有 API 均失败，回退为最近工作日: {fallback}")
                return fallback, "fallback"

        return today.strftime("%Y-%m-%d"), "fallback"

    # ------------------------------------------------------------------ #
    # Redis 读写                                                          #
    # ------------------------------------------------------------------ #

    async def _redis(self):
        # 优先使用 app.core.database 中由 init_database() 初始化的异步 Redis 客户端，
        # 因为 lifespan 只调用 init_db()→init_database()，而不调用 redis_client.init_redis()
        from app.core.database import get_redis_client
        return get_redis_client()

    async def _read_cache(self) -> Optional[dict]:
        try:
            r = await self._redis()
            raw = await r.get(REDIS_KEY)
            if raw:
                return json.loads(raw)
        except Exception as e:
            if self._is_loop_mismatch_error(e):
                logger.debug("[TradingCalendar] 异步 Redis 客户端跨事件循环，回退到同步 Redis 读取")
                return await asyncio.to_thread(self._read_cache_sync)
            logger.debug(f"[TradingCalendar] 读取 Redis 缓存失败: {e}")
        return None

    @staticmethod
    def _read_cache_sync() -> Optional[dict]:
        try:
            from app.core.database import get_redis_sync_client

            redis_sync = get_redis_sync_client()
            raw = redis_sync.get(REDIS_KEY)
            if raw:
                return json.loads(raw)
        except Exception as e:
            logger.debug(f"[TradingCalendar] 同步 Redis 读取缓存失败: {e}")
        return None

    async def _write_cache(self, last_trade_date: str, is_today: bool, source: str):
        payload = self._build_cache_payload(last_trade_date, is_today, source)
        try:
            r = await self._redis()
            await r.setex(REDIS_KEY, CACHE_TTL_SECONDS, json.dumps(payload, ensure_ascii=False))
            logger.info(f"✅ [TradingCalendar] 已缓存到 Redis: {payload}")
        except Exception as e:
            if self._is_loop_mismatch_error(e):
                try:
                    await asyncio.to_thread(self._write_cache_sync, payload)
                    logger.info(f"✅ [TradingCalendar] 已通过同步 Redis 回退缓存: {payload}")
                    return
                except Exception as sync_error:
                    logger.warning(f"⚠️ [TradingCalendar] 同步 Redis 回退写入失败: {sync_error}")
            logger.warning(f"⚠️ [TradingCalendar] 写入 Redis 缓存失败: {e}")

    @staticmethod
    def _write_cache_sync(payload: dict) -> None:
        from app.core.database import get_redis_sync_client

        redis_sync = get_redis_sync_client()
        redis_sync.setex(REDIS_KEY, CACHE_TTL_SECONDS, json.dumps(payload, ensure_ascii=False))

    # ------------------------------------------------------------------ #
    # 公开接口                                                            #
    # ------------------------------------------------------------------ #

    async def warm_up(self):
        """系统启动时调用，刷新交易日历缓存（总是重新查询 API，忽略旧缓存）"""
        logger.info("🚀 [TradingCalendar] 开始初始化交易日历缓存...")
        try:
            last_trade_date, source = await self._fetch_last_trade_date()
            is_today = last_trade_date == self._today_str()
            await self._write_cache(last_trade_date, is_today, source)
            logger.info(
                f"✅ [TradingCalendar] 初始化完成: 最近交易日={last_trade_date}, "
                f"今天是否交易日={is_today}, 数据源={source}"
            )
        except Exception as e:
            logger.error(f"❌ [TradingCalendar] 初始化失败: {e}", exc_info=True)

    async def get_last_trade_date(self) -> Optional[str]:
        """
        获取最近一个交易日（YYYY-MM-DD）。
        优先读 Redis 缓存；缓存不存在或不是今天写入的则重新查询 API。
        """
        cache = await self._read_cache()
        if cache and cache.get("fetched_at") == self._today_str():
            return cache.get("last_trade_date")

        # 缓存过期，重新获取
        last_trade_date, source = await self._fetch_last_trade_date()
        is_today = last_trade_date == self._today_str()
        await self._write_cache(last_trade_date, is_today, source)
        return last_trade_date

    async def is_today_trade_day(self) -> bool:
        """判断今天是否是交易日"""
        cache = await self._read_cache()
        if cache and cache.get("fetched_at") == self._today_str():
            return bool(cache.get("is_today_trade_day", False))

        last = await self.get_last_trade_date()
        return last == self._today_str()


# ------------------------------------------------------------------ #
# 单例                                                               #
# ------------------------------------------------------------------ #
_instance: Optional[TradingCalendarService] = None


def get_trading_calendar_service() -> TradingCalendarService:
    global _instance
    if _instance is None:
        _instance = TradingCalendarService()
    return _instance

