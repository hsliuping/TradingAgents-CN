"""日志治理机器强制测试（logging-governance.md §5.1/§5.2/§5.3）。

三道护栏：
1. 无新增 print/basicConfig/根 logger 劫持违规（AST 检测 + 存量基线只降不升）
2. 进度契约表单一来源（log_handler 只能引用 log_contract.PROGRESS_LOG_PATTERNS，禁止私藏正则）
3. logging_manager 不劫持 root handlers（历史问题：handlers.clear() 抢日志）
"""

import importlib.util
import logging
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent


def _load_checker():
    spec = importlib.util.spec_from_file_location(
        "check_logging_violations", ROOT / "scripts" / "check_logging_violations.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_no_new_logging_violations():
    """扫描业务代码，新增违规（超基线）必须让测试红"""
    checker = _load_checker()
    actual = checker.scan()
    baseline = checker.load_baseline()
    problems = checker.check(actual, baseline)
    assert not problems, "新增日志违规（不允许）:\n" + "\n".join(problems)


def test_progress_patterns_single_source():
    """进度契约表是唯一来源：log_handler 引用契约常量，不自带正则"""
    from app.services.progress import log_contract
    from app.services.progress.log_handler import ProgressLogHandler

    handler = ProgressLogHandler()
    assert handler.progress_patterns is log_contract.PROGRESS_LOG_PATTERNS
    assert log_contract.PROGRESS_LOG_PATTERNS, "契约表不能为空"
    assert log_contract.PROGRESS_KEYWORDS, "预筛关键词不能为空"
    # 契约表正则必须可编译（防手滑写坏）
    for pattern in log_contract.PROGRESS_LOG_PATTERNS:
        re.compile(pattern)


def test_logging_manager_does_not_hijack_root_handlers():
    """get_logger_manager/setup_logging 不得增删 root handlers（只允许 setLevel）"""
    import tradingagents.utils.logging_manager as lm

    root = logging.getLogger()
    before = list(root.handlers)

    lm.get_logger_manager()
    lm.setup_logging()

    after = list(root.handlers)
    assert after == before, (
        "logging_manager 劫持了 root handlers: "
        f"before={before!r} after={after!r}"
    )
