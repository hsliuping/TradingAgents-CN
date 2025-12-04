"""
Utility functions for screening evaluation and DSL parsing.
Extracted from ScreeningService to separate concerns while keeping API unchanged.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Iterable
import pandas as pd
import numpy as np


def collect_fields_from_conditions(node: Dict[str, Any], allowed_fields: Iterable[str]) -> List[str]:
    if not node:
        return []
    if node.get("op") == "group" or "children" in node:
        fields: List[str] = []
        for c in node.get("children", []):
            fields.extend(collect_fields_from_conditions(c, allowed_fields))
        # de-duplicate keep order
        return list(dict.fromkeys(fields))
    f = node.get("field")
    rf = node.get("right_field")
    out: List[str] = []
    if isinstance(f, str) and f in allowed_fields:
        out.append(f)
    if isinstance(rf, str) and rf in allowed_fields:
        out.append(rf)
    return out


def evaluate_fund_conditions(snap: Dict[str, Any], node: Dict[str, Any], fund_fields: Iterable[str]) -> bool:
    if not node:
        return True
    # group
    if node.get("op") == "group" or "children" in node:
        logic = (node.get("logic") or "AND").upper()
        children = node.get("children", [])
        flags = [evaluate_fund_conditions(snap, c, fund_fields) for c in children]
        return all(flags) if logic == "AND" else any(flags)
    # leaf
    field = node.get("field")
    op = node.get("op")
    if field not in fund_fields:
        return True  # 非基本面字段在纯基本面路径中跳过
    left = snap.get(field)
    if left is None:
        return False
    if node.get("right_field"):
        rf = node.get("right_field")
        right = snap.get(rf)
    else:
        right = node.get("value")
    try:
        if op == ">":
            return float(left) > float(right)
        if op == "<":
            return float(left) < float(right)
        if op == ">=":
            return float(left) >= float(right)
        if op == "<=":
            return float(left) <= float(right)
        if op == "==":
            return float(left) == float(right)
        if op == "!=":
            return float(left) != float(right)
        if op == "between":
            lo_hi = right if isinstance(right, (list, tuple)) else (None, None)
            lo, hi = lo_hi if isinstance(lo_hi, (list, tuple)) and len(lo_hi) == 2 else (None, None)
            if lo is None or hi is None:
                return False
            v = float(left)
            return float(lo) <= v <= float(hi)
    except Exception:
        return False
    return False


def evaluate_conditions(
    df: pd.DataFrame,
    node: Dict[str, Any],
    allowed_fields: Iterable[str],
    allowed_ops: Iterable[str],
) -> bool:
    if not node:
        return True
    # group 节点
    if node.get("op") == "group" or "children" in node:
        logic = (node.get("logic") or "AND").upper()
        children = node.get("children", [])
        if logic not in {"AND", "OR"}:
            logic = "AND"
        flags = [evaluate_conditions(df, c, allowed_fields, allowed_ops) for c in children]
        return all(flags) if logic == "AND" else any(flags)

    # 叶子：字段比较
    field = node.get("field")
    op = node.get("op")
    if field not in allowed_fields or op not in set(allowed_ops):
        return False

    # 需要最近两行（交叉）
    if op in {"cross_up", "cross_down"}:
        right_field = node.get("right_field")
        if right_field not in allowed_fields:
            return False
        if len(df) < 2:
            return False
        t0 = df.iloc[-1]
        t1 = df.iloc[-2]
        a0 = t0.get(field)
        a1 = t1.get(field)
        b0 = t0.get(right_field)
        b1 = t1.get(right_field)
        if any(pd.isna([a0, a1, b0, b1])):
            return False
        if op == "cross_up":
            return (a1 <= b1) and (a0 > b0)
        else:
            return (a1 >= b1) and (a0 < b0)

    # 普通比较：最近一行
    t0 = df.iloc[-1]
    left = t0.get(field)
    if pd.isna(left):
        return False

    if node.get("right_field"):
        rf = node.get("right_field")
        if rf not in allowed_fields:
            return False
        right = t0.get(rf)
    else:
        right = node.get("value")

    try:
        if op == ">":
            return float(left) > float(right)
        if op == "<":
            return float(left) < float(right)
        if op == ">=":
            return float(left) >= float(right)
        if op == "<=":
            return float(left) <= float(right)
        if op == "==":
            return float(left) == float(right)
        if op == "!=":
            return float(left) != float(right)
        if op == "between":
            lo_hi = right if isinstance(right, (list, tuple)) else (None, None)
            lo, hi = lo_hi if isinstance(lo_hi, (list, tuple)) and len(lo_hi) == 2 else (None, None)
            if lo is None or hi is None:
                return False
            v = float(left)
            return float(lo) <= v <= float(hi)
    except Exception:
        return False
    return False


def safe_float(v: Any) -> Optional[float]:
    try:
        if v is None or (isinstance(v, float) and np.isnan(v)):
            return None
        return float(v)
    except Exception:
        return None

