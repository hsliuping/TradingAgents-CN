# v3.0 实施计划：分析助理 + MCP Server + Gateway

## 📋 文档信息

| 项目 | 内容 |
|------|------|
| 版本 | v1.0 |
| 日期 | 2026-03 |
| 状态 | 规划中 |
| 依赖文档 | [intelligent-assistant.md](./intelligent-assistant.md)、[mcp-support.md](./mcp-support.md) |

---

## 0. 总体路线

```
Phase 1  分析助理操作工具升级          ██████████  3 周
Phase 2  MCP Server（暴露分析流）      ██████      2 周
Phase 3  Gateway（飞书/QQ 接入）       ████████    3 周
                                       ─────────────────→ 时间
```

三个 Phase 串行推进，Phase 1 是 Phase 2/3 的基础——所有外部通道最终都调用分析助理的能力。

---

## Phase 1：分析助理操作工具升级（3 周）

### 1.1 目标

将 `IntelligentAssistantService` 从"数据教练"升级为"全能操作员"，新增 12 个操作工具，使助理能够触发分析、查报告、管定时任务、管自选股。

### 1.2 前置条件

- 现有 `IntelligentAssistantService`（`app/services/intelligent_assistant_service.py`）可正常工作
- `TaskAnalysisService`（`app/services/task_analysis_service.py`）可正常创建和执行任务
- 定时分析 CRUD（`app/routers/scheduled_analysis.py`）已实现
- 自选股分组 CRUD（`app/routers/watchlist_groups.py`）已实现

### 1.3 实施步骤

#### Step 1.3.1：创建操作工具模块（Week 1, Day 1-2）

**新建文件**: `core/tools/implementations/assistant_ops/`

```
core/tools/implementations/assistant_ops/
├── __init__.py
├── analysis_trigger.py      # 分析触发类（3 个工具）
├── report_query.py          # 报告查询类（3 个工具）
├── schedule_manager.py      # 定时任务管理类（3 个工具）
└── watchlist_manager.py     # 自选股管理类（3 个工具）
```

每个工具函数遵循现有 ToolRegistry 规范：
- 使用 `@tool_registry.register()` 装饰器注册
- 返回字符串（LLM 可读的结果描述）
- 内部通过 `get_mongo_db()` 和现有 Service 实现逻辑

#### Step 1.3.2：实现分析触发类工具（Week 1, Day 2-3）

| 工具函数 | 内部实现 | 关键逻辑 |
|---------|---------|---------|
| `trigger_stock_analysis(symbol, depth?, workflow_id?)` | `TaskAnalysisService.create_and_execute_task()` | 异步创建任务，立即返回 task_id，不阻塞等待 |
| `trigger_batch_analysis(symbols[], depth?)` | 循环调用 `create_task()` | 创建批次，返回 batch_id |
| `get_analysis_status(task_id)` | `TaskAnalysisService.get_task()` | 返回状态、进度、预计完成时间 |

**关键设计**:
- `trigger_stock_analysis` 不能阻塞等待分析完成（分析需要 1-5 分钟），必须立即返回 task_id
- 使用 `asyncio.create_task()` 后台执行分析，助理告知用户"任务已创建，稍后可查看"
- 需要获取当前用户的 `user_id`，通过工具执行上下文传递

```python
# 伪代码
async def trigger_stock_analysis(symbol: str, depth: int = 3, workflow_id: str = None) -> str:
    from app.services.task_analysis_service import get_task_analysis_service
    from app.models.analysis import AnalysisTaskType
    
    service = get_task_analysis_service()
    task = await service.create_task(
        user_id=_get_current_user_id(),  # 从上下文获取
        task_type=AnalysisTaskType.STOCK_ANALYSIS,
        task_params={"symbol": symbol, "research_depth": depth},
        workflow_id=workflow_id
    )
    # 后台执行（不阻塞）
    asyncio.create_task(service.execute_task(task.task_id))
    
    return f"✅ 已创建分析任务\n任务ID: {task.task_id}\n股票: {symbol}\n深度: {depth}\n预计 2-5 分钟完成，届时可查看报告。"
```

