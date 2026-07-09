# MCP 支持设计文档

## 📋 文档信息

| 项目 | 内容 |
|------|------|
| 版本 | v2.0 |
| 状态 | MCP Client 已实现 / MCP Server 设计中 |
| 日期 | 2026-03 |
| 目标 | 双向 MCP 支持 —— 作为 Client 消费外部工具，作为 Server 暴露分析流能力 |

---

## 1. 概述

TradingAgents-CN 的 MCP 支持分为两个方向：

| 方向 | 角色 | 状态 | 说明 |
|------|------|------|------|
| **MCP Client** | 消费者 | ✅ 已实现 | 接入外部 MCP 服务器的工具（如 a-share-mcp、memory 等） |
| **MCP Server** | 提供者 | 🔧 设计中 | 将多智能体分析流暴露为 MCP 工具，供 Claude/Cursor/OpenClaw 调用 |

**核心理念**：MCP Server 暴露的是**分析能力（成品）**，而非原始数据工具（零件）。工具是内部实现细节，分析流才是产品。

```
❌ 不暴露：get_stock_data, get_news, get_financial_data...（零件）
✅ 暴露：analyze_stock, screen_stocks, get_market_overview...（成品）
```

---

## Part A: MCP Client（已实现）

## 2. MCP Client 已实现能力

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

---

## Part B: MCP Server（设计中）

## 7. MCP Server 设计

### 7.1 战略定位

```
Claude Desktop / Cursor / OpenClaw / 任意 MCP Client
                    │
                    ▼
    ┌──────── MCP Server ────────┐
    │                            │
    │  analyze_stock(symbol)     │  ← 暴露的是"分析能力"
    │  screen_stocks(criteria)   │
    │  get_market_overview()     │
    │  chat(message)             │
    │                            │
    └────────────┬───────────────┘
                 │
                 ▼
    ┌──── 内部黑箱（不暴露）────┐
    │                           │
    │  Workflow Engine           │
    │  ├── market_analyst        │
    │  ├── news_analyst          │
    │  ├── fundamental_analyst   │
    │  └── risk_manager          │
    │                           │
    │  Tools (AkShare, Tushare)  │
    │  MongoDB / Redis           │
    │                           │
    └───────────────────────────┘
```

**为什么不暴露原始工具**：
1. **护城河** —— 多 Agent 协作分析的质量、提示词调教、工作流设计是核心竞争力
2. **分发渠道** —— MCP 生态是分发渠道，用户在 Claude 里就能用，无需打开 Web UI
3. **商业模式** —— 按分析次数/深度计费，而非按 API 调用计费
4. **与 v3.0 契合** —— AI 工作流架构师生成的新流程，自动变成新的 MCP 能力

### 7.2 暴露的 MCP 工具

| MCP Tool | 输入 | 输出 | 内部实现 | 耗时 |
|----------|------|------|---------|------|
| `analyze_stock` | symbol, depth?, workflow_id? | 完整分析报告（Markdown） | 触发 UnifiedAnalysisTask → 等待完成 → 返回报告 | 1-5 min |
| `screen_stocks` | criteria（自然语言） | 符合条件的股票列表 + 理由 | 筛选工作流 | 30s-2 min |
| `get_market_overview` | market? (cn/hk/us) | 市场总览报告 | 市场概览流程 | 30s-1 min |
| `chat_with_assistant` | message | 助理回复 | AnalysisAssistant.chat() | 5-30s |
| `get_report` | task_id or symbol | 历史分析报告 | MongoDB 查询 | <1s |
| `list_workflows` | — | 可用工作流列表 | workflow_definitions 查询 | <1s |

### 7.3 技术实现

使用 `fastmcp` 库（Python MCP Server SDK）：

