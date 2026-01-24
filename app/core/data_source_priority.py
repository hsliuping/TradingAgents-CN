"""
数据源优先级管理模块

提供统一的数据源优先级获取函数，避免代码重复
"""
from typing import List
import logging

logger = logging.getLogger(__name__)


async def get_enabled_data_sources_async(market_category: str = "a_shares") -> List[str]:
    """
    获取启用的数据源列表（异步版本）
    
    从数据库读取数据源配置，按优先级从高到低排序
    不进行硬编码过滤，完全遵循数据库配置
    
    Args:
        market_category: 市场分类 (a_shares, us_stocks, hk_stocks)
        
    Returns:
        启用的数据源列表，按优先级从高到低排序
        例如: ['local', 'tushare', 'akshare', 'baostock']
    """
    try:
        from app.core.unified_config import UnifiedConfigManager
        
        config = UnifiedConfigManager()
        data_source_configs = await config.get_data_source_configs_async()
        
        # 提取启用的数据源（已按优先级从高到低排序）
        # 不再硬编码过滤，直接使用数据库中的配置
        enabled_sources = [
            ds.type.lower() for ds in data_source_configs
            if ds.enabled
        ]
        
        if enabled_sources:
            logger.info(f"✅ [数据源优先级] {market_category}: {enabled_sources}")
            return enabled_sources
        else:
            # 回退到默认配置
            default_sources = ['local', 'tushare', 'akshare', 'baostock']
            logger.warning(f"⚠️ [数据源优先级] 数据库中没有启用的数据源，使用默认配置: {default_sources}")
            return default_sources
            
    except Exception as e:
        # 发生异常时回退到默认配置
        default_sources = ['local', 'tushare', 'akshare', 'baostock']
        logger.error(f"❌ [数据源优先级] 获取失败: {e}，使用默认配置: {default_sources}")
        return default_sources


def get_enabled_data_sources_sync(market_category: str = "a_shares") -> List[str]:
    """
    获取启用的数据源列表（同步版本）
    
    从数据库读取数据源配置，按优先级从高到低排序
    不进行硬编码过滤，完全遵循数据库配置
    
    Args:
        market_category: 市场分类 (a_shares, us_stocks, hk_stocks)
        
    Returns:
        启用的数据源列表，按优先级从高到低排序
        例如: ['local', 'tushare', 'akshare', 'baostock']
    """
    try:
        from app.core.unified_config import UnifiedConfigManager
        
        config = UnifiedConfigManager()
        data_source_configs = config.get_data_source_configs()
        
        # 提取启用的数据源（已按优先级从高到低排序）
        # 不再硬编码过滤，直接使用数据库中的配置
        enabled_sources = [
            ds.type.lower() for ds in data_source_configs
            if ds.enabled
        ]
        
        if enabled_sources:
            logger.info(f"✅ [数据源优先级] {market_category}: {enabled_sources}")
            return enabled_sources
        else:
            # 回退到默认配置
            default_sources = ['local', 'tushare', 'akshare', 'baostock']
            logger.warning(f"⚠️ [数据源优先级] 数据库中没有启用的数据源，使用默认配置: {default_sources}")
            return default_sources
            
    except Exception as e:
        # 发生异常时回退到默认配置
        default_sources = ['local', 'tushare', 'akshare', 'baostock']
        logger.error(f"❌ [数据源优先级] 获取失败: {e}，使用默认配置: {default_sources}")
        return default_sources


async def get_preferred_data_source_async(market_category: str = "a_shares") -> str:
    """
    获取优先级最高的数据源（异步版本）
    
    Args:
        market_category: 市场分类 (a_shares, us_stocks, hk_stocks)
        
    Returns:
        优先级最高的数据源名称，例如: 'local'
    """
    enabled_sources = await get_enabled_data_sources_async(market_category)
    preferred_source = enabled_sources[0] if enabled_sources else 'tushare'
    logger.info(f"📊 [优先数据源] {market_category}: {preferred_source}")
    return preferred_source


def get_preferred_data_source_sync(market_category: str = "a_shares") -> str:
    """
    获取优先级最高的数据源（同步版本）
    
    Args:
        market_category: 市场分类 (a_shares, us_stocks, hk_stocks)
        
    Returns:
        优先级最高的数据源名称，例如: 'local'
    """
    enabled_sources = get_enabled_data_sources_sync(market_category)
    preferred_source = enabled_sources[0] if enabled_sources else 'tushare'
    logger.info(f"📊 [优先数据源] {market_category}: {preferred_source}")
    return preferred_source

