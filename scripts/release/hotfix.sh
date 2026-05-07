#!/bin/bash
# TradingAgents-CN Pro - Hotfix 辅助脚本
# 用法: ./hotfix.sh <子命令> [选项]
#
# 子命令:
#   start <version-line> <issue-name>  从 tag 创建 hotfix 分支
#   finish [--no-push]                 完成修复，打 tag，cherry-pick，清理
#   cherry-pick <target-branch>        向指定分支 cherry-pick

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/common.sh"

# Cherry-pick 矩阵：哪个版本线的修复需要同步到哪些分支
CHERRY_PICK_TARGETS_2_0="release/2.0.x"
CHERRY_PICK_TARGETS_2_1="release/2.1.x main"
CHERRY_PICK_TARGETS_3_0="main"
CHERRY_PICK_TARGETS_MAIN="release/2.1.x release/2.0.x"

# ==========================================
# start 子命令
# ==========================================
cmd_start() {
    local version_line="$1"
    local issue_name="$2"

    if [ -z "$version_line" ] || [ -z "$issue_name" ]; then
        log_error "用法: hotfix.sh start <version-line> <issue-name>"
        log_error "示例: hotfix.sh start 2.1 null-pointer-fix"
        exit 1
    fi

    # 查找该版本线的最新 tag
    local base_tag
    base_tag=$(get_latest_tag "$version_line")
    if [ -z "$base_tag" ]; then
        log_error "版本线 $version_line 没有找到 tag"
        exit 1
    fi

    local branch_name="hotfix/${version_line}/${issue_name}"

    # 检查分支是否已存在
    if git -C "$PROJECT_ROOT" show-ref --verify --quiet "refs/heads/$branch_name" 2>/dev/null; then
        log_error "分支 '$branch_name' 已存在"
        exit 1
    fi

    git -C "$PROJECT_ROOT" checkout -b "$branch_name" "$base_tag"
    log_success "Hotfix 分支已创建: $branch_name (基于 $base_tag)"
    log_info "请在此分支上进行修复，完成后运行: hotfix.sh finish"
}

