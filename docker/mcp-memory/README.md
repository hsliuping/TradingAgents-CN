# MCP Memory 服务 - 独立部署与测试计划

基于 [Model Context Protocol Memory Server](https://github.com/modelcontextprotocol/servers/tree/main/src/memory) 的 AI 记忆服务。

---

## 阶段一：独立部署

### 1. 构建并启动

```powershell
cd d:\TradingAgentsCN2.0\docker
docker-compose -f docker-compose.mcp-memory.yml up -d --build
```

### 2. 验证服务

```powershell
# 检查容器状态
docker ps | findstr mcp-memory

# 测试健康（若有 /ping）
curl http://localhost:8081/ping

# 或使用 MCP Inspector 连接
npx -y @modelcontextprotocol/inspector
# 连接 URL: http://localhost:8081/mcp (Streamable HTTP) 或 http://localhost:8081/sse (SSE)
```

---

## 阶段二：在 TradingAgents 中测试

### 1. 配置 MCP 服务器

1. 启动 TradingAgents 主应用（本地 `python -m app` 或 已有 Docker）
2. 打开 **分析流 → MCP 服务器**
3. 添加 MCP 服务器：
   - **服务器 ID**：`memory`
   - **名称**：`Memory`
   - **传输方式**：`Streamable HTTP` 或 `SSE`
   - **URL**：`http://localhost:8081/mcp`（Streamable HTTP）或 `http://localhost:8081/sse`（SSE）

### 2. 发现工具并启用

- 点击 **发现工具**
- 确认出现 create_entities、create_relations、add_observations、search_nodes、read_graph 等

### 3. 功能验证

- 在智能助手或分析流中触发使用 Memory 工具
- 确认能创建实体、添加观察、搜索节点

---

## 阶段三：验证通过后合并到主 compose

当独立部署测试无问题后，将 mcp-memory 服务加入 `docker-compose.compiled.yml`，并更新 nginx 或网络配置（如需要）。

---

## 连接信息

| 传输方式 | 本地 URL |
|----------|----------|
| Streamable HTTP | http://localhost:8081/mcp |
| SSE | http://localhost:8081/sse |

## 停止服务

```powershell
docker-compose -f docker-compose.mcp-memory.yml down
```
