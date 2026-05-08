"""
数据源优先级管理模块

提供统一的数据源优先级获取函数，避免代码重复
"""
from typing import Any, Dict, Iterable, List
import logging

logger = logging.getLogger(__name__)


DEFAULT_ENABLED_SOURCES = ['local', 'tushare', 'akshare', 'baostock']


def _normalize_source_name(value: Any) -> str:
    """将数据源名称或枚举值统一归一化为小写字符串。"""
    if value is None:
        return ""
    return str(getattr(value, "value", value)).strip().lower()


def _build_global_source_index(data_source_configs: Iterable[Any]) -> Dict[str, Any]:
    """为全局启用的数据源建立 name/type 双索引。"""
    source_index: Dict[str, Any] = {}
    for ds_config in data_source_configs:
        aliases = {
            _normalize_source_name(getattr(ds_config, "name", "")),
            _normalize_source_name(getattr(ds_config, "type", "")),
        }
        for alias in aliases:
            if alias:
                source_index[alias] = ds_config
    return source_index


def _extract_grouping_field(grouping: Any, field_name: str, default: Any = None) -> Any:
    """兼容 dict / Pydantic 对象两种分组记录访问方式。"""
    if isinstance(grouping, dict):
        return grouping.get(field_name, default)
    return getattr(grouping, field_name, default)


def _merge_grouped_enabled_sources(data_source_configs: Iterable[Any], groupings: Iterable[Any]) -> List[str]:
    """
    合并全局数据源配置和市场分类分组配置。

    规则：
    1. 全局 enabled=False 的数据源永不返回。
    2. 当前 market_category 下分组 enabled=False 的数据源只对该分类禁用。
    3. 分组内已声明的数据源按分组 priority 排序。
    4. 未分组的数据源按全局 priority 追加，避免旧数据缺少分组时直接丢失。
    """
    enabled_configs = [ds for ds in data_source_configs if getattr(ds, "enabled", False)]
    enabled_configs.sort(key=lambda item: getattr(item, "priority", 0), reverse=True)

    if not enabled_configs:
        return []

    source_index = _build_global_source_index(enabled_configs)
    grouped_entries = list(groupings or [])
    grouped_entries.sort(
        key=lambda item: _extract_grouping_field(item, "priority", 0),
        reverse=True,
    )

    selected_sources: List[str] = []
    handled_sources = set()

    for grouping in grouped_entries:
        grouping_name = _normalize_source_name(
            _extract_grouping_field(grouping, "data_source_name", "")
        )
        if not grouping_name:
            continue

        ds_config = source_index.get(grouping_name)
        if not ds_config:
            continue

        source_type = _normalize_source_name(getattr(ds_config, "type", ""))
        if not source_type:
            continue

        handled_sources.add(source_type)
        if not _extract_grouping_field(grouping, "enabled", False):
            continue

        if source_type not in selected_sources:
            selected_sources.append(source_type)

    for ds_config in enabled_configs:
        source_type = _normalize_source_name(getattr(ds_config, "type", ""))
        if not source_type or source_type in handled_sources:
            continue
        selected_sources.append(source_type)

    return selected_sources


async def _get_market_groupings_async(market_category: str) -> List[Dict[str, Any]]:
    """读取指定市场分类的数据源分组配置。"""
    if not market_category:
        return []

    try:
        from app.core.database import get_mongo_db

        db = get_mongo_db()
        return await db.datasource_groupings.find(
            {"market_category_id": market_category}
        ).sort("priority", -1).to_list(length=None)
    except Exception as exc:
        logger.warning(f"⚠️ [数据源优先级] 读取分组配置失败({market_category}): {exc}")
        return []


def _get_market_groupings_sync(market_category: str) -> List[Dict[str, Any]]:
    """同步读取指定市场分类的数据源分组配置。"""
    if not market_category:
        return []

    try:
        from app.core.database import get_mongo_db_sync

        db = get_mongo_db_sync()
        cursor = db.datasource_groupings.find({"market_category_id": market_category}).sort("priority", -1)
        return list(cursor)
    except Exception as exc:
        logger.warning(f"⚠️ [数据源优先级] 同步读取分组配置失败({market_category}): {exc}")
        return []


