"""
策略评估器
- DSL 评估：L2（语义）→ L3（执行）
- Python+config 评估：L2（config 校验）→ L3（/run_python 执行）
"""
import copy
import logging
from typing import Any, Dict, List, Optional, Tuple

from .dsl_validator import validate_dsl_semantics
from .engine_client import BacktestEngineClient

logger = logging.getLogger(__name__)


def validate_config_semantics(config: Dict[str, Any]) -> List[str]:
    """
    L2 语义校验：校验 config（symbols 非空、日期合理等）
    Returns:
        错误列表，空表示通过
    """
    errors: List[str] = []
    symbols = config.get("symbols")
    if not symbols:
        uni = config.get("universe") or {}
        symbols = uni.get("symbols", []) if isinstance(uni, dict) else []
    if not symbols:
        errors.append("股票池 symbols 不能为空")

    start_year = config.get("start_year")
    end_year = config.get("end_year")
    if start_year is not None and end_year is not None:
        try:
            sy, ey = int(start_year), int(end_year)
            if sy >= ey:
                errors.append(f"回测区间 start_year({sy}) 应小于 end_year({ey})")
        except (TypeError, ValueError):
            pass

    max_pos = config.get("max_positions", 10)
    if symbols and max_pos is not None and int(max_pos) < 1:
        errors.append("max_positions 至少为 1")
    return errors


def _make_lightweight_config(config: Dict[str, Any]) -> Dict[str, Any]:
    """
    生成轻量 config，用于 L3 执行校验（缩短区间、单标的）
    """
    lightweight = copy.deepcopy(config)
    symbols = lightweight.get("symbols")
    if not symbols:
        uni = lightweight.get("universe") or {}
        symbols = (uni.get("symbols", []) or []) if isinstance(uni, dict) else []
    if symbols:
        if "symbols" in lightweight:
            lightweight["symbols"] = [symbols[0]]
        else:
            uni = lightweight.setdefault("universe", {})
            if isinstance(uni, dict):
                uni["symbols"] = [symbols[0]]
    lightweight["start_year"] = 2024
    lightweight["end_year"] = 2024
    return lightweight


async def validate_execution_python(
    code: str, config: Dict[str, Any]
) -> Tuple[bool, Optional[str]]:
    """
    L3 执行校验：对 Python 策略做轻量回测，验证能否跑通
    Returns:
        (success, error_message)
    """
    try:
        client = BacktestEngineClient()
        lightweight = _make_lightweight_config(config)
        resp = await client.run_python(code, lightweight)
        if resp.get("success"):
            return True, None
        return False, resp.get("error", "回测执行失败")
    except Exception as e:
        logger.warning("L3 执行校验异常: %s", e)
        return False, str(e)


async def evaluate_strategy_python_full(
    code: str,
    config: Dict[str, Any],
    run_execution_check: bool = True,
) -> Tuple[bool, List[str]]:
    """
    完整评估：L2 config 校验 + L3 执行（可选）
    Returns:
        (passed, errors)
    """
    errors = validate_config_semantics(config)
    if errors:
        return False, errors
    if run_execution_check:
        ok, exec_err = await validate_execution_python(code, config)
        if not ok and exec_err:
            errors.append(f"执行校验失败: {exec_err}")
            return False, errors
    return True, []


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
