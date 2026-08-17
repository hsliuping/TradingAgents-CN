# TradingAgents-CN v3.0 真实功能清单

> **核实时间**: 2026-07-31
> **核实方法**: 直接读代码 + 查 MongoDB 样本 + 查前端路由 + 查侧边栏菜单
> **目的**: 为 [v3.0 课程](../README.md) 改写提供"对照表",确保每个功能描述都有据可查

## ⚠️ 重要声明

本文档与项目记忆可能存在差异。**以代码为准**。

例如:项目记忆曾提到"v3.0 已暂停港美股",前端入口已实际移除(§9),但后端代码暂未清理(系历史包袱,学员不可见)。课程改写应**明确告诉用户平台仅支持 A 股和 ETF**。

---

## §1 前端 25 个顶层路由

来源: [frontend/src/router/index.ts](../../../frontend/src/router/index.ts)

| # | 路径 | 名称 | 说明 |
|---|------|------|------|
| 1 | `/dashboard` | Dashboard | 仪表板(系统首页) |
| 2 | `/guide` | Guide | 平台引导(新手入门) |
| 3 | `/learning` | Learning | 学习中心(显示 3 个子页) |
| 4 | `/analysis/single` | SingleAnalysis | 单股研究 |
| 5 | `/analysis/batch` | BatchAnalysis | 批量研究 |
| 6 | `/analysis/general` | GeneralAnalysis | 通用研究(无明确股票) |
| 7 | `/screening` | StockScreening | 股票筛选 |
| 8 | `/favorites` | Favorites | 关注列表 |
| 9 | `/assistant` | Assistant | AI 智能助手(对话式) |
| 10 | `/memory` | Memory | AI 记忆管理(多主题会话) |
| 11 | `/reports` | Reports | 报告中心(报告查看、详情、Token 统计) |
| 12 | `/workflow` | Workflow | 工作流(5 个子菜单,见 §2) |
| 13 | `/tasks/unified` | UnifiedTaskCenter | 任务中心(统一版) |
| 14 | `/paper` | Paper | 模拟交易 |
| 15 | `/portfolio` | Portfolio | **持仓**(注意:不叫 position) |
| 16 | `/review` | Review | 复盘(实际叫 trade_review) |
| 17 | `/trading-system` | TradingSystem | 交易系统(策略) |
| 18 | `/stocks/:code` | StockDetail | 股票详情页 |
| 19 | `/backtest` | Backtest | 回测(前端入口已下线) |
| 20 | `/settings` | Settings | 设置(6 个子菜单,见 §3) |
| 21 | `/debug/embedded-nanobot` | EmbeddedNanobotDebug | 调试页面(开发者向) |
| 22 | `/about` | About | 关于 |
| 23 | `/login` | Login | 登录 |
| 24 | `/paper/:name.md` | PaperMdRedirect | 论文跳转 |
| 25 | `/:pathMatch(.*)*` | - | 404 兜底 |

## §2 工作流子菜单(5 个)

来源: [SidebarMenu.vue](../../../frontend/src/components/Layout/SidebarMenu.vue)

| 路径 | 名称 | 说明 |
|------|------|------|
| `/workflow` | 工作流首页 | 可视化编排工作流 |
| `/workflow/tools` | 工具管理 | 工具增删改 |
| `/workflow/agent-workshop` | Agent 工坊 | 创建自定义 Agent |
| `/workflow/skills` | Skill 中心 | 创建/管理 Skill |
| `/workflow/mcp-servers` | MCP 服务器 | 外部工具服务器 |

## §3 设置子菜单(11 个)

