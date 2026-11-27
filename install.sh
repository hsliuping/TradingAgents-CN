#!/usr/bin/env bash
# TradingAgents-CN 社区版一键安装脚本（Linux / macOS；Linux 支持 Debian/Ubuntu 与 RHEL 系 8/9）
#
# 自动完成：Python 环境准备 → 获取代码 → 下载 MongoDB/Redis → 构建/下载前端 →
#           创建虚拟环境并安装依赖 → 生成 .env → 启动服务
#
# 用法:
#   ./install.sh                                  # 默认安装到 ~/TradingAgentsCN
#   ./install.sh --port 8080 --admin-password xx  # 自定义端口与管理员密码
#   ./install.sh --source-path .                  # 本地源码模式（CI 验证用）
#   ./install.sh --mirror https://your-mirror     # 下载镜像前缀（可选）
set -euo pipefail

INSTALL_DIR="${HOME}/TradingAgentsCN"
SOURCE_PATH=""
PORT=8000
MONGO_PORT=27017
REDIS_PORT=6379
ADMIN_PASSWORD=""
SKIP_FRONTEND_BUILD=0
NO_START=0
MIRROR=""
MONGO_VERSION="7.0.14"
REDIS_VERSION="7.2.5"
REPO_URL="https://github.com/hsliuping/TradingAgents-CN"
REF="community"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --install-dir) INSTALL_DIR="$2"; shift 2;;
    --source-path) SOURCE_PATH="$2"; shift 2;;
    --port) PORT="$2"; shift 2;;
    --mongo-port) MONGO_PORT="$2"; shift 2;;
    --redis-port) REDIS_PORT="$2"; shift 2;;
    --admin-password) ADMIN_PASSWORD="$2"; shift 2;;
    --skip-frontend-build) SKIP_FRONTEND_BUILD=1; shift;;
    --no-start) NO_START=1; shift;;
    --mirror) MIRROR="$2"; shift 2;;
    --mongo-version) MONGO_VERSION="$2"; shift 2;;
    --redis-version) REDIS_VERSION="$2"; shift 2;;
    --repo-url) REPO_URL="$2"; shift 2;;
    --ref) REF="$2"; shift 2;;
    -h|--help) sed -n '2,14p' "$0"; exit 0;;
    *) echo "未知参数: $1"; exit 1;;
  esac
done

step() { printf '\n==> %s\n' "$1"; }
ok()   { printf '  [OK] %s\n' "$1"; }
warn() { printf '  [警告] %s\n' "$1"; }
fail() { printf '  [失败] %s\n' "$1" >&2; exit 1; }

OS="$(uname -s | tr '[:upper:]' '[:lower:]')"
ARCH="$(uname -m)"
case "$ARCH" in
  x86_64|amd64) ARCH="x86_64";;
  arm64|aarch64) ARCH="aarch64";;
  *) fail "不支持的 CPU 架构: $ARCH";;
esac
[[ "$OS" == "darwin" && "$ARCH" == "aarch64" ]] && ARCH="arm64"

