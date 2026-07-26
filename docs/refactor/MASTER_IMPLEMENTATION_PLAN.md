# AlphaGuard 股票研究与模拟交易系统

## 总体架构与 Codex 实施蓝图

**项目名称：** AlphaGuard  
**中文定位：** AlphaGuard 智能股票研究与风控系统  
**产品标语：** 量化证据驱动，双模型决策，程序化风控。  
**当前阶段：** 自动模拟交易，真实交易关闭  
**基础工程：** 完整改造 TradingAgents-CN，不从零重写

---

# 1. 文档用途与最终工程口径

本文件是 AlphaGuard 的统一实施基线，供 Codex、人工开发、测试和后续迭代共同使用。

现有方案中，早期总体架构提出过 PostgreSQL、DuckDB、Dify 等独立组件；后续源码级实施方案已经明确改为：

1. 完整保留 TradingAgents-CN 作为主工程；
2. 继续使用现有 FastAPI、Vue、MongoDB、Redis、任务队列和 LangGraph；
3. 第一版不引入 Dify、Qlib、FinRL、RD-Agent；
4. 第一版不迁移到 PostgreSQL；
5. DuckDB/Parquet 只作为未来大规模离线研究的可选扩展，不是 MVP 前置依赖；
6. 所有关键决策改为 Pydantic 结构化对象；
7. 大模型只提供分析与建议，Python 掌握最终准入和执行权限。

因此，本文以“TradingAgents-CN 完整 Fork 改造方案”为最终工程口径，以原总体架构作为业务逻辑来源。

---

# 2. 项目目标

AlphaGuard 不是一个只预测明日涨跌的模型，也不是一个依赖大模型自由文本直接下单的机器人。

它要建设的是：

> 以候选池控制研究范围，以数据快照和量化因子形成可验证证据，以 TradingAgents 多智能体完成基本面、技术面、新闻和多空研究，以普通模型制定完整交易计划，以顶尖模型完成独立风险终审，以 Python 完成一致性裁决和硬性风控，通过自动模拟交易验证真实执行效果，并利用评价、归因和 Champion/Challenger 实验体系持续迭代的股票研究与风险控制平台。

## 2.1 第一阶段目标

第一阶段只做：

- A 股和场内 ETF；
- 日线和收盘后决策；
- 20～50 只候选标的；
- 用户自选和持仓强制监控；
- 自动分析；
- 双模型决策；
- Python 硬风控；
- 自动模拟交易；
- 多账户对照评价；
- 离线实验和挑战者验证。

第一阶段不做：

- 真实自动交易；
- 分钟级、高频、日内做 T；
- 全市场逐股调用大模型；
- 大模型自动修改生产代码；
- 策略自动晋升；
- 复杂深度学习价格预测；
- 多券商接入；
- Dify 编排；
- Qlib、FinRL、RD-Agent 深度集成。

## 2.2 固定安全模式

```python
system_mode = "SIM_AUTONOMOUS"
live_trading_enabled = False
```

系统应在配置层、服务层、订单层设置三重保护。任何代码路径不得在 `live_trading_enabled=False` 时调用真实券商适配器。

---

# 3. 总体系统结构

AlphaGuard 由 10 个纵向模块和 4 个横向能力组成。

## 3.1 纵向模块

```text
0. 统一候选池 Candidate Pool
1. 数据与证据中心 Evidence Center
2. 量化因子与市场状态 Factor & Regime Engine
3. 程序化策略引擎 Strategy Engine
4. TradingAgents 多智能体研究层
5. 普通模型交易计划层 Normal Decision Model
6. 顶尖模型风险终审层 Top Review Model
7. Python 一致性裁决与硬风控
8. 自动模拟交易与账户系统
9. 评价归因与离线实验室
```

未来增加：

```text
10. 全市场低成本推荐模块
```

## 3.2 横向能力

```text
A. 调度、队列、重试与幂等
B. 版本、配置与审计
C. 统一结构化 Schema 和状态机
D. 日志、监控、告警与可观测性
```

## 3.3 完整主流程

```text
用户自选 / 持仓强制 / 未来程序推荐
                    ↓
                统一候选池
                    ↓
           基础数据完整性检查
                    ↓
          创建 EvidenceSnapshot
                    ↓
      市场状态 + 因子 + 风险事件计算
                    ↓
         程序化策略生成 QuantProposal
                    ↓
             是否触发深度分析？
             ├─ 否：继续观察并记录
             └─ 是
                    ↓
      TradingAgents 多智能体读取同一快照
                    ↓
        普通模型生成 NormalTradePlan
                    ↓
             是否提出交易？
             ├─ 否：记录 NO_TRADE/WAIT
             └─ 是
                    ↓
      顶尖模型生成 TopReviewDecision
                    ↓
      ConsensusEngine 判断是否形成一致
                    ↓
      HardRiskEngine 执行程序化硬风控
                    ↓
              生成 OrderIntent
                    ↓
        T+1 模拟订单、撮合、成交、结算
                    ↓
       账户、持仓、收益、风险指标更新
                    ↓
       多周期评价、反事实评价、失败归因
                    ↓
       Challenger 实验、影子运行和比较
```

---

# 4. TradingAgents-CN 在 AlphaGuard 中的定位

## 4.1 直接保留

保留并逐步重构，而不是推倒重做：

- FastAPI 后端；
- Vue 前端；
- MongoDB；
- Redis；
- 用户、权限、配置；
- 模型供应商和模型配置；
- 数据源管理；
- A 股、港股、美股基础数据能力；
- 行情、财务、新闻、公告同步；
- 自选股；
- 股票筛选；
- 分析任务、队列、进度展示；
- LangGraph 多 Agent 流程；
- 分析报告；
- 模拟账户、持仓、订单页面；
- 日志、通知、健康检查。

## 4.2 必须修复的原有问题

源码中现有 `SignalProcessor` 和相关流程存在以下不适合自动交易的行为：

- 空输入或模型失败默认返回“持有”；
- 要求目标价必须存在；
- 目标价缺失时从文本猜测；
- 无法提取时根据当前价自动估算；
- 交易决策依赖自然语言二次解析；
- 模型输出不合法时仍可能形成默认决策；
- 现有模拟交易接口按最新价即时成交；
- 自动策略与人工下单没有隔离；
- 风险经理输入和最终决策仍以文本字段为主。

AlphaGuard 必须将这些行为改为：

```text
模型失败 ≠ 持有
解析失败 ≠ 持有
缺少目标价 ≠ 自动推算目标价
字段缺失 ≠ 继续下单
```

统一结果：

```text
MODEL_FAILED / INVALID_OUTPUT / INSUFFICIENT_DATA
→ 阻断交易
→ 保存错误上下文
→ 可重试但不得静默降级为交易决定
```

## 4.3 新增能力

- Candidate Pool；
- EvidenceSnapshot；
- DataQualityGate；
- FactorRegistry；
- FactorEngine；
- MarketRegimeEngine；
- StrategyRegistry；
- QuantTradeProposal；
- NormalTradePlan；
- TopReviewDecision；
- ConsensusEngine；
- HardRiskEngine；
- OrderIntent；
- MatchingEngine；
- SettlementService；
- EvaluationService；
- AttributionEngine；
- ExperimentRegistry；
- Champion/Challenger 管理。

---

# 5. 推荐代码目录

不要另建第二套后端。应在现有主工程内新增模块，并保持模块化单体结构。

