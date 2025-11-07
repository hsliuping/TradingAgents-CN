# MongoDB 索引优化指南

## 📋 问题背景

### 慢查询日志示例

```json
{
  "t": {"$date": "2025-11-06T16:32:57.506+08:00"},
  "s": "I",
  "c": "WRITE",
  "id": 51803,
  "ctx": "conn650",
  "msg": "Slow query",
  "attr": {
    "type": "update",
    "ns": "tradingagents.stock_daily_quotes",
    "command": {
      "q": {
        "symbol": "688188",
        "trade_date": "2024-12-10",
        "data_source": "tushare",
        "period": "daily"
      },
      "u": {...}
    },
    "planSummary": "COLLSCAN",
    "execStats": {
      "stage": "UPDATE",
      "nReturned": 0,
      "executionTimeMillis": 287,
      "totalKeysExamined": 0,
      "totalDocsExamined": 4500,
      "nMatched": 1,
      "nModified": 1
    }
  }
}
```

### 问题分析

1. **执行时间**: 287 毫秒（慢）
2. **查询计划**: `COLLSCAN`（全集合扫描）
3. **扫描文档数**: 4500 个文档
4. **扫描索引键数**: 0（没有使用索引）
5. **根本原因**: 缺少匹配查询条件的索引

## 🔍 索引设计原则

### 1. 复合索引字段顺序

MongoDB 复合索引的字段顺序非常重要，应该遵循 **ESR 原则**：

- **E (Equality)**: 等值查询字段放在最前面
- **S (Sort)**: 排序字段放在中间
- **R (Range)**: 范围查询字段放在最后

### 2. 查询条件匹配

对于查询条件：
```javascript
{
  "symbol": "688188",           // 等值查询
  "trade_date": "2024-12-10",   // 等值查询
  "data_source": "tushare",     // 等值查询
  "period": "daily"             // 等值查询
}
```

最优索引应该是：
```javascript
db.stock_daily_quotes.createIndex({
  "symbol": 1,
  "data_source": 1,
  "trade_date": 1,
  "period": 1
})
```

或者（根据查询频率调整顺序）：
```javascript
db.stock_daily_quotes.createIndex({
  "symbol": 1,
  "trade_date": 1,
  "data_source": 1,
  "period": 1
})
```

### 3. 索引覆盖查询

如果查询只需要索引中的字段，MongoDB 可以直接从索引返回结果，无需访问文档（Covered Query）。

## 🔧 优化方案

### 方案 1：使用自动化脚本（推荐）

运行索引优化脚本：

```bash
# 激活虚拟环境
source env/bin/activate  # Linux/Mac
# 或
.\env\Scripts\activate   # Windows

# 运行优化脚本
python scripts/maintenance/optimize_mongodb_indexes.py
```

脚本会自动：
1. ✅ 分析现有索引
2. ✅ 创建优化索引
3. ✅ 测试查询性能
4. ✅ 生成优化报告

### 方案 2：手动创建索引

#### 2.1 连接到 MongoDB

```bash
# Docker 环境
docker exec -it tradingagents-mongodb mongosh -u admin -p your_password --authenticationDatabase admin

# 本地环境
mongosh mongodb://localhost:27017/tradingagents
```

#### 2.2 切换到数据库

```javascript
use tradingagents
```

#### 2.3 创建索引

```javascript
// 1. 慢查询优化索引（匹配 update 操作的查询条件）
db.stock_daily_quotes.createIndex(
  {
    "symbol": 1,
    "data_source": 1,
    "trade_date": 1,
    "period": 1
  },
  {
    name: "symbol_source_date_period_idx",
    background: true  // 后台创建，不阻塞数据库
  }
)

// 2. 查询优化索引（按股票代码+周期查询）
db.stock_daily_quotes.createIndex(
  {
    "symbol": 1,
    "period": 1,
    "trade_date": -1
  },
  {
    name: "symbol_period_date_idx",
    background: true
  }
)

// 3. 查询优化索引（按股票代码查询）
db.stock_daily_quotes.createIndex(
  {
    "symbol": 1,
    "trade_date": -1
  },
  {
    name: "symbol_date_idx",
    background: true
  }
)

// 4. 数据源索引
db.stock_daily_quotes.createIndex(
  {
    "data_source": 1
  },
  {
    name: "data_source_idx",
    background: true
  }
)
```

#### 2.4 验证索引

