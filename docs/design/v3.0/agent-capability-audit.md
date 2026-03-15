# TradingAgents-CN v3.0 流程 Agent 能力审计

## 📋 文档信息

| 项目 | 内容 |
|------|------|
| 版本 | v3.0 Audit Draft |
| 状态 | 草稿 |
| 日期 | 2026-03-15 |
| 目标 | 盘点流程内 Agent 的公共能力、输入输出契约、可沉淀性与成长钩子需求，作为受控成长设计的前置依据 |
| 关联文档 | [受控成长 Agent 设计](controlled-growth-agent-design.md) |

---

## 1. 审计结论摘要

### 1.1 先说结论

现阶段不建议先重设 `BaseAgent`，建议先完成 Agent 能力审计，再做最小增量改造。

原因很直接：

1. 现有流程 Agent 架构已经具备完整的公共底座。
2. 问题不在“有没有基类”，而在“能力信息有没有被结构化声明”。
3. 受控成长需要的是能力画像、产物提取和审核等级，不是重写执行主链路。

### 1.2 本次审计看到的现状

从代码结构看，流程 Agent 已经形成了 5 层能力组织：

1. `BaseAgent`
2. `AnalystAgent` / `ManagerAgent` 等角色基类
3. `AgentMetadata` 元数据
4. `AgentFactory` / `WorkflowBuilder` 创建与注入链路
5. Workflow Template 中的真实节点编排

这意味着：

- 受控成长适合建立在现有层之上。
- 首先要做的是“声明层补全”，而不是“执行层重写”。

---

## 2. 审计范围

本次审计只覆盖“流程里真实在跑的 Agent”，不覆盖开放式智能助手对话场景。

聚焦流程：

1. 股票完整分析流程 `v2_stock_analysis`
2. ETF 分析流程 `v2_etf_analysis`
3. 交易复盘流程 `trade_review_v2`
4. 持仓分析流程 `position_analysis_v2`

主要参考代码：

- [core/agents/base.py](core/agents/base.py)
- [core/agents/analyst.py](core/agents/analyst.py)
- [core/agents/manager.py](core/agents/manager.py)
- [core/agents/factory.py](core/agents/factory.py)
- [core/agents/config.py](core/agents/config.py)
- [core/agents/universal.py](core/agents/universal.py)
- [core/workflow/builder.py](core/workflow/builder.py)
- [core/workflow/templates/v2_stock_analysis_workflow.py](core/workflow/templates/v2_stock_analysis_workflow.py)
- [core/workflow/templates/v2_etf_analysis_workflow.py](core/workflow/templates/v2_etf_analysis_workflow.py)
- [core/workflow/templates/trade_review_workflow_v2.py](core/workflow/templates/trade_review_workflow_v2.py)
- [core/workflow/templates/position_analysis_workflow_v2.py](core/workflow/templates/position_analysis_workflow_v2.py)
- [app/services/workflow_registry.py](app/services/workflow_registry.py)

---

## 3. 公共底座能力盘点

### 3.1 BaseAgent 已经具备的能力

`BaseAgent` 当前已经承担：

1. LLM 注入与初始化。
2. 动态工具加载。
3. 提示词初始化。
4. 标准化工具调用循环 `invoke_with_tools()`。
5. 工具列表加载优先级：数据库绑定 -> metadata 默认工具 -> 空。

这说明它已经是“执行基类”，不适合轻易重构。

### 3.2 AgentMetadata 已经具备的能力声明

`AgentMetadata` 当前已声明：

1. `id / name / category`
2. `inputs / outputs`
3. `tools / default_tools / max_tool_calls`
4. `requires_tools`
5. `output_field`
6. `reads_from`
7. `execution_order`

这已经是“能力声明层”的雏形。

### 3.3 AgentFactory 已经具备的能力

`AgentFactory` 当前已支持：

1. 注册类 Agent 创建。
2. 运行时 LLM / tools / memory 注入。
3. 降级到数据库驱动 `UniversalAgent`。
4. 对旧版 Agent 的兼容式依赖注入。

这意味着后续如果要扩“成长能力”，可以优先在 Factory 注入能力声明或成长配置，而不是改每个 Agent 构造过程。

### 3.4 WorkflowBuilder 已经具备的能力