#### Step 1.3.3：实现报告查询类工具（Week 1, Day 3-4）

| 工具函数 | 内部实现 | 关键逻辑 |
|---------|---------|---------|
| `search_reports(keyword?, symbol?, date_range?)` | `db.unified_analysis_tasks.find()` | 按关键词/股票/日期范围查询，返回摘要列表 |
| `get_report_detail(task_id)` | `db.unified_analysis_tasks.find_one()` | 返回完整报告（Markdown 格式化） |
| `get_latest_report(symbol)` | `db.unified_analysis_tasks.find_one(sort=-created_at)` | 返回最新一次分析报告摘要 |

**关键设计**:
- `search_reports` 返回结果需精简（标题、股票、日期、结论），不能返回完整报告（太长）
- `get_report_detail` 格式化 `task.result` 为 Markdown，提取投资建议、置信度、关键要点
- 日期范围支持自然语言转换：`last_week` → 7天内，`last_month` → 30天内，`today` → 当天

#### Step 1.3.4：实现定时任务管理类工具（Week 2, Day 1-2）

| 工具函数 | 内部实现 | 关键逻辑 |
|---------|---------|---------|
| `list_scheduled_configs()` | `db.scheduled_analysis_configs.find(user_id)` | 返回所有定时配置摘要 |
| `create_scheduled_analysis(name, cron, group_ids, depth?)` | 复用 `scheduled_analysis.py` 中的创建逻辑 | 创建配置 + 注册调度器 |
| `toggle_scheduled_config(config_id, enabled)` | `db.scheduled_analysis_configs.update_one()` + 注册/取消注册调度器 | 启用/禁用配置 |

**关键设计**:
- `create_scheduled_analysis` 需要助理在调用前确认参数（通过系统提示词约束）
- CRON 表达式由 LLM 根据用户自然语言生成（如"每天早上9点" → `0 9 * * 1-5`）
- 注册/取消注册调度器需复用 `_register_scheduled_tasks()` / `_unregister_scheduled_tasks()`

#### Step 1.3.5：实现自选股管理类工具（Week 2, Day 2-3）

| 工具函数 | 内部实现 | 关键逻辑 |
|---------|---------|---------|
| `list_watchlist_groups()` | `db.watchlist_groups.find(user_id)` | 返回分组列表（名称 + 股票数量） |
| `add_stock_to_watchlist(group_name, symbol)` | `db.watchlist_groups.update_one($addToSet)` | 按名称查找分组，添加股票 |
| `remove_stock_from_watchlist(group_name, symbol)` | `db.watchlist_groups.update_one($pull)` | 按名称查找分组，移除股票 |

**关键设计**:
- 用 `group_name`（而非 `group_id`）作为参数，更自然语言友好
- 如果分组不存在，`add_stock_to_watchlist` 自动创建新分组
- 返回操作后的分组当前状态（股票数量）

#### Step 1.3.6：工具注册与上下文传递（Week 2, Day 3-4）

**核心问题**：操作工具需要知道"当前用户是谁"，但现有 ToolRegistry 的工具函数签名中没有 user context。

**解决方案**：使用 Python `contextvars` 传递用户上下文

```python
# core/tools/context.py（新建）
import contextvars

_current_user_id: contextvars.ContextVar[str] = contextvars.ContextVar('current_user_id', default=None)

def set_current_user_id(user_id: str):
    _current_user_id.set(user_id)

def get_current_user_id() -> str:
    return _current_user_id.get()
```

在 `IntelligentAssistantService.chat()` 入口设置：
```python
async def chat(self, user_message, conversation_id=None, user_id=None):
    from core.tools.context import set_current_user_id
    if user_id:
        set_current_user_id(user_id)
    ...
```

#### Step 1.3.7：升级系统提示词（Week 2, Day 4-5）

修改 `_get_system_prompt()` 函数，从"教练模式"切换为"操作员模式"：

