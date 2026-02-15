"""
股票池解析
支持 DSL 格式 (universe 在顶层) 和 config 格式 (universe 或 symbols)
"""
from typing import Any, Dict, List


def get_universe_symbols(dsl_or_config: Dict[str, Any]) -> List[str]:
    """
    从 DSL 或 config 解析股票池
    - DSL: {"universe": {"type": "static", "symbols": [...]}, "config": {...}}
    - Config: {"universe": {"type": "static", "symbols": [...]}} 或 {"symbols": [...]}
    - 当 type=index 时，由主平台预填 symbols 后传入
    """
    # 顶层 symbols（config 格式）
    symbols = dsl_or_config.get("symbols")
    if symbols:
        return symbols

    uni = dsl_or_config.get("universe") or {}
    if not isinstance(uni, dict):
        return []

    t = uni.get("type", "static")
    if t == "static":
        return uni.get("symbols", []) or []
    if t == "index":
        # 主平台预填 symbols 后传入
        return uni.get("symbols", []) or []
    # dividend_screen 等暂不支持
    return []
