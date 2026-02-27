"""
统一股票市场数据工具

自动识别股票类型（A股、港股、美股）并调用相应的数据源
"""

import asyncio
import concurrent.futures
import json
import logging
import re
from typing import Annotated, Optional
from langchain_core.tools import tool

from core.tools.base import register_tool

logger = logging.getLogger(__name__)


def _get_last_trade_date_sync() -> Optional[str]:
    """从 Redis 同步读取最近交易日（来自 TradingCalendarService）。

    Returns:
        最近交易日字符串，格式 YYYY-MM-DD；读取失败返回 None。
    """
    try:
        from app.core.database import get_redis_sync_client
        redis_client = get_redis_sync_client()
        raw = redis_client.get("trading_calendar:last_trade_date")
        if raw:
            data = json.loads(raw)
            return data.get("last_trade_date")
    except Exception as e:
        logger.debug(f"[JIT-Tool] 读取 Redis 交易日历失败（非致命）: {e}")
    return None


def _get_db_latest_trade_date_sync(symbol: str, data_source: Optional[str] = None) -> Optional[str]:
    """从 MongoDB stock_daily_quotes 同步查询股票的最新 trade_date。

    Args:
        symbol: 股票代码（6位或带后缀均可）
        data_source: 指定数据源（如 "tushare"）；为 None 时查询所有数据源中最新日期。

    Returns:
        最新日期字符串，格式 YYYY-MM-DD；不存在则返回 None。
    """
    try:
        from app.core.database import get_mongo_db_sync
        db = get_mongo_db_sync()
        code6 = str(symbol).zfill(6)
        query: dict = {"symbol": code6}
        if data_source:
            query["data_source"] = data_source
        doc = db.stock_daily_quotes.find_one(
            query,
            {"trade_date": 1, "_id": 0},
            sort=[("trade_date", -1)]
        )
        if doc:
            raw_date = doc.get("trade_date", "")
            # 统一转为 YYYY-MM-DD
            s = str(raw_date).replace("-", "")
            if len(s) == 8:
                return f"{s[:4]}-{s[4:6]}-{s[6:]}"
            return str(raw_date)
    except Exception as e:
        logger.debug(f"[JIT-Tool] 读取 MongoDB 最新交易日失败（非致命）: {e}")
    return None


def _trigger_jit_sync_in_thread(stock_code: str) -> None:
    """在独立线程中运行 JIT 异步同步，避免嵌套事件循环问题。

    因为 agent 工具运行在已有事件循环的线程中（ThreadWorker 的 async 上下文），
    不能直接 asyncio.run()，需要借助新线程创建独立事件循环。

    新线程中会初始化独立的异步 MongoDB 连接，避免跨线程共享事件循环绑定的客户端。
    """
    async def _do_sync():
        # 🔥 在新事件循环中初始化独立的异步 MongoDB 连接
        from motor.motor_asyncio import AsyncIOMotorClient
        from app.core.config import settings

        mongo_client = None
        try:
            # 创建新的异步 MongoDB 客户端（绑定到当前线程的事件循环）
            mongo_client = AsyncIOMotorClient(
                settings.MONGO_URI,
                maxPoolSize=10,
                minPoolSize=2,
                serverSelectionTimeoutMS=5000
            )
            mongo_db = mongo_client[settings.MONGO_DB_NAME]

            # 临时注入到全局变量，供 jit_sync_stock_data 使用
            import app.core.database as db_module
            original_db = db_module.mongo_db
            db_module.mongo_db = mongo_db

            try:
                from app.worker.analysis_worker import jit_sync_stock_data
                result = await jit_sync_stock_data(
                    stock_code=stock_code,
                    parameters_dict={"market_type": "cn"}
                )
                return result
            finally:
                # 恢复原始全局变量
                db_module.mongo_db = original_db
        finally:
            # 关闭新创建的 MongoDB 连接
            if mongo_client:
                mongo_client.close()

    def _run_in_new_loop():
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            return loop.run_until_complete(_do_sync())
        finally:
            loop.close()

    try:
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(_run_in_new_loop)
            result = future.result(timeout=120)  # 最多等待 2 分钟
            if result and hasattr(result, "is_valid"):
                if result.is_valid:
                    logger.info(f"✅ [JIT-Tool] {stock_code} 数据同步完成: {getattr(result, 'message', '')}")
                else:
                    logger.warning(f"⚠️ [JIT-Tool] {stock_code} 数据同步失败（继续使用现有数据）: {getattr(result, 'message', '')}")
    except concurrent.futures.TimeoutError:
        logger.warning(f"⚠️ [JIT-Tool] {stock_code} JIT 同步超时（120s），继续使用现有数据")
    except Exception as e:
        logger.warning(f"⚠️ [JIT-Tool] {stock_code} JIT 同步异常（继续使用现有数据）: {e}")


