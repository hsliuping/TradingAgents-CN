# Agent抽象层设计分析

**日期**: 2025-12-15  
**目的**: 分析Agent的工作模式，提取共性和特性，设计基于配置的Agent基类

---

## 📋 问题定义

### 核心问题
1. **Agents的主要工作是什么？**
2. **工作模式是什么？**
3. **实现目标是什么？**
4. **哪些是共性？哪些是特性？**

---

## 🔍 现状分析

### 1. Agent的主要工作

通过分析现有代码，Agent的主要工作可以归纳为：

#### 1.1 数据获取与处理
```python
# 示例：市场分析师
def market_analyst_node(state):
    ticker = state.get("company_of_interest")
    start_date = state.get("start_date")
    end_date = state.get("end_date")
    
    # 1. 获取公司名称
    company_name = _get_company_name(ticker, market_info)
    
    # 2. 调用工具获取数据
    # (通过LLM的tool calling机制)
```

#### 1.2 LLM推理与分析
```python
# 构建提示词
system_prompt = get_agent_prompt(
    agent_type="analyst",
    agent_name="market_analyst",
    variables={...}
)

# 调用LLM
response = llm.invoke(messages)
```

#### 1.3 生成结构化输出
```python
# 输出到state
state["market_report"] = analysis_result
state["messages"].append(AIMessage(content=analysis_result))
return state
```

### 2. Agent的工作模式

#### 模式A: 分析师模式 (Analyst Pattern)
**特点**: 调用工具 → LLM分析 → 生成报告

**代表**:
- MarketAnalyst (市场分析师)
- NewsAnalyst (新闻分析师)
- FundamentalsAnalyst (基本面分析师)
- SocialAnalyst (社交媒体分析师)
- SectorAnalyst (板块分析师)
- IndexAnalyst (大盘分析师)

**工作流程**:
```
输入(ticker, date) 
  → 调用工具获取数据 
  → LLM分析数据 
  → 生成分析报告 
  → 输出到state["{type}_report"]
```

**共性**:
- 都需要调用工具
- 都需要LLM推理
- 输出格式：`{type}_report`
- 都需要处理市场类型（A股/港股/美股）

#### 模式B: 研究员模式 (Researcher Pattern)
**特点**: 读取多个报告 → LLM综合研判 → 生成观点

**代表**:
- BullResearcher (看涨研究员)
- BearResearcher (看跌研究员)

**工作流程**:
```
输入(多个分析报告) 
  → 读取state中的各类报告 
  → LLM综合分析 
  → 生成投资观点 
  → 输出到state["bull_report"/"bear_report"]
```

**共性**:
- 不调用工具（或很少调用）
- 依赖其他Agent的输出
- 需要记忆系统（memory）
- 输出格式：观点报告

#### 模式C: 管理者模式 (Manager Pattern)
**特点**: 主持辩论/决策 → 综合多方意见 → 形成最终决策

**代表**:
- ResearchManager (研究经理)
- RiskManager (风险经理)

**工作流程**:
```
输入(多个观点报告) 
  → 主持辩论 
  → LLM综合研判 
  → 生成最终决策 
  → 输出到state["investment_plan"/"risk_assessment"]
```

**共性**:
- 不调用工具
- 依赖多个Agent的输出
- 需要辩论状态管理
- 输出格式：决策/计划

#### 模式D: 交易员模式 (Trader Pattern)
**特点**: 读取决策 → 生成具体交易指令

**代表**:
- Trader (交易员)

**工作流程**:
```
输入(投资计划) 
  → 读取所有分析报告 
  → LLM生成交易策略 
  → 输出具体交易指令 
  → 输出到state["trading_plan"]
```

**共性**:
- 不调用工具
- 依赖所有前序Agent的输出
- 需要记忆系统
- 输出格式：交易指令

---

## 🎯 共性提取

### 所有Agent的共性

