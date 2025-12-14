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
        from tradingagents.dataflows.index_data import get_index_data_provider
        
        provider = get_index_data_provider()
        macro_data = provider.get_macro_economics_data(end_date=query_date)
        
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
        from tradingagents.dataflows.index_data import get_index_data_provider
        
        provider = get_index_data_provider()
        news_list = provider.get_policy_news(lookback_days=lookback_days)
        
        # 格式化为Markdown
        report = _format_news_to_markdown(news_list)
        
        logger.info(f"✅ [政策新闻工具] 政策新闻获取成功，共{len(news_list)}条")
        return report
        
    except Exception as e:
        logger.error(f"❌ [政策新闻工具] 政策新闻获取失败: {e}")
        return f"⚠️ 政策新闻获取失败: {str(e)}\n\n请稍后重试或使用其他数据源。"


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
        from tradingagents.dataflows.index_data import get_index_data_provider
        
        provider = get_index_data_provider()
        sector_data = provider.get_sector_flows(trade_date=trade_date)
        
        # 格式化为Markdown
        report = _format_sector_data_to_markdown(sector_data, trade_date)
        
        logger.info(f"✅ [板块轮动工具] 板块数据获取成功")
        return report
        
    except Exception as e:
        logger.error(f"❌ [板块轮动工具] 板块数据获取失败: {e}")
        return f"⚠️ 板块数据获取失败: {str(e)}\n\n请稍后重试或使用其他数据源。"


# ==================== 辅助函数：格式化数据 ====================

def _format_macro_data_to_markdown(macro_data: dict) -> str:
    """将宏观数据格式化为Markdown"""
    
    report = f"""# 宏观经济指标数据

## 📊 经济增长指标

### GDP (国内生产总值)
- **季度**: {macro_data.get('gdp', {}).get('quarter', 'N/A')}
- **绝对值**: {macro_data.get('gdp', {}).get('value', 0):.2f} 亿元
- **同比增长**: {macro_data.get('gdp', {}).get('growth_rate', 0):.2f}%

---

## 💰 物价与通胀

### CPI (消费者物价指数)
- **月份**: {macro_data.get('cpi', {}).get('month', 'N/A')}
- **当月指数**: {macro_data.get('cpi', {}).get('value', 100):.2f}
- **同比增长**: {macro_data.get('cpi', {}).get('year_on_year', 0):.2f}%

---

## 🏭 生产与景气

### PMI (采购经理人指数)
- **月份**: {macro_data.get('pmi', {}).get('month', 'N/A')}
- **制造业PMI**: {macro_data.get('pmi', {}).get('manufacturing', 50):.2f} ({'扩张' if macro_data.get('pmi', {}).get('manufacturing', 50) > 50 else '收缩'})
- **非制造业PMI**: {macro_data.get('pmi', {}).get('non_manufacturing', 50):.2f} ({'扩张' if macro_data.get('pmi', {}).get('non_manufacturing', 50) > 50 else '收缩'})

---

## 💵 货币与信贷

### M2 (货币供应量)
- **月份**: {macro_data.get('m2', {}).get('month', 'N/A')}
- **M2余额**: {macro_data.get('m2', {}).get('value', 0):.2f} 亿元
- **同比增长**: {macro_data.get('m2', {}).get('growth_rate', 0):.2f}%

### LPR (贷款市场报价利率)
- **日期**: {macro_data.get('lpr', {}).get('date', 'N/A')}
- **1年期LPR**: {macro_data.get('lpr', {}).get('lpr_1y', 0):.2f}%
- **5年期LPR**: {macro_data.get('lpr', {}).get('lpr_5y', 0):.2f}%

---

📅 **数据获取时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
"""
    
    return report.strip()


def _format_news_to_markdown(news_list: list) -> str:
    """将新闻列表格式化为Markdown"""
    
    if not news_list or len(news_list) == 0:
        return "暂无政策新闻数据"
    
    report = "# 政策新闻汇总\n\n"
    
    for i, news in enumerate(news_list, 1):
        title = news.get('title', '无标题')
        content = news.get('content', '')
        date = news.get('date', '')
        source = news.get('source', '未知来源')
        
        report += f"## {i}. {title}\n\n"
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


# 工具列表，供外部导入使用
INDEX_ANALYSIS_TOOLS = [
    fetch_macro_data,
    fetch_policy_news,
    fetch_sector_rotation
]
