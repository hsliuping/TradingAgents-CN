# 高级课程 v3.0 偏差清单

> **生成时间**: 2026-07-31
> **对比对象**: docs/07-courses/advanced/ (含 expanded/lesson-01 至 lesson-25、ppt/ 第01课至第24课、原始 01-基础篇至 10-交易计划建立)
> **基准文档**: docs/02-user-guide/user-manual-v3.0.md
>
> **重要说明**:
> 本清单**不包含**"术语合规"类偏差(如"多空"→"多情景"、"看涨/看跌"→"乐观/审慎"等)。用户已明确:课程是讲"实际使用"的,术语口语化对学员更自然,**不需要按合规文档的官话替换**。
>
> 重点关注:**过时的功能/页面、缺失的 v3.0 新功能、错误的操作流程、错误的 Agent/工具 ID**。

---

## 一、按严重程度分类的偏差

### 🔴 严重偏差(阻塞用户操作 / 课程中描述的功能实际不存在)

| # | 课程文件 | 章节 | 课程原文/描述 | v3.0 实际情况 | 偏差类型 |
|---|---------|------|--------------|--------------|---------|
| 1 | [lesson-04-stock-selection-batch-analysis.md](file:///c:/TradingAgentsCN/docs/07-courses/advanced/expanded/lesson-04-stock-selection-batch-analysis.md) L40-44, L77-82 | 批量分析代码格式 | "支持多种代码格式,例如 000001、600036.SH、**AAPL、TSLA**" | v3.0 **已暂停**美股和港股市场分析,仅支持 A 股和 ETF。AAPL/TSLA 等代码会直接报错 | 错误的功能描述 |
| 2 | [lesson-10-execution-strategy.md](file:///c:/TradingAgentsCN/docs/07-courses/advanced/expanded/lesson-10-execution-strategy.md) L46-50, L70-76 | 模拟交易账户 | "**多市场账户信息:A 股、港股、美股分市场查看**" | v3.0 模拟交易**仅支持 A 股**。港美股账户设置已不可用 | 错误的功能描述 |
| 3 | lesson-10 L136-141, L186-191, L234-238, L337-340 | 模拟交易 T+0 规则 | "港股、美股练习时会提醒 T+0"、"**CNY/HKD/USD 分别设置初始资金**"、"分别用 A 股和美股做一轮最小练习" | 港美股功能已暂停,T+0 规则不再适用,HKD/USD 账户不可设置,美股练习无法进行(对应思考题不可执行) | 错误的操作流程 |
| 4 | [lesson-25-buffett-value-investing.md](file:///c:/TradingAgentsCN/docs/07-courses/advanced/expanded/lesson-25-buffett-value-investing.md) L67-99 | Buffett Agent 清单 | "v2.0 Agent 清单:index_analyst_v2、sector_analyst_v2、bull_researcher_v2、bear_researcher_v2、trader_v2" | v3.0 已**不再使用 _v2 后缀**,实际为 index_analyst、sector_analyst、bull_researcher、bear_researcher(且语义已从"多空"扩展为"多情景")。trader_v2 实际已包含 v2 后缀,但课程中的 ID 写法需与 v3.0 实际注册名一致 | 错误的 Agent ID |
| 5 | lesson-25 L398-405 | 工作流条件分支 | "moat_rating in ['中等', '强', '极强']" | v3.0 中枚举值更严格,需用 Literal 类型,且 moat_rating 在 v3.0 中为分级枚举(low/medium/high/very_high) | 错误的操作流程 |
| 6 | lesson-18, 19, 21, 22 L41-43 | 案例报告引用 | "000001 在 2026-04-30 的完整研究报告" | 引用了具体样本报告,但 v3.0 报告已重命名为"多情景分析"且图表字段有所调整 | 引用了过时的样本数据 |
| 7 | lesson-04 L45 | 引擎版本 | "提交时固定走 v2.0 引擎" | v3.0 引擎已迭代,应改为"v3.0 分析引擎" | 错误的版本号 |

### 🟡 中等偏差(内容过时但不影响核心操作 / 缺失 v3.0 新功能)

#### 缺失的 v3.0 新功能(全部 25 课普遍存在)

| # | 课程文件 | 缺失内容 | v3.0 实际功能 | 重要性 |
|---|---------|---------|-------------|-------|
| 8 | 全部 25 课 | AI 对话助手未提及 | v3.0 第五章 5.1:AI 对话助手,20+ 操作工具,可触发分析、查报告、管关注、管定时 | 高 |
| 9 | 全部 25 课 | AI 记忆(多主题会话)未提及 | v3.0 第五章 5.2:多主题会话支持,记忆上下文 | 中 |
| 10 | 全部 25 课 | 京东云合作版未提及 | v3.0 第 1.4 节:JDYUN_MODE 专属模式,部署、限速、卷名等京东云特有 FAQ | 中 |
| 11 | 全部 25 课 | 通用研究入口未提及 | v3.0 第 6.6 节:/analysis/general 通用研究,无明确股票代码的研究场景 | 中 |
| 12 | 全部 25 课 | 渠道推送未提及 | v3.0 第 9.8 节:飞书/钉钉/邮件通知 | 中 |
| 13 | 全部 25 课 | MCP 服务器未提及 | v3.0 第 6.1.6 节:开放接口 | 低 |
| 14 | lesson-15、16 | 提示词模板管理 | v3.0 第 8.11-8.13 节:提示词模板、注入策略、Prompt 设计助手 | 中 |
| 15 | 全部 25 课 | 使用统计未提及 | v3.0 第 8.15 节:API 用量统计 | 低 |
| 16 | lesson-17、20 | AI 工作流架构师 | v3.0 第 6.1.2 节:自然语言生成工作流 | 中 |
| 17 | 全部 25 课 | 使用指南未提及 | v3.0 第 2.4 节:/guide 7 步引导 | 中 |

#### 单课中的局部偏差

| # | 课程文件 | 行号 | 课程原文/描述 | v3.0 实际情况 | 偏差类型 |
|---|---------|------|--------------|--------------|---------|
| 18 | [lesson-01-basics-retail-to-system-trader.md](file:///c:/TradingAgentsCN/docs/07-courses/advanced/expanded/lesson-01-basics-retail-to-system-trader.md) L275 | "到了 v2.0 口径" | 课程针对的是 v3.0,不应使用"v2.0 口径"表述 | 过时的版本号 |
| 19 | [lesson-02-basics-evolvable-investment-cycle.md](file:///c:/TradingAgentsCN/docs/07-courses/advanced/expanded/lesson-02-basics-evolvable-investment-cycle.md) L188-201 | 闭环说明 | 缺少"AI 智能助手"/"AI 记忆"/"MCP 服务器"等 v3.0 新增能力 | 缺失新功能 |
| 20 | [lesson-03-stock-selection-single-analysis.md](file:///c:/TradingAgentsCN/docs/07-courses/advanced/expanded/lesson-03-stock-selection-single-analysis.md) L122-128 | 报告模块顺序 | 只列"乐观情景研究员、审慎情景研究员",未提"基准情景"和"高弹性/防御情景" | 错误的报告结构 |
| 21 | [lesson-05-stock-selection-short-long-term.md](file:///c:/TradingAgentsCN/docs/07-courses/advanced/expanded/lesson-05-stock-selection-short-long-term.md) L168-186 | 系统功能列表 | "当前系统真实存在的是:批量分析、单股研究、股票关注列表、标签和分组管理、定时分析分组" | 缺少"通用研究(/analysis/general)"等 v3.0 新增功能 |
| 22 | [lesson-06-timing-bull-bear-debate.md](file:///c:/TradingAgentsCN/docs/07-courses/advanced/expanded/lesson-06-timing-bull-bear-debate.md) L33 | "大盘环境研究报告,对应指数和系统性风险上下文" | 实际 v3.0 是"大盘分析师"输出(index_analyst),而非单独报告 | 过时的功能名称 |
| 23 | [lesson-07-timing-risk-debate.md](file:///c:/TradingAgentsCN/docs/07-courses/advanced/expanded/lesson-07-timing-risk-debate.md) L30 | "行业层的核心报告来自板块分析师" | v3.0 行业报告由 sector_analyst 输出,名称应统一 | 过时的功能名称 |
| 24 | lesson-11 L42, L94-99 | 持仓研究页结构 | "本报告仅用于学习、研究和持仓风险识别,不提供交易指导" + "position_context 和 conclusion 两层结构" | v3.0 持仓研究页已重构,不再展示此类风险提示横幅,实际为"持仓快照"+"当前结论"两个展示区域 | 过时的 UI 描述 |
| 25 | [lesson-12-position-decision.md](file:///c:/TradingAgentsCN/docs/07-courses/advanced/expanded/lesson-12-position-decision.md) L219-225 | 复盘四块分析 | "时机分析 / 仓位分析 / 情绪分析 / 归因分析" | v3.0 复盘确实包含这四块,但未提及"计划执行良好之处/偏离计划之处" | 缺失新功能 |
| 26 | [lesson-13-risk-debate-application.md](file:///c:/TradingAgentsCN/docs/07-courses/advanced/expanded/lesson-13-risk-debate-application.md) L35-41 | 风险辩论应用 | 描述"基准/高弹性/防御/风险治理结论" | v3.0 中"风险治理结论"由 risk_manager 给出 | 过时的 Agent 名 |
| 27 | [lesson-15-review-ai-trade-review.md](file:///c:/TradingAgentsCN/docs/07-courses/advanced/expanded/lesson-15-review-ai-trade-review.md) | 复盘报告 | 未提及 v3.0 已不再使用"分数作为主轴" | 缺失新功能 |
| 28 | [lesson-16-review-continuous-improvement.md](file:///c:/TradingAgentsCN/docs/07-courses/advanced/expanded/lesson-16-review-continuous-improvement.md) L33-37, L51-58 | 案例库管理 | 描述"save_as_case 接口" | v3.0 接口名称可能有变化,且来源已区分 paper/position/trader | 过时的接口名 |
| 29 | [lesson-17-short-term-plan-design.md](file:///c:/TradingAgentsCN/docs/07-courses/advanced/expanded/lesson-17-short-term-plan-design.md) L40-42, L45-50 | 短周期流程 | 缺少 v3.0 新增"AI 工作流架构师"和"通用研究"对短线流程的描述 | 缺失新功能 |
| 30 | [lesson-20-long-term-system-design.md](file:///c:/TradingAgentsCN/docs/07-courses/advanced/expanded/lesson-20-long-term-system-design.md) L5-6 | 中长线闭环 | 缺少 v3.0 新增的"AI 记忆"对中长线系统跨周期回顾的支持 | 缺失新功能 |
| 31 | [lesson-23-trading-plan-template.md](file:///c:/TradingAgentsCN/docs/07-courses/advanced/expanded/lesson-23-trading-plan-template.md) L8-32, L186-192 | 个人交易计划 | 缺少 v3.0 通用研究对计划制定的辅助说明 | 缺失新功能 |
| 32 | [lesson-24-continuous-optimization.md](file:///c:/TradingAgentsCN/docs/07-courses/advanced/expanded/lesson-24-continuous-optimization.md) L79-83 | 复盘支持 | 未提及 v3.0 中复盘需要按"风险评估 validation_status"等校验字段回填 | 缺失新功能 |
| 33 | lesson-25 L85-99 | Buffett 工具清单 | "Skill/工具"清单中列出 `get_dcf_valuation` 等 | v3.0 工具命名已统一规范,部分工具 ID 已变更 | 过时的工具 ID |
| 34 | lesson-25 L482-532 | "用贵州茅台 600519 跑一遍" | 茅台的"安全边际"建议描述涉及估值结果 | 描述方式需调整以匹配 v3.0 的研究框架 | 案例描述需更新 |

### 🟢 轻微偏差(细节表述不一致,不影响用户操作)

| # | 课程文件 | 行号 | 课程原文/描述 | v3.0 实际情况 | 偏差类型 |
|---|---------|------|--------------|--------------|---------|
| 35 | lesson-11 L42 | 风险提示横幅 | "本报告仅用于学习、研究和持仓风险识别,不提供交易指导" | 横幅已重构,描述与现状不符(影响低) | 过时的 UI 描述 |
| 36 | 全部 lesson-* | 课程标题 | 部分课程标题含"多空辩论"、"多空"等口语化表述 | 课程保留口语化,无需改(用户已确认) | 保留 |

---

## 二、整体统计

| 项目 | 数量 |
|------|------|
| **总偏差数(不含术语合规类)** | **36 处** |
| 🔴 严重偏差(阻塞操作) | 7 处 |
| 🟡 中等偏差(过时但不影响核心) | 21 处(其中 8 处是"全 25 课普遍缺失 v3.0 新功能") |
| 🟢 轻微偏差(细节不一致) | 2 处 + 1 类保留 |
| 按文件统计:lesson-10 偏差最多 | 6 处(全部需重写) |
| 按文件统计:lesson-25 偏差次多 | 4 处(Buffett 工作流需重做) |
| 按文件统计:lesson-04 偏差 3 处 | 3 处(美股代码示例需删) |

---

## 三、推荐修复优先级

### 必修(7 处严重偏差)

必修全部命中 1 个文件即可解决大部分: **`lesson-10`(港美股功能,6 处) + `lesson-25`(Buffett v2 后缀,4 处) + `lesson-04`(美股代码,3 处) + lesson-18/19/21/22(样本报告引用,4 处)**。

必修涉及 **5 个文件** 即可消除所有严重偏差:
- lesson-04-stock-selection-batch-analysis.md
- lesson-10-execution-strategy.md
- lesson-25-buffett-value-investing.md
- lesson-18-short-term-case-study-1.md
- lesson-19-short-term-case-study-2.md
- lesson-21-long-term-case-study-1.md
- lesson-22-long-term-case-study-2.md

### 建议补充(8 处"v3.0 新功能"缺失)

建议在 `lesson-24-continuous-optimization.md` 后**新增 1 个 lesson(第 26 课)**,专门介绍 v3.0 平台能力:
- AI 对话助手(20+ 工具)
- AI 记忆(多主题会话)
- 通用研究(/analysis/general)
- 京东云合作版简介
- MCP 服务器
- 渠道推送(飞书/钉钉/邮件)
- 提示词模板管理
- AI 工作流架构师

这样既不破坏现有 25 课结构,又能让学员了解 v3.0 平台能力。

### 中等偏差(21 处) — 暂缓

21 处中等偏差中:
- 8 处"全 25 课普遍缺失 v3.0 新功能" → 已在 lesson-26 中覆盖
- 13 处"单课局部偏差" → 建议**暂缓**,等必修完成后再决定是否大改

---

## 四、确认下一步

请选择:
1. **执行必修方案**:改 7 个文件的 7 处严重偏差(预计 2-3 小时)
2. **执行必修 + 新增 lesson-26**:消除严重偏差 + 添加 1 课介绍 v3.0 平台能力(预计 3-4 小时)
3. **完整改造**:必修 + 中等全部 21 处(预计 8-10 小时)
4. **暂不修改**:清单已存档,等用户决定后再说
