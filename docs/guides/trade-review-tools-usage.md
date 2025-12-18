# 交易复盘工具使用指南

## 概述

交易复盘工具集是 v2.0 工具系统的一部分，提供了完整的数据获取和分析功能。这些工具由 Agent 自动调用，无需手动干预。

## 核心工具

### 1. get_trade_records - 获取交易记录

**用途**: 从数据库获取用户的交易记录

**参数**:
- `user_id` (必需): 用户ID
- `trade_ids` (必需): 交易ID列表
- `source` (可选): 数据源，'real'(真实持仓) 或 'paper'(模拟交易)，默认 'real'

**返回值**:
```python
{
    "success": True,
    "data": [
        {
            "_id": "交易ID",
            "code": "688111",
            "market": "CN",
            "side": "buy",
            "quantity": 100,
            "price": 100.0,
            "amount": 10000.0,
            "timestamp": "2025-01-01T10:00:00"
        }
    ],
    "count": 1,
    "source": "real"
}
```

### 2. build_trade_info - 构建交易信息

**用途**: 从交易记录构建完整的交易信息对象

**参数**:
- `trade_records` (必需): 交易记录列表
- `code` (可选): 股票代码

**返回值**:
```python
{
    "success": True,
    "data": {
        "code": "688111",
        "total_buy_quantity": 100,
        "total_sell_quantity": 50,
        "avg_buy_price": 100.0,
        "avg_sell_price": 110.0,
        "realized_pnl": 500.0,
        "holding_days": 10,
        "trade_count": 2
    }
}
```

### 3. get_account_info - 获取账户信息 ⭐

**用途**: 获取用户的资金账户信息（关键工具）

**参数**:
- `user_id` (必需): 用户ID

**返回值**:
```python
{
    "success": True,
    "data": {
        "total_assets": 1000000.0,
        "cash": 500000.0,
        "positions_value": 500000.0,
        "total_pnl": 50000.0,
        "total_pnl_pct": 5.0,
        "initial_capital": 1000000.0,
        "total_deposit": 0.0,
        "total_withdraw": 0.0
    }
}
```

### 4. get_market_snapshot_for_review - 获取市场快照

**用途**: 获取交易期间的K线数据

**参数**:
- `code` (必需): 股票代码
- `market` (必需): 市场类型 ('CN' 或 'US')
- `start_date` (可选): 开始日期 YYYY-MM-DD
- `end_date` (可选): 结束日期 YYYY-MM-DD

**返回值**:
```python
{
    "success": True,
    "data": {
        "code": "688111",
        "market": "CN",
        "start_date": "2025-01-01",
        "end_date": "2025-01-31",
        "kline_data": [
            {
                "date": "2025-01-01",
                "open": 100.0,
                "high": 105.0,
                "low": 99.0,
                "close": 102.0,
                "volume": 1000000
            }
        ]
    }
}
```

## Agent 工具绑定

### position_analyst (仓位分析师)

**绑定工具**:
- `build_trade_info` - 构建交易信息
- `get_account_info` - 获取账户信息 ⭐
- `get_market_snapshot_for_review` - 获取市场快照
- `get_trade_records` - 获取交易记录
- `get_stock_market_data_unified` - 获取市场数据

**默认工具**: `build_trade_info`, `get_account_info`

**分析内容**:
- 仓位大小评估
- 资金利用率分析
- 风险控制评估
- 加减仓策略评估

### timing_analyst (时机分析师)

**绑定工具**: 5个工具（包括市场数据工具）

**分析内容**:
- 交易时机评估
- 市场环境分析
- 技术指标分析

### attribution_analyst (归因分析师)

**绑定工具**: 5个工具（包括市场概览工具）

**分析内容**:
- 收益归因分析
- 市场因素分析
- 个股因素分析

## 工作流执行流程

```
1. 用户提交交易复盘请求
   ↓
2. 工作流启动，传递 user_id 和 trade_ids
   ↓
3. Agent 执行分析
   ├─ 调用 build_trade_info() 获取交易统计
   ├─ 调用 get_account_info() 获取账户信息 ⭐
   ├─ 调用 get_market_snapshot_for_review() 获取市场数据
   └─ 基于完整数据生成分析报告
   ↓
4. 返回分析结果
```

## 常见问题

### Q: 为什么仓位分析现在能获取完整数据？
A: 因为 `get_account_info` 工具现在被绑定到 position_analyst Agent，Agent 可以在分析过程中调用此工具获取账户信息。

### Q: 工具是如何被调用的？
A: 工具通过 LLM 的工具调用机制被调用。Agent 的提示词会指导 LLM 在需要时调用相应的工具。

### Q: 可以添加更多工具吗？
A: 可以。只需创建新工具文件，使用 `@register_tool` 装饰器注册，然后在 Agent 配置中添加工具ID即可。

## 最佳实践

1. **工具设计**
   - 保持工具功能单一
   - 提供清晰的参数说明
   - 返回统一的响应格式

2. **Agent 配置**
   - 只绑定必要的工具
   - 设置合理的 `max_tool_calls` 限制
   - 定义 `default_tools` 优先调用

3. **错误处理**
   - 工具应捕获所有异常
   - 返回 `success: False` 和错误信息
   - 记录详细的日志

## 相关文档

- [交易复盘工具架构](../design/v2.0/trade-review-tools-architecture.md)
- [实现总结](../design/v2.0/IMPLEMENTATION_SUMMARY.md)
- [v2.0 工具系统](../development/v2.0-tools-system.md)

