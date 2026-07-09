# 数据源单位对比文档

## 📋 概述

本文档详细说明了三大数据源（Tushare、AKShare、BaoStock）返回的数据单位，以及系统中的单位转换策略。

---

## 📊 成交额单位对比

### 官方文档说明

| 数据源 | 接口 | 字段 | 单位 | 官方文档链接 |
|--------|------|------|------|-------------|
| **Tushare** | `daily()` | `amount` | **千元** | [日线行情](https://tushare.pro/document/2?doc_id=27) |
| **Tushare** | `weekly()` | `amount` | **千元** | [周线行情](https://tushare.pro/document/2?doc_id=144) |
| **Tushare** | `monthly()` | `amount` | **千元** | [月线行情](https://tushare.pro/document/2?doc_id=145) |
| **AKShare** | `stock_zh_a_spot_em()` | `成交额` | **元** | [沪深京A股](https://akshare.akfamily.xyz/data/stock/stock.html) |
| **AKShare** | `stock_zh_a_hist()` | `成交额` | **元** | [历史行情](https://akshare.akfamily.xyz/data/stock/stock.html) |
| **BaoStock** | `query_history_k_data_plus()` | `amount` | **元** | [历史K线](http://baostock.com/baostock/index.php/Python_API%E6%96%87%E6%A1%A3) |

### 关键发现

- ⚠️ **Tushare 是唯一使用千元作为成交额单位的数据源**
- ✅ **AKShare 和 BaoStock 都使用元作为成交额单位**
- 🔧 **系统需要对 Tushare 数据进行单位转换（千元 → 元）**

---

## 📊 成交量单位对比

| 数据源 | 接口 | 字段 | 单位 | 说明 |
|--------|------|------|------|------|
| **Tushare** | `daily()` | `vol` | **手** | 1手 = 100股 |
| **AKShare** | `stock_zh_a_spot_em()` | `成交量` | **手** | 1手 = 100股 |
| **AKShare** | `stock_zh_a_hist()` | `成交量` | **股** | 直接是股数 |
| **BaoStock** | `query_history_k_data_plus()` | `volume` | **股** | 累计单位：股 |

### 关键发现

- ⚠️ **成交量单位不统一：有的是手，有的是股**
- 🔧 **系统统一存储为股（需要将手转换为股：× 100）**

---

## 📊 市值单位对比

| 数据源 | 接口 | 字段 | 单位 | 说明 |
|--------|------|------|------|------|
| **Tushare** | `daily_basic()` | `total_mv` | **万元** | 总市值 |
| **Tushare** | `daily_basic()` | `circ_mv` | **万元** | 流通市值 |
| **AKShare** | `stock_individual_info_em()` | `总市值` | **元** | 需要除以1e8转为亿元 |
| **BaoStock** | - | - | - | 不提供市值数据 |

### 关键发现

- ⚠️ **Tushare 的市值单位是万元**
- ✅ **系统统一存储为亿元（Tushare: ÷ 10000，AKShare: ÷ 1e8）**

---

## 🔧 系统单位转换策略

### 1. 成交额转换

**目标单位**: **元**

**转换逻辑** (`app/services/historical_data_service.py`):

```python
# 成交额单位转换：Tushare 返回的是千元，需要转换为元
amount_value = self._safe_float(row.get('amount') or row.get('turnover'))
if amount_value is not None and data_source == "tushare":
    amount_value = amount_value * 1000  # 千元 -> 元
    logger.debug(f"📊 [单位转换] Tushare成交额: {amount_value/1000:.2f}千元 -> {amount_value:.2f}元")
```

**转换表**:

| 数据源 | 原始值 | 转换系数 | 转换后值 | 单位 |
|--------|--------|---------|---------|------|
| Tushare | 909180 | × 1000 | 9091800000 | 元 |
| AKShare | 9091800000 | × 1 | 9091800000 | 元 |
| BaoStock | 9091800000 | × 1 | 9091800000 | 元 |

### 2. 市值转换

**目标单位**: **亿元**

**转换逻辑** (`app/services/basics_sync/processing.py`):

```python
# 市值（万元 -> 亿元）
if "total_mv" in daily_metrics and daily_metrics["total_mv"] is not None:
    doc["total_mv"] = daily_metrics["total_mv"] / 10000
if "circ_mv" in daily_metrics and daily_metrics["circ_mv"] is not None:
    doc["circ_mv"] = daily_metrics["circ_mv"] / 10000
```

**转换表**:

| 数据源 | 原始值 | 原始单位 | 转换系数 | 转换后值 | 目标单位 |
|--------|--------|---------|---------|---------|---------|
| Tushare | 220063 | 万元 | ÷ 10000 | 2200.63 | 亿元 |
| AKShare | 22006300000000 | 元 | ÷ 1e8 | 2200.63 | 亿元 |

### 3. 成交量转换

**目标单位**: **股**

**转换逻辑**:

```python
# 如果数据源返回的是手，需要转换为股
if volume_unit == "手":
    volume = volume * 100  # 手 -> 股
```

---

## 📁 相关代码文件

### 成交额转换

1. **`app/services/historical_data_service.py`** (第 215-230 行)
   - 保存历史数据时进行 Tushare 成交额转换

2. **`tradingagents/dataflows/providers/china/tushare.py`** (第 1175-1178 行)
   - Tushare Provider 标准化数据时进行转换

### 市值转换

1. **`app/services/basics_sync/processing.py`** (第 16-20 行)
   - 将 Tushare 的市值从万元转换为亿元

2. **`app/services/basics_sync_service.py`** (第 199-210 行)
   - 基础信息同步时进行市值转换

### 数据标准化

1. **`tradingagents/dataflows/providers/china/akshare.py`** (第 712-751 行)
   - AKShare 历史数据列名标准化

2. **`tradingagents/dataflows/providers/china/tushare.py`** (第 1261-1278 行)
   - Tushare 历史数据标准化

---

## 🧪 测试方法

### 1. 测试 Tushare 成交额转换

```bash
python test_amount_fix.py
```

**预期输出**:
```
成交额(元): 9,091,800,000
成交额(亿元): 90.92
```

### 2. 测试 AKShare 成交额

```bash
python test_akshare_amount.py
```

**预期输出**:
```
成交额(元): 9,091,800,000
成交额(亿元): 90.92
```

### 3. 对比验证

| 数据源 | 成交额(元) | 成交额(亿元) | 成交额(万元) |
|--------|-----------|------------|------------|
| Tushare (转换后) | 9,091,800,000 | 90.92 | 909,180 |
| AKShare (原始) | 9,091,800,000 | 90.92 | 909,180 |
| BaoStock (原始) | 9,091,800,000 | 90.92 | 909,180 |

**✅ 所有数据源的成交额应该一致**

---

## 📊 前端显示格式

### 成交额格式化函数

**文件**: `frontend/src/views/Stocks/Detail.vue` (第 888-895 行)

```javascript
function fmtAmount(v: any) {
  const n = Number(v)
  if (!Number.isFinite(n)) return '-'
  if (n >= 1e12) return (n/1e12).toFixed(2) + '万亿'
  if (n >= 1e8) return (n/1e8).toFixed(2) + '亿'
  if (n >= 1e4) return (n/1e4).toFixed(2) + '万'
  return n.toFixed(0)
}
```

### 显示示例

| 数据库存储值(元) | 前端显示 |
|----------------|---------|
| 9,091,800,000 | 90.92亿 ✅ |
| 909,180 | 909.18万 ❌ (错误) |
| 9,091,800 | 909.18万 ❌ (错误) |

---

## 🎯 总结

### 单位统一标准

| 数据类型 | 系统统一单位 | 前端显示单位 |
|---------|------------|------------|
| 成交额 | 元 | 亿/万/元（自动） |
| 成交量 | 股 | 万股/股（自动） |
| 市值 | 亿元 | 亿元 |
| 价格 | 元 | 元 |

### 关键要点

1. ✅ **Tushare 成交额需要转换**：千元 → 元（× 1000）
2. ✅ **AKShare 和 BaoStock 成交额无需转换**：已经是元
3. ✅ **Tushare 市值需要转换**：万元 → 亿元（÷ 10000）
4. ✅ **所有数据源在入库时统一单位**：确保数据一致性
5. ✅ **前端按统一单位处理**：无需关心数据源差异

---

## 📚 参考资料

### 官方文档

- [Tushare 日线行情接口](https://tushare.pro/document/2?doc_id=27)
- [Tushare 每日指标接口](https://tushare.pro/document/2?doc_id=32)
- [AKShare 股票数据文档](https://akshare.akfamily.xyz/data/stock/stock.html)
- [BaoStock API 文档](http://baostock.com/baostock/index.php/Python_API%E6%96%87%E6%A1%A3)

### 内部文档

- [成交额单位修复文档](../fixes/amount-unit-fix.md)
- [MongoDB 集合对比文档](./database/MONGODB_COLLECTIONS_COMPARISON.md)
- [数据源迁移计划](../guides/tushare_unified/data_sources_migration_plan_a.md)

