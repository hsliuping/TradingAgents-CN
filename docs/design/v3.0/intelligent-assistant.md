# 智能助手（分析助理）

## 📋 文档信息

| 项目 | 内容 |
|------|------|
| 版本 | v2.0 |
| 状态 | v1.0 已实现 / v2.0 设计中 |
| 日期 | 2026-03 |
| 目标 | 从"数据教练"升级为"全能操作员"，成为 Gateway 和 MCP Server 的统一后端大脑 |

---

## 1. 概述

智能助手（分析助理）是 TradingAgents-CN 的**核心协调角色**。它不仅是对话式分析入口，更是连接外部通道（Gateway / MCP Server）与内部系统（工作流引擎、定时调度、报告库）的中枢。

### 1.1 角色演进

| 阶段 | 角色定位 | 能力范围 |
|------|---------|---------|
| **v1.0（已实现）** | 数据教练 | 调用数据工具回答问题、规划分析 |
| **v2.0（本设计）** | 全能操作员 | 触发分析流、查看报告、管理定时任务、管理自选股、多通道接入 |

### 1.2 三层架构定位

```
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
│  │  ├── 意图识别（LLM Function Calling）                │    │
│  │  ├── 操作工具（触发分析、查报告、管定时任务...）      │    │
│  │  ├── 数据工具（行情、财务、新闻...，已有）           │    │
│  │  ├── 会话管理（多通道 Session 隔离）                 │    │
│  │  └── 结果格式化（Markdown / 卡片消息 / MCP 响应）    │    │
│  └─────────────────────────────────────────────────────┘    │
│                          │                                   │
│                          ▼                                   │
├─────────────────────────────────────────────────────────────┤
│  Layer 3: 内部系统（黑箱，不对外暴露）                        │
│  ┌───────────┐  ┌───────────┐  ┌──────────┐  ┌──────────┐  │
│  │ Workflow   │  │ Scheduler │  │ Report   │  │ Watchlist│  │
│  │ Engine     │  │ Service   │  │ Store    │  │ Groups   │  │
│  └───────────┘  └───────────┘  └──────────┘  └──────────┘  │
└─────────────────────────────────────────────────────────────┘
```

---

## 2. v1.0 已实现能力

### 2.1 后端

| 模块 | 实现位置 | 说明 |
|------|----------|------|
| **API 路由** | `app/routers/intelligent_assistant.py` | 统一前缀 `/api/assistant` |
| **智能助手服务** | `app/services/intelligent_assistant_service.py` | ReAct 模式、LLM 配置、RAG 知识检索 |
| **规划分析服务** | `app/services/planned_analysis_service.py` | 种子流程匹配 → LLM 规划 → ReAct 回退 |
| **请求/响应模型** | `app/schemas/intelligent_assistant.py` | ChatRequest、ChatResponse、PlannedAnalysisResponse |

### 2.2 前端

| 模块 | 实现位置 | 说明 |
|------|----------|------|
| **助手页面** | `frontend/src/views/Assistant/index.vue` | 对话界面、模式切换（快速/深度） |
| **API** | `frontend/src/api/assistant.ts` | chat、planned-analysis、conversation |
| **侧边栏** | `SidebarMenu.vue` | 智能助手入口 |

### 2.3 API 端点（v1.0）

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | /api/assistant/chat | 智能助手对话（ReAct 模式） |
| POST | /api/assistant/planned-analysis | 规划分析（Plan-then-Execute） |
| GET | /api/assistant/conversation | 获取会话历史 |
| DELETE | /api/assistant/conversation | 清空会话 |

### 2.4 规划分析三级保障

| 级别 | 说明 |
|------|------|
| 1. 种子流程匹配 | 匹配预设种子流程（如单股分析、板块分析），执行固定工作流 |
| 2. LLM 自主规划 | 无匹配时，LLM 规划多步骤执行计划，并行执行 |
| 3. ReAct 回退 | 规划失败时，回退到 ReAct 模式逐步调用工具 |

### 2.5 v1.0 能力特性

- **RAG 知识检索**：从向量数据库获取金融知识片段注入系统提示词
- **工具自主选择**：根据 when_to_use 描述，LLM 自主选择最合适的工具
- **会话持久化**：对话历史持久化，支持下次进入查看
- **教练风格**：教方法、讲框架、用数据说话，不直接给投资建议

---

## 3. v2.0 设计：分析助理升级

### 3.1 核心变化

| 维度 | v1.0 | v2.0 |
|------|------|------|
| **角色** | 数据教练 | 全能操作员 |
| **工具范围** | 数据查询工具（行情、财务、新闻） | 数据工具 + 操作工具（触发分析、管理定时、查报告） |
| **接入通道** | 仅 Web UI | Web UI + Gateway（飞书/QQ/钉钉） + MCP Server |
| **会话隔离** | 按用户隔离 | 按用户 × 通道隔离（同一用户从飞书和Web的会话独立） |
| **输出格式** | 纯 Markdown | Markdown + 卡片消息 + MCP Response |
| **系统提示词** | 教练模式 | 操作员模式（可以做事，不仅是回答问题） |

### 3.2 操作工具定义（~12 个）

分析助理通过 LLM Function Calling 自动选择并调用以下工具：

#### 📊 分析触发类

