# TradingAgents-CN Pro 开发规则

## 完整流程文档

详见 [docs/DEVELOPMENT_WORKFLOW.md](docs/DEVELOPMENT_WORKFLOW.md)

## 分支模型

- `main`：v3.0 开发主线，所有新功能只往这里合
- `release/2.0.x`：v2.0.1 维护分支，只接受 Bug 修复
- `release/2.1.x`：v2.1.0 维护分支，只接受 Bug 修复
- `hotfix/<version>/<issue>`：紧急修复，用完即删

## Commit 规范

使用 Conventional Commits 格式：

```
feat: 新功能描述
fix: Bug修复描述
docs: 文档变更
refactor: 重构描述
chore: 构建/工具/依赖变更
perf: 性能优化
test: 测试相关
```

## 版本号规则

- 正式版本：`v2.1.0`（semver）
- 测试构建：`v2.1.0-006`（版本号 + 构建号）
- `VERSION` 文件是版本号唯一来源，所有构建/打包/镜像 tag 从此读取
- 构建号由脚本自动管理，正式发布时归零

## 发布规则

- 每次正式发布必须：打 Tag + 创建/更新 Release 分支
- 测试构建打构建 Tag：`v2.1.0-006`
- Docker 镜像不使用裸 `latest`，用 `2-latest` / `3-latest` 替代
- 精确版本标签不可变，永不覆盖

## Bug 修复流程

1. 先在 `main` 修复
2. Cherry-pick 到需要的 `release/*` 分支
3. 如果只影响某个 release 版本，可直接在该分支修复

## 数据库迁移

- 补丁版本（2.1.0 → 2.1.1）：只做加法，不删除/重命名字段和表
- 小版本（2.1 → 2.2）：允许结构变更，但需提供迁移和回滚脚本
- 补丁版本不包含数据库结构变更，确保可安全回退

## 开发环境隔离

三个版本使用独立目录、独立端口、独立数据卷，互不干扰：

| 版本 | MongoDB | Redis | Backend | 前端 | Docker 项目名 |
|------|---------|-------|---------|------|--------------|
| v3.0 | 27019 | 6381 | 8002 | 8082 | `ta-v3` |
| v2.1.0 | 27018 | 6380 | 8001 | 8081 | `ta-v210` |
| v2.0.1 | 27017 | 6379 | 8000 | 8080 | `ta-v201` |

## 分发渠道

- Windows：百度网盘 + QQ群（主渠道），阿里云 OSS/腾讯云 COS（可选加速），GitHub Releases（归档）
- Linux/Mac：Docker Hub

## 推送规则

- `pro` 远程（`hsliuping/TradingAgents-CN-Pro`）是 Pro 版私有仓库
- 推送时注意分支映射：本地 `pro-main` 对应远程 `main`
- Release 分支和 Tag 都要推送到 `pro` 远程
