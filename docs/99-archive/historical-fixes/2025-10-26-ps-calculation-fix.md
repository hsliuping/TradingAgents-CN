# 市销率（PS）计算修复

**日期**: 2025-10-26  
**问题**: 市销率（PS）计算使用了季度/半年报数据，导致 PS 被高估  
**严重程度**: 高（影响所有股票的估值指标）

---

## 📋 问题描述

### 用户反馈

用户发现市销率（PS）的计算公式可能有误，经过分析确认存在两个问题：

1. ✅ **公式本身正确**: `PS = 总市值 / 营业收入`
2. ❌ **数据使用错误**: 使用了季度/半年报的营业收入，而不是年度或 TTM 数据

### 问题影响

如果使用半年报数据计算 PS：
- **实际 PS**: 16.67 倍
- **错误 PS**: 33.33 倍
- **高估倍数**: 2 倍

如果使用季报数据计算 PS：
- **实际 PS**: 16.67 倍
- **错误 PS**: 66.67 倍
- **高估倍数**: 4 倍

---

## 🔍 根本原因分析

### 1. 总市值计算（正确）

**代码位置**: `scripts/sync_financial_data.py` 第 145-147 行

```python
# 计算市值（万元）
market_cap = price * financial_data['total_share']
financial_data['money_cap'] = market_cap
```

- `price`: 从 `market_quotes` 集合获取的**最新收盘价**（实时更新）✅
- `total_share`: 总股本（万股）
- `money_cap`: 总市值（万元）= 股价 × 总股本

**结论**: 总市值是动态变化的，随股价实时更新，这是正确的做法。

### 2. 营业收入数据（错误）

**代码位置**: `scripts/sync_financial_data.py` 第 69-93 行

```python
# 获取最新一期数据
latest = df.iloc[-1].to_dict()

# 财务数据（万元）
"revenue": _safe_float(latest.get('营业收入')),  # 营业收入
```

**问题**:
- AKShare 的 `stock_financial_analysis_indicator` 返回的是**最新一期**的财务数据
- 可能是 Q1（第一季度）、Q2（半年报）、Q3（第三季度）、Q4（年报）
- **没有进行年化处理或 TTM 计算**

**正确做法**:
- 市销率应该使用**年度营业收入**或 **TTM（最近12个月）营业收入**

---

## 🔧 修复方案

### 方案选择

采用 **TTM（Trailing Twelve Months）** 方法，即最近 12 个月的营业收入。

**优点**:
- 更准确反映公司当前的经营状况
- 避免季节性波动的影响
- 与市值的实时性相匹配

### TTM 计算逻辑

#### 情况 1：最新期是年报（12月31日）
```
TTM = 年报营业收入
```

#### 情况 2：最新期是中报/季报
```
TTM = 最近年报 + (本期 - 去年同期)
```

**示例**:
- 2023年报: 1100 万元
- 2023中报: 500 万元
- 2024中报: 600 万元（最新期）
- **TTM** = 1100 + (600 - 500) = **1200 万元**

#### 情况 3：数据不足时的降级策略

如果无法获取完整的历史数据，使用简单年化：
- **中报**: TTM = 营业收入 × 2
- **一季报**: TTM = 营业收入 × 4
- **三季报**: TTM = 营业收入 × 4/3

---

## 📝 代码修改

### 1. 新增 TTM 计算函数

**文件**: `scripts/sync_financial_data.py`

```python
def _calculate_ttm_revenue(df) -> Optional[float]:
    """
    计算 TTM（最近12个月）营业收入
    
    策略：
    1. 如果最新期是年报（12月31日），直接使用年报营业收入
    2. 如果最新期是中报/季报，计算 TTM = 最新年报 + (本期 - 去年同期)
    3. 如果数据不足，使用简单年化
    
    Args:
        df: AKShare 返回的财务指标 DataFrame
    
    Returns:
        TTM 营业收入（万元），如果无法计算则返回 None
    """
    # ... 实现代码见 scripts/sync_financial_data.py
```

### 2. 保存 TTM 数据到数据库

**文件**: `scripts/sync_financial_data.py`

```python
financial_data = {
    # ...
    "revenue": _safe_float(latest.get('营业收入')),  # 营业收入（单期）
    "revenue_ttm": ttm_revenue,  # TTM营业收入（最近12个月）
    # ...
}
```

### 3. 修改 PS 计算逻辑

**文件**: `tradingagents/dataflows/optimized_china_data.py`

```python
# 计算 PS - 市销率（使用TTM营业收入）
# 优先使用 TTM 营业收入，如果没有则使用单期营业收入
revenue_ttm = latest_indicators.get('revenue_ttm')
revenue = latest_indicators.get('revenue')

# 选择使用哪个营业收入数据
revenue_for_ps = revenue_ttm if revenue_ttm and revenue_ttm > 0 else revenue
revenue_type = "TTM" if revenue_ttm and revenue_ttm > 0 else "单期"

if revenue_for_ps and revenue_for_ps > 0:
    money_cap = latest_indicators.get('money_cap')
    if money_cap and money_cap > 0:
        ps_calculated = money_cap / revenue_for_ps
        metrics["ps"] = f"{ps_calculated:.2f}倍"
        logger.debug(f"✅ 计算PS({revenue_type}): 市值{money_cap}万元 / 营业收入{revenue_for_ps}万元 = {metrics['ps']}")
```

---

## ✅ 测试验证

### 测试脚本

创建了 `scripts/test_ttm_calculation.py` 进行单元测试。

