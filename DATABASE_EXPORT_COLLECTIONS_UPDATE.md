# 数据库导出集合更新总结

## 📋 更新日期

**日期**: 2026-01-10  
**原因**: 发现数据库中有很多新集合没有包含在迁移模式中

---

## 🔍 发现的问题

通过运行 `scripts/maintenance/list_collections.py` 发现数据库中有 **71 个集合**，但迁移模式只包含了 **22 个集合**，缺少了很多重要的配置和数据集合。

---

## ✅ 已更新的文件

### 1. 前端导出配置

**文件**: `frontend/src/views/System/DatabaseManagement.vue`

**更新内容**:

#### 配置集合（从 18 个增加到 30 个）

**新增集合**:
- `workflows` - 工作流实例
- `smtp_config` - SMTP 配置
- `sync_status` - 同步状态
- `paper_accounts` - 模拟账户
- `paper_market_rules` - 模拟市场规则
- `real_accounts` - 实盘账户
- `scheduled_analysis_configs` - 定时分析配置
- `scheduler_metadata` - 调度器元数据
- `watchlist_groups` - 自选股分组

**移除集合**（数据库中不存在）:
- `user_configs` - 用户配置
- `trading_system_versions` - 交易计划版本历史

#### 分析报告集合（从 3 个增加到 5 个）

**新增集合**:
- `position_analysis_reports` - 持仓分析报告
- `portfolio_analysis_reports` - 组合分析报告

#### 新增历史记录集合（5 个）

- `workflow_history` - 工作流历史
- `template_history` - 模板历史
- `scheduled_analysis_history` - 定时分析历史
- `notifications` - 通知
- `email_records` - 邮件记录

#### 新增交易记录集合（8 个）

- `paper_positions` - 模拟持仓
- `paper_orders` - 模拟订单
- `paper_trades` - 模拟交易
- `real_positions` - 实盘持仓
- `capital_transactions` - 资金交易
- `position_changes` - 持仓变化
- `trade_reviews` - 交易复盘
- `trading_system_evaluations` - 交易系统评估

---

### 2. 导入脚本配置

**文件**: `scripts/import_config_and_create_user.py`

**更新内容**: 同步更新 `CONFIG_COLLECTIONS` 列表，包含所有新增集合

---

### 3. Augment 规则文件

**文件**: `.augment/rules/database_export.md`

**更新内容**:
- 更新所有集合分类列表
- 更新场景 1（配置数据导出）的集合列表
- 更新场景 2（配置和报告导出）的集合列表
- 新增历史记录集合分类
- 新增交易记录集合分类

---

## 📊 更新后的集合统计

### 配置数据导出（用于演示系统）

**总计**: 30 个集合

- v2.0 核心配置: 7 个
- 系统配置: 8 个
- 用户相关: 3 个
- 交易系统: 4 个
- 提示词: 2 个
- 调度任务: 2 个
- 其他配置: 1 个

### 配置和报告导出（用于迁移）

**总计**: 48 个集合

- 配置数据: 30 个
- 分析报告: 5 个
- 历史记录: 5 个
- 交易记录: 8 个

---

## 🎯 导出场景对比

### 场景 1: 配置数据导出（用于演示系统）

**用途**: 为便携版提供预配置数据，用户开箱即用  
**脱敏**: ✅ 启用  
**集合数**: 30 个  
**文件大小**: 约 1-2 MB

### 场景 2: 配置和报告导出（用于迁移）

**用途**: 完整数据迁移，包含配置、报告和历史记录  
**脱敏**: ❌ 不启用  
**集合数**: 48 个  
**文件大小**: 根据实际数据量而定

---

## 🔧 使用方法

### 通过 Web 界面导出

1. 登录系统
2. 进入 **系统管理 → 数据库管理**
3. 选择导出类型：
   - **配置数据（用于演示系统）** - 脱敏模式，30 个集合
   - **配置和报告（用于迁移）** - 完整数据，48 个集合
4. 点击 **导出数据**

### 通过 API 导出

```bash
# 配置数据导出（脱敏）
POST /api/system/database/export
{
  "collections": [...],  # 30 个配置集合
  "format": "json",
  "sanitize": true
}

# 配置和报告导出（不脱敏）
POST /api/system/database/export
{
  "collections": [...],  # 48 个集合
  "format": "json",
  "sanitize": false
}
```

---

## 📝 注意事项

1. **数据量大的集合不包含在导出中**:
   - `stock_basic_info` (16,445 条)
   - `market_quotes` (5,796 条)
   - `stock_daily_quotes` (4,112 条)
   - `operation_logs` (3,165 条)
   - `token_usage` (6,132 条)

2. **脱敏规则**:
   - 配置数据导出时自动清空 API 密钥等敏感字段
   - `users` 集合在脱敏模式下只导出空数组

3. **导入顺序**:
   - 导入脚本会按照集合列表的顺序依次导入
   - 确保依赖关系正确（如先导入 `users` 再导入 `user_favorites`）

---

**相关文档**:
- `.augment/rules/database_export.md` - 数据库导出规则
- `scripts/maintenance/list_collections.py` - 列出所有集合的脚本
- `frontend/src/views/System/DatabaseManagement.vue` - 前端导出界面
- `scripts/import_config_and_create_user.py` - 导入脚本

