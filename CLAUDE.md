# CLAUDE.md — TradingAgents-CN 项目记忆

> 此文件由 AI 助手（Trae/Cursor/Claude Code 等）自动加载。
> 后续会话的协作默认遵守以下规则。

## 工作流约定

### 1. 测试落盘规则（2026-06-14 立）

**禁止**：在项目根目录临时写 `verify_*.py` / `test_*.py` / `debug_*.py` 验证后删除。

**应当**：所有验证/测试代码落到 `tests/` 目录，**作为单元测试或集成测试**保留。

落点参考：
- 单元测试：`tests/<模块路径>/test_<被测函数>.py`（如 `tests/tradingagents/agents/researchers/test_bear_researcher_sentinel.py`）
- 集成测试：`tests/integration/test_<场景>.py`（如 `tests/integration/test_china_guba_sentiment.py`）
- 临时调试脚本：`tests/_scratch/<日期>-<描述>.py`（不删除，可重跑）

跑测试：`pytest tests/<路径>::TestClass::test_method -v`

**已整理的 tests/ 结构**（2026-06-14）：
- `tests/_archive/legacy_2026-06-14/`：历史遗留（296 个文件，pytest 忽略）
- `tests/_scratch/`：临时调试（pytest 忽略）
- `tests/{config,dataflows,integration,middleware,services,system,tradingagents,unit,test_tushare_unified}/`：已组织的测试

### 2. PR 流程（2026-06-14 立）

- 一个 commit 对应一个逻辑修复，不要把无关改动混进同一 commit
- 推送目标：`lishinho` fork（`myfork` 远程）→ 上游 `hsliuping/TradingAgents-CN` 的 `main` 分支
- 互有依赖关系的修复**必须分两个 PR**（如 #755 CLI 暴露 social + #756 guba sentiment 接入），并在 PR body 显式声明依赖关系
- 详见 `docs/development/BRANCH_GUIDE.md`

### 3. 关键文档位置

- 设计文档：`docs/bugfix/` / `docs/design/`
- 修复总结：`docs/fixes/`
- 测试指南：`docs/guides/TESTING_GUIDE.md`
- 分支策略：`docs/development/BRANCH_GUIDE.md`

### 4. 数据接口现状（2026-06-14 立）

- A股实时行情：Tushare > BaoStock > AKShare（降级链）
- A股基本财务：`stock_basic_info` 静态（Tushare daily_basic）> 实时计算 > fall-back
- A股股吧情绪：5 个 AKShare 东方财富接口（`tradingagents/dataflows/providers/china/guba_sentiment.py`）
- LLM幻觉防御：研究员节点对空 `sentiment_report` 注入 ⚠️ 数据缺失哨兵
