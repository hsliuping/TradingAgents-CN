# 架构升级与 Seed-Evolving Demo 开发计划（2026-09–11）

> 日期：2026-09-10
> 开发分支：`v3.6-community`
> 上位依据：[现状与远期目标映射](../v4.0/current-state-and-vision-mapping.md) §3.3 技术升级线（泳道一）
> Demo 口径：[seed-evolving-demo-proposal.txt](../../08-blog/seed-evolving-demo-proposal.txt)（已提交官方，五环节单股研究主线）
> 关联：[v3.6.0 进度报告](./v3.6.0-progress-report.md)
> 状态：执行中（9/10：A1 旧链路完成、T0 勘察完成、实战排障 3 项；9/11：A9 方案升级为三阶段自我辩论路径；9/10 晚：**A9-P1 代码落地并通过结构验证**，赶 Demo 对比实验前）

---

## 1. 两条战线与总目标

1. **近期硬截止**：9/16 交付 Seed 共创小样（录屏 + 社媒 + 表单），只做架构 P0 中 Demo 直接依赖的两项，其余架构项冻结
2. **主线目标**：完成分析引擎架构升级（P0→P2 共 9 项 + 框架治理 + 稳定性补丁 Q1），把"用流程轮数补弱模型能力"的旧架构，转向"用模型能力重构流程"
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
| A1 | 深度档位 × 推理预算 | **旧链路已打通**（9/10 提交 c6c7dba44：`resolve_reasoning_efforts` 合并语义，20 项测试通过）；**core 工作流链路缺口**：`core/workflow/builder.py` 直读 DB 静态配置不读档位；且 5 档在主链路仅驱动辩论/风险轮数 + 记忆开关（`unified_analysis_service.py` L313-333 唯一分叉点，agent 层仅 `researcher.py:839` 消费记忆开关）——分析师集合/取数/提示词全不随档位变化，归入 A9 |
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

模型接入：`doubao-seed-evolving` 已经界面配置入 DB（9/10 诊断脚本直连验证可用），原 D1 注册任务取消。

---

## 3. 架构升级任务定义

### P0（9 月内）

#### A1 深度档位 × 推理预算打通【Demo 必需】
> **进度（9/10）**：旧 trading_graph 链路已完成（提交 c6c7dba44：`resolve_reasoning_efforts`，合并语义 = 档位默认 > DB 显式配置，仅火山 Agent Plan 注入，quick 模型降两档，非火山零影响；新增 13 项测试全部通过）。
> **剩余 A1b（core 工作流链路，9/11）**：`unified_analysis_service.py` L313-333 档位映射表补 effort 字段 → workflow config 透传 → `core/workflow/builder.py` 两处建 LLM 入口（`_create_custom_llm` / 依赖提供者）接入 `resolve_reasoning_efforts`，替换直读 DB 静态配置的写法。**Demo 对比实验（"更强模型+更少轮次"）的前置**。

- 5 档 → reasoning_effort 动态映射（快速=minimal / 基础=low / 标准=medium / 深度=high / 全面=xhigh，A1b 沿用同表，常量复用）
- 原"数据量"维度从 A1 拆出，并入 A9 真深度改造
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

#### Q1 LLM 稳定性三修复【新增 9/10，Demo 前必须】
> 实战发现（9/10 两次真实分析）：风险审阅节点异常形态直接写进报告——① 超时 363s 后裸错误 dict `{'error': 'Request timed out.', 'success': False}`；② 空响应 `{'content': '', 'success': True}`。根因：`core/agents/manager.py` `_parse_response` 对空内容也返回 success=True；报告渲染层不识别失败形态。已随排障完成的配套修复：agent 级 timeout 三层覆盖问题（代码兜底 120 移除 + 47 条种子记录统一 180）、seed-evolving max_tokens 8000→32768。

