#!/usr/bin/env python3
"""
集成缓存管理器
结合原有缓存系统和新的自适应数据库支持
提供向后兼容的接口
"""

import os
import logging
from pathlib import Path
from typing import Any, Dict, Optional, Union
import pandas as pd

# 导入统一日志系统
from tradingagents.utils.logging_init import setup_dataflow_logging

# 导入原有缓存系统
from .file_cache import StockDataCache

# 导入自适应缓存系统
try:
    from .adaptive import AdaptiveCacheSystem
    from tradingagents.config.database_manager import get_database_manager
    ADAPTIVE_CACHE_AVAILABLE = True
except ImportError as e:
    ADAPTIVE_CACHE_AVAILABLE = False
    import logging
    logging.getLogger(__name__).debug(f"自适应缓存不可用: {e}")

class IntegratedCacheManager:
    """集成缓存管理器 - 智能选择缓存策略"""
    
    def __init__(self, cache_dir: str = None):
        self.logger = setup_dataflow_logging()
        
        # 初始化原有缓存系统（作为备用）
        self.legacy_cache = StockDataCache(cache_dir)
        
        # 尝试初始化自适应缓存系统
        self.adaptive_cache = None
        self.use_adaptive = False
        
        if ADAPTIVE_CACHE_AVAILABLE:
            try:
                self.adaptive_cache = AdaptiveCacheSystem(cache_dir)
                self.db_manager = get_database_manager()
                self.use_adaptive = True
                self.logger.info("✅ 自适应缓存系统已启用")
            except Exception as e:
                self.logger.warning(f"自适应缓存系统初始化失败，使用传统缓存: {e}")
                self.use_adaptive = False
        else:
            self.logger.info("自适应缓存系统不可用，使用传统文件缓存")
        
        # 显示当前配置
        self._log_cache_status()
    
    def _log_cache_status(self):
        """记录缓存状态"""
        if self.use_adaptive:
            backend = self.adaptive_cache.primary_backend
            mongodb_available = self.db_manager.is_mongodb_available()
            redis_available = self.db_manager.is_redis_available()
            
            self.logger.info(f"📊 缓存配置:")
            self.logger.info(f"  主要后端: {backend}")
            self.logger.info(f"  MongoDB: {'✅ 可用' if mongodb_available else '❌ 不可用'}")
            self.logger.info(f"  Redis: {'✅ 可用' if redis_available else '❌ 不可用'}")
            self.logger.info(f"  降级支持: {'✅ 启用' if self.adaptive_cache.fallback_enabled else '❌ 禁用'}")
        else:
            self.logger.info("📁 使用传统文件缓存系统")
    
    def save_stock_data(self, symbol: str, data: Any, start_date: str = None, 
                       end_date: str = None, data_source: str = "default") -> str:
        """
        保存股票数据到缓存
        
        Args:
            symbol: 股票代码
            data: 股票数据
            start_date: 开始日期
            end_date: 结束日期
            data_source: 数据源
            
        Returns:
            缓存键
        """
        if self.use_adaptive:
            # 使用自适应缓存系统
            return self.adaptive_cache.save_data(
                symbol=symbol,
                data=data,
                start_date=start_date or "",
                end_date=end_date or "",
                data_source=data_source,
                data_type="stock_data"
            )
        else:
            # 使用传统缓存系统
            return self.legacy_cache.save_stock_data(
                symbol=symbol,
                data=data,
                start_date=start_date,
                end_date=end_date,
                data_source=data_source
            )
    
    def load_stock_data(self, cache_key: str) -> Optional[Any]:
        """
        从缓存加载股票数据
        
        Args:
            cache_key: 缓存键
            
        Returns:
            股票数据或None
        """
        if self.use_adaptive:
            # 使用自适应缓存系统
            return self.adaptive_cache.load_data(cache_key)
        else:
            # 使用传统缓存系统
            return self.legacy_cache.load_stock_data(cache_key)
    
    def find_cached_stock_data(self, symbol: str, start_date: str = None, 
                              end_date: str = None, data_source: str = "default") -> Optional[str]:
        """
        查找缓存的股票数据
        
        Args:
            symbol: 股票代码
            start_date: 开始日期
            end_date: 结束日期
            data_source: 数据源
            
        Returns:
            缓存键或None
        """
        if self.use_adaptive:
            # 使用自适应缓存系统
            return self.adaptive_cache.find_cached_data(
                symbol=symbol,
                start_date=start_date or "",
                end_date=end_date or "",
                data_source=data_source,
                data_type="stock_data"
            )
        else:
            # 使用传统缓存系统
            return self.legacy_cache.find_cached_stock_data(
                symbol=symbol,
                start_date=start_date,
                end_date=end_date,
                data_source=data_source
            )
    
    def save_news_data(self, symbol: str, data: Any, data_source: str = "default") -> str:
        """保存新闻数据"""
        if self.use_adaptive:
            return self.adaptive_cache.save_data(
                symbol=symbol,
                data=data,
                data_source=data_source,
                data_type="news_data"
            )
        else:
            return self.legacy_cache.save_news_data(symbol, data, data_source)
    
    def load_news_data(self, cache_key: str) -> Optional[Any]:
        """加载新闻数据"""
        if self.use_adaptive:
            return self.adaptive_cache.load_data(cache_key)
        else:
            return self.legacy_cache.load_news_data(cache_key)
    
    def save_fundamentals_data(self, symbol: str, data: Any, data_source: str = "default") -> str:
        """保存基本面数据"""
        if self.use_adaptive:
            return self.adaptive_cache.save_data(
                symbol=symbol,
                data=data,
                data_source=data_source,
                data_type="fundamentals_data"
            )
        else:
            return self.legacy_cache.save_fundamentals_data(symbol, data, data_source)
    
    def load_fundamentals_data(self, cache_key: str) -> Optional[Any]:
        """加载基本面数据"""
        if self.use_adaptive:
            return self.adaptive_cache.load_data(cache_key)
        else:
            return self.legacy_cache.load_fundamentals_data(cache_key)

    def find_cached_fundamentals_data(self, symbol: str, data_source: str = None,
                                     max_age_hours: int = None) -> Optional[str]:
        """
        查找匹配的基本面缓存数据

        Args:
            symbol: 股票代码
            data_source: 数据源（如 "openai", "finnhub"）
            max_age_hours: 最大缓存时间（小时），None时使用智能配置

        Returns:
            cache_key: 如果找到有效缓存则返回缓存键，否则返回None
        """
        if self.use_adaptive:
            # 自适应缓存暂不支持查找功能，降级到文件缓存
            return self.legacy_cache.find_cached_fundamentals_data(symbol, data_source, max_age_hours)
        else:
            return self.legacy_cache.find_cached_fundamentals_data(symbol, data_source, max_age_hours)

    def is_fundamentals_cache_valid(self, symbol: str, data_source: str = None,
                                   max_age_hours: int = None) -> bool:
        """
        检查基本面缓存是否有效

        Args:
            symbol: 股票代码
            data_source: 数据源
            max_age_hours: 最大缓存时间（小时）

        Returns:
            bool: 缓存是否有效
        """
        cache_key = self.find_cached_fundamentals_data(symbol, data_source, max_age_hours)
        return cache_key is not None

    # ========== 分析报告缓存 ==========

    def save_analysis_report(self, report_type: str, report_data: str,
                            symbol: str = None, trade_date: str = None,
                            data_source: str = "llm") -> str:
        """
        保存分析报告到缓存

        Args:
            report_type: 报告类型（如 "sector_report", "index_report"）
            report_data: 报告内容
            symbol: 股票代码（大盘分析可以为空）
            trade_date: 交易日期
            data_source: 数据源（默认为 "llm"）

        Returns:
            cache_key: 缓存键
        """
        # 构建缓存键：report_type_symbol_trade_date_data_source
        key_parts = [report_type]
        if symbol:
            key_parts.append(symbol)
        if trade_date:
            key_parts.append(trade_date.replace("-", ""))
        key_parts.append(data_source)
        cache_key = "_".join(key_parts)

        # 🔍 调试日志：记录保存参数
        self.logger.debug(f"💾 [IntegratedCache] save_analysis_report: report_type={report_type}, "
                          f"symbol={symbol}, trade_date={trade_date}, use_adaptive={self.use_adaptive}")

        if self.use_adaptive:
            return self.adaptive_cache.save_data(
                symbol=symbol or "market",
                data=report_data,
                start_date=trade_date or "",
                end_date=trade_date or "",
                data_source=data_source,
                data_type=report_type
            )
        else:
            # 使用文件缓存的通用保存方法
            return self.legacy_cache.save_fundamentals_data(
                symbol=cache_key,
                fundamentals_data=report_data,
                data_source=data_source
            )

    def load_analysis_report(self, cache_key: str) -> Optional[str]:
        """
        从缓存加载分析报告

        Args:
            cache_key: 缓存键

        Returns:
            报告内容，如果缓存不存在或失效则返回 None
        """
        if self.use_adaptive:
            return self.adaptive_cache.load_data(cache_key)
        else:
            return self.legacy_cache.load_fundamentals_data(cache_key)

    def find_cached_analysis_report(self, report_type: str, symbol: str = None,
                                   trade_date: str = None, data_source: str = "llm",
                                   max_age_hours: int = 12) -> Optional[str]:
        """
        查找缓存的分析报告

        Args:
            report_type: 报告类型（如 "sector_report", "index_report"）
            symbol: 股票代码（大盘分析可以为空）
            trade_date: 交易日期
            data_source: 数据源
            max_age_hours: 最大缓存时间（小时），默认12小时

        Returns:
            cache_key: 如果找到有效缓存则返回缓存键，否则返回 None
        """
        if self.use_adaptive:
            # 使用自适应缓存的查找方法
            # 参数匹配 save_analysis_report 的保存方式
            cache_key = self.adaptive_cache.find_cached_data(
                symbol=symbol or "market",
                start_date=trade_date or "",
                end_date=trade_date or "",
                data_source=data_source,
                data_type=report_type  # report_type 作为 data_type
            )
            if cache_key:
                self.logger.info(f"🎯 找到{report_type}缓存: {symbol or 'market'} @ {trade_date}")
                return cache_key
            else:
                self.logger.info(f"📭 未找到{report_type}缓存: {symbol or 'market'} @ {trade_date}")
                return None
        else:
            # 对于文件缓存，构建缓存键并查找
            key_parts = [report_type]
            if symbol:
                key_parts.append(symbol)
            if trade_date:
                key_parts.append(trade_date.replace("-", ""))
            key_parts.append(data_source)
            cache_key = "_".join(key_parts)
            return self.legacy_cache.find_cached_fundamentals_data(cache_key, data_source, max_age_hours)

    def get_cache_stats(self) -> Dict[str, Any]:
        """获取缓存统计信息"""
        if self.use_adaptive:
            # 获取自适应缓存统计（已经是标准格式）
            stats = self.adaptive_cache.get_cache_stats()

            # 添加缓存系统信息
            stats['cache_system'] = 'adaptive'

            # 确保后端信息存在
            if 'backend_info' not in stats:
                stats['backend_info'] = {}

            stats['backend_info']['database_available'] = self.db_manager.is_database_available()
            stats['backend_info']['mongodb_available'] = self.db_manager.is_mongodb_available()
            stats['backend_info']['redis_available'] = self.db_manager.is_redis_available()

            return stats
        else:
            # 返回传统缓存统计（已经是标准格式）
            stats = self.legacy_cache.get_cache_stats()

            # 添加缓存系统信息
            stats['cache_system'] = 'legacy'

            # 确保后端信息存在
            if 'backend_info' not in stats:
                stats['backend_info'] = {}

            stats['backend_info']['database_available'] = False
            stats['backend_info']['mongodb_available'] = False
            stats['backend_info']['redis_available'] = False

            return stats
    
    def clear_expired_cache(self):
        """清理过期缓存"""
        if self.use_adaptive:
            self.adaptive_cache.clear_expired_cache()

        # 总是清理传统缓存
        self.legacy_cache.clear_expired_cache()

    def clear_old_cache(self, max_age_days: int = 7):
        """
        清理过期缓存（兼容旧接口）

        Args:
            max_age_days: 清理多少天前的缓存，0表示清理所有缓存

        Returns:
            清理的记录数
        """
        cleared_count = 0

        # 1. 清理 Redis 缓存
        if self.use_adaptive and self.db_manager.is_redis_available():
            try:
                redis_client = self.db_manager.get_redis_client()
                if max_age_days == 0:
                    # 清空所有缓存
                    redis_client.flushdb()
                    self.logger.info(f"🧹 Redis 缓存已全部清空")
                else:
                    # Redis 会自动过期，这里只记录日志
                    self.logger.info(f"🧹 Redis 缓存会自动过期（TTL机制）")
            except Exception as e:
                self.logger.error(f"⚠️ Redis 缓存清理失败: {e}")

        # 2. 清理 MongoDB 缓存
        if self.use_adaptive and self.db_manager.is_mongodb_available():
            try:
                from datetime import datetime, timedelta
                from zoneinfo import ZoneInfo
                from tradingagents.config.runtime_settings import get_timezone_name

                mongodb_db = self.db_manager.get_mongodb_db()

                if max_age_days == 0:
                    # 清空所有缓存集合
                    for collection_name in ["stock_data", "news_data", "fundamentals_data"]:
                        result = mongodb_db[collection_name].delete_many({})
                        cleared_count += result.deleted_count
                        self.logger.info(f"🧹 MongoDB {collection_name} 清空了 {result.deleted_count} 条记录")
                else:
                    # 清理过期数据
                    cutoff_time = datetime.now(ZoneInfo(get_timezone_name())) - timedelta(days=max_age_days)
                    for collection_name in ["stock_data", "news_data", "fundamentals_data"]:
                        result = mongodb_db[collection_name].delete_many({"created_at": {"$lt": cutoff_time}})
                        cleared_count += result.deleted_count
                        self.logger.info(f"🧹 MongoDB {collection_name} 清理了 {result.deleted_count} 条记录")
            except Exception as e:
                self.logger.error(f"⚠️ MongoDB 缓存清理失败: {e}")

        # 3. 清理文件缓存
        try:
            file_cleared = self.legacy_cache.clear_old_cache(max_age_days)
            # 文件缓存可能返回 None，需要处理
            if file_cleared is not None:
                cleared_count += file_cleared
                self.logger.info(f"🧹 文件缓存清理了 {file_cleared} 个文件")
            else:
                self.logger.info(f"🧹 文件缓存清理完成（返回值为None）")
        except Exception as e:
            self.logger.error(f"⚠️ 文件缓存清理失败: {e}")

        self.logger.info(f"🧹 总共清理了 {cleared_count} 条缓存记录")
        return cleared_count
    
    def get_cache_backend_info(self) -> Dict[str, Any]:
        """获取缓存后端信息"""
        if self.use_adaptive:
            return {
                "system": "adaptive",
                "primary_backend": self.adaptive_cache.primary_backend,
                "fallback_enabled": self.adaptive_cache.fallback_enabled,
                "mongodb_available": self.db_manager.is_mongodb_available(),
                "redis_available": self.db_manager.is_redis_available()
            }
        else:
            return {
                "system": "legacy",
                "primary_backend": "file",
                "fallback_enabled": False,
                "mongodb_available": False,
                "redis_available": False
            }
    
    def is_database_available(self) -> bool:
        """检查数据库是否可用"""
        if self.use_adaptive:
            return self.db_manager.is_database_available()
        return False
    
    def get_performance_mode(self) -> str:
        """获取性能模式"""
        if not self.use_adaptive:
            return "基础模式 (文件缓存)"
        
        mongodb_available = self.db_manager.is_mongodb_available()
        redis_available = self.db_manager.is_redis_available()
        
        if redis_available and mongodb_available:
            return "高性能模式 (Redis + MongoDB + 文件)"
        elif redis_available:
            return "快速模式 (Redis + 文件)"
        elif mongodb_available:
            return "持久化模式 (MongoDB + 文件)"
        else:
            return "标准模式 (智能文件缓存)"


# 全局集成缓存管理器实例
_integrated_cache = None

def get_cache() -> IntegratedCacheManager:
    """获取全局集成缓存管理器实例"""
    global _integrated_cache
    if _integrated_cache is None:
        _integrated_cache = IntegratedCacheManager()
    return _integrated_cache

# 向后兼容的函数
def get_stock_cache():
    """向后兼容：获取股票缓存"""
    return get_cache()

def create_cache_manager(cache_dir: str = None):
    """向后兼容：创建缓存管理器"""
    return IntegratedCacheManager(cache_dir)
