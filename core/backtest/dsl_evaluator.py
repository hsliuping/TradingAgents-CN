"""
策略 DSL 评估器
编排 L1（Schema）→ L2（语义）→ L3（执行），支持自修正循环
"""
import copy
import logging
from typing import Any, Dict, List, Optional, Tuple

from .dsl_validator import validate_dsl_semantics
from .engine_client import BacktestEngineClient

logger = logging.getLogger(__name__)


def _make_lightweight_dsl(dsl: Dict[str, Any]) -> Dict[str, Any]:
    """
    生成轻量 DSL，用于 L3 执行校验（缩短区间、单标的）
    仅验证能否跑通，不关心收益
    """
    lightweight = copy.deepcopy(dsl)
    cfg = lightweight.setdefault("config", {})
    uni = lightweight.get("universe", {})
    symbols = uni.get("symbols", []) if isinstance(uni, dict) else []
    if symbols:
        lightweight["universe"] = {
            **uni,
            "symbols": [symbols[0]],
        }
    cfg["start_year"] = 2024
    cfg["end_year"] = 2024
    return lightweight


async def validate_execution(dsl: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
    """
    L3 执行校验：对 DSL 做轻量回测，验证能否跑通
    Returns:
        (success, error_message)
    """
    try:
        client = BacktestEngineClient()
        lightweight = _make_lightweight_dsl(dsl)
        resp = await client.run(lightweight)
        if resp.get("success"):
            return True, None
        return False, resp.get("error", "回测执行失败")
    except Exception as e:
        logger.warning("L3 执行校验异常: %s", e)
        return False, str(e)


def evaluate_dsl(dsl: Dict[str, Any]) -> List[str]:
    """
    L2 语义校验
    Returns:
        错误列表，空表示通过
    """
    return validate_dsl_semantics(dsl)


async def evaluate_dsl_full(
    dsl: Dict[str, Any],
    run_execution_check: bool = True,
) -> Tuple[bool, List[str]]:
    """
    完整评估：L2 语义 + L3 执行（可选）
    Returns:
        (passed, errors)
    """
    errors = evaluate_dsl(dsl)
    if errors:
        return False, errors
    if run_execution_check:
        ok, exec_err = await validate_execution(dsl)
        if not ok and exec_err:
            errors.append(f"执行校验失败: {exec_err}")
            return False, errors
    return True, []