# --- 发行版检测：debian 系（apt）/ rhel 系（dnf，含 Rocky/Alma/CentOS Stream）---
OSFAMILY=""
EL_MAJOR=""
if [[ "$OS" == "linux" ]]; then
  if [[ -r /etc/os-release ]]; then
    # shellcheck disable=SC1091
    . /etc/os-release
    case "${ID:-}" in
      ubuntu|debian) OSFAMILY="debian";;
      rhel|centos|rocky|almalinux|ol|fedora) OSFAMILY="rhel";;
      *) case "${ID_LIKE:-}" in
           *rhel*|*centos*|*fedora*) OSFAMILY="rhel";;
           *debian*|*ubuntu*) OSFAMILY="debian";;
         esac;;
    esac
    if [[ "$OSFAMILY" == "rhel" ]]; then
      EL_MAJOR="${VERSION_ID:-}"
      EL_MAJOR="${EL_MAJOR%%.*}"
      [[ "$EL_MAJOR" =~ ^[0-9]+$ ]] || EL_MAJOR="0"
    fi
  fi
  # glibc 检查：MongoDB 7 / Node 20 需要 glibc 2.28+（CentOS 7 为 2.17，无法支持）
  GLIBC_VER="$(ldd --version 2>/dev/null | head -n1 | grep -oE '[0-9]+\.[0-9]+$' || true)"
  if [[ -n "$GLIBC_VER" ]] && [[ "$(printf '%s\n2.28\n' "$GLIBC_VER" | sort -V | head -n1)" != "2.28" ]]; then
    fail "系统 glibc 版本过低（$GLIBC_VER < 2.28，如 CentOS 7）：请使用 Rocky Linux / AlmaLinux / CentOS Stream 8-9、Ubuntu 18.04+，或改用 Docker 部署"
  fi
  if [[ "$OSFAMILY" == "rhel" ]] && [[ "${EL_MAJOR:-0}" -lt 8 ]]; then
    fail "不支持的 RHEL 系版本（$EL_MAJOR）：仅支持 8/9（Rocky Linux、AlmaLinux、CentOS Stream、RHEL）"
  fi
fi

# root 环境（如容器）没有 sudo，需要直连包管理器
SUDO="sudo"
[[ "$(id -u)" -eq 0 ]] && SUDO=""
can_root() { [[ "$(id -u)" -eq 0 ]] || sudo -n true 2>/dev/null; }

resolve_url() {
  local url="$1"
  if [[ -n "$MIRROR" ]]; then echo "${MIRROR%/}/${url##*/}"; else echo "$url"; fi
}

download() {
  local url dest dir
  url="$(resolve_url "$1")"; dest="$2"; dir="$(dirname "$dest")"
  mkdir -p "$dir"
  echo "  下载: $url"
  curl -fL --retry 3 --retry-delay 2 -o "$dest" "$url" || fail "下载失败: $url"
  ok "已下载: $(basename "$dest")"
}

port_open() {
  (exec 3<>"/dev/tcp/127.0.0.1/$1") 2>/dev/null && exec 3>&- && return 0
  return 1
}

wait_port() { # port timeout name
  local deadline=$(( $(date +%s) + $2 ))
  while [[ $(date +%s) -lt $deadline ]]; do
    if port_open "$1"; then ok "$3 已就绪（端口 $1）"; return 0; fi
    sleep 2
  done
  return 1
}

wait_health() { # port timeout
  local deadline=$(( $(date +%s) + $2 ))
  while [[ $(date +%s) -lt $deadline ]]; do
    if curl -fsS --max-time 5 "http://127.0.0.1:$1/api/health" 2>/dev/null | grep -q '"status": *"ok"'; then
      return 0
    fi
    sleep 3
  done
  return 1
}

find_python() {
  local cand v
  for cand in python3.13 python3.12 python3.11 python3; do
    command -v "$cand" >/dev/null 2>&1 || continue
    v="$("$cand" -c 'import sys;print("%d.%d"%sys.version_info[:2])' 2>/dev/null || true)"
    if [[ "$v" == 3.* ]]; then
      local minor="${v#3.}"
      if [[ "$minor" -ge 11 ]]; then echo "$cand"; return 0; fi
    fi
  done
  return 1
}

