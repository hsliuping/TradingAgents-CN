# 数据库导出规则

## 📊 导出集合分类

### ✅ 配置类集合（必须导出）

这些集合包含系统配置和元数据，文档数量少，适合导出用于初始化新系统。

**v2.0 核心配置**:
```python
v2_core_collections = [
    'workflow_definitions',      # 工作流定义
    'agent_configs',             # Agent 配置
    'tool_configs',              # 工具配置
    'tool_agent_bindings',       # 工具-Agent 绑定
    'agent_workflow_bindings',   # Agent-工作流 绑定
    'agent_io_definitions',      # Agent IO 定义
]
```

**系统配置**:
```python
system_config_collections = [
    'system_configs',            # 系统配置（包括 LLM 配置）
    'llm_providers',             # LLM 提供商
    'model_catalog',             # 模型目录
    'platform_configs',          # 平台配置
    'datasource_groupings',      # 数据源分组
    'market_categories',         # 市场分类
]
```

**用户相关**:
```python
user_config_collections = [
    'users',                     # 用户数据（脱敏模式下只导出结构）
    'user_configs',              # 用户配置
    'user_tags',                 # 用户标签
    'user_favorites',            # 用户收藏
]
```

**交易系统**:
```python
trading_system_collections = [
    'trading_systems',           # 个人交易计划
    'trading_system_versions',   # 交易计划版本历史
]
```

**提示词**:
```python
prompt_collections = [
    'prompt_templates',          # 提示词模板
    'user_template_configs',     # 用户模板配置
]
```

### ❌ 数据类集合（不建议导出）

这些集合包含大量业务数据，不适合用于系统初始化。

```python
data_collections = [
    'stock_basic_info',          # 股票基础信息（数万条）
    'market_quotes',             # 市场行情（数十万条）
    'stock_financial_data',      # 财务数据（数万条）
    'stock_news',                # 股票新闻（数千条）
    'operation_logs',            # 操作日志（数千条）
]
```

### 📝 分析报告集合（可选导出）

```python
report_collections = [
    'unified_analysis_tasks',    # 统一分析任务（v2.0）
    'analysis_tasks',            # 分析任务（v1.x）
    'analysis_reports',          # 分析报告
]
```

---

## 🎯 导出场景

### 场景 1: 配置数据导出（用于演示系统）

**用途**: 为便携版提供预配置数据，用户开箱即用  
**脱敏**: ✅ 启用（清空 API 密钥等敏感字段）

**导出集合**:
```python
config_only_collections = [
    # v2.0 核心
    'workflow_definitions',
    'agent_configs',
    'tool_configs',
    'tool_agent_bindings',
    'agent_workflow_bindings',
    'agent_io_definitions',
    
    # 系统配置
    'system_configs',
    'llm_providers',
    'model_catalog',
    'platform_configs',
    'datasource_groupings',
    'market_categories',
    
    # 用户相关
    'users',                     # 脱敏模式下只导出结构
    'user_configs',
    'user_tags',
    'user_favorites',
    
    # 交易系统
    'trading_systems',
    'trading_system_versions',
    
    # 提示词
    'prompt_templates',
    'user_template_configs',
]
```

**导出方法**:
```bash
# 通过 Web 界面
系统管理 → 数据库管理 → 数据导出 → 选择"配置数据（用于演示系统）"

# 通过 API
POST /api/system/database/export
{
  "collections": [...],
  "format": "json",
  "sanitize": true
}
```

### 场景 2: 配置和报告导出（用于迁移）

**用途**: 完整数据迁移，包含配置和分析报告  
**脱敏**: ❌ 不启用（保留完整数据）

**导出集合**:
```python
config_and_reports_collections = [
    # 所有配置集合
    ...config_only_collections,
    
    # 分析报告
    'unified_analysis_tasks',
    'analysis_tasks',
    'analysis_reports',
]
```

---

## 🔐 脱敏规则

### 敏感字段关键词

以下字段会被自动清空（设置为空字符串）:
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

### 排除字段

以下字段虽然包含敏感关键词，但不会被清空:
```python
EXCLUDED_FIELDS = [
    "max_tokens",        # LLM 配置：最大 token 数
    "timeout",           # 超时时间
    "retry_times",       # 重试次数
    "context_length",    # 上下文长度
]
```

### 特殊处理

- **users 集合**: 脱敏模式下只导出空数组（保留结构，不导出实际用户数据）
- **递归脱敏**: 自动递归处理嵌套对象和数组中的敏感字段

---

## 📝 导出文件命名规范

```
database_export_{type}_{date}.json

类型:
- _config           # 仅配置数据（脱敏）
- _config_reports   # 配置和报告（不脱敏）
- _{collection}     # 单个集合

示例:
- database_export_config_2026-01-05.json
- database_export_config_reports_2026-01-05.json
- database_export_analysis_reports_2026-01-05.json
```

---

## 🚀 导入配置

### 导入模式

**覆盖模式** (`--overwrite`):
- 删除现有数据
- 插入新数据
- 用于全新安装或重置

**增量模式** (`--incremental`):
- 跳过已存在的数据
- 只插入新数据
- 用于更新或补充

### 导入脚本

```bash
# 覆盖模式（默认）
python scripts/import_config_and_create_user.py \
    install/database_export_config_2026-01-05.json \
    --host --overwrite

# 增量模式
python scripts/import_config_and_create_user.py \
    install/database_export_config_2026-01-05.json \
    --host --incremental

# 指定集合
python scripts/import_config_and_create_user.py \
    config.json \
    --collections system_configs llm_providers model_catalog

# 只创建用户
python scripts/import_config_and_create_user.py \
    --create-user-only --host
```

---

## ✅ 最佳实践

1. **定期导出配置**: 每次重大配置更改后导出备份
2. **版本控制**: 使用日期标记导出文件
3. **脱敏检查**: 导出前确认敏感数据已清空
4. **测试导入**: 在测试环境验证导入流程
5. **文档更新**: 更新 `install/README_PRO.md` 说明新增集合

---

**最后更新**: 2026-01-05  
**相关文档**: 
- `docs/deployment/database/export-sanitization-guide.md`
- `install/README_PRO.md`
- `DATABASE_INIT_SOLUTION.md`

