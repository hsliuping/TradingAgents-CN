# 🚀 TradingAgents-CN 快速开始

> ⏱️ **5分钟快速上手** | 📋 **零基础友好** | 🎯 **一键启动**

## 🎯 选择您的安装方式

### 🐳 方式一：Docker安装（推荐）
**适合**: 所有用户，特别是新手用户
**优势**: 一键启动，环境隔离，稳定可靠

```bash
# 1. 克隆项目
git clone https://github.com/hsliuping/TradingAgents-CN.git
cd TradingAgents-CN

# 2. 配置API密钥
cp .env.example .env
# 编辑.env文件，添加您的API密钥

# 3. 启动服务
docker-compose up -d

# 4. 访问应用
# 浏览器打开: http://localhost:8501
```

### 💻 方式二：本地安装
**适合**: 开发者和高级用户
**优势**: 更多控制权，便于开发调试

```bash
# 1. 克隆项目
git clone https://github.com/hsliuping/TradingAgents-CN.git
cd TradingAgents-CN

# 2. 创建虚拟环境
python -m venv env

# 3. 激活虚拟环境
# Windows: env\Scripts\activate
# macOS/Linux: source env/bin/activate

# 4. 安装依赖
pip install -r requirements.txt

# 5. 配置API密钥
cp .env.example .env
# 编辑.env文件，添加您的API密钥

# 6. 启动应用
python -m streamlit run web/app.py
```

### 🤖 方式三：自动安装（最简单）
```bash
# 下载并运行自动安装脚本
python scripts/setup/quick_install.py
```

## 🔑 必需的API密钥

### 推荐配置（选择一个即可）

#### 1. DeepSeek（推荐，性价比最高）
- 🌐 **注册地址**: https://platform.deepseek.com/
- 💰 **费用**: ~¥1/万tokens，新用户有免费额度
- 🔧 **配置**: 在`.env`文件中设置 `DEEPSEEK_API_KEY`

#### 2. 通义千问（国产，稳定）
- 🌐 **注册地址**: https://dashscope.aliyun.com/
- 💰 **费用**: 按量计费，有免费额度
- 🔧 **配置**: 在`.env`文件中设置 `DASHSCOPE_API_KEY`

#### 3. OpenAI（功能强大）
- 🌐 **注册地址**: https://platform.openai.com/
- 💰 **费用**: 按使用量计费，需美元支付
- 🔧 **配置**: 在`.env`文件中设置 `OPENAI_API_KEY`

### 可选配置（提升体验）

#### Tushare（A股数据）
- 🌐 **注册地址**: https://tushare.pro/
- 💰 **费用**: 免费，有积分限制
- 🔧 **配置**: 在`.env`文件中设置 `TUSHARE_TOKEN`

## 📝 配置示例

编辑`.env`文件，添加您的API密钥：

```bash
# 选择一个AI模型（必须）
DEEPSEEK_API_KEY=sk-your-deepseek-key-here

# 或者使用通义千问
# DASHSCOPE_API_KEY=your-dashscope-key-here

# 或者使用OpenAI
# OPENAI_API_KEY=sk-your-openai-key-here

# A股数据源（推荐）
TUSHARE_TOKEN=your-tushare-token-here

# 数据库（可选，提升性能）
MONGODB_ENABLED=false
REDIS_ENABLED=false
```

## ✅ 验证安装

### 1. 访问Web界面
打开浏览器访问: http://localhost:8501

### 2. 测试分析功能
- 输入股票代码（如：`000001`、`AAPL`、`0700.HK`）
- 选择分析师团队
- 点击"开始分析"

### 3. 检查日志
```bash
# Docker环境
docker-compose logs web

# 本地环境
tail -f logs/tradingagents.log
```

## 🎯 第一次使用

### 推荐测试股票

#### A股测试
```
股票代码: 000001
市场类型: A股
研究深度: 1级（快速测试）
分析师: 市场分析师 + 基本面分析师
```

#### 美股测试
```
股票代码: AAPL
市场类型: 美股
研究深度: 1级（快速测试）
分析师: 市场分析师 + 基本面分析师
```

#### 港股测试
```
股票代码: 0700.HK
市场类型: 港股
研究深度: 1级（快速测试）
分析师: 市场分析师 + 基本面分析师
```

## ❓ 常见问题

### Q: 启动失败怎么办？
**A**: 检查以下几点：
1. Python版本是否为3.10+
2. 是否正确配置了API密钥
3. 网络连接是否正常
4. 端口8501是否被占用

### Q: 分析失败怎么办？
**A**: 检查以下几点：
1. API密钥是否有效
2. API余额是否充足
3. 股票代码格式是否正确
4. 网络是否能访问相关API

### Q: 如何获取更多帮助？
**A**: 
- 📖 **详细文档**: [docs/INSTALLATION_GUIDE.md](INSTALLATION_GUIDE.md)
- 🐛 **问题反馈**: https://github.com/hsliuping/TradingAgents-CN/issues
- 💬 **社区讨论**: 见项目主页的微信群二维码

## 🎉 开始使用

恭喜！您已成功安装TradingAgents-CN。

**下一步**:
1. 🔍 **探索功能**: 尝试不同的分析师组合和研究深度
2. 📊 **查看报告**: 分析完成后可导出PDF/Word报告
3. ⚙️ **优化配置**: 根据需要调整数据库和缓存设置
4. 🚀 **高级功能**: 探索批量分析、自定义提示等功能

**享受您的AI股票分析之旅！** 🚀📈
