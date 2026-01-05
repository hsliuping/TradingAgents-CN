# TradingAgents-CN Pro - 数据库配置说明

## 📋 概述

本目录包含 TradingAgents-CN Pro 的预配置数据库文件，用于快速初始化系统。

## 📂 文件说明

### `database_export_config_2025-11-13.json`

**文件大小**: ~14 MB  
**创建日期**: 2025-11-13  
**用途**: 完整的系统配置和初始数据

**包含的集合**:
- ✅ `system_configs` - 系统配置
- ✅ `users` - 用户数据（脱敏）
- ✅ `llm_providers` - LLM 提供商配置
- ✅ `model_catalog` - 模型目录
- ✅ `market_categories` - 市场分类
- ✅ `datasource_groupings` - 数据源分组
- ✅ `platform_configs` - 平台配置
- ✅ `user_configs` - 用户配置
- ✅ `user_tags` - 用户标签
- ✅ `user_favorites` - 用户收藏

---

## 🚀 使用方法

### 方法 1: 自动初始化（推荐）

便携版首次启动时会自动运行初始化脚本：

```powershell
# 运行首次启动脚本
.\start_pro_first_time.ps1
```

这将自动：
1. ✅ 启动 MongoDB 和 Redis
2. ✅ 导入配置数据
3. ✅ 创建默认管理员账号
4. ✅ 启动应用服务

### 方法 2: 手动初始化

如果需要手动初始化或重新初始化：

```powershell
# 1. 确保 MongoDB 正在运行
# 2. 运行初始化脚本
.\scripts\deployment\init_pro_database.ps1
```

### 方法 3: 使用导入脚本

直接使用导入脚本（高级用户）：

```powershell
# 导入配置（覆盖模式）
python scripts\import_config_and_create_user.py install\database_export_config_2025-11-13.json --host --overwrite

# 导入配置（增量模式，跳过已存在的数据）
python scripts\import_config_and_create_user.py install\database_export_config_2025-11-13.json --host --incremental

# 只创建默认用户
python scripts\import_config_and_create_user.py --create-user-only --host
```

---

## 🔐 默认账号

导入配置后，系统会自动创建默认管理员账号：

- **用户名**: `admin`
- **密码**: `admin123`
- **角色**: 管理员

⚠️ **安全提示**: 首次登录后请立即修改默认密码！

---

## ⚙️ 配置 API 密钥

预配置的 LLM 模型需要配置 API 密钥才能使用。

### 方法 1: 通过 Web 界面（推荐）

1. 登录系统
2. 进入 **系统管理** → **LLM 配置**
3. 为每个模型配置 API 密钥

### 方法 2: 通过环境变量

编辑 `.env` 文件：

```env
# Google AI
GOOGLE_API_KEY=your-google-api-key

# OpenAI
OPENAI_API_KEY=your-openai-api-key

# DeepSeek
DEEPSEEK_API_KEY=your-deepseek-api-key

# 通义千问
DASHSCOPE_API_KEY=your-dashscope-api-key
```

修改后重启后端服务。

---

## 📊 预配置内容

### LLM 模型

已预配置以下 LLM 模型（需要配置 API 密钥）：

- ✅ Google Gemini 2.5 Pro
- ✅ Google Gemini 2.5 Flash
- ✅ OpenAI GPT-4o
- ✅ OpenAI GPT-4o Mini
- ✅ DeepSeek Chat
- ✅ 通义千问 Qwen Plus
- ✅ 通义千问 Qwen Turbo

### 数据源

已预配置以下数据源：

- ✅ AKShare（A股、港股）
- ✅ Tushare（需要 Token）
- ✅ Yahoo Finance（美股、港股）
- ✅ Alpha Vantage（需要 API Key）
- ✅ Finnhub（需要 API Key）

### 市场分类

- ✅ A股市场
- ✅ 港股市场
- ✅ 美股市场
- ✅ 指数
- ✅ 行业板块

---

## 🔄 重新初始化

如果需要重新初始化数据库：

```powershell
# 1. 删除初始化标记
Remove-Item .\data\.db_initialized -Force

# 2. 重新运行初始化
.\scripts\deployment\init_pro_database.ps1
```

---

## ❓ 常见问题

### Q: 导入失败怎么办？

**A**: 检查以下几点：
1. MongoDB 是否正在运行
2. 配置文件是否完整
3. 查看错误日志

### Q: 如何导出当前配置？

**A**: 使用导出脚本：
```powershell
python scripts\export_config_data.py
```

### Q: 可以自定义配置吗？

**A**: 可以！导入后在 Web 界面中修改配置，然后导出保存。

---

## 📝 技术支持

- 📖 文档: `docs/`
- 🐛 问题反馈: GitHub Issues
- 💬 讨论: GitHub Discussions

---

**版权所有 © 2024-2025 TradingAgents-CN Pro Team**

