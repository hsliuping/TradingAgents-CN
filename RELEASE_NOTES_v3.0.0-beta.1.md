# TradingAgentsCN Pro v3.0.0-beta.1 更新说明

发布日期：2026-03-19
版本定位：**多智能体平台化升级** — 智能助手全生命周期投资陪伴 + MCP 开放接口 + IM 接入 + AI 自动建流 + Skill 自生成

## 一、版本亮点

1. **智能助手全面升级**：从"数据教练"进化为"全能操作员"，支持 20+ 操作工具、多主题会话、用户画像记忆、RAG 金融知识检索。
2. **MCP Server 开放**：6 个标准工具通过 MCP 协议暴露，支持 API Key 认证与每日配额，可被 Claude Desktop、Cursor 等外部客户端直接调用。
3. **QQ Bot 接入**：通过 Gateway 框架接入 QQ 机器人（Webhook + WebSocket 双模式），QQ 发消息即可触发分析、收到报告推送。
4. **AI 工作流架构师**：用自然语言描述需求，AI 自动规划工作流拓扑、创建缺失 Skill、绑定工具与 Agent，一键发布。
5. **Skill 自动生成**：6 阶段管线（需求分析 → 代码生成 → 静态验证 → 沙箱运行 → 输出评估 → 迭代优化），AI 自主编写并验证新工具。
6. **智能选股**：三阶段对话式筛选（需求确认 → 策略规划 → 执行筛选），WebSocket 流式反馈，双层 fallback 保障结果可用。
7. **统一通知系统**：WebSocket 实时铃铛 + 邮件 + Webhook（飞书/钉钉/企微）+ QQ IM 推送，分析完成全渠道触达。

## 二、新增功能

### 1) 智能助手 v3.0

1. **20+ 操作工具**：分析触发（单股/批量/状态查询）、报告查询（搜索/详情/最新）、定时任务管理、自选股管理、持仓分析、交易复盘、投资计划、止盈/止损提醒。
2. **多主题会话**：支持创建多个研究主题，每个主题独立消息历史与上下文，支持手动总结生成结构化摘要。
3. **用户画像记忆**：`assistant_user_profiles` 持久化用户偏好、近期分析、关注领域，系统提示词自动注入画像信息。
4. **滑动窗口记忆**：最近 10 条对话自动截取（单条 800 字上限），平衡上下文质量与 Token 成本。
5. **RAG 金融知识检索**：`FinancialKnowledgeManager` 提供金融术语、规则、常识注入，减少幻觉。
6. **IM 格式自适应**：检测 `is_im` 标志，IM 渠道自动输出精简纯文本格式。

### 2) MCP Server（Model Context Protocol）

1. **6 个标准工具**：`analyze_stock`（阻塞/非阻塞）、`get_report`、`chat_with_assistant`、`list_workflows`、`screen_stocks`、`get_market_overview`。
2. **API Key 认证**：通过 `system_configs` 管理 MCP API Key，支持多 Key 分发。
3. **每日配额**：按用户 + 日期统计调用量，超额自动拒绝。
4. **FastMCP 框架**：基于 `fastmcp` 实现，符合 Anthropic MCP 规范。

### 3) Gateway IM 适配器

1. **QQ Bot 双模式**：Webhook（需公网 IP）和 WebSocket（无需公网 IP）两种接入方式。
2. **会话隔离**：`{user_id}:{channel_type}:{channel_id}` 复合 Key，Web 与 QQ 会话完全独立。
3. **用户身份映射**：`UserMappingManager` 支持绑定码 + TTL 验证，单用户模式下自动映射免绑定。
4. **Markdown → 纯文本**：12 项转换规则（表格竖排、标题→【】、列表→•、链接提取等），适配窄屏 IM。
5. **IM 上下文闭环**：QQ 触发分析 → ContextVar 传播 → task_params 持久化 → 完成后自动回推 QQ。

### 4) AI 工作流架构师

1. **自然语言建流**：描述分析需求，AI 规划多轮对话确认后生成工作流蓝图。
2. **ResourceCollector**：自动收集系统中现有 Agent、Tool、Skill 资源清单。
3. **SkillOrchestrator**：检测缺失能力并自动创建 External Skill，绑定到对应 Agent 节点。
4. **三层配置**：Node > Workflow > Agent 配置优先级，精细控制每个节点的工具集。
5. **UniversalAgent 兜底**：未注册的 Agent 自动从 `agent_configs` 创建 UniversalAgent 实例。
6. **完整生命周期**：start → respond → confirm → optimize → publish，含会话历史管理。

### 5) Skill 自动生成系统

1. **6 阶段管线**：需求分析（RequirementAnalyzer）→ 代码生成（CodeGenerator）→ 静态验证（StaticValidator）→ 沙箱运行（SandboxRunner）→ 输出评估（OutputEvaluator）→ 迭代控制（IterationController）。
2. **对话式需求澄清**：支持多轮对话逐步明确 Skill 功能、输入输出、边界条件。
3. **自动入库注册**：生成的 Skill 保存到 `external_skills` 集合，自动注册到 ToolRegistry。

### 6) 智能选股

