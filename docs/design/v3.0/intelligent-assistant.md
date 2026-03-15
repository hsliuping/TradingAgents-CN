# 智能助手（分析助理）

## 📋 文档信息

| 项目 | 内容 |
| ------ | ------ |
| 版本 | v3.0 |
| 状态 | v1.0 ✅ / v2.0 ✅ / v3.0 核心能力已实现，持续优化中 |
| 日期 | 2026-03 |
| 目标 | 从"数据教练"→"全能操作员"→"全生命周期投资助手"，覆盖选股→持仓→复盘→纪律全流程 |

---

## 1. 概述

智能助手（分析助理）是 TradingAgents-CN 的**核心协调角色**。它不仅是对话式分析入口，更是连接外部通道（Gateway / MCP Server）与内部系统（工作流引擎、定时调度、报告库）的中枢。

### 1.1 角色演进

| 阶段 | 角色定位 | 能力范围 |
| ------ | --------- | --------- |
| **v1.0（已实现）** | 数据教练 | 调用数据工具回答问题、规划分析 |
| **v2.0（已实现）** | 全能操作员 | 触发分析流、查报告、管定时任务、管自选股、Gateway + MCP 多通道接入 |
| **v3.0（核心能力已实现）** | 全生命周期投资助手 | 在 v2.0 基础上新增：持仓分析、交易复盘、投资计划、用户画像、意图驱动路由、IM 格式适配、主题会话摘要 |

### 1.2 三层架构定位

```text
┌─────────────────────────────────────────────────────────────┐
│  Layer 1: 接入层                                             │
│  ┌──────────┐  ┌──────────┐  ┌───────────┐  ┌───────────┐  │
│  │ Web UI   │  │ 飞书 Bot │  │  QQ Bot   │  │ MCP Server│  │
│  │ (已有)   │  │ (Gateway) │  │ (Gateway) │  │ (新增)    │  │
│  └────┬─────┘  └────┬─────┘  └─────┬─────┘  └─────┬─────┘  │
│       └──────────────┴──────────────┴──────────────┘        │
│                          │                                   │
│                          ▼                                   │
├─────────────────────────────────────────────────────────────┤
│  Layer 2: 分析助理（本文档核心）                               │
│                                                              │
│  ┌─────────────────────────────────────────────────────┐    │
│  │  AnalysisAssistant                                   │    │
│  │  ├── 意图驱动路由（LLM Function Calling）            │    │
│  │  ├── 操作工具（分析、报告、定时、自选股、持仓、      │    │
│  │  │            复盘、投资计划）                        │    │
│  │  ├── 数据工具（行情、财务、新闻、技术指标）          │    │
│  │  ├── 会话管理（滑动窗口 + 用户画像）                │    │
│  │  ├── 先确认再执行（模糊/高代价→确认，明确/轻量→直接）│    │
│  │  └── 格式适配（Markdown / IM竖排 / MCP Response）    │    │
│  └─────────────────────────────────────────────────────┘    │
│                          │                                   │
│                          ▼                                   │
├─────────────────────────────────────────────────────────────┤
│  Layer 3: 内部系统（黑箱，不对外暴露）                        │
│  ┌───────────┐  ┌───────────┐  ┌──────────┐  ┌──────────┐  │
│  │ Workflow   │  │ Scheduler │  │ Report   │  │ Watchlist│  │
│  │ Engine     │  │ Service   │  │ Store    │  │ Groups   │  │
│  └───────────┘  └───────────┘  └──────────┘  └──────────┘  │
│  ┌───────────┐  ┌───────────┐  ┌──────────┐  ┌──────────┐  │
│  │ Portfolio  │  │ Trade     │  │ Trading  │  │ User     │  │
│  │ Service    │  │ Review    │  │ System   │  │ Profile  │  │
│  └───────────┘  └───────────┘  └──────────┘  └──────────┘  │
└─────────────────────────────────────────────────────────────┘
```

---

## 2. v1.0 已实现能力

### 2.1 后端

