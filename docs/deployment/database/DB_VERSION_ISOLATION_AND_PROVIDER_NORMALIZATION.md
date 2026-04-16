# 数据库版本隔离与 Provider 规范化

本文档说明 TradingAgents-CN 当前的 MongoDB 命名策略、开发环境共享库保护，以及两个常用运维脚本的推荐用法。

## 1. 数据库命名策略

当前基础数据库名默认是：

```env
MONGODB_DATABASE=tradingagentscn
```

系统最终实际使用的数据库名由以下配置共同决定：

```env
MONGODB_DATABASE=tradingagentscn
MONGODB_DATABASE_SCOPE=auto
# MONGODB_DATABASE_INSTANCE=dev-yourname
ALLOW_SHARED_DB_IN_DEBUG=false
```

### `MONGODB_DATABASE_SCOPE` 支持值

- `explicit`
  - 直接使用 `MONGODB_DATABASE`
- `major`
  - 使用 `{base}_v{major}`
- `major_instance`
  - 使用 `{base}_v{major}_{instance}`
- `auto`
  - `DEBUG=true` 时自动使用 `major_instance`
  - `DEBUG=false` 时自动使用 `explicit`

### 推荐约定

- 本地开发：
  - `DEBUG=true`
  - `MONGODB_DATABASE_SCOPE=auto`
  - 可选配置 `MONGODB_DATABASE_INSTANCE=dev-你的名字`
- 测试/预发：
  - `MONGODB_DATABASE_SCOPE=major`
- 生产：
  - 默认保守策略是 `explicit`
  - 如果要做大版本隔离，再切换到 `major`

## 2. 开发环境共享库保护

当满足以下条件时，启动校验会阻止应用启动：

- `DEBUG=true`
- 实际数据库作用域不是 `major_instance`
- `ALLOW_SHARED_DB_IN_DEBUG=false`

这能防止本地开发误连共享库。

如果你明确知道自己在做什么，才允许临时放开：

```env
ALLOW_SHARED_DB_IN_DEBUG=true
```

不建议长期开启。

## 3. 查看当前实际数据库名

系统内部会计算最终库名，并通过数据库状态接口暴露：

- `database`
- `database_identity`

其中 `database_identity` 包含：

- `base_database`
- `scope_configured`
- `scope_effective`
- `major_version`
- `instance`
- `database`

如果出现“写到了错误数据库”或“为什么这台机器看不到那边配置”，优先检查这几个字段。

## 4. 数据库迁移脚本

脚本位置：

- `app/scripts/migrate_mongo_db.py`

### 默认行为

如果不传 `--include`，脚本会默认排除缓存/大表集合，例如：

- `historical_data`
- `market_quotes`
- `stock_basic_info`
- `stock_financial_data`
- `analysis_tasks`
- `analysis_reports`
- `usage_records`

这样默认更适合做“配置类集合迁移”，避免误把大体量运行数据整库搬过去。

### 查看默认排除集合

```bash
python -m app.scripts.migrate_mongo_db --show-default-excludes
```

### 推荐先 dry-run

```bash
python -m app.scripts.migrate_mongo_db --source-db tradingagents --target-db tradingagentscn_v1_devx --dry-run
```

### 只迁移配置类集合

```bash
python -m app.scripts.migrate_mongo_db \
  --source-db tradingagents \
  --target-db tradingagentscn_v1_devx \
  --include llm_providers,system_configs,model_catalog \
  --dry-run
```

### 实际执行

```bash
python -m app.scripts.migrate_mongo_db \
  --source-db tradingagents \
  --target-db tradingagentscn_v1_devx \
  --include llm_providers,system_configs,model_catalog
```

### 增量迁移

按 `created_at/updated_at` 做增量迁移：

```bash
python -m app.scripts.migrate_mongo_db \
  --source-db tradingagents \
  --target-db tradingagentscn_v1_devx \
  --include llm_providers,system_configs,model_catalog \
  --since 2026-01-01T00:00:00
```

### 小样本验证

先对每个集合只迁移少量文档，验证命令和目标库是否符合预期：

```bash
python -m app.scripts.migrate_mongo_db \
  --source-db tradingagents \
  --target-db tradingagentscn_v1_devx \
  --include llm_providers,system_configs,model_catalog \
  --limit 20 \
  --dry-run
```

### 输出迁移结果到 JSON

```bash
python -m app.scripts.migrate_mongo_db \
  --source-db tradingagents \
  --target-db tradingagentscn_v1_devx \
  --include llm_providers,system_configs,model_catalog \
  --summary-json ./tmp/migrate_summary.json
```

### 覆盖目标集合

```bash
python -m app.scripts.migrate_mongo_db \
  --source-db tradingagents \
  --target-db tradingagentscn_v1_devx \
  --include llm_providers,system_configs,model_catalog \
  --drop-target
```

## 5. Provider 规范化脚本

脚本位置：

- `app/scripts/normalize_provider_keys.py`

主要作用：

- 把数据库中的 provider 统一到 canonical key
- 当前重点规范：
  - `dashscope/alibaba/阿里百炼/百炼 -> qwen`
  - `zhipu/智谱/智谱AI -> glm`
- 自动合并：
  - `llm_providers`
  - `system_configs.llm_configs[].provider`
  - `model_catalog.provider`

### 推荐先 dry-run

```bash
python -m app.scripts.normalize_provider_keys --dry-run
```

### 只处理厂家配置

```bash
python -m app.scripts.normalize_provider_keys --include providers --dry-run
```

### 处理厂家配置和模型目录

```bash
python -m app.scripts.normalize_provider_keys --include providers,model_catalog --dry-run
```

### 排除某部分

```bash
python -m app.scripts.normalize_provider_keys --exclude model_catalog --dry-run
```

### 修复唯一索引

只有在确认数据已经清理完重复项后，再加 `--fix-indexes`：

```bash
python -m app.scripts.normalize_provider_keys --fix-indexes
```

## 6. 推荐执行顺序

对于已有旧库的环境，推荐按这个顺序操作：

1. 检查当前实际数据库名与作用域
2. 对目标数据库执行 `migrate_mongo_db.py --dry-run`
3. 优先只迁移配置类集合，必要时再显式 `--include` 大表
4. 对目标数据库执行 `normalize_provider_keys.py --dry-run`
5. 确认输出无异常后执行真实规范化
6. 最后视情况执行 `--fix-indexes`

## 7. 风险提示

- 不要在不了解当前 `database_identity` 的情况下直接运行迁移脚本
- 不传 `--include` 时，脚本默认不会迁移缓存/大表集合，这是有意设计
- 不要在生产环境直接对整库执行 `--drop-target`
- 不要在存在重复脏数据时直接运行 `--fix-indexes`
- 本地开发尽量保持 `ALLOW_SHARED_DB_IN_DEBUG=false`
