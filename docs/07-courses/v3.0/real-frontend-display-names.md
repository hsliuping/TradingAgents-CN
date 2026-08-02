# v3.0 课程字段名/术语核实参考

> **目的**:记录前端代码里**真实**的字段显示名/术语,作为课程修订的参考。
> **来源**:实际前端代码(`frontend/src/views/Reports/ReportDetail.vue` 等)
> **维护原则**:本文件内容必须**从代码中查到**,**禁止靠记忆/猜测**写入。

## 1. 批量分析页"分析深度"下拉项

来源: [BatchAnalysis.vue:139-158](file:///c:/TradingAgentsCN/frontend/src/views/Analysis/BatchAnalysis.vue#L139-L158)

| 档位 | 页面下拉显示名(用户看到的) |
|------|------------------|
| 1 | ⚡ **1级 - 快速分析**(2-4分钟/只) |
| 2 | 📈 **2级 - 基础分析**(4-6分钟/只) |
| 3 | 🎯 **3级 - 标准分析**(6-10分钟/只)⭐ |
| 4 | 🔍 **4级 - 深度分析**(10-15分钟/只) |
| 5 | 🏆 **5级 - 全面分析**(15-25分钟/只) |

## 2. 批量分析页"分析师团队"可勾选的角色(只有 7 个)

来源: [analysts.ts:13-59](file:///c:/TradingAgentsCN/frontend/src/constants/analysts.ts#L13-L59)

| 页面显示名 | 实际 ID | 描述 |
|---------|---------|------|
| 📈 市场分析师 | `market` | 分析个股价格走势与技术指标(均线/MACD/RSI/布林带) |
| 💰 基本面分析师 | `fundamentals` | 分析公司财务状况、业务模式和竞争优势 |
| 📰 新闻分析师 | `news` | 分析相关新闻、公告和市场事件的影响 |
| 💬 社媒分析师 | `social` | 分析社交媒体情绪、投资者心理和舆论导向 |
| 📊 大盘分析师 | `index_analyst` | 分析大盘指数走势、市场环境和系统性风险 |
| 🏭 板块分析师 | `sector_analyst` | 分析行业趋势、板块轮动和同业对比 |
| ETF分析师 | `etf` | 仅 ETF 市场时可选,分析 ETF 净值、跟踪误差和持仓结构 |

**系统默认勾选**:["市场分析师", "基本面分析师"](见 [analysts.ts:65](file:///c:/TradingAgentsCN/frontend/src/constants/analysts.ts#L65))

## 3. 报告模块的页面 Tab 名(报告里"详细研究报告"卡片)

来源: [ReportDetail.vue:286-312](file:///c:/TradingAgentsCN/frontend/src/views/Reports/ReportDetail.vue#L286-L312)

| 后端 key | 页面 Tab 显示名(带图标) |
|---------|------------------|
| `index_report` | 📊 大盘分析师 |
| `sector_report` | 🏭 板块分析师 |
| `market_report` | 📈 市场分析师 |
| `sentiment_report` | 💬 社交媒体分析师 |
| `news_report` | 📰 新闻分析师 |
| `fundamentals_report` | 💰 基本面分析师 |
| `bull_researcher` | 🐂 乐观情景研究员 |
| `bull_report` | 🐂 乐观情景研究 |
| `bear_researcher` | 🐻 审慎情景研究员 |
| `bear_report` | 🐻 审慎情景研究 |
| `research_team_decision` | 🔬 研究整合员 |
| `trader_investment_plan` | 🧩 研究整合员 |
| `risky_analyst` | ⚡ 高弹性情景分析师 |
| `risky_opinion` | ⚡ 高弹性情景研究观察 |
| `safe_analyst` | 🛡️ 防御情景分析师 |
| `safe_opinion` | 🛡️ 防御情景研究观察 |
| `neutral_analyst` | ⚖️ 基准情景分析师 |
| `neutral_opinion` | ⚖️ 基准情景研究观察 |
| `risk_management_decision` | 👔 风险评估师 |
| `risk_assessment` | ⚠️ 风险审阅 |
| `investment_plan` | 🧾 研究简报 |
| `final_trade_decision` | 🧾 综合研究结论 |
| `investment_debate_state` | 🔬 研究团队分析(旧) |
| `risk_debate_state` | ⚖️ 风险团队分析(旧) |
| `detailed_analysis` | 📄 详细分析 |

## 4. 报告内 Agent 顶部分析师列表显示名

来源: [ReportDetail.vue:235-284](file:///c:/TradingAgentsCN/frontend/src/views/Reports/ReportDetail.vue#L235-L284)

| 后端 key | 页面显示名(顶部分析师列表) |
|---------|----------------------|
| `index_analyst` / `index_analyst_v2` | 大盘分析师 |
| `sector_analyst` / `sector_analyst_v2` | 板块分析师 |
| `market_analyst` / `market_analyst_v2` / `market` / `technical` | 市场分析师 |
| `fundamentals_analyst` / `fundamentals_analyst_v2` / `fundamentals` | 基本面分析师 |
| `etf_analyst` / `etf_analyst_v2` / `etf` | ETF 分析师 |
| `news_analyst` / `news_analyst_v2` / `news` | 新闻分析师 |
| `social_analyst` / `social_analyst_v2` / `social` / `sentiment` | 社交媒体分析师 |
| `bull_researcher` / `bull_researcher_v2` / `多头研究员` | 乐观情景研究员 |
| `bear_researcher` / `bear_researcher_v2` / `空头研究员` | 审慎情景研究员 |
| `research_manager` / `research_manager_v2` | 研究经理 |
| `trader` / `trader_v2` | 研究整合员 |
| `risky_analyst` / `risky_analyst_v2` / `激进分析师` | 高弹性情景分析师 |
| `safe_analyst` / `safe_analyst_v2` / `保守分析师` | 防御情景分析师 |
| `neutral_analyst` / `neutral_analyst_v2` / `中性分析师` | 基准情景分析师 |
| `risk_manager` / `risk_manager_v2` | 风险评估师 |

**注意**:
- 报告顶部分析师列表(无图标) ≠ 报告 Tab 列表(带图标)。同样一个 Agent,顶部的标签是"市场分析师",Tab 标签是"📈 市场分析师"。
- "乐观情景研究员"和"🐂 乐观情景研究员"是**同一个 Agent 在不同位置的统一显示名**(顶部和 Tab)。

## 5. 风险评估 JSON 字段(报告里"风险审阅" Tab 渲染)

来源: [ReportDetail.vue:707-745](file:///c:/TradingAgentsCN/frontend/src/views/Reports/ReportDetail.vue#L707-L745)

| 后端 key | 页面显示标签(用户看到的) |
|---------|----------|
| `risk_level` | **风险等级** |
| `risk_score` | **风险评分** |
| `reasoning` / `conclusion` / `summary` / `assessment` | **评估结论** |
| `key_risks` (数组) | **核心风险**(以 `-` 列表渲染) |
| `risk_control` / `control` / `suggestions` | **风控建议** |
| `investment_adjustment` / `adjustment` | **投资调整建议** |

## 6. 持仓分析里的"动作标签"映射

来源: [PositionAnalysisDetailDialog.vue:235-244](file:///c:/TradingAgentsCN/frontend/src/views/Portfolio/components/PositionAnalysisDetailDialog.vue#L235-L244)

| 后端返回值 | 页面显示(用户看到的) |
|---------|---------|
| `乐观` | 乐观 |
| `审慎` | 审慎 |
| `中性` | 中性 |
v3.0 持仓研究与单股研究使用相同的 3 个决策标签(乐观/审慎/中性)，不再有"偏多/偏空/待验证"等额外标签。

## 7. 股票筛选页(Screening/index.vue)字段

### 7.1 智能筛选 Tab

- 页面标题:"股票筛选"
- 页面描述:"默认通过智能对话引导你完成选股;只有在需要精细手动配置时,再进入高级模式"
- 两个 Tab:**智能筛选** / **高级模式**(默认是"智能筛选")
- 左侧面板标题:"筛选历史"(副标题:"按会话查看之前的智能筛选记录"),带"新建"按钮
- 智能筛选确认操作按钮:"按原需求筛选" / "采纳建议后筛选" / "执行筛选方案" / "重新描述需求"

### 7.2 高级模式 Tab ——"常用条件"区(默认显示 8 个)

来源: [Screening/index.vue:267-403](file:///c:/TradingAgentsCN/frontend/src/views/Screening/index.vue#L267-L403)

| 字段标签(用户看到的) | 实际字段 | 类型 |
|---------|---------|------|
| **股票代码/名称** | `keyword` | 文本输入 |
| **行业分类** | `industry` | 多选下拉 |
| **市场类型** | `market` | 下拉(固定为 A股,disabled) |
| **市值范围** | `total_mv` | 下拉(小盘/中盘/大盘) |
| **市盈率 (PE)** | `pe` | 范围输入(最小-最大) |
| **市净率 (PB)** | `pb` | 范围输入 |
| **涨跌幅** | `pct_chg` | 范围输入 |
| **成交量** | `amount` | 下拉(活跃/正常/清淡) |

### 7.3 高级模式 Tab ——"高级字段"区(需手动添加)

来源: [Screening/index.vue:406-547](file:///c:/TradingAgentsCN/frontend/src/views/Screening/index.vue#L406-L547)

- 区域标题:"高级字段",副标题:"不常用字段不默认铺开;需要时再主动添加到过滤条件里"
- 右上标签:"可选 N 项"
- 添加字段下拉框占位符:"选择要追加的高级字段"
- 提示文字:"只显示你主动添加的字段;移除字段会同时清空对应条件"
- 空状态提示:"还没有添加高级字段。需要更细条件时,再从上方选择要补充的字段"

### 7.4 筛选结果表格列

来源: [Screening/index.vue:619-720](file:///c:/TradingAgentsCN/frontend/src/views/Screening/index.vue#L619-L720)

| 表格列(用户看到的) | 显示内容 |
|---------|----------|
| 复选框列 | 选中加入批量分析列表 |
| **股票代码** | 可点击链接,跳股票详情 |
| **股票名称** | - |
| **行业** | 行业分类 |
| **当前价格** | 格式:¥XX.XX |
| **涨跌幅** | 带正负号,如 +1.23% / -0.85% |
| **市值** | 格式:XX 亿 / XX 万亿 |

### 7.5 按钮

- 顶部:**开始筛选** / **重置条件**
- 结果区:**批量分析(N)** / **导出结果** / **重新筛选**
- 占位符:"未找到符合条件的股票"

## 8. 批量分析页(BatchAnalysis.vue)其他字段

来源: [BatchAnalysis.vue](file:///c:/TradingAgentsCN/frontend/src/views/Analysis/BatchAnalysis.vue)

- 页面标题:"批量分析",右上"高级"标签
- 风险提示:"⚠️ 重要提示:本次分析仅用于学习、研究和公开信息整理,不提供个股交易指导。"
- 描述:"AI 驱动的批量研究工作台,高效整理多只股票的研究线索"
- "股票列表"卡片(右上角标签:`N 只股票`)
  - 市场下拉选项:"🇨🇳 A股市场(6位数字)" / "📈 ETF 基金(510050、159919 等)"
  - 输入框占位符(A股):"请输入股票代码,每行一个\n支持格式:\n000001\n000002.SZ\n600036.SH"
  - 输入框占位符(ETF):"请输入ETF代码,每行一个\n支持格式:\n510050\n510300.SH\n159919.SZ"
  - 按钮:"解析股票代码" / "清空"
  - 股票预览标题:"股票预览"
  - 无效代码提示:"以下股票代码格式可能有误,请检查:"
- "分析配置"卡片(右上"批量设置"标签)
  - "分析深度"下拉(见第 1 节)
  - "分析流程"下拉:列 `workflow_type === 'stock_analysis'` 的工作流,默认选 `is_default=true` 的
  - "分析师团队"(见第 2 节)
  - 提交按钮:"开始批量分析(N只)"
- "高级配置"卡片:含 ModelConfig 组件,字段"快速分析模型"和"深度分析模型"

## 9. 通用研究分析页(GeneralAnalysis.vue)

来源: [GeneralAnalysis.vue](file:///c:/TradingAgentsCN/frontend/src/views/Analysis/GeneralAnalysis.vue)

- 页面标题:"通用研究分析",图标 Document
- 风险提示:"⚠️ 重要提示:本次分析所有结论用于学习和验证AI证券分析技术,不作为真实交易操盘指导。"
- 描述:"基于通用流程的灵活研究工作台,支持自定义分析目标与参数"
- Tab:**新分析** / **历史结果**
- 表单字段:
  - **流程选择**:"请选择通用分析流程"
  - 选中流程后显示"执行参数"分隔线,字段从 `selectedWorkflowFull.input_config.fields` 动态生成
  - 字段类型支持:string / textarea / number / boolean / date / select / multiselect
  - 字段标签使用 `field.label || field.name`(优先用 label,没有才用 name)
  - 字段描述在输入框下方显示:`field.description`
- 按钮:"开始分析" / "查看结果" / "重新分析"

## 10. Agent 名称中文显示(用于 Agent 工坊下拉等)

来源: [agentLabels.ts](file:///c:/TradingAgentsCN/frontend/src/constants/agentLabels.ts)

| 后端 key | 页面显示名(下拉) |
|---------|---------|
| `analysts_v2` | 独立分析师 v2.0 |
| `researchers_v2` | 乐观/审慎情景研究员 v2.0 |
| `debators_v2` | 风险多情景研究 v2.0 |
| `managers_v2` | 研究/风险评估师 v2.0 |
| `trader_v2` | 研究整合员 v2.0 |
| `reviewers_v2` | 复盘分析 v2.0 |
| `position_analysis_v2` | 仓位分析 v2.0 |
| `post_processors_v2` | 后处理器 v2.0 |
| `universal` | 自定义Agent |

## 11. 报告模块的展示顺序(用户在 Tab 上看到的顺序)

来源: [ReportDetail.vue:601-635](file:///c:/TradingAgentsCN/frontend/src/views/Reports/ReportDetail.vue#L601-L635)

```
第一阶段:宏观分析(2个)
  - index_report → 📊 大盘分析师
  - sector_report → 🏭 板块分析师

第二阶段:分析师团队(4个)
  - market_report → 📈 市场分析师
  - fundamentals_report → 💰 基本面分析师
  - sentiment_report → 💬 社交媒体分析师
  - news_report → 📰 新闻分析师

第三阶段:研究团队(多情景研究 + 初步研究观察)
  - bull_researcher → 🐂 乐观情景研究员
  - bull_report → 🐂 乐观情景研究
  - bear_researcher → 🐻 审慎情景研究员
  - bear_report → 🐻 审慎情景研究
  - research_team_decision → 🔬 研究整合员
  - investment_plan (与 research_team_decision 重复时隐藏)

第四阶段:交易团队
  - trader_investment_plan → 🧩 研究整合员

第五阶段:风险管理团队(风险辩论)
  - risky_analyst → ⚡ 高弹性情景分析师
  - risky_opinion → ⚡ 高弹性情景研究观察
  - safe_analyst → 🛡️ 防御情景分析师
  - safe_opinion → 🛡️ 防御情景研究观察
  - neutral_analyst → ⚖️ 基准情景分析师
  - neutral_opinion → ⚖️ 基准情景研究观察
  - risk_management_decision → 👔 风险评估师
  - risk_assessment → ⚠️ 风险审阅

第六阶段:最终研究结论
  - final_trade_decision → 🧾 综合研究结论

兼容旧字段
  - investment_debate_state → 🔬 研究团队分析(旧)
  - risk_debate_state → ⚖️ 风险团队分析(旧)
  - detailed_analysis → 📄 详细分析
```

## 12. 报告页面里用户看到的"风险提示"

来源: [ReportDetail.vue:83-93](file:///c:/TradingAgentsCN/frontend/src/views/Reports/ReportDetail.vue#L83-L93)

```
⚠️ 重要风险提示与免责声明

- 平台性质:本平台为AI辅助分析技术学习平台,专注于AI技术在证券与ETF分析领域的应用验证和技术学习。
- 分析目的:所有分析结论仅用于学习和验证AI辅助分析技术,不作为真实交易操盘指导或投资依据。
- 非投资建议:所有分析结果、评分、建议仅为技术验证参考,不构成任何买卖建议或投资决策依据。
- 数据局限性:分析基于历史数据和公开信息,可能存在延迟、不完整或不准确的情况,无法预测未来市场走势。
- 投资风险:股票与ETF投资均存在市场风险、流动性风险、政策风险等多种风险,可能导致本金损失。
- 独立决策:投资者应基于自身风险承受能力、投资目标和财务状况独立做出投资决策。
- 责任声明:使用本平台产生的任何投资决策及其后果由使用者自行承担,本平台不承担任何责任。
```

## 13. 报告页面里"研究简报"卡片

来源: [ReportDetail.vue:108-119](file:///c:/TradingAgentsCN/frontend/src/views/Reports/ReportDetail.vue#L108-L119)

- 卡片标题:**研究简报**
- 副标题图标:InfoFilled
- 内容: Markdown 渲染的 `summaryDisplayContent`

## 14. 报告页面里"详细研究报告"卡片

来源: [ReportDetail.vue:121-145](file:///c:/TradingAgentsCN/frontend/src/views/Reports/ReportDetail.vue#L121-L145)

- 卡片标题:**详细研究报告**
- 副标题图标:Files
- Tab 类型:`type="border-card"`
- Tab 标签:由 `getModuleDisplayName(moduleName)` 动态生成(参考第 3 节)

## 15. 报告中心列表(Reports/index.vue)字段

来源: [Reports/index.vue](file:///c:/TradingAgentsCN/frontend/src/views/Reports/index.vue)

| 表格列 | 页面显示名 |
|--------|----------|
| 报告标题 | `股票代码 - 股票名称` |
| 报告类型 | "分析报告" / "批量报告" |
| 格式 | "MARKDOWN" / "DOCX" / "PDF" / "JSON" |
| 状态 | "已完成" / "分析中" / "失败" |
| 分析模型 | LLM 模型名(如 "qwen-flash / qwen-max") |
| 分析深度 | "深度: 5" / "深度: 3" |
| 创建时间 | YYYY-MM-DD HH:mm |

## 16. 报告中心筛选器

- 搜索框占位符:**"搜索股票代码或名称"**
- 市场筛选占位符:**"市场筛选"**,选项:仅 **A股**
- 日期范围占位符:**"开始日期"** / **"结束日期"**

## 17. 报告中心顶部说明文字

```
查看和管理股票分析报告,支持多种格式导出(批量导出最多 10 个)
```

## 📋 仍待核实事项

以下功能未在前端代码中找到,需要进一步核实:

- [ ] `/portfolio` 持仓页的字段显示
- [ ] `/paper` 模拟交易的字段显示
- [ ] `/review` 复盘的字段显示
- [ ] `/assistant` AI 助手的字段显示
- [ ] `/position` 持仓管理的字段显示
- [ ] `/settings/*` 各种设置页的字段显示
- [ ] `report_manifest` 在不同工作流中的具体显示差异

## ⚠️ 修订课程时的注意事项

1. **优先以"用户在页面上看到的中文标签"为准**,而不是后端字段名
2. **同一个东西在不同位置的显示已统一**(如"乐观情景研究员"在顶部和 Tab 都一致)
3. **不要用代码 key**(如 `bull_researcher`、`risk_level`)给用户看,要写"🐂 乐观情景研究员"、"风险等级"
4. **写代码引用时**用 `[BatchAnalysis.vue:139-158](file:///...)` 这种带行号的格式,方便核对