ensure_python() {
  local py
  # 本函数通过 stdout 返回解释器名，调用方用 $(...) 捕获；所有提示信息必须走 stderr
  if py="$(find_python)"; then ok "Python 已就绪: $py ($("$py" -V 2>&1))" >&2; echo "$py"; return 0; fi

  warn "未检测到 Python 3.11+，尝试自动安装" >&2
  if [[ "$OS" == "darwin" ]]; then
    if command -v brew >/dev/null 2>&1; then
      brew install python@3.11 || true
    else
      fail "未找到 brew。请安装 Homebrew（https://brew.sh）后重试，或手动安装 Python 3.11+"
    fi
  else
    if [[ "$OSFAMILY" == "rhel" ]] && can_root; then
      # EL9 AppStream / EL8 8.6+ 模块提供 python3.11（默认 python3 版本过低）
      # 注意：本分支在 $(ensure_python) 命令替换中执行，dnf 输出必须重定向到 stderr，
      # 否则会把安装日志一起捕获进 $PYTHON（后续执行时报 "File name too long"）
      $SUDO dnf install -y python3.11 python3.11-pip >&2 || $SUDO dnf install -y python3.11 >&2 \
        || fail "dnf 安装 Python 3.11 失败（EL8 需 8.6+ AppStream 模块）"
    elif [[ "$OSFAMILY" == "debian" ]] && can_root; then
      $SUDO apt-get update -qq >&2 || true
      $SUDO apt-get install -y python3 python3-venv python3-pip >&2 || fail "apt 安装 Python 失败"
    else
      fail "无法自动安装 Python（需要 root/sudo 或包管理器）。请手动安装 Python 3.11+ 后重试"
    fi
  fi
  py="$(find_python)" || fail "Python 自动安装后仍未检测到 3.11+"
  ok "Python 自动安装完成: $py" >&2
  echo "$py"
}

ensure_node() {
  # 确保前端构建可用的 Node.js >= 18；缺失时下载官方 v20 预构建包到 $RUNTIME_DIR/node
  if command -v node >/dev/null 2>&1; then
    local nmaj
    nmaj="$(node -v 2>/dev/null | sed 's/^v//' | cut -d. -f1)"
    if [[ "${nmaj:-0}" -ge 18 ]]; then
      ok "Node.js 已就绪: $(node -v)"
      return 0
    fi
    warn "Node.js 版本过低（$(node -v) < 18），将下载官方 v20 预构建包"
  fi
  if [[ "$OS" == "darwin" ]]; then
    command -v brew >/dev/null 2>&1 || fail "未找到 Node.js 18+。请安装 Node.js 后重试（macOS 可用 brew install node）"
    brew install node || fail "brew install node 失败"
    ok "Node.js 安装完成: $(node -v)"
    return 0
  fi
  local narch fname ndir
  case "$ARCH" in
    x86_64)  narch="x64";;
    aarch64) narch="arm64";;
    *) fail "Node.js 无此架构预构建包: $ARCH";;
  esac
  # 从 SHASUMS256.txt 取 latest-v20.x 实际文件名（用 .tar.gz 避免 xz 依赖）
  fname="$(curl -fsSL "https://nodejs.org/dist/latest-v20.x/SHASUMS256.txt" \
    | grep -E "node-v[0-9.]+-linux-$narch\.tar\.gz$" | awk '{print $2}' | head -1)"
  [[ -n "$fname" ]] || fail "获取 Node.js v20 最新版本文件名失败"
  ndir="$RUNTIME_DIR/node"
  rm -rf "$ndir"
  TMPX="$(mktemp -d)"
  download "https://nodejs.org/dist/latest-v20.x/$fname" "$TMPX/$fname"
  tar -xzf "$TMPX/$fname" -C "$TMPX"
  mv "$TMPX"/node-v*-linux-"$narch" "$ndir"
  rm -rf "$TMPX"
  export PATH="$ndir/bin:$PATH"
  ok "Node.js 已安装: $(node -v)"
}

# ============================== 主流程 ==============================

if [[ -n "$SOURCE_PATH" ]]; then
  ROOT="$(cd "$SOURCE_PATH" && pwd)"
  step "本地源码模式：$ROOT"
else
  ROOT="$INSTALL_DIR"
  step "安装目录：$ROOT"
fi

RUNTIME_DIR="$ROOT/runtime"
DATA_DIR="$ROOT/data"
LOGS_DIR="$ROOT/logs"
mkdir -p "$RUNTIME_DIR" "$DATA_DIR/mongodb" "$DATA_DIR/redis" "$LOGS_DIR"

