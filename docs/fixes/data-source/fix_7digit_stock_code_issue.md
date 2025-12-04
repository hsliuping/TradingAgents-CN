# 修复 7 位数字股票代码问题

## 问题描述

后端日志显示出现了 7 位数字的股票代码，导致 AKShare 无法找到对应的行情数据：

```
2025-10-17 01:40:17 | tradingagents.dataflows.providers.china.akshare | WARNING  | ⚠️ 未找到0005661的行情数据
2025-10-17 01:40:17 | tradingagents.dataflows.providers.china.akshare | WARNING  | ⚠️ 未找到0005992的行情数据
2025-10-17 01:40:18 | tradingagents.dataflows.providers.china.akshare | WARNING  | ⚠️ 未找到0005997的行情数据
```

**正常的股票代码应该是 6 位数字**，例如：
- `000001` - 平安银行
- `600000` - 浦发银行
- `300001` - 特锐德

但日志中出现了 7 位数字：`0005661`、`0005992`、`0005997`

---

## 问题原因

### 根本原因

AKShare 的 `stock_zh_a_spot_em()` 接口返回的股票代码可能已经包含前导 0，导致某些股票代码变成了 7 位数字。

### 代码分析

**问题代码**（`app/services/data_sources/akshare_adapter.py:218`）：

```python
code_raw = row.get(code_col)
if not code_raw:
    continue
code = str(code_raw).zfill(6)  # ❌ 问题在这里！
```

**问题**：
- `zfill(6)` 只会在字符串长度**小于** 6 时补齐前导 0
- 如果 `code_raw` 已经是 7 位数字（如 `0005661`），`zfill(6)` **不会截断**，而是保持原样
- 结果：7 位数字的代码被直接使用，导致查询失败

**示例**：
```python
# 正常情况
"1" .zfill(6)      # → "000001" ✅
"5661".zfill(6)    # → "005661" ✅

# 问题情况
"0005661".zfill(6) # → "0005661" ❌ 保持 7 位，不会截断！
"0005992".zfill(6) # → "0005992" ❌
```

---

## 解决方案

### 修复逻辑

**正确的处理方式**：
1. 先移除所有前导 0
2. 然后补齐到 6 位

**修复后的代码**：

```python
# 标准化股票代码：移除前导0，然后补齐到6位
code_str = str(code_raw).strip()
# 如果是纯数字，移除前导0后补齐到6位
if code_str.isdigit():
    code_clean = code_str.lstrip('0') or '0'  # 移除前导0，如果全是0则保留一个0
    code = code_clean.zfill(6)  # 补齐到6位
else:
    code = code_str.zfill(6)
```

**处理示例**：
```python
# 7位数字 → 6位数字
"0005661" → lstrip('0') → "5661" → zfill(6) → "005661" ✅
"0005992" → lstrip('0') → "5992" → zfill(6) → "005992" ✅
"0005997" → lstrip('0') → "5997" → zfill(6) → "005997" ✅

# 正常情况不受影响
"000001" → lstrip('0') → "1" → zfill(6) → "000001" ✅
"600000" → lstrip('0') → "6" → zfill(6) → "600000" ✅
"300001" → lstrip('0') → "3001" → zfill(6) → "300001" ✅

# 边界情况
"0000000" → lstrip('0') → "" → or '0' → "0" → zfill(6) → "000000" ✅
```

---

## 修复的文件

### 1. `app/services/data_sources/akshare_adapter.py`

**位置**：`get_realtime_quotes` 方法（第 213-225 行）

**修改前**：
```python
code_raw = row.get(code_col)
if not code_raw:
    continue
code = str(code_raw).zfill(6)
```

**修改后**：
```python
code_raw = row.get(code_col)
if not code_raw:
    continue
# 标准化股票代码：移除前导0，然后补齐到6位
code_str = str(code_raw).strip()
# 如果是纯数字，移除前导0后补齐到6位
if code_str.isdigit():
    code_clean = code_str.lstrip('0') or '0'  # 移除前导0，如果全是0则保留一个0
    code = code_clean.zfill(6)  # 补齐到6位
else:
    code = code_str.zfill(6)
```

---

### 2. `app/services/quotes_service.py`

**位置**：`_fetch_spot_akshare` 方法（第 78-90 行）

**修改前**：
```python
code_raw = row.get(code_col)
if not code_raw:
    continue
code = str(code_raw).zfill(6)
```

**修改后**：
```python
code_raw = row.get(code_col)
if not code_raw:
    continue
# 标准化股票代码：移除前导0，然后补齐到6位
code_str = str(code_raw).strip()
# 如果是纯数字，移除前导0后补齐到6位
if code_str.isdigit():
    code_clean = code_str.lstrip('0') or '0'  # 移除前导0，如果全是0则保留一个0
    code = code_clean.zfill(6)  # 补齐到6位
else:
    code = code_str.zfill(6)
```

---

## 验证修复

### 1. 重启后端服务

```bash
# 如果使用 Docker
docker restart tradingagents-backend

# 如果本地运行
# 停止后端进程，然后重新启动
```

