# TradingAgents-CN 文档中心 (v0.1.11)

欢迎来到 TradingAgents-CN 多智能体金融交易框架的文档中心。本文档适用于中文增强版 v0.1.11，包含多LLM提供商集成、模型选择持久化、完整的A股支持、国产LLM集成、Docker容器化部署和专业报告导出功能。

## 🎯 版本亮点 (v0.1.11)

- 🤖 **多LLM提供商集成** - 4大提供商，60+模型，一站式AI体验
- 💾 **模型选择持久化** - URL参数存储，刷新保持，配置分享
- 🎯 **快速选择按钮** - 5个热门模型一键切换
- 📐 **320px侧边栏优化** - 响应式设计，空间利用更高效
- 🐳 **Docker容器化部署** - 一键启动完整环境
- 📄 **专业报告导出** - Word/PDF/Markdown多格式支持
- 🧠 **DeepSeek V3集成** - 成本低，中文优化，工具调用强
- 🛡️ **系统稳定性提升** - 内存管理优化，错误恢复增强

## 文档结构

### 📋 概览文档
- [项目概述](./overview/project-overview.md) - 项目的基本介绍和目标
- [快速开始](./overview/quick-start.md) - 快速上手指南
- [安装指南](./overview/installation.md) - 详细的安装说明

### 🏗️ 架构文档
- [系统架构](./architecture/system-architecture.md) - 整体系统架构设计 (v0.1.7更新) ✨
- [容器化架构](./architecture/containerization-architecture.md) - Docker容器化架构设计 (v0.1.7新增) ✨
- [数据库架构](./architecture/database-architecture.md) - MongoDB+Redis数据库架构
- [智能体架构](./architecture/agent-architecture.md) - 智能体设计模式
- [数据流架构](./architecture/data-flow-architecture.md) - 数据处理流程
- [图结构设计](./architecture/graph-structure.md) - LangGraph 图结构设计
- [配置优化指南](./architecture/configuration-optimization.md) - 架构优化历程详解

### 🤖 智能体文档
- [分析师团队](./agents/analysts.md) - 各类分析师智能体详解
- [研究员团队](./agents/researchers.md) - 研究员智能体设计
- [交易员](./agents/trader.md) - 交易决策智能体
- [风险管理](./agents/risk-management.md) - 风险管理智能体
- [管理层](./agents/managers.md) - 管理层智能体

### 📊 数据处理
- [数据源集成](./data/data-sources.md) - 支持的数据源和API (含A股支持) ✨
- [Tushare数据接口集成](./data/china_stock-api-integration.md) - A股数据源详解 ✨
- [数据处理流程](./data/data-processing.md) - 数据获取和处理
- [缓存机制](./data/caching.md) - 数据缓存策略

### 🎯 核心功能
- [🤖 多LLM提供商集成](./features/multi-llm-integration.md) - 4大提供商，60+模型支持 (v0.1.11新增) ✨
- [💾 模型选择持久化](./features/model-persistence.md) - URL参数存储，配置保持 (v0.1.11新增) ✨
- [📄 报告导出功能](./features/report-export.md) - Word/PDF/Markdown多格式导出 (v0.1.7) ✨
- [🐳 Docker容器化部署](./features/docker-deployment.md) - 一键部署完整环境 (v0.1.7) ✨

### ⚙️ 配置与部署
- [配置说明](./configuration/config-guide.md) - 配置文件详解 (v0.1.11更新) ✨
- [LLM配置](./configuration/llm-config.md) - 大语言模型配置 (v0.1.11更新) ✨
- [多提供商配置](./configuration/multi-provider-config.md) - 4大LLM提供商配置指南 (v0.1.11新增) ✨
- [OpenRouter配置](./configuration/openrouter-config.md) - OpenRouter 60+模型配置 (v0.1.11新增) ✨
- [Docker配置](./configuration/docker-config.md) - Docker环境配置指南 (v0.1.7) ✨
- [DeepSeek配置](./configuration/deepseek-config.md) - DeepSeek V3模型配置 ✨
- [阿里百炼配置](./configuration/dashscope-config.md) - 阿里百炼模型配置 ✨
- [Google AI配置](./configuration/google-ai-setup.md) - Google AI (Gemini)模型配置指南 ✨
- [Token追踪指南](./configuration/token-tracking-guide.md) - Token使用监控 (v0.1.7更新) ✨
- [数据目录配置](./configuration/data-directory-configuration.md) - 数据存储路径配置
- [Web界面配置](../web/README.md) - Web管理界面使用指南

