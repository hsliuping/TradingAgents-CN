# Git 分支管理状态

> 生成日期：2026-06-25  
> 当前分支：`integration/v3-sync-20260507`  
> 基准分支：`v3.0`

---

## 1. 核心分支关系

```text
7a0ac1d0  feat: 提交 Agent 工坊与因子治理阶段性改动  ← 三方共同祖先
├── v3.0 (HEAD = 0357fffc)
│   │  fix: 补齐智能助手编号承接与单股数据同步能力
│   │
│   └── integration/v3-sync-20260507 (HEAD = cddbd896)  ← 当前分支
│       feat: 新增 show_in_reports 字段，彻底消灭报告提取硬编码
│
└── test/agent-workshop-validation (HEAD = e8e8c688)
    修复 Nanobot 展示消息持久化与工作台会话恢复
```

| 分支 | HEAD | 说明 |
|------|------|------|
| `v3.0` | `0357fffc` | v3.0 发布基线 |
| `integration/v3-sync-20260507` | `cddbd896` | 当前工作分支，v3.0 的延续 |
| `test/agent-workshop-validation` | `e8e8c688` | Nanobot 工坊独立验证分支 |

---

## 2. 从 v3.0 分出去、未合并到 integration 的分支

### 2.1 高优先级（与当前项目直接相关）

| 分支 | 领先提交 | HEAD | 内容概要 |
|------|---------|------|---------|
| `test/agent-workshop-validation` | 12 | `e8e8c688` | **Nanobot 工坊链路**：Embedded Nanobot 运行时、AgentStudio 页面、Agent Workshop 阶段流转、会话恢复 |
| `pro/release/2.1.x` | 14 | `5bba1fcb` | 2.1.x 发布分支：A 股数据源使用指南、Pro Docker 代理 503 修复、多架构脚本 BUILD_INFO 兜底 |
| `pro/v3.1-cognee-integration` | 3 | `5cfb0f9f` | **v4.0 设计文档体系 + MCP/Cognee 集成实验**、v3.0 版本文档目录 |
| `pro-main` | 11 | `b95118c8` | Pro 主线：A 股数据源指南、Pro Docker 修复、高级课程安装包修复 |

### 2.2 中优先级（功能分支，1-5 个提交）

| 分支 | 领先提交 | HEAD | 内容概要 |
|------|---------|------|---------|
| `feature/data-source-optimization` | 5 | `c9caf295` | 数据源微服务部署方案、MongoDB 存储、缓存管理、Web 配置界面 |
| `pr-470` | 3 | `cfd19345` | 股票新闻接口 headers 修复、群号更新 |
| `refactor/code-cleanup-and-optimization` | 3 | `499c0024` | 项目结构清理、pyproject.toml 打包脚本、营销文章 |
| `feature/educational-articles` | 2 | `33f154f1` | 教育模块文件、基础系列文章优化 |

### 2.3 低优先级（单提交或旧版本线）

| 分支 | 领先提交 | HEAD | 内容概要 |
|------|---------|------|---------|
| `feature/deepseek-v3-integration` | 1 | `9edf8f2c` | 美股数据获取优先级调整（FinnHub 优先） |
| `feature/docker-optimization` | 1 | `3da5e9b6` | Docker 分层构建优化 |
| `feature/unified-standard-plugin-llm-v1` | 1 | `707bf0ce` | 目录文件 |
| `feature/web-ui-improvements` | 1 | `6e0186c3` | 侧边栏布局和 API 密钥验证优化 |
| `main` | 38 | `aab6f3cb` | 旧主线，大部分已被 v3.0 覆盖，不应直接合并 |
| `v1.0.1` | 27 | `11609b0d` | 旧版本线，不应合并 |

---

## 3. 已合并到 integration 的分支（无需处理）

以下分支的提交已在 `integration/v3-sync-20260507` 或其祖先中：

