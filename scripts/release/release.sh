#!/bin/bash
# TradingAgents-CN Pro - 发布编排脚本
# 用法: ./release.sh <子命令> [选项]
#
# 子命令:
#   status                            显示当前状态
#   bump [major|minor|patch|build]    更新版本号
#   tag [--build] [--dry-run]         创建 git tag
#   branch <version-line>             创建 release 分支
#   push [--remote <name>]            推送分支和 tag
#   changelog [--version-line <n>]    生成变更日志
#   docker-build [选项]               构建 Docker 镜像
#   github-release <tag>              创建 GitHub Release

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/common.sh"

# ==========================================
# status 子命令
# ==========================================
cmd_status() {
    local version
    version=$(read_version) || exit 1
    local branch
    branch=$(get_current_branch)

    echo "========================================="
    echo "  TradingAgents-CN Pro 发布状态"
    echo "========================================="
    echo ""
    echo "当前分支:   $branch"
    echo "VERSION:    $version"
    echo ""

    # 显示各版本线最新 tag
    echo "版本线最新 Tag:"
    for line in "2.0" "2.1" "3.0"; do
        local tag
        tag=$(get_latest_tag "$line")
        if [ -n "$tag" ]; then
            echo "  $line.x → $tag"
        else
            echo "  $line.x → (无 tag)"
        fi
    done
    echo ""

    # 显示工作树状态
    if git -C "$PROJECT_ROOT" diff --quiet HEAD 2>/dev/null; then
        log_success "工作树干净"
    else
        log_warning "存在未提交的更改"
        git -C "$PROJECT_ROOT" status --short
    fi
}

# ==========================================
# bump 子命令
# ==========================================
cmd_bump() {
    local bump_type="${1:-build}"
    local version
    version=$(read_version) || exit 1

    parse_version "$version" || exit 1

    local old_version="$version"
    local new_version

    case "$bump_type" in
        major)
            new_version="$((MAJOR + 1)).0.0"
            ;;
        minor)
            new_version="${MAJOR}.$((MINOR + 1)).0"
            ;;
        patch)
            new_version="${MAJOR}.${MINOR}.$((PATCH + 1))"
            ;;
        build)
            # build 不改变 VERSION 文件，只是显示下一个构建号
            local build_num
            build_num=$(get_next_build_number "$version")
            log_info "VERSION 文件不变: $version"
            log_info "下一个构建 Tag: v${version}-${build_num}"
            return 0
            ;;
        *)
            log_error "未知的 bump 类型: $bump_type (可选: major, minor, patch, build)"
            exit 1
            ;;
    esac

    # 保留 prerelease 后缀（如果有）
    if [ -n "$PRERELEASE" ]; then
        # patch bump 保留 prerelease，其他 bump 去掉
        if [ "$bump_type" = "patch" ]; then
            new_version="${new_version}-${PRERELEASE}"
        fi
    fi

    log_info "版本号: $old_version → $new_version"
    write_version "$new_version"

    # 更新 BUILD_INFO
    if [ -f "$PROJECT_ROOT/scripts/build/generate_build_info.sh" ]; then
        bash "$PROJECT_ROOT/scripts/build/generate_build_info.sh" 2>/dev/null || true
    fi
}

# ==========================================
# tag 子命令
# ==========================================
cmd_tag() {
    local is_build=false
    local dry_run=false

    while [[ $# -gt 0 ]]; do
        case "$1" in
            --build) is_build=true ;;
            --dry-run) dry_run=true ;;
            *) log_error "未知选项: $1"; exit 1 ;;
        esac
        shift
    done

    local version
    version=$(read_version) || exit 1
    local tag_name

    if $is_build; then
        local build_num
        build_num=$(get_next_build_number "$version")
        tag_name="v${version}-${build_num}"
    else
        tag_name="v${version}"
    fi

    # 检查 tag 是否已存在
    if tag_exists "$tag_name"; then
        log_error "Tag '$tag_name' 已存在，精确版本 tag 不可覆盖"
        exit 1
    fi

    if $dry_run; then
        log_info "[DRY RUN] 将创建 Tag: $tag_name"
        return 0
    fi

    git -C "$PROJECT_ROOT" tag "$tag_name"
    log_success "Tag 已创建: $tag_name"
}

# ==========================================
# branch 子命令
# ==========================================
cmd_branch() {
    local version_line="$1"
    if [ -z "$version_line" ]; then
        log_error "请指定版本线，如: release.sh branch 2.1"
        exit 1
    fi

    local branch_name="release/${version_line}.x"

    # 检查分支是否已存在
    if git -C "$PROJECT_ROOT" show-ref --verify --quiet "refs/heads/$branch_name" 2>/dev/null; then
        log_warning "分支 '$branch_name' 已存在"
        return 0
    fi

    git -C "$PROJECT_ROOT" checkout -b "$branch_name"
    log_success "Release 分支已创建: $branch_name"
}

# ==========================================
# push 子命令
# ==========================================
cmd_push() {
    local remote="pro"

    while [[ $# -gt 0 ]]; do
        case "$1" in
            --remote) remote="$2"; shift ;;
            *) log_error "未知选项: $1"; exit 1 ;;
        esac
        shift
    done

    check_git_remote "$remote" || exit 1

    local branch
    branch=$(get_current_branch)

    log_info "推送分支 $branch 到 $remote..."
    git -C "$PROJECT_ROOT" push "$remote" "$branch"

    log_info "推送所有 Tag 到 $remote..."
    git -C "$PROJECT_ROOT" push "$remote" --tags

    log_success "推送完成"
}

