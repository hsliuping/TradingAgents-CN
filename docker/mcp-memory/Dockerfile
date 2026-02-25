# MCP Memory Server - 基于知识图谱的 AI 记忆服务
# 使用 mcp-proxy 将 stdio 传输转为 HTTP/SSE，供 TradingAgents 调用
# 参考: https://github.com/modelcontextprotocol/servers/tree/main/src/memory

FROM node:22-alpine

WORKDIR /app

# 安装依赖
RUN npm init -y && \
    npm install mcp-proxy @modelcontextprotocol/server-memory

# 数据持久化目录
RUN mkdir -p /data

ENV MEMORY_FILE_PATH=/data/memory.jsonl
ENV NODE_ENV=production

# mcp-proxy 将 stdio 转为 HTTP，默认端口 8080
# - /mcp  : Streamable HTTP
# - /sse  : SSE
EXPOSE 8080

# 使用 mcp-proxy 包装 server-memory，暴露 HTTP
CMD ["npx", "mcp-proxy", "--port", "8080", "--", "npx", "-y", "@modelcontextprotocol/server-memory"]
