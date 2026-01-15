"""
与 Tushare 相关的阻塞式工具函数：
- fetch_stock_basic_df：获取股票列表（确保 Tushare 已连接）
- find_latest_trade_date：探测最近可用交易日（YYYYMMDD）
- fetch_daily_basic_mv_map：根据交易日获取日度基础指标映射（市值/估值/交易）
"""
from __future__ import annotations
from datetime import datetime, timedelta
from typing import Dict


def fetch_stock_basic_df():
    """
    从 Tushare 获取股票基础列表（DataFrame格式），要求已正确配置并连接。
    依赖环境变量：TUSHARE_ENABLED=true 且 .env 中提供 TUSHARE_TOKEN。

    注意：这是一个同步函数，会等待 Tushare 连接完成。
    """
    import time
    import logging
    from tradingagents.dataflows.providers.china.tushare import get_tushare_provider
    from app.core.config import settings

    logger = logging.getLogger(__name__)

    # 🔧 移除 TUSHARE_ENABLED 检查，与财务数据、历史数据同步保持一致
    # 只检查 Tushare 连接状态，如果连接失败则报错
    # 注意：如果需要多数据源支持，请使用 MultiSourceBasicsSyncService

    provider = get_tushare_provider()

    # 等待连接完成（最多等待 5 秒）
    max_wait_seconds = 5
    wait_interval = 0.1
    elapsed = 0.0

    logger.info(f"⏳ 等待 Tushare 连接...")
    while not getattr(provider, "connected", False) and elapsed < max_wait_seconds:
        time.sleep(wait_interval)
        elapsed += wait_interval

    # 检查连接状态和API可用性
    if not getattr(provider, "connected", False) or provider.api is None:
        logger.error(f"❌ Tushare 连接失败（等待 {max_wait_seconds}s 后超时）")
        logger.error(f"💡 请检查：")
        logger.error(f"   1. .env 文件中配置了有效的 TUSHARE_TOKEN")
        logger.error(f"   2. Tushare Token 未过期且有足够的积分")
        logger.error(f"   3. 网络连接正常")
        raise RuntimeError(
            f"Tushare not connected after waiting {max_wait_seconds}s. "
            "Check TUSHARE_TOKEN in .env and ensure it's valid."
        )

    logger.info(f"✅ Tushare 已连接，开始获取股票列表...")

    # 直接调用 Tushare API 获取 DataFrame
    try:
        df = provider.api.stock_basic(
            list_status='L',
            fields='ts_code,symbol,name,area,industry,market,exchange,list_date,is_hs'
        )

        # 🔧 增强错误诊断
        if df is None:
            logger.error(f"❌ Tushare API 返回 None")
            logger.error(f"💡 可能原因：")
            logger.error(f"   1. Tushare Token 无效或过期")
            logger.error(f"   2. API 积分不足")
            logger.error(f"   3. 网络连接问题")
            raise RuntimeError("Tushare API returned None. Check token validity and API credits.")

        if hasattr(df, 'empty') and df.empty:
            logger.error(f"❌ Tushare API 返回空 DataFrame")
            logger.error(f"💡 可能原因：")
            logger.error(f"   1. list_status='L' 参数可能不正确")
            logger.error(f"   2. Tushare 数据源暂时不可用")
            logger.error(f"   3. API 调用限制（请检查积分和调用频率）")
            raise RuntimeError("Tushare API returned empty DataFrame. Check API parameters and data availability.")

        logger.info(f"✅ 成功获取 {len(df)} 条股票数据")
        return df

    except Exception as e:
        logger.error(f"❌ 调用 Tushare API 失败: {e}")
        raise RuntimeError(f"Failed to fetch stock basic DataFrame: {e}")


