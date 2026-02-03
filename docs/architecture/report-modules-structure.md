# 分析报告模块结构说明

## 概述

TradingAgents-CN 采用**多智能体协作**的方式生成股票分析报告。系统实际保存 **9个主要报告模块**，但在前端展示时会拆分为更细粒度的视图，让用户可以看到完整的团队辩论过程。

## 报告生成流程

```
┌─────────────────────────────────────────────────────────────┐
│                    多智能体协作分析流程                        │
└─────────────────────────────────────────────────────────────┘

第一阶段：分析师团队（4个独立报告）
┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐
│ 📈 市场分析师 │  │ 💰 基本面分析师│  │ 💭 情绪分析师 │  │ 📰 新闻分析师 │
└──────┬───────┘  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘
       │                 │                 │                 │
       └─────────────────┴─────────────────┴─────────────────┘
                                 ↓
第二阶段：研究团队辩论（1个综合报告）
┌─────────────────────────────────────────────────────────────┐
│              🔬 研究团队决策（research_team_decision）          │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      │
│  │ 🐂 多头研究员 │  │ 🐻 空头研究员 │  │ 🔬 研究经理   │      │
│  │  bull_history│  │  bear_history│  │ judge_decision│      │
│  └──────────────┘  └──────────────┘  └──────────────┘      │
└─────────────────────────────────────────────────────────────┘
                                 ↓
第三阶段：交易团队（1个独立报告）
┌─────────────────────────────────────────────────────────────┐
│              💼 交易员计划（trader_investment_plan）           │
└─────────────────────────────────────────────────────────────┘
                                 ↓
第四阶段：风险管理团队辩论（1个综合报告）
┌─────────────────────────────────────────────────────────────┐
│           👔 风险管理决策（risk_management_decision）          │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      │
│  │ ⚡ 激进分析师 │  │ 🛡️ 保守分析师 │  │ ⚖️ 中性分析师 │      │
│  │ risky_history│  │  safe_history│  │neutral_history│      │
│  └──────────────┘  └──────────────┘  └──────────────┘      │
│                    ┌──────────────┐                         │
│                    │ 👔 投资组合   │                         │
│                    │   经理决策    │                         │
│                    │ judge_decision│                         │
│                    └──────────────┘                         │
└─────────────────────────────────────────────────────────────┘
                                 ↓
第五阶段：最终决策（1个独立报告）
┌─────────────────────────────────────────────────────────────┐
│              🎯 最终分析结果（final_trade_decision）           │
└─────────────────────────────────────────────────────────────┘
```

## 数据库保存结构

### MongoDB 文档结构

```json
{
  "analysis_id": "000001_20251014_120000",
  "stock_symbol": "000001",
  "market_type": "A股",
  "analysis_date": "2025-10-14",
  "timestamp": "2025-10-14T12:00:00Z",
  "status": "completed",
  "summary": "执行摘要...",
  "analysts": ["市场分析师", "基本面分析师", ...],
  "research_depth": 3,
  
  "reports": {
    // 第一阶段：分析师团队（4个独立报告）
    "market_report": "市场技术分析内容...",
    "fundamentals_report": "基本面分析内容...",
    "sentiment_report": "市场情绪分析内容...",
    "news_report": "新闻事件分析内容...",
    
    // 第二阶段：研究团队决策（1个综合报告）
    "research_team_decision": "研究经理的综合决策内容（包含多空辩论摘要）...",
    
    // 第三阶段：交易团队（1个独立报告）
    "trader_investment_plan": "交易员计划内容...",
    
    // 第四阶段：风险管理决策（1个综合报告）
    "risk_management_decision": "投资组合经理的综合决策内容（包含风险辩论摘要）...",
    
    // 第五阶段：最终决策（1个独立报告）
    "final_trade_decision": "最终分析结果内容...",
    
    // 可选：早期版本的投资建议
    "investment_plan": "投资建议内容..."
  }
}
```

### State 对象结构

在分析过程中，系统使用 `AgentState` 对象存储所有中间状态：

