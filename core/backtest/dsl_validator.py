"""
策略 DSL 语义校验（L2）
在 Schema 校验通过后，检查策略逻辑是否合理
"""
import logging
from typing import Any, Dict, List

logger = logging.getLogger(__name__)


def _get_entry_months(dsl: Dict[str, Any]) -> List[int]:
    """从 entry_rules 提取 calendar_month 的 months"""
    for r in dsl.get("entry_rules", []):
        if r.get("type") == "calendar_month" and r.get("months"):
            return r["months"]
    return []


def _get_exit_months(dsl: Dict[str, Any]) -> List[int]:
    """从 exit_rules 提取 calendar_month 的 months"""
    for r in dsl.get("exit_rules", []):
        if r.get("type") == "calendar_month" and r.get("months"):
            return r["months"]
    return []


def _get_holding_days(dsl: Dict[str, Any]) -> int:
    """从 exit_rules 提取 holding_days"""
    for r in dsl.get("exit_rules", []):
        if r.get("type") == "holding_days" and r.get("days") is not None:
            return r["days"]
    return 0


def validate_dsl_semantics(dsl: Dict[str, Any]) -> List[str]:
    """
    语义校验，返回错误/警告列表（空列表表示通过）
    """
    errors: List[str] = []

    # 1. symbols 非空
    uni = dsl.get("universe", {})
    symbols = uni.get("symbols") if isinstance(uni, dict) else []
    if not symbols:
        errors.append("股票池 symbols 不能为空")

    # 2. start_year < end_year
    cfg = dsl.get("config", {}) or {}
    start_year = cfg.get("start_year")
    end_year = cfg.get("end_year")
    if start_year is not None and end_year is not None:
        try:
            sy, ey = int(start_year), int(end_year)
            if sy >= ey:
                errors.append(f"回测区间 start_year({sy}) 应小于 end_year({ey})")
        except (TypeError, ValueError):
            pass

    # 3. entry_months 与 exit_months 先后关系
    entry_months = _get_entry_months(dsl)
    exit_months = _get_exit_months(dsl)
    if entry_months and exit_months:
        min_entry = min(entry_months)
        max_exit = max(exit_months)
        if min_entry >= max_exit:
            errors.append(
                f"买入月份({entry_months})与卖出月份({exit_months})顺序不合理，"
                "买入月应早于卖出月（如1月买、2月卖）"
            )

    # 4. 春节类策略：若描述含「春节」「过完春节」，holding_days 不宜过长
    desc = (dsl.get("description") or "").lower()
    holding_days = _get_holding_days(dsl)
    if holding_days > 0 and ("春节" in desc or "过完春节" in desc):
        if holding_days > 45:
            errors.append(
                f"春节策略「过完春节卖」通常持仓约20-35个交易日，当前 holding_days={holding_days} 偏长，"
                "建议改为 exit calendar_month months=[2] 或 holding_days<=35"
            )

    # 5. max_positions 与 symbols 数量
    max_pos = cfg.get("max_positions", 10)
    if symbols and max_pos > len(symbols):
        pass  # 允许，不报错
    if symbols and max_pos < 1:
        errors.append("max_positions 至少为 1")

    return errors
