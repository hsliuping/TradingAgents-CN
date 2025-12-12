# 估值指标计算问题总结

**日期**: 2025-10-26  
**问题**: 三个数据源的 PS/PE 计算都存在问题  
**严重程度**: 高（影响所有股票的估值指标）

---

## 📋 问题总览

| 数据源 | PS 问题 | PE 问题 | 市值问题 | 修复状态 |
|--------|---------|---------|----------|----------|
| **MongoDB (AKShare)** | ❌ 使用单期营业收入 | ❌ 使用单期净利润 | ✅ 正确（实际股本） | ✅ PS 已修复 |
| **Tushare** | ❌ 使用单期营业收入 | ❌ 使用单期净利润 | ❌ 固定10亿股本 | ⚠️ 已标记 |
| **实时行情** | ❌ 使用单期营业收入 | ❌ 使用单期净利润 | ❌ 固定10亿股本 | ⚠️ 已标记 |

---

## 🔍 详细分析

### 1. MongoDB 数据源（AKShare）

**代码位置**: `tradingagents/dataflows/optimized_china_data.py` 第 1126-1148 行

#### 问题

- **PS**: 使用 `revenue`（单期营业收入）
- **PE**: 使用 `net_profit`（单期净利润）
- **市值**: ✅ 正确（`money_cap = price * total_share`）

#### 修复状态

- ✅ **PS 已修复**: 使用 `revenue_ttm` 字段（TTM 营业收入）
- ❌ **PE 未修复**: 仍使用单期净利润

#### 修复代码

```python
# 优先使用 TTM 营业收入，如果没有则使用单期营业收入
revenue_ttm = latest_indicators.get('revenue_ttm')
revenue = latest_indicators.get('revenue')

revenue_for_ps = revenue_ttm if revenue_ttm and revenue_ttm > 0 else revenue
revenue_type = "TTM" if revenue_ttm and revenue_ttm > 0 else "单期"

if revenue_for_ps and revenue_for_ps > 0:
    money_cap = latest_indicators.get('money_cap')
    if money_cap and money_cap > 0:
        ps_calculated = money_cap / revenue_for_ps
        metrics["ps"] = f"{ps_calculated:.2f}倍"
```

---

### 2. Tushare 数据源

**代码位置**: `tradingagents/dataflows/optimized_china_data.py` 第 1377-1416 行

#### 问题

1. **PS**: 使用 `income_statement[0]['total_revenue']`（单期营业收入）
2. **PE**: 使用 `income_statement[0]['n_income']`（单期净利润）
3. **市值**: ❌ 使用固定的 10 亿股本（`price_value * 1000000000`）

#### 影响

- PS 被高估 2-4 倍
- PE 被高估 2-4 倍
- **市值计算完全错误**（不同股票的股本差异巨大）

#### 临时措施

添加了警告日志和 TODO 注释：

```python
# ⚠️ 警告：Tushare income_statement 的 total_revenue 是单期数据（可能是季报/半年报）
# 理想情况下应该使用 TTM 数据，但 Tushare 数据结构中没有预先计算的 TTM 字段
# TODO: 需要从多期数据中计算 TTM
total_revenue = latest_income.get('total_revenue', 0) or 0

# ⚠️ 警告：市值计算使用固定股本（10亿股）是不准确的
# 理想情况下应该从 stock_basic_info 或 daily_basic 获取实际总股本
# TODO: 需要获取实际总股本数据
market_cap = price_value * 1000000000  # 假设10亿股本（不准确！）
```

#### 完整修复方案

1. **修复 TTM 计算**:
   - 从 Tushare 获取多期 `income_statement` 数据
   - 计算 TTM 营业收入和净利润
   - 参考 AKShare 数据源的 `_calculate_ttm_revenue()` 函数

2. **修复市值计算**:
   - 从 `stock_basic_info` 集合获取 `total_share`（总股本）
   - 或从 Tushare `daily_basic` API 获取 `total_share`
   - 使用实际股本计算市值：`market_cap = price * total_share`

---

### 3. 实时行情数据源

**代码位置**: 同 Tushare 数据源

#### 问题

与 Tushare 数据源完全相同。

#### 建议

实时行情数据源应该只提供价格数据，不应该计算估值指标。建议：
- 移除 PS/PE/PB 等估值指标的计算
- 或者从 MongoDB 数据源获取财务数据进行计算

---

## 🎯 修复优先级

### 高优先级（必须修复）

1. ✅ **MongoDB PS 计算** - 已修复
2. ❌ **Tushare 市值计算** - 使用固定股本完全错误
3. ❌ **Tushare PS 计算** - 使用单期数据高估 2-4 倍
4. ❌ **Tushare PE 计算** - 使用单期数据高估 2-4 倍

### 中优先级（建议修复）

5. ❌ **MongoDB PE 计算** - 使用单期净利润
6. ❌ **实时行情估值指标** - 建议移除或重构

### 低优先级（可选）

7. ⚠️ **PB 计算** - 净资产使用最新期数据，问题不大

---

## 📝 修复步骤建议

### 步骤 1: 修复 Tushare 市值计算

**目标**: 使用实际总股本计算市值

**方案 A**: 从 MongoDB 获取总股本

```python
# 从 stock_basic_info 集合获取总股本
stock_info = await self.db.stock_basic_info.find_one({"code": symbol})
if stock_info and 'total_share' in stock_info:
    total_share = stock_info['total_share']  # 万股
    market_cap = price_value * total_share * 10000  # 转换为元
else:
    logger.warning(f"⚠️ {symbol} 无法获取总股本，无法计算市值")
    market_cap = None
```

