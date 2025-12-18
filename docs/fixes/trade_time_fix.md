# 持仓操作复盘数据时间修复

## 问题描述

持仓操作复盘使用的是 `created_at`（记录创建时间）而不是 `trade_time`（实际交易时间）。

由于持仓记录是通过手工录入的，不是通过交易系统自动创建的，所以可能存在交易时间和创建时间不一致的情况。

**示例**：
- 用户在 2025-12-12 11:20 录入了一条 2025-12-10 的交易记录
- `created_at` = 2025-12-12 11:20:15（记录创建时间）
- `trade_time` = 2025-12-10（实际交易时间）

复盘分析应该使用 `trade_time` 而不是 `created_at`。

## 修复方案

### 1. 数据模型修改 (`app/models/portfolio.py`)

在 `PositionChange` 模型中添加 `trade_time` 字段：

```python
trade_time: Optional[datetime] = None  # 交易时间（实际交易发生的时间，由用户手工录入）
created_at: datetime = Field(default_factory=now_tz)  # 记录创建时间
```

### 2. 服务层修改 (`app/services/portfolio_service.py`)

#### 2.1 修改 `record_position_change()` 方法

- 添加 `trade_time` 参数
- 在保存数据时，使用 `trade_time` 或默认为当前时间

#### 2.2 修改所有调用 `record_position_change()` 的地方

在以下方法中添加 `trade_time=data.operation_date` 参数：

- `add_position()` - 使用 `data.buy_date`
- `_handle_add_operation()` - 使用 `data.operation_date`
- `_handle_reduce_operation()` - 使用 `data.operation_date`
- `_handle_dividend_operation()` - 使用 `data.operation_date`
- `_handle_split_operation()` - 使用 `data.operation_date`
- `_handle_merge_operation()` - 使用 `data.operation_date`
- `_handle_adjust_operation()` - 使用 `data.operation_date`

### 3. 复盘数据获取修改 (`app/services/trade_review_service.py`)

在 `_get_trade_records()` 方法中修改时间戳处理逻辑：

```python
# 优先使用 trade_time（实际交易时间），其次使用 created_at（记录创建时间）
if trade_time:
    timestamp_str = trade_time.isoformat() if trade_time else ""
else:
    timestamp_str = created_at.isoformat() if created_at else ""
```

## 数据流

```
前端: PositionOperationDialog.vue
  ↓ 提交 operation_date
后端: PositionOperationRequest
  ↓ 传递 operation_date
PortfolioService.operate_position()
  ↓ 调用 record_position_change(trade_time=data.operation_date)
position_changes 集合
  ↓ 保存 trade_time 字段
TradeReviewService._get_trade_records()
  ↓ 优先使用 trade_time
复盘分析
  ↓ 使用正确的交易时间
```

## 测试步骤

1. 在前端添加一条持仓操作，指定一个过去的日期
2. 查看数据库中的 `position_changes` 记录，验证 `trade_time` 字段已保存
3. 创建复盘分析，验证使用的是 `trade_time` 而不是 `created_at`
4. 检查复盘报告中的交易时间是否正确

## 向后兼容性

- 如果 `trade_time` 为空，则使用 `created_at`
- 现有的持仓记录没有 `trade_time` 字段，复盘时会自动降级到 `created_at`
- 新创建的持仓记录会正确保存 `trade_time` 字段

