#!/bin/bash
# TradingAgents-CN Pro - 发布脚本共享函数库
# 被 release.sh、hotfix.sh、dev-env.sh 引用

# 项目根目录
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# 日志函数
log_info()    { echo -e "${BLUE}ℹ️  $1${NC}"; }
log_success() { echo -e "${GREEN}✅ $1${NC}"; }
log_warning() { echo -e "${YELLOW}⚠️  $1${NC}"; }
log_error()   { echo -e "${RED}❌ $1${NC}"; }

# 读取 VERSION 文件
read_version() {
    local version_file="$PROJECT_ROOT/VERSION"
    if [ ! -f "$version_file" ]; then
        log_error "VERSION 文件不存在: $version_file"
        return 1
    fi
    tr -d '\r\n' < "$version_file"
}

# 写入 VERSION 文件
write_version() {
    local version="$1"
    echo "$version" > "$PROJECT_ROOT/VERSION"
    log_success "VERSION 更新为: $version"
}

# 解析 semver 版本号
# 用法: parse_version "2.1.0" → MAJOR=2 MINOR=1 PATCH=0 PRERELEASE=""
# 用法: parse_version "3.0.0-beta" → MAJOR=3 MINOR=0 PATCH=0 PRERELEASE="beta"
parse_version() {
    local version="${1#v}"
    PRERELEASE=""
    if [[ "$version" =~ ^([0-9]+)\.([0-9]+)\.([0-9]+)(-(.+))?$ ]]; then
        MAJOR="${BASH_REMATCH[1]}"
        MINOR="${BASH_REMATCH[2]}"
        PATCH="${BASH_REMATCH[3]}"
        PRERELEASE="${BASH_REMATCH[5]:-}"
        return 0
    else
        log_error "无效的版本号格式: $1 (期望: MAJOR.MINOR.PATCH 或 MAJOR.MINOR.PATCH-prerelease)"
        return 1
    fi
}

# 获取版本线（主版本.次版本）
# "2.1.0" → "2.1"
# "3.0.0-beta" → "3.0"
get_version_line() {
    local version="${1#v}"
    echo "${version%%.*}.$(echo "$version" | cut -d. -f2)"
}

# 获取主版本号
# "2.1.0" → "2"
get_major_line() {
    local version="${1#v}"
    echo "${version%%.*}"
}

# 版本号比较（返回 -1/0/1）
# 用法: compare_version "2.1.0" "2.2.0" → -1
compare_version() {
    local v1="${1#v}" v2="${2#v}"
    # 去掉 prerelease 后缀
    v1="${v1%%-*}"
    v2="${v2%%-*}"

    local IFS='.'
    read -ra a <<< "$v1"
    read -ra b <<< "$v2"

    for i in 0 1 2; do
        local x="${a[$i]:-0}" y="${b[$i]:-0}"
        if (( x < y )); then echo -1; return 0; fi
        if (( x > y )); then echo 1; return 0; fi
    done
    echo 0
}

# 获取当前 git 分支名
get_current_branch() {
    git -C "$PROJECT_ROOT" rev-parse --abbrev-ref HEAD 2>/dev/null
}

# 检查工作树是否干净
check_clean_working_tree() {
    if ! git -C "$PROJECT_ROOT" diff --quiet HEAD 2>/dev/null; then
        log_error "存在未提交的更改，请先提交或暂存"
        git -C "$PROJECT_ROOT" status --short
        return 1
    fi
    return 0
}

# 检查 git remote 是否存在
check_git_remote() {
    local remote="$1"
    if ! git -C "$PROJECT_ROOT" remote get-url "$remote" &>/dev/null; then
        log_error "远程仓库 '$remote' 不存在"
        return 1
    fi
    return 0
}

# 扫描 git tag，获取指定版本前缀的下一个构建号
# 用法: get_next_build_number "2.1.0" → 007
# 兼容旧格式 v2.1.0-rev006 和新格式 v2.1.0-006
get_next_build_number() {
    local version="${1#v}"
    local max_build=0

    while IFS= read -r tag; do
        tag="${tag#v}"
        # 匹配 v2.1.0-NNN 或 v2.1.0-revNNN
        if [[ "$tag" =~ ^${version}-(rev)?([0-9]+)$ ]]; then
            local num="${BASH_REMATCH[2]}"
            # 去掉前导零
            num=$((10#$num))
            if (( num > max_build )); then
                max_build=$num
            fi
        fi
    done < <(git -C "$PROJECT_ROOT" tag -l "v${version}-*" 2>/dev/null)

    printf "%03d" $((max_build + 1))
}

# 获取指定版本线的最新 tag
# 用法: get_latest_tag "2.1" → v2.1.0
get_latest_tag() {
    local version_line="$1"
    git -C "$PROJECT_ROOT" tag -l "v${version_line}*" --sort=-version:refname 2>/dev/null | head -1
}

# 检查 tag 是否已存在
tag_exists() {
    local tag="$1"
    git -C "$PROJECT_ROOT" tag -l "$tag" 2>/dev/null | grep -q "^${tag}$"
}
