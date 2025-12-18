# 交易复盘 v2.0 工具系统架构

## 概述

交易复盘功能已完全重构为 v2.0 工具系统架构，所有数据获取现在通过注册的工具实现，而不是内部私有方法。这符合系统整体的 v2.0 架构设计。

## 核心工具集

### 1. `get_trade_records` - 获取交易记录
**位置**: `core/tools/implementations/trade_review/trade_records.py`

```python
get_trade_records(
    user_id: str,           # 用户ID
    trade_ids: List[str],   # 交易ID列表
    source: str = "real"    # 数据源: 'real'(真实持仓) 或 'paper'(模拟交易)
) -> Dict[str, Any]
```

**功能**:
- 从 MongoDB 获取交易记录
- 支持真实持仓 (`position_changes`) 和模拟交易 (`paper_trades`)
- 返回完整的交易数据

### 2. `build_trade_info` - 构建交易信息
**位置**: `core/tools/implementations/trade_review/trade_info.py`

```python
build_trade_info(
    trade_records: List[Dict[str, Any]],  # 交易记录列表
    code: Optional[str] = None             # 股票代码
) -> Dict[str, Any]
```

**功能**:
- 从交易记录构建完整的交易信息对象
- 计算统计数据（总买入量、平均价格、盈亏等）
- 计算持仓天数

### 3. `get_account_info` - 获取账户信息
**位置**: `core/tools/implementations/trade_review/account_info.py`

```python
get_account_info(
    user_id: str  # 用户ID
) -> Dict[str, Any]
```

**功能**:
- 获取用户的资金账户信息
- 返回现金、持仓市值、总资产、盈亏等
- **关键**: 这是解决仓位分析数据不完整的核心工具

### 4. `get_market_snapshot_for_review` - 获取市场快照
**位置**: `core/tools/implementations/trade_review/market_snapshot.py`

```python
get_market_snapshot_for_review(
    code: str,                    # 股票代码
    market: str,                  # 市场类型
    start_date: Optional[str],    # 开始日期
    end_date: Optional[str]       # 结束日期
) -> Dict[str, Any]
```

**功能**:
- 获取交易期间的K线数据
- 支持自定义日期范围
- 返回市场快照数据

## Agent 工具绑定

### 更新的 Agent 配置

#### position_analyst (仓位分析师)
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

#### timing_analyst (时机分析师)
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

#### attribution_analyst (归因分析师)
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

## 工作流数据流

### 工作流输入结构
```python
inputs = {
    "user_id": user_id,                    # 🆕 用户ID
    "trade_ids": [trade_ids],              # 🆕 交易ID列表
    "trade_info": {...},                   # 交易信息
    "market_data": {...},                  # 市场数据
    "benchmark_data": {...},               # 基准数据
    "messages": []                         # 消息历史
}
```

### 执行流程

1. **工作流启动** → 传递 `user_id` 和 `trade_ids`
2. **Agent 执行** → 通过工具获取完整数据
3. **工具调用链**:
   - `build_trade_info()` 构建交易信息
   - `get_account_info()` 获取账户信息
   - `get_market_snapshot_for_review()` 获取市场数据
4. **分析生成** → Agent 基于完整数据生成分析报告

## 关键改进

### ✅ 解决的问题

1. **仓位分析数据不完整**
   - 之前: 仓位分析师无法获取账户信息
   - 现在: 通过 `get_account_info` 工具获取完整账户数据

2. **架构一致性**
   - 之前: 数据获取通过内部私有方法
   - 现在: 所有数据通过 v2.0 工具系统获取

3. **可扩展性**
   - 之前: 添加新数据源需要修改内部方法
   - 现在: 只需创建新工具并绑定到 Agent

## 使用示例

### 在 Agent 中使用工具

工作流引擎会自动为 Agent 绑定配置中的工具，Agent 可以在分析过程中调用：

```
Agent 提示词:
"你是仓位分析师，请使用以下工具分析仓位：
- build_trade_info: 构建交易信息
- get_account_info: 获取账户信息
- get_market_snapshot_for_review: 获取市场数据

然后基于完整数据生成仓位分析报告..."
```

## 文件结构

```
core/tools/implementations/trade_review/
├── __init__.py                    # 工具集导出
├── trade_records.py               # 获取交易记录
├── trade_info.py                  # 构建交易信息
├── account_info.py                # 获取账户信息
└── market_snapshot.py             # 获取市场快照
```

## 下一步

1. **测试工具链** - 验证工具在工作流中的正确执行
2. **优化提示词** - 为 Agent 提供更好的工具使用指导
3. **添加更多工具** - 根据需要扩展工具集
4. **性能优化** - 缓存常用数据查询结果

