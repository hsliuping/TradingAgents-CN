"""
市场新闻数据库服务
提供新闻存储、查询、分析和词云数据生成功能
"""
import logging
import jieba
import jieba.analyse
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from collections import Counter

from app.core.database import get_mongo_db
from app.services.news_grouping_service import NewsGroupingService

logger = logging.getLogger("webapi")


class NewsDatabaseService:
    """新闻数据库服务"""

    # 集合名称
    COLLECTION = "market_news_enhanced"

    # 停用词
    STOP_WORDS = set([
        "的", "了", "在", "是", "我", "有", "和", "就", "不", "人", "都", "一",
        "一个", "上", "也", "很", "到", "说", "要", "去", "你", "会", "着", "没有",
        "看", "好", "自己", "这", "公司", "表示", "称", "指出", "认为", "据",
        "记者", "获悉", "相关", "目前", "本次", "公告", "显示", "数据", "万元", "亿元"
    ])

    @classmethod
    async def ensure_indexes(cls):
        """创建必要的索引"""
        db = get_mongo_db()
        collection = db[cls.COLLECTION]

        indexes = [
            [("dataTime", -1)],
            [("source", 1), ("dataTime", -1)],
            [("category", 1), ("hotnessScore", -1)],
            [("stocks.code", 1)],
            [("keywords", 1)],
            [("tags.name", 1)],
            [("sentiment", 1)],
            [("createdAt", -1)],
        ]

        for index in indexes:
            try:
                await collection.create_index(index)
            except Exception as e:
                logger.warning(f"Index creation failed: {index}, error: {e}")

    @classmethod
    def extract_entities_and_tags(cls, news: Dict) -> Dict[str, Any]:
        """提取实体和标签"""
        title = news.get("title", "")
        content = news.get("content", "")
        full_text = f"{title} {content}"

        # 使用分组服务提取实体
        entities = NewsGroupingService.extract_entities(title, content)

        # 提取关键词
        keywords = jieba.analyse.extract_tags(full_text, topK=10, withWeight=True)
        filtered_keywords = [
            {"word": word, "weight": weight}
            for word, weight in keywords
            if word not in cls.STOP_WORDS and len(word) >= 2
        ]

        # 构建标签
        tags = []
        for concept in entities.get("concepts", []):
            tags.append({"name": concept, "type": "concept", "weight": 5.0})
        for stock in entities.get("stocks", []):
            name = stock.get("name") or stock.get("code", "")
            if name:
                tags.append({"name": name, "type": "stock", "weight": 3.0})
        for status in entities.get("market_status", []):
            tags.append({"name": status, "type": "status", "weight": 4.0})
        for fund_type in entities.get("fund_types", []):
            tags.append({"name": fund_type, "type": "fund", "weight": 3.0})

        # 简单情感分析
        bullish_words = ["上涨", "涨停", "突破", "创新高", "利好", "增长", "盈利"]
        bearish_words = ["下跌", "跌停", "回调", "风险", "亏损", "下行"]

        sentiment = "neutral"
        sentiment_score = 0.0

        bullish_count = sum(1 for word in bullish_words if word in full_text)
        bearish_count = sum(1 for word in bearish_words if word in full_text)

        if bullish_count > bearish_count:
            sentiment = "bullish"
            sentiment_score = min(0.8, 0.3 + bullish_count * 0.1)
        elif bearish_count > bullish_count:
            sentiment = "bearish"
            sentiment_score = max(-0.8, -0.3 - bearish_count * 0.1)

        # 热度评分
        hotness_score = NewsGroupingService.calculate_hotness_score(news, entities)

        # 分类
        category = NewsGroupingService.classify_news_type(entities)

        return {
            "entities": entities,
            "tags": tags,
            "keywords": [k["word"] for k in filtered_keywords],
            "keyword_weights": {k["word"]: k["weight"] for k in filtered_keywords},
            "sentiment": sentiment,
            "sentimentScore": sentiment_score,
            "hotnessScore": hotness_score,
            "category": category,
            "stocks": entities.get("stocks", []),
            "marketStatus": entities.get("market_status", []),
        }

    @classmethod
    async def save_news(cls, news_list: List[Dict], source: str) -> int:
        """保存新闻到数据库（带完整标签和分析）"""
        try:
            db = get_mongo_db()
            collection = db[cls.COLLECTION]

            saved_count = 0

            for news in news_list:
                try:
                    # 提取实体和标签
                    enriched = cls.extract_entities_and_tags(news)

                    # 构建文档
                    doc = {
                        "title": news.get("title", ""),
                        "content": news.get("content", ""),
                        "url": news.get("url"),
                        "time": news.get("time", ""),
                        "dataTime": datetime.fromisoformat(news["dataTime"]) if isinstance(news.get("dataTime"), str) else news.get("dataTime"),
                        "source": source,
                        "isRed": news.get("isRed", False),
                        "subjects": news.get("subjects", []),
                        **enriched,
                        "createdAt": datetime.now(),
                        "updatedAt": datetime.now(),
                    }

                    # 检查是否存在
                    existing = None
                    if doc.get("url"):
                        existing = await collection.find_one({"url": doc["url"]})
                    elif doc.get("title") and doc.get("dataTime"):
                        existing = await collection.find_one({
                            "title": doc["title"],
                            "dataTime": doc["dataTime"]
                        })

                    if existing:
                        await collection.update_one({"_id": existing["_id"]}, {"$set": doc})
                    else:
                        await collection.insert_one(doc)

                    saved_count += 1

                except Exception as e:
                    logger.warning(f"保存单条新闻失败: {e}")
                    continue

            logger.info(f"成功保存 {saved_count} 条 {source} 新闻到增强数据库")
            return saved_count

        except Exception as e:
            logger.error(f"保存新闻到数据库失败: {e}")
            return 0

    @classmethod
    async def get_wordcloud_data(cls, hours: int = 24, top_n: int = 50, source: str = None) -> List[Dict]:
        """获取词云数据"""
        try:
            db = get_mongo_db()
            collection = db[cls.COLLECTION]

            query = {"dataTime": {"$gte": datetime.now() - timedelta(hours=hours)}}
            if source:
                query["source"] = source

            pipeline = [
                {"$match": query},
                {"$unwind": "$keywords"},
                {"$group": {"_id": "$keywords", "count": {"$sum": 1}}},
                {"$sort": {"count": -1}},
                {"$limit": top_n}
            ]

            results = []
            async for doc in collection.aggregate(pipeline):
                results.append({"word": doc["_id"], "weight": doc["count"], "count": doc["count"]})

            return results

        except Exception as e:
            logger.error(f"获取词云数据失败: {e}")
            return []

    @classmethod
    async def get_news_analytics(cls, start_date=None, end_date=None, sources=None, categories=None) -> Dict:
        """获取新闻分析数据"""
        try:
            db = get_mongo_db()
            collection = db[cls.COLLECTION]

            query = {}
            if start_date or end_date:
                query["dataTime"] = {}
                if start_date:
                    query["dataTime"]["$gte"] = start_date
                if end_date:
                    query["dataTime"]["$lte"] = end_date
            if sources:
                query["source"] = {"$in": sources}
            if categories:
                query["category"] = {"$in": categories}

            total_count = await collection.count_documents(query)

            # 来源分布
            source_dist = {}
            async for doc in collection.aggregate([
                {"$match": query},
                {"$group": {"_id": "$source", "count": {"$sum": 1}}}
            ]):
                source_dist[doc["_id"]] = doc["count"]

            # 分类分布
            category_dist = {}
            async for doc in collection.aggregate([
                {"$match": query},
                {"$group": {"_id": "$category", "count": {"$sum": 1}}}
            ]):
                category_dist[doc["_id"]] = doc["count"]

            # 热门股票
            hot_stocks = []
            async for doc in collection.aggregate([
                {"$match": query},
                {"$unwind": "$stocks"},
                {"$group": {"_id": "$stocks.code", "count": {"$sum": 1}}},
                {"$sort": {"count": -1}},
                {"$limit": 10}
            ]):
                hot_stocks.append({"code": doc["_id"], "count": doc["count"]})

            # 词云数据
            wordcloud = await cls.get_wordcloud_data(hours=24*7, top_n=30)

            return {
                "total_count": total_count,
                "source_distribution": source_dist,
                "category_distribution": category_dist,
                "hot_stocks": hot_stocks,
                "wordcloud": wordcloud
            }

        except Exception as e:
            logger.error(f"获取新闻分析失败: {e}")
            return {"total_count": 0}