# ---- 1. Python ----
step "[1/8] 检查 Python 环境"
PYTHON="$(ensure_python)"

# ---- 2. 获取代码 ----
step "[2/8] 获取代码"
if [[ -z "$SOURCE_PATH" ]]; then
  ZIP="$(mktemp -d)/src.zip"
  download "$REPO_URL/archive/refs/heads/$REF.zip" "$ZIP"
  TMPX="$(mktemp -d)"
  if command -v unzip >/dev/null 2>&1; then
    unzip -q "$ZIP" -d "$TMPX"
  else
    "$PYTHON" -m zipfile -e "$ZIP" "$TMPX"
  fi
  INNER="$(find "$TMPX" -mindepth 1 -maxdepth 1 -type d | head -1)"
  mkdir -p "$ROOT"
  find "$ROOT" -mindepth 1 -maxdepth 1 ! -name runtime ! -name data ! -name logs -exec rm -rf {} +
  cp -R "$INNER"/. "$ROOT"/
  rm -rf "$TMPX" "$(dirname "$ZIP")"
  ok "代码已就绪"
else
  ok "使用本地源码：$ROOT"
fi
[[ -f "$ROOT/app/main.py" ]] || fail "代码不完整（缺少 app/main.py）：$ROOT"

# ---- 3. MongoDB ----
step "[3/8] 准备 MongoDB $MONGO_VERSION"
MONGOD_BIN="$RUNTIME_DIR/mongodb/bin/mongod"
if [[ ! -x "$MONGOD_BIN" ]]; then
  # EL8 用 rhel8 构建，EL9+ 用 rhel90 构建（两者 glibc/OpenSSL 基线不同，不能混用）
  if [[ "$OSFAMILY" == "rhel" ]]; then
    if [[ "${EL_MAJOR:-0}" -ge 9 ]]; then MONGO_DISTRO="rhel90"; else MONGO_DISTRO="rhel8"; fi
  else
    MONGO_DISTRO="ubuntu2204"
  fi
  case "$OS-$ARCH" in
    linux-x86_64)  PKG="mongodb-linux-x86_64-$MONGO_DISTRO-$MONGO_VERSION.tgz";;
    linux-aarch64) PKG="mongodb-linux-aarch64-$MONGO_DISTRO-$MONGO_VERSION.tgz";;
    darwin-arm64)  PKG="mongodb-macos-arm64-$MONGO_VERSION.tgz";;
    darwin-x86_64) PKG="mongodb-macos-x86_64-$MONGO_VERSION.tgz";;
    *) fail "MongoDB 无此平台预编译包: $OS-$ARCH";;
  esac
  TMPX="$(mktemp -d)"
  # fastdl 的 macOS 目录名为 osx/（不是 macos/）
  DL_OS="linux"; [[ "$OS" == "darwin" ]] && DL_OS="osx"
  download "https://fastdl.mongodb.org/$DL_OS/$PKG" "$TMPX/$PKG"
  tar -xzf "$TMPX/$PKG" -C "$TMPX"
  INNER="$(find "$TMPX" -mindepth 1 -maxdepth 1 -type d | head -1)"
  mv "$INNER" "$RUNTIME_DIR/mongodb"
  rm -rf "$TMPX"
  # EL 最小安装/容器可能缺 libcurl/openssl 动态库，用 ldd 探测并补齐
  if [[ "$OSFAMILY" == "rhel" ]]; then
    MISSING_LIBS="$(ldd "$MONGOD_BIN" 2>/dev/null | awk '/not found/{print $1}' | sort -u | tr '\n' ' ' || true)"
    if [[ -n "$MISSING_LIBS" ]]; then
      warn "mongod 缺少动态库: $MISSING_LIBS，尝试 dnf 补齐"
      $SUDO dnf install -y libcurl openssl-libs || true
    fi
  fi
fi
ok "mongod: $MONGOD_BIN"