**核心变化**:
1. 角色定位：从"投资教练"改为"分析助理（操作员）"
2. 能力描述：新增"触发分析、查报告、管定时任务、管自选股"
3. 操作确认：创建定时任务、删除自选股等操作前主动确认
4. 保留原有教练能力：数据教学、分析框架等作为"附加能力"保留
5. 保留合规原则：不给投资建议

#### Step 1.3.8：集成测试与 Web UI 验证（Week 3）

| 测试场景 | 验证内容 |
|---------|---------|
| "帮我分析贵州茅台" | 调用 `trigger_stock_analysis`，返回 task_id |
| "任务进度怎么样了" | 调用 `get_analysis_status`，上下文关联上一个 task_id |
| "上周分析过哪些股票" | 调用 `search_reports(date_range="last_week")` |
| "设置每天早上9点分析科技股" | 调用 `create_scheduled_analysis` |
| "把比亚迪加到重点关注分组" | 调用 `add_stock_to_watchlist` |
| "查看我的自选股分组" | 调用 `list_watchlist_groups` |
| "贵州茅台的毛利率是多少" | 仍使用原有数据工具（不受影响） |

### 1.4 交付物

| 文件 | 说明 |
|------|------|
| `core/tools/implementations/assistant_ops/*.py` | 12 个操作工具实现 |
| `core/tools/context.py` | 用户上下文传递模块 |
| `app/services/intelligent_assistant_service.py`（修改） | 系统提示词升级 + user_id 传递 |
| `app/routers/intelligent_assistant.py`（修改） | 传递 user_id 到 chat |

---

## Phase 2：MCP Server — 暴露分析流（2 周）

### 2.1 目标

用 `fastmcp` 将多智能体分析流暴露为 MCP Tool，让任何 MCP Client（Claude Desktop、Cursor、OpenClaw）一句话获得完整分析报告。**暴露的是成品（分析能力），不是零件（内部工具）。**

### 2.2 前置条件

- Phase 1 完成（`trigger_stock_analysis`、`get_report_detail` 等操作工具可用）
- `fastmcp` 依赖已安装

### 2.3 实施步骤

#### Step 2.3.1：MCP Server 基础框架（Week 1, Day 1-2）

**新建文件**: `core/mcp/server.py`

```python
from fastmcp import FastMCP

mcp = FastMCP(
    "TradingAgents-CN",
    version="1.0.0",
    description="多智能体股票分析系统 — 暴露 A 股分析能力"
)
```

**启动方式**:
- 独立进程：`python -m core.mcp.server`（SSE 传输，供 Claude Desktop / Cursor 连接）
- 集成到 FastAPI：挂载到 `/mcp` 路径（Streamable HTTP，供云端 Client 连接）

#### Step 2.3.2：实现核心 MCP 工具（Week 1, Day 2-4）

| MCP Tool | 内部实现 | 耗时 | 说明 |
|----------|---------|------|------|
| `analyze_stock(symbol, depth?, wait?)` | Phase 1 的 `trigger_stock_analysis` + `get_report_detail` | 1-5 min | `wait=true` 阻塞等待返回报告；`wait=false` 返回 task_id |
| `get_report(task_id_or_symbol)` | Phase 1 的 `get_report_detail` / `get_latest_report` | <1s | 查询历史报告 |
| `chat_with_assistant(message)` | `IntelligentAssistantService.chat()` | 5-30s | 自由对话（含数据查询能力） |
| `list_workflows()` | `db.workflow_definitions.find()` | <1s | 返回可用分析流程列表 |

**长时间任务处理**（`analyze_stock`）：

```
默认行为（wait=false）:
  MCP Client 调用 analyze_stock("600519")
  → 立即返回 "任务已创建, task_id=xxx, 预计3分钟"
  → LLM 决策后调用 get_report("xxx")
  → 返回完整报告 或 "进行中, 进度60%"

阻塞行为（wait=true）:
  MCP Client 调用 analyze_stock("600519", wait=true)
  → 阻塞等待（最长 300s），完成后直接返回完整报告
```

#### Step 2.3.3：认证与用户映射（Week 1, Day 4-5）