# ==========================================
# finish 子命令
# ==========================================
cmd_finish() {
    local no_push=false

    while [[ $# -gt 0 ]]; do
        case "$1" in
            --no-push) no_push=true ;;
            *) log_error "未知选项: $1"; exit 1 ;;
        esac
        shift
    done

    local branch
    branch=$(get_current_branch)

    # 检查是否在 hotfix 分支上
    if [[ ! "$branch" =~ ^hotfix/ ]]; then
        log_error "当前不在 hotfix 分支上 (当前: $branch)"
        exit 1
    fi

    # 解析版本线和 issue 名
    # hotfix/2.1/null-pointer-fix → version_line=2.1, issue=null-pointer-fix
    local version_line
    version_line=$(echo "$branch" | cut -d/ -f2)

    # 检查是否有未提交的更改
    check_clean_working_tree || exit 1

    # Bump patch 版本
    local version
    version=$(read_version) || exit 1
    parse_version "$version" || exit 1
    local new_version="${MAJOR}.${MINOR}.$((PATCH + 1))"
    if [ -n "$PRERELEASE" ]; then
        new_version="${new_version}-${PRERELEASE}"
    fi

    log_info "版本号: $version → $new_version"
    write_version "$new_version"

    # 提交版本号变更
    git -C "$PROJECT_ROOT" add VERSION
    git -C "$PROJECT_ROOT" commit -m "chore: bump version to $new_version" || true

    # 打 tag
    local tag_name="v${new_version}"
    if tag_exists "$tag_name"; then
        log_error "Tag '$tag_name' 已存在"
        exit 1
    fi
    git -C "$PROJECT_ROOT" tag "$tag_name"
    log_success "Tag 已创建: $tag_name"

    # 确定 cherry-pick 目标
    local targets=""
    case "$version_line" in
        2.0) targets="$CHERRY_PICK_TARGETS_2_0" ;;
        2.1) targets="$CHERRY_PICK_TARGETS_2_1" ;;
        3.0) targets="$CHERRY_PICK_TARGETS_3_0" ;;
        *)   targets="$CHERRY_PICK_TARGETS_MAIN" ;;
    esac

    # Cherry-pick 到目标分支
    local hotfix_commits
    hotfix_commits=$(git -C "$PROJECT_ROOT" log --format="%H" "v${version}..HEAD" 2>/dev/null || echo "")

    if [ -n "$hotfix_commits" ]; then
        for target in $targets; do
            if git -C "$PROJECT_ROOT" show-ref --verify --quiet "refs/heads/$target" 2>/dev/null; then
                log_info "Cherry-pick 到 $target..."
                for commit in $hotfix_commits; do
                    git -C "$PROJECT_ROOT" checkout "$target" 2>/dev/null || continue
                    if git -C "$PROJECT_ROOT" cherry-pick "$commit" 2>/dev/null; then
                        log_success "Cherry-pick 成功: $commit → $target"
                    else
                        log_warning "Cherry-pick 冲突: $commit → $target，请手动解决"
                        git -C "$PROJECT_ROOT" cherry-pick --abort 2>/dev/null || true
                    fi
                done
            else
                log_warning "目标分支 '$target' 不存在，跳过"
            fi
        done
    fi

    # 切回 hotfix 分支
    git -C "$PROJECT_ROOT" checkout "$branch" 2>/dev/null || true

    # 推送
    if ! $no_push; then
        check_git_remote "pro" || exit 1
        log_info "推送到远程..."
        git -C "$PROJECT_ROOT" push pro "$branch" 2>/dev/null || true
        git -C "$PROJECT_ROOT" push pro "$tag_name"
        # 推送 cherry-pick 的分支
        for target in $targets; do
            if git -C "$PROJECT_ROOT" show-ref --verify --quiet "refs/heads/$target" 2>/dev/null; then
                git -C "$PROJECT_ROOT" push pro "$target" 2>/dev/null || true
            fi
        done
        log_success "推送完成"
    fi

    # 清理 hotfix 分支
    local original_branch="$branch"
    git -C "$PROJECT_ROOT" checkout main 2>/dev/null || git -C "$PROJECT_ROOT" checkout pro-main 2>/dev/null || true
    git -C "$PROJECT_ROOT" branch -d "$original_branch" 2>/dev/null || true
    if ! $no_push; then
        git -C "$PROJECT_ROOT" push pro --delete "$original_branch" 2>/dev/null || true
    fi
    log_success "Hotfix 分支已清理: $original_branch"
    log_success "Hotfix 完成: $tag_name"
}

# ==========================================
# cherry-pick 子命令
# ==========================================
cmd_cherry_pick() {
    local target_branch="$1"
    local commit="${2:-HEAD}"

    if [ -z "$target_branch" ]; then
        log_error "用法: hotfix.sh cherry-pick <target-branch> [<commit>]"
        exit 1
    fi

    if ! git -C "$PROJECT_ROOT" show-ref --verify --quiet "refs/heads/$target_branch" 2>/dev/null; then
        log_error "目标分支 '$target_branch' 不存在"
        exit 1
    fi

    local current_branch
    current_branch=$(get_current_branch)
    local commit_sha
    commit_sha=$(git -C "$PROJECT_ROOT" rev-parse "$commit")

    log_info "Cherry-pick: $commit_sha → $target_branch"
    git -C "$PROJECT_ROOT" checkout "$target_branch"
    if git -C "$PROJECT_ROOT" cherry-pick "$commit_sha"; then
        log_success "Cherry-pick 成功"
    else
        log_warning "Cherry-pick 冲突，请手动解决后运行: git cherry-pick --continue"
        git -C "$PROJECT_ROOT" checkout "$current_branch" 2>/dev/null || true
        exit 1
    fi

    git -C "$PROJECT_ROOT" checkout "$current_branch" 2>/dev/null || true
}

# ==========================================
# 主入口
# ==========================================
usage() {
    echo "用法: $0 <子命令> [选项]"
    echo ""
    echo "子命令:"
    echo "  start <version-line> <issue-name>  从 tag 创建 hotfix 分支"
    echo "  finish [--no-push]                 完成修复，打 tag，cherry-pick，清理"
    echo "  cherry-pick <target-branch> [<commit>]  向指定分支 cherry-pick"
}

case "${1:-}" in
    start)       shift; cmd_start "$@" ;;
    finish)      shift; cmd_finish "$@" ;;
    cherry-pick) shift; cmd_cherry_pick "$@" ;;
    *)           usage; exit 1 ;;
esac
