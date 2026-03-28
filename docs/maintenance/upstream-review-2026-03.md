# 上游更新调研（2026-03）

本文档用于记录 `TauricResearch/TradingAgents` 在中文仓库分叉后、尤其是 2026 年初以来的重要公开更新，并评估哪些值得在 `TradingAgents-CN` 中回补。

## 1. 调研范围

- 调研时间：2026-03-28
- 上游仓库：`TauricResearch/TradingAgents`
- 中文仓库：`hsliuping/TradingAgents-CN`
- 主要参考：
  - GitHub 仓库首页
  - GitHub 提交历史

## 2. 两个仓库当前节奏

### 上游仓库

上游 `main` 在 2026-03-22 仍有公开提交，最近里程碑包括：

- `TradingAgents v0.2.0`（2026-02-04）
- `TradingAgents v0.2.1`（2026-03-15）
- `TradingAgents v0.2.2`（2026-03-22）

### 中文仓库

中文仓库公开主线最近提交到：

- 2026-02-14：`去掉没有引用的包`

在此之前，2025-11 有一整批围绕：

- Docker 下新闻抓取
- 事件循环冲突
- AKShare 新闻反爬
- 统一新闻工具与自动同步

的连续提交。

结论：

- 中文仓库不是“机械跟随上游”
- 更像是在中文市场、前后端一体化、Mongo/Redis/Web UI、多数据源与本地部署方向上独立发展
- 上游在 2026 年的核心更新，中文仓库**并没有自动同步进来**

## 3. 上游 2026 年初以来的重要更新

以下是我认为最值得关注的上游公开更新。

### 3.1 v0.2.0 阶段

时间点：

- 2026-02-04：`TradingAgents v0.2.0: Multi-Provider LLM Support & Optimizations`
- 2026-02-07：构建系统迁移到 `pyproject.toml`

相关更新包括：

- 多 LLM Provider 支持增强
- 构建系统配置补全
- 依赖从 `setup.py` 向 `pyproject.toml` 整理
- 安全补丁：`langchain-core` 漏洞修补

### 3.2 v0.2.1 阶段

时间点：

- 2026-03-15：`v0.2.1`

关键更新包括：

- `fix: add http_client support for SSL certificate customization`
- `fix: harden stock data parsing against malformed CSV and NaN values`
- `fix: handle comma-separated indicators in get_indicators tool`
- `fix: initialize all debate state fields in propagation.py`
- `fix: add explicit UTF-8 encoding to all file open() calls`
- `fix: pass debate round config to ConditionalLogic`
- `chore: remove unused chainlit dependency (CVE-2026-22218)`

### 3.3 v0.2.2 阶段

时间点：

- 2026-03-22：`v0.2.2`

关键更新包括：

- `fix: use OpenAI Responses API for native models`
- `feat: add Anthropic effort level support for Claude models`
- `fix: add exponential backoff retry for yfinance rate limits`
- `fix: preserve exchange-qualified tickers across agent prompts`
- `refactor: five-tier rating scale and streamlined agent prompts`
- `refactor: standardize portfolio manager, five-tier rating scale, fix analyst status tracking`
- `fix: set process-level UTF-8 default for cross-platform consistency`
- `fix: handle list content when writing report sections`
- `chore: consolidate install, fix CLI portability, normalize LLM responses`

## 4. 对中文仓库的意义

## 4.1 已经被中文仓库自行覆盖的方向

中文仓库当前已经在下列方向上走得比上游更深：

- 前后端分离 Web 系统
- MongoDB / Redis / 用户体系 / 配置管理
- 多市场支持（A 股 / 港股 / 美股）
- A 股数据源（AKShare / Tushare 等）
- 报告导出、任务中心、同步历史、数据清理
- 中文提示词、中文报告、多模型配置管理

因此，上游很多“工程化基础搭建”并不能直接替换中文仓库现状。

### 4.2 值得优先回补的上游能力

我把值得回补的上游更新分成三档。

