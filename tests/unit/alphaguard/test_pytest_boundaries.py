from __future__ import annotations

import ast
import builtins
from pathlib import Path
import socket

import pytest

import conftest as root_conftest


def test_default_ci_boundary_is_alphaguard_and_fail_closed():
    root = Path(__file__).resolve().parents[3]
    config = (root / "pytest.ini").read_text(encoding="utf-8")

    assert "addopts = --alphaguard-suite=offline" in config
    assert root_conftest._category(
        root / "tests/unit/alphaguard/test_production_data_completion.py"
    ) == "unit"
    assert root_conftest._category(
        root / "tests/integration/alphaguard/test_mvp_smoke_pr009.py"
    ) == "integration"
    assert root_conftest._category(root / "tests/test_query.py") == "manual"
    assert root_conftest._category(root / "tests/test_baostock_quick.py") == "network"
    assert root_conftest._category(
        root / "tests/test_stock_info_debug.py"
    ) == "interactive"
    assert root_conftest._category(
        root / "tests/test_akshare_debug.py"
    ) == "legacy_collection_error"

    assert builtins.input is root_conftest._offline_input
    assert socket.socket.connect is root_conftest._offline_socket_connect
    with pytest.raises(root_conftest.OfflineBoundaryViolation):
        socket.create_connection(("example.invalid", 443))


def test_offline_collection_contains_no_known_interactive_module():
    root = Path(__file__).resolve().parents[3]
    input_modules: list[str] = []
    for path in (root / "tests").rglob("*.py"):
        source = path.read_text(encoding="utf-8", errors="ignore")
        try:
            tree = ast.parse(source)
        except SyntaxError:
            continue
        if any(
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "input"
            for node in ast.walk(tree)
        ):
            input_modules.append(path.relative_to(root).as_posix())

    assert input_modules
    assert all(
        root_conftest._category(root / relative)
        in {"interactive", "manual", "network", "legacy_collection_error"}
        for relative in input_modules
    )
