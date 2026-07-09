# 数据库导出配置更新总结

## 📋 问题描述

原来的数据库导出配置只包含旧版（v1.x）的集合，缺少 v2.0 新增的核心集合，导致导出的配置文件不完整。

---

## ✅ 已完成的工作

### 1. 创建 Augment 规则文件

在 `.augment/rules/` 目录下创建了完整的项目规则：

- **`project_overview.md`** - 项目概览（包含所有 MongoDB 集合列表）
- **`database_export.md`** - 数据库导出规则（详细的导出配置）
- **`README.md`** - 规则使用指南

### 2. 更新前端导出配置

**文件**: `frontend/src/views/System/DatabaseManagement.vue`

**更新内容**:

#### 配置集合列表（从 10 个增加到 22 个）

**新增的 v2.0 核心集合** (6个):
```javascript
'workflow_definitions',      // 工作流定义
'agent_configs',             // Agent 配置
'tool_configs',              // 工具配置
'tool_agent_bindings',       // 工具-Agent 绑定
'agent_workflow_bindings',   // Agent-工作流 绑定
'agent_io_definitions',      // Agent IO 定义
```

**新增的交易系统集合** (2个):
```javascript
'trading_systems',           // 个人交易计划
'trading_system_versions',   // 交易计划版本历史
```

**新增的提示词集合** (2个):
```javascript
'prompt_templates',          // 提示词模板
'user_template_configs'      // 用户模板配置
```

**新增的分析任务集合** (1个):
```javascript
'unified_analysis_tasks',    // 统一分析任务（v2.0）
```

#### 完整的配置集合列表

```javascript
const configCollections = [
  // v2.0 核心配置 (6个)
  'workflow_definitions',
  'agent_configs',
  'tool_configs',
  'tool_agent_bindings',
  'agent_workflow_bindings',
  'agent_io_definitions',
  
  // 系统配置 (6个)
  'system_configs',
  'llm_providers',
  'model_catalog',
  'platform_configs',
  'datasource_groupings',
  'market_categories',
  
  // 用户相关 (4个)
  'users',
  'user_configs',
  'user_tags',
  'user_favorites',
  
  // 交易系统 (2个)
  'trading_systems',
  'trading_system_versions',
  
  // 提示词 (2个)
  'prompt_templates',
  'user_template_configs'
]
```

**总计**: 22 个集合

---

## 🎯 导出场景

### 场景 1: 配置数据导出（用于演示系统）

**用途**: 便携版预配置数据  
**脱敏**: ✅ 启用  
**集合数**: 22 个

**通过 Web 界面**:
1. 登录系统
2. 进入 **系统管理** → **数据库管理**
3. 选择 **配置数据（用于演示系统，已脱敏）**
4. 点击 **导出数据**

**通过 API**:
```bash
POST http://127.0.0.1:3000/api/system/database/export
Content-Type: application/json

{
  "collections": [
    "workflow_definitions",
    "agent_configs",
    "tool_configs",
    ...
  ],
  "format": "json",
  "sanitize": true
}
```

### 场景 2: 配置和报告导出（用于迁移）

**用途**: 完整数据迁移  
**脱敏**: ❌ 不启用  
**集合数**: 25 个（配置 22 + 报告 3）

---

## 📊 导出文件对比

### 旧版导出（10 个集合）

```
system_configs
users
llm_providers
market_categories
user_tags
user_favorites
datasource_groupings
platform_configs
user_configs
model_catalog
```

**缺少**: v2.0 核心配置、交易系统、提示词等

### 新版导出（22 个集合）

**新增**:
- ✅ v2.0 核心配置 (6个)
- ✅ 交易系统 (2个)
- ✅ 提示词 (2个)
- ✅ 统一分析任务 (1个)

---

## 🔐 脱敏规则

### 敏感字段

以下字段会被自动清空：
```python
SENSITIVE_KEYWORDS = [
    "api_key",
    "api_secret",
    "secret",
    "token",
    "password",
    "client_secret",
    "webhook_secret",
    "private_key"
]
```

### 特殊处理

- **users 集合**: 脱敏模式下只导出空数组（保留结构）
- **递归脱敏**: 自动处理嵌套对象和数组

---

## 🚀 下一步操作

### 1. 重新导出配置文件

```bash
# 1. 启动系统
cd frontend
npm run dev

# 2. 访问 http://localhost:3000
# 3. 登录系统
# 4. 进入 系统管理 → 数据库管理
# 5. 选择 "配置数据（用于演示系统，已脱敏）"
# 6. 点击 "导出数据"
# 7. 保存为 install/database_export_config_2026-01-05.json
```

### 2. 更新安装脚本

确保初始化脚本使用新的配置文件：

```powershell
# scripts/deployment/init_pro_database.ps1
$configFile = "install\database_export_config_2026-01-05.json"
```

### 3. 测试导入

```powershell
# 测试导入
python scripts\import_config_and_create_user.py `
    install\database_export_config_2026-01-05.json `
    --host --overwrite
```

---

## ✅ 验证清单

- [x] 创建 Augment 规则文件
- [x] 更新前端导出配置（22 个集合）
- [x] 包含 v2.0 核心集合
- [x] 包含交易系统集合
- [x] 包含提示词集合
- [x] 包含统一分析任务
- [ ] 重新导出配置文件
- [ ] 测试导入流程
- [ ] 更新 `install/README_PRO.md`

---

## 📝 相关文档

- **Augment 规则**: `.augment/rules/`
- **导出规则**: `.augment/rules/database_export.md`
- **项目概览**: `.augment/rules/project_overview.md`
- **配置指南**: `AUGMENT_RULES_GUIDE.md`
- **数据库方案**: `DATABASE_INIT_SOLUTION.md`

---

**更新日期**: 2026-01-05  
**维护者**: TradingAgents-CN Pro Team