| 模块 | 实现位置 | 说明 |
| ------ | ---------- | ------ |
| **API 路由** | `app/routers/intelligent_assistant.py` | 统一前缀 `/api/assistant` |
| **智能助手服务** | `app/services/intelligent_assistant_service.py` | ReAct 模式、LLM 配置、RAG 知识检索 |
| **规划分析服务** | `app/services/planned_analysis_service.py` | 种子流程匹配 → LLM 规划 → ReAct 回退 |
| **请求/响应模型** | `app/schemas/intelligent_assistant.py` | ChatRequest、ChatResponse、PlannedAnalysisResponse、AssistantThread* |

### 2.2 前端

| 模块 | 实现位置 | 说明 |
| ------ | ---------- | ------ |
| **助手页面** | `frontend/src/views/Assistant/index.vue` | 对话界面、模式切换（快速/深度）、主题列表、摘要侧栏 |
| **API** | `frontend/src/api/assistant.ts` | chat、planned-analysis、threads、summarize、conversation |
| **侧边栏** | `SidebarMenu.vue` | 智能助手入口 |

### 2.3 API 端点（当前）

| 方法 | 路径 | 说明 |
| ------ | ------ | ------ |
| GET | /api/assistant/threads | 获取当前用户的主题会话列表 |
| POST | /api/assistant/threads | 创建主题会话 |
| GET | /api/assistant/threads/{thread_id}/messages | 获取指定主题消息 |
| DELETE | /api/assistant/threads/{thread_id}/messages | 清空指定主题消息 |
| POST | /api/assistant/threads/{thread_id}/summarize | 手动触发主题摘要更新 |
| POST | /api/assistant/chat | 智能助手对话（ReAct 模式） |
| POST | /api/assistant/planned-analysis | 规划分析（Plan-then-Execute） |
| GET | /api/assistant/conversation | 获取当前主题会话历史（兼容接口，支持 `conversation_id`） |
| DELETE | /api/assistant/conversation | 清空当前主题会话（兼容接口，支持 `conversation_id`） |

### 2.4 规划分析三级保障

| 级别 | 说明 |
| ------ | ------ |
| 1. 种子流程匹配 | 匹配预设种子流程（如单股分析、板块分析），执行固定工作流 |
| 2. LLM 自主规划 | 无匹配时，LLM 规划多步骤执行计划，并行执行 |
| 3. ReAct 回退 | 规划失败时，回退到 ReAct 模式逐步调用工具 |

### 2.5 v1.0 能力特性

- **RAG 知识检索**：从向量数据库获取金融知识片段注入系统提示词
- **工具自主选择**：根据 when_to_use 描述，LLM 自主选择最合适的工具
- **会话持久化**：对话历史持久化，支持下次进入查看
- **教练风格**：教方法、讲框架、用数据说话，不直接给投资建议

---

## 3. v2.0→v3.0 分析助理升级

### 3.1 核心变化

| 维度 | v1.0 | v2.0（已实现） | v3.0（核心能力已实现） |
| ------ | ------ | ------ | ------ |
| **角色** | 数据教练 | 全能操作员 | 全生命周期投资助手 |
| **工具范围** | 数据查询 | +操作工具（分析、报告、定时、自选股） | +持仓分析、交易复盘、投资计划 |
| **接入通道** | 仅 Web UI | +Gateway + MCP Server | +QQ Bot WebSocket 模式 |
| **会话管理** | 无状态 | 按用户×通道隔离 | +主题会话 + 滑动窗口记忆 + 结构化用户画像 |
| **输出格式** | 纯 Markdown | +卡片消息+MCP Response | +IM 竖排格式适配 |
| **行为模式** | 问答 | 操作员模式 | +意图驱动路由 + 先确认再执行 + 主题摘要承接 |

### 3.2 操作工具定义（~20 个）

分析助理通过 LLM Function Calling 自动选择并调用以下工具：

#### 📊 分析触发类

| 工具名 | 功能 | 内部调用 | 参数 |
| -------- | ------ | --------- | ------ |
| `trigger_stock_analysis` | 触发单只股票分析 | `TaskAnalysisService.create_and_execute_task()` | symbol, depth?, workflow_id? |
| `trigger_batch_analysis` | 触发批量股票分析 | `TaskAnalysisService.create_and_execute_task()` × N | symbols[], depth? |
| `get_analysis_status` | 查询分析任务状态 | `TaskAnalysisService.get_task()` | task_id |

**示例对话**：

