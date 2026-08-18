# TradingAgents-CN Pro - 单容器统一部署镜像（复用现有镜像版）
# 所有服务（MongoDB / Redis / Backend / Frontend / Nginx）打包到一个镜像
# 通过 s6-overlay 作为 PID 1 统一管理进程生命周期
#
# 关键设计：复用 hsliup/tradingagents-pro-backend + hsliup/tradingagents-pro-frontend
# 避免重新安装 Python 依赖、避免 npm 重新下载（本地已缓存）
#
# 构建：bash deploy-all-in-one/build.sh
# 运行：docker run -d -p 8082:8082 -v ta-data:/data/db tradingagents-cn-pro:3.0.0

# ==============================================================================
# 全局 ARG（必须在第一个 FROM 之前声明，所有 stage 可见）
# ==============================================================================
ARG BASE_BACKEND=hsliup/tradingagents-pro-backend:3-latest
ARG MONGO_IMAGE=mongo:7.0
ARG REDIS_IMAGE=redis:7-alpine
ARG NGINX_IMAGE=nginx:alpine

# ==============================================================================
# 阶段 0：用后端基础镜像生成 SearXNG wheel（不引入额外 Python 镜像）
# 基础镜像内已含 Python + searxng 运行依赖（msgspec/lxml 等），无需额外安装
# version_frozen.py：searx/version.py 的 freeze 用 git 获取版本号（若无 git 则写默认值兜底）
# ==============================================================================
FROM ${BASE_BACKEND} AS searxng-wheel-builder
COPY searxng /build/searxng
# 后端基础镜像不含 searxng 运行依赖（msgspec/lxml 等），
# setup.py 生成 metadata 时会 import searx → 触发 msgspec 导入，必须先装
RUN pip install --no-cache-dir -r /build/searxng/requirements.txt
RUN cd /build/searxng && \
    # 冻结版本号：有 git 就用 searx 自带的 freeze；没 git 就用 python 直接写兜底文件
    (command -v git >/dev/null 2>&1 && python -m searx.version freeze) || \
    python -c "open('searx/version_frozen.py','w').write('VERSION_STRING=\"2026.8.16+local\"\nVERSION_TAG=\"2026.8.16+local\"\nDOCKER_TAG=\"2026.8.16-local\"\nGIT_URL=\"https://github.com/searxng/searxng\"\nGIT_BRANCH=\"local\"\n')" && \
    mkdir -p /build/wheels && \
    python -m pip wheel . --no-deps --no-build-isolation -w /build/wheels && \
    python -c "import zipfile,glob; z=zipfile.ZipFile(glob.glob('/build/wheels/searxng-*.whl')[0]); assert 'searx/version_frozen.py' in z.namelist(), 'version_frozen missing'"

# ==============================================================================
# 阶段 1：构建运行时镜像（复用基础镜像 + 添加 MongoDB/Redis/Nginx/s6）
# ==============================================================================
FROM ${MONGO_IMAGE} AS mongo-source
FROM ${REDIS_IMAGE} AS redis-source
FROM ${NGINX_IMAGE} AS nginx-source

# 运行时基础镜像（复用现成后端镜像，包含所有 Python 依赖）
FROM ${BASE_BACKEND} AS runtime-base

# 元数据
LABEL maintainer="hsliup@163.com" \
      version="3.0.0" \
      description="TradingAgents-CN Pro - 单容器统一部署（复用现有镜像版）" \
      org.opencontainers.image.source="https://github.com/hsliuping/TradingAgents-CN-Pro"

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONIOENCODING=utf-8 \
    PYTHONUTF8=1 \
    PYTHONUNBUFFERED=1

# ------------------------------------------------------------------------------
# 提取 MongoDB 二进制（从 mongo:8.0 镜像）
# MongoDB 8.0 使用 mongosh（替代旧版 mongo shell）
# ------------------------------------------------------------------------------
COPY --from=mongo-source /usr/bin/mongod /usr/local/bin/mongod

