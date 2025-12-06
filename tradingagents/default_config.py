import os
from pathlib import Path

from tradingagents.utils.runtime_paths import (
    get_cache_dir,
    get_data_dir,
    get_results_dir,
    get_runtime_base_dir,
    resolve_path,
)

_RUNTIME_BASE = get_runtime_base_dir()


def _resolve_env_path(env_key: str, default_path: Path) -> str:
    """优先使用环境变量，未设置时使用统一的 runtime 目录"""
    env_val = os.getenv(env_key)
    if env_val:
        return str(resolve_path(env_val, _RUNTIME_BASE))
    return str(default_path)


DEFAULT_CONFIG = {
    "project_dir": os.path.abspath(os.path.join(os.path.dirname(__file__), ".")),
    "results_dir": _resolve_env_path("TRADINGAGENTS_RESULTS_DIR", get_results_dir(_RUNTIME_BASE)),
    "data_dir": _resolve_env_path("TRADINGAGENTS_DATA_DIR", get_data_dir(_RUNTIME_BASE)),
    "data_cache_dir": _resolve_env_path(
        "TRADINGAGENTS_CACHE_DIR",
        get_cache_dir(_RUNTIME_BASE) / "dataflows",
    ),
    # LLM settings
    "llm_provider": "openai",
    "deep_think_llm": "o4-mini",
    "quick_think_llm": "gpt-4o-mini",
    "backend_url": "https://api.openai.com/v1",
    # Debate and discussion settings
    "max_debate_rounds": 1,
    "max_risk_discuss_rounds": 1,
    "max_recur_limit": 100,
    # Tool settings - 从环境变量读取，提供默认值
    "online_tools": os.getenv("ONLINE_TOOLS_ENABLED", "false").lower() == "true",
    "online_news": os.getenv("ONLINE_NEWS_ENABLED", "true").lower() == "true", 
    "realtime_data": os.getenv("REALTIME_DATA_ENABLED", "false").lower() == "true",

    # Note: Database and cache configuration is now managed by .env file and config.database_manager
    # No database/cache settings in default config to avoid configuration conflicts
}
