#!/usr/bin/env python3
"""
获取两个版本之间的变更文件列表。

用法:
    python git_changed_files.py <prev_ref> [--paths path1 path2 ...]
    python git_changed_files.py v2.0.0
    python git_changed_files.py 2.0.0 --paths app core migrations

prev_ref: 上一版本 tag 或 commit，如 v2.0.0、2.0.0
--paths: 可选，过滤路径前缀

输出: JSON 数组，如 ["app/main.py", "core/config/xxx.py"]
"""

import json
import subprocess
import sys
from pathlib import Path

# 项目根目录 (scripts/prepare_release/scripts/ -> 3 levels up)
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent


def normalize_ref(ref: str) -> str:
    """确保 tag 格式正确（v 前缀）"""
    ref = ref.strip()
    if ref and not ref.startswith("v") and ref[0].isdigit():
        return f"v{ref}"
    return ref


def get_changed_files(prev_ref: str, paths: list[str] | None = None) -> list[str]:
    """获取 prev_ref..HEAD 之间的变更文件"""
    ref = normalize_ref(prev_ref)
    range_spec = f"{ref}..HEAD"

    cmd = ["git", "diff", "--name-only", range_spec]
    if paths:
        cmd.extend(["--"] + paths)

    try:
        result = subprocess.run(
            cmd,
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode != 0:
            return []

        lines = [line.strip() for line in result.stdout.strip().splitlines() if line.strip()]
        return lines

    except Exception:
        return []


def main() -> int:
    args = sys.argv[1:]
    if not args:
        print("Usage: git_changed_files.py <prev_ref> [--paths path1 path2 ...]", file=sys.stderr)
        return 1

    prev_ref = args[0]
    paths = None

    if "--paths" in args:
        idx = args.index("--paths")
        paths = args[idx + 1:] if idx + 1 < len(args) else []

    files = get_changed_files(prev_ref, paths)
    print(json.dumps(files, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
