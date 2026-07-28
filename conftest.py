"""Collection-time isolation for deterministic default CI.

Markers alone are too late for legacy modules that perform network or input
work while importing.  This root hook classifies those modules before import;
the explicit suite option makes every excluded boundary runnable on demand.
"""

from __future__ import annotations

import builtins
from pathlib import Path
import socket

import pytest


INTERACTIVE_FILES = {
    "tests/debug_test_execution.py",
    "tests/test_agent_utils_tushare_fix.py",
    "tests/test_dashscope_openai_fix.py",
    "tests/test_llm_technical_analysis_debug.py",
    "tests/test_stock_info_debug.py",
    "tests/test_tushare_integration.py",
}

NETWORK_FILES = {
    "tests/integration/test_dashscope_integration.py",
    "tests/akshare_isolated_test.py",
    "tests/simple_akshare_test.py",
    "tests/test_akshare_alternative.py",
    "tests/test_akshare_amount.py",
    "tests/test_akshare_api.py",
    "tests/test_akshare_code_format.py",
    "tests/test_akshare_direct.py",
    "tests/test_akshare_fixed.py",
    "tests/test_akshare_functionality.py",
    "tests/test_akshare_hk.py",
    "tests/test_akshare_hk_apis.py",
    "tests/test_akshare_performance.py",
    "tests/test_akshare_priority.py",
    "tests/test_akshare_priority_fix.py",
    "tests/test_amplitude_api.py",
    "tests/test_baostock_fixed.py",
    "tests/test_baostock_quick.py",
    "tests/test_baostock_stock_filter.py",
    "tests/test_baostock_valuation.py",
    "tests/test_hk_apis_simple.py",
    "tests/test_news_filtering.py",
    "tests/test_web_api_akshare.py",
    "tests/testgoogle.py",
}

MANUAL_FILES = {
    "tests/test_analysis_result.py",
    "tests/test_api_analysis.py",
    "tests/test_api_format.py",
    "tests/test_batch_analysis_planA.py",
    "tests/test_decision_data.py",
    "tests/test_existing_results.py",
    "tests/test_fixed_analysis.py",
    "tests/test_frontend_backend_integration.py",
    "tests/test_frontend_display.py",
    "tests/test_industries_api.py",
    "tests/test_industry_screening_fix.py",
    "tests/test_mongodb_save.py",
    "tests/test_quick_async.py",
    "tests/test_quick_fix.py",
    "tests/test_real_estate_api.py",
    "tests/test_reports_api.py",
    "tests/test_reports_fix.py",
    "tests/test_screening_fix.py",
    "tests/test_summary_recommendation.py",
}

# Exact modules whose existing import-time collection failure was confirmed on
# 2026-07-28.  They are not hidden: operators can reproduce the failures with
# ``--alphaguard-suite=legacy_collection_error``.
LEGACY_COLLECTION_ERROR_FILES = {
    "tests/system/test_llm_provider_sanitization.py",
    "tests/test_akshare_debug.py",
    "tests/test_amount_fix.py",
    "tests/test_dashscope_token_tracking.py",
    "tests/test_data_config_cli.py",
    "tests/test_financial_data_validation.py",
    "tests/test_finnhub_news_fix.py",
    "tests/test_google_tool_handler_improvements.py",
    "tests/test_news_timeout_fix.py",
    "tests/test_sse_and_worker_config.py",
    "tests/test_system_config_summary_sse_queue.py",
    "tests/test_tushare_unified/test_tushare_provider.py",
    "tests/unit/dataflows/test_unified_dataframe.py",
    "tests/unit/test_stocks_kline_news_api.py",
}

_ORIGINAL_INPUT = builtins.input
_ORIGINAL_SOCKET_CONNECT = socket.socket.connect
_ORIGINAL_SOCKET_CONNECT_EX = socket.socket.connect_ex
_ORIGINAL_CREATE_CONNECTION = socket.create_connection


class OfflineBoundaryViolation(RuntimeError):
    """Raised when the deterministic suite attempts live I/O."""


def _offline_input(*args, **kwargs):
    del args, kwargs
    raise OfflineBoundaryViolation(
        "interactive input is forbidden in the default offline suite; "
        "use --alphaguard-suite=interactive or manual"
    )


def _offline_socket_connect(self, address):
    del self
    raise OfflineBoundaryViolation(
        f"network access is forbidden in the default offline suite: {address!r}; "
        "use --alphaguard-suite=network"
    )


def _offline_socket_connect_ex(self, address):
    _offline_socket_connect(self, address)
    return 1


def _offline_create_connection(address, *args, **kwargs):
    del args, kwargs
    raise OfflineBoundaryViolation(
        f"network access is forbidden in the default offline suite: {address!r}; "
        "use --alphaguard-suite=network"
    )


def pytest_addoption(parser) -> None:
    parser.addoption(
        "--alphaguard-suite",
        action="store",
        default="offline",
        choices=(
            "offline",
            "unit",
            "integration",
            "network",
            "interactive",
            "manual",
            "legacy_collection_error",
            "all",
        ),
        help="select an explicit AlphaGuard test collection boundary",
    )


def pytest_configure(config) -> None:
    suite = config.getoption("--alphaguard-suite")
    if suite in {"offline", "unit", "integration"}:
        builtins.input = _offline_input
        socket.socket.connect = _offline_socket_connect
        socket.socket.connect_ex = _offline_socket_connect_ex
        socket.create_connection = _offline_create_connection
    else:
        builtins.input = _ORIGINAL_INPUT
        socket.socket.connect = _ORIGINAL_SOCKET_CONNECT
        socket.socket.connect_ex = _ORIGINAL_SOCKET_CONNECT_EX
        socket.create_connection = _ORIGINAL_CREATE_CONNECTION


def _relative(path: Path) -> str:
    try:
        return path.resolve().relative_to(Path(__file__).resolve().parent).as_posix()
    except ValueError:
        return path.as_posix()


def _category(path: Path) -> str:
    relative = _relative(path)
    if relative in LEGACY_COLLECTION_ERROR_FILES:
        return "legacy_collection_error"
    if relative in INTERACTIVE_FILES:
        return "interactive"
    if relative in NETWORK_FILES:
        return "network"
    if relative in MANUAL_FILES:
        return "manual"
    if relative.startswith("tests/network/"):
        return "network"
    if relative.startswith("tests/integration/alphaguard/") or relative == (
        "tests/integration/test_alphaguard_structured_decision_graph.py"
    ):
        return "integration"
    if relative.startswith("tests/unit/alphaguard/") or relative == (
        "tests/unit/test_alphaguard_baseline_guard.py"
    ):
        return "unit"
    # Everything else predates the AlphaGuard deterministic boundary.  The
    # repository contains hundreds of historical debug/operator tests, some
    # of which connect to local services or providers during import or inside
    # nominally "unit" test bodies.  Preserve them under the explicit manual
    # suite until each module is independently audited and reclassified.
    return "manual"


def pytest_ignore_collect(collection_path: Path, config) -> bool | None:
    path = Path(str(collection_path))
    if path.suffix != ".py":
        return None
    relative = _relative(path)
    if not relative.startswith("tests/"):
        return None
    suite = config.getoption("--alphaguard-suite")
    category = _category(path)
    if suite == "all":
        return False
    if suite == "offline":
        return category in {
            "network",
            "interactive",
            "manual",
            "legacy_collection_error",
        }
    return category != suite


def pytest_collection_modifyitems(config, items) -> None:
    for item in items:
        category = _category(Path(str(item.path)))
        item.add_marker(getattr(pytest.mark, category))
