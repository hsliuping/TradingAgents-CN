"""
统一股票新闻工具

自动识别股票类型（A股、港股、美股）并调用相应的新闻数据源

数据源优先级：
1. MongoDB 数据库（包括 local、akshare、tushare 等数据源）
2. 外部 API（AKShare、Google News、Finnhub）
"""

import logging
from typing import Annotated, List, Dict, Any
from langchain_core.tools import tool
from datetime import datetime, timedelta

from core.tools.base import register_tool

logger = logging.getLogger(__name__)


def _query_news_from_database(symbol: str, start_date: datetime, end_date: datetime, limit: int = 20) -> List[Dict[str, Any]]:
    """
    从 MongoDB 数据库查询新闻（按数据源优先级）

    Args:
        symbol: 股票代码（6位代码，如 000001）
        start_date: 开始日期
        end_date: 结束日期
        limit: 返回数量限制

    Returns:
        新闻数据列表，如果没有数据则返回空列表
    """
    try:
        from app.core.database import get_mongo_db_sync
        from app.core.data_source_priority import get_enabled_data_sources_sync

        db = get_mongo_db_sync()
        collection = db.stock_news

        # 获取数据源优先级
        enabled_sources = get_enabled_data_sources_sync(market_category="a_shares")
        logger.info(f"📊 [新闻数据库查询] 数据源优先级: {enabled_sources}")

        # 按优先级尝试每个数据源
        for data_source in enabled_sources:
            query = {
                "symbol": symbol,
                "data_source": data_source,
                "publish_time": {
                    "$gte": start_date,
                    "$lte": end_date
                }
            }

            cursor = collection.find(query).sort("publish_time", -1).limit(limit)
            news_list = list(cursor)

            if news_list:
                logger.info(f"✅ [新闻数据库查询] 从 {data_source} 数据源获取到 {len(news_list)} 条新闻")
                return news_list
            else:
                logger.debug(f"⚠️ [新闻数据库查询] {data_source} 数据源没有数据，尝试下一个数据源")

        # 所有数据源都没有数据
        logger.info(f"⚠️ [新闻数据库查询] 所有数据源都没有 {symbol} 的新闻数据")
        return []

    except Exception as e:
        logger.error(f"❌ [新闻数据库查询] 查询失败: {e}")
        return []


def _format_database_news(news_list: List[Dict[str, Any]], data_source_name: str = "数据库") -> str:
    """
    格式化数据库新闻为 Markdown 格式

    Args:
        news_list: 新闻数据列表
        data_source_name: 数据源名称

    Returns:
        格式化的 Markdown 文本
    """
    if not news_list:
        return ""

    news_items = []
    for news in news_list:
        title = news.get('title', '无标题')
        publish_time = news.get('publish_time', '')
        url = news.get('url', '')
        source = news.get('source', '')

        # 格式化时间
        if isinstance(publish_time, datetime):
            time_str = publish_time.strftime('%Y-%m-%d %H:%M')
        else:
            time_str = str(publish_time)

        # 构建新闻条目
        if url:
            news_item = f"- **{title}** [{time_str}]({url})"
        else:
            news_item = f"- **{title}** [{time_str}]"

        if source:
            news_item += f" - 来源: {source}"

        news_items.append(news_item)

    news_text = "\n".join(news_items)
    return f"## {data_source_name}\n{news_text}"


