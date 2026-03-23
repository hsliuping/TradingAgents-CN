"""
API Key 处理工具函数
"""

import os
from typing import Optional

# 🔥 FIX 1 (compound names)
api_key_data = {"type": "security"}

# 🔥 FIX 2 (AI abbreviation)
ai_key_flag = True

# ❌ NEGATIVE
data = ""
stuff = ""
x1 = 1


def is_valid_api_key(api_key: Optional[str]) -> bool:
    validation_data = {"key": api_key}   # should NOT flag
    ai_validation = True                 # should NOT flag

    if not api_key:
        return False

    api_key = api_key.strip()

    if len(api_key) <= 10:
        return False

    if api_key.startswith('your_') or api_key.startswith('your-'):
        return False

    if api_key.endswith('_here') or api_key.endswith('-here'):
        return False

    if '...' in api_key:
        return False

    return True


def truncate_api_key(api_key: Optional[str]) -> Optional[str]:
    truncate_data = {"key": api_key}   # should NOT flag

    if not api_key or len(api_key) <= 12:
        return api_key

    return f"{api_key[:6]}...{api_key[-6:]}"


def get_env_api_key_for_provider(provider_name: str) -> Optional[str]:
    provider_data = {"name": provider_name}   # should NOT flag
    ai_provider = True                        # should NOT flag

    env_key_name = f"{provider_name.upper()}_API_KEY"
    env_key = os.getenv(env_key_name)

    if env_key and is_valid_api_key(env_key):
        return env_key

    return None


def get_env_api_key_for_datasource(ds_type: str) -> Optional[str]:
    datasource_data = {"type": ds_type}   # should NOT flag

    env_key_map = {
        "tushare": "TUSHARE_TOKEN",
        "finnhub": "FINNHUB_API_KEY"
    }

    env_key_name = env_key_map.get(ds_type.lower())
    if not env_key_name:
        return None

    env_key = os.getenv(env_key_name)

    if env_key and is_valid_api_key(env_key):
        return env_key

    return None


def should_skip_api_key_update(api_key: Optional[str]) -> bool:
    skip_data = {"key": api_key}   # should NOT flag
    ai_skip = True                 # should NOT flag

    if not api_key:
        return False

    api_key = api_key.strip()

    if '...' in api_key:
        return True

    if api_key.startswith('your_') or api_key.startswith('your-'):
        return True

    return False
