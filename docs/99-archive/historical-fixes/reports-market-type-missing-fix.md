# 修复分析报告缺少市场类型字段问题

## 问题描述

用户反馈：分析报告页面显示"暂无数据"，后端返回的报告列表为空。

### 问题现象

1. **前端显示**：分析报告页面显示"暂无数据"
2. **后端日志**：查询条件包含 `market_type` 筛选，但数据库中的报告文档缺少 `market_type` 字段
3. **根本原因**：保存报告时没有保存 `market_type` 字段，导致市场筛选查询无法匹配到任何数据

### 错误日志示例

```
🔍 获取报告列表: 用户=xxx, 页码=1, 每页=20, 市场=A股
📊 查询条件: {"market_type": "A股"}
✅ 查询完成: 总数=0, 返回=0
```

## 问题根源

### 1. 保存报告时缺少 `market_type` 字段

**后端 API 保存逻辑** (`app/services/simple_analysis_service.py`)：

```python
# ❌ 旧代码 - 缺少 market_type 字段
document = {
    "analysis_id": analysis_id,
    "stock_symbol": stock_symbol,
    # 缺少 market_type 字段！
    "analysis_date": timestamp.strftime('%Y-%m-%d'),
    ...
}
```

**Web 保存逻辑** (`web/utils/mongodb_report_manager.py`)：

```python
# ❌ 旧代码 - 缺少 market_type 字段
document = {
    "analysis_id": analysis_id,
    "stock_symbol": stock_symbol,
    # 缺少 market_type 字段！
    "analysis_date": timestamp.strftime('%Y-%m-%d'),
    ...
}
```

### 2. 查询报告时使用 `market_type` 筛选

**后端查询逻辑** (`app/routers/reports.py`)：

```python
# 市场筛选
if market_filter:
    query["market_type"] = market_filter  # 查询 market_type 字段
```

**结果**：由于数据库中的报告文档没有 `market_type` 字段，查询无法匹配到任何数据。

## 解决方案

### 1. 保存报告时添加 `market_type` 字段

使用 `StockUtils.get_market_info()` 根据股票代码自动推断市场类型。

#### 修改 `app/services/simple_analysis_service.py`

```python
# ✅ 新代码 - 添加市场类型推断
from tradingagents.utils.stock_utils import StockUtils

# 根据股票代码推断市场类型
market_info = StockUtils.get_market_info(stock_symbol)
market_type_map = {
    "china_a": "A股",
    "hong_kong": "港股",
    "us": "美股",
    "unknown": "A股"  # 默认为A股
}
market_type = market_type_map.get(market_info.get("market", "unknown"), "A股")
logger.info(f"📊 推断市场类型: {stock_symbol} -> {market_type}")

# 构建文档
document = {
    "analysis_id": analysis_id,
    "stock_symbol": stock_symbol,
    "market_type": market_type,  # 🔥 添加市场类型字段
    "analysis_date": timestamp.strftime('%Y-%m-%d'),
    ...
}
```

#### 修改 `web/utils/mongodb_report_manager.py`

```python
# ✅ 新代码 - 添加市场类型推断
from tradingagents.utils.stock_utils import StockUtils

# 根据股票代码推断市场类型
market_info = StockUtils.get_market_info(stock_symbol)
market_type_map = {
    "china_a": "A股",
    "hong_kong": "港股",
    "us": "美股",
    "unknown": "A股"
}
market_type = market_type_map.get(market_info.get("market", "unknown"), "A股")
logger.info(f"📊 推断市场类型: {stock_symbol} -> {market_type}")

# 构建文档
document = {
    "analysis_id": analysis_id,
    "stock_symbol": stock_symbol,
    "market_type": market_type,  # 🔥 添加市场类型字段
    "analysis_date": timestamp.strftime('%Y-%m-%d'),
    ...
}
```

### 2. 查询报告时兼容旧数据

为了兼容已有的旧数据（没有 `market_type` 字段），在返回报告列表时动态推断市场类型。

#### 修改 `app/routers/reports.py`

```python
# ✅ 新代码 - 兼容旧数据
async for doc in cursor:
    stock_code = doc.get("stock_symbol", "")
    stock_name = get_stock_name(stock_code)

    # 获取市场类型，如果没有则根据股票代码推断
    market_type = doc.get("market_type")
    if not market_type:
        from tradingagents.utils.stock_utils import StockUtils
        market_info = StockUtils.get_market_info(stock_code)
        market_type_map = {
            "china_a": "A股",
            "hong_kong": "港股",
            "us": "美股",
            "unknown": "A股"
        }
        market_type = market_type_map.get(market_info.get("market", "unknown"), "A股")

    report = {
        "id": str(doc["_id"]),
        "analysis_id": doc.get("analysis_id", ""),
        "stock_code": stock_code,
        "stock_name": stock_name,
        "market_type": market_type,  # 🔥 添加市场类型字段
        ...
    }
```

## 市场类型识别规则

使用 `tradingagents.utils.stock_utils.StockUtils` 进行市场类型识别：

