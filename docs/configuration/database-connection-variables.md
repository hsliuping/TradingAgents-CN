# 数据库连接环境变量说明

## 📋 概述

TradingAgents-CN Pro 支持多种方式配置数据库连接。为了简化配置和避免冗余，系统会自动从基础变量构建连接字符串。

---

## 🗄️ MongoDB 配置

### 基础变量（推荐配置）

这些是**必需**的基础配置变量：

```env
MONGODB_HOST=localhost          # MongoDB 主机地址
MONGODB_PORT=27017              # MongoDB 端口
MONGODB_USERNAME=admin          # 用户名
MONGODB_PASSWORD=password123    # 密码
MONGODB_DATABASE=tradingagents  # 数据库名称
MONGODB_AUTH_SOURCE=admin       # 认证数据库
```

### 自动构建的变量

以下变量会**自动构建**，无需手动配置：

#### 1. `MONGODB_URL` (可选)
- **用途**: 在 `tradingagents/dataflows/cache/db_cache.py` 中使用
- **自动构建**: 从 `MONGODB_HOST` 等变量自动构建
- **优先级**: 如果设置了 `MONGODB_URL` 环境变量，会优先使用
- **示例**: `mongodb://admin:password123@localhost:27017/tradingagents?authSource=admin`

#### 2. `MONGO_URI` (代码属性)
- **用途**: 在 `app/core/config.py` 中作为**属性**动态构建
- **不需要设置**: 这是一个 Python 属性，不是环境变量
- **代码位置**: `app/core/config.py` 的 `Settings.MONGO_URI` 属性

#### 3. `MONGO_DB` (代码属性)
- **用途**: 在 `app/core/config.py` 中作为**属性**返回 `MONGODB_DATABASE`
- **不需要设置**: 这是一个 Python 属性，不是环境变量
- **代码位置**: `app/core/config.py` 的 `Settings.MONGO_DB` 属性

#### 4. `MONGODB_CONNECTION_STRING` (可选)
- **用途**: 在 `tradingagents/config/` 模块中使用
- **自动构建**: 从 `MONGODB_HOST` 等变量自动构建
- **优先级**: 如果设置了此变量，会优先使用
- **示例**: `mongodb://admin:password123@localhost:27017/tradingagents?authSource=admin`

#### 5. `MONGODB_DATABASE_NAME` (可选)
- **用途**: 在某些模块中作为数据库名称
- **自动使用**: 默认使用 `MONGODB_DATABASE` 的值
- **优先级**: 如果设置了此变量，会优先使用

---

## 📦 Redis 配置

### 基础变量（推荐配置）

这些是**必需**的基础配置变量：

```env
REDIS_HOST=localhost            # Redis 主机地址
REDIS_PORT=6379                 # Redis 端口
REDIS_PASSWORD=password123      # 密码（可选）
REDIS_DB=0                      # 数据库编号
```

### 自动构建的变量

#### 1. `REDIS_URL` (可选)
- **用途**: 在 `tradingagents/dataflows/cache/db_cache.py` 中使用
- **自动构建**: 从 `REDIS_HOST` 等变量自动构建
- **优先级**: 如果设置了 `REDIS_URL` 环境变量，会优先使用
- **示例**: `redis://:password123@localhost:6379/0`

---

## 🔧 配置优先级

### MongoDB 连接字符串构建优先级

```
1. MONGODB_CONNECTION_STRING (如果设置) → 直接使用
2. MONGODB_URL (如果设置) → 直接使用
3. 从 MONGODB_HOST, MONGODB_PORT 等变量自动拼接
```

### Redis 连接字符串构建优先级

```
1. REDIS_URL (如果设置) → 直接使用
2. 从 REDIS_HOST, REDIS_PORT 等变量自动拼接
```

---

## ✅ 推荐配置方式

### 方式 1: 只配置基础变量（推荐）✅

**`.env` 文件**:
```env
# MongoDB
MONGODB_HOST=localhost
MONGODB_PORT=27017
MONGODB_USERNAME=admin
MONGODB_PASSWORD=tradingagents123
MONGODB_DATABASE=tradingagents
MONGODB_AUTH_SOURCE=admin

# Redis
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_PASSWORD=tradingagents123
REDIS_DB=0
```

**优点**:
- ✅ 配置简洁，只需维护一套变量
- ✅ 端口修改后，连接字符串自动更新
- ✅ 不会出现配置不一致的问题

### 方式 2: 使用自定义连接字符串（可选）

**`.env` 文件**:
```env
# 使用自定义连接字符串（优先级更高）
MONGODB_CONNECTION_STRING=mongodb://custom:password@custom-host:12345/customdb?authSource=admin
REDIS_URL=redis://:password@custom-host:6380/1
```

**适用场景**:
- 需要使用特殊的连接参数
- 连接到远程数据库集群
- 使用 MongoDB Atlas 等云服务

---

## 🛠️ 工具函数

系统提供了统一的工具函数来构建连接字符串：

### MongoDB 工具函数

位置: `tradingagents/config/mongodb_utils.py`

```python
from tradingagents.config.mongodb_utils import (
    build_mongodb_connection_string,
    get_mongodb_database_name,
    get_mongodb_config
)

# 构建连接字符串
conn_str = build_mongodb_connection_string()

# 获取数据库名称
db_name = get_mongodb_database_name()

# 获取完整配置
config = get_mongodb_config()
```

### Redis 工具函数

位置: `tradingagents/config/mongodb_utils.py`

```python
from tradingagents.config.mongodb_utils import build_redis_connection_string

# 构建连接字符串
redis_url = build_redis_connection_string()
```

---

## 📝 迁移指南

### 从旧配置迁移

如果你的 `.env` 文件中有以下变量：

```env
# ❌ 旧配置（冗余）
MONGODB_URL=mongodb://admin:password@localhost:27017/tradingagents?authSource=admin
MONGO_URI=mongodb://admin:password@localhost:27017/tradingagents?authSource=admin
MONGO_DB=tradingagents
REDIS_URL=redis://:password@localhost:6379/0
```

**迁移步骤**:

1. **删除或注释掉**这些变量（它们会自动构建）
2. **保留基础变量**:
   ```env
   MONGODB_HOST=localhost
   MONGODB_PORT=27017
   MONGODB_USERNAME=admin
   MONGODB_PASSWORD=password
   MONGODB_DATABASE=tradingagents
   MONGODB_AUTH_SOURCE=admin
   
   REDIS_HOST=localhost
   REDIS_PORT=6379
   REDIS_PASSWORD=password
   REDIS_DB=0
   ```

3. **重启服务**，系统会自动构建连接字符串

---

**最后更新**: 2026-01-08  
**相关文档**: 
- `tradingagents/config/mongodb_utils.py` - 工具函数实现
- `.env.example` - 配置示例

