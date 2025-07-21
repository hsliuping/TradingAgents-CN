# TradingAgents-CN Web管理界面

基于Streamlit构建的TradingAgents Web管理界面，提供直观的股票分析体验。支持多种LLM提供商和AI模型，让您轻松进行专业的股票投资分析。

## ✨ 功能特性

### 🌐 现代化Web界面
- 🎯 直观的股票分析界面
- 📊 实时分析进度显示  
- 📱 响应式设计，支持移动端
- 🎨 专业的UI设计和用户体验

### 🤖 多LLM提供商支持
- **阿里百炼**: qwen-turbo, qwen-plus-latest, qwen-max
- **Google AI**: gemini-2.0-flash, gemini-1.5-pro, gemini-1.5-flash
- **智能切换**: 一键切换不同的AI模型
- **混合嵌入**: Google AI推理 + 阿里百炼嵌入

### 📈 专业分析功能
- **多分析师协作**: 市场技术、基本面、新闻、社交媒体分析师
- **可视化结果**: 专业的分析报告和图表展示
- **配置信息**: 显示使用的模型和分析师信息
- **风险评估**: 多维度风险分析和提示

## 🚀 快速开始

### 1. 环境准备

```bash
# 激活虚拟环境
.\env\Scripts\activate  # Windows
source env/bin/activate  # Linux/macOS

# 确保已安装依赖
pip install -r requirements.txt

# 安装项目到虚拟环境（重要！）
pip install -e .

# 配置API密钥
cp .env.example .env
# 编辑.env文件，添加您的API密钥
```

### 2. 启动Web界面

```bash
# 方法1: 使用简化启动脚本（推荐）
python start_web.py

# 方法2: 使用项目启动脚本
python web/run_web.py

# 方法3: 使用快捷脚本
# Windows
start_web.bat

# Linux/macOS
./start_web.sh

# 方法4: 直接启动（需要先安装项目）
python -m streamlit run web/app.py
```

### 3. 访问界面

在浏览器中打开 `http://localhost:8501`

## 📋 使用指南

### 🔧 配置分析参数

#### 左侧边栏配置：

1. **🔑 API密钥状态**
   - 查看已配置的API密钥状态
   - 绿色✅表示已配置，红色❌表示未配置

2. **🧠 AI模型配置**
   - **选择LLM提供商**: 阿里百炼 或 Google AI
   - **选择具体模型**: 
     - 阿里百炼: qwen-turbo(快速) / qwen-plus-latest(平衡) / qwen-max(最强)
     - Google AI: gemini-2.0-flash(推荐) / gemini-1.5-pro(强大) / gemini-1.5-flash(快速)

3. **⚙️ 高级设置**
   - **启用记忆功能**: 让AI学习和记住分析历史
   - **调试模式**: 显示详细的分析过程信息
   - **最大输出长度**: 控制AI回复的详细程度

#### 主界面配置：

1. **📊 股票分析配置**
   - **股票代码**: 输入要分析的股票代码（如AAPL、TSLA）
   - **分析日期**: 选择分析的基准日期
   - **分析师选择**: 选择参与分析的AI分析师
     - 📈 市场技术分析师 - 技术指标和图表分析
     - 💰 基本面分析师 - 财务数据和公司基本面
     - 📰 新闻分析师 - 新闻事件影响分析
     - 💭 社交媒体分析师 - 社交媒体情绪分析
   - **研究深度**: 设置分析的详细程度（1-5级）

### 🎯 开始分析

1. **点击"开始分析"按钮**
2. **观察实时进度**:
   - 📋 配置分析参数
   - 🔍 检查环境变量
   - 🚀 初始化分析引擎
   - 📊 执行股票分析
   - ✅ 分析完成

3. **等待分析完成** (通常需要2-5分钟)

### 📊 查看分析结果

#### 🎯 投资决策摘要
- **投资建议**: BUY/SELL/HOLD
- **置信度**: AI对建议的信心程度
- **风险评分**: 投资风险等级
- **目标价格**: 预期价格目标

#### 📋 分析配置信息
- **LLM提供商**: 使用的AI服务商
- **AI模型**: 具体使用的模型名称
- **分析师数量**: 参与分析的AI分析师
- **分析师列表**: 具体的分析师类型

#### 📈 详细分析报告
- **市场技术分析**: 技术指标、图表模式、趋势分析
- **基本面分析**: 财务健康度、估值分析、行业对比
- **新闻分析**: 最新新闻事件对股价的影响
- **社交媒体分析**: 投资者情绪和讨论热度
- **风险评估**: 多维度风险分析和建议

## 🏗️ 技术架构

### 📁 目录结构

