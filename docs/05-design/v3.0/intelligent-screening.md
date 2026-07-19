# 智能筛选（Intelligent Stock Screening）

## 📋 文档信息

| 项目 | 内容 |
|------|------|
| 版本 | v1.1 |
| 状态 | 已实现并持续优化 |
| 日期 | 2026-03 |
| 目标 | 在股票筛选页面提供基于 LLM 的自然语言选股能力，支持流式进度、结果卡片、股票关注列表联动与超时兜底 |

---

## 1. 概述

### 1.1 背景

现有股票筛选页面（`frontend/src/views/Screening/index.vue`）提供基于条件组合的传统筛选功能（行业、市值、PE、PB、ROE、涨跌幅等），用户需要手动配置多个筛选条件。

对于不熟悉财务指标的用户，或有模糊需求的场景（如"帮我找几只最近资金持续流入的低估值白马股"），传统筛选无法满足。

### 1.2 目标

在股票筛选页面新增 **智能筛选** Tab（与原有"传统筛选"并列），提供：

1. **自然语言选股**：用户用日常语言描述选股条件，LLM 理解后调用工具获取数据并推荐股票
2. **每次返回 5 只股票**：结构化展示，包含代码、名称、核心指标、推荐理由
3. **多轮对话记忆**：用户可追问调整条件（如"换成科技板块的""PE 再低一点"），系统保持上下文
4. **工具调用透明**：展示当前阶段、工具调用与摘要进度，增强可信度
5. **结果可落地**：支持将推荐结果加入股票关注列表，并可通过对话将结果放入指定分组

### 1.3 与智能助手的区别

| 维度 | 智能助手 | 智能筛选 |
|------|---------|---------|
| **定位** | 通用投资教练，回答任意问题 | 专注选股推荐 |
| **输出格式** | 自由文本 Markdown | 结构化股票卡片 + 理由 |
| **每次结果** | 不限 | 固定 5 只股票 |
| **需求确认** | 无 | **先分析需求 → 给出改进建议 → 生成执行计划 → 用户确认后再筛选** |
| **对话记忆** | 当前无（仅持久化，不传给 LLM） | **完整多轮记忆**（历史传给 LLM） |
| **系统提示词** | 通用投资教练风格 | 专注选股的专家风格 |
| **会话存储** | `assistant_conversations` | `screening_conversations`（独立） |
| **后续操作** | 无 | 当前已支持加入/取消自选；分组操作可通过对话触发，显式按钮待补 |

---

## 2. 系统架构

```
前端 Screening/index.vue
├── Tab: 传统筛选（现有功能，不变）
└── Tab: 智能筛选（新增）
   ├── 对话区域（多轮上下文 + Markdown 回复）
   ├── 阶段时间线（confirmation / planning / result）
   ├── 工具进度徽标（tool_started / tool_completed）
   ├── 股票结果卡片（每次 5 只，结构化展示）
   └── 操作按钮（当前已支持加入/取消自选）

     │ WebSocket /api/screening/intelligent/ws  ← 主链路，流式推送阶段与工具进度
     │ HTTP POST /api/screening/intelligent/chat ← 兼容同步调用
     ▼
后端 IntelligentScreeningService
├── 构建分阶段系统提示词（需求确认 / 执行规划 / 执行结果）
├── 拼接最近 N 轮对话历史作为 context
├── planning 阶段注入实际可用工具摘要，避免幻觉工具名
├── result 阶段仅开放批量筛选与股票关注列表相关工具
├── 通过 progress_callback 推送阶段、工具、超时、fallback 事件
├── 解析 LLM 返回 → 提取结构化股票列表
├── 超时后优先回退历史成功结果，再回退数据库快速粗筛
└── 持久化对话到 screening_conversations
```

---

## 3. 后端设计

### 3.1 复用与新增

智能筛选继续复用智能助手的底层能力，但运行时策略已经明显分化：

| 模块 | 当前实现 |
|------|---------|
| LLM 配置解析 | 复用 `_get_assistant_llm_config()` |
| 当前交易日 | 复用 `_get_latest_trade_date()` |
| 全局超时 | 复用 `ASSISTANT_TIMEOUT_SECONDS` |
| LLM 客户端 | 复用 `UnifiedLLMClient.from_config()` |
| 工具注册表 | 复用 `ToolRegistry`，但按智能筛选场景单独筛选工具 |
| 会话持久化 | 复用 MongoDB `$push + $slice` 模式 |
| 请求模型 | 继续复用 `ChatRequest` |

新增或定制的部分：