1. **三阶段流程**：需求确认（confirmation）→ 策略规划（planning）→ 执行筛选（result）。
2. **工具白名单**：result 阶段仅允许 5 个筛选相关工具，防止工具滥用。
3. **planning 工具摘要注入**：向 LLM 注入可用工具文档，避免幻觉不存在的工具名。
4. **WebSocket 流式**：实时推送阶段进度、工具调用步骤、超时提示、最终结果。
5. **双层 fallback**：超时/无结果时 ①历史成功结果 → ②数据库快速粗筛，确保总有候选输出。
6. **自选股联动**：筛选结果支持一键添加到自选股分组。

### 7) 统一通知系统

1. **单一入口**：所有业务通过 `NotificationsService.create_and_publish` 发通知。
2. **三步流程**：写 MongoDB → WebSocket 推前端铃铛 → ChannelNotifier fire-and-forget 外部渠道。
3. **多渠道支持**：WebSocket（实时）、邮件（SMTP）、Webhook（飞书/钉钉/企微）、QQ IM。
4. **自动清理**：90 天过期 + 每用户最多 1000 条，写入时自动清理。
5. **事件类型过滤**：用户可按渠道配置接收哪些事件类型的通知。


### 8) Agent Workshop（能力工坊）

1. **工具注册与同步**：新工具注册时自动同步 `tool_configs`、更新 Agent 绑定关系。
2. **协作运行时**：`CollaborationRuntime` 统一 Agent 间交接与日志链路。
3. **迭代修正链路**：工坊严格暴露 LLM 错误，不做规则兜底，便于定位问题。

### 9) QMT 数据源与 ETF 支持

1. **QMT 分析模式**：运行时根据数据源配置自动切换 QMT/Tushare 工具与提示词。
2. **5 类同步任务**：股票基础、行情、历史K线、财务数据、状态检查。
3. **QMT 配置桥接**：`config_bridge.py` 统一 env 配置与运行时配置。
4. **ETF 独立工作流**：`etf_basic_info`、`etf_daily_quotes` 独立集合，具备基础分析工作流。

## 三、功能优化

### 1) 提示词架构

1. 分层提示词架构：基础角色 / 场景 / 画像 / 能力 / 任务五层语义组装。
2. 提示词注入策略服务，支持行业/个股/能力块动态注入。
3. 智能选股 planning 阶段注入完整字段文档与工作流模板。

### 2) 数据源标准层

1. 财务数据标准化：QMT、AKShare、Tushare 数据统一字段映射。
2. 数据源分组与降级链：`datasource_groupings` 配置多源优先级自动切换。

### 3) 前端体验

1. 智能助手主题侧栏：支持创建/切换/搜索主题，显示摘要与最近搜索。
2. 智能选股 WebSocket 流式 UI：实时显示筛选步骤、工具调用进度。
3. 自选股标签与分组联动：筛选结果一键归入分组。
4. 通知铃铛实时推送：WebSocket 连接，新通知即时弹出。

## 四、稳定性与修复

### 1) 代码审计修复（5 个 Bug）

1. **Agent Workshop**：修复工具注册时 `tool_configs` 同步缺失、Agent 绑定未自动更新。
2. **MCP Server**：修复 `_check_daily_quota` 中 `source` 字段查询不匹配。
3. **MCP Server**：修复 `user_id` 字符串与 ObjectId 类型不一致。
4. **AI Workflow Architect**：修复 `WorkflowPlanner._call_llm_with_json` 中 `self.resource_collector` AttributeError。
5. **WebSocket 通知**：修复 `user_id` 硬编码为 `"admin"`，改为从 JWT 动态解析，支持多用户。

### 2) 其他修复

1. 修复智能筛选历史显示与自选标签创建问题。
2. 修复 MCP 兼容与止盈工具加载问题。
3. 修复程序退出阶段的日志报错。
4. 修复安装器构建与安装路径校验。
5. 清理前端类型错误与 lint 问题，收紧 CI 校验。

## 五、新增数据库集合

v3.0 新增以下 MongoDB 集合（首次安装时自动创建）：

| 集合名 | 用途 |
|--------|------|
| `external_skills` | Skill 自动生成系统产出的外部技能 |
| `workflow_generation_sessions` | AI 工作流架构师会话记录 |
| `assistant_user_profiles` | 智能助手用户画像 |
| `assistant_threads` | 智能助手主题会话 |
| `assistant_thread_checkpoints` | 主题会话摘要快照 |
| `user_identity_mappings` | Gateway IM 用户身份映射 |
| `user_channel_configs` | 通知渠道配置 |

## 六、已知限制（beta）

1. **飞书/钉钉适配器**未实现，Gateway 当前仅支持 QQ Bot。
2. **ETF 分析**产品层成熟度弱于普通股票主流程，工具与提示词仍需完善。
3. **MCP 数据源类接入**（数据降级链扩展）为规划内容，尚未落地。
4. **分层提示词架构**部分实现，五层完整组装需后续逐项对照补全。
5. **task_progress 广播**当前发给所有 WebSocket 连接，生产环境应限定为任务所属用户。

## 七、升级建议

1. 升级后优先验证智能助手主链路：对话、工具调用、分析触发、报告查看。
2. 如需使用 MCP Server，需在系统配置中创建 MCP API Key。
3. 如需接入 QQ Bot，需配置 QQ 开放平台 AppID/Secret/Token。
4. 数据库配置文件已更新，包含 v3.0 全部新集合的预配置数据。
5. 建议在测试环境验证后再部署到生产环境。

---

**版本标签**: `v3.0.0-beta.1`
**分支**: `v3.0`
**打包方式**: Windows 安装包（NSIS）