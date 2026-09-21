"""
筹码分布工具函数

提供筹码分布数据获取，支持 AkShare（优先）和 Tushare（备用）两个数据源。

数据源优先级：
  AkShare（免费，东财爬虫） → Tushare（官方API，需要5000积分）
"""

import logging
import random
import time
from typing import Optional, Dict, Any
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

# === Mock 开关：设为 True 时不调用真实 API，返回随机模拟数据 ===
_MOCK_CHIP_DATA = False


def _normalize_ticker(ticker: str) -> str:
    """标准化股票代码（去除交易所后缀）"""
    if "." in ticker:
        return ticker.split(".")[0]
    return ticker


def _normalize_ts_code(ticker: str) -> str:
    """转换为 Tushare ts_code 格式（如 000001.SZ）"""
    if "." in ticker:
        return ticker.upper()
    code = ticker.strip()
    if code.startswith(("6", "9")):
        return f"{code}.SH"
    return f"{code}.SZ"


def get_chip_distribution_akshare(ticker: str, trade_date: str) -> Optional[Dict[str, Any]]:
    """
    通过 AkShare 获取筹码分布数据
    
    使用 stock_cyq_em 接口获取东方财富筹码分布数据。
    
    Args:
        ticker: 股票代码（如 000001）
        trade_date: 交易日期（格式：YYYY-MM-DD）
    
    Returns:
        筹码分布数据字典，或 None（失败时）
    """
    try:
        import akshare as ak

        symbol = _normalize_ticker(ticker)
        t0 = time.time()
        logger.info(f"[AkShare筹码] 开始调用 stock_cyq_em: symbol={symbol}, adjust=''")
        # akshare stock_cyq_em 返回历史筹码分布
        df = ak.stock_cyq_em(symbol=symbol, adjust="")
        elapsed = time.time() - t0
        logger.info(f"[AkShare筹码] stock_cyq_em 调用完成: 耗时={elapsed:.2f}s, 行数={len(df) if df is not None else 0}")

        if df is None or df.empty:
            logger.warning(f"[AkShare筹码] {symbol} 返回空数据 (耗时={elapsed:.2f}s)")
            return None

        # 将日期列规范化
        date_col = "日期" if "日期" in df.columns else df.columns[0]
        df[date_col] = df[date_col].astype(str)

        # 尝试找最接近目标日期的数据
        target = trade_date.replace("-", "")
        # 优先精确匹配
        row = df[df[date_col].str.replace("-", "") == target]
        if row.empty:
            # 取最近一条数据
            row = df.tail(1)

        if row.empty:
            return None

        r = row.iloc[0]
        # 列名映射（东财接口）
        col_map = {
            "获利比例": "profit_ratio",
            "平均成本": "avg_cost",
            "90成本-低": "cost_90_low",
            "90成本-高": "cost_90_high",
            "90集中度": "concentration_90",
            "70成本-低": "cost_70_low",
            "70成本-高": "cost_70_high",
            "70集中度": "concentration_70",
        }

        result: Dict[str, Any] = {
            "code": symbol,
            "date": str(r.get(date_col, trade_date)),
            "source": "akshare",
            "profit_ratio": 0.0,
            "avg_cost": 0.0,
            "cost_90_low": 0.0,
            "cost_90_high": 0.0,
            "concentration_90": 0.0,
            "cost_70_low": 0.0,
            "cost_70_high": 0.0,
            "concentration_70": 0.0,
        }

        for ch_col, en_key in col_map.items():
            if ch_col in r.index:
                try:
                    val = float(r[ch_col])
                    result[en_key] = val
                except (ValueError, TypeError):
                    pass

        # 集中度是常见的静默失效点（接口列名变动时会全部退化为 0），显式留痕
        if not result["concentration_90"] and not result["concentration_70"]:
            logger.warning(f"[AkShare筹码] {symbol} 未取到集中度，接口实际列名: {list(df.columns)}")

        logger.info(f"[AkShare筹码] {symbol} 获取成功，来源日期: {result['date']}")
        return result

    except ImportError:
        logger.warning("[AkShare筹码] akshare 未安装")
        return None
    except Exception as e:
        logger.warning(f"[AkShare筹码] {ticker} 获取失败: {e}")
        return None


