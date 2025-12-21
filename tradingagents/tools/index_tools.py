#!/usr/bin/env python3
"""
指数分析工具集
封装指数分析所需的LangChain工具
"""

from langchain_core.tools import tool
from typing import Annotated
from datetime import datetime, timedelta

from tradingagents.utils.logging_manager import get_logger

logger = get_logger('agents')


@tool
def fetch_macro_data(query_date: Annotated[str, "查询日期，格式 YYYY-MM-DD，留空则使用当前日期"] = None) -> str:
    """
    获取宏观经济指标数据
    
    返回最新的宏观经济指标，包括:
    - GDP (国内生产总值)
    - CPI (消费者物价指数)
    - PMI (采购经理人指数)
    - M2 (货币供应量)
    - LPR (贷款市场报价利率)
    
    Args:
        query_date: 查询日期，格式 YYYY-MM-DD
        
    Returns:
        str: Markdown格式的宏观经济数据
    """
    logger.info(f"🌍 [宏观数据工具] 开始获取宏观经济数据, date={query_date}")
    
    try:
        # Use local helper
        provider = get_index_data_provider()
        macro_data = provider.get_macro_economics_data(end_date=query_date)
        
        # Handle list response if provider returns a list (some providers might)
        if isinstance(macro_data, list):
            macro_data = macro_data[0] if macro_data else {}
        
        # 格式化为Markdown
        report = _format_macro_data_to_markdown(macro_data)
        
        logger.info(f"✅ [宏观数据工具] 宏观数据获取成功")
        return report
        
    except Exception as e:
        logger.error(f"❌ [宏观数据工具] 宏观数据获取失败: {e}")
        return f"⚠️ 宏观数据获取失败: {str(e)}\n\n请稍后重试或使用其他数据源。"


@tool
def fetch_policy_news(lookback_days: Annotated[int, "回溯天数，默认7天"] = 7) -> str:
    """
    获取政策新闻
    
    获取最近N天的重要政策新闻，包括:
    - 新闻联播文字稿
    - 财经政策新闻
    - 监管政策动态
    
    Args:
        lookback_days: 回溯天数，默认7天
        
    Returns:
        str: Markdown格式的政策新闻
    """
    logger.info(f"📰 [政策新闻工具] 开始获取政策新闻, lookback_days={lookback_days}")
    
    try:
        # Use local helper
        provider = get_index_data_provider()
        news_list = provider.get_policy_news(lookback_days=lookback_days)
        
        # 格式化为Markdown
        report = _format_news_to_markdown(news_list, "政策新闻汇总")
        
        logger.info(f"✅ [政策新闻工具] 政策新闻获取成功，共{len(news_list)}条")
        return report
        
    except Exception as e:
        logger.error(f"❌ [政策新闻工具] 政策新闻获取失败: {e}")
        return f"⚠️ 政策新闻获取失败: {str(e)}\n\n请稍后重试或使用其他数据源。"


@tool
def fetch_sector_news(
    sector_name: Annotated[str, "板块或概念名称，如'半导体', '医药'"], 
    lookback_days: Annotated[int, "回溯天数，默认7天"] = 7
) -> str:
    """
    获取特定板块/概念新闻
    
    Args:
        sector_name: 板块或概念名称
        lookback_days: 回溯天数，默认7天
        
    Returns:
        str: Markdown格式的新闻
    """
    logger.info(f"🏭 [板块新闻工具] 开始获取板块新闻, sector={sector_name}")
    
    try:
        from tradingagents.dataflows.index_data import get_index_data_provider
        
        provider = get_index_data_provider()
        news_list = provider.get_sector_news(sector_name, lookback_days)
        
        # 格式化为Markdown
        report = _format_news_to_markdown(news_list, f"{sector_name}板块新闻")
        
        logger.info(f"✅ [板块新闻工具] {sector_name}新闻获取成功，共{len(news_list)}条")
        return report
        
    except Exception as e:
        logger.error(f"❌ [板块新闻工具] 新闻获取失败: {e}")
        return f"⚠️ {sector_name}板块新闻获取失败: {str(e)}"


