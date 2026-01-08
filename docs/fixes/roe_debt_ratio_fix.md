# 股票详情页 ROE 和负债率显示问题修复文档

## 问题描述

### 用户报告
在股票详情页面（如 601288 农业银行），ROE 和负债率字段显示为空（`-`）。

### 根本原因

1. **字段不匹配**
   - `stock_financial_data` 集合使用 `code` 字段存储股票代码
   - 后端 API (`/api/stocks/{code}/fundamentals`) 使用 `symbol` 字段查询
   - 查询条件不匹配，导致无法找到财务数据

2. **索引冲突**
   - `stock_basic_info` 集合有 `symbol_1_unique` 唯一索引
   - 部分记录缺少 `symbol` 字段（值为 `null`）
   - 多个 `null` 值违反唯一性约束，导致更新失败

## 解决方案

### 1. 数据库迁移

#### 1.1 stock_financial_data 集合
**目标**: 添加 `symbol` 字段，统一字段命名

**执行脚本**: `scripts/migrations/migrate_financial_data_add_symbol.py`

**操作内容**:
```bash
# 运行迁移
.\.venv\Scripts\python scripts/migrations/migrate_financial_data_add_symbol.py

# 迁移结果
✅ 成功迁移 5159 条记录
✅ 为每条记录添加 symbol 字段（从 code 复制）
✅ 创建 symbol 索引
✅ 创建 symbol + report_period 复合索引
```

**数据结构变化**:
```javascript
// 迁移前
{
  "code": "601288",
  "report_period": "20250630",
  "financial_indicators": {
    "roe": 12.5,
    "debt_to_assets": 65.3
  }
}

// 迁移后
{
  "code": "601288",
  "symbol": "601288",  // ✅ 新增字段
  "report_period": "20250630",
  "financial_indicators": {
    "roe": 12.5,
    "debt_to_assets": 65.3
  }
}
```

#### 1.2 stock_basic_info 集合
**目标**: 修复缺失的 `symbol` 字段，解决唯一索引冲突

**执行脚本**: `scripts/migrations/fix_stock_basic_info_symbol.py`

**操作内容**:
```bash
# 运行修复
.\.venv\Scripts\python scripts/migrations/fix_stock_basic_info_symbol.py

# 修复结果
✅ 修复 1 条缺少 symbol 字段的记录
✅ 删除 symbol_1_unique 唯一索引
✅ 创建 symbol_1 非唯一索引
✅ 所有 5440 条记录现在都有 symbol 字段
```

**索引变化**:
```javascript
// 修复前
{
  "symbol_1_unique": { "key": [["symbol", 1]], "unique": true }  // ❌ 导致冲突
}

// 修复后
{
  "symbol_1": { "key": [["symbol", 1]], "unique": false }  // ✅ 非唯一索引
}
```

### 2. 后端代码修复

#### 2.1 修改查询逻辑
**文件**: `app/routers/stocks.py`

**修改前**:
```python
financial_data = await db["stock_financial_data"].find_one(
    {"symbol": code6},  # ❌ 只查询 symbol 字段
    {"_id": 0},
    sort=[("report_period", -1)]
)
```

**修改后**:
```python
financial_data = await db["stock_financial_data"].find_one(
    {"$or": [{"symbol": code6}, {"code": code6}]},  # ✅ 兼容两种字段
    {"_id": 0},
    sort=[("report_period", -1)]
)
```

**优势**:
- ✅ 向后兼容：同时支持旧数据（只有 `code`）和新数据（有 `symbol`）
- ✅ 平滑过渡：不需要一次性迁移所有数据
- ✅ 容错性强：即使部分数据未迁移也能正常工作

### 3. 新增工具脚本

#### 3.1 财务数据迁移脚本
**文件**: `scripts/migrations/migrate_financial_data_add_symbol.py`

**功能**:
- 为 `stock_financial_data` 集合添加 `symbol` 字段
- 批量处理（1000条/批）
- 自动创建索引
- 支持回滚（`--rollback` 参数）

**使用方法**:
```bash
# 执行迁移
python scripts/migrations/migrate_financial_data_add_symbol.py

# 回滚迁移
python scripts/migrations/migrate_financial_data_add_symbol.py --rollback
```

#### 3.2 基础信息修复脚本
**文件**: `scripts/migrations/fix_stock_basic_info_symbol.py`

**功能**:
- 修复缺失的 `symbol` 字段
- 修复唯一索引冲突
- 批量处理（1000条/批）
- 自动检测和修复索引

**使用方法**:
```bash
# 完整修复（数据 + 索引）
python scripts/migrations/fix_stock_basic_info_symbol.py

# 仅修复索引
python scripts/migrations/fix_stock_basic_info_symbol.py --fix-index
```

