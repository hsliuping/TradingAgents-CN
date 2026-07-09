# TradingAgents-CN v0.1.16 API架构升级指南

## 🚀 概述

TradingAgents-CN v0.1.16 引入了全新的现代化API架构，在保持现有Streamlit界面的同时，提供了强大的后端API服务，支持高并发、队列管理、实时进度跟踪等企业级功能。

## 📋 新增功能

### 🏗️ 核心架构
- **FastAPI后端服务**: 现代化的异步API框架
- **Redis队列系统**: 支持优先级、并发控制、可见性超时
- **MongoDB数据存储**: 任务状态、用户数据、分析结果持久化
- **Worker进程**: 独立的分析任务处理器
- **实时进度推送**: SSE (Server-Sent Events) 支持

### 🔒 安全特性
- **JWT认证**: 无状态的用户认证
- **RBAC权限控制**: 基于角色的访问控制
- **速率限制**: 防止API滥用
- **CSRF防护**: 跨站请求伪造保护
- **输入验证**: 严格的数据验证

### 📊 队列管理
- **优先级队列**: 支持任务优先级排序
- **并发控制**: 用户级和全局级并发限制
- **可见性超时**: 防止任务丢失
- **自动重试**: 失败任务自动重新入队
- **批次管理**: 批量任务的聚合管理

## 🏛️ 架构设计

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Vue3 前端     │    │  Streamlit Web  │    │   移动端 App    │
│  (计划中)       │    │   (现有界面)    │    │   (计划中)      │
└─────────────────┘    └─────────────────┘    └─────────────────┘
         │                       │                       │
         └───────────────────────┼───────────────────────┘
                                 │
                    ┌─────────────────┐
                    │   FastAPI 网关  │
                    │   (路由/认证)   │
                    └─────────────────┘
                                 │
         ┌───────────────────────┼───────────────────────┐
         │                       │                       │
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   分析服务      │    │   队列服务      │    │   用户服务      │
│ (TradingAgents) │    │ (Redis队列)     │    │ (认证/权限)     │
└─────────────────┘    └─────────────────┘    └─────────────────┘
         │                       │                       │
         └───────────────────────┼───────────────────────┘
                                 │
                    ┌─────────────────┐
                    │   数据存储层    │
                    │ MongoDB + Redis │
                    └─────────────────┘
```

## 📁 目录结构

```
webapi/
├── core/                   # 核心配置和连接
│   ├── config.py          # 配置管理
│   ├── database.py        # 数据库连接
│   ├── redis_client.py    # Redis客户端
│   └── logging_config.py  # 日志配置
├── models/                 # 数据模型
│   ├── user.py            # 用户模型
│   ├── analysis.py        # 分析任务模型
│   └── __init__.py
├── schemas/                # API模式定义
│   └── __init__.py
├── services/               # 业务逻辑服务
│   ├── analysis_service.py # 分析服务
│   ├── queue_service.py    # 队列服务
│   ├── auth_service.py     # 认证服务
│   └── __init__.py
├── routers/                # API路由
│   ├── analysis.py         # 分析API
│   ├── auth.py            # 认证API
│   ├── queue.py           # 队列管理API
│   ├── health.py          # 健康检查API
│   ├── sse.py             # 实时推送API
│   └── __init__.py
├── middleware/             # 中间件
│   ├── error_handler.py    # 错误处理
│   ├── request_id.py       # 请求追踪
│   ├── rate_limit.py       # 速率限制
│   └── __init__.py
├── worker/                 # Worker进程
│   ├── analysis_worker.py  # 分析Worker
│   └── __init__.py
├── main.py                 # FastAPI应用入口
└── worker.py              # Worker启动脚本
```

## 🚀 快速开始

### 1. 环境准备

```bash
# 安装依赖
pip install fastapi uvicorn motor redis

# 启动Redis (Docker)
docker run -d --name redis -p 6379:6379 redis:alpine

# 启动MongoDB (Docker)
docker run -d --name mongodb -p 27017:27017 mongo:latest
```

### 2. 配置环境变量

复制并编辑环境配置文件：

```bash
cp .env.example .env
# 编辑 .env 文件，添加必要的配置
```

关键配置项：
```env
# API服务
API_HOST=0.0.0.0
API_PORT=8000
API_DEBUG=true

