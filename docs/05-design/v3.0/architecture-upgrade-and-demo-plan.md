# 架构升级与 Seed-Evolving Demo 开发计划（2026-09–11）

> 日期：2026-09-10
> 开发分支：`v3.6-community`
> 上位依据：[现状与远期目标映射](../v4.0/current-state-and-vision-mapping.md) §3.3 技术升级线（泳道一）
> Demo 口径：[seed-evolving-demo-proposal.txt](../../08-blog/seed-evolving-demo-proposal.txt)（已提交官方，五环节单股研究主线）
> 关联：[v3.6.0 进度报告](./v3.6.0-progress-report.md)
> 状态：待确认后执行

---

## 1. 两条战线与总目标

1. **近期硬截止**：9/16 交付 Seed 共创小样（录屏 + 社媒 + 表单），只做架构 P0 中 Demo 直接依赖的两项，其余架构项冻结
2. **主线目标**：完成分析引擎架构升级（P0→P2 共 8 项 + 框架治理），把"用流程轮数补弱模型能力"的旧架构，转向"用模型能力重构流程"
3. **发布并行**：升级期间穿插社区版对外发布（M2 合并 → 重生成快照 → 推送公开仓）
4. CRKB 接入本期**不做**，仅保留在映射文档待办中

## 2. 现状基线（2026-09-10 代码核验）

### 2.1 火山方舟适配：已完整实现

| 能力 | 实现位置 |
|------|---------|
| volcengine / volcengine_coding provider 注册 | `app/scripts/init_providers.py` |
| OpenAI 兼容适配器 + 模型目录（doubao-seed-2-1-turbo-260628 等） | `tradingagents/llm_adapters/openai_compatible_base.py` |
| reasoning_effort 七档透传（none→max） | `tradingagents/graph/trading_graph.py` |
| DB 模型配置读写 reasoning_effort | `app/services/simple_analysis_service.py`、`app/models/config.py` |
| 前端 provider 配置、embedding、硬编码模型列表 | 前端 Settings / config_service.py |

### 2.2 架构八项的代码现状

| # | 升级项 | 核验到的现状证据 |
|---|--------|-----------------|
| A1 | 深度档位 × 推理预算 | 5 档仅映射辩论轮数（1/1、1/1、1/2、2/2、3/3，simple_analysis_service.py L642-686）；reasoning_effort 是 DB 按模型的**静态**配置，与选档脱节 |
| A2 | 裁判节点结构化输出 | `InvestDebateState.judge_decision: str`、RiskDebateState 全为 history 字符串（agent_states.py L15-52），裁判产出自由文本，response_format 通道闲置 |
| A3 | 分析师并行化 | tradingagents/ 下无 Send / 并行原语，乐观/审慎研究员串行接力 |
| A4 | Prompt Caching | 无缓存实现 |
| A5 | Evidence Pack | `AgentState(MessagesState)` 仅 sender/messages（L54-58），证据靠消息摘要接力，无结构化证据池 |
| A6 | 辩论重构 | `count` 计次截断（InvestDebateState L25），无收敛判断终止条件 |
| A7 | 框架升级 | `langgraph` 裸依赖无版本锁定、`langchain-openai>=0.1.0` 旧版 |
| A8 | 多模态 K 线 | LLM 层无 image 通道 |

**双轨现状（框架治理 G1）**：UnifiedLLMClient 仅 core/ 新模块使用（10 个文件），tradingagents/ 分析主链路仍走 ChatOpenAI / 自有适配器。

### 2.3 Demo 五环节能力盘点

| 环节 | 现状 | 差距 |
|------|------|------|
| ① 自主规划（预检查 + 动态工具清单） | 已实现 | 演练即可 |
| ② 多 Agent 研究会议 | 角色齐全、研究员串行 | **A3** |
| ③ 证据溯源报告 | 数字溯源防线已实现 | 三层溯源动效缺失（V1） |
| ④ 追问诱导编造 → 拦截重答 | 已实现 | 准备脚本问题 |
| ⑤ Skill 现场生成 | skill_generation 已实现且社区版免费 | 准备真实数据缺口素材 |

模型 ID 缺口：`doubao-seed-evolving` 全仓库仅文档提及，需注册（D1，阻塞于 B1）。

---

## 3. 架构升级任务定义

### P0（9 月内）