def get_chip_distribution_tushare(ticker: str, trade_date: str) -> Optional[Dict[str, Any]]:
    """
    通过 Tushare 获取筹码分布数据（cyq_perf 接口，需要5000积分）

    Args:
        ticker: 股票代码（如 000001）
        trade_date: 交易日期（格式：YYYY-MM-DD）

    Returns:
        筹码分布数据字典，或 None（失败时）
    """
    try:
        t0 = time.time()
        from tradingagents.dataflows.providers.china.tushare import get_tushare_provider

        provider = get_tushare_provider()
        if not provider or not provider.is_available():
            logger.debug("[Tushare筹码] Tushare 未初始化或不可用")
            return None

        ts_code = _normalize_ts_code(ticker)
        trade_date_fmt = trade_date.replace("-", "")

        import asyncio
        loop = None
        try:
            loop = asyncio.get_event_loop()
            if loop.is_closed():
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        logger.info(f"[Tushare筹码] 开始调用 cyq_perf: ts_code={ts_code}, trade_date={trade_date_fmt}")
        # Tushare cyq_perf API: 筹码分析
        df = provider.api.cyq_perf(
            ts_code=ts_code,
            trade_date=trade_date_fmt,
            fields="ts_code,trade_date,his_low,his_high,cost_5pct,cost_15pct,cost_50pct,"
                   "cost_85pct,cost_95pct,weight_avg,winner_rate"
        )

        if df is None or df.empty:
            # 尝试获取最近几天的数据
            start = (datetime.strptime(trade_date, "%Y-%m-%d") - timedelta(days=10)).strftime("%Y%m%d")
            logger.info(f"[Tushare筹码] 精确日期无数据，回退查询范围: {start}~{trade_date_fmt}")
            df = provider.api.cyq_perf(
                ts_code=ts_code,
                start_date=start,
                end_date=trade_date_fmt,
                fields="ts_code,trade_date,his_low,his_high,cost_5pct,cost_15pct,cost_50pct,"
                       "cost_85pct,cost_95pct,weight_avg,winner_rate"
            )
            if df is None or df.empty:
                logger.warning(f"[Tushare筹码] {ts_code} 返回空数据")
                return None
            df = df.sort_values("trade_date", ascending=False)

        r = df.iloc[0]
        symbol = _normalize_ticker(ticker)
        result: Dict[str, Any] = {
            "code": symbol,
            "date": str(r.get("trade_date", trade_date_fmt)),
            "source": "tushare",
            "profit_ratio": float(r.get("winner_rate", 0)) / 100.0 if r.get("winner_rate") else 0.0,
            "avg_cost": float(r.get("weight_avg", 0)) if r.get("weight_avg") else 0.0,
            "cost_90_low": float(r.get("cost_5pct", 0)) if r.get("cost_5pct") else 0.0,
            "cost_90_high": float(r.get("cost_95pct", 0)) if r.get("cost_95pct") else 0.0,
            "concentration_90": 0.0,
            "cost_70_low": float(r.get("cost_15pct", 0)) if r.get("cost_15pct") else 0.0,
            "cost_70_high": float(r.get("cost_85pct", 0)) if r.get("cost_85pct") else 0.0,
            "concentration_70": 0.0,
        }
        # 计算集中度：标准口径 (高-低)/(高+低)，与东财/通达信/同花顺一致，数值越小越集中
        if result["cost_90_high"] + result["cost_90_low"] > 0:
            rng90 = result["cost_90_high"] - result["cost_90_low"]
            result["concentration_90"] = round(rng90 / (result["cost_90_high"] + result["cost_90_low"]), 4)
        if result["cost_70_high"] + result["cost_70_low"] > 0:
            rng70 = result["cost_70_high"] - result["cost_70_low"]
            result["concentration_70"] = round(rng70 / (result["cost_70_high"] + result["cost_70_low"]), 4)

        logger.info(f"[Tushare筹码] {ts_code} 获取成功 (耗时={time.time() - t0:.2f}s)")
        return result

    except Exception as e:
        logger.warning(f"[Tushare筹码] {ticker} 获取失败: {e}")
        return None