```text
TradingAgents-CN-main/
├─ app/
│  ├─ main.py
│  ├─ routers/
│  │  ├─ candidates.py                 # 新增
│  │  ├─ evidence.py                   # 新增
│  │  ├─ factors.py                    # 新增
│  │  ├─ strategies.py                 # 新增
│  │  ├─ decisions.py                  # 新增
│  │  ├─ risk.py                       # 新增
│  │  ├─ paper_orders.py               # 新增，自动模拟订单
│  │  ├─ evaluation.py                 # 新增
│  │  ├─ experiments.py                # 新增
│  │  ├─ paper.py                      # 保留，人工模拟交易
│  │  └─ favorites.py                  # 保留，作为候选池来源之一
│  │
│  ├─ schemas/
│  │  └─ alphaguard/
│  │     ├─ common.py
│  │     ├─ candidate.py
│  │     ├─ evidence.py
│  │     ├─ factor.py
│  │     ├─ strategy.py
│  │     ├─ decision.py
│  │     ├─ risk.py
│  │     ├─ order.py
│  │     ├─ evaluation.py
│  │     └─ experiment.py
│  │
│  ├─ models/
│  │  └─ alphaguard/
│  │     ├─ enums.py
│  │     ├─ collections.py
│  │     └─ indexes.py
│  │
│  ├─ services/
│  │  └─ alphaguard/
│  │     ├─ candidate_pool_service.py
│  │     ├─ evidence_snapshot_service.py
│  │     ├─ data_quality_service.py
│  │     ├─ factor_engine.py
│  │     ├─ factor_registry.py
│  │     ├─ market_regime_engine.py
│  │     ├─ strategy_engine.py
│  │     ├─ strategy_registry.py
│  │     ├─ analysis_orchestrator.py
│  │     ├─ normal_decision_service.py
│  │     ├─ top_review_service.py
│  │     ├─ consensus_engine.py
│  │     ├─ hard_risk_engine.py
│  │     ├─ order_intent_service.py
│  │     ├─ matching_engine.py
│  │     ├─ settlement_service.py
│  │     ├─ position_service.py
│  │     ├─ fee_engine.py
│  │     ├─ evaluation_service.py
│  │     ├─ attribution_engine.py
│  │     ├─ experiment_service.py
│  │     └─ version_service.py
│  │
│  ├─ worker/
│  │  └─ alphaguard/
│  │     ├─ candidate_scan_worker.py
│  │     ├─ evidence_worker.py
│  │     ├─ analysis_worker.py
│  │     ├─ order_worker.py
│  │     ├─ settlement_worker.py
│  │     ├─ evaluation_worker.py
│  │     └─ experiment_worker.py
│  │
│  └─ core/
│     └─ alphaguard_config.py
│
├─ tradingagents/
│  ├─ agents/
│  │  ├─ trader/trader.py              # 改造为结构化普通模型方案
│  │  └─ managers/risk_manager.py      # 改造为结构化顶尖终审
│  ├─ agents/utils/agent_states.py      # 增加 snapshot 和结构化字段
│  ├─ graph/setup.py                    # 注入结构化节点和终审节点
│  ├─ graph/trading_graph.py            # 返回结构化结果
│  ├─ graph/signal_processing.py        # 废弃自动猜价和默认持有
│  └─ alphaguard/
│     ├─ context_builder.py             # 新增，构建统一 Agent 上下文
│     ├─ structured_output.py           # 新增，结构化模型适配
│     └─ prompts/
│        ├─ normal_trade_plan_v1.md
│        └─ top_risk_review_v1.md
│
├─ frontend/src/
│  ├─ api/
│  │  ├─ candidates.ts
│  │  ├─ decisions.ts
│  │  ├─ paperOrders.ts
│  │  ├─ evaluation.ts
│  │  └─ experiments.ts
│  └─ views/
│     ├─ AlphaGuardDashboard/
│     ├─ CandidatePool/
│     ├─ DecisionCenter/
│     ├─ PaperTrading/
│     ├─ EvaluationCenter/
│     └─ ExperimentLab/
│
├─ tests/
│  ├─ unit/alphaguard/
│  ├─ integration/alphaguard/
│  ├─ replay/alphaguard/
│  └─ fixtures/alphaguard/
│
├─ scripts/
│  ├─ init_alphaguard_indexes.py
│  ├─ migrate_paper_accounts.py
│  ├─ seed_market_rules.py
│  └─ replay_decision.py
│
├─ docs/refactor/
│  ├─ MASTER_IMPLEMENTATION_PLAN.md
│  ├─ SOURCE_MODIFICATION_MAP.md
│  ├─ DATA_MODEL.md
│  ├─ API_SPEC.md
│  ├─ STATE_MACHINES.md
│  └─ CODEX_EXECUTION_STATUS.md
│
└─ docker-compose.yml
```

---

# 6. 统一核心数据对象

所有关键对象必须使用 Pydantic 定义，MongoDB 只保存其序列化结果。禁止在服务之间传递无法验证的任意字典。

## 6.1 通用元数据

每个核心对象至少包含：

```python
class TraceMeta(BaseModel):
    trace_id: str
    user_id: str | None = None
    symbol: str
    market: Literal["CN", "HK", "US"]
    trade_date: date
    created_at: datetime
    schema_version: str
    code_version: str
```

## 6.2 CandidateEntry

```python
class CandidateEntry(BaseModel):
    candidate_id: str
    symbol: str
    market: str
    name: str | None
    sources: set[CandidateSource]
    status: CandidateStatus
    priority: int
    added_at: datetime
    next_scan_at: datetime | None
    cooldown_until: datetime | None
    active_plan_id: str | None
    active_order_ids: list[str]
    held_account_ids: list[str]
    removal_requested: bool = False
```

候选来源：

```text
USER_SELECTED
POSITION_REQUIRED
SYSTEM_SCREENED
EVENT_TRIGGERED
EXPERIMENT_ASSIGNED
```

候选状态：

```text
WATCHING
SIGNAL_DETECTED
AI_ANALYZING
PLAN_PROPOSED
TOP_REVIEWING
APPROVED
REJECTED
ORDER_PENDING
POSITION_HELD
EXIT_REVIEW
RISK_ALERT
COOLDOWN
REMOVED
```

删除规则：只要存在持仓、未完成订单、有效交易计划、未完成评价任务，候选不得物理删除，只能设置 `removal_requested=True`。

## 6.3 EvidenceSnapshot

```python
class EvidenceSnapshot(BaseModel):
    snapshot_id: str
    symbol: str
    market: str
    trade_date: date
    price_cutoff_at: datetime
    news_cutoff_at: datetime
    announcement_cutoff_at: datetime
    price_data_version: str
    financial_data_version: str
    news_data_version: str
    account_snapshot_id: str
    market_context_id: str
    data_quality: DataQualityReport
    raw_refs: dict[str, list[str]]
    factor_version_set: dict[str, str]
    strategy_version: str | None
    normal_model_version: str | None
    top_model_version: str | None
    prompt_versions: dict[str, str]
    immutable_hash: str
```

快照创建后不可修改。数据修复必须生成新快照，不允许覆盖旧快照。

## 6.4 DataQualityReport

```python
class DataQualityReport(BaseModel):
    status: Literal["PASS", "WARN", "FAIL"]
    completeness_score: float
    freshness_score: float
    consistency_score: float
    missing_fields: list[str]
    stale_sources: list[str]
    anomalies: list[str]
    blocking_reasons: list[str]
```

