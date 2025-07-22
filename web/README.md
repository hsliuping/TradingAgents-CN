# TradingAgents-CN Web management interface

Based on Streamlit, this TradingAgents Web management interface provides an intuitive stock analysis experience. It supports multiple LLM providers and AI models, allowing you to easily perform professional stock investment analysis.

## ✨ Features

### 🌐 Modern Web Interface
- 🎯 Intuitive stock analysis interface
- 📊 Real-time analysis progress display  
- 📱 Responsive design, supports mobile devices
- 🎨 Professional UI design and user experience

### 🤖 Multiple LLM Provider Support
- **Ali Baiyan**: qwen-turbo, qwen-plus-latest, qwen-max
- **Google AI**: gemini-2.0-flash, gemini-1.5-pro, gemini-1.5-flash
- **Smart switching**: One-click switch between different AI models
- **Hybrid embedding**: Google AI inference + Ali Baiyan embedding

### 📈 Professional Analysis Features
- **Multiple analysts collaboration**: Market technology, fundamental, news, social media analysts
- **Visual results**: Professional analysis reports and charts
- **Configuration information**: Display used models and analysts
- **Risk assessment**: Multi-dimensional risk analysis and prompts

## 🚀 Quick Start

### 1. Environment Preparation

```bash
# Activate virtual environment
.\env\Scripts\activate  # Windows
source env/bin/activate  # Linux/macOS

# Ensure dependencies are installed
pip install -r requirements.txt

# Install project into virtual environment (important!)
pip install -e .

# Configure API keys
cp .env.example .env
# Edit .env file to add your API keys
```

### 2. Start Web Interface

```bash
# Method 1: Use simplified startup script (recommended)
python start_web.py

# Method 2: Use project startup script
python web/run_web.py

# Method 3: Use shortcut script
# Windows
start_web.bat

# Linux/macOS
./start_web.sh

# Method 4: Direct startup (requires project installation)
python -m streamlit run web/app.py
```

### 3. Access Interface

Open `http://localhost:8501` in your browser.

## 📋 Usage Guide

### 🔧 Configure Analysis Parameters

#### Left sidebar configuration:

1. **🔑 API Key Status**
   - View the status of configured API keys
   - Green ✅ indicates configured, red ❌ indicates not configured

2. **🧠 AI Model Configuration**
   - **Select LLM Provider**: Ali Baiyan or Google AI
   - **Select Specific Model**: 
     - Ali Baiyan: qwen-turbo(fast) / qwen-plus-latest(balanced) / qwen-max(strongest)
     - Google AI: gemini-2.0-flash(recommended) / gemini-1.5-pro(strong) / gemini-1.5-flash(fast)

3. **⚙️ Advanced Settings**
   - **Enable memory function**: Allow AI to learn and remember analysis history
   - **Debug mode**: Display detailed analysis process information
   - **Maximum output length**: Control the detailedness of AI responses

#### Main interface configuration:

1. **📊 Stock Analysis Configuration**
   - **Stock Code**: Enter the stock code you want to analyze (e.g., AAPL, TSLA)
   - **Analysis Date**: Select the base date for analysis
   - **Analyst Selection**: Select AI analysts to participate in analysis
     - 📈 Market Technology Analyst - Technical indicators and chart analysis
     - 💰 Fundamental Analyst - Financial data and company fundamentals
     - 📰 News Analyst - News event impact analysis
     - 💭 Social Media Analyst - Social media sentiment analysis
   - **Research Depth**: Set the level of analysis (1-5)

### 🎯 Start Analysis

1. **Click "Start Analysis" button**
2. **Observe real-time progress**:
   - �� Configure analysis parameters
   - 🔍 Check environment variables
   - 🚀 Initialize analysis engine
   - 📊 Execute stock analysis
   - ✅ Analysis complete

3. **Wait for analysis to complete** (usually 2-5 minutes)

### 📊 View Analysis Results

#### 🎯 Investment Decision Summary
- **Investment Advice**: BUY/SELL/HOLD
- **Confidence**: AI's confidence in the advice
- **Risk Score**: Investment risk level
- **Target Price**: Expected price target

#### 📋 Analysis Configuration Information
- **LLM Provider**: AI service used
- **AI Model**: Specific model name used
- **Number of Analysts**: AI analysts participating in analysis
- **Analyst List**: Specific analyst types

#### 📈 Detailed Analysis Report
- **Market Technical Analysis**: Technical indicators, chart patterns, trend analysis
- **Fundamental Analysis**: Financial health, valuation analysis, industry comparison
- **News Analysis**: Latest news events affecting stock price
- **Social Media Analysis**: Investor sentiment and discussion heat
- **Risk Assessment**: Multi-dimensional risk analysis and suggestions

