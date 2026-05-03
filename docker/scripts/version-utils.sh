#!/bin/bash

read_version_from_file() {
    local project_root="$1"
    local version_file="$project_root/VERSION"

    if [ ! -f "$version_file" ]; then
        return 0
    fi

    tr -d '\r\n' < "$version_file"
}

resolve_image_tag() {
    local requested_tag="${1:-}"
    local project_root="$2"

    if [ -n "$requested_tag" ]; then
        echo "$requested_tag"
        return 0
    fi

    local version_from_file
    version_from_file="$(read_version_from_file "$project_root")"
    if [ -n "$version_from_file" ]; then
        echo "$version_from_file"
        return 0
    fi

    echo "latest"
}

should_push_latest_alias() {
    local tag="$1"
    local push_latest="$2"

    if [ "$push_latest" = true ] && [ "$tag" != "latest" ]; then
        return 0
    fi

    return 1
}