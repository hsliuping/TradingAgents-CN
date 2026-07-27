# AlphaGuard 备份与恢复

本流程只处理 AlphaGuard 专用集合，默认不覆盖当前数据库。

## 范围

脚本从 `ALPHAGUARD_INDEX_SPECS` 的显式集合表生成精确范围，只处理 `ag_*` AlphaGuard
集合。它不会包含或修改旧人工模拟集合：

```text
paper_accounts
paper_positions
paper_orders
paper_trades
```

备份格式是逐文档 BSON stream，保留 Decimal128、ObjectId 和 datetime 等 MongoDB 类型。
`manifest.json` 保存源数据库、集合、记录数和每个文件的 SHA-256。

## 备份

预览：

```bash
.venv/bin/python scripts/alphaguard_backup.py \
  --output backups/alphaguard-20260727-100000
```

执行：

```bash
.venv/bin/python scripts/alphaguard_backup.py \
  --execute \
  --output backups/alphaguard-20260727-100000
```

目标目录必须为空，不能是 `/`、用户主目录或项目根目录。脚本不会打印 MongoDB 密码。

## 默认安全恢复

默认恢复到带时间戳的新数据库，不覆盖当前数据库：

```bash
.venv/bin/python scripts/alphaguard_restore.py \
  backups/alphaguard-20260727-100000
```

以上是 dry-run。确认目标后：

```bash
.venv/bin/python scripts/alphaguard_restore.py \
  backups/alphaguard-20260727-100000 \
  --execute
```

若目标数据库已存在 AlphaGuard 文档，脚本拒绝继续。

## 覆盖当前数据库

这是破坏性操作，只能在服务和 Worker 全部停止、已验证外部备份后执行。必须同时提供：

```bash
--overwrite-current
--confirmation "OVERWRITE <当前数据库名>"
```

脚本仅清空并恢复精确 AlphaGuard 集合，不使用通配删除，不触碰人工模拟集合。MongoDB
standalone 无法把跨集合恢复包装成单个事务；中途失败必须视为未完成恢复，不能启动业务。

恢复后依次执行：

```bash
.venv/bin/python scripts/init_alphaguard_indexes.py
.venv/bin/python scripts/verify_champion_assignments.py
.venv/bin/python scripts/alphaguard_readiness_report.py
.venv/bin/python scripts/alphaguard_mvp_smoke.py
```

确认 Champion 唯一、索引完整、负现金/负持仓为 0、Saga 无卡住记录后才能恢复 Worker。