| 组件 | 说明 |
|------|------|
| API Key 认证 | 在 `system_configs` 中配置 MCP API Key |
| 用户映射 | API Key → `system_user_id`，操作工具自动获取正确的 user context |
| 限流 | 按用户每日分析配额限制 `analyze_stock` 调用次数 |

```python
# core/mcp/auth.py（新建）
async def authenticate_mcp_request(api_key: str) -> str:
    """验证 API Key，返回 user_id"""
    mapping = await db.system_configs.find_one({"mcp_api_keys": api_key})
    if not mapping:
        raise AuthenticationError("Invalid API Key")
    return mapping["mapped_user_id"]
```

#### Step 2.3.4：传输与部署配置（Week 2, Day 1-2）

| 传输方式 | 适用场景 | 配置 |
|----------|---------|------|
| **SSE** | Claude Desktop / Cursor（本地部署） | `mcp.run(transport="sse", port=8001)` |
| **Streamable HTTP** | 云端 / SaaS 场景 | 挂载到 FastAPI `/mcp` 路由 |

**Claude Desktop 配置示例**（`claude_desktop_config.json`）:
```json
{
  "mcpServers": {
    "tradingagents-cn": {
      "url": "http://localhost:8001/sse",
      "api_key": "your-api-key"
    }
  }
}
```

#### Step 2.3.5：端到端测试（Week 2, Day 3-5）

| 测试场景 | 验证内容 |
|---------|---------|
| Claude Desktop 调用 `analyze_stock("600519")` | 任务创建 → 轮询 → 拿到报告 |
| Cursor 中对话"分析一下比亚迪" | `chat_with_assistant` → 自动调用 `analyze_stock` |
| 调用 `list_workflows` | 返回可用工作流列表 |
| 错误 API Key | 返回认证错误 |
| 超出配额 | 返回限流提示 |

### 2.4 交付物

| 文件 | 说明 |
|------|------|
| `core/mcp/__init__.py` | MCP 模块 |
| `core/mcp/server.py` | MCP Server 入口 + 工具定义 |
| `core/mcp/auth.py` | API Key 认证与用户映射 |
| `core/mcp/config.py` | MCP Server 配置（端口、传输方式等） |
| 配置文档 | Claude Desktop / Cursor 接入说明 |

---

## Phase 3：Gateway — IM 平台双向接入（3 周）

### 3.1 目标

实现 Gateway 适配器框架，让用户在飞书/QQ/钉钉等 IM 平台上直接与分析助理对话、触发分析、接收报告。

### 3.2 前置条件

- Phase 1 完成（分析助理操作工具可用）
- Phase 2 完成（MCP Server 验证了分析流端到端可用）

### 3.3 实施步骤

#### Step 3.3.1：Gateway 基础框架（Week 1, Day 1-3）

**新建目录**: `core/gateway/`

```
core/gateway/
├── __init__.py
├── router.py               # GatewayRouter — 路由分发
├── models.py               # GatewayMessage / GatewayResponse 统一消息模型
├── session.py              # 多通道 Session 管理
├── user_mapping.py         # IM 用户 → 系统用户映射
└── adapters/
    ├── __init__.py
    ├── base.py             # BaseGatewayAdapter 抽象基类
    ├── feishu.py           # 飞书适配器
    ├── qq.py               # QQ Bot 适配器
    └── dingtalk.py         # 钉钉适配器
```

**核心模型** (`core/gateway/models.py`):

```python
class GatewayMessage(BaseModel):
    channel_type: str           # "feishu" | "qq" | "dingtalk"
    channel_id: str             # 平台侧会话ID
    user_identity: str          # 平台侧用户标识
    message_type: str           # "text" | "image" | "file"
    content: str
    timestamp: datetime
    metadata: Dict[str, Any]

class GatewayResponse(BaseModel):
    channel_type: str
    channel_id: str
    response_type: str          # "text" | "card" | "markdown"
    content: str
    card_template: Optional[Dict]
    attachments: List[Dict]
```

**API 路由** (`app/routers/gateway.py` 新建):