@tool
def fetch_sector_rotation(trade_date: Annotated[str, "交易日期，格式 YYYY-MM-DD，留空则使用最新交易日"] = None) -> str:

    """
    获取板块轮动数据
    
    获取最新的板块资金流向和涨跌幅数据，包括:
    - 领涨板块 (Top 5)
    - 领跌板块 (Bottom 5)
    - 板块资金流入/流出
    - 板块换手率
    
    Args:
        trade_date: 交易日期，格式 YYYY-MM-DD
        
    Returns:
        str: Markdown格式的板块轮动数据
    """
    logger.info(f"💰 [板块轮动工具] 开始获取板块数据, trade_date={trade_date}")
    
    try:
        # Use local helper
        provider = get_index_data_provider()
        sector_data = provider.get_sector_flows(trade_date=trade_date)
        
        # 格式化为Markdown
        report = _format_sector_data_to_markdown(sector_data, trade_date)
        
        logger.info(f"✅ [板块轮动工具] 板块数据获取成功")
        return report
        
    except Exception as e:
        logger.error(f"❌ [板块轮动工具] 板块数据获取失败: {e}")
        return f"⚠️ 板块数据获取失败: {str(e)}\n\n请稍后重试或使用其他数据源。"


@tool
def fetch_index_valuation(index_code: Annotated[str, "指数代码，如 '000001.SH'"]) -> str:
    """
    获取指数估值数据
    
    返回指数的PE、PB、股息率及其历史百分位，用于评估指数是否低估。
    
    Args:
        index_code: 指数代码
        
    Returns:
        str: Markdown格式的估值报告
    """
    logger.info(f"📊 [估值工具] 开始获取估值数据, index={index_code}")
    
    try:
        provider = get_index_data_provider()
        val_data = provider.get_index_valuation(index_code)
        
        report = f"""# {index_code} 估值分析

## 📊 核心估值指标
- **PE (市盈率)**: {val_data.get('pe', 'N/A')} (分位: {val_data.get('pe_percentile', 'N/A')}%)
- **PB (市净率)**: {val_data.get('pb', 'N/A')} (分位: {val_data.get('pb_percentile', 'N/A')}%)
- **股息率**: {val_data.get('dividend_yield', 'N/A')}%
- **估值评价**: {val_data.get('evaluation', '未知')}

📅 **数据获取时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
"""
        logger.info(f"✅ [估值工具] 估值数据获取成功")
        return report
        
    except Exception as e:
        logger.error(f"❌ [估值工具] 估值数据获取失败: {e}")
        return f"⚠️ 估值数据获取失败: {str(e)}"


@tool
def fetch_index_constituents(index_code: Annotated[str, "指数代码，如 '000001.SH'"]) -> str:
    """
    获取指数前十大权重股
    
    Args:
        index_code: 指数代码
        
    Returns:
        str: Markdown格式的权重股列表
    """
    logger.info(f"🏗️ [权重股工具] 开始获取权重股, index={index_code}")
    
    try:
        provider = get_index_data_provider()
        constituents = provider.get_index_constituents(index_code)
        
        report = f"# {index_code} 前十大权重股\n\n"
        for i, stock in enumerate(constituents[:10], 1):
            report += f"{i}. **{stock.get('name', stock.get('symbol'))}** ({stock.get('symbol')}) - 权重: {stock.get('weight', 'N/A')}%\n"
            
        logger.info(f"✅ [权重股工具] 权重股获取成功")
        return report
        
    except Exception as e:
        logger.error(f"❌ [权重股工具] 权重股获取失败: {e}")
        return f"⚠️ 权重股获取失败: {str(e)}"


@tool
def fetch_market_funds_flow() -> str:
    """
    获取全市场资金流向
    
    返回北向资金、主力资金等整体流动性指标。
    
    Returns:
        str: Markdown格式的资金流向报告
    """
    logger.info(f"💸 [资金流向工具] 开始获取全市场资金流向")
    
    try:
        provider = get_index_data_provider()
        flow_data = provider.get_market_funds_flow()
        
        report = f"""# 全市场资金流向

## 🌏 北向资金
- **当日净流入**: {flow_data.get('north_money_inflow', 0):.2f} 亿元
- **累计净流入**: {flow_data.get('north_money_total', 0):.2f} 亿元

## 🏦 主力资金
- **全市场主力净流入**: {flow_data.get('main_force_inflow', 0):.2f} 亿元

📅 **数据获取时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
"""
        logger.info(f"✅ [资金流向工具] 资金流向获取成功")
        return report
        
    except Exception as e:
        logger.error(f"❌ [资金流向工具] 资金流向获取失败: {e}")
        return f"⚠️ 资金流向获取失败: {str(e)}"