`FAIL` 时不得进入模型决策。

## 6.5 FactorResult

```python
class FactorResult(BaseModel):
    factor_id: str
    factor_version: str
    symbol: str
    snapshot_id: str
    raw_value: float | None
    normalized_score: float | None
    direction: Literal["POSITIVE", "NEUTRAL", "NEGATIVE", "UNKNOWN"]
    confidence: float
    missing_reason: str | None
    calculated_at: datetime
```

## 6.6 MarketRegimeResult

```python
class MarketRegimeResult(BaseModel):
    regime: Literal[
        "TREND_UP", "RANGE_STRONG", "RANGE_WEAK",
        "TREND_DOWN", "EXTREME_RISK"
    ]
    confidence: float
    evidence: list[str]
    allowed_strategy_ids: list[str]
    max_total_exposure_pct: float
```

## 6.7 QuantTradeProposal

```python
class QuantTradeProposal(BaseModel):
    proposal_id: str
    snapshot_id: str
    strategy_id: str
    strategy_version: str
    status: Literal["TRIGGERED", "WATCH", "REJECTED"]
    action_candidate: Literal["BUY", "SELL", "REDUCE", "HOLD", "WAIT"]
    entry_zone: PriceRange | None
    initial_position_pct: float
    max_position_pct: float
    add_conditions: list[RuleCondition]
    reduce_conditions: list[RuleCondition]
    exit_conditions: list[RuleCondition]
    invalidation_conditions: list[RuleCondition]
    valid_until: datetime
    expected_holding_days: tuple[int, int] | None
    factor_summary: dict[str, float]
    risk_flags: list[str]
```

## 6.8 NormalTradePlan

```python
class NormalTradePlan(BaseModel):
    plan_id: str
    snapshot_id: str
    quant_proposal_id: str
    status: Literal[
        "PROPOSE_TRADE", "NO_TRADE", "WAIT",
        "INSUFFICIENT_DATA", "MODEL_FAILED", "INVALID_OUTPUT"
    ]
    action: Literal["BUY", "SELL", "REDUCE", "HOLD", "WAIT", "NONE"]
    confidence: float
    thesis: str
    bullish_evidence: list[EvidenceRef]
    bearish_evidence: list[EvidenceRef]
    entry_zone: PriceRange | None
    initial_position_pct: float | None
    max_position_pct: float | None
    add_conditions: list[RuleCondition]
    stop_conditions: list[RuleCondition]
    reduce_conditions: list[RuleCondition]
    exit_conditions: list[RuleCondition]
    invalidation_conditions: list[RuleCondition]
    target_price: float | None
    valid_until: datetime | None
    main_risks: list[RiskItem]
    unresolved_questions: list[str]
    model_meta: ModelExecutionMeta
```

`target_price` 允许为 `None`。交易有效性不能依赖必须存在的目标价。

## 6.9 TopReviewDecision

```python
class TopReviewDecision(BaseModel):
    review_id: str
    snapshot_id: str
    plan_id: str
    status: Literal[
        "CONFIRM", "RISK_ADJUST", "MATERIAL_REVISION",
        "REJECT", "SUSPEND", "MODEL_FAILED", "INVALID_OUTPUT"
    ]
    completeness_score: float
    logic_consistency_score: float
    risk_control_score: float
    missing_evidence: list[str]
    logical_conflicts: list[str]
    risk_findings: list[RiskItem]
    adjusted_plan: NormalTradePlan | None
    material_change_fields: list[str]
    review_reason: str
    model_meta: ModelExecutionMeta
```

顶尖模型不能独立创建与普通模型方向相反的新交易。

## 6.10 ConsensusDecision

```python
class ConsensusDecision(BaseModel):
    consensus_id: str
    snapshot_id: str
    plan_id: str
    review_id: str
    status: Literal[
        "CONSENSUS_PASS", "CONSENSUS_REVISE",
        "CONSENSUS_REJECT", "CONSENSUS_INVALID"
    ]
    final_plan: NormalTradePlan | None
    reasons: list[str]
    requires_normal_reconfirm: bool
```

## 6.11 RiskDecision

```python
class RiskDecision(BaseModel):
    risk_decision_id: str
    consensus_id: str
    status: Literal["PASS", "REDUCE", "REJECT", "SUSPEND"]
    approved_position_pct: float | None
    approved_quantity: int | None
    triggered_rules: list[RiskRuleResult]
    reasons: list[str]
    risk_policy_version: str
```

## 6.12 OrderIntent 和 PaperOrder

```python
class OrderIntent(BaseModel):
    intent_id: str
    account_id: str
    symbol: str
    market: str
    side: Literal["BUY", "SELL"]
    order_type: Literal["LIMIT", "MARKET_ON_OPEN", "MARKET"]
    quantity: int
    limit_price: float | None
    earliest_execute_at: datetime
    expires_at: datetime
    snapshot_id: str
    consensus_id: str
    risk_decision_id: str
    idempotency_key: str
```

```python
class PaperOrder(BaseModel):
    order_id: str
    intent_id: str
    status: Literal[
        "CREATED", "SUBMITTED", "PENDING", "PARTIALLY_FILLED",
        "FILLED", "CANCELLED", "REJECTED", "EXPIRED"
    ]
    requested_quantity: int
    filled_quantity: int
    average_fill_price: float | None
    fees: float
    reject_reason: str | None
    created_at: datetime
    updated_at: datetime
```

---

# 7. MongoDB 集合设计

第一版继续使用 MongoDB。集合命名建议统一添加 `ag_` 前缀，避免与原项目集合混淆。

```text
ag_candidates
ag_candidate_events
ag_evidence_snapshots
ag_data_quality_reports
ag_market_contexts
ag_factor_definitions
ag_factor_results
ag_regime_results
ag_strategy_definitions
ag_quant_proposals
ag_normal_trade_plans
ag_top_reviews
ag_consensus_decisions
ag_risk_policies
ag_risk_decisions
ag_order_intents
ag_paper_orders
ag_paper_fills
ag_paper_accounts
ag_paper_positions
ag_paper_position_lots
ag_daily_account_snapshots
ag_evaluation_labels
ag_attribution_results
ag_experiments
ag_strategy_versions
ag_prompt_versions
ag_model_runs
ag_audit_events
ag_job_runs
```

## 7.1 必要唯一索引

```text
ag_candidates: (user_id, market, symbol) unique
ag_evidence_snapshots: snapshot_id unique
ag_factor_results: (snapshot_id, factor_id, factor_version) unique
ag_quant_proposals: (snapshot_id, strategy_id, strategy_version) unique
ag_normal_trade_plans: plan_id unique
ag_top_reviews: review_id unique
ag_order_intents: idempotency_key unique
ag_paper_orders: order_id unique
ag_evaluation_labels: (source_object_id, horizon) unique
ag_job_runs: idempotency_key unique
```

所有时间序列查询字段必须建立复合索引：`symbol + trade_date`、`account_id + trade_date`、`status + next_scan_at`。

---

# 8. 候选池实现

## 8.1 候选池职责

候选池只决定“分析谁”，不决定“买什么”。

第一版来源：

- 用户收藏同步为 `USER_SELECTED`；
- 所有模拟持仓同步为 `POSITION_REQUIRED`；
- 未完成订单和有效交易计划对应标的强制保留；
- 后续再加入程序筛选和事件触发。

