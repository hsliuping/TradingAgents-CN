# Docker 初始化日志查看指南

## 📝 日志位置

`docker-entrypoint.sh` 脚本的所有操作都会记录到以下位置：

### 1. Docker 容器日志（标准输出）
所有 `echo` 输出都会显示在 Docker 容器日志中。

**查看方式：**
```bash
# 查看后端容器日志（实时）
docker logs -f tradingagents-backend-pro

# 查看最近 100 行日志
docker logs --tail 100 tradingagents-backend-pro

# 查看指定时间段的日志
docker logs --since "2026-01-24T00:00:00" tradingagents-backend-pro
```

### 2. 日志文件（持久化）
初始化过程的详细日志会保存到容器内的日志文件：

**日志文件路径：** `/app/logs/docker-entrypoint.log`

**查看方式：**
```bash
# 进入容器查看
docker exec -it tradingagents-backend-pro cat /app/logs/docker-entrypoint.log

# 查看最后 50 行
docker exec -it tradingagents-backend-pro tail -n 50 /app/logs/docker-entrypoint.log

# 实时跟踪日志
docker exec -it tradingagents-backend-pro tail -f /app/logs/docker-entrypoint.log

# 如果配置了卷挂载，可以直接在宿主机查看
# 日志文件位置：./docker/logs/docker-entrypoint.log
cat ./docker/logs/docker-entrypoint.log
```

## 🔍 常见问题排查

### MongoDB 连接失败

**查看相关日志：**
```bash
# 1. 查看后端初始化日志
docker logs tradingagents-backend-pro | grep -i mongo

# 2. 查看详细日志文件
docker exec -it tradingagents-backend-pro cat /app/logs/docker-entrypoint.log | grep -i mongo

# 3. 查看 MongoDB 容器日志
docker logs tradingagents-mongodb

# 4. 检查 MongoDB 容器状态
docker ps -a | grep mongodb
```

### 配置导入失败

**查看相关日志：**
```bash
# 1. 查看初始化脚本输出
docker logs tradingagents-backend-pro | grep -A 20 "导入配置"

# 2. 查看详细日志文件
docker exec -it tradingagents-backend-pro cat /app/logs/docker-entrypoint.log | grep -A 20 "导入配置"

# 3. 手动运行初始化脚本查看详细错误
docker exec -it tradingagents-backend-pro python scripts/import_config_and_create_user.py
```

### Redis 连接失败

**查看相关日志：**
```bash
# Redis 是可选的，失败不会阻塞启动
docker logs tradingagents-backend-pro | grep -i redis
```

## 📋 日志内容说明

日志文件包含以下信息：

1. **初始化开始标记** - 首次启动时的初始化提示
2. **MongoDB 连接状态** - 连接尝试、成功/失败信息
3. **MongoDB 认证检查** - 认证系统初始化状态
4. **Redis 连接状态** - Redis 连接尝试结果
5. **配置文件查找** - 使用的配置文件路径
6. **初始化脚本输出** - `import_config_and_create_user.py` 的完整输出
7. **错误信息** - 所有错误和警告信息
8. **时间戳** - 每条日志都有时间戳

## 🛠️ 调试技巧

### 查看完整启动日志
```bash
# 查看从容器启动开始的所有日志
docker logs tradingagents-backend-pro

# 查看最近 1 小时的日志
docker logs --since 1h tradingagents-backend-pro

# 查看特定时间段的日志
docker logs --since "2026-01-24T10:00:00" --until "2026-01-24T11:00:00" tradingagents-backend-pro
```

### 实时监控日志
```bash
# 同时监控容器日志和日志文件
docker logs -f tradingagents-backend-pro &
docker exec -it tradingagents-backend-pro tail -f /app/logs/docker-entrypoint.log
```

### 导出日志用于分析
```bash
# 导出容器日志到文件
docker logs tradingagents-backend-pro > backend-startup.log 2>&1

# 导出日志文件
docker cp tradingagents-backend-pro:/app/logs/docker-entrypoint.log ./docker-entrypoint.log
```

## ⚠️ 注意事项

1. **日志文件位置**：日志文件保存在容器内的 `/app/logs/` 目录
2. **卷挂载**：如果配置了卷挂载 `./logs:/app/logs`，日志文件会持久化到宿主机
3. **日志轮转**：建议配置日志轮转，避免日志文件过大
4. **权限问题**：确保 `/app/logs` 目录有写权限

## 🔗 相关文档

- Docker Compose 配置：`docker/docker-compose.compiled.yml`
- 初始化脚本：`docker/scripts/docker-entrypoint.sh`
- 配置导入脚本：`scripts/import_config_and_create_user.py`