# ==================== Helper Functions ====================

def get_index_data_provider():
    """Lazy load IndexDataProvider to avoid circular imports"""
    # Use HybridIndexDataProvider to support Tushare/AKShare failover
    from tradingagents.dataflows.hybrid_provider import HybridIndexDataProvider
    return HybridIndexDataProvider()

# ==================== 辅助函数：格式化数据 ====================

def _format_macro_data_to_markdown(macro_data: dict) -> str:
    """将宏观数据格式化为Markdown"""
    
    # Helper to get first item if it's a list (since providers return list of records)
    def get_latest(key):
        val = macro_data.get(key)
        if isinstance(val, list) and val:
            return val[0]
        if isinstance(val, dict):
            return val
        return {}

    gdp = get_latest('gdp')
    cpi = get_latest('cpi')
    pmi = get_latest('pmi')
    m2 = get_latest('m2')
    lpr = get_latest('lpr')
    
    # Mapping helper
    def get_val(data, keys, default=0):
        for k in keys:
            if k in data:
                return data[k]
        return default

    def get_str(data, keys, default='N/A'):
        for k in keys:
            if k in data:
                return str(data[k])
        return default
    
    report = f"""# 宏观经济指标数据

## 📊 经济增长指标

### GDP (国内生产总值)
- **季度**: {get_str(gdp, ['quarter', 'end_date'])}
- **绝对值**: {get_val(gdp, ['value', 'gdp']):.2f} 亿元
- **同比增长**: {get_val(gdp, ['growth_rate', 'gdp_yoy']):.2f}%

---

## 💰 物价与通胀

### CPI (消费者物价指数)
- **月份**: {get_str(cpi, ['month'])}
- **当月指数**: {get_val(cpi, ['value', 'nt_val'], 100):.2f}
- **同比增长**: {get_val(cpi, ['year_on_year', 'nt_yoy']):.2f}%

---

## 🏭 生产与景气

### PMI (采购经理人指数)
- **月份**: {get_str(pmi, ['month'])}
- **制造业PMI**: {get_val(pmi, ['manufacturing', 'manu'], 50):.2f} ({'扩张' if get_val(pmi, ['manufacturing', 'manu'], 50) > 50 else '收缩'})
- **非制造业PMI**: {get_val(pmi, ['non_manufacturing', 'non_manu'], 50):.2f} ({'扩张' if get_val(pmi, ['non_manufacturing', 'non_manu'], 50) > 50 else '收缩'})

---

## 💵 货币与信贷

### M2 (货币供应量)
- **月份**: {get_str(m2, ['month'])}
- **M2余额**: {get_val(m2, ['value', 'm2']):.2f} 亿元
- **同比增长**: {get_val(m2, ['growth_rate', 'm2_yoy']):.2f}%

### LPR (贷款市场报价利率)
- **日期**: {get_str(lpr, ['date'])}
- **1年期LPR**: {get_val(lpr, ['lpr_1y', '1y']):.2f}%
- **5年期LPR**: {get_val(lpr, ['lpr_5y', '5y']):.2f}%

---

📅 **数据获取时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
"""
    
    return report.strip()


def _format_news_to_markdown(news_list: list, title: str = "政策新闻汇总") -> str:
    """将新闻列表格式化为Markdown"""
    
    if not news_list or len(news_list) == 0:
        return f"暂无{title}数据"
    
    report = f"# {title}\n\n"
    
    for i, news in enumerate(news_list, 1):
        title_text = news.get('title', '无标题')
        content = news.get('content', '')
        date = news.get('date', '')
        source = news.get('source', '未知来源')
        
        report += f"## {i}. {title_text}\n\n"
        report += f"**来源**: {source} | **日期**: {date}\n\n"
        
        if content:
            # 限制内容长度，避免过长
            content_preview = content[:500] + '...' if len(content) > 500 else content
            report += f"{content_preview}\n\n"
        
        report += "---\n\n"
    
    report += f"📅 **数据获取时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
    
    return report.strip()