# ---- 4. Redis ----
step "[4/8] 准备 Redis"

build_redis_from_source() {
  warn "尝试源码编译 Redis $REDIS_VERSION（较慢，需要 gcc/make）"
  command -v make >/dev/null 2>&1 || fail "未找到 make，无法源码编译 Redis。请先安装编译工具链（如 dnf install -y gcc make）"
  TMPX="$(mktemp -d)"
  download "https://download.redis.io/releases/redis-$REDIS_VERSION.tar.gz" "$TMPX/redis.tgz"
  tar -xzf "$TMPX/redis.tgz" -C "$TMPX"
  ( cd "$TMPX/redis-$REDIS_VERSION" && make -j"$(nproc 2>/dev/null || echo 2)" BUILD_TLS=no >/dev/null )
  mkdir -p "$RUNTIME_DIR/redis"
  cp "$TMPX/redis-$REDIS_VERSION/src/redis-server" "$RUNTIME_DIR/redis/redis-server"
  chmod +x "$RUNTIME_DIR/redis/redis-server"
  REDIS_BIN="$RUNTIME_DIR/redis/redis-server"
  rm -rf "$TMPX"
}

REDIS_BIN="$(command -v redis-server || true)"
if [[ -z "$REDIS_BIN" ]]; then
  if [[ "$OS" == "darwin" ]] && command -v brew >/dev/null 2>&1; then
    brew install redis || fail "brew install redis 失败"
    REDIS_BIN="$(brew --prefix redis)/bin/redis-server"
  elif command -v apt-get >/dev/null 2>&1 && can_root; then
    $SUDO apt-get update -qq || true
    $SUDO apt-get install -y redis-server || fail "apt 安装 redis 失败"
    REDIS_BIN="$(command -v redis-server)"
  elif [[ "$OSFAMILY" == "rhel" ]] && command -v dnf >/dev/null 2>&1 && can_root; then
    # EL 各版本仓库的 Redis 版本不一且偏旧，统一源码编译保证版本一致
    # diffutils（cmp）、which 为 Redis Makefile 构建过程中会调用的工具
    $SUDO dnf install -y gcc make diffutils which || fail "dnf 安装 gcc/make 失败"
    build_redis_from_source
  else
    build_redis_from_source
  fi
fi
ok "redis-server: $REDIS_BIN"

if [[ "$NO_START" -eq 0 ]]; then
  # ---- 启动数据库 ----
  step "[5/8] 启动 MongoDB / Redis"
  if port_open "$MONGO_PORT"; then
    ok "MongoDB 端口 $MONGO_PORT 已在监听，跳过启动"
  else
    nohup "$MONGOD_BIN" --dbpath "$DATA_DIR/mongodb" --port "$MONGO_PORT" --bind_ip 127.0.0.1 \
      >"$LOGS_DIR/mongod.out.log" 2>"$LOGS_DIR/mongod.err.log" &
    echo $! > "$RUNTIME_DIR/mongod.pid"
    wait_port "$MONGO_PORT" 90 "MongoDB" || { tail -20 "$LOGS_DIR/mongod.err.log" 2>/dev/null || true; fail "MongoDB 未能就绪"; }
  fi
  if port_open "$REDIS_PORT"; then
    ok "Redis 端口 $REDIS_PORT 已在监听，跳过启动"
  else
    ( cd "$DATA_DIR/redis" && nohup "$REDIS_BIN" --port "$REDIS_PORT" --bind 127.0.0.1 --save "" --appendonly no \
      >"$LOGS_DIR/redis.out.log" 2>"$LOGS_DIR/redis.err.log" & echo $! > "$RUNTIME_DIR/redis.pid" )
    wait_port "$REDIS_PORT" 60 "Redis" || { tail -20 "$LOGS_DIR/redis.err.log" 2>/dev/null || true; fail "Redis 未能就绪"; }
  fi
else
  step "[5/8] 跳过数据库启动（--no-start）"
fi

