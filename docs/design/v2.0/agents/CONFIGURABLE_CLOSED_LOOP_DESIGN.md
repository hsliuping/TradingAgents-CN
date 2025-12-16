# 可配置闭环架构设计

**日期**: 2025-12-15  
**版本**: v2.0  
**目标**: 实现从数据获取到结果处理的完全可配置闭环

---

## 🎯 核心理念

> **"整个闭环都是可配置的"** - 从数据获取、分析、决策到保存、通知，全部通过配置实现

---

## 📊 完整闭环架构

### 当前架构（部分硬编码）

```
┌─────────────────────────────────────────────────────────────┐
│                      工作流执行                              │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  ┌──────────┐   ┌──────────┐   ┌──────────┐   ┌──────────┐ │
│  │ 市场分析 │──▶│ 新闻分析 │──▶│ 研究辩论 │──▶│ 交易决策 │ │
│  │  Agent   │   │  Agent   │   │  Agent   │   │  Agent   │ │
│  └──────────┘   └──────────┘   └──────────┘   └──────────┘ │
│                                                              │
│                        ▼ 分析结果                            │
└──────────────────────────┬──────────────────────────────────┘
                           │
                           ▼
        ┌──────────────────────────────────────┐
        │      硬编码的后处理逻辑 ❌           │
        ├──────────────────────────────────────┤
        │                                       │
        │  • app/routers/workflows.py          │
        │    └─ background_tasks.add_task()    │
        │       └─ _save_analysis_report()     │
        │                                       │
        │  • app/services/*_service.py         │
        │    └─ _save_analysis_results()       │
        │    └─ email_service.send_email()     │
        │    └─ notifications_service.create() │
        │                                       │
        └───────────────────────────────────────┘
```

**问题**:
- ❌ 后处理逻辑分散在多个文件
- ❌ 无法在工作流中可视化配置
- ❌ 新增后处理功能需要修改代码
- ❌ 无法动态启用/禁用后处理步骤

---

### 目标架构（完全可配置）

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         可配置工作流                                     │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  ┌─────────────────────────────────────────────────────────────┐       │
│  │                    分析阶段 (Analysis Phase)                 │       │
│  ├─────────────────────────────────────────────────────────────┤       │
│  │  ┌──────────┐   ┌──────────┐   ┌──────────┐   ┌──────────┐ │       │
│  │  │ 市场分析 │──▶│ 新闻分析 │──▶│ 研究辩论 │──▶│ 交易决策 │ │       │
│  │  │  Agent   │   │  Agent   │   │  Agent   │   │  Agent   │ │       │
│  │  └──────────┘   └──────────┘   └──────────┘   └──────────┘ │       │
│  └─────────────────────────────────────────────────────────────┘       │
│                                                                          │
│                              ▼ 分析结果                                 │
│                                                                          │
│  ┌─────────────────────────────────────────────────────────────┐       │
│  │                 后处理阶段 (Post-Processing Phase) ✅        │       │
│  ├─────────────────────────────────────────────────────────────┤       │
│  │                                                              │       │
│  │  ┌──────────────┐   ┌──────────────┐   ┌──────────────┐   │       │
│  │  │ 报告保存     │   │ 邮件通知     │   │ Webhook触发  │   │       │
│  │  │ Agent        │   │ Agent        │   │ Agent        │   │       │
│  │  ├──────────────┤   ├──────────────┤   ├──────────────┤   │       │
│  │  │• MongoDB     │   │• 用户邮箱    │   │• 外部API     │   │       │
│  │  │• 文件系统    │   │• 管理员邮箱  │   │• 钉钉/微信   │   │       │
│  │  │• S3/OSS      │   │• 条件过滤    │   │• Slack       │   │       │
│  │  └──────────────┘   └──────────────┘   └──────────────┘   │       │
│  │                                                              │       │
│  │  ┌──────────────┐   ┌──────────────┐   ┌──────────────┐   │       │
│  │  │ 系统通知     │   │ PDF生成      │   │ 缓存更新     │   │       │
│  │  │ Agent        │   │ Agent        │   │ Agent        │   │       │
│  │  └──────────────┘   └──────────────┘   └──────────────┘   │       │
│  │                                                              │       │
│  └─────────────────────────────────────────────────────────────┘       │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

