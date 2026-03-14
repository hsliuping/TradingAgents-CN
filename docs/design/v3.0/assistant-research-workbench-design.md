# 助手研究工作台设计方案（OpenViking 集成版）

## 1. 背景与目标

当前智能助手适合短对话，但不适合长链路股票研究，主要问题：

- 所有聊天按用户汇总到单条会话，没有主题切分。
- 后端 `conversation_id` 仍是预留字段，未真正参与会话路由。
- 模型上下文只注入最近少量原始消息，缺少滚动压缩层。
- 研究过程中的关键结论、假设、待验证问题、引用资料没有形成结构化沉淀。
- 聊天越长越容易发散，最终造成主线不清、成本上升、回答质量下降。

本方案目标是把现有“聊天框助手”升级为“研究工作台助手”：

- 支持多主题研究会话。
- 支持会话滚动摘要与阶段压缩。
- 支持研究主线/分支主题管理。
- 支持用户长期研究记忆沉淀。
- 支持把外部研报、财报、网页、历史报告作为研究资源统一检索。
- 保持现有 Tool/Workflow/Analysis 能力不变，只增强上下文管理层。

## 2. 设计原则

1. 不替换现有业务执行层。
2. MongoDB 继续承担业务主存储与查询入口。
3. OpenViking 作为上下文 sidecar，负责 Memory/Resource/Skill 的组织与检索增强。
4. 第一阶段优先解决“长对话失焦”问题，而不是一次性重构所有助手能力。
5. 所有新接口优先兼容现有 `/api/assistant/chat` 与 `/api/assistant/planned-analysis` 调用模式。

## 3. 总体架构

### 3.1 分层

保留现有层：

- 前端助手页面
- FastAPI Assistant Router
- IntelligentAssistantService / PlannedAnalysisService
- ToolRegistry / WorkflowEngine / Analysis Services
- MongoDB 业务数据

新增上下文层：

- Thread（主题会话）
- Thread Summary（滚动摘要）
- Research Memo（结构化研究备忘）
- OpenViking Context Sidecar

### 3.2 职责划分

MongoDB 负责：

- 会话主题元数据
- 原始消息
- UI 列表查询
- 权限归属
- 分析任务、报告、自选股、持仓等业务实体

OpenViking 负责：

- 用户长期记忆
- 主题摘要归档
- 研究资源归档
- 主题相关语义检索
- 分支主题上下文继承
- 未来的上下文可观察性

## 4. 数据模型

## 4.1 Mongo 集合设计

### assistant_threads

用途：研究主题主表。

建议字段：

```json
{
  "thread_id": "thr_xxx",
  "user_id": "<user_id>",
  "title": "宁德时代 2026Q1 跟踪",
  "topic_type": "stock_research",
  "topic_key": {
    "symbol": "300750",
    "market": "CN"
  },
  "status": "active",
  "mode": "research",
  "source": "manual",
  "parent_thread_id": null,
  "branch_reason": "从主线拆出行业景气分支",
  "pinned": false,
  "archived": false,
  "message_count": 26,
  "last_message_at": "2026-03-14T10:20:00Z",
  "last_user_message": "再看一下动力电池价格趋势",
  "summary_version": 3,
  "current_summary": {
    "abstract": "当前聚焦宁德时代与动力电池价格趋势的关系",
    "confirmed_facts": ["..."],
    "open_questions": ["..."],
    "next_actions": ["..."],
    "focus_score": 0.82
  },
  "created_at": "2026-03-14T09:00:00Z",
  "updated_at": "2026-03-14T10:20:00Z"
}
```

索引建议：

- `(user_id, archived, updated_at desc)`
- `(user_id, status, updated_at desc)`
- `(user_id, topic_type, updated_at desc)`
- `(user_id, topic_key.symbol, updated_at desc)`
- `(parent_thread_id)`

### assistant_thread_messages

用途：保存原始消息流，不再把整段历史塞到单文档数组里。

建议字段：

```json
{
  "message_id": "msg_xxx",
  "thread_id": "thr_xxx",
  "user_id": "<user_id>",
  "role": "assistant",
  "content": "...",
  "content_type": "markdown",
  "tools_used": ["get_stock_market_data_unified"],
  "tool_rounds": 2,
  "token_estimate": 1234,
  "stage_tag": "valuation",
  "source": "planned_analysis",
  "citations": [],
  "created_at": "2026-03-14T10:20:00Z"
}
```

