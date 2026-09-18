# -*- coding: utf-8 -*-
"""
社区版发布管道（v3.6.0 社区版开源分离 · M3）

功能：从私有仓当前分支生成社区版全量代码快照。
  1. git archive 导出干净快照（仅 git 跟踪文件，自动排除 env/node_modules/webroot）
  2. 按 docs/community-edition/removal-manifest.yaml 执行剔除（整文件/整目录删除、整文件替换）
  3. 源码泄露扫描（命中即失败）
  4. 输出剔除报告

用法（在私有仓根目录）：
  python scripts/publish_community.py --output D:/Temp/community-build
  python scripts/publish_community.py --output <dir> --commit <sha>   # 指定基线

注意：本脚本只生成快照，不推送、不改动私有仓工作区。
后续验证（后端 import 自检 / 前端 build / dist 扫描）由发布流程执行。
"""

import argparse
import hashlib
import shutil
import subprocess
import sys
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
MANIFEST_PATH = REPO_ROOT / "docs" / "community-edition" / "removal-manifest.yaml"
TEMPLATES_DIR = REPO_ROOT / "scripts" / "community_templates"


def die(msg: str) -> None:
    print(f"[publish_community] FATAL: {msg}", file=sys.stderr)
    sys.exit(1)


def run_git(args: list[str], cwd: Path = REPO_ROOT) -> str:
    result = subprocess.run(
        ["git", *args], cwd=cwd, capture_output=True, text=True, encoding="utf-8", errors="replace"
    )
    if result.returncode != 0:
        die(f"git {' '.join(args)} 失败: {result.stderr.strip()}")
    return result.stdout.strip()


def load_manifest() -> dict:
    if not MANIFEST_PATH.exists():
        die(f"剔除清单不存在: {MANIFEST_PATH}")
    with open(MANIFEST_PATH, encoding="utf-8") as f:
        return yaml.safe_load(f)


def check_clean_worktree() -> None:
    status = run_git(["status", "--porcelain"])
    if status:
        die(f"私有仓工作区不干净，请先提交或 stash：\n{status}")


def export_snapshot(commit: str | None, output: Path) -> None:
    """git archive 导出指定基线（默认 HEAD）到 output 目录"""
    treeish = commit or "HEAD"
    if output.exists():
        die(f"输出目录已存在，请先删除: {output}")
    output.mkdir(parents=True)
    # tar 流导出再解包：Windows 下无原生 tar -x 管道兼容性问题，用 python tarfile
    archive = subprocess.run(
        ["git", "archive", "--format=tar", treeish],
        cwd=REPO_ROOT,
        capture_output=True,
    )
    if archive.returncode != 0:
        die(f"git archive {treeish} 失败: {archive.stderr.decode('utf-8', errors='replace')}")
    import tarfile
    import io

    with tarfile.open(fileobj=io.BytesIO(archive.stdout)) as tar:
        # 安全解包：拒绝路径穿越
        for member in tar.getmembers():
            target = (output / member.name).resolve()
            if not str(target).startswith(str(output.resolve())):
                die(f"非法归档成员（路径穿越）: {member.name}")
        tar.extractall(output, filter="data")
    print(f"  [1/4] 快照导出完成: {treeish} -> {output}")


def do_removals(manifest: dict, output: Path) -> dict:
    """执行剔除，返回统计"""
    stats = {"dirs_deleted": 0, "files_deleted": 0, "files_replaced": 0, "missing": []}

    for section, key in [
        ("目录", "delete_dirs"),
        ("后端路由", "delete_files_backend_routers"),
        ("后端服务", "delete_files_backend_services"),
        ("后端模型/工具", "delete_files_backend_models"),
        ("licensing", "delete_files_licensing"),
        ("前端", "delete_files_frontend"),
        ("根目录", "delete_files_root"),
        ("用户文档", "delete_files_docs"),
        ("核心工具", "delete_files_core_tools"),
        ("测试", "delete_files_tests"),
    ]:
        for rel in manifest.get(key, []) or []:
            target = output / rel
            if target.is_dir():
                shutil.rmtree(target)
                stats["dirs_deleted"] += 1
            elif target.is_file():
                target.unlink()
                stats["files_deleted"] += 1
            else:
                stats["missing"].append(rel)
                print(f"  [警告] 清单条目不存在（跳过）: {rel}")

    for item in manifest.get("replace_files", []) or []:
        src = TEMPLATES_DIR / item["template"]
        dst = output / item["target"]
        if not src.is_file():
            die(f"模板不存在: {src}")
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
        stats["files_replaced"] += 1

    print(
        f"  [2/4] 剔除完成: 删除目录 {stats['dirs_deleted']} 个、"
        f"删除文件 {stats['files_deleted']} 个、替换文件 {stats['files_replaced']} 个"
    )
    return stats