```
web/
├── app.py                 # 主应用入口
├── run_web.py            # 启动脚本
├── components/           # UI组件
│   ├── __init__.py
│   ├── sidebar.py        # 左侧配置栏
│   ├── analysis_form.py  # 分析表单
│   ├── results_display.py # 结果展示
│   └── header.py         # 页面头部
├── utils/                # 工具函数
│   ├── __init__.py
│   ├── analysis_runner.py # 分析执行器
│   ├── api_checker.py    # API检查
│   └── progress_tracker.py # 进度跟踪
├── static/               # 静态资源
└── README.md            # 本文件
```

### 🔄 数据流程

```
用户输入 → 参数验证 → API检查 → 分析执行 → 结果展示
    ↓           ↓           ↓           ↓           ↓
  表单组件   → 配置验证   → 密钥检查   → 进度跟踪   → 结果组件
```

### 🧩 组件说明

- **sidebar.py**: 左侧配置栏，包含API状态、模型选择、高级设置
- **analysis_form.py**: 主分析表单，股票代码、分析师选择等
- **results_display.py**: 结果展示组件，包含决策摘要、详细报告等
- **analysis_runner.py**: 核心分析执行器，支持多LLM提供商
- **progress_tracker.py**: 实时进度跟踪，提供用户反馈

## ⚙️ 配置说明

### 🔑 环境变量配置

在项目根目录的 `.env` 文件中配置：

```env
# 阿里百炼API（推荐，国产模型）
DASHSCOPE_API_KEY=sk-your_dashscope_key

# Google AI API（可选，支持Gemini模型）
GOOGLE_API_KEY=your_google_api_key

# 金融数据API（可选）
FINNHUB_API_KEY=your_finnhub_key

# Reddit API（可选，用于社交媒体分析）
REDDIT_CLIENT_ID=your_reddit_client_id
REDDIT_CLIENT_SECRET=your_reddit_client_secret
REDDIT_USER_AGENT=TradingAgents-CN/1.0
```

### 🤖 模型配置说明

#### 阿里百炼模型
- **qwen-turbo**: 快速响应，适合简单分析
- **qwen-plus-latest**: 平衡性能，推荐日常使用
- **qwen-max**: 最强性能，适合复杂分析

#### Google AI模型  
- **gemini-2.0-flash**: 最新模型，推荐使用
- **gemini-1.5-pro**: 强大性能，适合深度分析
- **gemini-1.5-flash**: 快速响应，适合简单分析

## 🔧 故障排除

### ❌ 常见问题

#### 1. 页面无法加载
```bash
# 检查Python环境
python --version  # 需要3.10+

# 检查依赖安装
pip list | grep streamlit

# 检查端口占用
netstat -an | grep 8501
```

#### 2. API密钥问题
- ✅ 检查 `.env` 文件是否存在
- ✅ 确认API密钥格式正确
- ✅ 验证API密钥有效性和余额

#### 3. 分析失败
- ✅ 检查网络连接
- ✅ 确认股票代码有效
- ✅ 查看浏览器控制台错误信息

#### 4. 结果显示异常
- ✅ 刷新页面重试
- ✅ 清除浏览器缓存
- ✅ 检查模型配置是否正确

### 🐛 调试模式

启用详细日志查看问题：

```bash
# 启用Streamlit调试模式
streamlit run web/app.py --logger.level=debug

# 启用应用调试模式
# 在左侧边栏勾选"调试模式"
```

### 📞 获取帮助

如果遇到问题：

1. 📖 查看 [完整文档](../docs/)
2. 🧪 运行 [测试程序](../tests/test_web_interface.py)
3. 💬 提交 [GitHub Issue](https://github.com/hsliuping/TradingAgents-CN/issues)

## 🚀 开发指南

### 添加新组件

1. 在 `components/` 目录创建新文件
2. 实现组件函数
3. 在 `app.py` 中导入和使用

```python
# components/new_component.py
import streamlit as st

def render_new_component():
    """渲染新组件"""
    st.subheader("新组件")
    # 组件逻辑
    return component_data

# app.py
from components.new_component import render_new_component

# 在主应用中使用
data = render_new_component()
```

### 自定义样式

在 `static/` 目录中添加CSS文件：

```css
/* static/custom.css */
.custom-style {
    background-color: #f0f0f0;
    padding: 10px;
    border-radius: 5px;
}
```

然后在组件中引用：

```python
# 在组件中加载CSS
st.markdown('<link rel="stylesheet" href="static/custom.css">', unsafe_allow_html=True)
```

## 📄 许可证

本项目遵循Apache 2.0许可证。详见 [LICENSE](../LICENSE) 文件。

## 🙏 致谢

感谢 [TauricResearch/TradingAgents](https://github.com/TauricResearch/TradingAgents) 原始项目提供的优秀框架基础。