| 路径 | 名称 | 说明 |
|------|------|------|
| `/settings` | 通用设置 | 基础配置 |
| `/settings?tab=appearance` | 外观设置 | 主题/布局 |
| `/settings?tab=analysis` | 分析偏好 | 个人分析默认参数 |
| `/settings?tab=notifications` | 通知设置 | 通知方式 |
| `/settings?tab=security` | 安全设置 | 密码/2FA |
| `/settings?tab=assistant` | 助理设置 | AI 助手配置 |
| `/settings/email` | 邮箱配置 | SMTP 设置 |
| `/settings/channel-configs` | 渠道推送 | 飞书/钉钉/邮件/Webhook |
| `/settings/watchlist-groups` | 关注分组 | 关注列表分组管理 |
| `/settings/scheduled-analysis` | 定时分析 | 定时任务配置 |
| `/settings/license` | 授权(标准版) | License 激活(京东云版隐藏) |
| `/settings/jdyun-config` | 京东云配置 | 京东云版专用 |
| `/settings/config` | 配置管理(标准版) | LLM/数据源/系统设置 |
| `/settings/cache` | 缓存管理 | 缓存清理 |
| `/settings/templates` | 报告模板 | 模板管理 |
| `/settings/prompt-policies` | 提示词策略 | 防注入 |
| `/settings/prompt-design` | 提示词设计 | 自定义提示词 |
| `/settings/analysis-profiles` | 分析画像 | 行业/股票画像 |
| `/settings/database` | 数据库管理 | MongoDB 管理 |
| `/settings/logs` | 操作日志 | 用户操作日志 |
| `/settings/system-logs` | 系统日志 | 系统级日志 |
| `/settings/sync` | 多数据源同步 | Tushare/AKShare/BaoStock 同步 |
| `/settings/capability-index` | 工具能力索引 | 工具元数据 |
| `/settings/scheduler` | 定时任务 | 系统级定时任务 |
| `/settings/social-media` | 社媒消息管理 | 飞书/钉钉消息模板 |
| `/settings/data-import` | 数据导入 | 历史数据导入 |
| `/settings/usage` | 使用统计 | Token 用量 |
| `/settings/update` | 系统更新 | 系统升级 |

## §4 后端 78 个 APIRouter 路由模块

来源: [app/routers/](../../../app/routers/)

按功能分类(不完整列举):

| 前缀 | 模块 | 关键端点 |
|------|------|---------|
| `/api/agent-workshop` | agent_workshop.py | sessions/start, sessions/respond, build-version, versions/publish, prompt |
| `/api/akshare-init` | akshare_init.py | status, start-full, start-basic-sync |
| `/api/analysis-profiles` | analysis_profiles.py | industries, stocks |
| (无 prefix) | analysis.py | single, batch, general, tasks, history, queue-status, cancel, retry |
| `/api/backtest` | backtest.py | analyze, generate, run, results, sessions, optimize, evaluate |
| `/api/baostock-init` | baostock_init.py | status, start-full, start-basic |
| `/api/cache` | cache.py | stats, cleanup, clear |
| `/api/channel-configs` | channel_configs.py | 增删改查 + test + event-types |
| `/config` | config.py | jdyun/status, gateway, llm/providers, datasource, system, settings |
| `/database` | database.py | MongoDB 管理 |
| `/api/embedded-nanobot` | embedded_nanobot.py | 嵌入式纳米机器人 |
| `/favorites` | favorites.py | 关注列表增删改查 |
| `/api/financial-data` | financial_data.py | 财务数据查询 |
| `/api/gateway` | gateway.py | 网关配置 |
| `/api/historical-data` | historical_data.py | 历史行情查询 |
| `/api/assistant` | intelligent_assistant.py | 智能助手对话 |
| `/api/screening/intelligent` | intelligent_screening.py | **自然语言筛选对话** |
| `/api/internal-messages` | internal_messages.py | 内部消息 |
| `/api/knowledge` | knowledge.py | 知识库 |
| `/api/license` | license.py | 授权管理 |
| `/system-logs` | logs.py | 系统日志 |
| `/api/mcp` | mcp.py | MCP 服务器 |
| `/api/memory` | memory.py | AI 记忆 |
| `/api/model-capabilities` | model_capabilities.py | 模型能力管理 |
| `/markets` | multi_market_stocks.py | 多市场股票(后端保留,前端不可见) |
| `/api/multi-period-sync` | multi_period_sync.py | 多周期数据同步 |
| `/api/sync/multi-source` | multi_source_sync.py | 多数据源同步 |
| `/api/news-data` | news_data.py | 新闻数据 |
| `/logs` | operation_logs.py | 操作日志 |
| `/paper` | paper.py | 模拟交易(A 股账户;后端代码支持三市场,前端已下线) |
| `/api/v1/prompt-design` | prompt_design.py | 提示词设计 |
| `/api/v1/prompt-policies` | prompt_injection_policies.py | 提示词防注入 |
| `/api/v1/prompt-preview` | prompt_preview.py | 提示词预览 |
| `/api/quality-metrics` | quality_metrics.py | 质量指标 |
| `/report-templates` | report_templates.py | 报告模板 |
| `/api/reports` | reports.py | 报告管理 |
| `/api/scheduler` | scheduler.py | 系统级定时 |
| (无 prefix) | scheduled_analysis.py | 用户级定时分析 |
| `/api/screening` | screening.py | 条件式筛选(老版) |
| `/api/skill-center` | skill_center.py | Skill 管理中心 |
| `/api/skill-gaps` | skill_gaps.py | Skill 缺口分析 |
| `/api/skill-generation` | skill_generation.py | Skill 自动生成 |
| `/api/skills` | skills.py | Skills CRUD |
| `/api/social-media` | social_media.py | 社媒推送 |
| `/api/stock-data` | stock_data.py | 股票数据 |
| `/api/stock-sync` | stock_sync.py | 股票数据同步 |
| `/stocks` | stocks.py | 股票基础信息(后端代码支持三市场,前端已下线) |
| `/api/sync` | sync.py | 同步任务 |
| (无 prefix) | system_config.py | 系统配置 |
| `/tags` | tags.py | 标签管理 |
| `/api/tushare-init` | tushare_init.py | Tushare 初始化 |
| `/api/v2/tasks` | unified_tasks.py | 统一任务中心 |
| `/api/system/update` | update.py | 系统更新 |
| `/api/usage` | usage_statistics.py | Token 使用统计 |
| (无 prefix) | user_template_configs.py | 用户模板配置 |
| (无 prefix) | watchlist_groups.py | 关注分组 |
| `/api/v1/workflow` | workflow_api.py | 工作流 API |
| `/api/workflow-generation` | workflow_generation.py | 工作流生成 |
| `/api/workflow-growth` | workflow_growth.py | 工作流迭代 |

