#!/bin/bash
# TradingAgents-CN Pro - Docker 多标签推送
# 为已构建的镜像添加浮动标签（2.1, 2, 2-latest 等）
# 用法: ./docker-tags.sh <exact-tag> [--registry <registry>] [--dry-run]

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/common.sh"

REGISTRY="${DOCKER_IMAGE_NAMESPACE:-hsliup}"
DRY_RUN=false
EXACT_TAG=""

# 解析参数
while [[ $# -gt 0 ]]; do
    case "$1" in
        --registry) REGISTRY="$2"; shift ;;
        --dry-run) DRY_RUN=true ;;
        -*)
            log_error "未知选项: $1"
            exit 1
            ;;
        *)
            if [ -z "$EXACT_TAG" ]; then
                EXACT_TAG="$1"
            else
                log_error "多余的参数: $1"
                exit 1
            fi
            ;;
    esac
    shift
done

if [ -z "$EXACT_TAG" ]; then
    log_error "请指定精确版本 tag，如: docker-tags.sh 2.1.0"
    exit 1
fi

# 解析版本号
parse_version "$EXACT_TAG" || exit 1

# 计算浮动标签
# 精确版本: 2.1.0
# 浮动标签: 2.1, 2, 2-latest
# 但需要判断当前版本是否是该版本线的最高版本
FLOATING_TAGS=()

# 始终添加 minor 级浮动标签: 2.1
FLOATING_TAGS+=("${MAJOR}.${MINOR}")

# 判断是否为该主版本线的最高版本
# 通过检查 git tag 来确定
SHOULD_ADD_MAJOR_FLOATING=true
local_major_tags=$(git -C "$PROJECT_ROOT" tag -l "v${MAJOR}.*" --sort=-version:refname 2>/dev/null)

if [ -n "$local_major_tags" ]; then
    # 获取最高版本的 tag
    highest_tag=$(echo "$local_major_tags" | head -1)
    highest_version="${highest_tag#v}"
    highest_version="${highest_version%%-*}"  # 去掉 prerelease

    # 比较: 如果当前版本 < 最高版本，不加主版本浮动标签
    local cmp
    cmp=$(compare_version "$EXACT_TAG" "$highest_version")
    if [ "$cmp" = "-1" ]; then
        SHOULD_ADD_MAJOR_FLOATING=false
    fi
fi

if $SHOULD_ADD_MAJOR_FLOATING; then
    FLOATING_TAGS+=("${MAJOR}")
    FLOATING_TAGS+=("${MAJOR}-latest")
fi

# 如果有 prerelease 后缀（如 beta），浮动标签也带上
if [ -n "$PRERELEASE" ]; then
    FLOATING_TAGS+=("${MAJOR}.${MINOR}-${PRERELEASE}")
    FLOATING_TAGS+=("${MAJOR}-${PRERELEASE}")
    FLOATING_TAGS+=("${MAJOR}-${PRERELEASE}-latest")
fi

# 为 backend 和 frontend 添加浮动标签
IMAGES=(
    "${REGISTRY}/tradingagents-pro-backend"
    "${REGISTRY}/tradingagents-pro-frontend"
)

log_info "精确版本: $EXACT_TAG"
log_info "浮动标签: ${FLOATING_TAGS[*]}"

for image in "${IMAGES[@]}"; do
    for floating_tag in "${FLOATING_TAGS[@]}"; do
        if $DRY_RUN; then
            log_info "[DRY RUN] docker tag ${image}:${EXACT_TAG} ${image}:${floating_tag}"
            log_info "[DRY RUN] docker push ${image}:${floating_tag}"
        else
            log_info "标签 ${image}:${EXACT_TAG} → ${image}:${floating_tag}"
            docker tag "${image}:${EXACT_TAG}" "${image}:${floating_tag}" 2>/dev/null || {
                log_warning "标签失败，可能镜像 ${image}:${EXACT_TAG} 不存在，跳过"
                continue
            }
            docker push "${image}:${floating_tag}" || {
                log_warning "推送 ${image}:${floating_tag} 失败"
                continue
            }
            log_success "已推送: ${image}:${floating_tag}"
        fi
    done
done

if ! $DRY_RUN; then
    log_success "浮动标签推送完成"
fi
