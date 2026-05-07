"""Python 运行时解析工具。"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Iterable, Optional


DEFAULT_ENV_VAR_NAMES = (
    "TRADINGAGENTS_PYTHON_EXE",
    "TRADINGAGENTS_SANDBOX_PYTHON_EXE",
)


def resolve_python_executable(
    project_root: str | Path,
    *,
    env_var_names: Optional[Iterable[str]] = None,
) -> str:
    """解析项目应使用的 Python 可执行文件。"""
    root = Path(project_root)

    for env_name in env_var_names or DEFAULT_ENV_VAR_NAMES:
        configured = os.environ.get(env_name, "").strip()
        if configured and Path(configured).exists():
            return configured

    candidates = [
        root / "release" / "TradingAgentsCN-portable" / "vendors" / "python" / "python.exe",
        root / "env" / "Scripts" / "python.exe",
        root / "venv" / "Scripts" / "python.exe",
        root / "vendors" / "python" / "python.exe",
    ]

    for candidate in candidates:
        if candidate.exists():
            return str(candidate)

    if sys.executable:
        return sys.executable

    return "python"