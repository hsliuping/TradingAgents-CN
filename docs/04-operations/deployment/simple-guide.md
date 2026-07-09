# 🚀 个人用户简化部署指南

> **目标**：让个人用户在5分钟内完成部署，无需复杂配置

## 📋 方案概述

本指南提供了一个**极简部署方案**，专为个人用户设计，特点：

- ✅ **一键安装脚本**：自动安装所有依赖
- ✅ **交互式配置**：引导式填写必要信息
- ✅ **智能降级**：数据库可选，自动使用文件存储
- ✅ **健康检查**：自动诊断和修复问题
- ✅ **零基础友好**：无需Docker、数据库知识
- ✅ **开源透明**：所有脚本源代码可见，用户自行运行

## ⚠️ 重要说明

**本项目是开源软件**：
- ✅ 提供源代码和安装脚本
- ✅ 用户自行下载、运行脚本、配置环境
- ❌ 不提供预编译的可执行安装包
- ❌ 用户需自行承担使用责任

**为什么不提供安装包**：
1. 保持开源软件的透明性
2. 避免潜在的法律责任
3. 让用户完全掌控安装过程
4. 确保安全性（用户可审查脚本代码）

## 🎯 快速开始（推荐）

### Windows 用户

```powershell
# 1. 下载项目
git clone https://github.com/hsliuping/TradingAgents-CN.git
cd TradingAgents-CN

# 2. 运行一键安装脚本
powershell -ExecutionPolicy Bypass -File scripts/easy_install.ps1

# 3. 按照提示完成配置
# 脚本会自动：
# - 检查Python版本
# - 创建虚拟环境
# - 安装依赖
# - 引导配置API密钥
# - 启动应用

# 4. 浏览器自动打开 http://localhost:8501
```

### Linux/Mac 用户

```bash
# 1. 下载项目
git clone https://github.com/hsliuping/TradingAgents-CN.git
cd TradingAgents-CN

# 2. 运行一键安装脚本
chmod +x scripts/easy_install.sh
./scripts/easy_install.sh

# 3. 按照提示完成配置
# 4. 浏览器自动打开 http://localhost:8501
```

## 📝 最小化配置

### 必需配置（仅1项）

只需要配置**一个**大模型API密钥即可开始使用：

#### 选项1：DeepSeek（推荐，性价比最高）

```bash
# 获取地址：https://platform.deepseek.com/
# 注册 -> 创建API Key -> 复制
DEEPSEEK_API_KEY=sk-xxxxxxxxxxxxxxxx
```

#### 选项2：通义千问（国产，稳定）

```bash
# 获取地址：https://dashscope.aliyun.com/
# 注册阿里云 -> 开通百炼 -> 获取密钥
DASHSCOPE_API_KEY=sk-xxxxxxxxxxxxxxxx
```

#### 选项3：Google Gemini（免费额度大）

```bash
# 获取地址：https://aistudio.google.com/
# 注册 -> 创建API Key -> 复制
GOOGLE_API_KEY=AIzaSyxxxxxxxxxxxxxxxx
```

### 可选配置（提升体验）

```bash
# A股数据增强（可选）
TUSHARE_TOKEN=your_token  # https://tushare.pro/

# 美股数据（可选）
FINNHUB_API_KEY=your_key  # https://finnhub.io/
```

## 🔧 部署模式对比

### 模式1：极简模式（推荐个人用户）

**特点**：
- ✅ 无需数据库
- ✅ 使用文件存储
- ✅ 5分钟完成部署
- ✅ 适合日常使用

**配置**：
```bash
# .env 文件（仅需3行）
DEEPSEEK_API_KEY=sk-xxxxxxxx
MONGODB_ENABLED=false
REDIS_ENABLED=false
```

**启动**：
```bash
python start_web.py
```

### 模式2：标准模式（推荐有Docker用户）

**特点**：
- ✅ 包含数据库
- ✅ 性能更好
- ✅ 数据持久化
- ✅ 适合频繁使用

**启动**：
```bash
docker-compose up -d
```

### 模式3：专业模式（开发者）

