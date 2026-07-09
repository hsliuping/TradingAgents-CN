# 基本面分析实时API调用中的TTM计算问题

## 问题发现日期
2025-10-26

## 问题概述

在基本面分析时，当数据库中没有数据时，系统会直接调用 AKShare 或 Tushare API 获取数据。但是这些实时调用的代码中存在严重的 TTM 计算问题，导致 PE 和 PS 被严重高估。

## 问题详情

### 问题 1: AKShare 实时调用使用单期 EPS 计算 PE

**位置**: `tradingagents/dataflows/optimized_china_data.py:1236-1245`

**问题代码**:
```python
# 获取每股收益 - 用于计算PE
eps_value = indicators_dict.get('基本每股收益')
if eps_value is not None and str(eps_value) != 'nan' and eps_value != '--':
    try:
        eps_val = float(eps_value)
        if eps_val > 0:
            # 计算PE = 股价 / 每股收益
            pe_val = price_value / eps_val  # ❌ 使用单期EPS
            metrics["pe"] = f"{pe_val:.1f}倍"
```

**问题分析**:
- AKShare 的 `基本每股收益` 是**单期数据**（可能是 Q1/Q2/Q3/年报）
- 如果是 Q1 数据，PE 会被高估 **4 倍**
- 如果是 Q2 数据，PE 会被高估 **2 倍**
- 如果是 Q3 数据，PE 会被高估 **1.33 倍**

**影响**:
- 用户在数据库没有数据时，首次查询会得到错误的 PE 值
- 对投资决策产生严重误导

### 问题 2: AKShare 实时调用缺少 PS 计算

**位置**: `tradingagents/dataflows/optimized_china_data.py:1333`

**问题代码**:
```python
# 补充其他指标的默认值
metrics.update({
    "ps": "待计算",  # ❌ 没有实际计算！
    "dividend_yield": "待查询",
    "cash_ratio": "待分析"
})
```

**问题分析**:
- PS（市销率）完全没有计算
- 返回的是占位符字符串 `"待计算"`
- 用户无法获得 PS 指标

### 问题 3: Tushare 实时调用使用单期数据计算 PE/PS

**位置**: `tradingagents/dataflows/optimized_china_data.py:1403-1424`

**问题代码**:
```python
# PE比率（使用单期净利润，可能不准确）
if net_income > 0:
    pe_ratio = market_cap / (net_income * 10000)  # ❌ 使用单期净利润
    metrics["pe"] = f"{pe_ratio:.1f}倍"
    logger.warning(f"⚠️ Tushare PE 使用单期净利润，可能不准确")
else:
    metrics["pe"] = "N/A（亏损）"

# PS比率（使用单期营业收入，可能不准确）
if total_revenue > 0:
    ps_ratio = market_cap / (total_revenue * 10000)  # ❌ 使用单期营业收入
    metrics["ps"] = f"{ps_ratio:.1f}倍"
    logger.warning(f"⚠️ Tushare PS 使用单期营业收入，可能被高估2-4倍")
else:
    metrics["ps"] = "N/A"
```

**问题分析**:
- 虽然有警告日志，但仍然使用单期数据计算
- Tushare 的 `total_revenue` 和 `n_income` 是**累计值**（从年初到报告期）
- 需要使用 TTM 公式计算，而不是直接使用单期数据

**注释中的警告**:
```python
# ⚠️ 警告：Tushare income_statement 的 total_revenue 是单期数据（可能是季报/半年报）
# 理想情况下应该使用 TTM 数据，但 Tushare 数据结构中没有预先计算的 TTM 字段
# TODO: 需要从多期数据中计算 TTM
```

## 影响范围

### 触发条件
1. 用户首次查询某只股票的基本面数据
2. 数据库中没有该股票的财务数据
3. 系统调用 AKShare 或 Tushare API 实时获取数据

### 影响程度
- **严重**: PE/PS 被高估 1.33-4 倍
- **用户体验**: 首次查询得到错误数据，后续查询（从数据库读取）得到正确数据，造成混淆
- **投资决策**: 可能导致用户错误判断股票估值

## 修复方案

### 方案 1: 实时调用时计算 TTM（推荐）

**优点**:
- 数据准确
- 用户首次查询就能得到正确结果
- 与数据库数据保持一致

**缺点**:
- 需要获取多期数据（最近 4 期）
- API 调用次数增加
- 实现复杂度较高

**实现步骤**:
1. 修改 `_parse_akshare_financial_data` 方法
   - 获取最近 4 期的财务指标数据
   - 使用 `_calculate_ttm_metric` 函数计算 TTM EPS
   - 使用 TTM EPS 计算 PE
   - 计算 TTM 营业收入并计算 PS

2. 修改 `_parse_financial_data` 方法（Tushare）
   - 获取最近 4 期的利润表数据
   - 使用 TTM 公式计算 TTM 净利润和营业收入
   - 使用 TTM 数据计算 PE 和 PS

### 方案 2: 实时调用时返回 None，强制同步到数据库

**优点**:
- 实现简单
- 避免返回不准确的数据
- 强制用户使用准确的数据库数据

**缺点**:
- 用户首次查询会失败
- 需要手动触发数据同步
- 用户体验较差

### 方案 3: 实时调用时标注数据类型（临时方案）

**优点**:
- 实现简单
- 用户知道数据不准确

**缺点**:
- 仍然返回不准确的数据
- 只是治标不治本

**实现**:
```python
metrics["pe"] = f"{pe_val:.1f}倍（单期，可能高估）"
metrics["ps"] = f"{ps_val:.2f}倍（单期，可能高估）"
```

## 推荐修复方案

**采用方案 1**：实时调用时计算 TTM

理由：
1. 数据准确性最重要
2. 已经有 `_calculate_ttm_metric` 函数可以复用
3. 与数据库数据保持一致
4. 用户体验最好

## 修复优先级

**P0 - 紧急**

理由：
- 影响核心功能（基本面分析）
- 数据错误严重（高估 1.33-4 倍）
- 可能导致错误的投资决策

## 相关文件

- `tradingagents/dataflows/optimized_china_data.py`
  - `_parse_akshare_financial_data` 方法（第 1169-1357 行）
  - `_parse_financial_data` 方法（第 1359-1485 行）
- `scripts/sync_financial_data.py`
  - `_calculate_ttm_metric` 函数（可复用）

## 测试计划

1. 测试 AKShare 实时调用
   - 清空数据库中某只股票的财务数据
   - 调用基本面分析
   - 验证 PE 和 PS 是否使用 TTM 数据

2. 测试 Tushare 实时调用
   - 清空数据库中某只股票的财务数据
   - 调用基本面分析
   - 验证 PE 和 PS 是否使用 TTM 数据

3. 对比测试
   - 对比实时调用和数据库数据的 PE/PS
   - 确保两者一致

## 后续工作

1. 修复 AKShare 实时调用的 PE 计算
2. 添加 AKShare 实时调用的 PS 计算
3. 修复 Tushare 实时调用的 PE/PS 计算
4. 添加单元测试
5. 更新文档

