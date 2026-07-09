# 实时行情数据源说明

## 📊 概述

实时行情采集任务 (`QuotesIngestionService`) 使用**多数据源自动切换机制**，确保在主数据源不可用时自动切换到备用数据源。

## 🔄 数据源优先级和自动切换

### 优先级顺序

| 优先级 | 数据源 | 是否支持实时行情 | 说明 |
|--------|--------|-----------------|------|
| **1** | **Tushare** | ✅ 是 | 优先使用，需要 Token |
| **2** | **AKShare** | ✅ 是 | 备用数据源，免费 |
| **3** | **BaoStock** | ❌ 否 | 不支持实时行情 |

### 自动切换逻辑

```python
# app/services/data_sources/manager.py
def get_realtime_quotes_with_fallback(self):
    """
    按优先级依次尝试获取实时行情：
    1. Tushare (优先级 1)
    2. AKShare (优先级 2)
    3. BaoStock (优先级 3，但不支持实时行情)
    
    返回首个成功的结果
    """
    available_adapters = self.get_available_adapters()
    for adapter in available_adapters:
        try:
            logger.info(f"Trying to fetch realtime quotes from {adapter.name}")
            data = adapter.get_realtime_quotes()
            if data:
                return data, adapter.name
        except Exception as e:
            logger.error(f"Failed to fetch realtime quotes from {adapter.name}: {e}")
            continue
    return None, None
```

## 📋 各数据源详细说明

### 1️⃣ Tushare（优先级 1）

**可用性检查**：
```python
def is_available(self) -> bool:
    return (
        self._provider is not None
        and getattr(self._provider, "connected", False)
        and self._provider.api is not None
    )
```

**条件**：
- ✅ Tushare Token 已配置
- ✅ 成功连接到 Tushare API
- ✅ API 对象已初始化

**实时行情接口**：
```python
def get_realtime_quotes(self):
    # 使用 Tushare rt_k 接口
    df = self._provider.api.rt_k(ts_code='3*.SZ,6*.SH,0*.SZ,9*.BJ')
    # 返回格式：{'000001': {'close': 10.5, 'pct_chg': 2.34, 'amount': 123456789.0, ...}}
```

**数据字段**：
- `close`: 最新价
- `pct_chg`: 涨跌幅（%）
- `amount`: 成交额（元）
- `open`: 开盘价
- `high`: 最高价
- `low`: 最低价
- `pre_close`: 昨收价
- `volume`: 成交量

**如果 Tushare 不可用**：
- ❌ Token 未配置 → `is_available()` 返回 `False`
- ❌ Token 无效 → `is_available()` 返回 `False`
- ❌ API 调用失败 → 抛出异常，自动切换到 AKShare
- ❌ 网络问题 → 抛出异常，自动切换到 AKShare

---

### 2️⃣ AKShare（优先级 2）

**可用性检查**：
```python
def is_available(self) -> bool:
    try:
        import akshare as ak
        return True
    except ImportError:
        return False
```

**条件**：
- ✅ AKShare 库已安装
- ✅ 无需 Token，完全免费

**实时行情接口**：
```python
def get_realtime_quotes(self):
    import akshare as ak
    # 使用东方财富实时行情接口
    df = ak.stock_zh_a_spot_em()
    # 返回格式：{'000001': {'close': 10.5, 'pct_chg': 2.34, 'amount': 123456789.0, ...}}
```

**数据字段**：
- `close`: 最新价（从"最新价"列）
- `pct_chg`: 涨跌幅（从"涨跌幅"列）
- `amount`: 成交额（从"成交额"列）
- `open`: 开盘价（从"今开"列）
- `high`: 最高价（从"最高"列）
- `low`: 最低价（从"最低"列）
- `pre_close`: 昨收价（从"昨收"列）
- `volume`: 成交量（从"成交量"列）

**优点**：
- ✅ 免费，无需 Token
- ✅ 数据来源稳定（东方财富）
- ✅ 覆盖全市场股票