#### A1 深度档位 × 推理预算打通【Demo 必需】
- 5 档 → reasoning_effort 动态映射（建议：快速=minimal / 基础=low / 标准=medium / 深度=high / 全面=xhigh）
- 档位同时驱动：辩论轮数（已有）、**数据量**（工具数据窗口/分析师覆盖数，新增）、思考预算
- 改动点：`create_analysis_config` 五档分支写入 effort → config 透传 → `trading_graph.create_llm_by_provider` 读取（档位值优先，DB 静态配置降为覆盖层）；非火山/非推理模型自动跳过
- 验证：5 档各跑 1 次，日志确认实际透传值；其他 provider 回归无影响

#### A2 裁判节点结构化输出
- Research Manager / Risk Judge 输出 JSON Schema：`conclusion`（乐观/审慎/中性枚举）、`confidence`、`conclusion_level`（充分度，为修订 R6 结论降级预留）、`key_points[]`、`divergence_points[]`、`evidence_refs[]`
- response_format / with_structured_output 通道；解析失败显式重试，沿用现有术语合规枚举校验
- 前端报告按结构化字段渲染（事实-观点-规则分层的第一块地基）
- 价值：A6 收敛终止、未来市场验证裁判、事实-观点-规则分层的共同前置
- 验证：5 档抽样 schema 校验零失败；前端报告正常渲染；自由文本兜底路径有测试

#### A3 分析师并行化【Demo 必需】
- fan-out/fan-in（LangGraph Send 或 asyncio）：乐观/审慎研究员并行探索，共享数据状态
- 时间盒 1 天；失败降级：录屏走单研究员深度流，代码转 9/16 后
- 验证：日志时间戳确认并行；结论质量不低于串行基线；失败有降级开关

#### A4 Prompt Caching
- 系统提示 + 工具定义 + 稳定上下文打缓存；定时分析批量场景收益最大
- **前置核实**：方舟 Context Cache 支持情况与计费；不支持时按 provider 能力开关，不影响其他任务
- 验证：同批次第二次请求缓存命中、token 计费下降；结果与无缓存一致

### P1（10 月）

#### A5 Evidence Pack（结构化证据池）
- AgentState 增加证据池字段（source / tool / 采集日期 / payload 引用），分析师写入，裁判读全量证据而非消息摘要
- 验证：裁判结论可回链证据条目；证据池条目通过数字溯源校验

#### A6 辩论重构
- 并行简报（多空视角，预留 methodology 视角扩展点）+ 集中质证 + 基于 A2 `divergence_points` 的收敛判断终止，取代 `count` 计次截断
- 前置：A2、A5
- 验证：平均轮次下降而结论质量不降（复用 Demo 对比实验的评分口径）

### P2（10 月底–11 月）

#### A7 LangGraph / LangChain 升 1.x
- 先锁版本基线 + 全量回归，再升级；高风险项独立分支验证
- 验证：主链路、定时分析、回测、工作流生成四条链路回归通过

#### A8 多模态 K 线
- vision 模型读图做技术形态分析；A7 之后实施
- 验证：形态识别结果有图可回溯；不污染基本面结论

### 框架治理（随上述任务顺带，不搞大爆炸）

- G1：tradingagents/ 老链路 LLM 调用随节点改造逐步收敛到 UnifiedLLMClient（动哪个节点迁哪个），不单独立项

---

## 4. 排期

### 阶段一：Demo 死线周（9/10–9/16）

> **T0 勘察结论（2026-09-10 完成）**：
> - 分析师串行：`tradingagents/graph/setup.py` L289-314 以 for 循环把 selected_analysts 链成单线（analyst → tools_X 自循环 → Msg Clear → 下一 analyst）
> - 研究员串行接力：L319-334 Bull → conditional → Bear/Bull/Manager，第一轮乐观/审慎也先后执行（非并行简报）
> - 风险三角串行：Risky → Safe → Neutral → Risk Judge
> - **A3 最小改造点**：① 分析师链改 LangGraph Send fan-out（MessagesState 自带 add_messages reducer 支持并发写；难点在每个 analyst 独立的 tools 自循环与 Msg Clear 汇聚重设计）；② 研究员第一轮并行出简报（汇聚后再进入对抗辩论，对抗接力结构保留，属 A6 范畴）。Demo 优先做②（改动小、画面直接），①作争取项

