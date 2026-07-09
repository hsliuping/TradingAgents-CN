
# 数据库备份与还原指南

## 概述

TradingAgents-CN 使用 MongoDB 作为主数据库。对于大数据量（>100MB）的备份和还原操作，**强烈建议使用 MongoDB 原生工具**（`mongodump` 和 `mongorestore`），而不是通过 Web 界面操作。

## 为什么使用命令行工具？

### Web 界面的局限性

- ❌ **速度慢**：需要通过 Python 序列化/反序列化，效率低
- ❌ **内存占用大**：大数据量会占用大量内存
- ❌ **容易超时**：HTTP 请求有超时限制
- ❌ **用户体验差**：长时间等待，无法中断

### 命令行工具的优势

- ✅ **速度快**：直接操作 BSON 格式，比 JSON 快 10-100 倍
- ✅ **压缩效率高**：原生支持 gzip 压缩
- ✅ **支持大数据量**：可以处理 GB 级别的数据
- ✅ **并行处理**：自动并行备份多个集合
- ✅ **增量备份**：支持 oplog 增量备份
- ✅ **可靠性高**：MongoDB 官方工具，经过充分测试

## 安装 MongoDB Database Tools

### Windows

1. 下载 MongoDB Database Tools：
   ```
   https://www.mongodb.com/try/download/database-tools
   ```

2. 解压到任意目录，例如：
   ```
   C:\Program Files\MongoDB\Tools\100\bin
   ```

3. 添加到系统 PATH 环境变量

4. 验证安装：
   ```powershell
   mongodump --version
   mongorestore --version
   ```

### Linux (Ubuntu/Debian)

```bash
# 安装
sudo apt-get install mongodb-database-tools

# 验证
mongodump --version
mongorestore --version
```

### macOS

```bash
# 使用 Homebrew 安装
brew install mongodb-database-tools

# 验证
mongodump --version
mongorestore --version
```

## 备份操作

### 基本备份

备份整个数据库：

**Windows（便携版）**：
```powershell
vendors\mongodb\mongodb-win32-x86_64-windows-8.0.13\bin\mongodump.exe --uri="mongodb://localhost:27017" --db=tradingagents --out=./backup --gzip
```

**Linux/macOS**：
```bash
mongodump \
  --uri="mongodb://localhost:27017" \
  --db=tradingagents \
  --out=./backup \
  --gzip
```

**参数说明**：
- `--uri`：MongoDB 连接字符串
- `--db`：数据库名称
- `--out`：备份输出目录
- `--gzip`：启用 gzip 压缩（推荐）

**注意**：
- Windows 便携版中，MongoDB 工具位于 `vendors\mongodb\mongodb-win32-x86_64-windows-8.0.13\bin\` 目录
- 如果 MongoDB 版本不同，请修改路径中的版本号
- 如果已将工具添加到 PATH，可以直接使用 `mongodump` 命令

### 备份特定集合

只备份某些集合：

```bash
mongodump \
  --uri="mongodb://localhost:27017" \
  --db=tradingagents \
  --collection=system_configs \
  --out=./backup \
  --gzip
```

### 备份多个集合

```bash
# 备份配置相关的集合
mongodump \
  --uri="mongodb://localhost:27017" \
  --db=tradingagents \
  --out=./backup_config \
  --gzip \
  --nsInclude="tradingagents.system_configs" \
  --nsInclude="tradingagents.llm_providers" \
  --nsInclude="tradingagents.market_categories" \
  --nsInclude="tradingagents.datasource_groupings"
```

### 排除某些集合

排除大数据量的集合：

```bash
mongodump \
  --uri="mongodb://localhost:27017" \
  --db=tradingagents \
  --out=./backup \
  --gzip \
  --nsExclude="tradingagents.market_quotes" \
  --nsExclude="tradingagents.stock_basic_info"