## §5 单股研究报告实际结构

来源: MongoDB `analysis_reports` 集合(样本:宁德时代 300750 / 工商银行 601398)

### 顶层字段(28 个)

| 字段 | 类型 | 说明 |
|------|------|------|
| `_id` | ObjectId | 主键 |
| `analysis_id` | str | 业务 ID(格式 `<code>_<date>_<time>`) |
| `stock_symbol` | str | 股票代码(如 300750) |
| `stock_code` | str | 股票代码(同 stock_symbol) |
| `stock_name` | str | 股票名称(如 宁德时代) |
| `market_type` | str | 市场类型(A股/ETF;数据表保留港美股字段,前端已不可用) |
| `model_info` | str | 使用的模型(如 `qwen-flash/qwen-plus`) |
| `analysis_date` | date | 分析日期 |
| `timestamp` | datetime | 创建时间 |
| `status` | str | 状态(`completed`/`failed`/`running`) |
| `source` | str | 来源(`api`/`manual` 等) |
| `engine` | str | 引擎版本(`v2`) |
| `research_depth` | str | 研究深度(**字符串**,如 `标准`/`深度`/`快速`) |
| `summary` | str(长文本) | 投资摘要(最终交易决策) |
| `analysts` | list[str] | 使用的 7 个分析师 ID(见 §6) |
| `reports` | dict | 12 个子报告(见 §7) |
| `decision` | dict | 决策结构(见 §8) |
| `recommendation` | str(长文本) | 投资建议(详细版) |
| `confidence_score` | float | 信心度(0-1,如 0.76) |
| `risk_level` | str | 风险等级(`低`/`中`/`高`/`中等`) |
| `risk_score` | float | 风险评分(0-1,如 0.5) |
| `key_points` | list[str] | 关键要点(数组) |
| `execution_time` | float | 执行耗时(秒,如 525.32) |
| `tokens_used` | int | Token 用量 |
| `performance_metrics` | dict | 性能指标 |
| `user_id` | str | 用户 ID |
| `created_at` | datetime | 创建时间 |
| `updated_at` | datetime | 更新时间 |
| `task_id` | str | 关联任务 ID |

