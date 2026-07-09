# 交易计划与操作复盘分析关联功能

## 功能概述

本功能实现了交易计划与操作复盘分析的关联，用户在进行操作复盘分析时，可以选择关联一个交易计划，AI 将根据交易计划中定义的规则对交易进行合规性检查。

## 实现日期

2025-12-24

## 功能特性

### 1. 可选关联

- 用户可以选择是否关联交易计划
- 如果不关联，复盘分析按原有逻辑进行
- 如果关联，AI 会额外检查交易是否符合交易计划规则

### 2. 规则检查

当关联交易计划时，AI 会检查以下规则：

- **选股规则**：检查股票是否符合选股标准
- **择时规则**：检查买入/卖出时机是否符合入场/出场信号
- **仓位规则**：检查仓位是否超过单只股票上限
- **风险管理规则**：检查是否执行了止损止盈策略
- **纪律规则**：检查是否违反了必须做到/严禁操作的规则

### 3. 报告展示

- 复盘报告中会显示关联的交易计划名称
- AI 分析结果中会指出违反规则的地方
- 帮助用户发现交易中的纪律问题

## 技术实现

### 后端修改

#### 1. 数据模型 (`app/models/review.py`)

**CreateTradeReviewRequest**：
```python
class CreateTradeReviewRequest(BaseModel):
    trade_ids: List[str]
    review_type: ReviewType = ReviewType.COMPLETE_TRADE
    code: Optional[str] = None
    source: str = "paper"
    trading_system_id: Optional[str] = None  # 新增：关联的交易计划ID
```

**TradeReviewReport**：
```python
class TradeReviewReport(BaseModel):
    # ... 其他字段
    trading_system_id: Optional[str] = None  # 新增：关联的交易计划ID
    trading_system_name: Optional[str] = None  # 新增：关联的交易计划名称
```

#### 2. 服务层 (`app/services/trade_review_service.py`)

**新增方法**：
- `_get_trading_system()`: 获取交易计划信息

**修改方法**：
- `create_trade_review()`: 获取交易计划信息并保存到报告
- `_call_ai_trade_review()`: 传递交易计划信息给提示词生成
- `_build_trade_review_prompt()`: 接收交易计划参数
- `_build_legacy_trade_review_prompt()`: 在提示词中加入交易计划规则
- `_call_workflow_trade_review()`: 支持交易计划参数

**提示词增强**：
在 AI 提示词中添加了交易计划规则部分，包括：
- 选股规则（必须满足、排除条件）
- 择时规则（入场信号、出场信号）
- 仓位规则（单只股票上限、最大持股数）
- 风险管理规则（止损、止盈）
- 纪律规则（必须做到、严禁操作）

### 前端修改

#### 1. API 接口 (`frontend/src/api/review.ts`)

**CreateTradeReviewRequest**：
```typescript
export interface CreateTradeReviewRequest {
  trade_ids: string[]
  review_type?: ReviewType
  code?: string
  source?: 'real' | 'paper'
  trading_system_id?: string  // 新增：关联的交易计划ID
}
```

**TradeReviewReport**：
```typescript
export interface TradeReviewReport {
  // ... 其他字段
  trading_system_id?: string  // 新增：关联的交易计划ID
  trading_system_name?: string  // 新增：关联的交易计划名称
}
```

#### 2. UI 组件

**StockOperationHistoryDialog.vue** (`frontend/src/views/Portfolio/components/`)：
- 交易计划选择器（下拉框）
- 自动加载用户的交易计划列表
- 在复盘报告中显示关联的交易计划名称
- 选择器位于"操作分析"按钮旁边
- 支持清空选择（不关联交易计划）
- 下拉选项显示交易计划名称和风格标签
- 报告头部显示关联的交易计划名称（绿色标签）

**PositionReviewDialog.vue** (`frontend/src/views/TradeReview/components/`)：
- 在"复盘分析内容"表单中添加交易计划选择器
- 位于"分析维度"选项之前
- 显示提示文字："选择后将按照交易计划规则进行合规性检查"
- 支持清空选择（不关联交易计划）
- 下拉选项显示交易计划名称和风格标签

## 使用流程

### 1. 创建交易计划

首先在"交易计划"模块创建一个交易计划，定义好各项规则。

### 2. 进行操作复盘

1. 进入"持仓管理"或"模拟交易"页面
2. 点击某只股票的"操作历史"
3. 在弹出的对话框中，选择一个交易计划（可选）
4. 点击"操作分析"按钮
5. 等待 AI 分析完成

### 3. 查看分析结果

- 报告头部会显示关联的交易计划名称
- AI 分析中会指出违反规则的地方
- 改进建议中会包含如何遵守交易计划规则的建议

## 示例

### 不关联交易计划

```
📊 操作分析报告                    评分: 75分
```

### 关联交易计划

```
📊 操作分析报告    🎯 短线趋势追踪系统    评分: 75分
```

AI 分析会包含类似内容：
```
本次交易关联了"短线趋势追踪系统"，检查发现以下问题：
1. 违反择时规则：买入时未出现明确的入场信号
2. 违反仓位规则：单只股票仓位达到18%，超过系统规定的15%上限
3. 违反风险管理规则：未在-7%处止损，导致亏损扩大到-12%
```

## 后续优化建议

1. **规则匹配度评分**：为每条规则单独打分，显示整体合规度
2. **规则违反统计**：统计用户最常违反的规则类型
3. **规则提醒**：在下单时提醒用户当前操作是否符合交易计划规则
4. **规则优化建议**：根据历史交易数据，建议优化交易计划规则

## 相关文件

### 后端
- `app/models/review.py` - 数据模型
- `app/services/trade_review_service.py` - 服务层

### 前端
- `frontend/src/api/review.ts` - API 接口
- `frontend/src/views/Portfolio/components/StockOperationHistoryDialog.vue` - 股票操作历史对话框
- `frontend/src/views/TradeReview/components/PositionReviewDialog.vue` - 持仓操作复盘对话框

## 测试建议

1. 测试不关联交易计划的复盘（应该和之前一样）
2. 测试关联交易计划的复盘（应该包含规则检查）
3. 测试关联不存在的交易计划（应该优雅降级）
4. 测试交易计划规则为空的情况（应该不影响分析）

