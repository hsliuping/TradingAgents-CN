# 交易复盘 Agent 名称对照表

## 📋 Agent ID 与中文名称映射

| Agent ID | 中文名称 | 图标 | 执行顺序 | 类别 |
|---------|--------|------|--------|------|
| `timing_analyst` | **时机分析师** | ⏰ | 10 | ANALYST |
| `position_analyst` | **仓位分析师** | 📊 | 20 | ANALYST |
| `emotion_analyst` | **情绪分析师** | 🧠 | 30 | ANALYST |
| `attribution_analyst` | **归因分析师** | 🎯 | 40 | ANALYST |
| `review_manager` | **复盘总结师** | 📝 | 100 | MANAGER |

---

## 🎯 各 Agent 职责

### ⏰ 时机分析师 (timing_analyst)

**职责**: 分析买入卖出时机，评估交易时机选择的合理性

**分析内容**:
- 买入时机是否合理
- 卖出时机是否合理
- 市场环境评估
- 技术指标支持度

**使用工具**:
- `get_stock_market_data_unified` - 获取市场数据
- `get_stockstats_indicators_report` - 获取技术指标
- `build_trade_info` - 构建交易信息
- `get_market_snapshot_for_review` - 获取市场快照

---

### 📊 仓位分析师 (position_analyst)

**职责**: 分析仓位控制和加减仓策略的合理性

**分析内容**:
- 初始仓位是否合理
- 加减仓策略是否合理
- 资金利用效率
- 风险控制水平

**使用工具**:
- `get_stock_market_data_unified` - 获取市场数据
- `build_trade_info` - 构建交易信息
- `get_account_info` ⭐ - 获取账户信息（关键）
- `get_market_snapshot_for_review` - 获取市场快照

---

### 🧠 情绪分析师 (emotion_analyst)

**职责**: 分析交易中的情绪化操作和纪律执行情况

**分析内容**:
- 是否存在追涨杀跌
- 是否存在贪婪恐惧
- 纪律执行情况
- 情绪控制水平

**使用工具**:
- `get_stock_news_unified` - 获取新闻数据
- `get_stock_sentiment_unified` - 获取情绪数据
- `build_trade_info` - 构建交易信息
- `get_account_info` ⭐ - 获取账户信息（关键）

---

### 🎯 归因分析师 (attribution_analyst)

**职责**: 分析收益来源，区分大盘/行业/个股Alpha贡献

**分析内容**:
- 收益来自大盘还是个股
- 行业因素的影响
- Alpha 贡献度
- 风险调整后的收益

**使用工具**:
- `get_stock_market_data_unified` - 获取市场数据
- `get_china_market_overview` - 获取市场概览
- `build_trade_info` - 构建交易信息
- `get_market_snapshot_for_review` - 获取市场快照

---

### 📝 复盘总结师 (review_manager)

**职责**: 综合所有分析维度，生成完整复盘报告和改进建议

**分析内容**:
- 综合总结所有分析
- 识别优点和不足
- 提出改进建议
- 生成最终报告

**使用工具**:
- `build_trade_info` - 构建交易信息
- `get_account_info` - 获取账户信息
- `get_trade_records` - 获取交易记录
- `get_market_snapshot_for_review` - 获取市场快照

---

## 🔄 工作流执行顺序

```
1️⃣ 时机分析师 (⏰ timing_analyst)
   ↓
2️⃣ 仓位分析师 (📊 position_analyst)
   ↓
3️⃣ 情绪分析师 (🧠 emotion_analyst)
   ↓
4️⃣ 归因分析师 (🎯 attribution_analyst)
   ↓
5️⃣ 复盘总结师 (📝 review_manager)
```

---

## 📊 工具使用统计

### 按 Agent 统计

| Agent | 工具数 | 默认工具 |
|------|-------|--------|
| 时机分析师 | 5 | 2 |
| 仓位分析师 | 5 | 2 |
| 情绪分析师 | 5 | 2 |
| 归因分析师 | 5 | 2 |
| 复盘总结师 | 4 | 2 |

### 按工具统计

| 工具 | 使用 Agent 数 | 使用 Agent |
|------|-------------|----------|
| `build_trade_info` | 5 | 全部 |
| `get_account_info` | 3 | 仓位、情绪、总结 |
| `get_market_snapshot_for_review` | 3 | 时机、归因、总结 |
| `get_stock_market_data_unified` | 3 | 时机、仓位、归因 |
| `get_stock_news_unified` | 1 | 情绪 |
| `get_stock_sentiment_unified` | 1 | 情绪 |
| `get_stockstats_indicators_report` | 1 | 时机 |
| `get_china_market_overview` | 1 | 归因 |
| `get_trade_records` | 1 | 总结 |

---

## 🏷️ Agent 标签

| Agent | 标签 |
|------|------|
| 时机分析师 | 复盘, 时机, 买卖点 |
| 仓位分析师 | 复盘, 仓位, 资金管理 |
| 情绪分析师 | 复盘, 情绪, 纪律 |
| 归因分析师 | 复盘, 归因, Alpha |
| 复盘总结师 | 复盘, 总结, 建议 |

---

## 💡 快速参考

```python
# 时机分析师
"timing_analyst" → "时机分析师" (⏰)

# 仓位分析师
"position_analyst" → "仓位分析师" (📊)

# 情绪分析师
"emotion_analyst" → "情绪分析师" (🧠)

# 归因分析师
"attribution_analyst" → "归因分析师" (🎯)

# 复盘总结师
"review_manager" → "复盘总结师" (📝)
```

---

## 📚 相关文档

- [Agent 工具配置快速参考](./AGENT_TOOLS_QUICK_REFERENCE.md)
- [完整迁移总结](./COMPLETE_AGENT_TOOLS_MIGRATION.md)
- [最终总结](./FINAL_SUMMARY.md)

