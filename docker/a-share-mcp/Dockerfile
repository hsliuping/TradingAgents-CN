# A股 MCP 服务 - 基于 Baostock 的 A 股市场数据
# 参考: https://github.com/24mlight/a-share-mcp-is-just-i-need
# 使用 mcp-proxy 将 stdio 转为 HTTP/SSE，供 TradingAgents 调用

# Stage 1: 准备 mcp-proxy 和 Node 运行时（需用 bookworm 以兼容 python:slim 的 glibc）
FROM node:22-bookworm-slim AS node-runtime
WORKDIR /app
RUN npm init -y && npm install mcp-proxy

# Stage 2: 主镜像（Python + 从 stage1 复制 Node 和 mcp-proxy）
FROM python:3.12-slim

WORKDIR /app

# 仅安装 unzip（最小依赖，避免 apt 503）
RUN apt-get update && apt-get install -y --no-install-recommends unzip \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

# 从 GitHub 下载 a-share-mcp 源码
ADD https://github.com/24mlight/a-share-mcp-is-just-i-need/archive/refs/heads/main.zip /tmp/repo.zip
RUN cd /tmp && unzip -q repo.zip \
    && mv a-share-mcp-is-just-i-need-main /app/a-share-mcp \
    && rm repo.zip

# 从 stage 1 复制 Node 和 mcp-proxy
COPY --from=node-runtime /usr/local/bin/node /usr/local/bin/node
COPY --from=node-runtime /app/node_modules /app/node_modules
COPY --from=node-runtime /app/package.json /app/package.json

# 创建 mcp-proxy 包装脚本（用 node 直接运行，避免 npx 的 npm 依赖）
RUN echo '#!/bin/sh\nexec node /app/node_modules/.bin/mcp-proxy "$@"' > /usr/local/bin/mcp-proxy-wrapper \
    && chmod +x /usr/local/bin/mcp-proxy-wrapper

# 安装 a-share-mcp 依赖
RUN pip install --no-cache-dir uv \
    && cd /app/a-share-mcp \
    && uv venv \
    && uv sync

WORKDIR /app/a-share-mcp

ENV NODE_ENV=production
ENV PATH="/usr/local/bin:$PATH"
EXPOSE 8080

# 用 node 直接运行 mcp-proxy（避免 npx 依赖）
CMD ["mcp-proxy-wrapper", "--port", "8080", "--", ".venv/bin/python", "mcp_server.py"]