1. 空响应防线：manager 检测 `response.content` 为空 → 走失败路径并自动重试 1 次（记录 finish_reason / usage，区分瞬时异常与预算耗尽）
2. 失败不进报告：报告渲染识别 `success=False` / 空内容形态 → 该节显示"⚠️ 本节生成失败（原因），建议重新分析"；关键终局节点失败时中止后续节点
3. 适配器 finish_reason 永久日志（此类问题 5 秒定位）

- 验证：构造空响应/超时场景，报告不再出现裸 dict；重试路径有日志；trader 等后续节点不白跑

### P1（10 月）

#### A5 Evidence Pack（结构化证据池）
- AgentState 增加证据池字段（source / tool / 采集日期 / payload 引用），分析师写入，裁判读全量证据而非消息摘要
- 验证：裁判结论可回链证据条目；证据池条目通过数字溯源校验

#### A6 辩论重构
- 并行简报（多空视角，预留 methodology 视角扩展点）+ 集中质证 + 基于 A2 `divergence_points` 的收敛判断终止，取代 `count` 计次截断
- 前置：A2、A5
- 验证：平均轮次下降而结论质量不降（复用 Demo 对比实验的评分口径）
- **范围收窄（9/11，随 A9 方案升级）**：风险辩论的深度/全面档部分由 A9-P1/P2 承接（自我辩论路径）；本项聚焦投资辩论（bull/bear）与低档位风险辩论的结构优化，A9-P1 落地后重估优先级

#### A9 真深度改造（深度档自我辩论路径）【新增 9/10，方案升级 9/11】
> **问题（9/10 代码核验）**：5 档深度在 core 主链路仅改变辩论轮数 / 风险轮数 / 记忆开关三样（`unified_analysis_service.py` L313-333 为唯一分叉点，agent 层仅 `researcher.py:839` 消费记忆开关）。**分析师集合、取数、提示词全部不随档位变化**——深度档"深"不下去（对同一批材料多辩 2 轮，边际收益递减）、快速档"快"不起来、报告同质化。9/11 实战（深度档真实分析）进一步暴露：风险三角 3 agent × 2 轮 = 6 次深度模型调用串行跑约 11 分钟，是深度档耗时与超时的主要来源。
>
> **方案转向（9/11）**：原"档位全维度分层"（分析师集合/数据量/提示词逐档裁剪）改动面大且与框架治理耦合。转向**路径分治**：深度/全面档的风险辩论环节切换到 seed-evolving 单节点**自我辩论**路径——用新一代模型的原生深度思考替代"多 agent 多轮辩论"这个为弱模型时代设计的流程补丁；**低档位路径完全不动**。

**设计原则：加开关、换档位、留退路。** 新旧两条路径并存：深度/全面档经状态开关 `_risk_self_debate` 路由到新路径，快速/基础/标准档走原路径；环境变量 `RISK_SELF_DEBATE`（on/off）一键切回。

**三阶段落地（每阶段独立可验证、可发布、可回退）**：

| 阶段 | 内容 | 改动量 | 独立价值 |
|------|------|--------|---------|
| A9-P1 自我辩论 | 新增 `risk_self_debate_v2` 单节点（自我辩论提示词，一次调用内完成三视角构建→互相质证→产出）+ `workflow_api._prepare_inputs` 按档位注入开关 + builder 风险辩论入口条件路由 | 最小（1 个模板 + 1 处路由开关） | 风险三角 6 次调用→1 次，深度档风险辩论环节约 11 分钟→3 分钟（裁决节点不变） |
| A9-P2 收敛制 | 自我辩论输出 `unresolved_conflicts` 结构化字段 + 按 unresolved_conflicts 动态路由第二轮 | 中（schema + 路由函数） | 分歧可见、报告可标注"未决分歧" |
| A9-P3 取证轮 | 自我辩论节点绑定工具白名单 + 取证计划提示词（发现证据缺口时主动补证） | 中（工具绑定 + 新提示词） | 主动补证，产品差异化 |

P1 单独上线即解决深度档超时与时长问题；P2/P3 延后不影响 P1 收益。