`WorkflowBuilder` 当前已支持：

1. workflow/node 级工具解析。
2. 节点级 Agent 创建。
3. 根据 Agent 类型切换 quick/deep LLM。
4. 注入 node_id、workflow_id、memory。

这非常适合作为后续“流程级成长注入”的主入口。

---

## 4. 审计维度定义

为了后续做成长设计，建议所有流程 Agent 按以下维度审计：

| 维度 | 含义 |
|------|------|
| `agent_id` | Agent 唯一标识 |
| `workflow_scope` | 出现在哪些流程 |
| `role_type` | analyst / researcher / manager / trader / risk |
| `execution_mode` | 工具调用 / 纯 LLM / 汇总决策 |
| `input_contract` | 读取哪些 state 字段 |
| `output_contract` | 写入哪个字段，是否稳定结构化 |
| `tool_profile` | 默认工具、动态工具、最大调用次数 |
| `prompt_profile` | 是否支持 workflow/node 级模板覆盖 |
| `growth_value` | 更适合沉淀检查项、模式还是优化建议 |
| `review_level` | auto_pending / manual_required |

---

## 5. 流程 Agent 能力矩阵

### 5.1 股票完整分析流程 `v2_stock_analysis`

| Agent | 角色 | 执行模式 | 主要输入 | 主要输出 | 成长价值判断 | 审核级别 |
|------|------|------|------|------|------|------|
| `index_analyst_v2` | 宏观分析师 | 工具调用型分析师 | `ticker`, `analysis_date` | `index_report` | 适合沉淀“大盘检查项”与宏观上下文 | `auto_pending` |
| `sector_analyst_v2` | 板块分析师 | 工具/适配器混合 | `ticker`, `analysis_date` | `sector_report` | 适合沉淀行业对比维度和板块轮动检查项 | `auto_pending` |
| `market_analyst_v2` | 技术分析师 | 工具调用型分析师 | `ticker`, `analysis_date` | `market_analysis` 或 `market_report` | 适合沉淀技术面检查项，不适合直接沉淀结论 | `auto_pending` |
| `fundamentals_analyst_v2` | 基本面分析师 | 工具调用型分析师 | `ticker`, `analysis_date` | `fundamentals_report` | 适合沉淀估值/现金流/盈利质量检查项 | `auto_pending` |
| `news_analyst_v2` | 新闻分析师 | 工具调用型分析师 | `ticker`, `analysis_date` | `news_report` | 更适合沉淀“事件类别”，不适合沉淀短期新闻判断 | `manual_required` |
| `social_analyst_v2` | 舆情分析师 | 工具调用型分析师 | `ticker`, `analysis_date` | `sentiment_report` | 适合沉淀情绪指标使用习惯，不适合沉淀时效性结论 | `manual_required` |
| `bull_researcher_v2` | 看多研究员 | 汇总推理 | 上游分析报告 | 辩论观点 | 适合用于生成“争议点”，不适合直接入长期事实 | `manual_required` |
| `bear_researcher_v2` | 看空研究员 | 汇总推理 | 上游分析报告 | 辩论观点 | 适合用于生成“风险点清单”，不适合直接入长期事实 | `manual_required` |
| `research_manager_v2` | 研究经理 | 综合决策 | 多空观点 + 分析报告 | 投资建议 / 计划摘要 | 适合生成流程优化建议和研究卡片候选 | `manual_required` |
| `trader_v2` | 交易员 | 综合决策 | 研究经理结论 | 交易计划 | 只适合生成“计划结构经验”，不适合入长期事实 | `manual_required` |
| `risky_analyst_v2` | 激进风险分析师 | 汇总推理 | 交易计划 | 风险观点 | 适合沉淀风险视角标签，不适合直接长期化 | `manual_required` |
| `safe_analyst_v2` | 保守风险分析师 | 汇总推理 | 交易计划 | 风险观点 | 适合沉淀资本保护检查项 | `manual_required` |
| `neutral_analyst_v2` | 中性风险分析师 | 汇总推理 | 交易计划 | 风险观点 | 适合沉淀平衡类评估维度 | `manual_required` |
| `risk_manager_v2` | 风险经理 | 综合决策 | 三方风险观点 | 风险裁决 | 适合生成流程优化建议，不适合自动沉淀事实 | `manual_required` |

