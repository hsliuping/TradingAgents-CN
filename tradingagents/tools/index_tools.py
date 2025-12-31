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
async def fetch_macro_data(query_date: Annotated[str, "查询日期，格式 YYYY-MM-DD，留空则使用当前日期"] = None) -> str:
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
    
    # -------------------- 缓存逻辑开始 --------------------
    mongo_db = None
    collection = None
    target_date = query_date if query_date else datetime.now().strftime('%Y-%m-%d')
    cache_key = f"macro_analysis:{target_date}"
    
    try:
        from tradingagents.config.database_manager import get_database_manager
        
        # 1. 获取数据库连接
        db_manager = get_database_manager()
        mongo_db = db_manager.get_mongodb_db()
        
        if mongo_db is not None:
            collection = mongo_db["macro_analysis_cache"]
            
            # 2. 查询缓存
            cached_doc = collection.find_one({"_id": cache_key})
            
            if cached_doc:
                # 4. 检查有效期 (7天)
                cache_time = cached_doc.get("timestamp")
                if cache_time and (datetime.now() - cache_time) < timedelta(days=7):
                    logger.info(f"✅ [宏观数据工具] 命中缓存: {cache_key}")
                    return cached_doc.get("report", "")
                else:
                    logger.info(f"⚠️ [宏观数据工具] 缓存已过期: {cache_key}")
            else:
                logger.debug(f"ℹ️ [宏观数据工具] 未找到缓存: {cache_key}")
                
    except Exception as e:
        logger.warning(f"⚠️ [宏观数据工具] 读取缓存失败 (降级执行): {e}")
    # -------------------- 缓存逻辑结束 --------------------
    
    try:
        # Use local helper
        provider = get_index_data_provider()
        # Use async method directly to avoid event loop conflicts
        if hasattr(provider, 'get_macro_data'):
            macro_data = await provider.get_macro_data(end_date=query_date)
        else:
            # Fallback for non-hybrid providers if any
            macro_data = provider.get_macro_economics_data(end_date=query_date)
        
        # Handle list response if provider returns a list (some providers might)
        if isinstance(macro_data, list):
            macro_data = macro_data[0] if macro_data else {}
        
        # 格式化为Markdown
        report = _format_macro_data_to_markdown(macro_data)

        # -------------------- 写入缓存开始 --------------------
        try:
            if collection is not None:
                cache_doc = {
                    "_id": cache_key,
                    "data": macro_data,
                    "report": report,
                    "timestamp": datetime.now(),
                    "query_date": target_date
                }
                # 使用 upsert=True 插入或更新
                collection.replace_one({"_id": cache_key}, cache_doc, upsert=True)
                logger.info(f"💾 [宏观数据工具] 结果已写入缓存: {cache_key}")
        except Exception as e:
            logger.warning(f"⚠️ [宏观数据工具] 写入缓存失败: {e}")
        # -------------------- 写入缓存结束 --------------------
        
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
    sector_name: Annotated[str, "板块或概念名称，如'半导体', '医药'，或者指数代码 '980022'"], 
    lookback_days: Annotated[int, "回溯天数，默认7天"] = 7
) -> str:
    """
    获取特定板块/概念新闻
    
    Args:
        sector_name: 板块或概念名称，也可以是指数代码
        lookback_days: 回溯天数，默认7天
        
    Returns:
        str: Markdown格式的新闻
    """
    logger.info(f"🏭 [板块新闻工具] 开始获取板块新闻, sector={sector_name}")
    
    try:
        from tradingagents.dataflows.index_data import get_index_data_provider
        from tradingagents.utils.index_resolver import IndexResolver
        import asyncio
        
        # 尝试解析代码为名称
        # fetch_sector_news 是同步工具，但IndexResolver是异步的
        # 为了兼容性，这里使用 run_until_complete (在 executor 中可能不支持)
        # 或者直接在这里做一个简化的同步解析，或者将 fetch_sector_news 改为 async
        
        # 考虑到 IndexResolver 内部使用 run_in_executor 调用 AKShare，
        # 如果我们在同步工具中直接调用 async resolve，需要 event loop。
        # 简单起见，我们假设 sector_name 可能是代码，如果是，我们尝试动态解析
        
        real_sector_name = sector_name
        
        # 简单的代码特征检测
        if any(char.isdigit() for char in sector_name):
             # 包含数字，可能是代码，尝试解析
             try:
                 # 创建临时 loop 或使用现有 loop
                 try:
                     loop = asyncio.get_event_loop()
                 except RuntimeError:
                     loop = asyncio.new_event_loop()
                     asyncio.set_event_loop(loop)
                 
                 resolved = loop.run_until_complete(IndexResolver.resolve(sector_name))
                 if resolved and resolved.get('name') and "未知" not in resolved['name']:
                     real_sector_name = resolved['name']
                     logger.info(f"🔄 [板块新闻工具] 代码解析成功: {sector_name} -> {real_sector_name}")
             except Exception as e:
                 logger.warning(f"⚠️ [板块新闻工具] 代码解析失败: {e}")

        provider = get_index_data_provider()
        news_list = provider.get_sector_news(real_sector_name, lookback_days)
        
        # 格式化为Markdown
        report = _format_news_to_markdown(news_list, f"{real_sector_name}板块新闻")
        
        logger.info(f"✅ [板块新闻工具] {real_sector_name}新闻获取成功，共{len(news_list)}条")
        return report
        
    except Exception as e:
        logger.error(f"❌ [板块新闻工具] 新闻获取失败: {e}")
        return f"⚠️ {sector_name}板块新闻获取失败: {str(e)}"