```text
用户: "帮我分析一下贵州茅台"
助理: [调用 trigger_stock_analysis(symbol="600519")]
      "已为您创建贵州茅台(600519)的分析任务，任务ID: xxx，预计 3 分钟完成。"

用户: "分析进度怎么样了？"
助理: [调用 get_analysis_status(task_id="xxx")]
      "任务正在运行中，当前进度 60%，市场分析师和基本面分析师已完成，新闻分析师正在工作。"
```

#### 📝 报告查询类

| 工具名 | 功能 | 内部调用 | 参数 |
| -------- | ------ | --------- | ------ |
| `search_reports` | 搜索历史分析报告 | `db.analysis_reports.find()` | keyword?, symbol?, date_range? |
| `get_report_detail` | 获取报告详情 | `db.analysis_reports.find_one()` | report_id or task_id |
| `get_latest_report` | 获取某只股票最新报告 | `db.unified_analysis_tasks.find_one(sort)` | symbol |

**示例对话**：

```text
用户: "上周分析过哪些股票？"
助理: [调用 search_reports(date_range="last_week")]
      "上周共分析了 8 只股票：贵州茅台(600519)、宁德时代(300750)..."

用户: "茅台那次分析结论是什么？"
助理: [调用 get_latest_report(symbol="600519")]
      "最近一次贵州茅台分析（2026-03-02）：
       📊 投资建议：持有
       📈 置信度：78%
       🔑 要点：..."
```

#### ⏰ 定时任务管理类

| 工具名 | 功能 | 内部调用 | 参数 |
| -------- | ------ | --------- | ------ |
| `list_scheduled_configs` | 查看定时分析配置 | `db.scheduled_analysis_configs.find()` | — |
| `create_scheduled_analysis` | 创建定时分析 | 调用 ScheduledAnalysis API | name, cron, group_ids, depth? |
| `toggle_scheduled_config` | 启用/禁用定时配置 | `db.scheduled_analysis_configs.update_one()` | config_id, enabled |

**示例对话**：

```text
用户: "帮我设置每天早上9点分析科技股分组"
助理: [调用 create_scheduled_analysis(name="每日科技股分析", cron="0 9 * * 1-5", group_ids=["group_tech"])]
      "已创建定时分析配置 '每日科技股分析'，将在每个交易日 9:00 自动分析科技股分组中的所有股票。"
```

#### 📁 自选股管理类

| 工具名 | 功能 | 内部调用 | 参数 |
| -------- | ------ | --------- | ------ |
| `list_watchlist_groups` | 查看自选股分组 | `db.watchlist_groups.find()` | — |
| `add_stock_to_watchlist` | 添加股票到分组 | `db.watchlist_groups.update_one($addToSet)` | group_name, symbol |
| `remove_stock_from_watchlist` | 从分组移除股票 | `db.watchlist_groups.update_one($pull)` | group_name, symbol |

**示例对话**：

```text
用户: "把比亚迪加到科技股分组里"
助理: [调用 add_stock_to_watchlist(group_name="科技股", symbol="002594")]
      "已将比亚迪(002594)添加到「科技股」分组。该分组现有 12 只股票。"
```

#### 💼 持仓分析类（v3.0 新增）

| 工具名 | 功能 | 内部调用 | 参数 |
| -------- | ------ | --------- | ------ |
| `list_positions` | 查看持仓列表 | `PortfolioService.get_positions()` | account_type（all/real/paper） |
| `get_position_analysis` | 获取持仓 AI 分析报告 | `PortfolioService.get_position_analysis()` | symbol |

**示例对话**：

```text
用户: "我现在持仓了哪些股票？"
助理: [调用 list_positions(account_type="all")]
      "您当前持仓 5 只股票：
      实盘：茅台 200股 +12.5%、宁德时代 100股 -3.2%
      模拟：比亚迪 300股 +8.1%..."
```

#### 📋 交易复盘类（v3.0 新增）

| 工具名 | 功能 | 内部调用 | 参数 |
| -------- | ------ | --------- | ------ |
| `list_trade_reviews` | 查看复盘历史 | `TradeReviewService.get_review_history()` | symbol?, source? |
| `get_trade_review_detail` | 获取完整复盘报告 | `TradeReviewService.get_review()` | review_id |

**示例对话**：

