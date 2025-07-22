#!/usr/bin/env python3
"""
MongoDB + Redis 数据库缓存管理器
提供高性能的股票数据缓存和持久化存储
"""

import os
import json
import pickle
import hashlib
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List, Union
import pandas as pd

# 导入日志模块
from tradingagents.utils.logging_manager import get_logger
logger = get_logger('agents')

# MongoDB
try:
    from pymongo import MongoClient
    from pymongo.errors import ConnectionFailure, ServerSelectionTimeoutError
    MONGODB_AVAILABLE = True
except ImportError:
    MONGODB_AVAILABLE = False
    logger.warning(f"⚠️ pymongo 未安装，MongoDB功能不可用")

# Redis
try:
    import redis
    from redis.exceptions import ConnectionError as RedisConnectionError
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False
    logger.warning(f"⚠️ redis 未安装，Redis功能不可用")


class DatabaseCacheManager:
    """MongoDB + Redis 数据库缓存管理器"""
    
    def __init__(self,
                 mongodb_url: Optional[str] = None,
                 redis_url: Optional[str] = None,
                 mongodb_db: str = "tradingagents",
                 redis_db: int = 0):
        """
        Initialize the database cache manager.

        Args:
            mongodb_url: MongoDB connection URL, default to configuration port
            redis_url: Redis connection URL, default to configuration port
            mongodb_db: MongoDB database name
            redis_db: Redis database number
        """
        mongodb_port = os.getenv("MONGODB_PORT", "27018")
        redis_port = os.getenv("REDIS_PORT", "6380")
        mongodb_password = os.getenv("MONGODB_PASSWORD", "tradingagents123")
        redis_password = os.getenv("REDIS_PASSWORD", "tradingagents123")

        self.mongodb_url = mongodb_url or os.getenv("MONGODB_URL", f"mongodb://admin:{mongodb_password}@localhost:{mongodb_port}")
        self.redis_url = redis_url or os.getenv("REDIS_URL", f"redis://:{redis_password}@localhost:{redis_port}")
        self.mongodb_db_name = mongodb_db
        self.redis_db = redis_db
        
        self.mongodb_client = None
        self.mongodb_db = None
        self.redis_client = None
        
        self._init_mongodb()
        self._init_redis()
        
        logger.info(f"🗄️ Database cache manager initialized")
        logger.error(f"   MongoDB: {'✅ Connected' if self.mongodb_client else '❌ Not connected'}")
        logger.error(f"   Redis: {'✅ Connected' if self.redis_client else '❌ Not connected'}")
    
    def _init_mongodb(self):
        """Initialize MongoDB connection"""
        if not MONGODB_AVAILABLE:
            return
        
        try:
            self.mongodb_client = MongoClient(
                self.mongodb_url,
                serverSelectionTimeoutMS=5000,  # 5 seconds timeout
                connectTimeoutMS=5000
            )
            self.mongodb_client.admin.command('ping')
            self.mongodb_db = self.mongodb_client[self.mongodb_db_name]
            
            self._create_mongodb_indexes()
            
            logger.info(f"✅ MongoDB connection successful: {self.mongodb_url}")
            
        except Exception as e:
            logger.error(f"❌ MongoDB connection failed: {e}")
            self.mongodb_client = None
            self.mongodb_db = None
    
    def _init_redis(self):
        """Initialize Redis connection"""
        if not REDIS_AVAILABLE:
            return
        
        try:
            self.redis_client = redis.from_url(
                self.redis_url,
                db=self.redis_db,
                socket_timeout=5,
                socket_connect_timeout=5,
                decode_responses=True
            )
            self.redis_client.ping()
            
            logger.info(f"✅ Redis connection successful: {self.redis_url}")
            
        except Exception as e:
            logger.error(f"❌ Redis connection failed: {e}")
            self.redis_client = None
    
    def _create_mongodb_indexes(self):
        """Create MongoDB indexes"""
        if self.mongodb_db is None:
            return
        
        try:
            stock_collection = self.mongodb_db.stock_data
            stock_collection.create_index([
                ("symbol", 1),
                ("data_source", 1),
                ("start_date", 1),
                ("end_date", 1)
            ])
            stock_collection.create_index([("created_at", 1)])
            
            news_collection = self.mongodb_db.news_data
            news_collection.create_index([
                ("symbol", 1),
                ("data_source", 1),
                ("date_range", 1)
            ])
            news_collection.create_index([("created_at", 1)])
            
            fundamentals_collection = self.mongodb_db.fundamentals_data
            fundamentals_collection.create_index([
                ("symbol", 1),
                ("data_source", 1),
                ("analysis_date", 1)
            ])
            fundamentals_collection.create_index([("created_at", 1)])
            
            logger.info(f"✅ MongoDB indexes created")
            
        except Exception as e:
            logger.error(f"⚠️ MongoDB index creation failed: {e}")
    
    def _generate_cache_key(self, data_type: str, symbol: str, **kwargs) -> str:
        """Generate cache key"""
        params_str = f"{data_type}_{symbol}"
        for key, value in sorted(kwargs.items()):
            params_str += f"_{key}_{value}"
        
        cache_key = hashlib.md5(params_str.encode()).hexdigest()[:16]
        return f"{data_type}:{symbol}:{cache_key}"
    
    def save_stock_data(self, symbol: str, data: Union[pd.DataFrame, str],
                       start_date: str = None, end_date: str = None,
                       data_source: str = "unknown", market_type: str = None) -> str:
        """
        Save stock data to MongoDB and Redis.
        
        Args:
            symbol: Stock code
            data: Stock data
            start_date: Start date
            end_date: End date
            data_source: Data source
            market_type: Market type (us/china)
        
        Returns:
            cache_key: Cache key
        """
        cache_key = self._generate_cache_key("stock", symbol,
                                           start_date=start_date,
                                           end_date=end_date,
                                           source=data_source)
        
        if market_type is None:
            import re

            if re.match(r'^\d{6}$', symbol):  # 6 digits for A-shares
                market_type = "china"
            else:  # TODO: Add English comment
                market_type = "us"
        
        doc = {
            "_id": cache_key,
            "symbol": symbol,
            "market_type": market_type,
            "data_type": "stock_data",
            "start_date": start_date,
            "end_date": end_date,
            "data_source": data_source,
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow()
        }
        
        if isinstance(data, pd.DataFrame):
            doc["data"] = data.to_json(orient='records', date_format='iso')
            doc["data_format"] = "dataframe_json"
        else:
            doc["data"] = str(data)
            doc["data_format"] = "text"
        
        if self.mongodb_db is not None:
            try:
                collection = self.mongodb_db.stock_data
                collection.replace_one({"_id": cache_key}, doc, upsert=True)
                logger.info(f"💾 Stock data saved to MongoDB: {symbol} -> {cache_key}")
            except Exception as e:
                logger.error(f"⚠️ MongoDB save failed: {e}")
        
        if self.redis_client:
            try:
                redis_data = {
                    "data": doc["data"],
                    "data_format": doc["data_format"],
                    "symbol": symbol,
                    "data_source": data_source,
                    "created_at": doc["created_at"].isoformat()
                }
                self.redis_client.setex(
                    cache_key,
                    6 * 3600,  # 6 hours expiration
                    json.dumps(redis_data, ensure_ascii=False)
                )
                logger.info(f"⚡ Stock data cached to Redis: {symbol} -> {cache_key}")
            except Exception as e:
                logger.error(f"⚠️ Redis cache failed: {e}")
        
        return cache_key
    
    def load_stock_data(self, cache_key: str) -> Optional[Union[pd.DataFrame, str]]:
        """Load stock data from Redis or MongoDB"""
        
        if self.redis_client:
            try:
                redis_data = self.redis_client.get(cache_key)
                if redis_data:
                    data_dict = json.loads(redis_data)
                    logger.info(f"⚡ Data loaded from Redis: {cache_key}")
                    
                    if data_dict["data_format"] == "dataframe_json":
                        return pd.read_json(data_dict["data"], orient='records')
                    else:
                        return data_dict["data"]
            except Exception as e:
                logger.error(f"⚠️ Redis load failed: {e}")
        
        if self.mongodb_db is not None:
            try:
                collection = self.mongodb_db.stock_data
                doc = collection.find_one({"_id": cache_key})
                
                if doc:
                    logger.info(f"💾 Data loaded from MongoDB: {cache_key}")
                    
                    if self.redis_client:
                        try:
                            redis_data = {
                                "data": doc["data"],
                                "data_format": doc["data_format"],
                                "symbol": doc["symbol"],
                                "data_source": doc["data_source"],
                                "created_at": doc["created_at"].isoformat()
                            }
                            self.redis_client.setex(
                                cache_key,
                                6 * 3600,
                                json.dumps(redis_data, ensure_ascii=False)
                            )
                            logger.info(f"⚡ Data synchronized to Redis cache")
                        except Exception as e:
                            logger.error(f"⚠️ Redis synchronization failed: {e}")
                    
                    if doc["data_format"] == "dataframe_json":
                        return pd.read_json(doc["data"], orient='records')
                    else:
                        return doc["data"]
                        
            except Exception as e:
                logger.error(f"⚠️ MongoDB load failed: {e}")
        
        return None
    
    def find_cached_stock_data(self, symbol: str, start_date: str = None,
                              end_date: str = None, data_source: str = None,
                              max_age_hours: int = 6) -> Optional[str]:
        """Find matching cached data"""
        
        exact_key = self._generate_cache_key("stock", symbol,
                                           start_date=start_date,
                                           end_date=end_date,
                                           source=data_source)
        
        if self.redis_client and self.redis_client.exists(exact_key):
            logger.info(f"⚡ Found exact match in Redis: {symbol} -> {exact_key}")
            return exact_key
        
        if self.mongodb_db is not None:
            try:
                collection = self.mongodb_db.stock_data
                cutoff_time = datetime.utcnow() - timedelta(hours=max_age_hours)
                
                query = {
                    "symbol": symbol,
                    "created_at": {"$gte": cutoff_time}
                }
                
                if data_source:
                    query["data_source"] = data_source
                if start_date:
                    query["start_date"] = start_date
                if end_date:
                    query["end_date"] = end_date
                
                doc = collection.find_one(query, sort=[("created_at", -1)])
                
                if doc:
                    cache_key = doc["_id"]
                    logger.info(f"💾 Found match in MongoDB: {symbol} -> {cache_key}")
                    return cache_key
                    
            except Exception as e:
                logger.error(f"⚠️ MongoDB query failed: {e}")
        
        logger.error(f"❌ No valid cache found: {symbol}")
        return None

    def save_news_data(self, symbol: str, news_data: str,
                      start_date: str = None, end_date: str = None,
                      data_source: str = "unknown") -> str:
        """Save news data to MongoDB and Redis"""
        cache_key = self._generate_cache_key("news", symbol,
                                           start_date=start_date,
                                           end_date=end_date,
                                           source=data_source)

        doc = {
            "_id": cache_key,
            "symbol": symbol,
            "data_type": "news_data",
            "date_range": f"{start_date}_{end_date}",
            "start_date": start_date,
            "end_date": end_date,
            "data_source": data_source,
            "data": news_data,
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow()
        }

        if self.mongodb_db is not None:
            try:
                collection = self.mongodb_db.news_data
                collection.replace_one({"_id": cache_key}, doc, upsert=True)
                logger.info(f"📰 News data saved to MongoDB: {symbol} -> {cache_key}")
            except Exception as e:
                logger.error(f"⚠️ MongoDB save failed: {e}")

        if self.redis_client:
            try:
                redis_data = {
                    "data": news_data,
                    "symbol": symbol,
                    "data_source": data_source,
                    "created_at": doc["created_at"].isoformat()
                }
                self.redis_client.setex(
                    cache_key,
                    24 * 3600,  # 24 hours expiration
                    json.dumps(redis_data, ensure_ascii=False)
                )
                logger.info(f"⚡ News data cached to Redis: {symbol} -> {cache_key}")
            except Exception as e:
                logger.error(f"⚠️ Redis cache failed: {e}")

        return cache_key

    def save_fundamentals_data(self, symbol: str, fundamentals_data: str,
                              analysis_date: str = None,
                              data_source: str = "unknown") -> str:
        """Save fundamental data to MongoDB and Redis"""
        if not analysis_date:
            analysis_date = datetime.now().strftime("%Y-%m-%d")

        cache_key = self._generate_cache_key("fundamentals", symbol,
                                           date=analysis_date,
                                           source=data_source)

        doc = {
            "_id": cache_key,
            "symbol": symbol,
            "data_type": "fundamentals_data",
            "analysis_date": analysis_date,
            "data_source": data_source,
            "data": fundamentals_data,
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow()
        }

        if self.mongodb_db is not None:
            try:
                collection = self.mongodb_db.fundamentals_data
                collection.replace_one({"_id": cache_key}, doc, upsert=True)
                logger.info(f"💼 Fundamental data saved to MongoDB: {symbol} -> {cache_key}")
            except Exception as e:
                logger.error(f"⚠️ MongoDB save failed: {e}")

        if self.redis_client:
            try:
                redis_data = {
                    "data": fundamentals_data,
                    "symbol": symbol,
                    "data_source": data_source,
                    "analysis_date": analysis_date,
                    "created_at": doc["created_at"].isoformat()
                }
                self.redis_client.setex(
                    cache_key,
                    24 * 3600,  # 24 hours expiration
                    json.dumps(redis_data, ensure_ascii=False)
                )
                logger.info(f"⚡ Fundamental data cached to Redis: {symbol} -> {cache_key}")
            except Exception as e:
                logger.error(f"⚠️ Redis cache failed: {e}")

        return cache_key

    def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache statistics"""
        stats = {
            "mongodb": {"available": self.mongodb_db is not None, "collections": {}},
            "redis": {"available": self.redis_client is not None, "keys": 0, "memory_usage": "N/A"}
        }

        # MongoDB statistics
        if self.mongodb_db is not None:
            try:
                for collection_name in ["stock_data", "news_data", "fundamentals_data"]:
                    collection = self.mongodb_db[collection_name]
                    count = collection.count_documents({})
                    size = self.mongodb_db.command("collStats", collection_name).get("size", 0)
                    stats["mongodb"]["collections"][collection_name] = {
                        "count": count,
                        "size_mb": round(size / (1024 * 1024), 2)
                    }
            except Exception as e:
                logger.error(f"⚠️ MongoDB statistics retrieval failed: {e}")

        # Redis statistics
        if self.redis_client:
            try:
                info = self.redis_client.info()
                stats["redis"]["keys"] = info.get("db0", {}).get("keys", 0)
                stats["redis"]["memory_usage"] = f"{info.get('used_memory_human', 'N/A')}"
            except Exception as e:
                logger.error(f"⚠️ Redis statistics retrieval failed: {e}")

        return stats

    def clear_old_cache(self, max_age_days: int = 7):
        """Clear expired cache"""
        cutoff_time = datetime.utcnow() - timedelta(days=max_age_days)
        cleared_count = 0

        if self.mongodb_db is not None:
            try:
                for collection_name in ["stock_data", "news_data", "fundamentals_data"]:
                    collection = self.mongodb_db[collection_name]
                    result = collection.delete_many({"created_at": {"$lt": cutoff_time}})
                    cleared_count += result.deleted_count
                    logger.info(f"🧹 MongoDB {collection_name} cleared {result.deleted_count} records")
            except Exception as e:
                logger.error(f"⚠️ MongoDB cleanup failed: {e}")

        # Redis expires automatically, no need to manually clear
        logger.info(f"🧹 Total {cleared_count} expired records cleared")
        return cleared_count

    def close(self):
        """Close database connections"""
        if self.mongodb_client:
            self.mongodb_client.close()
            logger.info(f"🔒 MongoDB connection closed")

        if self.redis_client:
            self.redis_client.close()
            logger.info(f"🔒 Redis connection closed")


# TODO: Add English comment
_db_cache_instance = None

def get_db_cache() -> DatabaseCacheManager:
    """Get the global database cache instance"""
    global _db_cache_instance
    if _db_cache_instance is None:
        _db_cache_instance = DatabaseCacheManager()
    return _db_cache_instance
