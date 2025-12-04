# 新闻数据系统指南

## 概述

TradingAgents-CN 新闻数据系统提供了完整的股票新闻数据获取、存储、分析和查询功能。系统支持多数据源新闻聚合、智能情绪分析、重要性评估和高级查询功能。

## 系统架构

### 三层架构设计

```
┌─────────────────────────────────────────────────────────────┐
│                    RESTful API 层                           │
│  app/routers/news_data.py - 新闻数据API接口                 │
└─────────────────────────────────────────────────────────────┘
                              │
┌─────────────────────────────────────────────────────────────┐
│                    业务服务层                               │
│  app/services/news_data_service.py - 新闻数据管理服务       │
│  app/worker/news_data_sync_service.py - 新闻数据同步服务    │
└─────────────────────────────────────────────────────────────┘
                              │
┌─────────────────────────────────────────────────────────────┐
│                    数据提供层                               │
│  AKShare Provider - 东方财富、CCTV财经、新浪财经新闻       │
│  Tushare Provider - Tushare新闻数据                        │
│  Realtime Provider - 实时新闻聚合                          │
└─────────────────────────────────────────────────────────────┘
```

## 核心功能

### 1. 多数据源新闻获取

#### AKShare 新闻源
- **个股新闻**: 东方财富个股新闻
- **市场新闻**: CCTV财经、新浪财经新闻
- **数据字段**: 标题、内容、摘要、链接、来源、作者、发布时间

#### Tushare 新闻源
- **个股新闻**: Tushare个股新闻
- **市场新闻**: Tushare市场新闻
- **数据字段**: 标题、内容、来源、发布时间、重要性

#### 实时新闻聚合
- **多源整合**: 整合多个新闻源数据
- **去重处理**: 基于标题和URL的智能去重
- **实时更新**: 支持实时新闻数据获取

### 2. 智能数据分析

#### 情绪分析
```python
# 情绪分析结果
sentiment_analysis = {
    "positive": ["利好", "上涨", "增长", "盈利", "突破"],
    "negative": ["利空", "下跌", "亏损", "风险", "暴跌"],
    "neutral": ["公告", "会议", "发布", "披露", "变更"]
}
```

#### 重要性评估
- **高重要性**: 业绩公告、重大事项、监管公告
- **中重要性**: 行业新闻、市场分析、投资建议
- **低重要性**: 一般新闻、市场传闻、其他信息

#### 新闻分类
- **公司公告**: company_announcement
- **市场新闻**: market_news
- **政策新闻**: policy_news
- **行业新闻**: industry_news
- **其他新闻**: other

### 3. 高性能存储

#### MongoDB 集合设计
```javascript
// stock_news 集合结构
{
  "_id": ObjectId,
  "symbol": "000001",                    // 股票代码
  "symbols": ["000001", "000002"],       // 多股票代码
  "title": "新闻标题",                   // 新闻标题
  "content": "新闻内容",                 // 新闻内容
  "summary": "新闻摘要",                 // 新闻摘要
  "url": "https://...",                  // 新闻链接
  "source": "东方财富",                  // 新闻来源
  "author": "记者姓名",                  // 作者
  "publish_time": ISODate,               // 发布时间
  "category": "company_announcement",    // 新闻类别
  "sentiment": "positive",               // 情绪分析
  "sentiment_score": 0.8,                // 情绪得分
  "importance": "high",                  // 重要性
  "keywords": ["关键词1", "关键词2"],    // 关键词
  "data_source": "akshare",              // 数据源
  "region": "CN",                        // 地区
  "created_at": ISODate,                 // 创建时间
  "updated_at": ISODate                  // 更新时间
}
```

#### 优化索引设计
```javascript
// 15个优化索引
db.stock_news.createIndex({"url": 1, "title": 1, "publish_time": 1}, {unique: true})  // 唯一约束
db.stock_news.createIndex({"symbol": 1})                                               // 股票代码
db.stock_news.createIndex({"symbols": 1})                                              // 多股票代码
db.stock_news.createIndex({"publish_time": -1})                                        // 发布时间
db.stock_news.createIndex({"symbol": 1, "publish_time": -1})                          // 股票时间复合
db.stock_news.createIndex({"symbols": 1, "publish_time": -1})                         // 多股票时间复合
db.stock_news.createIndex({"category": 1})                                             // 新闻类别
db.stock_news.createIndex({"sentiment": 1})                                            // 情绪分析
db.stock_news.createIndex({"importance": 1})                                           // 重要性
db.stock_news.createIndex({"data_source": 1})                                          // 数据源
db.stock_news.createIndex({"symbol": 1, "category": 1, "publish_time": -1})           // 股票类别时间
db.stock_news.createIndex({"sentiment": 1, "importance": 1, "publish_time": -1})      // 情绪重要性时间
db.stock_news.createIndex({"title": "text", "content": "text", "summary": "text"})    // 全文搜索
db.stock_news.createIndex({"created_at": -1})                                          // 创建时间
```

## API 接口

### 1. 新闻查询接口

#### 查询股票新闻
```http
GET /api/news-data/query/000001?hours_back=24&limit=20&category=company_announcement
```

#### 高级查询
```http
POST /api/news-data/query
Content-Type: application/json

{
  "symbol": "000001",
  "start_time": "2024-01-01T00:00:00Z",
  "end_time": "2024-12-31T23:59:59Z",
  "category": "company_announcement",
  "sentiment": "positive",
  "importance": "high",
  "limit": 50
}
```