| 模块 | 当前实现 |
|------|---------|
| 阶段控制 | 三阶段流程：`confirmation` → `planning` → `result` |
| 进度推送 | 通过 `progress_callback` 将阶段、工具和 fallback 事件推送给前端 |
| 工具收敛 | result 阶段只允许批量筛选和股票关注列表相关工具 |
| 超时预算 | result 阶段独立使用 `SCREENING_RESULT_TIMEOUT_SECONDS=180` 秒 |
| 结构化结果 | 保持 `stocks` 字段，但当前仍依赖回复中的 JSON 代码块提取 |
| 用户上下文 | 调用 `set_current_user_id(user_id)`，使 assistant_ops 类工具在智能筛选中可用 |

### 3.2 当前服务行为

文件：`app/services/intelligent_screening_service.py`

1. `confirmation` 阶段
   - 只分析用户需求，不调用工具。
   - 输出需求理解、改进建议，并等待用户确认。

2. `planning` 阶段
   - 仍不执行工具，只说明接下来将调用哪些工具、用什么筛选思路。
   - 提示词中会注入实际可用工具摘要，避免生成不存在的工具名。

3. `result` 阶段
   - 调用 `UnifiedLLMClient.achat(..., auto_execute_tools=True)` 执行工具链。
   - `max_tool_rounds` 收紧为 4，避免多轮重工具导致长尾超时。
   - 结果阶段仅开放以下工具：

```text
screen_stocks_by_criteria
batch_check_profit_consistency
add_stocks_to_favorites
list_watchlist_groups
add_stock_to_watchlist
```

4. 超时与无结果兜底
   - result 阶段超时后，优先回退最近一次历史成功结果。
   - 若历史无结果，则调用数据库快速粗筛，返回高流动性、高市值的替代优质股。
   - 所有兜底结果都设置 `is_fallback=true`，并在文案中明确说明“不是原始条件的直接命中结果”。

5. 结果提取
   - 当前仍通过 `_extract_stocks()` 从 Markdown 回复末尾的 JSON 代码块中提取 `stocks`。
   - 这是当前最主要的可靠性风险，也是下一轮优化重点。

### 3.3 提示词约束

当前提示词与实现保持一致，关键约束如下：

| 约束 | 当前要求 |
|------|---------|
| 阶段隔离 | confirmation 和 planning 阶段不调用工具 |
| 数量约束 | result 阶段默认输出 5 只股票 |
| 结构化输出 | result 阶段末尾必须附带 JSON 代码块，供后端提取 `stocks` |
| 结果真实性 | 若未筛出符合原条件的股票，必须明确说明并将替代结果标注为参考 |
| 操作闭环 | 仅在用户明确要求时，才调用“加入自选/加入分组”类工具 |
| 范围约束 | 仅推荐 A 股，不给买卖建议 |

### 3.4 与智能助手的运行差异

| 维度 | 智能助手 | 智能筛选 |
|------|---------|---------|
| 对话历史 | 默认不把完整历史传给 LLM | 传最近 20 条历史 |
| 主交互方式 | HTTP 问答为主 | WebSocket 流式为主，HTTP 保留兼容 |
| 阶段模型 | 单阶段 | confirmation → planning → result |
| 工具范围 | 全量 `fc_enabled` 工具 | 加载选股相关工具，执行阶段再收敛到白名单 |
| 超时策略 | 使用全局超时 | result 阶段使用独立更紧的预算 |
| 失败处理 | 文本报错为主 | 历史成功结果 / 数据库粗筛双层 fallback |

---

## 4. API 端点设计

### 4.1 路由

文件：`app/routers/intelligent_screening.py`
前缀：`/api/screening/intelligent`

| 方法 | 路径 | 说明 |
|------|------|------|
| `POST` | `/chat` | 同步模式对话接口，保留兼容用途 |
| `WS` | `/ws` | 主交互链路，流式推送阶段与工具进度 |
| `GET` | `/conversation` | 获取对话历史 |
| `DELETE` | `/conversation` | 清空对话 |

### 4.2 请求/响应模型

请求模型继续复用 `app/schemas/intelligent_assistant.py` 中的 `ChatRequest`。

响应模型位于 `app/schemas/intelligent_screening.py`，当前已扩展为：