## 🏗️ Technical Architecture

### 📁 Directory Structure

```
web/
├── app.py                 # Main application entry
├── run_web.py            # Startup script
├── components/           # UI components
│   ├── __init__.py
│   ├── sidebar.py        # Left configuration sidebar
│   ├── analysis_form.py  # Analysis form
│   ├── results_display.py # Result display
│   └── header.py         # Page header
├── utils/                # Utility functions
│   ├── __init__.py
│   ├── analysis_runner.py # Analysis executor
│   ├── api_checker.py    # API check
│   └── progress_tracker.py # Progress tracking
├── static/               # Static resources
└── README.md            # This file
```

### 🔄 Data Flow

```
User input → Parameter validation → API check → Analysis execution → Result display
    ↓           ↓           ↓           ↓           ↓
  Form component → Configuration validation → Key check → Progress tracking → Result component
```

### 🧩 组件说明

- **sidebar.py**: Left configuration sidebar, includes API status, model selection, advanced settings
- **analysis_form.py**: Main analysis form, stock code, analyst selection, etc.
- **results_display.py**: Result display component, includes decision summary, detailed report, etc.
- **analysis_runner.py**: Core analysis executor, supports multiple LLM providers
- **progress_tracker.py**: Real-time progress tracking, provides user feedback

## ⚙️ Configuration Instructions

### 🔑 Environment Variable Configuration

Configure in the `.env` file in the project root:

```env
# Ali Baiyan API (recommended, domestic model)
DASHSCOPE_API_KEY=sk-your_dashscope_key

# Google AI API (optional, supports Gemini model)
GOOGLE_API_KEY=your_google_api_key

# Financial data API (optional)
FINNHUB_API_KEY=your_finnhub_key

# Reddit API (optional, for social media analysis)
REDDIT_CLIENT_ID=your_reddit_client_id
REDDIT_CLIENT_SECRET=your_reddit_client_secret
REDDIT_USER_AGENT=TradingAgents-CN/1.0
```

### 🤖 Model Configuration Instructions

#### Ali Baiyan Models
- **qwen-turbo**: Fast response, suitable for simple analysis
- **qwen-plus-latest**: Balanced performance, recommended for daily use
- **qwen-max**: Strongest performance, suitable for complex analysis

#### Google AI Models  
- **gemini-2.0-flash**: Latest model, recommended for use
- **gemini-1.5-pro**: Strong performance, suitable for deep analysis
- **gemini-1.5-flash**: Fast response, suitable for simple analysis

## 🔧 Troubleshooting

### ❌ Common Issues

#### 1. Page cannot load
```bash
# Check Python environment
python --version  # Requires 3.10+

# Check dependency installation
pip list | grep streamlit

# Check port occupancy
netstat -an | grep 8501
```

#### 2. API Key Issues
- ✅ Check if `.env` file exists
- ✅ Confirm correct API key format
- ✅ Verify API key validity and balance

#### 3. Analysis Failed
- ✅ Check network connection
- ✅ Confirm valid stock code
- ✅ View browser console error messages

#### 4. Result display anomalies
- ✅ Refresh page and try again
- ✅ Clear browser cache
- ✅ Check if model configuration is correct

### �� Debug Mode

Enable detailed logging to view issues:

```bash
# Enable Streamlit debug mode
streamlit run web/app.py --logger.level=debug

# Enable application debug mode
# Check "Debug Mode" in the left sidebar
```

### 📞 Get Help

If you encounter issues:

1. 📖 Refer to [Complete Documentation](../docs/)
2. 🧪 Run [Test Program](../tests/test_web_interface.py)
3. 💬 Submit [GitHub Issue](https://github.com/hsliuping/TradingAgents-CN/issues)

## 🚀 Development Guide

### Add New Components

1. Create a new file in the `components/` directory
2. Implement the component function
3. Import and use in `app.py`

```python
# components/new_component.py
import streamlit as st

def render_new_component():
    """Render new component"""
    st.subheader("New Component")
    # Component logic
    return component_data

# app.py
from components.new_component import render_new_component

# Use in main application
data = render_new_component()
```

### Custom Styles

Add CSS files to the `static/` directory:

```css
/* static/custom.css */
.custom-style {
    background-color: #f0f0f0;
    padding: 10px;
    border-radius: 5px;
}
```

Then reference them in components:

```python
# Load CSS in components
st.markdown('<link rel="stylesheet" href="static/custom.css">', unsafe_allow_html=True)
```

## 📄 License

This project follows the Apache 2.0 license. See [LICENSE](../LICENSE) file.

## 🙏 Acknowledgments

Thank you [TauricResearch/TradingAgents](https://github.com/TauricResearch/TradingAgents) for providing the excellent framework foundation.