```

### 带认证的备份

如果 MongoDB 启用了认证：

```bash
mongodump \
  --uri="mongodb://username:password@localhost:27017/tradingagents?authSource=admin" \
  --out=./backup \
  --gzip
```

### 远程备份

备份远程服务器的数据库：

```bash
mongodump \
  --uri="mongodb://username:password@remote-server:27017/tradingagents" \
  --out=./backup \
  --gzip
```

## 还原操作

### 基本还原

还原整个数据库：

**Windows（便携版）**：

⚠️ **重要**：执行命令前，请先在命令行中进入应用安装目录（项目根目录）：

```powershell
cd C:\TradingAgentsCN
```

然后执行还原命令：

```powershell
vendors\mongodb\mongodb-win32-x86_64-windows-8.0.13\bin\mongorestore.exe --uri="mongodb://localhost:27017" --db=tradingagents --gzip ./backup/tradingagents
```

**Linux/macOS**：

同样需要先进入应用安装目录：

```bash
cd /path/to/TradingAgentsCN
```

然后执行还原命令：

```bash
mongorestore \
  --uri="mongodb://localhost:27017" \
  --db=tradingagents \
  --gzip \
  ./backup/tradingagents
```

**⚠️ 警告**：此操作会**覆盖**现有数据！

**注意**：
- ⚠️ **必须先在应用安装目录下执行命令**，因为命令中使用了相对路径 `vendors\mongodb\...` 和 `./backup\...`
- Windows 便携版中，MongoDB 工具位于 `vendors\mongodb\mongodb-win32-x86_64-windows-8.0.13\bin\` 目录
- 如果 MongoDB 版本不同，请修改路径中的版本号
- 如果已将工具添加到 PATH，可以直接使用 `mongorestore` 命令

### 还原前先删除现有数据

```bash
mongorestore \
  --uri="mongodb://localhost:27017" \
  --db=tradingagents \
  --drop \
  --gzip \
  ./backup/tradingagents
```

**参数说明**：
- `--drop`：还原前先删除现有集合

### 还原到不同的数据库

```bash
mongorestore \
  --uri="mongodb://localhost:27017" \
  --db=tradingagents_test \
  --gzip \
  ./backup/tradingagents
```

### 还原特定集合

```bash
mongorestore \
  --uri="mongodb://localhost:27017" \
  --db=tradingagents \
  --collection=system_configs \
  --gzip \
  ./backup/tradingagents/system_configs.bson.gz
```

### 合并还原（不覆盖现有数据）

```bash
mongorestore \
  --uri="mongodb://localhost:27017" \
  --db=tradingagents \
  --gzip \
  --noIndexRestore \
  ./backup/tradingagents
```

**参数说明**：
- `--noIndexRestore`：不还原索引（如果索引已存在）

## 实际使用场景

### 场景 1：每日自动备份

创建备份脚本 `backup.sh`：

```bash
#!/bin/bash

# 配置
BACKUP_DIR="/data/backups/tradingagents"
DATE=$(date +%Y%m%d_%H%M%S)
BACKUP_PATH="$BACKUP_DIR/backup_$DATE"

# 创建备份目录
mkdir -p "$BACKUP_PATH"

# 执行备份
mongodump \
  --uri="mongodb://localhost:27017" \
  --db=tradingagents \
  --out="$BACKUP_PATH" \
  --gzip

# 删除 7 天前的备份
find "$BACKUP_DIR" -type d -name "backup_*" -mtime +7 -exec rm -rf {} \;

