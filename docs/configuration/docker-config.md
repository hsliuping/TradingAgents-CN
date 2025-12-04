# 🐳 Docker环境配置指南

## 📋 概述

本文档详细介绍TradingAgents-CN在Docker环境中的配置方法，包括环境变量设置、服务配置、网络配置和数据持久化配置。

## 🎯 Docker配置特点

### 与本地部署的区别

| 配置项 | 本地部署 | Docker部署 |
|-------|---------|-----------|
| **数据库连接** | localhost | 容器服务名 |
| **端口配置** | 直接端口 | 端口映射 |
| **文件路径** | 绝对路径 | 容器内路径 |
| **环境隔离** | 系统环境 | 容器环境 |

### 配置优势

- ✅ **环境一致性**: 开发、测试、生产环境完全一致
- ✅ **自动服务发现**: 容器间自动DNS解析
- ✅ **网络隔离**: 安全的内部网络通信
- ✅ **数据持久化**: 数据卷保证数据安全

## 🔧 环境变量配置

### 基础环境变量

```bash
# === Docker环境基础配置 ===
# 应用配置
APP_NAME=TradingAgents-CN
APP_VERSION=0.1.7
APP_ENV=production

# 服务端口配置
WEB_PORT=8501
MONGODB_PORT=27017
REDIS_PORT=6379
MONGO_EXPRESS_PORT=8081
REDIS_COMMANDER_PORT=8082
```

### 数据库连接配置

```bash
# === 数据库连接配置 ===
# MongoDB配置 (使用容器服务名)
MONGODB_URL=mongodb://mongodb:27017/tradingagents
MONGODB_HOST=mongodb
MONGODB_PORT=27017
MONGODB_DATABASE=tradingagents

# MongoDB认证 (生产环境)
MONGODB_USERNAME=admin
MONGODB_PASSWORD=${MONGO_PASSWORD}
MONGODB_AUTH_SOURCE=admin

# Redis配置 (使用容器服务名)
REDIS_URL=redis://redis:6379
REDIS_HOST=redis
REDIS_PORT=6379
REDIS_DB=0

# Redis认证 (生产环境)
REDIS_PASSWORD=${REDIS_PASSWORD}
```

### LLM服务配置

```bash
# === LLM模型配置 ===
# DeepSeek配置
DEEPSEEK_API_KEY=${DEEPSEEK_API_KEY}
DEEPSEEK_ENABLED=true
DEEPSEEK_MODEL=deepseek-chat
DEEPSEEK_BASE_URL=https://api.deepseek.com

# 阿里百炼配置
QWEN_API_KEY=${QWEN_API_KEY}
QWEN_ENABLED=true
QWEN_MODEL=qwen-plus

# Google AI配置
GOOGLE_API_KEY=${GOOGLE_API_KEY}
GOOGLE_ENABLED=true
GOOGLE_MODEL=gemini-1.5-pro

# 模型路由配置
LLM_SMART_ROUTING=true
LLM_PRIORITY_ORDER=deepseek,qwen,gemini
```

## 📊 Docker Compose配置

### 主应用服务配置

```yaml
# docker-compose.yml
version: '3.8'

services:
  web:
    build: .
    container_name: TradingAgents-web
    ports:
      - "${WEB_PORT:-8501}:8501"
    environment:
      # 数据库连接
      - MONGODB_URL=mongodb://mongodb:27017/tradingagents
      - REDIS_URL=redis://redis:6379
      
      # LLM配置
      - DEEPSEEK_API_KEY=${DEEPSEEK_API_KEY}
      - QWEN_API_KEY=${QWEN_API_KEY}
      - GOOGLE_API_KEY=${GOOGLE_API_KEY}
      
      # 应用配置
      - APP_ENV=docker
      - EXPORT_ENABLED=true
      - EXPORT_DEFAULT_FORMAT=word,pdf
    volumes:
      # 配置文件
      - .env:/app/.env
      
      # 开发环境代码同步 (可选)
      - ./web:/app/web
      - ./tradingagents:/app/tradingagents
      
      # 导出文件存储
      - ./exports:/app/exports
    depends_on:
      - mongodb
      - redis
    networks:
      - tradingagents
    restart: unless-stopped
```

### 数据库服务配置

```yaml
  mongodb:
    image: mongo:4.4
    container_name: TradingAgents-mongodb
    ports:
      - "${MONGODB_PORT:-27017}:27017"
    environment:
      - MONGO_INITDB_DATABASE=tradingagents
      # 生产环境认证
      - MONGO_INITDB_ROOT_USERNAME=${MONGO_USERNAME:-admin}
      - MONGO_INITDB_ROOT_PASSWORD=${MONGO_PASSWORD}
    volumes:
      - mongodb_data:/data/db
      - ./scripts/mongo-init.js:/docker-entrypoint-initdb.d/mongo-init.js:ro
    networks:
      - tradingagents
    restart: unless-stopped

  redis:
    image: redis:6-alpine
    container_name: TradingAgents-redis
    ports:
      - "${REDIS_PORT:-6379}:6379"
    command: redis-server --appendonly yes --requirepass ${REDIS_PASSWORD:-}
    volumes:
      - redis_data:/data
    networks:
      - tradingagents
    restart: unless-stopped
```