async def get_enabled_data_sources_async(market_category: str = "a_shares") -> List[str]:
    """
    获取启用的数据源列表（异步版本）。

    从数据库读取数据源配置，按优先级从高到低排序。
    不进行硬编码过滤，完全遵循数据库配置。
    """
    try:
        from app.core.unified_config import UnifiedConfigManager

        config = UnifiedConfigManager()
        data_source_configs = await config.get_data_source_configs_async()

        groupings = await _get_market_groupings_async(market_category)
        enabled_sources = _merge_grouped_enabled_sources(data_source_configs, groupings)

        if enabled_sources:
            logger.info(f"✅ [数据源优先级] {market_category}: {enabled_sources}")
            return enabled_sources

        default_sources = DEFAULT_ENABLED_SOURCES
        logger.warning(f"⚠️ [数据源优先级] 数据库中没有启用的数据源，使用默认配置: {default_sources}")
        return default_sources

    except Exception as e:
        default_sources = DEFAULT_ENABLED_SOURCES
        logger.error(f"❌ [数据源优先级] 获取失败: {e}，使用默认配置: {default_sources}")
        return default_sources


async def get_available_data_sources_async(market_category: str = "a_shares") -> List[str]:
    """
    获取启用且当前可用的数据源列表（异步版本）。

    返回顺序遵循数据库中的优先级配置，仅保留当前 adapter.is_available() 为 True 的数据源。
    """
    enabled_sources = await get_enabled_data_sources_async(market_category)

    try:
        from app.services.data_sources.manager import DataSourceManager

        manager = DataSourceManager()
        available_adapters = manager.get_available_adapters()
        available_names = {_normalize_source_name(adapter.name) for adapter in available_adapters}
        available_sources = [source for source in enabled_sources if source in available_names]

        if available_sources:
            logger.info(f"✅ [可用数据源] {market_category}: {available_sources}")
            return available_sources

        logger.warning(f"⚠️ [可用数据源] {market_category}: 没有启用且可用的数据源")
        return []

    except Exception as e:
        logger.error(f"❌ [可用数据源] 获取失败: {e}")
        return []


def get_available_data_sources_sync(market_category: str = "a_shares") -> List[str]:
    """
    获取启用且当前可用的数据源列表（同步版本）。
    """
    enabled_sources = get_enabled_data_sources_sync(market_category)

    try:
        from app.services.data_sources.manager import DataSourceManager

        manager = DataSourceManager()
        available_adapters = manager.get_available_adapters()
        available_names = {_normalize_source_name(adapter.name) for adapter in available_adapters}
        available_sources = [source for source in enabled_sources if source in available_names]

        if available_sources:
            logger.info(f"✅ [可用数据源] {market_category}: {available_sources}")
            return available_sources

        logger.warning(f"⚠️ [可用数据源] {market_category}: 没有启用且可用的数据源")
        return []

    except Exception as e:
        logger.error(f"❌ [可用数据源] 获取失败: {e}")
        return []


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

        groupings = _get_market_groupings_sync(market_category)
        enabled_sources = _merge_grouped_enabled_sources(data_source_configs, groupings)
        
        if enabled_sources:
            logger.info(f"✅ [数据源优先级] {market_category}: {enabled_sources}")
            return enabled_sources
        else:
            # 回退到默认配置
            default_sources = DEFAULT_ENABLED_SOURCES
            logger.warning(f"⚠️ [数据源优先级] 数据库中没有启用的数据源，使用默认配置: {default_sources}")
            return default_sources
            
    except Exception as e:
        # 发生异常时回退到默认配置
        default_sources = DEFAULT_ENABLED_SOURCES
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
    available_sources = await get_available_data_sources_async(market_category)
    preferred_source = available_sources[0] if available_sources else 'tushare'
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
    available_sources = get_available_data_sources_sync(market_category)
    preferred_source = available_sources[0] if available_sources else 'tushare'
    logger.info(f"📊 [优先数据源] {market_category}: {preferred_source}")
    return preferred_source

