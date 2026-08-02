# 快速开始

## 一、构建镜像

```bash
cd tradingagents-cn-pro
bash deploy-all-in-one/build.sh 3.0.0
```

构建完成后镜像大小约 2-3 GB，包含：
- Python 3.11 运行环境
- MongoDB 8.0
- Redis 7
- Nginx 1.22
- s6-overlay 进程管理
- 完整应用代码

## 二、本地启动

### 1. 设置环境变量

```bash
# 必填：MongoDB 密码
export MONGODB_PASSWORD="your-secure-password"

# 可选：Redis 密码
export REDIS_PASSWORD="your-redis-password"

# 可选：Tushare Token
export TUSHARE_TOKEN="your-tushare-token"

# 可选：OpenAI 配置
export OPENAI_API_KEY="sk-xxx"
export OPENAI_API_BASE="https://api.openai.com/v1"
export OPENAI_MODEL="gpt-4"
```

### 2. 启动容器

```bash
bash deploy-all-in-one/run.sh
```

### 3. 查看日志

```bash
bash deploy-all-in-one/run.sh --logs
```

### 4. 访问应用

打开浏览器：http://localhost:8082

默认账号：
- 用户名：`admin`
- 密码：见容器启动日志（`ADMIN_DEFAULT_PASSWORD` 环境变量）

## 三、Docker 启动

### 1. 直接 docker run

```bash
docker run -d \
  --name tradingagents \
  -p 8082:8082 \
  -v ta-mongo:/data/db \
  -v ta-redis:/var/lib/redis \
  -v ta-runtime:/app/runtime \
  -v ta-logs:/app/logs \
  -e MONGODB_PASSWORD="your-password" \
  -e TUSHARE_TOKEN="your-token" \
  tradingagents-cn-pro:3.0.0
```

### 2. 验证

```bash
# 检查容器状态
docker ps

# 查看日志
docker logs -f tradingagents

# 健康检查
curl http://localhost:8082/api/health
```

## 四、常见问题

### 启动慢

首次启动需要：
- 初始化 MongoDB 认证系统（~3s）
- 创建 admin 用户（~1s）
- 导入配置数据（~3s）
- 启动 Backend（~5s）
- 启动 Nginx（~1s）

总时间：约 15-30 秒。

### 端口被占用

修改宿主机端口：

```bash
HOST_PORT=9082 bash run.sh
```

### 数据持久化

容器使用 4 个数据卷：
- `ta-mongo` - MongoDB 数据
- `ta-redis` - Redis 数据
- `ta-runtime` - 标记文件、临时文件
- `ta-logs` - 应用日志

删除容器不会丢失数据。如需完全清理：

```bash
bash run.sh --clean
```

### 重置管理员密码

```bash
# 进入容器
docker exec -it tradingagents /bin/bash

# 执行密码重置脚本
python3 scripts/reset_admin_password.py
```

## 五、京东云模式

启用京东云合作版模式：

```bash
docker run -d \
  --name tradingagents \
  -p 8082:8082 \
  -v ta-mongo:/data/db \
  -v ta-redis:/var/lib/redis \
  -v ta-runtime:/app/runtime \
  -v ta-logs:/app/logs \
  -e JDYUN_MODE=true \
  -e MONGODB_PASSWORD="xxx" \
  -e OPENAI_API_KEY="your-jd-api-key" \
  -e OPENAI_API_BASE="https://modelservice.jdcloud.com/v1" \
  -e OPENAI_MODEL="GLM-5" \
  -e TUSHARE_TOKEN="your-tushare-token" \
  tradingagents-cn-pro:3.0.0
```

京东云模式下：
- License 验证跳过
- Provider/数据源 API 只读
- 配置通过环境变量注入
- LLM 限速（429 重试 + 降并发）

## 六、下一步

- 查看 [K8s 部署文档](k8s-deployment.md) 部署到生产环境
- 查看 [设计文档](../../../docs/05-design/v3.0/all-in-one-deployment.md) 了解架构细节
