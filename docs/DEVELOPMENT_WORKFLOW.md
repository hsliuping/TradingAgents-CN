

# TradingAgents-CN Pro 开发维护流程指南

## 项目概述

- **开发者**：1人
- **开发环境**：Windows 11（多 IDE 并行开发）
- **部署环境**：Linux 服务器（Docker）
- **发布频率**：不固定，按功能完成情况发布

## 版本线

| 版本 | 类型 | 仓库 | 状态 |
|------|------|------|------|
| v1.0.1 | 开源版 | `origin`（`hsliuping/TradingAgents-CN`，公开） | 已发布，不再主要维护 |
| v2.0.1 | Pro | `pro`（`hsliuping/TradingAgents-CN-Pro`，私有） | 已发布，仅维护 |
| v2.1.0 | Pro | `pro`（私有） | 当前生产版本，仅维护 |
| v3.0 | Pro | `pro`（私有） | 开发中 |

**v2.x 与 v3.0 长期并行，v3.0 不会替代 v2.x。**

## 分支模型

```
main (v3.0 开发主线，新功能都在这里)
 ├── release/2.0.x  (v2.0.1 维护分支，只接受 Bug 修复)
 └── release/2.1.x  (v2.1.0 维护分支，只接受 Bug 修复)
```

### 分支规则

| 操作 | 目标分支 | 说明 |
|------|----------|------|
| 新功能开发 | `main`（v3.0） | 所有新功能只往 main 合并 |
| Bug 修复 | 先修 `main`，再 cherry-pick 到需要的 `release/*` | 确保修复不遗漏 |
| release/2.x 维护 | `release/2.0.x` 或 `release/2.1.x` | 只做 Bug 修复，不加新功能 |

### Bug 修复流程

1. 在 `main` 分支上修复 Bug
2. 验证通过后，cherry-pick 到需要修复的 `release/*` 分支
3. 如果 Bug 只影响某个 release 版本，也可以直接在该 release 分支修复

### Hotfix 流程

紧急修复使用短生命周期分支，修复完成后删除：

```
hotfix/2.1/null-pointer-fix    # v2.1.x 的紧急修复
hotfix/3.0/api-crash           # v3.0.x 的紧急修复
```

流程：
1. 从受影响的最低版本 tag 创建 hotfix 分支：`git checkout -b hotfix/2.1/null-pointer-fix v2.1.0`
2. 修复 Bug，更新 VERSION 文件，提交并打 tag
3. Cherry-pick 到更高版本分支（如 `release/3.x`），再 cherry-pick 到 `main`
4. 推送所有分支和 tag
5. 删除 hotfix 分支

### 版本快照：Tag 与 Release 分支

**核心原则：每次正式发布时，必须同时创建 Tag 和 Release 分支，确保任何时候都能回到任意版本的代码。**

**当前问题**：发布后代码都合入 `main`，没有版本快照，后续修 Bug 时找不到对应版本的代码。

**解决方式**：

1. **正式发布时打 Tag**：`git tag v2.1.0`，标记这个版本对应的精确代码快照
2. **正式发布时创建 Release 分支**：从当前代码创建 `release/2.1.x`，作为该版本的维护分支
3. **测试构建打构建 Tag**：`git tag v2.1.0-006`，记录每次测试打包对应的代码

**示例**：

```
# v2.1.0 正式发布
git checkout -b release/2.1.x       # 创建维护分支
git tag v2.1.0                       # 打正式版本 Tag

# v2.1.0 测试构建
git tag v2.1.0-006                   # 打构建 Tag

# 后续 v2.1.1 Bug 修复发布
git tag v2.1.1                       # 新版本 Tag
```

**为什么需要 Release 分支而不仅仅是 Tag？**

- Tag 是只读快照，适合标记"这个版本的代码是什么"
- Release 分支是可写的，适合"在这个版本基础上继续修 Bug"
- 两者配合使用：Tag 留存历史，Release 分支承载后续修复

## 版本号规则

### 格式

- **正式版本**：`v2.1.0`（semver 格式，正式发布时更新）
- **测试构建**：`v2.1.0-006`（版本号 + 构建号，开发测试时自增）

### 单一来源

`VERSION` 文件是版本号的唯一来源，所有构建脚本、打包脚本、Docker 镜像 tag 均从该文件读取。

