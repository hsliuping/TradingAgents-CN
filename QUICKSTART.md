# 🚀 TradingAgents-CN Quick Start Guide

> 📋 **Version**: cn-0.1.10 | **Last Updated**: 2025-07-18
> 🎯 **Goal**: Deploy and start stock analysis in 5 minutes

## 🎯 Choose Deployment Method

### 🐳 Method 1: Docker Deployment (Recommended)

**Best for**: Production, quick experience, zero-configuration startup

```bash
# 1. Clone the project
git clone https://github.com/hsliuping/TradingAgents-CN.git
cd TradingAgents-CN

# 2. Configure environment variables
cp .env.example .env
# Edit the .env file and fill in your API keys

# 3. Build and start services
docker-compose up -d --build

# Note: The first run will automatically build the Docker image and may take 5-10 minutes
# The build process includes:
# - Downloading base images and dependencies (~800MB)
# - Installing system tools (pandoc, wkhtmltopdf, etc.)
# - Installing Python dependencies
# - Configuring the runtime environment

# 4. Access the application
# Web interface: http://localhost:8501
# Database management: http://localhost:8081
# Cache management: http://localhost:8082
```

### 🔧 Step-by-Step Build (Optional)

If you prefer to build in steps, you can build the image separately:

```bash
# Method A: Step-by-step build
# 1. Build the Docker image first
docker build -t tradingagents-cn:latest .

# 2. Then start all services
docker-compose up -d

# Method B: One-click build and start (recommended)
docker-compose up -d --build
```

### 💻 Method 2: Local Deployment

**Best for**: Development, custom configuration, offline use

```bash
# 1. Clone the project
git clone https://github.com/hsliuping/TradingAgents-CN.git
cd TradingAgents-CN

# 2. Create a virtual environment
python -m venv env
env\Scripts\activate  # Windows
# source env/bin/activate  # Linux/macOS

# 3. Install dependencies
pip install -r requirements.txt

# 4. Install the project into the virtual environment (important!)
pip install -e .

# 5. Configure environment variables
cp .env.example .env
# Edit the .env file

# 6. Start the application
# Method 1: Use the simplified startup script (recommended)
python start_web.py

# Method 2: Use the project startup script
python web/run_web.py

# Method 3: Use streamlit directly (project must be installed first)
streamlit run web/app.py
```

## 🔧 Environment Configuration

### 📋 Required Configuration

Create a `.env` file and configure the following:

```bash
# === LLM Model Configuration (choose at least one) ===

# 🇨🇳 DeepSeek (Recommended - low cost, optimized for Chinese)
DEEPSEEK_API_KEY=sk-your_deepseek_api_key_here
DEEPSEEK_ENABLED=true

# 🇨🇳 Alibaba Qwen (Recommended - good Chinese understanding)
QWEN_API_KEY=your_qwen_api_key
QWEN_ENABLED=true

# 🌍 Google AI Gemini (Recommended - strong reasoning)
GOOGLE_API_KEY=your_google_api_key
GOOGLE_ENABLED=true

# 🤖 OpenAI (Optional - strong general capability, higher cost)
OPENAI_API_KEY=your_openai_api_key
OPENAI_ENABLED=true
```

### 🔑 How to Get API Keys