```javascript
// 查看所有索引
db.stock_daily_quotes.getIndexes()

// 查看索引大小
db.stock_daily_quotes.stats()
```

## 📊 性能测试

### 测试查询性能

```javascript
// 测试慢查询场景
db.stock_daily_quotes.find({
  "symbol": "688188",
  "trade_date": "2024-12-10",
  "data_source": "tushare",
  "period": "daily"
}).explain("executionStats")
```

### 关键指标

查看 `explain()` 输出中的关键指标：

1. **executionTimeMillis**: 执行时间（毫秒）
   - ✅ < 10ms: 优秀
   - ⚠️ 10-100ms: 可接受
   - ❌ > 100ms: 需要优化

2. **totalDocsExamined**: 扫描的文档数
   - ✅ 应该接近 `nReturned`（返回的文档数）
   - ❌ 如果远大于 `nReturned`，说明索引不够优化

3. **totalKeysExamined**: 扫描的索引键数
   - ✅ 应该接近 `nReturned`
   - ❌ 如果为 0，说明没有使用索引

4. **stage**: 查询阶段
   - ✅ `IXSCAN`: 使用了索引扫描
   - ❌ `COLLSCAN`: 全集合扫描（需要添加索引）

### 优化前后对比

**优化前**（COLLSCAN）：
```json
{
  "executionTimeMillis": 287,
  "totalDocsExamined": 4500,
  "totalKeysExamined": 0,
  "stage": "COLLSCAN"
}
```

**优化后**（IXSCAN）：
```json
{
  "executionTimeMillis": 2,
  "totalDocsExamined": 1,
  "totalKeysExamined": 1,
  "stage": "IXSCAN",
  "indexName": "symbol_source_date_period_idx"
}
```

性能提升：**287ms → 2ms**（提升 143 倍）

## 🎯 索引维护建议

### 1. 定期监控慢查询

```bash
# 查看 MongoDB 慢查询日志
docker logs tradingagents-mongodb | grep "Slow query"
```

### 2. 定期运行优化脚本

建议每月运行一次索引优化脚本：

```bash
# 添加到 crontab（每月1号凌晨2点）
0 2 1 * * cd /path/to/TradingAgentsCN && python scripts/maintenance/optimize_mongodb_indexes.py
```

### 3. 监控索引大小

索引会占用存储空间，定期检查：

```javascript
// 查看集合统计信息
db.stock_daily_quotes.stats()

// 查看索引大小
db.stock_daily_quotes.totalIndexSize()
```

### 4. 删除未使用的索引

```javascript
// 查看索引使用情况（MongoDB 4.4+）
db.stock_daily_quotes.aggregate([
  { $indexStats: {} }
])

// 删除未使用的索引
db.stock_daily_quotes.dropIndex("unused_index_name")
```

## 📚 参考资料

- [MongoDB 索引最佳实践](https://www.mongodb.com/docs/manual/indexes/)
- [MongoDB 查询优化](https://www.mongodb.com/docs/manual/core/query-optimization/)
- [MongoDB Explain 输出解读](https://www.mongodb.com/docs/manual/reference/explain-results/)

## 🆘 常见问题

### Q1: 索引创建需要多长时间？

**A**: 取决于集合大小：
- 小集合（< 10万文档）：几秒钟
- 中等集合（10万-100万文档）：几分钟
- 大集合（> 100万文档）：可能需要几十分钟

建议使用 `background: true` 选项，在后台创建索引，不阻塞数据库操作。

### Q2: 索引会占用多少存储空间？

**A**: 通常是数据大小的 10-30%。可以通过 `db.collection.stats()` 查看。

### Q3: 索引越多越好吗？

**A**: 不是！索引的缺点：
- ❌ 占用存储空间
- ❌ 写入操作变慢（需要更新索引）
- ❌ 内存占用增加

建议：只为**频繁查询**的字段创建索引。

### Q4: 如何判断是否需要添加索引？

**A**: 监控慢查询日志，如果看到：
- `planSummary: "COLLSCAN"`
- `executionTimeMillis > 100`
- `totalDocsExamined >> nReturned`

说明需要添加索引。

## ✅ 总结

1. ✅ 使用自动化脚本优化索引
2. ✅ 定期监控慢查询日志
3. ✅ 测试查询性能，确认优化效果
4. ✅ 根据实际查询模式调整索引
5. ✅ 删除未使用的索引，节省资源