```
# VERSION 文件内容示例
2.1.0
```

### 构建号管理

- 构建号在每次测试打包时自增（如 `001` → `002` → `003`）
- 正式发布时，构建号归零，更新主版本号（如 `2.1.0-012` → `2.2.0`）
- 构建号由构建脚本自动管理，无需手动维护

### 各分支 VERSION 示例

| 分支 | VERSION 内容 | 构建示例 |
|------|-------------|----------|
| `main` | `3.0.0-beta` | `3.0.0-beta-005` |
| `release/2.1.x` | `2.1.0` | `2.1.0-006` |
| `release/2.0.x` | `2.0.1` | `2.0.1-013` |

## Commit 规范

### Conventional Commits

所有 commit 消息统一使用 Conventional Commits 格式：

```
<类型>: <描述>

# 示例
feat: 添加 Agent 工坊功能
fix: 修复股票新闻接口返回空响应
docs: 更新部署文档
refactor: 重构数据同步模块
chore: 更新依赖版本
```

**类型说明**：

| 类型 | 用途 |
|------|------|
| `feat` | 新功能 |
| `fix` | Bug 修复 |
| `docs` | 文档变更 |
| `refactor` | 重构（不改变功能） |
| `chore` | 构建/工具/依赖变更 |
| `perf` | 性能优化 |
| `test` | 测试相关 |

**好处**：
- 可以用工具（如 `git-cliff`）自动从 commit 历史生成每个版本的 Changelog
- 一眼看出 commit 是新功能、修复还是其他变更
- 便于后续筛选和统计

## 变更日志管理

### 自动生成 Changelog

使用 `git-cliff` 从 commit 历史自动生成变更日志，按版本线过滤：

```bash
# 生成 v2.x 的变更日志
git-cliff --tag-pattern "v2.*"

# 生成 v3.x 的变更日志
git-cliff --tag-pattern "v3.*"
```

### 生成规则

- 每次正式发布前，自动生成该版本的 Changelog
- `feat:` 类型的 commit 归入"新功能"分组
- `fix:` 类型的 commit 归入"Bug 修复"分组
- 其他类型归入"其他变更"分组
- Changelog 提交到仓库的 `CHANGELOG.md` 中

### Changelog 格式

```markdown
## v2.1.1 (2026-05-03)

### Bug Fixes
- 修复股票新闻接口返回空响应的问题

### Features
- 添加自选股批量导入功能

### Upgrade Notes
- 可从 v2.1.0 安全升级，无需配置变更
```

## Docker 镜像标签策略

### 多标签体系

每个版本构建时同时打多个标签：

| 标签 | 含义 | 示例 |
|------|------|------|
| `2.1.0` | 精确版本，不可变 | 永远指向同一镜像 |
| `2.1` | 2.1.x 最新补丁 | 2.1.1 发布后自动指向 2.1.1 |
| `2` | 2.x 最新版本 | 2.2.0 发布后自动指向 2.2.0 |
| `2-latest` | 2.x 系列最新 | 明确表示 2.x 最新版 |
| `3.0.0-beta` | 预发布版本 | 测试用 |

**关键规则**：
- **不使用裸 `latest`**：多版本并行时 `latest` 指向谁不明确，用 `2-latest` / `3-latest` 替代
- **精确版本标签不可变**：`2.1.0` 永远指向同一镜像，绝不覆盖
- **浮动标签可更新**：`2.1` 在 2.1.1 发布后自动指向 2.1.1

### 镜像内嵌版本信息

Dockerfile 中通过构建参数嵌入版本号，方便运行时查询：

```dockerfile
ARG VERSION=dev
LABEL org.opencontainers.image.version=${VERSION}
ENV APP_VERSION=${VERSION}
```

## 开发环境隔离

### 目录隔离

每个版本使用独立的项目目录，互不干扰：

| 版本 | 目录 | Git 分支 | 用途 |
|------|------|----------|------|
| v3.0（开发） | `~/TradingAgents-v3/` | `main` | 主力 IDE，日常开发 |
| v2.1.0（维护） | `~/TradingAgents-v2.1/` | `release/2.1.x` | 需要时打开，只修 Bug |
| v2.0.1（维护） | `~/TradingAgents-v2.0/` | `release/2.0.x` | 很少动，紧急修复才打开 |