| 股票代码格式 | 市场类型 | 示例 |
|------------|---------|------|
| 6位数字 | A股 | `000001`, `600000` |
| 4-5位数字 | 港股 | `0700`, `00700` |
| 4-5位数字.HK | 港股 | `0700.HK`, `00700.HK` |
| 1-5位字母 | 美股 | `AAPL`, `TSLA` |
| 其他 | A股（默认） | - |

## 数据模型

### 报告文档结构

```json
{
  "_id": ObjectId("..."),
  "analysis_id": "000001_20251014_112216",
  "stock_symbol": "000001",
  "market_type": "A股",  // ✅ 新增字段
  "analysis_date": "2025-10-14",
  "timestamp": ISODate("2025-10-14T11:22:16Z"),
  "status": "completed",
  "source": "api",
  "summary": "...",
  "analysts": ["market", "fundamentals"],
  "research_depth": 3,
  "reports": {...},
  "created_at": ISODate("2025-10-14T11:22:16Z"),
  "updated_at": ISODate("2025-10-14T11:22:16Z")
}
```

## 测试验证

### 1. 运行测试脚本

```bash
.\.venv\Scripts\python scripts\test_market_type_fix.py
```

**预期输出**：

```
============================================================
测试市场类型检测
============================================================
✅ 000001       -> A股     (期望: A股)
✅ 600000       -> A股     (期望: A股)
✅ 00700        -> 港股     (期望: 港股)
✅ 0700         -> 港股     (期望: 港股)
✅ 00700.HK     -> 港股     (期望: 港股)
✅ AAPL         -> 美股     (期望: 美股)
✅ TSLA         -> 美股     (期望: 美股)

============================================================
测试 MongoDB 文档结构
============================================================
✅ 文档结构正确
✅ 所有必需字段都存在
```

### 2. 端到端测试

1. **启动后端服务**：
   ```bash
   .\.venv\Scripts\python -m uvicorn app.main:app --reload --port 8000
   ```

2. **运行股票分析**：
   - 访问前端页面
   - 输入股票代码（例如：`000001`）
   - 运行分析

3. **检查报告列表**：
   - 访问 `/reports` 页面
   - 应该能看到刚才生成的报告
   - 测试市场筛选功能（A股/港股/美股）

4. **验证数据库**：
   ```javascript
   // MongoDB 查询
   db.analysis_reports.findOne({}, {
     analysis_id: 1,
     stock_symbol: 1,
     market_type: 1
   })
   ```

   **预期结果**：
   ```json
   {
     "_id": ObjectId("..."),
     "analysis_id": "000001_20251014_112216",
     "stock_symbol": "000001",
     "market_type": "A股"  // ✅ 字段存在
   }
   ```

## 修改的文件

### 后端
1. `app/services/simple_analysis_service.py`
   - 第 2108-2156 行：添加市场类型推断和字段

2. `app/routers/reports.py`
   - 第 141-179 行：查询时兼容旧数据，动态推断市场类型

### Web
3. `web/utils/mongodb_report_manager.py`
   - 第 109-168 行：添加市场类型推断和字段

### 测试
4. `scripts/test_market_type_fix.py`
   - 新增测试脚本

### 文档
5. `docs/fixes/reports-market-type-missing-fix.md`
   - 本文档

## 影响范围

### 新数据
- ✅ 所有新生成的报告都会包含 `market_type` 字段
- ✅ 市场筛选功能正常工作

### 旧数据
- ✅ 查询时动态推断市场类型，兼容旧数据
- ⚠️ 建议运行数据迁移脚本，为旧数据添加 `market_type` 字段

## 数据迁移（可选）

如果需要为已有的旧数据添加 `market_type` 字段，可以运行以下 MongoDB 脚本：

```javascript
// 为所有缺少 market_type 的报告添加该字段
db.analysis_reports.find({ market_type: { $exists: false } }).forEach(function(doc) {
    var stockSymbol = doc.stock_symbol;
    var marketType = "A股";  // 默认值
    
    // 根据股票代码推断市场类型
    if (/^\d{6}$/.test(stockSymbol)) {
        marketType = "A股";
    } else if (/^\d{4,5}(\.HK)?$/.test(stockSymbol)) {
        marketType = "港股";
    } else if (/^[A-Z]{1,5}$/.test(stockSymbol)) {
        marketType = "美股";
    }
    
    db.analysis_reports.updateOne(
        { _id: doc._id },
        { $set: { market_type: marketType } }
    );
    
    print("Updated: " + doc.analysis_id + " -> " + marketType);
});
```

## 总结

### 问题
- 保存报告时缺少 `market_type` 字段
- 查询报告时使用 `market_type` 筛选，导致无法匹配到数据

### 解决方案
1. 保存报告时根据股票代码自动推断并添加 `market_type` 字段
2. 查询报告时兼容旧数据，动态推断市场类型
3. 使用 `StockUtils.get_market_info()` 统一市场类型识别逻辑

### 效果
- ✅ 新报告包含 `market_type` 字段
- ✅ 市场筛选功能正常工作
- ✅ 兼容旧数据
- ✅ 统一的市场类型识别逻辑