def _mock_chip_report(symbol: str, trade_date: str) -> str:
    """生成随机模拟筹码分布报告（用于隔离测试）"""
    avg_cost = round(random.uniform(8.0, 15.0), 2)
    current_price = round(avg_cost * random.uniform(0.85, 1.15), 2)
    profit_ratio = round(random.uniform(25, 60), 1)
    cost_90_low = round(avg_cost * random.uniform(0.75, 0.88), 2)
    cost_90_high = round(avg_cost * random.uniform(1.12, 1.35), 2)
    conc_90 = round((cost_90_high - cost_90_low) / avg_cost, 4)
    cost_70_low = round(avg_cost * random.uniform(0.85, 0.93), 2)
    cost_70_high = round(avg_cost * random.uniform(1.05, 1.15), 2)
    conc_70 = round((cost_70_high - cost_70_low) / avg_cost, 4)

    logger.info(f"[筹码分布-MOCK] {symbol} 返回模拟数据 (avg_cost={avg_cost}, profit_ratio={profit_ratio}%)")

    return f"""## 📊 筹码分布分析 - {symbol} ({trade_date})

**数据来源**: mock（模拟数据，用于功能验证）

### 核心指标
- **获利比例**: {profit_ratio}%（当前价格下持有浮盈的筹码占比）
- **平均成本**: {avg_cost} 元

### 筹码集中度
| 区间 | 成本下限 | 成本上限 | 集中度 |
|------|---------|---------|------|
| 90%筹码 | {cost_90_low} 元 | {cost_90_high} 元 | {conc_90} |
| 70%筹码 | {cost_70_low} 元 | {cost_70_high} 元 | {conc_70} |

### 分析要点
- 当前价格: {current_price} 元 (vs 平均成本 {avg_cost} 元)
- 90%筹码区间: [{cost_90_low}, {cost_90_high}]，集中度 {conc_90}（{'较为集中' if conc_90 < 0.3 else '较为分散'}）
- 70%筹码区间: [{cost_70_low}, {cost_70_high}]，集中度 {conc_70}

> ⚠️ 此数据为模拟生成，仅用于排除 API 调用问题。如需真实数据请关闭 mock 模式。
"""


def get_chip_distribution_unified(ticker: str, trade_date: str) -> str:
    """
    统一筹码分布接口（AkShare 优先，Tushare 备用）

    Args:
        ticker: 股票代码（如 000001 或 000001.SZ）
        trade_date: 交易日期（格式：YYYY-MM-DD）

    Returns:
        str: 筹码分布分析报告文本
    """
    symbol = _normalize_ticker(ticker)
    t0 = time.time()

    # Mock 模式：直接返回随机模拟数据，不调用真实 API
    if _MOCK_CHIP_DATA:
        return _mock_chip_report(symbol, trade_date)

    # 优先 AkShare
    logger.info(f"[筹码分布] 开始获取 {symbol} 筹码数据，优先使用 AkShare")
    data = get_chip_distribution_akshare(symbol, trade_date)
    if data is None:
        elapsed_ak = time.time() - t0
        logger.info(f"[筹码分布] AkShare失败 (耗时={elapsed_ak:.2f}s)，切换到Tushare: {symbol}")
        data = get_chip_distribution_tushare(symbol, trade_date)

    total_elapsed = time.time() - t0
    if data is None:
        logger.warning(f"[筹码分布] {symbol} 所有数据源均失败 (总耗时={total_elapsed:.2f}s)")
        return (
            f"❌ 无法获取 {ticker} 的筹码分布数据（{trade_date}）。\n"
            "可能原因：数据源不可用、该日期非交易日或股票代码不正确。"
        )

    logger.info(f"[筹码分布] {symbol} 获取成功 (总耗时={total_elapsed:.2f}s, 来源={data['source']})")

    # 格式化输出
    profit_pct = data["profit_ratio"] * 100 if data["profit_ratio"] <= 1 else data["profit_ratio"]
    report = f"""## 📊 筹码分布分析 - {symbol} ({data['date']})

**数据来源**: {data['source']}

### 核心指标
- **获利比例**: {profit_pct:.1f}%（当前价格下持有浮盈的筹码占比）
- **平均成本**: {data['avg_cost']:.2f} 元

### 筹码集中度
| 区间 | 成本下限 | 成本上限 | 集中度 |
|------|---------|---------|------|
| 90%筹码 | {data['cost_90_low']:.2f} 元 | {data['cost_90_high']:.2f} 元 | {data['concentration_90']:.4f} |
| 70%筹码 | {data['cost_70_low']:.2f} 元 | {data['cost_70_high']:.2f} 元 | {data['concentration_70']:.4f} |

### 筹码分析说明
- 获利比例越高，说明持仓者整体盈利，抛压可能较大
- 获利比例越低，说明大多数持仓者亏损，下方支撑较强
- 筹码集中度越低（数值越小），说明筹码越集中，趋势可能越稳定
- 90%筹码范围表示全市场90%的持仓者的成本区间
"""
    return report


def get_chip_distribution_sync(ticker: str, trade_date: str) -> str:
    """同步包装（别名，供工具层调用）"""
    return get_chip_distribution_unified(ticker, trade_date)