## 8.2 低成本扫描

每日候选池基础扫描不调用大模型，只运行 Python：

- 数据是否更新；
- 价格趋势是否变化；
- 是否触发策略；
- 是否接近入场区间；
- 是否触发持仓退出；
- 是否出现重大公告或风险事件；
- 是否需要更新已有交易计划。

只有满足触发条件的标的才进入 TradingAgents 深度分析。

## 8.3 推荐触发条件

第一版可以使用以下任一条件触发：

- 新策略信号产生；
- 原有信号由 WATCH 转为 TRIGGERED；
- 市场状态发生实质变化；
- 价格进入计划入场区间；
- 持仓触发减仓、止损或退出条件；
- 新重大公告或高风险事件；
- 旧计划即将到期；
- 数据快照发生重要修订。

## 8.4 冷却机制

同一股票在无新证据时不得反复调用模型。

建议：

- `NO_TRADE`：冷却 3 个交易日；
- `REJECT`：冷却 5 个交易日；
- `WAIT`：由计划指定下一检查条件；
- `MODEL_FAILED`：允许有限重试，不进入普通冷却；
- 新重大事件可打破冷却。

---

# 9. 数据与证据中心

## 9.1 数据来源

复用 TradingAgents-CN 现有数据适配器：

- Tushare；
- AkShare；
- BaoStock；
- 现有行情数据库；
- 财务数据；
- 新闻和公告；
- 指数和行业信息；
- 模拟账户数据。

## 9.2 数据截止时间

收盘后任务必须记录：

- 行情数据截止到哪个交易日；
- 财务数据发布日期；
- 新闻和公告抓取截止时间；
- 是否包含盘后公告；
- 所有数据源是否完成同步。

禁止使用在决策时点尚未发布的数据。

## 9.3 Snapshot 生成流程

```text
检查交易日
→ 等待必要数据同步完成
→ 汇总行情、财务、估值、新闻、公告和账户
→ 执行缺失、异常、时效和一致性检查
→ 生成 DataQualityReport
→ FAIL 则停止
→ PASS/WARN 则创建不可变 EvidenceSnapshot
→ 计算 immutable_hash
```

## 9.4 证据引用

模型输出中的多头、空头和风险结论应引用证据 ID，而不是只写自然语言。

```json
{
  "evidence_id": "news:abc123",
  "evidence_type": "ANNOUNCEMENT",
  "summary": "公司披露重要股东减持计划",
  "as_of": "2026-07-26T18:00:00+08:00"
}
```

---

# 10. 因子和市场状态引擎

## 10.1 因子原则

第一版只使用 15～25 个可解释因子。每个因子必须：

- 有明确公式；
- 有输入字段；
- 有回看窗口；
- 有缺失值处理；
- 有版本；
- 有单元测试；
- 能独立重算；
- 不含未来数据。

## 10.2 第一版因子组

### 趋势与动量

- 收盘价相对 MA20；
- 收盘价相对 MA60；
- MA20/MA60 多空排列；
- MA20 斜率；
- 20 日动量；
- 60 日动量；
- 相对沪深 300 强弱；
- 相对行业强弱；
- 放量确认。

### 基本面质量

- 营收同比；
- 扣非净利润同比；
- ROE；
- 经营现金流/净利润；
- 毛利率趋势；
- 负债水平。

### 估值

- PE-TTM 历史分位；
- PB 历史分位；
- 行业相对估值；
- 股息率；
- 估值变化趋势。

### 风险和交易性

- ATR；
- 20 日波动率；
- 平均成交额；
- 换手率；
- 短期异常涨幅；
- ST/停牌/涨跌停；
- 解禁、减持、诉讼、监管风险。

## 10.3 聚合分数

第一版输出：

```text
TrendScore
MomentumScore
ValuationScore
QualityScore
LiquidityScore
VolatilityRiskScore
EventRiskScore
IndustryStrengthScore
```

分数范围统一为 0～100，但必须同时保留原始因子值，避免只剩不可解释总分。

## 10.4 市场状态

第一版状态：

```text
TREND_UP
RANGE_STRONG
RANGE_WEAK
TREND_DOWN
EXTREME_RISK
```

市场状态至少考虑：

- 主要指数趋势；
- 市场宽度；
- 成交额变化；
- 上涨/下跌家数；
- 新高/新低家数；
- 波动率；
- 行业扩散度；
- 极端风险事件。

状态影响：

- 可启用策略；
- 单股最大仓位；
- 总仓位上限；
- 触发深度分析门槛；
- 是否暂停新开仓。

---

# 11. 程序化策略引擎

## 11.1 第一版策略

```text
SWING_TREND_PULLBACK_V1
ETF_ROTATION_V1
POSITION_EXIT_V1
RISK_REDUCTION_V1
```

其中首个 Champion 建议为：

```text
SWING_TREND_PULLBACK_V1
```

## 11.2 趋势回调策略示例

基础条件示例：

- 市场状态不是 `TREND_DOWN` 或 `EXTREME_RISK`；
- 价格位于 MA60 之上；
- MA20 上行；
- 20 日或 60 日动量为正；
- 相对指数强弱为正；
- 近期从阶段高点回调但未破坏中期趋势；
- 流动性满足要求；
- 无阻断级事件风险。

触发后输出：

- 入场区间；
- 初始仓位；
- 最大仓位；
- 加仓条件；
- 失效条件；
- 减仓条件；
- 退出条件；
- 有效期；
- 风险标签。

策略不得直接创建订单，只能创建 `QuantTradeProposal`。

## 11.3 策略版本

每个策略版本需保存：

```text
strategy_id
strategy_version
status
code_hash
parameter_hash
factor_dependencies
allowed_regimes
created_at
promoted_at
parent_version
```

---

# 12. TradingAgents 多智能体研究层

继续保留现有 Agent：

- 市场分析师；
- 基本面分析师；
- 新闻分析师；
- 社交媒体分析师（MVP 可关闭）；
- 多头研究员；
- 空头研究员；
- 研究经理；
- 交易员；
- 激进、保守、中性风险辩论；
- 风险经理。

## 12.1 新的输入边界

所有 Agent 必须读取同一个：

```text
snapshot_id
QuantTradeProposal
账户快照
市场状态
因子结果
证据引用
```

Agent 不得自行获取不同时间点的数据后覆盖快照结论。确需新数据时，应终止本次分析并要求创建新快照。

## 12.2 市场分析师

职责：解释已计算的技术指标、趋势和量价结构。不得在 Prompt 中自行发明不存在的指标值。

## 12.3 基本面分析师

职责：

- 盈利质量；
- 财务趋势；
- 估值合理性；
- 行业位置；
- 现金流和负债风险；
- 关键财务异常。

## 12.4 新闻和公告分析师

输出结构：

```text
事件类别
方向
强度
时间范围
可信度
是否阻断交易
证据引用
```

## 12.5 多空研究和研究经理

多空双方必须围绕同一快照和同一量化候选方案讨论。研究经理输出投资逻辑，但不直接生成订单。

---

# 13. 普通模型交易计划

普通模型对应现有 Trader 节点，但必须改为结构化输出。

## 13.1 普通模型职责

- 判断量化候选方案是否被基本面、新闻和市场环境支持；
- 判断当前是否值得交易；
- 给出完整、可执行、可失效的计划；
- 主动列出反对理由和未解决问题；
- 不确定时返回 WAIT 或 INSUFFICIENT_DATA，而不是编造。