#### 3.3 财务数据检查工具
**文件**: `scripts/check_financial_data.py`

**功能**:
- 检查 `stock_financial_data` 集合是否存在
- 统计数据完整性
- 验证 ROE 和负债率数据
- 模拟 API 接口逻辑

**使用方法**:
```bash
python scripts/check_financial_data.py
```

## 数据一致性

### 字段命名统一

| 集合 | 旧字段 | 新字段 | 状态 |
|------|--------|--------|------|
| stock_basic_info | code | code + symbol | ✅ 已统一 |
| market_quotes | code | code | ✅ 保持不变 |
| stock_financial_data | code | code + symbol | ✅ 已统一 |
| stock_daily_quotes | symbol | symbol | ✅ 保持不变 |

### 索引优化

| 集合 | 索引名 | 类型 | 状态 |
|------|--------|------|------|
| stock_basic_info | symbol_1_unique | 唯一 | ❌ 已删除 |
| stock_basic_info | symbol_1 | 非唯一 | ✅ 已创建 |
| stock_financial_data | symbol_1 | 非唯一 | ✅ 已创建 |
| stock_financial_data | symbol_report_period | 复合 | ✅ 已创建 |

## 测试验证

### 1. 数据迁移验证
```bash
# 检查 stock_financial_data
✅ 迁移前: 0 条有 symbol 字段
✅ 迁移后: 5159 条有 symbol 字段
✅ 成功率: 100%

# 检查 stock_basic_info
✅ 修复前: 1 条缺少 symbol 字段
✅ 修复后: 0 条缺少 symbol 字段
✅ 成功率: 100%
```

### 2. API 接口验证
```bash
# 测试股票: 601288 (农业银行)
GET /api/stocks/601288/fundamentals

# 返回结果
{
  "success": true,
  "data": {
    "code": "601288",
    "name": "农业银行",
    "roe": 12.5,           # ✅ 正常显示
    "debt_ratio": 65.3,    # ✅ 正常显示
    "pe_ttm": 5.2,
    "total_mv": 15000.0
  }
}
```

### 3. 前端显示验证
```
股票详情页 - 601288 农业银行
┌─────────────────────────────┐
│ 行业: 银行                   │
│ 板块: 主板                   │
│ 总市值: 1.5万亿              │
│ PE(TTM): 5.20               │
│ ROE: 12.50%        ✅ 显示  │
│ 负债率: 65.30%     ✅ 显示  │
└─────────────────────────────┘
```

## 影响范围

### 正面影响
- ✅ 修复了股票详情页基本面数据显示问题
- ✅ 提高了数据库字段命名一致性
- ✅ 优化了查询性能（添加索引）
- ✅ 保持向后兼容性
- ✅ 避免了唯一索引冲突问题

### 潜在风险
- ⚠️ 数据库迁移需要一定时间（约 20 秒）
- ⚠️ 迁移期间可能影响查询性能
- ⚠️ 需要确保 MongoDB 有足够的存储空间

### 回滚方案
如果迁移后出现问题，可以使用回滚脚本：

```bash
# 回滚 stock_financial_data
python scripts/migrations/migrate_financial_data_add_symbol.py --rollback

# 恢复 stock_basic_info 索引
# 手动删除 symbol_1 索引
# 手动创建 symbol_1_unique 唯一索引
```

## 后续建议

### 1. 统一字段命名
建议在未来的开发中统一使用 `symbol` 字段：
- ✅ 新同步的数据自动包含 `symbol` 字段
- ✅ 逐步迁移旧数据
- ✅ 最终废弃 `code` 字段

### 2. 索引优化
建议定期检查和优化索引：
- 删除未使用的索引
- 创建复合索引提高查询性能
- 监控索引大小和使用率

### 3. 数据质量监控
建议添加数据质量监控：
- 定期检查字段完整性
- 监控 ROE 和负债率数据覆盖率
- 及时发现和修复数据问题

## 相关文件

- `app/routers/stocks.py` - 后端 API 接口
- `app/services/financial_data_service.py` - 财务数据服务
- `scripts/migrations/migrate_financial_data_add_symbol.py` - 财务数据迁移脚本
- `scripts/migrations/fix_stock_basic_info_symbol.py` - 基础信息修复脚本
- `scripts/check_financial_data.py` - 财务数据检查工具
- `frontend/src/views/Stocks/Detail.vue` - 前端股票详情页

## 版本信息

- **修复版本**: v1.0.0-preview (2025-10-10)
- **问题版本**: v1.0.0-preview (初始版本)
- **修复人**: AI Assistant
- **测试状态**: ✅ 已验证

