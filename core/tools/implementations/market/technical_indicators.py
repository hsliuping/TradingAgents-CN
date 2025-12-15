"""
统一技术指标工具

自动识别股票类型（A股、港股、美股）并调用相应的数据源获取数据，
然后使用 stockstats 计算技术指标。
"""

import logging
import re
import pandas as pd
from typing import Annotated, List, Union
from langchain_core.tools import tool
from datetime import datetime, timedelta

from core.tools.base import register_tool
from tradingagents.utils.stock_utils import StockUtils

logger = logging.getLogger(__name__)

@tool
@register_tool(
    tool_id="get_technical_indicators",
    name="统一技术指标分析",
    description="获取股票的各类技术指标（MACD, RSI, KDJ, BOLL等），支持A股/港股/美股",
    category="market",
    is_online=True,
    auto_register=True
)
def get_technical_indicators(
    ticker: Annotated[str, "股票代码（支持A股、港股、美股）"],
    indicators: Annotated[str, "技术指标列表，用逗号分隔，如 'macd,rsi_14,boll,kdj'"],
    start_date: Annotated[str, "开始日期，格式：YYYY-MM-DD。通常为分析日期的前一年，以确保有足够数据计算指标"] = None,
    end_date: Annotated[str, "结束日期，格式：YYYY-MM-DD。通常为分析日期"] = None
) -> str:
    """
    获取统一的技术指标分析报告
    
    Args:
        ticker: 股票代码
        indicators: 指标列表字符串，如 "macd,rsi,kdj"
        start_date: 开始日期 (默认会自动计算为 end_date 前365天)
        end_date: 结束日期 (默认为今天)
        
    Returns:
        str: 格式化的技术指标报告
    """
    # 1. 初始化日期
    if not end_date:
        end_date = datetime.now().strftime("%Y-%m-%d")
    
    if not start_date:
        # 默认回溯 365 天以确保 MA250 等长周期指标可用
        start_dt = datetime.strptime(end_date, "%Y-%m-%d") - timedelta(days=365)
        start_date = start_dt.strftime("%Y-%m-%d")

    # 2. 标准化股票代码
    original_ticker = ticker
    ticker = re.sub(r'\.(SZ|SH|BJ|sz|sh|bj)$', '', ticker.strip())
    
    logger.info(f"📈 [技术指标] 分析股票: {ticker} ({start_date} -> {end_date})")
    
    try:
        # 3. 识别市场
        market_info = StockUtils.get_market_info(ticker)
        is_china = market_info['is_china']
        is_hk = market_info['is_hk']
        is_us = market_info['is_us']
        
        df = None
        
        # 4. 获取原始数据 (DataFrame)
        if is_china:
            from tradingagents.dataflows.providers.china.tushare import TushareProvider
            from tradingagents.dataflows.providers.china.akshare import AKShareProvider
            import asyncio
            
            # Helper to run async code in sync tool
            def run_async(coro):
                try:
                    return asyncio.run(coro)
                except RuntimeError:
                    # Loop already running, try to use it
                    loop = asyncio.get_event_loop()
                    if loop.is_running():
                        import nest_asyncio
                        nest_asyncio.apply()
                        return asyncio.run(coro)
                    return loop.run_until_complete(coro)

            # 优先尝试 Tushare
            try:
                provider = TushareProvider()
                # TushareProvider needs async call
                df = run_async(provider.get_historical_data(ticker, start_date, end_date))
                
                if df is not None and not df.empty:
                    # Rename columns for stockstats
                    # Tushare: ts_code, trade_date, open, high, low, close, pre_close, change, pct_chg, vol, amount
                    df = df.rename(columns={
                        'trade_date': 'date',
                        'vol': 'volume'
                    })
            except Exception as e:
                logger.warning(f"Tushare 获取数据失败: {e}")
            
            # 降级到 AKShare
            if df is None or df.empty:
                try:
                    provider = AKShareProvider()
                    # AKShareProvider needs async call
                    df = run_async(provider.get_historical_data(ticker, start_date, end_date))
                    # AKShareProvider.get_historical_data already standardizes columns
                except Exception as e:
                    logger.warning(f"AKShare 获取数据失败: {e}")

        elif is_hk:
            from tradingagents.dataflows.providers.hk.improved_hk import ImprovedHKStockProvider
            try:
                provider = ImprovedHKStockProvider()
                df = provider.get_daily_data(ticker, start_date, end_date)
            except Exception as e:
                logger.warning(f"港股数据获取失败: {e}")
                
        elif is_us:
            from tradingagents.dataflows.providers.us.optimized import OptimizedUSProvider
            try:
                provider = OptimizedUSProvider()
                df = provider.get_daily_data(ticker, start_date, end_date)
            except Exception as e:
                logger.warning(f"美股数据获取失败: {e}")

        # 5. 验证数据
        if df is None or df.empty:
            return f"❌ 无法获取股票 {ticker} 的历史数据，无法计算技术指标。"
            
        # 6. 计算指标 (使用 stockstats)
        from stockstats import wrap
        
        # 确保列名符合 stockstats 要求 (open, high, low, close, volume)
        # 我们的 get_daily_data 应该已经标准化了列名，但为了保险再次检查
        df.columns = [c.lower() for c in df.columns]
        
        # stockstats 需要 Date 列作为索引或列? 
        # wrap() 通常接受 DataFrame
        stock = wrap(df)
        
        indicator_list = [i.strip() for i in indicators.split(',')]
        
        # 扩展简写指标
        expanded_list = []
        for ind in indicator_list:
            if ind.lower() == 'kdj':
                expanded_list.extend(['kdjk', 'kdjd', 'kdjj'])
            else:
                expanded_list.append(ind)
        indicator_list = expanded_list
        
        report_lines = [f"## {original_ticker} 技术指标分析", f"日期范围: {start_date} 至 {end_date}", ""]
        
        # 获取最近的数据（最后一行）
        latest_date = df.index[-1] if isinstance(df.index, pd.DatetimeIndex) else df['date'].iloc[-1]
        report_lines.append(f"### 最新数据 ({latest_date})")
        report_lines.append(f"收盘价: {stock['close'].iloc[-1]:.2f}")
        
        for ind in indicator_list:
            try:
                # 计算指标
                series = stock[ind]
                val = series.iloc[-1]
                
                # 格式化输出
                val_str = f"{val:.4f}" if isinstance(val, (int, float)) else str(val)
                
                # 添加简单的趋势判断 (基于最后两天的变化)
                trend = ""
                if len(series) >= 2:
                    prev_val = series.iloc[-2]
                    if isinstance(val, (int, float)) and isinstance(prev_val, (int, float)):
                        if val > prev_val: trend = "↑"
                        elif val < prev_val: trend = "↓"
                        else: trend = "-"
                
                report_lines.append(f"- **{ind}**: {val_str} {trend}")
                
                # 对于某些指标，提供额外信息
                if 'rsi' in ind:
                    status = "中性"
                    if val > 70: status = "超买 ⚠️"
                    elif val < 30: status = "超卖 💎"
                    report_lines.append(f"  - 状态: {status}")
                elif 'macd' in ind and ind == 'macd':
                    # MACD 包含 macd, macds (signal), macdh (hist)
                    macds = stock['macds'].iloc[-1]
                    macdh = stock['macdh'].iloc[-1]
                    report_lines.append(f"  - Signal: {macds:.4f}")
                    report_lines.append(f"  - Hist: {macdh:.4f}")
                    if macdh > 0 and stock['macdh'].iloc[-2] <= 0:
                        report_lines.append(f"  - 信号: 金叉 (看涨) 📈")
                    elif macdh < 0 and stock['macdh'].iloc[-2] >= 0:
                        report_lines.append(f"  - 信号: 死叉 (看跌) 📉")

            except Exception as e:
                report_lines.append(f"- {ind}: 计算失败 ({e})")
        
        return "\n".join(report_lines)

    except Exception as e:
        logger.error(f"技术指标计算失败: {e}", exc_info=True)
        return f"❌ 技术指标计算发生错误: {str(e)}"
