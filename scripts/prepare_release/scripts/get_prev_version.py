#!/usr/bin/env python3
"""
获取上一版本号。

从 releases/ 目录或 git tags 推断小于当前版本的最大版本。
供发布准备智能体流程调用。

用法:
    python get_prev_version.py [current_version]
    python get_prev_version.py 2.0.2

输出: 上一版本号，如 2.0.1；若无则输出空并退出码 1。
"""

import re
import sys
from pathlib import Path

# 项目根目录 (scripts/prepare_release/scripts/ -> 3 levels up)
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent


def parse_version(version_str: str) -> tuple:
    """将版本号转为可比较元组，如 '2.0.1' -> (2, 0, 1)"""
    parts = []
    for p in re.split(r"[.-]", str(version_str).strip()):
        p = re.sub(r"build.*", "", p, flags=re.I).strip()
        if not p:
            continue
        try:
            parts.append(int(p))
        except ValueError:
            parts.append(0)
    return tuple(parts) if parts else (0, 0, 0)


def get_current_version() -> str:
    """从 VERSION 或 BUILD_INFO 读取当前版本"""
    version_file = PROJECT_ROOT / "VERSION"
    if version_file.exists():
        return version_file.read_text(encoding="utf-8").strip()

    build_info = PROJECT_ROOT / "BUILD_INFO"
    if build_info.exists():
        try:
            import json
            data = json.loads(build_info.read_text(encoding="utf-8"))
            return (data.get("version") or data.get("full_version", "0.0.0")).split("-")[0]
        except Exception:
            pass

    return "0.0.0"


def get_prev_version_from_releases(current: str) -> str | None:
    """从 releases/ 目录获取上一版本"""
    releases_dir = PROJECT_ROOT / "releases"
    if not releases_dir.exists():
        return None

    current_tuple = parse_version(current)
    pattern = re.compile(r"^(\d+)[._](\d+)[._](\d+.*?)$", re.I)
    candidates = []

    for d in releases_dir.iterdir():
        if not d.is_dir():
            continue
        m = pattern.match(d.name)
        if not m:
            continue
        ver_str = d.name.replace("_", ".")
        ver_tuple = parse_version(ver_str)
        if ver_tuple < current_tuple:
            candidates.append((ver_str, ver_tuple))

    if not candidates:
        return None

    candidates.sort(key=lambda x: x[1])
    return candidates[-1][0]


def get_prev_version_from_tags(current: str) -> str | None:
    """从 git tags 获取上一版本（需 v 前缀）"""
    import subprocess

    try:
        result = subprocess.run(
            ["git", "tag", "-l", "v*"],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode != 0:
            return None

        current_tuple = parse_version(current)
        pattern = re.compile(r"^v(\d+)[._](\d+)[._](\d+.*?)$", re.I)
        candidates = []

        for line in result.stdout.strip().splitlines():
            tag = line.strip()
            m = pattern.match(tag)
            if not m:
                continue
            ver_str = tag.lstrip("v").replace("_", ".")
            ver_tuple = parse_version(ver_str)
            if ver_tuple < current_tuple:
                candidates.append((ver_str, ver_tuple))

        if not candidates:
            return None

        candidates.sort(key=lambda x: x[1])
        return candidates[-1][0]

    except Exception:
        return None


def main() -> int:
    current = sys.argv[1] if len(sys.argv) > 1 else get_current_version()
    prev = get_prev_version_from_releases(current) or get_prev_version_from_tags(current)

    if prev:
        print(prev)
        return 0
    else:
        return 1


if __name__ == "__main__":
    sys.exit(main())