@tool
async def fetch_sector_rotation(
    trade_date: Annotated[str, "交易日期，格式 YYYY-MM-DD，留空则使用最新交易日"] = None,
    sector_name: Annotated[str, "可选：指定板块名称以获取特定板块数据"] = None
) -> str:

    """
    获取板块轮动数据或特定板块资金流向
    
    获取最新的板块资金流向和涨跌幅数据，包括:
    - 领涨板块 (Top 5)
    - 领跌板块 (Bottom 5)
    - 板块资金流入/流出
    - 板块换手率
    - (如果指定sector_name) 特定板块的详细数据
    
    Args:
        trade_date: 交易日期，格式 YYYY-MM-DD
        sector_name: 可选，指定板块名称
        
    Returns:
        str: Markdown格式的板块轮动数据
    """
    logger.info(f"💰 [板块轮动工具] 开始获取板块数据, trade_date={trade_date}, sector={sector_name}")
    
    try:
        # 尝试解析代码为名称 (如果 sector_name 包含数字)
        real_sector_name = sector_name
        if sector_name and any(char.isdigit() for char in sector_name):
             try:
                 from tradingagents.utils.index_resolver import IndexResolver
                 import asyncio
                 
                 # 我们在 async 函数中，可以直接 await
                 resolved = await IndexResolver.resolve(sector_name)
                 if resolved and resolved.get('name') and "未知" not in resolved['name']:
                     real_sector_name = resolved['name']
                     logger.info(f"🔄 [板块轮动工具] 代码解析成功: {sector_name} -> {real_sector_name}")
             except Exception as e:
                 logger.warning(f"⚠️ [板块轮动工具] 代码解析失败: {e}")

        # Use local helper
        provider = get_index_data_provider()
        
        # Use async method directly to avoid event loop conflicts
        if hasattr(provider, 'get_sector_flows_async'):
            # 传递 real_sector_name 参数
            if hasattr(provider, 'akshare_provider'):
                 sector_data = await provider.akshare_provider.get_sector_fund_flow(sector_name=real_sector_name)
            else:
                 # Fallback
                 sector_data = await provider.get_sector_flows_async(trade_date=trade_date)
        else:
            sector_data = provider.get_sector_flows(trade_date=trade_date)
        
        # 格式化为Markdown
        report = _format_sector_data_to_markdown(sector_data, trade_date)
        
        # 如果有特定板块数据，添加到报告中
        if real_sector_name and sector_data.get('specific_sector'):
            spec = sector_data['specific_sector']
            # 将特定板块分析置顶
            specific_report = f"# 🎯 {spec['name']} ({sector_name if sector_name != spec['name'] else ''}) 板块深度分析\n\n"
            specific_report += f"- **涨跌幅**: {spec['change_pct']:+.2f}%\n"
            specific_report += f"- **资金净流入**: {spec['net_inflow']:.2f} 亿元\n"
            
            if spec.get('turnover_rate', 0) > 0:
                specific_report += f"- **换手率**: {spec['turnover_rate']:.2f}%\n"
                
            if spec.get('leading_stock'):
                specific_report += f"- **领涨股**: {spec['leading_stock']}\n"
                
            specific_report += f"- **市场排名**: 第 {spec['rank']} 名\n\n"
            specific_report += "---\n\n"
            
            report = specific_report + report

        logger.info(f"✅ [板块轮动工具] 板块数据获取成功")
        return report
        
    except Exception as e:
        logger.error(f"❌ [板块轮动工具] 板块数据获取失败: {e}")
        return f"⚠️ 板块数据获取失败: {str(e)}\n\n请稍后重试或使用其他数据源。"


