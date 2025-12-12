# 修复财务数据 code 字段缺失问题

## 问题描述

保存财务数据时出现 MongoDB 唯一索引冲突错误：

```
E11000 duplicate key error collection: tradingagents.stock_financial_data 
index: code_period_source_unique 
dup key: { code: null, report_period: "20251231", data_source: "akshare" }
```

**错误信息解读**：
- **集合**：`stock_financial_data`（财务数据表）
- **唯一索引**：`code_period_source_unique`（股票代码 + 报告期 + 数据源）
- **冲突键值**：`code: null`（**股票代码为空！**）
- **报告期**：`20251231`
- **数据源**：`akshare`

---

## 问题原因

### 1. **索引定义与字段不匹配**

MongoDB 中的唯一索引使用 `code` 字段：

```javascript
// 唯一索引定义
db.stock_financial_data.createIndex(
    { "code": 1, "report_period": -1, "data_source": 1 },
    { unique: true, name: "code_period_source_unique" }
)
```

但是，财务数据标准化时只设置了 `symbol` 字段，**没有设置 `code` 字段**：

```python
# 错误的代码（缺少 code 字段）
base_data = {
    "symbol": symbol,        # ✅ 有 symbol
    # "code": symbol,        # ❌ 缺少 code
    "full_symbol": self._get_full_symbol(symbol, market),
    "market": market,
    "report_period": report_period,
    "data_source": "akshare",
    # ...
}
```

### 2. **历史遗留问题**

项目中存在一个迁移脚本 `migrate_financial_data_symbol_to_code.py`，用于将 `symbol` 字段迁移到 `code` 字段：

```python
# 迁移脚本的目的
# 1. 将 symbol 复制到 code
# 2. 删除旧的 symbol_period_source_unique 索引
# 3. 创建新的 code_period_source_unique 索引
# 4. 删除 symbol 字段
```

但是，**新代码仍然使用 `symbol` 字段**，导致：
- 保存数据时没有 `code` 字段
- MongoDB 中 `code` 为 `null`
- 违反唯一索引约束（多条记录的 `code` 都是 `null`）

---

## 解决方案

### 修复方法

在所有财务数据标准化方法中，**同时设置 `code` 和 `symbol` 字段**，以兼容新旧索引：

#### 1. **修复 AKShare 数据标准化**

<augment_code_snippet path="app/services/financial_data_service.py" mode="EXCERPT">
```python
def _standardize_akshare_data(
    self,
    symbol: str,
    financial_data: Dict[str, Any],
    market: str,
    report_period: str,
    report_type: str,
    now: datetime
) -> Dict[str, Any]:
    """标准化AKShare财务数据"""
    base_data = {
        "code": symbol,      # ✅ 添加 code 字段
        "symbol": symbol,    # ✅ 保留 symbol 字段
        "full_symbol": self._get_full_symbol(symbol, market),
        "market": market,
        "report_period": report_period or self._extract_latest_period(financial_data),
        "report_type": report_type,
        "data_source": "akshare",
        "created_at": now,
        "updated_at": now,
        "version": 1
    }
    
    # 提取关键财务指标
    base_data.update(self._extract_akshare_indicators(financial_data))
    return base_data
```
</augment_code_snippet>

#### 2. **修复 Tushare 数据标准化**

<augment_code_snippet path="app/services/financial_data_service.py" mode="EXCERPT">
```python
def _standardize_tushare_data(
    self,
    symbol: str,
    financial_data: Dict[str, Any],
    market: str,
    report_period: str,
    report_type: str,
    now: datetime
) -> Dict[str, Any]:
    """标准化Tushare财务数据"""
    base_data = {
        "code": symbol,      # ✅ 添加 code 字段
        "symbol": symbol,    # ✅ 保留 symbol 字段
        "full_symbol": self._get_full_symbol(symbol, market),
        "market": market,
        "report_period": report_period or financial_data.get("report_period"),
        "report_type": report_type or financial_data.get("report_type", "quarterly"),
        "data_source": "tushare",
        "created_at": now,
        "updated_at": now,
        "version": 1
    }
    
    # 合并Tushare标准化后的财务数据
    exclude_fields = {'symbol', 'data_source', 'updated_at'}
    for key, value in financial_data.items():
        if key not in exclude_fields:
            base_data[key] = value
    
    return base_data
```
</augment_code_snippet>

#### 3. **修复 BaoStock 数据标准化**