```python
@router.post("/gateway/{platform}")
async def gateway_webhook(platform: str, request: Request):
    adapter = get_adapter(platform)
    if not await adapter.verify_signature(raw_data):
        raise HTTPException(403, "Invalid signature")
    message = await adapter.parse_message(raw_data)
    # 映射用户 → 调用助理 → 格式化回复 → 发回平台
```

#### Step 3.3.2：多通道 Session 管理（Week 1, Day 3-5）

**Session Key 格式**: `{user_id}:{channel_type}:{channel_id}`

```python
# core/gateway/session.py
class SessionManager:
    async def get_or_create_session(self, user_id, channel_type, channel_id):
        key = f"{user_id}:{channel_type}:{channel_id}"
        # 从 MongoDB 加载会话或创建新会话
        # 每个 Session 独立维护：对话历史、上下文状态、输出格式偏好
```

- 同一用户从 Web 和飞书的会话完全独立
- Session 存储在 MongoDB `gateway_sessions` 集合
- 对话历史自动裁剪（保留最近 N 轮）
- TTL 索引自动清理过期 Session

#### Step 3.3.3：飞书 Bot 适配器（Week 2）

**飞书接入流程**:

1. 创建飞书自建应用（App ID + App Secret）
2. 配置 Event Subscription（消息事件回调到 `/api/gateway/feishu`）
3. 实现 `FeishuAdapter`:
   - `verify_signature()` — 验证飞书 Challenge + 签名
   - `parse_message()` — 提取 `open_id`、`chat_id`、消息内容
   - `send_response()` — 调用飞书 OpenAPI 发送消息（支持文本 + 卡片）

**卡片消息格式化**:

- 分析报告 → 飞书交互卡片（可折叠摘要 + 查看详情按钮）
- 任务状态 → 进度条卡片
- 简单回复 → 纯文本

#### Step 3.3.4：用户身份绑定（Week 3, Day 1-2）

**绑定流程**:

1. 用户在飞书中发送 `/bind` 命令
2. Gateway 返回一次性验证码
3. 用户在 Web UI 输入验证码，完成绑定
4. 之后飞书 `open_id` 自动映射到系统 `user_id`

**存储** (MongoDB `user_identity_mappings`):

```python
{
    "user_id": "system_user_001",
    "platform": "feishu",
    "platform_identity": "ou_xxxxxxxxx",
    "bound_at": datetime
}
```

#### Step 3.3.5：端到端测试（Week 3, Day 3-5）

| 测试场景 | 预期行为 |
|---------|---------|
| 飞书私聊"分析贵州茅台" | 飞书收到"任务已创建"→ 完成后推送报告卡片 |
| 飞书群聊 @Bot "上周分析报告" | Bot 回复报告摘要列表 |
| 未绑定用户发消息 | 回复"请先绑定账号"+ 绑定引导 |
| 多通道并发 | Web 和飞书的会话独立，互不影响 |

### 3.4 交付物

| 文件 | 说明 |
|------|------|
| `core/gateway/*.py` | Gateway 基础框架（路由、Session、用户映射） |
| `core/gateway/adapters/feishu.py` | 飞书 Bot 适配器 |
| `app/routers/gateway.py` | Gateway Webhook 路由 |
| 配置文档 | 飞书自建应用配置说明 |

---

## 📊 总体风险与依赖

| 风险 | 影响 | 缓解措施 |
|------|------|---------|
| 分析任务超时（>5min） | MCP Client / Gateway 用户体验差 | 轮询模式 + 进度通知 |
| 飞书 API 限流 | 高并发场景消息发送失败 | 消息队列 + 重试机制 |
| LLM 生成的 CRON 表达式错误 | 定时任务配置失败 | 系统提示词约束 + 验证逻辑 |
| 多通道 Session 数据膨胀 | MongoDB 存储压力 | TTL 索引自动清理过期 Session |

---

## 📝 版本历史

| 版本 | 日期 | 变更 |
|------|------|------|
| v1.0 | 2026-03 | 初始版本，三阶段实施计划 |

