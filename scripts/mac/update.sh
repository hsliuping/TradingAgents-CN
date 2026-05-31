#!/usr/bin/env bash
# TradingAgents-CN OTA 更新脚本
# 从 Gitee manifest 检查新版本，更新 .env 镜像地址并重启 compose

set -euo pipefail

INSTALL_DIR="${INSTALL_DIR:-$HOME/Applications/TradingAgents-CN}"
COMPOSE_FILE="${COMPOSE_FILE:-docker-compose.hub.nginx.arm.yml}"
ENV_FILE="${INSTALL_DIR}/.env"
VERSION_FILE="${INSTALL_DIR}/VERSION"
LOG_FILE="${INSTALL_DIR}/logs/update.log"

mkdir -p "${INSTALL_DIR}/logs"

log() {
  local msg="[$(date '+%Y-%m-%d %H:%M:%S')] $*"
  echo "$msg"
  echo "$msg" >> "$LOG_FILE"
}

load_env() {
  if [[ -f "$ENV_FILE" ]]; then
    # shellcheck disable=SC1090
    set -a
    source "$ENV_FILE"
    set +a
  fi
}

get_local_version() {
  if [[ -f "$VERSION_FILE" ]]; then
    cat "$VERSION_FILE" | tr -d '[:space:]'
  else
    echo "v0.0.0"
  fi
}

version_gt() {
  # 比较 v1.0.1 格式版本号，$1 > $2 返回 0
  local a="${1#v}" b="${2#v}"
  [[ "$(printf '%s\n%s\n' "$a" "$b" | sort -V | tail -n1)" == "$a" && "$a" != "$b" ]]
}

update_env_var() {
  local key="$1" val="$2" file="$3"
  if grep -q "^${key}=" "$file" 2>/dev/null; then
    sed -i '' "s|^${key}=.*|${key}=${val}|" "$file"
  else
    echo "${key}=${val}" >> "$file"
  fi
}

parse_manifest() {
  local manifest_file="$1"
  python3 - "$manifest_file" <<'PY'
import json, sys
with open(sys.argv[1], encoding="utf-8") as f:
    data = json.load(f)
print(data["version"])
print(data["images"]["backend"])
print(data["images"]["frontend"])
PY
}

wait_health() {
  local max=60 i=0
  while [[ $i -lt $max ]]; do
    if curl -sf "http://localhost/api/health" | grep -qE '"status"[[:space:]]*:[[:space:]]*"ok"'; then
      return 0
    fi
    sleep 3
    i=$((i + 1))
  done
  return 1
}

do_update() {
  local manifest_url="${MANIFEST_URL:-}"
  if [[ -z "$manifest_url" ]]; then
    log "未配置 MANIFEST_URL，跳过 OTA 检查"
    return 0
  fi

  local tmp
  tmp="$(mktemp)"
  if ! curl -sfL --connect-timeout 15 --max-time 60 "$manifest_url" -o "$tmp"; then
    log "无法下载 manifest: $manifest_url（跳过更新）"
    rm -f "$tmp"
    return 0
  fi

  local remote_version backend_image frontend_image parsed
  parsed="$(parse_manifest "$tmp")"
  remote_version="$(echo "$parsed" | sed -n '1p')"
  backend_image="$(echo "$parsed" | sed -n '2p')"
  frontend_image="$(echo "$parsed" | sed -n '3p')"
  rm -f "$tmp"

  local local_version
  local_version="$(get_local_version)"

  if ! version_gt "$remote_version" "$local_version"; then
    log "已是最新版本: ${local_version}（远程 ${remote_version}）"
    return 0
  fi

  log "发现新版本: ${local_version} -> ${remote_version}"

  cp "$ENV_FILE" "${ENV_FILE}.bak.$(date +%Y%m%d%H%M%S)"

  update_env_var "BACKEND_IMAGE" "$backend_image" "$ENV_FILE"
  update_env_var "FRONTEND_IMAGE" "$frontend_image" "$ENV_FILE"

  cd "$INSTALL_DIR"

  if [[ -n "${DOCKER_HUB_TOKEN:-}" && -n "${DOCKER_HUB_USER:-}" ]]; then
    echo "$DOCKER_HUB_TOKEN" | docker login -u "$DOCKER_HUB_USER" --password-stdin >/dev/null 2>&1 || true
  fi

  docker compose -f "$COMPOSE_FILE" pull backend frontend
  docker compose -f "$COMPOSE_FILE" up -d --remove-orphans

  if wait_health; then
    echo "$remote_version" > "$VERSION_FILE"
    log "更新成功: ${remote_version}"
    osascript -e "display notification \"已更新到 ${remote_version}\" with title \"TradingAgents-CN\"" 2>/dev/null || true
  else
    log "更新后健康检查失败，请检查日志或从 .env.bak 恢复"
    return 1
  fi
}

main() {
  load_env
  cd "$INSTALL_DIR" 2>/dev/null || {
    log "安装目录不存在: $INSTALL_DIR"
    exit 1
  }

  case "${1:-}" in
    --check|--now|"")
      do_update
      ;;
    *)
      echo "用法: $0 [--check|--now]"
      exit 1
      ;;
  esac
}

main "$@"