```text
用户: "我最近有做过什么复盘吗？"
助理: [调用 list_trade_reviews()]
      "最近 3 次复盘：
      1. 茅台 2026-03-01 · 综合评分 75 · 操作评价：择时偏早
      2. 比亚迪 2026-02-28 · 综合评分 82 · 操作评价：止盈得当..."
```

#### 📖 投资计划类（v3.0 新增）

| 工具名 | 功能 | 内部调用 | 参数 |
| -------- | ------ | --------- | ------ |
| `list_trading_plans` | 查看投资计划列表 | `TradingSystemService.list_systems()` | — |
| `get_active_trading_plan` | 获取当前激活计划规则 | `TradingSystemService.get_active_system()` | — |

**示例对话**：

```text
用户: "我现在用的是什么交易策略？"
助理: [调用 get_active_trading_plan()]
      "当前激活计划：价值投资策略 v2
      选股规则: PE<25, ROE>15%, 连续3年利润增长
      仓位规则: 单只不超过20%, 总仓位不超过80%
      止损规则: 跌破成本价10%止损..."
```

### 3.3 意图驱动路由（v3.0 核心机制）

#### 先确认再执行原则

```text
用户消息
    │
    ▼
┌──────────────────────────────────────────────┐
│  LLM 自主判断：任务明确度 × 操作代价          │
│                                              │
│  明确 + 轻量 ──→ 直接执行                     │
│    · 数据查询、查看持仓、查看报告              │
│    · 查看复盘历史、查看投资计划                │
│                                              │
│  模糊 或 有副作用 ──→ 先确认再执行             │
│    · 创建定时分析：先查已有 → 确认参数          │
│    · 触发分析：模糊则询问，明确则执行           │
│    · 删除操作：告知将做什么 → 用户确认          │
│    · 复杂多步：先说方案 → 用户确认              │
└──────┬───────────────────────────────────────┘
       │
       ├── function_call → 执行操作工具 → 返回结果
       │
       └── text_response → 直接回复（闲聊/解释/建议/确认请求）
```

### 3.4 会话管理（多通道隔离）

```python
# Session Key 格式
session_key = f"{user_id}:{channel_type}:{channel_id}"

# 示例
"user_001:web:default"           # Web UI
"user_001:feishu:chat_abc123"    # 飞书私聊
"user_001:feishu:group_xyz789"   # 飞书群聊
"user_001:mcp:claude_desktop"    # Claude Desktop via MCP
"user_001:qq:friend_12345"       # QQ 私聊
```

每个 Session 独立维护：

- 对话历史（conversation_history）
- 上下文状态（当前关注的股票、上一次分析的任务ID等）
- 通道特性（输出格式偏好：Markdown / 卡片消息）

当前 Web 端在 Session 之上已引入“主题会话”模型：

- `conversation_id` 实际对应 `thread_id`
- 每个主题维护 `title`、`message_count`、`last_user_message`、`current_summary`
- 对话保存后会自动刷新主题摘要，也支持用户手动触发总结

### 3.5 系统提示词升级

```text
你是 TradingAgents-CN 的分析助理，一个专业的 A 股多智能体分析系统的操作员。

你的能力：
1. 触发股票分析 —— 调用多智能体协作，生成完整分析报告
2. 查看分析报告 —— 搜索和展示历史分析结果
3. 管理定时分析 —— 创建、查看、启用/禁用自动分析任务
4. 管理自选股 —— 查看、添加、移除自选股分组中的股票
5. 回答股票相关问题 —— 查询实时行情、财务数据、新闻等
6. 提供分析框架 —— 教方法、讲框架、用数据说话

你的原则：
- 不直接给出"买入"或"卖出"建议，提供分析框架和数据支持
- 主动确认用户意图，避免误操作（如创建定时任务前确认参数）
- 用简洁清晰的语言回复，重要信息用 emoji 标注
- 当分析任务正在运行时，主动告知预计完成时间
```

---

## 4. Gateway 集成设计

### 4.1 概述

Gateway 是接入层的适配器，负责将各 IM 平台的消息转换为统一格式，交给分析助理处理。

### 4.2 架构

```text
飞书 Event Callback ──→ ┐
QQ Bot WebSocket    ──→ ├─→ GatewayRouter ──→ AnalysisAssistant ──→ 格式化 ──→ 回复
钉钉 Webhook 回调   ──→ ┤
企业微信 Callback   ──→ ┘
```