## §6 7 个内置分析师角色

来源: MongoDB `agent_configs` 集合(过滤 `is_builtin=True`)

实际报告 `analysts` 字段包含 7 个 ID:

| # | ID | 角色 | 类型 |
|---|----|------|------|
| 1 | `market_analyst` | 市场分析师 | analyst |
| 2 | `fundamentals_analyst` | 基本面分析师 | analyst |
| 3 | `bull_researcher` | 看涨研究员 | researcher |
| 4 | `bear_researcher` | 看跌研究员 | researcher |
| 5 | `risky_analyst` | 激进风险分析师 | risk |
| 6 | `safe_analyst` | 保守风险分析师 | risk |
| 7 | `neutral_analyst` | 中性风险分析师 | risk |

## §7 reports 字典 12 个子报告

| Key | 说明 |
|-----|------|
| `market_report` | 市场/技术面分析(MA/MACD/RSI/BOLL) |
| `fundamentals_report` | 基本面分析(估值/财务/行业) |
| `investment_plan` | 投资计划 |
| `trader_investment_plan` | 交易员的实操框架 |
| `final_trade_decision` | 最终交易决策 |
| `bull_researcher` | 看涨研究员报告 |
| `bear_researcher` | 看跌研究员报告 |
| `research_team_decision` | 研究团队决策 |
| `risky_analyst` | 激进风险分析 |
| `safe_analyst` | 保守风险分析 |
| `neutral_analyst` | 中性风险分析 |
| `risk_management_decision` | 风险管理决策 |

## §8 decision 字段(决策结构,已合规化)

