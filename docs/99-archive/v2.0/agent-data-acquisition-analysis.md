# 交易复盘 Agent 数据获取方式分析

## 概述

交易复盘工作流包含 5 个 Agent 节点，每个 Agent 的数据获取方式不同。本文分析各 Agent 是否需要转化为工具系统。

## Agent 节点分析

### 1. timing_analyst (时机分析师) ✅ 已转化

**执行顺序**: 10  
**数据来源**: 
- `trade_info` - 从工作流输入获取
- `market_data` - 从工作流输入获取
- 通过工具调用获取额外数据

**工具绑定**:
```python
tools=[
    "get_stock_market_data_unified",
    "get_stockstats_indicators_report",
    "get_trade_records",
    "build_trade_info",
    "get_market_snapshot_for_review"
],
default_tools=[
    "get_stock_market_data_unified",
    "build_trade_info"
]
```

**状态**: ✅ 已支持 v2.0 工具系统

---

### 2. position_analyst (仓位分析师) ✅ 已转化

**执行顺序**: 20  
**数据来源**:
- `trade_info` - 从工作流输入获取
- 通过工具调用获取账户信息 ⭐

**工具绑定**:
```python
tools=[
    "get_stock_market_data_unified",
    "get_trade_records",
    "build_trade_info",
    "get_account_info",
    "get_market_snapshot_for_review"
],
default_tools=[
    "build_trade_info",
    "get_account_info"
]
```

**状态**: ✅ 已支持 v2.0 工具系统

---

### 3. emotion_analyst (情绪分析师) ⚠️ 需要转化

**执行顺序**: 30  
**当前数据获取方式**:
- 直接从 `state` 获取 `trade_info` 和 `market_data`
- 不调用任何工具
- 数据完全依赖工作流输入

**当前工具配置**:
```python
tools=["get_stock_news_unified", "get_stock_sentiment_unified"],
max_tool_calls=3,
requires_tools=False  # ⚠️ 不需要工具
```

**问题**:
- 无法获取账户信息（现金、持仓市值等）
- 无法获取交易记录详情
- 无法进行量化的情绪分析

**建议转化**:
```python
tools=[
    "get_stock_news_unified",
    "get_stock_sentiment_unified",
    "get_trade_records",
    "build_trade_info",
    "get_account_info"
],
default_tools=[
    "build_trade_info",
    "get_account_info"
],
max_tool_calls=5,
requires_tools=True
```

---

### 4. attribution_analyst (归因分析师) ✅ 已转化

**执行顺序**: 40  
**数据来源**:
- `trade_info` - 从工作流输入获取
- 通过工具调用获取市场数据

**工具绑定**:
```python
tools=[
    "get_stock_market_data_unified",
    "get_china_market_overview",
    "get_trade_records",
    "build_trade_info",
    "get_market_snapshot_for_review"
],
default_tools=[
    "get_stock_market_data_unified",
    "build_trade_info"
]
```

**状态**: ✅ 已支持 v2.0 工具系统

---

### 5. review_manager (复盘总结师) ⚠️ 需要转化

**执行顺序**: 100  
**当前数据获取方式**:
- 直接从 `state` 获取所有分析结果
- 不调用任何工具
- 数据完全依赖前面 Agent 的输出

**当前工具配置**:
```python
tools=[],
max_tool_calls=0,
requires_tools=False  # ⚠️ 不需要工具
```

**问题**:
- 无法验证前面 Agent 的分析结果
- 无法获取原始数据进行交叉验证
- 无法进行独立的数据分析

**建议转化**:
```python
tools=[
    "get_trade_records",
    "build_trade_info",
    "get_account_info",
    "get_market_snapshot_for_review"
],
default_tools=[
    "build_trade_info",
    "get_account_info"
],
max_tool_calls=5,
requires_tools=True
```

---

## 总结表

| Agent | 执行顺序 | 当前状态 | 需要转化 | 优先级 |
|------|--------|--------|--------|------|
| timing_analyst | 10 | ✅ 已转化 | ❌ 否 | - |
| position_analyst | 20 | ✅ 已转化 | ❌ 否 | - |
| emotion_analyst | 30 | ⚠️ 部分 | ✅ 是 | 🔴 高 |
| attribution_analyst | 40 | ✅ 已转化 | ❌ 否 | - |
| review_manager | 100 | ❌ 未转化 | ✅ 是 | 🟡 中 |

---

## 建议实施计划

### Phase 1: emotion_analyst (高优先级)
- 添加 `get_trade_records` 工具
- 添加 `build_trade_info` 工具
- 添加 `get_account_info` 工具
- 更新提示词以使用工具获取数据
- 预期效果: 情绪分析可以基于完整的账户和交易数据

### Phase 2: review_manager (中优先级)
- 添加数据验证工具
- 添加交叉验证能力
- 支持独立数据分析
- 预期效果: 总结报告更加准确和全面

---

## 相关文档

- [交易复盘工具架构](./trade-review-tools-architecture.md)
- [实现总结](./IMPLEMENTATION_SUMMARY.md)