### 4.3 统一消息接口

```python
class GatewayMessage(BaseModel):
    """Gateway 统一消息格式"""
    channel_type: str           # "feishu" | "qq" | "dingtalk" | "wechat_work"
    channel_id: str             # 平台侧的会话ID
    user_identity: str          # 平台侧的用户标识
    message_type: str           # "text" | "image" | "file"
    content: str                # 消息内容
    timestamp: datetime
    metadata: Dict[str, Any]    # 平台特有信息（如飞书的 open_id、tenant_key 等）

class GatewayResponse(BaseModel):
    """Gateway 统一回复格式"""
    channel_type: str
    channel_id: str
    response_type: str          # "text" | "card" | "markdown"
    content: str                # 文本内容
    card_template: Optional[Dict]  # 卡片消息模板（飞书/钉钉）
    attachments: List[Dict]     # 附件（图表、报告文件等）
```

### 4.4 用户身份映射

```text
平台用户标识 ──→ user_identity_mappings 集合 ──→ 系统 user_id

db.user_identity_mappings:
{
    "platform": "feishu",
    "platform_user_id": "ou_xxxx",
    "system_user_id": ObjectId("..."),
    "bound_at": ISODate,
    "is_active": true
}
```

首次使用时通过验证码或OAuth绑定，之后自动映射。

### 4.5 Gateway 适配器接口

```python
class BaseGatewayAdapter(ABC):
    """Gateway 适配器基类"""

    @abstractmethod
    async def parse_message(self, raw_request: dict) -> GatewayMessage:
        """解析平台原始请求为统一消息"""

    @abstractmethod
    async def send_response(self, response: GatewayResponse) -> bool:
        """将统一回复发送到平台"""

    @abstractmethod
    async def verify_signature(self, raw_request: dict) -> bool:
        """验证平台回调签名"""
```

每个 IM 平台实现一个适配器：`FeishuAdapter`、`QQBotAdapter`、`DingtalkAdapter` 等。

### 4.6 完整消息处理流程

```text
1. IM 平台推送 Webhook 回调到 /api/gateway/{platform}
2. GatewayRouter 选择对应的 Adapter 解析消息
3. 通过 user_identity_mappings 映射到系统用户
4. 构建 session_key = f"{user_id}:{channel_type}:{channel_id}"
5. 调用 AnalysisAssistant.chat(message, session_key)
6. 助理处理消息（可能调用操作工具、数据工具）
7. 格式化回复（根据 channel_type 选择 Markdown / 卡片消息）
8. 通过 Adapter.send_response() 回复到平台
```

---

## 5. MCP Server 集成

分析助理同时作为 MCP Server 的后端，详见 [MCP 支持设计文档](./mcp-support.md) 第 7 章。

MCP Server 暴露的是"分析流能力"而非原始工具：

| MCP Tool | 对应助理操作 |
| ---------- | ------------- |
| `analyze_stock` | `trigger_stock_analysis` + 等待完成 + 返回报告 |
| `screen_stocks` | 调用筛选工作流 + 返回结果 |
| `get_market_overview` | 调用市场概览流程 |
| `chat_with_assistant` | 直接调用 `AnalysisAssistant.chat()` |
| `get_report` | `get_report_detail` |
| `list_workflows` | 查询可用工作流定义 |

---

## 6. 实施计划

### Phase 1: 操作工具 ✅

- [x] 实现 12+ 操作工具函数（`core/tools/implementations/assistant_ops/`）
- [x] 集成到 `IntelligentAssistantService` 的工具列表（自动注册 123+ 工具）
- [x] 升级系统提示词为"操作员"模式
- [x] Web UI 验证全部操作工具可正常工作
- [x] 多通道会话隔离框架

### Phase 2: MCP Server ✅

- [x] 用 `fastmcp` 创建 MCP Server 入口，挂载到 `/mcp`
- [x] 暴露 `analyze_stock` / `chat_with_assistant` / `get_report` 等
- [x] 验证 Claude Desktop / Cursor 可调用
- [x] 长时间任务的进度通知机制

### Phase 3: Gateway ✅