**缺点**：
- ⚠️ 可能有频率限制
- ⚠️ 数据延迟可能略高于 Tushare

---

### 3️⃣ BaoStock（优先级 3）

**可用性检查**：
```python
def is_available(self) -> bool:
    try:
        import baostock as bs
        return True
    except ImportError:
        return False
```

**实时行情接口**：
```python
def get_realtime_quotes(self):
    """
    BaoStock 不支持全市场实时快照
    返回 None，允许切换到其他数据源
    """
    return None
```

**说明**：
- ❌ **不支持实时行情**
- ✅ 支持历史数据和每日基础数据
- ✅ 用于股票基础信息同步

---

## 🔍 实际运行场景

### 场景1：Tushare 正常工作

```
14:30:00 ─→ 任务触发
14:30:01 ─→ 检查可用数据源
14:30:02 ─→ Tushare is_available() = True
14:30:03 ─→ 尝试从 Tushare 获取行情
14:30:08 ─→ ✅ 成功获取 5438 只股票行情
14:30:10 ─→ 批量更新 MongoDB
14:30:12 ─→ 日志: "✅ 行情入库成功: 5438 只股票 (来源: tushare)"
```

### 场景2：Tushare 不可用，自动切换到 AKShare

```
14:30:00 ─→ 任务触发
14:30:01 ─→ 检查可用数据源
14:30:02 ─→ Tushare is_available() = False (Token 未配置)
14:30:03 ─→ ⚠️ 日志: "Data source tushare is not available"
14:30:04 ─→ AKShare is_available() = True
14:30:05 ─→ 尝试从 AKShare 获取行情
14:30:12 ─→ ✅ 成功获取 5438 只股票行情
14:30:15 ─→ 批量更新 MongoDB
14:30:17 ─→ 日志: "✅ 行情入库成功: 5438 只股票 (来源: akshare)"
```

### 场景3：Tushare 调用失败，自动切换到 AKShare

```
14:30:00 ─→ 任务触发
14:30:01 ─→ 检查可用数据源
14:30:02 ─→ Tushare is_available() = True
14:30:03 ─→ 尝试从 Tushare 获取行情
14:30:05 ─→ ❌ Tushare API 调用失败（网络超时）
14:30:06 ─→ ⚠️ 日志: "Failed to fetch realtime quotes from tushare: timeout"
14:30:07 ─→ 自动切换到 AKShare
14:30:08 ─→ AKShare is_available() = True
14:30:09 ─→ 尝试从 AKShare 获取行情
14:30:15 ─→ ✅ 成功获取 5438 只股票行情
14:30:18 ─→ 批量更新 MongoDB
14:30:20 ─→ 日志: "✅ 行情入库成功: 5438 只股票 (来源: akshare)"
```

### 场景4：所有数据源都不可用

```
14:30:00 ─→ 任务触发
14:30:01 ─→ 检查可用数据源
14:30:02 ─→ Tushare is_available() = False
14:30:03 ─→ AKShare is_available() = False (库未安装)
14:30:04 ─→ BaoStock is_available() = True
14:30:05 ─→ 尝试从 BaoStock 获取行情
14:30:06 ─→ ❌ BaoStock 返回 None（不支持实时行情）
14:30:07 ─→ ⚠️ 日志: "未获取到行情数据，跳过本次入库"
14:30:08 ─→ 任务结束，等待下次执行
```

---

## ⚙️ 配置说明

### Tushare 配置

在 `.env` 文件中配置：

```env
# Tushare Token（必需）
TUSHARE_TOKEN=your_tushare_token_here

# 是否启用 Tushare
TUSHARE_ENABLED=true
```

**如何获取 Tushare Token**：
1. 访问 https://tushare.pro/
2. 注册账号
3. 在"个人中心"获取 Token

### AKShare 配置

无需配置，只需确保已安装：

```bash
pip install akshare
```