**特点**：
- ✅ 完整功能
- ✅ 可定制化
- ✅ 多应用架构
- ✅ 适合二次开发

**启动**：
```bash
# 后端
python start_backend.py

# 前端
python start_frontend.py

# Web
python start_web.py
```

## 📦 一键安装脚本功能

### 自动检测和安装

1. **环境检查**
   - Python版本（3.10+）
   - pip版本
   - 网络连接

2. **依赖安装**
   - 自动创建虚拟环境
   - 安装Python包
   - 配置环境变量

3. **配置向导**
   - 交互式选择LLM提供商
   - 引导填写API密钥
   - 自动生成.env文件

4. **健康检查**
   - 验证API密钥
   - 测试网络连接
   - 检查端口占用

5. **自动启动**
   - 启动Web应用
   - 打开浏览器
   - 显示使用提示

## 🎯 使用流程

### 第一次使用

```
1. 运行安装脚本
   ↓
2. 选择LLM提供商（DeepSeek/通义千问/Gemini）
   ↓
3. 输入API密钥
   ↓
4. 选择部署模式（极简/标准）
   ↓
5. 自动安装和启动
   ↓
6. 浏览器打开，开始使用
```

### 日常使用

```bash
# Windows
.\start_web.bat

# Linux/Mac
./start_web.sh

# 或使用Python脚本
python start_web.py
```

## 🔍 故障排除

### 问题1：Python版本不符

```bash
# 检查Python版本
python --version

# 需要Python 3.10+
# 下载地址：https://www.python.org/downloads/
```

### 问题2：网络连接失败

```bash
# 测试网络
ping api.deepseek.com

# 如果无法访问，尝试：
# 1. 检查防火墙设置
# 2. 使用代理
# 3. 切换其他LLM提供商
```

### 问题3：端口被占用

```bash
# Windows查看端口占用
netstat -ano | findstr :8501

# Linux/Mac查看端口占用
lsof -i :8501

# 修改端口（在.env中）
STREAMLIT_PORT=8502
```

### 问题4：API密钥无效

```bash
# 运行验证脚本
python scripts/validate_api_keys.py

# 重新配置
python scripts/easy_install.py --reconfigure
```

## 💡 使用技巧

### 技巧1：快速切换模型

在Web界面侧边栏可以快速切换不同的LLM模型，无需重启应用。

### 技巧2：离线使用

配置好后，可以在无网络环境下使用（需要提前缓存数据）：

```bash
# 预先下载股票数据
python scripts/prefetch_stock_data.py 000001 600519 AAPL
```

### 技巧3：批量分析

使用批量分析功能一次分析多只股票：

```python
# 在Web界面输入多个股票代码（逗号分隔）
000001, 600519, 300750
```

### 技巧4：导出报告

分析完成后可以导出专业报告：
- Markdown：适合在线查看
- Word：适合编辑修改
- PDF：适合打印分享

## 📊 性能对比

| 部署模式 | 启动时间 | 分析速度 | 内存占用 | 磁盘占用 |
|---------|---------|---------|---------|---------|
| 极简模式 | 10秒 | 中等 | 500MB | 1GB |
| 标准模式 | 30秒 | 快速 | 1.5GB | 3GB |
| 专业模式 | 60秒 | 最快 | 2.5GB | 5GB |

## 🎓 学习路径

### 新手用户

1. 使用极简模式部署
2. 尝试分析熟悉的股票
3. 了解基本功能
4. 阅读使用文档

### 进阶用户

1. 升级到标准模式
2. 配置多个数据源
3. 使用批量分析
4. 自定义分析参数

### 专业用户

1. 使用专业模式
2. 二次开发定制
3. 集成到工作流
4. 贡献代码改进

## 📚 相关文档

- [完整部署指南](./README.md#-快速开始)
- [配置说明](./docs/configuration/)
- [API文档](./docs/api/)
- [常见问题](./docs/faq/faq.md)

## 🆘 获取帮助

- **GitHub Issues**: [提交问题](https://github.com/hsliuping/TradingAgents-CN/issues)
- **QQ群**: 782124367
- **邮箱**: hsliup@163.com

---

**🎉 祝您使用愉快！**

