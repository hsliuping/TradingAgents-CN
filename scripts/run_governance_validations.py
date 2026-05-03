#!/usr/bin/env python
"""Run the current governance validation suite."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TEST_TARGETS = [
    "tests/test_prompt_template_service_sync.py",
    "tests/test_sync_research_brief_templates_selection.py",
]


def main() -> int:
    command = [sys.executable, "-m", "pytest", *TEST_TARGETS, "-q"]
    print("Running governance validations:")
    for target in TEST_TARGETS:
        print(f"- {target}")

    completed = subprocess.run(command, cwd=ROOT)
    return completed.returncode


if __name__ == "__main__":
    raise SystemExit(main())