**边界保障**：
- 辩论多轮路由代码全部保留，只加辩论入口的档位判断，不做删除式改造（开关关闭时图结构与旧版一致，三角节点照常接线）
- A/B 总开关：`workflow_api._prepare_inputs` 按档位注入（深度/全面开、快速/基础/标准关），环境变量 `RISK_SELF_DEBATE`（on/off/auto，默认 auto）强制覆盖，任务输入 `risk_self_debate` 可按次显式覆盖；出问题设 `RISK_SELF_DEBATE=off` 一键回旧路径
- 报告章节零改动：自我辩论节点输出兼容现有 `risky/safe/neutral_opinion` 字段与 `risk_debate_state` 三方 history（裁决节点 risk_manager_v2 与报告渲染层均无感知）

**与 Demo / A6 的关系**：
- A9-P1 是 Demo 对比实验的最佳实证素材——"seed-evolving 深度思考原生替代多 agent 多轮辩论，风险辩论环节耗时降约 70%"，正是申请稿"新一代模型特性重构分析流程"的落地。**P1 赶在 9/12 对比实验前落地**，P2/P3 排 Demo 后，互不拖累
- A6（辩论重构）范围相应收窄：风险辩论的深度档部分由 A9-P1/P2 承接；A6 剩余范围（投资辩论 bull/bear 并行简报与收敛终止）在 A9-P1 落地后重估

**验证**：
- P1：深度档全链路跑通，三方情景报告章节正常渲染、裁决结论正常；开关关闭后深度档回退旧路径（风险环节调用数恢复 6）；快速/标准档回归零变化；日志确认深度档风险环节 LLM 调用数=1
- P2：`unresolved_conflicts` 结构化输出并渲染标注；无分歧时单轮即止
- P3：取证轮仅在证据缺口时触发，工具调用可溯源

**P1 落地记录（9/10 晚，代码完成 + 结构验证通过）**：
- `core/agents/adapters/risk_self_debate_v2.py`：自我辩论 agent（三视角提示词 + 三段标记解析，严格→宽松→全文三级降级；输出 `risky/safe/neutral_opinion` + `risk_debate_state`）
- `core/workflow/builder.py`：`build()` 为风险辩论挂隐藏节点 `risk_debate_self_debate`（创建失败自动降级不加节点，不阻塞构建）；`_add_edges()` 辩论入口改条件路由（`_risk_self_debate` True→单节点 / False·缺省→原三角路径，参与者条件边与 bull/bear 辩论零改动）；`_DEEP_AGENTS` 与默认 State schema 同步登记
- `core/workflow/engine.py`：动态 State 内部字段表加 `_risk_self_debate: BOOLEAN`（keep_non_empty reducer）
- `core/api/workflow_api.py` `_prepare_inputs`：按档位注入开关（深度/全面=True，其余=False），`RISK_SELF_DEBATE` 环境变量 on/off 强制覆盖，任务输入 `risk_self_debate` 按次覆盖
- 结构验证（MongoDB 27019 实测）：隐藏节点成功添加且走 deep LLM；入口路由 True→`risk_debate_self_debate`、False/缺省→`risky_analyst_v2`；边 `risk_debate → risk_debate_self_debate → risk_manager_v2` 成立；参与者原路由（count 继续辩论/结束→裁决）不变；`debate`（bull/bear）无分支不受影响；解析器 7 用例（标准/Markdown 标题/同行内容/缺段降级/空输入/重复标记）全过；开关 9 用例（5 档位 + env on/off + 输入双向覆盖）全过
- 待办：深度档真实分析 E2E（对比实验时一并采集耗时/调用数证据）

**后续（P2/P3 之后视带宽）**：低档位优化（分析师集合按档裁剪、数据量分层、提示词分层）维持原方向，作为独立小项排期，不与自我辩论路径耦合。

