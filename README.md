# TradingAgents 中文增强版

[![License](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)
[![Python](https://img.shields.io/badge/Python-3.10%2B-blue.svg)](https://www.python.org/)
[![Version](https://img.shields.io/badge/Version-cn--0.1.7-green.svg)](./VERSION)
[![Documentation](https://img.shields.io/badge/docs-中文文档-green.svg)](./docs/)
[![Original](https://img.shields.io/badge/基于-TauricResearch/TradingAgents-orange.svg)](https://github.com/TauricResearch/TradingAgents)

> 🎉 **版本**: 当前版本为 cn-0.1.7 版，已具备Docker容器化部署、专业报告导出、DeepSeek V3集成、完整的A股数据支持等核心功能。
>
> 📝 **版本说明**: 为避免与源项目版本冲突，中文增强版使用 `cn-` 前缀的独立版本体系。

基于多智能体大语言模型的中文金融交易决策框架。本项目基于 [TauricResearch/TradingAgents](https://github.com/TauricResearch/TradingAgents) 开发，专为中文用户提供Docker容器化部署、专业报告导出、DeepSeek V3成本优化、完整的A股支持和本地化体验。

## 🙏 致敬与感谢

### 向源项目开发者致敬

我们向 [Tauric Research](https://github.com/TauricResearch) 团队及 [TradingAgents](https://github.com/TauricResearch/TradingAgents) 项目的所有贡献者致以最诚挚的敬意和感谢！

- **🎯 创新理念**: 感谢您们创造了这个革命性的多智能体交易框架
- **💎 珍贵源码**: 感谢您们开源的每一行代码，它们凝聚着无数的智慧和心血
- **🏗️ 优秀架构**: 感谢您们设计了如此优雅和可扩展的系统架构
- **🔬 前沿技术**: 感谢您们将最新的AI技术应用到金融交易领域
- **🔄 持续贡献**: 感谢您们持续的维护、更新和改进工作
- **🌍 开源精神**: 感谢您们选择Apache 2.0协议，给予开发者最大的自由

> 💝 **特别说明**: 虽然Apache 2.0协议赋予了我们使用源码的权利，但我们深知每一行代码的珍贵价值。我们将永远铭记并感谢您们的无私贡献。

### 我们的使命

本项目的创建初衷是为了**更好地在中国推广TradingAgents**，让更多中文用户能够：

- **🇨🇳 无障碍使用**: 提供完整的中文文档和界面，降低使用门槛
- **🧠 本土化适配**: 集成国产大模型，适应国内网络环境
- **📊 市场对接**: 支持A股、港股等中国金融市场
- **🎓 学习交流**: 为中文社区提供学习和交流平台
- **🚀 技术推广**: 推动AI在中国金融科技领域的应用

我们始终尊重源项目的知识产权，遵循开源协议，并致力于将改进和创新反馈给开源社区。

## 🎯 项目目标

### 源项目介绍

[TradingAgents](https://github.com/TauricResearch/TradingAgents) 是由杰出的 [Tauric Research](https://github.com/TauricResearch) 团队开发的**革命性多智能体交易框架**。这个项目的创新之处在于：

- **🤖 智能体协作**: 模拟真实交易公司的专业分工和协作决策流程
- **🧠 AI驱动**: 通过多个专业化AI智能体协作评估市场条件
- **📈 实战导向**: 专注于实际的交易决策和风险管理
- **🔬 前沿技术**: 将最新的大语言模型技术应用到金融领域

### 中文增强的使命

为了**更好地在中国推广这个优秀的TradingAgents框架**，我们创建了这个中文增强版本，目标是：

#### 🌉 搭建技术桥梁

- **语言无障碍**: 提供完整的中文文档和用户界面
- **技术本土化**: 集成国产大模型，适应国内技术环境
- **社区建设**: 为中文开发者社区提供学习和交流平台

#### 🇨🇳 服务中国市场

- **市场对接**: 支持A股、港股、新三板等中国金融市场
- **数据源集成**: 整合Tushare、AkShare、Wind等中文金融数据
- **合规适配**: 符合国内金融监管和数据安全要求

#### 🎓 推动技术普及

- **教育资源**: 为高校和研究机构提供AI金融教学工具
- **人才培养**: 帮助培养更多AI金融复合型人才
- **创新应用**: 推动AI技术在中国金融科技领域的创新应用

我们深信，通过这些努力，能够让更多中国用户体验到TradingAgents的强大功能，并为全球开源社区贡献中国智慧。

## 🎯 详细功能列表 (v0.1.7)

### 📊 功能统计总览


| 功能类别          | 已实现   | 开发中  | 规划中   | 完成度  |
| ----------------- | -------- | ------- | -------- | ------- |
| **🌐 Web界面**    | 7项      | 0项     | 2项      | 100%    |
| **🤖 智能体系统** | 9项      | 0项     | 1项      | 100%    |
| **🧠 LLM集成**    | 6项      | 0项     | 2项      | 100%    |
| **📊 数据源**     | 6项      | 0项     | 2项      | 100%    |
| **🗄️ 存储系统** | 5项      | 0项     | 1项      | 100%    |
| **📄 报告导出**   | 3项      | 1项     | 1项      | 85%     |
| **🐳 容器化**     | 5项      | 0项     | 2项      | 100%    |
| **⚙️ 配置管理** | 5项      | 0项     | 1项      | 100%    |
| **🛠️ 开发工具** | 5项      | 0项     | 2项      | 100%    |
| **🌐 部署运维**   | 5项      | 0项     | 3项      | 85%     |
| **📚 文档支持**   | 5项      | 0项     | 1项      | 100%    |
| **总计**          | **61项** | **1项** | **18项** | **97%** |

### 🌐 Web界面与用户体验


| 功能特性                   | 状态        | 详细说明                                   |
| -------------------------- | ----------- | ------------------------------------------ |
| **🖥️ Streamlit Web界面** | ✅ 完整支持 | 现代化响应式界面，支持实时交互和数据可视化 |
| **📱 移动端适配**          | ✅ 完整支持 | 响应式设计，支持手机和平板设备访问         |
| **🎨 主题定制**            | ✅ 完整支持 | 深色/浅色主题切换，自定义配色方案          |
| **🌍 多语言界面**          | ✅ 中文优先 | 完整中文界面，部分英文支持                 |
| **⚙️ 配置管理界面**      | ✅ 完整支持 | Web端API密钥管理，模型选择，参数配置       |
| **📊 实时监控面板**        | ✅ 完整支持 | Token使用统计，API调用监控，系统状态       |
| **🔔 消息通知**            | ✅ 完整支持 | 分析进度提示，错误警告，成功通知           |

### 🤖 多智能体协作系统


| 智能体类型          | 状态        | 功能描述                               |
| ------------------- | ----------- | -------------------------------------- |
| **📈 市场分析师**   | ✅ 完整支持 | 技术指标分析，价格趋势判断，成交量分析 |
| **💰 基本面分析师** | ✅ 完整支持 | 财务数据分析，行业对比，估值评估       |
| **📰 新闻分析师**   | ✅ 完整支持 | 新闻情绪分析，事件影响评估，舆情监控   |
| **💬 情绪分析师**   | ✅ 完整支持 | 社交媒体情绪，市场恐慌指数，投资者情绪 |
| **🐂 看涨研究员**   | ✅ 完整支持 | 多角度看涨论证，风险收益分析           |
| **🐻 看跌研究员**   | ✅ 完整支持 | 风险识别，下跌因素分析，防御策略       |
| **🎯 交易决策员**   | ✅ 完整支持 | 综合决策制定，仓位建议，止损止盈       |
| **🛡️ 风险管理员** | ✅ 完整支持 | 风险评估，资金管理，风控建议           |
| **👔 研究主管**     | ✅ 完整支持 | 团队协调，质量控制，最终审核           |

### 🧠 LLM模型集成


| 模型提供商        | 支持模型                           | 状态          | 特色功能                       |
| ----------------- | ---------------------------------- | ------------- | ------------------------------ |
| **🇨🇳 阿里百炼** | qwen-turbo, qwen-plus, qwen-max    | ✅ 完整支持   | 中文优化，成本效益高，响应快速 |
| **🇨🇳 DeepSeek** | deepseek-chat, deepseek-coder      | ✅ 完整支持   | 工具调用，数学计算，代码分析   |
| **🌍 Google AI**  | gemini-2.0-flash, gemini-1.5-pro   | ✅ 完整支持   | 多模态支持，推理能力强         |
| **🤖 OpenAI**     | GPT-4o, GPT-4o-mini, GPT-3.5-turbo | ⚙️ 配置即用 | 通用能力强，生态完善           |
| **🧠 Anthropic**  | Claude-3-Opus, Claude-3-Sonnet     | ⚙️ 配置即用 | 安全性高，长文本处理           |
| **💡 智能路由**   | 自动模型选择                       | ✅ 完整支持   | 根据任务类型自动选择最优模型   |

### 📊 数据源与市场支持


| 数据类型             | 数据源                 | 状态        | 覆盖范围                     |
| -------------------- | ---------------------- | ----------- | ---------------------------- |
| **🇨🇳 A股实时数据** | 通达信API, AkShare     | ✅ 完整支持 | 沪深两市，实时行情，历史数据 |
| **🇺🇸 美股数据**    | FinnHub, Yahoo Finance | ✅ 完整支持 | NYSE, NASDAQ，实时行情       |
| **📰 新闻数据**      | Google News, 财经新闻  | ✅ 完整支持 | 实时新闻，多语言支持         |
| **💬 社交情绪**      | Reddit, Twitter API    | ✅ 完整支持 | 情绪指数，热度分析           |
| **📈 技术指标**      | 自研算法               | ✅ 完整支持 | MA, RSI, MACD, 布林带等      |
| **💰 基本面数据**    | Tushare, 财务API       | ✅ 完整支持 | 财报数据，估值指标           |

### 🗄️ 数据存储与缓存


| 存储类型          | 技术方案     | 状态        | 功能特性                     |
| ----------------- | ------------ | ----------- | ---------------------------- |
| **📚 持久化存储** | MongoDB 4.4+ | ✅ 完整支持 | 分析结果，用户配置，历史数据 |
| **⚡ 高速缓存**   | Redis 6.0+   | ✅ 完整支持 | 实时数据，API响应，会话管理  |
| **📁 文件存储**   | 本地文件系统 | ✅ 完整支持 | 报告文件，日志文件，配置备份 |
| **🔄 智能降级**   | 多层数据源   | ✅ 完整支持 | MongoDB → Redis → 本地文件 |
| **🔐 数据安全**   | 加密存储     | ✅ 完整支持 | API密钥加密，敏感数据保护    |

### 📄 报告导出系统


| 导出格式          | 状态        | 功能特性                           |
| ----------------- | ----------- | ---------------------------------- |
| **📝 Markdown**   | ✅ 完整支持 | 轻量级格式，版本控制友好，在线查看 |
| **📄 Word文档**   | ✅ 完整支持 | 专业格式，可编辑，商业报告标准     |
| **📊 PDF文档**    | ✅ 完整支持 | 固定格式，打印友好，正式发布       |
| **🎨 自定义模板** | 🔄 开发中   | 多种报告模板，企业品牌定制         |
| **📧 自动分发**   | 🔄 规划中   | 邮件发送，定时报告，批量导出       |

### 🐳 容器化部署


| 部署方式              | 状态        | 功能描述                         |
| --------------------- | ----------- | -------------------------------- |
| **🐳 Docker支持**     | ✅ 完整支持 | 单容器部署，环境隔离，快速启动   |
| **🔧 Docker Compose** | ✅ 完整支持 | 多服务编排，一键部署，开发环境   |
| **📊 服务监控**       | ✅ 完整支持 | MongoDB Express，Redis Commander |
| **🔄 Volume映射**     | ✅ 完整支持 | 实时代码同步，开发调试优化       |
| **🌐 网络配置**       | ✅ 完整支持 | 服务发现，端口映射，安全隔离     |

### ⚙️ 系统配置与管理


| 配置类型           | 状态        | 管理方式                      |
| ------------------ | ----------- | ----------------------------- |
| **🔑 API密钥管理** | ✅ 完整支持 | .env文件，Web界面，环境变量   |
| **🎛️ 模型配置**  | ✅ 完整支持 | 模型选择，参数调优，成本控制  |
| **📊 监控配置**    | ✅ 完整支持 | Token统计，使用限制，告警设置 |
| **🔧 系统参数**    | ✅ 完整支持 | 缓存策略，超时设置，重试机制  |
| **🛡️ 安全配置**  | ✅ 完整支持 | 访问控制，数据加密，审计日志  |

### 🚀 核心优势

- **🎛️ 开箱即用**: 完整的Web界面，无需命令行操作
- **🇨🇳 中国优化**: A股数据 + 国产LLM + 中文界面
- **🔧 智能配置**: 自动检测，智能降级，零配置启动
- **📊 实时监控**: Token使用统计，缓存状态，系统监控
- **🛡️ 稳定可靠**: 多层数据源，错误恢复，生产就绪
- **🐳 容器化**: Docker部署，环境隔离，快速扩展
- **📄 专业报告**: 多格式导出，商业级质量，自动生成

### 🔧 技术架构与性能


| 技术领域        | 使用技术                                 | 版本要求   | 性能特性               |
| --------------- | ---------------------------------------- | ---------- | ---------------------- |
| **🐍 核心语言** | Python                                   | 3.10+      | 异步处理，多线程支持   |
| **🧠 AI框架**   | LangChain, LangGraph                     | 最新版     | 智能体编排，工具调用   |
| **🌐 Web界面**  | Streamlit                                | 1.28+      | 响应式设计，实时更新   |
| **🗄️ 数据库** | MongoDB, Redis                           | 4.4+, 6.0+ | 分布式存储，毫秒级缓存 |
| **📊 数据处理** | Pandas, NumPy                            | 最新版     | 向量化计算，内存优化   |
| **🔌 API集成**  | 通达信API, FinnHub, Google News          | -          | 并发请求，智能限流     |
| **🧠 LLM支持**  | DeepSeek V3, 阿里百炼, Google AI, OpenAI | -          | 智能路由，成本优化     |
| **📦 容器化**   | Docker, Docker Compose                   | 20.0+      | 微服务架构，弹性扩展   |
| **📄 文档转换** | Pandoc, wkhtmltopdf                      | 最新版     | 多格式支持，批量处理   |

### 🚀 性能与可靠性


| 性能指标          | 技术实现              | 性能数据        |
| ----------------- | --------------------- | --------------- |
| **⚡ 响应速度**   | Redis缓存 + 异步处理  | < 2秒分析响应   |
| **🔄 并发处理**   | 多智能体并行 + 线程池 | 支持10+并发用户 |
| **💾 内存优化**   | 数据流处理 + 垃圾回收 | < 1GB内存占用   |
| **🛡️ 错误恢复** | 多层降级 + 重试机制   | 99.9%服务可用性 |
| **📊 缓存命中**   | 智能缓存策略          | > 80%缓存命中率 |
| **🔐 数据安全**   | 加密存储 + 访问控制   | 企业级安全标准  |

### 🛠️ 开发与调试


| 开发工具        | 状态        | 功能描述                         |
| --------------- | ----------- | -------------------------------- |
| **🔧 开发环境** | ✅ 完整支持 | Volume映射，实时代码同步，热重载 |
| **🧪 测试工具** | ✅ 完整支持 | 单元测试，集成测试，性能测试     |
| **📝 日志系统** | ✅ 完整支持 | 结构化日志，级别控制，文件轮转   |
| **🔍 调试工具** | ✅ 完整支持 | 断点调试，性能分析，内存监控     |
| **📊 监控面板** | ✅ 完整支持 | 实时指标，告警通知，性能图表     |

### 🌐 部署与运维


| 部署方式          | 状态          | 适用场景                     |
| ----------------- | ------------- | ---------------------------- |
| **🖥️ 本地部署** | ✅ 完整支持   | 开发测试，个人使用，离线环境 |
| **🐳 Docker部署** | ✅ 完整支持   | 生产环境，容器化，微服务     |
| **☁️ 云端部署** | ⚙️ 配置即用 | AWS, Azure, GCP, 阿里云      |
| **🔄 CI/CD**      | 📋 文档完整   | 自动化部署，版本管理，回滚   |
| **📊 监控运维**   | ✅ 完整支持   | 健康检查，性能监控，日志分析 |

### 📚 文档与支持


| 文档类型        | 状态        | 内容覆盖                     |
| --------------- | ----------- | ---------------------------- |
| **📖 用户手册** | ✅ 完整支持 | 安装指南，使用教程，常见问题 |
| **🔧 开发文档** | ✅ 完整支持 | API文档，架构说明，扩展指南  |
| **🚨 故障排除** | ✅ 完整支持 | 错误诊断，解决方案，最佳实践 |
| **🎯 最佳实践** | ✅ 完整支持 | 配置优化，性能调优，安全建议 |
| **🔄 更新日志** | ✅ 完整支持 | 版本历史，功能变更，升级指南 |

## ✨ 核心特性

### 🤖 多智能体协作架构

- **分析师团队**: 基本面、技术面、新闻面、社交媒体四大专业分析师
- **研究员团队**: 看涨/看跌研究员进行结构化辩论
- **交易员智能体**: 基于所有输入做出最终交易决策
- **风险管理**: 多层次风险评估和管理机制
- **管理层**: 协调各团队工作，确保决策质量

### 🧠 多LLM模型支持

- **🇨🇳 阿里百炼**: qwen-turbo, qwen-plus-latest, qwen-max ✅ **已完整支持**
- **Google AI**: gemini-2.0-flash, gemini-1.5-pro, gemini-1.5-flash ✅ **已完整支持**
- **OpenAI**: GPT-4o, GPT-4o-mini, GPT-3.5-turbo ⚙️ **配置即用**
- **Anthropic**: Claude-3-Opus, Claude-3-Sonnet, Claude-3-Haiku ⚙️ **配置即用**
- **智能混合**: Google AI推理 + 阿里百炼嵌入 ✅ **已优化**

### 📊 全面数据集成

- **🇨🇳 A股数据**: 通达信API 实时行情和历史数据 ✅ **已完整支持**
- **美股数据**: FinnHub、Yahoo Finance 实时行情 ✅ **已完整支持**
- **新闻数据**: Google News、财经新闻、实时新闻API ✅ **已完整支持**
- **社交数据**: Reddit情绪分析 ✅ **已完整支持**
- **🗄️ 数据库支持**: MongoDB 数据持久化 + Redis 高速缓存 ✅ **已完整支持**
- **🔄 智能降级**: MongoDB → 通达信API → 本地缓存的多层数据源 ✅ **已完整支持**
- **⚙️ 统一配置**: .env文件统一管理，启用开关完全生效 ✅ **已完整支持**

### 🚀 高性能特性

- **并行处理**: 多智能体并行分析，提高效率
- **智能缓存**: 多层缓存策略，减少API调用成本
- **实时分析**: 支持实时市场数据分析
- **灵活配置**: 高度可定制的智能体行为和模型选择
- **📁 数据目录配置**: 灵活的数据存储路径配置，支持CLI、环境变量等多种方式
- **⚡ 数据库加速**: Redis毫秒级缓存 + MongoDB持久化存储
- **🔄 高可用架构**: 多层数据源降级，确保服务稳定性

### 🌐 Web管理界面 ✅ **已完整支持**

- **直观操作**: 基于Streamlit的现代化Web界面
- **实时进度**: 分析过程可视化，实时显示进度
- **智能配置**: 5级研究深度，从快速分析(2-4分钟)到全面分析(15-25分钟)
- **结果展示**: 结构化显示投资建议、目标价位、风险评估等
- **中文界面**: 完全中文化的用户界面和分析结果
- **🎛️ 配置管理**: API密钥管理、模型选择、系统配置 ✅ **已完整支持**
- **💰 Token统计**: 实时Token使用统计和成本追踪 ✅ **已完整支持**
- **💾 缓存管理**: 数据缓存状态监控和管理 ✅ **已完整支持**

## 🆚 与原版的主要区别

### ✅ 已完成的增强 (v0.1.7)


| 功能分类          | 原版状态     | 中文增强版状态                   | 完成度  |
| ----------------- | ------------ | -------------------------------- | ------- |
| **📚 文档体系**   | 英文基础文档 | 完整中文文档体系 + 架构设计文档  | ✅ 100% |
| **🌐 Web界面**    | 无           | Streamlit现代化界面 + 配置管理   | ✅ 100% |
| **🇨🇳 A股支持**  | 无           | 混合数据源 + 实时行情 + 历史数据 | ✅ 100% |
| **🧠 多LLM集成**  | 仅OpenAI     | DeepSeek+阿里百炼+Google AI      | ✅ 100% |
| **🗄️ 数据库**   | 无           | MongoDB + Redis + 智能降级       | ✅ 100% |
| **🐳 容器化部署** | 无           | Docker Compose + 一键部署        | ✅ 100% |
| **📄 报告导出**   | 无           | Word/PDF/Markdown多格式导出      | ✅ 100% |
| **⚙️ 配置管理** | 基础配置     | 统一.env配置 + Web管理界面       | ✅ 100% |
| **💰 成本控制**   | 无           | 智能路由 + 成本优化              | ✅ 100% |
| **🏗️ 架构优化** | 基础架构     | 容器化架构 + 微服务设计          | ✅ 100% |

### 🚀 v0.1.7 重大更新

- **🐳 容器化部署**: Docker Compose一键部署完整环境
- **📄 专业报告导出**: Word/PDF/Markdown多格式专业报告
- **🧠 DeepSeek V3集成**: 成本优化90%的中文AI模型
- **🔄 智能模型路由**: 根据任务自动选择最优模型
- **🛡️ 系统稳定性**: 全面错误修复和性能优化
- **📚 文档体系完善**: 新增10+专门功能文档

## 🚀 快速开始

### 🔐 重要安全提醒

> ⚠️ **API密钥安全警告**:
>
> - 绝对不要将包含真实API密钥的`.env`文件提交到Git仓库
> - 使用`.env.example`作为模板，创建您自己的`.env`文件
> - 详细安全指南请参考: [API密钥安全指南](docs/security/api_keys_security.md)

### 🎯 选择部署方式

#### 🐳 方式一：Docker部署 (推荐)

**适用场景**: 生产环境、快速体验、零配置启动

```bash
# 1. 克隆项目
git clone https://github.com/hsliuping/TradingAgents-CN.git
cd TradingAgents-CN

# 2. 配置环境变量
cp .env.example .env
# 编辑 .env 文件，填入API密钥

# 3. 构建并启动所有服务
docker-compose up -d --build
# 注意：首次运行会构建Docker镜像，需要5-10分钟

# 4. 访问应用
# Web界面: http://localhost:8501
# 数据库管理: http://localhost:8081
# 缓存管理: http://localhost:8082
```

**Docker部署包含的服务**:
- 🌐 **Web应用**: TradingAgents-CN主程序
- 🗄️ **MongoDB**: 数据持久化存储
- ⚡ **Redis**: 高速缓存
- 📊 **MongoDB Express**: 数据库管理界面
- 🎛️ **Redis Commander**: 缓存管理界面

#### 💻 方式二：本地部署

**适用场景**: 开发环境、自定义配置、离线使用

### 环境要求

- Python 3.10+ (推荐 3.11)
- 4GB+ RAM (推荐 8GB+)
- 稳定的网络连接

### 安装步骤

```bash
# 1. 克隆项目
git clone https://github.com/hsliuping/TradingAgents-CN.git
cd TradingAgents-CN

# 2. 创建虚拟环境
python -m venv env
# Windows
env\Scripts\activate
# Linux/macOS
source env/bin/activate

# 3. 安装基础依赖
pip install -r requirements.txt

# 4. 安装A股数据支持（可选）
pip install pytdx  # 通达信API，用于A股实时数据

# 5. 安装数据库支持（可选，推荐）
pip install -r requirements_db.txt  # MongoDB + Redis 支持
```

### 配置API密钥

#### 🇨🇳 推荐：使用阿里百炼（国产大模型）

```bash
# 复制配置模板
cp .env.example .env

# 编辑 .env 文件，配置以下必需的API密钥：
DASHSCOPE_API_KEY=your_dashscope_api_key_here
FINNHUB_API_KEY=your_finnhub_api_key_here

# 可选：Google AI API（支持Gemini模型）
GOOGLE_API_KEY=your_google_api_key_here

# 可选：数据库配置（提升性能，默认禁用）
MONGODB_ENABLED=false  # 设为true启用MongoDB
REDIS_ENABLED=false    # 设为true启用Redis
MONGODB_HOST=localhost
MONGODB_PORT=27018     # 使用非标准端口避免冲突
REDIS_HOST=localhost
REDIS_PORT=6380        # 使用非标准端口避免冲突
```

#### 🌍 可选：使用国外模型

```bash
# OpenAI (需要科学上网)
OPENAI_API_KEY=your_openai_api_key

# Anthropic (需要科学上网)
ANTHROPIC_API_KEY=your_anthropic_api_key
```

### 🗄️ 数据库配置（MongoDB + Redis）

#### 高性能数据存储支持

本项目支持 **MongoDB** 和 **Redis** 数据库，提供：

- **📊 股票数据缓存**: 减少API调用，提升响应速度
- **🔄 智能降级机制**: MongoDB → API → 本地缓存的多层数据源
- **⚡ 高性能缓存**: Redis缓存热点数据，毫秒级响应
- **🛡️ 数据持久化**: MongoDB存储历史数据，支持离线分析

#### 数据库部署方式

**🐳 Docker部署（推荐）**

如果您使用Docker部署，数据库已自动包含在内：

```bash
# Docker部署会自动启动所有服务，包括：
docker-compose up -d --build
# - Web应用 (端口8501)
# - MongoDB (端口27017)
# - Redis (端口6379)
# - 数据库管理界面 (端口8081, 8082)
```

**💻 本地部署 - 数据库配置**

如果您使用本地部署，可以选择以下方式：

**方式一：仅启动数据库服务**

```bash
# 仅启动 MongoDB + Redis 服务（不启动Web应用）
docker-compose up -d mongodb redis mongo-express redis-commander

# 查看服务状态
docker-compose ps

# 停止服务
docker-compose down
```

**方式二：完全本地安装**

```bash
# 安装数据库依赖
pip install -r requirements_db.txt

# 启动 MongoDB (默认端口 27017)
mongod --dbpath ./data/mongodb

# 启动 Redis (默认端口 6379)
redis-server
```

> ⚠️ **重要说明**:
> - **🐳 Docker部署**: 数据库自动包含，无需额外配置
> - **💻 本地部署**: 可选择仅启动数据库服务或完全本地安装
> - **📋 推荐**: 使用Docker部署以获得最佳体验和一致性

#### 数据库配置选项

**环境变量配置**（推荐）：

```bash
# MongoDB 配置
MONGODB_HOST=localhost
MONGODB_PORT=27017
MONGODB_DATABASE=trading_agents
MONGODB_USERNAME=admin
MONGODB_PASSWORD=your_password

# Redis 配置
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_PASSWORD=your_redis_password
REDIS_DB=0
```

**配置文件方式**：

```python
# config/database_config.py
DATABASE_CONFIG = {
    'mongodb': {
        'host': 'localhost',
        'port': 27017,
        'database': 'trading_agents',
        'username': 'admin',
        'password': 'your_password'
    },
    'redis': {
        'host': 'localhost',
        'port': 6379,
        'password': 'your_redis_password',
        'db': 0
    }
}
```

#### 数据库功能特性

**MongoDB 功能**：

- ✅ 股票基础信息存储
- ✅ 历史价格数据缓存
- ✅ 分析结果持久化
- ✅ 用户配置管理
- ✅ 自动数据同步

**Redis 功能**：

- ⚡ 实时价格数据缓存
- ⚡ API响应结果缓存
- ⚡ 会话状态管理
- ⚡ 热点数据预加载
- ⚡ 分布式锁支持

#### 智能降级机制

系统采用多层数据源降级策略，确保高可用性：

```
📊 数据获取流程：
1. 🔍 检查 Redis 缓存 (毫秒级)
2. 📚 查询 MongoDB 存储 (秒级)
3. 🌐 调用通达信API (秒级)
4. 💾 本地文件缓存 (备用)
5. ❌ 返回错误信息
```

**配置降级策略**：

```python
# 在 .env 文件中配置
ENABLE_MONGODB=true
ENABLE_REDIS=true
ENABLE_FALLBACK=true

# 缓存过期时间（秒）
REDIS_CACHE_TTL=300
MONGODB_CACHE_TTL=3600
```

#### 性能优化建议

**生产环境配置**：

```bash
# MongoDB 优化
MONGODB_MAX_POOL_SIZE=50
MONGODB_MIN_POOL_SIZE=5
MONGODB_MAX_IDLE_TIME=30000

# Redis 优化
REDIS_MAX_CONNECTIONS=20
REDIS_CONNECTION_POOL_SIZE=10
REDIS_SOCKET_TIMEOUT=5
```

#### 数据库管理工具

```bash
# 初始化数据库
python scripts/init_database.py

# 数据库状态检查
python scripts/check_database_status.py

# 数据同步工具
python scripts/sync_stock_data.py

# 清理过期缓存
python scripts/cleanup_cache.py
```

#### 故障排除

**常见问题解决**：

1. **MongoDB连接失败**

   **Docker部署**：
   ```bash
   # 检查服务状态
   docker-compose logs mongodb

   # 重启服务
   docker-compose restart mongodb
   ```

   **本地部署**：
   ```bash
   # 检查MongoDB进程
   ps aux | grep mongod

   # 重启MongoDB
   sudo systemctl restart mongod  # Linux
   brew services restart mongodb  # macOS
   ```
2. **Redis连接超时**

   ```bash
   # 检查Redis状态
   redis-cli ping

   # 清理Redis缓存
   redis-cli flushdb
   ```
3. **数据同步问题**

   ```bash
   # 手动触发数据同步
   python scripts/manual_sync.py
   ```

> 💡 **提示**: 即使不配置数据库，系统仍可正常运行，会自动降级到API直接调用模式。数据库配置是可选的性能优化功能。

> 📚 **详细文档**: 更多数据库配置信息请参考 [数据库架构文档](docs/architecture/database-architecture.md)

### 📤 报告导出功能

#### 新增功能：专业分析报告导出

本项目现已支持将股票分析结果导出为多种专业格式：

**支持的导出格式**：

- **📄 Markdown (.md)** - 轻量级标记语言，适合技术用户和版本控制
- **📝 Word (.docx)** - Microsoft Word文档，适合商务报告和进一步编辑
- **📊 PDF (.pdf)** - 便携式文档格式，适合正式分享和打印

**报告内容结构**：

- 🎯 **投资决策摘要** - 买入/持有/卖出建议，置信度，风险评分
- 📊 **详细分析报告** - 技术分析，基本面分析，市场情绪，新闻事件
- ⚠️ **风险提示** - 完整的投资风险声明和免责条款
- 📋 **配置信息** - 分析参数，模型信息，生成时间

**使用方法**：

1. 完成股票分析后，在结果页面底部找到"📤 导出报告"部分
2. 选择需要的格式：Markdown、Word或PDF
3. 点击导出按钮，系统自动生成并提供下载

**安装导出依赖**：

```bash
# 安装Python依赖
pip install markdown pypandoc

# 安装系统工具（用于PDF导出）
# Windows: choco install pandoc wkhtmltopdf
# macOS: brew install pandoc wkhtmltopdf
# Linux: sudo apt-get install pandoc wkhtmltopdf
```

> 📚 **详细文档**: 完整的导出功能使用指南请参考 [导出功能指南](docs/EXPORT_GUIDE.md)

### 🚀 启动应用

#### 🐳 Docker启动（推荐）

如果您使用Docker部署，应用已经自动启动：

```bash
# 应用已在Docker中运行，直接访问：
# Web界面: http://localhost:8501
# 数据库管理: http://localhost:8081
# 缓存管理: http://localhost:8082

# 查看运行状态
docker-compose ps

# 查看日志
docker-compose logs -f web
```

#### 💻 本地启动

如果您使用本地部署：

```bash
# 1. 激活虚拟环境
# Windows
.\env\Scripts\activate
# Linux/macOS
source env/bin/activate

# 2. 启动Web管理界面
streamlit run web/app.py
```

然后在浏览器中访问 `http://localhost:8501`

**Web界面特色功能**:

- 🇺🇸 **美股分析**: 支持 AAPL, TSLA, NVDA 等美股代码
- 🇨🇳 **A股分析**: 支持 000001, 600519, 300750 等A股代码
- 📊 **实时数据**: 通达信API提供A股实时行情数据
- 🤖 **智能体选择**: 可选择不同的分析师组合
- 📤 **报告导出**: 一键导出Markdown/Word/PDF格式专业分析报告
- 🎯 **5级研究深度**: 从快速分析(2-4分钟)到全面分析(15-25分钟)
- 📊 **智能分析师选择**: 市场技术、基本面、新闻、社交媒体分析师
- 🔄 **实时进度显示**: 可视化分析过程，避免等待焦虑
- 📈 **结构化结果**: 投资建议、目标价位、置信度、风险评估
- 🇨🇳 **完全中文化**: 界面和分析结果全中文显示

**研究深度级别说明**:

- **1级 - 快速分析** (2-4分钟): 日常监控，基础决策
- **2级 - 基础分析** (4-6分钟): 常规投资，平衡速度
- **3级 - 标准分析** (6-10分钟): 重要决策，推荐默认
- **4级 - 深度分析** (10-15分钟): 重大投资，详细研究
- **5级 - 全面分析** (15-25分钟): 最重要决策，最全面分析

#### 💻 代码调用（适合开发者）

```python
from tradingagents.graph.trading_graph import TradingAgentsGraph
from tradingagents.default_config import DEFAULT_CONFIG

# 配置阿里百炼
config = DEFAULT_CONFIG.copy()
config["llm_provider"] = "dashscope"
config["deep_think_llm"] = "qwen-plus"      # 深度分析
config["quick_think_llm"] = "qwen-turbo"    # 快速任务

# 创建交易智能体
ta = TradingAgentsGraph(debug=True, config=config)

# 分析股票 (以苹果公司为例)
state, decision = ta.propagate("AAPL", "2024-01-15")

# 输出分析结果
print(f"推荐动作: {decision['action']}")
print(f"置信度: {decision['confidence']:.1%}")
print(f"风险评分: {decision['risk_score']:.1%}")
print(f"推理过程: {decision['reasoning']}")
```

#### 快速启动脚本

```bash
# 阿里百炼演示（推荐中文用户）
python examples/dashscope/demo_dashscope_chinese.py

# 阿里百炼完整演示
python examples/dashscope/demo_dashscope.py

# 阿里百炼简化测试
python examples/dashscope/demo_dashscope_simple.py

# OpenAI演示（需要国外API）
python examples/openai/demo_openai.py

# 集成测试
python tests/integration/test_dashscope_integration.py
```

#### 📁 数据目录配置

**新功能**: 灵活配置数据存储路径，支持多种配置方式：

```bash
# 查看当前数据目录配置
python -m cli.main data-config --show

# 设置自定义数据目录
python -m cli.main data-config --set /path/to/your/data

# 重置为默认配置
python -m cli.main data-config --reset
```

**环境变量配置**:

```bash
# Windows
set TRADING_AGENTS_DATA_DIR=C:\MyTradingData

# Linux/macOS
export TRADING_AGENTS_DATA_DIR=/home/user/trading_data
```

**程序化配置**:

```python
from tradingagents.config_manager import ConfigManager

# 设置数据目录
config_manager = ConfigManager()
config_manager.set_data_directory("/path/to/data")

# 获取配置
data_dir = config_manager.get_data_directory()
print(f"数据目录: {data_dir}")
```

**配置优先级**: 程序设置 > 环境变量 > 配置文件 > 默认值

详细说明请参考: [📁 数据目录配置指南](docs/configuration/data-directory-configuration.md)

### 交互式分析

```bash
# 启动交互式命令行界面
python -m cli.main
```

## 🎯 **快速导航** - 找到您需要的内容


| 🎯**我想要...** | 📖**推荐文档**                                            | ⏱️**阅读时间** |
| --------------- | --------------------------------------------------------- | ---------------- |
| **快速上手**    | [🚀 快速开始](docs/overview/quick-start.md)               | 10分钟           |
| **了解架构**    | [🏛️ 系统架构](docs/architecture/system-architecture.md) | 15分钟           |
| **看代码示例**  | [📚 基础示例](docs/examples/basic-examples.md)            | 20分钟           |
| **解决问题**    | [🆘 常见问题](docs/faq/faq.md)                            | 5分钟            |
| **深度学习**  | [📁 完整文档目录](#-详细文档目录)                         | 2小时+           |

> 💡 **提示**: 我们的 `docs/` 目录包含了 **50,000+字** 的详细中文文档，这是与原版最大的区别！

## 📚 完整文档体系 - 核心亮点

> **🌟 这是本项目与原版最大的区别！** 我们构建了业界最完整的中文金融AI框架文档体系，包含超过 **50,000字** 的详细技术文档，**20+** 个专业文档文件，**100+** 个代码示例。

### 🎯 为什么选择我们的文档？


| 对比维度     | 原版 TradingAgents | 🚀**中文增强版**           |
| ------------ | ------------------ | -------------------------- |
| **文档语言** | 英文基础说明       | **完整中文体系**           |
| **文档深度** | 简单介绍           | **深度技术剖析**           |
| **架构说明** | 概念性描述         | **详细设计文档 + 架构图**  |
| **使用指南** | 基础示例           | **从入门到专家的完整路径** |
| **故障排除** | 无                 | **详细FAQ + 解决方案**     |
| **代码示例** | 少量示例           | **100+ 实用示例**          |

### 📖 文档导航 - 按学习路径组织

#### 🚀 **新手入门路径** (推荐从这里开始)

1. [📋 项目概述](docs/overview/project-overview.md) - **了解项目背景和核心价值**
2. [⚙️ 详细安装](docs/overview/installation.md) - **各平台详细安装指南**
3. [🚀 快速开始](docs/overview/quick-start.md) - **10分钟上手指南**
4. [📚 基础示例](docs/examples/basic-examples.md) - **8个实用的入门示例**

#### 🏗️ **架构理解路径** (深入了解系统设计)

1. [🏛️ 系统架构](docs/architecture/system-architecture.md) - **完整的系统架构设计**
2. [🤖 智能体架构](docs/architecture/agent-architecture.md) - **多智能体协作机制**
3. [📊 数据流架构](docs/architecture/data-flow-architecture.md) - **数据处理全流程**
4. [🔄 图结构设计](docs/architecture/graph-structure.md) - **LangGraph工作流程**

#### 🤖 **智能体深度解析** (了解每个智能体的设计)

1. [📈 分析师团队](docs/agents/analysts.md) - **四类专业分析师详解**
2. [🔬 研究员团队](docs/agents/researchers.md) - **看涨/看跌辩论机制**
3. [💼 交易员智能体](docs/agents/trader.md) - **交易决策制定流程**
4. [🛡️ 风险管理](docs/agents/risk-management.md) - **多层次风险评估**
5. [👔 管理层智能体](docs/agents/managers.md) - **协调和决策管理**

#### 📊 **数据处理专题** (掌握数据处理技术)

1. [🔌 数据源集成](docs/data/data-sources.md) - **多数据源API集成**
2. [⚙️ 数据处理流程](docs/data/data-processing.md) - **数据清洗和转换**
3. [💾 缓存策略](docs/data/caching.md) - **多层缓存优化性能**

#### ⚙️ **配置和优化** (性能调优和定制)

1. [📝 配置指南](docs/configuration/config-guide.md) - **详细配置选项说明**
2. [🧠 LLM配置](docs/configuration/llm-config.md) - **大语言模型优化**

#### 💡 **高级应用** (扩展开发和实战)

1. [📚 基础示例](docs/examples/basic-examples.md) - **8个实用基础示例**
2. [🚀 高级示例](docs/examples/advanced-examples.md) - **复杂场景和扩展开发**

#### ❓ **问题解决** (遇到问题时查看)

1. [🆘 常见问题](docs/faq/faq.md) - **详细FAQ和解决方案**

### 📊 文档统计数据

- 📄 **文档文件数**: 20+ 个专业文档
- 📝 **总字数**: 50,000+ 字详细内容
- 💻 **代码示例**: 100+ 个实用示例
- 📈 **架构图表**: 10+ 个专业图表
- 🎯 **覆盖范围**: 从入门到专家的完整路径

### 🎨 文档特色

- **🇨🇳 完全中文化**: 专为中文用户优化的表达方式
- **📊 图文并茂**: 丰富的架构图和流程图
- **💻 代码丰富**: 每个概念都有对应的代码示例
- **🔍 深度剖析**: 不仅告诉你怎么做，还告诉你为什么这样做
- **🛠️ 实用导向**: 所有文档都面向实际应用场景

---

## 📚 详细文档目录

### 📁 **docs/ 目录结构** - 完整的知识体系

```
docs/
├── 📖 overview/              # 项目概览 - 新手必读
│   ├── project-overview.md   # 📋 项目详细介绍
│   ├── quick-start.md        # 🚀 10分钟快速上手
│   └── installation.md       # ⚙️ 详细安装指南
│
├── 🏗️ architecture/          # 系统架构 - 深度理解
│   ├── system-architecture.md    # 🏛️ 整体架构设计
│   ├── agent-architecture.md     # 🤖 智能体协作机制
│   ├── data-flow-architecture.md # 📊 数据流处理架构
│   └── graph-structure.md        # 🔄 LangGraph工作流
│
├── 🤖 agents/               # 智能体详解 - 核心组件
│   ├── analysts.md          # 📈 四类专业分析师
│   ├── researchers.md       # 🔬 看涨/看跌辩论机制
│   ├── trader.md           # 💼 交易决策制定
│   ├── risk-management.md  # 🛡️ 多层风险评估
│   └── managers.md         # 👔 管理层协调
│
├── 📊 data/                 # 数据处理 - 技术核心
│   ├── data-sources.md      # 🔌 多数据源集成
│   ├── data-processing.md   # ⚙️ 数据处理流程
│   └── caching.md          # 💾 缓存优化策略
│
├── ⚙️ configuration/        # 配置优化 - 性能调优
│   ├── config-guide.md      # 📝 详细配置说明
│   └── llm-config.md       # 🧠 LLM模型优化
│
├── 💡 examples/             # 示例教程 - 实战应用
│   ├── basic-examples.md    # 📚 8个基础示例
│   └── advanced-examples.md # 🚀 高级开发示例
│
└── ❓ faq/                  # 问题解决 - 疑难解答
    └── faq.md              # 🆘 常见问题FAQ
```

### 🎯 **重点推荐文档** (必读精选)

#### 🔥 **最受欢迎的文档**

1. **[📋 项目概述](docs/overview/project-overview.md)** - ⭐⭐⭐⭐⭐

   > 了解项目的核心价值和技术特色，5分钟读懂整个框架
   >
2. **[🏛️ 系统架构](docs/architecture/system-architecture.md)** - ⭐⭐⭐⭐⭐

   > 深度解析多智能体协作机制，包含详细架构图
   >
3. **[📚 基础示例](docs/examples/basic-examples.md)** - ⭐⭐⭐⭐⭐

   > 8个实用示例，从股票分析到投资组合优化
   >

#### 🚀 **技术深度文档**

1. **[🤖 智能体架构](docs/architecture/agent-architecture.md)**

   > 多智能体设计模式和协作机制详解
   >
2. **[📊 数据流架构](docs/architecture/data-flow-architecture.md)**

   > 数据获取、处理、缓存的完整流程
   >
3. **[🔬 研究员团队](docs/agents/researchers.md)**

   > 看涨/看跌研究员辩论机制的创新设计
   >

#### 💼 **实用工具文档**

1. **[🌐 Web界面指南](docs/usage/web-interface-guide.md)** - ⭐⭐⭐⭐⭐

   > 完整的Web界面使用教程，包含5级研究深度详细说明
   >
2. **[💰 投资分析指南](docs/usage/investment_analysis_guide.md)**

   > 从基础到高级的完整投资分析教程
   >
3. **[🧠 LLM配置](docs/configuration/llm-config.md)**

   > 多LLM模型配置和成本优化策略
   >
4. **[💾 缓存策略](docs/data/caching.md)**

   > 多层缓存设计，显著降低API调用成本
   >
5. **[🆘 常见问题](docs/faq/faq.md)**

   > 详细的FAQ和故障排除指南
   >

### 📖 **按模块浏览文档**

<details>
<summary><strong>📖 概览文档</strong> - 项目入门必读</summary>

- [📋 项目概述](docs/overview/project-overview.md) - 详细的项目背景和特性介绍
- [🚀 快速开始](docs/overview/quick-start.md) - 从安装到第一次运行的完整指南
- [⚙️ 详细安装](docs/overview/installation.md) - 各平台详细安装说明

</details>

<details>
<summary><strong>🏗️ 架构文档</strong> - 深度理解系统设计</summary>

- [🏛️ 系统架构](docs/architecture/system-architecture.md) - 完整的系统架构设计
- [🤖 智能体架构](docs/architecture/agent-architecture.md) - 智能体设计模式和协作机制
- [📊 数据流架构](docs/architecture/data-flow-architecture.md) - 数据获取、处理和分发流程
- [🔄 图结构设计](docs/architecture/graph-structure.md) - LangGraph工作流程设计

</details>

<details>
<summary><strong>🤖 智能体文档</strong> - 核心组件详解</summary>

- [📈 分析师团队](docs/agents/analysts.md) - 四类专业分析师详解
- [🔬 研究员团队](docs/agents/researchers.md) - 看涨/看跌研究员和辩论机制
- [💼 交易员智能体](docs/agents/trader.md) - 交易决策制定流程
- [🛡️ 风险管理](docs/agents/risk-management.md) - 多层次风险评估体系
- [👔 管理层智能体](docs/agents/managers.md) - 协调和决策管理

</details>

<details>
<summary><strong>📊 数据处理</strong> - 技术核心实现</summary>

- [🔌 数据源集成](docs/data/data-sources.md) - 支持的数据源和API集成
- [⚙️ 数据处理流程](docs/data/data-processing.md) - 数据清洗、转换和验证
- [💾 缓存策略](docs/data/caching.md) - 多层缓存优化性能

</details>

<details>
<summary><strong>⚙️ 配置与部署</strong> - 性能调优指南</summary>

- [📝 配置指南](docs/configuration/config-guide.md) - 详细的配置选项说明
- [🧠 LLM配置](docs/configuration/llm-config.md) - 大语言模型配置优化

</details>

<details>
<summary><strong>💡 示例和教程</strong> - 实战应用指南</summary>

- [📚 基础示例](docs/examples/basic-examples.md) - 8个实用的基础示例
- [🚀 高级示例](docs/examples/advanced-examples.md) - 复杂场景和扩展开发

</details>

<details>
<summary><strong>❓ 帮助文档</strong> - 问题解决方案</summary>

- [🆘 常见问题](docs/faq/faq.md) - 详细的FAQ和解决方案

</details>

## 💰 成本控制

### 典型使用成本

- **经济模式**: $0.01-0.05/次分析 (使用 gpt-4o-mini)
- **标准模式**: $0.05-0.15/次分析 (使用 gpt-4o)
- **高精度模式**: $0.10-0.30/次分析 (使用 gpt-4o + 多轮辩论)

### 成本优化建议

```python
# 低成本配置示例
cost_optimized_config = {
    "deep_think_llm": "gpt-4o-mini",
    "quick_think_llm": "gpt-4o-mini", 
    "max_debate_rounds": 1,
    "online_tools": False  # 使用缓存数据
}
```

## 🤝 贡献指南

我们欢迎各种形式的贡献：

### 贡献类型

- 🐛 **Bug修复** - 发现并修复问题
- ✨ **新功能** - 添加新的功能特性
- 📚 **文档改进** - 完善文档和教程
- 🌐 **本地化** - 翻译和本地化工作
- 🎨 **代码优化** - 性能优化和代码重构

### 贡献流程

1. Fork 本仓库
2. 创建特性分支 (`git checkout -b feature/AmazingFeature`)
3. 提交更改 (`git commit -m 'Add some AmazingFeature'`)
4. 推送到分支 (`git push origin feature/AmazingFeature`)
5. 创建 Pull Request

## 📄 许可证

本项目基于 Apache 2.0 许可证开源。详见 [LICENSE](LICENSE) 文件。

### 许可证说明

- ✅ 商业使用
- ✅ 修改和分发
- ✅ 私人使用
- ✅ 专利使用
- ❗ 需要保留版权声明
- ❗ 需要包含许可证副本

## 🙏 致谢与感恩

### 🌟 向源项目开发者致敬

我们向 [Tauric Research](https://github.com/TauricResearch) 团队表达最深的敬意和感谢：

- **🎯 愿景领导者**: 感谢您们在AI金融领域的前瞻性思考和创新实践
- **💎 珍贵源码**: 感谢您们开源的每一行代码，它们凝聚着无数的智慧和心血
- **🏗️ 架构大师**: 感谢您们设计了如此优雅、可扩展的多智能体框架
- **💡 技术先驱**: 感谢您们将前沿AI技术与金融实务完美结合
- **🔄 持续贡献**: 感谢您们持续的维护、更新和改进工作

### 🤝 社区贡献者致谢

感谢以下社区贡献者为TradingAgents-CN项目做出的重要贡献：

#### 🐳 Docker容器化功能

- **[@breeze303](https://github.com/breeze303)**: 提供完整的Docker Compose配置和容器化部署方案，大大简化了项目的部署和开发环境配置

#### 📄 报告导出功能

- **[@baiyuxiong](https://github.com/baiyuxiong)** (baiyuxiong@163.com): 设计并实现了完整的多格式报告导出系统，包括Word、PDF、Markdown格式支持

#### 🌟 其他贡献

- **所有提交Issue的用户**: 感谢您们的问题反馈和功能建议
- **测试用户**: 感谢您们在开发过程中的测试和反馈
- **文档贡献者**: 感谢您们对项目文档的完善和改进
- **🌍 开源贡献**: 感谢您们选择Apache 2.0协议，给予开发者最大的自由
- **📚 知识分享**: 感谢您们提供的详细文档和最佳实践指导

**特别感谢**：[TradingAgents](https://github.com/TauricResearch/TradingAgents) 项目为我们提供了坚实的技术基础。虽然Apache 2.0协议赋予了我们使用源码的权利，但我们深知每一行代码的珍贵价值，将永远铭记并感谢您们的无私贡献。

### 🇨🇳 推广使命的初心

创建这个中文增强版本，我们怀着以下初心：

- **🌉 技术传播**: 让优秀的TradingAgents技术在中国得到更广泛的应用
- **🎓 教育普及**: 为中国的AI金融教育提供更好的工具和资源
- **🤝 文化桥梁**: 在中西方技术社区之间搭建交流合作的桥梁
- **🚀 创新推动**: 推动中国金融科技领域的AI技术创新和应用

### 🌍 开源社区

感谢所有为本项目贡献代码、文档、建议和反馈的开发者和用户。正是因为有了大家的支持，我们才能更好地服务中文用户社区。

### 🤝 合作共赢

我们承诺：

- **尊重原创**: 始终尊重源项目的知识产权和开源协议
- **反馈贡献**: 将有价值的改进和创新反馈给源项目和开源社区
- **持续改进**: 不断完善中文增强版本，提供更好的用户体验
- **开放合作**: 欢迎与源项目团队和全球开发者进行技术交流与合作

## 📈 版本历史

- **v0.1.7** (2025-07-13): 🐳 容器化部署与专业报告导出 ✨ **最新版本**
- **v0.1.6** (2025-07-11): 🔧 阿里百炼修复与数据源升级
- **v0.1.5** (2025-07-08): 📊 添加Deepseek模型支持
- **v0.1.4** (2025-07-05): 🏗️ 架构优化与配置管理重构
- **v0.1.3** (2025-06-28): 🇨🇳 A股市场完整支持
- **v0.1.2** (2025-06-15): 🌐 Web界面和配置管理
- **v0.1.1** (2025-06-01): 🧠 国产LLM集成

📋 **详细更新日志**: [CHANGELOG.md](CHANGELOG.md)

## 📞 联系方式

- **GitHub Issues**: [提交问题和建议](https://github.com/hsliuping/TradingAgents-CN/issues)
- **邮箱**: hsliup@163.com
- **原项目**: [TauricResearch/TradingAgents](https://github.com/TauricResearch/TradingAgents)
- **文档**: [完整文档目录](docs/)

## ⚠️ 风险提示

**重要声明**: 本框架仅用于研究和教育目的，不构成投资建议。

- 📊 交易表现可能因多种因素而异
- 🤖 AI模型的预测存在不确定性
- 💰 投资有风险，决策需谨慎
- 👨‍💼 建议咨询专业财务顾问

---

<div align="center">

**🌟 如果这个项目对您有帮助，请给我们一个 Star！**

[⭐ Star this repo](https://github.com/hsliuping/TradingAgents-CN) | [🍴 Fork this repo](https://github.com/hsliuping/TradingAgents-CN/fork) | [📖 Read the docs](./docs/)

</div>