| Provider      | Get Key At                                              | Features                | Cost      |
| ------------- | ------------------------------------------------------- | ----------------------- | --------- |
| **DeepSeek**  | [platform.deepseek.com](https://platform.deepseek.com/) | Tool use, Chinese opt.  | 💰 Very Low |
| **Alibaba**   | [dashscope.aliyun.com](https://dashscope.aliyun.com/)   | Chinese, fast response  | 💰 Low     |
| **Google AI** | [aistudio.google.com](https://aistudio.google.com/)     | Reasoning, multimodal   | 💰💰 Medium |
| **OpenAI**    | [platform.openai.com](https://platform.openai.com/)     | General capability      | 💰💰💰 High  |

### 📊 Optional Configuration

```bash
# === Data Source Configuration (optional) ===
TUSHARE_TOKEN=your_tushare_token          # Enhanced A-share data
FINNHUB_API_KEY=your_finnhub_key          # US stock data

# === Database Configuration (Docker auto-configures) ===
MONGODB_URL=mongodb://mongodb:27017/tradingagents  # Docker environment
REDIS_URL=redis://redis:6379                       # Docker environment

# === Export Feature Configuration ===
EXPORT_ENABLED=true                       # Enable report export
EXPORT_DEFAULT_FORMAT=word,pdf            # Default export formats
```

## 🚀 Getting Started

### 1️⃣ Access the Web Interface

```bash
# Open your browser and visit
http://localhost:8501
```

### 2️⃣ Configure Analysis Parameters

- **🧠 Choose LLM Model**: DeepSeek V3 / Qwen / Gemini
- **📊 Choose Analysis Depth**: Quick / Standard / In-depth
- **🎯 Choose Analysts**: Market Analysis / Fundamental Analysis / News Analysis

### 3️⃣ Enter Stock Codes

```bash
# 🇨🇳 A-share examples
000001  # Ping An Bank
600519  # Kweichow Moutai
000858  # Wuliangye

# 🇺🇸 US stock examples  
AAPL    # Apple
TSLA    # Tesla
MSFT    # Microsoft
```

### 4️⃣ Start Analysis

1. Click the "🚀 Start Analysis" button
2. **📊 Real-Time Progress Tracking**: Watch analysis progress and current step
   - Shows elapsed and estimated remaining time
   - Real-time updates of analysis status and step descriptions
   - Supports manual and auto-refresh
3. **⏰ Analysis Complete**: Wait for analysis to finish (2-10 minutes, depending on depth)
   - Shows accurate total time
   - Automatically displays "🎉 Analysis Complete" status
4. **📋 View Report**: Click the "📊 View Analysis Report" button
   - Instantly shows detailed investment advice and analysis report
   - Supports repeated viewing and recovery after page refresh
5. **📄 Export Report**: Option to export as Word/PDF/Markdown

### 🆕 v0.1.10 New Feature Highlights

#### 🚀 Real-Time Progress Display
- **Async Progress Tracking**: See analysis progress in real time, no more waiting in the dark
- **Intelligent Step Recognition**: Automatically identifies current analysis step and status
- **Accurate Time Calculation**: Shows real analysis time, not affected by viewing time

#### 📊 Intelligent Session Management
- **State Persistence**: Restore analysis state after page refresh
- **Automatic Fallback**: Switches to file storage if Redis is unavailable
- **User Experience**: More stable and reliable session management

#### 🎨 Interface Optimization
- **View Report Button**: One-click report viewing after analysis
- **Removed Duplicate Buttons**: Cleaner interface
- **Responsive Design**: Improved adaptation for mobile and different screens

## 📄 Report Export Feature

### Supported Formats

| Format         | Use Case             | Features                |
| -------------- | -------------------- | ----------------------- |
| **📝 Markdown**| Online viewing, VCS  | Lightweight, editable   |
| **📄 Word**    | Business reports     | Professional, editable  |
| **📊 PDF**     | Official, archiving  | Fixed format, pro look  |

### Export Steps

1. Complete stock analysis
2. Click the export button on the results page
3. Choose export format
4. File is automatically downloaded locally

## 🎯 Feature Highlights

### 🤖 Multi-Agent Collaboration

- **📈 Market Analyst**: Technical indicators, trend analysis
- **💰 Fundamental Analyst**: Financial data, valuation models
- **📰 News Analyst**: News sentiment, event impact
- **🐂🐻 Researchers**: Bullish/Bearish debate
- **🎯 Trader**: Integrated decision making

### 🧠 Intelligent Model Selection

- **DeepSeek V3**: Low cost, strong tool use, Chinese optimized
- **Qwen**: Good Chinese understanding, fast, Alibaba Cloud
- **Gemini**: Strong reasoning, multimodal, Google
- **GPT-4**: Best general capability, higher cost

### 📊 Comprehensive Data Support

- **🇨🇳 A-shares**: Real-time quotes, historical data, financial indicators
- **🇺🇸 US stocks**: NYSE/NASDAQ, real-time data
- **📰 News**: Real-time financial news, sentiment analysis
- **💬 Social**: Reddit sentiment, market heat

## 🚨 FAQ

### ❓ What if analysis fails?

1. **Check API keys**: Make sure keys are correct and have balance
2. **Network connection**: Ensure stable network and API access
3. **Switch models**: Try another LLM model
4. **Check logs**: Look for errors in the console

### ❓ How to speed up analysis?

1. **Choose fast model**: DeepSeek V3 is fastest
2. **Enable cache**: Use Redis to cache repeated data
3. **Quick mode**: Select quick analysis depth
4. **Network optimization**: Ensure stable network

### ❓ Docker deployment issues?

```bash
# Check service status
docker-compose ps

# View logs
docker logs TradingAgents-web

# Restart services
docker-compose restart
```

## 📚 Next Steps

### 🎯 Go Deeper

1. **📖 Read the docs**: [Full Documentation](./docs/)
2. **🔧 Dev environment**: [Development Guide](./docs/DEVELOPMENT_SETUP.md)
3. **🚨 Troubleshooting**: [Problem Solving](./docs/troubleshooting/)
4. **🏗️ Architecture**: [Technical Architecture](./docs/architecture/)

### 🤝 Contribute

- 🐛 [Report Issues](https://github.com/hsliuping/TradingAgents-CN/issues)
- 💡 [Feature Suggestions](https://github.com/hsliuping/TradingAgents-CN/discussions)
- 🔧 [Submit Code](https://github.com/hsliuping/TradingAgents-CN/pulls)
- 📚 [Improve Docs](https://github.com/hsliuping/TradingAgents-CN/tree/develop/docs)

---

## 🎉 Congratulations, Quick Start Complete!

**💡 Tip**: Try with familiar stock codes first to experience the full analysis flow.

**📞 Tech Support**: [GitHub Issues](https://github.com/hsliuping/TradingAgents-CN/issues)

---

*Last updated: 2025-07-13 | Version: cn-0.1.7*
