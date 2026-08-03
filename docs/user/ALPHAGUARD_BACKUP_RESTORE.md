# AlphaGuard 备份与恢复

备份覆盖 AlphaGuard 受索引管理的 MongoDB 集合和 `config/alphaguard` 配置快照。它保存
`backup_id`、`created_at`、`schema_version`、`collection_counts`、`manifest_hash`、
`source_commit` 和 `source_tag`。

Secret 不允许进入备份。API Key、密码、Token、Cookie、私钥或 Bearer 值会使创建或校验直接失败；
macOS Keychain 只保存 `credential_ref`，不会导出 Key。

## 创建前准备

1. 确认目标目录是专用空目录；
2. 确认 MongoDB 指向要读取的环境；
3. 先运行 dry-run 查看集合范围；
4. 不要把 `.env`、Keychain 内容或临时凭证复制到 `config/alphaguard`。

默认只预览：

```bash
.venv/bin/python scripts/alphaguard_backup.py
```

创建备份：

```bash
.venv/bin/python scripts/alphaguard_backup.py \
  --execute \
  --output backups/alphaguard-20260803-184000
```

目标目录已有文件时命令会拒绝覆盖。失败或 Secret 阻断时会自动清理部分 BSON 和目标目录，
不会留下可被误认为有效备份的文件。

## 列出与校验

列出默认备份目录：

```bash
.venv/bin/python scripts/alphaguard_backup.py --list
```

指定目录：

```bash
.venv/bin/python scripts/alphaguard_backup.py \
  --list --backup-root backups
```

完整校验会核对 Manifest Hash、每个 BSON 文件 Hash、文档数量、配置文件 Hash 和 Secret：

```bash
.venv/bin/python scripts/alphaguard_backup.py \
  --verify backups/alphaguard-20260803-184000
```

只有输出 `status=PASS` 和 `secret_scan=PASS` 的备份才可恢复。

## 默认隔离恢复

先 dry-run；不指定目标名时脚本自动生成独立数据库名：

```bash
.venv/bin/python scripts/alphaguard_restore.py \
  backups/alphaguard-20260803-184000
```

执行隔离恢复和恢复演练：

```bash
.venv/bin/python scripts/alphaguard_restore.py \
  backups/alphaguard-20260803-184000 \
  --target-database tradingagentscn_alphaguard_restore_20260803 \
  --execute --drill
```

隔离目标已有 AlphaGuard 文档时会拒绝覆盖；恢复中途失败时会自动删除该不完整隔离数据库。
恢复完成后再次核对所有集合数量，并输出 `restore_drill=PASS`。然后在隔离数据库中初始化
create-only 索引、运行一致性检查和只读页面验收。

## 正式数据库恢复边界

本发布不自动恢复正式数据库。正式恢复是破坏性管理员操作，必须同时提供：

```text
--overwrite-current
--confirmation "OVERWRITE <当前数据库名>"
```

缺少任一项都会拒绝。执行前还必须由管理员人工确认停机窗口、备份校验、账户资产、Champion 指针、
Challenger 状态和回退方案。不要在日常验收、测试或故障排查中使用正式覆盖参数。

## 恢复后检查

1. 集合数量与 Manifest 完全一致；
2. 必要索引已用 create-only 方式初始化；
3. 四个模拟账户资产与备份记录一致；
4. Champion 指针唯一且 Hash 一致；
5. `ACTIVE_CHALLENGER=false`；
6. 一致性报告没有失败；
7. `/health/ready` 和 Operations 显示真实状态；
8. 不执行测试交易来证明恢复成功。

恢复异常见 [AlphaGuard 故障排查](ALPHAGUARD_TROUBLESHOOTING.md)。
