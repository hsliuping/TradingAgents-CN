#!/usr/bin/env python
"""Run the current factor validation suite."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TEST_TARGETS = [
    "tests/test_agent_base_classes.py::TestTechnicalAnalystV2::test_fallback_user_prompt_avoids_execution_language",
    "tests/test_agent_base_classes.py::TestFundamentalAnalystV2::test_fallback_user_prompt_avoids_execution_language",
    "tests/test_agent_base_classes.py::TestRiskAssessorV2::test_fallback_user_prompt_avoids_reference_prices",
    "tests/test_agent_base_classes.py::TestActionAdvisorV2::test_fallback_user_prompt_uses_research_schema",
]


def main() -> int:
    command = [sys.executable, "-m", "pytest", *TEST_TARGETS, "-q"]
    print("Running factor validations:")
    for target in TEST_TARGETS:
        print(f"- {target}")

    completed = subprocess.run(command, cwd=ROOT)
    return completed.returncode


if __name__ == "__main__":
    raise SystemExit(main())