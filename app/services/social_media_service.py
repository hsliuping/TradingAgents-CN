"""
社媒消息数据服务
提供统一的社媒消息存储、查询和分析功能
"""
from typing import Optional, List, Dict, Any, Union
from datetime import datetime, timedelta
from dataclasses import dataclass, field
import logging
from pymongo import ReplaceOne
from pymongo.errors import BulkWriteError
from bson import ObjectId

from app.core.database import get_database

logger = logging.getLogger(__name__)


def convert_objectid_to_str(data: Union[Dict, List[Dict]]) -> Union[Dict, List[Dict]]:
    """
    转换 MongoDB ObjectId 为字符串，避免 JSON 序列化错误
    
    Args:
        data: 单个文档或文档列表
        
    Returns:
        转换后的数据
    """
    if isinstance(data, list):
        for item in data:
            if isinstance(item, dict):
                if '_id' in item and isinstance(item['_id'], ObjectId):
                    item['_id'] = str(item['_id'])
                # 递归处理嵌套字典
                for key, value in item.items():
                    if isinstance(value, dict):
                        convert_objectid_to_str(value)
                    elif isinstance(value, list):
                        for sub_item in value:
                            if isinstance(sub_item, dict):
                                convert_objectid_to_str(sub_item)
    elif isinstance(data, dict):
        if '_id' in data and isinstance(data['_id'], ObjectId):
            data['_id'] = str(data['_id'])
        # 递归处理嵌套字典
        for key, value in data.items():
            if isinstance(value, dict):
                convert_objectid_to_str(value)
            elif isinstance(value, list):
                for sub_item in value:
                    if isinstance(sub_item, dict):
                        convert_objectid_to_str(sub_item)
    return data


@dataclass
class SocialMediaQueryParams:
    """社媒消息查询参数"""
    symbol: Optional[str] = None
    symbols: Optional[List[str]] = None
    market: Optional[str] = None  # A股/港股/美股
    platform: Optional[str] = None  # weibo/wechat/douyin/xiaohongshu/zhihu/twitter/reddit
    message_type: Optional[str] = None  # post/comment/repost/reply
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    sentiment: Optional[str] = None
    importance: Optional[str] = None
    min_influence_score: Optional[float] = None
    min_engagement_rate: Optional[float] = None
    verified_only: bool = False
    keywords: Optional[List[str]] = None
    hashtags: Optional[List[str]] = None
    limit: int = 50
    skip: int = 0
    sort_by: str = "publish_time"
    sort_order: int = -1  # -1 for desc, 1 for asc


@dataclass
class SocialMediaStats:
    """社媒消息统计信息"""
    total_count: int = 0
    positive_count: int = 0
    negative_count: int = 0
    neutral_count: int = 0
    platforms: Dict[str, int] = field(default_factory=dict)
    message_types: Dict[str, int] = field(default_factory=dict)
    top_hashtags: List[Dict[str, Any]] = field(default_factory=list)
    avg_engagement_rate: float = 0.0
    total_views: int = 0
    total_likes: int = 0
    total_shares: int = 0
    total_comments: int = 0


