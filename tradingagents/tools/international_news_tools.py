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
            return _fetch_cn_news_fallback(keywords, lookback_days)
        
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
        return _fetch_cn_news_fallback(keywords, lookback_days)
    except Exception as e:
        logger.error(f"❌ [Google News] 获取失败: {e}")
        return _fetch_cn_news_fallback(keywords, lookback_days)


def _fetch_cn_news_fallback(keywords: str, lookback_days: int) -> str:
    """
    降级方案：使用国内源获取国际新闻
    
    Args:
        keywords: 搜索关键词
        lookback_days: 回溯天数
        
    Returns:
        Markdown格式的新闻摘要
    """
    logger.info(f"⚠️ [国际新闻] Google News不可用，降级使用国内源 (AKShare/金十数据)...")
    try:
        from tradingagents.dataflows.index_data import get_index_data_provider
        
        # 获取全局Provider实例
        provider = get_index_data_provider()
        
        # 尝试调用同步方法 (HybridIndexDataProvider已实现同步包装器)
        if hasattr(provider, 'get_international_news'):
            # 自动检测英文关键词并处理
            search_keywords = keywords
            if keywords and all(ord(c) < 128 for c in keywords):
                logger.info(f"⚠️ [国际新闻] 检测到英文关键词 '{keywords}'，降级到国内源时将获取全量新闻以提高命中率")
                search_keywords = ""
                
            news_list = provider.get_international_news(search_keywords, lookback_days)
            
            if not news_list:
                return f"## 国际新闻 (国内源, 关键词: {keywords})\n\n暂无相关新闻 (数据源可能为空或关键词未匹配)。"
                
            md = f"## 国际新闻摘要 (国内源, 关键词: {keywords})\n\n"
            
            for i, news in enumerate(news_list[:10], 1):
                title = news.get('title', '无标题')
                date = news.get('date', '')
                source = news.get('source', '')
                content = news.get('content', '')
                
                md += f"### {i}. {title}\n"
                md += f"**发布时间**: {date}\n"
                md += f"**来源**: {source}\n"
                if content and len(content) > 10:
                    md += f"**摘要**: {content[:100]}...\n"
                md += "\n"
                
            logger.info(f"✅ [国际新闻] 国内源获取成功: {len(news_list)} 条")
            return md
            
        else:
            return f"国际新闻获取失败: Google News不可用且国内源未实现get_international_news"
            
    except Exception as e:
        logger.error(f"❌ [国际新闻] 国内源降级失败: {e}")
        return f"国际新闻获取失败: Google News不可用且国内源报错 ({str(e)})"


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
async def fetch_cn_international_news(
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
        
        from tradingagents.dataflows.hybrid_provider import HybridIndexDataProvider
        
        provider = HybridIndexDataProvider()
        
        if hasattr(provider, 'get_international_news_async'):
            news_list = await provider.get_international_news_async(keywords, lookback_days)
        else:
            # Fallback (should not happen if hybrid_provider updated)
            loop = asyncio.get_running_loop()
            news_list = await loop.run_in_executor(None, getattr(provider, 'get_international_news', lambda x,y: []), keywords, lookback_days)
        
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


import asyncio
from concurrent.futures import ThreadPoolExecutor

@tool
async def fetch_aggregated_news(
    keywords: Annotated[str, "搜索关键词，如'China economic stimulus'"],
    lookback_days: Annotated[int, "回溯天数，默认3天"] = 3
) -> str:
    """
    聚合获取多源新闻（国际+国内）
    
    并行调用以下数据源，确保至少有数据返回：
    1. 彭博社 (Bloomberg via NewsAPI)
    2. 路透社 (Reuters via NewsAPI)
    3. Google News
    4. 国内国际新闻源 (AKShare/金十数据)
    5. 国内政策新闻 (Policy News)
    
    Args:
        keywords: 搜索关键词
        lookback_days: 回溯天数
        
    Returns:
        Markdown格式的聚合新闻报告
    """
    logger.info(f"🌍 [聚合新闻工具] 开始并行获取多源新闻, 关键词: {keywords}")
    
    # 定义各个子任务
    
    # 1. Bloomberg (Sync -> Thread)
    async def task_bloomberg():
        try:
            # 检查API Key，如果没有则直接返回空，避免降级逻辑重复执行Google News
            if not os.getenv("NEWSAPI_KEY"):
                return ""
            
            # 使用 run_in_executor 执行同步的 fetch_bloomberg_news
            # 注意：fetch_bloomberg_news 是 Tool 对象，我们需要调用其 run 或 invoke，或者提取逻辑
            # 为了简单，我们直接调用 tool.invoke，但要小心它的降级逻辑
            # 更好的方式是：在 task 中直接使用 requests 调用，或者复用 _fetch_newsapi_impl (如果提取的话)
            # 由于未提取，我们直接调用 tool，但如果不配置 Key，tool 会降级调用 Google。
            # 这会导致 Google 被调用两次。
            # 因此，我们在上面加了 Key 检查。
            
            # 调用 Tool 对象需要传入字典
            return await asyncio.to_thread(fetch_bloomberg_news.invoke, {"keywords": keywords, "lookback_days": lookback_days})
        except Exception as e:
            logger.warning(f"⚠️ [聚合新闻] Bloomberg任务失败: {e}")
            return ""

    # 2. Reuters (Sync -> Thread)
    async def task_reuters():
        try:
            if not os.getenv("NEWSAPI_KEY"):
                return ""
            return await asyncio.to_thread(fetch_reuters_news.invoke, {"keywords": keywords, "lookback_days": lookback_days})
        except Exception as e:
            logger.warning(f"⚠️ [聚合新闻] Reuters任务失败: {e}")
            return ""

    # 3. Google News (Sync -> Thread)
    async def task_google():
        try:
            # 直接调用内部实现，避免 Tool 包装带来的额外开销
            return await asyncio.to_thread(_fetch_google_news_impl, keywords, lookback_days)
        except Exception as e:
            logger.warning(f"⚠️ [聚合新闻] Google News任务失败: {e}")
            return ""

    # 4. 国内国际新闻源 (Async)
    async def task_cn_intl():
        try:
            return await fetch_cn_international_news.ainvoke({"keywords": keywords, "lookback_days": lookback_days})
        except Exception as e:
            logger.warning(f"⚠️ [聚合新闻] 国内国际新闻任务失败: {e}")
            return ""
            
    # 5. 国内政策新闻 (Sync -> Thread)
    async def task_policy():
        try:
            from tradingagents.tools.index_tools import fetch_policy_news
            return await asyncio.to_thread(fetch_policy_news.invoke, {"lookback_days": lookback_days})
        except Exception as e:
            logger.warning(f"⚠️ [聚合新闻] 政策新闻任务失败: {e}")
            return ""

    # 并行执行所有任务，设置总体超时
    # 注意：fetch_cn_international_news 内部可能有降级逻辑
    
    tasks = [
        task_bloomberg(),
        task_reuters(),
        task_google(),
        task_cn_intl(),
        task_policy()
    ]
    
    # 使用 gather 并发执行
    results = await asyncio.gather(*tasks, return_exceptions=True)
    
    # 处理结果
    final_output = []
    sources_found = 0
    
    source_names = ["Bloomberg", "Reuters", "Google News", "Domestic Intl News", "Policy News"]
    
    for i, res in enumerate(results):
        source_name = source_names[i]
        if isinstance(res, Exception):
            logger.error(f"❌ [聚合新闻] {source_name} 异常: {res}")
        elif res and isinstance(res, str) and "暂无相关新闻" not in res and "获取失败" not in res:
            final_output.append(res)
            sources_found += 1
        else:
            logger.debug(f"ℹ️ [聚合新闻] {source_name} 无有效数据")
            
    if not final_output:
        logger.warning("⚠️ [聚合新闻] 所有源均未返回有效数据")
        # 尝试最后的兜底：强制调用国内全量新闻
        try:
            fallback = await fetch_cn_international_news.ainvoke({"keywords": "", "lookback_days": lookback_days})
            if fallback and "暂无相关新闻" not in fallback:
                 return f"## 聚合新闻报告 (全源失败，使用兜底)\n\n{fallback}"
        except:
            pass
        return f"## 聚合新闻报告\n\n未找到关于 '{keywords}' 的相关新闻 (尝试了Bloomberg, Reuters, Google, 国内源, 政策源)。"
        
    logger.info(f"✅ [聚合新闻工具] 成功获取 {sources_found} 个源的数据")
    return "## 聚合新闻报告\n\n" + "\n\n---\n\n".join(final_output)

# 工具列表导出
INTERNATIONAL_NEWS_TOOLS = [
    fetch_aggregated_news, # 首选聚合工具
    fetch_bloomberg_news,
    fetch_reuters_news,
    fetch_google_news,
    fetch_cn_international_news
]
