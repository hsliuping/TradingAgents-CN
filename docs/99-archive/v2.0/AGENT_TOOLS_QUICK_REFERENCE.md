# 交易复盘 Agent 工具配置快速参考

## 1️⃣ timing_analyst (时机分析师)

```python
AgentMetadata(
    id="timing_analyst",
    name="时机分析师",
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
    ],
    max_tool_calls=5,
    execution_order=10
)
```

**分析内容**: 交易时机、市场环境、技术指标

---

## 2️⃣ position_analyst (仓位分析师)

```python
AgentMetadata(
    id="position_analyst",
    name="仓位分析师",
    tools=[
        "get_stock_market_data_unified",
        "get_trade_records",
        "build_trade_info",
        "get_account_info",              # ⭐ 关键工具
        "get_market_snapshot_for_review"
    ],
    default_tools=[
        "build_trade_info",
        "get_account_info"               # ⭐ 默认调用
    ],
    max_tool_calls=5,
    execution_order=20
)
```

**分析内容**: 仓位大小、资金利用率、风险控制、加减仓策略

---

## 3️⃣ emotion_analyst (情绪分析师) ✨

```python
AgentMetadata(
    id="emotion_analyst",
    name="情绪分析师",
    tools=[
        "get_stock_news_unified",
        "get_stock_sentiment_unified",
        "get_trade_records",             # 🆕
        "build_trade_info",              # 🆕
        "get_account_info"               # 🆕
    ],
    default_tools=[
        "build_trade_info",
        "get_account_info"
    ],
    max_tool_calls=5,
    requires_tools=True,
    execution_order=30
)
```

**分析内容**: 追涨杀跌、贪婪恐惧、纪律执行、情绪控制

---

## 4️⃣ attribution_analyst (归因分析师)

```python
AgentMetadata(
    id="attribution_analyst",
    name="归因分析师",
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
    ],
    max_tool_calls=5,
    execution_order=40
)
```

**分析内容**: 收益归因、大盘因素、行业因素、个股因素

---

## 5️⃣ review_manager (复盘总结师) ✨

```python
AgentMetadata(
    id="review_manager",
    name="复盘总结师",
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
    requires_tools=True,
    execution_order=100
)
```

**分析内容**: 综合总结、优点识别、不足分析、改进建议

---

## 🔧 工具速查表

| 工具 ID | 功能 | 使用 Agent |
|--------|------|-----------|
| `get_trade_records` | 获取交易记录 | 所有 Agent |
| `build_trade_info` | 构建交易信息 | 所有 Agent |
| `get_account_info` | 获取账户信息 | 所有 Agent |
| `get_market_snapshot_for_review` | 获取市场快照 | timing, attribution, review_manager |
| `get_stock_market_data_unified` | 获取市场数据 | timing, position, attribution |
| `get_stockstats_indicators_report` | 获取技术指标 | timing |
| `get_china_market_overview` | 获取市场概览 | attribution |
| `get_stock_news_unified` | 获取新闻 | emotion |
| `get_stock_sentiment_unified` | 获取情绪 | emotion |

---

## 📊 工具调用统计

- **共享工具** (所有 Agent): 3 个
  - get_trade_records
  - build_trade_info
  - get_account_info

- **多个 Agent 使用**: 2 个
  - get_stock_market_data_unified (3 个 Agent)
  - get_market_snapshot_for_review (3 个 Agent)

- **单个 Agent 使用**: 4 个
  - get_stockstats_indicators_report
  - get_china_market_overview
  - get_stock_news_unified
  - get_stock_sentiment_unified

---

## ✅ 配置检查清单

- [x] 所有 Agent 都有 `tools` 列表
- [x] 所有 Agent 都有 `default_tools` 列表
- [x] 所有 Agent 的 `max_tool_calls >= 3`
- [x] emotion_analyst 和 review_manager 设置 `requires_tools=True`
- [x] 所有工具都在 ToolRegistry 中注册
- [x] 所有工具都有正确的 category
- [x] 单元测试全部通过

---

## 🚀 使用示例

### 调用工作流
```python
from app.services.trade_review_service import TradeReviewService

service = TradeReviewService()
result = await service.create_trade_review(
    user_id="user123",
    trade_ids=["trade1", "trade2"],
    code="688111",
    market="CN"
)
```

### 工作流自动调用工具
```
工作流启动
  ↓
timing_analyst 自动调用:
  - build_trade_info()
  - get_market_snapshot_for_review()
  ↓
position_analyst 自动调用:
  - build_trade_info()
  - get_account_info() ⭐
  ↓
emotion_analyst 自动调用:
  - build_trade_info()
  - get_account_info() ⭐
  ↓
attribution_analyst 自动调用:
  - build_trade_info()
  - get_market_snapshot_for_review()
  ↓
review_manager 自动调用:
  - build_trade_info()
  - get_account_info()
  ↓
返回完整报告
```

---

## 📚 相关文档

- [工具架构详解](./trade-review-tools-architecture.md)
- [完整迁移总结](./COMPLETE_AGENT_TOOLS_MIGRATION.md)
- [使用指南](../guides/trade-review-tools-usage.md)

