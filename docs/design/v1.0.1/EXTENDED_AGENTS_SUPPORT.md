# 提示词模版系统 - 扩展支持所有Agent

## 📊 完整Agent体系

### 1. 分析师 (Analysts) - 4个
- **基本面分析师** (fundamentals_analyst)
- **市场分析师** (market_analyst)
- **新闻分析师** (news_analyst)
- **社媒分析师** (social_media_analyst)

### 2. 研究员 (Researchers) - 2个
- **看涨研究员** (bull_researcher)
- **看跌研究员** (bear_researcher)

### 3. 风险管理 (Risk Management) - 3个
- **激进辩手** (aggressive_debator)
- **保守辩手** (conservative_debator)
- **中立辩手** (neutral_debator)

### 4. 管理者 (Managers) - 2个
- **研究经理** (research_manager)
- **风险经理** (risk_manager)

### 5. 交易员 (Trader) - 1个
- **交易员** (trader)

**总计: 13个Agent**

---

## 🎯 Agent分类和模版规划

### 分析师类Agent (6个)
**特点**: 使用工具进行数据分析，生成分析报告

| Agent | 模版数 | 模版类型 |
|-------|--------|---------|
| fundamentals_analyst | 3 | default, conservative, aggressive |
| market_analyst | 3 | default, short_term, long_term |
| news_analyst | 3 | default, real_time, deep |
| social_media_analyst | 3 | default, sentiment_focus, trend_focus |
| bull_researcher | 3 | default, optimistic, moderate |
| bear_researcher | 3 | default, pessimistic, moderate |

### 辩手类Agent (3个)
**特点**: 参与辩论，评估和反驳观点

| Agent | 模版数 | 模版类型 |
|-------|--------|---------|
| aggressive_debator | 2 | default, extreme |
| conservative_debator | 2 | default, cautious |
| neutral_debator | 2 | default, balanced |

### 管理者类Agent (2个)
**特点**: 综合分析，做出决策

| Agent | 模版数 | 模版类型 |
|-------|--------|---------|
| research_manager | 2 | default, strict |
| risk_manager | 2 | default, strict |

### 交易员类Agent (1个)
**特点**: 做出交易决策

| Agent | 模版数 | 模版类型 |
|-------|--------|---------|
| trader | 3 | default, conservative, aggressive |

---

## 📁 扩展的目录结构

```
prompts/
├── templates/
│   ├── analysts/
│   │   ├── fundamentals/
│   │   │   ├── default.yaml
│   │   │   ├── conservative.yaml
│   │   │   └── aggressive.yaml
│   │   ├── market/
│   │   │   ├── default.yaml
│   │   │   ├── short_term.yaml
│   │   │   └── long_term.yaml
│   │   ├── news/
│   │   │   ├── default.yaml
│   │   │   ├── real_time.yaml
│   │   │   └── deep.yaml
│   │   └── social/
│   │       ├── default.yaml
│   │       ├── sentiment_focus.yaml
│   │       └── trend_focus.yaml
│   ├── researchers/
│   │   ├── bull/
│   │   │   ├── default.yaml
│   │   │   ├── optimistic.yaml
│   │   │   └── moderate.yaml
│   │   └── bear/
│   │       ├── default.yaml
│   │       ├── pessimistic.yaml
│   │       └── moderate.yaml
│   ├── debators/
│   │   ├── aggressive/
│   │   │   ├── default.yaml
│   │   │   └── extreme.yaml
│   │   ├── conservative/
│   │   │   ├── default.yaml
│   │   │   └── cautious.yaml
│   │   └── neutral/
│   │       ├── default.yaml
│   │       └── balanced.yaml
│   ├── managers/
│   │   ├── research/
│   │   │   ├── default.yaml
│   │   │   └── strict.yaml
│   │   └── risk/
│   │       ├── default.yaml
│   │       └── strict.yaml
│   └── trader/
│       ├── default.yaml
│       ├── conservative.yaml
│       └── aggressive.yaml
└── schema/
    └── prompt_template_schema.json
```

---

## 🔄 Agent分类体系

### 按功能分类

**数据收集型** (使用工具获取数据):
- fundamentals_analyst
- market_analyst
- news_analyst
- social_media_analyst

**分析型** (基于数据进行分析):
- bull_researcher
- bear_researcher

**决策型** (做出决策):
- research_manager
- risk_manager
- trader

**评估型** (评估和反驳):
- aggressive_debator
- conservative_debator
- neutral_debator

### 按工作流分类