### BaoStock 配置

无需配置，只需确保已安装：

```bash
pip install baostock
```

---

## 🛠️ 如何查看当前使用的数据源

### 方法1：查看日志

```bash
# 查看应用日志
tail -f logs/app.log

# 成功日志示例
[INFO] Trying to fetch realtime quotes from tushare
[INFO] ✅ 行情入库成功: 5438 只股票 (来源: tushare)

# 切换日志示例
[WARNING] Data source tushare is not available
[INFO] Data source akshare is available (priority: 2)
[INFO] Trying to fetch realtime quotes from akshare
[INFO] ✅ 行情入库成功: 5438 只股票 (来源: akshare)
```

### 方法2：查看 MongoDB

```javascript
// 查看最新的行情数据
db.market_quotes.findOne({}, {sort: {updated_at: -1}})

// 输出示例
{
  "code": "000001",
  "close": 10.50,
  "pct_chg": 2.34,
  "amount": 123456789.0,
  "trade_date": "20251017",
  "updated_at": "2025-10-17T14:30:00",
  "source": "tushare"  // 或 "akshare"
}
```

### 方法3：通过 API 测试

```bash
# 测试数据源可用性
POST /api/sync/multi-source/test-sources

# 返回示例
{
  "success": true,
  "data": [
    {
      "name": "tushare",
      "priority": 1,
      "available": true,
      "tests": {
        "get_stock_list": {"success": true, "count": 5438},
        "get_realtime_quotes": {"success": true, "count": 5438}
      }
    },
    {
      "name": "akshare",
      "priority": 2,
      "available": true,
      "tests": {
        "get_stock_list": {"success": true, "count": 5438},
        "get_realtime_quotes": {"success": true, "count": 5438}
      }
    }
  ]
}
```

---

## 🚨 常见问题

### Q1: 如果 Tushare 不可用，会发生什么？

**A**: 系统会**自动切换到 AKShare**，不会影响实时行情采集。

**流程**：
1. 检测到 Tushare 不可用
2. 自动尝试 AKShare
3. 如果 AKShare 可用，使用 AKShare 获取行情
4. 日志中会记录数据源切换信息

### Q2: AKShare 和 Tushare 的数据有差异吗？

**A**: 可能有轻微差异：
- **数据来源不同**：Tushare 和 AKShare 使用不同的数据源
- **更新频率不同**：Tushare 可能更新更快
- **字段精度不同**：小数位数可能略有差异

但对于大多数应用场景，差异可以忽略。

### Q3: 如何强制使用 AKShare？

**A**: 禁用 Tushare：

```env
# 方法1：不配置 Token
TUSHARE_TOKEN=

# 方法2：禁用 Tushare
TUSHARE_ENABLED=false
```

### Q4: 如何监控数据源切换？

**A**: 查看日志或设置告警：

```bash
# 监控日志中的数据源切换
grep "Data source.*is not available" logs/app.log

# 监控成功的数据源
grep "行情入库成功.*来源:" logs/app.log
```

### Q5: 如果所有数据源都不可用怎么办？

**A**: 系统会：
1. 记录警告日志："未获取到行情数据，跳过本次入库"
2. 保持上次的行情数据不变
3. 等待下次执行（30秒后）再次尝试

---

## ✅ 总结

| 特性 | 说明 |
|------|------|
| **主数据源** | Tushare（优先级 1） |
| **备用数据源** | AKShare（优先级 2） |
| **自动切换** | ✅ 是，无需人工干预 |
| **切换条件** | Tushare 不可用或调用失败 |
| **数据质量** | 两者数据质量相当 |
| **免费方案** | AKShare 完全免费 |

**关键点**：
- ✅ **自动容错**：Tushare 不可用时自动切换到 AKShare
- ✅ **无缝切换**：用户无感知，系统自动处理
- ✅ **日志记录**：所有切换都有日志记录
- ✅ **数据保障**：确保实时行情采集不中断