**优势**:
- ✅ 所有后处理步骤都是Agent
- ✅ 在工作流编辑器中可视化配置
- ✅ 拖拽添加/删除后处理步骤
- ✅ 配置执行条件和顺序
- ✅ 新增功能无需修改代码

---

## 🔧 5种Agent模式总结

| 模式 | 代表Agent | 主要工作 | 是否调用工具 | 是否调用LLM | 输入 | 输出 |
|------|----------|---------|------------|------------|------|------|
| **A. 分析师** | MarketAnalyst<br>NewsAnalyst | 调用工具获取数据<br>LLM分析数据 | ✅ 是 | ✅ 是 | ticker, date | {type}_report |
| **B. 研究员** | BullResearcher<br>BearResearcher | 读取多个报告<br>LLM综合研判 | ❌ 否 | ✅ 是 | 多个报告 | 观点报告 |
| **C. 管理者** | ResearchManager<br>RiskManager | 主持辩论<br>LLM综合决策 | ❌ 否 | ✅ 是 | 多个观点 | 决策/计划 |
| **D. 交易员** | Trader | 读取决策<br>LLM生成指令 | ❌ 否 | ✅ 是 | 投资计划 | 交易指令 |
| **E. 后处理** | ReportSaver<br>EmailNotifier | 执行外部操作<br>可选LLM摘要 | ❌ 否 | 🔶 可选 | 分析结果 | 执行状态 |

---

## 💡 后处理Agent详细设计

### 1. ReportSaverAgent (报告保存Agent)

**功能**: 将分析报告保存到多个目标

**配置示例**:
```yaml
report_saver:
  enabled: true
  
  targets:
    - type: mongodb
      collection: analysis_reports
      enabled: true
      
    - type: file
      path: "data/reports/{ticker}_{date}.json"
      format: json
      enabled: true
      
    - type: s3
      bucket: "trading-reports"
      key: "reports/{ticker}/{date}.json"
      enabled: false
  
  conditions:
    - field: success
      operator: equals
      value: true
```

**替代的硬编码代码**:
- `app/routers/workflows.py::_save_analysis_report()`
- `app/services/simple_analysis_service.py::_save_analysis_results_complete()`
- `app/services/unified_analysis_service.py::_save_analysis_result()`

---

### 2. EmailNotifierAgent (邮件通知Agent)

**功能**: 根据条件发送邮件通知

**配置示例**:
```yaml
email_notifier:
  enabled: true
  
  # 收件人配置
  recipients:
    - type: user
      email: "{user.email}"
    - type: admin
      email: "admin@example.com"
      only_on_error: true
  
  # 邮件模板
  template: analysis_complete
  subject: "{ticker} 分析完成 - {recommendation}"
  
  # LLM摘要（可选）
  use_llm_summary: true
  llm_prompt: "请用3句话总结核心观点"
  
  # 附件
  attachments:
    - type: pdf
      source: state["pdf_report"]
      enabled: false
  
  # 发送条件
  conditions:
    - field: user.email_settings.enabled
      operator: equals
      value: true
    - field: recommendation
      operator: in
      value: ["买入", "卖出"]
```

**替代的硬编码代码**:
- `app/services/simple_analysis_service.py::send_analysis_email()`
- `app/worker/watchlist_analysis_task.py::send_completion_notification()`

---

### 3. SystemNotifierAgent (系统通知Agent)

**功能**: 发送系统内通知