- [x] Gateway 基础框架（路由、统一消息格式、Session 管理）
- [x] QQ Bot 适配器（WebSocket 模式，无需公网 IP）
- [x] 单用户自动映射模式（免绑定流程）
- [x] IM 格式适配（Markdown 表格→竖排 KV、字数控制）
- [x] 分析完成后 QQ IM 主动推送通知
- [ ] 飞书 / 钉钉 / 企业微信适配器（后续扩展）

### Phase 4: 全生命周期集成（v3.0 核心能力已完成，增量优化中）

- [x] 持仓分析工具（`position_analysis.py`：list_positions, get_position_analysis）
- [x] 交易复盘工具（`trade_review_ops.py`：list_trade_reviews, get_trade_review_detail）
- [x] 投资计划工具（`trading_plan.py`：list_trading_plans, get_active_trading_plan）
- [x] 滑动窗口会话记忆（最近 10 条历史注入 context）
- [x] 结构化用户画像（`assistant_user_profiles` 集合，分析完成后自动更新）
- [x] 用户画像注入系统提示词
- [x] 意图驱动路由 + 先确认再执行原则
- [x] RAG 金融知识检索（`FinancialKnowledgeManager`）
- [x] 主题会话列表与摘要侧栏（`assistant_threads` + Web UI）
- [x] 主题摘要快照与手动总结接口（`assistant_thread_checkpoints` / `summarize_assistant_thread`）
- [ ] 助手设置个性化 UI（名字、语气、自定义指令）
- [ ] 更多 IM 平台适配

---

## 7. 配置

- LLM 配置：从数据库 system_configs 读取，支持 quick_analysis_model、deep_analysis_model、deep_reasoning_model
- **ASSISTANT_TIMEOUT_SECONDS**：整体超时（默认 120 秒）
- **Gateway 配置**：存储在 `system_configs` 集合，包含各平台的 App ID、App Secret、Webhook URL 等

---

## 8. 助手记忆架构（v3.0）

### 8.1 问题背景

v1.0 的助手每次对话都是无状态的：LLM 不知道上一轮说了什么，用户说「帮我解读这份报告」时，助手会反问「请问是哪只股票的报告？」——即使几秒钟前刚刚完成了分析。

### 8.2 记忆方案评估

| 方案 | 原理 | 优点 | 缺点 | 适用场景 |
| ------ | ------ | ------ | ------ | --------- |
| **滑动窗口（当前）** | 最近 N 条原始消息注入 context | 实现简单，零延迟 | Token 随轮次增长；跨会话归零 | 短对话、快速上线 |
| **摘要记忆** | 超过阈值时 LLM 自动摘要 | Token 可控，不丢语义 | 摘要本身有信息损耗 | 中长对话 |
| **向量检索记忆（RAG）** | 对话 embedding 后按需检索 | 长期记忆、Token 高效 | 需向量库基础设施，有检索延迟 | 长期用户 |
| **知识图谱记忆（Cognee）** | 实体+关系图谱，图遍历检索 | 推理精准，关系清晰 | 依赖图数据库，方案较新 | 复杂推理场景 |
| **结构化用户画像（选定）** | MongoDB 显式存储用户偏好和历史 | 精准、可控、无 Token 消耗 | 需主动维护 | **交易场景，本项目首选** |

### 8.3 Cognee 评估结论

Cognee 是一个知识图谱记忆引擎（2026年2月完成 $7.5M 种子轮），能把非结构化文本自动转化为实体+关系图谱，适合"谁说了什么关于哪只股票"这类推理。

**评估结论：当前阶段不引入 Cognee**，原因：

1. 现有 Qdrant 向量基础设施（`core/memory/`、`core/knowledge/`）运行稳定，金融知识 RAG 已满足需求
2. Cognee 需额外引入图数据库（NetworkX/Neo4j），增加运维复杂度
3. 本项目最大痛点是"用户画像缺失"而非"记忆检索不精准"，结构化画像可低成本解决
4. 若未来助手需要跨会话的复杂语义推理，再评估引入 Cognee 作为会话实体提取层

### 8.4 已实现：滑动窗口（v3.0 第一步）

**实现文件**：`app/services/intelligent_assistant_service.py`

```text
chat_with_assistant()
    │
    ├── get_assistant_conversation(db, user_id)   ← 从 MongoDB 读历史
    │   └── 取最近 10 条，每条截断至 800 字
    │
    └── service.chat(..., history_messages=[...])
            │
            └── 消息列表构建顺序：
                [SystemMessage] → [历史1, 历史2, ..., 历史N] → [当前用户消息]
```