```python
from fastmcp import FastMCP

mcp = FastMCP("TradingAgents-CN", version="1.0.0")

@mcp.tool()
async def analyze_stock(
    symbol: str,
    depth: int = 3,
    workflow_id: str = None
) -> str:
    """
    对指定股票进行多智能体协作分析，返回完整分析报告。

    Args:
        symbol: 股票代码，如 "600519"（贵州茅台）、"000858"（五粮液）
        depth: 分析深度 1-5（1=快速, 3=标准, 5=全面），默认 3
        workflow_id: 指定工作流ID（可选，不指定则使用默认工作流）

    Returns:
        Markdown 格式的完整分析报告，包含：
        - 投资建议（买入/持有/卖出）
        - 置信度评分
        - 各维度分析（市场、基本面、新闻、技术面）
        - 风险评估
        - 关键要点
    """
    # 1. 触发分析任务
    task = await task_service.create_and_execute_task(
        user_id=mcp_service_user_id,
        task_type=AnalysisTaskType.STOCK_ANALYSIS,
        task_params={"symbol": symbol, "research_depth": depth},
        workflow_id=workflow_id
    )

    # 2. 等待完成（带超时）
    result = await wait_for_task_completion(task.task_id, timeout=300)

    # 3. 格式化报告
    return format_report_as_markdown(result)

@mcp.tool()
async def chat_with_assistant(message: str) -> str:
    """
    与 TradingAgents 分析助理自由对话。
    可以问任何 A 股相关问题，助理会调用内部工具获取数据并回答。

    Args:
        message: 你的问题或指令

    Returns:
        助理的回复
    """
    response = await analysis_assistant.chat(
        message=message,
        session_key="mcp:default"
    )
    return response.content
```

### 7.4 传输方式

MCP Server 支持以下传输方式：

| 传输 | 适用场景 | 说明 |
|------|---------|------|
| **SSE** | Claude Desktop、Cursor | HTTP 长连接，适合本地部署 |
| **Streamable HTTP** | 云端部署 | MCP 新版标准，适合 SaaS 场景 |
| **stdio** | 本地开发 | 标准输入输出，用于调试 |

### 7.5 长时间任务处理

分析任务通常需要 1-5 分钟，MCP 协议需要特殊处理：

**方案：轮询模式**

```
MCP Client 调用 analyze_stock("600519")
    ↓
MCP Server 立即返回: "任务已创建，task_id=xxx，预计 3 分钟完成。
                     请稍后调用 get_report(task_id='xxx') 获取结果。"
    ↓
MCP Client（由 LLM 决策）调用 get_report("xxx")
    ↓
MCP Server 返回: 完整报告（如已完成）或 "任务进行中，进度 60%"
```

**方案（备选）：阻塞等待**

对于支持长超时的 MCP Client，`analyze_stock` 可以阻塞等待直到分析完成后返回完整报告。通过参数 `wait: bool = true` 控制行为。

### 7.6 认证与限流

| 维度 | 方案 |
|------|------|
| **认证** | API Key 认证（在 MCP Server 配置中设置） |
| **用户映射** | API Key → system_user_id |
| **限流** | 按用户的分析配额（daily_quota）限制 |
| **计费** | 每次 analyze_stock 调用消耗 1 次配额 |

---

## 8. 实施计划

### Phase 1: MCP Server 基础框架（1-2 周）

- [ ] 安装 `fastmcp` 依赖
- [ ] 创建 `core/mcp/server.py` —— MCP Server 入口
- [ ] 实现 `analyze_stock` 工具（核心链路）
- [ ] 实现 `chat_with_assistant` 工具
- [ ] 实现 `get_report` / `list_workflows` 工具
- [ ] SSE 传输支持
- [ ] 验证 Claude Desktop 可调用

### Phase 2: 完善与优化（1 周）

- [x] 长时间任务的轮询/阻塞双模式
- [x] API Key 认证机制
- [x] 用户配额限制
- [x] `screen_stocks` / `get_market_overview` 工具
- [ ] Streamable HTTP 传输支持

### Phase 3: 与 v3.0 Skill 系统集成

- [ ] AI 工作流架构师生成的新流程自动注册为 MCP Tool
- [ ] 动态工具列表（根据可用工作流自动更新）