### 测试用例

1. **年报数据**: 直接使用年报营业收入 ✅
2. **中报数据（完整历史）**: TTM = 年报 + (本期 - 去年同期) ✅
3. **中报数据（简单年化）**: TTM = 营业收入 × 2 ✅
4. **一季报数据**: TTM = 营业收入 × 4 ✅
5. **三季报数据**: TTM = 营业收入 × 4/3 ✅

### 测试结果

```
================================================================================
✅ 所有测试通过！
================================================================================
```

---

## 📊 修复效果对比

### 示例：某公司

**基本信息**:
- 当前股价: 10 元
- 总股本: 10 亿股
- 总市值: 100 亿元

**修复前（使用半年报数据）**:
- 半年营业收入: 30 亿元
- PS = 100 / 30 = **33.33 倍** ❌

**修复后（使用 TTM 数据）**:
- TTM 营业收入: 60 亿元
- PS = 100 / 60 = **16.67 倍** ✅

**差异**: 高估了 **2 倍**！

---

## 🚀 部署步骤

### 1. 重新同步财务数据

运行以下命令重新同步所有股票的财务数据，计算 TTM 营业收入：

```bash
# 同步单只股票
python scripts/sync_financial_data.py 600036

# 批量同步前 100 只
python scripts/sync_financial_data.py --batch 100

# 同步所有股票
python scripts/sync_financial_data.py --all
```

### 2. 验证数据

检查数据库中是否包含 `revenue_ttm` 字段：

```python
from motor.motor_asyncio import AsyncIOMotorClient

client = AsyncIOMotorClient("mongodb://localhost:27017")
db = client["tradingagents"]

# 查询一只股票的财务数据
doc = await db.stock_financial_data.find_one({"code": "600036"})
print(f"revenue: {doc.get('revenue')}")
print(f"revenue_ttm: {doc.get('revenue_ttm')}")
```

### 3. 重新运行分析

重新运行股票分析，使用新的 PS 计算逻辑。

---

## 📌 注意事项

### 1. 数据兼容性

- 旧数据没有 `revenue_ttm` 字段，会降级使用 `revenue`（单期数据）
- 建议重新同步所有股票的财务数据

### 2. 其他数据源也存在同样问题 ⚠️

经过检查，发现 **Tushare 数据源** 和 **实时行情数据源** 也存在类似问题：

#### Tushare 数据源问题

**位置**: `tradingagents/dataflows/optimized_china_data.py` 第 1377-1416 行

**问题**:
1. **营业收入**: 使用 `income_statement[0]` 的 `total_revenue`（单期数据）
2. **净利润**: 使用 `income_statement[0]` 的 `n_income`（单期数据）
3. **市值计算**: 使用固定的 10 亿股本（`price_value * 1000000000`），完全不准确！

**影响**:
- PS 被高估 2-4 倍
- PE 被高估 2-4 倍
- 市值计算完全错误（不同股票的股本差异巨大）

**临时措施**:
- 添加了警告日志，提醒用户数据可能不准确
- 添加了 TODO 注释，标记需要修复的地方

**完整修复方案**（需要后续实施）:
1. 从 Tushare 获取多期数据，计算 TTM
2. 从 `stock_basic_info` 或 `daily_basic` 获取实际总股本
3. 使用实际总股本计算市值

#### 实时行情数据源问题

**位置**: 同上

**问题**: 与 Tushare 数据源完全相同

**建议**: 实时行情数据源应该只提供价格数据，不应该计算估值指标

### 3. PE 和 PB 是否也有问题？

**PE（市盈率）**:
- ❌ 存在同样问题：使用单期净利润，应该使用 TTM 净利润
- 影响：被高估 2-4 倍

**PB（市净率）**:
- ✅ 问题不大：净资产通常使用最新期数据（资产负债表是时点数据）
- 但市值计算错误会影响 PB 的准确性

### 4. 性能影响

TTM 计算需要读取多期数据，可能会略微增加数据同步时间，但影响不大。

---

## 📚 参考资料

### 市销率（PS）定义

**市销率（Price-to-Sales Ratio, PS）** = **总市值 / 营业收入**

- 用于衡量公司市值相对于营业收入的倍数
- 适用于尚未盈利但有营业收入的公司
- 通常使用年度营业收入或 TTM 营业收入

### TTM（Trailing Twelve Months）

**TTM** 是指最近 12 个月的累计数据，常用于财务分析：
- 更准确反映公司当前的经营状况
- 避免季节性波动的影响
- 与实时市值相匹配

---

## 🎯 总结

### 问题

市销率（PS）计算使用了季度/半年报的营业收入，导致 PS 被高估 2-4 倍。

### 修复

1. 新增 `_calculate_ttm_revenue()` 函数计算 TTM 营业收入
2. 在数据库中保存 `revenue_ttm` 字段
3. 修改 PS 计算逻辑，优先使用 TTM 数据

### 影响

- ✅ PS 计算更准确
- ✅ 与市值的实时性相匹配
- ✅ 避免季节性波动的影响

### 后续工作

- [ ] 重新同步所有股票的财务数据（AKShare 数据源）
- [x] 检查其他数据源是否也存在类似问题（已确认 Tushare 和实时行情也有问题）
- [ ] 修复 Tushare 数据源的 TTM 计算
- [ ] 修复 Tushare 数据源的市值计算（获取实际总股本）
- [ ] 修复 PE 计算（使用 TTM 净利润）
- [ ] 更新用户文档，说明 PS/PE 计算方法