### 管理界面配置

```yaml
  mongo-express:
    image: mongo-express
    container_name: TradingAgents-mongo-express
    ports:
      - "${MONGO_EXPRESS_PORT:-8081}:8081"
    environment:
      - ME_CONFIG_MONGODB_SERVER=mongodb
      - ME_CONFIG_MONGODB_PORT=27017
      - ME_CONFIG_MONGODB_ADMINUSERNAME=${MONGO_USERNAME:-admin}
      - ME_CONFIG_MONGODB_ADMINPASSWORD=${MONGO_PASSWORD}
      - ME_CONFIG_BASICAUTH_USERNAME=${ADMIN_USERNAME:-admin}
      - ME_CONFIG_BASICAUTH_PASSWORD=${ADMIN_PASSWORD}
    depends_on:
      - mongodb
    networks:
      - tradingagents
    restart: unless-stopped

  redis-commander:
    image: rediscommander/redis-commander
    container_name: TradingAgents-redis-commander
    ports:
      - "${REDIS_COMMANDER_PORT:-8082}:8081"
    environment:
      - REDIS_HOSTS=local:redis:6379:0:${REDIS_PASSWORD:-}
    depends_on:
      - redis
    networks:
      - tradingagents
    restart: unless-stopped
```

## 🌐 网络配置

### 网络定义

```yaml
networks:
  tradingagents:
    driver: bridge
    name: tradingagents_network
    ipam:
      config:
        - subnet: 172.20.0.0/16
```

### 服务发现

```bash
# 容器内服务访问
# MongoDB: mongodb:27017
# Redis: redis:6379
# Web应用: web:8501

# 外部访问
# Web界面: localhost:8501
# MongoDB: localhost:27017
# Redis: localhost:6379
# Mongo Express: localhost:8081
# Redis Commander: localhost:8082
```

## 💾 数据持久化配置

### 数据卷定义

```yaml
volumes:
  mongodb_data:
    driver: local
    driver_opts:
      type: none
      o: bind
      device: ${DATA_PATH:-./data}/mongodb
  
  redis_data:
    driver: local
    driver_opts:
      type: none
      o: bind
      device: ${DATA_PATH:-./data}/redis
```

### 备份配置

```bash
# === 数据备份配置 ===
# 备份路径
BACKUP_PATH=./backups
BACKUP_RETENTION_DAYS=30

# 自动备份
ENABLE_AUTO_BACKUP=true
BACKUP_SCHEDULE="0 2 * * *"  # 每天凌晨2点

# 备份压缩
BACKUP_COMPRESS=true
BACKUP_ENCRYPTION=false
```

## 🔒 安全配置

### 生产环境安全

```bash
# === 安全配置 ===
# 管理员认证
ADMIN_USERNAME=admin
ADMIN_PASSWORD=${ADMIN_PASSWORD}

# 数据库认证
MONGO_USERNAME=admin
MONGO_PASSWORD=${MONGO_PASSWORD}
REDIS_PASSWORD=${REDIS_PASSWORD}

# API密钥加密
ENCRYPT_API_KEYS=true
ENCRYPTION_KEY=${ENCRYPTION_KEY}

# 网络安全
ENABLE_FIREWALL=true
ALLOWED_IPS=127.0.0.1,10.0.0.0/8,172.16.0.0/12,192.168.0.0/16
```

### SSL/TLS配置

```yaml
# HTTPS配置 (可选)
  nginx:
    image: nginx:alpine
    ports:
      - "443:443"
      - "80:80"
    volumes:
      - ./nginx.conf:/etc/nginx/nginx.conf
      - ./ssl:/etc/nginx/ssl
    depends_on:
      - web
```

## 📊 监控配置

### 健康检查

```yaml
healthcheck:
  test: ["CMD", "curl", "-f", "http://localhost:8501/health"]
  interval: 30s
  timeout: 10s
  retries: 3
  start_period: 40s
```

### 日志配置

```yaml
logging:
  driver: "json-file"
  options:
    max-size: "10m"
    max-file: "3"
```

## 🚀 部署配置

### 开发环境

```bash
# 开发环境配置
APP_ENV=development
DEBUG=true
LOG_LEVEL=DEBUG
ENABLE_HOT_RELOAD=true
```

### 生产环境

```bash
# 生产环境配置
APP_ENV=production
DEBUG=false
LOG_LEVEL=INFO
ENABLE_HOT_RELOAD=false

# 性能配置
WORKERS=4
MAX_MEMORY=4G
MAX_CPU=2.0
```

## 🔧 故障排除

### 常见问题

1. **服务连接失败**
   ```bash
   # 检查网络连接
   docker exec TradingAgents-web ping mongodb
   docker exec TradingAgents-web ping redis
   ```

2. **数据持久化问题**
   ```bash
   # 检查数据卷
   docker volume ls
   docker volume inspect mongodb_data
   ```

3. **环境变量问题**
   ```bash
   # 检查环境变量
   docker exec TradingAgents-web env | grep MONGODB
   ```

---

*最后更新: 2025-07-13*  
*版本: cn-0.1.7*  
*贡献者: [@breeze303](https://github.com/breeze303)*