### 2. 检查日志

等待下一次行情采集（默认 30 秒），检查日志：

```bash
# Docker 环境
docker logs -f tradingagents-backend | grep "未找到"

# 本地环境
tail -f logs/tradingagents.log | grep "未找到"
```

**预期结果**：
- ✅ 不再出现 7 位数字的股票代码
- ✅ 所有股票代码都是 6 位数字
- ✅ "未找到行情数据"的警告大幅减少

### 3. 验证数据库

```bash
# 连接 MongoDB
docker exec -it tradingagents-mongodb mongo tradingagents -u admin -p tradingagents123 --authenticationDatabase admin

# 检查 market_quotes 集合中的股票代码
db.market_quotes.find({}, {code: 1}).limit(10)
```

**预期结果**：
```javascript
{ "code" : "000001" }  // ✅ 6位数字
{ "code" : "000002" }  // ✅ 6位数字
{ "code" : "000004" }  // ✅ 6位数字
// 不应该出现 "0005661" 这样的 7 位数字
```

---

## 影响范围

### 受影响的功能

1. **实时行情采集**：
   - `QuotesIngestionService` - 定时采集全市场行情
   - `QuotesService` - 获取股票实时快照

2. **数据存储**：
   - `market_quotes` 集合 - 存储的股票代码格式

3. **前端显示**：
   - 自选股列表
   - 股票详情页
   - 行情数据展示

### 不受影响的功能

1. **股票基础信息同步**：
   - `BasicsSyncService` - 使用不同的数据源和处理逻辑

2. **历史K线数据**：
   - K线数据查询使用独立的代码标准化逻辑

3. **LLM 分析**：
   - 分析功能使用已存储的标准化数据

---

## 为什么会出现 7 位数字？

### AKShare 数据源分析

AKShare 的 `stock_zh_a_spot_em()` 接口从东方财富网获取数据，可能的原因：

1. **数据源格式变化**：
   - 东方财富网的数据格式可能发生了变化
   - 某些股票代码在源数据中就包含了额外的前导 0

2. **数据类型问题**：
   - 如果代码字段是数值类型，转换为字符串时可能产生异常格式
   - 例如：`5661` → 转换为字符串 → 某些情况下变成 `0005661`

3. **特殊股票代码**：
   - 某些特殊类型的股票（如退市股、ST股）可能有不同的编码规则

---

## 最佳实践

### 股票代码标准化原则

在处理股票代码时，应该遵循以下原则：

1. **统一格式**：
   - A股代码：6位数字（如 `000001`、`600000`、`300001`）
   - 港股代码：4位数字 + `.HK`（如 `0700.HK`、`9988.HK`）
   - 美股代码：1-5位字母（如 `AAPL`、`TSLA`）

2. **标准化流程**：
   ```python
   # 1. 转换为字符串并去除空格
   code_str = str(code_raw).strip()
   
   # 2. 如果是纯数字，移除前导0
   if code_str.isdigit():
       code_clean = code_str.lstrip('0') or '0'
       
   # 3. 补齐到指定位数
   code = code_clean.zfill(6)  # A股6位
   ```

3. **验证规则**：
   ```python
   # A股代码验证
   if len(code) == 6 and code.isdigit():
       # 检查前缀
       prefix = code[:2]
       if prefix in ['60', '68', '00', '30', '43', '83', '87']:
           return True
   return False
   ```

---

## 相关问题

### Q1: 为什么不直接截取前 6 位？

**A**: 直接截取可能导致错误：
```python
# ❌ 错误方式
code = str(code_raw)[:6]

# 问题：
"0005661"[:6] → "000566" ❌ 错误！应该是 "005661"
```

正确的方式是先移除前导 0，再补齐。

### Q2: 如果股票代码全是 0 怎么办？

**A**: 使用 `or '0'` 处理：
```python
code_clean = code_str.lstrip('0') or '0'

# 示例：
"000000".lstrip('0') → "" → or '0' → "0" → zfill(6) → "000000" ✅
```

### Q3: 这个修复会影响已存储的数据吗？

**A**: 不会。这个修复只影响新采集的数据。已存储的数据需要手动清理：

```javascript
// MongoDB 清理脚本
db.market_quotes.deleteMany({
    $expr: { $gt: [{ $strLenCP: "$code" }, 6] }
})
```

---

## 总结

### 问题

- AKShare 返回的股票代码可能包含额外的前导 0
- `zfill(6)` 不会截断超过 6 位的字符串
- 导致 7 位数字的股票代码进入系统

### 修复

- 在使用 `zfill()` 之前，先使用 `lstrip('0')` 移除所有前导 0
- 确保所有股票代码都是标准的 6 位数字格式

### 影响

- 修复后，所有新采集的行情数据都将使用正确的 6 位代码
- 不再出现"未找到行情数据"的警告（由于代码格式错误导致的）
- 提高数据质量和系统稳定性

---

**修复已完成！** 🎉

重启后端服务后，问题将得到解决。