### 🔧 开发指南
- [开发环境搭建](./development/dev-setup.md) - 开发环境配置
- [代码结构](./development/code-structure.md) - 代码组织结构
- [扩展开发](./development/extending.md) - 如何扩展框架
- [测试指南](./development/testing.md) - 测试策略和方法

### 📋 版本发布 (v0.1.7更新)
- [更新日志](./releases/CHANGELOG.md) - 所有版本更新记录 ✨
- [v0.1.7发布说明](./releases/v0.1.7-release-notes.md) - 最新版本详细说明 ✨
- [版本对比](./releases/version-comparison.md) - 各版本功能对比 ✨
- [升级指南](./releases/upgrade-guide.md) - 版本升级详细指南 ✨

### 📚 API参考
- [核心API](./api/core-api.md) - 核心类和方法
- [智能体API](./api/agents-api.md) - 智能体接口
- [数据API](./api/data-api.md) - 数据处理接口

### 🌐 使用指南
- [多LLM提供商使用指南](./guides/multi-llm-usage-guide.md) - 4大提供商使用方法 (v0.1.11新增) ✨
- [模型选择持久化指南](./guides/model-persistence-guide.md) - 配置保存和分享方法 (v0.1.11新增) ✨
- [OpenRouter使用指南](./guides/openrouter-usage-guide.md) - 60+模型使用指南 (v0.1.11新增) ✨
- [Web界面指南](./usage/web-interface-guide.md) - Web界面详细使用指南 (v0.1.11更新) ✨
- [投资分析指南](./usage/investment_analysis_guide.md) - 投资分析完整流程
- [A股分析指南](./guides/a-share-analysis-guide.md) - A股市场分析专项指南 (v0.1.7) ✨
- [配置管理指南](./guides/config-management-guide.md) - 配置管理和成本统计使用方法 (v0.1.7) ✨
- [Docker部署指南](./guides/docker-deployment-guide.md) - Docker容器化部署详细指南 (v0.1.7) ✨
- [报告导出指南](./guides/report-export-guide.md) - 专业报告导出使用指南 (v0.1.7) ✨
- [DeepSeek使用指南](./guides/deepseek-usage-guide.md) - DeepSeek V3模型使用指南 (v0.1.7) ✨

### 💡 示例和教程
- [基础示例](./examples/basic-examples.md) - 基本使用示例
- [高级示例](./examples/advanced-examples.md) - 高级功能示例
- [自定义智能体](./examples/custom-agents.md) - 创建自定义智能体

### ❓ 常见问题
- [FAQ](./faq/faq.md) - 常见问题解答
- [故障排除](./faq/troubleshooting.md) - 问题诊断和解决

### 📋 版本历史
- [📄 v0.1.11 发布说明](./releases/v0.1.11-release-notes.md) - 多LLM提供商集成与模型选择持久化 ✨
- [📄 v0.1.11 更新日志](./releases/CHANGELOG_v0.1.11.md) - 详细技术更新记录 ✨
- [📄 完整更新日志](./releases/CHANGELOG.md) - 所有版本历史记录
- [📄 升级指南](./releases/upgrade-guide.md) - 版本升级操作指南
- [📄 版本对比](./releases/version-comparison.md) - 各版本功能对比

## 贡献指南

如果您想为文档做出贡献，请参考 [贡献指南](../CONTRIBUTING.md)。

## 联系我们

- GitHub: [TauricResearch/TradingAgents](https://github.com/TauricResearch/TradingAgents)
- Discord: [TradingResearch](https://discord.com/invite/hk9PGKShPK)
- 微信: TauricResearch
- Twitter: [@TauricResearch](https://x.com/TauricResearch)
