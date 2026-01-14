#!/usr/bin/env python3
"""
自适应缓存系统
根据数据库可用性自动选择最佳缓存策略
"""

import os
import json
import pickle
import hashlib
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, Optional, Union
import pandas as pd

from tradingagents.config.database_manager import get_database_manager

class AdaptiveCacheSystem:
    """自适应缓存系统"""
    
    def __init__(self, cache_dir: str = None):
        self.logger = logging.getLogger(__name__)

        # 获取数据库管理器
        self.db_manager = get_database_manager()

        # 设置缓存目录
        if cache_dir is None:
            # 默认使用 data/cache 目录
            cache_dir = "data/cache"
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        
        # 获取配置
        self.config = self.db_manager.get_config()
        self.cache_config = self.config["cache"]
        
        # 初始化缓存后端
        self.primary_backend = self.cache_config["primary_backend"]
        self.fallback_enabled = self.cache_config["fallback_enabled"]
        
        self.logger.info(f"自适应缓存系统初始化 - 主要后端: {self.primary_backend}")
    
    def _get_cache_key(self, symbol: str, start_date: str = "", end_date: str = "", 
                      data_source: str = "default", data_type: str = "stock_data") -> str:
        """生成缓存键"""
        key_data = f"{symbol}_{start_date}_{end_date}_{data_source}_{data_type}"
        return hashlib.md5(key_data.encode()).hexdigest()
    
    def _get_ttl_seconds(self, symbol: str, data_type: str = "stock_data") -> int:
        """获取TTL秒数"""
        # 判断市场类型
        if len(symbol) == 6 and symbol.isdigit():
            market = "china"
        else:
            market = "us"

        # 获取TTL配置
        ttl_key = f"{market}_{data_type}"
        ttl_seconds = self.cache_config["ttl_settings"].get(ttl_key, 7200)

        # 确保返回整数（配置文件中可能是字符串）
        try:
            return int(ttl_seconds)
        except (ValueError, TypeError):
            self.logger.warning(f"⚠️ TTL配置无效: {ttl_key}={ttl_seconds}, 使用默认值7200秒")
            return 7200
    
    def _is_cache_valid(self, cache_time: datetime, ttl_seconds: int) -> bool:
        """检查缓存是否有效"""
        if cache_time is None:
            return False
        
        expiry_time = cache_time + timedelta(seconds=ttl_seconds)
        return datetime.now() < expiry_time
    
    def _save_to_file(self, cache_key: str, data: Any, metadata: Dict) -> bool:
        """保存到文件缓存"""
        try:
            cache_file = self.cache_dir / f"{cache_key}.pkl"
            cache_data = {
                'data': data,
                'metadata': metadata,
                'timestamp': datetime.now(),
                'backend': 'file'
            }
            
            with open(cache_file, 'wb') as f:
                pickle.dump(cache_data, f)
            
            self.logger.debug(f"文件缓存保存成功: {cache_key}")
            return True
            
        except Exception as e:
            self.logger.error(f"文件缓存保存失败: {e}")
            return False
    
    def _load_from_file(self, cache_key: str) -> Optional[Dict]:
        """从文件缓存加载"""
        try:
            cache_file = self.cache_dir / f"{cache_key}.pkl"
            if not cache_file.exists():
                return None
            
            with open(cache_file, 'rb') as f:
                cache_data = pickle.load(f)
            
            self.logger.debug(f"文件缓存加载成功: {cache_key}")
            return cache_data
            
        except Exception as e:
            self.logger.error(f"文件缓存加载失败: {e}")
            return None
    
    def _save_to_redis(self, cache_key: str, data: Any, metadata: Dict, ttl_seconds: int) -> bool:
        """保存到Redis缓存"""
        redis_client = self.db_manager.get_redis_client()
        if not redis_client:
            return False
        
        try:
            cache_data = {
                'data': data,
                'metadata': metadata,
                'timestamp': datetime.now().isoformat(),
                'backend': 'redis'
            }
            
            serialized_data = pickle.dumps(cache_data)
            redis_client.setex(cache_key, ttl_seconds, serialized_data)
            
            self.logger.debug(f"Redis缓存保存成功: {cache_key}")
            return True
            
        except Exception as e:
            self.logger.error(f"Redis缓存保存失败: {e}")
            return False
    
    def _load_from_redis(self, cache_key: str) -> Optional[Dict]:
        """从Redis缓存加载"""
        redis_client = self.db_manager.get_redis_client()
        if not redis_client:
            return None
        
        try:
            serialized_data = redis_client.get(cache_key)
            if not serialized_data:
                return None
            
            cache_data = pickle.loads(serialized_data)
            
            # 转换时间戳
            if isinstance(cache_data['timestamp'], str):
                cache_data['timestamp'] = datetime.fromisoformat(cache_data['timestamp'])
            
            self.logger.debug(f"Redis缓存加载成功: {cache_key}")
            return cache_data
            
        except Exception as e:
            self.logger.error(f"Redis缓存加载失败: {e}")
            return None
    
    def _save_to_mongodb(self, cache_key: str, data: Any, metadata: Dict, ttl_seconds: int) -> bool:
        """保存到MongoDB缓存"""
        mongodb_client = self.db_manager.get_mongodb_client()
        if not mongodb_client:
            return False
        
        try:
            db = mongodb_client.tradingagents
            collection = db.cache
            
            # 序列化数据
            if isinstance(data, pd.DataFrame):
                serialized_data = data.to_json()
                data_type = 'dataframe'
            else:
                serialized_data = pickle.dumps(data).hex()
                data_type = 'pickle'
            
            cache_doc = {
                '_id': cache_key,
                'data': serialized_data,
                'data_type': data_type,
                'metadata': metadata,
                'timestamp': datetime.now(),
                'expires_at': datetime.now() + timedelta(seconds=ttl_seconds),
                'backend': 'mongodb'
            }
            
            collection.replace_one({'_id': cache_key}, cache_doc, upsert=True)
            
            self.logger.debug(f"MongoDB缓存保存成功: {cache_key}")
            return True
            
        except Exception as e:
            self.logger.error(f"MongoDB缓存保存失败: {e}")
            return False
    
    def _load_from_mongodb(self, cache_key: str) -> Optional[Dict]:
        """从MongoDB缓存加载"""
        mongodb_client = self.db_manager.get_mongodb_client()
        if not mongodb_client:
            return None
        
        try:
            db = mongodb_client.tradingagents
            collection = db.cache
            
            doc = collection.find_one({'_id': cache_key})
            if not doc:
                return None
            
            # 检查是否过期
            if doc.get('expires_at') and doc['expires_at'] < datetime.now():
                collection.delete_one({'_id': cache_key})
                return None
            
            # 反序列化数据
            if doc['data_type'] == 'dataframe':
                data = pd.read_json(doc['data'])
            else:
                data = pickle.loads(bytes.fromhex(doc['data']))
            
            cache_data = {
                'data': data,
                'metadata': doc['metadata'],
                'timestamp': doc['timestamp'],
                'backend': 'mongodb'
            }
            
            self.logger.debug(f"MongoDB缓存加载成功: {cache_key}")
            return cache_data
            
        except Exception as e:
            self.logger.error(f"MongoDB缓存加载失败: {e}")
            return None
    
    def save_data(self, symbol: str, data: Any, start_date: str = "", end_date: str = "",
                  data_source: str = "default", data_type: str = "stock_data") -> str:
        """保存数据到缓存"""
        # 生成缓存键
        cache_key = self._get_cache_key(symbol, start_date, end_date, data_source, data_type)

        # 准备元数据
        metadata = {
            'symbol': symbol,
            'start_date': start_date,
            'end_date': end_date,
            'data_source': data_source,
            'data_type': data_type
        }

        # 获取TTL
        ttl_seconds = self._get_ttl_seconds(symbol, data_type)

        # 🔍 调试日志：记录TTL类型
        self.logger.debug(f"💾 [AdaptiveCache] save_data: symbol={symbol}, data_type={data_type}, "
                          f"ttl_seconds={ttl_seconds} (type={type(ttl_seconds).__name__}), "
                          f"primary_backend={self.primary_backend}")

        # 根据主要后端保存
        success = False

        if self.primary_backend == "redis":
            success = self._save_to_redis(cache_key, data, metadata, ttl_seconds)
        elif self.primary_backend == "mongodb":
            success = self._save_to_mongodb(cache_key, data, metadata, ttl_seconds)
        elif self.primary_backend == "file":
            success = self._save_to_file(cache_key, data, metadata)

        # 如果主要后端失败，使用降级策略
        if not success and self.fallback_enabled:
            self.logger.warning(f"主要后端({self.primary_backend})保存失败，使用文件缓存降级")
            success = self._save_to_file(cache_key, data, metadata)

        if success:
            self.logger.info(f"数据缓存成功: {symbol} -> {cache_key} (后端: {self.primary_backend})")
        else:
            self.logger.error(f"数据缓存失败: {symbol}")

        return cache_key
    
    def load_data(self, cache_key: str) -> Optional[Any]:
        """从缓存加载数据"""
        cache_data = None
        
        # 根据主要后端加载
        if self.primary_backend == "redis":
            cache_data = self._load_from_redis(cache_key)
        elif self.primary_backend == "mongodb":
            cache_data = self._load_from_mongodb(cache_key)
        elif self.primary_backend == "file":
            cache_data = self._load_from_file(cache_key)
        
        # 如果主要后端失败，尝试降级
        if not cache_data and self.fallback_enabled:
            self.logger.debug(f"主要后端({self.primary_backend})加载失败，尝试文件缓存")
            cache_data = self._load_from_file(cache_key)
        
        if not cache_data:
            return None
        
        # 检查缓存是否有效（仅对文件缓存，数据库缓存有自己的TTL机制）
        if cache_data.get('backend') == 'file':
            symbol = cache_data['metadata'].get('symbol', '')
            data_type = cache_data['metadata'].get('data_type', 'stock_data')
            ttl_seconds = self._get_ttl_seconds(symbol, data_type)
            
            if not self._is_cache_valid(cache_data['timestamp'], ttl_seconds):
                self.logger.debug(f"文件缓存已过期: {cache_key}")
                return None
        
        return cache_data['data']
    
    def find_cached_data(self, symbol: str, start_date: str = "", end_date: str = "", 
                        data_source: str = "default", data_type: str = "stock_data") -> Optional[str]:
        """查找缓存的数据"""
        cache_key = self._get_cache_key(symbol, start_date, end_date, data_source, data_type)
        
        # 检查缓存是否存在且有效
        if self.load_data(cache_key) is not None:
            return cache_key
        
        return None
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """获取缓存统计信息"""
        # 标准统计格式
        stats = {
            'total_files': 0,
            'stock_data_count': 0,
            'news_count': 0,
            'fundamentals_count': 0,
            'total_size': 0,  # 字节
            'total_size_mb': 0,  # MB
            'skipped_count': 0
        }

        # 后端信息
        backend_info = {
            'primary_backend': self.primary_backend,
            'fallback_enabled': self.fallback_enabled,
            'database_available': self.db_manager.is_database_available(),
            'mongodb_available': self.db_manager.is_mongodb_available(),
            'redis_available': self.db_manager.is_redis_available(),
            'file_cache_directory': str(self.cache_dir),
            'file_cache_count': len(list(self.cache_dir.glob("*.pkl"))),
        }

        total_size_bytes = 0

        # MongoDB统计
        mongodb_client = self.db_manager.get_mongodb_client()
        if mongodb_client:
            try:
                db = mongodb_client.tradingagents

                # 统计各个集合
                for collection_name in ["stock_data", "news_data", "fundamentals_data"]:
                    if collection_name in db.list_collection_names():
                        collection = db[collection_name]
                        count = collection.count_documents({})

                        # 获取集合大小
                        try:
                            coll_stats = db.command("collStats", collection_name)
                            size = coll_stats.get("size", 0)
                            total_size_bytes += size
                        except:
                            pass

                        stats['total_files'] += count

                        # 按类型分类
                        if collection_name == "stock_data":
                            stats['stock_data_count'] += count
                        elif collection_name == "news_data":
                            stats['news_count'] += count
                        elif collection_name == "fundamentals_data":
                            stats['fundamentals_count'] += count

                backend_info['mongodb_cache_count'] = stats['total_files']
            except:
                backend_info['mongodb_status'] = 'Error'

        # Redis统计
        redis_client = self.db_manager.get_redis_client()
        if redis_client:
            try:
                redis_info = redis_client.info()
                backend_info['redis_memory_used'] = redis_info.get('used_memory_human', 'N/A')
                backend_info['redis_keys'] = redis_client.dbsize()
            except:
                backend_info['redis_status'] = 'Error'

        # 文件缓存统计
        if self.primary_backend == 'file' or self.fallback_enabled:
            for pkl_file in self.cache_dir.glob("*.pkl"):
                try:
                    total_size_bytes += pkl_file.stat().st_size
                except:
                    pass

        # 设置总大小
        stats['total_size'] = total_size_bytes
        stats['total_size_mb'] = round(total_size_bytes / (1024 * 1024), 2)

        # 添加后端详细信息
        stats['backend_info'] = backend_info

        return stats
    
    def clear_expired_cache(self):
        """清理过期缓存"""
        self.logger.info("开始清理过期缓存...")
        
        # 清理文件缓存
        cleared_files = 0
        for cache_file in self.cache_dir.glob("*.pkl"):
            try:
                with open(cache_file, 'rb') as f:
                    cache_data = pickle.load(f)
                
                symbol = cache_data['metadata'].get('symbol', '')
                data_type = cache_data['metadata'].get('data_type', 'stock_data')
                ttl_seconds = self._get_ttl_seconds(symbol, data_type)
                
                if not self._is_cache_valid(cache_data['timestamp'], ttl_seconds):
                    cache_file.unlink()
                    cleared_files += 1
                    
            except Exception as e:
                self.logger.error(f"清理缓存文件失败 {cache_file}: {e}")
        
        self.logger.info(f"文件缓存清理完成，删除 {cleared_files} 个过期文件")
        
        # MongoDB会自动清理过期文档（通过expires_at字段）
        # Redis会自动清理过期键


# 全局缓存系统实例
_cache_system = None

def get_cache_system() -> AdaptiveCacheSystem:
    """获取全局自适应缓存系统实例"""
    global _cache_system
    if _cache_system is None:
        _cache_system = AdaptiveCacheSystem()
    return _cache_system