## 13.2 允许状态

```text
PROPOSE_TRADE
NO_TRADE
WAIT
INSUFFICIENT_DATA
MODEL_FAILED
INVALID_OUTPUT
```

## 13.3 结构化调用

优先使用模型原生结构化输出或工具调用；不支持时，允许 JSON 模式，但必须通过 Pydantic 严格校验。

禁止：

- 用正则从长文本猜最终方向；
- 用另一个 LLM 二次猜测字段；
- 缺字段时自动补默认交易值；
- 强制生成目标价；
- 输出失败时默认 HOLD。

---

# 14. 顶尖模型风险终审

顶尖模型对应改造后的 Risk Judge，但其定位不是另一个发现机会的交易员。

## 14.1 职责

- 检查证据完整性；
- 检查普通模型是否漏掉重大事件；
- 检查多周期逻辑是否冲突；
- 检查交易方向、入场位置、盈亏结构和仓位；
- 检查市场状态、组合风险和相关性；
- 检查量化方案与自然语言论证是否一致；
- 给出确认、降险调整、重大修改、否决或暂停。

## 14.2 状态

```text
CONFIRM
RISK_ADJUST
MATERIAL_REVISION
REJECT
SUSPEND
MODEL_FAILED
INVALID_OUTPUT
```

## 14.3 修改权限

允许的 `RISK_ADJUST`：

- 降低初始仓位；
- 降低最大仓位；
- 缩窄买入区间；
- 增加风险条件；
- 缩短计划有效期；
- 提高触发门槛。

视为 `MATERIAL_REVISION`：

- BUY 改为 SELL；
- SELL 改为 BUY；
- 交易改为等待；
- 核心入场逻辑重写；
- 持有周期和策略类型改变；
- 退出逻辑发生实质变化。

重大修改必须返回普通模型重新确认，最多一轮。超过一轮仍不一致则拒绝。

---

# 15. ConsensusEngine

ConsensusEngine 是纯 Python 模块，不调用大模型。

## 15.1 检查项

- 两个对象是否引用同一 `snapshot_id`；
- 普通模型是否为 `PROPOSE_TRADE`；
- 顶尖模型状态是否允许；
- action 是否一致；
- 调整是否仅为降险；
- 调整后的字段是否合法；
- 关键字段是否完整；
- 证据引用是否存在；
- 决策是否已过期；
- 是否完成重大修改重新确认；
- 模型运行是否成功。

## 15.2 输出规则

```text
PROPOSE_TRADE + CONFIRM
→ CONSENSUS_PASS

PROPOSE_TRADE + RISK_ADJUST 且仅降险
→ CONSENSUS_PASS，使用 adjusted_plan

PROPOSE_TRADE + MATERIAL_REVISION
→ CONSENSUS_REVISE，最多返回普通模型一次

任一模型 REJECT / SUSPEND / FAILED / INVALID
→ CONSENSUS_REJECT 或 CONSENSUS_INVALID
```

---

# 16. HardRiskEngine

HardRiskEngine 是最终交易准入门。它只执行固定规则，不判断股票“值不值得”。

## 16.1 第一版规则

### 数据和决策

- DataQuality 不得为 FAIL；
- snapshot 未过期；
- 决策未过期；
- 计划字段完整；
- snapshot、plan、review、consensus 关联一致。

### 标的交易状态

- 非停牌；
- 非禁止交易名单；
- ST 标的默认禁止新增买入；
- 涨停无法买入；
- 跌停无法卖出；
- 流动性满足最低标准。

### 账户和组合

- 现金充足；
- 单股仓位上限；
- 总仓位上限；
- 行业集中度；
- ETF/股票分类限额；
- 组合相关性上限；
- 单日新开仓数量；
- 单日风险预算；
- 已存在同方向有效订单时禁止重复提交。

### A 股交易规则

- T+1；
- 买入数量为 100 股整数倍；
- 卖出允许处理剩余零股；
- 手续费、印花税、过户费；
- 交易日和交易时段；
- 决策使用 T 日完整收盘数据时，最早 T+1 执行。

## 16.2 风控结果

```text
PASS
REDUCE
REJECT
SUSPEND
```

`REDUCE` 只能降低仓位或数量，不得改变交易方向。

## 16.3 初始参数建议

第一版采用保守默认值，并全部配置化：

```yaml
max_single_position_pct: 0.10
max_total_exposure_pct: 0.60
max_industry_exposure_pct: 0.25
max_new_positions_per_day: 3
min_cash_reserve_pct: 0.20
max_order_participation_rate: 0.05
st_buy_enabled: false
live_trading_enabled: false
```

具体数值后续通过模拟结果调整，不写死在业务代码中。

---

# 17. 自动模拟交易系统

## 17.1 与现有人工模拟交易隔离

现有 `/paper/order` 即时成交接口保留为：

```text
MANUAL_PAPER
```

自动决策不得调用该接口。新增独立链路：

```text
OrderIntent
→ OrderService
→ PaperOrder
→ MatchingEngine
→ PaperFill
→ SettlementService
→ PositionService
```

## 17.2 模拟账户

```text
MANUAL_PAPER
PAPER_QUANT
PAPER_NORMAL
PAPER_TOP_CONFIRMED
PAPER_CHALLENGER
```

对照意义：

```text
PAPER_NORMAL - PAPER_QUANT
= 普通模型相对纯量化方案的增量价值

PAPER_TOP_CONFIRMED - PAPER_NORMAL
= 顶尖模型终审的增量价值
```

所有自动账户必须使用：

- 相同初始资金；
- 相同快照；
- 相同手续费；
- 相同滑点；
- 相同交易时间；
- 相同撮合规则。

## 17.3 撮合规则

第一版支持：

- 限价单；
- 次日开盘执行；
- 开盘跳空；
- 价格未触及则不成交；
- 涨跌停；
- 停牌；
- 部分成交；
- 成交量参与率；
- 订单有效期；
- 手续费和税费；
- 滑点。

日线撮合示例：

### 买入限价单

- 次日开盘价低于等于限价：按 `min(开盘价+滑点, 限价)` 成交；
- 开盘未成交但日内最低价触及限价：按限价加模型化滑点成交；
- 最低价未触及：订单继续等待或过期。

### 卖出限价单

- 次日开盘价高于等于限价：按 `max(开盘价-滑点, 限价)` 成交；
- 日内最高价触及限价：按限价减滑点成交；
- 最高价未触及：不成交。

撮合算法必须版本化，并明确这是日线近似，不声称重建真实逐笔成交。

## 17.4 持仓批次

为正确处理 T+1，应保存持仓 lot：

```text
account_id
symbol
acquired_trade_date
quantity
remaining_quantity
cost_price
available_from_date
```

不能只用“今天成交记录字符串比较”来推导可卖数量。

---

# 18. 评价与归因

## 18.1 全样本保存

不仅保存成交交易，还要保存：

- 未触发策略；
- 策略 WATCH；
- 普通模型 NO_TRADE；
- 普通模型 WAIT；
- 顶尖模型 REJECT；
- 顶尖模型调整前后计划；
- Consensus 拒绝；
- HardRisk 拦截；
- 未触发入场区间；
- 未成交和过期订单；
- 已成交交易；
- 持仓退出。

