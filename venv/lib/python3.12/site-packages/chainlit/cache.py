import importlib.util
import os
import threading
from typing import Any

from chainlit.config import config
from chainlit.logger import logger


def init_lc_cache():
    use_cache = config.project.cache is True and config.run.no_cache is False

    if use_cache and importlib.util.find_spec("langchain") is not None:
        from langchain.cache import SQLiteCache
        from langchain.globals import set_llm_cache

        if config.project.lc_cache_path is not None:
            set_llm_cache(SQLiteCache(database_path=config.project.lc_cache_path))

            if not os.path.exists(config.project.lc_cache_path):
                logger.info(
                    f"LangChain cache created at: {config.project.lc_cache_path}"
                )


_cache: dict[tuple, Any] = {}
_cache_lock = threading.Lock()


def cache(func):
    def wrapper(*args, **kwargs):
        # Create a cache key based on the function name, arguments, and keyword arguments
        cache_key = (
            (func.__name__,) + args + tuple((k, v) for k, v in sorted(kwargs.items()))
        )

        with _cache_lock:
            # Check if the result is already in the cache
            if cache_key not in _cache:
                # If not, call the function and store the result in the cache
                _cache[cache_key] = func(*args, **kwargs)

        return _cache[cache_key]

    return wrapper