**前置**：A1b（深度档 effort=high/xhigh 先通，自我辩论才有原生深思考可用）

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
| 9/10 | ① Demo 描述表单（已提交）；② T0 勘察（完成）；③ **A1 旧链路完成**（c6c7dba44）；④ 实战排障：timeout 三层覆盖修复（代码兜底 120 移除 + 47 条种子记录统一 180）、seed-evolving max_tokens 32768、空响应根因诊断（模型侧瞬时异常，Q1 重试兜底） |
| 9/11 | **A1b core 链路档位透传**；**Q1 稳定性三修复**（空响应重试 + 失败不进报告 + finish_reason 日志，Demo 前必须）；**A9-P1 风险自我辩论**（新 agent + 路由开关，赶在对比实验前）；D1 模型注册已取消——seed-evolving 经界面配置入 DB，9/10 诊断脚本直连验证可用 |
| 9/12 | **A3 并行化（时间盒 1 天）**；五环节链路跑通（标的：赛力斯，主题：爆雷风险）；数据同步 + 预留明细缺口 |
| 9/12–9/14 | 对比实验：Seed-Evolving 深度档（4 档/debate=2/effort=high/**风险环节走 A9-P1 自我辩论**）vs 原模型全面档（5 档/debate=3/风险三角多轮），2–3 只股票同题；采集耗时/token/工具轮次/质量评分/拦截实录（风险辩论环节耗时对比即 A9-P1 实证素材） |
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
- 第 2–3 周：A6 辩论重构（4–5d，范围已收窄：投资辩论 + 低档位风险辩论，见 A6 说明）
- 第 3–4 周：**A9-P2 收敛制**（unresolved_conflicts 结构化输出 + 动态路由第二轮，2–3d）→ **A9-P3 取证轮**（工具白名单 + 取证计划提示词，3–4d）；低档位优化小项（分析师裁剪/数据量/提示词分层）视带宽插入
- 穿插：MCP 三平台接入文档（约 0.5d，TraeWork/钉钉 DEAP/企业微信）；Demo 入选后的配合调优（视筛选结果）

### 阶段四：P2（10 月底–11 月）

- A7 框架升级（1–2 周，独立分支，风险最高）→ A8 多模态 K 线（3–5d）
- G1 随 A5–A8 节点改造持续收敛
- 完成后复盘，再定 v4.0 产品层（计划环/沉淀环）与 CRKB 是否接入

## 5. 依赖关系

```
A1 ──→ Demo 对比实验（旧链路已通；A1b 补 core 链路）
A1b ──→ A9-P1（思考预算先通，自我辩论才有原生深思考可用）
A9-P1 ──→ Demo 对比实验（风险辩论环节耗时对比为实证素材）
A9-P1 ──→ A9-P2 ──→ A9-P3（三阶段串行，各自独立可回退）
A3 ──→ Demo 环节②画面
Q1 ──→ Demo 录屏稳定性（空响应/超时不再进报告）
A2 ──→ A6（收敛终止）、A9-P2（结构化输出通道复用）、市场验证裁判、事实-观点-规则分层
A5 ──→ A6
A7 ──→ A8
社区版发布：A1/A3/A9-P1 验证通过后随 M2 快照带出
```

## 6. 风险与对策

| 风险 | 对策 |
|------|------|
| B1 模型 ID/Key 延迟 | A1/T0 先行不阻塞；注册仅 0.5d |
| A3 改动影响主链路 | 1 天时间盒 + 降级开关，不碰辩论/风控节点 |
| A9-P1 自我辩论输出格式漂移/质量不达基线 | 输出兼容现有三 opinion 字段与 debate_state（渲染层零改动）；三段标记解析失败自动全文降级；`RISK_SELF_DEBATE=off` 一键回退旧路径；对比实验双路径同题跑分 |
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

- [x] **B1（已解决 9/10）**：doubao-seed-evolving 经界面配置入 DB，诊断脚本直连两次实测可用（19.3s / 319.5s，思考 token 计入输出预算已确认；max_tokens 已调 32768、timeout 180、D1 注册取消）
- [ ] **B2**：官方《KOL Demo 录屏规范》文档
- [ ] 本计划排期确认（Q1/A1b 提入 9/11、A9-P1 提入 9/11–9/12（Demo 对比实验前）、A9-P2/P3 排 10 月第 3–4 周）
