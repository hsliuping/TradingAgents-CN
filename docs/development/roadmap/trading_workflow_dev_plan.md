# 单人交易学习平台：前端整合与迭代开发计划

> 文档版本：v1.0  
> 日期：2025-08-21  
> 适用范围：前端（Vue3 + Pinia + ElementPlus）、后端联动（API 协议）  
> 目标：把“筛选→分析→计划→模拟执行→复盘→循环”的个人交易流水线产品化，面向学习/教育场景（仅模拟盘，不接入券商）。

---

## 1. 背景与定位
- 平台定位：学习与研究，不构成投资建议（教育用途）。
- 合规基调：延时/回放行情，模拟盘执行，触发文案为“学习条件满足”，不自动代客决策。
- 当前能力：
  - 后端已生成结构化报告（decision/summary/recommendation/reports）。
  - 前端 SingleAnalysis.vue 已支持 Markdown 渲染与结果展示。

## 2. 用户工作流（One-person pipeline）
1) 股票筛选（Screening）→ 选中一批候选标的
2) 自选/候选篮（Favorites/Basket）→ 管理与分组
3) 批量分析（BatchAnalysis）→ 生成任务并进入队列
4) 队列管理（Queue）→ 跟踪进度、对完成项生成计划
5) 单股分析（SingleAnalysis）→ 阅读报告，一键生成交易计划
6) 模拟盘（Practice/Sim）→ 按计划触发条件模拟执行、持仓与权益
7) 复盘中心（Journal/Review）→ 交易日记、报表、周度复盘
8) 持续循环：保存筛选器定时运行→新命中加入候选→批量分析

## 3. 现有前端与改造入口
- views/Analysis/SingleAnalysis.vue：结果展示、Markdown 修复完成（挂载“一键生成计划”）。
- views/Analysis/BatchAnalysis.vue：批量发起分析（支持预填与回跳 Queue）。
- views/Queue：任务队列（增强完成项的“生成计划”CTA）。
- views/Favorites：自选股（支持多选→批量分析、状态徽标）。
- views/Screening：股票筛选（新增“加入候选篮/自选/批量分析”操作条）。

## 4. 端到端方案概览
- 统一入口：在 Screening/Favorites 批量选择后，底部操作条“一键批量分析/加入候选篮/加入自选”。
- 统一状态：Pinia Stores 管理“候选篮、工作流状态、计划、触发器、模拟盘、复盘”。
- 统一动作：在 Queue/SingleAnalysis 对已完成分析项，强引导“生成计划（可套模板）→启用触发器→推送到模拟盘”。

## 5. 页面级改造清单
### A. Screening（股票筛选）
- 新增：多选 + 底部操作条 [加入自选][加入候选篮][批量分析]
- 列增强：最近分析日期/摘要/置信度（缓存/后端）
- 保存筛选器：可命名与“一键运行”→ 自动加入候选篮并触发批量分析（可选）

### B. Favorites（自选股）
- 新增：分组管理与多选批量分析；“新鲜度”徽标（>7天黄，>14天红）
- 快捷 CTA：重新分析 | 生成计划 | 移至候选篮

### C. BatchAnalysis（批量分析）
- 预填：从候选篮/自选/筛选器导入股票与参数
- 提交后：显示嵌入式队列面板或跳转 Queue
- 完成项就地弹出 PlanEditor 抽屉

### D. Queue（队列管理）
- 分组：待执行/进行中/已完成/失败；来源标记（筛选器/自选/候选篮）
- 已完成项 CTA：生成计划（单个/批量套模板）、查看报告、重试失败

### E. SingleAnalysis（单股分析）
- 固定入口：“生成交易计划”按钮（模板下拉：波段/趋势/中长线）
- 侧栏：显示“同批次其他标的”快捷切换
- 生成计划后可直接：启用触发器 → 推送至模拟盘

### F. 新增视图：
- Plans 工作台：计划列表/启停/编辑，状态流转（草稿/启用/完成/取消）
- Practice（模拟盘）：持仓/订单/权益曲线，延时/回放成交
- Journal（复盘中心）：交易日记、报表、周报

## 6. Stores 设计（Pinia）
- stores/basket.ts：候选篮（跨页临时收集股票）
- stores/workflow.ts：工作流状态（collected→analyzing→ready_for_plan→planned→executing→review）
- stores/plans.ts：计划（草稿/启用/完成）
- stores/triggers.ts：触发器（价格/均线/量能/关键词）
- stores/sim.ts：模拟盘（账户、订单、持仓、权益）
- stores/journal.ts：复盘（日记、统计）

