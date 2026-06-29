"""Skill 运行时异步桥接与结果标准化。"""

from __future__ import annotations

import asyncio
from threading import Thread
from typing import Any, Dict


def run_async_in_sync(coro: Any) -> Any:
    """在同步上下文中安全执行协程。"""
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)

    outcome: Dict[str, Any] = {}

    def _runner() -> None:
        try:
            outcome["result"] = asyncio.run(coro)
        except Exception as exc:
            outcome["error"] = exc

    thread = Thread(target=_runner, daemon=True)
    thread.start()
    thread.join()
    if "error" in outcome:
        raise outcome["error"]
    return outcome.get("result")


def normalize_tabular_result(data: Any) -> Any:
    """将 DataFrame 等表格对象标准化为可序列化结果。"""
    if data is None:
        return None
    if hasattr(data, "to_dict"):
        try:
            tabular = data
            if hasattr(tabular, "reset_index") and hasattr(tabular, "index"):
                index_name = getattr(tabular.index, "name", None)
                index_type = type(tabular.index).__name__
                if index_name or index_type != "RangeIndex":
                    tabular = tabular.reset_index()
            return tabular.to_dict("records")
        except TypeError:
            return data.to_dict()
    return data