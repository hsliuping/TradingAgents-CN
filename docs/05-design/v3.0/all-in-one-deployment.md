# 单容器统一部署方案（s6-overlay）

> **ADR 状态**：已批准
> **决策日期**：2026-07-18
> **目标用户**：个人用户（单用户部署）、京东云 K8s 部署
> **替代方案**：多容器 docker-compose

---

## 1. 背景与动机

### 1.1 现状问题

当前采用**多容器架构**（`docker-compose.yml`）：

| 容器 | 作用 | 镜像 |
|------|------|------|
| mongodb | 数据存储 | mongo:4.4 / 8.0 |
| redis | 缓存/任务队列 | redis:7-alpine |
| backend | FastAPI 服务 | 自定义 |
| frontend | Vite 构建产物 | 自定义 |
| nginx | 反向代理 | nginx:alpine |

普通用户部署时面临：
- 5 个容器协同启动，启动顺序难调试
- 镜像版本协调困难（mongod 4.4 vs 8.0 不兼容）
- 数据卷管理复杂
- 端口映射多（27019/6381/8002/3002/8082）
- K8s 部署需要设计多 Pod 协调

### 1.2 决策

采用 **s6-overlay 单容器方案**，将所有服务打包到一个 Docker 镜像中，通过 s6-overlay 统一管理进程生命周期。

### 1.3 关键收益

| 收益 | 量化 |
|------|------|
| 部署命令简化 | 5 条 → 1 条 `docker run` |
| 启动时间 | 30-60s → 5-10s（内部进程拉起） |
| 端口数量 | 5 → 1（仅暴露 nginx 8082） |
| 镜像数量 | 5 → 1 |
| K8s 资源 | 5 Pod → 1 Pod |
| 镜像体积 | 约 2.5 GB（可接受） |

---

## 2. 架构设计

### 2.1 进程拓扑

```
┌─────────────────────────────────────────────────────┐
│                   Docker Container                   │
│  ┌───────────────────────────────────────────────┐  │
│  │   s6-overlay (PID 1) — 进程管家              │  │
│  │   ├─ init-mongodb (oneshot)                 │  │
│  │   │   └─ 等待端口 27017 可用                │  │
│  │   ├─ init-redis (oneshot)                    │  │
│  │   │   └─ 等待端口 6379 可用                 │  │
│  │   ├─ mongodb (longrun)                       │  │
│  │   │   └─ mongod --config /etc/mongod.conf   │  │
│  │   ├─ redis (longrun)                         │  │
│  │   │   └─ redis-server ...                   │  │
│  │   ├─ backend (longrun)                       │  │
│  │   │   └─ uvicorn app.main:app --port 8000  │  │
│  │   ├─ frontend-static (longrun)              │  │
│  │   │   └─ 静态文件由 nginx 托管              │  │
│  │   └─ nginx (longrun)                         │  │
│  │       └─ nginx -g 'daemon off;'             │  │
│  └───────────────────────────────────────────────┘  │
└──────────────────────┬──────────────────────────────┘
                       ↓
                  Port 8082（对外）
```

### 2.2 启动顺序（s6 依赖图）

```
                    [init]
                       │
        ┌──────────────┼──────────────┐
        │              │              │
   [mongodb]      [redis]      [init-data]
   oneshot         oneshot       (数据库初始化)
        │              │              │
        └──────┬───────┘              │
               │                      │
           [backend]  ←───────────────┘
               │
           [nginx]
               │
           就绪 ✅
```

### 2.3 内部端口分配

| 服务 | 内部端口 | 对外暴露 |
|------|---------|---------|
| MongoDB | 27017 | ❌ |
| Redis | 6379 | ❌ |
| Backend | 8000 | ❌（仅 nginx 反代） |
| Frontend | 80 (nginx) | ❌ |
| **Nginx** | **8082** | ✅ 统一入口 |

---

## 3. 镜像设计

### 3.1 基础镜像

```dockerfile
FROM python:3.11-bookworm
```

理由：
- Python 3.11.9 与项目 `env/` 虚拟环境版本一致
- Debian Bookworm 提供完整的 apt 仓库（mongodb/redis/nginx）

### 3.2 安装的服务

