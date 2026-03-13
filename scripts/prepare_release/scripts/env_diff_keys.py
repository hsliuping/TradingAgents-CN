#!/usr/bin/env python3
"""
从 .env.example 的 git diff 中提取新增或修改的 KEY 列表。

用法:
    python env_diff_keys.py <prev_ref>
    python env_diff_keys.py v2.0.0

prev_ref: 上一版本 tag 或 commit

输出: JSON 数组，如 ["NEW_KEY","ANOTHER_KEY"]
"""

import json
import re
import subprocess
import sys
from pathlib import Path

# 项目根目录 (scripts/prepare_release/scripts/ -> 3 levels up)
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
ENV_EXAMPLE = ".env.example"


def normalize_ref(ref: str) -> str:
    """确保 tag 格式正确"""
    ref = ref.strip()
    if ref and not ref.startswith("v") and ref[0].isdigit():
        return f"v{ref}"
    return ref


def get_env_diff(prev_ref: str) -> str:
    """获取 .env.example 的 diff 输出"""
    ref = normalize_ref(prev_ref)
    range_spec = f"{ref}..HEAD"

    try:
        result = subprocess.run(
            ["git", "diff", range_spec, "--", ENV_EXAMPLE],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode != 0:
            return ""
        return result.stdout or ""
    except Exception:
        return ""


def extract_keys_from_diff(diff_text: str) -> list[str]:
    """
    从 diff 输出中提取新增或修改的 KEY。
    匹配 +KEY= 或 -KEY= 行，取 KEY 部分。
    去重并去重。
    """
    # 匹配 +KEY= 或 -KEY= 行（KEY 为字母数字下划线）
    key_pattern = re.compile(r"^[+-]\s*([A-Za-z_][A-Za-z0-9_]*)\s*=", re.MULTILINE)
    keys = set()

    for m in key_pattern.finditer(diff_text):
        key = m.group(1).strip()
        if key and not key.startswith("#"):
            keys.add(key)

    return sorted(keys)


def main() -> int:
    if len(sys.argv) < 2:
        print("Usage: env_diff_keys.py <prev_ref>", file=sys.stderr)
        return 1

    prev_ref = sys.argv[1]
    diff = get_env_diff(prev_ref)
    keys = extract_keys_from_diff(diff)
    print(json.dumps(keys, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
