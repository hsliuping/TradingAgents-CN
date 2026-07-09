# 交易复盘工作流 Agent 中文名称总结

## 📌 直接回答

你提到的工作流中各 Agent 的中文名称如下：

```
Agent 工作流
  ├─ timing_analyst              → ⏰ 时机分析师
  │  ├─ build_trade_info() 工具
  │  └─ get_market_snapshot_for_review() 工具
  │
  ├─ position_analyst            → 📊 仓位分析师
  │  ├─ build_trade_info() 工具
  │  └─ get_account_info() 工具 ⭐
  │
  ├─ emotion_analyst             → 🧠 情绪分析师
  │  ├─ build_trade_info() 工具
  │  └─ get_account_info() 工具 ⭐
  │
  ├─ attribution_analyst         → 🎯 归因分析师
  │  ├─ build_trade_info() 工具
  │  └─ get_market_snapshot_for_review() 工具
  │
  └─ review_manager              → 📝 复盘总结师
     ├─ build_trade_info() 工具
     └─ get_account_info() 工具
```

---

## 🎯 Agent 中文名称速查表

| Agent ID | 中文名称 | 图标 | 类别 |
|---------|--------|------|------|
| `timing_analyst` | **时机分析师** | ⏰ | 分析师 |
| `position_analyst` | **仓位分析师** | 📊 | 分析师 |
| `emotion_analyst` | **情绪分析师** | 🧠 | 分析师 |
| `attribution_analyst` | **归因分析师** | 🎯 | 分析师 |
| `review_manager` | **复盘总结师** | 📝 | 管理者 |

---

## 📊 各 Agent 的核心职责

### ⏰ 时机分析师 (timing_analyst)
- 分析买入卖出时机的合理性
- 评估市场环境和技术指标支持度

### 📊 仓位分析师 (position_analyst)
- 分析仓位控制和加减仓策略
- 评估资金利用效率和风险控制水平 ⭐

### 🧠 情绪分析师 (emotion_analyst)
- 分析交易中的情绪化操作
- 评估纪律执行情况 ⭐

### 🎯 归因分析师 (attribution_analyst)
- 分析收益来源（大盘/行业/个股）
- 区分 Alpha 贡献度

### 📝 复盘总结师 (review_manager)
- 综合所有分析维度
- 生成完整复盘报告和改进建议

---

## 🔑 关键工具

### ⭐ 核心工具（解决关键问题）

| 工具 | 功能 | 使用 Agent |
|------|------|-----------|
| `get_account_info` | 获取账户信息 | 仓位、情绪、总结 |
| `build_trade_info` | 构建交易信息 | 全部 |

### 📊 数据工具

| 工具 | 功能 | 使用 Agent |
|------|------|-----------|
| `get_market_snapshot_for_review` | 获取市场快照 | 时机、归因、总结 |
| `get_stock_market_data_unified` | 获取市场数据 | 时机、仓位、归因 |
| `get_trade_records` | 获取交易记录 | 总结 |

### 📰 分析工具

| 工具 | 功能 | 使用 Agent |
|------|------|-----------|
| `get_stock_news_unified` | 获取新闻 | 情绪 |
| `get_stock_sentiment_unified` | 获取情绪 | 情绪 |
| `get_stockstats_indicators_report` | 获取技术指标 | 时机 |
| `get_china_market_overview` | 获取市场概览 | 归因 |

---

## 💡 使用示例

### 在代码中引用

```python
# 获取 Agent 配置
from core.agents.config import AGENTS_CONFIG

# 时机分析师
timing_agent = AGENTS_CONFIG["timing_analyst"]
print(timing_agent.name)  # 输出: "时机分析师"

# 仓位分析师
position_agent = AGENTS_CONFIG["position_analyst"]
print(position_agent.name)  # 输出: "仓位分析师"

# 情绪分析师
emotion_agent = AGENTS_CONFIG["emotion_analyst"]
print(emotion_agent.name)  # 输出: "情绪分析师"

# 归因分析师
attribution_agent = AGENTS_CONFIG["attribution_analyst"]
print(attribution_agent.name)  # 输出: "归因分析师"

# 复盘总结师
review_agent = AGENTS_CONFIG["review_manager"]
print(review_agent.name)  # 输出: "复盘总结师"
```

### 在日志中显示

```python
logger.info(f"🚀 启动 {agent.name} 进行分析...")
# 输出: 🚀 启动 时机分析师 进行分析...
# 输出: 🚀 启动 仓位分析师 进行分析...
# 输出: 🚀 启动 情绪分析师 进行分析...
# 输出: 🚀 启动 归因分析师 进行分析...
# 输出: 🚀 启动 复盘总结师 进行分析...
```

---

## 📚 相关文档

- [Agent 工具配置快速参考](./AGENT_TOOLS_QUICK_REFERENCE.md)
- [Agent 名称对照表](./AGENT_NAMES_MAPPING.md)
- [完整迁移总结](./COMPLETE_AGENT_TOOLS_MIGRATION.md)
- [最终总结](./FINAL_SUMMARY.md)

---

## ✅ 总结

交易复盘工作流中的 5 个 Agent 的中文名称分别是：

1. **⏰ 时机分析师** (timing_analyst)
2. **📊 仓位分析师** (position_analyst)
3. **🧠 情绪分析师** (emotion_analyst)
4. **🎯 归因分析师** (attribution_analyst)
5. **📝 复盘总结师** (review_manager)

所有 Agent 都已支持 v2.0 工具系统，可以通过工具获取完整的数据进行分析。

