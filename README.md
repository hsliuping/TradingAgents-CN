<!--
 * @Author: zhengweicheng 46236959+zwczwczwc@users.noreply.github.com
 * @Date: 2025-12-13 17:06:34
 * @LastEditors: zhengweicheng 46236959+zwczwczwc@users.noreply.github.com
 * @LastEditTime: 2025-12-24 00:07:50
 * @FilePath: /TradingAgents-CN-Test/README.md
 * @Description: 这是默认设置,请设置`customMade`, 打开koroFileHeader查看配置 进行设置: https://github.com/OBKoro1/koro1FileHeader/wiki/%E9%85%8D%E7%BD%AE
-->
# TradingAgents 中文增强版

[![License](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)
[![Python](https://img.shields.io/badge/Python-3.10%2B-blue.svg)](https://www.python.org/)
[![Version](https://img.shields.io/badge/Version-cn--0.1.15-green.svg)](./VERSION)
[![Documentation](https://img.shields.io/badge/docs-中文文档-green.svg)](./docs/)
[![Original](https://img.shields.io/badge/基于-TauricResearch/TradingAgents-orange.svg)](https://github.com/TauricResearch/TradingAgents)

面向中文用户的**多智能体与大模型股票分析学习平台**。帮助你系统化学习如何使用多智能体交易框架与 AI 大模型进行合规的股票研究与策略实验。

**🎯 定位与使命**: 专注学习与研究，提供中文化学习中心与工具，合规友好，支持 A股/港股/美股 的分析与教学，推动 AI 金融技术在中文社区的普及与正确使用。

---

## 🚀 核心业务升级：指数级全维分析 (P0 需求)

本项目在原有个股分析的基础上，进行了重大业务逻辑扩展，引入了全新的**指数/大盘分析 Workflow**，实现了从"点"（个股）到"面"（宏观市场）的跨越。

### � 三大核心特性

1.  **宏观与指数分析 Workflow**
    *   新增 **宏观经济分析师**：实时跟踪 GDP、CPI、利率等宏观指标。
    *   新增 **政策解读分析师**：深度解读财政、货币及产业政策对市场的影响。
    *   新增 **国际地缘分析师**：监控全球地缘政治事件及外围市场波动。
    *   新增 **多空博弈辩论**：引入红蓝对抗机制，模拟市场上多头与空头的激烈观点碰撞，最终由裁判给出客观结论。

2.  **并行执行架构 (Parallel Execution)**
    *   重构了底层图计算引擎，支持**Fan-out/Fan-in (扇出/扇入)** 模式。
    *   **效率提升**：将原本串行的分析流程（如：市场->社媒->新闻->基本面）改为并行执行，分析速度提升 3-4 倍。
    *   **动态调度**：基于任务类型（个股 vs 指数）动态构建执行图。

3.  **深度/快速双模式**
    *   **快速模式**：仅通过宏观与技术面快速扫描市场状态。
    *   **深度模式**：启动全量 Agent，包含国际新闻检索、多轮辩论与风险深度评估。

### 🆚 业务能力对比

| 特性 | 源项目 (TradingAgents) | **本项目 (TradingAgents-CN 增强版)** |
| :--- | :--- | :--- |
| **核心场景** | 个股分析 (Stock Analysis) | **个股分析 + 指数/大盘分析 (Index Analysis)** |
| **分析维度** | 基本面、技术面、情绪面 | 新增 **宏观经济、产业政策、国际地缘、多空博弈** |
| **决策机制** | 线性汇总 (Linear Aggregation) | **对抗式辩论 (Debate) + 风险裁判 (Risk Judge)** |
| **执行架构** | 串行执行 | **并行执行 (Parallel Execution) + 动态调度** |
| **实效性** | 盘后分析为主 | **支持盘中实时快照 (早盘/尾盘决策)** |

---

## 🎉 v1.0.0-preview 技术架构升级

为了支撑更复杂的业务流程，我们将底层架构进行了全面重构，带来企业级的性能体验。

### 🏗️ 全新技术架构
- **后端升级**: 从 Streamlit 迁移到 **FastAPI**，提供更强大的 RESTful API 和异步处理能力。
- **前端重构**: 采用 **Vue 3 + Element Plus**，打造响应式、现代化的单页应用 (SPA)。
- **数据库优化**: **MongoDB + Redis** 双数据库架构，读写性能提升 10 倍，支持复杂查询与缓存。
- **容器化部署**: 完整的 Docker 多架构支持（amd64 + arm64），一键部署。

### 🎯 企业级功能支持
- **用户权限管理**: 完整的用户认证、角色管理、操作日志系统。
- **配置管理中心**: 可视化的大模型配置、数据源管理、系统设置。
- **实时通知系统**: SSE + WebSocket 双通道推送，实时跟踪分析进度。
- **多数据源路由**: 统一的数据源管理，支持 Tushare、AkShare、BaoStock 自动切换。

---

## 📥 安装部署

**三种部署方式，任选其一**：

| 部署方式 | 适用场景 | 难度 | 文档链接 |
|---------|---------|------|---------|
| 🟢 **绿色版** | Windows 用户、快速体验 | ⭐ 简单 | [绿色版安装指南](https://mp.weixin.qq.com/s/eoo_HeIGxaQZVT76LBbRJQ) |
| 🐳 **Docker版** | 生产环境、跨平台 | ⭐⭐ 中等 | [Docker 部署指南](https://mp.weixin.qq.com/s/JkA0cOu8xJnoY_3LC5oXNw) |
| 💻 **本地代码版** | 开发者、定制需求 | ⭐⭐⭐ 较难 | [本地安装指南](https://mp.weixin.qq.com/s/cqUGf-sAzcBV19gdI4sYfA) |

⚠️ **重要提醒**：在分析股票之前，请按相关文档要求，将股票数据同步完成，否则分析结果将会出现数据错误。

---

## 🙏 致敬与鸣谢

本项目是基于 [Tauric Research](https://github.com/TauricResearch) 团队创造的革命性多智能体交易框架 [TradingAgents](https://github.com/TauricResearch/TradingAgents) 开发的增强版本。

感谢 Tauric Research 团队的开源精神与卓越贡献！虽然 Apache 2.0 协议赋予了我们自由使用源码的权利，但我们深知每一行代码背后的智慧与汗水，将永远铭记并感谢您们的无私付出。

---

## ⚠️ 风险提示

**重要声明**: 本框架仅用于研究和教育目的，不构成投资建议，不提供任何实盘交易接口。

- 📊 交易表现可能因多种因素而异
- 🤖 AI模型的预测存在不确定性
- 💰 投资有风险，决策需谨慎
- 👨‍💼 建议咨询专业财务顾问
