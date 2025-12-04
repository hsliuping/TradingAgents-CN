# TradingAgents 数据库配置指南

## 📋 概述

TradingAgents现在支持MongoDB和Redis数据库，提供数据持久化存储和高性能缓存功能。

## 🚀 快速启动

### 1. 启动Docker服务

```bash
# Windows
scripts\start_services_alt_ports.bat

# Linux/Mac
scripts/start_services_alt_ports.sh
```

### 2. 安装Python依赖

```bash
pip install pymongo redis
```

### 3. 初始化数据库

```bash
python scripts/init_database.py
```

### 4. 启动Web应用

```bash
cd web
python -m streamlit run app.py
```

## 🔧 服务配置

### Docker服务端口

由于本地环境端口冲突，使用了替代端口：

| 服务 | 默认端口 | 实际端口 | 访问地址 |
|------|----------|----------|----------|
| MongoDB | 27017 | **27018** | localhost:27018 |
| Redis | 6379 | **6380** | localhost:6380 |
| Redis Commander | 8081 | **8082** | http://localhost:8082 |

### 认证信息

- **用户名**: admin
- **密码**: tradingagents123
- **数据库**: tradingagents

## 📊 数据库结构

### MongoDB集合

1. **stock_data** - 股票历史数据
   - 索引: (symbol, market_type), created_at, updated_at
   
2. **analysis_results** - 分析结果
   - 索引: (symbol, analysis_type), created_at
   
3. **user_sessions** - 用户会话
   - 索引: session_id, created_at, last_activity
   
4. **configurations** - 系统配置
   - 索引: (config_type, config_name), updated_at

### Redis缓存结构

- **键前缀**: `tradingagents:`
- **TTL配置**:
  - 美股数据: 2小时
  - A股数据: 1小时
  - 新闻数据: 4-6小时
  - 基本面数据: 12-24小时

## 🛠️ 管理工具

### Redis Commander
- 访问地址: http://localhost:8082
- 功能: Redis数据可视化管理

### 缓存管理页面
- 访问地址: http://localhost:8501 -> 缓存管理
- 功能: 缓存统计、清理、测试

## 📝 配置文件

### 环境变量 (.env)

```bash
# MongoDB配置
MONGODB_HOST=localhost
MONGODB_PORT=27018
MONGODB_USERNAME=admin
MONGODB_PASSWORD=tradingagents123
MONGODB_DATABASE=tradingagents

# Redis配置
REDIS_HOST=localhost
REDIS_PORT=6380
REDIS_PASSWORD=tradingagents123
REDIS_DB=0
```

### 默认配置 (default_config.py)

数据库配置已集成到默认配置中，支持环境变量覆盖。

## 🔍 故障排除

### 常见问题

1. **端口冲突**
   ```bash
   # 检查端口占用
   netstat -an | findstr :27018
   netstat -an | findstr :6380
   ```

2. **连接失败**
   ```bash
   # 检查Docker容器状态
   docker ps --filter "name=tradingagents-"
   
   # 查看容器日志
   docker logs tradingagents-mongodb
   docker logs tradingagents-redis
   ```

3. **权限问题**
   ```bash
   # 重启容器
   docker restart tradingagents-mongodb tradingagents-redis
   ```

### 重置数据库

```bash
# 停止并删除容器
docker stop tradingagents-mongodb tradingagents-redis tradingagents-redis-commander
docker rm tradingagents-mongodb tradingagents-redis tradingagents-redis-commander

# 删除数据卷（可选，会丢失所有数据）
docker volume rm tradingagents_mongodb_data tradingagents_redis_data

# 重新启动
scripts\start_services_alt_ports.bat
python scripts/init_database.py
```

## 📈 性能优化

### 缓存策略

1. **分层缓存**: Redis + 文件缓存
2. **智能TTL**: 根据数据类型设置不同过期时间
3. **压缩存储**: 大数据自动压缩（可配置）
4. **批量操作**: 支持批量读写

### 监控指标

- 缓存命中率
- 数据库连接数
- 内存使用量
- 响应时间

## 🔐 安全配置

### 生产环境建议

1. **修改默认密码**
2. **启用SSL/TLS**
3. **配置防火墙规则**
4. **定期备份数据**
5. **监控异常访问**

## 📚 API使用示例

### Python代码示例

```python
from tradingagents.config.database_manager import get_database_manager

# 获取数据库管理器
db_manager = get_database_manager()

# 检查数据库可用性
if db_manager.is_mongodb_available():
    print("MongoDB可用")

if db_manager.is_redis_available():
    print("Redis可用")

# 获取数据库客户端
mongodb_client = db_manager.get_mongodb_client()
redis_client = db_manager.get_redis_client()

# 获取缓存统计
stats = db_manager.get_cache_stats()
```

## 🎯 下一步计划

1. **数据同步**: 实现多实例数据同步
2. **备份策略**: 自动备份和恢复
3. **性能监控**: 集成监控仪表板
4. **集群支持**: MongoDB和Redis集群配置
5. **数据分析**: 内置数据分析工具

---

**注意**: 本配置适用于开发和测试环境。生产环境请参考安全配置章节进行相应调整。
