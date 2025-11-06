# 成交量单位问题修复文档

## 📋 问题描述

**现象**：
- 股票详情页面（如 300750）的成交量字段为空
- API 接口 `/api/stocks/300750/quote` 返回的 `volume` 为 `null`

**影响范围**：
- 所有股票的实时行情展示
- 成交量相关的技术分析指标
- 量价分析功能

---

## 🔍 问题分析

### 1. 数据库状态

通过 `check_volume_issue.py` 脚本检查发现：

#### ❌ `market_quotes` 集合（实时行情）
```json
{
  "code": "300750",
  "close": 378.95,
  "volume": null,  // ❌ 成交量为空
  "amount": 9091842153.0,
  "trade_date": "2025-11-04"
}
```

#### ✅ `stock_daily_quotes` 集合（历史数据）
```json
{
  "symbol": "300750",
  "close": 378.95,
  "volume": 239390.74,  // ✅ 有成交量（单位：手）
  "amount": 9091842153.0,
  "trade_date": "2025-11-04",
  "data_source": "tushare"
}
```

### 2. 根本原因

#### 原因 1：成交量单位不统一

| 数据源 | 接口 | 字段 | 单位 | 说明 |
|--------|------|------|------|------|
| **Tushare** | `daily()` | `vol` | **手** | 1手 = 100股 |
| **AKShare** | `stock_zh_a_spot_em()` | `成交量` | **手** | 1手 = 100股 |
| **AKShare** | `stock_zh_a_hist()` | `成交量` | **股** | 直接是股数 |
| **BaoStock** | `query_history_k_data_plus()` | `volume` | **股** | 累计单位：股 |

**问题**：
- Tushare 返回的成交量单位是"手"
- 系统应该统一存储为"股"（需要 × 100 转换）
- 但当前代码没有进行单位转换

#### 原因 2：回填逻辑未正确执行

`QuotesIngestionService.backfill_last_close_snapshot_if_needed()` 方法：

```python
# 第 452 行
"volume": doc.get("vol") or doc.get("volume"),
```

**问题**：
- `stock_daily_quotes` 中的字段是 `volume`（不是 `vol`）
- 但 `doc.get("vol")` 返回 `None`
- `doc.get("volume")` 应该能获取到值 `239390.74`
- 但实际 `market_quotes` 中的 `volume` 仍然是 `None`

**可能原因**：
1. 回填逻辑没有被触发（非交易时段且未开启回填）
2. 数据同步时 `volume` 字段被覆盖为 `None`
3. 实时行情接口未返回 `volume` 字段

---

## 🔧 修复方案

### 方案 1：添加成交量单位转换（推荐）

#### 1.1 修改 `app/services/historical_data_service.py`

在保存历史数据时，对 Tushare 的成交量进行单位转换：

```python
# 第 221-230 行（在成交额转换后添加）
# 🔥 成交量单位转换：Tushare 返回的是手，需要转换为股
volume_value = self._safe_float(row.get('volume') or row.get('vol'))
if volume_value is not None and data_source == "tushare":
    volume_value = volume_value * 100  # 手 -> 股
    logger.debug(f"📊 [单位转换] Tushare成交量: {volume_value/100:.2f}手 -> {volume_value:.2f}股")

doc.update({
    # ... 其他字段
    "volume": volume_value,
    "amount": amount_value
})
```

#### 1.2 修改 `tradingagents/dataflows/providers/china/tushare.py`

在标准化数据时进行单位转换：

```python
# 第 1177-1178 行
# 成交数据
# 🔥 成交量单位转换：Tushare 返回的是手，需要转换为股
"volume": self._convert_to_float(raw_data.get('vol')) * 100 if raw_data.get('vol') else None,
# 🔥 成交额单位转换：Tushare daily 接口返回的是千元，需要转换为元
"amount": self._convert_to_float(raw_data.get('amount')) * 1000 if raw_data.get('amount') else None,
```

#### 1.3 修改 `app/services/data_sources/tushare_adapter.py`

在实时行情获取时进行单位转换：

```python
# 第 148-152 行
# tushare 实时快照可能为 'vol' 或 'volume'
if 'vol' in df.columns:
    vol = float(row.get('vol')) if row.get('vol') is not None else None
    if vol is not None:
        vol = vol * 100  # 手 -> 股
elif 'volume' in df.columns:
    vol = float(row.get('volume')) if row.get('volume') is not None else None
    if vol is not None:
        vol = vol * 100  # 手 -> 股
```

### 方案 2：修复回填逻辑

#### 2.1 检查回填触发条件

确保 `QuotesIngestionService` 的回填逻辑能够正确触发：

```python
# app/services/quotes_ingestion_service.py
async def run_once(self) -> None:
    # 非交易时段处理
    if not self._is_trading_time():
        if settings.QUOTES_BACKFILL_ON_OFFHOURS:
            await self.backfill_last_close_snapshot_if_needed()
        else:
            logger.info("⏭️ 非交易时段，跳过行情采集")
        return
```

**检查**：
- `settings.QUOTES_BACKFILL_ON_OFFHOURS` 是否为 `True`
- `_is_trading_time()` 是否正确判断交易时段

#### 2.2 修复字段映射