```python
class AgentState(MessagesState):
    # 基础信息
    company_of_interest: str
    trade_date: str
    sender: str
    
    # 第一阶段：分析师报告
    market_report: str
    sentiment_report: str
    news_report: str
    fundamentals_report: str
    
    # 第二阶段：研究团队辩论状态
    investment_debate_state: InvestDebateState  # 包含 bull_history, bear_history, judge_decision
    investment_plan: str  # 可选
    
    # 第三阶段：交易员计划
    trader_investment_plan: str
    
    # 第四阶段：风险管理团队辩论状态
    risk_debate_state: RiskDebateState  # 包含 risky_history, safe_history, neutral_history, judge_decision
    
    # 第五阶段：最终决策
    final_trade_decision: str
```

### 辩论状态结构

#### InvestDebateState（研究团队辩论）

```python
class InvestDebateState(TypedDict):
    bull_history: str        # 多头研究员的完整对话历史
    bear_history: str        # 空头研究员的完整对话历史
    history: str            # 整体对话历史
    current_response: str   # 最新回复
    judge_decision: str     # 研究经理的最终决策（保存到 research_team_decision）
    count: int             # 对话轮数
```

#### RiskDebateState（风险管理团队辩论）

```python
class RiskDebateState(TypedDict):
    risky_history: str              # 激进分析师的完整对话历史
    safe_history: str               # 保守分析师的完整对话历史
    neutral_history: str            # 中性分析师的完整对话历史
    history: str                    # 整体对话历史
    latest_speaker: str             # 最后发言的分析师
    current_risky_response: str     # 激进分析师的最新回复
    current_safe_response: str      # 保守分析师的最新回复
    current_neutral_response: str   # 中性分析师的最新回复
    judge_decision: str             # 投资组合经理的最终决策（保存到 risk_management_decision）
    count: int                      # 对话轮数
```

## 前端展示逻辑

### 报告模块映射

前端定义了13个展示模块，但实际从9个保存的报告中读取数据：

```typescript
const nameMap: Record<string, string> = {
  // 第一阶段：分析师团队（4个独立报告）
  market_report: '📈 市场技术分析',
  sentiment_report: '💭 市场情绪分析',
  news_report: '📰 新闻事件分析',
  fundamentals_report: '💰 基本面分析',

  // 第二阶段：研究团队（从 research_team_decision 拆分展示）
  bull_researcher: '🐂 多头研究员',           // 从 investment_debate_state.bull_history 提取
  bear_researcher: '🐻 空头研究员',           // 从 investment_debate_state.bear_history 提取
  research_team_decision: '🔬 研究经理决策',  // 从 investment_debate_state.judge_decision 提取

  // 第三阶段：交易团队（1个独立报告）
  trader_investment_plan: '💼 交易员计划',

  // 第四阶段：风险管理团队（从 risk_management_decision 拆分展示）
  risky_analyst: '⚡ 激进分析师',                    // 从 risk_debate_state.risky_history 提取
  safe_analyst: '🛡️ 保守分析师',                    // 从 risk_debate_state.safe_history 提取
  neutral_analyst: '⚖️ 中性分析师',                  // 从 risk_debate_state.neutral_history 提取
  risk_management_decision: '👔 投资组合经理',       // 从 risk_debate_state.judge_decision 提取

  // 第五阶段：最终决策（1个独立报告）
  final_trade_decision: '🎯 最终分析结果',

  // 兼容旧字段
  investment_plan: '📋 投资建议',
  investment_debate_state: '🔬 研究团队决策（旧）',
  risk_debate_state: '⚖️ 风险管理团队（旧）'
}
```

### 展示逻辑说明

1. **独立报告**（7个）：直接从 `reports` 对象中读取
   - market_report
   - fundamentals_report
   - sentiment_report
   - news_report
   - trader_investment_plan
   - final_trade_decision
   - investment_plan（可选）

2. **综合报告**（2个）：需要拆分展示
   - **research_team_decision**：包含多头/空头/研究经理的观点
   - **risk_management_decision**：包含激进/保守/中性/投资组合经理的观点

3. **前端拆分展示**：
   - 前端可以选择直接展示综合报告（1个模块）
   - 或者拆分展示各个角色的观点（3个或4个子模块）
   - 目前前端代码支持两种展示方式，通过字段名映射实现

## 报告内容说明

### 第一阶段：分析师团队（4个报告）