| 共性维度 | 说明 | 实现方式 |
|---------|------|---------|
| **输入处理** | 从state读取输入参数 | `state.get("ticker")` |
| **LLM调用** | 使用LLM进行推理 | `llm.invoke(messages)` |
| **提示词管理** | 使用模板系统 | `get_agent_prompt()` |
| **输出写入** | 将结果写入state | `state["{type}_report"] = result` |
| **日志记录** | 记录执行过程 | `logger.info()` |
| **错误处理** | 异常捕获和降级 | `try-except` |
| **市场适配** | 处理不同市场类型 | `StockUtils.get_market_info()` |

### 按模式分类的共性

#### 分析师类Agent共性
- ✅ 需要工具调用能力
- ✅ 输入：ticker, date
- ✅ 输出：`{type}_report`
- ✅ 需要处理工具调用循环
- ✅ 需要市场类型检测

#### 研究员类Agent共性
- ✅ 需要读取多个报告
- ✅ 需要记忆系统
- ✅ 输入：多个分析报告
- ✅ 输出：观点报告
- ✅ 需要辩论状态管理

#### 管理者类Agent共性
- ✅ 需要主持辩论
- ✅ 需要综合多方意见
- ✅ 输入：多个观点报告
- ✅ 输出：决策/计划
- ✅ 需要辩论历史管理

#### 交易员类Agent共性
- ✅ 需要读取所有报告
- ✅ 需要记忆系统
- ✅ 输入：投资计划
- ✅ 输出：交易指令
- ✅ 需要历史交易记录

---

## 🔧 特性提取

### 每个Agent的特性

| Agent类型 | 特性工具 | 特性输入 | 特性输出 | 特性逻辑 |
|----------|---------|---------|---------|---------|
| **MarketAnalyst** | 市场数据工具 | ticker, start_date, end_date | market_report | 技术分析 |
| **NewsAnalyst** | 新闻工具 | ticker, trade_date | news_report | 新闻解读 |
| **FundamentalsAnalyst** | 财务数据工具 | ticker, trade_date | fundamentals_report | 财务分析 |
| **SocialAnalyst** | 社交媒体工具 | ticker, trade_date | sentiment_report | 情绪分析 |
| **SectorAnalyst** | 板块数据工具 | ticker, trade_date | sector_report | 板块分析 |
| **IndexAnalyst** | 指数数据工具 | ticker, trade_date | index_report | 大盘分析 |
| **BullResearcher** | 无 | 所有分析报告 | bull_report | 看涨论证 |
| **BearResearcher** | 无 | 所有分析报告 | bear_report | 看跌论证 |
| **ResearchManager** | 无 | bull/bear报告 | investment_plan | 综合决策 |
| **Trader** | 无 | 投资计划+所有报告 | trading_plan | 交易策略 |

---

## 💡 设计建议

### 方案：基于配置的Agent基类

#### 核心思想
**将Agent的共性抽象到基类，特性通过配置注入**

#### 设计层次

```
BaseAgent (抽象基类)
  ├── 共性功能：LLM调用、状态管理、日志、错误处理
  ├── 抽象方法：execute()
  └── 工具方法：render_prompt(), invoke_with_tools()

AnalystAgent (分析师基类) extends BaseAgent
  ├── 共性：工具调用循环、市场类型处理
  ├── 配置：default_tools, report_field
  └── 子类只需配置：提示词模板、工具列表

ResearcherAgent (研究员基类) extends BaseAgent
  ├── 共性：读取报告、记忆系统
  ├── 配置：input_reports, output_field
  └── 子类只需配置：提示词模板、依赖报告

ManagerAgent (管理者基类) extends BaseAgent
  ├── 共性：辩论管理、综合决策
  ├── 配置：debate_participants, decision_field
  └── 子类只需配置：提示词模板、辩论规则

TraderAgent (交易员基类) extends BaseAgent
  ├── 共性：读取所有报告、记忆系统
  ├── 配置：input_reports, output_field
  └── 子类只需配置：提示词模板、交易规则
```

