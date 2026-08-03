# 数据库版本映射表

维护与各版本对应的 Docker 数据卷、MongoDB 端口和 Redis 端口关系，避免混用导致数据损坏。

## Docker 数据卷清单

| 数据卷名 (MongoDB) | 数据卷名 (Redis) | 版本 | 创建时间 | 最后活动 | 用途 |
|--------------------|------------------|------|----------|----------|------|
| `docker_tradingagents_mongodb_data` | `docker_tradingagents_redis_data` | v1.0.x | 2026-01-24 | 2026-01-24 | v1.0 开发数据 |
| `tradingagentscn_tradingagents_mongodb_data` | `tradingagentscn_tradingagents_redis_data` | v1.0 京东云版 | 2025-11-04 | 2026-07-19 | 京东云合作版测试数据 |
| `ta-v210_ta-v210_mongodb_data` | `ta-v210_ta-v210_redis_data` | v2.1.0 | — | — | v2.1.0 docker-compose dev |
| `ta-v3_mongodb_data` | `ta-v3_redis_data` | v3.0 | — | — | v3.0 docker-compose dev |
| `ta-v3_tradingagents_mongodb_data` | `ta-v3_tradingagents_redis_data` | v3.0 | — | — | v3.0 docker-compose（旧） |
| `ta-mongo-data` | `ta-redis-data` | v3.0 普通版 | — | — | 单容器统一部署（普通版） |
| `ta-data` | （同v3.0） | v3.0 京东云版 | — | — | 单容器统一部署（京东云版） |
| `microservices_mongodb_data` | `microservices_redis_data` | microservices | — | — | 微服务架构（实验） |

## 开发环境端口映射

| 版本 | MongoDB 端口 | Redis 端口 | Backend 端口 | 前端端口 | Docker 项目名 |
|------|-------------|-----------|-------------|---------|--------------|
| v2.0 | 27017 | 6379 | 8000 | 3000 | `ta-v201` |
| v2.1 | 27018 | 6380 | 8001 | 3001 | `ta-v210` |
| v3.0 | 27019 | 6381 | 8002 | 3002 | `ta-v3` |
| v3.0 京东云版 | 27020 | (内置) | 8082 | 8082 | `tradingagents`（单容器） |

## 数据库名映射

| 版本 | 主数据库名 | 辅助数据库名 |
|------|-----------|-------------|
| v1.0.x | `tradingagents` | — |
| v1.0 京东云版 | `tradingagents` | `tradingagentscn` |
| v2.x | `tradingagents` | `tradingagentscn` |
| v3.0 | `tradingagents` | `tradingagentscn` |

## 启动命令

### v1.0/v2.0（端口 27017/6379）

```powershell
.\start_dev.ps1 backend 2.0
.\start_dev.ps1 frontend 2.0
```

### v2.1（端口 27018/6380）

```powershell
.\start_dev.ps1 backend 2.1
.\start_dev.ps1 frontend 2.1
```

### v3.0（端口 27019/6381）

```powershell
.\start_dev.ps1 docker 3.0
.\start_dev.ps1 backend 3.0
.\start_dev.ps1 frontend 3.0
```

### v3.0 单容器版

见 [deploy-all-in-one/run.sh](../../deploy-all-in-one/run.sh) 启动脚本。

## 注意事项

1. **禁止跨版本共用数据库**：不同版本数据结构可能不兼容
2. **启动后端必须用 `start_dev.ps1`**：禁止手动 `uvicorn`，否则环境变量未设置会连错数据库
3. **操作数据库时确认端口**：
   - v3.0 → `mongodb://...:27019/...`
   - v2.1.0 → `mongodb://...:27018/...`
   - v1.0/v2.0 → `mongodb://...:27017/...`
4. 新增数据卷时，记得更新本文档