def _format_sector_data_to_markdown(sector_data: dict, trade_date: str = None) -> str:
    """将板块数据格式化为Markdown"""
    
    top_sectors = sector_data.get('top_sectors', [])
    bottom_sectors = sector_data.get('bottom_sectors', [])
    
    if trade_date is None:
        trade_date = datetime.now().strftime('%Y-%m-%d')
    
    report = f"""# 板块资金流向分析

📅 **交易日期**: {trade_date}

---

## 📈 领涨板块 (Top 5)

"""
    
    if top_sectors:
        for i, sector in enumerate(top_sectors, 1):
            name = sector.get('name', '未知板块')
            change_pct = sector.get('change_pct', 0)
            net_inflow = sector.get('net_inflow', 0)
            turnover_rate = sector.get('turnover_rate', 0)
            
            emoji = "🔥" if change_pct > 3 else "📈"
            
            report += f"### {i}. {emoji} {name}\n"
            report += f"- **涨跌幅**: {change_pct:+.2f}%\n"
            if net_inflow != 0:
                report += f"- **资金净流入**: {net_inflow:.2f} 万元\n"
            if turnover_rate != 0:
                report += f"- **换手率**: {turnover_rate:.2f}%\n"
            report += "\n"
    else:
        report += "暂无领涨板块数据\n\n"
    
    report += "---\n\n"
    
    if bottom_sectors:
        report += "## 📉 领跌板块 (Bottom 5)\n\n"
        
        for i, sector in enumerate(bottom_sectors, 1):
            name = sector.get('name', '未知板块')
            change_pct = sector.get('change_pct', 0)
            net_inflow = sector.get('net_inflow', 0)
            turnover_rate = sector.get('turnover_rate', 0)
            
            emoji = "💧" if change_pct < -3 else "📉"
            
            report += f"### {i}. {emoji} {name}\n"
            report += f"- **涨跌幅**: {change_pct:+.2f}%\n"
            if net_inflow != 0:
                report += f"- **资金净流出**: {net_inflow:.2f} 万元\n"
            if turnover_rate != 0:
                report += f"- **换手率**: {turnover_rate:.2f}%\n"
            report += "\n"
        
        report += "---\n\n"
    
    report += f"📅 **数据获取时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
    
    return report.strip()


@tool
def fetch_multi_source_news(
    keywords: Annotated[str, "搜索关键词（可选）"] = "", 
    lookback_days: Annotated[int, "回溯天数，默认1天（快讯）"] = 1
) -> str:
    """
    获取多源聚合财经快讯 (用于交叉验证)
    
    整合来源: 财联社、新浪财经、同花顺、富途牛牛
    适用于获取最新的市场快讯和多源验证
    
    Args:
        keywords: 搜索关键词
        lookback_days: 回溯天数
        
    Returns:
        str: Markdown格式的新闻
    """
    logger.info(f"🌐 [多源新闻工具] 开始获取多源新闻, keywords={keywords}")
    
    try:
        from tradingagents.dataflows.index_data import get_index_data_provider
        
        provider = get_index_data_provider()
        news_list = provider.get_multi_source_news(keywords, lookback_days)
        
        # 格式化为Markdown
        title = f"多源财经快讯 ({keywords})" if keywords else "多源财经快讯"
        report = _format_news_to_markdown(news_list, title)
        
        logger.info(f"✅ [多源新闻工具] 新闻获取成功，共{len(news_list)}条")
        return report
        
    except Exception as e:
        logger.error(f"❌ [多源新闻工具] 新闻获取失败: {e}")
        return f"⚠️ 多源新闻获取失败: {str(e)}"


