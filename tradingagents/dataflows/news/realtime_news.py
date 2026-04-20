#!/usr/bin/env python3
"""
实时新闻数据获取工具
解决新闻滞后性问题
"""

import requests
import json
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from typing import List, Dict, Optional
import time
import os
from dataclasses import dataclass

# 导入日志模块
from tradingagents.config.runtime_settings import get_timezone_name

from tradingagents.utils.logging_manager import get_logger
logger = get_logger('agents')



@dataclass
class NewsItem:
    """新闻项目数据结构"""
    title: str
    content: str
    source: str
    publish_time: datetime
    url: str
    urgency: str  # high, medium, low
    relevance_score: float


class RealtimeNewsAggregator:
    """实时新闻聚合器"""

    def __init__(self):
        self.headers = {
            'User-Agent': 'TradingAgents-CN/1.0'
        }

        # API密钥配置
        self.finnhub_key = os.getenv('FINNHUB_API_KEY')
        self.alpha_vantage_key = os.getenv('ALPHA_VANTAGE_API_KEY')
        self.newsapi_key = os.getenv('NEWSAPI_KEY')

    def get_realtime_stock_news(self, ticker: str, hours_back: int = 6, max_news: int = 10) -> List[NewsItem]:
        """
        获取实时股票新闻
        优先级：专业API > 新闻API > 搜索引擎

        Args:
            ticker: 股票代码
            hours_back: 回溯小时数
            max_news: 最大新闻数量，默认10条
        """
        logger.info(f"[新闻聚合器] 开始获取 {ticker} 的实时新闻，回溯时间: {hours_back}小时")
        start_time = datetime.now(ZoneInfo(get_timezone_name()))
        all_news = []

        # 1. FinnHub实时新闻 (最高优先级)
        logger.info(f"[新闻聚合器] 尝试从 FinnHub 获取 {ticker} 的新闻")
        finnhub_start = datetime.now(ZoneInfo(get_timezone_name()))
        finnhub_news = self._get_finnhub_realtime_news(ticker, hours_back)
        finnhub_time = (datetime.now(ZoneInfo(get_timezone_name())) - finnhub_start).total_seconds()

        if finnhub_news:
            logger.info(f"[新闻聚合器] 成功从 FinnHub 获取 {len(finnhub_news)} 条新闻，耗时: {finnhub_time:.2f}秒")
        else:
            logger.info(f"[新闻聚合器] FinnHub 未返回新闻，耗时: {finnhub_time:.2f}秒")

        all_news.extend(finnhub_news)

        # 2. Alpha Vantage新闻
        logger.info(f"[新闻聚合器] 尝试从 Alpha Vantage 获取 {ticker} 的新闻")
        av_start = datetime.now(ZoneInfo(get_timezone_name()))
        av_news = self._get_alpha_vantage_news(ticker, hours_back)
        av_time = (datetime.now(ZoneInfo(get_timezone_name())) - av_start).total_seconds()

        if av_news:
            logger.info(f"[新闻聚合器] 成功从 Alpha Vantage 获取 {len(av_news)} 条新闻，耗时: {av_time:.2f}秒")
        else:
            logger.info(f"[新闻聚合器] Alpha Vantage 未返回新闻，耗时: {av_time:.2f}秒")

        all_news.extend(av_news)

        # 3. NewsAPI (如果配置了)
        if self.newsapi_key:
            logger.info(f"[新闻聚合器] 尝试从 NewsAPI 获取 {ticker} 的新闻")
            newsapi_start = datetime.now(ZoneInfo(get_timezone_name()))
            newsapi_news = self._get_newsapi_news(ticker, hours_back)
            newsapi_time = (datetime.now(ZoneInfo(get_timezone_name())) - newsapi_start).total_seconds()

            if newsapi_news:
                logger.info(f"[新闻聚合器] 成功从 NewsAPI 获取 {len(newsapi_news)} 条新闻，耗时: {newsapi_time:.2f}秒")
            else:
                logger.info(f"[新闻聚合器] NewsAPI 未返回新闻，耗时: {newsapi_time:.2f}秒")

            all_news.extend(newsapi_news)
        else:
            logger.info(f"[新闻聚合器] NewsAPI 密钥未配置，跳过此新闻源")

        # 4. 中文财经新闻源
        logger.info(f"[新闻聚合器] 尝试获取 {ticker} 的中文财经新闻")
        chinese_start = datetime.now(ZoneInfo(get_timezone_name()))
        chinese_news = self._get_chinese_finance_news(ticker, hours_back)
        chinese_time = (datetime.now(ZoneInfo(get_timezone_name())) - chinese_start).total_seconds()

        if chinese_news:
            logger.info(f"[新闻聚合器] 成功获取 {len(chinese_news)} 条中文财经新闻，耗时: {chinese_time:.2f}秒")
        else:
            logger.info(f"[新闻聚合器] 未获取到中文财经新闻，耗时: {chinese_time:.2f}秒")

        all_news.extend(chinese_news)

        # 去重和排序
        logger.info(f"[新闻聚合器] 开始对 {len(all_news)} 条新闻进行去重和排序")
        dedup_start = datetime.now(ZoneInfo(get_timezone_name()))
        unique_news = self._deduplicate_news(all_news)
        sorted_news = sorted(unique_news, key=lambda x: x.publish_time, reverse=True)
        dedup_time = (datetime.now(ZoneInfo(get_timezone_name())) - dedup_start).total_seconds()

        # 记录去重结果
        removed_count = len(all_news) - len(unique_news)
        logger.info(f"[新闻聚合器] 新闻去重完成，移除了 {removed_count} 条重复新闻，剩余 {len(sorted_news)} 条，耗时: {dedup_time:.2f}秒")

        # 记录总体情况
        total_time = (datetime.now(ZoneInfo(get_timezone_name())) - start_time).total_seconds()
        logger.info(f"[新闻聚合器] {ticker} 的新闻聚合完成，总共获取 {len(sorted_news)} 条新闻，总耗时: {total_time:.2f}秒")

        # 限制新闻数量为最新的max_news条
        if len(sorted_news) > max_news:
            original_count = len(sorted_news)
            sorted_news = sorted_news[:max_news]
            logger.info(f"[新闻聚合器] 📰 新闻数量限制: 从{original_count}条限制为{max_news}条最新新闻")

        # 记录一些新闻标题示例
        if sorted_news:
            sample_titles = [item.title for item in sorted_news[:3]]
            logger.info(f"[新闻聚合器] 新闻标题示例: {', '.join(sample_titles)}")

        return sorted_news

    def _get_finnhub_realtime_news(self, ticker: str, hours_back: int) -> List[NewsItem]:
        """获取FinnHub实时新闻"""
        if not self.finnhub_key:
            return []

        try:
            # 计算时间范围
            end_time = datetime.now(ZoneInfo(get_timezone_name()))
            start_time = end_time - timedelta(hours=hours_back)

            # FinnHub API调用
            url = "https://finnhub.io/api/v1/company-news"
            params = {
                'symbol': ticker,
                'from': start_time.strftime('%Y-%m-%d'),
                'to': end_time.strftime('%Y-%m-%d'),
                'token': self.finnhub_key
            }

            response = requests.get(url, params=params, headers=self.headers)
            response.raise_for_status()

            news_data = response.json()
            news_items = []

            for item in news_data:
                # 检查新闻时效性
                publish_time = datetime.fromtimestamp(item.get('datetime', 0), tz=ZoneInfo(get_timezone_name()))
                if publish_time < start_time:
                    continue

                # 评估紧急程度
                urgency = self._assess_news_urgency(item.get('headline', ''), item.get('summary', ''))

                news_items.append(NewsItem(
                    title=item.get('headline', ''),
                    content=item.get('summary', ''),
                    source=item.get('source', 'FinnHub'),
                    publish_time=publish_time,
                    url=item.get('url', ''),
                    urgency=urgency,
                    relevance_score=self._calculate_relevance(item.get('headline', ''), ticker)
                ))

            return news_items

        except Exception as e:
            logger.error(f"FinnHub新闻获取失败: {e}")
            return []

    def _get_alpha_vantage_news(self, ticker: str, hours_back: int) -> List[NewsItem]:
        """获取Alpha Vantage新闻"""
        if not self.alpha_vantage_key:
            return []

        try:
            url = "https://www.alphavantage.co/query"
            params = {
                'function': 'NEWS_SENTIMENT',
                'tickers': ticker,
                'apikey': self.alpha_vantage_key,
                'limit': 50
            }

            response = requests.get(url, params=params, headers=self.headers)
            response.raise_for_status()

            data = response.json()
            news_items = []

            if 'feed' in data:
                for item in data['feed']:
                    # 解析时间
                    time_str = item.get('time_published', '')
                    try:
                        publish_time = datetime.strptime(time_str, '%Y%m%dT%H%M%S').replace(tzinfo=ZoneInfo(get_timezone_name()))
                    except:
                        continue

                    # 检查时效性
                    if publish_time < datetime.now(ZoneInfo(get_timezone_name())) - timedelta(hours=hours_back):
                        continue

                    urgency = self._assess_news_urgency(item.get('title', ''), item.get('summary', ''))

                    news_items.append(NewsItem(
                        title=item.get('title', ''),
                        content=item.get('summary', ''),
                        source=item.get('source', 'Alpha Vantage'),
                        publish_time=publish_time,
                        url=item.get('url', ''),
                        urgency=urgency,
                        relevance_score=self._calculate_relevance(item.get('title', ''), ticker)
                    ))

            return news_items

        except Exception as e:
            logger.error(f"Alpha Vantage新闻获取失败: {e}")
            return []

    def _get_newsapi_news(self, ticker: str, hours_back: int) -> List[NewsItem]:
        """获取NewsAPI新闻"""
        try:
            # 构建搜索查询
            company_names = {
                'AAPL': 'Apple',
                'TSLA': 'Tesla',
                'NVDA': 'NVIDIA',
                'MSFT': 'Microsoft',
                'GOOGL': 'Google'
            }

            query = f"{ticker} OR {company_names.get(ticker, ticker)}"

            url = "https://newsapi.org/v2/everything"
            params = {
                'q': query,
                'language': 'en',
                'sortBy': 'publishedAt',
                'from': (datetime.now(ZoneInfo(get_timezone_name())) - timedelta(hours=hours_back)).isoformat(),
                'apiKey': self.newsapi_key
            }

            response = requests.get(url, params=params, headers=self.headers)
            response.raise_for_status()

            data = response.json()
            news_items = []

            for item in data.get('articles', []):
                # 解析时间
                time_str = item.get('publishedAt', '')
                try:
                    publish_time = datetime.fromisoformat(time_str.replace('Z', '+00:00'))
                except:
                    continue

                urgency = self._assess_news_urgency(item.get('title', ''), item.get('description', ''))

                news_items.append(NewsItem(
                    title=item.get('title', ''),
                    content=item.get('description', ''),
                    source=item.get('source', {}).get('name', 'NewsAPI'),
                    publish_time=publish_time,
                    url=item.get('url', ''),
                    urgency=urgency,
                    relevance_score=self._calculate_relevance(item.get('title', ''), ticker)
                ))

            return news_items

        except Exception as e:
            logger.error(f"NewsAPI新闻获取失败: {e}")
            return []

    def _get_chinese_finance_news(self, ticker: str, hours_back: int) -> List[NewsItem]:
        """获取中文财经新闻"""
        # 集成中文财经新闻API：财联社、东方财富等
        logger.info(f"[中文财经新闻] 开始获取 {ticker} 的中文财经新闻，回溯时间: {hours_back}小时")
        start_time = datetime.now(ZoneInfo(get_timezone_name()))

        try:
            news_items = []

            # 1. 尝试使用AKShare获取东方财富个股新闻
            # 如果没有传入ticker（例如获取市场新闻），跳过东方财富个股新闻部分
            if ticker:
                try:
                    logger.info(f"[中文财经新闻] 尝试通过 AKShare Provider 获取新闻")
                    from tradingagents.dataflows.providers.china.akshare import AKShareProvider

                    provider = AKShareProvider()

                    # 处理股票代码格式
                    # 如果是美股代码，不使用东方财富新闻
                    if '.' in ticker and any(suffix in ticker for suffix in ['.US', '.N', '.O', '.NYSE', '.NASDAQ']):
                        logger.info(f"[中文财经新闻] 检测到美股代码 {ticker}，跳过东方财富新闻获取")
                    else:
                        # 处理A股和港股代码
                        clean_ticker = ticker.replace('.SH', '').replace('.SZ', '').replace('.SS', '')\
                                        .replace('.HK', '').replace('.XSHE', '').replace('.XSHG', '')

                        # 获取东方财富新闻
                        logger.info(f"[中文财经新闻] 开始获取 {clean_ticker} 的东方财富新闻")
                        em_start_time = datetime.now(ZoneInfo(get_timezone_name()))
                        news_df = provider.get_stock_news_sync(symbol=clean_ticker)

                        if not news_df.empty:
                            logger.info(f"[中文财经新闻] 东方财富返回 {len(news_df)} 条新闻数据，开始处理")
                            processed_count = 0
                            skipped_count = 0
                            error_count = 0

                            # 转换为NewsItem格式
                            for _, row in news_df.iterrows():
                                try:
                                    # 解析时间
                                    time_str = row.get('时间', '')
                                    if time_str:
                                        # 尝试解析时间格式，可能是'2023-01-01 12:34:56'格式
                                        try:
                                            publish_time = datetime.strptime(time_str, '%Y-%m-%d %H:%M:%S').replace(tzinfo=ZoneInfo(get_timezone_name()))
                                        except:
                                            # 尝试其他可能的格式
                                            try:
                                                publish_time = datetime.strptime(time_str, '%Y-%m-%d').replace(tzinfo=ZoneInfo(get_timezone_name()))
                                            except:
                                                logger.warning(f"[中文财经新闻] 无法解析时间格式: {time_str}，使用当前时间")
                                                publish_time = datetime.now(ZoneInfo(get_timezone_name()))
                                    else:
                                        logger.warning(f"[中文财经新闻] 新闻时间为空，使用当前时间")
                                        publish_time = datetime.now(ZoneInfo(get_timezone_name()))

                                    # 检查时效性
                                    if publish_time < datetime.now(ZoneInfo(get_timezone_name())) - timedelta(hours=hours_back):
                                        skipped_count += 1
                                        continue

                                    # 评估紧急程度
                                    title = row.get('标题', '')
                                    content = row.get('内容', '')
                                    urgency = self._assess_news_urgency(title, content)

                                    news_items.append(NewsItem(
                                        title=title,
                                        content=content,
                                        source='东方财富',
                                        publish_time=publish_time,
                                        url=row.get('链接', ''),
                                        urgency=urgency,
                                        relevance_score=self._calculate_relevance(title, ticker)
                                    ))
                                    processed_count += 1
                                except Exception as item_e:
                                    logger.error(f"[中文财经新闻] 处理东方财富新闻项目失败: {item_e}")
                                    error_count += 1
                                    continue

                            em_time = (datetime.now(ZoneInfo(get_timezone_name())) - em_start_time).total_seconds()
                            logger.info(f"[中文财经新闻] 东方财富新闻处理完成，成功: {processed_count}条，跳过: {skipped_count}条，错误: {error_count}条，耗时: {em_time:.2f}秒")
                except Exception as ak_e:
                    logger.error(f"[中文财经新闻] 获取东方财富新闻失败: {ak_e}")
            else:
                logger.info("[中文财经新闻] ticker为空（市场级新闻），跳过东方财富个股新闻，仅使用RSS等全市场来源")

            # 2. 财联社RSS (如果可用)
            logger.info(f"[中文财经新闻] 开始获取财联社RSS新闻")
            rss_start_time = datetime.now(ZoneInfo(get_timezone_name()))
            rss_sources = [
                "https://www.cls.cn/api/sw?app=CailianpressWeb&os=web&sv=7.7.5",
                # 可以添加更多RSS源
            ]

            rss_success_count = 0
            rss_error_count = 0
            total_rss_items = 0

            for rss_url in rss_sources:
                try:
                    logger.info(f"[中文财经新闻] 尝试解析RSS源: {rss_url}")
                    rss_item_start = datetime.now(ZoneInfo(get_timezone_name()))
                    items = self._parse_rss_feed(rss_url, ticker, hours_back)
                    rss_item_time = (datetime.now(ZoneInfo(get_timezone_name())) - rss_item_start).total_seconds()

                    if items:
                        logger.info(f"[中文财经新闻] 成功从RSS源获取 {len(items)} 条新闻，耗时: {rss_item_time:.2f}秒")
                        news_items.extend(items)
                        total_rss_items += len(items)
                        rss_success_count += 1
                    else:
                        logger.info(f"[中文财经新闻] RSS源未返回相关新闻，耗时: {rss_item_time:.2f}秒")
                except Exception as rss_e:
                    logger.error(f"[中文财经新闻] 解析RSS源失败: {rss_e}")
                    rss_error_count += 1
                    continue

            # 记录RSS获取总结
            rss_total_time = (datetime.now(ZoneInfo(get_timezone_name())) - rss_start_time).total_seconds()
            logger.info(f"[中文财经新闻] RSS新闻获取完成，成功源: {rss_success_count}个，失败源: {rss_error_count}个，获取新闻: {total_rss_items}条，总耗时: {rss_total_time:.2f}秒")

            # 记录中文财经新闻获取总结
            total_time = (datetime.now(ZoneInfo(get_timezone_name())) - start_time).total_seconds()
            logger.info(f"[中文财经新闻] {ticker} 的中文财经新闻获取完成，总共获取 {len(news_items)} 条新闻，总耗时: {total_time:.2f}秒")

            return news_items

        except Exception as e:
            logger.error(f"[中文财经新闻] 中文财经新闻获取失败: {e}")
            return []

    def _parse_rss_feed(self, rss_url: str, ticker: str, hours_back: int) -> List[NewsItem]:
        """解析RSS源"""
        logger.info(f"[RSS解析] 开始解析RSS源: {rss_url}，股票: {ticker}，回溯时间: {hours_back}小时")
        start_time = datetime.now(ZoneInfo(get_timezone_name()))

        try:
            # 实际实现需要使用feedparser库
            # 这里是简化实现，实际项目中应该替换为真实的RSS解析逻辑
            import feedparser

            logger.info(f"[RSS解析] 尝试获取RSS源内容")
            feed = feedparser.parse(rss_url)

            if not feed or not feed.entries:
                logger.warning(f"[RSS解析] RSS源未返回有效内容")
                return []

            logger.info(f"[RSS解析] 成功获取RSS源，包含 {len(feed.entries)} 条条目")
            news_items = []
            processed_count = 0
            skipped_count = 0

            for entry in feed.entries:
                try:
                    # 解析时间
                    if hasattr(entry, 'published_parsed') and entry.published_parsed:
                        publish_time = datetime.fromtimestamp(time.mktime(entry.published_parsed), tz=ZoneInfo(get_timezone_name()))
                    else:
                        logger.warning(f"[RSS解析] 条目缺少发布时间，使用当前时间")
                        publish_time = datetime.now(ZoneInfo(get_timezone_name()))

                    # 检查时效性
                    if publish_time < datetime.now(ZoneInfo(get_timezone_name())) - timedelta(hours=hours_back):
                        skipped_count += 1
                        continue

                    title = entry.title if hasattr(entry, 'title') else ''
                    content = entry.description if hasattr(entry, 'description') else ''

                    # 检查相关性
                    if ticker.lower() not in title.lower() and ticker.lower() not in content.lower():
                        skipped_count += 1
                        continue

                    # 评估紧急程度
                    urgency = self._assess_news_urgency(title, content)

                    news_items.append(NewsItem(
                        title=title,
                        content=content,
                        source='财联社',
                        publish_time=publish_time,
                        url=entry.link if hasattr(entry, 'link') else '',
                        urgency=urgency,
                        relevance_score=self._calculate_relevance(title, ticker)
                    ))
                    processed_count += 1
                except Exception as e:
                    logger.error(f"[RSS解析] 处理RSS条目失败: {e}")
                    continue

            total_time = (datetime.now(ZoneInfo(get_timezone_name())) - start_time).total_seconds()
            logger.info(f"[RSS解析] RSS源解析完成，成功: {processed_count}条，跳过: {skipped_count}条，耗时: {total_time:.2f}秒")
            return news_items
        except ImportError:
            logger.error(f"[RSS解析] feedparser库未安装，无法解析RSS源")
            return []
        except Exception as e:
            logger.error(f"[RSS解析] 解析RSS源失败: {e}")
            return []

    def _assess_news_urgency(self, title: str, content: str) -> str:
        """评估新闻紧急程度"""
        text = (title + ' ' + content).lower()

        # 高紧急度关键词
        high_urgency_keywords = [
            'breaking', 'urgent', 'alert', 'emergency', 'halt', 'suspend',
            '突发', '紧急', '暂停', '停牌', '重大'
        ]

        # 中等紧急度关键词
        medium_urgency_keywords = [
            'earnings', 'report', 'announce', 'launch', 'merger', 'acquisition',
            '财报', '发布', '宣布', '并购', '收购'
        ]

        # 检查高紧急度关键词
        for keyword in high_urgency_keywords:
            if keyword in text:
                logger.debug(f"[紧急度评估] 检测到高紧急度关键词 '{keyword}' 在新闻中: {title[:50]}...")
                return 'high'

        # 检查中等紧急度关键词
        for keyword in medium_urgency_keywords:
            if keyword in text:
                logger.debug(f"[紧急度评估] 检测到中等紧急度关键词 '{keyword}' 在新闻中: {title[:50]}...")
                return 'medium'

        logger.debug(f"[紧急度评估] 未检测到紧急关键词，评估为低紧急度: {title[:50]}...")
        return 'low'

    def _calculate_relevance(self, title: str, ticker: str) -> float:
        """计算新闻相关性分数"""
        text = title.lower()
        ticker_lower = ticker.lower()

        # 基础相关性 - 股票代码直接出现在标题中
        if ticker_lower in text:
            logger.debug(f"[相关性计算] 股票代码 {ticker} 直接出现在标题中，相关性评分: 1.0，标题: {title[:50]}...")
            return 1.0

        # 公司名称匹配
        company_names = {
            'aapl': ['apple', 'iphone', 'ipad', 'mac'],
            'tsla': ['tesla', 'elon musk', 'electric vehicle'],
            'nvda': ['nvidia', 'gpu', 'ai chip'],
            'msft': ['microsoft', 'windows', 'azure'],
            'googl': ['google', 'alphabet', 'search']
        }

        # 检查公司相关关键词
        if ticker_lower in company_names:
            for name in company_names[ticker_lower]:
                if name in text:
                    logger.debug(f"[相关性计算] 检测到公司相关关键词 '{name}' 在标题中，相关性评分: 0.8，标题: {title[:50]}...")
                    return 0.8

        # 提取股票代码的纯数字部分（适用于中国股票）
        pure_code = ''.join(filter(str.isdigit, ticker))
        if pure_code and pure_code in text:
            logger.debug(f"[相关性计算] 股票代码数字部分 {pure_code} 出现在标题中，相关性评分: 0.9，标题: {title[:50]}...")
            return 0.9

        logger.debug(f"[相关性计算] 未检测到明确相关性，使用默认评分: 0.3，标题: {title[:50]}...")
        return 0.3  # 默认相关性

    def _deduplicate_news(self, news_items: List[NewsItem]) -> List[NewsItem]:
        """去重新闻"""
        logger.info(f"[新闻去重] 开始对 {len(news_items)} 条新闻进行去重处理")
        start_time = datetime.now(ZoneInfo(get_timezone_name()))

        seen_titles = set()
        unique_news = []
        duplicate_count = 0
        short_title_count = 0

        for item in news_items:
            # 简单的标题去重
            title_key = item.title.lower().strip()

            # 检查标题长度
            if len(title_key) <= 10:
                logger.debug(f"[新闻去重] 跳过标题过短的新闻: '{item.title}'，来源: {item.source}")
                short_title_count += 1
                continue

            # 检查是否重复
            if title_key in seen_titles:
                logger.debug(f"[新闻去重] 检测到重复新闻: '{item.title[:50]}...'，来源: {item.source}")
                duplicate_count += 1
                continue

            # 添加到结果集
            seen_titles.add(title_key)
            unique_news.append(item)

        # 记录去重结果
        time_taken = (datetime.now(ZoneInfo(get_timezone_name())) - start_time).total_seconds()
        logger.info(f"[新闻去重] 去重完成，原始新闻: {len(news_items)}条，去重后: {len(unique_news)}条，")
        logger.info(f"[新闻去重] 去除重复: {duplicate_count}条，标题过短: {short_title_count}条，耗时: {time_taken:.2f}秒")

        return unique_news

    def format_news_report(self, news_items: List[NewsItem], ticker: str) -> str:
        """格式化新闻报告"""
        logger.info(f"[新闻报告] 开始为 {ticker} 生成新闻报告")
        start_time = datetime.now(ZoneInfo(get_timezone_name()))

        if not news_items:
            logger.warning(f"[新闻报告] 未获取到 {ticker} 的实时新闻数据")
            return f"未获取到{ticker}的实时新闻数据。"

        # 按紧急程度分组
        high_urgency = [n for n in news_items if n.urgency == 'high']
        medium_urgency = [n for n in news_items if n.urgency == 'medium']
        low_urgency = [n for n in news_items if n.urgency == 'low']

        # 记录新闻分类情况
        logger.info(f"[新闻报告] {ticker} 新闻分类统计: 高紧急度 {len(high_urgency)}条, 中紧急度 {len(medium_urgency)}条, 低紧急度 {len(low_urgency)}条")

        # 记录新闻来源分布
        news_sources = {}
        for item in news_items:
            source = item.source
            if source in news_sources:
                news_sources[source] += 1
            else:
                news_sources[source] = 1

        sources_info = ", ".join([f"{source}: {count}条" for source, count in news_sources.items()])
        logger.info(f"[新闻报告] {ticker} 新闻来源分布: {sources_info}")

        report = f"# {ticker} 实时新闻分析报告\n\n"
        report += f"📅 生成时间: {datetime.now(ZoneInfo(get_timezone_name())).strftime('%Y-%m-%d %H:%M:%S')}\n"
        report += f"📊 新闻总数: {len(news_items)}条\n\n"

        if high_urgency:
            report += "## 🚨 紧急新闻\n\n"
            for news in high_urgency[:3]:  # 最多显示3条
                report += f"### {news.title}\n"
                report += f"**来源**: {news.source} | **时间**: {news.publish_time.strftime('%H:%M')}\n"
                report += f"{news.content}\n\n"

        if medium_urgency:
            report += "## 📢 重要新闻\n\n"
            for news in medium_urgency[:5]:  # 最多显示5条
                report += f"### {news.title}\n"
                report += f"**来源**: {news.source} | **时间**: {news.publish_time.strftime('%H:%M')}\n"
                report += f"{news.content}\n\n"

        # 添加时效性说明
        latest_news = max(news_items, key=lambda x: x.publish_time)
        time_diff = datetime.now(ZoneInfo(get_timezone_name())) - latest_news.publish_time

        report += f"\n## ⏰ 数据时效性\n"
        report += f"最新新闻发布于: {time_diff.total_seconds() / 60:.0f}分钟前\n"

        if time_diff.total_seconds() < 1800:  # 30分钟内
            report += "🟢 数据时效性: 优秀 (30分钟内)\n"
        elif time_diff.total_seconds() < 3600:  # 1小时内
            report += "🟡 数据时效性: 良好 (1小时内)\n"
        else:
            report += "🔴 数据时效性: 一般 (超过1小时)\n"

        # 记录报告生成完成信息
        end_time = datetime.now(ZoneInfo(get_timezone_name()))
        time_taken = (end_time - start_time).total_seconds()
        report_length = len(report)

        logger.info(f"[新闻报告] {ticker} 新闻报告生成完成，耗时: {time_taken:.2f}秒，报告长度: {report_length}字符")

        # 记录时效性信息
        time_diff_minutes = time_diff.total_seconds() / 60
        logger.info(f"[新闻报告] {ticker} 新闻时效性: 最新新闻发布于 {time_diff_minutes:.1f}分钟前")

        return report


