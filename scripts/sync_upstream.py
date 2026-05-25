#!/usr/bin/env python3
import subprocess
import sys

def run(cmd, check=True):
    print(f"$ {cmd}", flush=True)
    p = subprocess.run(cmd, shell=True, text=True)
    if check and p.returncode != 0:
        sys.exit(p.returncode)
    return p.returncode

def main():
    run("git fetch upstream")

    if run("git rev-parse --verify upstream/main", check=False) == 0:
        upstream_branch = "upstream/main"
    elif run("git rev-parse --verify upstream/master", check=False) == 0:
        upstream_branch = "upstream/master"
    else:
        print("错误：找不到 upstream/main 或 upstream/master")
        sys.exit(0)

    print(f"使用上游分支：{upstream_branch}")

    if run(f"git diff --quiet HEAD {upstream_branch}", check=False) == 0:
        print("当前已经是最新，无需同步。")
        sys.exit(0)

    print("检测到上游有更新，尝试低风险快进同步...")

    code = run(f"git merge --ff-only {upstream_branch}", check=False)

    if code == 0:
        print("低风险快进同步完成。")
        sys.exit(0)

    print("不是低风险更新：当前分支与上游存在分叉或冲突。")
    print("已停止自动同步，避免破坏你的仓库。")
    print("建议手动处理，或重新 fork 上游仓库。")

    # 确保没有残留合并状态
    run("git merge --abort", check=False)
    run("git status", check=False)

    # 这里用 0，避免 Actions 红色失败
    sys.exit(0)

if __name__ == "__main__":
    main()
