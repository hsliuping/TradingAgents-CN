# 股票名称获取问题排查指南

## 问题描述

在进行市场分析时，可能会出现显示"股票代码XXXXXX"而不是实际股票名称的情况。

例如：
- ❌ 显示：`股票代码601127`
- ✅ 期望：`赛力斯`

## 问题原因

股票名称获取失败通常由以下原因导致：

### 1. 数据库中没有该股票的基础信息

**症状**：
- 日志中出现：`⚠️ 无法从统一接口解析股票名称`
- 返回的 `stock_info` 字符串中没有 "股票名称:" 字段

**原因**：
- MongoDB 中 `stock_basic_info` 集合没有该股票的数据
- 或者数据源降级到其他数据源（Tushare/AKShare/BaoStock），但这些数据源也无法获取到数据

### 2. 数据库连接问题

**症状**：
- 日志中出现数据库连接错误
- 在 Docker 环境中特别容易出现

**原因**：
- MongoDB 服务未启动
- 网络连接问题
- 配置错误（主机名、端口、认证信息）

### 3. 数据源配置问题

**症状**：
- 所有数据源都返回失败
- 日志中出现：`❌ 所有数据源都无法获取股票信息`

**原因**：
- 没有配置任何可用的数据源
- 所有配置的数据源都不可用（API 密钥失效、网络问题等）

## 解决方案

### 方案 1：检查数据库中是否有股票数据

```bash
# 连接到 MongoDB
mongo tradingagents

# 查询股票基础信息
db.stock_basic_info.findOne({code: "601127"})

# 如果没有数据，需要同步股票列表
```

### 方案 2：手动同步股票基础信息

使用后端 API 同步股票数据：

```bash
# 同步 A 股股票列表
curl -X POST http://localhost:8000/api/stocks/sync/a-shares

# 同步港股股票列表
curl -X POST http://localhost:8000/api/stocks/sync/hk-stocks

# 同步美股股票列表
curl -X POST http://localhost:8000/api/stocks/sync/us-stocks
```

或者使用前端界面：
1. 进入"系统设置" → "数据管理"
2. 点击"同步股票列表"按钮
3. 选择要同步的市场（A股/港股/美股）

### 方案 3：检查数据库连接

```bash
# 检查 MongoDB 是否运行
docker ps | grep mongodb

# 检查 MongoDB 日志
docker logs tradingagents-mongodb

# 测试 MongoDB 连接
mongo --host localhost --port 27017 -u admin -p tradingagents123
```

### 方案 4：检查数据源配置

查看 `.env` 文件中的数据源配置：

```bash
# Tushare 配置
TUSHARE_TOKEN=your_token_here

# 检查是否启用 App Cache
TA_USE_APP_CACHE=true
```

### 方案 5：查看详细日志

启用调试日志以获取更多信息：

```python
# 在 .env 文件中设置
LOG_LEVEL=DEBUG

# 或者在代码中临时启用
import logging
logging.getLogger("dataflows").setLevel(logging.DEBUG)
```

## 代码改进

我们已经在以下文件中增强了错误处理和降级逻辑：

1. `tradingagents/agents/analysts/market_analyst.py`
2. `tradingagents/agents/analysts/fundamentals_analyst.py`
3. `tradingagents/agents/analysts/china_market_analyst.py`
4. `tradingagents/agents/analysts/social_media_analyst.py`
5. `app/services/simple_analysis_service.py`

### 改进内容

#### 1. 增加详细日志

```python
logger.debug(f"📊 获取股票信息返回: {stock_info[:200] if stock_info else 'None'}...")
```

这样可以看到实际返回的内容，便于诊断问题。

#### 2. 添加降级方案

```python
if stock_info and "股票名称:" in stock_info:
    # 主方案：从字符串解析
    company_name = stock_info.split("股票名称:")[1].split("\n")[0].strip()
else:
    # 降级方案：直接从数据源管理器获取字典
    from tradingagents.dataflows.data_source_manager import get_china_stock_info_unified as get_info_dict
    info_dict = get_info_dict(ticker)
    if info_dict and info_dict.get('name'):
        company_name = info_dict['name']
```

#### 3. 更好的错误提示

```python
logger.error(f"❌ 所有方案都无法获取股票名称: {ticker}")
```

## 测试脚本

使用以下脚本测试股票名称获取：

```bash
python scripts/test_stock_name_issue.py
```

该脚本会：
1. 检查数据源配置
2. 测试多个股票代码的名称获取
3. 显示详细的调试信息

## 常见问题

### Q1: 为什么有些股票能获取名称，有些不能？

**A**: 这通常是因为：
- MongoDB 中只同步了部分股票的数据
- 某些股票是新上市的，数据源还没有更新
- 某些股票已经退市，数据源不再提供数据

**解决方法**：重新同步股票列表

### Q2: Docker 环境中经常出现这个问题怎么办？

**A**: Docker 环境中的常见问题：
1. 容器之间网络连接问题
2. MongoDB 数据卷没有正确挂载
3. 环境变量没有正确传递

**解决方法**：
```bash
# 检查容器网络
docker network inspect tradingagents-network

# 检查环境变量
docker exec tradingagents-backend env | grep MONGODB

# 重启服务
docker-compose down
docker-compose up -d
```

### Q3: 如何确认数据源是否可用？

**A**: 查看启动日志：

```
✅ MongoDB数据源可用（最高优先级）
✅ Tushare数据源可用
✅ AKShare数据源可用
✅ BaoStock数据源可用
```

如果某个数据源不可用，会显示：
```
❌ Tushare数据源不可用: 未配置 API Token
```

## 监控和预防

### 1. 定期同步股票列表

建议设置定时任务，每天同步一次股票列表：

```bash
# 添加到 crontab
0 2 * * * curl -X POST http://localhost:8000/api/stocks/sync/a-shares
```

### 2. 监控数据源状态

在系统设置中查看数据源状态，确保至少有一个数据源可用。

### 3. 检查日志

定期检查日志文件，查找警告和错误信息：

```bash
# 查找股票名称获取失败的日志
grep "无法从统一接口解析股票名称" logs/app.log

# 查找数据源错误
grep "数据源.*失败" logs/app.log
```

## 相关文件

- `tradingagents/dataflows/interface.py` - 统一数据接口
- `tradingagents/dataflows/data_source_manager.py` - 数据源管理器
- `tradingagents/dataflows/cache/app_adapter.py` - MongoDB 缓存适配器
- `app/routers/stocks.py` - 股票数据同步 API

## 更新日志

- 2025-10-28: 增强错误处理和降级逻辑
- 2025-10-28: 添加详细日志记录
- 2025-10-28: 创建测试脚本