<augment_code_snippet path="app/services/financial_data_service.py" mode="EXCERPT">
```python
def _standardize_baostock_data(
    self,
    symbol: str,
    financial_data: Dict[str, Any],
    market: str,
    report_period: str,
    report_type: str,
    now: datetime
) -> Dict[str, Any]:
    """标准化BaoStock财务数据"""
    base_data = {
        "code": symbol,      # ✅ 添加 code 字段
        "symbol": symbol,    # ✅ 保留 symbol 字段
        "full_symbol": self._get_full_symbol(symbol, market),
        "market": market,
        "report_period": report_period or self._generate_current_period(),
        "report_type": report_type,
        "data_source": "baostock",
        "created_at": now,
        "updated_at": now,
        "version": 1
    }
    
    # 合并BaoStock财务数据
    base_data.update(financial_data)
    return base_data
```
</augment_code_snippet>

---

## 验证修复

### 1. **重启后端服务**

```bash
# Docker 环境
docker restart tradingagents-backend

# 本地环境
# 停止后端进程，然后重新启动
```

### 2. **检查日志**

等待下一次财务数据同步，检查日志：

```bash
# Docker 环境
docker logs -f tradingagents-backend | grep "财务数据"

# 本地环境
tail -f logs/tradingagents.log | grep "财务数据"
```

**预期结果**：
- ✅ 不再出现 `E11000 duplicate key error`
- ✅ 财务数据保存成功
- ✅ 日志显示：`✅ {symbol} 财务数据保存完成: X条记录`

### 3. **验证数据库**

```bash
# 连接 MongoDB
docker exec -it tradingagents-mongodb mongo tradingagents -u admin -p tradingagents123 --authenticationDatabase admin

# 检查 stock_financial_data 集合
db.stock_financial_data.find({}, {code: 1, symbol: 1, report_period: 1, data_source: 1}).limit(5)
```

**预期结果**：
```javascript
{ "code" : "000001", "symbol" : "000001", "report_period" : "20251231", "data_source" : "akshare" }
{ "code" : "000002", "symbol" : "000002", "report_period" : "20251231", "data_source" : "akshare" }
// code 字段不再为 null
```

---

## 清理旧数据（可选）

如果数据库中已经存在 `code` 为 `null` 的记录，需要清理：

```javascript
// 连接 MongoDB
docker exec -it tradingagents-mongodb mongo tradingagents -u admin -p tradingagents123 --authenticationDatabase admin

// 查看有多少条 code 为 null 的记录
db.stock_financial_data.count({ code: null })

// 删除 code 为 null 的记录
db.stock_financial_data.deleteMany({ code: null })

// 验证删除结果
db.stock_financial_data.count({ code: null })  // 应该返回 0
```

---

## 索引管理建议

### 当前索引状态

```javascript
// 查看当前索引
db.stock_financial_data.getIndexes()
```

**可能的索引**：
1. `code_period_source_unique` - 使用 `code` 字段（新索引）
2. `symbol_period_source_unique` - 使用 `symbol` 字段（旧索引）

### 推荐操作

**方案 1：保留两个字段（推荐）**
- 同时保留 `code` 和 `symbol` 字段
- 兼容新旧代码
- 便于数据迁移和回滚

**方案 2：统一使用 `code` 字段**
- 删除 `symbol` 字段
- 只使用 `code` 字段
- 需要修改所有相关代码

---

## 相关文件

### 修改的文件

1. **app/services/financial_data_service.py**
   - `_standardize_tushare_data()` - 添加 `code` 字段
   - `_standardize_akshare_data()` - 添加 `code` 字段
   - `_standardize_baostock_data()` - 添加 `code` 字段

### 相关脚本

1. **scripts/migrate_financial_data_symbol_to_code.py**
   - 数据迁移脚本（将 `symbol` 迁移到 `code`）

2. **scripts/setup/create_financial_data_collection.py**
   - 创建财务数据集合和索引

3. **scripts/mongo-init.js**
   - MongoDB 初始化脚本

---

## 总结

### 问题

- MongoDB 唯一索引使用 `code` 字段
- 财务数据标准化时只设置了 `symbol` 字段
- 导致 `code` 为 `null`，违反唯一索引约束

### 修复

- 在所有财务数据标准化方法中添加 `code` 字段
- 同时保留 `symbol` 字段以兼容旧代码
- 确保 `code` 和 `symbol` 的值相同

### 影响

- 修复后，所有新保存的财务数据都会包含 `code` 字段
- 不再出现唯一索引冲突错误
- 提高数据质量和系统稳定性

---

**修复已完成！** 🎉

重启后端服务后，问题将得到解决。

