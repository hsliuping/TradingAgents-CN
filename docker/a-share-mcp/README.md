# A股 MCP 服务 - Docker 部署

基于 [a-share-mcp](https://github.com/24mlight/a-share-mcp-is-just-i-need) 的 A 股市场数据 MCP 服务，提供股票基础信息、历史 K 线、财务指标、宏观经济等 41+ 工具。

---

## 构建与运行

```powershell
cd d:\TradingAgentsCN2.0\docker
docker-compose -f docker-compose.a-share-mcp.yml up -d --build
```

---

## 连接信息

| 传输方式       | 本地 URL              |
|----------------|------------------------|
| Streamable HTTP | http://localhost:8082/mcp |
| SSE            | http://localhost:8082/sse |

---

## 在 TradingAgents 中配置

1. 打开 **分析流 → MCP 服务器**
2. 添加 MCP 服务器：
   - **服务器 ID**：`a-share-mcp`
   - **名称**：`A股数据`
   - **传输方式**：`Streamable HTTP` 或 `SSE`
   - **URL**：`http://localhost:8082/mcp` 或 `http://localhost:8082/sse`
3. 点击「发现工具」，启用该服务器
4. 在智能体工具配置中勾选需要的 A 股工具

---

## 停止服务

```powershell
docker-compose -f docker-compose.a-share-mcp.yml down
```