| 工具名 | 功能 | 内部调用 | 参数 |
|--------|------|---------|------|
| `trigger_stock_analysis` | 触发单只股票分析 | `TaskAnalysisService.create_and_execute_task()` | symbol, depth?, workflow_id? |
| `trigger_batch_analysis` | 触发批量股票分析 | `TaskAnalysisService.create_and_execute_task()` × N | symbols[], depth? |
| `get_analysis_status` | 查询分析任务状态 | `TaskAnalysisService.get_task()` | task_id |

**示例对话**：
```
用户: "帮我分析一下贵州茅台"
助理: [调用 trigger_stock_analysis(symbol="600519")]
      "已为您创建贵州茅台(600519)的分析任务，任务ID: xxx，预计 3 分钟完成。"

用户: "分析进度怎么样了？"
助理: [调用 get_analysis_status(task_id="xxx")]
      "任务正在运行中，当前进度 60%，市场分析师和基本面分析师已完成，新闻分析师正在工作。"
```

#### 📝 报告查询类

| 工具名 | 功能 | 内部调用 | 参数 |
|--------|------|---------|------|
| `search_reports` | 搜索历史分析报告 | `db.analysis_reports.find()` | keyword?, symbol?, date_range? |
| `get_report_detail` | 获取报告详情 | `db.analysis_reports.find_one()` | report_id or task_id |
| `get_latest_report` | 获取某只股票最新报告 | `db.unified_analysis_tasks.find_one(sort)` | symbol |

**示例对话**：
```
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
|--------|------|---------|------|
| `list_scheduled_configs` | 查看定时分析配置 | `db.scheduled_analysis_configs.find()` | — |
| `create_scheduled_analysis` | 创建定时分析 | 调用 ScheduledAnalysis API | name, cron, group_ids, depth? |
| `toggle_scheduled_config` | 启用/禁用定时配置 | `db.scheduled_analysis_configs.update_one()` | config_id, enabled |

**示例对话**：
```
用户: "帮我设置每天早上9点分析科技股分组"
助理: [调用 create_scheduled_analysis(name="每日科技股分析", cron="0 9 * * 1-5", group_ids=["group_tech"])]
      "已创建定时分析配置 '每日科技股分析'，将在每个交易日 9:00 自动分析科技股分组中的所有股票。"
```

#### 📁 自选股管理类

| 工具名 | 功能 | 内部调用 | 参数 |
|--------|------|---------|------|
| `list_watchlist_groups` | 查看自选股分组 | `db.watchlist_groups.find()` | — |
| `add_stock_to_watchlist` | 添加股票到分组 | `db.watchlist_groups.update_one($addToSet)` | group_name, symbol |
| `remove_stock_from_watchlist` | 从分组移除股票 | `db.watchlist_groups.update_one($pull)` | group_name, symbol |

**示例对话**：
```
用户: "把比亚迪加到科技股分组里"
助理: [调用 add_stock_to_watchlist(group_name="科技股", symbol="002594")]
      "已将比亚迪(002594)添加到「科技股」分组。该分组现有 12 只股票。"
```

### 3.3 意图识别流程

```
用户消息
    │
    ▼
┌──────────────────────────────────────────┐
│  LLM（带 Function Calling 定义）          │
│                                          │
│  System Prompt:                          │
│  "你是 TradingAgents 分析助理，           │
│   可以触发分析、查看报告、管理定时任务..." │
│                                          │
│  Tools:                                  │
│  - trigger_stock_analysis                │
│  - search_reports                        │
│  - create_scheduled_analysis             │
│  - ... (全部 12 个工具)                   │
│  - (原有数据工具保留)                     │
└──────┬───────────────────────────────────┘
       │
       ├── function_call → 执行操作工具 → 返回结果
       │
       └── text_response → 直接回复（闲聊/解释/建议）
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

### 3.5 系统提示词升级

```
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

```
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

```
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

```
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
|----------|-------------|
| `analyze_stock` | `trigger_stock_analysis` + 等待完成 + 返回报告 |
| `screen_stocks` | 调用筛选工作流 + 返回结果 |
| `get_market_overview` | 调用市场概览流程 |
| `chat_with_assistant` | 直接调用 `AnalysisAssistant.chat()` |
| `get_report` | `get_report_detail` |
| `list_workflows` | 查询可用工作流定义 |

---

## 6. 实施计划

### Phase 1: 操作工具（2-3 周）

- [ ] 实现 12 个操作工具函数
- [ ] 集成到 `IntelligentAssistantService` 的工具列表
- [ ] 升级系统提示词为"操作员"模式
- [ ] Web UI 验证全部操作工具可正常工作
- [ ] 多通道会话隔离框架

### Phase 2: MCP Server（1-2 周）

- [ ] 用 `fastmcp` 创建 MCP Server 入口
- [ ] 暴露 `analyze_stock` / `chat_with_assistant` / `get_report` 等
- [ ] 验证 Claude Desktop / Cursor 可调用
- [ ] 长时间任务的进度通知机制

### Phase 3: Gateway（2-3 周）

- [ ] Gateway 基础框架（路由、统一消息格式）
- [ ] 飞书 Bot 适配器（Event Subscription + 消息回复）
- [ ] 用户身份绑定机制
- [ ] 卡片消息格式化
- [ ] 逐步扩展 QQ / 钉钉 / 企业微信

---

## 7. 配置

- LLM 配置：从数据库 system_configs 读取，支持 quick_analysis_model、deep_analysis_model、deep_reasoning_model
- **ASSISTANT_TIMEOUT_SECONDS**：整体超时（默认 120 秒）
- **Gateway 配置**：存储在 `system_configs` 集合，包含各平台的 App ID、App Secret、Webhook URL 等
