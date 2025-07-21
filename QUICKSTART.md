# 🚀 TradingAgents-CN 快速开始指南

> 📋 **版本**: cn-0.1.10 | **更新时间**: 2025-07-18
> 🎯 **目标**: 5分钟内完成部署并开始股票分析

## 🎯 选择部署方式

### 🐳 方式一：Docker部署 (推荐)

**适用场景**: 生产环境、快速体验、零配置启动

```bash
# 1. 克隆项目
git clone https://github.com/hsliuping/TradingAgents-CN.git
cd TradingAgents-CN

# 2. 配置环境变量
cp .env.example .env
# 编辑 .env 文件，填入API密钥

# 3. 构建并启动服务
docker-compose up -d --build

# 注意：首次运行会自动构建Docker镜像，需要5-10分钟时间
# 构建过程包括：
# - 下载基础镜像和依赖 (~800MB)
# - 安装系统工具 (pandoc, wkhtmltopdf等)
# - 安装Python依赖包
# - 配置运行环境

# 4. 访问应用
# Web界面: http://localhost:8501
# 数据库管理: http://localhost:8081
# 缓存管理: http://localhost:8082
```

### 🔧 分步构建方式 (可选)

如果您希望分步进行，可以先单独构建镜像：

```bash
# 方式A: 分步构建
# 1. 先构建Docker镜像
docker build -t tradingagents-cn:latest .

# 2. 再启动所有服务
docker-compose up -d

# 方式B: 一键构建启动 (推荐)
docker-compose up -d --build
```

### 💻 方式二：本地部署

**适用场景**: 开发环境、自定义配置、离线使用

```bash
# 1. 克隆项目
git clone https://github.com/hsliuping/TradingAgents-CN.git
cd TradingAgents-CN

# 2. 创建虚拟环境
python -m venv env
env\Scripts\activate  # Windows
# source env/bin/activate  # Linux/macOS

# 3. 安装依赖
pip install -r requirements.txt

# 4. 安装项目到虚拟环境（重要！）
pip install -e .

# 5. 配置环境变量
cp .env.example .env
# 编辑 .env 文件

# 6. 启动应用
# 方法1: 使用简化启动脚本（推荐）
python start_web.py

# 方法2: 使用项目启动脚本
python web/run_web.py

# 方法3: 直接使用streamlit（需要先安装项目）
streamlit run web/app.py
```

## 🔧 环境配置

### 📋 必需配置

创建 `.env` 文件并配置以下内容：

```bash
# === LLM模型配置 (至少选择一个) ===

# 🇨🇳 DeepSeek (推荐 - 成本低，中文优化)
DEEPSEEK_API_KEY=sk-your_deepseek_api_key_here
DEEPSEEK_ENABLED=true

# 🇨🇳 阿里百炼通义千问 (推荐 - 中文理解好)
QWEN_API_KEY=your_qwen_api_key
QWEN_ENABLED=true

# 🌍 Google AI Gemini (推荐 - 推理能力强)
GOOGLE_API_KEY=your_google_api_key
GOOGLE_ENABLED=true

# 🤖 OpenAI (可选 - 通用能力强，成本较高)
OPENAI_API_KEY=your_openai_api_key
OPENAI_ENABLED=true
```

### 🔑 API密钥获取