**第1阶段 - 数据收集**:
- fundamentals_analyst
- market_analyst
- news_analyst
- social_media_analyst

**第2阶段 - 观点生成**:
- bull_researcher
- bear_researcher

**第3阶段 - 风险评估**:
- aggressive_debator
- conservative_debator
- neutral_debator

**第4阶段 - 决策制定**:
- research_manager
- risk_manager
- trader

---

## 🎯 模版变量标准化

所有Agent的模版都支持以下标准变量:

### 基础变量
- `{ticker}` - 股票代码
- `{company_name}` - 公司名称
- `{market_name}` - 市场名称 (A股/港股/美股)
- `{currency_name}` - 货币名称 (CNY/HKD/USD)
- `{currency_symbol}` - 货币符号 (¥/HK$/US$)

### 时间变量
- `{current_date}` - 当前日期
- `{start_date}` - 分析开始日期
- `{end_date}` - 分析结束日期

### 数据变量
- `{market_report}` - 市场分析报告
- `{sentiment_report}` - 情绪分析报告
- `{news_report}` - 新闻分析报告
- `{fundamentals_report}` - 基本面分析报告
- `{investment_plan}` - 投资计划
- `{trader_decision}` - 交易员决策

### 辩论变量
- `{history}` - 辩论历史
- `{current_response}` - 当前回应
- `{bull_history}` - 看涨历史
- `{bear_history}` - 看跌历史
- `{risky_history}` - 激进历史
- `{safe_history}` - 保守历史
- `{neutral_history}` - 中立历史

---

## 📋 模版YAML结构 (扩展)

```yaml
version: "1.0"
agent_type: "fundamentals_analyst"  # 改为agent_type
agent_category: "analyst"           # 新增: agent分类
name: "基本面分析 - 默认模版"
description: "标准的基本面分析提示词"

# 核心提示词
system_prompt: |
  你是一位专业的股票基本面分析师。
  任务：分析{company_name}（股票代码：{ticker}）

# Agent特定的指导
tool_guidance: |
  立即调用 get_stock_fundamentals_unified 工具

# 分析要求
analysis_requirements: |
  - 财务数据分析
  - 估值指标分析

# 输出格式
output_format: |
  # 公司基本信息
  ## 财务数据分析

# 约束条件
constraints:
  forbidden:
    - "不允许假设数据"
  required:
    - "必须调用工具"

# 标签
tags:
  - "fundamental"
  - "analysis"

# 是否为默认模版
is_default: true

# 适用的Agent类型
applicable_agents:
  - "fundamentals_analyst"
```

---

## 🔌 集成方式

### 方式1: 创建Agent时指定模版
```python
from tradingagents.agents import create_fundamentals_analyst

analyst = create_fundamentals_analyst(
    llm=llm,
    toolkit=toolkit,
    template_name="conservative"
)
```

### 方式2: 在工作流中动态选择
```python
from tradingagents.config.prompt_manager import PromptTemplateManager

manager = PromptTemplateManager()
template = manager.load_template("fundamentals_analyst", "conservative")

analyst = create_fundamentals_analyst(
    llm=llm,
    toolkit=toolkit,
    template_name="conservative"
)
```

### 方式3: 通过API选择
```bash
POST /api/analysis
{
  "ticker": "000001",
  "agent_templates": {
    "fundamentals_analyst": "conservative",
    "market_analyst": "short_term",
    "bull_researcher": "optimistic",
    "bear_researcher": "moderate",
    "aggressive_debator": "default",
    "conservative_debator": "cautious",
    "neutral_debator": "balanced",
    "research_manager": "default",
    "risk_manager": "strict",
    "trader": "conservative"
  }
}
```

---

## 📊 实现优先级

### Phase 1 (高优先级) - 核心Agent
- fundamentals_analyst
- market_analyst
- news_analyst
- social_media_analyst
- trader

### Phase 2 (中优先级) - 研究和管理
- bull_researcher
- bear_researcher
- research_manager
- risk_manager

### Phase 3 (低优先级) - 辩手
- aggressive_debator
- conservative_debator
- neutral_debator

---

## 🎯 关键设计决策

1. **统一的模版管理**: 所有Agent使用同一个PromptTemplateManager
2. **灵活的分类**: 支持按功能、工作流等多种分类方式
3. **标准化变量**: 所有Agent共享标准变量集合
4. **向后兼容**: 默认模版保持现有行为
5. **渐进式实现**: 可以分阶段实现不同Agent的模版支持

