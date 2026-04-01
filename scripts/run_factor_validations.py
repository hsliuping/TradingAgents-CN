from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path
from typing import List, Sequence, Tuple


ROOT = Path(__file__).resolve().parents[1]

VALIDATORS: List[Tuple[str, Path]] = [
    ("fundamental", ROOT / "scripts" / "validate_moutai_fundamental_factors.py"),
    ("technical", ROOT / "scripts" / "validate_technical_factors.py"),
    ("factor_registry", ROOT / "scripts" / "validate_factor_registry.py"),
]


def _select_validators(args: argparse.Namespace) -> List[Tuple[str, Path]]:
    if args.only == "fundamental":
        return [VALIDATORS[0]]
    if args.only == "technical":
        return [VALIDATORS[1]]
    if args.only == "factor_registry":
        return [VALIDATORS[2]]
    return VALIDATORS


def _build_command(script_path: Path, symbol: str | None) -> Sequence[str]:
    command: List[str] = [sys.executable, str(script_path)]
    if symbol:
        command.append(symbol)
    return command


def main() -> int:
    parser = argparse.ArgumentParser(description="运行因子回归校验脚本")
    parser.add_argument("symbol", nargs="?", default=None, help="可选股票代码，默认使用脚本内置样例")
    parser.add_argument(
        "--only",
        choices=["fundamental", "technical", "factor_registry"],
        default=None,
        help="只运行某一类因子校验",
    )
    args = parser.parse_args()

    selected = _select_validators(args)
    failures: List[str] = []

    print("=" * 72)
    print("Factor Validation Suite")
    print(f"Python: {sys.executable}")
    print(f"Root:   {ROOT}")
    print("=" * 72)

    for name, script_path in selected:
        command = _build_command(script_path, args.symbol)
        print(f"\n[RUN] {name}: {' '.join(command)}")
        completed = subprocess.run(command, cwd=ROOT)
        if completed.returncode == 0:
            print(f"[PASS] {name}")
        else:
            print(f"[FAIL] {name} exit={completed.returncode}")
            failures.append(name)

    print("\n" + "=" * 72)
    if failures:
        print("Factor validation failed:", ", ".join(failures))
        print("=" * 72)
        return 1

    print("All factor validations passed")
    print("=" * 72)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())