### 服务端口隔离

每个版本的开发环境使用不同的端口，避免服务冲突：

| 版本 | MongoDB | Redis | Backend | 前端 | Docker 项目名 |
|------|---------|-------|---------|------|--------------|
| v3.0 | 27019 | 6381 | 8002 | 8082 | `ta-v3` |
| v2.1.0 | 27018 | 6380 | 8001 | 8081 | `ta-v210` |
| v2.0.1 | 27017 | 6379 | 8000 | 8080 | `ta-v201` |

每个目录自带 `.env` 文件，指定各自的端口和容器名。Docker Compose 使用 `-p` 指定项目名，确保容器名、网络、数据卷完全隔离。

### 数据卷隔离

不同版本使用不同的数据卷前缀，数据库数据完全独立：

- v3.0：`ta-v3_mongodb_data`、`ta-v3_redis_data`
- v2.1.0：`ta-v210_mongodb_data`、`ta-v210_redis_data`
- v2.0.1：`ta-v201_mongodb_data`、`ta-v201_redis_data`

## 分发方式

### Windows

- **分发方式**：安装文件（便携版/安装包，约 300MB+）
- **分发渠道**：
  - **主渠道**：百度网盘 + QQ群共享文件（国内下载速度快）
  - **归档渠道**：阿里云 OSS / 腾讯云 COS（可选，CDN 加速，成本极低）
  - **GitHub Releases**：作为版本发布官方记录存档（国内下载慢，不建议作为用户下载渠道）
- **通知方式**：微信公众号通知 + QQ群内通知

### Linux / Mac

- **分发方式**：Docker 镜像
- **分发渠道**：Docker Hub（`hsliup/tradingagents-pro-backend`、`hsliup/tradingagents-pro-frontend`）
- **通知方式**：同上

### Windows 大文件分发方案

当前安装包约 300MB+，GitHub Releases 国内下载速度慢，不适合作为用户下载主渠道。

**推荐方案**：

| 优先级 | 渠道 | 用途 | 成本 |
|--------|------|------|------|
| 主渠道 | 百度网盘 + QQ群 | 用户实际下载 | 免费 |
| 可选加速 | 阿里云 OSS / 腾讯云 COS | CDN 加速下载，体验更好 | 极低（按流量计费） |
| 归档 | GitHub Releases | 版本发布官方记录 | 免费 |

**长期优化方向**：

- **拆分安装包**：将不变的依赖（Python 运行时、node_modules 等）和业务代码分开，依赖包用户只需下载一次，后续更新只下载业务代码包（通常几十 MB）
- **增量更新**：只发布与上一版本的差异部分，而非每次 300MB 全量包

## 发布流程

### Docker 镜像发布（Linux / Mac）

1. 确认代码已合并到 `main`
2. 更新 `VERSION` 文件（正式发布时更新版本号，测试构建时构建号自增）
3. 创建 Release 分支（首次发布时）：`git checkout -b release/2.1.x`
4. 打版本 Tag：`git tag v2.1.0`（正式发布）或 `git tag v2.1.0-006`（测试构建）
5. 推送分支和 Tag：`git push pro release/2.1.x && git push pro v2.1.0`
6. 在 Ubuntu 构建服务器上运行构建脚本：
   ```bash
   ./docker/scripts/build-and-push-all.sh -t $(cat VERSION)
   ```
7. 镜像自动推送到 Docker Hub（同时打精确版本标签和浮动标签）
8. 在部署服务器上运行部署：
   ```bash
   cd ~/TradingAgents-CN-Pro/docker
   ./deploy.sh
   # 输入版本号（如 2.1.0-006）完成部署
   ```
9. 创建 GitHub Release（包含 Changelog 和升级说明）
10. 发布通知（微信公众号 + QQ群）

### Windows 安装包发布

1. 确认代码已合并到 `main`
2. 更新 `VERSION` 文件
3. 创建 Release 分支（首次发布时）：`git checkout -b release/2.1.x`
4. 打版本 Tag：`git tag v2.1.0`
5. 推送分支和 Tag：`git push pro release/2.1.x && git push pro v2.1.0`
6. 本地构建安装包
7. 上传到百度网盘 + QQ群共享文件
8. 创建 GitHub Release（包含 Changelog 和升级说明）
9. 发布通知（微信公众号 + QQ群）