**方案 B**: 从 Tushare API 获取总股本

```python
# 从 Tushare daily_basic 获取总股本
daily_basic = await asyncio.to_thread(
    self.api.daily_basic,
    ts_code=ts_code,
    trade_date=trade_date,
    fields='total_share'
)
if daily_basic is not None and not daily_basic.empty:
    total_share = daily_basic.iloc[0]['total_share']  # 万股
    market_cap = price_value * total_share * 10000  # 转换为元
```

### 步骤 2: 修复 Tushare TTM 计算

**目标**: 计算 TTM 营业收入和净利润

**方案**: 参考 AKShare 数据源的实现

```python
def _calculate_ttm_from_tushare(income_statements: List[dict], field: str) -> Optional[float]:
    """
    从 Tushare 利润表数据计算 TTM
    
    Args:
        income_statements: 利润表数据列表（按报告期倒序）
        field: 字段名（'total_revenue' 或 'n_income'）
    
    Returns:
        TTM 值，如果无法计算则返回 None
    """
    if not income_statements or len(income_statements) < 1:
        return None
    
    latest = income_statements[0]
    latest_period = latest.get('end_date')
    latest_value = latest.get(field)
    
    if not latest_period or latest_value is None:
        return None
    
    # 判断是否是年报
    if latest_period.endswith('1231'):
        return latest_value
    
    # 非年报，需要计算 TTM
    # 查找最近年报和去年同期
    year = int(latest_period[:4])
    month_day = latest_period[4:]
    
    last_annual_period = f"{year-1}1231"
    last_same_period = f"{year-1}{month_day}"
    
    last_annual = next((x for x in income_statements if x.get('end_date') == last_annual_period), None)
    last_same = next((x for x in income_statements if x.get('end_date') == last_same_period), None)
    
    if last_annual and last_same:
        last_annual_value = last_annual.get(field)
        last_same_value = last_same.get(field)
        
        if last_annual_value is not None and last_same_value is not None:
            # TTM = 最近年报 + (本期 - 去年同期)
            return last_annual_value + (latest_value - last_same_value)
    
    # 降级：简单年化
    if month_day == '0630':
        return latest_value * 2
    elif month_day == '0331':
        return latest_value * 4
    elif month_day == '0930':
        return latest_value * 4 / 3
    
    return None
```

### 步骤 3: 修复 MongoDB PE 计算

**目标**: 使用 TTM 净利润

**方案**: 类似 PS 修复，添加 `net_profit_ttm` 字段

```python
# 在 scripts/sync_financial_data.py 中
ttm_net_profit = _calculate_ttm_net_profit(df)
financial_data['net_profit_ttm'] = ttm_net_profit

# 在 optimized_china_data.py 中
net_profit_ttm = latest_indicators.get('net_profit_ttm')
net_profit = latest_indicators.get('net_profit')
net_profit_for_pe = net_profit_ttm if net_profit_ttm and net_profit_ttm > 0 else net_profit
```

---

## 🚀 部署计划

### 阶段 1: 紧急修复（已完成）

- ✅ 修复 MongoDB PS 计算（使用 TTM）
- ✅ 添加单元测试验证 TTM 计算
- ✅ 标记 Tushare 和实时行情的问题

### 阶段 2: 高优先级修复（待实施）

- [ ] 修复 Tushare 市值计算（获取实际总股本）
- [ ] 修复 Tushare PS 计算（使用 TTM）
- [ ] 修复 Tushare PE 计算（使用 TTM）
- [ ] 重新同步所有股票的财务数据

### 阶段 3: 中优先级修复（待规划）

- [ ] 修复 MongoDB PE 计算（使用 TTM）
- [ ] 重构实时行情数据源（移除估值指标或使用 MongoDB 数据）

---

## 📚 参考资料

### 相关文档

- `docs/bugfix/2025-10-26-ps-calculation-fix.md` - PS 计算修复详细文档
- `scripts/test_ttm_calculation.py` - TTM 计算单元测试
- `scripts/sync_financial_data.py` - AKShare 数据同步脚本

### 相关代码

- `tradingagents/dataflows/optimized_china_data.py` - 数据提供者（三个数据源）
- `scripts/sync_financial_data.py` - 财务数据同步脚本

### 估值指标定义

- **PS（市销率）** = 总市值 / 营业收入（TTM）
- **PE（市盈率）** = 总市值 / 净利润（TTM）
- **PB（市净率）** = 总市值 / 净资产（最新期）
- **TTM（Trailing Twelve Months）** = 最近 12 个月的累计数据

---

## 🎯 总结

### 核心问题

1. **数据使用错误**: 使用单期数据而非 TTM 数据
2. **市值计算错误**: Tushare 使用固定股本（10亿股）
3. **影响范围广**: 三个数据源都存在问题

### 修复进展

- ✅ MongoDB PS 已修复
- ⚠️ Tushare 和实时行情已标记问题
- ❌ PE 计算尚未修复

### 后续工作

1. 修复 Tushare 市值计算（最高优先级）
2. 修复 Tushare PS/PE 计算（高优先级）
3. 修复 MongoDB PE 计算（中优先级）
4. 重构实时行情数据源（中优先级）
5. 重新同步所有财务数据
6. 更新用户文档

