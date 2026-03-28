#!/bin/bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
LOG_DIR="$ROOT_DIR/logs"
RUNTIME_DIR="$ROOT_DIR/runtime"
VENV_DIR="$ROOT_DIR/.venv"
PYTHON_BIN="${PYTHON_BIN:-python3}"
ENV_FILE=""
FRONTEND_PM=""

usage() {
  cat <<'EOF'
Usage:
  ./scripts/startup/start_local_stack.sh --env /path/to/local_stack.env

Required env vars:
  TA_MODEL_PROVIDER
  TA_MODEL_NAME
  TA_MODEL_BASE_URL
  TA_MODEL_API_KEY
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --env)
      ENV_FILE="$2"
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown argument: $1"
      usage
      exit 1
      ;;
  esac
done

if [[ -z "$ENV_FILE" ]]; then
  echo "Missing --env"
  usage
  exit 1
fi

if [[ ! -f "$ENV_FILE" ]]; then
  echo "Env file not found: $ENV_FILE"
  exit 1
fi

mkdir -p "$LOG_DIR" "$RUNTIME_DIR"
set -a
. "$ENV_FILE"
set +a

log() {
  printf '%s\n' "$*"
}

ensure_cmd() {
  if ! command -v "$1" >/dev/null 2>&1; then
    log "Missing required command: $1"
    exit 1
  fi
}

ensure_python() {
  ensure_cmd "$PYTHON_BIN"
  "$PYTHON_BIN" - <<'PY'
import sys
if sys.version_info < (3, 10):
    raise SystemExit(f"Python >= 3.10 required, got {sys.version.split()[0]}")
print(sys.executable)
PY
}

ensure_brew_package() {
  local package="$1"
  if command -v brew >/dev/null 2>&1; then
    if ! brew list "$package" >/dev/null 2>&1; then
      log "Installing Homebrew package: $package"
      brew install "$package"
    fi
  fi
}

ensure_redis() {
  if ! command -v redis-server >/dev/null 2>&1; then
    ensure_brew_package redis
  fi

  if command -v redis-server >/dev/null 2>&1; then
    if command -v brew >/dev/null 2>&1; then
      if ! brew services list | grep -E 'redis\s+started' >/dev/null 2>&1; then
        brew services start redis >/dev/null 2>&1 || true
      fi
    fi

    for _ in {1..20}; do
      if redis-cli ping >/dev/null 2>&1; then
        return 0
      fi
      sleep 1
    done
  fi

  log "Redis is required but not healthy. Please install/start Redis first."
  exit 1
}

ensure_mongodb() {
  if ! command -v mongosh >/dev/null 2>&1 && ! command -v mongo >/dev/null 2>&1; then
    if command -v brew >/dev/null 2>&1; then
      if ! brew tap | grep -q '^mongodb/brew$'; then
        brew tap mongodb/brew
      fi
      if ! brew list mongodb-community@7.0 >/dev/null 2>&1; then
        log "Installing Homebrew package: mongodb-community@7.0"
        brew install mongodb-community@7.0
      fi
      brew services start mongodb/brew/mongodb-community@7.0 >/dev/null 2>&1 || \
      brew services start mongodb-community@7.0 >/dev/null 2>&1 || true
    fi
  fi

  if command -v mongosh >/dev/null 2>&1; then
    for _ in {1..30}; do
      if mongosh --quiet --eval 'db.adminCommand({ ping: 1 })' >/dev/null 2>&1; then
        return 0
      fi
      sleep 1
    done
  elif command -v mongo >/dev/null 2>&1; then
    for _ in {1..30}; do
      if mongo --quiet --eval 'db.adminCommand({ ping: 1 })' >/dev/null 2>&1; then
        return 0
      fi
      sleep 1
    done
  elif command -v nc >/dev/null 2>&1; then
    for _ in {1..30}; do
      if nc -z "${MONGODB_HOST:-localhost}" "${MONGODB_PORT:-27017}" >/dev/null 2>&1; then
        return 0
      fi
      sleep 1
    done
  fi

  log "MongoDB is required but not healthy. Please install/start MongoDB first."
  exit 1
}

ensure_export_tools() {
  if ! command -v pandoc >/dev/null 2>&1; then
    ensure_brew_package pandoc
  fi

  if ! command -v wkhtmltopdf >/dev/null 2>&1; then
    ensure_brew_package wkhtmltopdf
  fi

  if ! command -v pandoc >/dev/null 2>&1; then
    log "pandoc is required for Word export. Please install pandoc first."
    exit 1
  fi

  if ! command -v wkhtmltopdf >/dev/null 2>&1; then
    log "wkhtmltopdf is required for PDF export. Please install wkhtmltopdf first."
    exit 1
  fi
}

ensure_venv() {
  if [[ ! -x "$VENV_DIR/bin/python" ]]; then
    "$PYTHON_BIN" -m venv "$VENV_DIR"
  fi

  "$VENV_DIR/bin/python" -m pip install --upgrade pip
  "$VENV_DIR/bin/pip" install -e "$ROOT_DIR"
}