---

## 📝 下一步

1. **设计详细的基类接口**
2. **定义配置Schema**
3. **实现示例Agent**
4. **迁移现有Agent**
5. **测试和验证**

---

## 🚀 扩展：后处理Agent（Post-Processing Agents）

### 用户提出的重要问题

> "像将报告保存到数据库，发送邮件通知，这些实现现在是在代码里写死的。后面是不是可以迁移到agents当中去做呢。这样我们就完全可以实现整个闭环都是可配置的了。"

### 现状分析

#### 当前后处理逻辑的位置

**1. 报告保存到数据库** (硬编码在多个地方)
- `app/routers/workflows.py` - 工作流执行后通过 `background_tasks.add_task()` 保存
- `app/services/simple_analysis_service.py` - 分析完成后直接调用 `_save_analysis_results_complete()`
- `app/services/unified_analysis_service.py` - 分析完成后调用 `_save_analysis_result()`
- `app/worker/watchlist_analysis_task.py` - 批量分析后保存

**问题**:
- ❌ 保存逻辑分散在多个服务中
- ❌ 无法配置保存的目标（只能MongoDB）
- ❌ 无法配置保存的格式
- ❌ 无法动态启用/禁用保存

**2. 邮件通知** (硬编码在服务层)
- `app/services/simple_analysis_service.py` - 分析完成后调用 `email_service.send_analysis_email()`
- `app/worker/watchlist_analysis_task.py` - 批量分析完成后发送汇总邮件
- `app/services/email_service.py` - 邮件发送逻辑

**问题**:
- ❌ 通知逻辑硬编码在业务代码中
- ❌ 只支持邮件，无法扩展到其他通知方式（微信、钉钉、Slack等）
- ❌ 无法配置通知条件（如只在重要信号时通知）
- ❌ 无法在工作流中可视化配置

**3. 其他后处理逻辑**
- 系统内通知 (`notifications_service.create_and_publish()`)
- 进度更新 (`memory_manager.update_task_status()`)
- 缓存更新
- 性能指标记录

### 解决方案：后处理Agent模式

#### 模式E: 后处理Agent模式 (Post-Processor Pattern)

**特点**: 读取分析结果 → 执行后处理操作 → 返回执行状态

**代表**:
- **ReportSaverAgent** (报告保存Agent)
- **EmailNotifierAgent** (邮件通知Agent)
- **SystemNotifierAgent** (系统通知Agent)
- **CacheUpdaterAgent** (缓存更新Agent)
- **MetricsRecorderAgent** (指标记录Agent)
- **WebhookTriggerAgent** (Webhook触发Agent)

**工作流程**:
```
输入(分析结果)
  → 读取结果数据
  → 执行后处理操作（保存/通知/触发等）
  → 返回执行状态
  → 输出到state["post_processing_status"]
```

**共性**:
- 不调用LLM（或可选调用LLM生成摘要）
- 依赖前序Agent的输出
- 执行外部操作（数据库、邮件、API等）
- 输出格式：执行状态

**示例配置**:

```yaml
# ReportSaverAgent 配置
report_saver:
  agent_type: post_processor
  agent_name: report_saver

  # 输入配置
  inputs:
    - name: analysis_result
      type: object
      required: true
      source: state["final_result"]

  # 操作配置
  operations:
    - type: save_to_mongodb
      collection: analysis_reports
      fields:
        - analysis_id
        - stock_symbol
        - reports
        - decision
        - timestamp

    - type: save_to_file
      path: "data/reports/{ticker}_{date}.json"
      format: json

  # 条件配置
  conditions:
    - field: success
      operator: equals
      value: true

  # 输出配置
  outputs:
    - name: save_status
      type: object
      fields:
        - saved_to_mongodb: boolean
        - saved_to_file: boolean
        - file_path: string
```