索引建议：

- `(thread_id, created_at asc)`
- `(user_id, thread_id, created_at desc)`

### assistant_thread_checkpoints

用途：保存阶段摘要和压缩结果。

建议字段：

```json
{
  "checkpoint_id": "chk_xxx",
  "thread_id": "thr_xxx",
  "user_id": "<user_id>",
  "range": {
    "from_message_id": "msg_001",
    "to_message_id": "msg_018"
  },
  "summary_type": "rolling",
  "summary_text": "...",
  "structured_summary": {
    "research_goal": "确认业绩驱动是否持续",
    "confirmed_facts": ["..."],
    "hypotheses": ["..."],
    "open_questions": ["..."],
    "risks": ["..."],
    "next_actions": ["..."],
    "mentioned_symbols": ["300750", "002594"]
  },
  "created_by": "system",
  "created_at": "2026-03-14T10:15:00Z"
}
```

索引建议：

- `(thread_id, created_at desc)`
- `(thread_id, summary_type, created_at desc)`

### assistant_thread_links

用途：记录会话与业务对象的关系，避免把业务主键硬编码进消息。

建议字段：

```json
{
  "thread_id": "thr_xxx",
  "user_id": "<user_id>",
  "link_type": "analysis_task",
  "link_id": "task_xxx",
  "title": "宁德时代单股分析任务",
  "meta": {
    "symbol": "300750"
  },
  "created_at": "2026-03-14T10:00:00Z"
}
```

可关联类型：

- `analysis_task`
- `report`
- `portfolio_position`
- `review`
- `favorite_group`
- `uploaded_file`
- `external_url`

### assistant_user_profiles

继续保留现有集合，但职责收缩为“轻量用户画像缓存”，不要再承担复杂长期记忆。

保留字段：

- `recently_analyzed`
- `watchlist_symbols`
- `preference`

长期研究记忆迁移到 OpenViking。

## 4.2 OpenViking 结构设计

建议把 OpenViking 作为用户级上下文空间，每个主题会话挂在其下。

建议路径语义：

- `viking://users/{user_id}/memories/profile/`
- `viking://users/{user_id}/threads/{thread_id}/memories/`
- `viking://users/{user_id}/threads/{thread_id}/resources/`
- `viking://users/{user_id}/threads/{thread_id}/summaries/`
- `viking://users/{user_id}/threads/{thread_id}/skills/`

写入规则：

- 用户稳定偏好写 `profile`
- 当前研究主题阶段总结写 `summaries`
- 研报、财报、网页、历史报告写 `resources`
- 复用价值高的研究结论写 `memories`

## 5. 上下文拼装策略

每轮对话前的上下文不再是“最近 N 条原始消息”，而是五段式拼装：

1. 系统提示词
2. 当前主题摘要 `current_summary`
3. 最近原始消息窗口（建议 6-8 条）
4. OpenViking 检索到的主题相关资源/记忆
5. 用户轻量画像

建议优先级：

```text
system_prompt
-> thread_summary
-> recent_raw_messages
-> openviking_resources
-> openviking_memories
-> user_profile
```

### 5.1 压缩触发条件

满足任一条件触发滚动摘要：

- 单主题消息数 >= 12
- 最近 6 条消息累计字符数 >= 6000
- 工具调用轮数 >= 6
- 主题发生明显漂移
- 进入新的研究阶段（估值、财报、行业、风险、交易计划）

### 5.2 结构化摘要模板

每次摘要输出固定结构：

```json
{
  "research_goal": "当前主要研究目标",
  "confirmed_facts": ["已确认事实"],
  "hypotheses": ["待验证假设"],
  "open_questions": ["未解决问题"],
  "risks": ["主要风险点"],
  "next_actions": ["建议下一步"],
  "focus_score": 0.0
}
```

### 5.3 分支策略

当检测到对话偏离主线时，系统提示：

- 继续在当前主题深入
- 拆成新分支主题

适合拆分的情况：

- 从个股跳到板块景气
- 从基本面跳到交易纪律
- 从研究结论跳到组合配置
- 从主问题跳到资料核验

