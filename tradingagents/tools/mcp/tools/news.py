"""
MCP 新闻工具

使用 FastMCP 的 @mcp.tool() 装饰器定义统一新闻获取工具。
保留现有的统一新闻获取逻辑，支持 A股、港股、美股。
"""

import logging
import re
from datetime import datetime, timedelta
from typing import Optional

logger = logging.getLogger(__name__)

# 全局 toolkit 配置，由 LocalMCPServer 初始化时设置
_toolkit_config: dict = {}


def set_toolkit_config(config: dict):
    """设置工具配置"""
    global _toolkit_config
    _toolkit_config = config or {}


def _identify_stock_type(stock_code: str) -> str:
    """识别股票类型"""
    stock_code = stock_code.upper().strip()
    
    # A股判断
    if re.match(r'^(00|30|60|68)\d{4}$', stock_code):
        return "A股"
    elif re.match(r'^(SZ|SH)\d{6}$', stock_code):
        return "A股"
    
    # 港股判断
    elif re.match(r'^\d{4,5}\.HK$', stock_code):
        return "港股"
    elif re.match(r'^\d{4,5}$', stock_code) and len(stock_code) <= 5:
        return "港股"
    
    # 美股判断
    elif re.match(r'^[A-Z]{1,5}$', stock_code):
        return "美股"
    elif '.' in stock_code and not stock_code.endswith('.HK'):
        return "美股"
    
    # 默认按A股处理
    return "A股"


def _get_news_from_database(stock_code: str, max_news: int = 10) -> str:
    """从数据库获取新闻"""
    try:
        from tradingagents.dataflows.cache.app_adapter import get_mongodb_client
        
        max_news = int(max_news)
        client = get_mongodb_client()
        if not client:
            logger.warning("[MCP新闻工具] 无法连接到MongoDB")
            return ""

        db = client.get_database('tradingagents')
        collection = db.stock_news

        # 标准化股票代码
        clean_code = stock_code.replace('.SH', '').replace('.SZ', '').replace('.SS', '')\
                               .replace('.XSHE', '').replace('.XSHG', '').replace('.HK', '')

        # 查询最近30天的新闻
        thirty_days_ago = datetime.now() - timedelta(days=30)

        query_list = [
            {'symbol': clean_code, 'publish_time': {'$gte': thirty_days_ago}},
            {'symbol': stock_code, 'publish_time': {'$gte': thirty_days_ago}},
            {'symbols': clean_code, 'publish_time': {'$gte': thirty_days_ago}},
            {'symbol': clean_code},
            {'symbols': clean_code},
        ]

        news_items = []
        for query in query_list:
            cursor = collection.find(query).sort('publish_time', -1).limit(max_news)
            news_items = list(cursor)
            if news_items:
                logger.info(f"[MCP新闻工具] 使用查询 {query} 找到 {len(news_items)} 条新闻")
                break

        if not news_items:
            return ""

        # 格式化新闻
        report = f"# {stock_code} 最新新闻 (数据库缓存)\n\n"
        report += f"📅 查询时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
        report += f"📊 新闻数量: {len(news_items)} 条\n\n"

        for i, news in enumerate(news_items, 1):
            title = news.get('title', '无标题')
            content = news.get('content', '') or news.get('summary', '')
            source = news.get('source', '未知来源')
            publish_time = news.get('publish_time', datetime.now())
            sentiment = news.get('sentiment', 'neutral')

            sentiment_icon = {'positive': '📈', 'negative': '📉', 'neutral': '➖'}.get(sentiment, '➖')

            report += f"## {i}. {sentiment_icon} {title}\n\n"
            report += f"**来源**: {source} | **时间**: {publish_time.strftime('%Y-%m-%d %H:%M') if isinstance(publish_time, datetime) else publish_time}\n"
            report += f"**情绪**: {sentiment}\n\n"

            if content:
                content_preview = content[:500] + '...' if len(content) > 500 else content
                report += f"{content_preview}\n\n"

            report += "---\n\n"

        return report

    except Exception as e:
        logger.error(f"[MCP新闻工具] 从数据库获取新闻失败: {e}")
        return ""