> ⚠️ 本表为合规化后的结构(2026-08 更新)。旧的 `target_price` / `stop_loss` / "买入/卖出/持有" 等字段已移除。
> 来源: [core/agents/adapters/risk_manager_v2.py](file:///c:/TradingAgentsCN/core/agents/adapters/risk_manager_v2.py) 的 `FinalTradeDecision` / `RiskAssessmentOutput` schema。

| Key | 类型 | 说明 |
|-----|------|------|
| `action` | str | 决策标签,**只能是 `乐观` / `审慎` / `中性`**(非交易指令) |
| `confidence` | float | 信心度(0-1) |
| `price_analysis_range` | str(可选) | 价格分析区间(替代旧 `target_price`,**非目标价**) |
| `risk_reference_price` | str(可选) | 风险控制参考价位(替代旧 `stop_loss`,**非止损价**) |
| `risk_exposure_ratio` | str(可选) | 风险敞口分析 |
| `reasoning` | str | 推理过程 |
| `summary` | str | 分析摘要 |
| `risk_warning` | str | 风险提示 |

风险审阅(`risk_assessment`)另有:`risk_level`(低/中/高)、`risk_score`(0-1)、`key_risks`(数组)、`risk_control`、`investment_adjustment`(乐观/审慎/中性)。

## §9 ⚠️ 港美股功能状态:前端已下线,后端保留

**业务决策**(2026-07-31 用户确认):
- **港美股前端入口已全部移除**,用户从 UI 看不到、也无法使用
- **后端代码暂时保留**(`foreign_stock_service.py` 2402 行等),未来可能复用
- **课程应按"港美股不可用"处理**,不向学员介绍

### 前端入口核实现状(2026-07-31)

| 入口 | 港美股选项? | 说明 |
|------|---------|------|
| `/analysis/single` 单股研究 | ❌ 无 | `MarketType = 'A股' \| 'ETF'`,前端不含港美股选项 |
| `/analysis/batch` 批量研究 | ❌ 无 | 同上,`market: 'A股' as 'A股' \| 'ETF'` |
| `/screening` 筛选 | ❌ 无 | `<el-select v-model="basicFilters.market" disabled>`,只显示 A 股 |
| `/favorites` 关注列表 | ❌ 已清理 | 仅 A 股自选 |
| `/paper` 模拟交易 | ❌ 已清理 | 仅 A 股账户 |
| 侧边栏菜单 | ❌ 无相关入口 | 见 §1 路由表 |
| Dashboard 卡片 | ❌ 无相关入口 | 仅 A 股入口 |

### 后端代码保留(课程无需涉及)

- ⚠️ `multi_market_stocks.py` API 端点仍在(CN/HK/US 三市场搜索)
- ⚠️ `foreign_stock_service.py` 2402 行
- ⚠️ `paper.py` 模拟交易路由支持三市场账户
- ⚠️ `hk_sync_service.py` 港股数据同步
- ⚠️ `market_categories` 集合 `us_stocks` / `hk_stocks` 仍 `enabled=True`

**这些后端代码对学员不可见,课程不应涉及**。将来如需清理后端代码,那是另一项工程任务。

### 课程改写影响

- ❌ **lesson-10 模拟交易**:不写港美股账户(原课程中我误判要保留港美股)
- ❌ **lesson-04 多情景**:删除"5 种情景",改为讲解"2 角色辩论(乐观/审慎)+ 1 整合员"
- ❌ **lesson-03 单股研究**:示例股票用 A 股代码(如 600519/601919)
- ✅ **课程应明确告诉用户**:"平台仅支持 A 股和 ETF 基金分析"

## §10 内置 Agent 完整列表(20+)

来源: MongoDB `agent_configs` 集合

### analyst 类别(15 个)
- 市场分析师 / 市场分析师 v2
- 基本面分析师
- 新闻分析师
- 社交媒体分析师
- 行业/板块分析师
- 大盘/指数分析师
- 时机分析师
- 仓位分析师
- 情绪分析师
- 归因分析师
- 复盘总结师
- 持仓技术面分析师
- 持仓基本面分析师
- 持仓风险评估师
- 技术面分析师 v2.0
- 风险评估师 v2.0

### researcher 类别(4 个)
- 看涨研究员 / 看涨研究员 v2.0
- 看跌研究员 / 看跌研究员 v2.0

### trader 类别(3 个)
- 交易员 / 交易员 v2.0
- 持仓分析师

### risk 类别(6 个)
- 激进风险分析师 / 激进风险分析师 v2.0
- 保守风险分析师 / 保守风险分析师 v2.0
- 中性风险分析师 / 中性风险分析师 v2.0

### manager 类别(5 个)
- 风险经理
- 研究经理
- 持仓操作建议师
- 操作建议师 v2.0

### post_processor 类别(3 个)
- 报告保存器
- 邮件通知器
- 系统通知器

## §11 数据集合清单(48 个)

来源: MongoDB `db.list_collection_names()`

| 集合 | 文档数 | 说明 |
|------|--------|------|
| `users` | 1 | 用户表 |
| `user_sessions` | 0 | 会话表 |
| `user_favorites` | 3 | 用户关注列表 |
| `user_tags` | 2 | 用户标签 |
| `user_template_configs` | 48 | 用户模板配置 |
| `watchlist_groups` | 1 | 关注分组 |
| `analysis_reports` | 2 | 分析报告 |
| `analysis_tasks` | 1 | 分析任务(老版) |
| `unified_analysis_tasks` | 1 | 统一任务(新版) |
| `scheduled_analysis_configs` | 1 | 定时分析配置 |
| `paper_accounts` | 5 | 模拟账户 |
| `paper_market_rules` | 3 | 模拟市场规则 |
| `real_accounts` | 1 | 真实账户 |
| `trading_systems` | 2 | 交易系统策略 |
| `workflows` | 1 | 工作流定义 |
| `workflow_history` | 0 | 工作流执行历史 |
| `agent_configs` | 47 | Agent 配置 |
| `tool_agent_bindings` | 38 | 工具-Agent 绑定 |
| `tool_configs` | 1 | 工具配置 |
| `model_catalog` | 12 | 模型目录 |
| `llm_providers` | 11 | LLM 供应商 |
| `platform_configs` | 4 | 平台配置 |
| `system_configs` | 38 | 系统配置(复数) |
| `system_config` | 1 | 系统配置(单数) |
| `prompt_templates` | 146 | 提示词模板 |
| `stock_basic_info` | 16578 | 股票基础信息 |
| `stock_screening_view` | 16578 | 股票筛选视图 |
| `stock_daily_quotes` | 484 | 日线行情 |
| `stock_news` | 60 | 股票新闻 |
| `stock_financial_data` | 2 | 财务数据 |
| `market_quotes` | 5548 | 实时行情(A股) |
| `market_categories` | 3 | 市场分类(A/HK/US) |
| `sync_status` | 1 | 同步状态 |
| `quotes_ingestion_status` | 1 | 行情入库状态 |
| `token_usage` | 15 | Token 用量记录 |
| `notifications` | 1 | 通知 |
| `operation_logs` | 102 | 操作日志 |
| `capital_transactions` | 1 | 资金流水 |
| `datasource_groupings` | 11 | 数据源分组 |
| `smtp_config` | 1 | SMTP 邮箱配置 |
| `license_cache` | 1 | License 缓存 |
| `scheduler_metadata` | 1 | 调度元数据 |
| `system.views` | 1 | MongoDB 视图元数据 |

## §12 交易系统集合结构

来源: MongoDB `trading_systems` 集合(样本:短线趋势追踪系统 / 中线价值成长系统)

| 字段 | 类型 | 说明 |
|------|------|------|
| `name` | str | 系统名称 |
| `description` | str | 描述 |
| `style` | str | **风格**(`short_term` / `medium_term` / `long_term`) |
| `risk_profile` | str | 风险画像(`aggressive` / `balanced` / `conservative`) |
| `stock_selection` | dict(2) | 选股方法 |
| `timing` | dict(1) | 时机判断 |
| `position` | dict(3) | 仓位管理 |
| `holding` | dict(3) | 持仓管理 |
| `risk_management` | dict(2) | 风险管理 |
| `review` | dict(2) | 复盘 |
| `discipline` | dict(2) | 纪律 |
| `version` | str | 版本号 |
| `is_active` | bool | 是否激活 |

**对课程的影响**:
- ✅ 课程中"短线/中长线"区分有真实数据支持(`style` 字段)
- 实际有 3 种风格: `short_term` / `medium_term` / `long_term`(不是只有 2 种)

## §13 重点:用户能找到的所有 v3.0 新功能

通过前端路由 + 后端 API + MongoDB 集合,系统能识别出的 v3.0 新功能(对比 v2.x):

| # | 功能 | 路径/模块 | v3.0 新增? |
|---|------|----------|------------|
| 1 | **自然语言选股** | `/api/screening/intelligent/chat` | ✅ |
| 2 | **AI 智能助手(对话式)** | `/assistant` | ✅ |
| 3 | **AI 记忆(多主题会话)** | `/memory` | ✅ |
| 4 | **通用研究(无明确股票)** | `/analysis/general` | ✅ |
| 5 | **MCP 服务器** | `/api/mcp` | ✅ |
| 6 | **Agent 工坊** | `/workflow/agent-workshop` | ✅ |
| 7 | **Skill 中心** | `/api/skill-center` | ✅ |
| 8 | **Skill 自动生成** | `/api/skill-generation` | ✅ |
| 9 | **AI 工作流架构师** | `/api/workflow-generation` | ✅ |
| 10 | **多数据源同步** | `/api/sync/multi-source` | ✅ |
| 11 | **多周期同步** | `/api/multi-period-sync` | ✅ |
| 12 | **分析画像** | `/api/analysis-profiles` | ✅ |
| 13 | **报告模板** | `/report-templates` | ✅ |
| 14 | **提示词设计** | `/api/v1/prompt-design` | ✅ |
| 15 | **提示词防注入策略** | `/api/v1/prompt-policies` | ✅ |
| 16 | **统一任务中心** | `/tasks/unified` | ✅ |
| 17 | **统一报告中心** | `/reports` | ✅ |
| 18 | **Token 统计** | `/reports/token` | ✅ |
| 19 | **渠道推送(飞书/钉钉/邮件/Webhook)** | `/api/channel-configs` | ✅ |
| 20 | **止盈告警** | `/api/stop-gain-alerts`(待确认) | ✅ |
| 21 | **回测** | `/backtest` | ❌ 前端入口已下线 |
| 22 | **嵌入式纳米机器人** | `/api/embedded-nanobot` | ✅ |
| 23 | **工具能力索引** | `/api/capability-index` | ✅ |
| 24 | **系统更新** | `/api/system/update` | ✅ |
| 25 | **使用问答助手** | (右下角浮窗) | ✅ |

## §14 课程改写时需要核对的"易错点"

1. **多情景分析**: ❌ 没有"乐观/基准/审慎/高弹性/防御"5 情景。实际是 **2 角色辩论(乐观/审慎)+ 1 整合员** + **3 风险视角(高弹性/防御/基准)**,最终由风险评估师综合输出 decision(`action` ∈ {乐观/审慎/中性})
2. **置信度**: ✅ 正确存在 `confidence_score` 字段(0-1)
3. **AI 评分**: ❌ 没有"AI 综合评分 0-100"。实际是 `confidence_score` (0-1) 和 `risk_score` (0-1)
4. **风险等级**: ✅ 有 `risk_level` 字段(字符串:"低"/"中"/"高"/"中等")
5. **目标价/止损**: ❌ 已合规化移除。decision 不再有 `target_price`/`stop_loss`,改为可选的 `price_analysis_range`(价格分析区间) 和 `risk_reference_price`(风险参考价),且明确"禁止给出具体目标价或止损价"
6. **持仓分析**: ✅ 有专门的 4 个 Agent(持仓技术面/基本面/风险评估/操作建议)
7. **复盘**: ✅ 有 `/review` 路由,后端 `trade_review_service.py` 3618 行
8. **回测**: ⚠️ 后端有 `/backtest` 路由和 `/api/backtest` API 残留,但前端入口已下线,产品不提供
9. **关注列表分组**: ✅ 有 `watchlist_groups` 集合,可在 `/settings/watchlist-groups` 管理
10. **定时分析**: ✅ 有 `scheduled_analysis_configs` 集合
11. **自然语言筛选**: ✅ 有 `/api/screening/intelligent/chat` API,在 Dashboard 有入口

## §15 课程阶段与真实功能的映射

| 课程阶段 | 应使用的真实功能 |
|---------|-----------------|
| **阶段 1:发现** | 自然语言筛选(`/api/screening/intelligent/chat`) + 条件式筛选(`/screening`) + 批量分析(`/analysis/batch`) + 单股研究(`/analysis/single`) |
| **阶段 2:跟踪** | 通用研究(`/analysis/general`) + 定时分析(`/settings/scheduled-analysis`) + 关注列表(`/favorites`) + 关注分组(`/settings/watchlist-groups`) + 渠道推送(`/settings/channel-configs`) |
| **阶段 3:持仓** | 模拟交易(`/paper`) + 持仓(`/portfolio`) + 4 个持仓 Agent(技术面/基本面/风险/操作建议) |
| **阶段 4:复盘** | 复盘(`/review`) + 案例库(`trade_review_service.py`) + 归因分析师 |
| **阶段 5:短线** | 交易系统 `/trading-system` 的 `short_term` 风格 |
| **阶段 6:中长线** | 交易系统 `/trading-system` 的 `medium_term` / `long_term` 风格 |
| **阶段 7:平台扩展** | AI 工作流架构师(`/api/workflow-generation`) + Agent 工坊(`/workflow/agent-workshop`) + Skill 中心(`/workflow/skills`) + Skill 自动生成(`/api/skill-generation`) |
| **阶段 8:个人计划** | 交易系统(`/trading-system`) + AI 助手(`/assistant`) + AI 记忆(`/memory`) |

---

> **最后更新**: 2026-07-31
> **配套文档**: [v3.0 课程 README](../README.md) | [课程偏差清单](../../06-knowledge/course-v3-deviation-list-2026-07-31.md)