## 6. API 设计

## 6.1 主题管理 API

### GET /api/assistant/threads

用途：获取主题列表。

查询参数：

- `archived`
- `status`
- `topic_type`
- `keyword`
- `symbol`
- `page`
- `page_size`

响应示例：

```json
{
  "items": [
    {
      "thread_id": "thr_xxx",
      "title": "宁德时代 2026Q1 跟踪",
      "topic_type": "stock_research",
      "topic_key": {"symbol": "300750", "market": "CN"},
      "status": "active",
      "message_count": 26,
      "last_user_message": "再看一下动力电池价格趋势",
      "summary": "当前聚焦业绩驱动与电池价格趋势",
      "updated_at": "2026-03-14T10:20:00Z"
    }
  ],
  "total": 1
}
```

### POST /api/assistant/threads

用途：创建新主题。

请求：

```json
{
  "title": "比亚迪出口链跟踪",
  "topic_type": "stock_research",
  "topic_key": {"symbol": "002594", "market": "CN"},
  "initial_message": "先从出口销量和海外定价开始分析"
}
```

### GET /api/assistant/threads/{thread_id}

用途：获取主题详情。

返回：

- thread metadata
- current summary
- latest checkpoint
- related links preview

### PATCH /api/assistant/threads/{thread_id}

用途：修改标题、归档状态、置顶状态、状态。

### DELETE /api/assistant/threads/{thread_id}

用途：软删除主题。

### POST /api/assistant/threads/{thread_id}/fork

用途：从当前主题派生新分支。

请求：

```json
{
  "title": "动力电池行业价格趋势",
  "branch_reason": "从宁德时代主线拆出行业分支",
  "inherit_summary": true,
  "inherit_recent_messages": 4
}
```

## 6.2 消息与上下文 API

### GET /api/assistant/threads/{thread_id}/messages

用途：分页拉取消息。

查询参数：

- `cursor`
- `limit`

### GET /api/assistant/threads/{thread_id}/context

用途：调试接口，返回本轮实际注入模型的上下文片段。

返回：

- `system_prompt_preview`
- `thread_summary`
- `recent_messages`
- `retrieved_memories`
- `retrieved_resources`
- `user_profile`

这个接口只给内部调试和管理员使用。

### POST /api/assistant/threads/{thread_id}/summarize

用途：手动触发主题压缩。

响应：

- `checkpoint_id`
- `summary`
- `focus_score`

## 6.3 对话 API

### POST /api/assistant/threads/{thread_id}/chat

用途：在指定主题内进行快速对话。

请求：

```json
{
  "message": "再看一下估值和资金面的矛盾点",
  "mode": "react"
}
```

响应：

```json
{
  "reply": "...",
  "tools_used": ["..."],
  "data_refs": [],
  "thread_summary_updated": true,
  "focus_score": 0.76,
  "suggested_actions": [
    {"type": "fork_thread", "title": "拆分为行业景气分支"}
  ]
}
```

### POST /api/assistant/threads/{thread_id}/planned-analysis

用途：在指定主题内进行规划分析。

保留现有返回结构，并新增：

- `thread_summary_updated`
- `focus_score`
- `related_links`

## 6.4 兼容 API

为兼容现有前端，保留旧接口一段时间：

- `GET /api/assistant/conversation`
- `DELETE /api/assistant/conversation`
- `POST /api/assistant/chat`
- `POST /api/assistant/planned-analysis`

兼容策略：

- 如果未传 `conversation_id`，则路由到“默认临时主题”
- 前端升级完成后，再将旧接口标记为 deprecated

## 7. 前端交互方案

## 7.1 页面结构

现有单列聊天页升级为三段式布局：

- 左侧：主题列表
- 中间：聊天与研究过程
- 右侧：研究摘要 / 相关资源 / 相关对象

### 左侧主题列表

显示内容：

- 主题标题
- 股票代码或主题标签
- 最新摘要一句话
- 更新时间
- 是否分支主题

支持操作：

- 新建主题
- 搜索主题
- 归档
- 置顶
- 分叉主题

### 中间聊天区

保留现有聊天体验，但每条消息归属于当前 thread。

增强显示：