| 模型 | 关键字段 |
|------|---------|
| `StockRecommendation` | `code`、`name`、`industry`、`price`、`pe`、`pb`、`roe`、`roa`、`gross_margin`、`netprofit_margin`、`dividend_yield`、`debt_to_assets`、`assets_to_eqt`、`current_ratio`、`quick_ratio`、`cash_ratio`、`revenue_ttm`、`net_profit_ttm`、`n_cashflow_act`、`report_period`、`pct_change`、`reason` |
| `ScreeningChatResponse` | `reply`、`tools_used`、`stocks`、`phase`、`is_fallback` |
| `ScreeningMessageItem` | `role`、`content`、`tools_used`、`stocks`、`phase`、`is_fallback` |
| `ScreeningConversationResponse` | `messages` |

### 4.3 WebSocket 消息结构

前端通过 WebSocket 获取流式事件，当前消息类型包括：

| 类型 | 用途 |
|------|------|
| `connected` | 连接建立成功 |
| `started` | 后端已收到请求 |
| `progress` | 阶段切换、工具开始/完成、fallback 预告 |
| `final` | 最终回复，包含 `reply/stocks/tools_used/phase/is_fallback` |
| `error` | 处理失败 |
| `pong` | 心跳响应 |

`progress` 事件中的关键字段：

| 字段 | 说明 |
|------|------|
| `event` | 如 `phase_determined`、`status`、`tool_started`、`tool_completed`、`timeout`、`fallback_ready` |
| `phase` | 当前阶段 |
| `message` | 面向用户的简短说明 |
| `tool` | 当前工具名 |
| `summary` | 工具执行摘要，例如候选数量、新增自选数量等 |

### 4.4 当前路由行为

- `/chat`：直接调用 `IntelligentScreeningService.chat()`，适合测试或兼容场景。
- `/ws`：校验 token 后建立长连接，把阶段和工具进度实时推送给前端。
- `/conversation`：读取或清空 `screening_conversations`。
- 历史接口会把 `phase` 和 `is_fallback` 一并返回，前端可完整恢复 UI 状态。

---

## 5. MongoDB Schema

### 5.1 集合: `screening_conversations`

```javascript
{
  "_id": ObjectId(),
  "user_id": "admin",
  "messages": [
  {
    "role": "user",
    "content": "帮我找几只低估值的银行股",
    "timestamp": ISODate("2026-03-13T10:00:00Z")
  },
  {
    "role": "assistant",
    "content": "## 需求分析 ...",
    "tools_used": [],
    "stocks": [],
    "phase": "confirmation",
    "is_fallback": false,
    "timestamp": ISODate("2026-03-13T10:00:03Z")
  },
  {
    "role": "assistant",
    "content": "未能为您筛出明确符合原条件的股票...",
    "tools_used": ["screen_stocks_by_criteria"],
    "stocks": [/* 5 只替代优质股 */],
    "phase": "result",
    "is_fallback": true,
    "timestamp": ISODate("2026-03-13T10:00:30Z")
  }
  ],
  "created_at": ISODate("2026-03-13T10:00:00Z"),
  "updated_at": ISODate("2026-03-13T10:00:30Z")
}
```

索引与消息限制保持不变：

- `db.screening_conversations.createIndex({"user_id": 1}, {unique: true})`
- 使用 `$push + $slice: -50` 保留最近 50 条消息

---

## 6. 前端设计

### 6.1 当前页面结构

智能筛选仍内嵌在 `frontend/src/views/Screening/index.vue` 的 Tab 中，但交互已从“提交后等待整包返回”升级为“阶段化流式反馈”：

1. 对话区
   - 展示用户消息和助手 Markdown 回复。
   - 支持从历史接口恢复会话。

2. 进度时间线
   - 当 assistant 消息尚未完成时，先展示占位消息。
   - `progressSteps` 按时间线展示阶段切换和工具执行摘要。

3. 阶段按钮
   - `confirmation` 阶段：展示“按原需求筛选”“采纳建议后筛选”。
   - `planning` 阶段：展示“执行筛选方案”“重新描述需求”。

4. 结果卡片
   - 当前展示 `price/pe/pb/roe/roa/gross_margin/netprofit_margin/dividend_yield/debt_to_assets/assets_to_eqt/current_ratio/quick_ratio/cash_ratio/revenue_ttm/net_profit_ttm/n_cashflow_act/report_period/pct_change`。
   - 当 `is_fallback=true` 时，顶部显示黄色警示，明确这是替代候选而非命中结果。

5. 卡片操作
   - 当前前端显式支持“加入自选/取消自选”。
   - “查看详情 / 发起分析 / 指定分组”仍属于下一轮体验增强项。

### 6.2 前端 API 与类型

文件：`frontend/src/api/screening.ts`

当前已包含：

