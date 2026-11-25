# 🤝 贡献者名单

感谢所有为TradingAgents-CN项目做出贡献的开发者和用户！

## 🌟 贡献者分类

### 🐳 Docker容器化功能

- **[@breeze303](https://github.com/breeze303)**
  - 贡献内容：提供完整的Docker Compose配置和容器化部署方案
  - 影响：大大简化了项目的部署和开发环境配置
  - 贡献时间：2025年

### 📄 报告导出功能

- **[@baiyuxiong](https://github.com/baiyuxiong)** (baiyuxiong@163.com)
  - 贡献内容：设计并实现了完整的多格式报告导出系统
  - 技术细节：包括Word、PDF、Markdown格式支持
  - 影响：为用户提供了灵活的分析报告输出选项
  - 贡献时间：2025年

### 🤖 AI模型集成与扩展

- **[@charliecai](https://github.com/charliecai)**
  - 贡献内容：添加硅基流动(SiliconFlow) LLM提供商支持
  - 技术细节：完整的API集成、配置管理和用户界面支持
  - 影响：为用户提供了更多的AI模型选择，扩展了平台的LLM生态
  - 贡献时间：2025年

- **[@yifanhere](https://github.com/yifanhere)**
  - 贡献内容：修复logging_manager.py中的NameError异常
  - 技术细节：添加模块级自举日志器，解决配置文件加载失败时未定义logger变量的问题
  - 影响：修复了系统启动时的关键错误，提升了日志系统的稳定性和可靠性
  - 贡献时间：2025年8月

- **[@kjlintong](https://github.com/kjlintong)**
  - 贡献内容：一键接入大模型服务向导（前端引导页 + 后端配置接口 + 启动脚本）
  - 技术细节：填入API Key → 自动拉取模型列表 → 选择默认模型，全流程前后端联动
  - 影响：大幅降低用户接入LLM的门槛，实现「填Key即用」
  - 贡献时间：2026年11月 ([PR #813](https://github.com/hsliuping/TradingAgents-CN/pull/813))

### 🐛 Bug修复与系统优化

- **[@YifanHere](https://github.com/YifanHere)**
  - **主要贡献**：
    - 🔧 **CLI代码质量改进** ([PR #158](https://github.com/hsliuping/TradingAgents-CN/pull/158))
      - 优化命令行界面的用户体验和错误处理机制
      - 提升了命令行工具的稳定性和用户友好性
      - 贡献时间：2025年
    - 🐛 **关键Bug修复** ([PR #173](https://github.com/hsliuping/TradingAgents-CN/pull/173))
      - 发现并报告了关键的 `KeyError: 'volume'` 问题
      - 提供了详细的问题分析、根因定位和修复方案
      - 显著提升了Tushare数据源的系统稳定性，解决了缓存数据标准化问题
      - 贡献时间：2025年7月
  - **总体影响**：通过多次贡献持续改善项目的稳定性和用户体验

- **[@BG8CFB](https://github.com/BG8CFB)**
  - **主要贡献**：
    - 🐛 修复 GLM 模型无法调用新闻分析的问题 ([PR #457](https://github.com/hsliuping/TradingAgents-CN/pull/457))
      - 修正新闻分析模块与 GLM 模型的适配问题
      - 提升新闻分析功能在 GLM 模型下的可用性与稳定性
      - 贡献时间：2025年11月

- **[@springlin2012](https://github.com/springlin2012)**
  - **主要贡献**：
    - 🐛 AKShare 东财数据源限流自动回退 ([PR #819](https://github.com/hsliuping/TradingAgents-CN/pull/819))
      - 东财接口被限流时自动切换新浪/腾讯备用数据源
      - 失败原因透传给用户端，便于排查
      - 贡献时间：2026年11月

- **[@baishanyue](https://github.com/baishanyue)**
  - **主要贡献**：
    - 🔧 数据源同步健壮性修复 ([PR #822](https://github.com/hsliuping/TradingAgents-CN/pull/822))
      - 裸 `except` 改为 `except Exception`，避免吞掉 KeyboardInterrupt/SystemExit 等系统信号
      - 贡献时间：2026年11月

- **[@guoximin66](https://github.com/guoximin66)**
  - **主要贡献**：
    - 🔧 `.env.example` 配置样例清理 ([PR #816](https://github.com/hsliuping/TradingAgents-CN/pull/816))
      - 修复失效文档链接、去除重复配置项、修复编码损坏字符
      - 贡献时间：2026年11月

### 📐 算法修正与数据质量

- **[@Mattbusel](https://github.com/Mattbusel)**
  - 贡献内容：港股/指数 RSI 算法修正为 Wilder 平滑法
  - 技术细节：内联 30 行 Wilder RSI 算法，移除单作者维护包 fin-primitives 依赖，精度对齐 1e-9
  - 影响：使技术指标与通达信/同花顺等主流行情软件一致，提升分析可信度
  - 贡献时间：2026年11月 ([PR #823](https://github.com/hsliuping/TradingAgents-CN/pull/823))

### 🛡️ 安全贡献

- **[@andesyteoss](https://github.com/andesyteoss)**
  - 贡献内容：负责任地报告日志读取/导出/删除接口的路径穿越漏洞（CWE-22）
  - 技术细节：`../`、`..\`、空字节等穿越载荷可绕过原弱校验读写任意文件
  - 影响：已修复（`_resolve_and_validate` 路径校验 + 三处端点接入），消除任意文件读写风险
  - 贡献时间：2026年11月 ([PR #775](https://github.com/hsliuping/TradingAgents-CN/pull/775))

## 🎯 贡献统计

### 按贡献类型统计


| 贡献类型      | 贡献者数量 | 主要贡献                        |
| ------------- | ---------- | ------------------------------- |
| 🐳 容器化部署 | 1          | Docker配置、部署优化            |
| 📄 功能开发   | 2          | 报告导出系统、一键接入大模型向导(#813) |
| 🤖 AI模型集成 | 3          | 硅基流动LLM提供商支持、日志系统修复、千帆模型集成 |
| 📐 算法修正   | 1          | RSI Wilder 平滑算法(#823)、精度1e-9对齐 |
| 🐛 Bug修复    | 3          | GLM新闻分析修复、AKShare限流回退(#819)、配置样例清理(#816) |
| 🔧 代码优化   | 2          | 命令行界面优化、数据源同步异常处理(#822) |
| 🛡️ 安全贡献   | 1          | 日志接口路径穿越漏洞报告(#775) |

### 

## 🏆 特别贡献奖

### 🥇 最佳持续贡献奖

- **[@YifanHere](https://github.com/YifanHere)** - 通过多个PR持续改善项目质量，包括CLI优化(#158)和关键Bug修复(#173)

### 🥈 最佳功能贡献奖

- **[@baiyuxiong](https://github.com/baiyuxiong)** - 完整的报告导出系统实现

### 🥉 最佳部署优化奖

- **[@breeze303](https://github.com/breeze303)** - Docker容器化部署方案

### 🏅 最佳AI集成贡献奖

- **[@charliecai](https://github.com/charliecai)** - 硅基流动(SiliconFlow) LLM提供商集成
- **[@kjlintong](https://github.com/kjlintong)** - 一键接入大模型服务向导，实现「填Key即用」的零门槛接入体验 (#813)
- **TradingAgents-CN团队** - 百度千帆(Qianfan) ERNIE模型集成，提供OpenAI兼容接口

### 📐 最佳算法贡献奖

- **[@Mattbusel](https://github.com/Mattbusel)** - 港股/指数 RSI 修正为 Wilder 平滑法，使技术指标与主流行情软件一致 (#823)

### 🛠️ 最佳Bug修复贡献奖

- **[@yifanhere](https://github.com/yifanhere)** - 修复了logging_manager.py中的关键NameError异常，通过添加自举日志器解决了系统启动时的核心问题，大幅提升了系统稳定性
- **[@springlin2012](https://github.com/springlin2012)** - AKShare 东财限流自动回退新浪/腾讯数据源，解决生产环境高频事故 (#819)

### 🛡️ 安全贡献奖

- **[@andesyteoss](https://github.com/andesyteoss)** - 负责任地报告日志接口路径穿越漏洞（CWE-22），推动任意文件读写风险及时修复 (#775)

## 🌟 其他贡献

### 📝 问题反馈与建议

- **所有提交Issue的用户** - 感谢您们的问题反馈和功能建议
- **测试用户** - 感谢您们在开发过程中的测试和反馈
- **文档贡献者** - 感谢您们对项目文档的完善和改进

### 🌍 社区推广

- **技术博客作者** - 感谢您们撰写技术文章推广项目
- **社交媒体推广者** - 感谢您们在各平台分享项目信息
- **会议演讲者** - 感谢您们在技术会议上介绍项目

## 🤝 如何成为贡献者

我们欢迎各种形式的贡献：

### 🔧 技术贡献

- **代码贡献**：Bug修复、新功能开发、性能优化
- **测试贡献**：编写测试用例、发现并报告Bug
- **文档贡献**：完善文档、编写教程、翻译内容

### 💡 非技术贡献

- **用户反馈**：使用体验反馈、功能需求建议
- **社区建设**：回答问题、帮助新用户、组织活动
- **推广宣传**：撰写文章、社交媒体分享、会议演讲

### 📋 贡献流程

1. **Fork项目** - 创建项目的个人副本
2. **创建分支** - 为您的贡献创建特性分支
3. **开发测试** - 实现功能并确保测试通过
4. **提交PR** - 提交Pull Request并描述您的更改
5. **代码审查** - 配合维护者进行代码审查
6. **合并发布** - 通过审查后合并到主分支

## 📞 联系方式

如果您想成为贡献者或有任何问题，请通过以下方式联系我们：

- **GitHub Issues**: [提交问题或建议](https://github.com/hsliuping/TradingAgents-CN/issues)
- **GitHub Discussions**: [参与社区讨论](https://github.com/hsliuping/TradingAgents-CN/discussions)
- **Pull Requests**: [提交代码贡献](https://github.com/hsliuping/TradingAgents-CN/pulls)
- 加入到ＱＱ群：782124367

## 🙏 致谢

感谢每一位贡献者的无私奉献！正是因为有了大家的支持和贡献，TradingAgents-CN才能不断发展壮大，为中文用户提供更好的AI金融分析工具。

---

**最后更新时间**: 2026年11月25日
**贡献者总数**: 11位
**总PR数量**: 14个 (Docker化、报告导出、AI模型集成、CLI优化、Bug修复、日志系统修复、GLM新闻分析修复、一键接入大模型向导(#813)、配置样例清理(#816)、AKShare限流回退(#819)、异常处理规范化(#822)、RSI算法修正(#823)、路径穿越安全修复(#775)等)
**活跃贡献者**: 11位