- 当前主题名
- 当前研究阶段标签
- 主题是否失焦提示
- “建议拆分新主题”提示

### 右侧研究面板

包含：

- 当前摘要
- 已确认事实
- 待验证问题
- 下一步建议
- 相关报告/链接/任务

## 7.2 前端状态模型

建议新增：

```ts
interface AssistantThread {
  thread_id: string
  title: string
  topic_type: string
  topic_key?: Record<string, any>
  summary?: string
  message_count: number
  updated_at: string
  pinned: boolean
  archived: boolean
  parent_thread_id?: string | null
}

interface AssistantThreadDetail extends AssistantThread {
  current_summary?: {
    abstract: string
    confirmed_facts: string[]
    open_questions: string[]
    next_actions: string[]
    focus_score?: number
  }
}
```

## 8. 服务端流程设计

## 8.1 chat 流程

1. 校验线程归属
2. 写入用户消息
3. 读取 thread metadata
4. 读取最近消息窗口
5. 读取当前摘要
6. 从 OpenViking 检索该 thread 的 memory/resource
7. 拼装上下文
8. 调用 IntelligentAssistantService 或 PlannedAnalysisService
9. 写入 assistant 消息
10. 根据条件触发摘要更新
11. 返回 reply + summary delta

## 8.2 摘要更新流程

建议异步化：

1. 找到最近未压缩消息范围
2. 调用轻量模型输出结构化摘要
3. 写入 `assistant_thread_checkpoints`
4. 更新 `assistant_threads.current_summary`
5. 将高价值结论同步到 OpenViking memory

## 8.3 OpenViking 同步规则

同步到 OpenViking 的内容必须经过筛选，不直接灌整段聊天：

- 高置信度研究结论
- 用户长期偏好
- 与当前主题强相关的资料摘要
- 阶段性研究总结

不要同步：

- 普通寒暄
- 临时追问
- 无法确认的模型猜测
- 重复工具日志

## 9. 与现有代码的映射

建议保留：

- `IntelligentAssistantService.chat()` 作为执行核心
- `PlannedAnalysisService.analyze()` 作为深度分析执行核心
- `assistant_user_profiles` 作为轻量画像缓存

建议重构：

- `save_assistant_message()` 改为按 thread 写 message 表
- `get_assistant_conversation()` 改为 thread list + thread messages
- `chat_with_assistant()` 不再直接加载用户总会话，而是加载 thread context

## 10. 分阶段实施建议

### Phase 1：多主题会话 MVP

目标：先解决“所有聊天混在一起”。

范围：

- 新增 `assistant_threads`
- 新增 `assistant_thread_messages`
- 前端增加主题列表
- chat/planned-analysis 全部基于 thread_id
- 旧接口兼容默认 thread

不做：

- OpenViking 接入
- 自动压缩
- 分支建议

### Phase 2：滚动摘要与研究面板

目标：先解决“长对话越来越脏”。

范围：

- 新增 `assistant_thread_checkpoints`
- 增加手动总结和自动总结
- 前端右侧显示研究摘要
- prompt 改成“摘要 + 最近消息”模式

### Phase 3：OpenViking Sidecar 接入

目标：让研究上下文可长期沉淀、可跨会话复用。

范围：

- 接入 OpenViking HTTP 服务
- 写入 thread summaries / resources / memories
- chat 前进行 OpenViking 检索增强
- 支持资料上传后入库检索

### Phase 4：分支研究与焦点控制

目标：解决研究发散问题。

范围：

- 主题分叉建议
- 焦点分数
- 自动识别话题漂移
- 一键拆分子主题

## 11. 最小落地建议

如果只做一个最小可用版本，建议优先级如下：

1. 先实现多主题会话。
2. 再实现滚动摘要。
3. 最后把摘要和资源接到 OpenViking。

原因：

- 多主题会话先解决结构问题。
- 滚动摘要再解决上下文污染问题。
- OpenViking 最后接入，风险最小，收益最明确。

## 12. 预期收益

- 助手从短对话工具升级为长期研究助手。
- 单个研究主题可持续数天甚至数周，而不会越聊越乱。
- 用户的研究偏好和结论可以跨主题复用。
- 分析链路更适合股票投研场景的发散式探索。
- 为后续报告沉淀、投研知识库、研究协作打下基础。