# 数据库
MONGO_URI=mongodb://localhost:27017
REDIS_URL=redis://localhost:6379/0

# 安全
JWT_SECRET=your-secret-key
```

### 3. 启动服务

```bash
# 启动API服务
cd webapi
python main.py

# 启动Worker进程 (新终端)
python scripts/start_worker.py

# 启动现有Streamlit界面 (新终端)
cd web
streamlit run app.py
```

### 4. 测试API

```bash
# 健康检查
curl http://localhost:8000/api/health

# 队列统计
curl http://localhost:8000/api/queue/stats

# 提交分析任务
curl -X POST http://localhost:8000/api/analysis/single \
  -H "Content-Type: application/json" \
  -d '{"stock_code": "AAPL", "parameters": {"research_depth": "深度"}}'
```

## 📊 API文档

启动服务后，访问以下地址查看API文档：

- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

## 🔧 主要API端点

### 分析相关
- `POST /api/analysis/single` - 提交单股分析
- `POST /api/analysis/batch` - 提交批量分析
- `GET /api/analysis/tasks/{task_id}` - 获取任务状态
- `POST /api/analysis/tasks/{task_id}/cancel` - 取消任务

### 队列管理
- `GET /api/queue/stats` - 队列统计
- `GET /api/queue/user-status` - 用户队列状态

### 实时推送
- `GET /api/sse/task-progress/{task_id}` - 任务进度推送
- `GET /api/sse/queue-stats` - 队列统计推送

### 健康检查
- `GET /api/health` - 服务健康状态
- `GET /api/health/database` - 数据库连接状态

## 🔄 兼容性

### 现有功能保持不变
- ✅ Streamlit Web界面完全兼容
- ✅ 现有分析功能无变化
- ✅ 配置文件向后兼容
- ✅ 数据存储格式兼容

### 渐进式升级
1. **阶段一**: API服务与现有系统并行运行
2. **阶段二**: 逐步迁移功能到API架构
3. **阶段三**: 开发新的前端界面
4. **阶段四**: 完全切换到新架构

## 🛠️ 开发指南

### 添加新的API端点

1. 在 `models/` 中定义数据模型
2. 在 `services/` 中实现业务逻辑
3. 在 `routers/` 中添加API路由
4. 在 `main.py` 中注册路由

### 扩展Worker功能

1. 继承 `AnalysisWorker` 类
2. 重写 `_process_task` 方法
3. 添加自定义任务类型处理

### 自定义中间件

1. 在 `middleware/` 中创建中间件类
2. 继承 `BaseHTTPMiddleware`
3. 在 `main.py` 中注册中间件

## 📈 性能优化

### 队列优化
- 使用Redis有序集合实现优先级队列
- 批量操作减少Redis调用
- 连接池复用减少连接开销

### 数据库优化
- MongoDB索引优化查询性能
- 连接池管理并发连接
- 异步操作提升吞吐量

### 缓存策略
- Redis缓存热点数据
- 分层缓存架构
- TTL自动过期清理

## 🔍 监控和调试

### 日志系统
- 结构化日志输出
- 请求ID追踪
- 分级日志记录

### 健康检查
- 服务状态监控
- 数据库连接检查
- 队列状态监控

### 性能指标
- 请求响应时间
- 队列处理速度
- 资源使用情况

## 🚧 后续计划

### 短期目标 (v0.1.17)
- [ ] Vue3前端界面开发
- [ ] 用户认证系统完善
- [ ] 批次进度聚合功能

### 中期目标 (v0.2.x)
- [ ] 微服务架构拆分
- [ ] 容器化部署方案
- [ ] 负载均衡支持

### 长期目标 (v1.0.x)
- [ ] 多租户支持
- [ ] 分布式队列
- [ ] 云原生部署

## 🤝 贡献指南

欢迎贡献代码！请遵循以下步骤：

1. Fork项目仓库
2. 创建功能分支
3. 提交代码变更
4. 创建Pull Request

## 📞 支持

如有问题，请通过以下方式联系：

- 📧 邮箱: hsliup@163.com
- 💬 微信群: 扫描README中的二维码
- 🐛 问题反馈: GitHub Issues

---

**TradingAgents-CN v0.1.16** - 现代化的多智能体股票分析学习平台
