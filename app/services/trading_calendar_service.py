"""
交易日历服务

在系统启动时从 Tushare/AkShare 查询 A 股最近实际交易日，
并将结果缓存到 Redis，供 JIT 数据同步等模块精确判断数据新鲜度。

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

import json
import logging
from datetime import datetime, date, timedelta
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
    def _fmt(raw: str) -> str:
        """统一格式化为 YYYY-MM-DD（兼容 YYYYMMDD 和 YYYY-MM-DD 两种输入）"""
        raw = raw.strip()
        if len(raw) == 8 and "-" not in raw:
            return f"{raw[:4]}-{raw[4:6]}-{raw[6:8]}"
        return raw

    # ------------------------------------------------------------------ #
    # 从外部 API 获取最后交易日                                            #
    # ------------------------------------------------------------------ #

    async def _fetch_from_tushare(self) -> Optional[str]:
        """调用 tushare daily_basic 逐日回溯，找到最近的交易日（YYYY-MM-DD）"""
        try:
            from tradingagents.dataflows.providers.china.tushare import get_tushare_provider
            import asyncio

            provider = get_tushare_provider()
            if not provider.is_available() or provider.api is None:
                return None

            today = datetime.now()
            for delta in range(0, 10):
                d = (today - timedelta(days=delta)).strftime("%Y%m%d")
                try:
                    df = await asyncio.to_thread(
                        provider.api.daily_basic,
                        trade_date=d,
                        fields="ts_code",
                        limit=1,
                    )
                    if df is not None and not df.empty:
                        logger.info(f"📅 [TradingCalendar] Tushare 确认最新交易日: {d}")
                        return self._fmt(d)
                except Exception:
                    continue
        except Exception as e:
            logger.warning(f"⚠️ [TradingCalendar] Tushare 查询失败: {e}")
        return None

    async def _fetch_from_akshare(self) -> Optional[str]:
        """调用 akshare tool_trade_date_hist_sina 获取近期交易日历，取最近 ≤ 今天的交易日"""
        try:
            import akshare as ak
            import asyncio
            import pandas as pd

            df = await asyncio.to_thread(ak.tool_trade_date_hist_sina)
            if df is None or df.empty:
                return None

            # 列名可能是 trade_date 或第0列
            col = df.columns[0]
            dates = pd.to_datetime(df[col]).dt.date
            today_d = date.today()
            valid = sorted([d for d in dates if d <= today_d], reverse=True)
            if valid:
                result = valid[0].strftime("%Y-%m-%d")
                logger.info(f"📅 [TradingCalendar] AkShare 确认最新交易日: {result}")
                return result
        except Exception as e:
            logger.warning(f"⚠️ [TradingCalendar] AkShare 查询失败: {e}")
        return None

    async def _fetch_last_trade_date(self) -> tuple[str, str]:
        """
        按优先级（tushare → akshare → 简单回溯）获取最近交易日。
        Returns: (last_trade_date: YYYY-MM-DD, source: str)
        """
        result = await self._fetch_from_tushare()
        if result:
            return result, "tushare"

        result = await self._fetch_from_akshare()
        if result:
            return result, "akshare"

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
            logger.debug(f"[TradingCalendar] 读取 Redis 缓存失败: {e}")
        return None

    async def _write_cache(self, last_trade_date: str, is_today: bool, source: str):
        try:
            r = await self._redis()
            payload = {
                "last_trade_date": last_trade_date,
                "is_today_trade_day": is_today,
                "fetched_at": self._today_str(),
                "source": source,
            }
            await r.setex(REDIS_KEY, CACHE_TTL_SECONDS, json.dumps(payload, ensure_ascii=False))
            logger.info(f"✅ [TradingCalendar] 已缓存到 Redis: {payload}")
        except Exception as e:
            logger.warning(f"⚠️ [TradingCalendar] 写入 Redis 缓存失败: {e}")

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

