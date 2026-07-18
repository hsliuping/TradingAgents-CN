# deploy-all-in-one

单容器统一部署方案，使用 s6-overlay 管理所有服务。

## 目录结构

```
deploy-all-in-one/
├── Dockerfile                       # 单容器镜像构建
├── README.md                        # 本文件
├── build.sh                         # 构建脚本
├── run.sh                           # 本地启动脚本
├── s6-rc.d/                         # s6-overlay 服务编排
│   ├── init/                        # oneshot - 容器初始化
│   ├── mongodb/                     # longrun - MongoDB
│   ├── redis/                       # longrun - Redis
│   ├── init-data/                   # oneshot - 数据库初始化
│   ├── backend/                     # longrun - FastAPI
│   └── nginx/                       # longrun - 反向代理
├── conf/                            # 各服务配置文件
│   ├── nginx.conf                   # Nginx 配置
│   ├── mongod.conf                  # MongoDB 配置
│   └── redis.conf                   # Redis 配置
├── scripts/                         # 辅助脚本
│   ├── wait_for_services.py         # 服务就绪等待
│   └── entrypoint-helpers.sh        # 入口辅助
├── k8s/                             # K8s 部署清单
│   ├── deployment.yaml
│   ├── pvc.yaml
│   ├── service.yaml
│   └── secret.yaml.example
└── docs/                            # 部署文档
    ├── quick-start.md
    └── k8s-deployment.md
```

## 启动顺序

```
init (oneshot)
  ↓
mongodb + redis (并行)
  ↓
init-data (oneshot) - 等待 mongodb/redis 就绪后初始化数据
  ↓
backend (longrun) - 启动 FastAPI
  ↓
nginx (longrun) - 启动反向代理
  ↓
就绪
```

## 快速开始

### 构建镜像

```bash
cd deploy-all-in-one
bash build.sh
```

### 本地启动

```bash
# 准备环境变量
export MONGODB_PASSWORD="your-secure-password"
export REDIS_PASSWORD="your-secure-redis-password"
export TUSHARE_TOKEN="your-tushare-token"

# 启动
bash run.sh
```

### Docker 启动

```bash
docker run -d \
  --name tradingagents \
  -p 8082:8082 \
  -v ta-mongo:/data/db \
  -v ta-redis:/var/lib/redis \
  -v ta-runtime:/app/runtime \
  -v ta-logs:/app/logs \
  -e MONGODB_PASSWORD="your-secure-password" \
  -e REDIS_PASSWORD="your-secure-redis-password" \
  -e TUSHARE_TOKEN="your-tushare-token" \
  tradingagents-cn-pro:3.0.0
```

### 访问

- 前端：http://localhost:8082
- API 文档：http://localhost:8082/docs
- 健康检查：http://localhost:8082/api/health

## 详细文档

- [单容器部署方案设计](../../../docs/05-design/v3.0/all-in-one-deployment.md)
- [K8s 部署文档](docs/k8s-deployment.md)
- [快速开始](docs/quick-start.md)
