# TradingAgents-CN 快速安装指南

> 5分钟快速上手 TradingAgents-CN v1.0.0-preview

## 🚀 三种部署方式，一键选择

### 方式一：绿色版（最简单）⭐ 推荐新手

**适合**: Windows 用户、快速体验、个人使用

```powershell
# 1. 下载绿色版压缩包
# 2. 解压到任意目录（如 D:\TradingAgentsCN-portable）
# 3. 以管理员身份运行 PowerShell，执行：
cd D:\TradingAgentsCN-portable
powershell -ExecutionPolicy Bypass -File start_all.ps1

# 4. 打开浏览器访问 http://localhost
```

**优点**: ✅ 开箱即用 ✅ 无需配置环境 ✅ 一键启动  
**缺点**: ⚠️ 仅支持 Windows

📥 **下载地址**: 

- 关注公众号 "TradingAgents-CN" 获取网盘链接

操作手册：

https://mp.weixin.qq.com/s/uAk4RevdJHMuMvlqpdGUEw
TradingAgents-CN v1.0.0-preview绿色版（目前只支持windows）简单使用手册
https://mp.weixin.qq.com/s/o5QdNuh2-iKkIHzJXCj7vQ
TradingAgents-CN v1.0.0-preview绿色版绿色版端口配置说明
---

### 方式二：Docker版（最稳定）⭐ 推荐生产环境

**适合**: 所有平台、生产环境、多用户、长期运行

```bash
# 1. 安装 Docker 和 Docker Compose
# 2. 创建项目目录
mkdir tradingagents-cn && cd tradingagents-cn

# 3. 下载配置文件
curl -O https://raw.githubusercontent.com/hsliuping/TradingAgents-CN/main/docker-compose.yml
curl -O https://raw.githubusercontent.com/hsliuping/TradingAgents-CN/main/.env.example
mv .env.example .env

# 4. 编辑 .env 文件，配置 API 密钥
nano .env

# 5. 启动服务
docker-compose up -d

# 6. 查看日志
docker-compose logs -f

# 7. 打开浏览器访问 http://localhost:5173
```

**优点**: ✅ 跨平台 ✅ 隔离性好 ✅ 易于维护 ✅ 生产就绪  
**缺点**: ⚠️ 需要学习 Docker

📚 **详细文档**: [Docker 部署指南](./docker-deployment-guide.md)

---

### 方式三：本地代码版（最灵活）⭐ 推荐开发者

**适合**: 开发者、定制需求、学习研究

```bash
# 1. 安装依赖: Python 3.10+, MongoDB 4.4+, Redis 6.2+

# 2. 克隆代码
git clone https://github.com/hsliuping/TradingAgents-CN.git
cd TradingAgents-CN

# 3. 创建虚拟环境
python -m venv env
source env/bin/activate  # Windows: env\Scripts\activate

# 4. 安装依赖
pip install -r requirements.txt

# 5. 配置环境变量
cp .env.example .env
nano .env  # 编辑配置

# 6. 初始化数据库
python scripts/import_config_and_create_user.py

# 7. 启动后端
python -m app

# 8. 打开浏览器访问 http://localhost:8000/docs
```

**优点**: ✅ 完全控制 ✅ 可调试 ✅ 可定制  
**缺点**: ⚠️ 配置复杂 ⚠️ 需要手动管理依赖

📚 **详细文档**: [本地安装指南](./installation-guide.md)

---

## 🔑 必需配置：API 密钥

无论选择哪种部署方式，都需要配置至少一个 LLM API 密钥。

### 推荐的 API 提供商

| 提供商 | 推荐理由 | 获取地址 | 价格 |
|--------|---------|---------|------|
| **阿里百炼** | 性价比高、稳定 | [dashscope.console.aliyun.com](https://dashscope.console.aliyun.com/) | ¥0.002/1k tokens |
| **DeepSeek** | 价格便宜、效果好 | [platform.deepseek.com](https://platform.deepseek.com/) | ¥0.001/1k tokens |
| **Google AI** | 免费额度大 | [aistudio.google.com](https://aistudio.google.com/) | 免费 |
| **OpenAI** | 效果最好 | [platform.openai.com](https://platform.openai.com/) | $0.01/1k tokens |

### 配置方法

编辑 `.env` 文件，添加以下内容（至少配置一个）：

```env
# 阿里百炼（推荐）
DASHSCOPE_API_KEY=sk-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx

# DeepSeek（推荐）
DEEPSEEK_API_KEY=sk-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx

# Google AI（推荐）
GOOGLE_API_KEY=AIzaSyxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx

# OpenAI（可选）
OPENAI_API_KEY=sk-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
```

---

## 👤 首次登录

所有部署方式的默认管理员账号：

- **用户名**: `admin`
- **密码**: `admin123`

⚠️ **重要**: 首次登录后请立即修改密码！

---

## 🎯 快速开始分析

1. **登录系统**: 使用默认账号登录
2. **进入股票分析**: 点击左侧菜单 "股票分析"
3. **输入股票代码**: 
   - A股: `600519` (贵州茅台)
   - 港股: `00700.HK` (腾讯控股)
   - 美股: `AAPL` (苹果)
4. **选择分析参数**:
   - 分析师: 建议选择 "完整分析"
   - 研究深度: 建议选择 "标准"
   - LLM 模型: 选择已配置的模型
5. **开始分析**: 点击 "开始分析" 按钮
6. **查看结果**: 等待分析完成，查看详细报告

---

## ❓ 常见问题

### Q: 启动失败，提示端口被占用？

**A**: 修改 `.env` 文件中的端口配置：

```env
# 后端端口（默认 8000）
BACKEND_PORT=8001

# 前端端口（默认 5173）
FRONTEND_PORT=5174
```

### Q: MongoDB 连接失败？

**A**: 
1. 检查 MongoDB 是否正在运行
2. 检查 `.env` 中的 `MONGODB_URL` 配置
3. 绿色版用户：确保 MongoDB 服务已启动

### Q: API 密钥无效？

**A**:
1. 检查 API 密钥是否正确复制（无多余空格）
2. 确认 API 密钥有足够的额度
3. 检查 API 密钥是否过期

### Q: 分析失败，提示数据获取错误？

**A**:
1. 检查网络连接是否正常
2. 确认股票代码格式正确
3. 配置 Tushare Token（可选，提高数据质量）

---

## 📚 更多资源

### 官方文档

- [完整安装指南](./INSTALLATION_GUIDE_V1.md)
- [使用指南](https://mp.weixin.qq.com/s/ppsYiBncynxlsfKFG8uEbw)
- [配置管理指南](./config-management-guide.md)
- [API 文档](http://localhost:8000/docs)

### 视频教程

关注微信公众号 **"TradingAgents-CN"** 获取：
- 安装部署视频教程
- 功能使用演示
- 最佳实践分享

### 社区支持

- **GitHub Issues**: [提交问题](https://github.com/hsliuping/TradingAgents-CN/issues)
- **微信公众号**: TradingAgents-CN
- **QQ 群**: 关注公众号获取群号

---

## 🎉 开始使用

选择适合您的部署方式，5分钟快速上手！

- 🟢 **新手用户** → [绿色版](#方式一绿色版最简单-推荐新手)
- 🐳 **生产环境** → [Docker版](#方式二docker版最稳定-推荐生产环境)
- 💻 **开发者** → [本地代码版](#方式三本地代码版最灵活-推荐开发者)

祝您使用愉快！如有问题，欢迎随时联系我们。

