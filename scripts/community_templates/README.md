# TradingAgents-CN 社区版

基于多智能体协作的 A 股研究辅助系统（Community Edition）。

> 本项目是研究辅助工具，所有 AI 生成内容仅供学习参考，不构成投资建议。

## 核心功能

- **单股研究**：多智能体辩论式分析（5 级深度），多情景观点呈现
- **通用研究**：自然语言提问，研究任意市场主题
- **股票筛选**：自然语言 + 条件筛选，从 6000+ 只股票中发现标的
- **选股助手**：按研究需求描述匹配候选股票池
- **智能助手**：联网搜索 + 工具调用 + 事实记忆
- **AI 记忆**：项目级记忆与事实沉淀
- **Skill 中心**：创建和管理自定义数据获取技能
- **学习中心**：免费系统课程（发现阶段 5 课）
- **模拟交易**：纸面交易与复盘

## 技术栈

- 后端：Python 3.11 / FastAPI / MongoDB / Redis
- 前端：Vue 3 / TypeScript / Element Plus
- 引擎：多智能体协作框架（分析、辩论、复盘）

## 快速开始

```bash
# 1. 克隆
git clone <本仓库地址>
cd TradingAgents-CN

# 2. 后端环境
python -m venv env
env\Scripts\activate            # Windows
pip install -r requirements.txt

# 3. 配置
copy .env.example .env          # 按需填写 LLM API Key 等

# 4. 启动 MongoDB / Redis（本地或 Docker）

# 5. 启动后端
uvicorn app.main:app --port 8002

# 6. 启动前端
cd frontend
npm install
npm run dev
```

详细部署说明见 `docs/` 目录。

## 数据来源

行情与财务数据来自 Tushare / AKShare / Boustick 等公开接口，需自行注册获取 token。

## 免责声明

- 本系统仅支持 A 股市场研究，输出为 AI 生成的研究参考，不构成投资建议
- 不提供目标价、止损止盈、买卖时机等交易指令
- 投资有风险，决策需独立判断

## License

本项目采用 Apache-2.0 许可证，详见 [LICENSE](LICENSE)。