def find_latest_trade_date() -> str:
    """
    探测最近可用的交易日（YYYYMMDD）。
    - 从今天起回溯最多 5 天；
    - 如都不可用，回退为昨天日期。
    """
    from tradingagents.dataflows.providers.china.tushare import get_tushare_provider

    provider = get_tushare_provider()
    api = provider.api
    if api is None:
        raise RuntimeError("Tushare API unavailable")

    today = datetime.now()
    for delta in range(0, 6):
        d = (today - timedelta(days=delta)).strftime("%Y%m%d")
        try:
            db = api.daily_basic(trade_date=d, fields="ts_code,total_mv")
            if db is not None and not db.empty:
                return d
        except Exception:
            continue
    return (today - timedelta(days=1)).strftime("%Y%m%d")


def fetch_daily_basic_mv_map(trade_date: str) -> Dict[str, Dict[str, float]]:
    """
    根据交易日获取日度基础指标映射。
    覆盖字段：total_mv/circ_mv/pe/pb/ps/turnover_rate/volume_ratio/pe_ttm/pb_mrq/ps_ttm
    """
    from tradingagents.dataflows.providers.china.tushare import get_tushare_provider

    provider = get_tushare_provider()
    api = provider.api
    if api is None:
        raise RuntimeError("Tushare API unavailable")

    # 🔥 新增：添加 ps、ps_ttm、total_share、float_share 字段
    fields = "ts_code,total_mv,circ_mv,pe,pb,ps,turnover_rate,volume_ratio,pe_ttm,pb_mrq,ps_ttm,total_share,float_share"
    db = api.daily_basic(trade_date=trade_date, fields=fields)

    data_map: Dict[str, Dict[str, float]] = {}
    if db is not None and not db.empty:
        for _, row in db.iterrows():  # type: ignore
            ts_code = row.get("ts_code")
            if ts_code is not None:
                try:
                    metrics = {}
                    # 🔥 新增：添加 ps、ps_ttm、total_share、float_share 到字段列表
                    for field in [
                        "total_mv",
                        "circ_mv",
                        "pe",
                        "pb",
                        "ps",
                        "turnover_rate",
                        "volume_ratio",
                        "pe_ttm",
                        "pb_mrq",
                        "ps_ttm",
                        "total_share",
                        "float_share",
                    ]:
                        value = row.get(field)
                        if value is not None and str(value).lower() not in ["nan", "none", ""]:
                            metrics[field] = float(value)
                    if metrics:
                        data_map[str(ts_code)] = metrics
                except Exception:
                    pass
    return data_map




def fetch_latest_roe_map() -> Dict[str, Dict[str, float]]:
    """
    获取最近一个可用财报期的 ROE 映射（ts_code -> {"roe": float}）。
    优先按最近季度的 end_date 逆序探测，找到第一期非空数据。
    """
    from tradingagents.dataflows.providers.china.tushare import get_tushare_provider
    from datetime import datetime

    provider = get_tushare_provider()
    api = provider.api
    if api is None:
        raise RuntimeError("Tushare API unavailable")

    # 生成最近若干个财政季度的期末日期，格式 YYYYMMDD
    def quarter_ends(now: datetime):
        y = now.year
        q_dates = [
            f"{y}0331",
            f"{y}0630",
            f"{y}0930",
            f"{y}1231",
        ]
        # 包含上一年，增加成功概率
        py = y - 1
        q_dates_prev = [
            f"{py}1231",
            f"{py}0930",
            f"{py}0630",
            f"{py}0331",
        ]
        # 近6期即可
        return q_dates_prev + q_dates

    candidates = quarter_ends(datetime.now())
    data_map: Dict[str, Dict[str, float]] = {}

    for end_date in candidates:
        try:
            df = api.fina_indicator(end_date=end_date, fields="ts_code,end_date,roe")
            if df is not None and not df.empty:
                for _, row in df.iterrows():  # type: ignore
                    ts_code = row.get("ts_code")
                    val = row.get("roe")
                    if ts_code is None or val is None:
                        continue
                    try:
                        v = float(val)
                    except Exception:
                        continue
                    data_map[str(ts_code)] = {"roe": v}
                if data_map:
                    break  # 找到最近一期即可
        except Exception:
            continue

    return data_map