#### 第一优先级：建议尽快评估吸收

1. `OpenAI Responses API for native models`

原因：

- 中文仓库当前分析报告阶段已经在处理长文本、流式与超时问题
- 如果上游把“原生模型 -> Responses API”这条链路处理得更稳，这对长报告稳定性有直接价值
- 这不是 UI 功能，而是核心调用链能力

2. `yfinance rate limit exponential backoff`

原因：

- 中文仓库当前港股 / 美股仍大量依赖 `yfinance`
- 我们自己近期也遇到过港股实时行情部分成功、刷新不一致、数据兜底口径等问题
- 上游这条修复与中文仓库现状高度相关

3. `exchange-qualified tickers`

原因：

- 中文仓库已经有多市场、多交易所、多代码格式问题
- 上游专门修这个，说明他们在 agent prompt 透传 ticker 身份时踩过坑
- 这类问题在港股 / 美股 / 多地上市股票上尤其重要

#### 第二优先级：值得择机吸收

4. `Anthropic effort level support`

原因：

- 中文仓库已有多模型配置体系
- 如果后续继续支持 Claude 系列，这条能力有配置价值
- 但当前你主要用 GPT 路线，这不是最急迫项

5. `malformed CSV / NaN parsing hardening`

原因：

- 中文仓库有大量多源数据适配
- 数据脏值、空值、异常格式很常见
- 这类修复通常收益稳定、冲突较小

6. `comma-separated indicators` / `debate round config` / `initialize all debate state fields`

原因：

- 都属于图执行、工具参数与 debate 状态稳定性修复
- 对分析流程的边缘稳定性有帮助

#### 第三优先级：需要谨慎，不建议直接照搬

7. `five-tier rating scale` / `portfolio manager standardization`

原因：

- 这会直接影响上游决策链、提示词和输出结构
- 中文仓库当前有自己的分析页面、报告展示、任务进度和中文输出规范
- 直接照搬很容易引入兼容性回归

8. `install consolidation / CLI portability / pyproject-only packaging`

原因：

- 中文仓库已经是前后端分离、多脚本、多部署路径的形态
- 上游 CLI 项目的安装方式不能直接套进中文仓库
- 这类更新只适合局部借鉴，不适合整体迁移

## 5. 中文仓库当前明显未对齐的上游点

结合仓库内搜索结果，当前中文仓库中**没有明显看到**以下上游新能力已经被系统性吸收：

- 原生 OpenAI 模型统一切到 Responses API
- Claude effort level / thinking effort 之类的正式支持
- `exchange-qualified tickers` 的完整贯穿
- `yfinance` 的统一指数退避限流重试实现
- 上游新的五档评级口径

相对而言，以下方向中文仓库已有部分覆盖或替代实现：

- UTF-8 编码处理：仓库中已大量显式使用 `encoding='utf-8'`
- 多 Provider 配置：中文仓库已自行实现更重的配置管理与前端 UI
- 安装脚本与依赖整理：中文仓库有自己的本地部署脚本体系

## 6. 推荐动作

如果后续要继续对齐上游，我建议按以下顺序：

1. 先看上游 `Responses API` 这条链路
   - 目标：提升长文本报告稳定性

2. 再看 `yfinance` 指数退避与 ticker 透传
   - 目标：提升港股 / 美股行情链路稳定性

3. 最后再评估 Anthropic effort 与五档评级体系
   - 前者是模型能力增强
   - 后者属于行为层变更，风险更高

## 7. 当前判断

截至 2026-03-28，我的判断是：

- 上游在中文仓库分叉后，**确实还有值得关注的重要更新**
- 这些更新主要集中在：
  - LLM 调用链现代化
  - 多市场 ticker 身份稳定性
  - `yfinance` 稳定性
  - 状态机/解析边界修复
- 中文仓库并不是简单落后，而是**在完全不同的产品方向上走得更远**
- 因此后续同步不应追求“全量跟上游”，而应采用“按价值点回补”的策略