def _format_news_result(news_content: str, source: str) -> str:
    """格式化新闻结果"""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    return f"""
=== 📰 新闻数据来源: {source} ===
获取时间: {timestamp}
数据长度: {len(news_content)} 字符

=== 📋 新闻内容 ===
{news_content}

=== ✅ 数据状态 ===
状态: 成功获取
来源: {source}
时间戳: {timestamp}
""".strip()


def get_stock_news(
    stock_code: str,
    max_news: int = 10
) -> str:
    """
    统一新闻获取工具 - 根据股票代码自动获取相应市场的新闻。
    
    自动识别股票类型（A股/港股/美股）并从最佳数据源获取新闻：
    - A股: 数据库缓存、东方财富实时新闻、Google中文搜索
    - 港股: Google搜索、实时行情资讯
    - 美股: OpenAI全球新闻、Google英文搜索、FinnHub数据
    
    Args:
        stock_code: 股票代码，支持多种格式：
            - A股：如 '600519', '000001', '300750'
            - 港股：如 '0700.HK', '09988', '01810.HK'
            - 美股：如 'AAPL', 'TSLA', 'NVDA'
        max_news: 获取新闻的最大数量，建议范围 5-20，默认 10
    
    Returns:
        格式化的新闻内容，包含新闻标题、来源、时间和摘要
    """
    if not stock_code:
        return "❌ 错误: 未提供股票代码"
    
    logger.info(f"[MCP新闻工具] 开始获取 {stock_code} 的新闻")
    
    stock_type = _identify_stock_type(stock_code)
    logger.info(f"[MCP新闻工具] 股票类型: {stock_type}")
    
    # 优先从数据库获取
    try:
        db_news = _get_news_from_database(stock_code, max_news)
        if db_news:
            logger.info(f"[MCP新闻工具] ✅ 数据库新闻获取成功")
            return _format_news_result(db_news, "数据库缓存")
    except Exception as e:
        logger.warning(f"[MCP新闻工具] 数据库新闻获取失败: {e}")
    
    # 尝试从 AKShare 同步新闻
    try:
        from tradingagents.dataflows.providers.china.akshare import AKShareProvider
        import asyncio
        
        clean_code = stock_code.replace('.SH', '').replace('.SZ', '').replace('.SS', '')\
                               .replace('.XSHE', '').replace('.XSHG', '').replace('.HK', '')
        
        provider = AKShareProvider()
        
        # 在新线程中运行异步任务
        def run_async():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                return loop.run_until_complete(provider.get_stock_news(symbol=clean_code, limit=max_news))
            finally:
                loop.close()
        
        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(run_async)
            news_data = future.result(timeout=30)
        
        if news_data:
            # 格式化新闻数据
            report = f"# {stock_code} 最新新闻 (AKShare)\n\n"
            report += f"📅 查询时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
            report += f"📊 新闻数量: {len(news_data)} 条\n\n"
            
            for i, news in enumerate(news_data[:max_news], 1):
                title = news.get('title', '无标题')
                content = news.get('content', '') or news.get('summary', '')
                source = news.get('source', '未知来源')
                
                report += f"## {i}. {title}\n\n"
                report += f"**来源**: {source}\n\n"
                
                if content:
                    content_preview = content[:500] + '...' if len(content) > 500 else content
                    report += f"{content_preview}\n\n"
                
                report += "---\n\n"
            
            return _format_news_result(report, "AKShare")
    except Exception as e:
        logger.warning(f"[MCP新闻工具] AKShare新闻获取失败: {e}")
    
    # 返回无数据提示
    return f"""
=== 📰 新闻数据来源: 无可用数据源 ===
获取时间: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}

=== ⚠️ 提示 ===
无法获取 {stock_code} ({stock_type}) 的新闻数据。
可能的原因：
1. 数据库中没有该股票的新闻缓存
2. 外部数据源暂时不可用
3. 股票代码格式不正确

建议：
- 检查股票代码是否正确
- 稍后重试
- 尝试使用其他工具获取信息
"""