@tool
async def fetch_stock_sector_info(stock_code: Annotated[str, "股票代码，如 '600519'"]) -> str:
    """
    获取股票所属行业板块信息
    
    Args:
        stock_code: 股票代码
        
    Returns:
        str: 股票所属行业名称
    """
    logger.info(f"🏭 [行业查询工具] 开始查询股票行业: {stock_code}")
    
    try:
        provider = get_index_data_provider()
        
        # 尝试通过 AKShareProvider 获取
        sector = None
        if hasattr(provider, 'akshare_provider'):
            sector = await provider.akshare_provider.get_stock_sector(stock_code)
            
        if sector:
            logger.info(f"✅ [行业查询工具] 查询成功: {stock_code} -> {sector}")
            return f"股票 {stock_code} 属于 **{sector}** 行业板块。"
        else:
            logger.warning(f"⚠️ [行业查询工具] 未找到股票 {stock_code} 的行业信息")
            return f"未能查询到股票 {stock_code} 的所属行业信息。"
            
    except Exception as e:
        logger.error(f"❌ [行业查询工具] 查询失败: {e}")
        return f"⚠️ 行业查询失败: {str(e)}"


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
async def fetch_market_funds_flow() -> str:
    """
    获取全市场资金流向
    
    返回北向资金、主力资金等整体流动性指标。
    
    Returns:
        str: Markdown格式的资金流向报告
    """
    logger.info(f"💸 [资金流向工具] 开始获取全市场资金流向")
    
    try:
        provider = get_index_data_provider()
        
        if hasattr(provider, 'get_market_funds_flow_async'):
            flow_data = await provider.get_market_funds_flow_async()
        else:
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
    top_concepts = sector_data.get('top_concepts', [])
    bottom_concepts = sector_data.get('bottom_concepts', [])
    
    if trade_date is None:
        trade_date = datetime.now().strftime('%Y-%m-%d')
    
    report = f"""# 板块资金流向分析

📅 **交易日期**: {trade_date}

---

## 🏭 行业板块表现

### 📈 领涨行业 (Top 5)

"""
    
    if top_sectors:
        for i, sector in enumerate(top_sectors, 1):
            name = sector.get('name', '未知板块')
            change_pct = sector.get('change_pct', 0)
            net_inflow = sector.get('net_inflow', 0)
            turnover_rate = sector.get('turnover_rate', 0)
            
            emoji = "🔥" if change_pct > 3 else "📈"
            
            report += f"**{i}. {emoji} {name}**\n"
            report += f"- 涨跌幅: {change_pct:+.2f}%\n"
            if net_inflow != 0:
                report += f"- 资金净流入: {net_inflow:.2f} 亿元\n"
            if turnover_rate != 0:
                report += f"- 换手率: {turnover_rate:.2f}%\n"
            report += "\n"
    else:
        report += "暂无领涨行业数据\n\n"
    
    if bottom_sectors:
        report += "### 📉 领跌行业 (Bottom 5)\n\n"
        
        for i, sector in enumerate(bottom_sectors, 1):
            name = sector.get('name', '未知板块')
            change_pct = sector.get('change_pct', 0)
            net_inflow = sector.get('net_inflow', 0)
            turnover_rate = sector.get('turnover_rate', 0)
            
            emoji = "💧" if change_pct < -3 else "📉"
            
            report += f"**{i}. {emoji} {name}**\n"
            report += f"- 涨跌幅: {change_pct:+.2f}%\n"
            if net_inflow != 0:
                report += f"- 资金净流出: {net_inflow:.2f} 亿元\n"
            if turnover_rate != 0:
                report += f"- 换手率: {turnover_rate:.2f}%\n"
            report += "\n"
        
    report += "---\n\n"
    
    # 添加概念板块部分
    if top_concepts or bottom_concepts:
        report += "## 💡 概念板块表现\n\n"
        
        if top_concepts:
            report += "### 📈 领涨概念 (Top 5)\n\n"
            for i, sector in enumerate(top_concepts, 1):
                name = sector.get('name', '未知概念')
                change_pct = sector.get('change_pct', 0)
                net_inflow = sector.get('net_inflow', 0)
                leading_stock = sector.get('leading_stock', '')
                
                emoji = "🚀" if change_pct > 3 else "📈"
                
                report += f"**{i}. {emoji} {name}**\n"
                report += f"- 涨跌幅: {change_pct:+.2f}%\n"
                if net_inflow != 0:
                    report += f"- 资金净流入: {net_inflow:.2f} 亿元\n"
                if leading_stock:
                    report += f"- 领涨股: {leading_stock}\n"
                report += "\n"

        if bottom_concepts:
            report += "### 📉 领跌概念 (Bottom 5)\n\n"
            for i, sector in enumerate(bottom_concepts, 1):
                name = sector.get('name', '未知概念')
                change_pct = sector.get('change_pct', 0)
                net_inflow = sector.get('net_inflow', 0)
                leading_stock = sector.get('leading_stock', '')
                
                emoji = "❄️" if change_pct < -3 else "📉"
                
                report += f"**{i}. {emoji} {name}**\n"
                report += f"- 涨跌幅: {change_pct:+.2f}%\n"
                if net_inflow != 0:
                    report += f"- 资金净流出: {net_inflow:.2f} 亿元\n"
                if leading_stock:
                    report += f"- 领跌股: {leading_stock}\n"
                report += "\n"
                
        report += "---\n\n"
    
    report += f"📅 **数据获取时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
    
    return report.strip()