@tool
async def fetch_technical_indicators(
    symbol: Annotated[str, "指数代码，如 '000001.SH' (上证指数)"] = "000001.SH",
    period: Annotated[str, "周期，暂只支持 'daily'"] = "daily"
) -> str:
    """
    获取指数技术指标分析
    
    计算并返回关键技术指标，包括:
    - 均线系统 (MA5, MA20, MA60)
    - MACD (趋势动能)
    - RSI (超买超卖)
    - KDJ (随机指标)
    - 布林带 (BOLL)
    
    Args:
        symbol: 指数代码，默认为上证指数 (000001.SH)
        period: 周期
        
    Returns:
        str: Markdown格式的技术分析报告
    """
    logger.info(f"📈 [技术分析工具] 开始计算技术指标, symbol={symbol}")
    
    # 常用指数名称映射
    NAME_TO_CODE = {
        "上证指数": "000001.SH",
        "上证综指": "000001.SH",
        "深证成指": "399001.SZ",
        "创业板指": "399006.SZ",
        "科创50": "000688.SH",
        "沪深300": "000300.SH",
        "中证500": "000905.SH",
        "半导体": "399281.SZ", # 电子50 (AKShare支持，作为半导体替代)
        "半导体指数": "H30184.CSI",
        "白酒": "399997.SZ", # 中证白酒
        "医药": "000933.SH", # 中证医药
        "新能源": "399808.SZ", # 中证新能源
    }
    
    # 尝试映射名称到代码
    if symbol in NAME_TO_CODE:
        logger.info(f"🔄 将名称 '{symbol}' 映射为代码 '{NAME_TO_CODE[symbol]}'")
        symbol = NAME_TO_CODE[symbol]
    
    try:
        from tradingagents.dataflows.index_data import get_index_data_provider
        from tradingagents.tools.analysis.indicators import add_all_indicators, last_values
        import pandas as pd
        
        provider = get_index_data_provider()
        
        # 获取K线数据 (Async)
        # 如果是CSI代码，可能需要特殊处理，这里假设Provider能处理或降级
        df = await provider.get_index_daily_async(ts_code=symbol)
        
        if df is None or df.empty:
            # 尝试去掉后缀重试 (针对某些数据源可能不需要后缀)
            if "." in symbol:
                pure_code = symbol.split(".")[0]
                logger.info(f"⚠️ 获取失败，尝试使用纯代码 '{pure_code}' 重试...")
                df = await provider.get_index_daily_async(ts_code=pure_code)
                
            if df is None or df.empty:
                return f"⚠️ 未获取到 {symbol} 的K线数据"
            
        # 确保按日期升序
        if 'trade_date' in df.columns:
            df = df.sort_values('trade_date')
            
        # 计算指标
        df = add_all_indicators(df, close_col='close', high_col='high', low_col='low')
        
        # 获取最新值
        latest = df.iloc[-1]
        prev = df.iloc[-2] if len(df) > 1 else latest
        
        # 格式化报告
        report = f"""# {symbol} 技术分析报告

📅 **日期**: {latest.get('trade_date', 'N/A')}
💰 **收盘价**: {latest.get('close', 0):.2f} ({latest.get('pct_chg', 0):+.2f}%)

## 📊 趋势分析 (MA系统)
- **MA5**: {latest.get('ma5', 0):.2f} (短线)
- **MA20**: {latest.get('ma20', 0):.2f} (中线)
- **MA60**: {latest.get('ma60', 0):.2f} (长线)
- **信号**: {"多头排列" if latest.get('ma5') > latest.get('ma20') > latest.get('ma60') else "非多头排列"}

## 🌊 动能分析 (MACD)
- **DIF**: {latest.get('macd_dif', 0):.3f}
- **DEA**: {latest.get('macd_dea', 0):.3f}
- **MACD柱**: {latest.get('macd', 0):.3f}
- **信号**: {"金叉" if latest.get('macd_dif') > latest.get('macd_dea') and prev.get('macd_dif') <= prev.get('macd_dea') else ("死叉" if latest.get('macd_dif') < latest.get('macd_dea') and prev.get('macd_dif') >= prev.get('macd_dea') else "维持")}

## 📉 超买超卖 (RSI & KDJ)
- **RSI (14)**: {latest.get('rsi', 0):.2f} ({"超买" if latest.get('rsi') > 80 else ("超卖" if latest.get('rsi') < 20 else "正常")})
- **KDJ**: K={latest.get('kdj_k', 0):.2f}, D={latest.get('kdj_d', 0):.2f}, J={latest.get('kdj_j', 0):.2f}

## 🔔 布林带 (BOLL)
- **上轨**: {latest.get('boll_upper', 0):.2f}
- **中轨**: {latest.get('boll_mid', 0):.2f}
- **下轨**: {latest.get('boll_lower', 0):.2f}
- **位置**: {"突破上轨" if latest.get('close') > latest.get('boll_upper') else ("跌破下轨" if latest.get('close') < latest.get('boll_lower') else "通道内")}

"""
        logger.info(f"✅ [技术分析工具] 指标计算完成")
        return report
        
    except Exception as e:
        logger.error(f"❌ [技术分析工具] 计算失败: {e}")
        return f"⚠️ 技术指标计算失败: {str(e)}"


# 工具列表，供外部导入使用
INDEX_ANALYSIS_TOOLS = [
    fetch_macro_data,
    fetch_policy_news,
    fetch_sector_news,
    fetch_sector_rotation,
    fetch_multi_source_news,
    fetch_technical_indicators
]
