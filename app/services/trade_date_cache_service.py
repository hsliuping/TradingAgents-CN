"""
最后交易日期缓存服务
使用Redis缓存各数据源的最后有效交易日期，避免频繁调用API
"""
import json
import logging
from datetime import datetime, timedelta
from typing import Optional, Dict
from app.core.config import settings

logger = logging.getLogger(__name__)

# Redis键名
CACHE_KEY_PREFIX = "trade_date:latest"
CACHE_KEY_TUSHARE = f"{CACHE_KEY_PREFIX}:tushare"
CACHE_KEY_AKSHARE = f"{CACHE_KEY_PREFIX}:akshare"
CACHE_KEY_BAOSTOCK = f"{CACHE_KEY_PREFIX}:baostock"


class TradeDateCacheService:
    """最后交易日期缓存服务"""
    
    def __init__(self):
        self._redis_sync = None
        self._redis_async = None
    
    @property
    def redis(self):
        """延迟获取同步Redis客户端（用于同步方法）"""
        if self._redis_sync is None:
            try:
                # 使用同步Redis客户端，避免事件循环问题
                import redis
                
                # 从配置获取Redis URL
                redis_url = settings.REDIS_URL
                
                # 使用redis.from_url自动解析URL，更可靠
                try:
                    self._redis_sync = redis.from_url(
                        redis_url,
                        decode_responses=True,
                        socket_connect_timeout=5,
                        socket_timeout=10
                    )
                    # 测试连接
                    self._redis_sync.ping()
                    logger.debug("✅ 同步Redis客户端连接成功（使用from_url）")
                except Exception as e1:
                    # 如果from_url失败，尝试手动解析
                    logger.debug(f"from_url失败，尝试手动解析: {e1}")
                    
                    # 解析URL: redis://[:password@]host[:port][/db]
                    if not redis_url.startswith('redis://'):
                        redis_url = f"redis://{redis_url}"
                    
                    url_parts = redis_url.replace('redis://', '').split('@')
                    if len(url_parts) == 2:
                        # 有密码
                        password = url_parts[0].split(':', 1)[-1] if ':' in url_parts[0] else url_parts[0]
                        host_part = url_parts[1]
                    else:
                        password = None
                        host_part = url_parts[0]
                    
                    # 解析主机、端口和数据库
                    if '/' in host_part:
                        host_port, db_str = host_part.rsplit('/', 1)
                        db = int(db_str) if db_str.isdigit() else 0
                    else:
                        host_port = host_part
                        db = 0
                    
                    if ':' in host_port:
                        host, port_str = host_port.split(':', 1)
                        port = int(port_str) if port_str.isdigit() else 6379
                    else:
                        host = host_port if host_port else 'localhost'
                        port = 6379
                    
                    # 确保host不为空
                    if not host:
                        host = 'localhost'
                    
                    # 创建同步Redis客户端
                    if password:
                        self._redis_sync = redis.Redis(
                            host=host,
                            port=port,
                            password=password,
                            db=db,
                            decode_responses=True,
                            socket_connect_timeout=5,
                            socket_timeout=10
                        )
                    else:
                        self._redis_sync = redis.Redis(
                            host=host,
                            port=port,
                            db=db,
                            decode_responses=True,
                            socket_connect_timeout=5,
                            socket_timeout=10
                        )
                    
                    # 测试连接
                    self._redis_sync.ping()
                    logger.debug("✅ 同步Redis客户端连接成功（手动解析）")
            except Exception as e:
                logger.warning(f"⚠️  同步Redis客户端初始化失败: {e}，将直接调用API获取交易日期", exc_info=True)
                self._redis_sync = None
        return self._redis_sync
    
    @property
    def redis_async(self):
        """延迟获取异步Redis客户端（用于异步方法）"""
        if self._redis_async is None:
            try:
                from app.core.redis_client import get_redis
                self._redis_async = get_redis()
            except RuntimeError:
                logger.warning("异步Redis客户端未初始化，异步方法可能不可用")
                self._redis_async = None
        return self._redis_async
    
    def _is_today(self, date_str: str) -> bool:
        """判断日期字符串是否是今天"""
        try:
            cache_date = datetime.strptime(date_str, "%Y-%m-%d")
            today = datetime.now().date()
            return cache_date.date() == today
        except Exception:
            return False
    
    def get_cached_trade_date_sync(self, source: str) -> Optional[str]:
        """
        从缓存获取最后交易日期（同步版本）
        
        Args:
            source: 数据源名称 ('tushare', 'akshare', 'baostock')
            
        Returns:
            如果缓存存在且是当天更新的，返回交易日期（YYYYMMDD格式），否则返回None
        """
        if not self.redis:
            return None
        
        try:
            cache_key = self._get_cache_key(source)
            cached_data = self.redis.get(cache_key)
            
            if cached_data:
                data = json.loads(cached_data)
                update_date = data.get("update_date")
                trade_date = data.get("trade_date")
                
                # 判断是否是当天更新的
                if self._is_today(update_date):
                    logger.debug(f"✅ [{source}] 从缓存获取最后交易日期: {trade_date} (更新于: {update_date})")
                    return trade_date
                else:
                    logger.debug(f"⚠️  [{source}] 缓存已过期 (更新于: {update_date})，需要重新获取")
                    return None
            
            return None
        except Exception as e:
            logger.warning(f"⚠️  [{source}] 读取缓存失败: {e}")
            return None
    
    async def _get_cached_trade_date_async(self, source: str) -> Optional[str]:
        """异步获取缓存"""
        if not self.redis_async:
            return None
        
        try:
            cache_key = self._get_cache_key(source)
            cached_data = await self.redis_async.get(cache_key)
            
            if cached_data:
                data = json.loads(cached_data)
                update_date = data.get("update_date")
                trade_date = data.get("trade_date")
                
                # 判断是否是当天更新的
                if self._is_today(update_date):
                    logger.debug(f"✅ [{source}] 从缓存获取最后交易日期: {trade_date} (更新于: {update_date})")
                    return trade_date
                else:
                    logger.debug(f"⚠️  [{source}] 缓存已过期 (更新于: {update_date})，需要重新获取")
                    return None
            
            return None
        except Exception as e:
            logger.warning(f"⚠️  [{source}] 读取缓存失败: {e}")
            return None
    
    async def get_cached_trade_date(self, source: str) -> Optional[str]:
        """
        从缓存获取最后交易日期（异步版本）
        
        Args:
            source: 数据源名称 ('tushare', 'akshare', 'baostock')
            
        Returns:
            如果缓存存在且是当天更新的，返回交易日期（YYYYMMDD格式），否则返回None
        """
        return await self._get_cached_trade_date_async(source)
    
    def set_cached_trade_date_sync(self, source: str, trade_date: str) -> bool:
        """
        将最后交易日期保存到缓存（同步版本）
        
        Args:
            source: 数据源名称 ('tushare', 'akshare', 'baostock')
            trade_date: 交易日期（YYYYMMDD格式）
            
        Returns:
            是否保存成功
        """
        if not self.redis:
            return False
        
        try:
            cache_key = self._get_cache_key(source)
            today = datetime.now().strftime("%Y-%m-%d")
            
            data = {
                "trade_date": trade_date,
                "update_date": today,
                "source": source
            }
            
            # 保存到Redis，设置TTL为7天（防止缓存永久存在）
            self.redis.setex(
                cache_key,
                7 * 24 * 3600,  # 7天TTL
                json.dumps(data, ensure_ascii=False)
            )
            
            logger.info(f"✅ [{source}] 已缓存最后交易日期: {trade_date} (更新于: {today})")
            return True
        except Exception as e:
            logger.warning(f"⚠️  [{source}] 保存缓存失败: {e}")
            return False
    
    async def _set_cached_trade_date_async(self, source: str, trade_date: str) -> bool:
        """异步保存缓存"""
        if not self.redis_async:
            return False
        
        try:
            cache_key = self._get_cache_key(source)
            today = datetime.now().strftime("%Y-%m-%d")
            
            data = {
                "trade_date": trade_date,
                "update_date": today,
                "source": source
            }
            
            # 保存到Redis，设置TTL为7天（防止缓存永久存在）
            await self.redis_async.setex(
                cache_key,
                7 * 24 * 3600,  # 7天TTL
                json.dumps(data, ensure_ascii=False)
            )
            
            logger.info(f"✅ [{source}] 已缓存最后交易日期: {trade_date} (更新于: {today})")
            return True
        except Exception as e:
            logger.warning(f"⚠️  [{source}] 保存缓存失败: {e}")
            return False
    
    async def set_cached_trade_date(self, source: str, trade_date: str) -> bool:
        """
        将最后交易日期保存到缓存（异步版本）
        
        Args:
            source: 数据源名称 ('tushare', 'akshare', 'baostock')
            trade_date: 交易日期（YYYYMMDD格式）
            
        Returns:
            是否保存成功
        """
        return await self._set_cached_trade_date_async(source, trade_date)
    
    def _get_cache_key(self, source: str) -> str:
        """获取缓存键名"""
        key_map = {
            "tushare": CACHE_KEY_TUSHARE,
            "akshare": CACHE_KEY_AKSHARE,
            "baostock": CACHE_KEY_BAOSTOCK,
        }
        return key_map.get(source.lower(), f"{CACHE_KEY_PREFIX}:{source.lower()}")
    
    def clear_cache_sync(self, source: Optional[str] = None) -> bool:
        """
        清除缓存（同步版本）
        
        Args:
            source: 数据源名称，如果为None则清除所有缓存
            
        Returns:
            是否清除成功
        """
        if not self.redis:
            return False
        
        try:
            if source:
                cache_key = self._get_cache_key(source)
                self.redis.delete(cache_key)
                logger.info(f"✅ [{source}] 缓存已清除")
            else:
                # 清除所有交易日期缓存
                keys = [CACHE_KEY_TUSHARE, CACHE_KEY_AKSHARE, CACHE_KEY_BAOSTOCK]
                for key in keys:
                    self.redis.delete(key)
                logger.info("✅ 所有交易日期缓存已清除")
            return True
        except Exception as e:
            logger.warning(f"⚠️  清除缓存失败: {e}")
            return False
    
    async def _clear_cache_async(self, source: Optional[str] = None) -> bool:
        """异步清除缓存"""
        if not self.redis_async:
            return False
        
        try:
            if source:
                cache_key = self._get_cache_key(source)
                await self.redis_async.delete(cache_key)
                logger.info(f"✅ [{source}] 缓存已清除")
            else:
                # 清除所有交易日期缓存
                keys = [CACHE_KEY_TUSHARE, CACHE_KEY_AKSHARE, CACHE_KEY_BAOSTOCK]
                for key in keys:
                    await self.redis_async.delete(key)
                logger.info("✅ 所有交易日期缓存已清除")
            return True
        except Exception as e:
            logger.warning(f"⚠️  清除缓存失败: {e}")
            return False
    
    async def clear_cache(self, source: Optional[str] = None) -> bool:
        """
        清除缓存（异步版本）
        
        Args:
            source: 数据源名称，如果为None则清除所有缓存
            
        Returns:
            是否清除成功
        """
        return await self._clear_cache_async(source)


# 单例实例
_trade_date_cache_service: Optional[TradeDateCacheService] = None


def get_trade_date_cache_service() -> TradeDateCacheService:
    """获取交易日期缓存服务单例"""
    global _trade_date_cache_service
    if _trade_date_cache_service is None:
        _trade_date_cache_service = TradeDateCacheService()
    return _trade_date_cache_service
