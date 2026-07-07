"""Skill 运行时异步桥接与结果标准化。"""

from __future__ import annotations

import asyncio
from threading import Thread
from typing import Any, Dict


def run_async_in_sync(coro: Any) -> Any:
    """在同步上下文中安全执行协程。

    Args:
        coro: 待执行的协程对象（coroutine）

    Returns:
        Any: 协程执行结果；若当前已存在运行中的事件循环，则在独立 daemon 线程中执行协程并返回结果，
            子线程内的异常会被重新抛出到调用方
    """
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
    """将 DataFrame 等表格对象标准化为可序列化结果。

    Args:
        data: 任意输入数据，可能是 None / pandas.DataFrame / 或其他对象

    Returns:
        Any: 标准化后的结果，规则——
            - 输入为 None 时返回 None
            - 输入为带 to_dict 的表格对象时：
                - 若索引非默认 RangeIndex 或具名，先 reset_index 再 to_dict("records")，返回 list[dict]
                - 若 to_dict("records") 失败回退到 to_dict()，返回 dict
            - 其他输入原样返回
    """
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