否则无法评价模型是否过于保守、是否错过机会。

## 18.2 多周期标签

第一版至少：

```text
1D
5D
10D
20D
```

后续增加 60D。

每个决策对象计算：

- 未来收益；
- 相对沪深 300 收益；
- 相对行业收益；
- MFE；
- MAE；
- 是否触及入场区间；
- 是否触及止损；
- 是否触及退出条件；
- 计划是否仍有效；
- 实际成交后的净收益。

## 18.3 反事实评价

对于被顶尖模型否决或风控拦截的方案，仍要模拟“若执行会怎样”，但不得计入正式账户。

这用于判断：

- 顶尖模型否决是否有效；
- 风控是否过度保守；
- 普通模型是否比量化基准更好。

## 18.4 失败归因

```text
DATA_QUALITY
CANDIDATE_SELECTION
FACTOR_FAILURE
REGIME_MISCLASSIFICATION
STRATEGY_ENTRY
NORMAL_MODEL
TOP_MODEL
CONSENSUS
HARD_RISK
EXECUTION
MARKET_SHOCK
UNKNOWN
```

归因应同时提供：

- 机器规则结果；
- 关键证据；
- 可选的大模型总结；
- 人工可修改标签。

---

# 19. 离线实验室和 Champion/Challenger

## 19.1 可实验对象

- 因子公式；
- 因子权重；
- 市场状态算法；
- 策略参数；
- 入场和退出规则；
- 仓位和风险参数；
- 普通模型 Prompt；
- 顶尖模型 Prompt；
- 模型组合；
- Agent 组合；
- 辩论轮数；
- 撮合参数。

## 19.2 版本状态

```text
DRAFT
EXPERIMENT
BACKTESTED
SHADOW
CHALLENGER
CHAMPION
DEGRADED
SUSPENDED
RETIRED
```

## 19.3 晋升流程

```text
发现问题
→ 明确实验假设
→ 创建 Challenger
→ 历史回放
→ 时间序列样本外验证
→ 稳健性和压力测试
→ 实时 Shadow
→ PAPER_CHALLENGER 模拟运行
→ 与 Champion 比较
→ 顶尖模型审查实验风险
→ 人工批准
→ 晋升 Champion
```

每次实验原则上只修改一个主要变量。禁止同时修改因子、策略、Prompt 和风控后宣称某一项有效。

## 19.4 晋升最低条件

不预设固定收益门槛，但必须检查：

- 样本外收益；
- 最大回撤；
- 收益/回撤比；
- 交易次数；
- 换手率和成本；
- 不同市场状态稳定性；
- 是否依赖少数极端交易；
- 是否存在未来数据泄漏；
- Shadow 和 Challenger 是否一致。

---

# 20. API 设计

## 20.1 候选池

```text
GET    /api/alphaguard/candidates
POST   /api/alphaguard/candidates
GET    /api/alphaguard/candidates/{candidate_id}
PATCH  /api/alphaguard/candidates/{candidate_id}
DELETE /api/alphaguard/candidates/{candidate_id}
POST   /api/alphaguard/candidates/{candidate_id}/scan
```

## 20.2 证据和研究

```text
POST /api/alphaguard/evidence/snapshots
GET  /api/alphaguard/evidence/snapshots/{snapshot_id}
GET  /api/alphaguard/evidence/snapshots/{snapshot_id}/quality
GET  /api/alphaguard/factors/{snapshot_id}
GET  /api/alphaguard/strategies/proposals/{snapshot_id}
```

## 20.3 决策

```text
POST /api/alphaguard/analyses
GET  /api/alphaguard/analyses/{analysis_id}
GET  /api/alphaguard/decisions/{plan_id}
GET  /api/alphaguard/reviews/{review_id}
GET  /api/alphaguard/consensus/{consensus_id}
GET  /api/alphaguard/risk-decisions/{risk_decision_id}
```

## 20.4 自动模拟交易

```text
GET  /api/alphaguard/paper/accounts
GET  /api/alphaguard/paper/accounts/{account_id}
GET  /api/alphaguard/paper/orders
GET  /api/alphaguard/paper/orders/{order_id}
POST /api/alphaguard/paper/orders/{order_id}/cancel
GET  /api/alphaguard/paper/positions
GET  /api/alphaguard/paper/equity-curve
```

自动订单创建应仅由内部服务完成，不开放普通用户直接提交 `OrderIntent` 的公共接口。

## 20.5 评价和实验

```text
GET  /api/alphaguard/evaluations/overview
GET  /api/alphaguard/evaluations/decisions/{object_id}
GET  /api/alphaguard/evaluations/model-value
GET  /api/alphaguard/attributions
POST /api/alphaguard/experiments
GET  /api/alphaguard/experiments
GET  /api/alphaguard/experiments/{experiment_id}
POST /api/alphaguard/experiments/{experiment_id}/run
POST /api/alphaguard/experiments/{experiment_id}/promote
```

晋升接口必须要求人工确认和权限校验。

---

# 21. 调度与每日任务

## 21.1 交易日前

- 同步交易日历；
- 检查系统配置；
- 检查 MongoDB、Redis、模型供应商和数据源健康；
- 恢复未完成但可重试任务。

## 21.2 盘后数据阶段

```text
收盘
→ 行情同步
→ 财务/公告/新闻同步
→ 数据完整性等待
→ 市场状态计算
→ 候选池扫描
→ 生成 EvidenceSnapshot
→ 因子计算
→ 策略计算
```

## 21.3 决策阶段

```text
触发深度分析
→ TradingAgents 研究
→ 普通模型计划
→ 顶尖模型终审
→ Consensus
→ HardRisk
→ 生成 T+1 OrderIntent
```

## 21.4 次日执行阶段

```text
检查停牌和涨跌停
→ 激活订单
→ 日线撮合
→ 记录成交
→ 结算和更新持仓
→ 更新候选池持仓状态
```

## 21.5 评价阶段

- 每日更新 1D/5D/10D/20D 标签；
- 计算账户净值和回撤；
- 运行失败归因；
- 生成日报和异常告警。

## 21.6 幂等

每个任务必须包含：

```text
job_name
trade_date
symbol/account_id
version
idempotency_key
```

重复运行不得：

- 重复生成快照；
- 重复调用模型；
- 重复生成计划；
- 重复创建订单；
- 重复成交；
- 重复结算；
- 重复写入评价标签。

---

# 22. 前端页面

## 22.1 AlphaGuard 总览

显示：

- 系统模式；
- 服务健康；
- 当前交易日；
- 候选池数量；
- 今日触发数量；
- 待分析、待终审、已通过、已拒绝数量；
- 各模拟账户净值；
- 当前风险状态；
- 最近异常。

## 22.2 候选池

显示：

- 股票代码和名称；
- 来源标签；
- 当前状态；
- 最新信号；
- 市场状态；
- 下一检查时间；
- 是否持仓；
- 冷却状态；
- 最近快照和计划。

## 22.3 决策中心

按时间线展示：

```text
EvidenceSnapshot
→ QuantProposal
→ Agent 报告
→ NormalTradePlan
→ TopReview
→ Consensus
→ HardRisk
→ OrderIntent
```

应明确显示每一步为什么通过或失败。

## 22.4 自动模拟交易

显示：

- 多账户切换；
- 订单状态；
- 成交；
- 持仓批次；
- 可卖数量；
- 手续费；
- 净值；
- 回撤；
- 计划与订单关联。