**配置示例**:
```yaml
system_notifier:
  enabled: true
  
  notification:
    type: analysis
    title: "{ticker} 分析完成"
    content: "{summary}"
    link: "/analysis/{analysis_id}"
    severity: "{severity}"
  
  conditions:
    - field: success
      operator: equals
      value: true
```

---

### 4. WebhookTriggerAgent (Webhook触发Agent)

**功能**: 触发外部Webhook

**配置示例**:
```yaml
webhook_trigger:
  enabled: true
  
  webhook:
    url: "https://api.example.com/trading-signal"
    method: POST
    headers:
      Authorization: "Bearer {api_key}"
      Content-Type: "application/json"
    
    body:
      ticker: "{ticker}"
      recommendation: "{recommendation}"
      confidence: "{confidence_score}"
      timestamp: "{timestamp}"
  
  retry:
    max_attempts: 3
    backoff: exponential
  
  conditions:
    - field: recommendation
      operator: in
      value: ["买入", "卖出"]
    - field: confidence_score
      operator: greater_than
      value: 0.8
```

---

## 🎨 Web界面配置示例

### 工作流编辑器中的后处理节点

```
┌─────────────────────────────────────────────────────────┐
│  工作流编辑器                                            │
├─────────────────────────────────────────────────────────┤
│                                                          │
│  节点面板                     画布                       │
│  ┌──────────┐         ┌──────────┐                     │
│  │ 分析师   │         │ 市场分析 │                     │
│  │ 研究员   │         └────┬─────┘                     │
│  │ 管理者   │              │                            │
│  │ 交易员   │         ┌────▼─────┐                     │
│  ├──────────┤         │ 交易决策 │                     │
│  │后处理 ▼ │         └────┬─────┘                     │
│  ├──────────┤              │                            │
│  │📁 保存   │         ┌────┴─────┬─────────┬─────────┐ │
│  │📧 邮件   │         │          │         │         │ │
│  │🔔 通知   │    ┌────▼────┐┌───▼───┐┌───▼───┐┌───▼───┐
│  │🔗 Webhook│    │报告保存 ││邮件通知││系统通知││Webhook│
│  │📊 PDF    │    └─────────┘└───────┘└───────┘└───────┘
│  │📈 图表   │                                           │
│  └──────────┘                                           │
└─────────────────────────────────────────────────────────┘
```

---

## 📝 实现路线图

### 阶段1: 基础架构 (1周)
- [ ] 创建 `PostProcessorAgent` 基类
- [ ] 定义后处理操作接口
- [ ] 实现配置加载和验证
- [ ] 实现条件执行引擎

### 阶段2: 核心后处理Agent (2周)
- [ ] `ReportSaverAgent` - 支持MongoDB、文件、S3
- [ ] `EmailNotifierAgent` - 支持模板、条件、附件
- [ ] `SystemNotifierAgent` - 系统内通知

### 阶段3: 工作流集成 (1周)
- [ ] 工作流编辑器支持后处理节点
- [ ] 实现并行后处理执行
- [ ] 实现错误处理和重试

### 阶段4: 扩展功能 (2周)
- [ ] `WebhookTriggerAgent` - 外部API触发
- [ ] `PDFGeneratorAgent` - PDF报告生成
- [ ] `WeChatNotifierAgent` - 微信通知
- [ ] `DingTalkNotifierAgent` - 钉钉通知

### 阶段5: 迁移现有代码 (1周)
- [ ] 迁移所有硬编码的保存逻辑
- [ ] 迁移所有硬编码的通知逻辑
- [ ] 更新文档和示例

---

## ✅ 预期收益

1. **完全可配置** - 从数据到通知的完整闭环都可配置
2. **可视化管理** - 在Web界面拖拽配置后处理流程
3. **易于扩展** - 新增后处理功能只需配置，无需代码
4. **灵活组合** - 用户可自由组合后处理步骤
5. **条件执行** - 支持复杂的条件逻辑
6. **代码简化** - 消除大量硬编码的后处理逻辑

---

**下一步**: 讨论并确认设计方案，开始实现