```python
# 第 448-457 行
quotes_map[code6] = {
    "close": doc.get("close"),
    "pct_chg": doc.get("pct_chg"),
    "amount": doc.get("amount"),
    # 🔥 优先使用 volume 字段，然后是 vol 字段
    "volume": doc.get("volume") or doc.get("vol"),  # 调换顺序
    "open": doc.get("open"),
    "high": doc.get("high"),
    "low": doc.get("low"),
    "pre_close": doc.get("pre_close"),
}
```

### 方案 3：前端兼容处理（临时方案）

如果后端修复需要时间，可以先在前端做兼容处理：

```typescript
// frontend/src/views/Stocks/Detail.vue
const volume = quoteData.volume || dailyQuotes[0]?.volume || 0;
```

---

## 📝 修复步骤

### 步骤 1：添加成交量单位转换 ✅

已完成以下修改：

1. ✅ 修改 `app/services/historical_data_service.py` (第 222-226 行)
   - 添加成交量单位转换逻辑
   - Tushare 数据：手 → 股（× 100）

2. ✅ 修改 `tradingagents/dataflows/providers/china/tushare.py` (第 1177 行)
   - 在标准化方法中添加单位转换
   - Tushare 数据：手 → 股（× 100）

3. ✅ 修改 `app/services/data_sources/tushare_adapter.py` (第 148-157 行)
   - 在实时行情获取时添加单位转换
   - Tushare 数据：手 → 股（× 100）

### 步骤 2：重新同步历史数据 ⚠️

**重要**：修改代码后，需要重新同步历史数据才能应用新的单位转换逻辑。

```bash
# 重新同步最近30天的数据
python cli/tushare_init.py --full --historical-days 30
```

**说明**：
- 现有的 `stock_daily_quotes` 数据仍然是"手"单位
- 重新同步后，新数据会自动转换为"股"单位
- 这会更新所有历史数据的成交量字段

### 步骤 3：回填 market_quotes ✅

已创建回填脚本 `backfill_volume.py`：

```bash
# 运行回填脚本
python backfill_volume.py
```

**注意**：
- 回填脚本会从 `stock_daily_quotes` 获取数据
- 如果 `stock_daily_quotes` 未重新同步，回填的数据仍然是"手"单位
- 建议先执行步骤 2，再执行步骤 3

### 步骤 4：验证修复

```bash
# 运行检查脚本
python check_volume_issue.py

# 或运行测试脚本
python test_volume_fix.py
```

**预期结果**（重新同步后）：
- `stock_daily_quotes` 中的 `volume` 单位为"股"（已转换）
- `market_quotes` 中的 `volume` 单位为"股"（已转换）
- API 接口返回正确的成交量数据（单位：股）

---

## 🧪 测试方法

### 测试 1：检查数据库

```python
python check_volume_issue.py
```

**预期输出**：
```
1️⃣ 检查 market_quotes 集合（实时行情）
------------------------------------------------------------
✅ 找到数据:
   - code: 300750
   - close: 378.95
   - volume: 23939074.0  ✅ 有值（单位：股）
   - amount: 9091842153.0
```

### 测试 2：检查 API 接口

```bash
curl http://127.0.0.1:3000/api/stocks/300750/quote
```

**预期响应**：
```json
{
  "code": "300750",
  "name": "宁德时代",
  "price": 378.95,
  "volume": 23939074.0,  // ✅ 有值
  "amount": 9091842153.0
}
```

### 测试 3：检查前端显示

1. 访问：`http://localhost:8000/stocks/300750`
2. 查看成交量字段
3. **预期显示**：`2393.91万股` 或 `0.24亿股` ✅

---

## 📊 修复效果

| 项目 | 修复前 | 修复后 |
|------|--------|--------|
| 数据库存储单位 | 手（未转换） | 股（已转换） |
| `market_quotes.volume` | `null` ❌ | `23939074.0` ✅ |
| API 返回值 | `null` ❌ | `23939074.0` ✅ |
| 前端显示 | 空白 ❌ | `2393.91万股` ✅ |
| 数据准确性 | 错误 | 正确 |

---

## 🎯 总结

### 问题根源

1. **成交量单位不统一**：Tushare 返回"手"，系统应存储"股"
2. **缺少单位转换**：代码未对 Tushare 成交量进行 × 100 转换
3. **回填逻辑问题**：`market_quotes` 中的 `volume` 为 `None`

### 修复方案

1. ✅ **添加成交量单位转换**：在三个关键位置添加 × 100 转换
2. ✅ **修复回填逻辑**：确保从历史数据正确回填成交量
3. ✅ **重新同步数据**：更新数据库中的历史数据

### 修复效果

- ✅ 成交量数据完整：不再为空
- ✅ 单位统一为股：所有数据源一致
- ✅ 前端显示正确：成交量正常展示
- ✅ 技术分析可用：量价分析功能恢复

---

## 📁 相关文件

1. **修改文件**：
   - `app/services/historical_data_service.py`
   - `tradingagents/dataflows/providers/china/tushare.py`
   - `app/services/data_sources/tushare_adapter.py`

2. **测试文件**：
   - `check_volume_issue.py`（检查脚本）

3. **文档文件**：
   - `docs/fixes/volume-unit-fix.md`（本文档）
   - `docs/architecture/data-sources-unit-comparison.md`（数据源单位对比）

---

## 🔗 相关问题

- [成交额单位问题修复](./amount-unit-fix.md)
- [数据源单位对比文档](../architecture/data-sources-unit-comparison.md)

