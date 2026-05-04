from app.core.data_source_priority import _merge_grouped_enabled_sources
from app.models.config import DataSourceConfig, DataSourceType


def _build_config(name: str, source_type: DataSourceType, priority: int, enabled: bool = True) -> DataSourceConfig:
    return DataSourceConfig(
        name=name,
        type=source_type,
        enabled=enabled,
        priority=priority,
    )


def test_category_disable_excludes_source_from_current_market():
    configs = [
        _build_config("Tushare", DataSourceType.TUSHARE, 30),
        _build_config("AKShare", DataSourceType.AKSHARE, 20),
        _build_config("BaoStock", DataSourceType.BAOSTOCK, 10),
    ]
    groupings = [
        {"data_source_name": "baostock", "enabled": False, "priority": 100},
        {"data_source_name": "tushare", "enabled": True, "priority": 90},
    ]

    assert _merge_grouped_enabled_sources(configs, groupings) == ["tushare", "akshare"]


def test_global_disable_overrides_grouping_enable():
    configs = [
        _build_config("Tushare", DataSourceType.TUSHARE, 30),
        _build_config("BaoStock", DataSourceType.BAOSTOCK, 10, enabled=False),
    ]
    groupings = [
        {"data_source_name": "baostock", "enabled": True, "priority": 100},
        {"data_source_name": "tushare", "enabled": True, "priority": 90},
    ]

    assert _merge_grouped_enabled_sources(configs, groupings) == ["tushare"]


def test_ungrouped_enabled_sources_fall_back_to_global_priority():
    configs = [
        _build_config("Tushare", DataSourceType.TUSHARE, 30),
        _build_config("AKShare", DataSourceType.AKSHARE, 20),
        _build_config("Local", DataSourceType.LOCAL, 40),
    ]
    groupings = [
        {"data_source_name": "local", "enabled": True, "priority": 100},
    ]

    assert _merge_grouped_enabled_sources(configs, groupings) == ["local", "tushare", "akshare"]