## 22.5 评价中心

显示：

- Quant、Normal、Top Confirmed 对照；
- 顶尖模型确认和否决效果；
- 风控拦截效果；
- 因子分组表现；
- 市场状态分组表现；
- 失败归因分布；
- 未交易反事实结果。

## 22.6 实验室

显示：

- Champion；
- Challenger；
- 修改变量；
- 回测结果；
- 样本外结果；
- Shadow 状态；
- 挑战者模拟表现；
- 晋升审批。

---

# 23. 配置和版本管理

## 23.1 配置分层

```text
系统安全配置
市场交易规则
账户与组合风控
因子配置
策略配置
模型配置
Prompt 配置
调度配置
撮合配置
实验配置
```

## 23.2 禁止事项

- 不在代码中硬编码模型名称；
- 不在 Prompt 中硬编码仓位上限；
- 不在业务代码中写死手续费；
- 不覆盖旧策略版本；
- 不覆盖旧 Prompt；
- 不在运行时修改 Champion 配置；
- 不允许大模型写入生产配置。

## 23.3 审计链

每个最终订单必须能追溯：

```text
候选来源
→ 快照
→ 数据质量
→ 因子版本
→ 策略版本
→ Agent 报告
→ 普通模型和 Prompt 版本
→ 顶尖模型和 Prompt 版本
→ Consensus 规则版本
→ HardRisk 版本
→ OrderIntent
→ 撮合版本
→ 成交和费用
→ 后续评价和归因
```

---

# 24. 日志、监控和告警

## 24.1 结构化日志字段

```text
trace_id
snapshot_id
analysis_id
plan_id
review_id
consensus_id
risk_decision_id
intent_id
order_id
account_id
symbol
trade_date
job_id
```

## 24.2 关键告警

- 数据同步失败；
- DataQuality FAIL；
- 模型连续失败；
- Pydantic 校验失败；
- 同一幂等键产生多个对象；
- 订单重复；
- 账户现金为负；
- 持仓数量为负；
- T+1 违规；
- 系统意外进入实盘模式；
- Champion 配置被未授权修改；
- 撮合或结算不平衡。

---

# 25. 测试策略

## 25.1 单元测试

必须覆盖：

- 每个因子；
- 市场状态；
- 策略规则；
- Pydantic 校验；
- Consensus 状态组合；
- HardRisk 每条规则；
- 手续费；
- T+1；
- 100 股整数手；
- 持仓批次；
- 限价撮合；
- 涨跌停和停牌；
- 幂等键。

## 25.2 集成测试

完整路径：

```text
候选加入
→ 快照
→ 因子
→ 策略
→ 模型桩输出
→ Consensus
→ Risk
→ OrderIntent
→ 次日撮合
→ 持仓
→ 评价
```

## 25.3 模型测试

不得直接依赖真实模型完成 CI。应提供：

- 固定合法输出；
- 缺字段输出；
- 非法 JSON；
- 超时；
- 供应商异常；
- CONFIRM；
- RISK_ADJUST；
- MATERIAL_REVISION；
- REJECT。

## 25.4 回放测试

保存固定历史数据集，支持：

```bash
python scripts/replay_decision.py --snapshot-id xxx
```

相同代码和版本应产生一致的确定性计算结果。大模型结果则使用已保存输出或模型桩回放。

## 25.5 安全不变量

测试必须证明：

1. 模型失败不会创建订单；
2. 解析失败不会变成 HOLD 并继续；
3. target_price 为 null 不会导致自动猜价；
4. 未通过 Consensus 不会进入 HardRisk 后订单链路；
5. HardRisk REJECT 不会创建 OrderIntent；
6. T 日收盘决策不能在 T 日成交；
7. 同一 idempotency_key 不会重复下单；
8. `live_trading_enabled=False` 时无真实券商调用。

---

# 26. Codex 开发原则

Codex 不应一次性实现整个系统。必须按小步 PR/里程碑推进。

每个阶段要求：

1. 先读相关源码；
2. 输出改造计划和影响文件；
3. 只修改当前阶段范围；
4. 补充测试；
5. 运行测试和静态检查；
6. 更新 `docs/refactor/CODEX_EXECUTION_STATUS.md`；
7. 不顺手重构无关模块；
8. 不引入未经批准的大型依赖；
9. 不改变现有公开接口，除非提供兼容层；
10. 不删除原有人工模拟交易功能。

---

# 27. 分阶段实施计划

## PR-001：Baseline Guard

### 目标

建立可改造、可回退、可验证的稳定基线。

### 任务

- 读取项目结构；
- 验证后端、前端、MongoDB、Redis 可启动；
- 运行现有测试；
- 记录失败测试；
- 增加 AlphaGuard 配置：`system_mode`、`live_trading_enabled`；
- 增加安全启动校验；
- 创建 `docs/refactor/` 文档骨架；
- 创建 `CODEX_EXECUTION_STATUS.md`；
- 不改变交易逻辑。

### 验收

- 原系统可启动；
- 现有核心功能未破坏；
- 安全配置默认关闭实盘；
- 测试基线有记录；
- 所有改动可独立回退。

## PR-002：Structured Decision Foundation

### 目标

消除自由文本猜测、默认持有和目标价自动推算。

### 任务

- 新增 AlphaGuard decision schemas；
- 改造 Trader 输出 `NormalTradePlan`；
- 改造 Risk Judge 输出 `TopReviewDecision`；
- 改造 `AgentState`；
- 废弃 `SignalProcessor` 中默认持有和智能猜价；
- 模型失败、解析失败明确阻断；
- target_price 可空；
- 保存模型和 Prompt 版本；
- 提供旧接口兼容转换，但不得用于自动下单。

### 重点文件

```text
tradingagents/agents/trader/trader.py
tradingagents/agents/managers/risk_manager.py
tradingagents/agents/utils/agent_states.py
tradingagents/graph/signal_processing.py
tradingagents/graph/setup.py
tradingagents/graph/trading_graph.py
```

### 验收

- 合法结构化输出可通过；
- 非法输出被阻断；
- 空输出不再返回默认持有；
- 无目标价也可形成合法 WAIT/交易计划；
- 自动猜价代码不再参与决策。

## PR-003：Candidate Pool & EvidenceSnapshot

### 目标

建立统一入口和可复现数据快照。

### 任务

- CandidateEntry 和状态机；
- 同步 favorites 为 USER_SELECTED；
- 持仓强制加入；
- DataQualityGate；
- EvidenceSnapshot；
- snapshot_id 全链路传递；
- 新增候选池和快照 API；
- MongoDB 索引和迁移脚本。

### 验收

- 用户自选可进入候选池；
- 持仓无法被移出监控；
- 快照不可变；
- 数据质量 FAIL 阻断分析；
- 分析结果能追溯 snapshot_id。

## PR-004：Factor, Regime & Strategy Engine

### 目标

建立确定性量化证据和首个 Champion 策略。

### 任务

- FactorRegistry；
- 15～25 个因子；
- MarketRegimeEngine；
- StrategyRegistry；
- `SWING_TREND_PULLBACK_V1`；
- `POSITION_EXIT_V1`；
- QuantTradeProposal；
- 因子和策略版本化；
- 单元测试。

### 验收

- 同一快照重复计算结果一致；
- 无未来数据；
- 策略不直接创建订单；
- 因子可独立测试；
- 市场状态能控制策略启停。