# ------------------------------------------------------------------------------
# 提取 MongoDB 依赖的共享库
# MongoDB 4.4 需要 libssl.so.1.1 + libcrypto.so.1.1（OpenSSL 1.1，Debian 12 已移除）
# MongoDB 8.0 使用 OpenSSL 3.x，基础镜像 Debian 12 自带，无需额外复制
# 如果需要兼容 4.4，取消下面两行注释：
# COPY --from=mongo-source /usr/lib/x86_64-linux-gnu/libssl.so.1.1 /usr/lib/x86_64-linux-gnu/libssl.so.1.1
# COPY --from=mongo-source /usr/lib/x86_64-linux-gnu/libcrypto.so.1.1 /usr/lib/x86_64-linux-gnu/libcrypto.so.1.1
# ------------------------------------------------------------------------------
RUN ldconfig 2>/dev/null || true

# ------------------------------------------------------------------------------
# 提取 Redis 二进制（从 redis:7-alpine 镜像）
# ------------------------------------------------------------------------------
COPY --from=redis-source /usr/local/bin/redis-server /usr/local/bin/redis-server

# ------------------------------------------------------------------------------
# 提取 Nginx（从 nginx:alpine 镜像）
# ------------------------------------------------------------------------------
COPY --from=nginx-source /usr/sbin/nginx /usr/sbin/nginx
COPY --from=nginx-source /etc/nginx /etc/nginx
COPY --from=nginx-source /var/log/nginx /var/log/nginx
COPY --from=nginx-source /usr/lib/nginx /usr/lib/nginx
COPY --from=nginx-source /usr/share/nginx /usr/share/nginx
# Nginx 需要的库文件
COPY --from=nginx-source /lib /lib
COPY --from=nginx-source /usr/lib /usr/lib

# ------------------------------------------------------------------------------
# 安装 s6-overlay v3.2.3.2（轻量级 init 系统，本地文件）
# ------------------------------------------------------------------------------
# s6-overlay v3 需要 4 个包：noarch + x86_64 + symlinks-noarch + symlinks-arch
# 顺序很重要：noarch 先（包含 /init），然后是 arch 二进制，最后是符号链接
COPY deploy-all-in-one/s6-overlay-noarch.tar.xz /tmp/s6-noarch.tar.xz
COPY deploy-all-in-one/s6-overlay-x86_64.tar.xz /tmp/s6-x86_64.tar.xz
COPY deploy-all-in-one/s6-overlay-symlinks-noarch.tar.xz /tmp/s6-symlinks-noarch.tar.xz
COPY deploy-all-in-one/s6-overlay-symlinks-arch.tar.xz /tmp/s6-symlinks-arch.tar.xz