# ---- 5. 前端 ----
step "[6/8] 准备前端"
if [[ -f "$ROOT/frontend/dist/index.html" ]]; then
  ok "前端构建产物已存在，跳过"
elif [[ "$SKIP_FRONTEND_BUILD" -eq 1 ]]; then
  fail "指定了 --skip-frontend-build 但 frontend/dist 不存在"
else
  ensure_node
  echo "  使用 npm 构建前端（首次较慢）"
  ( cd "$ROOT/frontend" && NODE_OPTIONS=--max-old-space-size=4096 npm ci --no-audit --no-fund && NODE_OPTIONS=--max-old-space-size=4096 npm run build ) || fail "前端构建失败"
  ok "前端构建完成"
fi

# ---- 6. 虚拟环境与依赖 ----
step "[7/8] 安装 Python 依赖"
VENV_DIR="$ROOT/.venv"
VENV_PY="$VENV_DIR/bin/python"
if [[ ! -x "$VENV_PY" ]]; then
  "$PYTHON" -m venv "$VENV_DIR" || fail "创建虚拟环境失败（Linux 请确认已安装 python3-venv）"
fi
"$VENV_PY" -m pip install --upgrade pip --quiet
PIP_ARGS=(-m pip install -e . --quiet)
if [[ -n "$MIRROR" ]]; then PIP_ARGS+=(-i "${MIRROR%/}/pypi/simple"); fi
( cd "$ROOT" && "$VENV_PY" "${PIP_ARGS[@]}" ) || fail "依赖安装失败（可尝试 --mirror 换源后重试）"
ok "依赖安装完成"

# Chroma 要求 sqlite3 >= 3.35；EL8/EL9 系统自带 3.34，会导致 import chromadb 直接失败。
# 在 venv 内安装 pysqlite3-binary，并用 sitecustomize 把 sqlite3 模块替换掉（仅对该 venv 生效）
if [[ "$OS" == "linux" ]]; then
  SQLITE_VER="$("$VENV_PY" -c 'import sqlite3;print(sqlite3.sqlite_version)' 2>/dev/null || echo "0")"
  if [[ "$(printf '%s\n3.35.0\n' "$SQLITE_VER" | sort -V | head -n1)" != "3.35.0" ]]; then
    warn "系统 sqlite3 版本过低（$SQLITE_VER < 3.35.0，Chroma 需要），改用 pysqlite3-binary"
    "$VENV_PY" -m pip install --quiet pysqlite3-binary || fail "pysqlite3-binary 安装失败"
    SITE_DIR="$("$VENV_PY" -c 'import site;print(site.getsitepackages()[0])')"
    cat > "$SITE_DIR/sitecustomize.py" <<'PY'
# 由 install.sh 生成：EL8/EL9 系统 sqlite3 过旧时，用 pysqlite3 替换 sqlite3（Chroma 需要 >= 3.35）
try:
    import pysqlite3
    import sys

    sys.modules["sqlite3"] = sys.modules.pop("pysqlite3")
except Exception:
    pass
PY
    ok "sqlite3 已替换为 $("$VENV_PY" -c 'import sqlite3;print(sqlite3.sqlite_version)' 2>/dev/null)"
  fi
fi

