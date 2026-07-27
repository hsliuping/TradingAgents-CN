#!/usr/bin/env python3
"""Run the isolated PR-009 MVP smoke test without external services."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


if __name__ == "__main__":
    raise SystemExit(
        subprocess.run(
            [
                sys.executable,
                "-m",
                "pytest",
                "-q",
                "tests/integration/alphaguard/test_mvp_smoke_pr009.py",
            ],
            cwd=ROOT,
            check=False,
        ).returncode
    )
