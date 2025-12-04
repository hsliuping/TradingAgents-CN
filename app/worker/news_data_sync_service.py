"""
新闻数据同步服务
支持多数据源新闻数据同步和情绪分析
"""
import asyncio
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
from dataclasses import dataclass, field

from app.services.news_data_service import get_news_data_service
from tradingagents.dataflows.providers.china.tushare import get_tushare_provider
from tradingagents.dataflows.providers.china.akshare import get_akshare_provider
from tradingagents.dataflows.news.realtime_news import RealtimeNewsAggregator

logger = logging.getLogger(__name__)


@dataclass
class NewsSyncStats:
    """新闻同步统计"""
    total_processed: int = 0
    successful_saves: int = 0
    failed_saves: int = 0
    duplicate_skipped: int = 0
    sources_used: List[str] = field(default_factory=list)
    start_time: datetime = field(default_factory=datetime.utcnow)
    end_time: Optional[datetime] = None
    
    @property
    def duration_seconds(self) -> float:
        """同步耗时（秒）"""
        if self.end_time:
            return (self.end_time - self.start_time).total_seconds()
        return 0.0
    
    @property
    def success_rate(self) -> float:
        """成功率"""
        if self.total_processed == 0:
            return 0.0
        return (self.successful_saves / self.total_processed) * 100