## PR-005：Dual Model Consensus & Hard Risk

### 目标

完成双模型一致规则和 Python 最终准入。

### 任务

- ContextBuilder 将快照和 QuantProposal 注入 Agent；
- 普通模型与顶尖模型完整链路；
- ConsensusEngine；
- 一轮重大修改返回机制；
- HardRiskEngine；
- 风控规则配置；
- RiskDecision；
- 审计事件。

### 验收

- 只有双模型一致才可能通过；
- 顶尖模型只能确认、降险、否决或请求修改；
- 任何失败状态不创建订单；
- 风控可 REDUCE/REJECT；
- 风控不能改变方向。

## PR-006：Automatic Paper Trading

### 目标

建立独立于人工即时成交接口的自动模拟交易链路。

### 任务

- 多模拟账户；
- OrderIntent；
- OrderService；
- MatchingEngine；
- FeeEngine；
- Position lots；
- T+1；
- 涨跌停、停牌、部分成交、订单过期；
- SettlementService；
- 前端订单和持仓展示。

### 验收

- T 日决策最早 T+1 成交；
- 同一订单不重复执行；
- 账户资产守恒；
- 现金和持仓不为负；
- 四类自动账户使用统一规则；
- 人工模拟交易仍可用。

## PR-007：Evaluation & Attribution

### 目标

建立系统自我评价所需的全样本数据。

### 任务

- 1/5/10/20 日标签；
- MFE/MAE；
- 相对指数和行业收益；
- 未交易反事实；
- 多账户对照；
- 失败归因；
- 评价 API 和前端页面。

### 验收

- 已交易和未交易样本均可评价；
- 可比较 Quant、Normal、Top Confirmed；
- 可评价顶尖模型否决价值；
- 可评价 HardRisk 拦截价值；
- 每个结果可追溯版本。

## PR-008：Experiment Lab

### 目标

建立受控的 Champion/Challenger 迭代机制。

### 任务

- ExperimentRegistry；
- 历史重放；
- 时间序列样本外验证；
- Shadow；
- PAPER_CHALLENGER；
- Champion 对比报告；
- 人工晋升；
- 版本状态机。

### 验收

- Challenger 不影响 Champion；
- 未经人工批准不能晋升；
- 每个实验只记录明确变量；
- 可复现实验输入和结果；
- 可回退旧 Champion。

## PR-009：Front-end Integration & Operations

### 目标

形成可日常使用的 AlphaGuard 产品界面和运维能力。

### 任务

- 总览；
- 候选池；
- 决策时间线；
- 多账户模拟交易；
- 评价中心；
- 实验室；
- 告警、健康检查和权限；
- Docker Compose 验证。

### 验收

- 用户可从前端完成候选管理和查看全链路；
- 无法从前端开启未授权实盘；
- 所有关键异常可见；
- 一键启动开发环境。

---

# 28. MVP 完成定义

AlphaGuard MVP 只有同时满足以下条件才算完成：

1. 用户可以把 A 股或场内 ETF 加入候选池；
2. 持仓自动强制保留；
3. 系统可以创建不可变 EvidenceSnapshot；
4. 系统可以计算首批可解释因子和市场状态；
5. 至少一个 Champion 策略输出 QuantTradeProposal；
6. TradingAgents 读取同一快照完成研究；
7. 普通模型输出结构化完整计划；
8. 顶尖模型输出结构化风险终审；
9. ConsensusEngine 可以严格裁决；
10. HardRiskEngine 掌握最终准入；
11. 自动订单只能 T+1 执行；
12. 模拟交易处理 A 股主要交易约束；
13. 至少有 PAPER_QUANT、PAPER_NORMAL、PAPER_TOP_CONFIRMED、PAPER_CHALLENGER；
14. 已交易和未交易决策都有评价标签；
15. 可进行 Champion/Challenger 对照；
16. 所有交易可追溯到快照、模型、Prompt、策略和风控版本；
17. 真实交易始终关闭。

---

# 29. Codex 每次任务的标准输出格式

Codex 每个 PR 开始时应先输出：

```text
1. 当前目标
2. 已阅读的相关文件
3. 发现的现状和风险
4. 计划修改的文件
5. 明确不修改的范围
6. 数据迁移方案
7. 测试方案
8. 回退方案
```

完成后输出：

```text
1. 实际修改文件
2. 核心实现说明
3. 数据结构变化
4. API 变化
5. 测试结果
6. 尚未解决的问题
7. 下一阶段建议
8. CODEX_EXECUTION_STATUS.md 更新摘要
```

---

# 30. 第一条 Codex 总控指令

将本文件放入：

```text
docs/refactor/MASTER_IMPLEMENTATION_PLAN.md
```

然后向 Codex 下达：

```text
你正在改造 TradingAgents-CN，项目名称为 AlphaGuard。

先完整阅读：
1. docs/refactor/MASTER_IMPLEMENTATION_PLAN.md
2. README.md
3. docker-compose.yml
4. app/main.py
5. app/worker.py
6. tradingagents/graph/trading_graph.py
7. tradingagents/graph/setup.py
8. tradingagents/graph/signal_processing.py
9. tradingagents/agents/trader/trader.py
10. tradingagents/agents/managers/risk_manager.py
11. app/routers/paper.py
12. app/routers/favorites.py

本次只执行 PR-001 Baseline Guard，不得提前实现 PR-002 及后续功能。

要求：
- 先检查项目能否启动和测试现状；
- 建立 docs/refactor 文档目录；
- 新增 AlphaGuard 安全配置；
- 默认 system_mode=SIM_AUTONOMOUS；
- 默认 live_trading_enabled=false；
- 增加启动时安全校验；
- 不修改现有交易决策逻辑；
- 不重构无关代码；
- 不引入新数据库或大型依赖；
- 保留现有人工模拟交易；
- 建立 CODEX_EXECUTION_STATUS.md；
- 补充必要测试；
- 完成后运行测试并报告结果。

开始编码前，先输出：现状、风险、拟修改文件、测试方案和回退方案。
```

---

# 31. 最终原则

1. 候选池决定分析对象；
2. 数据快照保证可复现；
3. 因子和策略提供可验证证据；
4. TradingAgents 负责研究，不掌握执行权；
5. 普通模型先制定完整计划；
6. 顶尖模型做独立完整性和风险终审；
7. 两个模型必须认可同一最终方案；
8. Python ConsensusEngine 判断一致性；
9. Python HardRiskEngine 掌握最终准入；
10. 自动订单与人工即时成交彻底隔离；
11. T 日收盘决策最早 T+1 执行；
12. 所有已交易和未交易样本都必须保存；
13. 系统是否有效由对照账户和样本外结果证明；
14. 所有改进先做 Challenger，不能直接覆盖 Champion；
15. 大模型不得直接修改生产策略、风控或执行代码；
16. 第一版以稳定、可追溯、可评价为先，不追求功能数量；
17. 真实交易在明确批准前始终保持关闭。

---

# 32. 一句话总结

> AlphaGuard 是一个以 TradingAgents-CN 为产品和 AI 投研底座，以候选池和不可变证据快照控制研究范围，以可解释因子和程序化策略形成候选方案，以普通模型制定计划、顶尖模型终审风险、Python 完成一致性裁决和硬风控，并通过自动模拟交易、全样本评价及 Champion/Challenger 实验持续进化的股票研究与模拟交易系统。