#### 1. 📈 市场技术分析（market_report）
- K线/技术指标与趋势判断
- 支撑阻力位与形态识别
- 市场情绪、资金流向与板块表现
- 阶段性买卖时机评估

#### 2. 💰 基本面分析（fundamentals_report）
- 财务数据分析
- 盈利能力评估
- 成长性分析
- 估值分析

#### 3. 💭 市场情绪分析（sentiment_report）
- 社交媒体与社区舆情监测
- 热点传播强度与扩散路径
- 短期情绪对股价的可能影响

#### 4. 📰 新闻事件分析（news_report）
- 相关新闻汇总
- 事件影响评估与新闻情绪
- 风险与不确定性提示

### 第二阶段：研究团队决策（1个综合报告）

#### 5. 🔬 研究团队决策（research_team_decision）

这个报告是研究经理的综合决策，通常会包含：
- 多头研究员的主要观点摘要
- 空头研究员的主要观点摘要
- 研究经理综合两方观点后的最终判断
- 投资建议初步结论

**注意**：完整的辩论历史存储在 `investment_debate_state` 中，但不直接保存到 `reports` 字段。

### 第三阶段：交易团队（1个报告）

#### 6. 💼 交易员计划（trader_investment_plan）
- 具体交易策略
- 仓位管理建议
- 买卖时机规划
- 止损止盈设置

### 第四阶段：风险管理团队决策（1个综合报告）

#### 7. 👔 风险管理决策（risk_management_decision）

这个报告是投资组合经理的综合决策，通常会包含：
- 激进分析师的主要观点摘要
- 保守分析师的主要观点摘要
- 中性分析师的主要观点摘要
- 投资组合经理综合三方观点后的最终决策
- 最终风险等级和投资组合建议

**注意**：完整的辩论历史存储在 `risk_debate_state` 中，但不直接保存到 `reports` 字段。

### 第五阶段：最终决策（1个报告）

#### 8. 🎯 最终分析结果（final_trade_decision）
- 综合所有团队分析
- 最终投资建议
- 置信度评分
- 风险等级
- 执行计划

### 可选报告

#### 9. 📋 投资建议（investment_plan）
- 早期版本的投资建议
- 部分报告可能包含此字段
- 在有研究团队决策时，此字段可能为空

## 分析深度与报告数量

不同的分析深度会生成不同数量的报告：

| 分析深度 | 报告数量 | 包含的报告 |
|---------|---------|-----------|
| 深度 1 | 4-5个 | 分析师团队报告 + 投资建议 |
| 深度 2 | 6-7个 | 深度1 + 研究团队决策 + 交易员计划 |
| 深度 3 | 8-9个 | 深度2 + 风险管理决策 + 最终分析结果 |

## 技术实现

### 后端保存逻辑

**文件**：`app/services/simple_analysis_service.py` (第2036-2092行)

```python
# 从 state 中提取报告内容
report_fields = [
    'market_report',
    'sentiment_report',
    'news_report',
    'fundamentals_report',
    'investment_plan',
    'trader_investment_plan',
    'final_trade_decision'
]

# 处理辩论状态报告
if 'investment_debate_state' in state:
    debate_state = state['investment_debate_state']
    reports['research_team_decision'] = debate_state['judge_decision']

if 'risk_debate_state' in state:
    risk_state = state['risk_debate_state']
    reports['risk_management_decision'] = risk_state['judge_decision']
```

### 前端展示逻辑

**文件**：`frontend/src/views/Reports/ReportDetail.vue` (第589-624行)

```typescript
const getModuleDisplayName = (moduleName: string) => {
  const nameMap: Record<string, string> = {
    // 映射13个展示模块到9个保存的报告
    // ...
  }
  return nameMap[moduleName] || moduleName.replace(/_/g, ' ')
}
```

## 总结

- **保存层面**：系统实际保存 **9个主要报告模块**
- **展示层面**：前端可以展示为 **13个细分模块**
- **核心设计**：研究团队决策和风险管理决策是综合报告，包含了各个角色的观点和最终决策
- **灵活性**：前端可以选择展示综合报告或拆分展示各个角色的观点
- **可扩展性**：未来可以根据需要调整展示粒度，而不需要修改后端保存逻辑

这种设计既保证了数据的完整性，又提供了灵活的展示方式，让用户可以根据需要查看不同层次的分析内容。