## 7. TypeScript 数据模型（前端）
```ts
type CandidateItem = { symbol: string; from?: string; lastAnalysisAt?: string; latestSummary?: string; decision?: any };

type Plan = {
  id: string; analysisId: string; symbol: string;
  direction: 'buy'|'hold'|'reduce'|'sell';
  entryRules: any[]; stopRule: any; targets: any[]; trailStop?: any;
  positionRule: { riskPct: number; basePos?: number; adjustBy?: { confidence?: number; riskScore?: number } };
  status: 'draft'|'active'|'done'|'cancelled'; notes?: string
};

type Trigger = { id: string; planId: string; type: 'price'|'ma'|'rsi'|'news'; params: any; throttle?: number; status: 'on'|'off' };

type SimOrder = { id: string; planId: string; side: 'buy'|'sell'; qty: number; price: number; filledPrice?: number; ts: number };

type Journal = { id: string; planId: string; events: any[]; pnl?: number; adherenceScore?: number };
```

## 8. API 规划（后端对齐，学习平台版）
- Plans：POST /api/plans，GET/PUT/DELETE（状态流转）
- Triggers：POST /api/triggers，GET/PUT/DELETE
- Sim（模拟盘）：POST /api/sim/orders，GET /api/sim/positions|orders|equity
- Journal：POST /api/journal，GET 报表
- Screener：POST /api/screener/run（保存的筛选器一键运行）
- 分析任务：已有 /api/analysis/single|batch|tasks|result（复用）

## 9. 字段映射（报告→计划）
- decision.action → 方向建议（buy/hold/reduce/sell）
- decision.target_price → 目标位/分批止盈建议
- decision.confidence & decision.risk_score → 仓位调节系数、止损宽度建议
- summary/recommendation → 计划说明书摘要
- reports.final_trade_decision（Markdown）→ 计划说明书正文

## 10. 验收标准（MVP）
- 从筛选到“生成计划”的总点击 ≤ 6（批量）
- Queue 完成项中 ≥ 60% 被生成计划
- 一周内 ≥ 60% 的计划进入模拟执行
- 复盘完成率 ≥ 50%，“按计划执行率”可追踪
- Markdown 报告渲染稳定，计划生成字段映射正确率 ≥ 98%

## 11. 里程碑与时间表（2–3 周）
- 第1周：
  - Screening/Favorites 增加“多选 + 操作条 + 候选篮”
  - BatchAnalysis 支持从候选篮预填；提交后串联 Queue
  - Queue 完成项加入“生成计划”CTA（单个）
- 第2周：
  - SingleAnalysis 加“一键生成计划 + 模板”
  - 新增 Plans 工作台（列表/启停/编辑）与 stores/plans.ts
  - 触发器基础版（价格/均线）与 stores/triggers.ts
- 第3周：
  - 模拟盘与复盘中心骨架（stores/sim.ts、stores/journal.ts）
  - Favorites 新鲜度提醒与“一键重新分析”
  - 保存的筛选器“一键运行”与自动化链路（可选）

## 12. 关键 UI/交互要点（示例）
- Screening 结果底部操作条：
  - [加入自选][加入候选篮][批量分析]
- Queue 卡片 CTA：
  - [查看报告][生成计划][重试]
- SingleAnalysis 结果区：
  - [生成交易计划 ▼模板] [启用触发器] [去模拟盘]

## 13. 合规与风险控制（落地）
- 全站“教育用途，不构成投资建议”常显；触发提示文案为“学习条件满足”。
- 默认不接入券商；仅模拟盘（可延时/回放），禁止“保证收益”等敏感词。
- 风险约束：单笔风险上限（默认≤1%）、单日最大回撤提示、单票集中度限制。

## 14. 任务拆解（角色）
- 前端：
  - Stores：basket/workflow/plans/triggers/sim/journal 骨架与本地持久化
  - 组件：PlanEditor、PlanCard、TriggerBuilder、Plans 工作台、Practice、Journal
  - 页面改造：Screening/Favorites/Batch/Queue/Single 集成 CTA
- 后端：
  - Plans/Triggers/Sim/Journal API 基线（可后置；首期用前端本地存储占位）
  - Screener 保存与一键运行

## 15. 依赖与工具
- 前端：marked（已用）、Pinia、ECharts（权益曲线/统计）、dayjs
- 后端：Redis Stream/定时任务（触发器）、MongoDB（计划与日志）

## 16. 指标与埋点
- 转化：筛选→计划→触发→执行→复盘 漏斗
- 纪律：止损执行率、计划偏离度
- 参与：周活跃、复盘完成率
- 去投机：高频下单占比下降、超风险限额触发率下降

---

> 附：目录与文件位置  
> docs/development/roadmap/trading_workflow_dev_plan.md  
> 如需细化为更具体的“组件 API 与接口定义”，建议新增：docs/development/api/plans_triggers_sim.md

