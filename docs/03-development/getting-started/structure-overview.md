# 文档目录结构

```
docs/
├── README.md                           # 文档主页和导航
├── STRUCTURE.md                        # 本文件 - 文档结构说明
│
├── overview/                           # 📋 概览文档
│   ├── project-overview.md            # ✅ 项目概述
│   ├── quick-start.md                 # ✅ 快速开始指南
│   └── installation.md                # 🔄 详细安装说明
│
├── architecture/                      # 🏗️ 架构文档
│   ├── system-architecture.md         # ✅ 系统架构设计
│   ├── agent-architecture.md          # ✅ 智能体架构设计
│   ├── data-flow-architecture.md      # ✅ 数据流架构
│   └── graph-structure.md             # ✅ LangGraph 图结构设计
│
├── agents/                            # 🤖 智能体文档
│   ├── analysts.md                    # ✅ 分析师团队详解
│   ├── researchers.md                 # 🔄 研究员团队设计
│   ├── trader.md                      # 🔄 交易员智能体
│   ├── risk-management.md             # 🔄 风险管理智能体
│   └── managers.md                    # 🔄 管理层智能体
│
├── data/                              # 📊 数据处理文档
│   ├── data-sources.md                # 🔄 支持的数据源和API
│   ├── data-processing.md             # 🔄 数据获取和处理
│   └── caching.md                     # 🔄 数据缓存策略
│
├── configuration/                     # ⚙️ 配置与部署
│   ├── config-guide.md               # 🔄 配置文件详解
│   └── llm-config.md                 # 🔄 大语言模型配置
│
├── deployment/                        # 🚀 部署文档
│   └── deployment-guide.md           # 🔄 生产环境部署
│
├── development/                       # 🔧 开发指南
│   ├── dev-setup.md                  # 🔄 开发环境搭建
│   ├── code-structure.md             # 🔄 代码组织结构
│   ├── extending.md                  # 🔄 如何扩展框架
│   └── testing.md                    # 🔄 测试策略和方法
│
├── api/                               # 📚 API参考
│   ├── core-api.md                   # 🔄 核心类和方法
│   ├── agents-api.md                 # 🔄 智能体接口
│   └── data-api.md                   # 🔄 数据处理接口
│
├── examples/                          # 💡 示例和教程
│   ├── basic-examples.md             # 🔄 基本使用示例
│   ├── advanced-examples.md          # 🔄 高级功能示例
│   └── custom-agents.md              # 🔄 创建自定义智能体
│
└── faq/                               # ❓ 常见问题
    ├── faq.md                         # 🔄 常见问题解答
    └── troubleshooting.md             # 🔄 问题诊断和解决
```

## 图例说明

- ✅ **已完成**: 文档已创建并包含完整内容
- 🔄 **待完成**: 文档结构已规划，内容待补充
- 📋 **概览类**: 项目介绍和快速上手
- 🏗️ **架构类**: 系统设计和技术架构
- 🤖 **智能体类**: 各类智能体的详细说明
- 📊 **数据类**: 数据处理和管理
- ⚙️ **配置类**: 系统配置和设置
- 🚀 **部署类**: 部署和运维
- 🔧 **开发类**: 开发和扩展指南
- 📚 **API类**: 接口和方法参考
- 💡 **示例类**: 使用示例和教程
- ❓ **帮助类**: 问题解答和故障排除

## 文档编写规范

### 1. 文件命名
- 使用小写字母和连字符
- 文件名应简洁明了，体现内容主题
- 使用 `.md` 扩展名

### 2. 内容结构
- 每个文档都应包含清晰的标题层次
- 使用适当的Markdown语法
- 包含代码示例和图表说明
- 提供相关链接和参考

### 3. 代码示例
- 提供完整可运行的代码示例
- 包含必要的注释和说明
- 使用一致的代码风格
- 提供预期的输出结果

### 4. 图表和图像
- 使用Mermaid图表展示架构和流程
- 图片应存储在适当的目录中
- 提供图表的文字描述
- 确保图表在不同设备上的可读性

## 维护指南

### 1. 定期更新
- 随着代码更新同步更新文档
- 定期检查链接的有效性
- 更新过时的信息和示例

### 2. 质量控制
- 确保文档的准确性和完整性
- 检查语法和拼写错误
- 验证代码示例的可执行性

### 3. 用户反馈
- 收集用户对文档的反馈
- 根据常见问题完善文档
- 持续改进文档的可读性

## 贡献指南

### 如何贡献文档

1. **Fork 项目**: 在GitHub上fork TradingAgents项目
2. **创建分支**: 为文档更新创建新分支
3. **编写文档**: 按照规范编写或更新文档
4. **提交PR**: 提交Pull Request并描述更改内容
5. **代码审查**: 等待维护者审查和合并

### 文档贡献类型

- **新增文档**: 创建缺失的文档内容
- **内容完善**: 补充现有文档的详细信息
- **错误修正**: 修复文档中的错误和过时信息
- **示例补充**: 添加更多使用示例和教程
- **翻译工作**: 将文档翻译成其他语言

### 贡献者认可

我们会在文档中认可所有贡献者的工作，包括：
- 在README中列出贡献者
- 在相关文档中标注作者信息
- 在发布说明中感谢贡献者

## 联系方式

如果您对文档有任何建议或问题，请通过以下方式联系我们：

- **GitHub Issues**: [提交文档相关问题](https://github.com/TauricResearch/TradingAgents/issues)
- **Discord**: [加入讨论](https://discord.com/invite/hk9PGKShPK)
- **邮箱**: docs@tauric.ai

感谢您对TradingAgents文档建设的关注和支持！