#### 获取最新新闻
```http
GET /api/news-data/latest?symbol=000001&limit=10&hours_back=24
```

#### 全文搜索
```http
GET /api/news-data/search?query=银行&symbol=000001&limit=20
```

### 2. 新闻统计接口

#### 获取统计信息
```http
GET /api/news-data/statistics?symbol=000001&days_back=7
```

响应示例：
```json
{
  "success": true,
  "data": {
    "symbol": "000001",
    "days_back": 7,
    "statistics": {
      "total_count": 25,
      "sentiment_distribution": {
        "positive": 10,
        "negative": 5,
        "neutral": 10
      },
      "importance_distribution": {
        "high": 8,
        "medium": 12,
        "low": 5
      },
      "categories": {
        "company_announcement": 15,
        "market_news": 8,
        "industry_news": 2
      },
      "sources": {
        "东方财富": 20,
        "新浪财经": 3,
        "CCTV财经": 2
      }
    }
  }
}
```

### 3. 新闻同步接口

#### 启动同步任务
```http
POST /api/news-data/sync/start
Content-Type: application/json

{
  "symbol": "000001",
  "data_sources": ["akshare", "tushare"],
  "hours_back": 24,
  "max_news_per_source": 50
}
```

#### 同步单只股票
```http
POST /api/news-data/sync/single?symbol=000001&hours_back=24&max_news_per_source=50
```

### 4. 管理接口

#### 清理过期新闻
```http
DELETE /api/news-data/cleanup?days_to_keep=90
```

#### 健康检查
```http
GET /api/news-data/health
```

## 使用示例

### Python SDK 使用

#### 1. 获取新闻数据服务
```python
from app.services.news_data_service import get_news_data_service, NewsQueryParams

# 获取服务实例
service = await get_news_data_service()
```

#### 2. 查询新闻数据
```python
# 查询最新新闻
latest_news = await service.get_latest_news(symbol="000001", limit=10)

# 高级查询
params = NewsQueryParams(
    symbol="000001",
    start_time=datetime.utcnow() - timedelta(days=7),
    category="company_announcement",
    sentiment="positive",
    limit=20
)
news_list = await service.query_news(params)

# 全文搜索
search_results = await service.search_news("银行", symbol="000001", limit=10)
```

#### 3. 新闻数据同步
```python
from app.worker.news_data_sync_service import get_news_data_sync_service

# 获取同步服务
sync_service = await get_news_data_sync_service()

# 同步股票新闻
stats = await sync_service.sync_stock_news(
    symbol="000001",
    data_sources=["akshare"],
    hours_back=24,
    max_news_per_source=50
)

print(f"同步完成: {stats.successful_saves} 条成功保存")
```

## 配置说明

### 环境变量配置
```bash
# .env 文件
TUSHARE_TOKEN=your_tushare_token_here
AKSHARE_TIMEOUT=60
MONGODB_URL=mongodb://localhost:27017
MONGODB_DB=tradingagents
```

### 数据源配置
```python
# 数据源优先级配置
DATA_SOURCE_PRIORITY = {
    "akshare": 1,    # 优先使用AKShare
    "tushare": 2,    # 其次使用Tushare
    "realtime": 3    # 最后使用实时聚合
}

# 同步配置
SYNC_CONFIG = {
    "default_hours_back": 24,
    "max_news_per_source": 50,
    "batch_size": 100,
    "retry_times": 3
}
```

## 性能优化

### 1. 数据库优化
- **索引优化**: 15个专门优化的索引，支持毫秒级查询
- **批量操作**: 使用`bulk_write`进行高效批量插入
- **连接池**: MongoDB连接池优化，支持高并发访问

### 2. 缓存策略
- **查询缓存**: 热点查询结果缓存
- **数据缓存**: 频繁访问的新闻数据缓存
- **统计缓存**: 统计信息定期缓存更新

### 3. 并发处理
- **异步处理**: 全异步架构，支持高并发
- **批量同步**: 支持多股票并发同步
- **限流控制**: API调用限流，避免数据源限制

## 监控和日志

### 日志级别
- **INFO**: 正常操作日志
- **WARNING**: 警告信息（部分数据获取失败等）
- **ERROR**: 错误信息（数据库连接失败、API调用异常等）

### 关键指标监控
- **同步成功率**: 新闻数据同步成功率
- **查询性能**: 数据库查询响应时间
- **数据质量**: 新闻数据完整性和准确性
- **系统健康**: 服务可用性和稳定性

## 故障排除

### 常见问题

1. **数据库连接失败**
   - 检查MongoDB服务状态
   - 验证连接字符串配置
   - 确认网络连接正常

2. **新闻数据获取失败**
   - 检查数据源API可用性
   - 验证API Token配置
   - 确认网络访问权限

3. **查询性能慢**
   - 检查索引使用情况
   - 优化查询条件
   - 考虑增加缓存

4. **同步数据重复**
   - 检查唯一索引配置
   - 验证去重逻辑
   - 清理重复数据

## 扩展开发

### 添加新数据源
1. 继承`BaseProvider`类
2. 实现`get_stock_news`方法
3. 添加数据标准化逻辑
4. 注册到同步服务

### 自定义分析算法
1. 扩展情绪分析词典
2. 优化重要性评估规则
3. 添加新的分类标准
4. 实现自定义分析指标

---

## 总结

TradingAgents-CN 新闻数据系统提供了完整的新闻数据管理解决方案，支持多数据源聚合、智能分析、高效存储和灵活查询。系统经过充分测试，性能优秀，可靠性高，是股票投资分析的重要工具。
