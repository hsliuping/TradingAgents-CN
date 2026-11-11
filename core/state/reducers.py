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


def keep_latest_bool(left: Any, right: Any) -> Any:
    """布尔字段取最新值（None 不覆盖）

    布尔没有「空值」概念：False 是合法取值。若沿用 keep_non_empty，
    一旦某节点写入 True，后续节点写 False 会被当成空值丢弃，
    _condition_result / _skip_* 等开关将永久停留在 True（门控恒不跳段）。
    """
    if right is None:
        return left
    return right


def merge_dict(left: dict, right: dict) -> dict:
    """智能合并两个字典，用于处理并发更新

    特殊处理：对于辩论状态的历史字段（*_history），
    优先保留非空值，避免被空字符串覆盖。
    """
    if left is None:
        return right
    if right is None:
        return left

    # 防御：节点异常降级时可能把失败说明文本（str）写入 dict 字段
    # （如 risk_profile_card / scenario_simulation），此时保留左侧已有值，
    # 避免状态合并阶段崩溃中断整个工作流（宁缺勿造：宁可丢注入不炸流程）
    if not isinstance(right, dict):
        return left if isinstance(left, dict) else right
    if not isinstance(left, dict):
        return right

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
