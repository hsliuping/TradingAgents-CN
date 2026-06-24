"""
状态 Reducer 函数

用于 LangGraph StateGraph 的 Annotated reducer，处理并发节点执行时的状态合并。

Reducer 规则：
- keep_non_empty: 字符串/标量字段，保留非空值（新值优先）
- merge_dict: 字典字段，智能合并（特殊处理历史字段）
- keep_latest_list: 列表字段，始终采用最新值
"""

from typing import Any


def keep_non_empty(left: Any, right: Any) -> Any:
    """保留非空值，优先使用 right（新值）

    用于字符串/标量字段，避免并行节点执行时空值覆盖已有结果。
    """
    if right:
        return right
    return left if left else right


def merge_dict(left: dict, right: dict) -> dict:
    """智能合并两个字典，用于处理并发更新

    特殊处理：对于辩论状态的历史字段（*_history），
    优先保留非空值，避免被空字符串覆盖。
    """
    if left is None:
        return right
    if right is None:
        return left

    result = left.copy()

    # 需要特殊处理的历史字段
    history_fields = [
        'bull_history', 'bear_history', 'history',
        'risky_history', 'safe_history', 'neutral_history'
    ]

    for key, value in right.items():
        # 对于历史字段，只有当新值非空时才更新
        if key in history_fields:
            old_value = result.get(key, "")
            # 如果新值为空但旧值非空，保留旧值
            if not value and old_value:
                continue
            # 如果两者都非空，保留更长的那个（包含更多内容）
            if value and old_value and len(old_value) > len(value):
                continue
        result[key] = value

    return result


def keep_latest_list(left: Any, right: Any) -> Any:
    """列表字段始终采用最新值，允许用空列表显式清空消息历史。"""
    if right is None:
        return left
    return right
