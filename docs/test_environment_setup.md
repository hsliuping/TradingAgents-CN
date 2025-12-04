# 测试环境搭建指南

## 概述

本文档介绍如何使用独立的测试环境来验证 TradingAgents-CN 的部署，而不影响现有的生产数据。

## 方案说明

### 为什么使用独立测试环境？

1. **保留现有数据**：生产数据卷不受影响
2. **快速切换**：可以随时在生产和测试环境之间切换
3. **安全测试**：测试失败不会影响生产环境
4. **易于清理**：测试完成后可以一键清理

### 环境对比

| 项目 | 生产环境 | 测试环境 |
|------|---------|---------|
| **Docker Compose 文件** | `docker-compose.hub.yml` | `docker-compose.hub.test.yml` |
| **容器名称** | `tradingagents-*` | `tradingagents-*-test` |
| **数据卷名称** | `tradingagents_mongodb_data`<br>`tradingagents_redis_data` | `tradingagents_test_mongodb_data`<br>`tradingagents_test_redis_data` |
| **网络名称** | `tradingagents-network` | `tradingagents-test-network` |
| **日志目录** | `logs/` | `logs-test/` |
| **配置目录** | `config/` | `config-test/` |
| **数据目录** | `data/` | `data-test/` |
| **端口** | 3000, 8000, 27017, 6379 | 3000, 8000, 27017, 6379 |

**注意**：测试环境和生产环境使用相同的端口，因此**不能同时运行**。

---

## 快速开始

### 1. 切换到测试环境

```powershell
# 停止生产环境，启动测试环境
.\scripts\switch_to_test_env.ps1
```

**执行内容**：
- 停止生产容器（`docker-compose.hub.yml down`）
- 启动测试容器（`docker-compose.hub.test.yml up -d`）
- 创建全新的测试数据卷

**预期输出**：
```
======================================================================
[OK] Test environment started!
======================================================================

[INFO] Test containers:
  - tradingagents-mongodb-test
  - tradingagents-redis-test
  - tradingagents-backend-test
  - tradingagents-frontend-test

[INFO] Test data volumes:
  - tradingagents_test_mongodb_data
  - tradingagents_test_redis_data

[INFO] Access URLs:
  - Frontend: http://localhost:3000
  - Backend API: http://localhost:8000
  - API Docs: http://localhost:8000/docs
```

---

### 2. 验证测试环境

#### 检查容器状态

```powershell
docker ps
```

**预期输出**：
```
CONTAINER ID   IMAGE                                  STATUS         PORTS                      NAMES
xxxxxxxxxx     hsliup/tradingagents-frontend:latest   Up 2 minutes   0.0.0.0:3000->80/tcp       tradingagents-frontend-test
xxxxxxxxxx     hsliup/tradingagents-backend:latest    Up 2 minutes   0.0.0.0:8000->8000/tcp     tradingagents-backend-test
xxxxxxxxxx     redis:7-alpine                         Up 2 minutes   0.0.0.0:6379->6379/tcp     tradingagents-redis-test
xxxxxxxxxx     mongo:4.4                              Up 2 minutes   0.0.0.0:27017->27017/tcp   tradingagents-mongodb-test
```

#### 检查数据卷

```powershell
docker volume ls | Select-String "tradingagents"
```

**预期输出**：
```
local     tradingagents_mongodb_data           # 生产数据卷（保留）
local     tradingagents_redis_data             # 生产数据卷（保留）
local     tradingagents_test_mongodb_data      # 测试数据卷（新建）
local     tradingagents_test_redis_data        # 测试数据卷（新建）
```

#### 查看后端日志

```powershell
docker logs -f tradingagents-backend-test
```

**预期输出**：
```
INFO:     Started server process [1]
INFO:     Waiting for application startup.
INFO:     Application startup complete.
INFO:     Uvicorn running on http://0.0.0.0:8000 (Press CTRL+C to quit)
```

#### 访问前端

打开浏览器访问：http://localhost:3000

**预期结果**：
- 前端页面正常加载
- 可以注册新用户（测试环境是全新数据库）
- 可以配置数据源（Tushare/AKShare/BaoStock）
- 可以测试各项功能

---

### 3. 测试场景

#### 场景 1：从零部署测试

**目的**：验证新用户首次部署的体验

**步骤**：
1. 切换到测试环境（全新数据库）
2. 访问前端，注册新用户
3. 配置 Tushare Token
4. 启用数据同步任务
5. 等待数据同步完成
6. 测试股票查询、分析等功能

**验证点**：
- ✅ 用户注册流程是否顺畅
- ✅ 数据源配置是否正确
- ✅ 定时任务是否正常启动
- ✅ 数据同步是否成功
- ✅ 前端功能是否正常

#### 场景 2：受限环境测试