| 服务 | 安装方式 | 用途 |
|------|---------|------|
| Python 3.11 | 基础镜像自带 | Backend 运行环境 |
| MongoDB 8.0 | apt: mongodb-org | 数据存储（EOL 2029-10） |
| Redis 7 | apt: redis-server | 缓存 + Celery broker |
| Nginx 1.22 | apt: nginx | 反向代理 + 静态资源 |
| Node.js 20 | NodeSource 源 | 构建前端（仅 build 阶段） |
| gosu | apt: gosu | 权限降级（安全） |
| s6-overlay | 官方 tarball | 进程管理 |

### 3.3 用户与权限

| 用户 | UID | 用途 |
|------|-----|------|
| `appuser` | 1000 | 运行所有应用进程 |
| `mongodb` | 999 | MongoDB 内部用户 |
| `redis` | 998 | Redis 内部用户 |

安全原则：
- s6-overlay 启动时以 root 处理挂载卷权限
- 各服务进程通过 s6 的 `run` 脚本以 `appuser` 身份启动
- MongoDB/Redis 用各自的系统用户隔离数据目录

---

## 4. s6-overlay 服务编排

### 4.1 目录结构

```
/etc/s6-overlay/s6-rc.d/
├── init/
│   ├── type                       # oneshot
│   ├── run                        # 创建目录 + 权限修复
│   └── dependencies
│
├── mongodb/
│   ├── type                       # longrun
│   ├── run                        # 启动 mongod
│   ├── finish                     # 退出处理
│   └── dependencies               # init
│
├── redis/
│   ├── type                       # longrun
│   ├── run                        # 启动 redis
│   └── dependencies               # init
│
├── init-data/
│   ├── type                       # oneshot
│   ├── run                        # 等待 mongodb/redis 就绪
│   │                              # 执行数据库初始化
│   ├── up                         # /etc/s6-overlay/s6-rc.d/init-data/up
│   └── dependencies               # mongodb, redis
│
├── backend/
│   ├── type                       # longrun
│   ├── run                        # 启动 uvicorn
│   └── dependencies               # init-data
│
└── nginx/
    ├── type                       # longrun
    ├── run                        # 启动 nginx
    └── dependencies               # backend
```

### 4.2 关键服务脚本

#### mongodb/run
```bash
#!/command/with-contenv bash
exec gosu mongodb mongod \
    --config /etc/mongod.conf \
    --bind_ip 127.0.0.1 \
    --port 27017
```

#### backend/run
```bash
#!/command/with-contenv bash
cd /app
exec gosu appuser python -m uvicorn \
    app.main:app \
    --host 127.0.0.1 \
    --port 8000 \
    --log-level info
```

#### init-data/run（数据库初始化）
```bash
#!/command/with-contenv bash
# 等待 MongoDB 和 Redis 就绪
python /app/scripts/wait_for_services.py

# 检查是否已初始化（标记文件 + admin 用户存在性）
if [ -f /app/runtime/.config_imported ]; then
    echo "✅ 数据库已初始化"
    exit 0
fi

# 执行初始化
python /app/scripts/import_config_and_create_user.py
echo "$(date -u +'%Y-%m-%d %H:%M:%S UTC')" > /app/runtime/.config_imported
echo "✅ 数据库初始化完成"
```

#### nginx/run
```bash
#!/command/with-contenv bash
exec nginx -g 'daemon off;'
```

---

## 5. Nginx 配置

### 5.1 监听与代理

```nginx
# /etc/nginx/nginx.conf
worker_processes auto;
error_log /var/log/nginx/error.log warn;

events { worker_connections 1024; }

http {
    include /etc/nginx/mime.types;
    sendfile on;
    keepalive_timeout 65;

    upstream backend {
        server 127.0.0.1:8000;
    }

    server {
        listen 8082;
        server_name _;
        client_max_body_size 50M;

        # 前端静态资源
        root /app/frontend/dist;
        index index.html;

        # API 反代
        location /api/ {
            proxy_pass http://backend;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto $scheme;
        }

        # 后端其他路径
        location / {
            try_files $uri $uri/ /index.html;
        }

        # 后端文档
        location /docs {
            proxy_pass http://backend;
        }
    }
}
```

### 5.2 京东云模式适配

通过环境变量 `JDYUN_MODE=true` 控制：
- 前端构建时注入 `VITE_JDYUN_MODE=true`（构建时决定）
- 后端通过 `app/core/jdyun.py` 短路数据库配置读取
- 单容器内不影响 s6 编排

---

## 6. 数据持久化

### 6.1 K8s PVC 挂载

