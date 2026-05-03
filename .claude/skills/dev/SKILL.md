---
name: dev
description: >
  Use this skill when the user asks to "start dev environment", "spin up v2.1",
  "stop dev services", "check running environments", "switch to v3.0 dev",
  "启动开发环境", "停止开发环境", "查看开发环境状态",
  or needs to manage isolated development environments for parallel version development.
version: 0.1.0
---

# Dev Skill — 开发环境管理

管理多版本并行开发的隔离环境。每个版本使用独立的端口、数据卷和 Docker 项目名，互不干扰。

## 支持的版本

| 版本 | MongoDB | Redis | Backend | Frontend |
|------|---------|-------|---------|----------|
| 2.0 | 27017 | 6379 | 8000 | 8080 |
| 2.1 | 27018 | 6380 | 8001 | 8081 |
| 3.0 | 27019 | 6381 | 8002 | 8082 |

## 操作

### 启动开发环境

```bash
bash scripts/release/dev-env.sh up <version>
# 例如: bash scripts/release/dev-env.sh up 2.1
```

### 停止开发环境

```bash
bash scripts/release/dev-env.sh down <version>
# 例如: bash scripts/release/dev-env.sh down 2.1
```

### 查看状态

```bash
bash scripts/release/dev-env.sh status
```

## 注意事项

- 可以同时运行多个版本的开发环境（端口隔离）
- 每个版本的数据存储在独立的 Docker 数据卷中
- 前端访问地址为 `http://localhost:<FRONTEND_PORT>`