| 提供商        | 获取地址                                                | 特色               | 成本      |
| ------------- | ------------------------------------------------------- | ------------------ | --------- |
| **DeepSeek**  | [platform.deepseek.com](https://platform.deepseek.com/) | 工具调用，中文优化 | 💰 极低   |
| **阿里百炼**  | [dashscope.aliyun.com](https://dashscope.aliyun.com/)   | 中文理解，响应快   | 💰 低     |
| **Google AI** | [aistudio.google.com](https://aistudio.google.com/)     | 推理能力，多模态   | 💰💰 中等 |
| **OpenAI**    | [platform.openai.com](https://platform.openai.com/)     | 通用能力强         | 💰💰💰 高 |

### 📊 可选配置

```bash
# === 数据源配置 (可选) ===
TUSHARE_TOKEN=your_tushare_token          # A股数据增强
FINNHUB_API_KEY=your_finnhub_key          # 美股数据

# === 数据库配置 (Docker自动配置) ===
MONGODB_URL=mongodb://mongodb:27017/tradingagents  # Docker环境
REDIS_URL=redis://redis:6379                       # Docker环境

# === 导出功能配置 ===
EXPORT_ENABLED=true                       # 启用报告导出
EXPORT_DEFAULT_FORMAT=word,pdf            # 默认导出格式
```

## 🚀 开始使用

### 1️⃣ 访问Web界面

```bash
# 打开浏览器访问
http://localhost:8501
```

### 2️⃣ 配置分析参数

- **🧠 选择LLM模型**: DeepSeek V3 / 通义千问 / Gemini
- **📊 选择分析深度**: 快速 / 标准 / 深度
- **🎯 选择分析师**: 市场分析 / 基本面分析 / 新闻分析

### 3️⃣ 输入股票代码

```bash
# 🇨🇳 A股示例
000001  # 平安银行
600519  # 贵州茅台
000858  # 五粮液

# 🇺🇸 美股示例  
AAPL    # 苹果公司
TSLA    # 特斯拉
MSFT    # 微软
```

### 4️⃣ 开始分析

1. 点击"🚀 开始分析"按钮
2. **📊 实时进度跟踪**: 观察分析进度和当前步骤
   - 显示已用时间和预计剩余时间
   - 实时更新分析状态和步骤说明
   - 支持手动刷新和自动刷新控制
3. **⏰ 分析完成**: 等待分析完成（2-10分钟，取决于分析深度）
   - 显示准确的总耗时
   - 自动显示"🎉 分析完成"状态
4. **📋 查看报告**: 点击"📊 查看分析报告"按钮
   - 即时显示详细的投资建议和分析报告
   - 支持重复查看和页面刷新后恢复
5. **📄 导出报告**: 可选择导出为Word/PDF/Markdown格式

### 🆕 v0.1.10 新功能亮点

#### 🚀 实时进度显示
- **异步进度跟踪**: 实时显示分析进度，不再需要盲等
- **智能步骤识别**: 自动识别当前分析步骤和状态
- **准确时间计算**: 显示真实的分析耗时，不受查看时间影响

#### 📊 智能会话管理
- **状态持久化**: 支持页面刷新后恢复分析状态
- **自动降级**: Redis不可用时自动切换到文件存储
- **用户体验**: 提供更稳定可靠的会话管理

#### 🎨 界面优化
- **查看报告按钮**: 分析完成后一键查看报告
- **重复按钮清理**: 移除重复的刷新按钮，界面更简洁
- **响应式设计**: 改进移动端和不同屏幕的适配

## 📄 报告导出功能

### 支持格式


| 格式            | 用途               | 特点               |
| --------------- | ------------------ | ------------------ |
| **📝 Markdown** | 在线查看，版本控制 | 轻量级，可编辑     |
| **📄 Word**     | 商业报告，编辑修改 | 专业格式，易编辑   |
| **📊 PDF**      | 正式发布，打印存档 | 固定格式，专业外观 |

### 导出步骤

1. 完成股票分析
2. 在结果页面点击导出按钮
3. 选择导出格式
4. 自动下载到本地

## 🎯 功能特色

### 🤖 多智能体协作

- **📈 市场分析师**: 技术指标，趋势分析
- **💰 基本面分析师**: 财务数据，估值模型
- **📰 新闻分析师**: 新闻情绪，事件影响
- **🐂🐻 研究员**: 看涨看跌辩论
- **🎯 交易决策员**: 综合决策制定

### 🧠 智能模型选择

- **DeepSeek V3**: 成本低，工具调用强，中文优化
- **通义千问**: 中文理解好，响应快，阿里云
- **Gemini**: 推理能力强，多模态，Google
- **GPT-4**: 通用能力最强，成本较高

### 📊 全面数据支持

- **🇨🇳 A股**: 实时行情，历史数据，财务指标
- **🇺🇸 美股**: NYSE/NASDAQ，实时数据
- **📰 新闻**: 实时财经新闻，情绪分析
- **💬 社交**: Reddit情绪，市场热度

## 🚨 常见问题

### ❓ 分析失败怎么办？

1. **检查API密钥**: 确认密钥正确且有余额
2. **网络连接**: 确保网络稳定，可访问API
3. **模型切换**: 尝试切换其他LLM模型
4. **查看日志**: 检查控制台错误信息

### ❓ 如何提高分析速度？

1. **选择快速模型**: DeepSeek V3 响应最快
2. **启用缓存**: 使用Redis缓存重复数据
3. **快速模式**: 选择快速分析深度
4. **网络优化**: 确保网络环境稳定

### ❓ Docker部署问题？

```bash
# 检查服务状态
docker-compose ps

# 查看日志
docker logs TradingAgents-web

# 重启服务
docker-compose restart
```

## 📚 下一步

### 🎯 深入使用

1. **📖 阅读文档**: [完整文档](./docs/)
2. **🔧 开发环境**: [开发指南](./docs/DEVELOPMENT_SETUP.md)
3. **🚨 故障排除**: [问题解决](./docs/troubleshooting/)
4. **🏗️ 架构了解**: [技术架构](./docs/architecture/)

### 🤝 参与贡献

- 🐛 [报告问题](https://github.com/hsliuping/TradingAgents-CN/issues)
- 💡 [功能建议](https://github.com/hsliuping/TradingAgents-CN/discussions)
- 🔧 [提交代码](https://github.com/hsliuping/TradingAgents-CN/pulls)
- 📚 [完善文档](https://github.com/hsliuping/TradingAgents-CN/tree/develop/docs)

---

## 🎉 恭喜完成快速开始！

**💡 提示**: 建议先用熟悉的股票代码进行测试，体验完整的分析流程。

**📞 技术支持**: [GitHub Issues](https://github.com/hsliuping/TradingAgents-CN/issues)

---

*最后更新: 2025-07-13 | 版本: cn-0.1.7*