```yaml
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: tradingagents-data
spec:
  accessModes:
    - ReadWriteOnce
  resources:
    requests:
      storage: 50Gi
---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: tradingagents
spec:
  replicas: 1
  template:
    spec:
      containers:
      - name: app
        image: tradingagents-cn-pro:v3.0
        ports:
        - containerPort: 8082
        volumeMounts:
        - name: data
          mountPath: /data/db           # MongoDB 数据
        - name: data
          mountPath: /var/lib/redis     # Redis 持久化
        - name: data
          mountPath: /app/runtime       # 标记文件 + 临时
        - name: data
          mountPath: /app/logs          # 日志
        env:
        - name: MONGODB_PASSWORD
          valueFrom:
            secretKeyRef:
              name: ta-secrets
              key: mongodb-password
        - name: TUSHARE_TOKEN
          valueFrom:
            secretKeyRef:
              name: ta-secrets
              key: tushare-token
      volumes:
      - name: data
        persistentVolumeClaim:
          claimName: tradingagents-data
```

### 6.2 Docker 本地挂载

```bash
docker run -d \
  --name tradingagents \
  -p 8082:8082 \
  -v ta-data:/data/db \
  -v ta-redis:/var/lib/redis \
  -v ta-runtime:/app/runtime \
  -v ta-logs:/app/logs \
  -e MONGODB_PASSWORD=xxx \
  -e TUSHARE_TOKEN=xxx \
  tradingagents-cn-pro:v3.0
```

---

## 7. 启动流程

### 7.1 容器启动时序

```
T+0s    容器启动，s6-overlay 作为 PID 1 运行
T+1s    init 服务完成（目录创建 + 权限修复）
T+2s    mongodb/redis 启动（并行）
T+5s    MongoDB 监听 27017
T+5s    Redis 监听 6379
T+5s    init-data 检测到服务就绪
T+10s   数据库初始化完成（首次）
T+11s   backend 启动
T+15s   uvicorn 监听 8000
T+15s   nginx 启动
T+16s   nginx 监听 8082
T+16s   容器就绪 ✅
```

### 7.2 优雅停止

```
docker stop 发送 SIGTERM
  ↓
s6-overlay 收到信号，按反序停止
  ↓
nginx 停止（关闭监听）
  ↓
backend 停止（uvicorn 处理完当前请求）
  ↓
mongodb/redis 优雅关闭
  ↓
容器退出
```

---

## 8. 健康检查

### 8.1 容器级健康检查

```dockerfile
HEALTHCHECK --interval=30s --timeout=10s --retries=3 --start-period=60s \
    CMD curl -f http://localhost:8082/api/health || exit 1
```

### 8.2 各服务独立健康检查

由 s6 通过 `finish` 脚本实现：
- MongoDB 退出码非 0 → 重启 mongodb 服务
- Backend 退出码非 0 → 重启 backend 服务
- 持续失败 3 次 → 停止整个容器

---

## 9. 开发与生产构建

### 9.1 镜像构建

```bash
# 一键构建
bash scripts/build_all_in_one.sh 3.0

# 镜像 tag
tradingagents-cn-pro:3.0.0
tradingagents-cn-pro:3-latest
```

### 9.2 构建流程

```
1. 基础镜像 python:3.11-bookworm
2. apt 安装 mongodb/redis/nginx/gosu
3. 安装 s6-overlay
4. 复制 s6 服务定义
5. 复制 Python 依赖（pip install -r requirements.txt）
6. 复制应用代码
7. 构建前端（npm run build）→ dist/
8. 复制 dist/ 到镜像
9. 配置环境变量
10. 健康检查
11. ENTRYPOINT ["/init"]
```

### 9.3 多架构支持

```bash
docker buildx build --platform linux/amd64,linux/arm64 \
  -t tradingagents-cn-pro:3.0.0 \
  -f Dockerfile.all-in-one \
  --push .
```

---

## 10. 与原 docker-compose 方案的关系

### 10.1 不废弃

- **开发环境**继续使用 `docker-compose.dev.yml`（开发时需要单独调试某个服务）
- **生产部署**使用单容器镜像（用户友好）
- 两个方案并存，按场景选择

### 10.2 数据迁移

旧方案用户升级到新方案时：
```bash
# 1. 停止旧容器
docker-compose down

# 2. 备份数据卷
docker run --rm -v ta-v3_mongodb_data:/from -v $(pwd):/to \
  alpine tar czf /to/mongo-backup.tar.gz /from

# 3. 启动新单容器，挂载同一数据卷
docker run -d \
  -v $(pwd)/mongo-backup.tar.gz:/backup.tar.gz:ro \
  tradingagents-cn-pro:3.0.0 \
  # s6 init-data 步骤检测到已初始化则跳过
```