@tool
async def fetch_multi_source_news(
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
        
        # Use async method
        if hasattr(provider, 'get_multi_source_news_async'):
            news_list = await provider.get_multi_source_news_async(keywords, lookback_days)
        else:
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
    
    try:
        from tradingagents.dataflows.index_data import get_index_data_provider
        from tradingagents.tools.analysis.indicators import add_all_indicators, last_values
        from tradingagents.utils.index_resolver import IndexResolver
        import pandas as pd
        import akshare as ak
        
        provider = get_index_data_provider()
        
        # 1. 智能解析代码
        resolved_info = await IndexResolver.resolve(symbol)
        source_type = resolved_info.get("source_type", "index")
        real_symbol = resolved_info.get("symbol", symbol)
        name = resolved_info.get("name", symbol)
        
        logger.info(f"🔄 [技术分析工具] 解析结果: {symbol} -> {name} ({source_type})")
        
        df = None
        
        # 2. 根据类型分流获取数据
        if source_type == "concept":
            # 概念/行业板块数据
            logger.info(f"📊 [技术分析工具] 获取板块历史数据: {real_symbol}")
            try:
                # 东方财富概念历史
                # 注意：akshare 同步调用，需在 executor 中运行以免阻塞
                import asyncio
                loop = asyncio.get_running_loop()
                
                def fetch_concept():
                    return ak.stock_board_concept_hist_em(symbol=real_symbol, period="daily", adjust="qfq")
                
                df_raw = await loop.run_in_executor(None, fetch_concept)
                df = IndexResolver.normalize_concept_data(df_raw)
                
            except Exception as e:
                logger.error(f"❌ [技术分析工具] 获取板块数据失败: {e}")
                
        elif source_type == "industry":
             # 行业板块数据 (逻辑同 concept，通常接口通用或类似)
            logger.info(f"📊 [技术分析工具] 获取行业历史数据: {real_symbol}")
            try:
                import asyncio
                loop = asyncio.get_running_loop()
                def fetch_industry():
                    return ak.stock_board_industry_hist_em(symbol=real_symbol, period="daily", adjust="qfq")
                
                df_raw = await loop.run_in_executor(None, fetch_industry)
                df = IndexResolver.normalize_concept_data(df_raw)
            except Exception as e:
                logger.error(f"❌ [技术分析工具] 获取行业数据失败: {e}")

        else:
            # 标准指数数据 (Fallback to original logic)
            # 获取K线数据 (Async)
            df = await provider.get_index_daily_async(ts_code=real_symbol)
            
            if df is None or df.empty:
                # 尝试去掉后缀重试
                if "." in real_symbol:
                    pure_code = real_symbol.split(".")[0]
                    logger.info(f"⚠️ 获取失败，尝试使用纯代码 '{pure_code}' 重试...")
                    df = await provider.get_index_daily_async(ts_code=pure_code)

        # 3. 检查数据有效性
        if df is None or df.empty:
            return f"⚠️ 未获取到 {symbol} ({name}) 的K线数据，请检查代码是否正确或数据源是否支持。"
            
        # 确保按日期升序
        if 'trade_date' in df.columns:
            df = df.sort_values('trade_date')
            
        # 4. 计算指标
        df = add_all_indicators(df, close_col='close', high_col='high', low_col='low')
        
        # 获取最新值
        latest = df.iloc[-1]
        prev = df.iloc[-2] if len(df) > 1 else latest
        
        # 5. 格式化报告
        report = f"""# {name} ({symbol}) 技术分析报告

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
    fetch_stock_sector_info,
    fetch_multi_source_news,
    fetch_technical_indicators
]
