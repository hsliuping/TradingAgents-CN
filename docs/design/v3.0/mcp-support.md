# MCP 支持设计文档

## 📋 文档信息

| 项目 | 内容 |
|------|------|
| 版本 | v1.0 |
| 状态 | 已实现 |
| 日期 | 2026-02 |
| 目标 | 支持用户配置外部 MCP 服务器，工具可被 Agent 和 Skill 直接调用 |

---

## 1. 概述

MCP (Model Context Protocol) 支持允许用户配置自己的 MCP 服务器，系统将自动发现工具并注册到 ToolRegistry，供 Agent 和 Skill 调用。

---

## 2. 已实现能力

| 模块 | 实现位置 | 说明 |
|------|----------|------|
| **API 路由** | `app/routers/mcp.py` | 端点前缀 `/api/mcp`，CRUD、测试、发现、启用/禁用 |
| **业务逻辑** | `app/services/mcp_service.py` | 集合 `mcp_server_configs`，工具注册/注销 |
| **客户端管理** | `core/tools/mcp/client_manager.py` | 支持 SSE、streamable_http、stdio 传输 |
| **前端管理页** | `frontend/src/views/Workflow/McpServers.vue` | 配置、测试连接、发现工具、启用/禁用 |
| **启动恢复** | `app/main.py` | 恢复已启用的 MCP 服务器工具到 ToolRegistry |

---

## 3. 连接配置

支持三种传输类型：

- **sse**：Server-Sent Events
- **streamable_http**：Streamable HTTP（新版 MCP 标准）
- **stdio**：标准输入输出

---

## 4. 工具注册

- 工具 ID 格式：`mcp_{server_id}_{tool_name}`
- 工具分类：`category="mcp"`
- 工具可被 Agent 和 Skill 直接调用

---

## 5. 侧边栏入口

分析流 → MCP 服务器

---

## 6. 在流程中使用 MCP 工具

### 前置条件

1. **MCP 服务器已配置**：在「分析流 → MCP 服务器」中添加并测试连接
2. **已发现工具**：点击「发现工具」，确认工具列表正常
3. **已启用**：打开该 MCP 服务器的「启用」开关（工具才会注册到系统）

### 方式一：在工作流中使用

1. 打开 **分析流 → 智能体**，选择要使用 MCP 工具的 Agent（如 `market_analyst`）
2. 在 **工具配置** 卡片中点击「编辑」
3. 在「可用工具」下拉框中，勾选需要的 MCP 工具（如 `mcp_memory_create_entities`、`mcp_memory_search_nodes` 等）
4. 保存
5. 打开 **工作流编辑器**，该 Agent 节点会自动具备这些工具；LLM 会根据任务自动选择调用

**工作流节点级覆盖**：在编辑器中点击某个 Agent 节点，右侧「工具配置」可勾选/取消该节点在此流程中使用的工具，可覆盖 Agent 默认配置。

### 方式二：在智能助手中使用

智能助手会加载 **所有已启用** 的 MCP 工具（来自 `registry.list_all()`），无需额外配置。只要 MCP 服务器已启用，智能助手对话中 LLM 即可根据用户问题选择调用。

### 工具 ID 格式

- 格式：`mcp_{server_id}_{tool_name}`
- 示例：`mcp_memory_create_entities`、`mcp_memory_search_nodes`（`server_id` 为 `memory` 时）