---

## 11. 实施计划

### 11.1 文件清单

| 文件 | 说明 | 状态 |
|------|------|------|
| `deploy-all-in-one/Dockerfile` | 单容器构建文件 | ✅ 已创建 |
| `deploy-all-in-one/s6-rc.d/init/` | 初始化服务 | ✅ 已创建 |
| `deploy-all-in-one/s6-rc.d/mongodb/` | MongoDB 服务 | ✅ 已创建 |
| `deploy-all-in-one/s6-rc.d/redis/` | Redis 服务 | ✅ 已创建 |
| `deploy-all-in-one/s6-rc.d/init-data/` | 数据库初始化服务 | ✅ 已创建 |
| `deploy-all-in-one/s6-rc.d/backend/` | 后端服务 | ✅ 已创建 |
| `deploy-all-in-one/s6-rc.d/nginx/` | Nginx 服务 | ✅ 已创建 |
| `deploy-all-in-one/conf/nginx.conf` | Nginx 配置 | ✅ 已创建 |
| `deploy-all-in-one/conf/mongod.conf` | MongoDB 配置 | ✅ 已创建 |
| `deploy-all-in-one/conf/redis.conf` | Redis 配置 | ✅ 已创建 |
| `deploy-all-in-one/build.sh` | 构建脚本 | ✅ 已创建 |
| `deploy-all-in-one/run.sh` | 启动脚本 | ✅ 已创建 |
| `deploy-all-in-one/k8s/00-namespace.yaml` | K8s 命名空间 | ✅ 已创建 |
| `deploy-all-in-one/k8s/10-secret.yaml.example` | Secret 模板 | ✅ 已创建 |
| `deploy-all-in-one/k8s/20-pvc.yaml` | 持久化存储 | ✅ 已创建 |
| `deploy-all-in-one/k8s/30-deployment.yaml` | Deployment | ✅ 已创建 |
| `deploy-all-in-one/k8s/40-service.yaml` | Service + Ingress | ✅ 已创建 |
| `deploy-all-in-one/docs/quick-start.md` | 快速开始 | ✅ 已创建 |
| `deploy-all-in-one/docs/k8s-deployment.md` | K8s 部署 | ✅ 已创建 |

### 11.2 实施阶段

| 阶段 | 内容 | 验证 |
|------|------|------|
| P1 | 基础镜像 + MongoDB/Redis | 容器启动后 mongo/redis-cli 可连接 |
| P2 | + Backend + Nginx | http://localhost:8082 可见前端 |
| P3 | + 数据库初始化 | 首次启动自动建表 + 创建 admin |
| P4 | + 健康检查 + 优雅停止 | docker stop 后无残留进程 |
| P5 | + K8s 部署配置 | K8s 单 Pod 正常运行 |
| P6 | + 多架构构建 | amd64/arm64 都可拉起 |

---

## 12. 风险与缓解

| 风险 | 缓解 |
|------|------|
| 镜像体积过大 | 多阶段构建，最终镜像不含 Node.js 源码 |
| MongoDB 重启影响后端 | s6 自动重启，uvicorn 进程保留 |
| 数据丢失 | K8s 使用 ReadWriteOnce PVC，本地使用 named volume |
| 启动顺序错误 | s6 dependencies 保证 |
| 日志分散 | 统一输出到 /app/logs，符号链接到 /var/log/services/ |
| s6 学习成本 | 配置文件模板化，新服务按模板复制 |

---

## 13. 验收标准

- [ ] `docker run -p 8082:8082 tradingagents-cn-pro:3.0.0` 一条命令启动
- [ ] 首次启动自动初始化数据库（10 秒内完成）
- [ ] 非首次启动 < 16 秒就绪
- [ ] `docker stop` 后所有进程 5 秒内优雅退出
- [ ] 后端进程崩溃后 3 秒内由 s6 自动重启
- [ ] K8s 单 Pod 运行，PVC 数据持久化
- [ ] amd64 + arm64 双架构镜像
- [ ] 镜像体积 < 3 GB

---

## 14. 相关文档

- [jdyun-edition-design.md](jdyun-edition-design.md) — 京东云合作版设计
- [jdyun-branch-progress.md](jdyun-branch-progress.md) — 京东云分支进度
- [workflow-generation-architecture.md](workflow-generation-architecture.md) — 工作流生成架构