**局限**：滑动窗口只能覆盖当前主题附近的短期上下文；跨主题承接仍需依赖用户画像与主题摘要，不等同于长期记忆。

### 8.5 已实现：结构化用户画像（v3.0 第二步）

#### 数据结构

MongoDB 集合：`assistant_user_profiles`

```json
{
  "user_id": "ObjectId",
  "recently_analyzed": [
    {
      "symbol": "600519",
      "name": "贵州茅台",
      "analyzed_at": "ISODate",
      "conclusion": "买入",
      "task_id": "ObjectId"
    }
  ],
  "watchlist_symbols": ["600519", "300750", "002594"],
  "preference": {
    "investment_style": "价值投资",
    "risk_level": "稳健",
    "focus_sectors": ["消费", "新能源"]
  },
  "updated_at": "ISODate"
}
```

#### 更新时机

| 触发事件 | 更新内容 |
| --------- | --------- |
| 分析任务完成 | 追加到 `recently_analyzed`（保留最近 20 条） |
| 添加/移除自选股 | 同步更新 `watchlist_symbols` |
| 助手识别到用户偏好关键词 | 更新 `preference`（可选，LLM 提取） |

#### 注入方式

每次对话时，在系统提示词末尾注入用户画像摘要：

```text
【你对该用户的了解】
- 最近分析：贵州茅台(600519) · 2026-03-04 · 结论：买入
- 自选股：茅台、宁德时代、比亚迪（共 3 只）
- 偏好：价值投资，稳健风格，关注消费/新能源板块
```

#### 优先级说明

- 用户画像信息优先级 **高于** 滑动窗口历史
- 历史消息提供对话上下文，画像提供跨会话持久偏好
- 两者同时注入，画像放在系统提示词，历史放在 user/assistant 轮次之间

### 8.6 实现状态（含主题会话摘要）

除滑动窗口和用户画像外，当前实现还补上了面向长链路研究的主题会话承接能力：

- `assistant_threads`：按用户维护多主题会话，支持标题、最近消息、消息数和当前摘要
- `assistant_thread_checkpoints`：存储主题摘要快照，区分自动摘要与手动总结
- 每次保存对话后自动更新 `current_summary`，前端侧边栏展示摘要、已确认事实、待解决问题、建议下一步与聚焦度
- 提供 `/api/assistant/threads/{thread_id}/summarize` 接口，允许用户在研究中途手动收口

| 功能 | 状态 | 文件 |
| ------ | ------ | ------ |
| 滑动窗口记忆（最近 10 条） | ✅ 已实现 | `intelligent_assistant_service.py` |
| 主动调工具（get_latest_report）提示词规则 | ✅ 已实现 | `intelligent_assistant_service.py` `_get_system_prompt` |
| 结构化用户画像存储 | ✅ 已实现 | `assistant_user_profiles` 集合 |
| 用户画像注入系统提示词 | ✅ 已实现 | `intelligent_assistant_service.py` `_build_profile_block` |
| 分析完成后自动更新画像 | ✅ 已实现 | `task_analysis_service.py` `update_user_profile` |
| RAG 金融知识检索 | ✅ 已实现 | `core/knowledge/financial_knowledge_manager.py` |
| IM 渠道格式适配 | ✅ 已实现 | `intelligent_assistant_service.py` `is_im` 参数 |
| 主题会话列表 / 消息读取 | ✅ 已实现 | `app/routers/intelligent_assistant.py`、`frontend/src/api/assistant.ts` |
| 结构化主题摘要（abstract / facts / questions / actions / focus） | ✅ 已实现 | `summarize_assistant_thread`、`assistant_thread_checkpoints` |
| 手动总结入口与摘要侧栏 | ✅ 已实现 | `frontend/src/views/Assistant/index.vue` |
| 持仓分析工具 | ✅ 已实现 | `core/tools/implementations/assistant_ops/position_analysis.py` |
| 交易复盘工具 | ✅ 已实现 | `core/tools/implementations/assistant_ops/trade_review_ops.py` |
| 投资计划工具 | ✅ 已实现 | `core/tools/implementations/assistant_ops/trading_plan.py` |
