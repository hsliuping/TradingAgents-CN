# TradingAgents-CN 文档中心

> 本文档体系按"产品发展、迭代、开发"三层规划，服务于不同角色的读者。
>
> **当前版本：v3.0** | [版本号管理规范](#版本号管理规范)

## 文档体系总览

| 层级 | 目录 | 面向角色 | 说明 |
|------|------|---------|------|
| 产品层 | [01-product](./01-product/) | 所有人 | 产品定位、路线图、发布说明、版本对比 |
| 用户层 | [02-user-guide](./02-user-guide/) | 最终用户 | 安装、配置、功能使用、进阶指南 |
| 开发层 | [03-development](./03-development/) | 开发者 | 架构设计、API 文档、开发指南、开发流程 |
| 运维层 | [04-operations](./04-operations/) | 运维人员 | 部署、数据库、监控、故障排查 |
| 设计层 | [05-design](./05-design/) | 产品/架构师 | **按版本号管理**：v3.0/v4.0/v5.0 |
| 知识层 | [06-knowledge](./06-knowledge/) | 全体成员 | 经验教训、Bug 编年史、合规要求 |
| 课程层 | [07-courses](./07-courses/) | 用户/学员 | 高级交易课程（24 课） |
| 博客层 | [08-blog](./08-blog/) | 所有人 | 技术博客、版本发布博客 |
| 归档区 | [99-archive](./99-archive/) | 历史参考 | **按版本号归档**：v0.1.x/v1.0.x/v2.0/v2.1 |

## 快速导航

### 完整使用手册

- [v4.0 操作手册（4.0.0-beta.1）](./02-user-guide/user-manual-v4.0.md) ⭐ 当前版本：三档深度 / 方法论板块 / 五行业工作台为核心章
- [v3.0 完整使用手册（标准版）](./02-user-guide/user-manual-v3.0.md)（前代版本）
- [v3.0 京东云合作版使用手册](./02-user-guide/jdyun-user-manual-v3.0.md) ⭐ 京东云版用户专用

### 新用户入门
0. [v4.0 系统介绍（产品宣传）](./01-product/v4.0-system-introduction.md) ⭐ 盈亏双轨产品论点、三档研究漏斗、价值层三件、减损侧六机制、行业工作台矩阵
   - [v3.0 系统介绍（技术文档版）](./01-product/v3.0-system-introduction.md)
   - [v3.0 系统介绍（公众号传播版）](./01-product/v3.0-system-introduction-for-wechat.md)
   - [专业版（Expert Edition）产品定位](./01-product/expert-edition-positioning.md) ⭐ 四层产品矩阵（社区/Pro/专业/京东云）、专业版功能边界与授权决策、传播计划绑 roadmap 波次
   - [Pro 版 vs 专业版对比页](./01-product/comparison/pro-vs-expert.md) 面向存量用户的升级转化，功能口径以专业版定位文档为唯一依据
1. [快速开始](./02-user-guide/getting-started/quick-start.md)
2. [安装指南](./02-user-guide/getting-started/installation.md)
3. [Docker 安装使用指南](./02-user-guide/getting-started/docker-installation-guide.md)
4. [数据库配置](./02-user-guide/getting-started/database-setup.md)
5. [LLM 配置](./02-user-guide/configuration/llm-config.md)
6. [数据源配置](./02-user-guide/configuration/config-guide.md)

### 功能使用
- [个股分析](./02-user-guide/features/stock-analysis.md)
- [模拟交易（虚拟学习环境）](./02-user-guide/features/paper-trading.md)
- [持仓分析](./02-user-guide/features/portfolio-analysis.md)
- [定时分析](./02-user-guide/features/scheduled-analysis.md)
- [报告导出](./02-user-guide/features/report-export.md)
- **行业研究工作台 · 怎么看**（每个行业看什么 / 口径 / 验证逻辑）
  - [总索引与统一约定](./02-user-guide/industry-workbenches/README.md)
  - [猪周期怎么看](./02-user-guide/industry-workbenches/pig-cycle.md)
  - [保险怎么看](./02-user-guide/industry-workbenches/insurance.md)
  - [电池怎么看](./02-user-guide/industry-workbenches/battery.md)
  - [汽车怎么看](./02-user-guide/industry-workbenches/auto.md)
  - [银行怎么看](./02-user-guide/industry-workbenches/bank.md)

### 进阶功能
- [Agent 工坊](./02-user-guide/advanced/prompt-management.md)
- [提示词管理](./02-user-guide/advanced/prompt-management.md)
- [QMT 对接](./02-user-guide/advanced/qmt-usage.md)

### 开发者
- [开发环境搭建](./03-development/getting-started/setup.md)
- [项目结构](./03-development/getting-started/project-structure.md)
- [系统架构](./03-development/architecture/system-overview.md)
- [API 文档](./03-development/api/)
- [开发流程](./03-development/workflow/development-workflow.md)
- [分支策略](./03-development/workflow/branch-guide.md)
- [Git 分支状态与关系](./03-development/workflow/git-branch-status.md) ⭐ 活跃分支关系图、v4.0 双线交替策略（升级线/行业内容线）、合流去向与归档清单
- [京东云对接指南](./03-development/guides/jdyun-integration-guide.md) ⭐ 京东云工程师专用

### 运维部署
- [Docker 部署](./04-operations/deployment/docker-deployment-guide.md)
- [Windows 便携版](./04-operations/deployment/windows-portable.md)
- [数据库运维](./04-operations/database/)
- [故障排查](./04-operations/troubleshooting/)

### 产品演进（按版本号管理）
- **[v3.0（当前版本）](./05-design/v3.0/)** - 当前发布版本的设计文档
  - [京东云合作版定制设计](./05-design/v3.0/jdyun-edition-design.md)
  - [京东云登录认证设计](./05-design/v3.0/jdyun-auth-design.md)
  - [v3.6.0 社区版开源分离方案](./05-design/v3.0/v3.6.0-community-edition-separation-plan.md)
  - [估值测算 Excel 交付物设计（声明式交付物）](./05-design/v3.0/valuation-excel-deliverable-design.md)
  - [智能助手质量架构重构设计（A11）](./05-design/v3.0/assistant-quality-architecture-refactor.md) ⭐ 统一质量出口/证据集/路径注册表，终结"发现一个修一个"模式
- **[v4.0（下一版本）](./05-design/v4.0/)** - 下一版本规划
  - [v4.0 总设计：从分析工具到行业研究系统](./05-design/v4.0/v4.0-master-plan.md) ⭐ 纲领文档：产品+技术差距总表（P1-P6/T1-T6）、分析流程 9 点优化、LangGraph 能力启用、三波落地路径
  - [v4.0 主线进度追踪（执行台账）](./05-design/v4.0/v4.0-progress-tracker.md) 各任务完成状态、commit 证据与剩余缺口的唯一事实源；每完成一项工作必须同步更新
  - [现状与远期目标映射（基准文档）](./05-design/v4.0/current-state-and-vision-mapping.md) ⭐ 三层架构定位、代码现状盘点、目标修订记录（R1-R8）与四泳道统一路线图
  - [数据口径管理规范](./05-design/v4.0/data-conventions.md) ⭐ 猪周期信源分层（官方/人工参考/推算/日频）、使用场景与校验规则的唯一权威
  - [行业研究工作台功能基线（PRD）](./05-design/v4.0/industry-workbench-baseline.md) ⭐ 五层功能模型与 P0 验收清单：新行业工作台（数据页签/治理页/我的研究/我的资料）上线必查，终结"建完才发现缺研究功能"
  - [行业工作台统一框架与跨系统集成规范](./05-design/v4.0/industry-workbench-integration-spec.md) ⭐ P0 七项之外的 6 类跨系统集成（智能助手工具/个股摘要卡/工作台互引/持仓复盘/持仓分析/治理页）：新行业上线完整交付边界 + S0-S6 接入流程与检查清单
  - [行业工作台全行业覆盖排期](./05-design/v4.0/industry-roadmap.md) 两周一行业、一年 26 slot 的全行业排期：20 个新行业分四波次（新能源/地产基建/科技消费/金融）、观察池与 M0/P0 双门禁
  - [行业工作台传导关系登记设计](./05-design/v4.0/transmission-registry.md) 政策冲击跨行业传导结构化：传导边（方向/变量/时滞）登记 + 政策事件映射 + 链路自动展开，与 P0-6 互引兼容的叠加层
  - [五档分析画像体系重构设计](./05-design/v4.0/analysis-depth-profiles-refactor.md) ⭐ DEPTH_PROFILES 单一注册表：档位结构性差异（流程环节/产出规范/工具预算/模型/数据面），终结"选哪档报告都一样"；2026-11-04 已简化为三档（快速1/标准3/深度5）
  - [五档分析画像体系重构实施设计](./05-design/v4.0/analysis-depth-profiles-implementation.md) 文件级改点与任务拆解：收编四处 depth_mapping + 三个流程开关（自我辩论/并行开局），产出规范注入/工具预算/模型分层/流程门控 M1-M4（已实施，档位矩阵按三档理解）
  - [执行模式（研究/执行双模式提示词）设计](./05-design/v4.0/execution-advice-mode-design.md) ⭐ 代码发行、内容不发行：三流程 agent 提示词双轨（advice_mode 维度）+ 机器级开关 + 拦截体系开关化（agent 层 A1-A5/服务层 S1-S7）+ 回落保证
  - [双轨产品架构：获利侧与减损侧](./05-design/v4.0/profit-loss-dual-track-architecture.md) ⭐ 系统建设参考：获利侧生产判断/减损侧消费判断的双轨组织原则、生命周期×流程×Agent 编队分层对应、数据工具层与覆盖度盘点、三大缺口（快照只产不消/观察哨接入/复盘归因）与立项三问
  - [v4.0-beta.1 测试用例清单与功能点地图](./05-design/v4.0/test-case-checklist.md) 干净环境复测执行清单：功能点地图（12 模块）+ A-E 五组用例（安装环境/核心分析/行业工作台/传导登记/非功能）+ 通过标准与留痕
  - [v4.0 用户手册改版方案](./05-design/v4.0/user-guide-plan.md) 手册现状盘点与功能差距矩阵：主手册就地升级策略、章节级改点清单、写作口径基线、P0/P1/P2 分期
- **[v5.0（远期愿景）](./05-design/v5.0/)** - 远期愿景
- [前沿探索](./05-design/research/) - 不绑定版本的前沿研究
  - [保险行业研究方案（A股保险股）](./05-design/research/insurance/insurance-research-plan.md) - 保险域研究启动方案：商业模式/数据体系/监控框架映射/四周研究路径（独立于猪周期）

## 版本号管理规范

### 核心原则

**设计文档（05-design）和归档文档（99-archive）必须使用明确版本号目录**，禁止使用 `current`、`latest`、`new` 等相对概念命名。

### 05-design 版本号目录规则

```
05-design/
├── v3.0/              # 当前发布版本（v3.0.x 系列）的设计文档
├── v4.0/              # 下一版本规划
├── v5.0/              # 远期愿景
└── research/          # 前沿探索（不绑定版本）
```

**版本号命名规则**：
- 主版本号目录：`v3.0`、`v4.0`、`v5.0`（对应 major.minor 中的 major）
- 同一主版本号下的小版本迭代不新建目录，直接在原目录内更新文件
- 例如 v3.0.1、v3.0.2、v3.1.0 的设计文档都放在 `v3.0/` 目录下

### 99-archive 版本号目录规则

```
99-archive/
├── v0.1.x/            # v0.1.x 时代所有文档
├── v1.0.x/            # v1.0.x 时代所有文档
├── v2.0/              # v2.0 设计文档
├── v2.1/              # v2.1 设计文档
├── deprecated-features/ # 已废弃功能（跨版本）
└── historical-fixes/    # 历史修复记录（跨版本）
```

### 版本迭代流程

当发布新主版本（如 v3.0 → v4.0）时：

1. **设计文档迁移**：
   - `05-design/v3.0/` → `99-archive/v3.0/`（当前版本归档）
   - `05-design/v4.0/` → `05-design/v4.0/`（保持不变，成为新的当前版本）
   - 新建 `05-design/v5.0/`（开始下一版本规划）

2. **发布说明**：
   - 在 `01-product/release-notes/` 新建 `v4.0.0.md`

3. **知识沉淀**：
   - 将本版本周期内的重大 Bug 整理到 `06-knowledge/bug-chronicle/`

4. **禁止的操作**：
   - ❌ 禁止在 `05-design/` 下使用 `current/`、`next/`、`future/` 等相对命名
   - ❌ 禁止把旧版本文档留在 `05-design/v3.0/` 中不归档
   - ❌ 禁止跨版本修改已归档的文档（如需修改，复制到当前版本目录）

### 其他层的版本管理

| 层级 | 版本管理方式 | 说明 |
|------|-------------|------|
| 01-product | 按版本号命名文件 | `release-notes/v3.0.0.md`、`comparison/v2.1-vs-v3.0.md` |
| 02-user-guide | 跟随当前版本 | 文档内容随当前版本更新，不保留历史版本 |
| 03-development | 跟随当前版本 | 文档内容随当前版本更新，不保留历史版本 |
| 04-operations | 跟随当前版本 | 文档内容随当前版本更新，不保留历史版本 |
| 05-design | **按版本号目录** | 每个主版本一个目录，版本迭代时归档 |
| 06-knowledge | 跨版本积累 | 按季度/主题组织，不绑定版本 |
| 99-archive | **按版本号目录** | 每个主版本一个目录 |

## 文档命名规范

- 统一使用小写 kebab-case（如 `quick-start.md`）
- 版本相关文件加版本后缀（如 `docker-deployment-v1.md`）
- 临时文件加日期前缀（如 `2025-10-26-bugfix.md`）

## ADR（架构决策记录）

重要架构决策记录在 [03-development/decisions/](./03-development/decisions/)，每个 ADR 包含：
- 背景：面临什么问题
- 决策：选择了什么方案
- 原因：为什么选这个方案
- 后果：带来了什么影响