class SocialMediaService:
    """社媒消息数据服务"""
    
    def __init__(self):
        self.db = None
        self.collection = None
        self.logger = logging.getLogger(self.__class__.__name__)
    
    async def initialize(self):
        """初始化服务"""
        try:
            self.db = get_database()
            self.collection = self.db.social_media_messages
            self.logger.info("✅ 社媒消息数据服务初始化成功")
        except Exception as e:
            self.logger.error(f"❌ 社媒消息数据服务初始化失败: {e}")
            raise
    
    async def _get_collection(self):
        """获取集合实例"""
        if self.collection is None:
            await self.initialize()
        return self.collection
    
    async def save_social_media_messages(
        self, 
        messages: List[Dict[str, Any]]
    ) -> Dict[str, int]:
        """
        批量保存社媒消息
        
        Args:
            messages: 社媒消息列表
            
        Returns:
            保存统计信息
        """
        if not messages:
            return {"saved": 0, "failed": 0}
        
        try:
            collection = await self._get_collection()
            
            # 准备批量操作
            operations = []
            for message in messages:
                # 添加时间戳
                message["created_at"] = datetime.utcnow()
                message["updated_at"] = datetime.utcnow()
                
                # 🔥 自动识别市场类型（如果缺失）
                if not message.get("market") and message.get("symbol"):
                    try:
                        from tradingagents.utils.stock_utils import StockUtils
                        market_info = StockUtils.get_market_info(message["symbol"])
                        if market_info.get('is_china'):
                            message["market"] = 'A股'
                        elif market_info.get('is_hk'):
                            message["market"] = '港股'
                        elif market_info.get('is_us'):
                            message["market"] = '美股'
                        else:
                            message["market"] = 'A股'  # 默认A股
                    except Exception as e:
                        self.logger.warning(f"⚠️ 无法识别市场类型，使用默认值A股: {e}")
                        message["market"] = 'A股'
                
                # 🔥 修复MongoDB语言代码问题：将zh-CN转换为none（MongoDB文本索引不支持zh-CN）
                if message.get("language") == "zh-CN":
                    message["language"] = "none"
                elif message.get("language") and message.get("language") not in ["none", "english", "spanish", "french", "german", "portuguese", "russian", "chinese"]:
                    # 如果是不支持的语言代码，改为none
                    message["language"] = "none"
                
                # 🔥 使用message_id、platform和symbol作为唯一标识
                # 这样同一个消息ID和平台，如果股票代码不同，会被视为不同的消息
                filter_dict = {
                    "message_id": message.get("message_id"),
                    "platform": message.get("platform"),
                    "symbol": message.get("symbol")
                }
                
                # 确保symbol存在
                if not message.get("symbol"):
                    self.logger.warning(f"⚠️ 消息缺少symbol字段，跳过: {message.get('message_id')}")
                    continue
                
                operations.append(ReplaceOne(filter_dict, message, upsert=True))
            
            # 执行批量操作
            result = await collection.bulk_write(operations, ordered=False)
            
            saved_count = result.upserted_count + result.modified_count
            self.logger.info(f"✅ 社媒消息批量保存完成: {saved_count}/{len(messages)}")
            
            return {
                "saved": saved_count,
                "failed": len(messages) - saved_count,
                "upserted": result.upserted_count,
                "modified": result.modified_count
            }
            
        except BulkWriteError as e:
            self.logger.error(f"❌ 社媒消息批量保存部分失败: {e.details}")
            return {
                "saved": e.details.get("nUpserted", 0) + e.details.get("nModified", 0),
                "failed": len(e.details.get("writeErrors", [])),
                "errors": e.details.get("writeErrors", [])
            }
        except Exception as e:
            self.logger.error(f"❌ 社媒消息保存失败: {e}")
            return {"saved": 0, "failed": len(messages), "error": str(e)}
    
    async def query_social_media_messages(
        self, 
        params: SocialMediaQueryParams
    ) -> List[Dict[str, Any]]:
        """
        查询社媒消息
        
        Args:
            params: 查询参数
            
        Returns:
            社媒消息列表
        """
        try:
            collection = await self._get_collection()
            
            # 构建查询条件
            query = {}
            
            if params.symbol:
                query["symbol"] = params.symbol
            elif params.symbols:
                query["symbol"] = {"$in": params.symbols}
            
            if params.market:
                query["market"] = params.market
            
            if params.platform:
                query["platform"] = params.platform
            
            if params.message_type:
                query["message_type"] = params.message_type
            
            if params.start_time or params.end_time:
                time_query = {}
                if params.start_time:
                    time_query["$gte"] = params.start_time
                if params.end_time:
                    time_query["$lte"] = params.end_time
                query["publish_time"] = time_query
            
            if params.sentiment:
                query["sentiment"] = params.sentiment
            
            if params.importance:
                query["importance"] = params.importance
            
            if params.min_influence_score:
                query["author.influence_score"] = {"$gte": params.min_influence_score}
            
            if params.min_engagement_rate:
                query["engagement.engagement_rate"] = {"$gte": params.min_engagement_rate}
            
            if params.verified_only:
                query["author.verified"] = True
            
            if params.keywords:
                query["keywords"] = {"$in": params.keywords}
            
            if params.hashtags:
                query["hashtags"] = {"$in": params.hashtags}
            
            # 执行查询
            cursor = collection.find(query)
            
            # 排序
            cursor = cursor.sort(params.sort_by, params.sort_order)
            
            # 分页
            cursor = cursor.skip(params.skip).limit(params.limit)
            
            # 获取结果
            messages = await cursor.to_list(length=params.limit)
            
            # 🔥 转换 ObjectId 为字符串，避免 JSON 序列化错误
            messages = convert_objectid_to_str(messages)
            
            self.logger.debug(f"📊 查询到 {len(messages)} 条社媒消息")
            return messages
            
        except Exception as e:
            self.logger.error(f"❌ 社媒消息查询失败: {e}")
            return []
    
    async def get_latest_messages(
        self, 
        symbol: str = None, 
        platform: str = None,
        limit: int = 20
    ) -> List[Dict[str, Any]]:
        """获取最新社媒消息"""
        params = SocialMediaQueryParams(
            symbol=symbol,
            platform=platform,
            limit=limit,
            sort_by="publish_time",
            sort_order=-1
        )
        return await self.query_social_media_messages(params)
    
    async def search_messages(
        self, 
        query: str, 
        symbol: str = None,
        platform: str = None,
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        """全文搜索社媒消息"""
        try:
            collection = await self._get_collection()
            
            # 构建搜索条件
            search_query = {
                "$text": {"$search": query}
            }
            
            if symbol:
                search_query["symbol"] = symbol
            
            if platform:
                search_query["platform"] = platform
            
            # 执行搜索
            cursor = collection.find(
                search_query,
                {"score": {"$meta": "textScore"}}
            ).sort([("score", {"$meta": "textScore"})])
            
            messages = await cursor.limit(limit).to_list(length=limit)
            
            # 🔥 转换 ObjectId 为字符串，避免 JSON 序列化错误
            messages = convert_objectid_to_str(messages)
            
            self.logger.debug(f"🔍 搜索到 {len(messages)} 条相关消息")
            return messages
            
        except Exception as e:
            self.logger.error(f"❌ 社媒消息搜索失败: {e}")
            return []
    
    async def get_social_media_statistics(
        self, 
        symbol: str = None,
        start_time: datetime = None,
        end_time: datetime = None,
        market: str = None,
        platform: str = None,
        sentiment: str = None
    ) -> SocialMediaStats:
        """获取社媒消息统计信息"""
        try:
            collection = await self._get_collection()
            
            # 构建匹配条件（与查询接口保持一致）
            match_stage = {}
            if symbol:
                match_stage["symbol"] = symbol
            if market:
                match_stage["market"] = market
            if platform:
                match_stage["platform"] = platform
            if sentiment:
                match_stage["sentiment"] = sentiment
            if start_time or end_time:
                time_query = {}
                if start_time:
                    time_query["$gte"] = start_time
                if end_time:
                    time_query["$lte"] = end_time
                match_stage["publish_time"] = time_query
            
            # 聚合管道
            pipeline = []
            if match_stage:
                pipeline.append({"$match": match_stage})
            
            pipeline.extend([
                {
                    "$group": {
                        "_id": None,
                        "total_count": {"$sum": 1},
                        "positive_count": {
                            "$sum": {"$cond": [{"$eq": ["$sentiment", "positive"]}, 1, 0]}
                        },
                        "negative_count": {
                            "$sum": {"$cond": [{"$eq": ["$sentiment", "negative"]}, 1, 0]}
                        },
                        "neutral_count": {
                            "$sum": {"$cond": [{"$eq": ["$sentiment", "neutral"]}, 1, 0]}
                        },
                        "total_views": {"$sum": "$engagement.views"},
                        "total_likes": {"$sum": "$engagement.likes"},
                        "total_shares": {"$sum": "$engagement.shares"},
                        "total_comments": {"$sum": "$engagement.comments"},
                        "avg_engagement_rate": {"$avg": "$engagement.engagement_rate"}
                    }
                }
            ])
            
            # 执行聚合
            result = await collection.aggregate(pipeline).to_list(length=1)
            
            if result:
                stats_data = result[0]
                return SocialMediaStats(
                    total_count=stats_data.get("total_count", 0),
                    positive_count=stats_data.get("positive_count", 0),
                    negative_count=stats_data.get("negative_count", 0),
                    neutral_count=stats_data.get("neutral_count", 0),
                    total_views=stats_data.get("total_views", 0),
                    total_likes=stats_data.get("total_likes", 0),
                    total_shares=stats_data.get("total_shares", 0),
                    total_comments=stats_data.get("total_comments", 0),
                    avg_engagement_rate=stats_data.get("avg_engagement_rate", 0.0)
                )
            else:
                return SocialMediaStats()
                
        except Exception as e:
            self.logger.error(f"❌ 社媒消息统计失败: {e}")
            return SocialMediaStats()


# 全局服务实例
_social_media_service = None

async def get_social_media_service() -> SocialMediaService:
    """获取社媒消息数据服务实例"""
    global _social_media_service
    if _social_media_service is None:
        _social_media_service = SocialMediaService()
        await _social_media_service.initialize()
    return _social_media_service