| 日期 | 事项 |
|------|------|
| 9/10 | ① Demo 描述表单（已提交）；② B1 用户确认方舟 seed-evolving 模型 ID 串 + Key；③ T0 只读勘察研究员执行方式；④ **A1 开发启动** |
| 9/11 | A1 完成；D1 模型注册（拿到 B1 后约 0.5d：init 数据 + 模型目录 + 能力表 + 前端列表，模型名小写） |
| 9/12 | **A3 并行化（时间盒 1 天）**；五环节链路跑通（标的：赛力斯，主题：爆雷风险）；数据同步 + 预留明细缺口 |
| 9/12–9/14 | 对比实验：Seed-Evolving 深度档（4 档/debate=2/effort=high）vs 原模型全面档（5 档/debate=3），2–3 只股票同题；采集耗时/token/工具轮次/质量评分/拦截实录 |
| 9/13–9/15 | 视觉：V1 三层溯源动效（必做）→ V2 多 Agent 协作实时视图（复用 WebSocket，争取）→ V3 ECharts 图表（可砍）；9/13 晚 go/no-go 盘点 |
| 9/15 | 按官方录屏规范（B2）预演，全部预录不做现场实时演示 |
| 9/16 | 1 分钟录屏 + 自媒体发布 + 小样表单提交 |

### 阶段二：架构 P0 收尾 + 社区版发布（9/17–9/30）

| 工作 | 工期 | 说明 |
|------|------|------|
| A2 裁判结构化输出 | 4d | prompt 契约 + 解析重试 + 前端渲染 |
| A4 Prompt Caching | 2d | 含方舟缓存能力核实 |
| 社区版发布 | 2d | v3.6-community 合 pro-main 全量回归 → publish_community.py 重生成快照 → 四道验证 → 推送 community 公开仓；A1/A3 改造随快照进社区版；新功能回合 v3.0 |
| M4 文案清理 | 1d | dist 18 处残留 + 社区版用户手册 |
| 缓冲 | 1d | |

### 阶段三：P1（10 月国庆后）

- 第 1 周：A5 Evidence Pack（3–4d）
- 第 2–3 周：A6 辩论重构（4–5d）
- 穿插：MCP 三平台接入文档（约 0.5d，TraeWork/钉钉 DEAP/企业微信）；Demo 入选后的配合调优（视筛选结果）

### 阶段四：P2（10 月底–11 月）

- A7 框架升级（1–2 周，独立分支，风险最高）→ A8 多模态 K 线（3–5d）
- G1 随 A5–A8 节点改造持续收敛
- 完成后复盘，再定 v4.0 产品层（计划环/沉淀环）与 CRKB 是否接入

## 5. 依赖关系

```
A1 ──→ Demo 对比实验
A3 ──→ Demo 环节②画面
A2 ──→ A6（收敛终止）、市场验证裁判、事实-观点-规则分层
A5 ──→ A6
A7 ──→ A8
社区版发布：A1/A3 验证通过后随 M2 快照带出
```

## 6. 风险与对策

| 风险 | 对策 |
|------|------|
| B1 模型 ID/Key 延迟 | A1/T0 先行不阻塞；注册仅 0.5d |
| A3 改动影响主链路 | 1 天时间盒 + 降级开关，不碰辩论/风控节点 |
| A7 升级回归面大 | 独立分支 + 四链路回归清单，不与功能开发混提 |
| 方舟不支持 Context Cache | A4 按 provider 能力开关，顺延不阻塞 |
| 单人带宽 | Demo 周冻结其他架构项；9/13 go/no-go；V3 可砍、实验样本下限 2 只 |
| 模型周级迭代行为漂移 | 锁定演示用模型版本，实验期间不更换 |

## 7. 合规检查（录屏前逐条过）

- [ ] 结论仅用"乐观/审慎/中性"，无买卖指令、目标价、止损止盈
- [ ] 报告含"不构成投资建议"与"AI 生成"标识
- [ ] 数据来源仅 Tushare/AKShare 公开接口
- [ ] 追问拦截环节话术不诱导成"系统荐股"

## 8. 分支与提交约定

- 全部开发在 `v3.6-community`，按任务粒度独立提交（`feat(llm):` / `feat(graph):` / `refactor(graph):`）
- 每项任务给验证证据（日志/截图/测试结果），不合入未验证代码
- 社区版经 publish_community.py 机器生成 community orphan 快照（四道验证），不手工提交
- 新功能验证后回合 v3.0；pro-main 只在发布节点合并

## 9. 待确认输入

- [ ] **B1**：方舟控制台 doubao-seed-evolving 实际模型 ID 串 + API Key 开通情况
- [ ] **B2**：官方《KOL Demo 录屏规范》文档
- [ ] 本计划排期确认（A2/A4 放 9/17 后、P1/P2 排 10–11 月）