def _ensure_fresh_china_data(ticker: str, data_source: Optional[str] = None) -> None:
    """检查 A 股数据新鲜度，如果陈旧则触发 JIT 同步。

    新鲜度以**优先级最高的真实 API 数据源**为准：
    - 若未指定 data_source，则自动从数据库配置中取第一个非 local 数据源。
    - 若指定了 data_source，则直接使用该数据源做检查。

    该函数完全同步，内部通过独立线程处理异步 JIT 同步调用，
    不会阻塞当前事件循环，也不会产生嵌套事件循环冲突。
    """
    # 1. 从 Redis 获取最近交易日（交易日历服务维护）
    last_trade_date = _get_last_trade_date_sync()
    if not last_trade_date:
        logger.debug("[JIT-Tool] 未获取到 Redis 交易日历，跳过新鲜度检查，直接使用现有数据")
        return

    # 2. 确定要检查的数据源：优先使用调用方指定值；否则取优先级最高的真实 API 源
    check_source = data_source
    if not check_source:
        try:
            from app.core.data_source_priority import get_enabled_data_sources_sync
            all_sources = get_enabled_data_sources_sync("a_shares")
            # 排除 local / mongodb 等缓存层，只取真实 API 数据源
            api_sources = [s for s in all_sources if s not in ("local", "mongodb", "local_file")]
            check_source = api_sources[0] if api_sources else None
        except Exception as _e:
            logger.debug(f"[JIT-Tool] 获取数据源优先级失败（非致命）: {_e}")

    # 3. 查 MongoDB 最新数据日期（按指定数据源过滤）
    db_latest = _get_db_latest_trade_date_sync(ticker, data_source=check_source)

    logger.info(
        f"🔍 [JIT-Tool] {ticker} 新鲜度检查 [数据源={check_source or '全部'}]: "
        f"DB最新日={db_latest or '无数据'}, 最近交易日={last_trade_date}"
    )

    # 4. 判断是否需要同步
    if db_latest is None or db_latest < last_trade_date:
        logger.info(
            f"📡 [JIT-Tool] {ticker} 数据陈旧，触发 JIT 同步 "
            f"[{check_source or '全部'}] (DB={db_latest or 'N/A'} < 最近交易日={last_trade_date})"
        )
        _trigger_jit_sync_in_thread(ticker)
    else:
        logger.info(
            f"✅ [JIT-Tool] {ticker} 数据已是最新 [{check_source or '全部'}]"
            f"（{db_latest} >= {last_trade_date}），跳过同步"
        )