class NewsDataSyncService:
    """新闻数据同步服务"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self._news_service = None
        self._tushare_provider = None
        self._akshare_provider = None
        self._realtime_aggregator = None
    
    async def _get_news_service(self):
        """获取新闻数据服务"""
        if self._news_service is None:
            self._news_service = await get_news_data_service()
        return self._news_service
    
    async def _get_tushare_provider(self):
        """获取Tushare提供者"""
        if self._tushare_provider is None:
            self._tushare_provider = get_tushare_provider()
            await self._tushare_provider.connect()
        return self._tushare_provider
    
    async def _get_tushare_provider(self):
        """获取Tushare提供者"""
        if self._tushare_provider is None:
            from tradingagents.dataflows.providers.china.tushare import get_tushare_provider
            self._tushare_provider = get_tushare_provider()
            await self._tushare_provider.connect()
        return self._tushare_provider

    async def _get_akshare_provider(self):
        """获取AKShare提供者"""
        if self._akshare_provider is None:
            self._akshare_provider = get_akshare_provider()
            await self._akshare_provider.connect()
        return self._akshare_provider
    
    async def _get_realtime_aggregator(self):
        """获取实时新闻聚合器"""
        if self._realtime_aggregator is None:
            self._realtime_aggregator = RealtimeNewsAggregator()
        return self._realtime_aggregator
    
    async def sync_stock_news(
        self,
        symbol: str,
        data_sources: List[str] = None,
        hours_back: int = 24,
        max_news_per_source: int = 50
    ) -> NewsSyncStats:
        """
        同步单只股票的新闻数据
        
        Args:
            symbol: 股票代码
            data_sources: 数据源列表，默认使用所有可用源
            hours_back: 回溯小时数
            max_news_per_source: 每个数据源最大新闻数量
            
        Returns:
            同步统计信息
        """
        stats = NewsSyncStats()
        
        try:
            self.logger.info(f"📰 开始同步股票新闻: {symbol}")
            
            if data_sources is None:
                data_sources = ["tushare", "akshare", "realtime"]
            
            news_service = await self._get_news_service()
            all_news = []
            
            # 1. Tushare新闻
            if "tushare" in data_sources:
                try:
                    tushare_news = await self._sync_tushare_news(
                        symbol, hours_back, max_news_per_source
                    )
                    if tushare_news:
                        all_news.extend(tushare_news)
                        stats.sources_used.append("tushare")
                        self.logger.info(f"✅ Tushare新闻获取成功: {len(tushare_news)}条")
                except Exception as e:
                    self.logger.error(f"❌ Tushare新闻获取失败: {e}")
            
            # 2. AKShare新闻
            if "akshare" in data_sources:
                try:
                    akshare_news = await self._sync_akshare_news(
                        symbol, hours_back, max_news_per_source
                    )
                    if akshare_news:
                        all_news.extend(akshare_news)
                        stats.sources_used.append("akshare")
                        self.logger.info(f"✅ AKShare新闻获取成功: {len(akshare_news)}条")
                except Exception as e:
                    self.logger.error(f"❌ AKShare新闻获取失败: {e}")
            
            # 3. 实时新闻聚合
            if "realtime" in data_sources:
                try:
                    realtime_news = await self._sync_realtime_news(
                        symbol, hours_back, max_news_per_source
                    )
                    if realtime_news:
                        all_news.extend(realtime_news)
                        stats.sources_used.append("realtime")
                        self.logger.info(f"✅ 实时新闻获取成功: {len(realtime_news)}条")
                except Exception as e:
                    self.logger.error(f"❌ 实时新闻获取失败: {e}")
            
            # 保存新闻数据
            if all_news:
                stats.total_processed = len(all_news)
                
                # 去重处理
                unique_news = self._deduplicate_news(all_news)
                stats.duplicate_skipped = len(all_news) - len(unique_news)
                
                # 批量保存
                saved_count = await news_service.save_news_data(
                    unique_news, "multi_source", "CN"
                )
                stats.successful_saves = saved_count
                stats.failed_saves = len(unique_news) - saved_count
                
                self.logger.info(f"💾 {symbol} 新闻同步完成: {saved_count}条保存成功")
            
            stats.end_time = datetime.utcnow()
            return stats
            
        except Exception as e:
            self.logger.error(f"❌ 同步股票新闻失败 {symbol}: {e}")
            stats.end_time = datetime.utcnow()
            return stats
    
    async def _sync_tushare_news(
        self,
        symbol: str,
        hours_back: int,
        max_news: int
    ) -> List[Dict[str, Any]]:
        """同步Tushare新闻"""
        try:
            provider = await self._get_tushare_provider()

            if not provider.is_available():
                self.logger.warning("⚠️ Tushare提供者不可用")
                return []

            # 获取新闻数据，传递hours_back参数
            news_data = await provider.get_stock_news(
                symbol=symbol,
                limit=max_news,
                hours_back=hours_back
            )

            if news_data:
                # 标准化新闻数据
                standardized_news = []
                for news in news_data:
                    standardized = self._standardize_tushare_news(news, symbol)
                    if standardized:
                        standardized_news.append(standardized)

                self.logger.info(f"✅ Tushare新闻获取成功: {len(standardized_news)}条")
                return standardized_news
            else:
                self.logger.debug("⚠️ Tushare未返回新闻数据")
                return []

        except Exception as e:
            # 详细的错误处理
            if any(keyword in str(e).lower() for keyword in ['权限', 'permission', 'unauthorized']):
                self.logger.warning(f"⚠️ Tushare新闻接口需要单独开通权限: {e}")
            elif "积分" in str(e) or "point" in str(e).lower():
                self.logger.warning(f"⚠️ Tushare积分不足: {e}")
            else:
                self.logger.error(f"❌ Tushare新闻同步失败: {e}")
            return []
    
    async def _sync_akshare_news(
        self, 
        symbol: str, 
        hours_back: int, 
        max_news: int
    ) -> List[Dict[str, Any]]:
        """同步AKShare新闻"""
        try:
            provider = await self._get_akshare_provider()
            
            if not provider.is_available():
                return []
            
            # 获取新闻数据
            news_data = await provider.get_stock_news(symbol, limit=max_news)
            
            if news_data:
                # 标准化新闻数据
                standardized_news = []
                for news in news_data:
                    standardized = self._standardize_akshare_news(news, symbol)
                    if standardized:
                        standardized_news.append(standardized)
                
                return standardized_news
            
            return []
            
        except Exception as e:
            self.logger.error(f"❌ AKShare新闻同步失败: {e}")
            return []
    
    async def _sync_realtime_news(
        self, 
        symbol: str, 
        hours_back: int, 
        max_news: int
    ) -> List[Dict[str, Any]]:
        """同步实时新闻"""
        try:
            aggregator = await self._get_realtime_aggregator()
            
            # 获取实时新闻
            news_items = aggregator.get_realtime_stock_news(
                symbol, hours_back, max_news
            )
            
            if news_items:
                # 标准化新闻数据
                standardized_news = []
                for news_item in news_items:
                    standardized = self._standardize_realtime_news(news_item, symbol)
                    if standardized:
                        standardized_news.append(standardized)
                
                return standardized_news
            
            return []
            
        except Exception as e:
            self.logger.error(f"❌ 实时新闻同步失败: {e}")
            return []
    
    def _standardize_tushare_news(self, news: Dict[str, Any], symbol: str) -> Optional[Dict[str, Any]]:
        """标准化Tushare新闻数据"""
        try:
            return {
                "symbol": symbol,
                "title": news.get("title", ""),
                "content": news.get("content", ""),
                "summary": news.get("summary", ""),
                "url": news.get("url", ""),
                "source": news.get("source", "Tushare"),
                "author": news.get("author", ""),
                "publish_time": news.get("publish_time"),
                "category": self._classify_news_category(news.get("title", "")),
                "sentiment": self._analyze_sentiment(news.get("title", "") + " " + news.get("content", "")),
                "importance": self._assess_importance(news.get("title", "")),
                "keywords": self._extract_keywords(news.get("title", "") + " " + news.get("content", "")),
                "data_source": "tushare"
            }
        except Exception as e:
            self.logger.error(f"❌ 标准化Tushare新闻失败: {e}")
            return None
    
    def _standardize_akshare_news(self, news: Dict[str, Any], symbol: str) -> Optional[Dict[str, Any]]:
        """标准化AKShare新闻数据"""
        try:
            return {
                "symbol": symbol,
                "title": news.get("title", ""),
                "content": news.get("content", ""),
                "summary": news.get("summary", ""),
                "url": news.get("url", ""),
                "source": news.get("source", "AKShare"),
                "author": news.get("author", ""),
                "publish_time": news.get("publish_time"),
                "category": self._classify_news_category(news.get("title", "")),
                "sentiment": self._analyze_sentiment(news.get("title", "") + " " + news.get("content", "")),
                "importance": self._assess_importance(news.get("title", "")),
                "keywords": self._extract_keywords(news.get("title", "") + " " + news.get("content", "")),
                "data_source": "akshare"
            }
        except Exception as e:
            self.logger.error(f"❌ 标准化AKShare新闻失败: {e}")
            return None
    
    def _standardize_realtime_news(self, news_item, symbol: str) -> Optional[Dict[str, Any]]:
        """标准化实时新闻数据"""
        try:
            return {
                "symbol": symbol,
                "title": news_item.title,
                "content": news_item.content,
                "summary": news_item.content[:200] + "..." if len(news_item.content) > 200 else news_item.content,
                "url": news_item.url,
                "source": news_item.source,
                "author": "",
                "publish_time": news_item.publish_time,
                "category": self._classify_news_category(news_item.title),
                "sentiment": self._analyze_sentiment(news_item.title + " " + news_item.content),
                "importance": self._assess_importance(news_item.title),
                "keywords": self._extract_keywords(news_item.title + " " + news_item.content),
                "data_source": "realtime"
            }
        except Exception as e:
            self.logger.error(f"❌ 标准化实时新闻失败: {e}")
            return None
    
    def _classify_news_category(self, title: str) -> str:
        """分类新闻类别"""
        title_lower = title.lower()
        
        if any(word in title_lower for word in ["年报", "季报", "业绩", "财报", "公告"]):
            return "company_announcement"
        elif any(word in title_lower for word in ["政策", "央行", "监管", "法规"]):
            return "policy_news"
        elif any(word in title_lower for word in ["市场", "行情", "指数", "板块"]):
            return "market_news"
        elif any(word in title_lower for word in ["研报", "分析", "评级", "推荐"]):
            return "research_report"
        else:
            return "general"
    
    def _analyze_sentiment(self, text: str) -> str:
        """分析情绪"""
        text_lower = text.lower()
        
        positive_words = ["增长", "上涨", "利好", "盈利", "成功", "突破", "创新", "优秀"]
        negative_words = ["下跌", "亏损", "风险", "问题", "困难", "下滑", "减少", "警告"]
        
        positive_count = sum(1 for word in positive_words if word in text_lower)
        negative_count = sum(1 for word in negative_words if word in text_lower)
        
        if positive_count > negative_count:
            return "positive"
        elif negative_count > positive_count:
            return "negative"
        else:
            return "neutral"
    
    def _assess_importance(self, title: str) -> str:
        """评估重要性"""
        title_lower = title.lower()
        
        high_importance_words = ["重大", "紧急", "突发", "年报", "业绩", "重组", "收购"]
        medium_importance_words = ["公告", "通知", "变更", "调整", "计划"]
        
        if any(word in title_lower for word in high_importance_words):
            return "high"
        elif any(word in title_lower for word in medium_importance_words):
            return "medium"
        else:
            return "low"
    
    def _extract_keywords(self, text: str) -> List[str]:
        """提取关键词"""
        # 简单的关键词提取，实际应用中可以使用更复杂的NLP技术
        keywords = []
        
        common_keywords = [
            "业绩", "年报", "季报", "增长", "利润", "营收", "股价", "投资",
            "市场", "行业", "政策", "监管", "风险", "机会", "创新", "发展"
        ]
        
        for keyword in common_keywords:
            if keyword in text:
                keywords.append(keyword)
        
        return keywords[:10]  # 最多返回10个关键词
    
    def _deduplicate_news(self, news_list: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """去重新闻"""
        seen = set()
        unique_news = []
        
        for news in news_list:
            # 使用标题和URL作为去重标识
            key = (news.get("title", ""), news.get("url", ""))
            if key not in seen:
                seen.add(key)
                unique_news.append(news)
        
        return unique_news
    
    async def sync_market_news(
        self,
        data_sources: List[str] = None,
        hours_back: int = 24,
        max_news_per_source: int = 100
    ) -> NewsSyncStats:
        """
        同步市场新闻
        
        Args:
            data_sources: 数据源列表
            hours_back: 回溯小时数
            max_news_per_source: 每个数据源最大新闻数量
            
        Returns:
            同步统计信息
        """
        stats = NewsSyncStats()
        
        try:
            self.logger.info("📰 开始同步市场新闻...")
            
            if data_sources is None:
                data_sources = ["realtime"]
            
            news_service = await self._get_news_service()
            all_news = []
            
            # 实时市场新闻
            if "realtime" in data_sources:
                try:
                    aggregator = await self._get_realtime_aggregator()
                    
                    # 获取市场新闻（不指定股票代码）
                    news_items = aggregator.get_realtime_stock_news(
                        None, hours_back, max_news_per_source
                    )
                    
                    if news_items:
                        for news_item in news_items:
                            standardized = self._standardize_realtime_news(news_item, None)
                            if standardized:
                                all_news.append(standardized)
                        
                        stats.sources_used.append("realtime")
                        self.logger.info(f"✅ 市场新闻获取成功: {len(all_news)}条")
                        
                except Exception as e:
                    self.logger.error(f"❌ 市场新闻获取失败: {e}")
            
            # 保存新闻数据
            if all_news:
                stats.total_processed = len(all_news)
                
                # 去重处理
                unique_news = self._deduplicate_news(all_news)
                stats.duplicate_skipped = len(all_news) - len(unique_news)
                
                # 批量保存
                saved_count = await news_service.save_news_data(
                    unique_news, "market_news", "CN"
                )
                stats.successful_saves = saved_count
                stats.failed_saves = len(unique_news) - saved_count
                
                self.logger.info(f"💾 市场新闻同步完成: {saved_count}条保存成功")
            
            stats.end_time = datetime.utcnow()
            return stats
            
        except Exception as e:
            self.logger.error(f"❌ 同步市场新闻失败: {e}")
            stats.end_time = datetime.utcnow()
            return stats


# 全局服务实例
_sync_service_instance = None

async def get_news_data_sync_service() -> NewsDataSyncService:
    """获取新闻数据同步服务实例"""
    global _sync_service_instance
    if _sync_service_instance is None:
        _sync_service_instance = NewsDataSyncService()
        logger.info("✅ 新闻数据同步服务初始化成功")
    return _sync_service_instance