echo "✅ 备份完成: $BACKUP_PATH"
```

添加到 crontab（每天凌晨 2 点执行）：

```bash
0 2 * * * /path/to/backup.sh >> /var/log/tradingagents_backup.log 2>&1
```

### 场景 2：迁移到新服务器

1. **在旧服务器上备份**：
   ```bash
   mongodump \
     --uri="mongodb://localhost:27017" \
     --db=tradingagents \
     --out=./backup \
     --gzip
   ```

2. **打包备份文件**：
   ```bash
   tar -czf tradingagents_backup.tar.gz backup/
   ```

3. **传输到新服务器**：
   ```bash
   scp tradingagents_backup.tar.gz user@new-server:/tmp/
   ```

4. **在新服务器上解压**：
   ```bash
   cd /tmp
   tar -xzf tradingagents_backup.tar.gz
   ```

5. **还原数据**：
   ```bash
   mongorestore \
     --uri="mongodb://localhost:27017" \
     --db=tradingagents \
     --gzip \
     ./backup/tradingagents
   ```

### 场景 3：只备份配置数据（用于演示系统）

```bash
# 备份配置集合
mongodump \
  --uri="mongodb://localhost:27017" \
  --db=tradingagents \
  --out=./backup_config \
  --gzip \
  --nsInclude="tradingagents.system_configs" \
  --nsInclude="tradingagents.llm_providers" \
  --nsInclude="tradingagents.market_categories" \
  --nsInclude="tradingagents.datasource_groupings" \
  --nsInclude="tradingagents.model_catalog"
```

### 场景 4：灾难恢复

如果数据库损坏，从最近的备份恢复：

```bash
# 1. 停止应用
docker-compose stop web

# 2. 删除现有数据并还原
mongorestore \
  --uri="mongodb://localhost:27017" \
  --db=tradingagents \
  --drop \
  --gzip \
  ./backup/tradingagents

# 3. 重启应用
docker-compose start web
```

## 性能对比

以 500MB 数据库为例：

| 方法 | 备份时间 | 还原时间 | 文件大小 |
|------|---------|---------|---------|
| Web 界面（JSON） | ~10 分钟 | ~15 分钟 | 500 MB |
| mongodump（BSON + gzip） | ~30 秒 | ~45 秒 | 50 MB |

**速度提升**：20-30 倍 🚀

## 常见问题

### Q1: 如何查看备份文件的内容？

```bash
# 查看备份的集合列表
ls -lh backup/tradingagents/

# 查看集合的文档数量
bsondump backup/tradingagents/system_configs.bson.gz | wc -l
```

### Q2: 备份文件可以在不同版本的 MongoDB 之间使用吗？

可以，但建议：
- MongoDB 3.x → 4.x：兼容
- MongoDB 4.x → 5.x：兼容
- 跨大版本（如 3.x → 5.x）：建议先测试

### Q3: 如何验证备份是否成功？

```bash
# 方法 1：检查备份文件大小
du -sh backup/tradingagents/

# 方法 2：还原到测试数据库
mongorestore \
  --uri="mongodb://localhost:27017" \
  --db=tradingagents_test \
  --gzip \
  ./backup/tradingagents

# 方法 3：使用 bsondump 检查文件
bsondump backup/tradingagents/system_configs.bson.gz | head -n 10
```

### Q4: 备份时会锁定数据库吗？

不会。`mongodump` 使用快照读取，不会阻塞写操作。

### Q5: 如何备份到云存储（如 AWS S3）？

```bash
# 1. 先备份到本地
mongodump --uri="mongodb://localhost:27017" --db=tradingagents --out=./backup --gzip

# 2. 上传到 S3
aws s3 sync ./backup s3://my-bucket/tradingagents-backup/$(date +%Y%m%d)/
```

## 相关资源

- [MongoDB Database Tools 官方文档](https://www.mongodb.com/docs/database-tools/)
- [mongodump 参考手册](https://www.mongodb.com/docs/database-tools/mongodump/)
- [mongorestore 参考手册](https://www.mongodb.com/docs/database-tools/mongorestore/)

## 总结

- ✅ **推荐**：使用 `mongodump` 和 `mongorestore` 进行备份和还原
- ❌ **不推荐**：通过 Web 界面操作大数据量备份
- 💡 **最佳实践**：设置自动备份脚本，定期清理旧备份
- 🔒 **安全提示**：备份文件包含敏感数据，请妥善保管