# ==========================================
# changelog 子命令
# ==========================================
cmd_changelog() {
    local version_line=""

    while [[ $# -gt 0 ]]; do
        case "$1" in
            --version-line) version_line="$2"; shift ;;
            *) log_error "未知选项: $1"; exit 1 ;;
        esac
        shift
    done

    # 检查 git-cliff 是否安装
    if ! command -v git-cliff &>/dev/null; then
        log_error "git-cliff 未安装"
        log_info "安装方式: cargo install git-cliff 或 pip install git-cliff"
        exit 1
    fi

    local args=()
    if [ -n "$version_line" ]; then
        args+=(--tag-pattern "v${version_line}.*")
    fi

    git-cliff -c "$PROJECT_ROOT/cliff.toml" "${args[@]}" -r "$PROJECT_ROOT"
}

# ==========================================
# docker-build 子命令
# ==========================================
cmd_docker_build() {
    local multiarch=false
    local skip_push=false
    local tag=""

    while [[ $# -gt 0 ]]; do
        case "$1" in
            --multiarch) multiarch=true ;;
            --skip-push) skip_push=true ;;
            --tag) tag="$2"; shift ;;
            *) log_error "未知选项: $1"; exit 1 ;;
        esac
        shift
    done

    if [ -z "$tag" ]; then
        tag=$(read_version) || exit 1
    fi

    # 生成 BUILD_INFO
    if [ -f "$PROJECT_ROOT/scripts/build/generate_build_info.sh" ]; then
        bash "$PROJECT_ROOT/scripts/build/generate_build_info.sh" || true
    fi

    # 构建并推送
    if $multiarch; then
        log_info "多架构构建: $tag"
        if $skip_push; then
            bash "$PROJECT_ROOT/docker/scripts/build-multiarch.sh" -t "$tag" --skip-push
        else
            bash "$PROJECT_ROOT/docker/scripts/build-multiarch.sh" -t "$tag"
        fi
    else
        log_info "单架构构建: $tag"
        local build_args="-t $tag"
        if $skip_push; then
            build_args="$build_args --skip-push"
        fi
        bash "$PROJECT_ROOT/docker/scripts/build-and-push-all.sh" $build_args
    fi

    # 推送浮动标签（仅在非 skip-push 时）
    if ! $skip_push; then
        log_info "添加浮动 Docker 标签..."
        bash "$SCRIPT_DIR/docker-tags.sh" "$tag" || true
    fi

    log_success "Docker 构建完成: $tag"
}

# ==========================================
# github-release 子命令
# ==========================================
cmd_github_release() {
    local tag="$1"
    if [ -z "$tag" ]; then
        log_error "请指定 tag，如: release.sh github-release v2.1.0"
        exit 1
    fi

    # 检查 gh CLI 是否安装
    if ! command -v gh &>/dev/null; then
        log_error "gh CLI 未安装，请安装 GitHub CLI"
        exit 1
    fi

    # 检查 tag 是否存在
    if ! tag_exists "$tag"; then
        log_error "Tag '$tag' 不存在"
        exit 1
    fi

    # 提取版本线用于标题
    local version="${tag#v}"
    local major_line
    major_line=$(get_major_line "$version")
    local title="${tag} (${major_line}.x)"

    # 生成 changelog 作为 body
    local body=""
    if command -v git-cliff &>/dev/null; then
        body=$(git-cliff -c "$PROJECT_ROOT/cliff.toml" --tag-pattern "${tag}" -r "$PROJECT_ROOT" 2>/dev/null || echo "")
    fi

    if [ -z "$body" ]; then
        body="发布 ${tag}"
    fi

    # 检查 pro remote 对应的 GitHub 仓库
    local repo
    repo=$(git -C "$PROJECT_ROOT" remote get-url pro 2>/dev/null | sed -E 's|.*github.com[:/]([^/]+/[^/]+)(\.git)?|\1|')

    if [ -n "$repo" ]; then
        gh release create "$tag" --repo "$repo" --title "$title" --notes "$body"
        log_success "GitHub Release 已创建: $tag"
    else
        log_warning "无法确定 GitHub 仓库，请手动创建 Release"
        log_info "标题: $title"
        log_info "内容: $body"
    fi
}

# ==========================================
# 主入口
# ==========================================
usage() {
    echo "用法: $0 <子命令> [选项]"
    echo ""
    echo "子命令:"
    echo "  status                            显示当前状态"
    echo "  bump [major|minor|patch|build]    更新版本号"
    echo "  tag [--build] [--dry-run]         创建 git tag"
    echo "  branch <version-line>             创建 release 分支"
    echo "  push [--remote <name>]            推送分支和 tag"
    echo "  changelog [--version-line <n>]    生成变更日志"
    echo "  docker-build [选项]               构建 Docker 镜像"
    echo "  github-release <tag>              创建 GitHub Release"
}

case "${1:-}" in
    status)         shift; cmd_status "$@" ;;
    bump)           shift; cmd_bump "$@" ;;
    tag)            shift; cmd_tag "$@" ;;
    branch)         shift; cmd_branch "$@" ;;
    push)           shift; cmd_push "$@" ;;
    changelog)      shift; cmd_changelog "$@" ;;
    docker-build)   shift; cmd_docker_build "$@" ;;
    github-release) shift; cmd_github_release "$@" ;;
    *)              usage; exit 1 ;;
esac