detect_frontend_pm() {
  if command -v pnpm >/dev/null 2>&1; then
    FRONTEND_PM="pnpm"
    return 0
  fi

  if command -v corepack >/dev/null 2>&1; then
    FRONTEND_PM="corepack-yarn"
    corepack enable >/dev/null 2>&1 || true
    corepack prepare yarn@1.22.22 --activate >/dev/null 2>&1 || true
    return 0
  fi

  log "Missing required frontend package manager: pnpm or corepack"
  exit 1
}

setup_frontend() {
  ensure_cmd node
  detect_frontend_pm

  if [[ ! -d "$ROOT_DIR/frontend/node_modules" ]]; then
    if [[ "$FRONTEND_PM" = "pnpm" ]]; then
      (cd "$ROOT_DIR/frontend" && pnpm install --frozen-lockfile)
    else
      (cd "$ROOT_DIR/frontend" && corepack yarn install --frozen-lockfile --network-timeout 300000)
    fi
  fi
}

write_pidfile() {
  local pid="$1"
  local path="$2"
  printf '%s\n' "$pid" >"$path"
}

launch_detached() {
  local log_file="$1"
  shift

  nohup "$@" </dev/null >"$log_file" 2>&1 &
  local pid="$!"
  disown "$pid" 2>/dev/null || true
  printf '%s\n' "$pid"
}

cleanup_pid() {
  local path="$1"
  if [[ -f "$path" ]]; then
    local pid
    pid="$(cat "$path" 2>/dev/null || true)"
    if [[ -n "${pid:-}" ]] && kill -0 "$pid" >/dev/null 2>&1; then
      kill "$pid" >/dev/null 2>&1 || true
      sleep 1
    fi
    rm -f "$path"
  fi
}

wait_http() {
  local url="$1"
  local name="$2"
  local attempts="${3:-60}"

  for _ in $(seq 1 "$attempts"); do
    if curl -fsS "$url" >/dev/null 2>&1; then
      return 0
    fi
    sleep 2
  done

  log "$name did not become healthy: $url"
  return 1
}

test_login() {
  local backend_port="${TA_BACKEND_PORT:-8000}"
  curl -fsS \
    -H 'Content-Type: application/json' \
    -d "{\"username\":\"${ADMIN_USERNAME:-admin}\",\"password\":\"${ADMIN_PASSWORD:-change_me_local_admin_password}\"}" \
    "http://localhost:${backend_port}/api/auth/login" >/dev/null
}

main() {
  ensure_cmd curl
  ensure_python
  ensure_redis
  ensure_mongodb
  ensure_export_tools
  ensure_venv

  "$VENV_DIR/bin/python" "$ROOT_DIR/scripts/startup/bootstrap_local_env.py" --env-file "$ENV_FILE"
  "$VENV_DIR/bin/python" "$ROOT_DIR/scripts/startup/init_local_env_db.py" --env-file "$ENV_FILE"

  cleanup_pid "$RUNTIME_DIR/local-backend.pid"
  cleanup_pid "$RUNTIME_DIR/local-frontend.pid"

  local backend_port="${TA_BACKEND_PORT:-8000}"
  local frontend_port="${TA_FRONTEND_PORT:-3000}"

  log "Starting backend..."
  (
    cd "$ROOT_DIR"
    backend_pid="$(launch_detached "$LOG_DIR/local-backend.log" "$VENV_DIR/bin/python" -m uvicorn app.main:app --host 0.0.0.0 --port "$backend_port")"
    write_pidfile "$backend_pid" "$RUNTIME_DIR/local-backend.pid"
  )

  wait_http "http://localhost:${backend_port}/api/health" "Backend"
  test_login

  setup_frontend
  log "Starting frontend..."
  (
    cd "$ROOT_DIR/frontend"
    if [[ "$FRONTEND_PM" = "pnpm" ]]; then
      frontend_pid="$(launch_detached "$LOG_DIR/local-frontend.log" pnpm dev --host 0.0.0.0 --port "$frontend_port")"
    else
      frontend_pid="$(launch_detached "$LOG_DIR/local-frontend.log" corepack yarn dev --host 0.0.0.0 --port "$frontend_port")"
    fi
    write_pidfile "$frontend_pid" "$RUNTIME_DIR/local-frontend.pid"
  )

  wait_http "http://localhost:${frontend_port}" "Frontend"

  log ""
  log "Local stack is up:"
  log "  - frontend: http://localhost:${frontend_port}"
  log "  - backend : http://localhost:${backend_port}"
  log "  - health  : http://localhost:${backend_port}/api/health"
  log "  - login   : ${ADMIN_USERNAME:-admin} / ${ADMIN_PASSWORD:-change_me_local_admin_password}"
  log ""
  log "Logs:"
  log "  - $LOG_DIR/local-backend.log"
  log "  - $LOG_DIR/local-frontend.log"
}

main "$@"