## GitHub Release 管理

每次正式发布在 GitHub 上创建 Release，作为版本发布的官方记录：

- **标题**：`v2.1.0 (2.x)` 或 `v3.0.0-beta (3.x)`，标注版本线
- **内容**：包含 Changelog（可从 `git-cliff` 自动生成）和升级说明
- **附件**：可选挂载安装包（国内下载慢，仅作归档）
- **触发方式**：推送 tag 后由 GitHub Actions 自动创建（CI/CD 建成后），或手动创建

## 数据库迁移策略

多版本并行时，数据库结构变更需谨慎：

### 规则

| 版本变更类型 | 允许的操作 | 示例 |
|-------------|-----------|------|
| 补丁版本（2.1.0 → 2.1.1） | 只做加法：新增字段/表，不删除、不重命名 | 新增 `user_preferences` 字段 |
| 小版本（2.1 → 2.2） | 允许结构性变更，但需提供迁移和回滚脚本 | 重命名表、修改字段类型 |
| 大版本（2.x → 3.x） | 允许重大变更，需提供完整迁移指南 | 全新数据模型 |

### 回滚保障

- 每个版本附带迁移脚本，需支持**向前和向后执行**
- 补丁版本不允许数据库结构变更，确保可安全回退
- 部署前在测试环境验证迁移和回滚

## 部署健康检查与回滚

### 健康检查

Docker Compose 中配置健康检查，部署后自动验证服务状态：

```yaml
services:
  backend:
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 30s
      retries: 3
      start_period: 10s
```

### 回滚策略

| 层级 | 方式 | 说明 |
|------|------|------|
| L1 基础回滚 | 修改 `IMAGE_TAG` 指向上一版本，重启容器 | 最简单，适用于配置不变的场景 |
| L2 数据库回滚 | 执行版本的回滚迁移脚本 | 适用于有数据库变更的场景 |
| L3 完整回滚 | L1 + L2 + 恢复数据备份 | 重大故障时使用 |

**回滚原则**：
- 精确版本标签不可变，`v2.1.0` 永远可用，随时可回退
- 保留至少最近 3-5 个版本的镜像在 Docker Hub 上
- 补丁版本不包含数据库结构变更，回滚无需担心数据库

## 当前已知问题与优化方向

| 优先级 | 问题 | 优化方案 | 状态 |
|--------|------|----------|------|
| P0 | 发布后无版本快照，修 Bug 找不到对应代码 | 每次发布打 Tag + 创建 Release 分支 | 待实施 |
| P0 | 三版本共用 MongoDB，开发调试互相干扰 | 按目录/端口/数据卷隔离 | 待实施 |
| P0 | 版本号 rev 后缀非标准，多处手动维护 | 改为 semver + 构建号，VERSION 单一来源 | 待实施 |
| P1 | 分支关系不清晰，pro-main 和 v3.0 关系混乱 | 改为 main + release/* 分支模型 | 待实施 |
| P1 | 发布流程全手动，步骤多易出错 | 编写一键发布脚本 | 待实施 |
| P1 | Commit 消息格式不统一，无法自动生成 Changelog | 采用 Conventional Commits 规范 | 待实施 |
| P1 | Docker 镜像只打 latest 和版本号，多版本并行时混淆 | 多标签体系，废弃裸 latest | 待实施 |
| P1 | 部署无健康检查，服务异常无法自动发现 | Docker Compose 加 healthcheck | 待实施 |
| P2 | Pro 版无 CI/CD，构建全靠手动 | 在 pro 仓库加 GitHub Actions | 待实施 |
| P2 | 部署配置从网站下载，版本不可控 | .env/nginx.conf 纳入仓库管理 | 待实施 |
| P2 | 无 Changelog，版本变更记录靠手动 | 用 git-cliff 自动生成 | 待实施 |
| P2 | Windows 安装包全量 300MB+，每次完整下载 | 拆分依赖包和业务包，支持增量更新 | 待实施 |
| P2 | 数据库迁移无规范，补丁版本可能引入结构变更 | 补丁只做加法，小版本才允许结构变更 | 待实施 |