### 5.2 ETF 分析流程 `v2_etf_analysis`

| Agent | 角色 | 执行模式 | 主要输入 | 主要输出 | 成长价值判断 | 审核级别 |
|------|------|------|------|------|------|------|
| `etf_analyst_v2` | ETF 分析师 | 工具调用型分析师 | `ticker`, `analysis_date` | `fundamentals_report` | 适合沉淀 ETF 特有检查项，如规模/费率/跟踪误差 | `auto_pending` |
| `market_analyst_v2` | 市场分析师 | 工具调用型分析师 | `ticker`, `analysis_date` | `market_analysis` | 适合沉淀技术面检查项 | `auto_pending` |
| `news_analyst_v2` | 新闻分析师 | 工具调用型分析师 | `ticker`, `analysis_date` | `news_report` | 事件驱动信息时效性高，需谨慎沉淀 | `manual_required` |
| `research_manager_v2` | 研究经理 | 综合决策 | 三类分析报告 | 投资建议摘要 | 适合形成 ETF 流程优化建议 | `manual_required` |
| `trader_v2` | 交易员 | 综合决策 | 研究经理结论 | 交易计划 | 只适合沉淀计划结构模板 | `manual_required` |
| `safe_analyst_v2` | 保守风险分析师 | 汇总推理 | 交易计划 | 风险观点 | 适合沉淀 ETF 风险边界检查项 | `manual_required` |
| `risk_manager_v2` | 风险经理 | 综合决策 | 风险观点 | 风险裁决 | 适合生成流程优化建议 | `manual_required` |

### 5.3 交易复盘流程 `trade_review_v2`

| Agent | 角色 | 执行模式 | 主要输入 | 主要输出 | 成长价值判断 | 审核级别 |
|------|------|------|------|------|------|------|
| `timing_analyst_v2` | 时机分析师 | 工具调用型分析师 | `trade_info`, `review_id` | `timing_analysis` | 非常适合沉淀“买卖时机偏差模式” | `auto_pending` |
| `position_analyst_v2` | 仓位分析师 | 工具调用型分析师 | `trade_info`, `account_info` | `position_analysis` | 非常适合沉淀仓位管理规则与偏差模式 | `auto_pending` |
| `emotion_analyst_v2` | 情绪分析师 | 工具调用型分析师 | `trade_info`, `account_info`, 新闻/情绪数据 | `emotion_analysis` | 适合沉淀纪律偏差与情绪触发模式 | `manual_required` |
| `attribution_analyst_v2` | 归因分析师 | 工具调用型分析师 | `trade_info`, 市场快照 | `attribution_analysis` | 适合沉淀收益归因框架 | `auto_pending` |
| `review_manager_v2` | 复盘总结师 | 综合决策 | 四类复盘报告 | `review_summary` | 非常适合生成经验卡片和流程优化建议 | `manual_required` |

### 5.4 持仓分析流程 `position_analysis_v2`

| Agent | 角色 | 执行模式 | 主要输入 | 主要输出 | 成长价值判断 | 审核级别 |
|------|------|------|------|------|------|------|
| `pa_technical_v2` | 持仓技术分析师 | 工具调用型分析师 | `position_id`, `ticker` | `technical_analysis` | 适合沉淀持仓技术检查项 | `auto_pending` |
| `pa_fundamental_v2` | 持仓基本面分析师 | 工具调用型分析师 | `position_id`, `ticker` | `fundamental_analysis` | 适合沉淀持仓基本面检查项 | `auto_pending` |
| `pa_risk_v2` | 持仓风险评估师 | 工具调用型分析师 | 技术/基本面结果 + 市场数据 | `risk_analysis` | 适合沉淀止损、风控边界、仓位风险模式 | `auto_pending` |
| `pa_advisor_v2` | 持仓操作建议师 | 综合决策 | 技术/基本面/风险结果 | `action_advice` | 适合生成结构化建议模板，不适合自动长期化 | `manual_required` |

---

## 6. Agent 分组观察

### 6.1 最适合第一阶段接成长抽取的 Agent

这类 Agent 输出相对稳定、结构更清晰、风险较低：

