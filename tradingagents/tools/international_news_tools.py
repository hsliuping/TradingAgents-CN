#!/usr/bin/env python3
"""
国际新闻数据工具

提供彭博社、路透社、Google News等国际媒体数据源
用于International News Analyst获取短期新闻影响

数据源优先级：
1. NewsAPI (付费，需配置NEWSAPI_KEY) - 彭博社、路透社
2. Google News (免费降级方案)
"""

from langchain.tools import tool
from typing import Annotated
from datetime import datetime, timedelta
import os
import requests

from tradingagents.utils.logging_manager import get_logger

logger = get_logger("tools")


@tool
def fetch_bloomberg_news(
    keywords: Annotated[str, "搜索关键词，如'China semiconductor policy'"],
    lookback_days: Annotated[int, "回溯天数，默认7天"] = 7
) -> str:
    """
    获取彭博社新闻
    
    数据源: NewsAPI (bloomberg.com)
    降级方案: Google News
    
    Args:
        keywords: 搜索关键词，建议使用英文
        lookback_days: 回溯天数，默认7天
        
    Returns:
        Markdown格式的新闻摘要
    """
    try:
        logger.info(f"🌍 [彭博社新闻] 开始获取，关键词: {keywords}, 回溯: {lookback_days}天")
        
        # 1. 检查NewsAPI配置
        api_key = os.getenv("NEWSAPI_KEY")
        if not api_key:
            logger.warning("⚠️ NewsAPI Key未配置，降级到Google News")
            # 直接调用实现函数而不是工具对象
            return _fetch_google_news_impl(keywords, lookback_days)
        
        # 2. 调用NewsAPI
        end_date = datetime.now()
        start_date = end_date - timedelta(days=lookback_days)
        
        url = "https://newsapi.org/v2/everything"
        params = {
            "apiKey": api_key,
            "sources": "bloomberg",
            "q": keywords,
            "from": start_date.strftime("%Y-%m-%d"),
            "to": end_date.strftime("%Y-%m-%d"),
            "language": "en",
            "sortBy": "publishedAt",
            "pageSize": 10
        }
        
        logger.info(f"🌍 [彭博社新闻] 请求NewsAPI: {url}")
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        
        data = response.json()
        articles = data.get("articles", [])
        
        if not articles:
            logger.warning(f"⚠️ [彭博社新闻] 未找到相关新闻")
            return f"## 彭博社新闻 (关键词: {keywords})\n\n暂无相关新闻。"
        
        # 3. 格式化为Markdown
        result = _format_news_to_markdown(articles, "Bloomberg", keywords)
        
        logger.info(f"✅ [彭博社新闻] 获取成功: {len(articles)} 条")
        return result
        
    except requests.exceptions.RequestException as e:
        logger.error(f"❌ [彭博社新闻] API请求失败: {e}")
        # 直接调用实现函数而不是工具对象
        return _fetch_google_news_impl(keywords, lookback_days)
    except Exception as e:
        logger.error(f"❌ [彭博社新闻] 获取失败: {e}")
        # 直接调用实现函数而不是工具对象
        return _fetch_google_news_impl(keywords, lookback_days)


@tool
def fetch_reuters_news(
    keywords: Annotated[str, "搜索关键词"],
    lookback_days: Annotated[int, "回溯天数，默认7天"] = 7
) -> str:
    """
    获取路透社新闻
    
    数据源: NewsAPI (reuters.com)
    降级方案: Google News
    
    Args:
        keywords: 搜索关键词
        lookback_days: 回溯天数
        
    Returns:
        Markdown格式的新闻摘要
    """
    try:
        logger.info(f"🌍 [路透社新闻] 开始获取，关键词: {keywords}")
        
        # 1. 检查NewsAPI配置
        api_key = os.getenv("NEWSAPI_KEY")
        if not api_key:
            logger.warning("⚠️ NewsAPI Key未配置，降级到Google News")
            # 直接调用实现函数而不是工具对象
            return _fetch_google_news_impl(keywords, lookback_days)
        
        # 2. 调用NewsAPI
        end_date = datetime.now()
        start_date = end_date - timedelta(days=lookback_days)
        
        url = "https://newsapi.org/v2/everything"
        params = {
            "apiKey": api_key,
            "sources": "reuters",
            "q": keywords,
            "from": start_date.strftime("%Y-%m-%d"),
            "to": end_date.strftime("%Y-%m-%d"),
            "language": "en",
            "sortBy": "publishedAt",
            "pageSize": 10
        }
        
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        
        data = response.json()
        articles = data.get("articles", [])
        
        if not articles:
            logger.warning(f"⚠️ [路透社新闻] 未找到相关新闻")
            return f"## 路透社新闻 (关键词: {keywords})\n\n暂无相关新闻。"
        
        # 3. 格式化为Markdown
        result = _format_news_to_markdown(articles, "Reuters", keywords)
        
        logger.info(f"✅ [路透社新闻] 获取成功: {len(articles)} 条")
        return result
        
    except Exception as e:
        logger.error(f"❌ [路透社新闻] 获取失败: {e}")
        # 直接调用实现函数而不是工具对象
        return _fetch_google_news_impl(keywords, lookback_days)