def scan_leaks(manifest: dict, output: Path) -> list[str]:
    """源码泄露扫描：命中即记录（发布时应为空）"""
    hits: list[str] = []
    patterns = manifest.get("scan_source_patterns", []) or []
    text_suffixes = {
        ".py", ".ts", ".vue", ".js", ".json", ".yaml", ".yml", ".md",
        ".txt", ".toml", ".cfg", ".ini", ".html", ".css", ".scss", ".sh", ".ps1",
    }
    skip_dirs = {"node_modules", ".git", "dist", "webroot", "__pycache__", ".venv", "env"}
    for path in output.rglob("*"):
        if not path.is_file():
            continue
        if any(part in skip_dirs for part in path.parts):
            continue
        if path.suffix.lower() not in text_suffixes:
            continue
        try:
            content = path.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue
        for pat in patterns:
            if pat in content:
                rel = path.relative_to(output).as_posix()
                hits.append(f"{rel} :: '{pat}'")
    if hits:
        print(f"  [3/4] 泄露扫描: 命中 {len(hits)} 处")
        for h in hits[:50]:
            print(f"        {h}")
    else:
        print("  [3/4] 泄露扫描: 通过（0 命中）")
    return hits


def write_report(output: Path, commit: str, stats: dict, leaks: list[str]) -> None:
    lines = [
        "# 社区版生成报告",
        "",
        f"- 基线: {commit}",
        f"- 生成时间: {__import__('datetime').datetime.now().isoformat()}",
        f"- 删除目录: {stats['dirs_deleted']}",
        f"- 删除文件: {stats['files_deleted']}",
        f"- 替换文件: {stats['files_replaced']}",
        f"- 清单缺失条目: {len(stats['missing'])}" + (f" {stats['missing']}" if stats['missing'] else ""),
        f"- 源码泄露扫描: {'通过' if not leaks else f'失败（{len(leaks)} 处命中）'}",
        "",
        "## 后续验证步骤（发布流程执行）",
        "1. 后端 import 自检: env/Scripts/python -c \"import app.main\"",
        "2. 后端启动 + OpenAPI 路由对比（Pro 路由应全部消失）",
        "3. 前端: npm install && npx vue-tsc --noEmit && npm run build",
        "4. dist 产物泄露扫描（scan_dist_patterns）",
        "5. 运行冒烟: 登录 / 社区路由 200 / Pro 路由 404",
    ]
    (output / "COMMUNITY_BUILD_REPORT.md").write_text("\n".join(lines), encoding="utf-8")
    print(f"  [4/4] 报告已生成: {output / 'COMMUNITY_BUILD_REPORT.md'}")


def main() -> None:
    parser = argparse.ArgumentParser(description="社区版发布管道")
    parser.add_argument("--output", required=True, help="输出目录（必须不存在）")
    parser.add_argument("--commit", default=None, help="基线 commit（默认 HEAD）")
    parser.add_argument("--allow-dirty", action="store_true", help="允许工作区不干净（调试用）")
    args = parser.parse_args()

    output = Path(args.output).resolve()
    print(f"=== 社区版生成 ===")
    print(f"  清单: {MANIFEST_PATH}")
    print(f"  输出: {output}")

    if not args.allow_dirty:
        check_clean_worktree()

    commit = args.commit or run_git(["rev-parse", "HEAD"])
    short = run_git(["log", "-1", "--format=%h %s", commit])
    print(f"  基线: {short}")

    manifest = load_manifest()
    export_snapshot(args.commit, output)
    stats = do_removals(manifest, output)
    leaks = scan_leaks(manifest, output)
    write_report(output, short, stats, leaks)

    if leaks:
        print("\n结果: 失败（存在泄露命中，请处理后再生成）")
        sys.exit(2)
    if stats["missing"]:
        print(f"\n结果: 警告（清单存在 {len(stats['missing'])} 个幽灵条目，请修正清单）")
        sys.exit(3)
    print("\n结果: 生成成功。请继续执行验证步骤（见 COMMUNITY_BUILD_REPORT.md）")


if __name__ == "__main__":
    main()