# ---- 7. 生成 .env ----
step "生成 .env 配置"
[[ -n "$ADMIN_PASSWORD" ]] || ADMIN_PASSWORD="admin$( "$PYTHON" -c 'import secrets;print(secrets.token_hex(4))' )"
MONGO_PORT="$MONGO_PORT" REDIS_PORT="$REDIS_PORT" WEB_PORT="$PORT" \
ADMIN_PASSWORD="$ADMIN_PASSWORD" \
"$PYTHON" - "$ROOT/.env.example" "$ROOT/.env" <<'PY'
import os, re, secrets, sys
src, dst = sys.argv[1], sys.argv[2]
overrides = {
    "MONGODB_HOST": "127.0.0.1",
    "MONGODB_PORT": os.environ["MONGO_PORT"],
    "MONGODB_USERNAME": "",
    "MONGODB_PASSWORD": "",
    # 本地 mongod 未启用认证，必须清掉 .env.example 里的占位凭据连接串（否则认证失败）
    "MONGODB_CONNECTION_STRING": "mongodb://127.0.0.1:%s/tradingagents" % os.environ["MONGO_PORT"],
    "REDIS_HOST": "127.0.0.1",
    "REDIS_PORT": os.environ["REDIS_PORT"],
    "REDIS_PASSWORD": "",
    "REDIS_DB": "0",
    "JWT_SECRET": secrets.token_hex(32),
    "CSRF_SECRET": secrets.token_hex(32),
    "ADMIN_DEFAULT_PASSWORD": os.environ["ADMIN_PASSWORD"],
    "HOST": "127.0.0.1",
    "PORT": os.environ["WEB_PORT"],
    "DEBUG": "false",
}
seen, out = set(), []
with open(src, encoding="utf-8") as f:
    for line in f.read().splitlines():
        m = re.match(r"^([A-Za-z_][A-Za-z0-9_]*)=", line)
        if m and m.group(1) in overrides:
            out.append(f"{m.group(1)}={overrides[m.group(1)]}")
            seen.add(m.group(1))
        else:
            out.append(line)
for k, v in overrides.items():
    if k not in seen:
        out.append(f"{k}={v}")
with open(dst, "w", encoding="utf-8") as f:
    f.write("\n".join(out) + "\n")
PY
ok ".env 已生成（JWT/CSRF 密钥随机，管理员密码见下方输出）"

if [[ "$NO_START" -eq 1 ]]; then
  step "安装完成（--no-start，未启动服务）"
  echo "  启动命令: $VENV_PY installer/run_server.py"
  exit 0
fi

# ---- 8. 启动服务 ----
step "[8/8] 启动服务"
( cd "$ROOT" && nohup "$VENV_PY" installer/run_server.py \
  >"$LOGS_DIR/server.out.log" 2>"$LOGS_DIR/server.err.log" & echo $! > "$RUNTIME_DIR/server.pid" )
if ! wait_health "$PORT" 300; then
  warn "服务未在 5 分钟内就绪，最近日志："
  tail -20 "$LOGS_DIR/server.err.log" 2>/dev/null || true
  fail "启动失败"
fi
ok "服务已就绪"

# ---- 生成启动/停止脚本（非本地源码模式）----
if [[ -z "$SOURCE_PATH" ]]; then
  cat > "$ROOT/start.sh" <<EOF
#!/usr/bin/env bash
cd "$ROOT"
nohup "$VENV_PY" installer/run_server.py >"$LOGS_DIR/server.out.log" 2>"$LOGS_DIR/server.err.log" &
echo \$! > "$RUNTIME_DIR/server.pid"
echo "TradingAgents-CN 已启动: http://127.0.0.1:$PORT"
EOF
  cat > "$ROOT/stop.sh" <<EOF
#!/usr/bin/env bash
for f in "$RUNTIME_DIR/server.pid" "$RUNTIME_DIR/mongod.pid" "$RUNTIME_DIR/redis.pid"; do
  [[ -f "\$f" ]] && kill "\$(cat "\$f")" 2>/dev/null || true
  rm -f "\$f"
done
echo "TradingAgents-CN 已停止"
EOF
  chmod +x "$ROOT/start.sh" "$ROOT/stop.sh"
fi

cat <<EOF

==================================================
 TradingAgents-CN 安装完成
==================================================
  访问地址   : http://127.0.0.1:$PORT
  管理员账号 : admin
  管理员密码 : $ADMIN_PASSWORD
  项目目录   : $ROOT
  日志目录   : $LOGS_DIR
$([[ -z "$SOURCE_PATH" ]] && echo "  启动/停止  : ./start.sh / ./stop.sh")
==================================================
EOF
