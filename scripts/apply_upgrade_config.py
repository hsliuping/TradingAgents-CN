#!/usr/bin/env python3
"""
升级配置导入脚本

在升级安装后首次启动时，检测版本变化并导入新版本的配置增量（新模板、新配置项等）。
仅补充缺失项，不覆盖用户已有配置。

使用方法：
    python scripts/apply_upgrade_config.py --host
    python scripts/apply_upgrade_config.py --host --mongodb-port 27017
"""

import json
import re
import sys
from pathlib import Path
from typing import Optional, List, Tuple

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


def parse_version(version_str: str) -> Tuple[int, ...]:
    """将版本号字符串转为可比较的元组，如 '2.0.1' -> (2, 0, 1)"""
    parts = []
    for p in re.split(r"[.-]", str(version_str).strip()):
        # 去掉 build 后缀等
        p = re.sub(r"build.*", "", p, flags=re.I).strip()
        if not p:
            continue
        try:
            parts.append(int(p))
        except ValueError:
            parts.append(0)
    return tuple(parts) if parts else (0, 0, 0)


def get_current_version(project_root: Path) -> str:
    """从 BUILD_INFO 或 VERSION 获取当前版本"""
    build_info = project_root / "BUILD_INFO"
    if build_info.exists():
        try:
            with open(build_info, "r", encoding="utf-8") as f:
                data = json.load(f)
                return data.get("version") or data.get("full_version", "0.0.0").split("-")[0]
        except Exception:
            pass

    version_file = project_root / "VERSION"
    if version_file.exists():
        return version_file.read_text(encoding="utf-8").strip()

    return "0.0.0"


def get_last_applied_version(project_root: Path) -> str:
    """从 runtime/.config_version 读取上次应用的版本"""
    version_file = project_root / "runtime" / ".config_version"
    if version_file.exists():
        return version_file.read_text(encoding="utf-8").strip()
    return "0.0.0"


def set_last_applied_version(project_root: Path, version: str) -> None:
    """写入 runtime/.config_version"""
    runtime_dir = project_root / "runtime"
    runtime_dir.mkdir(parents=True, exist_ok=True)
    version_file = runtime_dir / ".config_version"
    version_file.write_text(version, encoding="utf-8")


def find_upgrade_configs(
    releases_dir: Path, last_version: str, current_version: str
) -> List[Tuple[str, Path]]:
    """
    查找需要应用的升级配置文件。
    从 releases/{version}/ 目录读取，每个版本目录包含 upgrade_config.json。
    返回 [(version, path), ...] 按版本升序排列。
    """
    last_tuple = parse_version(last_version)
    current_tuple = parse_version(current_version)

    if current_tuple <= last_tuple:
        return []

    # 匹配 releases/X.Y.Z/ 或 releases/X_Y_Z/
    pattern = re.compile(r"^(\d+)[._](\d+)[._](\d+.*?)$", re.I)
    candidates = []

    for version_dir in releases_dir.iterdir():
        if not version_dir.is_dir():
            continue
        m = pattern.match(version_dir.name)
        if not m:
            continue
        ver_str = version_dir.name.replace("_", ".")
        ver_tuple = parse_version(ver_str)
        if last_tuple < ver_tuple <= current_tuple:
            config_path = version_dir / "upgrade_config.json"
            if config_path.exists():
                candidates.append((ver_str, ver_tuple, config_path))

    # 按版本排序
    candidates.sort(key=lambda x: x[1])
    return [(ver_str, path) for ver_str, _, path in candidates]


def load_env_config(script_dir: Path) -> dict:
    """从 .env 文件加载 MongoDB 配置"""
    env_file = script_dir.parent / ".env"
    config = {
        "mongodb_port": 27017,
        "mongodb_host": "localhost",
        "mongodb_username": "admin",
        "mongodb_password": "tradingagents123",
    }
    if env_file.exists():
        try:
            with open(env_file, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith("#") or "=" not in line:
                        continue
                    key, value = line.split("=", 1)
                    key, value = key.strip(), value.strip()
                    if key == "MONGODB_PORT":
                        config["mongodb_port"] = int(value)
                    elif key == "MONGODB_HOST":
                        config["mongodb_host"] = value
                    elif key == "MONGODB_USERNAME":
                        config["mongodb_username"] = value
                    elif key == "MONGODB_PASSWORD":
                        config["mongodb_password"] = value
        except Exception:
            pass
    return config


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Apply upgrade config (incremental)")
    parser.add_argument("--host", action="store_true", help="Run on host (localhost)")
    parser.add_argument("--mongodb-port", type=int, help="MongoDB port")
    parser.add_argument("--mongodb-host", type=str, help="MongoDB host")
    parser.add_argument("--dry-run", action="store_true", help="Only show what would be done")
    args = parser.parse_args()

    script_dir = Path(__file__).parent
    env_config = load_env_config(script_dir)
    if args.mongodb_port:
        env_config["mongodb_port"] = args.mongodb_port
    if args.mongodb_host:
        env_config["mongodb_host"] = args.mongodb_host

    releases_dir = project_root / "releases"
    last_version = get_last_applied_version(project_root)
    current_version = get_current_version(project_root)

    print("=" * 60)
    print("Upgrade Config Check")
    print("=" * 60)
    print(f"  Last applied version: {last_version}")
    print(f"  Current version:      {current_version}")

    upgrade_files = find_upgrade_configs(releases_dir, last_version, current_version)
    if not upgrade_files:
        print("  No upgrade configs to apply.")
        return 0

    print(f"  Found {len(upgrade_files)} upgrade config(s) to apply:")
    for ver, path in upgrade_files:
        print(f"    - {ver}: {path.relative_to(project_root)}")

    if args.dry_run:
        print("  (Dry run - no changes made)")
        return 0

    # 调用 import_config_and_create_user.py --incremental
    import subprocess

    python_exe = sys.executable
    import_script = project_root / "scripts" / "import_config_and_create_user.py"

    for ver, config_path in upgrade_files:
        print(f"\nApplying upgrade config for {ver}...")
        cmd = [
            python_exe,
            str(import_script),
            str(config_path),
            "--host",
            "--incremental",
            "--skip-user",
            "--mongodb-port",
            str(env_config["mongodb_port"]),
        ]
        if env_config.get("mongodb_host"):
            cmd.extend(["--mongodb-host", env_config["mongodb_host"]])

        result = subprocess.run(cmd, cwd=str(project_root))
        if result.returncode != 0:
            print(f"  ERROR: Failed to apply {config_path.name}")
            return result.returncode

        set_last_applied_version(project_root, ver)
        print(f"  Updated last_applied_config_version to {ver}")

    # 最终更新为当前版本
    set_last_applied_version(project_root, current_version)
    print(f"\nUpgrade config applied. last_applied_config_version = {current_version}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