@tool
@register_tool(
    tool_id="get_stock_news_unified",
    name="统一股票新闻",
    description="获取股票相关新闻，支持A股、港股、美股",
    category="news",
    is_online=True,
    auto_register=True
)
def get_stock_news_unified(
    ticker: Annotated[str, "股票代码（支持A股、港股、美股）"],
    curr_date: Annotated[str, "当前日期，格式：YYYY-MM-DD"]
) -> str:
    """
    统一的股票新闻工具
    自动识别股票类型（A股、港股、美股）并调用相应的新闻数据源

    Args:
        ticker: 股票代码（如：000001、0700.HK、AAPL）
        curr_date: 当前日期（格式：YYYY-MM-DD）

    Returns:
        str: 新闻分析报告
    """
    logger.info(f"📰 [统一新闻工具] 分析股票: {ticker}")

    try:
        from tradingagents.utils.stock_utils import StockUtils

        # 自动识别股票类型
        market_info = StockUtils.get_market_info(ticker)
        is_china = market_info['is_china']
        is_hk = market_info['is_hk']
        is_us = market_info['is_us']

        logger.info(f"📰 [统一新闻工具] 股票类型: {market_info['market_name']}")

        # 计算新闻查询的日期范围
        # 处理可能包含时间的日期字符串（如 "2026-01-14 00:00:00"）
        curr_date_clean = curr_date.split()[0] if ' ' in curr_date else curr_date
        end_date = datetime.strptime(curr_date_clean, '%Y-%m-%d')
        start_date = end_date - timedelta(days=7)
        start_date_str = start_date.strftime('%Y-%m-%d')

        result_data = []

        if is_china:
            # 中国A股：优先从数据库查询，降级到AKShare东方财富新闻
            logger.info(f"🇨🇳 [统一新闻工具] 处理A股新闻...")

            clean_ticker = ticker.replace('.SH', '').replace('.SZ', '').replace('.SS', '')\
                           .replace('.XSHE', '').replace('.XSHG', '')

            # 1. 优先从数据库查询（按数据源优先级：local > akshare > tushare）
            try:
                logger.info(f"📊 [统一新闻工具] 优先从数据库查询新闻...")
                db_news = _query_news_from_database(
                    symbol=clean_ticker,
                    start_date=start_date,
                    end_date=end_date,
                    limit=20
                )

                if db_news:
                    # 获取数据源名称
                    data_source = db_news[0].get('data_source', 'unknown')
                    source_name_map = {
                        'local': '本地数据',
                        'akshare': '东方财富（数据库缓存）',
                        'tushare': 'Tushare（数据库缓存）'
                    }
                    source_name = source_name_map.get(data_source, f'{data_source}（数据库缓存）')

                    formatted_news = _format_database_news(db_news, source_name)
                    result_data.append(formatted_news)
                    logger.info(f"✅ 从数据库获取到 {len(db_news)} 条新闻（数据源: {data_source}）")
                else:
                    logger.info(f"⚠️ 数据库中没有新闻，降级到外部API...")

                    # 2. 降级到AKShare东方财富新闻（实时获取）
                    try:
                        from tradingagents.dataflows.providers.china.akshare import AKShareProvider
                        provider = AKShareProvider()
                        news_df = provider.get_stock_news_sync(symbol=clean_ticker)

                        if news_df is not None and not news_df.empty:
                            em_news_items = []
                            for _, row in news_df.iterrows():
                                news_title = row.get('新闻标题', '') or row.get('标题', '')
                                news_time = row.get('发布时间', '') or row.get('时间', '')
                                news_url = row.get('新闻链接', '') or row.get('链接', '')
                                news_item = f"- **{news_title}** [{news_time}]({news_url})"
                                em_news_items.append(news_item)

                            if em_news_items:
                                em_news_text = "\n".join(em_news_items)
                                result_data.append(f"## 东方财富新闻（实时获取）\n{em_news_text}")
                                logger.info(f"✅ 实时获取{len(em_news_items)}条东方财富新闻")
                    except Exception as em_e:
                        logger.error(f"❌ 东方财富新闻获取失败: {em_e}")
                        result_data.append(f"## 东方财富新闻\n获取失败: {em_e}")

            except Exception as db_e:
                logger.error(f"❌ 数据库查询失败: {db_e}，降级到外部API")

                # 降级到AKShare东方财富新闻
                try:
                    from tradingagents.dataflows.providers.china.akshare import AKShareProvider
                    provider = AKShareProvider()
                    news_df = provider.get_stock_news_sync(symbol=clean_ticker)

                    if news_df is not None and not news_df.empty:
                        em_news_items = []
                        for _, row in news_df.iterrows():
                            news_title = row.get('新闻标题', '') or row.get('标题', '')
                            news_time = row.get('发布时间', '') or row.get('时间', '')
                            news_url = row.get('新闻链接', '') or row.get('链接', '')
                            news_item = f"- **{news_title}** [{news_time}]({news_url})"
                            em_news_items.append(news_item)

                        if em_news_items:
                            em_news_text = "\n".join(em_news_items)
                            result_data.append(f"## 东方财富新闻（实时获取）\n{em_news_text}")
                            logger.info(f"✅ 实时获取{len(em_news_items)}条东方财富新闻")
                except Exception as em_e:
                    logger.error(f"❌ 东方财富新闻获取失败: {em_e}")
                    result_data.append(f"## 东方财富新闻\n获取失败: {em_e}")

        elif is_hk:
            # 港股：使用Google新闻
            logger.info(f"🇭🇰 [统一新闻工具] 处理港股新闻...")

            try:
                search_query = f"{ticker} 港股"

                from tradingagents.dataflows.interface import get_google_news
                from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeoutError
                
                # 🔥 使用 ThreadPoolExecutor 实现超时控制，避免 Google 新闻获取阻塞整个流程
                # 设置 30 秒超时，如果超时则跳过 Google 新闻，不阻塞其他节点的执行
                with ThreadPoolExecutor(max_workers=1) as executor:
                    future = executor.submit(get_google_news, search_query, curr_date_clean)
                    try:
                        news_data = future.result(timeout=30.0)  # 最多等待30秒
                        if news_data:
                            result_data.append(f"## Google新闻\n{news_data}")
                            logger.info(f"✅ 成功获取Google新闻")
                        else:
                            logger.warning(f"⚠️ Google新闻返回空结果")
                    except FutureTimeoutError:
                        logger.warning(f"⚠️ Google新闻获取超时（30秒），跳过Google新闻以避免阻塞流程")
                        # 不添加到结果中，让流程继续
                    except Exception as e:
                        logger.error(f"❌ Google新闻获取失败: {e}")
                        # 不添加到结果中，避免显示错误信息，让流程继续
                        
            except Exception as google_e:
                logger.error(f"❌ Google新闻获取异常: {google_e}")
                # 不添加到结果中，避免显示错误信息，让流程继续

        elif is_us:
            # 美股：使用Finnhub新闻和Google新闻
            logger.info(f"🇺🇸 [统一新闻工具] 处理美股新闻...")

            # 1. 获取Finnhub新闻
            try:
                from tradingagents.dataflows.interface import get_finnhub_news
                news_data = get_finnhub_news(ticker, start_date_str, curr_date)
                if news_data:
                    result_data.append(f"## 美股新闻\n{news_data}")
            except Exception as e:
                logger.error(f"❌ Finnhub新闻获取失败: {e}")
                result_data.append(f"## 美股新闻\n获取失败: {e}")

            # 2. 获取Google新闻作为补充（带超时保护，避免阻塞整个流程）
            try:
                search_query = f"{ticker} stock news"

                from tradingagents.dataflows.interface import get_google_news
                from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeoutError
                
                # 🔥 使用 ThreadPoolExecutor 实现超时控制，避免 Google 新闻获取阻塞整个流程
                # 设置 30 秒超时，如果超时则跳过 Google 新闻，不阻塞其他节点的执行
                with ThreadPoolExecutor(max_workers=1) as executor:
                    future = executor.submit(get_google_news, search_query, curr_date_clean)
                    try:
                        news_data = future.result(timeout=30.0)  # 最多等待30秒
                        if news_data:
                            result_data.append(f"## Google新闻\n{news_data}")
                            logger.info(f"✅ 成功获取Google新闻")
                        else:
                            logger.warning(f"⚠️ Google新闻返回空结果")
                    except FutureTimeoutError:
                        logger.warning(f"⚠️ Google新闻获取超时（30秒），跳过Google新闻以避免阻塞流程")
                        # 不添加到结果中，让流程继续
                    except Exception as e:
                        logger.error(f"❌ Google新闻获取失败: {e}")
                        # 不添加到结果中，避免显示错误信息，让流程继续
                        
            except Exception as google_e:
                logger.error(f"❌ Google新闻获取异常: {google_e}")
                # 不添加到结果中，避免显示错误信息，让流程继续

        # 组合所有数据
        combined_result = f"""# {ticker} 新闻分析

**股票类型**: {market_info['market_name']}
**分析日期**: {curr_date}
**新闻时间范围**: {start_date_str} 至 {curr_date}

{chr(10).join(result_data)}

---
*数据来源: 优先使用数据库缓存（按数据源优先级：local > akshare > tushare），降级到外部API*
"""

        logger.info(f"📰 [统一新闻工具] 数据获取完成，总长度: {len(combined_result)}")
        return combined_result

    except Exception as e:
        error_msg = f"统一新闻工具执行失败: {str(e)}"
        logger.error(f"❌ [统一新闻工具] {error_msg}")
        return error_msg

