# TradingAgents-CN 社区版（Community Edition）

**English**: TradingAgents-CN Community Edition is an open-source (Apache-2.0) multi-agent stock research assistant for the Chinese A-share market. It orchestrates LLM-based analyst agents for debate-style research, natural-language stock screening, paper trading and study courses. For learning and research only — **not investment advice**.

[![License](https://img.shields.io/badge/License-Apache--2.0-blue.svg)](./LICENSE)
[![Python](https://img.shields.io/badge/Python-3.11-blue.svg)](https://www.python.org/)
[![Vue](https://img.shields.io/badge/Vue-3-brightgreen.svg)](https://vuejs.org/)

基于多智能体协作的 A 股研究辅助系统。由多个扮演不同角色（大盘/板块/市场/基本面/新闻分析师，乐观/审慎研究员等）的 AI 智能体协作完成研究流程，帮助你系统化学习多智能体框架与 AI 大模型在股票研究中的应用。

> 本项目是研究辅助工具，所有 AI 生成内容仅供学习参考，**不构成投资建议**。

## 核心功能

- **单股研究**：多智能体辩论式分析（5 级深度），多情景观点呈现
- **通用研究**：自然语言提问，研究任意市场主题
- **股票筛选**：自然语言 + 条件筛选，从 6000+ 只股票中发现标的
- **选股助手**：按研究需求描述匹配候选股票池
- **智能助手**：联网搜索 + 工具调用 + 事实记忆
- **AI 记忆**：项目级记忆与事实沉淀
- **Skill 中心**：创建和管理自定义数据获取技能
- **学习中心**：免费系统课程（发现阶段 5 课）+ 8 篇学习指南
- **模拟交易**：纸面交易与复盘

## 社区版与 Pro 版的差异

| 能力 | 社区版 | Pro 版 |
|------|:------:|:------:|
| 单股研究 / 通用研究 / 股票筛选 | ✅ | ✅ |
| 学习中心（免费课程） / 模拟交易 / Skill 中心 | ✅ | ✅ |
| Agent 工作坊（创建、发布、管理自定义 Agent） | — | ✅ |
| 交易系统（策略创建 / 优化 / 模板调试） | — | ✅ |
| 定时分析 / 批量分析 | — | ✅ |
| 专业报告导出（Word / PDF 多格式） | — | ✅ |
| 高级课程（进阶 8 阶段） | — | ✅ |
| 许可 | Apache 2.0 开源 | 商业许可 |

Pro 版面向有更高阶研究工作流需求的用户，获取方式见项目主页或联系作者。

## 快速开始

### 环境要求

- Python 3.11
- Node.js 18+
- MongoDB 与 Redis（本地或 Docker）

### 启动步骤

```bash
# 1. 克隆
git clone <本仓库地址>
cd TradingAgents-CN

# 2. 后端环境（Python 3.11）
python -m venv env
env\Scripts\activate            # Windows
source env/bin/activate         # Linux / macOS
pip install -r requirements.txt

# 3. 配置（必填 MongoDB / Redis / JWT_SECRET，详见 .env.example 注释）
copy .env.example .env          # Windows
cp .env.example .env            # Linux / macOS

# 4. 启动 MongoDB / Redis（本地或 Docker，账号密码与 .env 保持一致）

# 5. 启动后端（默认 8000 端口，与前端默认代理一致）
uvicorn app.main:app

# 6. 启动前端
cd frontend
npm install
npm run dev                     # 默认 http://localhost:3000
```

首次使用请先在系统设置中配置大模型 API Key（OpenAI / DeepSeek / 通义千问等），并按需配置行情数据 Token。

## 文档

- 用户手册：[docs/02-user-guide/user-manual-v3.0.md](docs/02-user-guide/user-manual-v3.0.md)
- 学习指南：[docs/02-user-guide/](docs/02-user-guide/)（learning-01 ~ 08）
- 免费课程：[docs/07-courses/v3.0/phase-01-discover/](docs/07-courses/v3.0/phase-01-discover/)

## 数据来源

行情与财务数据来自 [Tushare](https://tushare.pro/) / [AKShare](https://github.com/akfamily/akshare) / [BaoStock](https://www.baostock.com/) 等公开接口，需自行注册获取 token。

## 参与贡献

欢迎通过 Pull Request 参与共建——**PR 是唯一的考察方式**：修 Bug、完善文档、适配数据源、讨论功能方向都算贡献。详见 [CONTRIBUTING.md](CONTRIBUTING.md)（含贡献者协议 CLA 说明）。

## 免责声明

- 本系统仅支持 A 股市场研究，输出为 AI 生成的研究参考，不构成投资建议
- 不提供目标价、止损止盈、买卖时机等交易指令
- 投资有风险，决策需独立判断

## License

本项目采用 [Apache-2.0](LICENSE) 许可证。提交贡献即表示同意签署 [贡献者许可协议（CLA）](CONTRIBUTING.md)。

## 致谢

- [Tauric Research / TradingAgents](https://github.com/TauricResearch/TradingAgents) — 多智能体交易框架原版项目
- 所有通过 PR 参与共建的贡献者