- `index_analyst_v2`
- `sector_analyst_v2`
- `fundamentals_analyst_v2`
- `timing_analyst_v2`
- `position_analyst_v2`
- `attribution_analyst_v2`
- `pa_technical_v2`
- `pa_fundamental_v2`
- `pa_risk_v2`

这些更适合生成：

- 检查项
- 跟踪项
- 经验模式
- 风险边界候选

### 6.2 适合只做“建议生成”，不适合自动沉淀的 Agent

- `research_manager_v2`
- `trader_v2`
- `risk_manager_v2`
- `review_manager_v2`
- `bull_researcher_v2`
- `bear_researcher_v2`
- `risky_analyst_v2`
- `safe_analyst_v2`
- `neutral_analyst_v2`
- `pa_advisor_v2`

这类 Agent 更适合：

- 生成“待确认的研究卡片”
- 生成“流程优化建议”
- 生成“规则候选”

但不适合直接进入长期事实库。

### 6.3 时效性强、需要谨慎沉淀的 Agent

- `news_analyst_v2`
- `social_analyst_v2`

这类 Agent 的输出不适合直接长期化，更适合作为：

- 短期证据引用
- 事件标签
- 情绪波动背景

---

## 7. 当前缺口分析

### 7.1 已有能力

当前系统已经有：

1. 执行基类
2. 元数据层
3. Factory 注入层
4. Workflow 编排层
5. 工具绑定与模板覆盖层

### 7.2 缺失能力

为了做受控成长，当前真正缺的是：

1. Agent 成长角色声明
2. 哪些输出字段允许进入成长抽取的声明
3. 审核等级声明
4. 流程后处理层统一提取成长产物的接口约定

---

## 8. 建议的最小增量设计

### 8.1 优先扩 `AgentMetadata`

建议新增以下字段：

| 字段 | 类型 | 作用 |
|------|------|------|
| `growth_role` | `str` | `extractor` / `reviewer` / `optimizer` / `none` |
| `growth_outputs` | `List[str]` | 哪些输出字段允许进入成长抽取 |
| `memory_scope_hint` | `str` | `object_tracking` / `pattern` / `research_asset` |
| `review_level` | `str` | `auto_pending` / `manual_required` |
| `growth_source_type` | `str` | `analysis_report` / `review_report` / `manager_decision` |

### 8.2 谨慎扩 `BaseAgent`

建议只加钩子，不改核心执行主链路：

| 方法 | 用途 |
|------|------|
| `describe_capabilities()` | 返回结构化能力描述 |
| `get_growth_artifacts(result, state)` | 返回当前 Agent 适合成长抽取的产物 |
| `get_review_requirement()` | 返回审核级别 |

不建议现在改：

- `execute()` 主签名
- `invoke_with_tools()` 主流程
- LLM 初始化主路径
- Factory 创建协议

### 8.3 成长逻辑应放在 Agent 外层

建议由流程后处理层统一执行：

1. 收集各 Agent 输出
2. 根据 `AgentMetadata.growth_outputs` 选择候选字段
3. 交给 `Memory Extractor` / `Growth Suggestion Generator`
4. 落入 `pending` 审核流

而不是让每个 Agent 自己直接写长期记忆。

---

## 9. 推荐实施顺序

### Phase A: 能力审计固化

1. 以本表为基础，把所有 v2 流程 Agent 的能力声明补齐。
2. 明确哪些 Agent 元数据来自 `BUILTIN_AGENTS`，哪些来自 adapter / DB 配置。

### Phase B: 元数据最小扩展

1. 给 `AgentMetadata` 增加成长声明字段。
2. 不改 `BaseAgent.execute()`。

### Phase C: 流程后处理接成长抽取

1. 在 workflow result 后处理里读取成长声明。
2. 对低风险 Agent 先落 `pending`。
3. 对 manager / trader / risk manager 类 Agent 只生成 suggestion，不直接沉淀。

---

## 10. 结论

这次审计的核心结论是：

**流程 Agent 体系已经有基类，不缺框架；缺的是一层能被成长系统消费的能力画像。**

因此，下一步最正确的动作不是“重设基类”，而是：

1. 固化这份能力矩阵。
2. 给 `AgentMetadata` 增加最小成长声明。
3. 在流程后处理层接入成长抽取。

这条路线风险最小，也最符合你现在“先在流程里做，功能单一、边界清晰”的思路。