```yaml
# EmailNotifierAgent 配置
email_notifier:
  agent_type: post_processor
  agent_name: email_notifier

  # 输入配置
  inputs:
    - name: analysis_result
      type: object
      required: true
    - name: user_id
      type: string
      required: true

  # 操作配置
  operations:
    - type: send_email
      template: analysis_complete
      to: "{user.email}"
      subject: "{ticker} 分析完成"

      # 可选：使用LLM生成邮件摘要
      use_llm_summary: true
      llm_prompt: "请用3句话总结这份分析报告的核心观点"

      # 附件配置
      attachments:
        - type: pdf
          source: state["pdf_report"]

  # 条件配置（只在满足条件时发送）
  conditions:
    - field: user.email_settings.enabled
      operator: equals
      value: true
    - field: recommendation
      operator: in
      value: ["买入", "卖出"]  # 只在强烈信号时通知

  # 输出配置
  outputs:
    - name: email_status
      type: object
      fields:
        - sent: boolean
        - email_id: string
        - error: string
```

### 架构优势

#### 1. 完全可配置的闭环

**工作流配置示例**:
```yaml
workflow:
  id: full_analysis_with_post_processing
  name: 完整分析工作流（含后处理）

  nodes:
    # 分析阶段
    - id: market_analyst
      type: agent
      agent_id: market_analyst_v2

    - id: news_analyst
      type: agent
      agent_id: news_analyst_v2

    - id: trader
      type: agent
      agent_id: trader_v2

    # 后处理阶段
    - id: save_report
      type: agent
      agent_id: report_saver
      config:
        save_to_mongodb: true
        save_to_file: true

    - id: send_email
      type: agent
      agent_id: email_notifier
      config:
        only_important_signals: true

    - id: trigger_webhook
      type: agent
      agent_id: webhook_trigger
      config:
        url: "https://api.example.com/trading-signal"
        method: POST

  edges:
    - source: market_analyst
      target: news_analyst
    - source: news_analyst
      target: trader

    # 后处理并行执行
    - source: trader
      target: save_report
    - source: trader
      target: send_email
    - source: trader
      target: trigger_webhook
```

#### 2. 灵活的后处理组合

用户可以在Web界面中：
- ✅ 拖拽添加后处理节点
- ✅ 配置保存目标（MongoDB、文件、S3、数据库等）
- ✅ 配置通知方式（邮件、微信、钉钉、Slack等）
- ✅ 配置触发条件（只在特定情况下执行）
- ✅ 配置执行顺序（串行/并行）

#### 3. 扩展性

**新增后处理功能只需**:
1. 创建新的PostProcessorAgent配置
2. 在工作流中添加节点
3. 无需修改任何代码

**示例扩展**:
- **WeChatNotifierAgent** - 微信通知
- **DingTalkNotifierAgent** - 钉钉通知
- **SlackNotifierAgent** - Slack通知
- **PDFGeneratorAgent** - PDF报告生成
- **ChartGeneratorAgent** - 图表生成
- **DataExporterAgent** - 数据导出（CSV、Excel等）
- **BacktestTriggerAgent** - 触发回测
- **PortfolioUpdaterAgent** - 更新投资组合

### 实现计划

#### 阶段1: 基础架构
1. 创建 `PostProcessorAgent` 基类
2. 定义后处理操作接口
3. 实现配置加载和验证

#### 阶段2: 核心后处理Agent
1. `ReportSaverAgent` - 报告保存
2. `EmailNotifierAgent` - 邮件通知
3. `SystemNotifierAgent` - 系统通知

#### 阶段3: 工作流集成
1. 在工作流编辑器中支持后处理节点
2. 实现条件执行逻辑
3. 实现并行后处理

#### 阶段4: 扩展功能
1. 更多通知方式
2. 更多保存目标
3. 更多触发器

---

**待讨论**:
- 配置格式（JSON/YAML/Python类）
- 提示词模板管理方式
- 工具绑定的灵活性
- 向后兼容性
- **后处理Agent的优先级和实现顺序**
- **是否需要LLM参与后处理（如生成邮件摘要）**