def _fetch_google_news_impl(keywords: str, lookback_days: int = 7) -> str:
    """
    内部实现：获取Google News新闻（免费降级方案）
    
    使用Google News RSS Feed
    
    Args:
        keywords: 搜索关键词
        lookback_days: 回溯天数（参考值，Google News可能不严格遵守）
        
    Returns:
        Markdown格式的新闻摘要
    """
    try:
        logger.info(f"🌍 [Google News] 开始获取，关键词: {keywords}")
        
        from GoogleNews import GoogleNews
        
        # 配置GoogleNews
        googlenews = GoogleNews(lang='en', period=f'{lookback_days}d')
        googlenews.search(keywords)
        results = googlenews.results()
        
        if not results:
            logger.warning(f"⚠️ [Google News] 未找到相关新闻")
            return f"## Google News (关键词: {keywords})\n\n暂无相关新闻。"
        
        # 格式化为Markdown
        output = f"## Google News 新闻摘要 (关键词: {keywords})\n\n"
        
        for idx, article in enumerate(results[:10], 1):
            title = article.get('title', '无标题')
            date = article.get('date', article.get('datetime', ''))
            media = article.get('media', article.get('source', ''))
            link = article.get('link', '')
            desc = article.get('desc', article.get('description', ''))
            
            output += f"### {idx}. {title}\n"
            output += f"**发布时间**: {date}\n"
            if media:
                output += f"**来源**: {media}\n"
            if desc:
                output += f"**摘要**: {desc}\n"
            if link:
                output += f"**链接**: {link}\n"
            output += "\n"
        
        logger.info(f"✅ [Google News] 获取成功: {len(results)} 条")
        return output
        
    except ImportError:
        logger.error("❌ [Google News] GoogleNews库未安装，请运行: pip install GoogleNews")
        return "Google News获取失败: GoogleNews库未安装"
    except Exception as e:
        logger.error(f"❌ [Google News] 获取失败: {e}")
        return f"Google News获取失败: {str(e)}"


@tool
def fetch_google_news(
    keywords: Annotated[str, "搜索关键词"],
    lookback_days: Annotated[int, "回溯天数，默认7天"] = 7
) -> str:
    """
    获取Google News新闻（免费降级方案）
    
    使用Google News RSS Feed
    
    Args:
        keywords: 搜索关键词
        lookback_days: 回溯天数（参考值，Google News可能不严格遵守）
        
    Returns:
        Markdown格式的新闻摘要
    """
    return _fetch_google_news_impl(keywords, lookback_days)


def _format_news_to_markdown(articles: list, source: str, keywords: str) -> str:
    """
    格式化新闻为Markdown
    
    Args:
        articles: 新闻列表
        source: 新闻源名称
        keywords: 搜索关键词
        
    Returns:
        Markdown格式的新闻摘要
    """
    if not articles:
        return f"## {source} (关键词: {keywords})\n\n暂无相关新闻"
    
    md = f"## {source} 新闻摘要 (关键词: {keywords})\n\n"
    
    for i, article in enumerate(articles[:10], 1):
        title = article.get('title', '无标题')
        published = article.get('publishedAt', article.get('published', ''))
        description = article.get('description', article.get('summary', ''))
        url = article.get('url', '')
        
        md += f"### {i}. {title}\n"
        md += f"**发布时间**: {published}\n"
        if description:
            md += f"**摘要**: {description}\n"
        if url:
            md += f"**链接**: {url}\n"
        md += "\n"
    
    return md


@tool
def fetch_cn_international_news(
    keywords: Annotated[str, "搜索关键词"] = "",
    lookback_days: Annotated[int, "回溯天数，默认7天"] = 7
) -> str:
    """
    获取国际新闻（国内源）
    
    使用AKShare获取东方财富美股/全球新闻
    作为网络受限环境下的替代方案
    
    Args:
        keywords: 搜索关键词（可选）
        lookback_days: 回溯天数
        
    Returns:
        Markdown格式的新闻摘要
    """
    try:
        logger.info(f"🌍 [国际新闻(国内源)] 开始获取，关键词: {keywords}")
        
        from tradingagents.dataflows.index_data import IndexDataProvider
        
        provider = IndexDataProvider()
        news_list = provider.get_international_news(keywords, lookback_days)
        
        if not news_list:
            return f"## 国际新闻 (国内源, 关键词: {keywords})\n\n暂无相关新闻"
            
        md = f"## 国际新闻摘要 (国内源, 关键词: {keywords})\n\n"
        
        for i, news in enumerate(news_list[:15], 1):
            title = news.get('title', '无标题')
            date = news.get('date', '')
            source = news.get('source', '')
            content = news.get('content', '')
            url = news.get('url', '')
            
            md += f"### {i}. {title}\n"
            md += f"**发布时间**: {date}\n"
            md += f"**来源**: {source}\n"
            if content and len(content) > 10:
                # 截取前100个字符
                md += f"**摘要**: {content[:100]}...\n"
            if url:
                md += f"**链接**: {url}\n"
            md += "\n"
            
        logger.info(f"✅ [国际新闻(国内源)] 获取成功: {len(news_list)} 条")
        return md
        
    except Exception as e:
        logger.error(f"❌ [国际新闻(国内源)] 获取失败: {e}")
        return f"国际新闻(国内源)获取失败: {str(e)}"


# 工具列表导出
INTERNATIONAL_NEWS_TOOLS = [
    fetch_bloomberg_news,
    fetch_reuters_news,
    fetch_google_news,
    fetch_cn_international_news
]
