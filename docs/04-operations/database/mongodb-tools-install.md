# MongoDB Database Tools 安装指南

## 概述

MongoDB Database Tools 包含 `mongodump` 和 `mongorestore` 等工具，用于快速备份和还原 MongoDB 数据库。

**为什么需要安装？**

- ✅ **速度快**：使用原生 BSON 格式，比 Python 实现快 20-30 倍
- ✅ **压缩效率高**：原生支持 gzip 压缩
- ✅ **支持大数据量**：可以处理 GB 级别的数据
- ✅ **可靠性高**：MongoDB 官方工具，经过充分测试

**如果不安装会怎样？**

系统会自动降级到 Python 实现的备份功能，虽然速度较慢，但功能完整。

## 自动安装（推荐）

### Windows

1. **运行安装脚本**：
   ```powershell
   # 方法1：使用 BAT 文件（双击运行）
   scripts\installer\install_mongodb_tools.bat
   
   # 方法2：使用 PowerShell 脚本
   powershell.exe -ExecutionPolicy Bypass -File scripts\installer\install_mongodb_tools.ps1
   ```

2. **安装选项**：
   - 默认安装到 `tools\mongodb-tools\` 目录
   - 可选择是否添加到系统 PATH
   - 如果添加到 PATH，需要重新打开命令行窗口

3. **验证安装**：
   ```powershell
   mongodump --version
   mongorestore --version
   ```

### Linux / macOS

```bash
# Ubuntu/Debian
sudo apt-get install mongodb-database-tools

# macOS (使用 Homebrew)
brew install mongodb-database-tools

# 验证
mongodump --version
mongorestore --version
```

## 手动安装

### Windows

1. **下载 MongoDB Database Tools**：
   - 访问：https://www.mongodb.com/try/download/database-tools
   - 选择 Windows 版本（x86_64）
   - 下载 ZIP 文件

2. **解压文件**：
   - 解压到应用目录下的 `tools\mongodb-tools\` 目录
   - 例如：`C:\TradingAgentsCN\tools\mongodb-tools\`

3. **添加到 PATH（可选）**：
   - 打开"系统属性" → "环境变量"
   - 在"用户变量"的 PATH 中添加：`C:\TradingAgentsCN\tools\mongodb-tools`
   - 重新打开命令行窗口

4. **验证安装**：
   ```powershell
   C:\TradingAgentsCN\tools\mongodb-tools\mongodump.exe --version
   ```

### Linux

```bash
# 下载并解压
wget https://fastdl.mongodb.org/tools/db/mongodb-database-tools-ubuntu2004-x86_64-100.9.4.tgz
tar -xzf mongodb-database-tools-ubuntu2004-x86_64-100.9.4.tgz

# 移动到系统目录（可选）
sudo mv mongodb-database-tools-ubuntu2004-x86_64-100.9.4/bin/* /usr/local/bin/

# 验证
mongodump --version
```

### macOS

```bash
# 使用 Homebrew（推荐）
brew install mongodb-database-tools

# 或手动下载
# 访问：https://www.mongodb.com/try/download/database-tools
# 选择 macOS 版本，解压后添加到 PATH
```

## 应用自动检测

应用会自动检测 MongoDB Database Tools 的位置：

1. **PATH 环境变量**：优先使用系统 PATH 中的工具
2. **应用目录**：如果 PATH 中没有，会检查以下位置：
   - `tools\mongodb-tools\mongodump.exe`
   - `data\tools\mongodb-tools\mongodump.exe`
   - 应用根目录下的 `tools\mongodb-tools\mongodump.exe`

**注意**：如果工具安装在应用目录下，即使没有添加到 PATH，应用也能自动找到并使用。

## 使用说明

### 备份数据库

安装完成后，在 Web 界面的"数据库管理"页面创建备份时，系统会自动使用 `mongodump`（如果可用）。

### 还原数据库

使用命令行还原：

```powershell
# Windows
mongorestore --uri="mongodb://localhost:27017" --db=tradingagents --gzip .\backup\tradingagents

# Linux/macOS
mongorestore --uri="mongodb://localhost:27017" --db=tradingagents --gzip ./backup/tradingagents
```

## 常见问题

### Q1: 安装后仍然提示找不到 mongodump？

**解决方案**：
1. 检查工具是否安装在正确的位置
2. 如果添加到 PATH，请重新打开命令行窗口
3. 检查应用日志，查看检测到的路径

### Q2: 不想安装 MongoDB Database Tools，可以使用其他方式吗？

**可以**：系统会自动降级到 Python 实现的备份功能，虽然速度较慢，但功能完整。

### Q3: 安装脚本下载失败？

**解决方案**：
1. 检查网络连接
2. 手动下载：https://www.mongodb.com/try/download/database-tools
3. 解压到 `tools\mongodb-tools\` 目录

### Q4: 如何更新 MongoDB Database Tools？

**方法**：
1. 删除旧版本：`tools\mongodb-tools\`
2. 运行安装脚本重新安装
3. 或手动下载新版本替换

## 性能对比

以 500MB 数据库为例：

| 方法 | 备份时间 | 还原时间 | 文件大小 |
|------|---------|---------|---------|
| Python 实现（JSON） | ~10 分钟 | ~15 分钟 | 500 MB |
| mongodump（BSON + gzip） | ~30 秒 | ~45 秒 | 50 MB |

**速度提升**：20-30 倍 🚀

## 相关文档

- [数据库备份与还原指南](./DATABASE_BACKUP_RESTORE.md)
- [MongoDB 官方文档](https://docs.mongodb.com/database-tools/)
