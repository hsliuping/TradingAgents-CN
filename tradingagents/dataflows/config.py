"""
历史 dataflows 配置接口兼容层。

旧测试和脚本仍依赖 ``tradingagents.dataflows.config``，
这里桥接到当前 ``tradingagents.config.config_manager``。
"""

from __future__ import annotations

import os
from typing import Any, Dict

from tradingagents.config.config_manager import config_manager


def initialize_config() -> Dict[str, Any]:
    """初始化兼容配置，并确保相关目录存在。"""
    env_data_dir = os.getenv("TRADINGAGENTS_DATA_DIR")
    if env_data_dir:
        config_manager.set_data_dir(env_data_dir)

    config_manager.ensure_directories_exist()
    settings = config_manager.load_settings()
    settings.setdefault("data_dir", config_manager.get_data_dir())
    return settings


def get_data_dir() -> str:
    """返回当前数据目录。"""
    return config_manager.get_data_dir()


def set_data_dir(data_dir: str) -> str:
    """设置数据目录并返回新的目录值。"""
    config_manager.set_data_dir(data_dir)
    config_manager.ensure_directories_exist()
    return config_manager.get_data_dir()


def get_config() -> Dict[str, Any]:
    """返回兼容配置字典。"""
    settings = config_manager.load_settings()
    settings.setdefault("data_dir", config_manager.get_data_dir())
    return settings


def set_config(config: Dict[str, Any]) -> Dict[str, Any]:
    """保存兼容配置字典。"""
    if not isinstance(config, dict):
        raise TypeError("config must be a dict")

    current = config_manager.load_settings()
    current.update(config)

    if current.get("data_dir"):
        current["cache_dir"] = os.path.join(current["data_dir"], "cache")

    config_manager.save_settings(current)
    config_manager.ensure_directories_exist()
    return current

