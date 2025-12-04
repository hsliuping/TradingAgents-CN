---
name: 🐛 Bug报告 / Bug Report
about: 报告一个问题帮助我们改进 / Report a bug to help us improve
title: '[BUG] '
labels: ['bug', 'needs-triage']
assignees: ''
---

## 🐛 问题描述 / Bug Description

**问题类型 / Issue Type:**
- [ ] 🚀 启动/安装问题 / Startup/Installation Issue
- [ ] 🌐 Web界面问题 / Web Interface Issue
- [ ] 💻 CLI工具问题 / CLI Tool Issue
- [ ] 🤖 LLM调用问题 / LLM API Issue
- [ ] 📊 数据获取问题 / Data Acquisition Issue
- [ ] 🐳 Docker部署问题 / Docker Deployment Issue
- [ ] ⚙️ 配置问题 / Configuration Issue
- [ ] 🔄 功能异常 / Feature Malfunction
- [ ] 🐌 性能问题 / Performance Issue
- [ ] 其他 / Other: ___________

**简要描述问题 / Brief description:**
清晰简洁地描述遇到的问题。

**期望行为 / Expected behavior:**
描述您期望发生的行为。

**实际行为 / Actual behavior:**
描述实际发生的行为。

## 🔄 复现步骤 / Steps to Reproduce

请提供详细的复现步骤：

1. 进入 '...'
2. 点击 '....'
3. 滚动到 '....'
4. 看到错误

## 📱 环境信息 / Environment

**系统信息 / System Info:**
- 操作系统 / OS: [例如 Windows 11, macOS 13, Ubuntu 22.04]
- Python版本 / Python Version: [例如 3.10.0]
- 项目版本 / Project Version: [例如 v0.1.6]

**安装方式 / Installation Method:**
- [ ] 本地安装 / Local Installation
- [ ] Docker部署 / Docker Deployment
- [ ] 其他 / Other: ___________

**依赖版本 / Dependencies:**
```bash
# 请运行以下命令并粘贴结果 / Please run the following command and paste the result
pip list | grep -E "(streamlit|langchain|openai|requests|tushare|akshare|baostock)"
```

**浏览器信息 / Browser Info (仅Web界面问题):**
- 浏览器 / Browser: [例如 Chrome 120, Firefox 121, Safari 17]
- 浏览器版本 / Version:
- 是否使用无痕模式 / Incognito mode: [ ] 是 / Yes [ ] 否 / No

## 📊 配置信息 / Configuration

**API配置 / API Configuration:**
- [ ] 已配置Tushare Token
- [ ] 已配置DeepSeek API Key
- [ ] 已配置DashScope API Key
- [ ] 已配置FinnHub API Key
- [ ] 已配置数据库 / Database configured

**数据源 / Data Sources:**
- 中国股票数据源 / Chinese Stock Source: [tushare/akshare/baostock]
- 美股数据源 / US Stock Source: [finnhub/yfinance]

## 📝 错误日志 / Error Logs

**控制台错误 / Console Errors:**
```
请粘贴完整的错误信息和堆栈跟踪
Please paste the complete error message and stack trace
```

**日志文件 / Log Files:**
```bash
# 如果启用了日志记录，请提供相关日志
# If logging is enabled, please provide relevant logs

# Web应用日志 / Web app logs
tail -n 50 logs/tradingagents.log

# Docker日志 / Docker logs
docker-compose logs web
```

**网络请求错误 / Network Request Errors:**
如果是API调用问题，请提供：
- API响应状态码 / API response status code
- 错误响应内容 / Error response content
- 请求参数（隐藏敏感信息）/ Request parameters (hide sensitive info)

## 📸 截图 / Screenshots

如果适用，请添加截图来帮助解释问题。
If applicable, add screenshots to help explain your problem.

## 🔍 额外信息 / Additional Context

添加任何其他有关问题的上下文信息。
Add any other context about the problem here.

## ✅ 检查清单 / Checklist

请确认您已经：
- [ ] 搜索了现有的issues，确认这不是重复问题
- [ ] 使用了最新版本的代码
- [ ] 提供了完整的错误信息
- [ ] 包含了复现步骤
- [ ] 填写了环境信息

---

**感谢您的反馈！我们会尽快处理这个问题。**
**Thank you for your feedback! We will address this issue as soon as possible.**