RUN echo "安装 s6-overlay v3.2.3.2 (4 个包)..." && \
    apt-get update && \
    apt-get install -y --no-install-recommends xz-utils && \
    rm -rf /var/lib/apt/lists/* && \
    # 1. noarch（包含 /init 和 /etc/s6-overlay）
    tar -C / -xJf /tmp/s6-noarch.tar.xz && \
    # 2. x86_64 平台二进制
    tar -C / -xJf /tmp/s6-x86_64.tar.xz && \
    # 3. 跨平台符号链接
    tar -C / -xJf /tmp/s6-symlinks-noarch.tar.xz && \
    # 4. 架构特定符号链接
    tar -C / -xJf /tmp/s6-symlinks-arch.tar.xz && \
    # 清理
    rm /tmp/s6-*.tar.xz && \
    # 验证 /init 存在
    ls -la /init && \
    echo "s6-overlay 安装完成"

# 安装 gosu（用于权限降级）和 curl（用于健康检查）
# 注意：基础镜像可能已经有这些，但显式安装保证可用
RUN apt-get update && apt-get install -y --no-install-recommends gosu curl ca-certificates gnupg && rm -rf /var/lib/apt/lists/*

# ------------------------------------------------------------------------------
# 创建系统用户
# ------------------------------------------------------------------------------
RUN groupadd --system --gid 1000 appuser 2>/dev/null || true && \
    useradd --system --uid 1000 --gid 1000 \
        --home-dir /app --shell /usr/sbin/nologin appuser 2>/dev/null || true && \
    groupadd --system --gid 999 mongodb 2>/dev/null || true && \
    useradd --system --uid 999 --gid 999 --no-create-home mongodb 2>/dev/null || true && \
    groupadd --system --gid 998 redis 2>/dev/null || true && \
    useradd --system --uid 998 --gid 998 --no-create-home redis 2>/dev/null || true && \
    echo "用户创建完成"

# ------------------------------------------------------------------------------
# 复制前端构建产物（从本地 frontend/dist，需先 npm run build）
# ------------------------------------------------------------------------------
COPY frontend/dist /app/frontend/dist

# 复制应用代码（如果基础镜像不包含最新代码）
# 基础镜像已经包含代码，这里复制新代码覆盖
COPY app /app/app
COPY core /app/core
COPY tradingagents /app/tradingagents
COPY config /app/config
COPY scripts /app/scripts
COPY install /app/install
COPY migrations /app/migrations
# 第三方开源组件声明（SearXNG AGPL-3.0 合规，对应源码补丁随 config/searxng/ 分发）
COPY THIRD_PARTY_NOTICES.md /app/THIRD_PARTY_NOTICES.md

# ------------------------------------------------------------------------------
# 源码保护：编译 Python 代码为 .pyc 字节码，删除 .py 源码
# 参考 v2.0 docker/scripts/compile-and-cleanup.sh
# 保留 __init__.py（包导入）、__main__.py（入口）、tradingagents/（开源）
# 京东云版不需要 Cython 编译（License 已禁用），纯字节码编译即可
# ------------------------------------------------------------------------------
# 清理宿主机带来的 __pycache__ 和旧 .pyc（避免版本不匹配）
RUN find /app/app /app/core -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true && \
    find /app/app /app/core -name "*.pyc" -delete 2>/dev/null || true
# 复制编译脚本并执行
COPY deploy-all-in-one/compile-and-cleanup.sh /tmp/compile-and-cleanup.sh
RUN cd /app && chmod +x /tmp/compile-and-cleanup.sh && \
    /tmp/compile-and-cleanup.sh && \
    rm -f /tmp/compile-and-cleanup.sh

# 用户手册文件（向量索引用，打包到镜像，容器内路径 /app/docs/02-user-guide/）
COPY docs/02-user-guide/user-manual-v3.0.md /app/docs/02-user-guide/
COPY docs/02-user-guide/jdyun-user-manual-v3.0.md /app/docs/02-user-guide/

# ------------------------------------------------------------------------------
# SearXNG Web 搜索引擎（智能助手实时资讯）
# wheel 由阶段 0（searxng-wheel-builder）生成，使用同一基础镜像的 Python 环境
# 配置文件已随 COPY config /app/config 包含（config/searxng/settings.yml）
# ------------------------------------------------------------------------------
COPY --from=searxng-wheel-builder /build/wheels/searxng-*.whl /tmp/
RUN pip install --no-cache-dir /tmp/searxng-*.whl && \
    rm -f /tmp/searxng-*.whl && \
    python -c "import searx; print('searxng OK:', searx.__file__)"

# 预生成的向量索引种子数据（首次启动时从 /app/qdrant-seed 导入到持久化卷，避免全量 embedding 请求）
# 注意：种子数据中的签名在 build.sh 中通过 update_seed_signature_local.py 更新（确保跨环境一致）
COPY deploy-all-in-one/qdrant-seed /app/qdrant-seed

# ------------------------------------------------------------------------------
# 复制 s6-overlay 服务定义和配置文件
# ------------------------------------------------------------------------------
COPY deploy-all-in-one/s6-rc.d /etc/s6-overlay/s6-rc.d
COPY deploy-all-in-one/conf/nginx.conf /etc/nginx/nginx.conf
COPY deploy-all-in-one/conf/mongod.conf /etc/mongod.conf
COPY deploy-all-in-one/conf/redis.conf /etc/redis/redis.conf

# ------------------------------------------------------------------------------
# 创建数据目录并设置权限
# ------------------------------------------------------------------------------
RUN mkdir -p /data/db /var/lib/redis /app/runtime /app/logs /app/data \
             /var/log/mongodb /var/log/redis \
             /var/run && \
    chown -R appuser:appuser /app /var/log/nginx /app/frontend 2>/dev/null || true && \
    chown -R mongodb:mongodb /data/db /var/log/mongodb 2>/dev/null || true && \
    chown -R redis:redis /var/lib/redis /var/log/redis 2>/dev/null || true && \
    chmod 750 /data/db /var/lib/redis /app/runtime /app/logs /app/data && \
    # s6 服务脚本需要可执行权限
    find /etc/s6-overlay/s6-rc.d -name "run" | xargs chmod +x 2>/dev/null || true && \
    echo "目录权限设置完成"

# ------------------------------------------------------------------------------
# 关键步骤：s6-overlay v3 服务结构配置
#
# s6-overlay v3 oneshot 服务：
#   - type:    包含 "oneshot"
#   - up:      execline 命令链（不带 shebang！），s6-rc-oneshot-run 把内容当作命令链
#              每行一个命令，从 /command/ 等路径找命令
#              典型格式: with-contenv\nbash /path/to/script.sh
#   - run:     不需要（s6-rc-oneshot-run 只读 up）
#
# s6-overlay v3 longrun 服务：
#   - type:    包含 "longrun"
#   - run:     s6-supervise 自动启动
#   - up:      标记就绪的信号文件（通常为空）
# ------------------------------------------------------------------------------
RUN mkdir -p /etc/s6-overlay/user-bundles.d/user/contents.d && \
    for svc in init init-data mongodb redis backend searxng nginx; do \
        ln -sf /etc/s6-overlay/s6-rc.d/$svc /etc/s6-overlay/user-bundles.d/user/contents.d/$svc; \
    done && \
    ls -la /etc/s6-overlay/user-bundles.d/user/contents.d/ && \
    # oneshot 服务：up 是 execline 命令链（直接调用 bash 执行 run 脚本）\
    for svc in init init-data; do \
        printf '/command/with-contenv\nbash /etc/s6-overlay/s6-rc.d/%s/run\n' "$svc" > /etc/s6-overlay/s6-rc.d/$svc/up; \
    done && \
    # longrun 服务：up 是空文件（标记就绪）\
    for svc in mongodb redis backend searxng nginx; do \
        : > /etc/s6-overlay/s6-rc.d/$svc/up; \
    done && \
    echo "s6-overlay contents.d 符号链接和 up 文件创建完成" && \
    cat /etc/s6-overlay/s6-rc.d/init/up

# ------------------------------------------------------------------------------
# 环境变量默认值
# ------------------------------------------------------------------------------
ENV APP_USER=appuser \
    APP_UID=1000 \
    APP_GID=1000 \
    MONGODB_HOST=127.0.0.1 \
    MONGODB_PORT=27017 \
    MONGODB_USERNAME=admin \
    MONGODB_DATABASE=tradingagents \
    MONGODB_AUTH_SOURCE=admin \
    REDIS_HOST=127.0.0.1 \
    REDIS_PORT=6379 \
    BACKEND_PORT=8000 \
    NGINX_PORT=8082 \
    TZ=Asia/Shanghai

# 暴露端口
EXPOSE 8082

# 健康检查
HEALTHCHECK --interval=30s --timeout=10s --retries=3 --start-period=60s \
    CMD curl -f http://127.0.0.1:8082/nginx-health || exit 1

# 入口点：s6-overlay 作为 PID 1
ENTRYPOINT ["/init"]