**目的**：验证在某些 API 不可用时的表现

**步骤**：
1. 切换到测试环境
2. 不配置 Tushare Token（模拟无 Token 场景）
3. 只启用 AKShare 数据源
4. 测试系统是否能正常运行

**验证点**：
- ✅ 系统是否能在缺少 Tushare 的情况下运行
- ✅ AKShare 数据同步是否正常
- ✅ 错误提示是否友好
- ✅ 日志是否清晰

#### 场景 3：配置错误测试

**目的**：验证错误配置的处理

**步骤**：
1. 切换到测试环境
2. 故意配置错误的 Tushare Token
3. 观察系统行为

**验证点**：
- ✅ 系统是否能检测到错误配置
- ✅ 错误提示是否清晰
- ✅ 系统是否能继续运行（不崩溃）

---

### 4. 切换回生产环境

测试完成后，切换回生产环境：

```powershell
# 停止测试环境，启动生产环境
.\scripts\switch_to_prod_env.ps1
```

**执行内容**：
- 停止测试容器（`docker-compose.hub.test.yml down`）
- 启动生产容器（`docker-compose.hub.yml up -d`）
- 恢复使用生产数据卷

**预期输出**：
```
======================================================================
[OK] Production environment started!
======================================================================

[INFO] Production containers:
  - tradingagents-mongodb
  - tradingagents-redis
  - tradingagents-backend
  - tradingagents-frontend

[INFO] Production data volumes:
  - tradingagents_mongodb_data
  - tradingagents_redis_data
```

---

### 5. 清理测试环境

如果测试完成，不再需要测试数据：

```powershell
# 清理测试容器、数据卷和目录
.\scripts\cleanup_test_env.ps1
```

**执行内容**：
- 停止并删除测试容器
- 删除测试数据卷
- 删除测试目录（`logs-test/`, `config-test/`, `data-test/`）

**警告**：此操作会删除所有测试数据，无法恢复！

---

## 手动操作

如果您不想使用脚本，也可以手动操作：

### 启动测试环境

```powershell
# 停止生产环境
docker-compose -f docker-compose.hub.yml down

# 启动测试环境
docker-compose -f docker-compose.hub.test.yml up -d

# 查看日志
docker logs -f tradingagents-backend-test
```

### 切换回生产环境

```powershell
# 停止测试环境
docker-compose -f docker-compose.hub.test.yml down

# 启动生产环境
docker-compose -f docker-compose.hub.yml up -d

# 查看日志
docker logs -f tradingagents-backend
```

### 清理测试环境

```powershell
# 停止并删除测试容器和数据卷
docker-compose -f docker-compose.hub.test.yml down -v

# 删除测试目录
Remove-Item -Path logs-test -Recurse -Force
Remove-Item -Path config-test -Recurse -Force
Remove-Item -Path data-test -Recurse -Force
```

---

## 常见问题

### Q1: 测试环境和生产环境可以同时运行吗？

**A**: 不可以。因为它们使用相同的端口（3000, 8000, 27017, 6379），会发生端口冲突。

### Q2: 测试数据会影响生产数据吗？

**A**: 不会。测试环境使用独立的数据卷（`tradingagents_test_*`），与生产数据卷（`tradingagents_*`）完全隔离。

### Q3: 如何查看测试环境的日志？

**A**: 使用以下命令：
```powershell
# 后端日志
docker logs -f tradingagents-backend-test

# 前端日志
docker logs -f tradingagents-frontend-test

# MongoDB 日志
docker logs -f tradingagents-mongodb-test

# Redis 日志
docker logs -f tradingagents-redis-test
```

### Q4: 测试环境的数据存储在哪里？

**A**: 
- **数据卷**：Docker 管理的卷（`tradingagents_test_mongodb_data`, `tradingagents_test_redis_data`）
- **日志文件**：`logs-test/` 目录
- **配置文件**：`config-test/` 目录
- **数据文件**：`data-test/` 目录

### Q5: 如何删除测试数据卷？

**A**: 使用以下命令：
```powershell
# 停止测试容器
docker-compose -f docker-compose.hub.test.yml down

# 删除测试数据卷
docker volume rm tradingagents_test_mongodb_data
docker volume rm tradingagents_test_redis_data
```

或者使用清理脚本：
```powershell
.\scripts\cleanup_test_env.ps1
```

---

## 总结

使用独立测试环境的优势：

✅ **安全**：不影响生产数据  
✅ **灵活**：可以随时切换  
✅ **完整**：完全模拟真实部署  
✅ **易用**：一键启动和清理  

推荐在以下场景使用测试环境：

- 🧪 测试新功能
- 🔧 验证配置更改
- 📚 编写文档和教程
- 🐛 复现和修复 Bug
- 🎓 培训和演示

---

**祝测试顺利！** 🎉