@tool
@register_tool(
    tool_id="get_stock_market_data_unified",
    name="统一股票市场数据",
    description="获取股票市场数据和技术指标，支持A股、港股、美股",
    category="market",
    is_online=True,
    auto_register=True
)
def get_stock_market_data_unified(
    ticker: Annotated[str, "股票代码（支持A股、港股、美股）"],
    start_date: Annotated[str, "开始日期，格式：YYYY-MM-DD。注意：系统会自动扩展到配置的回溯天数（通常为365天），你只需要传递分析日期即可"],
    end_date: Annotated[str, "结束日期，格式：YYYY-MM-DD。通常与start_date相同，传递当前分析日期即可"]
) -> str:
    """
    统一的股票市场数据工具
    自动识别股票类型（A股、港股、美股）并调用相应的数据源获取价格和技术指标数据

    ⚠️ 重要：系统会自动扩展日期范围到配置的回溯天数（通常为365天），以确保技术指标计算有足够的历史数据。
    你只需要传递当前分析日期作为 start_date 和 end_date 即可，无需手动计算历史日期范围。

    Args:
        ticker: 股票代码（如：000001、0700.HK、AAPL）
        start_date: 开始日期（格式：YYYY-MM-DD）。传递当前分析日期即可，系统会自动扩展
        end_date: 结束日期（格式：YYYY-MM-DD）。传递当前分析日期即可

    Returns:
        str: 市场数据和技术分析报告

    示例：
        如果分析日期是 2025-11-09，传递：
        - ticker: "00700.HK"
        - start_date: "2025-11-09"
        - end_date: "2025-11-09"
        系统会自动获取 2024-11-09 到 2025-11-09 的365天历史数据
    """
    # 标准化 A股代码：去掉 .SZ/.SH/.BJ 后缀（前后端统一使用纯6位数字）
    original_ticker = ticker
    ticker = re.sub(r'\.(SZ|SH|BJ|sz|sh|bj)$', '', ticker.strip())
    if original_ticker != ticker:
        logger.info(f"📈 [统一市场工具] 标准化股票代码: {original_ticker} -> {ticker}")

    logger.info(f"📈 [统一市场工具] 分析股票: {ticker}")

    try:
        from tradingagents.utils.stock_utils import StockUtils

        # 自动识别股票类型
        market_info = StockUtils.get_market_info(ticker)
        is_china = market_info['is_china']
        is_hk = market_info['is_hk']
        is_us = market_info['is_us']

        logger.info(f"📈 [统一市场工具] 股票类型: {market_info['market_name']}")
        logger.info(f"📈 [统一市场工具] 货币: {market_info['currency_name']} ({market_info['currency_symbol']})")

        result_data = []

        if is_china:
            # 中国A股：使用中国股票数据源
            logger.info(f"🇨🇳 [统一市场工具] 处理A股市场数据...")

            # ===== JIT 新鲜度检查：确保 MongoDB 数据覆盖最近交易日 =====
            # 先检查 DB 数据是否已覆盖 Redis 缓存的最近交易日；
            # 若陈旧，则在独立线程中异步拉取最新行情并写入 MongoDB，
            # 之后 get_china_stock_data_unified 就能读到最新数据。
            try:
                _ensure_fresh_china_data(ticker)
            except Exception as _jit_err:
                logger.warning(f"⚠️ [JIT-Tool] 新鲜度检查出现异常（不影响分析）: {_jit_err}")
            # ============================================================

            try:
                from tradingagents.dataflows.interface import get_china_stock_data_unified
                stock_data = get_china_stock_data_unified(ticker, start_date, end_date)

                # 🔍 调试：打印返回数据的前500字符
                logger.info(f"🔍 [市场工具调试] A股数据返回长度: {len(stock_data)}")
                logger.info(f"🔍 [市场工具调试] A股数据前500字符:\n{stock_data[:500]}")

                result_data.append(f"## A股市场数据\n{stock_data}")
            except Exception as e:
                logger.error(f"❌ [市场工具调试] A股数据获取失败: {e}")
                result_data.append(f"## A股市场数据\n获取失败: {e}")

        elif is_hk:
            # 港股：使用AKShare数据源
            logger.info(f"🇭🇰 [统一市场工具] 处理港股市场数据...")

            try:
                from tradingagents.dataflows.interface import get_hk_stock_data_unified
                hk_data = get_hk_stock_data_unified(ticker, start_date, end_date)

                # 🔍 调试：打印返回数据的前500字符
                logger.info(f"🔍 [市场工具调试] 港股数据返回长度: {len(hk_data)}")
                logger.info(f"🔍 [市场工具调试] 港股数据前500字符:\n{hk_data[:500]}")

                result_data.append(f"## 港股市场数据\n{hk_data}")
            except Exception as e:
                logger.error(f"❌ [市场工具调试] 港股数据获取失败: {e}")
                result_data.append(f"## 港股市场数据\n获取失败: {e}")

        else:
            # 美股：优先使用FINNHUB API数据源
            logger.info(f"🇺🇸 [统一市场工具] 处理美股市场数据...")

            try:
                from tradingagents.dataflows.providers.us.optimized import get_us_stock_data_cached
                us_data = get_us_stock_data_cached(ticker, start_date, end_date)
                result_data.append(f"## 美股市场数据\n{us_data}")
            except Exception as e:
                result_data.append(f"## 美股市场数据\n获取失败: {e}")

        # 组合所有数据
        combined_result = f"""# {ticker} 市场数据分析

**股票类型**: {market_info['market_name']}
**货币**: {market_info['currency_name']} ({market_info['currency_symbol']})
**分析期间**: {start_date} 至 {end_date}

{chr(10).join(result_data)}

---
*数据来源: 根据股票类型自动选择最适合的数据源*
"""

        logger.info(f"📈 [统一市场工具] 数据获取完成，总长度: {len(combined_result)}")
        return combined_result

    except Exception as e:
        error_msg = f"统一市场数据工具执行失败: {str(e)}"
        logger.error(f"❌ [统一市场工具] {error_msg}")
        return error_msg

