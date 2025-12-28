<!--
 * @Author: zhengweicheng 46236959+zwczwczwc@users.noreply.github.com
 * @Date: 2025-12-13 17:06:34
 * @LastEditors: zhengweicheng 46236959+zwczwczwc@users.noreply.github.com
 * @LastEditTime: 2025-12-27 00:26:19
 * @FilePath: /TradingAgents-CN-Test/README.md
 * @Description: 这是默认设置,请设置`customMade`, 打开koroFileHeader查看配置 进行设置: https://github.com/OBKoro1/koro1FileHeader/wiki/%E9%85%8D%E7%BD%AE
-->
# TradingAgents 中文增强版

[![License](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)
[![Python](https://img.shields.io/badge/Python-3.10%2B-blue.svg)](https://www.python.org/)
[![Version](https://img.shields.io/badge/Version-v1.0.0--preview-green.svg)](./VERSION)
[![Documentation](https://img.shields.io/badge/docs-中文文档-green.svg)](./docs/)
[![Original](https://img.shields.io/badge/基于-TauricResearch/TradingAgents-orange.svg)](https://github.com/TauricResearch/TradingAgents)

面向中文用户的**多智能体与大模型股票分析学习平台**。帮助你系统化学习如何使用多智能体交易框架与 AI 大模型进行合规的股票研究与策略实验。

**🎯 定位与使命**: 专注学习与研究，提供中文化学习中心与工具，合规友好，支持 A股/港股/美股 的分析与教学，推动 AI 金融技术在中文社区的普及与正确使用。

---

## 🚀 核心业务升级：指数级全维分析 (P0 需求)

本项目在原有个股分析的基础上，进行了重大业务逻辑扩展，引入了全新的**指数/大盘分析 Workflow**，实现了从"点"（个股）到"面"（宏观市场）的跨越。

### 🎯 六大核心特性

1.  **专业分析团队模拟**
    *   **宏观分析师**: 深度分析GDP、CPI、PMI等宏观指标及经济周期
    *   **政策分析师**: 解读国家战略、财政/货币政策及产业支持政策
    *   **板块分析师**: 分析板块资金流向、热点主题及行业轮动
    *   **国际新闻分析师**: 监控国际舆情、地缘政治及外部冲击
    *   **技术分析师**: 基于量化指标（MA, MACD, RSI等）进行趋势研判
    *   **多空辩论组**: 模拟市场上多头与空头的观点博弈，挖掘潜在风险与机会
    *   **策略顾问**: 综合各方观点，给出最终的仓位建议、分层配置及动态调整策略

2.  **并行执行架构 (Parallel Execution)**
    *   重构了底层图计算引擎，支持**Fan-out/Fan-in (扇出/扇入)** 模式
    *   **效率提升**: 将原本串行的分析流程改为并行执行，分析速度提升 3-4 倍
    *   **动态调度**: 基于任务类型（个股 vs 指数）动态构建执行图

3.  **深度/快速双模式**
    *   **快速模式**: 仅通过宏观与技术面快速扫描市场状态
    *   **深度模式**: 启动全量 Agent，包含国际新闻检索、多轮辩论与风险深度评估

4.  **多空博弈决策机制**
    *   **多头研究员**: 挖掘目标指数的积极因素，主张增加仓位
    *   **空头研究员**: 挖掘目标指数的风险因素，主张降低仓位
    *   **循环辩论**: 引入多轮辩论机制，确保真理越辩越明
    *   **深度决策报告**: 包含辩论综述、决策逻辑和具体调仓建议

5.  **混合数据源架构**
    *   **高可用数据层**: Tushare Pro为主源，AKShare为辅，构建多级降级链
    *   **实时监控引擎**: 支持秒级数据穿透，适应盘中决策需求
    *   **分时决策体系**: 支持早盘、尾盘、盘后三种分析模式

6.  **动态Agent选择**
    *   **模块化分析**: 用户可选择特定分析模块（如只关注宏观政策）
    *   **成本优化**: 跳过不必要的分析步骤，大幅减少 Token 消耗
    *   **灵活配置**: 支持前端实现"自定义指数分析报告"功能

---

## 📊 指数分析Workflow演进历程

### v2.0.0 - 基础构建 (Foundation)
**核心目标**: 构建指数分析的基础框架，实现核心Agent节点
- 实现了 Macro, Policy, Sector, Strategy 四大核心Agent
- 集成 AKShare 数据源，支持宏观、政策、板块数据的获取
- 实现了基于 MongoDB 的数据缓存与降级机制
- 确立了线性的工作流路由机制

### v2.1.0 - 架构优化 (Architecture Optimization)  
**核心目标**: 实现职责分离架构，优化决策机制
- **新增 International News Analyst**: 引入国际视野，弥补信息盲区
- **Policy Analyst 扩展**: 区分长期战略政策与短期政策利好
- **Strategy Advisor 重构**: 引入统一决策算法，实现双层仓位决策
- **输出增强**: 提供分层持仓策略和动态调整触发条件

### v2.2.0 - 数据源优化与实时决策 (Data Source & Realtime)
**核心目标**: 增强数据底座，支持实盘辅助决策
- **混合数据架构**: 引入 Tushare Pro 为主源，AKShare 为辅
- **Technical Analyst**: 新增独立的技术分析Agent
- **分时决策体系**: 支持早盘、尾盘、盘后三种分析模式
- **实时监控引擎**: 支持秒级数据穿透，适应盘中决策需求

### v2.3.0 - 多空博弈与深度决策 (Bull/Bear Debate)
**核心目标**: 引入多空博弈机制，提升决策的辩证深度
- **多空辩论层**: 新增 Index Bull/Bear Researcher
- **决策深度优化**: Strategy Advisor 必须综合辩论双方观点
- **报告增强**: 策略报告包含辩论总结与胜负手分析
- **Workflow升级**: 引入循环辩论机制

### v2.4.0 - 流程优化与并行化 (Process Optimization)
**核心目标**: 提升分析效率和灵活性
- **动态Agent选择**: 支持模块化分析，用户可自定义分析组合
- **并行执行**: 宏观、政策、技术面等独立分析并行运行
- **数据预验证**: 增加指数代码格式检查和数据源可用性检查
- **风险评估层**: 引入独立的风险评估环节

---

## 🎉 v1.0.0-preview 技术架构升级

为了支撑更复杂的业务流程，我们将底层架构进行了全面重构，带来企业级的性能体验。

### 🏗️ 全新技术架构
- **后端升级**: 从 Streamlit 迁移到 **FastAPI**，提供更强大的 RESTful API 和异步处理能力
- **前端重构**: 采用 **Vue 3 + Element Plus**，打造响应式、现代化的单页应用 (SPA)
- **数据库优化**: **MongoDB + Redis** 双数据库架构，读写性能提升 10 倍，支持复杂查询与缓存
- **容器化部署**: 完整的 Docker 多架构支持（amd64 + arm64），一键部署

### 🎯 企业级功能支持
- **用户权限管理**: 完整的用户认证、角色管理、操作日志系统
- **配置管理中心**: 可视化的大模型配置、数据源管理、系统设置
- **实时通知系统**: SSE + WebSocket 双通道推送，实时跟踪分析进度
- **多数据源路由**: 统一的数据源管理，支持 Tushare、AkShare、BaoStock 自动切换

---

### 🚀 快速开始

#### 1. 启动后端服务
确保已安装 Docker 和 Python 环境。

```bash
# 启动 Redis 和 MongoDB
docker start tradingagents-redis tradingagents-mongo

# 启动后端 API 服务
python -m app.main
```

#### 2. 运行指数分析
使用提供的脚本直接调用后端接口进行分析。

```bash
# 分析半导体指数 (H30184.CSI)
python scripts/download_index_report.py --index 半导体 --depth 深度

# 快速分析模式
python scripts/download_index_report.py --index 沪深300 --depth 快速

# 自定义分析模块
python scripts/download_index_report.py --index 创业板 --analysts macro,technical --depth 标准
```

#### 3. 查看报告
分析完成后，报告将自动保存为 PDF 和 Markdown 格式，通常位于项目根目录下。

⚠️ **重要提醒**: 在分析股票之前，请按相关文档要求，将股票数据同步完成，否则分析结果将会出现数据错误。

---

## 📚 核心功能使用指南

### 深度分析级别 (Research Depth)
系统支持5级深度分析，根据分析需求选择合适的级别：

| 深度级别 | 辩论轮次 | 风险讨论 | 记忆功能 | 适用场景 |
|---------|---------|---------|---------|---------|
| **1级 (快速)** | 1轮 | 1轮 | ❌ 关闭 | 基础扫描、日常监控 |
| **2级 (基础)** | 1轮 | 1轮 | ✅ 开启 | 常规分析、趋势判断 |
| **3级 (标准)** | 1轮 | 2轮 | ✅ 开启 | 投资决策、中等风险 |
| **4级 (深度)** | 2轮 | 2轮 | ✅ 开启 | 重要决策、高置信度 |
| **5级 (全面)** | 3轮 | 3轮 | ✅ 开启 | 战略配置、极高要求 |

### 支持的主流指数
- **A股主要指数**: 沪深300 (000300.SH), 上证50 (000016.SH), 中证500 (000905.SH)
- **行业板块指数**: 半导体 (H30184.CSI), 新能源 (399808.SZ), 医药 (399441.SZ)
- **港股指数**: 恒生指数 (HSI), 恒生科技指数 (HSTECH)
- **美股指数**: 纳斯达克100 (NDX), 标普500 (SPX)

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

---

## 🔗 相关资源

- [项目文档](./docs/) - 详细的技术文档和使用指南
- [P0需求文档](./文档/P0需求一：指数分析workflow/) - 指数分析workflow的完整需求说明
- [版本演进](./文档/项目说明/项目总览与版本演进.md) - 项目发展历程和版本变更记录
- [问题反馈](https://github.com/zwczwczwc/TradingAgents-CN/issues) - 提交bug报告和功能建议

**📞 技术支持**: 如有技术问题，请通过GitHub Issues或项目文档中的联系方式获取支持。