| 类型/方法 | 当前实现 |
|------|---------|
| `StockRecommendation` | 已同步更多财务字段 |
| `ScreeningChatResponse` | 包含 `phase` 与 `is_fallback` |
| `ScreeningMessageItem` | 支持历史恢复阶段和 fallback 状态 |
| `ScreeningWsEnvelope` | WebSocket 统一消息封装 |
| `ScreeningWsProgressData` | 进度、工具、摘要字段 |
| `getIntelligentChatWsUrl()` | 生成智能筛选 WebSocket 地址 |

### 6.3 当前前端能力边界

已实现：

- WebSocket 流式连接与断线处理
- 阶段时间线和工具摘要
- fallback 警示文案
- 智能筛选结果加入/取消自选
- 会话历史恢复与清空

未完成：

- 结果卡片显式“查看详情”按钮
- 结果卡片显式“发起分析”按钮
- 结果卡片显式“加入指定分组”按钮

---

## 7. 工具选择策略

智能筛选仍通过统一的 `ToolRegistry` 加载工具，但已经拆成“可见工具集”和“执行工具集”两层：

### 7.1 加载层

服务初始化时会加载与以下类别相关的工具：

- `screening`
- `market`
- `fundamentals`
- `news`
- `china`
- `technical`

此外，显式补入以下与用户操作闭环相关的工具：

- `add_stocks_to_favorites`
- `list_watchlist_groups`
- `add_stock_to_watchlist`

### 7.2 执行层

真正进入 `result` 阶段时，只保留如下白名单：

| 工具 | 作用 |
|------|------|
| `screen_stocks_by_criteria` | 批量数据库筛选，核心工具 |
| `batch_check_profit_consistency` | 对候选进行批量盈利稳定性校验 |
| `add_stocks_to_favorites` | 用户明确要求时批量加入自选 |
| `list_watchlist_groups` | 查询已有分组 |
| `add_stock_to_watchlist` | 将推荐股票放入指定分组 |

这样做的目的：

- 避免单股重工具串行调用导致长尾超时
- 让 planning 阶段与 result 阶段的工具集合保持一致
- 保证“筛选结果生成”和“结果落地操作”在同一条对话链路内完成

---

## 8. 当前实现状态与后续方向

### 8.1 已完成能力

1. 三阶段智能筛选流程已经落地：`confirmation` → `planning` → `result`。
2. 前后端主链路已切换为 WebSocket 流式反馈，不再只在最后返回结果。
3. result 阶段已收敛到批量筛选白名单，并设置独立超时预算。
4. 超时或无命中结果时，已支持历史成功结果 / 数据库快速粗筛双层 fallback。
5. fallback 文案已明确区分“未命中原条件”和“优质股替代参考”。
6. 智能筛选已支持调用股票关注列表与分组相关工具。
7. 前端结果卡片已展示更多财务指标，并支持加入/取消自选。
8. 结果卡片已可展示盈利质量、偿债能力、滚动营收、滚动净利润和经营现金流等扩展字段。

### 8.2 当前已知限制

1. 结构化结果提取仍依赖 LLM 回复中的 JSON 代码块，鲁棒性不足。
2. 结果卡片还没有显式暴露“查看详情 / 发起分析 / 加入指定分组”按钮。
3. 当前对“本轮实际筛选条件”和“排序依据”的可解释展示还不够结构化。

### 8.3 下一步优先级

1. 优先增强结果可靠性，减少对 JSON 代码块提取的脆弱依赖。
2. 补齐结果闭环，增加详情、分析和分组入口。
3. 增强筛选条件与排序依据的可解释展示。

## 9. 路由注册

在 `app/main.py` 中注册新路由：

```python
from app.routers.intelligent_screening import router as intelligent_screening_router
app.include_router(intelligent_screening_router)
```

---

## 10. 变更同步说明

本次文档同步主要反映以下已落地改动：

1. 智能筛选已不是“待实现”功能，而是线上可用功能。
2. 交互方式从同步 HTTP 补充为 WebSocket 主链路。
3. 流程从两阶段升级为三阶段，并增加 planning 阶段。
4. 增加了 result 阶段工具白名单、独立超时预算与 fallback 机制。
5. 增加了 `is_fallback`、更多财务字段、股票关注列表与分组操作能力。
6. 将“后续操作”修正为当前真实状态，避免文档继续误导为“已支持详情/分析显式按钮”。

---

## 11. 相关文档

- [智能助手](./intelligent-assistant.md) — 参考实现模式
- [Skill 生成系统](./skill-generation-system.md) — 会话管理参考
- [MCP 支持](./mcp-support.md) — 外部数据源工具

