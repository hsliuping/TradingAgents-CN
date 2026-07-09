# TradingAgents-CN Pro v1.0.0 - 快速开始

## 🚀 5分钟快速启动

### 步骤 1: 解压文件

```powershell
# 解压便携版包
Expand-Archive TradingAgentsCN-Pro-Portable-1.0.0-YYYYMMDD-HHMMSS.zip -DestinationPath C:\TradingAgentsCN-Pro
```

### 步骤 2: 首次启动

```powershell
# 进入目录
cd C:\TradingAgentsCN-Pro

# 运行首次启动脚本（自动初始化数据库）
.\start_pro_first_time.ps1
```

### 步骤 3: 访问系统

打开浏览器访问: **http://localhost**

**默认账号**:
- 用户名: `admin`
- 密码: `admin123`

### 步骤 4: 配置 API 密钥

登录后进入 **系统管理** → **LLM 配置**，配置以下 API 密钥：

- Google Gemini API Key
- OpenAI API Key
- DeepSeek API Key
- 通义千问 API Key

### 步骤 5: 开始使用

- 创建分析任务
- 查看分析报告
- 管理投资组合

---

## 📋 系统要求

### 最低配置

- **操作系统**: Windows 10/11 (64位)
- **CPU**: 双核 2.0 GHz
- **内存**: 4 GB RAM
- **硬盘**: 2 GB 可用空间

### 推荐配置

- **操作系统**: Windows 11 (64位)
- **CPU**: 四核 3.0 GHz
- **内存**: 8 GB RAM
- **硬盘**: 5 GB 可用空间
- **网络**: 稳定的互联网连接

---

## 🔧 常用命令

### 启动服务

```powershell
# 首次启动（自动初始化）
.\start_pro_first_time.ps1

# 正常启动
.\start_all.ps1

# 启动单个服务
.\start_mongodb.ps1
.\start_redis.ps1
.\start_backend.ps1
.\start_frontend.ps1
```

### 停止服务

```powershell
# 停止所有服务
.\stop_all.ps1
```

### 数据库管理

```powershell
# 初始化数据库
.\scripts\deployment\init_pro_database.ps1

# 重新初始化（先删除标记文件）
Remove-Item .\data\.db_initialized -Force
.\scripts\deployment\init_pro_database.ps1
```

---

## 🗄️ 数据库配置

### 自动初始化

首次启动时会自动：
1. ✅ 启动 MongoDB 和 Redis
2. ✅ 导入预配置数据
3. ✅ 创建默认管理员账号
4. ✅ 启动应用服务

### 手动初始化

如需手动初始化：

```powershell
# 方法 1: 使用初始化脚本
.\scripts\deployment\init_pro_database.ps1

# 方法 2: 使用导入脚本
python scripts\import_config_and_create_user.py `
    install\database_export_config_2025-11-13.json `
    --host --overwrite
```

---

## 🔐 安全建议

### 首次登录后

⚠️ **重要**: 请立即执行以下操作：

1. **修改默认密码**
   - 进入 **用户设置** → **修改密码**
   - 设置强密码（至少 8 位，包含大小写字母、数字和特殊字符）

2. **配置 API 密钥**
   - 进入 **系统管理** → **LLM 配置**
   - 为每个模型配置 API 密钥
   - 不要在配置中使用测试密钥

3. **备份配置**
   - 定期导出配置数据
   - 保存到安全位置

---

## 📊 预配置内容

### LLM 模型 (需配置 API 密钥)

| 模型 | 提供商 | 用途 |
|------|--------|------|
| Gemini 2.5 Pro | Google | 深度分析 |
| Gemini 2.5 Flash | Google | 快速分析 |
| GPT-4o | OpenAI | 高质量分析 |
| GPT-4o Mini | OpenAI | 快速分析 |
| DeepSeek Chat | DeepSeek | 成本优化 |
| Qwen Plus | 阿里云 | 中文优化 |

### 数据源

| 数据源 | 市场 | 需要配置 |
|--------|------|---------|
| AKShare | A股、港股 | ❌ 免费 |
| Tushare | A股 | ✅ Token |
| Yahoo Finance | 美股、港股 | ❌ 免费 |
| Alpha Vantage | 美股 | ✅ API Key |
| Finnhub | 美股 | ✅ API Key |

---

## ❓ 常见问题

### Q: 启动失败怎么办？

**A**: 检查以下几点：
1. 端口是否被占用（27017, 6379, 8000, 3000）
2. 防火墙是否阻止
3. 查看日志文件 `logs/`

### Q: 无法登录？

**A**: 
1. 确认使用默认账号: `admin` / `admin123`
2. 检查数据库是否初始化成功
3. 查看后端日志

### Q: API 调用失败？

**A**:
1. 检查 API 密钥是否正确配置
2. 检查网络连接
3. 查看 LLM 配置中的错误信息

### Q: 数据同步失败？

**A**:
1. 检查数据源 API 密钥
2. 检查网络连接
3. 查看同步日志

---

## 📚 更多资源

- 📖 **完整文档**: `docs/`
- 🗄️ **数据库配置**: `DATABASE_INIT_SOLUTION.md`
- 📝 **发布说明**: `RELEASE_NOTES_v1.0.0.md`
- 🔧 **配置说明**: `install/README_PRO.md`

---

## 💬 技术支持

- 📧 Email: support@tradingagents-cn.com
- 🐛 Issues: GitHub Issues
- 💬 讨论: GitHub Discussions

---

**版权所有 © 2024-2025 TradingAgents-CN Pro Team**

**祝您使用愉快！** 🎉