| 分支 | 说明 |
|------|------|
| `backup/pro-v3.0-20260507` | v3.0 备份，内容已包含 |
| `origin/feature/hk-stock-optimization` | 港股优化 |
| `origin/feature/logging-management` | 日志管理 |
| `origin/feature/multi-market-support` | 多市场支持 |
| `origin/feature/native-openai-support` | OpenAI 原生支持 |
| `origin/feature/tushare-integration` | Tushare 集成 |
| `origin/feature/unify-cli-web-reports` | CLI/Web 报告统一 |
| `origin/feature/user-permissions` | 用户权限 |

---

## 4. 建议合并策略

### 4.1 立即处理

| 优先级 | 分支 | 操作 | 说明 |
|--------|------|------|------|
| P0 | `test/agent-workshop-validation` | cherry-pick | Nanobot 工坊链路，详见 [agent-workshop-workflow-compatibility.md](./agent-workshop-workflow-compatibility.md) |
| P1 | `pro/release/2.1.x` | 评估后 cherry-pick | 选取 Pro Docker 修复和构建脚本修复，跳过纯文档提交 |
| P1 | `pro/v3.1-cognee-integration` | 评估后 cherry-pick | 选取 v4.0 设计文档和 Cognee 实验代码，跳过纯文档目录调整 |

### 4.2 按需处理

| 优先级 | 分支 | 操作 | 说明 |
|--------|------|------|------|
| P2 | `pro-main` | 不合并 | 与 `pro/release/2.1.x` 有重叠，且包含大量与 v3.0 无关的 Pro 特性 |
| P2 | `feature/data-source-optimization` | 评估后 cherry-pick | 数据源微服务化方案，如果后续要做数据源独立部署则合并 |
| P2 | `pr-470` | cherry-pick | 股票新闻接口修复，低风险 |
| P2 | `refactor/code-cleanup-and-optimization` | 评估后 cherry-pick | 选取 pyproject.toml 打包改进，跳过营销文章 |

### 4.3 不建议合并

| 分支 | 原因 |
|------|------|
| `main` | 旧主线，大部分已被 v3.0 覆盖，合并会引入大量冲突 |
| `v1.0.1` | 旧版本线，架构不兼容 |
| `feature/deepseek-v3-integration` | 单提交，内容简单，按需 cherry-pick 即可 |
| `feature/docker-optimization` | 单提交，按需 cherry-pick |
| `feature/educational-articles` | 纯文档，按需 cherry-pick |
| `feature/unified-standard-plugin-llm-v1` | 单提交，内容不明 |
| `feature/web-ui-improvements` | 单提交，按需 cherry-pick |

---

## 5. 分支清理建议

以下本地分支可以考虑在合并后删除：

```text
# 已合并到 integration 的备份分支
backup/pro-v3.0-20260507

# 旧版本线（保留远程即可）
v1.0.1
main

# 已合并的 feature 分支（远程已存在）
feature/deepseek-v3-integration
feature/docker-optimization
feature/unified-standard-plugin-llm-v1
feature/web-ui-improvements
```

---

## 6. 远程分支注意事项

当前仓库配置了多个 remote：

| Remote | 说明 |
|--------|------|
| `origin` | 主远程仓库 |
| `pro` | Pro 版本远程仓库 |
| `upstream` | 上游开源仓库（TradingAgents） |
| `hub` | 备用仓库 |
| `charliecai` / `yifanhere` | 协作者分支 |

远程分支中 `pro/integration/v3-sync-20260507` 领先本地 2020 个提交，`pro/v3.0` 领先 1946 个提交。这些是 Pro 远程的历史累积，不代表本地落后——本地 `integration/v3-sync-20260507` 和 `v3.0` 已经是当前工作基线。

---

## 7. 维护建议

1. **每次合并后更新本文档**，记录新合并的分支和日期。
2. **定期清理已合并的本地分支**，避免分支列表膨胀。
3. **新功能开发先评估是否需要从历史分支 cherry-pick**，避免重复造轮子。
4. **`test/agent-workshop-validation` 合并后应删除该分支**，避免后续混淆。