def get_realtime_stock_news(ticker: str, curr_date: str, hours_back: int = 6) -> str:
    """
    获取实时股票新闻的主要接口函数
    """
    logger.info(f"[新闻分析] ========== 函数入口 ==========")
    logger.info(f"[新闻分析] 函数: get_realtime_stock_news")
    logger.info(f"[新闻分析] 参数: ticker={ticker}, curr_date={curr_date}, hours_back={hours_back}")
    logger.info(f"[新闻分析] 开始获取 {ticker} 的实时新闻，日期: {curr_date}, 回溯时间: {hours_back}小时")
    start_total_time = datetime.now(ZoneInfo(get_timezone_name()))
    logger.info(f"[新闻分析] 开始时间: {start_total_time.strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]}")

    # 判断股票类型
    logger.info(f"[新闻分析] ========== 步骤1: 股票类型判断 ==========")
    stock_type = "未知"
    is_china_stock = False
    logger.info(f"[新闻分析] 原始ticker: {ticker}")

    if '.' in ticker:
        logger.info(f"[新闻分析] 检测到ticker包含点号，进行后缀匹配")
        if any(suffix in ticker for suffix in ['.SH', '.SZ', '.SS', '.XSHE', '.XSHG']):
            stock_type = "A股"
            is_china_stock = True
            logger.info(f"[新闻分析] 匹配到A股后缀，股票类型: {stock_type}")
        elif '.HK' in ticker:
            stock_type = "港股"
            logger.info(f"[新闻分析] 匹配到港股后缀，股票类型: {stock_type}")
        elif any(suffix in ticker for suffix in ['.US', '.N', '.O', '.NYSE', '.NASDAQ']):
            stock_type = "美股"
            logger.info(f"[新闻分析] 匹配到美股后缀，股票类型: {stock_type}")
        else:
            logger.info(f"[新闻分析] 未匹配到已知后缀")
    else:
        logger.info(f"[新闻分析] ticker不包含点号，尝试使用StockUtils判断")
        # 尝试使用StockUtils判断股票类型
        try:
            from tradingagents.utils.stock_utils import StockUtils
            logger.info(f"[新闻分析] 成功导入StockUtils，开始判断股票类型")
            market_info = StockUtils.get_market_info(ticker)
            logger.info(f"[新闻分析] StockUtils返回市场信息: {market_info}")
            if market_info['is_china']:
                stock_type = "A股"
                is_china_stock = True
                logger.info(f"[新闻分析] StockUtils判断为A股")
            elif market_info['is_hk']:
                stock_type = "港股"
                logger.info(f"[新闻分析] StockUtils判断为港股")
            elif market_info['is_us']:
                stock_type = "美股"
                logger.info(f"[新闻分析] StockUtils判断为美股")
        except Exception as e:
            logger.warning(f"[新闻分析] 使用StockUtils判断股票类型失败: {e}")

    logger.info(f"[新闻分析] 最终判断结果 - 股票 {ticker} 类型: {stock_type}, 是否A股: {is_china_stock}")

    # 对于A股，优先使用东方财富新闻源
    if is_china_stock:
        logger.info(f"[新闻分析] ========== 步骤2: A股东方财富新闻获取 ==========")
        logger.info(f"[新闻分析] 检测到A股股票 {ticker}，优先尝试使用东方财富新闻源")
        try:
            logger.info(f"[新闻分析] 尝试通过 AKShare Provider 获取新闻")
            from tradingagents.dataflows.providers.china.akshare import AKShareProvider

            provider = AKShareProvider()
            logger.info(f"[新闻分析] 成功创建 AKShare Provider 实例")

            # 处理A股代码
            clean_ticker = ticker.replace('.SH', '').replace('.SZ', '').replace('.SS', '')\
                            .replace('.XSHE', '').replace('.XSHG', '')
            logger.info(f"[新闻分析] 原始ticker: {ticker} -> 清理后ticker: {clean_ticker}")

            logger.info(f"[新闻分析] 准备调用 provider.get_stock_news_sync({clean_ticker})")
            logger.info(f"[新闻分析] 开始从东方财富获取 {clean_ticker} 的新闻数据")
            start_time = datetime.now(ZoneInfo(get_timezone_name()))
            logger.info(f"[新闻分析] 东方财富API调用开始时间: {start_time.strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]}")

            news_df = provider.get_stock_news_sync(symbol=clean_ticker, limit=10)

            end_time = datetime.now(ZoneInfo(get_timezone_name()))
            time_taken = (end_time - start_time).total_seconds()
            logger.info(f"[新闻分析] 东方财富API调用结束时间: {end_time.strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]}")
            logger.info(f"[新闻分析] 东方财富API调用耗时: {time_taken:.2f}秒")
            logger.info(f"[新闻分析] 东方财富API返回数据类型: {type(news_df)}")

            if hasattr(news_df, 'empty'):
                logger.info(f"[新闻分析] 东方财富API返回DataFrame，是否为空: {news_df.empty}")
                if not news_df.empty:
                    logger.info(f"[新闻分析] 东方财富API返回DataFrame形状: {news_df.shape}")
                    logger.info(f"[新闻分析] 东方财富API返回DataFrame列名: {list(news_df.columns) if hasattr(news_df, 'columns') else '无列名'}")
            else:
                logger.info(f"[新闻分析] 东方财富API返回数据: {news_df}")

            if not news_df.empty:
                # 构建简单的新闻报告
                news_count = len(news_df)
                logger.info(f"[新闻分析] 成功获取 {news_count} 条东方财富新闻，耗时 {time_taken:.2f} 秒")

                report = f"# {ticker} 东方财富新闻报告\n\n"
                report += f"📅 生成时间: {datetime.now(ZoneInfo(get_timezone_name())).strftime('%Y-%m-%d %H:%M:%S')}\n"
                report += f"📊 新闻总数: {news_count}条\n"
                report += f"🕒 获取耗时: {time_taken:.2f}秒\n\n"

                # 记录一些新闻标题示例
                sample_titles = [row.get('新闻标题', '无标题') for _, row in news_df.head(3).iterrows()]
                logger.info(f"[新闻分析] 新闻标题示例: {', '.join(sample_titles)}")

                logger.info(f"[新闻分析] 开始构建新闻报告")
                for idx, (_, row) in enumerate(news_df.iterrows()):
                    if idx < 3:  # 只记录前3条的详细信息
                        logger.info(f"[新闻分析] 第{idx+1}条新闻: 标题={row.get('新闻标题', '无标题')}, 时间={row.get('发布时间', '无时间')}")
                    report += f"### {row.get('新闻标题', '')}\n"
                    report += f"📅 {row.get('发布时间', '')}\n"
                    report += f"🔗 {row.get('新闻链接', '')}\n\n"
                    report += f"{row.get('新闻内容', '无内容')}\n\n"

                total_time_taken = (datetime.now(ZoneInfo(get_timezone_name())) - start_total_time).total_seconds()
                logger.info(f"[新闻分析] 成功生成 {ticker} 的新闻报告，总耗时 {total_time_taken:.2f} 秒，新闻来源: 东方财富")
                logger.info(f"[新闻分析] 报告长度: {len(report)} 字符")
                logger.info(f"[新闻分析] ========== 东方财富新闻获取成功，函数即将返回 ==========")
                return report
            else:
                logger.warning(f"[新闻分析] 东方财富未获取到 {ticker} 的新闻，耗时 {time_taken:.2f} 秒，尝试使用其他新闻源")
        except Exception as e:
            logger.error(f"[新闻分析] 东方财富新闻获取失败: {e}，将尝试其他新闻源")
            logger.error(f"[新闻分析] 异常详情: {type(e).__name__}: {str(e)}")
            import traceback
            logger.error(f"[新闻分析] 异常堆栈: {traceback.format_exc()}")
    else:
        logger.info(f"[新闻分析] ========== 跳过A股东方财富新闻获取 ==========")
        logger.info(f"[新闻分析] 股票类型为 {stock_type}，不是A股，跳过东方财富新闻源")

    # 如果不是A股或A股新闻获取失败，使用实时新闻聚合器
    logger.info(f"[新闻分析] ========== 步骤3: 实时新闻聚合器 ==========")
    aggregator = RealtimeNewsAggregator()
    logger.info(f"[新闻分析] 成功创建实时新闻聚合器实例")
    try:
        logger.info(f"[新闻分析] 尝试使用实时新闻聚合器获取 {ticker} 的新闻")
        start_time = datetime.now(ZoneInfo(get_timezone_name()))
        logger.info(f"[新闻分析] 聚合器调用开始时间: {start_time.strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]}")

        # 获取实时新闻
        news_items = aggregator.get_realtime_stock_news(ticker, hours_back, max_news=10)

        end_time = datetime.now(ZoneInfo(get_timezone_name()))
        time_taken = (end_time - start_time).total_seconds()
        logger.info(f"[新闻分析] 聚合器调用结束时间: {end_time.strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]}")
        logger.info(f"[新闻分析] 聚合器调用耗时: {time_taken:.2f}秒")
        logger.info(f"[新闻分析] 聚合器返回数据类型: {type(news_items)}")
        logger.info(f"[新闻分析] 聚合器返回数据: {news_items}")

        # 如果成功获取到新闻
        if news_items and len(news_items) > 0:
            news_count = len(news_items)
            logger.info(f"[新闻分析] 实时新闻聚合器成功获取 {news_count} 条 {ticker} 的新闻，耗时 {time_taken:.2f} 秒")

            # 记录一些新闻标题示例
            sample_titles = [item.title for item in news_items[:3]]
            logger.info(f"[新闻分析] 新闻标题示例: {', '.join(sample_titles)}")

            # 格式化报告
            logger.info(f"[新闻分析] 开始格式化新闻报告")
            report = aggregator.format_news_report(news_items, ticker)
            logger.info(f"[新闻分析] 报告格式化完成，长度: {len(report)} 字符")

            total_time_taken = (datetime.now(ZoneInfo(get_timezone_name())) - start_total_time).total_seconds()
            logger.info(f"[新闻分析] 成功生成 {ticker} 的新闻报告，总耗时 {total_time_taken:.2f} 秒，新闻来源: 实时新闻聚合器")
            logger.info(f"[新闻分析] ========== 实时新闻聚合器获取成功，函数即将返回 ==========")
            return report
        else:
            logger.warning(f"[新闻分析] 实时新闻聚合器未获取到 {ticker} 的新闻，耗时 {time_taken:.2f} 秒，尝试使用备用新闻源")
            # 如果没有获取到新闻，继续尝试备用方案
    except Exception as e:
        logger.error(f"[新闻分析] 实时新闻聚合器获取失败: {e}，将尝试备用新闻源")
        logger.error(f"[新闻分析] 异常详情: {type(e).__name__}: {str(e)}")
        import traceback
        logger.error(f"[新闻分析] 异常堆栈: {traceback.format_exc()}")
        # 发生异常时，继续尝试备用方案

    # 备用方案1: 对于港股，优先尝试使用东方财富新闻（A股已在前面处理）
    if not is_china_stock and '.HK' in ticker:
        logger.info(f"[新闻分析] 检测到港股代码 {ticker}，尝试使用东方财富新闻源")
        try:
            from tradingagents.dataflows.providers.china.akshare import AKShareProvider

            provider = AKShareProvider()

            # 处理港股代码
            clean_ticker = ticker.replace('.HK', '')

            logger.info(f"[新闻分析] 开始从东方财富获取港股 {clean_ticker} 的新闻数据")
            start_time = datetime.now(ZoneInfo(get_timezone_name()))
            news_df = provider.get_stock_news_sync(symbol=clean_ticker, limit=10)
            end_time = datetime.now(ZoneInfo(get_timezone_name()))
            time_taken = (end_time - start_time).total_seconds()

            if not news_df.empty:
                # 构建简单的新闻报告
                news_count = len(news_df)
                logger.info(f"[新闻分析] 成功获取 {news_count} 条东方财富港股新闻，耗时 {time_taken:.2f} 秒")

                report = f"# {ticker} 东方财富新闻报告\n\n"
                report += f"📅 生成时间: {datetime.now(ZoneInfo(get_timezone_name())).strftime('%Y-%m-%d %H:%M:%S')}\n"
                report += f"📊 新闻总数: {news_count}条\n"
                report += f"🕒 获取耗时: {time_taken:.2f}秒\n\n"

                # 记录一些新闻标题示例
                sample_titles = [row.get('新闻标题', '无标题') for _, row in news_df.head(3).iterrows()]
                logger.info(f"[新闻分析] 新闻标题示例: {', '.join(sample_titles)}")

                for _, row in news_df.iterrows():
                    report += f"### {row.get('新闻标题', '')}\n"
                    report += f"📅 {row.get('发布时间', '')}\n"
                    report += f"🔗 {row.get('新闻链接', '')}\n\n"
                    report += f"{row.get('新闻内容', '无内容')}\n\n"

                logger.info(f"[新闻分析] 成功生成东方财富新闻报告，新闻来源: 东方财富")
                return report
            else:
                logger.warning(f"[新闻分析] 东方财富未获取到 {clean_ticker} 的新闻数据，耗时 {time_taken:.2f} 秒，尝试下一个备用方案")
        except Exception as e:
            logger.error(f"[新闻分析] 东方财富新闻获取失败: {e}，将尝试下一个备用方案")

    # 备用方案2: 尝试使用Google新闻
    try:
        from tradingagents.dataflows.interface import get_google_news

        # 根据股票类型构建搜索查询
        if stock_type == "A股":
            # A股使用中文关键词
            clean_ticker = ticker.replace('.SH', '').replace('.SZ', '').replace('.SS', '')\
                           .replace('.XSHE', '').replace('.XSHG', '')
            search_query = f"{clean_ticker} 股票 公司 财报 新闻"
            logger.info(f"[新闻分析] 开始从Google获取A股 {clean_ticker} 的中文新闻数据，查询: {search_query}")
        elif stock_type == "港股":
            # 港股使用中文关键词
            clean_ticker = ticker.replace('.HK', '')
            search_query = f"{clean_ticker} 港股 公司"
            logger.info(f"[新闻分析] 开始从Google获取港股 {clean_ticker} 的新闻数据，查询: {search_query}")
        else:
            # 美股使用英文关键词
            search_query = f"{ticker} stock news"
            logger.info(f"[新闻分析] 开始从Google获取 {ticker} 的新闻数据，查询: {search_query}")

        start_time = datetime.now(ZoneInfo(get_timezone_name()))
        google_news = get_google_news(search_query, curr_date, 1)
        end_time = datetime.now(ZoneInfo(get_timezone_name()))
        time_taken = (end_time - start_time).total_seconds()

        if google_news and len(google_news.strip()) > 0:
            # 估算获取的新闻数量
            news_lines = google_news.strip().split('\n')
            news_count = sum(1 for line in news_lines if line.startswith('###'))

            logger.info(f"[新闻分析] 成功获取 Google 新闻，估计 {news_count} 条新闻，耗时 {time_taken:.2f} 秒")

            # 记录一些新闻标题示例
            sample_titles = [line.replace('### ', '') for line in news_lines if line.startswith('### ')][:3]
            if sample_titles:
                logger.info(f"[新闻分析] 新闻标题示例: {', '.join(sample_titles)}")

            logger.info(f"[新闻分析] 成功生成 Google 新闻报告，新闻来源: Google")
            return google_news
        else:
            logger.warning(f"[新闻分析] Google 新闻未获取到 {ticker} 的新闻数据，耗时 {time_taken:.2f} 秒")
    except Exception as e:
        logger.error(f"[新闻分析] Google 新闻获取失败: {e}，所有备用方案均已尝试")

    # 所有方法都失败，返回错误信息
    total_time_taken = (datetime.now(ZoneInfo(get_timezone_name())) - start_total_time).total_seconds()
    logger.error(f"[新闻分析] {ticker} 的所有新闻获取方法均已失败，总耗时 {total_time_taken:.2f} 秒")

    # 记录详细的失败信息
    failure_details = {
        "股票代码": ticker,
        "股票类型": stock_type,
        "分析日期": curr_date,
        "回溯时间": f"{hours_back}小时",
        "总耗时": f"{total_time_taken:.2f}秒"
    }
    logger.error(f"[新闻分析] 新闻获取失败详情: {failure_details}")

    return f"""
实时新闻获取失败 - {ticker}
分析日期: {curr_date}

❌ 错误信息: 所有可用的新闻源都未能获取到相关新闻

💡 备用建议:
1. 检查网络连接和API密钥配置
2. 使用基础新闻分析作为备选
3. 关注官方财经媒体的最新报道
4. 考虑使用专业金融终端获取实时新闻

注: 实时新闻获取依赖外部API服务的可用性。
"""
